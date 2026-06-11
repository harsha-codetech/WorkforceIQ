from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.assessments.forms import (
    AssessmentForm,
    AssignAssessmentForm,
    GradeForm,
    QuestionForm,
    SubmissionForm,
)
from app.extensions import db
from app.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAssignment,
    AssessmentAttempt,
    AssessmentQuestion,
    User,
)
from app.utils.badges import evaluate_badges
from app.utils.notify import notify
from app.utils.security import (
    ensure_can_view,
    log_action,
    role_required,
    visible_employee_ids,
)
from app.utils.storage import file_url, save_file

assessments_bp = Blueprint("assessments", __name__)


@assessments_bp.route("/")
@login_required
def index():
    if current_user.is_admin:
        rows = Assessment.query.order_by(Assessment.created_at.desc()).all()
        return render_template("assessments/list_admin.html", assessments=rows)
    assigned = (
        db.session.query(AssessmentAssignment, Assessment)
        .join(Assessment, AssessmentAssignment.assessment_id == Assessment.id)
        .filter(AssessmentAssignment.employee_id == current_user.id)
        .all()
    )
    attempts = {}
    for a in AssessmentAttempt.query.filter_by(employee_id=current_user.id).all():
        attempts.setdefault(a.assessment_id, []).append(a)
    return render_template("assessments/list.html", assigned=assigned, attempts=attempts)


@assessments_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create():
    form = AssessmentForm()
    if form.validate_on_submit():
        assessment = Assessment(
            title=form.title.data.strip(),
            description=form.description.data,
            type=form.type.data,
            grading_mode="auto" if form.type.data == "mcq" else "manual",
            domain=form.domain.data or None,
            total_marks=form.total_marks.data,
            pass_percentage=form.pass_percentage.data,
            duration_minutes=form.duration_minutes.data,
            max_attempts=form.max_attempts.data,
            scheduled_at=form.scheduled_at.data,
            created_by=current_user.id,
        )
        db.session.add(assessment)
        db.session.commit()
        log_action("create_assessment", "assessment", assessment.id)
        flash("Assessment created.", "success")
        return redirect(url_for("assessments.manage", assessment_id=assessment.id))
    return render_template("assessments/form.html", form=form)


@assessments_bp.route("/<int:assessment_id>/manage", methods=["GET", "POST"])
@role_required("admin")
def manage(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if not assessment:
        abort(404)
    form = QuestionForm()
    if assessment.type == "mcq" and form.validate_on_submit():
        db.session.add(
            AssessmentQuestion(
                assessment_id=assessment.id,
                question_text=form.question_text.data,
                option_a=form.option_a.data,
                option_b=form.option_b.data,
                option_c=form.option_c.data,
                option_d=form.option_d.data,
                correct_option=form.correct_option.data,
                marks=form.marks.data,
            )
        )
        db.session.commit()
        flash("Question added.", "success")
        return redirect(url_for("assessments.manage", assessment_id=assessment.id))
    return render_template(
        "assessments/manage.html", assessment=assessment, form=form
    )


@assessments_bp.route("/<int:assessment_id>/assign", methods=["GET", "POST"])
@role_required("admin")
def assign(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if not assessment:
        abort(404)
    form = AssignAssessmentForm()
    employees = User.query.filter_by(
        organization_id=current_user.organization_id, role="employee", status="active"
    ).order_by(User.full_name).all()
    form.employees.choices = [(e.id, f"{e.full_name} ({e.email})") for e in employees]
    if form.validate_on_submit():
        count = 0
        for emp_id in form.employees.data:
            if AssessmentAssignment.query.filter_by(
                assessment_id=assessment_id, employee_id=emp_id
            ).first():
                continue
            db.session.add(
                AssessmentAssignment(
                    assessment_id=assessment_id,
                    employee_id=emp_id,
                    assigned_by=current_user.id,
                    due_date=assessment.scheduled_at,
                )
            )
            notify(
                emp_id, "upcoming_assessment", "New assessment assigned",
                f"You have been assigned '{assessment.title}'.",
                entity_type="assessment", entity_id=assessment.id, send_mail=True,
            )
            count += 1
        db.session.commit()
        flash(f"Assigned to {count} employee(s).", "success")
        return redirect(url_for("assessments.manage", assessment_id=assessment_id))
    return render_template("assessments/assign.html", form=form, assessment=assessment)


def _next_attempt_number(assessment_id, employee_id):
    last = (
        AssessmentAttempt.query.filter_by(
            assessment_id=assessment_id, employee_id=employee_id
        )
        .order_by(AssessmentAttempt.attempt_number.desc())
        .first()
    )
    return (last.attempt_number + 1) if last else 1


@assessments_bp.route("/<int:assessment_id>/take", methods=["GET", "POST"])
@login_required
def take(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if not assessment:
        abort(404)
    assignment = AssessmentAssignment.query.filter_by(
        assessment_id=assessment_id, employee_id=current_user.id
    ).first()
    if not assignment:
        abort(403)

    used = AssessmentAttempt.query.filter_by(
        assessment_id=assessment_id, employee_id=current_user.id
    ).count()
    if used >= assessment.max_attempts:
        flash("You have used all available attempts.", "warning")
        return redirect(url_for("assessments.index"))

    if assessment.type == "mcq":
        return _take_mcq(assessment, assignment)
    return _take_submission(assessment, assignment)


def _take_mcq(assessment, assignment):
    questions = assessment.questions
    if request.method == "POST":
        if not questions:
            flash("This assessment has no questions yet.", "danger")
            return redirect(url_for("assessments.index"))
        attempt = AssessmentAttempt(
            assessment_id=assessment.id,
            employee_id=current_user.id,
            attempt_number=_next_attempt_number(assessment.id, current_user.id),
            started_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
            status="graded",
        )
        db.session.add(attempt)
        db.session.flush()

        earned = 0
        total = 0
        for q in questions:
            total += q.marks
            chosen = request.form.get(f"q_{q.id}")
            correct = chosen == q.correct_option
            awarded = q.marks if correct else 0
            earned += awarded
            db.session.add(
                AssessmentAnswer(
                    attempt_id=attempt.id,
                    question_id=q.id,
                    selected_option=chosen if chosen in ("A", "B", "C", "D") else None,
                    is_correct=correct,
                    marks_awarded=awarded,
                )
            )
        pct = round(earned / total * 100, 2) if total else 0
        attempt.score = earned
        attempt.percentage = pct
        attempt.result = "pass" if pct >= float(assessment.pass_percentage) else "fail"
        attempt.time_taken_seconds = 0
        assignment.status = "graded"
        db.session.commit()
        evaluate_badges(current_user.id)
        flash(f"Submitted. Score: {pct}% ({attempt.result}).", "success")
        return redirect(url_for("assessments.result", attempt_id=attempt.id))

    return render_template("assessments/take_mcq.html", assessment=assessment, questions=questions)


def _take_submission(assessment, assignment):
    form = SubmissionForm()
    if form.validate_on_submit():
        if not form.submission_url.data and not form.upload.data:
            flash("Provide a link or upload a file.", "danger")
            return render_template(
                "assessments/take_submission.html", assessment=assessment, form=form
            )
        file_key = save_file(form.upload.data, prefix="submissions") if form.upload.data else None
        attempt = AssessmentAttempt(
            assessment_id=assessment.id,
            employee_id=current_user.id,
            attempt_number=_next_attempt_number(assessment.id, current_user.id),
            started_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
            status="submitted",
            submission_url=form.submission_url.data or None,
            submission_file_key=file_key,
        )
        db.session.add(attempt)
        assignment.status = "submitted"
        db.session.commit()
        flash("Submission received. Awaiting manual grading.", "success")
        return redirect(url_for("assessments.index"))
    return render_template(
        "assessments/take_submission.html", assessment=assessment, form=form
    )


@assessments_bp.route("/grading")
@role_required("admin")
def grading_queue():
    rows = (
        AssessmentAttempt.query.filter_by(status="submitted")
        .order_by(AssessmentAttempt.submitted_at)
        .all()
    )
    return render_template("assessments/grading.html", attempts=rows)


@assessments_bp.route("/attempt/<int:attempt_id>/grade", methods=["GET", "POST"])
@role_required("admin")
def grade(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if not attempt:
        abort(404)
    form = GradeForm()
    if form.validate_on_submit():
        total = attempt.assessment.total_marks or 100
        score = min(float(form.score.data), total)
        pct = round(score / total * 100, 2) if total else 0
        attempt.score = score
        attempt.percentage = pct
        attempt.result = "pass" if pct >= float(attempt.assessment.pass_percentage) else "fail"
        attempt.feedback = form.feedback.data
        attempt.status = "graded"
        attempt.graded_by = current_user.id
        attempt.graded_at = datetime.utcnow()
        assignment = AssessmentAssignment.query.filter_by(
            assessment_id=attempt.assessment_id, employee_id=attempt.employee_id
        ).first()
        if assignment:
            assignment.status = "graded"
        notify(
            attempt.employee_id, "assessment_graded", "Assessment graded",
            f"'{attempt.assessment.title}' was graded: {pct}% ({attempt.result}).",
            entity_type="assessment", entity_id=attempt.assessment_id, send_mail=True,
        )
        db.session.commit()
        evaluate_badges(attempt.employee_id)
        flash("Grade saved.", "success")
        return redirect(url_for("assessments.grading_queue"))
    return render_template(
        "assessments/grade.html",
        form=form,
        attempt=attempt,
        download_url=file_url(attempt.submission_file_key),
    )


@assessments_bp.route("/result/<int:attempt_id>")
@login_required
def result(attempt_id):
    attempt = db.session.get(AssessmentAttempt, attempt_id)
    if not attempt:
        abort(404)
    ensure_can_view(current_user, attempt.employee_id)
    return render_template("assessments/result.html", attempt=attempt)


@assessments_bp.route("/<int:assessment_id>/analytics")
@login_required
def analytics(assessment_id):
    assessment = db.session.get(Assessment, assessment_id)
    if not assessment:
        abort(404)
    allowed = set(visible_employee_ids(current_user))
    attempts = (
        AssessmentAttempt.query.filter_by(assessment_id=assessment_id)
        .filter(AssessmentAttempt.employee_id.in_(allowed))
        .order_by(AssessmentAttempt.employee_id, AssessmentAttempt.attempt_number)
        .all()
    )
    by_emp = {}
    for a in attempts:
        by_emp.setdefault(a.employee_id, []).append(a)
    return render_template(
        "assessments/analytics.html", assessment=assessment, by_emp=by_emp,
        users={u.id: u for u in User.query.filter(User.id.in_(by_emp.keys())).all()}
        if by_emp else {},
    )

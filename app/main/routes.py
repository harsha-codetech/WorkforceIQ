from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.main.forms import DepartmentForm, UserForm
from app.models import (
    Assessment,
    AssessmentAttempt,
    Department,
    EmployeeBadge,
    Goal,
    LearningProgress,
    ModuleAssignment,
    PerformanceScore,
    User,
)
from app.utils.scoring import compute_growth_score
from app.utils.security import ensure_can_view, log_action, role_required, visible_employee_ids

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        return _admin_dashboard()
    if current_user.is_manager:
        return _manager_dashboard()
    return _employee_dashboard(current_user.id)


def _employee_dashboard(employee_id):
    ensure_can_view(current_user, employee_id)
    employee = db.session.get(User, employee_id)
    score = compute_growth_score(employee_id, "monthly", persist=False)

    assignments = ModuleAssignment.query.filter_by(employee_id=employee_id).count()
    completed = LearningProgress.query.filter_by(
        employee_id=employee_id, status="completed"
    ).count()
    pending = max(assignments - completed, 0)
    total_hours = round(
        (
            db.session.query(func.coalesce(func.sum(LearningProgress.watch_seconds), 0))
            .filter_by(employee_id=employee_id)
            .scalar()
            or 0
        )
        / 3600,
        1,
    )

    weekly_goals = Goal.query.filter_by(
        employee_id=employee_id, type="weekly"
    ).order_by(Goal.due_date).limit(5).all()
    monthly_goals = Goal.query.filter_by(
        employee_id=employee_id, type="monthly"
    ).order_by(Goal.due_date).limit(5).all()
    badges = (
        EmployeeBadge.query.filter_by(employee_id=employee_id)
        .order_by(EmployeeBadge.awarded_at.desc())
        .all()
    )
    return render_template(
        "dashboard/employee.html",
        employee=employee,
        score=score,
        assignments=assignments,
        completed=completed,
        pending=pending,
        total_hours=total_hours,
        weekly_goals=weekly_goals,
        monthly_goals=monthly_goals,
        badges=badges,
    )


def _manager_dashboard():
    ids = [i for i in visible_employee_ids(current_user) if i != current_user.id]
    team = User.query.filter(User.id.in_(ids)).all() if ids else []
    scores = []
    for member in team:
        scores.append((member, compute_growth_score(member.id, "monthly", persist=False)))
    avg = round(
        sum(s["overall"] for _, s in scores) / len(scores), 1
    ) if scores else 0
    return render_template(
        "dashboard/manager.html", team=team, scores=scores, team_avg=avg
    )


def _admin_dashboard():
    org_id = current_user.organization_id
    emp_count = User.query.filter_by(organization_id=org_id, role="employee").count()
    mgr_count = User.query.filter_by(organization_id=org_id, role="manager").count()
    module_count = LearningProgress.query.count()
    assessment_count = Assessment.query.count()
    dept_count = Department.query.filter_by(organization_id=org_id).count()
    recent_scores = (
        PerformanceScore.query.order_by(PerformanceScore.calculated_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "dashboard/admin.html",
        emp_count=emp_count,
        mgr_count=mgr_count,
        module_count=module_count,
        assessment_count=assessment_count,
        dept_count=dept_count,
        recent_scores=recent_scores,
    )


# ----- Employee profile (drill-down) ----------------------------------- #
@main_bp.route("/employees/<int:employee_id>")
@login_required
def employee_profile(employee_id):
    return _employee_dashboard(employee_id)


# ----- Admin: departments ---------------------------------------------- #
@main_bp.route("/admin/departments", methods=["GET", "POST"])
@role_required("admin")
def departments():
    form = DepartmentForm()
    if form.validate_on_submit():
        exists = Department.query.filter_by(
            organization_id=current_user.organization_id, name=form.name.data.strip()
        ).first()
        if exists:
            flash("A department with that name already exists.", "warning")
        else:
            db.session.add(
                Department(
                    organization_id=current_user.organization_id,
                    name=form.name.data.strip(),
                )
            )
            db.session.commit()
            flash("Department created.", "success")
        return redirect(url_for("main.departments"))
    rows = Department.query.filter_by(
        organization_id=current_user.organization_id
    ).order_by(Department.name).all()
    return render_template("admin/departments.html", form=form, departments=rows)


# ----- Admin: users ----------------------------------------------------- #
def _populate_user_choices(form):
    org_id = current_user.organization_id
    depts = Department.query.filter_by(organization_id=org_id).order_by(Department.name).all()
    managers = User.query.filter_by(organization_id=org_id, role="manager").all()
    form.department_id.choices = [(0, "— None —")] + [(d.id, d.name) for d in depts]
    form.manager_id.choices = [(0, "— None —")] + [(m.id, m.full_name) for m in managers]


@main_bp.route("/admin/users")
@role_required("admin")
def users():
    rows = (
        User.query.filter_by(organization_id=current_user.organization_id)
        .order_by(User.role, User.full_name)
        .all()
    )
    return render_template("admin/users.html", users=rows)


@main_bp.route("/admin/users/new", methods=["GET", "POST"])
@role_required("admin")
def user_new():
    form = UserForm()
    _populate_user_choices(form)
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash("Email already registered.", "warning")
            return render_template("admin/user_form.html", form=form, mode="new")
        if not form.password.data:
            flash("Password is required for new users.", "warning")
            return render_template("admin/user_form.html", form=form, mode="new")
        user = User(
            organization_id=current_user.organization_id,
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            role=form.role.data,
            department_id=form.department_id.data or None,
            manager_id=form.manager_id.data or None,
            status=form.status.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        log_action("create_user", "user", user.id)
        flash("User created.", "success")
        return redirect(url_for("main.users"))
    return render_template("admin/user_form.html", form=form, mode="new")


@main_bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user or user.organization_id != current_user.organization_id:
        abort(404)
    form = UserForm(obj=user)
    _populate_user_choices(form)
    if request.method == "GET":
        form.department_id.data = user.department_id or 0
        form.manager_id.data = user.manager_id or 0
    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.email = form.email.data.lower().strip()
        user.role = form.role.data
        user.department_id = form.department_id.data or None
        user.manager_id = form.manager_id.data or None
        user.status = form.status.data
        if form.password.data:
            user.set_password(form.password.data)
        db.session.commit()
        log_action("update_user", "user", user.id)
        flash("User updated.", "success")
        return redirect(url_for("main.users"))
    return render_template("admin/user_form.html", form=form, mode="edit", user=user)

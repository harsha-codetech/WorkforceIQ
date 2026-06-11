import re
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.learning.forms import AssignModuleForm, ModuleForm
from app.models import (
    LearningModule,
    LearningProgress,
    ModuleAssignment,
    User,
)
from app.utils.badges import evaluate_badges
from app.utils.notify import notify
from app.utils.storage import file_url, save_file
from app.utils.security import log_action, role_required

learning_bp = Blueprint("learning", __name__)

YT_RE = re.compile(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})")


def youtube_id(url):
    if not url:
        return None
    m = YT_RE.search(url)
    return m.group(1) if m else None


@learning_bp.route("/")
@login_required
def catalog():
    if current_user.is_admin:
        modules = LearningModule.query.order_by(LearningModule.created_at.desc()).all()
        return render_template("learning/catalog_admin.html", modules=modules)

    assigned = (
        db.session.query(ModuleAssignment, LearningModule)
        .join(LearningModule, ModuleAssignment.module_id == LearningModule.id)
        .filter(ModuleAssignment.employee_id == current_user.id)
        .all()
    )
    progress = {
        p.module_id: p
        for p in LearningProgress.query.filter_by(employee_id=current_user.id).all()
    }
    return render_template("learning/catalog.html", assigned=assigned, progress=progress)


@learning_bp.route("/modules/new", methods=["GET", "POST"])
@role_required("admin")
def module_new():
    form = ModuleForm()
    if form.validate_on_submit():
        ctype = form.content_type.data
        content_url = None
        file_key = None
        if ctype == "youtube":
            if not youtube_id(form.content_url.data):
                flash("Enter a valid YouTube URL.", "danger")
                return render_template("learning/module_form.html", form=form, mode="new")
            content_url = form.content_url.data.strip()
        else:
            if not form.upload.data:
                flash("A file upload is required for this content type.", "danger")
                return render_template("learning/module_form.html", form=form, mode="new")
            file_key = save_file(form.upload.data, prefix="modules")

        module = LearningModule(
            title=form.title.data.strip(),
            description=form.description.data,
            category=form.category.data,
            domain=form.domain.data,
            content_type=ctype,
            content_url=content_url,
            file_key=file_key,
            duration_minutes=form.duration_minutes.data,
            difficulty=form.difficulty.data,
            created_by=current_user.id,
        )
        db.session.add(module)
        db.session.commit()
        log_action("create_module", "learning_module", module.id)
        flash("Module created.", "success")
        return redirect(url_for("learning.module_detail", module_id=module.id))
    return render_template("learning/module_form.html", form=form, mode="new")


@learning_bp.route("/modules/<int:module_id>")
@login_required
def module_detail(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module:
        abort(404)

    progress = None
    if current_user.is_employee:
        assigned = ModuleAssignment.query.filter_by(
            module_id=module_id, employee_id=current_user.id
        ).first()
        if not assigned:
            abort(403)
        progress = LearningProgress.query.filter_by(
            employee_id=current_user.id, module_id=module_id
        ).first()
        if not progress:
            progress = LearningProgress(
                employee_id=current_user.id, module_id=module_id, status="in_progress",
                started_at=datetime.utcnow(), last_activity_at=datetime.utcnow(),
            )
            db.session.add(progress)
            assigned.status = "in_progress"
            db.session.commit()

    return render_template(
        "learning/module_detail.html",
        module=module,
        progress=progress,
        yt_id=youtube_id(module.content_url),
        download_url=file_url(module.file_key),
    )


@learning_bp.route("/modules/<int:module_id>/complete", methods=["POST"])
@login_required
def mark_complete(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module or module.content_type == "youtube":
        abort(400)
    assigned = ModuleAssignment.query.filter_by(
        module_id=module_id, employee_id=current_user.id
    ).first()
    if not assigned:
        abort(403)
    progress = LearningProgress.query.filter_by(
        employee_id=current_user.id, module_id=module_id
    ).first()
    if not progress:
        progress = LearningProgress(employee_id=current_user.id, module_id=module_id)
        db.session.add(progress)
    progress.is_completed = True
    progress.status = "completed"
    progress.watch_percentage = 100
    progress.completed_at = datetime.utcnow()
    progress.last_activity_at = datetime.utcnow()
    assigned.status = "completed"
    db.session.commit()
    evaluate_badges(current_user.id)
    flash("Module marked as complete.", "success")
    return redirect(url_for("learning.module_detail", module_id=module_id))


@learning_bp.route("/modules/<int:module_id>/assign", methods=["GET", "POST"])
@role_required("admin")
def assign(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module:
        abort(404)
    form = AssignModuleForm()
    employees = User.query.filter_by(
        organization_id=current_user.organization_id, role="employee", status="active"
    ).order_by(User.full_name).all()
    form.employees.choices = [(e.id, f"{e.full_name} ({e.email})") for e in employees]
    if form.validate_on_submit():
        count = 0
        for emp_id in form.employees.data:
            if ModuleAssignment.query.filter_by(
                module_id=module_id, employee_id=emp_id
            ).first():
                continue
            db.session.add(
                ModuleAssignment(
                    module_id=module_id, employee_id=emp_id, assigned_by=current_user.id
                )
            )
            notify(
                emp_id, "new_module", "New learning module assigned",
                f"You have been assigned '{module.title}'.",
                entity_type="learning_module", entity_id=module.id, send_mail=True,
            )
            count += 1
        db.session.commit()
        flash(f"Assigned to {count} employee(s).", "success")
        return redirect(url_for("learning.module_detail", module_id=module_id))
    return render_template("learning/assign.html", form=form, module=module)

import re
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.learning.forms import AssignModuleForm, DomainForm, ModuleForm, ResourceForm
from app.models import (
    Domain, LearningModule, LearningProgress, ModuleAssignment,
    ModuleResource, ResourceProgress, User,
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


def _ensure_assignment(module_id, employee_id):
    a = ModuleAssignment.query.filter_by(module_id=module_id, employee_id=employee_id).first()
    if not a:
        a = ModuleAssignment(
            module_id=module_id, employee_id=employee_id, assigned_by=employee_id
        )
        db.session.add(a)
        db.session.flush()
    return a


# ── Learning home / catalog ──────────────────────────────────────────────────

@learning_bp.route("/")
@login_required
def catalog():
    if current_user.is_admin:
        modules = LearningModule.query.order_by(LearningModule.created_at.desc()).all()
        domains = Domain.query.filter_by(is_active=True).order_by(Domain.name).all()
        return render_template("learning/catalog_admin.html", modules=modules, domains=domains)

    emp_id = current_user.id
    progress_map = {
        p.module_id: p
        for p in LearningProgress.query.filter_by(employee_id=emp_id).all()
    }
    assigned_ids = {
        a.module_id
        for a in ModuleAssignment.query.filter_by(employee_id=emp_id).all()
    }

    in_progress_rows = (
        db.session.query(LearningProgress, LearningModule)
        .join(LearningModule, LearningProgress.module_id == LearningModule.id)
        .filter(LearningProgress.employee_id == emp_id, LearningProgress.status == "in_progress")
        .order_by(LearningProgress.last_activity_at.desc())
        .limit(6)
        .all()
    )

    recently_completed = (
        db.session.query(LearningProgress, LearningModule)
        .join(LearningModule, LearningProgress.module_id == LearningModule.id)
        .filter(LearningProgress.employee_id == emp_id, LearningProgress.status == "completed")
        .order_by(LearningProgress.completed_at.desc())
        .limit(4)
        .all()
    )

    total_completed = sum(1 for p in progress_map.values() if p.status == "completed")
    total_hours = round(
        (db.session.query(func.coalesce(func.sum(LearningProgress.watch_seconds), 0))
         .filter_by(employee_id=emp_id).scalar() or 0) / 3600, 1
    )
    total_assigned = len(assigned_ids)

    active_domains = Domain.query.filter_by(is_active=True).order_by(Domain.name).all()
    domain_stats = []
    for d in active_domains:
        mods = LearningModule.query.filter_by(domain_id=d.id, is_active=True).all()
        if not mods:
            continue
        done = sum(1 for m in mods if progress_map.get(m.id) and progress_map[m.id].status == "completed")
        pct = round(done / len(mods) * 100) if mods else 0
        domain_stats.append({
            "domain": d, "total": len(mods), "done": done, "pct": pct,
            "thumbnail_url": file_url(d.thumbnail_key) if d.thumbnail_key else None,
        })

    return render_template(
        "learning/home.html",
        in_progress=in_progress_rows,
        recently_completed=recently_completed,
        total_completed=total_completed,
        total_hours=total_hours,
        total_assigned=total_assigned,
        domain_stats=domain_stats,
        progress_map=progress_map,
    )


# ── Domain browser ───────────────────────────────────────────────────────────

@learning_bp.route("/domains/")
@login_required
def domains():
    all_domains = Domain.query.filter_by(is_active=True).order_by(Domain.name).all()
    emp_id = current_user.id if current_user.is_employee else None
    progress_map = {}
    if emp_id:
        progress_map = {
            p.module_id: p
            for p in LearningProgress.query.filter_by(employee_id=emp_id).all()
        }

    domain_cards = []
    for d in all_domains:
        mods = LearningModule.query.filter_by(domain_id=d.id, is_active=True).all()
        total = len(mods)
        done = sum(1 for m in mods if progress_map.get(m.id) and progress_map[m.id].status == "completed") if emp_id else 0
        pct = round(done / total * 100) if total else 0
        total_mins = sum(m.duration_minutes or 0 for m in mods)
        domain_cards.append({
            "domain": d, "total": total, "done": done, "pct": pct,
            "total_hours": round(total_mins / 60, 1),
            "thumbnail_url": file_url(d.thumbnail_key) if d.thumbnail_key else None,
        })

    return render_template("learning/domain_list.html", domain_cards=domain_cards)


@learning_bp.route("/domains/<int:domain_id>")
@login_required
def domain_detail(domain_id):
    domain = db.session.get(Domain, domain_id)
    if not domain or not domain.is_active:
        abort(404)

    modules = (
        LearningModule.query.filter_by(domain_id=domain_id, is_active=True)
        .order_by(LearningModule.created_at.asc())
        .all()
    )
    emp_id = current_user.id
    progress_map = {
        p.module_id: p
        for p in LearningProgress.query.filter(
            LearningProgress.employee_id == emp_id,
            LearningProgress.module_id.in_([m.id for m in modules])
        ).all()
    } if modules else {}

    total_mins = sum(m.duration_minutes or 0 for m in modules)
    total_completed = sum(1 for m in modules if progress_map.get(m.id) and progress_map[m.id].status == "completed")
    pct = round(total_completed / len(modules) * 100) if modules else 0

    module_cards = []
    for m in modules:
        p = progress_map.get(m.id)
        module_cards.append({
            "module": m,
            "progress": p,
            "pct": float(p.watch_percentage) if p else 0,
            "status": p.status if p else "not_started",
            "thumbnail_url": file_url(m.thumbnail_key) if m.thumbnail_key else None,
        })

    return render_template(
        "learning/domain_detail.html",
        domain=domain,
        banner_url=file_url(domain.banner_image_key) if domain.banner_image_key else None,
        modules=module_cards,
        total_hours=round(total_mins / 60, 1),
        total_completed=total_completed,
        pct=pct,
    )


@learning_bp.route("/domains/new", methods=["GET", "POST"])
@role_required("admin")
def domain_new():
    form = DomainForm()
    if form.validate_on_submit():
        slug = re.sub(r"[^a-z0-9]+", "-", form.name.data.lower().strip()).strip("-")
        base = slug
        i = 1
        while Domain.query.filter_by(slug=slug).first():
            slug = f"{base}-{i}"
            i += 1
        d = Domain(
            name=form.name.data.strip(), slug=slug,
            description=form.description.data, created_by=current_user.id,
        )
        if form.banner_image.data:
            d.banner_image_key = save_file(form.banner_image.data, prefix="domains/banners")
        if form.thumbnail.data:
            d.thumbnail_key = save_file(form.thumbnail.data, prefix="domains/thumbnails")
        db.session.add(d)
        db.session.commit()
        flash("Domain created.", "success")
        return redirect(url_for("learning.domain_detail", domain_id=d.id))
    return render_template("learning/domain_form.html", form=form, mode="new", domain=None)


@learning_bp.route("/domains/<int:domain_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def domain_edit(domain_id):
    domain = db.session.get(Domain, domain_id)
    if not domain:
        abort(404)
    form = DomainForm(obj=domain)
    if form.validate_on_submit():
        domain.name = form.name.data.strip()
        domain.description = form.description.data
        if form.banner_image.data:
            domain.banner_image_key = save_file(form.banner_image.data, prefix="domains/banners")
        if form.thumbnail.data:
            domain.thumbnail_key = save_file(form.thumbnail.data, prefix="domains/thumbnails")
        db.session.commit()
        flash("Domain updated.", "success")
        return redirect(url_for("learning.domain_detail", domain_id=domain.id))
    return render_template("learning/domain_form.html", form=form, mode="edit", domain=domain)


@learning_bp.route("/domains/<int:domain_id>/archive", methods=["POST"])
@role_required("admin")
def domain_archive(domain_id):
    domain = db.session.get(Domain, domain_id)
    if not domain:
        abort(404)
    domain.is_active = False
    db.session.commit()
    flash("Domain archived.", "info")
    return redirect(url_for("learning.domains"))


# ── Module create ─────────────────────────────────────────────────────────────

@learning_bp.route("/modules/new", methods=["GET", "POST"])
@role_required("admin")
def module_new():
    form = ModuleForm()
    form.domain_id.choices = [(0, "— No domain —")] + [
        (d.id, d.name)
        for d in Domain.query.filter_by(is_active=True).order_by(Domain.name).all()
    ]
    if form.validate_on_submit():
        ctype = form.content_type.data
        content_url = file_key = thumbnail_key = None
        if ctype == "youtube":
            if not youtube_id(form.content_url.data):
                flash("Enter a valid YouTube URL.", "danger")
                return render_template("learning/module_form.html", form=form, mode="new")
            content_url = form.content_url.data.strip()
        elif form.upload.data:
            file_key = save_file(form.upload.data, prefix="modules")
        if form.thumbnail.data:
            thumbnail_key = save_file(form.thumbnail.data, prefix="modules/thumbnails")

        module = LearningModule(
            title=form.title.data.strip(),
            description=form.description.data,
            category=form.category.data,
            domain=form.domain.data,
            domain_id=form.domain_id.data or None,
            content_type=ctype,
            content_url=content_url,
            file_key=file_key,
            thumbnail_key=thumbnail_key,
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


# ── Module viewer ─────────────────────────────────────────────────────────────

@learning_bp.route("/modules/<int:module_id>")
@login_required
def module_detail(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module:
        abort(404)

    progress = None
    resource_progress_map = {}

    if not current_user.is_admin:
        assignment = _ensure_assignment(module_id, current_user.id)
        progress = LearningProgress.query.filter_by(
            employee_id=current_user.id, module_id=module_id
        ).first()
        if not progress:
            progress = LearningProgress(
                employee_id=current_user.id, module_id=module_id, status="in_progress",
                started_at=datetime.utcnow(), last_activity_at=datetime.utcnow(),
            )
            db.session.add(progress)
            assignment.status = "in_progress"
        db.session.commit()

    resources = ModuleResource.query.filter_by(module_id=module_id).order_by(
        ModuleResource.display_order
    ).all()

    if resources and not current_user.is_admin:
        rp_rows = ResourceProgress.query.filter(
            ResourceProgress.employee_id == current_user.id,
            ResourceProgress.resource_id.in_([r.id for r in resources]),
        ).all()
        resource_progress_map = {rp.resource_id: rp for rp in rp_rows}

    active_resource = None
    active_rid = request.args.get("resource", type=int)
    if resources:
        if active_rid:
            active_resource = next((r for r in resources if r.id == active_rid), resources[0])
        else:
            active_resource = resources[0]

    yt_id = download_url = None
    if active_resource:
        if active_resource.resource_type == "youtube":
            yt_id = youtube_id(active_resource.video_url)
        elif active_resource.file_key:
            download_url = file_url(active_resource.file_key)
        elif active_resource.video_url:
            download_url = active_resource.video_url
    elif not resources:
        yt_id = youtube_id(module.content_url)
        download_url = file_url(module.file_key)

    siblings = []
    if module.domain_id:
        siblings = (
            LearningModule.query.filter_by(domain_id=module.domain_id, is_active=True)
            .filter(LearningModule.id != module_id)
            .order_by(LearningModule.created_at)
            .limit(5)
            .all()
        )

    return render_template(
        "learning/module_viewer.html",
        module=module,
        progress=progress,
        resources=resources,
        active_resource=active_resource,
        resource_progress_map=resource_progress_map,
        yt_id=yt_id,
        download_url=download_url,
        siblings=siblings,
    )


@learning_bp.route("/modules/<int:module_id>/complete", methods=["POST"])
@login_required
def mark_complete(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module:
        abort(404)
    assignment = _ensure_assignment(module_id, current_user.id)
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
    assignment.status = "completed"
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
            if ModuleAssignment.query.filter_by(module_id=module_id, employee_id=emp_id).first():
                continue
            db.session.add(ModuleAssignment(
                module_id=module_id, employee_id=emp_id, assigned_by=current_user.id
            ))
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


# ── Module resources ──────────────────────────────────────────────────────────

@learning_bp.route("/modules/<int:module_id>/resources/new", methods=["GET", "POST"])
@role_required("admin")
def resource_new(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module:
        abort(404)
    form = ResourceForm()
    if form.validate_on_submit():
        rtype = form.resource_type.data
        video_url = file_key = None
        if rtype in ("youtube", "link"):
            video_url = form.video_url.data.strip() if form.video_url.data else None
        elif form.upload.data:
            file_key = save_file(form.upload.data, prefix="resources")

        max_order = (
            db.session.query(func.max(ModuleResource.display_order))
            .filter_by(module_id=module_id).scalar() or 0
        )
        resource = ModuleResource(
            module_id=module_id,
            title=form.title.data.strip(),
            resource_type=rtype,
            video_url=video_url,
            file_key=file_key,
            duration_minutes=form.duration_minutes.data,
            display_order=max_order + 1,
        )
        db.session.add(resource)
        db.session.commit()
        flash("Resource added.", "success")
        return redirect(url_for("learning.module_detail", module_id=module_id))
    return render_template("learning/resource_form.html", form=form, module=module)


@learning_bp.route("/modules/<int:module_id>/resources/<int:resource_id>/delete", methods=["POST"])
@role_required("admin")
def resource_delete(module_id, resource_id):
    resource = db.session.get(ModuleResource, resource_id)
    if not resource or resource.module_id != module_id:
        abort(404)
    db.session.delete(resource)
    db.session.commit()
    flash("Resource removed.", "info")
    return redirect(url_for("learning.module_detail", module_id=module_id))

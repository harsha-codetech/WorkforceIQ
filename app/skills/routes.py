from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import EmployeeSkill, Skill, SkillHistory, User
from app.skills.forms import EmployeeSkillForm, SkillCatalogForm
from app.utils.security import ensure_can_view, role_required, visible_employee_ids

skills_bp = Blueprint("skills", __name__)


@skills_bp.route("/")
@login_required
def matrix():
    if current_user.is_employee:
        return redirect(url_for("skills.employee_matrix", employee_id=current_user.id))

    ids = [i for i in visible_employee_ids(current_user) if i != current_user.id] or \
        visible_employee_ids(current_user)
    employees = User.query.filter(User.id.in_(ids), User.role == "employee").order_by(
        User.full_name
    ).all()
    skills = Skill.query.order_by(Skill.name).all()
    grid = {}
    for es in EmployeeSkill.query.filter(EmployeeSkill.employee_id.in_(ids)).all():
        grid[(es.employee_id, es.skill_id)] = es.level
    return render_template(
        "skills/matrix.html", employees=employees, skills=skills, grid=grid
    )


@skills_bp.route("/employee/<int:employee_id>", methods=["GET", "POST"])
@login_required
def employee_matrix(employee_id):
    ensure_can_view(current_user, employee_id)
    employee = db.session.get(User, employee_id)
    if not employee:
        abort(404)
    can_edit = current_user.id == employee_id or current_user.is_admin

    form = EmployeeSkillForm()
    form.skill_id.choices = [(s.id, s.name) for s in Skill.query.order_by(Skill.name).all()]
    if can_edit and form.validate_on_submit():
        es = EmployeeSkill.query.filter_by(
            employee_id=employee_id, skill_id=form.skill_id.data
        ).first()
        if es:
            if es.level != form.level.data:
                es.level = form.level.data
                db.session.add(
                    SkillHistory(
                        employee_id=employee_id, skill_id=form.skill_id.data,
                        level=form.level.data,
                    )
                )
        else:
            db.session.add(
                EmployeeSkill(
                    employee_id=employee_id, skill_id=form.skill_id.data,
                    level=form.level.data,
                )
            )
            db.session.add(
                SkillHistory(
                    employee_id=employee_id, skill_id=form.skill_id.data,
                    level=form.level.data,
                )
            )
        db.session.commit()
        flash("Skill saved.", "success")
        return redirect(url_for("skills.employee_matrix", employee_id=employee_id))

    rows = (
        db.session.query(EmployeeSkill, Skill)
        .join(Skill, EmployeeSkill.skill_id == Skill.id)
        .filter(EmployeeSkill.employee_id == employee_id)
        .order_by(Skill.name)
        .all()
    )
    return render_template(
        "skills/employee.html", employee=employee, rows=rows, form=form, can_edit=can_edit
    )


@skills_bp.route("/catalog", methods=["GET", "POST"])
@role_required("admin")
def catalog():
    form = SkillCatalogForm()
    if form.validate_on_submit():
        if Skill.query.filter_by(name=form.name.data.strip()).first():
            flash("That skill already exists.", "warning")
        else:
            db.session.add(
                Skill(name=form.name.data.strip(), domain=form.domain.data or None)
            )
            db.session.commit()
            flash("Skill added to catalog.", "success")
        return redirect(url_for("skills.catalog"))
    skills = Skill.query.order_by(Skill.name).all()
    return render_template("skills/catalog.html", form=form, skills=skills)

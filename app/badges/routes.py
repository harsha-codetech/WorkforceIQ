from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Badge, EmployeeBadge, User
from app.utils.badges import evaluate_badges
from app.utils.scoring import compute_growth_score
from app.utils.security import ensure_can_view

badges_bp = Blueprint("badges", __name__)


def _earned_detail(employee_id):
    rows = (
        db.session.query(EmployeeBadge, Badge)
        .join(Badge, EmployeeBadge.badge_id == Badge.id)
        .filter(EmployeeBadge.employee_id == employee_id)
        .order_by(EmployeeBadge.awarded_at.desc())
        .all()
    )
    score = compute_growth_score(employee_id, "monthly", persist=False)
    comp = score["components"]
    detail = []
    for eb, badge in rows:
        stats = _badge_stats(badge.name, comp, employee_id)
        detail.append({"eb": eb, "badge": badge, "stats": stats})
    return detail


def _badge_stats(name, comp, employee_id):
    from app.models import EmployeeSkill, LearningProgress
    if name == "Learning Champion":
        done = LearningProgress.query.filter_by(employee_id=employee_id, status="completed").count()
        return [f"Modules completed: {done}", f"Learning score: {comp['learning']}"]
    if name == "Assessment Master":
        return [f"Assessment score: {comp['assessment']}%", "Threshold: 85%"]
    if name == "Goal Achiever":
        return [f"Goal achievement: {comp['goal']}%", "Threshold: 80%"]
    if name == "Skill Builder":
        adv = EmployeeSkill.query.filter(
            EmployeeSkill.employee_id == employee_id,
            EmployeeSkill.level.in_(["advanced", "expert"]),
        ).count()
        return [f"Advanced/expert skills: {adv}", "Threshold: 3"]
    if name == "Consistency Award":
        return [f"Consistency score: {comp['consistency']}%", "Threshold: 80%"]
    return []


@badges_bp.route("/")
@login_required
def index():
    catalog = Badge.query.order_by(Badge.name).all()
    if current_user.is_employee:
        earned_map = {
            eb.badge_id: eb
            for eb in EmployeeBadge.query.filter_by(employee_id=current_user.id).all()
        }
        earned_ids = set(earned_map.keys())
        score = compute_growth_score(current_user.id, "monthly", persist=False)
        comp = score["components"]
        badge_details = {}
        for b in catalog:
            if b.id in earned_map:
                eb = earned_map[b.id]
                badge_details[b.id] = {
                    "awarded_at": eb.awarded_at,
                    "stats": _badge_stats(b.name, comp, current_user.id),
                }
        return render_template(
            "badges/index.html",
            catalog=catalog,
            earned_ids=earned_ids,
            badge_details=badge_details,
        )

    counts = dict(
        db.session.query(EmployeeBadge.badge_id, func.count(EmployeeBadge.id))
        .group_by(EmployeeBadge.badge_id)
        .all()
    )
    return render_template("badges/overview.html", catalog=catalog, counts=counts)


@badges_bp.route("/employee/<int:employee_id>")
@login_required
def employee_badges(employee_id):
    ensure_can_view(current_user, employee_id)
    employee = db.session.get(User, employee_id)
    detail = _earned_detail(employee_id)
    return render_template("badges/employee.html", employee=employee, detail=detail)


@badges_bp.route("/refresh", methods=["POST"])
@login_required
def refresh():
    if current_user.is_employee:
        evaluate_badges(current_user.id)
    return redirect(url_for("badges.index"))

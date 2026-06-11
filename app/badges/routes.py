from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Badge, EmployeeBadge, User
from app.utils.badges import evaluate_badges
from app.utils.security import ensure_can_view

badges_bp = Blueprint("badges", __name__)


@badges_bp.route("/")
@login_required
def index():
    catalog = Badge.query.order_by(Badge.name).all()
    if current_user.is_employee:
        earned_ids = {
            eb.badge_id
            for eb in EmployeeBadge.query.filter_by(employee_id=current_user.id).all()
        }
        return render_template(
            "badges/index.html", catalog=catalog, earned_ids=earned_ids
        )

    # admin / manager: award counts per badge
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
    earned = (
        db.session.query(EmployeeBadge, Badge)
        .join(Badge, EmployeeBadge.badge_id == Badge.id)
        .filter(EmployeeBadge.employee_id == employee_id)
        .order_by(EmployeeBadge.awarded_at.desc())
        .all()
    )
    return render_template("badges/employee.html", employee=employee, earned=earned)


@badges_bp.route("/refresh", methods=["POST"])
@login_required
def refresh():
    if current_user.is_employee:
        evaluate_badges(current_user.id)
    return redirect(url_for("badges.index"))

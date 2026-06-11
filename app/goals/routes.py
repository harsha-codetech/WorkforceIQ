from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.goals.forms import GoalForm
from app.models import Goal, User
from app.utils.badges import evaluate_badges
from app.utils.security import ensure_can_view

goals_bp = Blueprint("goals", __name__)

VALID_STATUS = {"pending", "in_progress", "completed", "missed"}


@goals_bp.route("/")
@login_required
def index():
    employee_id = request.args.get("employee_id", type=int) or current_user.id
    ensure_can_view(current_user, employee_id)
    employee = db.session.get(User, employee_id)
    weekly = Goal.query.filter_by(employee_id=employee_id, type="weekly").order_by(
        Goal.due_date.desc()
    ).all()
    monthly = Goal.query.filter_by(employee_id=employee_id, type="monthly").order_by(
        Goal.due_date.desc()
    ).all()
    stats = _goal_stats(employee_id)
    return render_template(
        "goals/index.html",
        weekly=weekly,
        monthly=monthly,
        employee=employee,
        stats=stats,
        can_edit=(employee_id == current_user.id),
    )


def _goal_stats(employee_id):
    total = Goal.query.filter_by(employee_id=employee_id).count()
    completed = Goal.query.filter_by(employee_id=employee_id, status="completed").count()
    missed = Goal.query.filter_by(employee_id=employee_id, status="missed").count()
    rate = round(completed / total * 100, 1) if total else 0
    return {"total": total, "completed": completed, "missed": missed, "rate": rate}


@goals_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if not current_user.is_employee:
        abort(403)
    form = GoalForm()
    if form.validate_on_submit():
        db.session.add(
            Goal(
                employee_id=current_user.id,
                title=form.title.data.strip(),
                description=form.description.data,
                type=form.type.data,
                start_date=form.start_date.data,
                due_date=form.due_date.data,
                status="pending",
            )
        )
        db.session.commit()
        flash("Goal created.", "success")
        return redirect(url_for("goals.index"))
    return render_template("goals/form.html", form=form)


@goals_bp.route("/<int:goal_id>/status", methods=["POST"])
@login_required
def update_status(goal_id):
    goal = db.session.get(Goal, goal_id)
    if not goal or goal.employee_id != current_user.id:
        abort(403)
    status = request.form.get("status")
    if status not in VALID_STATUS:
        abort(400)
    goal.status = status
    goal.completed_at = datetime.utcnow() if status == "completed" else None
    db.session.commit()
    if status == "completed":
        evaluate_badges(current_user.id)
    flash("Goal updated.", "success")
    return redirect(url_for("goals.index"))


@goals_bp.route("/<int:goal_id>/delete", methods=["POST"])
@login_required
def delete(goal_id):
    goal = db.session.get(Goal, goal_id)
    if not goal or goal.employee_id != current_user.id:
        abort(403)
    db.session.delete(goal)
    db.session.commit()
    flash("Goal deleted.", "info")
    return redirect(url_for("goals.index"))

from datetime import date, datetime

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import (
    AssessmentAttempt,
    LearningActivity,
    LearningModule,
    LearningProgress,
    ModuleAssignment,
)
from app.utils.badges import evaluate_badges
from app.utils.scoring import compute_growth_score
from app.utils.security import ensure_can_view

api_bp = Blueprint("api", __name__)


def _touch_activity(employee_id, minutes=1):
    today = date.today()
    row = LearningActivity.query.filter_by(
        employee_id=employee_id, activity_date=today
    ).first()
    if not row:
        row = LearningActivity(employee_id=employee_id, activity_date=today, active_minutes=0)
        db.session.add(row)
    row.active_minutes = (row.active_minutes or 0) + minutes


@api_bp.route("/learning/<int:module_id>/progress", methods=["POST"])
@login_required
def update_progress(module_id):
    module = db.session.get(LearningModule, module_id)
    if not module or module.content_type != "youtube":
        abort(400)
    assigned = ModuleAssignment.query.filter_by(
        module_id=module_id, employee_id=current_user.id
    ).first()
    if not assigned:
        abort(403)

    data = request.get_json(silent=True) or {}
    try:
        pct = max(0.0, min(100.0, float(data.get("percentage", 0))))
        watched = max(0, int(data.get("watched_seconds", 0)))
    except (TypeError, ValueError):
        abort(400)

    progress = LearningProgress.query.filter_by(
        employee_id=current_user.id, module_id=module_id
    ).first()
    if not progress:
        progress = LearningProgress(
            employee_id=current_user.id, module_id=module_id,
            started_at=datetime.utcnow(),
        )
        db.session.add(progress)

    progress.watch_percentage = max(float(progress.watch_percentage or 0), pct)
    progress.watch_seconds = max(progress.watch_seconds or 0, watched)
    progress.last_activity_at = datetime.utcnow()
    newly_completed = False
    if progress.watch_percentage >= 90 and progress.status != "completed":
        progress.status = "completed"
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        assigned.status = "completed"
        newly_completed = True
    elif progress.status == "not_started":
        progress.status = "in_progress"
        assigned.status = "in_progress"

    _touch_activity(current_user.id)
    db.session.commit()
    if newly_completed:
        evaluate_badges(current_user.id)
    return jsonify(
        {
            "watch_percentage": float(progress.watch_percentage),
            "status": progress.status,
            "completed": progress.status == "completed",
        }
    )


@api_bp.route("/charts/score/<int:employee_id>")
@login_required
def score_chart(employee_id):
    ensure_can_view(current_user, employee_id)
    score = compute_growth_score(employee_id, "monthly", persist=False)
    comp = score["components"]
    return jsonify(
        {
            "labels": ["Learning", "Assessment", "Goals", "Skill", "Consistency"],
            "values": [
                comp["learning"], comp["assessment"], comp["goal"],
                comp["skill"], comp["consistency"],
            ],
            "overall": score["overall"],
            "category": score["category"],
        }
    )


@api_bp.route("/charts/assessment/<int:employee_id>")
@login_required
def assessment_chart(employee_id):
    ensure_can_view(current_user, employee_id)
    rows = (
        AssessmentAttempt.query.filter(
            AssessmentAttempt.employee_id == employee_id,
            AssessmentAttempt.percentage.isnot(None),
        )
        .order_by(AssessmentAttempt.submitted_at)
        .all()
    )
    return jsonify(
        {
            "labels": [
                (a.submitted_at or a.id).__str__()[:16] if a.submitted_at else f"#{a.id}"
                for a in rows
            ],
            "values": [float(a.percentage) for a in rows],
        }
    )

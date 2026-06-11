from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import case, func

from app.extensions import db
from app.models import (
    Assessment,
    AssessmentAttempt,
    Goal,
    LearningModule,
    LearningProgress,
    User,
)
from app.utils.scoring import compute_growth_score
from app.utils.security import visible_employee_ids

intelligence_bp = Blueprint("intelligence", __name__)


@intelligence_bp.route("/")
@login_required
def dashboard():
    ids = visible_employee_ids(current_user)
    emp_ids = [
        u.id
        for u in User.query.filter(User.id.in_(ids), User.role == "employee").all()
    ] or ids

    # Learning analytics
    total_seconds = (
        db.session.query(func.coalesce(func.sum(LearningProgress.watch_seconds), 0))
        .filter(LearningProgress.employee_id.in_(emp_ids))
        .scalar()
        or 0
    )
    total_hours = round(total_seconds / 3600, 1)

    popular = (
        db.session.query(LearningModule.title, func.count(LearningProgress.id))
        .join(LearningProgress, LearningProgress.module_id == LearningModule.id)
        .filter(LearningProgress.employee_id.in_(emp_ids))
        .group_by(LearningModule.id)
        .order_by(func.count(LearningProgress.id).desc())
        .limit(5)
        .all()
    )

    completion_rows = (
        db.session.query(
            LearningModule.title,
            func.sum(case((LearningProgress.status == "completed", 1), else_=0)),
            func.count(LearningProgress.id),
        )
        .join(LearningProgress, LearningProgress.module_id == LearningModule.id)
        .filter(LearningProgress.employee_id.in_(emp_ids))
        .group_by(LearningModule.id)
        .order_by(func.count(LearningProgress.id).desc())
        .limit(8)
        .all()
    )
    completion = [
        {"title": t, "rate": round((c or 0) / total * 100, 1) if total else 0}
        for t, c, total in completion_rows
    ]

    # Performance analytics
    avg_assessment = (
        db.session.query(func.avg(AssessmentAttempt.percentage))
        .filter(
            AssessmentAttempt.employee_id.in_(emp_ids),
            AssessmentAttempt.percentage.isnot(None),
        )
        .scalar()
    )
    avg_assessment = round(float(avg_assessment), 1) if avg_assessment else 0

    scored = [
        (u, compute_growth_score(u.id, "monthly", persist=False))
        for u in User.query.filter(User.id.in_(emp_ids)).all()
    ]
    top_learners = sorted(
        scored, key=lambda x: x[1]["components"]["learning"], reverse=True
    )[:5]
    team_productivity = (
        round(sum(s["overall"] for _, s in scored) / len(scored), 1) if scored else 0
    )

    # Goal analytics
    total_goals = Goal.query.filter(Goal.employee_id.in_(emp_ids)).count()
    completed_goals = Goal.query.filter(
        Goal.employee_id.in_(emp_ids), Goal.status == "completed"
    ).count()
    goal_rate = round(completed_goals / total_goals * 100, 1) if total_goals else 0

    return render_template(
        "intelligence/dashboard.html",
        total_hours=total_hours,
        popular=popular,
        completion=completion,
        avg_assessment=avg_assessment,
        top_learners=top_learners,
        team_productivity=team_productivity,
        goal_rate=goal_rate,
        total_goals=total_goals,
        completed_goals=completed_goals,
        module_count=LearningModule.query.count(),
        assessment_count=Assessment.query.count(),
    )

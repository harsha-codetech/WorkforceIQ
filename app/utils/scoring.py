"""Growth Score engine.

Weights (approved): learning 30, assessment 30, goal 20, skill 10, consistency 10.
"""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from app.extensions import db
from app.models import (
    AssessmentAttempt,
    EmployeeSkill,
    Goal,
    LearningActivity,
    LearningProgress,
    ModuleAssignment,
    PerformanceScore,
)

WEIGHTS = {
    "learning": 0.30,
    "assessment": 0.30,
    "goal": 0.20,
    "skill": 0.10,
    "consistency": 0.10,
}
LEVEL_VALUE = {"beginner": 25, "intermediate": 50, "advanced": 75, "expert": 100}


def period_bounds(period_type, ref=None):
    ref = ref or date.today()
    if period_type == "weekly":
        start = ref - timedelta(days=ref.weekday())
        end = start + timedelta(days=6)
    elif period_type == "monthly":
        start = ref.replace(day=1)
        nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = nxt - timedelta(days=1)
    else:  # quarterly
        q = (ref.month - 1) // 3
        start = date(ref.year, q * 3 + 1, 1)
        nxt_month = q * 3 + 4
        year = ref.year + (1 if nxt_month > 12 else 0)
        month = nxt_month - 12 if nxt_month > 12 else nxt_month
        end = date(year, month, 1) - timedelta(days=1)
    return start, end


def categorize(score):
    if score >= 90:
        return "elite"
    if score >= 75:
        return "high_performer"
    if score >= 60:
        return "good"
    if score >= 40:
        return "needs_improvement"
    return "critical"


def _learning_score(employee_id):
    rows = (
        db.session.query(LearningProgress.status, LearningProgress.watch_percentage)
        .filter(LearningProgress.employee_id == employee_id)
        .all()
    )
    if not rows:
        return 0.0
    df = pd.DataFrame(rows, columns=["status", "watch_percentage"])
    completed = (df["status"] == "completed").mean() * 100
    watch = pd.to_numeric(df["watch_percentage"], errors="coerce").fillna(0).mean()
    return float(np.clip(0.6 * completed + 0.4 * watch, 0, 100))


def _assessment_score(employee_id):
    rows = (
        db.session.query(AssessmentAttempt.assessment_id, AssessmentAttempt.percentage)
        .filter(
            AssessmentAttempt.employee_id == employee_id,
            AssessmentAttempt.percentage.isnot(None),
        )
        .all()
    )
    if not rows:
        return 0.0
    df = pd.DataFrame(rows, columns=["assessment_id", "percentage"])
    df["percentage"] = pd.to_numeric(df["percentage"], errors="coerce")
    best = df.groupby("assessment_id")["percentage"].max()
    return float(np.clip(best.mean(), 0, 100))


def _goal_score(employee_id, start, end):
    total = Goal.query.filter(
        Goal.employee_id == employee_id, Goal.due_date >= start, Goal.due_date <= end
    ).count()
    if total == 0:
        return 0.0
    done = Goal.query.filter(
        Goal.employee_id == employee_id,
        Goal.due_date >= start,
        Goal.due_date <= end,
        Goal.status == "completed",
    ).count()
    return float(np.clip(done / total * 100, 0, 100))


def _skill_score(employee_id):
    rows = (
        db.session.query(EmployeeSkill.level)
        .filter(EmployeeSkill.employee_id == employee_id)
        .all()
    )
    if not rows:
        return 0.0
    values = [LEVEL_VALUE[r.level] for r in rows]
    return float(np.clip(np.mean(values), 0, 100))


def _consistency_score(employee_id, start, end):
    span = (end - start).days + 1
    active = LearningActivity.query.filter(
        LearningActivity.employee_id == employee_id,
        LearningActivity.activity_date >= start,
        LearningActivity.activity_date <= end,
    ).count()
    return float(np.clip(active / span * 100, 0, 100)) if span else 0.0


def compute_growth_score(employee_id, period_type="monthly", ref=None, persist=True):
    start, end = period_bounds(period_type, ref)
    parts = {
        "learning": round(_learning_score(employee_id), 2),
        "assessment": round(_assessment_score(employee_id), 2),
        "goal": round(_goal_score(employee_id, start, end), 2),
        "skill": round(_skill_score(employee_id), 2),
        "consistency": round(_consistency_score(employee_id, start, end), 2),
    }
    overall = round(sum(parts[k] * WEIGHTS[k] for k in parts), 2)
    category = categorize(overall)

    if persist:
        ps = PerformanceScore.query.filter_by(
            employee_id=employee_id, period_type=period_type, period_start=start
        ).first()
        if not ps:
            ps = PerformanceScore(
                employee_id=employee_id, period_type=period_type, period_start=start
            )
            db.session.add(ps)
        ps.period_end = end
        ps.learning_score = parts["learning"]
        ps.assessment_score = parts["assessment"]
        ps.goal_score = parts["goal"]
        ps.skill_growth_score = parts["skill"]
        ps.consistency_score = parts["consistency"]
        ps.overall_score = overall
        ps.category = category
        ps.calculated_at = datetime.utcnow()
        db.session.commit()

    return {
        "period_start": start,
        "period_end": end,
        "components": parts,
        "overall": overall,
        "category": category,
    }


def recompute_all(period_type="monthly"):
    from app.models import User

    employees = User.query.filter_by(role="employee", status="active").all()
    for emp in employees:
        compute_growth_score(emp.id, period_type, persist=True)
    return len(employees)

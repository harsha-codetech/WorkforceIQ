from app.extensions import db
from app.models import (
    Badge,
    EmployeeBadge,
    EmployeeSkill,
    LearningProgress,
)
from app.utils.notify import notify
from app.utils.scoring import compute_growth_score

BADGE_DEFS = [
    ("Learning Champion", "Completed 10 or more learning modules", "modules_completed>=10"),
    ("Assessment Master", "Average assessment score of 85% or higher", "assessment>=85"),
    ("Goal Achiever", "Goal achievement rate of 80% or higher", "goal>=80"),
    ("Skill Builder", "Reached advanced/expert in 3 or more skills", "skills_advanced>=3"),
    ("Consistency Award", "Learning consistency of 80% or higher", "consistency>=80"),
]


def seed_badges():
    for name, desc, criteria in BADGE_DEFS:
        if not Badge.query.filter_by(name=name).first():
            db.session.add(Badge(name=name, description=desc, criteria=criteria))
    db.session.commit()


def _award(employee_id, name):
    badge = Badge.query.filter_by(name=name).first()
    if not badge:
        return False
    if EmployeeBadge.query.filter_by(employee_id=employee_id, badge_id=badge.id).first():
        return False
    db.session.add(EmployeeBadge(employee_id=employee_id, badge_id=badge.id))
    notify(
        employee_id, "badge_awarded", "New badge earned",
        f"You earned the '{name}' badge.", entity_type="badge", entity_id=badge.id,
    )
    return True


def evaluate_badges(employee_id):
    """Award any newly-earned badges. Returns count awarded."""
    score = compute_growth_score(employee_id, "monthly", persist=False)
    comp = score["components"]
    awarded = 0

    modules_done = LearningProgress.query.filter_by(
        employee_id=employee_id, status="completed"
    ).count()
    advanced_skills = EmployeeSkill.query.filter(
        EmployeeSkill.employee_id == employee_id,
        EmployeeSkill.level.in_(["advanced", "expert"]),
    ).count()

    checks = {
        "Learning Champion": modules_done >= 10,
        "Assessment Master": comp["assessment"] >= 85,
        "Goal Achiever": comp["goal"] >= 80,
        "Skill Builder": advanced_skills >= 3,
        "Consistency Award": comp["consistency"] >= 80,
    }
    for name, earned in checks.items():
        if earned and _award(employee_id, name):
            awarded += 1
    db.session.commit()
    return awarded

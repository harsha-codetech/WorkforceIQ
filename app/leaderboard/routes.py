from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.models import User
from app.utils.scoring import compute_growth_score, period_bounds
from app.utils.security import visible_employee_ids

leaderboard_bp = Blueprint("leaderboard", __name__)
PERIODS = ("weekly", "monthly", "quarterly")


@leaderboard_bp.route("/")
@login_required
def index():
    period = request.args.get("period", "monthly")
    if period not in PERIODS:
        period = "monthly"
    start, end = period_bounds(period)

    ids = visible_employee_ids(current_user)
    employees = User.query.filter(User.id.in_(ids), User.role == "employee").all()

    data = []
    for emp in employees:
        score = compute_growth_score(emp.id, period, persist=False)
        data.append({"employee": emp, "score": score})

    top_learners = sorted(
        data, key=lambda d: d["score"]["components"]["learning"], reverse=True
    )[:10]
    top_assessment = sorted(
        data, key=lambda d: d["score"]["components"]["assessment"], reverse=True
    )[:10]
    goal_champions = sorted(
        data, key=lambda d: d["score"]["components"]["goal"], reverse=True
    )[:10]
    most_improved = sorted(
        data, key=lambda d: d["score"]["overall"], reverse=True
    )[:10]

    return render_template(
        "leaderboard/index.html",
        period=period,
        periods=PERIODS,
        start=start,
        end=end,
        top_learners=top_learners,
        top_assessment=top_assessment,
        goal_champions=goal_champions,
        most_improved=most_improved,
    )

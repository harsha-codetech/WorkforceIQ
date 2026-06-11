import os

os.environ.setdefault("FLASK_CONFIG", "testing")

from app import create_app
from app.extensions import db
from app.utils.seed import seed_demo_data


def setup_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        seed_demo_data()
    return app


def test_app_boots_and_seeds():
    app = setup_app()
    client = app.test_client()
    assert client.get("/login").status_code == 200


def test_login_and_dashboard():
    app = setup_app()
    client = app.test_client()
    r = client.post(
        "/login",
        data={"email": "admin@workforceiq.com", "password": "Password123"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"Organization Overview" in r.data


def test_employee_growth_score():
    app = setup_app()
    with app.app_context():
        from app.models import User
        from app.utils.scoring import compute_growth_score

        emp = User.query.filter_by(role="employee").first()
        score = compute_growth_score(emp.id, "monthly", persist=False)
        assert 0 <= score["overall"] <= 100
        assert score["category"] in (
            "elite", "high_performer", "good", "needs_improvement", "critical"
        )

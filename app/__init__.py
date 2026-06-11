import os

from flask import Flask, render_template
from flask_login import current_user

from config import config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config["default"]))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    _register_blueprints(app)
    _register_errorhandlers(app)
    _register_context(app)
    _register_cli(app)
    return app


def _register_blueprints(app):
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.learning.routes import learning_bp
    from app.assessments.routes import assessments_bp
    from app.goals.routes import goals_bp
    from app.skills.routes import skills_bp
    from app.intelligence.routes import intelligence_bp
    from app.leaderboard.routes import leaderboard_bp
    from app.badges.routes import badges_bp
    from app.reports.routes import reports_bp
    from app.notifications.routes import notifications_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(learning_bp, url_prefix="/learning")
    app.register_blueprint(assessments_bp, url_prefix="/assessments")
    app.register_blueprint(goals_bp, url_prefix="/goals")
    app.register_blueprint(skills_bp, url_prefix="/skills")
    app.register_blueprint(intelligence_bp, url_prefix="/intelligence")
    app.register_blueprint(leaderboard_bp, url_prefix="/leaderboard")
    app.register_blueprint(badges_bp, url_prefix="/badges")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(api_bp, url_prefix="/api")
    csrf.exempt(api_bp)


def _register_errorhandlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/error.html", code=400, message="Bad request"), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return render_template("errors/error.html", code=401, message="Unauthorized"), 401

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, message="Access denied"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, message="Page not found"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/error.html", code=413, message="File too large"), 413

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/error.html", code=500, message="Server error"), 500


def _register_context(app):
    from app.models import Notification

    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return {"unread_notifications": unread}


def _register_cli(app):
    import click

    from app.utils.seed import seed_demo_data

    @app.cli.command("init-db")
    def init_db():
        """Create all tables."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Populate demo organization, users and content."""
        db.create_all()
        seed_demo_data()
        click.echo("Demo data seeded.")

    @app.cli.command("recompute-scores")
    @click.option("--period", default="monthly")
    def recompute(period):
        """Recalculate Growth Scores for all employees."""
        from app.utils.scoring import recompute_all

        n = recompute_all(period)
        click.echo(f"Recomputed {n} employee scores ({period}).")

import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import (
    ChangePasswordForm,
    LoginForm,
    RequestResetForm,
    ResetPasswordForm,
)
from app.extensions import db
from app.models import PasswordReset, User
from app.utils.mailer import send_email
from app.utils.security import log_action

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if user.status != "active":
                flash("Your account is inactive. Contact an administrator.", "danger")
                return render_template("auth/login.html", form=form)
            login_user(user)
            user.last_login_at = datetime.utcnow()
            log_action("login", "user", user.id)
            db.session.commit()
            nxt = request.args.get("next")
            return redirect(nxt or url_for("main.dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("logout", "user", current_user.id)
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            raw = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw.encode()).hexdigest()
            db.session.add(
                PasswordReset(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                )
            )
            db.session.commit()
            link = url_for("auth.reset_password", token=raw, _external=True)
            send_email(
                user.email,
                "WorkforceIQ password reset",
                f"Reset your password using this link (valid 1 hour): {link}",
            )
        flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = (
        PasswordReset.query.filter_by(token_hash=token_hash, used_at=None)
        .filter(PasswordReset.expires_at >= datetime.utcnow())
        .first()
    )
    if not record:
        flash("This reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = db.session.get(User, record.user_id)
        user.set_password(form.password.data)
        record.used_at = datetime.utcnow()
        db.session.commit()
        flash("Password updated. Please sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(form.password.data)
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/change_password.html", form=form)

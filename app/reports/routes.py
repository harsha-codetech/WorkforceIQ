from datetime import datetime

from flask import Blueprint, abort, current_app, flash, render_template, send_file
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ReportExport, User
from app.reports.forms import ReportForm
from app.reports.generator import render
from app.utils.security import log_action, visible_employee_ids

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    form = ReportForm()
    scope_ids = visible_employee_ids(current_user)
    employees = User.query.filter(
        User.id.in_(scope_ids), User.role == "employee"
    ).order_by(User.full_name).all()
    form.employee_id.choices = [(0, "— Select —")] + [
        (e.id, e.full_name) for e in employees
    ]

    # Restrict report types by role
    if current_user.is_employee:
        form.report_type.choices = [("employee", "Employee report")]
    elif current_user.is_manager:
        form.report_type.choices = [
            ("employee", "Employee report"),
            ("team", "Team report"),
        ]

    if form.validate_on_submit():
        rtype = form.report_type.data
        if current_user.is_employee:
            rtype = "employee"
            focus = current_user.id
        else:
            focus = form.employee_id.data or None
        if rtype == "employee":
            if not focus or focus not in scope_ids:
                flash("Select a valid employee for this report.", "warning")
                return render_template("reports/index.html", form=form)
        if rtype == "organization" and not current_user.is_admin:
            abort(403)

        export = ReportExport(
            requested_by=current_user.id,
            report_type=rtype,
            format=form.format.data,
            status="processing",
        )
        db.session.add(export)
        db.session.commit()
        try:
            buffer, mimetype, ext = render(rtype, form.format.data, scope_ids, focus)
            export.status = "completed"
            export.completed_at = datetime.utcnow()
            export.file_key = f"{rtype}_{export.id}.{ext}"
            db.session.commit()
            log_action("generate_report", "report_export", export.id)
            return send_file(
                buffer,
                mimetype=mimetype,
                as_attachment=True,
                download_name=f"workforceiq_{rtype}_{datetime.now():%Y%m%d}.{ext}",
            )
        except Exception:
            export.status = "failed"
            db.session.commit()
            current_app.logger.exception("Report generation failed")
            flash("Report generation failed. Please try again.", "danger")
            return render_template("reports/index.html", form=form)

    recent = (
        ReportExport.query.filter_by(requested_by=current_user.id)
        .order_by(ReportExport.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template("reports/index.html", form=form, recent=recent)

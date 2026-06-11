import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to_address, subject, body):
    """Best-effort SMTP send. Silently no-ops when SMTP is not configured
    so dashboard notifications continue to work in any environment."""
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["MAIL_SENDER"]
        msg["To"] = to_address
        msg.set_content(body)
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as server:
            if cfg.get("MAIL_USE_TLS"):
                server.starttls()
            if cfg.get("MAIL_USERNAME"):
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception:  # pragma: no cover - external dependency
        current_app.logger.exception("Email send failed")
        return False

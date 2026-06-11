from datetime import datetime

from app.extensions import db
from app.models import Notification, User
from app.utils.mailer import send_email


def notify(user_id, ntype, title, message, channel="dashboard",
           entity_type=None, entity_id=None, send_mail=False):
    note = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        channel="email" if send_mail else channel,
        related_entity_type=entity_type,
        related_entity_id=entity_id,
    )
    if send_mail:
        user = db.session.get(User, user_id)
        if user and send_email(user.email, title, message):
            note.sent_at = datetime.utcnow()
    db.session.add(note)
    return note

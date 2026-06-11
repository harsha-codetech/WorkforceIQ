from functools import wraps

from flask import abort, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog, User


def role_required(*roles):
    """Restrict a view to the given roles."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def visible_employee_ids(user):
    """IDs the given user is allowed to view.

    Admin -> everyone in the organization.
    Manager -> direct reports + self.
    Employee -> only self.
    """
    if user.is_admin:
        rows = User.query.filter_by(organization_id=user.organization_id).with_entities(User.id)
        return [r.id for r in rows]
    if user.is_manager:
        rows = User.query.filter_by(manager_id=user.id).with_entities(User.id)
        return [r.id for r in rows] + [user.id]
    return [user.id]


def ensure_can_view(user, employee_id):
    if employee_id not in visible_employee_ids(user):
        abort(403)


def log_action(action, entity_type=None, entity_id=None):
    entry = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)

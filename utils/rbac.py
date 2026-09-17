"""
utils/rbac.py
----------------
Lightweight role-based access control (Module 6, Part 4/16).

A single `@role_required(...)` decorator, layered on top of
Flask-Login's `@login_required` rather than replacing it — every
protected route still requires authentication first, and this only
adds an authorization check on top. Kept intentionally simple (roles
are a plain string column on User, see models/user.py) rather than a
full permissions/ACL system, which would be over-engineering for the
two roles this app currently has.
"""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*allowed_roles):
    """
    Restrict a route to users whose `.role` is one of `allowed_roles`.
    Always implies login_required — an anonymous user is redirected to
    login (via Flask-Login) rather than getting a 403, since 403 would
    leak "this route exists but you can't see it" to logged-out users.

    Usage:
        @invigilator_bp.route("/invigilator")
        @role_required("invigilator", "admin")
        def dashboard():
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in allowed_roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator

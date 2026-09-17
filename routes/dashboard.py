"""
routes/dashboard.py
---------------------
Candidate dashboard, profile, and settings pages.

Kept as its own blueprint (separate from auth) so future modules can
extend dashboard-related routes without growing the auth blueprint.
"""

from flask import Blueprint, render_template, session
from flask_login import login_required, current_user

from services import event_logger, integrity_service, assessment_service
from services.system_health import get_system_health

dashboard_bp = Blueprint("dashboard", __name__)

# Session key used to log "Dashboard Accessed" only once per login
# session, rather than on every single page view — keeps the activity
# timeline meaningful instead of flooded with repeat entries.
_SESSION_DASHBOARD_LOGGED = "dashboard_access_logged"


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    """Protected route — the candidate's main landing page after login."""

    if not session.get(_SESSION_DASHBOARD_LOGGED):
        event_logger.log_event(current_user.id, "dashboard_accessed")
        session[_SESSION_DASHBOARD_LOGGED] = True

    active_assessments = assessment_service.get_active_assessments()
    next_assessment = active_assessments[0] if active_assessments else None
    exam_status = "Available" if next_assessment else "Not Available"

    return render_template(
        "dashboard.html",
        user=current_user,
        exam_status=exam_status,
        next_assessment=next_assessment,
        recent_events=event_logger.get_recent_events(current_user.id, limit=6),
        integrity_score=integrity_service.get_score(current_user),
        score_label=integrity_service.score_status_label(current_user.integrity_score),
        risk_label=integrity_service.risk_label(current_user.integrity_score),
        system_health=get_system_health(),
        monitoring_active=session.get("monitoring_active", False),
        stats=assessment_service.get_candidate_stats(current_user.id),
        violations_count=len(event_logger.get_violations(current_user.id, limit=1000)),
    )


@dashboard_bp.route("/profile")
@login_required
def profile():
    """Read-only candidate profile page (linked from the sidebar)."""
    return render_template(
        "profile.html",
        user=current_user,
        recent_events=event_logger.get_recent_events(current_user.id, limit=10),
    )


@dashboard_bp.route("/settings")
@login_required
def settings():
    """Account settings page (placeholder for future preference controls)."""
    return render_template("settings.html", user=current_user)

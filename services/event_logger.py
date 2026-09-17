"""
services/event_logger.py
---------------------------
Central place to write and read ExamEvent rows.

Every module that observes something worth auditing (auth, camera
monitoring, browser monitoring) calls `log_event()` here rather than
constructing an ExamEvent and committing it directly. This keeps the
event schema and severity conventions in one place, and means the
Recent Activity timeline, Violations page, and Analytics charts can all
rely on the same consistent data.
"""

from datetime import datetime

from models import db
from models.exam_event import ExamEvent

# Canonical severity levels. Kept as plain strings (not an Enum) so
# future event types never require a schema change — see
# models/exam_event.py for the reasoning.
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

# Human-readable descriptions for each known event_type slug. Used as a
# fallback when the caller doesn't supply a custom description, so the
# timeline always reads naturally (e.g. "Face Verified" rather than
# the raw slug "face_verified").
_DEFAULT_DESCRIPTIONS = {
    "registered": "Candidate registered",
    "login": "Candidate logged in",
    "logout": "Candidate logged out",
    "face_verified": "Face verified and profile photo saved",
    "dashboard_accessed": "Dashboard accessed",
    "monitoring_started": "Live monitoring started",
    "monitoring_stopped": "Live monitoring stopped",
    "exam_finished": "Exam session finished",
    "no_face": "No face detected in webcam feed",
    "multiple_faces": "Multiple faces detected in webcam feed",
    "face_restored": "Single face re-established in webcam feed",
    "camera_lost": "Webcam connection lost",
    "camera_restored": "Webcam connection restored",
    "tab_switch": "Candidate switched browser tabs",
    "window_blur": "Exam window lost focus",
    "window_focus": "Exam window regained focus",
    "fullscreen_exit": "Candidate exited fullscreen mode",
    "page_refresh": "Candidate attempted to refresh the page",
    "copy_attempt": "Copy action attempted",
    "paste_attempt": "Paste action attempted",
    "right_click": "Right-click context menu attempted",
    "devtools_detected": "Browser developer tools usage detected",
    # Module 5: pre-assessment workflow + assessment engine
    "readiness_passed": "System readiness check passed",
    "declaration_submitted": "Candidate declaration submitted",
    "assessment_started": "Assessment attempt started",
    "assessment_submitted": "Assessment submitted",
    "assessment_auto_submitted": "Assessment auto-submitted (time expired)",
    "phone_detected": "Mobile phone detected in webcam feed",
    "face_covered": "Face covering detected in webcam feed",
    # Module 6: invigilator session controls
    "session_paused": "Assessment session paused by an invigilator",
    "session_resumed": "Assessment session resumed by an invigilator",
    "session_terminated": "Assessment session terminated by an invigilator",
}


def log_event(user_id: int, event_type: str, severity: str = SEVERITY_INFO, description: str = None) -> ExamEvent:
    """
    Write a single ExamEvent row.

    `description` defaults to a friendly, pre-written sentence for known
    event_type slugs (see _DEFAULT_DESCRIPTIONS) — callers only need to
    supply their own when they want to add specific detail.
    """
    if description is None:
        description = _DEFAULT_DESCRIPTIONS.get(event_type, event_type.replace("_", " ").capitalize())

    event = ExamEvent(
        user_id=user_id,
        event_type=event_type,
        severity=severity,
        description=description,
        timestamp=datetime.utcnow(),
    )
    db.session.add(event)
    db.session.commit()
    return event


def get_recent_events(user_id: int, limit: int = 10):
    """Most recent events for a candidate, newest first — for the dashboard timeline."""
    return (
        ExamEvent.query.filter_by(user_id=user_id)
        .order_by(ExamEvent.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_violations(user_id: int, limit: int = 100):
    """Events flagged as warning/critical — for the Violations page."""
    return (
        ExamEvent.query.filter(
            ExamEvent.user_id == user_id,
            ExamEvent.severity.in_([SEVERITY_WARNING, SEVERITY_CRITICAL]),
        )
        .order_by(ExamEvent.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_violations_in_window(user_id: int, start, end=None, limit: int = 200):
    """
    Warning/critical events for a candidate, scoped to a specific time
    window — used by the assessment Result page (Module 7, Part 13) and
    the invigilator session review (Module 6) to show violations from
    THIS attempt only, not a candidate's entire history.
    """
    query = ExamEvent.query.filter(
        ExamEvent.user_id == user_id,
        ExamEvent.severity.in_([SEVERITY_WARNING, SEVERITY_CRITICAL]),
        ExamEvent.timestamp >= start,
    )
    if end is not None:
        query = query.filter(ExamEvent.timestamp <= end)

    return query.order_by(ExamEvent.timestamp.desc()).limit(limit).all()


def get_events_in_window(user_id: int, start, end=None, limit: int = 500):
    """
    ALL events (any severity) for a candidate, scoped to a time window
    — the full-timeline counterpart to get_violations_in_window, used
    by the invigilator session review and its CSV/JSON export, which
    intentionally include informational events (e.g. "monitoring
    started") alongside violations for a complete audit trail.
    """
    query = ExamEvent.query.filter(ExamEvent.user_id == user_id, ExamEvent.timestamp >= start)
    if end is not None:
        query = query.filter(ExamEvent.timestamp <= end)

    return query.order_by(ExamEvent.timestamp.desc()).limit(limit).all()


def get_all_events(user_id: int, limit: int = 500):
    """All events for a candidate, newest first — for the Reports page."""
    return (
        ExamEvent.query.filter_by(user_id=user_id)
        .order_by(ExamEvent.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_latest_event_of_type(user_id: int, event_type: str):
    """Most recent event of a given type, or None. Used to find 'when did the current monitoring session start'."""
    return (
        ExamEvent.query.filter_by(user_id=user_id, event_type=event_type)
        .order_by(ExamEvent.timestamp.desc())
        .first()
    )


def get_event_counts_by_type(user_id: int) -> dict:
    """{event_type: count} for all of a candidate's events — feeds the Analytics violation-distribution chart."""
    rows = (
        db.session.query(ExamEvent.event_type, db.func.count(ExamEvent.id))
        .filter(ExamEvent.user_id == user_id)
        .group_by(ExamEvent.event_type)
        .all()
    )
    return {event_type: count for event_type, count in rows}

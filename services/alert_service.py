"""
services/alert_service.py
----------------------------
Milestone 3, Part 19: Alert Management Module.

Alerts are raised for configured critical events (config.py's
ALERT_SEVERITY_EVENTS) plus two pattern-based rules — repeated tab
switching and extended face absence — that no single ExamEvent row
can represent on its own. Routes call `evaluate_session_for_alerts()`
after logging a new event (or the invigilator dashboard can call it
periodically); it's idempotent per-event via `source_event_id`-style
de-duplication (matched on session+event_type+timestamp) so re-running
it doesn't create duplicate alerts.
"""

from datetime import datetime

from flask import current_app

from models import db
from models.analytics import Alert
from services import event_logger

_DEFAULT_SEVERITY_EVENTS = {
    "multiple_faces": "critical", "camera_lost": "warning", "phone_detected": "critical",
    "face_covered": "warning", "session_terminated": "critical", "devtools_detected": "warning",
}


def _severity_events() -> dict:
    try:
        return current_app.config.get("ALERT_SEVERITY_EVENTS", _DEFAULT_SEVERITY_EVENTS)
    except RuntimeError:
        return _DEFAULT_SEVERITY_EVENTS


def _repeated_tab_switch_threshold() -> int:
    try:
        return current_app.config.get("ALERT_REPEATED_TAB_SWITCH_THRESHOLD", 3)
    except RuntimeError:
        return 3


def _extended_absence_seconds() -> int:
    try:
        return current_app.config.get("ALERT_EXTENDED_FACE_ABSENCE_SECONDS", 30)
    except RuntimeError:
        return 30


def _alert_exists(session_id: int, event_type: str, description: str) -> bool:
    return db.session.query(Alert.id).filter_by(
        session_id=session_id, event_type=event_type, description=description
    ).first() is not None


def create_alert(session, event_type: str, severity: str, description: str) -> Alert:
    if _alert_exists(session.id, event_type, description):
        return None
    alert = Alert(
        session_id=session.id, user_id=session.user_id, event_type=event_type,
        severity=severity, description=description, status="OPEN",
        timestamp=datetime.utcnow(),
    )
    db.session.add(alert)
    db.session.commit()
    return alert


def evaluate_session_for_alerts(session) -> list:
    """
    Scan a session's events for configured critical-event and
    pattern-based alert conditions, creating any new Alert rows.
    Returns the list of newly-created alerts (empty if none).
    """
    start = session.started_at
    end = session.submitted_at or datetime.utcnow()
    events = event_logger.get_events_in_window(session.user_id, start=start, end=end, limit=1000)
    severity_map = _severity_events()

    created = []

    # 1. Direct configured-severity events.
    for e in events:
        if e.event_type in severity_map:
            alert = create_alert(session, e.event_type, severity_map[e.event_type], e.description)
            if alert:
                created.append(alert)

    # 2. Repeated tab switching.
    tab_switch_count = sum(1 for e in events if e.event_type == "tab_switch")
    threshold = _repeated_tab_switch_threshold()
    if tab_switch_count >= threshold:
        alert = create_alert(
            session, "tab_switch", "warning",
            f"Repeated tab switching detected — {tab_switch_count} tab switches this session (threshold {threshold}).",
        )
        if alert:
            created.append(alert)

    # 3. Extended continuous face absence.
    ordered = sorted(events, key=lambda e: e.timestamp)
    absence_start = None
    max_absence = 0.0
    for e in ordered:
        if e.event_type in ("no_face", "camera_lost") and absence_start is None:
            absence_start = e.timestamp
        elif e.event_type in ("face_restored", "camera_restored") and absence_start is not None:
            max_absence = max(max_absence, (e.timestamp - absence_start).total_seconds())
            absence_start = None
    if absence_start is not None:
        max_absence = max(max_absence, (end - absence_start).total_seconds())

    threshold_seconds = _extended_absence_seconds()
    if max_absence >= threshold_seconds:
        alert = create_alert(
            session, "no_face", "warning",
            f"Extended face absence detected — {int(max_absence)}s continuous (threshold {threshold_seconds}s).",
        )
        if alert:
            created.append(alert)

    return created


def get_alerts_for_session(session_id: int):
    return Alert.query.filter_by(session_id=session_id).order_by(Alert.timestamp.desc()).all()


def get_open_alerts(limit: int = 200):
    return Alert.query.filter(Alert.status == "OPEN").order_by(Alert.timestamp.desc()).limit(limit).all()


def get_all_alerts(status: str = None, limit: int = 200):
    query = Alert.query
    if status:
        query = query.filter(Alert.status == status)
    return query.order_by(Alert.timestamp.desc()).limit(limit).all()


def acknowledge_alert(alert: Alert, examiner_user_id: int) -> Alert:
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = examiner_user_id
    db.session.commit()
    return alert


def resolve_alert(alert: Alert, examiner_user_id: int) -> Alert:
    alert.status = "RESOLVED"
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = examiner_user_id
    db.session.commit()
    return alert

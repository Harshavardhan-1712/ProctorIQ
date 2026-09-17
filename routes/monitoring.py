"""
routes/monitoring.py
-----------------------
Module 4 routing: live exam monitoring, browser-integrity event
ingestion, and the Violations / Analytics / Reports pages.

Like routes/camera.py, this file is intentionally just orchestration:
    - services/monitoring_service.py decides the current face status
    - services/browser_monitor.py validates/classifies client-reported
      browser events
    - services/integrity_service.py owns the scoring rules
    - services/event_logger.py owns writing/reading ExamEvent rows
This route module wires them together and is the only place that
knows about Flask sessions, the logged-in candidate, or HTTP status
codes — none of the services above import Flask at all.

Routes:
    GET  /monitoring              -> live monitoring page (face status + browser JS)
    POST /monitoring/start        -> resets integrity score, logs "monitoring_started"
    GET  /monitoring/status       -> polled by the page; returns current face status + score
    POST /monitoring/browser-event -> receives one browser-integrity event from JS
    POST /monitoring/stop         -> logs "exam_finished", ends the monitoring session
    GET  /violations              -> table of this candidate's warning/critical events
    GET  /analytics               -> Chart.js dashboard page
    GET  /analytics/data          -> JSON feed consumed by the Analytics charts
    GET  /reports                 -> full chronological event report
"""

from flask import Blueprint, render_template, jsonify, request, session
from flask_login import login_required, current_user

from services import monitoring_service, event_logger, integrity_service
from services.browser_monitor import classify_event, InvalidBrowserEventError
from services.event_logger import SEVERITY_WARNING, SEVERITY_CRITICAL, SEVERITY_INFO
from services import assessment_service, evidence_service, alert_service
from services.camera_service import Camera, CameraError

monitoring_bp = Blueprint("monitoring", __name__)

# Session key tracking the last-seen face status, so /monitoring/status
# only logs (and deducts points for) a TRANSITION into a bad state —
# not every single poll while that state persists. This is a routing
# concern (state across requests), which is why it lives here rather
# than in monitoring_service.py.
_SESSION_LAST_FACE_STATUS = "monitoring_last_face_status"
_SESSION_MONITORING_ACTIVE = "monitoring_active"


def _capture_incident_evidence(event_type: str, description: str, severity: str = SEVERITY_CRITICAL) -> None:
    """
    Milestone 3, Parts 19-22: for a configured critical event, raise an
    alert, capture a screenshot (if a live camera frame is available),
    and create a linked incident — scoped to the candidate's current
    in-progress AssessmentSession, if one exists. A candidate not
    currently inside a monitored assessment session (e.g. viewing the
    standalone Module 4 monitoring demo page) simply has nothing to
    scope the incident to, so this is a no-op in that case.
    """
    assessment_session = assessment_service.get_current_session_for_user(current_user.id)
    if assessment_session is None:
        return

    evidence = None
    if evidence_service.should_capture_evidence(event_type):
        try:
            jpeg_bytes = Camera.get_instance().get_jpeg_bytes()
            import base64 as _b64
            evidence = evidence_service.store_evidence(
                assessment_session, event_type, _b64.b64encode(jpeg_bytes).decode("ascii"),
            )
        except CameraError:
            evidence = None  # no frame available right now — incident is still logged, just without a screenshot

    evidence_service.create_incident(
        assessment_session, event_type, severity, description, evidence=evidence,
    )
    alert_service.evaluate_session_for_alerts(assessment_session)


@monitoring_bp.route("/monitoring")
@login_required
def monitoring():
    """Render the live exam monitoring page."""
    return render_template("monitoring.html", user=current_user)


@monitoring_bp.route("/monitoring/start", methods=["POST"])
@login_required
def monitoring_start():
    """Begin a monitoring session: reset the integrity score and log the start event."""
    integrity_service.reset_score(current_user)
    session[_SESSION_LAST_FACE_STATUS] = None
    session[_SESSION_MONITORING_ACTIVE] = True
    event_logger.log_event(current_user.id, "monitoring_started", SEVERITY_INFO)

    return jsonify(success=True, score=current_user.integrity_score)


@monitoring_bp.route("/monitoring/status")
@login_required
def monitoring_status():
    """
    Polled periodically by the monitoring page's JS. Runs one face-
    detection check, logs + deducts on transition into a bad state,
    and always returns the current status and score.
    """
    result = monitoring_service.check_face_status()
    status = result["status"]
    previous_status = session.get(_SESSION_LAST_FACE_STATUS)

    if status != previous_status:
        # Only log/deduct on an actual transition, and only for
        # "bad" statuses — recovering back to single_face is logged
        # as an informational event (no deduction).
        if status == monitoring_service.STATUS_NO_FACE:
            event_logger.log_event(current_user.id, "no_face", SEVERITY_WARNING)
            integrity_service.apply_deduction(current_user, "no_face")
        elif status == monitoring_service.STATUS_MULTIPLE_FACES:
            event_logger.log_event(current_user.id, "multiple_faces", SEVERITY_CRITICAL)
            integrity_service.apply_deduction(current_user, "multiple_faces")
            _capture_incident_evidence("multiple_faces", "Multiple faces detected in webcam feed", SEVERITY_CRITICAL)
        elif status == monitoring_service.STATUS_CAMERA_ERROR:
            event_logger.log_event(current_user.id, "camera_lost", SEVERITY_CRITICAL)
            integrity_service.apply_deduction(current_user, "camera_lost")
        elif status == monitoring_service.STATUS_SINGLE_FACE and previous_status is not None:
            # Recovered from a bad state — worth a timeline entry, but
            # not worth restoring lost points (matches the spirit of
            # real proctoring systems: violations are logged, not undone).
            event_logger.log_event(current_user.id, "face_restored", SEVERITY_INFO)

        session[_SESSION_LAST_FACE_STATUS] = status

    return jsonify(
        status=status,
        face_count=result["face_count"],
        message=result["message"],
        score=current_user.integrity_score,
    )


@monitoring_bp.route("/monitoring/browser-event", methods=["POST"])
@login_required
def monitoring_browser_event():
    """
    Receive a single browser-integrity event reported by
    static/js/browser-monitor.js (tab switch, window blur, fullscreen
    exit, copy/paste, right-click, devtools, etc.).
    """
    payload = request.get_json(silent=True) or {}
    event_type = payload.get("event_type", "")

    try:
        severity = classify_event(event_type)
    except InvalidBrowserEventError:
        return jsonify(success=False, error="Unrecognized event type."), 400

    event_logger.log_event(current_user.id, event_type, severity)
    new_score = integrity_service.apply_deduction(current_user, event_type)

    if severity == SEVERITY_CRITICAL:
        # Only CRITICAL browser events (fullscreen exit, devtools) become
        # incidents — routine WARNING-level events (tab switches, copy/
        # paste) are still scored and alertable via the repeated-pattern
        # rules in alert_service, but don't each spawn their own incident
        # row (Milestone 3, Part 20: incidents are for configured
        # important events, not continuous/routine monitoring noise).
        _capture_incident_evidence(event_type, f"Browser event: {event_type.replace('_', ' ')}", severity)

    return jsonify(success=True, score=new_score)


@monitoring_bp.route("/monitoring/stop", methods=["POST"])
@login_required
def monitoring_stop():
    """End the monitoring session and log the final event."""
    event_logger.log_event(current_user.id, "exam_finished", SEVERITY_INFO)
    session.pop(_SESSION_LAST_FACE_STATUS, None)
    session.pop(_SESSION_MONITORING_ACTIVE, None)

    return jsonify(success=True, score=current_user.integrity_score)


@monitoring_bp.route("/violations")
@login_required
def violations():
    """Table of this candidate's warning/critical events."""
    events = event_logger.get_violations(current_user.id)
    return render_template("violations.html", user=current_user, events=events)


@monitoring_bp.route("/analytics")
@login_required
def analytics():
    """Chart.js analytics dashboard page (data is fetched client-side from /analytics/data)."""
    return render_template("analytics.html", user=current_user)


@monitoring_bp.route("/analytics/data")
@login_required
def analytics_data():
    """JSON feed consumed by the Analytics page's Chart.js charts."""
    counts_by_type = event_logger.get_event_counts_by_type(current_user.id)

    warning_count = sum(
        1 for e in event_logger.get_all_events(current_user.id)
        if e.severity in (SEVERITY_WARNING, SEVERITY_CRITICAL)
    )

    timeline = [
        {
            "timestamp": e.timestamp.isoformat() + "Z",
            "event_type": e.event_type,
            "severity": e.severity,
            "description": e.description,
        }
        for e in reversed(event_logger.get_all_events(current_user.id, limit=100))
    ]

    return jsonify(
        integrity_score=current_user.integrity_score,
        warning_count=warning_count,
        violation_distribution=counts_by_type,
        timeline=timeline,
    )


@monitoring_bp.route("/reports")
@login_required
def reports():
    """Full chronological event report for this candidate."""
    events = event_logger.get_all_events(current_user.id)
    return render_template(
        "reports.html",
        user=current_user,
        events=events,
        score=current_user.integrity_score,
    )

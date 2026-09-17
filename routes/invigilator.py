"""
routes/invigilator.py
------------------------
Invigilator/admin dashboard (Module 6, Part 4).

Architecture note, stated plainly rather than glossed over: this app's
`services/camera_service.py` (Module 2) assumes ONE shared physical
webcam for the whole Flask process — a fine assumption for a
single-candidate local demo, but it means there is no real per-candidate
live VIDEO feed to show an invigilator watching multiple remote
candidates simultaneously; that would require moving capture to each
candidate's own browser (WebRTC) with a server-side relay, which is a
bigger architectural change than fits this pass. What IS genuinely
real and multi-candidate-safe here: every candidate's monitoring
status, violations, and integrity score are DATABASE rows
(ExamEvent/AssessmentSession/User.integrity_score), so the dashboard
below shows accurate, live, per-candidate data pulled from the DB —
it just labels the camera column "Last Status" rather than pretending
to embed live video it can't actually provide.

Routes stay thin: all state changes go through
services/assessment_service.py's pause_session/resume_session/
terminate_session, which already existed as tested, standalone
functions before this file used them.
"""

import csv
import io
import json

from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, Response
from flask_login import current_user

from services import assessment_service, event_logger, integrity_service
from services.assessment_service import AssessmentError
from services import alert_service, evidence_service, integrity_scoring_service
from utils.rbac import role_required

invigilator_bp = Blueprint("invigilator", __name__, url_prefix="/invigilator")


def _session_summary(assessment_session):
    """Shared shape used by both the dashboard list and its JSON refresh endpoint."""
    candidate = assessment_session.user
    return {
        "session_id": assessment_session.id,
        "candidate_name": candidate.full_name,
        "candidate_email": candidate.email,
        "assessment_name": assessment_session.assessment.name,
        "status": assessment_session.status,
        "current_question": assessment_session.current_question_index + 1,
        "total_questions": assessment_session.assessment.total_questions,
        "time_remaining": assessment_service.time_remaining_seconds(assessment_session),
        "integrity_score": candidate.integrity_score,
        "risk_label": integrity_service.risk_label(candidate.integrity_score),
        "started_at": assessment_session.started_at.isoformat() + "Z",
    }


@invigilator_bp.route("/")
@role_required("invigilator", "admin")
def dashboard():
    """Live candidates dashboard — the main invigilator landing page."""
    search = request.args.get("q", "").strip().lower()
    risk_filter = request.args.get("risk", "").strip()

    sessions = assessment_service.get_active_sessions()

    if search:
        sessions = [
            s for s in sessions
            if search in s.user.full_name.lower() or search in s.user.email.lower()
        ]

    if risk_filter:
        sessions = [s for s in sessions if integrity_service.risk_label(s.user.integrity_score) == risk_filter]

    return render_template(
        "invigilator/dashboard.html",
        sessions=sessions,
        search=search,
        risk_filter=risk_filter,
        risk_label_fn=integrity_service.risk_label,
        time_remaining_fn=assessment_service.time_remaining_seconds,
    )


@invigilator_bp.route("/live-data")
@role_required("invigilator", "admin")
def live_data():
    """JSON feed the dashboard polls to refresh candidate cards without a full page reload."""
    sessions = assessment_service.get_active_sessions()
    return jsonify(sessions=[_session_summary(s) for s in sessions])


@invigilator_bp.route("/session/<int:session_id>")
@role_required("invigilator", "admin")
def session_detail(session_id):
    """Detailed view of one candidate's session — full violation timeline + summary."""
    assessment_session = assessment_service.get_session(session_id)
    candidate = assessment_session.user

    # Scope the timeline to roughly this session's window, so an
    # invigilator reviewing session #5 doesn't see violations from a
    # completely different attempt mixed in.
    events = event_logger.get_events_in_window(candidate.id, start=assessment_session.started_at, limit=200)

    violation_counts = {}
    for e in events:
        if e.severity in ("warning", "critical"):
            violation_counts[e.event_type] = violation_counts.get(e.event_type, 0) + 1

    # Milestone 3: weighted score breakdown, alerts, incidents, evidence
    # for this specific session.
    score_result = integrity_scoring_service.score_session(assessment_session)
    alert_service.evaluate_session_for_alerts(assessment_session)  # catch up on any pattern-based alerts

    return render_template(
        "invigilator/session_detail.html",
        assessment_session=assessment_session,
        candidate=candidate,
        events=events,
        violation_counts=violation_counts,
        risk_label=integrity_service.risk_label(candidate.integrity_score),
        score_result=score_result,
        alerts=alert_service.get_alerts_for_session(session_id),
        incidents=evidence_service.get_incidents_for_session(session_id),
        evidence_list=evidence_service.get_evidence_for_session(session_id),
    )


@invigilator_bp.route("/session/<int:session_id>/pause", methods=["POST"])
@role_required("invigilator", "admin")
def pause(session_id):
    assessment_session = assessment_service.get_session(session_id)
    note = request.get_json(silent=True).get("note") if request.is_json else request.form.get("note")

    try:
        assessment_service.pause_session(assessment_session, note=note)
        event_logger.log_event(
            assessment_session.user_id, "session_paused", "warning",
            f"Session paused by invigilator {current_user.full_name}" + (f" — {note}" if note else ""),
        )
    except AssessmentError as e:
        if request.is_json:
            return jsonify(success=False, error=str(e)), 400
        flash(str(e), "danger")

    if request.is_json:
        return jsonify(success=True)
    return redirect(url_for("invigilator.session_detail", session_id=session_id))


@invigilator_bp.route("/session/<int:session_id>/resume", methods=["POST"])
@role_required("invigilator", "admin")
def resume(session_id):
    assessment_session = assessment_service.get_session(session_id)
    try:
        assessment_service.resume_session(assessment_session)
        event_logger.log_event(
            assessment_session.user_id, "session_resumed", "info",
            f"Session resumed by invigilator {current_user.full_name}",
        )
    except AssessmentError as e:
        if request.is_json:
            return jsonify(success=False, error=str(e)), 400
        flash(str(e), "danger")

    if request.is_json:
        return jsonify(success=True)
    return redirect(url_for("invigilator.session_detail", session_id=session_id))


@invigilator_bp.route("/session/<int:session_id>/terminate", methods=["POST"])
@role_required("invigilator", "admin")
def terminate(session_id):
    assessment_session = assessment_service.get_session(session_id)
    note = request.form.get("note", "")

    try:
        assessment_service.terminate_session(
            assessment_session, integrity_score=assessment_session.user.integrity_score, note=note
        )
        event_logger.log_event(
            assessment_session.user_id, "session_terminated", "critical",
            f"Session terminated by invigilator {current_user.full_name}" + (f" — {note}" if note else ""),
        )
        evidence_service.create_incident(
            assessment_session, "session_terminated", "critical",
            f"Session terminated by invigilator {current_user.full_name}" + (f" — {note}" if note else ""),
        )
        alert_service.evaluate_session_for_alerts(assessment_session)
        flash(f"Session for {assessment_session.user.full_name} has been terminated.", "info")
    except AssessmentError as e:
        flash(str(e), "danger")

    return redirect(url_for("invigilator.dashboard"))


@invigilator_bp.route("/session/<int:session_id>/export.csv")
@role_required("invigilator", "admin")
def export_csv(session_id):
    """CSV export of one candidate session's full event/violation timeline (Part 13)."""
    assessment_session = assessment_service.get_session(session_id)
    events = event_logger.get_events_in_window(assessment_session.user_id, start=assessment_session.started_at, limit=1000)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Timestamp (UTC)", "Event Type", "Severity", "Description"])
    for e in events:
        writer.writerow([e.timestamp.isoformat(), e.event_type, e.severity, e.description])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}_events.csv"},
    )


@invigilator_bp.route("/session/<int:session_id>/export.json")
@role_required("invigilator", "admin")
def export_json(session_id):
    """JSON export of one candidate session's full event/violation timeline (Part 13)."""
    assessment_session = assessment_service.get_session(session_id)
    events = event_logger.get_events_in_window(assessment_session.user_id, start=assessment_session.started_at, limit=1000)

    payload = {
        "candidate": assessment_session.user.full_name,
        "email": assessment_session.user.email,
        "assessment": assessment_session.assessment.name,
        "session_id": session_id,
        "status": assessment_session.status,
        "integrity_score": assessment_session.user.integrity_score,
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "severity": e.severity,
                "description": e.description,
            }
            for e in events
        ],
    }

    return Response(
        json.dumps(payload, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}_events.json"},
    )

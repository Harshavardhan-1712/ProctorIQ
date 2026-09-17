"""
routes/preassessment.py
--------------------------
The pre-assessment workflow (Module 5, Parts 2-7):

    Identity Verification (reuses routes/camera.py — not duplicated here)
        -> Readiness Check -> Overview -> Terms -> Privacy -> Integrity
        Policy -> Declaration -> Final Confirmation -> Start Assessment

Each step is gated by a small piece of session state
(`_SESSION_STEP_KEY`) tracking the furthest step reached for the
assessment currently being entered, so a candidate can't skip ahead by
typing a later URL directly — every route re-checks it before
rendering. This is intentionally simple (an ordered int, not a state
machine library) since the flow is strictly linear.

Routes stay thin: readiness data comes from services/readiness_service.py,
declaration persistence is a single model write, and starting the
actual attempt delegates to services/assessment_service.py.
"""

from flask import Blueprint, render_template, redirect, url_for, session, jsonify, flash, request, current_app
from flask_login import login_required, current_user

from models import db
from models.declaration import CandidateDeclaration
from services import readiness_service, assessment_service, event_logger
from services.assessment_service import AssessmentError
from services.event_logger import SEVERITY_INFO

preassessment_bp = Blueprint("preassessment", __name__, url_prefix="/assessment")

# Step ordering — a candidate must reach step N-1 before step N renders.
STEP_READINESS = 1
STEP_OVERVIEW = 2
STEP_TERMS = 3
STEP_PRIVACY = 4
STEP_INTEGRITY_POLICY = 5
STEP_DECLARATION = 6
STEP_CONFIRM = 7

_SESSION_ASSESSMENT_ID = "preassessment_assessment_id"
_SESSION_STEP_KEY = "preassessment_max_step"


def _require_step(assessment_id: int, step: int):
    """
    Returns a redirect response if the candidate hasn't reached this
    step yet (or is mid-flow for a DIFFERENT assessment), else None.
    """
    if session.get(_SESSION_ASSESSMENT_ID) != assessment_id or session.get(_SESSION_STEP_KEY, 0) < step - 1:
        return redirect(url_for("preassessment.readiness", assessment_id=assessment_id))
    return None


def _advance_to(assessment_id: int, step: int):
    session[_SESSION_ASSESSMENT_ID] = assessment_id
    session[_SESSION_STEP_KEY] = max(session.get(_SESSION_STEP_KEY, 0), step)


@preassessment_bp.route("/")
@login_required
def list_assessments():
    """Menu page listing assessments currently available to the candidate."""
    assessments = assessment_service.get_active_assessments()
    return render_template("preassessment/list.html", assessments=assessments)


@preassessment_bp.route("/<int:assessment_id>/readiness")
@login_required
def readiness(assessment_id):
    """Step 1 — System Readiness Check (Part 3). Entry point of the whole flow."""
    assessment = assessment_service.get_assessment(assessment_id)
    session[_SESSION_ASSESSMENT_ID] = assessment_id
    session[_SESSION_STEP_KEY] = max(session.get(_SESSION_STEP_KEY, 0), STEP_READINESS - 1)
    return render_template("preassessment/readiness.html", assessment=assessment)


@preassessment_bp.route("/readiness/status")
@login_required
def readiness_status():
    """Polled by readiness.html's JS for the camera/face/lighting checks."""
    return jsonify(readiness_service.get_server_readiness())


@preassessment_bp.route("/<int:assessment_id>/readiness/continue", methods=["POST"])
@login_required
def readiness_continue(assessment_id):
    event_logger.log_event(current_user.id, "readiness_passed", SEVERITY_INFO)
    _advance_to(assessment_id, STEP_READINESS)
    return redirect(url_for("preassessment.overview", assessment_id=assessment_id))


@preassessment_bp.route("/<int:assessment_id>/overview")
@login_required
def overview(assessment_id):
    """Step 2 — Assessment Overview (Part 4)."""
    redirect_response = _require_step(assessment_id, STEP_OVERVIEW)
    if redirect_response:
        return redirect_response
    assessment = assessment_service.get_assessment(assessment_id)
    return render_template("preassessment/overview.html", assessment=assessment)


@preassessment_bp.route("/<int:assessment_id>/overview/continue", methods=["POST"])
@login_required
def overview_continue(assessment_id):
    _advance_to(assessment_id, STEP_OVERVIEW)
    return redirect(url_for("preassessment.terms", assessment_id=assessment_id))


@preassessment_bp.route("/<int:assessment_id>/terms")
@login_required
def terms(assessment_id):
    """Step 3 — Terms & Conditions (Part 5)."""
    redirect_response = _require_step(assessment_id, STEP_TERMS)
    if redirect_response:
        return redirect_response
    assessment = assessment_service.get_assessment(assessment_id)
    return render_template("preassessment/terms.html", assessment=assessment)


@preassessment_bp.route("/<int:assessment_id>/terms/continue", methods=["POST"])
@login_required
def terms_continue(assessment_id):
    _advance_to(assessment_id, STEP_TERMS)
    return redirect(url_for("preassessment.privacy", assessment_id=assessment_id))


@preassessment_bp.route("/<int:assessment_id>/privacy")
@login_required
def privacy(assessment_id):
    """Step 4 — Privacy Policy (Part 5)."""
    redirect_response = _require_step(assessment_id, STEP_PRIVACY)
    if redirect_response:
        return redirect_response
    assessment = assessment_service.get_assessment(assessment_id)
    return render_template("preassessment/privacy.html", assessment=assessment)


@preassessment_bp.route("/<int:assessment_id>/privacy/continue", methods=["POST"])
@login_required
def privacy_continue(assessment_id):
    _advance_to(assessment_id, STEP_PRIVACY)
    return redirect(url_for("preassessment.integrity_policy", assessment_id=assessment_id))


@preassessment_bp.route("/<int:assessment_id>/integrity-policy")
@login_required
def integrity_policy(assessment_id):
    """Step 5 — Integrity Policy (Part 5)."""
    redirect_response = _require_step(assessment_id, STEP_INTEGRITY_POLICY)
    if redirect_response:
        return redirect_response
    assessment = assessment_service.get_assessment(assessment_id)
    return render_template(
        "preassessment/integrity_policy.html",
        assessment=assessment,
        starting_score=current_app.config.get("INTEGRITY_STARTING_SCORE"),
        penalty_weights=current_app.config.get("PENALTY_WEIGHTS"),
        warning_threshold=current_app.config.get("INTEGRITY_WARNING_THRESHOLD"),
        high_risk_threshold=current_app.config.get("INTEGRITY_HIGH_RISK_THRESHOLD"),
    )


@preassessment_bp.route("/<int:assessment_id>/integrity-policy/continue", methods=["POST"])
@login_required
def integrity_policy_continue(assessment_id):
    _advance_to(assessment_id, STEP_INTEGRITY_POLICY)
    return redirect(url_for("preassessment.declaration", assessment_id=assessment_id))


@preassessment_bp.route("/<int:assessment_id>/declaration", methods=["GET", "POST"])
@login_required
def declaration(assessment_id):
    """Step 6 — Candidate Declaration (Part 6)."""
    redirect_response = _require_step(assessment_id, STEP_DECLARATION)
    if redirect_response:
        return redirect_response

    assessment = assessment_service.get_assessment(assessment_id)

    if request.method == "POST":
        checkbox_fields = [
            "confirmed_candidate", "ai_monitoring_ack", "webcam_monitoring_ack",
            "browser_monitoring_ack", "integrity_score_ack", "rules_ack",
            "log_storage_consent", "terms_ack",
        ]
        values = {field: request.form.get(field) == "on" for field in checkbox_fields}

        if not all(values.values()):
            flash("All acknowledgements must be accepted before you can continue.", "danger")
            return render_template("preassessment/declaration.html", assessment=assessment, values=values)

        record = CandidateDeclaration(user_id=current_user.id, assessment_id=assessment_id, **values)
        db.session.add(record)
        db.session.commit()
        event_logger.log_event(current_user.id, "declaration_submitted", SEVERITY_INFO)

        _advance_to(assessment_id, STEP_DECLARATION)
        return redirect(url_for("preassessment.confirm", assessment_id=assessment_id))

    return render_template("preassessment/declaration.html", assessment=assessment, values={})


@preassessment_bp.route("/<int:assessment_id>/confirm")
@login_required
def confirm(assessment_id):
    """Step 7 — Final Confirmation (Part 7)."""
    redirect_response = _require_step(assessment_id, STEP_CONFIRM)
    if redirect_response:
        return redirect_response
    assessment = assessment_service.get_assessment(assessment_id)
    return render_template("preassessment/confirm.html", assessment=assessment)


@preassessment_bp.route("/<int:assessment_id>/confirm/cancel")
@login_required
def confirm_cancel(assessment_id):
    """Candidate backed out at the final confirmation step."""
    session.pop(_SESSION_ASSESSMENT_ID, None)
    session.pop(_SESSION_STEP_KEY, None)
    flash("Assessment start was cancelled.", "info")
    return redirect(url_for("dashboard.dashboard"))


@preassessment_bp.route("/<int:assessment_id>/confirm/start", methods=["POST"])
@login_required
def confirm_start(assessment_id):
    """Candidate clicked Start Assessment on the final confirmation dialog."""
    redirect_response = _require_step(assessment_id, STEP_CONFIRM)
    if redirect_response:
        return redirect_response

    try:
        assessment_session = assessment_service.start_session(current_user.id, assessment_id)
    except AssessmentError as e:
        flash(str(e), "danger")
        return redirect(url_for("dashboard.dashboard"))

    event_logger.log_event(current_user.id, "assessment_started", SEVERITY_INFO)

    session.pop(_SESSION_ASSESSMENT_ID, None)
    session.pop(_SESSION_STEP_KEY, None)

    return redirect(url_for("assessment.session_view", session_id=assessment_session.id))

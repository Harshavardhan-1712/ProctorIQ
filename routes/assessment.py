"""
routes/assessment.py
-----------------------
The assessment-taking engine itself (Module 5, Part 8/10; extended in
Module 6): the timed, monitored question-answering UI, plus
submission, results, and reacting to invigilator pause/terminate
actions from the candidate's side.

Live monitoring during the assessment deliberately reuses the exact
same endpoints Module 4 already built (`/monitoring/start`,
`/monitoring/status`, `/monitoring/browser-event`) — see
templates/assessment/session.html's JS, which calls them directly.
Nothing about camera or browser monitoring is duplicated here; this
blueprint only owns the question/answer/timer/submission logic.
"""

from flask import Blueprint, render_template, redirect, url_for, jsonify, request, abort
from flask_login import login_required, current_user

from services import assessment_service, event_logger, integrity_service
from services.assessment_service import AssessmentError
from services.event_logger import SEVERITY_INFO

assessment_bp = Blueprint("assessment", __name__, url_prefix="/assessment")

# Statuses that mean "this session has a final result to show" — used
# in a couple of places below to avoid repeating the same tuple.
_FINISHED_STATUSES = ("submitted", "auto_submitted", "terminated")


def _ensure_owns_session(assessment_session):
    """A candidate may only view/act on their own session."""
    if assessment_session.user_id != current_user.id:
        abort(403)


@assessment_bp.route("/session/<int:session_id>")
@login_required
def session_view(session_id):
    """
    The main exam-taking page: question card, palette, timer, and the
    live-monitoring sidebar (camera + integrity gauge).
    """
    assessment_session = assessment_service.get_session(session_id)
    _ensure_owns_session(assessment_session)

    if assessment_session.status in _FINISHED_STATUSES:
        return redirect(url_for("assessment.result", session_id=session_id))

    if assessment_session.status == "paused":
        return render_template("assessment/paused.html", assessment_session=assessment_session)

    if assessment_service.is_expired(assessment_session):
        _finalize_submission(assessment_session, auto_submitted=True)
        return redirect(url_for("assessment.result", session_id=session_id))

    questions = assessment_session.assessment.questions
    answers_map = assessment_service.get_answers_map(assessment_session)

    # Per-candidate option shuffling (Part 9) — deterministic per
    # (session, question), so the order is stable across reloads.
    shuffled_options_by_question = {
        q.id: assessment_service.shuffled_options(assessment_session, q) for q in questions
    }

    return render_template(
        "assessment/session.html",
        assessment_session=assessment_session,
        assessment=assessment_session.assessment,
        questions=questions,
        answers_map=answers_map,
        shuffled_options_by_question=shuffled_options_by_question,
        time_remaining=assessment_service.time_remaining_seconds(assessment_session),
    )


@assessment_bp.route("/session/<int:session_id>/state")
@login_required
def session_state(session_id):
    """
    Polled by the exam page's JS to keep the timer/palette in sync,
    detect server-side auto-submit, and detect invigilator
    pause/terminate actions (time expiry and invigilator actions are
    both authoritative on the server, never trusted from the client).
    """
    assessment_session = assessment_service.get_session(session_id)
    _ensure_owns_session(assessment_session)

    if assessment_session.status == "paused":
        return jsonify(status="paused", expired=False, note=assessment_session.invigilator_note)

    if assessment_session.status in _FINISHED_STATUSES:
        return jsonify(status=assessment_session.status, expired=True)

    if assessment_service.is_expired(assessment_session):
        _finalize_submission(assessment_session, auto_submitted=True)
        return jsonify(status="auto_submitted", expired=True)

    answers_map = assessment_service.get_answers_map(assessment_session)
    palette = [
        {
            "question_id": q.id,
            "answered": q.id in answers_map and answers_map[q.id].selected_option_id is not None,
            "marked_for_review": q.id in answers_map and answers_map[q.id].marked_for_review,
        }
        for q in assessment_session.assessment.questions
    ]

    return jsonify(
        status="in_progress",
        expired=False,
        time_remaining=assessment_service.time_remaining_seconds(assessment_session),
        integrity_score=current_user.integrity_score,
        palette=palette,
    )


@assessment_bp.route("/session/<int:session_id>/answer", methods=["POST"])
@login_required
def answer(session_id):
    """Auto-save one answer (selected option, mark-for-review flag, or a Clear Response)."""
    assessment_session = assessment_service.get_session(session_id)
    _ensure_owns_session(assessment_session)

    if assessment_session.status != "in_progress":
        return jsonify(success=False, error="This assessment is not currently active."), 400

    payload = request.get_json(silent=True) or {}
    question_id = payload.get("question_id")
    selected_option_id = payload.get("selected_option_id")
    marked_for_review = payload.get("marked_for_review")
    clear = bool(payload.get("clear", False))

    if question_id is None:
        return jsonify(success=False, error="question_id is required."), 400

    assessment_service.save_answer(
        assessment_session,
        question_id=question_id,
        selected_option_id=selected_option_id,
        marked_for_review=marked_for_review,
        clear=clear,
    )
    return jsonify(success=True)


@assessment_bp.route("/session/<int:session_id>/progress", methods=["POST"])
@login_required
def progress(session_id):
    """
    Fire-and-forget: records which question the candidate is currently
    viewing, purely for invigilator visibility (Part 4's "Current
    Question" column). Never blocks or errors the candidate's UI.
    """
    assessment_session = assessment_service.get_session(session_id)
    _ensure_owns_session(assessment_session)

    if assessment_session.status == "in_progress":
        payload = request.get_json(silent=True) or {}
        assessment_service.update_current_question(assessment_session, payload.get("index", 0))

    return jsonify(success=True)


@assessment_bp.route("/session/<int:session_id>/submit", methods=["POST"])
@login_required
def submit(session_id):
    """Candidate-initiated final submission."""
    assessment_session = assessment_service.get_session(session_id)
    _ensure_owns_session(assessment_session)

    if assessment_session.status == "in_progress":
        _finalize_submission(assessment_session, auto_submitted=False)

    return jsonify(success=True, redirect_url=url_for("assessment.result", session_id=session_id))


def _finalize_submission(assessment_session, auto_submitted: bool):
    """Shared by both candidate-initiated and time-expiry submission paths."""
    assessment_service.submit_session(
        assessment_session,
        integrity_score=current_user.integrity_score,
        auto_submitted=auto_submitted,
    )
    event_type = "assessment_auto_submitted" if auto_submitted else "assessment_submitted"
    event_logger.log_event(current_user.id, event_type, SEVERITY_INFO)

    # Milestone 3: run the pattern-based alert rules (repeated tab
    # switching, extended face absence) once against the now-complete
    # session, so alerts based on a session-wide pattern aren't missed
    # just because no single event crossed a per-event threshold.
    from services import alert_service
    alert_service.evaluate_session_for_alerts(assessment_session)


@assessment_bp.route("/session/<int:session_id>/result")
@login_required
def result(session_id):
    """Results page — score, pass/fail, and the integrity score as it stood at submission."""
    assessment_session = assessment_service.get_session(session_id)
    _ensure_owns_session(assessment_session)

    result_record = assessment_service.get_result(session_id)
    if result_record is None:
        # Session hasn't actually been submitted yet — nothing to show.
        return redirect(url_for("assessment.session_view", session_id=session_id))

    violations = event_logger.get_violations_in_window(
        assessment_session.user_id, start=assessment_session.started_at, end=assessment_session.submitted_at
    )

    return render_template(
        "assessment/result.html",
        assessment_session=assessment_session,
        assessment=assessment_session.assessment,
        result=result_record,
        risk_label=integrity_service.risk_label(assessment_session.integrity_score_at_submit or 100),
        time_taken_seconds=assessment_service.time_taken_seconds(assessment_session),
        violations_count=len(violations),
    )

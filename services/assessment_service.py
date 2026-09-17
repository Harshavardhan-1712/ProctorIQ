"""
services/assessment_service.py
---------------------------------
Business logic for the Assessment Engine (Module 5, Part 8).

Kept separate from routes/assessment.py the same way
services/auth_service.py is kept separate from routes/auth.py: routes
parse the request and render a response; this module owns session
lifecycle, answer persistence, and scoring so it's independently
testable and reusable (e.g. by a future admin "re-grade this session"
tool without going through HTTP at all).
"""

from datetime import datetime, timedelta
import random

from models import db
from models.assessment import Assessment, AssessmentSession, CandidateAnswer, AssessmentResult


class AssessmentError(Exception):
    """Raised for invalid assessment operations (e.g. attempt limit exceeded)."""
    pass


def get_active_assessments():
    """All assessments currently available to candidates."""
    return Assessment.query.filter_by(is_active=True).order_by(Assessment.id).all()


def get_assessment(assessment_id: int) -> Assessment:
    return Assessment.query.get_or_404(assessment_id)


def count_attempts(user_id: int, assessment_id: int) -> int:
    """How many sessions (of any status) this candidate has already started for this assessment."""
    return AssessmentSession.query.filter_by(user_id=user_id, assessment_id=assessment_id).count()


def get_in_progress_session(user_id: int, assessment_id: int):
    """
    An existing, still-running session for this candidate+assessment,
    if one exists — this is what powers "resume support": if the
    candidate's browser crashes or they navigate away mid-assessment,
    coming back finds the same session (and its saved answers) rather
    than starting a fresh attempt (and burning another one of their
    limited allowed_attempts).
    """
    return (
        AssessmentSession.query.filter_by(user_id=user_id, assessment_id=assessment_id, status="in_progress")
        .order_by(AssessmentSession.started_at.desc())
        .first()
    )


def get_current_session_for_user(user_id: int):
    """
    Milestone 3 helper: the candidate's most recent in-progress session,
    regardless of which assessment it belongs to. Used by
    routes/monitoring.py (which is shared across all assessments and
    doesn't otherwise know "which AssessmentSession is this candidate
    in right now") to scope Milestone 3 evidence capture/alerts to the
    correct session without duplicating any session-lookup logic.
    """
    return (
        AssessmentSession.query.filter_by(user_id=user_id, status="in_progress")
        .order_by(AssessmentSession.started_at.desc())
        .first()
    )


def start_session(user_id: int, assessment_id: int) -> AssessmentSession:
    """
    Begin a new attempt, or resume an existing in-progress one.

    Raises AssessmentError if the candidate has already used up all
    of their allowed_attempts for this assessment (and has no
    in-progress session to resume).
    """
    existing = get_in_progress_session(user_id, assessment_id)
    if existing:
        return existing

    assessment = get_assessment(assessment_id)

    if count_attempts(user_id, assessment_id) >= assessment.allowed_attempts:
        raise AssessmentError("You have already used all allowed attempts for this assessment.")

    now = datetime.utcnow()
    session = AssessmentSession(
        user_id=user_id,
        assessment_id=assessment_id,
        started_at=now,
        ends_at=now + timedelta(minutes=assessment.duration_minutes),
        status="in_progress",
    )
    db.session.add(session)
    db.session.commit()
    return session


def get_session(session_id: int) -> AssessmentSession:
    return AssessmentSession.query.get_or_404(session_id)


def time_remaining_seconds(session: AssessmentSession) -> int:
    """Seconds left on the timer, floored at 0 (never negative — the client shouldn't show '-00:05')."""
    remaining = (session.ends_at - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


def is_expired(session: AssessmentSession) -> bool:
    return datetime.utcnow() >= session.ends_at


def save_answer(session: AssessmentSession, question_id: int, selected_option_id: int = None, marked_for_review: bool = None, clear: bool = False) -> CandidateAnswer:
    """
    Create or update this candidate's answer to one question within
    this session.

    `selected_option_id=None` (the default) means "don't touch the
    selection" — it's the sentinel for a mark-for-review-only update.
    To actually CLEAR a previously selected answer (the "Clear
    Response" button), pass `clear=True` explicitly; this is a
    separate flag rather than overloading `selected_option_id=None`
    for both meanings, which would make "no change" and "clear it"
    indistinguishable from the caller's side.
    """
    answer = CandidateAnswer.query.filter_by(session_id=session.id, question_id=question_id).first()

    if answer is None:
        answer = CandidateAnswer(session_id=session.id, question_id=question_id)
        db.session.add(answer)

    if clear:
        answer.selected_option_id = None
    elif selected_option_id is not None:
        answer.selected_option_id = selected_option_id

    if marked_for_review is not None:
        answer.marked_for_review = marked_for_review

    answer.answered_at = datetime.utcnow()
    db.session.commit()
    return answer


def get_answers_map(session: AssessmentSession) -> dict:
    """{question_id: CandidateAnswer} for every answer saved so far in this session."""
    return {a.question_id: a for a in session.answers}


def update_current_question(session: AssessmentSession, index: int) -> None:
    """
    Best-effort progress tracking for the invigilator dashboard's
    "Current Question" column — not scoring-relevant, so failures here
    should never block the candidate's UI.
    """
    session.current_question_index = max(0, int(index))
    db.session.commit()


def submit_session(session: AssessmentSession, integrity_score: int, auto_submitted: bool = False) -> AssessmentResult:
    """
    Score the session and create its AssessmentResult. Idempotent: if
    a result already exists (e.g. a duplicate submit request), the
    existing one is returned rather than creating a second one.
    """
    existing_result = AssessmentResult.query.filter_by(session_id=session.id).first()
    if existing_result:
        return existing_result

    assessment = session.assessment
    answers_by_question = get_answers_map(session)

    score = 0.0
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0

    for question in assessment.questions:
        answer = answers_by_question.get(question.id)

        if answer is None or answer.selected_option_id is None:
            unanswered_count += 1
            continue

        if answer.selected_option and answer.selected_option.is_correct:
            score += question.marks
            correct_count += 1
        else:
            incorrect_count += 1
            if assessment.negative_marking_enabled:
                score -= assessment.negative_marking_value

    total_marks = assessment.total_marks
    percentage = (score / total_marks * 100) if total_marks else 0.0

    # Module 7, Part 3: prefer an absolute-marks threshold when the
    # assessment defines one (e.g. "12 marks to pass"); fall back to
    # the percentage-based threshold otherwise, so assessments seeded
    # before this field existed (Module 5's sample assessment) keep
    # scoring exactly as they did before.
    if assessment.passing_marks is not None:
        passed = max(0.0, score) >= assessment.passing_marks
    else:
        passed = percentage >= assessment.passing_score_percent

    result = AssessmentResult(
        session_id=session.id,
        user_id=session.user_id,
        assessment_id=session.assessment_id,
        score=max(0.0, score),
        total_marks=total_marks,
        percentage=round(max(0.0, percentage), 2),
        passed=passed,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        unanswered_count=unanswered_count,
    )
    db.session.add(result)

    session.status = "auto_submitted" if auto_submitted else "submitted"
    session.submitted_at = datetime.utcnow()
    session.integrity_score_at_submit = integrity_score

    db.session.commit()
    return result


def get_result(session_id: int):
    return AssessmentResult.query.filter_by(session_id=session_id).first()


def time_taken_seconds(session: AssessmentSession) -> int:
    """
    How long the candidate actually spent on this attempt — for the
    Result page's "Time Taken" display (Module 7, Part 13). Uses
    `submitted_at` if the session has finished; if called on a
    still-in-progress session (shouldn't normally happen from the
    result page, but defensively), falls back to "now".
    """
    end = session.submitted_at or datetime.utcnow()
    return max(0, int((end - session.started_at).total_seconds()))


# ---------------------------------------------------------------------
# Invigilator controls (Module 6, Part 4)
# ---------------------------------------------------------------------

def get_active_sessions():
    """
    Every currently in_progress or paused session, across all
    candidates — the core data feed for the invigilator dashboard.
    Ordered by most-recently-started first.
    """
    return (
        AssessmentSession.query.filter(AssessmentSession.status.in_(["in_progress", "paused"]))
        .order_by(AssessmentSession.started_at.desc())
        .all()
    )


def pause_session(session: AssessmentSession, note: str = None) -> AssessmentSession:
    """
    Invigilator-initiated pause. The candidate's timer effectively
    freezes (time elapsed while paused is credited back on resume —
    see resume_session below), and the candidate-facing UI blocks
    further interaction until resumed.
    """
    if session.status != "in_progress":
        raise AssessmentError("Only an in-progress session can be paused.")

    session.status = "paused"
    session.paused_at = datetime.utcnow()
    session.invigilator_note = note
    db.session.commit()
    return session


def resume_session(session: AssessmentSession) -> AssessmentSession:
    """
    Resume a paused session. Shifts `ends_at` forward by however long
    it was paused, so the candidate doesn't lose exam time to an
    invigilator's pause.
    """
    if session.status != "paused":
        raise AssessmentError("Only a paused session can be resumed.")

    if session.paused_at:
        paused_duration = datetime.utcnow() - session.paused_at
        session.ends_at = session.ends_at + paused_duration

    session.status = "in_progress"
    session.paused_at = None
    db.session.commit()
    return session


def terminate_session(session: AssessmentSession, integrity_score: int, note: str = None) -> AssessmentResult:
    """
    Invigilator-initiated termination — immediately and permanently
    ends the attempt. Scores whatever answers were saved up to this
    point (same scoring path as a normal submit), so the candidate
    still gets a real result rather than a void attempt.
    """
    if session.status not in ("in_progress", "paused"):
        raise AssessmentError("Only an active session can be terminated.")

    session.invigilator_note = note
    result = submit_session(session, integrity_score=integrity_score, auto_submitted=False)
    session.status = "terminated"
    db.session.commit()
    return result


# ---------------------------------------------------------------------
# Per-candidate option shuffling (Module 6, Part 9)
# ---------------------------------------------------------------------

def shuffled_options(session: AssessmentSession, question):
    """
    Return this question's options in an order that's shuffled
    per-candidate-per-question, but DETERMINISTIC across repeated
    calls (page reloads, palette navigation) — the candidate must see
    the same order every time within one attempt, or "Option B" would
    silently point at a different answer choice each time they revisit
    a question.

    Seeded from (session.id, question.id) rather than pure randomness,
    so no extra state needs to be stored anywhere to reproduce it.
    """
    options = list(question.options)
    rng = random.Random(f"{session.id}:{question.id}")
    rng.shuffle(options)
    return options


# ---------------------------------------------------------------------
# Candidate performance stats (Module 6, Part 7 — dashboard)
# ---------------------------------------------------------------------

def get_candidate_stats(user_id: int) -> dict:
    """
    Aggregate stats for the candidate dashboard: completed-assessment
    count, average score/integrity, violation count, and a recent
    performance trend — all computed from real AssessmentResult /
    AssessmentSession rows, not placeholder data.
    """
    results = (
        AssessmentResult.query.filter_by(user_id=user_id)
        .order_by(AssessmentResult.submitted_at.desc())
        .all()
    )

    completed_count = len(results)
    average_score = round(sum(r.percentage for r in results) / completed_count, 1) if completed_count else 0.0

    sessions_with_score = [
        s.integrity_score_at_submit
        for s in AssessmentSession.query.filter_by(user_id=user_id).all()
        if s.integrity_score_at_submit is not None
    ]
    average_integrity = round(sum(sessions_with_score) / len(sessions_with_score), 1) if sessions_with_score else 100.0

    # Trend: oldest-to-newest percentage for the last 8 attempts, for a
    # simple sparkline on the dashboard.
    trend = [r.percentage for r in reversed(results[:8])]

    return {
        "completed_count": completed_count,
        "average_score": average_score,
        "average_integrity": average_integrity,
        "recent_results": results[:5],
        "trend": trend,
    }

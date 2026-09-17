"""
models/assessment.py
-----------------------
Core data model for the Assessment Engine (Module 5, Parts 8-9).

Six related tables:
    Assessment        — a test definition (name, duration, scoring rules)
    Question           — one MCQ belonging to an Assessment
    Option              — one answer choice belonging to a Question
    AssessmentSession  — one candidate's attempt at an Assessment (timer,
                          status, links to the live monitoring/integrity
                          system via `user_id`)
    CandidateAnswer     — one candidate's answer to one Question within
                          a specific AssessmentSession
    AssessmentResult    — the final scored outcome of a submitted session

Design notes for future modules:
- `AssessmentSession.status` is a plain string ("in_progress" /
  "paused" / "submitted" / "auto_submitted" / "terminated") rather
  than an enum class, matching the same pattern used for
  ExamEvent.severity — new statuses never require a migration.
- Monitoring/integrity data already lives on `User` (integrity_score)
  and `ExamEvent` (user_id-scoped); AssessmentSession doesn't duplicate
  it, it just provides the time window (`started_at`/`submitted_at`)
  a future reporting module can use to filter ExamEvent rows down to
  "what happened during this specific assessment attempt."
- Question/Option order is stored explicitly (`order` column) rather
  than relying on primary-key order, so an admin question-bank editor
  (Part 8, deferred) can reorder without renumbering IDs.

Naming note (Module 6, Part 10): the spec asks for "AssessmentAttempt",
"Violation", and "MonitoringEvent" tables. This module deliberately
does NOT create three near-duplicate tables for these — they already
exist under different, established names:
    AssessmentAttempt  -> AssessmentSession (this file)   — one
                           candidate's timed attempt at an Assessment
    MonitoringEvent     -> ExamEvent (models/exam_event.py) — every
                           observed event, camera/browser/system
    Violation            -> ExamEvent rows where severity is "warning"
                           or "critical" (see event_logger.get_violations())
Creating separate tables with overlapping meaning would violate Part
18's "no duplicate code" requirement and fragment the audit trail
across two places that would need to be kept in sync. See the README's
Database Schema section for the full mapping.
"""

from datetime import datetime

from models import db


class Assessment(db.Model):
    """A test definition — what a candidate can be assigned to take."""

    __tablename__ = "assessments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    passing_score_percent = db.Column(db.Integer, nullable=False, default=50)

    # Module 7, Part 3: an absolute-marks passing threshold (e.g. "12
    # marks to pass"), as distinct from `passing_score_percent`. Kept
    # as a SEPARATE nullable column rather than replacing
    # passing_score_percent, so Module 5's existing seeded assessment
    # (which only ever set the percent field) keeps working unchanged.
    # services/assessment_service.py prefers `passing_marks` when it's
    # set, and falls back to `passing_score_percent` otherwise — see
    # that module's submit_session() for the exact rule.
    passing_marks = db.Column(db.Float, nullable=True)

    allowed_attempts = db.Column(db.Integer, nullable=False, default=1)
    negative_marking_enabled = db.Column(db.Boolean, nullable=False, default=False)
    negative_marking_value = db.Column(db.Float, nullable=False, default=0.0)
    question_pattern = db.Column(db.String(100), nullable=False, default="Multiple Choice (Single Answer)")
    monitoring_enabled = db.Column(db.Boolean, nullable=False, default=True)

    # Free-text instructions shown on the Assessment Details page
    # (Module 7, Part 3) — separate from `description` (a short
    # one-line summary shown on the assessment cards) since
    # instructions are typically longer and more procedural.
    instructions = db.Column(db.Text, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    questions = db.relationship(
        "Question", backref="assessment", order_by="Question.order", cascade="all, delete-orphan"
    )

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def total_marks(self) -> float:
        return sum(q.marks for q in self.questions)

    def __repr__(self) -> str:
        return f"<Assessment id={self.id} name={self.name!r}>"


class Question(db.Model):
    """One multiple-choice question belonging to an Assessment."""

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"), nullable=False, index=True)

    text = db.Column(db.Text, nullable=False)
    marks = db.Column(db.Float, nullable=False, default=1.0)
    order = db.Column(db.Integer, nullable=False, default=0)

    # Metadata (Module 6, Part 9). Plain strings, not lookup tables —
    # a real question bank editor (Part 8, deferred) would likely want
    # a proper Category table with its own CRUD, but that's premature
    # without the admin UI to manage it; a free-text field is enough to
    # unblock filtering/display today without over-building.
    category = db.Column(db.String(80), nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="Medium")  # "Easy" | "Medium" | "Hard"

    options = db.relationship(
        "Option", backref="question", order_by="Option.order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} assessment_id={self.assessment_id}>"


class Option(db.Model):
    """One answer choice belonging to a Question."""

    __tablename__ = "options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True)

    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    order = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Option id={self.id} question_id={self.question_id} correct={self.is_correct}>"


class AssessmentSession(db.Model):
    """One candidate's attempt at an Assessment — the timer/status/lifecycle record."""

    __tablename__ = "assessment_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"), nullable=False, index=True)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=True)

    # "in_progress" | "paused" | "submitted" | "auto_submitted" | "terminated"
    status = db.Column(db.String(20), nullable=False, default="in_progress", index=True)

    # When the session was most recently paused by an invigilator — used
    # to shift `ends_at` forward by the paused duration on resume, so a
    # candidate never loses exam time to an invigilator-initiated pause.
    paused_at = db.Column(db.DateTime, nullable=True)

    # Free-text reason recorded when an invigilator pauses or terminates
    # a session — shown back to the candidate and kept in the audit trail.
    invigilator_note = db.Column(db.String(255), nullable=True)

    # Updated (fire-and-forget, best-effort) as the candidate navigates
    # between questions — lets the invigilator dashboard show genuine
    # "Current Question" progress rather than a placeholder. Not used
    # for anything scoring-related, purely a live-visibility signal.
    current_question_index = db.Column(db.Integer, nullable=False, default=0)

    # Snapshot of the candidate's integrity score at submission time —
    # kept here (in addition to the live User.integrity_score, which
    # keeps changing) so a result/report page shows the score as it
    # stood when THIS attempt ended, not whatever it is now.
    integrity_score_at_submit = db.Column(db.Integer, nullable=True)

    assessment = db.relationship("Assessment")
    user = db.relationship("User")
    answers = db.relationship("CandidateAnswer", backref="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AssessmentSession id={self.id} user_id={self.user_id} status={self.status}>"


class CandidateAnswer(db.Model):
    """One candidate's answer to one Question within a specific AssessmentSession."""

    __tablename__ = "candidate_answers"
    __table_args__ = (db.UniqueConstraint("session_id", "question_id", name="uq_answer_per_question"),)

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("options.id"), nullable=True)

    marked_for_review = db.Column(db.Boolean, nullable=False, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    question = db.relationship("Question")
    selected_option = db.relationship("Option")

    def __repr__(self) -> str:
        return f"<CandidateAnswer session_id={self.session_id} question_id={self.question_id}>"


class AssessmentResult(db.Model):
    """The final scored outcome of a submitted AssessmentSession."""

    __tablename__ = "assessment_results"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"), nullable=False, index=True)

    score = db.Column(db.Float, nullable=False, default=0.0)
    total_marks = db.Column(db.Float, nullable=False, default=0.0)
    percentage = db.Column(db.Float, nullable=False, default=0.0)
    passed = db.Column(db.Boolean, nullable=False, default=False)

    correct_count = db.Column(db.Integer, nullable=False, default=0)
    incorrect_count = db.Column(db.Integer, nullable=False, default=0)
    unanswered_count = db.Column(db.Integer, nullable=False, default=0)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship("AssessmentSession")
    assessment = db.relationship("Assessment")

    def __repr__(self) -> str:
        return f"<AssessmentResult session_id={self.session_id} score={self.score}/{self.total_marks}>"

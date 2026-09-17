"""
models/analytics.py
--------------------
Milestone 3 database tables — Integrity Analytics, Alerts, Evidence and
AI Reporting.

Design notes:
- These tables deliberately reuse the existing `AssessmentSession` as
  "the session" (see models/assessment.py's naming-note docstring —
  Milestone 3's spec calls this a "session" but the concept already
  exists) and the existing `User` as "the candidate". No duplicate
  session/candidate tables are created here.
- `ExamEvent` (models/exam_event.py) remains the single source of raw
  monitoring events. Nothing here duplicates it — Alert/Incident/
  Evidence rows are created FROM specific ExamEvent rows (see
  `source_event_id`), and IntegrityScore/analytics are computed
  on-demand from ExamEvent by services/integrity_scoring_service.py
  rather than being a separately-maintained duplicate ledger.
- `ClusterAssignment` is the one exception that IS persisted rather
  than computed on every page load: K-Means cluster IDs are only
  meaningful relative to the specific model run that produced them
  (Milestone 3 spec, "K-Means cluster numbers have no inherent
  meaning"), so a `run_id` groups all assignments from one clustering
  run together and lets the UI show a stable, already-interpreted
  result instead of an internal integer that changes on every re-run.
"""

from datetime import datetime

from models import db


class Alert(db.Model):
    """An examiner-facing alert raised for a configured critical event (Milestone 3, Part 19)."""

    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    event_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="warning")  # "warning" | "critical"
    description = db.Column(db.String(255), nullable=False)

    # "OPEN" | "ACKNOWLEDGED" | "RESOLVED"
    status = db.Column(db.String(20), nullable=False, default="OPEN", index=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    session = db.relationship("AssessmentSession")
    user = db.relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<Alert id={self.id} session_id={self.session_id} status={self.status}>"


class Incident(db.Model):
    """A confirmed, evidence-worthy incident within a session (Milestone 3, Part 22)."""

    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # The ExamEvent row that triggered this incident, if any — keeps the
    # incident traceable back to the raw monitoring event without
    # duplicating its fields.
    source_event_id = db.Column(db.Integer, db.ForeignKey("exam_events.id"), nullable=True)

    event_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="warning")
    description = db.Column(db.String(255), nullable=False)
    action_taken = db.Column(db.String(255), nullable=True)

    evidence_id = db.Column(db.Integer, db.ForeignKey("evidence.id"), nullable=True)

    # "OPEN" | "UNDER_REVIEW" | "CLEARED" | "CONFIRMED" — examiner disposition.
    examiner_status = db.Column(db.String(20), nullable=False, default="OPEN")

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    session = db.relationship("AssessmentSession")
    user = db.relationship("User")
    evidence = db.relationship("Evidence", foreign_keys=[evidence_id])

    def __repr__(self) -> str:
        return f"<Incident id={self.id} session_id={self.session_id} type={self.event_type}>"


class Evidence(db.Model):
    """
    Secure screenshot/evidence storage (Milestone 3, Part 20-23).

    Screenshots are stored as a Base64-encoded string in a SQLite TEXT
    column rather than a raw BLOB of binary bytes. This keeps the row
    portable across SQLAlchemy backends and avoids binary-safety issues
    with naive BLOB handling, at the cost of ~33% storage overhead —
    an acceptable trade-off given evidence is only captured for
    configured critical incidents (Part 20), not continuously.
    """

    __tablename__ = "evidence"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    incident_id = db.Column(db.Integer, nullable=True)  # set after the Incident row is created (avoids a cycle)

    event_type = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    mime_type = db.Column(db.String(50), nullable=False, default="image/png")
    # Base64-encoded image bytes.
    image_data = db.Column(db.Text, nullable=False)
    # SHA-256 hex digest of the RAW (decoded) image bytes — an
    # integrity-control mechanism (Part 23), not a legal-admissibility
    # claim.
    sha256_hash = db.Column(db.String(64), nullable=False)

    session = db.relationship("AssessmentSession")
    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<Evidence id={self.id} session_id={self.session_id} type={self.event_type}>"


class AIIntegrityReport(db.Model):
    """A generated (LangChain or deterministic-fallback) integrity report for one session."""

    __tablename__ = "ai_integrity_reports"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    integrity_score = db.Column(db.Integer, nullable=False)
    risk_level = db.Column(db.String(10), nullable=False)

    summary_text = db.Column(db.Text, nullable=False)
    recommendations_text = db.Column(db.Text, nullable=True)

    # Structured evidence handed to the agent, kept alongside the
    # generated text so an examiner can verify the summary against
    # exactly what the agent was given — never re-derived from memory.
    structured_input_json = db.Column(db.Text, nullable=False)

    model_used = db.Column(db.String(80), nullable=False)
    is_fallback = db.Column(db.Boolean, nullable=False, default=False)

    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship("AssessmentSession")
    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<AIIntegrityReport id={self.id} session_id={self.session_id} risk={self.risk_level}>"


class ClusterRun(db.Model):
    """Metadata for one K-Means clustering run over session-level features."""

    __tablename__ = "cluster_runs"

    id = db.Column(db.Integer, primary_key=True)
    run_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    n_clusters = db.Column(db.Integer, nullable=False)
    n_sessions = db.Column(db.Integer, nullable=False)
    features_json = db.Column(db.Text, nullable=False)  # list of feature names used
    data_source = db.Column(db.String(20), nullable=False, default="REAL")  # "REAL" | "SYNTHETIC"

    assignments = db.relationship("ClusterAssignment", backref="run", cascade="all, delete-orphan")


class ClusterAssignment(db.Model):
    """One session's cluster assignment from a specific ClusterRun."""

    __tablename__ = "cluster_assignments"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("cluster_runs.id"), nullable=False, index=True)
    session_id = db.Column(db.Integer, nullable=True, index=True)  # null for synthetic sessions
    synthetic_session_id = db.Column(db.String(40), nullable=True)

    cluster_index = db.Column(db.Integer, nullable=False)  # raw KMeans label (0..k-1), no inherent meaning
    cluster_label = db.Column(db.String(40), nullable=False)  # interpreted label, e.g. "High-risk pattern"

    def __repr__(self) -> str:
        return f"<ClusterAssignment run_id={self.run_id} session_id={self.session_id} cluster={self.cluster_label}>"

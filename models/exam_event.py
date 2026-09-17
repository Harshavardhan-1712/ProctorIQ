"""
models/exam_event.py
----------------------
ExamEvent — a single monitoring/audit log entry for a candidate.

Every observable event during registration, login, and (starting in
Module 4) live exam monitoring is written here: identity events
("Candidate Registered", "Face Verified"), session events
("Dashboard Accessed", "Monitoring Started"), camera-monitoring events
("Face Missing", "Multiple Faces", "Camera Lost"), and browser-integrity
events ("Tab Switched", "Fullscreen Exit", "Copy Attempt", ...).

Design notes for future modules:
- `event_type` is a short machine-readable slug (e.g. "tab_switch"),
  while `description` is the human-readable sentence shown in the
  Recent Activity timeline and Violations/Reports pages. Keeping both
  lets the UI render nice text while services/integrity_service.py can
  still branch on the stable `event_type` key.
- `severity` is a plain string ("info" / "warning" / "critical") rather
  than an enum class, deliberately, so new severities or event types
  never require a schema migration — just a new string value.
- This table is intentionally NOT scoped to an "ExamSession" model
  (there isn't one yet). services/integrity_service.py derives the
  *current* exam's integrity score from events after the most recent
  "monitoring_started" event for that user. A future ExamSession
  module can add a nullable `session_id` column here without breaking
  anything that already queries by `user_id` + `timestamp`.
"""

from datetime import datetime

from models import db


class ExamEvent(db.Model):
    """A single monitoring/audit log entry."""

    __tablename__ = "exam_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Short, stable, machine-readable slug — e.g. "tab_switch", "no_face".
    event_type = db.Column(db.String(50), nullable=False, index=True)

    # "info" | "warning" | "critical" — drives badge color in the UI.
    severity = db.Column(db.String(20), nullable=False, default="info")

    # Human-readable sentence for the activity timeline / reports table.
    description = db.Column(db.String(255), nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Convenience relationship — lets `event.user` be accessed without a
    # manual query, and `user.events` (via backref) for the reverse direction.
    user = db.relationship("User", backref=db.backref("events", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<ExamEvent id={self.id} user_id={self.user_id} type={self.event_type} severity={self.severity}>"

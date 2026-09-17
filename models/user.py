"""
models/user.py
--------------
Defines the User (Candidate) database model.

Design notes for future modules:
- `photo_path` is nullable today. The upcoming OpenCV face-monitoring
  module will populate this after capturing a reference photo — no
  schema change needed then.
- Relationships to future tables (ExamSession, IntegrityScore,
  EvidenceLog, BrowserEvent, etc.) can be added later via
  `db.relationship(...)` without touching this file's existing fields.
"""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from models import db


class User(db.Model, UserMixin):
    """Represents a candidate account."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Nullable — populated later by the face-capture module.
    photo_path = db.Column(db.String(255), nullable=True)

    # Running integrity score for the candidate's current/most recent
    # monitored exam session. Reset to 100 whenever monitoring starts
    # (see services/integrity_service.py) and decremented as
    # violations are logged during that session.
    integrity_score = db.Column(db.Integer, nullable=False, default=100)

    # "candidate" | "invigilator" | "admin" — plain string rather than
    # an Enum class, matching the same convention as ExamEvent.severity
    # and AssessmentSession.status: new roles never require a migration.
    # Every account defaults to "candidate"; invigilator/admin accounts
    # are provisioned via seed_database.py or directly in the database
    # until a Part 8 admin UI exists for managing them.
    role = db.Column(db.String(20), nullable=False, default="candidate")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def is_invigilator(self) -> bool:
        return self.role in ("invigilator", "admin")

    def is_admin(self) -> bool:
        return self.role == "admin"

    # ------------------------------------------------------------------
    # Password helpers — keep hashing/verification logic co-located with
    # the model so services never touch raw password_hash directly.
    # ------------------------------------------------------------------
    def set_password(self, plain_password: str) -> None:
        """Hash and store the given plaintext password."""
        self.password_hash = generate_password_hash(plain_password)

    def check_password(self, plain_password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, plain_password)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"

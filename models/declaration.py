"""
models/declaration.py
------------------------
CandidateDeclaration — records the exact acknowledgements a candidate
agreed to before starting a specific assessment attempt (Module 5,
Part 6).

Stored as individual boolean columns (rather than one "agreed" flag)
so that if the wording or requirements of any single acknowledgement
change in the future, historical records still show precisely which
statements THIS candidate agreed to at THIS point in time — important
for an audit trail, which is the entire point of this table.
"""

from datetime import datetime

from models import db


class CandidateDeclaration(db.Model):
    """One candidate's set of pre-assessment acknowledgements for one attempt."""

    __tablename__ = "candidate_declarations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"), nullable=False, index=True)

    confirmed_candidate = db.Column(db.Boolean, nullable=False, default=False)
    ai_monitoring_ack = db.Column(db.Boolean, nullable=False, default=False)
    webcam_monitoring_ack = db.Column(db.Boolean, nullable=False, default=False)
    browser_monitoring_ack = db.Column(db.Boolean, nullable=False, default=False)
    integrity_score_ack = db.Column(db.Boolean, nullable=False, default=False)
    rules_ack = db.Column(db.Boolean, nullable=False, default=False)
    log_storage_consent = db.Column(db.Boolean, nullable=False, default=False)
    terms_ack = db.Column(db.Boolean, nullable=False, default=False)

    declared_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
    assessment = db.relationship("Assessment")

    def all_acknowledged(self) -> bool:
        """True only if every required checkbox was checked."""
        return all([
            self.confirmed_candidate,
            self.ai_monitoring_ack,
            self.webcam_monitoring_ack,
            self.browser_monitoring_ack,
            self.integrity_score_ack,
            self.rules_ack,
            self.log_storage_consent,
            self.terms_ack,
        ])

    def __repr__(self) -> str:
        return f"<CandidateDeclaration user_id={self.user_id} assessment_id={self.assessment_id}>"

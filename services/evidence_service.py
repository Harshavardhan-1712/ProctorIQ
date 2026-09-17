"""
services/evidence_service.py
--------------------------------
Milestone 3, Parts 20-23: Alert & Evidence Management + Secure
Screenshot/Incident Storage.

Screenshots are captured ONLY for configured critical incidents
(config.py's EVIDENCE_CAPTURE_EVENTS) — never continuously (Part 20).
Each stored Evidence row carries a SHA-256 hash of the raw image bytes
as a tamper-evidence control (Part 23) — NOT a claim of legal
admissibility, which this module explicitly does not make.

Evidence/Incident rows are examiner-only: routes/insights.py gates
every read/write behind `@role_required("invigilator", "admin")`, and
this service never exposes a route a candidate session can reach.
"""

import base64
import hashlib
from datetime import datetime

from models import db
from models.analytics import Evidence, Incident


def _default_severity_events() -> set:
    return {"multiple_faces", "phone_detected", "session_terminated"}


def capture_evidence_events():
    from flask import current_app
    try:
        return current_app.config.get("EVIDENCE_CAPTURE_EVENTS", _default_severity_events())
    except RuntimeError:
        return _default_severity_events()


def should_capture_evidence(event_type: str) -> bool:
    return event_type in capture_evidence_events()


def store_evidence(session, event_type: str, image_base64: str, mime_type: str = "image/png") -> Evidence:
    """
    Persist one screenshot as evidence. `image_base64` is the raw
    (not data-URI-prefixed) base64 string — callers should strip any
    "data:image/png;base64," prefix before calling this.
    """
    raw_bytes = base64.b64decode(image_base64)
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    evidence = Evidence(
        session_id=session.id,
        user_id=session.user_id,
        event_type=event_type,
        mime_type=mime_type,
        image_data=image_base64,
        sha256_hash=sha256_hash,
        timestamp=datetime.utcnow(),
    )
    db.session.add(evidence)
    db.session.commit()
    return evidence


def create_incident(session, event_type: str, severity: str, description: str,
                     source_event_id: int = None, evidence: Evidence = None,
                     action_taken: str = None) -> Incident:
    """Create an incident record, optionally linked to a captured Evidence row."""
    incident = Incident(
        session_id=session.id,
        user_id=session.user_id,
        source_event_id=source_event_id,
        event_type=event_type,
        severity=severity,
        description=description,
        action_taken=action_taken,
        evidence_id=evidence.id if evidence else None,
        examiner_status="OPEN",
        timestamp=datetime.utcnow(),
    )
    db.session.add(incident)
    db.session.commit()

    if evidence is not None:
        evidence.incident_id = incident.id
        db.session.commit()

    return incident


def verify_evidence_integrity(evidence: Evidence) -> bool:
    """Re-hash the stored image bytes and compare to the stored hash — detects tampering."""
    raw_bytes = base64.b64decode(evidence.image_data)
    return hashlib.sha256(raw_bytes).hexdigest() == evidence.sha256_hash


def get_incidents_for_session(session_id: int):
    return Incident.query.filter_by(session_id=session_id).order_by(Incident.timestamp.desc()).all()


def get_evidence_for_session(session_id: int):
    return Evidence.query.filter_by(session_id=session_id).order_by(Evidence.timestamp.desc()).all()


def get_all_incidents(limit: int = 200):
    return Incident.query.order_by(Incident.timestamp.desc()).limit(limit).all()

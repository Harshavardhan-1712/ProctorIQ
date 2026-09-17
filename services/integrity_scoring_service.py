"""
services/integrity_scoring_service.py
--------------------------------------
Milestone 3, Parts 2-6: Integrity Scoring Module.

Turns the raw, per-event `ExamEvent` audit trail (Module 4) for one
`AssessmentSession` into a transparent, Pandas-computed integrity
score, using the centralized weights in config.py's
`EVENT_SCORING_WEIGHTS` / `EVENT_SCORING_BASE_SCORE`.

This is intentionally a SEPARATE engine from services/integrity_service.py
(Module 4's live, cumulative `User.integrity_score`, decremented in
real time during monitoring). This module recomputes a session-scoped
score AFTER the fact, deterministically, from the stored events —
useful for analytics/clustering/reporting where the live running score
isn't the right shape of data (it isn't session-scoped, and it doesn't
expose the breakdown a report needs).

Public API:
    score_session(session)                 -> dict (see SCHEMA below)
    face_presence_ratio(session)            -> dict
    session_feature_row(session)            -> dict (flat, for Pandas/NumPy)
    build_sessions_dataframe(sessions)      -> pandas.DataFrame
"""

from datetime import datetime

import pandas as pd

from flask import current_app

from services import event_logger

MIN_SCORE = 0
MAX_SCORE = 100

# Event types that represent the face going away / coming back, used
# to derive face-presence intervals from paired events rather than
# any single frame (Milestone 3, Part 4).
_FACE_LOST_TYPES = {"no_face", "camera_lost"}
_FACE_RESTORED_TYPES = {"face_restored", "camera_restored"}

_DEFAULT_WEIGHTS = {
    "tab_switch": 4, "window_blur": 4, "no_face": 8, "multiple_faces": 15,
    "camera_lost": 12, "fullscreen_exit": 8, "copy_attempt": 6, "paste_attempt": 6,
    "phone_detected": 18, "face_covered": 10, "devtools_detected": 10, "right_click": 2,
    "page_refresh": 3,
}


def _base_score() -> int:
    try:
        return current_app.config.get("EVENT_SCORING_BASE_SCORE", 100)
    except RuntimeError:
        return 100


def _weights() -> dict:
    try:
        return current_app.config.get("EVENT_SCORING_WEIGHTS", _DEFAULT_WEIGHTS)
    except RuntimeError:
        return _DEFAULT_WEIGHTS


def _risk_thresholds() -> tuple:
    """Returns (high_risk_threshold, medium_risk_threshold)."""
    try:
        high = current_app.config.get("HIGH_RISK_THRESHOLD", 50)
        medium = current_app.config.get("MEDIUM_RISK_THRESHOLD", 75)
    except RuntimeError:
        high, medium = 50, 75
    return high, medium


def risk_label_from_score(score: float) -> str:
    """Normalized LOW/MEDIUM/HIGH label from a Milestone 3 session score (Part 5)."""
    high, medium = _risk_thresholds()
    if score < high:
        return "HIGH"
    if score < medium:
        return "MEDIUM"
    return "LOW"


def _session_window(session):
    start = session.started_at
    end = session.submitted_at or datetime.utcnow()
    return start, end


def get_session_events(session) -> list:
    """Raw ExamEvent rows for this session's time window."""
    start, end = _session_window(session)
    return event_logger.get_events_in_window(session.user_id, start=start, end=end, limit=2000)


def _events_dataframe(events: list) -> pd.DataFrame:
    """Raw events -> a tidy Pandas DataFrame. Empty-safe (returns an empty, correctly-columned frame)."""
    if not events:
        return pd.DataFrame(columns=["event_type", "severity", "description", "timestamp"])
    return pd.DataFrame(
        [
            {
                "event_type": e.event_type,
                "severity": e.severity,
                "description": e.description,
                "timestamp": e.timestamp,
            }
            for e in events
        ]
    )


def face_presence_ratio(session, events: list = None) -> dict:
    """
    Face Presence Ratio = Total Time Face Detected / Total Monitored Duration
    (Milestone 3, Part 4).

    Derived from timestamped "face lost" -> "face restored" event pairs
    within the session window, NOT a single frame. Handles: temporary
    face loss, missing "restored" pair at session end (face still
    absent when monitoring stopped), and sessions with zero monitoring
    events (returns a 0-duration, N/A-safe result rather than dividing
    by zero).
    """
    start, end = _session_window(session)
    monitored_duration = max(0.0, (end - start).total_seconds())

    if events is None:
        events = get_session_events(session)
    # Chronological order — get_events_in_window returns newest-first.
    ordered = sorted(events, key=lambda e: e.timestamp)

    face_absent_seconds = 0.0
    absence_start = None
    for e in ordered:
        if e.event_type in _FACE_LOST_TYPES and absence_start is None:
            absence_start = e.timestamp
        elif e.event_type in _FACE_RESTORED_TYPES and absence_start is not None:
            face_absent_seconds += max(0.0, (e.timestamp - absence_start).total_seconds())
            absence_start = None
    # Face was still absent when the window ended (no matching "restored" event).
    if absence_start is not None:
        face_absent_seconds += max(0.0, (end - absence_start).total_seconds())

    face_absent_seconds = min(face_absent_seconds, monitored_duration) if monitored_duration else face_absent_seconds
    face_present_seconds = max(0.0, monitored_duration - face_absent_seconds)

    ratio = (face_present_seconds / monitored_duration) if monitored_duration > 0 else None

    return {
        "monitored_duration_seconds": round(monitored_duration, 1),
        "face_present_seconds": round(face_present_seconds, 1),
        "face_absent_seconds": round(face_absent_seconds, 1),
        "face_presence_ratio": round(ratio, 4) if ratio is not None else None,
        "face_presence_percent": round(ratio * 100, 2) if ratio is not None else None,
    }


def score_session(session) -> dict:
    """
    Weighted integrity score for one AssessmentSession (Milestone 3, Parts 2-3).

    Returns a transparent breakdown:
        {
            "session_id": ...,
            "base_score": 100,
            "event_counts": {...},
            "penalties": {"tab_switch_penalty": 10, ...},
            "total_penalty": 19,
            "integrity_score": 81,
            "risk_level": "LOW",
            ...face_presence_ratio fields...
        }
    """
    events = get_session_events(session)
    df = _events_dataframe(events)
    weights = _weights()
    base = _base_score()

    if df.empty:
        event_counts = {}
    else:
        event_counts = df["event_type"].value_counts().to_dict()

    penalties = {}
    total_penalty = 0
    for event_type, weight in weights.items():
        count = int(event_counts.get(event_type, 0))
        penalty = int(count * weight)
        if count:
            penalties[f"{event_type}_penalty"] = penalty
        total_penalty += penalty

    integrity_score = max(MIN_SCORE, min(MAX_SCORE, base - total_penalty))
    risk_level = risk_label_from_score(integrity_score)

    presence = face_presence_ratio(session, events=events)

    total_violations = int(
        sum(count for etype, count in event_counts.items() if etype in weights)
    )

    return {
        "session_id": session.id,
        "candidate_id": session.user_id,
        "base_score": base,
        "event_counts": {k: int(v) for k, v in event_counts.items()},
        "penalties": penalties,
        "total_penalty": int(total_penalty),
        "integrity_score": int(integrity_score),
        "risk_level": risk_level,
        "total_violations": total_violations,
        **presence,
    }


def session_feature_row(session) -> dict:
    """
    Flat, numeric-first feature dict for one session — the row shape
    consumed by services/analytics_service.py and
    services/clustering_service.py's Pandas/NumPy pipeline
    (Milestone 3, Part 6).
    """
    result = score_session(session)
    counts = result["event_counts"]

    return {
        "session_id": session.id,
        "candidate_id": session.user_id,
        "candidate_name": session.user.full_name if session.user else "Unknown",
        "assessment_id": session.assessment_id,
        "status": session.status,
        "tab_switches": counts.get("tab_switch", 0),
        "focus_losses": counts.get("window_blur", 0),
        "face_absent_events": counts.get("no_face", 0),
        "face_absent_duration": result["face_absent_seconds"],
        "face_presence_ratio": result["face_presence_ratio"] if result["face_presence_ratio"] is not None else 1.0,
        "multiple_face_events": counts.get("multiple_faces", 0),
        "copy_attempts": counts.get("copy_attempt", 0),
        "paste_attempts": counts.get("paste_attempt", 0),
        "fullscreen_exits": counts.get("fullscreen_exit", 0),
        "network_interruptions": counts.get("camera_lost", 0),
        "object_detection_events": counts.get("phone_detected", 0),
        "face_movement_events": counts.get("face_covered", 0),
        "total_violations": result["total_violations"],
        "integrity_score": result["integrity_score"],
        "risk_level": result["risk_level"],
        "data_source": "REAL",
    }


def build_sessions_dataframe(sessions: list) -> pd.DataFrame:
    """
    Sessions -> one Pandas DataFrame, one row per session
    (Milestone 3, Part 6's pipeline: "Session Event Logs -> Pandas
    DataFrame -> Feature Extraction -> Integrity Scoring -> Analytics
    Dataset"). Empty-safe.
    """
    rows = [session_feature_row(s) for s in sessions]
    if not rows:
        return pd.DataFrame(columns=[
            "session_id", "candidate_id", "candidate_name", "assessment_id", "status",
            "tab_switches", "focus_losses", "face_absent_events", "face_absent_duration",
            "face_presence_ratio", "multiple_face_events", "copy_attempts", "paste_attempts",
            "fullscreen_exits", "network_interruptions", "object_detection_events",
            "face_movement_events", "total_violations", "integrity_score", "risk_level", "data_source",
        ])
    return pd.DataFrame(rows)

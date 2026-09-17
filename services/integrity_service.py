"""
services/integrity_service.py
--------------------------------
Integrity Score Engine (Module 4 Part 6 / Module 5 Part 14).

Every monitored exam session starts at a configurable starting score
(default 100). Specific violation types deduct configurable point
values as they're logged; the score never drops below 0. The score is
persisted on `User.integrity_score` (not just computed on the fly) so
it can be displayed instantly anywhere in the app.

Part 13 groundwork: starting score, per-violation penalty weights, and
risk thresholds are read from Flask config (config.py's
`INTEGRITY_STARTING_SCORE` / `PENALTY_WEIGHTS` /
`INTEGRITY_WARNING_THRESHOLD` / `INTEGRITY_HIGH_RISK_THRESHOLD`)
instead of being hardcoded here. A future admin-configuration UI only
needs to write to those config values (or move them to a database-backed
settings table) — this module never needs to change.
"""

from flask import current_app

from models import db
from models.user import User

MIN_SCORE = 0

# Fallback defaults, used only if this module is somehow called outside
# an application context (e.g. a standalone script). Normal request
# handling always reads live values from current_app.config instead.
_DEFAULT_STARTING_SCORE = 100
_DEFAULT_PENALTY_WEIGHTS = {
    "tab_switch": 5,
    "window_blur": 5,
    "no_face": 10,
    "multiple_faces": 20,
    "camera_lost": 30,
    "fullscreen_exit": 10,
    "phone_detected": 20,
    "face_covered": 15,
}
_DEFAULT_WARNING_THRESHOLD = 70
_DEFAULT_HIGH_RISK_THRESHOLD = 40


def _starting_score() -> int:
    try:
        return current_app.config.get("INTEGRITY_STARTING_SCORE", _DEFAULT_STARTING_SCORE)
    except RuntimeError:
        return _DEFAULT_STARTING_SCORE


def _penalty_weights() -> dict:
    try:
        return current_app.config.get("PENALTY_WEIGHTS", _DEFAULT_PENALTY_WEIGHTS)
    except RuntimeError:
        return _DEFAULT_PENALTY_WEIGHTS


def reset_score(user: User) -> int:
    """Reset a candidate's integrity score to the configured starting score."""
    user.integrity_score = _starting_score()
    db.session.commit()
    return user.integrity_score


def apply_deduction(user: User, event_type: str) -> int:
    """
    Deduct points for a violation event_type, if it's one that carries
    a deduction, and persist the new score. Returns the resulting score
    (deductions for unlisted event_types are a no-op that just returns
    the current score unchanged).
    """
    points = _penalty_weights().get(event_type, 0)
    if points:
        user.integrity_score = max(MIN_SCORE, user.integrity_score - points)
        db.session.commit()
    return user.integrity_score


def get_score(user: User) -> int:
    """Current stored integrity score for a candidate."""
    return user.integrity_score


def score_status_label(score: int) -> str:
    """
    A short, dashboard-friendly quality label for the current score band.
    Kept for backward compatibility with Module 4 templates that already
    display this. New code should prefer `risk_label()` below, which
    matches the Low/Medium/High terminology from Module 5 Part 14.
    """
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "At Risk"
    return "Critical"


def risk_label(score: int) -> str:
    """
    Low / Medium / High risk label, per Module 5 Part 14's explicit
    terminology. Thresholds are configurable via
    `INTEGRITY_WARNING_THRESHOLD` and `INTEGRITY_HIGH_RISK_THRESHOLD`.

    score >= warning_threshold        -> "Low" risk
    high_risk_threshold <= score < .. -> "Medium" risk
    score < high_risk_threshold        -> "High" risk
    """
    try:
        warning_threshold = current_app.config.get("INTEGRITY_WARNING_THRESHOLD", _DEFAULT_WARNING_THRESHOLD)
        high_risk_threshold = current_app.config.get("INTEGRITY_HIGH_RISK_THRESHOLD", _DEFAULT_HIGH_RISK_THRESHOLD)
    except RuntimeError:
        warning_threshold = _DEFAULT_WARNING_THRESHOLD
        high_risk_threshold = _DEFAULT_HIGH_RISK_THRESHOLD

    if score >= warning_threshold:
        return "Low"
    if score >= high_risk_threshold:
        return "Medium"
    return "High"

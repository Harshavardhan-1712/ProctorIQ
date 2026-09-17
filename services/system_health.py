"""
services/system_health.py
----------------------------
Lightweight status checks powering the dashboard's "System Health"
card (database connectivity, OpenCV availability, Flask server status,
camera availability).

These are intentionally cheap, synchronous checks suitable for running
on every dashboard page load — not a full health-check/monitoring
subsystem. A future ops/monitoring module could replace this with
something more thorough without changing the dashboard template, since
it only ever sees the small dict returned by `get_system_health()`.
"""

from sqlalchemy import text

from models import db
from services.camera_service import Camera


def _check_database() -> bool:
    """A trivial round-trip query — confirms the DB connection is alive."""
    try:
        db.session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_opencv() -> bool:
    """Confirm the OpenCV (cv2) module is importable and usable."""
    try:
        import cv2  # noqa: F401 — presence of the import is the check itself
        return True
    except Exception:
        return False


def get_system_health() -> dict:
    """
    Returns a dict of {label: is_healthy} for the four checks shown on
    the dashboard. The Flask server check is always True — if this
    code is running at all, the server is up.
    """
    return {
        "Database Connection": _check_database(),
        "OpenCV Status": _check_opencv(),
        "Flask Server Status": True,
        "Camera Availability": Camera.check_available(),
    }

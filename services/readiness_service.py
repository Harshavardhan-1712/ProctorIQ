"""
services/readiness_service.py
--------------------------------
System Readiness Check (Module 5, Part 3) — server-verifiable checks.

Of the 8 checks the spec asks for, four can only be genuinely verified
server-side (they need the actual camera frame): Camera Connected, Face
Visible, Single Face Detected, and Good Lighting. This module bundles
those into one call so routes/preassessment.py's readiness endpoint
stays a thin wrapper.

The remaining four — Browser Supported, Fullscreen Enabled, Stable
Internet, Microphone (optional) — are properties of the candidate's
browser, not the server, and are checked client-side in JavaScript
(see templates/readiness.html). Mixing "ask the browser" checks into a
Python service would just mean re-implementing browser feature
detection in Python for no benefit — so this module deliberately only
owns the camera-dependent half, and the template owns aggregating all
8 into the overall readiness score.
"""

from services import monitoring_service


def check_camera_readiness() -> dict:
    """
    One combined check covering Camera Connected, Face Visible, and
    Single Face Detected — all three come from the same frame read, so
    there's no reason to hit the camera three times.

    Returns:
        {
          "camera_connected": bool,
          "face_visible": bool,
          "single_face": bool,
          "face_count": int,
          "message": str,
        }
    """
    result = monitoring_service.check_face_status()
    status = result["status"]

    camera_connected = status != monitoring_service.STATUS_CAMERA_ERROR
    face_visible = status in (monitoring_service.STATUS_SINGLE_FACE, monitoring_service.STATUS_MULTIPLE_FACES)
    single_face = status == monitoring_service.STATUS_SINGLE_FACE

    return {
        "camera_connected": camera_connected,
        "face_visible": face_visible,
        "single_face": single_face,
        "face_count": result["face_count"],
        "message": result["message"],
    }


def check_lighting_readiness() -> dict:
    """Good Lighting check — thin pass-through to monitoring_service, kept here for a single import point."""
    result = monitoring_service.check_lighting_status()
    return {
        "good_lighting": result["status"] == "good",
        "brightness": result["brightness"],
        "message": result["message"],
    }


def get_server_readiness() -> dict:
    """
    All server-verifiable checks in one call — what
    routes/preassessment.py's /readiness/status endpoint returns.
    """
    camera = check_camera_readiness()
    lighting = check_lighting_readiness()

    return {
        "camera_connected": camera["camera_connected"],
        "face_visible": camera["face_visible"],
        "single_face": camera["single_face"],
        "face_count": camera["face_count"],
        "good_lighting": lighting["good_lighting"],
        "brightness": lighting["brightness"],
        "message": camera["message"],
    }

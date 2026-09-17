"""
services/monitoring_service.py
---------------------------------
Live camera monitoring (Module 4, Part 3).

This module does NOT talk to OpenCV directly — it reuses
services/camera_service.py (for reading a frame) and
services/face_detection_service.py (for detecting faces) exactly as
Module 2/3 already established, and simply interprets the result into
one of four monitoring statuses that the dashboard/monitoring page
polls for:

    "single_face"    -> exactly one face, all good
    "no_face"        -> zero faces detected
    "multiple_faces" -> two or more faces detected
    "camera_error"   -> the webcam itself is unavailable

Deliberately framework-light (no Flask session/DB access here) so a
future continuous-monitoring worker (e.g. a background thread, or a
head-pose/eye-gaze module) can call `check_face_status()` directly.
Transition tracking (to avoid re-logging/re-deducting every single
poll while a bad status persists) is handled by the caller
(routes/monitoring.py), since "what counts as a new violation" is a
routing/session concern, not a detection concern.
"""

from services.camera_service import read_current_frame, CameraError
from services.face_detection_service import detect_faces

STATUS_SINGLE_FACE = "single_face"
STATUS_NO_FACE = "no_face"
STATUS_MULTIPLE_FACES = "multiple_faces"
STATUS_CAMERA_ERROR = "camera_error"

# Human-readable labels for each status, for the monitoring page UI.
STATUS_LABELS = {
    STATUS_SINGLE_FACE: "Face detected — monitoring normally",
    STATUS_NO_FACE: "No face detected",
    STATUS_MULTIPLE_FACES: "Multiple faces detected",
    STATUS_CAMERA_ERROR: "Camera unavailable",
}

# Mean grayscale brightness (0-255) thresholds used by
# check_lighting_status() below. Frames outside this band tend to
# produce unreliable face detection, so the pre-assessment readiness
# check (Module 5, Part 3) surfaces this to the candidate before they
# start, rather than letting it silently degrade monitoring later.
LIGHTING_TOO_DARK_THRESHOLD = 60
LIGHTING_TOO_BRIGHT_THRESHOLD = 200


def check_face_status() -> dict:
    """
    Perform one monitoring check: grab the current webcam frame and
    classify it into a status.

    Returns a dict: {"status": <one of the STATUS_* constants>,
                      "face_count": int,
                      "message": <human-readable label>}

    Never raises — camera failures are reported as a status, not an
    exception, since the monitoring poll loop needs to keep running
    (and keep showing a status) even while the camera is down.
    """
    try:
        frame = read_current_frame()
    except CameraError:
        return {
            "status": STATUS_CAMERA_ERROR,
            "face_count": 0,
            "message": STATUS_LABELS[STATUS_CAMERA_ERROR],
        }

    faces = detect_faces(frame)
    face_count = len(faces)

    if face_count == 0:
        status = STATUS_NO_FACE
    elif face_count == 1:
        status = STATUS_SINGLE_FACE
    else:
        status = STATUS_MULTIPLE_FACES

    return {
        "status": status,
        "face_count": face_count,
        "message": STATUS_LABELS[status],
    }


def check_lighting_status() -> dict:
    """
    Grab the current frame and classify ambient lighting as "good",
    "too_dark", or "too_bright" based on mean grayscale brightness.

    Used by the pre-assessment System Readiness Check (Module 5, Part
    3) — poor lighting is exactly the kind of thing worth catching
    BEFORE the candidate starts a timed, monitored assessment, since it
    directly affects face-detection reliability during the exam.

    Reuses the same read_current_frame() as check_face_status() rather
    than opening a second capture — camera failures are reported the
    same way (a status dict, never raised).
    """
    import cv2  # local import: keeps this a light, optional check

    try:
        frame = read_current_frame()
    except CameraError:
        return {"status": STATUS_CAMERA_ERROR, "brightness": 0, "message": STATUS_LABELS[STATUS_CAMERA_ERROR]}

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(gray.mean())

    if mean_brightness < LIGHTING_TOO_DARK_THRESHOLD:
        status, message = "too_dark", "Lighting is too dim — move to a brighter area"
    elif mean_brightness > LIGHTING_TOO_BRIGHT_THRESHOLD:
        status, message = "too_bright", "Lighting is too bright — reduce backlighting or glare"
    else:
        status, message = "good", "Lighting looks good"

    return {"status": status, "brightness": round(mean_brightness, 1), "message": message}

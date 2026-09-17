"""
routes/camera.py
------------------
Blueprint handling the candidate photo-capture workflow, including
Module 3's face-detection validation:

    GET  /capture-photo   -> renders the capture page (live preview + controls)
    GET  /video_feed      -> MJPEG live webcam stream (consumed by an <img> tag)
    GET  /temp-photo      -> serves the just-captured temp image (for the
                              "review your photo" preview, before saving)
    POST /capture         -> grabs the current frame, validates it contains
                              exactly one face, draws a bounding box, and
                              saves it as a temp file (only if valid)
    POST /retake          -> discards the temp file, back to live preview
    POST /save-photo      -> commits the (already-validated) temp file as
                              the candidate's permanent profile photo and
                              updates the DB
    GET  /skip-photo      -> lets the candidate continue without a photo

All routes are login_required since a photo belongs to a specific,
already-authenticated candidate.

Architecture: this module is intentionally just orchestration — it
reads a frame via services/camera_service.py, validates it via
services/face_detection_service.py, and saves it back via
services/camera_service.py. Neither service module knows about the
other; routes/camera.py is the only place that wires them together.
This keeps both services independently reusable for future modules
(e.g. a face-verification check during the exam can call
face_detection_service.detect_faces() directly on a live frame without
touching this file).
"""

import time

from flask import Blueprint, render_template, redirect, url_for, flash, Response, jsonify
from flask_login import login_required, current_user

from models import db
from services.camera_service import (
    Camera,
    CameraError,
    generate_mjpeg_stream,
    read_current_frame,
    save_frame_as_temp,
    get_temp_photo_bytes,
    discard_temp_photo,
    finalize_photo,
)
from services.face_detection_service import validate_and_annotate_face, FaceDetectionError
from services.event_logger import log_event

camera_bp = Blueprint("camera", __name__)


@camera_bp.route("/capture-photo")
@login_required
def capture_photo():
    """Render the photo capture page (live preview + capture/retake/save controls)."""
    return render_template("capture_photo.html")


@camera_bp.route("/video_feed")
@login_required
def video_feed():
    """
    Live MJPEG stream consumed by the <img> tag on the capture page.

    If the webcam can't be opened at all, fail fast with a 503 instead
    of returning a stream that will just hang — the front-end's
    `onerror` handler on the <img> turns this into a friendly message.
    """
    try:
        Camera.get_instance()
    except CameraError as e:
        return Response(str(e), status=503, mimetype="text/plain")

    return Response(
        generate_mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@camera_bp.route("/temp-photo")
@login_required
def temp_photo():
    """Serve the candidate's just-captured (not-yet-saved) temp photo."""
    try:
        photo_bytes = get_temp_photo_bytes(current_user.id)
    except CameraError as e:
        return Response(str(e), status=404, mimetype="text/plain")

    return Response(photo_bytes, mimetype="image/jpeg")


@camera_bp.route("/capture", methods=["POST"])
@login_required
def capture():
    """
    Grab the current webcam frame, validate it contains exactly one
    face, and — only if valid — save it (with a bounding box drawn
    around the face) as a temp preview.

    Returns distinct error types so the front-end can react
    appropriately:
      - "camera": hardware/device failure -> fatal, stop offering retries
      - "face":   0 or 2+ faces detected  -> recoverable, let the
                  candidate try capturing again immediately
    """
    # Step 1: grab a raw frame from the webcam.
    try:
        frame = read_current_frame()
    except CameraError as e:
        return jsonify(success=False, error_type="camera", error=str(e)), 503

    # Step 2: validate exactly one face is present, and get back the
    # frame annotated with a bounding box around it.
    try:
        annotated_frame = validate_and_annotate_face(frame)
    except FaceDetectionError as e:
        return jsonify(
            success=False,
            error_type="face",
            error=str(e),
            face_count=e.face_count,
        ), 422  # 422 Unprocessable Entity: the image itself is invalid

    # Step 3: only a validated, annotated frame ever reaches disk.
    try:
        save_frame_as_temp(current_user.id, annotated_frame)
    except CameraError as e:
        return jsonify(success=False, error_type="camera", error=str(e)), 503

    # Cache-busting query param so the browser doesn't reuse a stale
    # cached image if the candidate captures more than once.
    preview_url = url_for("camera.temp_photo") + f"?t={int(time.time())}"
    return jsonify(success=True, preview_url=preview_url)


@camera_bp.route("/retake", methods=["POST"])
@login_required
def retake():
    """Discard the temp photo so the candidate can go back to the live feed."""
    discard_temp_photo(current_user.id)
    return jsonify(success=True)


@camera_bp.route("/save-photo", methods=["POST"])
@login_required
def save_photo():
    """
    Commit the temp photo as the candidate's permanent profile photo.

    The temp file was only ever written by /capture after it passed
    face validation, so no re-validation is needed here — this route
    just promotes it to its final location and records it in the DB.
    """
    try:
        relative_path = finalize_photo(current_user.id)
    except CameraError as e:
        flash(str(e), "danger")
        return redirect(url_for("camera.capture_photo"))

    current_user.photo_path = relative_path
    db.session.commit()
    log_event(current_user.id, "face_verified")

    flash("Profile photo verified and saved successfully!", "success")
    return redirect(url_for("dashboard.dashboard"))


@camera_bp.route("/skip-photo")
@login_required
def skip_photo():
    """Let the candidate proceed without a profile photo (e.g. no webcam available)."""
    flash("You can add your profile photo later from the dashboard.", "info")
    return redirect(url_for("dashboard.dashboard"))


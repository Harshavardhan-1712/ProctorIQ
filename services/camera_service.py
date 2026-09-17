"""
services/camera_service.py
----------------------------
OpenCV webcam access, MJPEG streaming, and photo capture/save logic.
"""

import os
import threading

import cv2
from flask import current_app


class CameraError(Exception):
    """Raised whenever the webcam cannot be opened or a frame can't be read."""
    pass


class Camera:
    """
    Thread-safe singleton wrapper around a single OpenCV VideoCapture device.
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.capture = None
        self.read_lock = threading.Lock()
        self._open()

    def _open(self) -> None:
        capture = cv2.VideoCapture(self.device_index)

        if not capture.isOpened():
            capture.release()
            raise CameraError(
                "Unable to access the webcam. Please make sure it is connected, "
                "not being used by another application, and that camera "
                "permissions are granted."
            )

        self.capture = capture

    @classmethod
    def get_instance(cls) -> "Camera":
        """Return the shared Camera instance."""
        with cls._instance_lock:
            if cls._instance is None or not cls._instance.is_open():
                device_index = current_app.config.get(
                    "CAMERA_DEVICE_INDEX", 0
                )
                cls._instance = cls(device_index=device_index)

            return cls._instance

    @classmethod
    def release_instance(cls) -> None:
        """Release the webcam device."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.release()
                cls._instance = None

    def is_open(self) -> bool:
        return (
            self.capture is not None
            and self.capture.isOpened()
        )

    @classmethod
    def check_available(cls) -> bool:
        """
        Check whether the webcam is available.
        """

        if cls._instance is not None and cls._instance.is_open():
            return True

        try:
            device_index = current_app.config.get(
                "CAMERA_DEVICE_INDEX", 0
            )

            probe = cv2.VideoCapture(device_index)
            available = probe.isOpened()
            probe.release()

            return available

        except Exception:
            return False

    def read_frame(self):
        """Read a single raw frame from the webcam."""

        if not self.is_open():
            raise CameraError("Camera is not available.")

        with self.read_lock:
            success, frame = self.capture.read()

        if not success or frame is None:
            raise CameraError(
                "Failed to read a frame from the webcam."
            )

        return frame

    def get_jpeg_bytes(self) -> bytes:
        """Read a frame and encode it as JPEG."""

        frame = self.read_frame()

        ok, buffer = cv2.imencode(".jpg", frame)

        if not ok:
            raise CameraError(
                "Failed to encode the captured frame as JPEG."
            )

        return buffer.tobytes()

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None


def generate_mjpeg_stream():
    """Generate MJPEG stream for live camera preview."""

    camera = Camera.get_instance()

    while True:
        try:
            jpeg_bytes = camera.get_jpeg_bytes()

        except CameraError:
            break

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg_bytes
            + b"\r\n"
        )


# ---------------------------------------------------------------------
# Capture / Retake / Save workflow
# ---------------------------------------------------------------------

def _uploads_dir() -> str:
    return current_app.config["UPLOAD_FOLDER"]


def _tmp_dir() -> str:
    tmp_dir = os.path.join(
        _uploads_dir(),
        "tmp"
    )

    os.makedirs(tmp_dir, exist_ok=True)

    return tmp_dir


def _temp_photo_path(user_id: int) -> str:
    return os.path.join(
        _tmp_dir(),
        f"user_{user_id}_temp.jpg"
    )


def _final_photo_relative_path(user_id: int) -> str:
    return f"uploads/user_{user_id}.jpg"


def read_current_frame():
    """
    Read one frame from the shared camera.

    IMPORTANT:
    The frame is returned BEFORE anything is written to disk.
    Face validation happens in routes/camera.py.
    """

    camera = Camera.get_instance()

    return camera.read_frame()


def save_frame_as_temp(user_id: int, frame) -> str:
    """
    Save an already-validated frame as a temporary JPEG.
    """

    ok, buffer = cv2.imencode(".jpg", frame)

    if not ok:
        raise CameraError(
            "Failed to encode the captured frame as JPEG."
        )

    temp_path = _temp_photo_path(user_id)

    with open(temp_path, "wb") as f:
        f.write(buffer.tobytes())

    return temp_path


def get_temp_photo_bytes(user_id: int) -> bytes:
    """Read the temporary photo."""

    temp_path = _temp_photo_path(user_id)

    if not os.path.exists(temp_path):
        raise CameraError(
            "No captured photo found. Please capture a photo first."
        )

    with open(temp_path, "rb") as f:
        return f.read()


def discard_temp_photo(user_id: int) -> None:
    """Delete the temporary photo."""

    temp_path = _temp_photo_path(user_id)

    if os.path.exists(temp_path):
        os.remove(temp_path)


def finalize_photo(user_id: int) -> str:
    """
    Promote temporary photo to permanent location.
    """

    temp_path = _temp_photo_path(user_id)

    if not os.path.exists(temp_path):
        raise CameraError(
            "No captured photo to save. Please capture a photo first."
        )

    relative_path = _final_photo_relative_path(user_id)

    final_path = os.path.join(
        _uploads_dir(),
        f"user_{user_id}.jpg"
    )

    os.replace(
        temp_path,
        final_path
    )

    return relative_path
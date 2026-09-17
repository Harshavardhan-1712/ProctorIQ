"""
services/face_detection_service.py
-----------------------------------
Face detection and candidate-photo validation using OpenCV Haar Cascades.

Validation rule:
    0 faces  -> REJECT
    1 face   -> ACCEPT
    2+ faces -> REJECT

The frame is saved only after exactly one face is confirmed.
"""

import cv2


# ---------------------------------------------------------------------
# Cascade configuration
# ---------------------------------------------------------------------

_PRIMARY_CASCADE_FILENAME = "haarcascade_frontalface_default.xml"
_SECONDARY_CASCADE_FILENAME = "haarcascade_frontalface_alt2.xml"

# Primary detector
PRIMARY_SCALE_FACTOR = 1.1
PRIMARY_MIN_NEIGHBORS = 5
PRIMARY_MIN_FACE_SIZE = (60, 60)

# Secondary detector
# More sensitive so that smaller/distant faces can be detected.
SECONDARY_SCALE_FACTOR = 1.05
SECONDARY_MIN_NEIGHBORS = 2
SECONDARY_MIN_FACE_SIZE = (30, 30)


_primary_cascade = None
_secondary_cascade = None


class FaceDetectionError(Exception):
    """Raised when a captured frame fails face-count validation."""

    def __init__(self, message: str, face_count: int = 0):
        super().__init__(message)
        self.face_count = face_count


def _load_cascades():
    """Load and cache both Haar Cascade classifiers."""

    global _primary_cascade
    global _secondary_cascade

    if _primary_cascade is None:
        primary_path = (
            f"{cv2.data.haarcascades}"
            f"{_PRIMARY_CASCADE_FILENAME}"
        )

        _primary_cascade = cv2.CascadeClassifier(primary_path)

        if _primary_cascade.empty():
            raise RuntimeError(
                f"Could not load Haar Cascade classifier from "
                f"'{primary_path}'."
            )

    if _secondary_cascade is None:
        secondary_path = (
            f"{cv2.data.haarcascades}"
            f"{_SECONDARY_CASCADE_FILENAME}"
        )

        _secondary_cascade = cv2.CascadeClassifier(secondary_path)

        if _secondary_cascade.empty():
            raise RuntimeError(
                f"Could not load Haar Cascade classifier from "
                f"'{secondary_path}'."
            )

    return _primary_cascade, _secondary_cascade


def _boxes_overlap(box1, box2, threshold=0.20):
    """
    Determine whether two bounding boxes represent approximately
    the same face using Intersection over Union.
    """

    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    left = max(x1, x2)
    top = max(y1, y2)

    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)

    intersection_width = max(0, right - left)
    intersection_height = max(0, bottom - top)

    intersection_area = (
        intersection_width * intersection_height
    )

    area1 = w1 * h1
    area2 = w2 * h2

    union_area = area1 + area2 - intersection_area

    if union_area <= 0:
        return False

    iou = intersection_area / union_area

    return iou >= threshold


def detect_faces(frame):
    """
    Detect faces using two Haar Cascade classifiers.

    The secondary detector is intentionally more sensitive so that
    smaller/distant faces are not missed.

    If either detector finds multiple faces, the frame is considered
    invalid.

    For a single-face frame, both detectors must agree on the same
    face before the frame is accepted.
    """

    if frame is None:
        return []

    primary, secondary = _load_cascades()

    # Convert BGR frame to grayscale.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Improve contrast.
    gray = cv2.equalizeHist(gray)

    # ---------------------------------------------------------------
    # Primary detector
    # ---------------------------------------------------------------

    primary_faces = primary.detectMultiScale(
        gray,
        scaleFactor=PRIMARY_SCALE_FACTOR,
        minNeighbors=PRIMARY_MIN_NEIGHBORS,
        minSize=PRIMARY_MIN_FACE_SIZE,
    )

    primary_faces = list(primary_faces)

    # ---------------------------------------------------------------
    # Secondary sensitive detector
    # ---------------------------------------------------------------

    secondary_faces = secondary.detectMultiScale(
        gray,
        scaleFactor=SECONDARY_SCALE_FACTOR,
        minNeighbors=SECONDARY_MIN_NEIGHBORS,
        minSize=SECONDARY_MIN_FACE_SIZE,
    )

    secondary_faces = list(secondary_faces)

    # ---------------------------------------------------------------
    # MULTIPLE FACE CHECK
    # ---------------------------------------------------------------

    # If the primary detector sees multiple faces,
    # immediately reject as multiple faces.

    if len(primary_faces) > 1:
        return primary_faces

    # If the sensitive detector sees multiple faces,
    # immediately reject as multiple faces.

    if len(secondary_faces) > 1:
        return secondary_faces

    # ---------------------------------------------------------------
    # NO FACE CHECK
    # ---------------------------------------------------------------

    if len(primary_faces) == 0 and len(secondary_faces) == 0:
        return []

    # ---------------------------------------------------------------
    # SINGLE FACE CONFIRMATION
    # ---------------------------------------------------------------

    # A single detected face must be confirmed by BOTH detectors.

    if len(primary_faces) == 1 and len(secondary_faces) == 1:

        primary_face = primary_faces[0]
        secondary_face = secondary_faces[0]

        if _boxes_overlap(
            primary_face,
            secondary_face,
            threshold=0.20,
        ):
            return [primary_face]

    # Only one detector detected a face.
    # Treat it as uncertain and reject.

    return []


def draw_face_boxes(
    frame,
    faces,
    color=(37, 99, 235),
    thickness=3,
):
    """Return a copy of the frame with face bounding boxes."""

    annotated = frame.copy()

    for (x, y, w, h) in faces:
        cv2.rectangle(
            annotated,
            (x, y),
            (x + w, y + h),
            color,
            thickness,
        )

    return annotated


def validate_and_annotate_face(frame):
    """
    Validate that exactly ONE face is present.

    0 faces:
        REJECT

    2+ faces:
        REJECT

    1 confirmed face:
        ACCEPT

    Only an accepted frame is returned to the camera route for saving.
    """

    faces = detect_faces(frame)

    face_count = len(faces)

    # ---------------------------------------------------------------
    # NO FACE
    # ---------------------------------------------------------------

    if face_count == 0:
        raise FaceDetectionError(
            "No valid face detected. Please make sure your face is "
            "clearly visible, well lit, and centered in the frame, "
            "then try again.",
            face_count=0,
        )

    # ---------------------------------------------------------------
    # MULTIPLE FACES
    # ---------------------------------------------------------------

    if face_count > 1:
        raise FaceDetectionError(
            f"{face_count} faces were detected in the frame. "
            "Only one person is allowed. Please make sure no other "
            "person is visible and try again.",
            face_count=face_count,
        )

    # ---------------------------------------------------------------
    # EXACTLY ONE FACE
    # ---------------------------------------------------------------

    return draw_face_boxes(frame, faces)
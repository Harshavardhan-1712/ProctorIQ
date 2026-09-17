"""
config.py
----------
Central application configuration.

Keeping configuration in one place (instead of scattered across app.py)
makes it trivial to add new environments (development/testing/production)
later, and keeps secrets/paths out of business logic.
"""

import os

# Base directory of the project (proctoriq/)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared by all environments."""

    # Platform branding — centralized here (rather than hardcoded per
    # template) so a future rebrand is a one-line change. Injected into
    # every template via app.py's context_processor.
    PLATFORM_NAME = os.environ.get("PLATFORM_NAME", "ProctorIQ")
    PLATFORM_TAGLINE = os.environ.get(
        "PLATFORM_TAGLINE", "AI-Powered Secure Assessment & Intelligent Proctoring Platform"
    )

    # Secret key used by Flask to sign session cookies.
    # In production this MUST be overridden via an environment variable.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # SQLite database stored inside instance/ (Flask's recommended location
    # for files that should not be part of version control, e.g. secrets/db).
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'proctoriq.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Folder where candidate photos will be stored.
    # Not used yet (Module 1 has no photo capture), but the path is
    # provisioned now so the OpenCV face-monitoring module can plug in
    # later without touching auth code.
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

    # Session lifetime (in seconds) — 1 hour of inactivity logs the user out.
    PERMANENT_SESSION_LIFETIME = 3600

    # --- Session cookie hardening (Module 6, Part 16) ---
    # HTTPONLY: JavaScript can never read the session cookie (mitigates
    #   XSS-based session theft). SAMESITE=Lax: the cookie isn't sent on
    #   cross-site requests except top-level navigation, blocking most
    #   CSRF vectors as defense-in-depth alongside Flask-WTF's CSRFProtect.
    # SECURE: only sent over HTTPS. Defaults to False so local HTTP
    #   development still works — set SESSION_COOKIE_SECURE=true in any
    #   real deployment, which should be behind HTTPS regardless (see
    #   README "Deployment Instructions").
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Index of the OpenCV video capture device to use (0 = default/first
    # webcam). Override via env var on machines with multiple cameras.
    CAMERA_DEVICE_INDEX = int(os.environ.get("CAMERA_DEVICE_INDEX", 0))

    # Timezone used to display timestamps (e.g. registration date) to
    # candidates. Timestamps are always STORED in UTC in the database;
    # this only affects what's shown on screen.
    DISPLAY_TIMEZONE = os.environ.get("DISPLAY_TIMEZONE", "Asia/Kolkata")

    # --- Configurable monitoring/integrity policy (Part 13 groundwork) ---
    # Centralized here rather than hardcoded in services/integrity_service.py,
    # so a future admin-configuration UI only needs to write to this one
    # place. See services/integrity_service.py for how these are consumed.
    INTEGRITY_STARTING_SCORE = int(os.environ.get("INTEGRITY_STARTING_SCORE", 100))
    MAX_TAB_SWITCHES = int(os.environ.get("MAX_TAB_SWITCHES", 5))
    FACE_ABSENCE_GRACE_SECONDS = int(os.environ.get("FACE_ABSENCE_GRACE_SECONDS", 10))
    INTEGRITY_WARNING_THRESHOLD = int(os.environ.get("INTEGRITY_WARNING_THRESHOLD", 70))
    INTEGRITY_HIGH_RISK_THRESHOLD = int(os.environ.get("INTEGRITY_HIGH_RISK_THRESHOLD", 40))
    PENALTY_WEIGHTS = {
        "tab_switch": int(os.environ.get("PENALTY_TAB_SWITCH", 5)),
        "window_blur": int(os.environ.get("PENALTY_WINDOW_BLUR", 5)),
        "no_face": int(os.environ.get("PENALTY_NO_FACE", 10)),
        "multiple_faces": int(os.environ.get("PENALTY_MULTIPLE_FACES", 20)),
        "camera_lost": int(os.environ.get("PENALTY_CAMERA_LOST", 30)),
        "fullscreen_exit": int(os.environ.get("PENALTY_FULLSCREEN_EXIT", 10)),
        # Forward-compatible: no detector emits these yet (Part 12,
        # deferred), but the policy engine is ready to score them the
        # moment a future module starts logging these event_types.
        "phone_detected": int(os.environ.get("PENALTY_PHONE_DETECTED", 20)),
        "face_covered": int(os.environ.get("PENALTY_FACE_COVERED", 15)),
    }

    # ------------------------------------------------------------------
    # Milestone 3 — Integrity Analytics, Clustering & AI Reporting
    # ------------------------------------------------------------------
    # services/integrity_scoring_service.py's per-*session* weighted
    # scoring model. Deliberately a SEPARATE dict from PENALTY_WEIGHTS
    # above rather than reusing it: PENALTY_WEIGHTS drives the *live*,
    # cumulative User.integrity_score used during an exam (Module 4/5),
    # while EVENT_SCORING_WEIGHTS drives Milestone 3's session-scoped,
    # Pandas-computed integrity score used for analytics/clustering/AI
    # reporting. Keeping them separate lets each be tuned independently
    # without one policy change silently altering the other subsystem.
    # Values documented per Milestone 3, Part 3.
    EVENT_SCORING_BASE_SCORE = int(os.environ.get("EVENT_SCORING_BASE_SCORE", 100))
    EVENT_SCORING_WEIGHTS = {
        "tab_switch": int(os.environ.get("SCORE_W_TAB_SWITCH", 2)),
        "window_blur": int(os.environ.get("SCORE_W_FOCUS_LOSS", 2)),
        "no_face": int(os.environ.get("SCORE_W_FACE_ABSENCE", 4)),
        "multiple_faces": int(os.environ.get("SCORE_W_MULTIPLE_FACE", 8)),
        "camera_lost": int(os.environ.get("SCORE_W_CAMERA_LOST", 6)),
        "fullscreen_exit": int(os.environ.get("SCORE_W_FULLSCREEN_EXIT", 4)),
        "copy_attempt": int(os.environ.get("SCORE_W_COPY_ATTEMPT", 3)),
        "paste_attempt": int(os.environ.get("SCORE_W_PASTE_ATTEMPT", 3)),
        "phone_detected": int(os.environ.get("SCORE_W_OBJECT_DETECTION", 10)),
        "face_covered": int(os.environ.get("SCORE_W_ABNORMAL_FACE_MOVEMENT", 5)),
        "devtools_detected": int(os.environ.get("SCORE_W_DEVTOOLS", 6)),
        "right_click": int(os.environ.get("SCORE_W_RIGHT_CLICK", 1)),
        "page_refresh": int(os.environ.get("SCORE_W_PAGE_REFRESH", 2)),
    }

    # Risk thresholds for the Milestone 3 normalized session score.
    # Reuses the same LOW/MEDIUM/HIGH terminology and numeric defaults
    # as INTEGRITY_WARNING_THRESHOLD/INTEGRITY_HIGH_RISK_THRESHOLD above
    # (score >= HIGH_RISK_THRESHOLD -> "MEDIUM"/"LOW"), kept as their own
    # env vars so Milestone 3's session-level policy can be tuned without
    # touching the live per-event Module 4 policy.
    HIGH_RISK_THRESHOLD = int(os.environ.get("HIGH_RISK_THRESHOLD", 50))   # score < this -> HIGH
    MEDIUM_RISK_THRESHOLD = int(os.environ.get("MEDIUM_RISK_THRESHOLD", 75))  # score < this -> MEDIUM, else LOW

    # K-Means session clustering (services/clustering_service.py)
    KMEANS_CLUSTERS = int(os.environ.get("KMEANS_CLUSTERS", 3))
    KMEANS_RANDOM_STATE = int(os.environ.get("KMEANS_RANDOM_STATE", 42))
    MIN_SESSIONS_FOR_CLUSTERING = int(os.environ.get("MIN_SESSIONS_FOR_CLUSTERING", 6))

    # Alert management (services/alert_service.py) — event_type ->
    # severity for events serious enough to raise an examiner-facing
    # alert. Not every scored event needs one (e.g. a single tab switch
    # doesn't), only the configured critical ones do.
    ALERT_SEVERITY_EVENTS = {
        "multiple_faces": "critical",
        "camera_lost": "warning",
        "phone_detected": "critical",
        "face_covered": "warning",
        "session_terminated": "critical",
        "devtools_detected": "warning",
    }
    # Consecutive/repeated tab-switch count within a session that raises
    # a "repeated tab switching" alert (Milestone 3, Part 19 example).
    ALERT_REPEATED_TAB_SWITCH_THRESHOLD = int(os.environ.get("ALERT_REPEATED_TAB_SWITCH_THRESHOLD", 3))
    # Continuous face-absence duration (seconds) that raises an
    # "extended face absence" alert.
    ALERT_EXTENDED_FACE_ABSENCE_SECONDS = int(os.environ.get("ALERT_EXTENDED_FACE_ABSENCE_SECONDS", 30))

    # Evidence capture (services/evidence_service.py) — only these
    # event_types trigger a stored screenshot/incident, per Milestone 3
    # Part 20 ("do not capture screenshots continuously").
    EVIDENCE_CAPTURE_EVENTS = {"multiple_faces", "phone_detected", "session_terminated"}

    # LangChain AI Integrity Report Agent (services/integrity_report_agent.py)
    LANGCHAIN_API_KEY = os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")

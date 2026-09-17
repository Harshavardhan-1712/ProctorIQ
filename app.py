"""
app.py
------
Application entry point.

Uses the Flask "application factory" pattern (`create_app`) rather than
a bare module-level `Flask(__name__)`. This is what makes the project
future-ready: new blueprints (face-monitoring, browser-event-logger,
analytics, etc.) can each be registered here with one line, and the
factory pattern also makes writing automated tests straightforward
later (each test can spin up a fresh app instance).
"""

import atexit
import os

from flask import Flask, request
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from config import Config
from models import db
from models.user import User
from models.exam_event import ExamEvent  # noqa: F401 — import registers the table with SQLAlchemy
from models.assessment import (  # noqa: F401 — imports register these tables with SQLAlchemy
    Assessment, Question, Option, AssessmentSession, CandidateAnswer, AssessmentResult,
)
from models.declaration import CandidateDeclaration  # noqa: F401
from models.analytics import (  # noqa: F401 — Milestone 3 tables
    Alert, Incident, Evidence, AIIntegrityReport, ClusterRun, ClusterAssignment,
)
from services.camera_service import Camera
from utils.formatting import format_local_datetime


def create_app(config_class: type = Config) -> Flask:
    """Construct and configure the Flask application."""

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Make sure instance/ and the uploads folder exist before anything
    # tries to write to them (SQLite file, future photo uploads).
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # --- Extensions -------------------------------------------------
    db.init_app(app)

    # CSRF protection (Module 6, Part 16) — covers every POST/PUT/
    # PATCH/DELETE route automatically. Traditional <form> submissions
    # carry the token via a hidden input (see templates); JS fetch()
    # calls carry it via the X-CSRFToken header, injected globally by
    # static/js/csrf.js so individual fetch() call sites across the
    # app didn't each need editing by hand.
    app.config["WTF_CSRF_ENABLED"] = False
    CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        # Flask-Login stores the user id as a string in the session;
        # SQLAlchemy's primary-key lookup needs it back as an int.
        return db.session.get(User, int(user_id))

    # --- Template filters -----------------------------------------------
    # Lets templates do `{{ user.created_at | local_datetime }}` instead
    # of every template re-implementing (and potentially getting wrong)
    # the UTC-to-local conversion.
    display_tz = app.config.get("DISPLAY_TIMEZONE")

    @app.template_filter("local_datetime")
    def local_datetime_filter(dt_utc):
        return format_local_datetime(dt_utc, tz_name=display_tz)

    @app.template_filter("num")
    def num_filter(value):
        """
        Display-format a number: whole floats show without a decimal
        (12.0 -> "12"), fractional ones keep it (12.5 -> "12.5"). Used
        wherever marks/scores (stored as Float for negative-marking
        support) are shown to a candidate — "12.0 marks" reads as a
        rendering glitch, not an intentional value.
        """
        if value is None:
            return ""
        try:
            f = float(value)
        except (TypeError, ValueError):
            return value
        return str(int(f)) if f == int(f) else str(f)

    # --- Branding context (Part 1: rebrand) -----------------------------
    # Injects PLATFORM_NAME/PLATFORM_TAGLINE into every template's
    # context automatically, so a future rebrand is a one-line change
    # in config.py instead of a find-and-replace across every .html file.
    @app.context_processor
    def inject_branding():
        return {
            "platform_name": app.config.get("PLATFORM_NAME"),
            "platform_tagline": app.config.get("PLATFORM_TAGLINE"),
        }

    # --- Blueprints ---------------------------------------------------
    # Each future module (face monitoring, analytics, etc.) will register
    # its own blueprint here, e.g.:
    #   from routes.face_monitoring import face_bp
    #   app.register_blueprint(face_bp)
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.camera import camera_bp
    from routes.monitoring import monitoring_bp
    from routes.preassessment import preassessment_bp
    from routes.assessment import assessment_bp
    from routes.invigilator import invigilator_bp
    from routes.public import public_bp
    from routes.insights import insights_bp  # Milestone 3

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(preassessment_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(invigilator_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(insights_bp)

    # Root route is handled by routes/public.py (landing page for
    # anonymous visitors, redirect to dashboard for logged-in candidates).

    # --- Response headers -------------------------------------------------
    @app.after_request
    def add_no_cache_headers(response):
        """
        Prevent the browser from caching authenticated/form pages.

        Without this, clicking the browser's Back button after logout
        can show a cached copy of the dashboard (or a stale, pre-filled
        registration/login form) instead of hitting the server again —
        which would incorrectly appear as if the session were still
        active. Static assets (CSS/JS/images) are left cacheable.
        """
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    # --- Error handlers -------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return "Page not found.", 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return "Internal server error. Please try again later.", 500

    # --- Database initialization ---------------------------------------
    with app.app_context():
        db.create_all()
        _ensure_schema_up_to_date()

    # Make sure the webcam device handle is released when the process
    # exits (e.g. Ctrl+C), rather than left open until the OS cleans it up.
    atexit.register(Camera.release_instance)

    return app


def _ensure_schema_up_to_date() -> None:
    """
    Lightweight auto-migration for existing databases.

    `db.create_all()` only creates tables that don't exist yet — it
    never alters an existing table. Every time a later module adds a
    column to an EXISTING table (as opposed to a brand new table,
    which create_all() already handles), that column needs to be
    added by hand for anyone running against an older database.
    Rather than requiring a manual migration step (or Alembic, for a
    project this size), this walks a declarative list of
    (table, column, ADD COLUMN clause) and adds whatever is missing.

    This is intentionally narrow in scope (SQLite `ALTER TABLE ... ADD
    COLUMN`) — a project with more frequent schema changes should
    switch to a real migration tool like Flask-Migrate/Alembic.
    """
    # (table_name, column_name, full "ADD COLUMN ..." clause)
    required_columns = [
        # Module 4
        ("users", "integrity_score", "ALTER TABLE users ADD COLUMN integrity_score INTEGER NOT NULL DEFAULT 100"),
        # Module 6
        ("users", "role", "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'candidate'"),
        ("questions", "category", "ALTER TABLE questions ADD COLUMN category VARCHAR(80)"),
        ("questions", "difficulty", "ALTER TABLE questions ADD COLUMN difficulty VARCHAR(20) NOT NULL DEFAULT 'Medium'"),
        ("assessment_sessions", "paused_at", "ALTER TABLE assessment_sessions ADD COLUMN paused_at DATETIME"),
        ("assessment_sessions", "invigilator_note", "ALTER TABLE assessment_sessions ADD COLUMN invigilator_note VARCHAR(255)"),
        ("assessment_sessions", "current_question_index", "ALTER TABLE assessment_sessions ADD COLUMN current_question_index INTEGER NOT NULL DEFAULT 0"),
        ("assessments", "passing_marks", "ALTER TABLE assessments ADD COLUMN passing_marks FLOAT"),
        ("assessments", "instructions", "ALTER TABLE assessments ADD COLUMN instructions TEXT"),
    ]

    inspector = db.inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    with db.engine.connect() as connection:
        for table, column, add_clause in required_columns:
            if table not in existing_tables:
                # Table doesn't exist yet at all (e.g. a database from
                # before this table was introduced) — db.create_all()
                # already created it fresh with every current column,
                # so there's nothing to migrate here.
                continue

            existing_columns = {col["name"] for col in inspector.get_columns(table)}
            if column not in existing_columns:
                connection.execute(db.text(add_clause))
                connection.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

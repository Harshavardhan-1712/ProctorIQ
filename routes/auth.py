"""
routes/auth.py
---------------
Blueprint handling registration, login, and logout.

Routes stay intentionally thin: they read the request, delegate to
utils/services for validation and business logic, then render a
response or redirect. This keeps the module easy to extend — e.g. the
face-monitoring module can later add a `/capture-photo` route to this
same blueprint without disturbing existing logic.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user

from services.auth_service import register_user, authenticate_user, EmailAlreadyExistsError
from services.event_logger import log_event
from utils.validators import validate_registration_form, validate_login_form

auth_bp = Blueprint("auth", __name__)


def _post_login_redirect(user):
    """
    Where to send a user right after login (or when an already-logged-in
    user hits /login or /register again). Invigilators/admins land on
    their console; candidates land on the candidate dashboard. Kept as
    one small helper rather than duplicating the role check at each of
    the three call sites below.
    """
    if user.is_invigilator():
        return redirect(url_for("invigilator.dashboard"))
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Candidate self-registration."""

    # Already logged in? No need to register again.
    if current_user.is_authenticated:
        return _post_login_redirect(current_user)

    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = validate_registration_form(full_name, email, password, confirm_password)

        if errors:
            for error in errors:
                flash(error, "danger")
            # Re-render with previously entered values (except passwords)
            return render_template(
                "register.html", full_name=full_name, email=email
            )

        try:
            new_user = register_user(full_name, email, password)
        except EmailAlreadyExistsError as e:
            flash(str(e), "danger")
            return render_template("register.html", full_name=full_name, email=email)
        except Exception:
            # Catch-all for unexpected DB errors so the candidate never
            # sees a raw stack trace.
            flash("Something went wrong while creating your account. Please try again.", "danger")
            return render_template("register.html", full_name=full_name, email=email)

        # Log the candidate in immediately so the (login_required) photo
        # capture page is reachable right after registration, without
        # making them log in twice.
        login_user(new_user)
        log_event(new_user.id, "registered")
        flash("Registration successful! Let's capture your profile photo.", "success")
        return redirect(url_for("camera.capture_photo"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Candidate login."""

    if current_user.is_authenticated:
        return _post_login_redirect(current_user)

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        errors = validate_login_form(email, password)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("login.html", email=email)

        user = authenticate_user(email, password)

        if user is None:
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email)

        # Creates the authenticated session (Flask-Login handles the
        # secure session cookie under the hood).
        login_user(user)
        log_event(user.id, "login")
        flash(f"Welcome back, {user.full_name}!", "success")
        return _post_login_redirect(user)

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """
    Destroy the session and return to login.

    `logout_user()` removes Flask-Login's own session keys, but we go
    further and clear the entire session — any leftover keys from this
    or future modules (e.g. an in-progress exam state) should never
    survive past logout. The user id is captured BEFORE logout_user()
    runs, since `current_user` becomes anonymous immediately after.
    `flash()` is called AFTER the clear so the "logged out" message
    itself still makes it to the next request.
    """
    user_id = current_user.id
    logout_user()
    session.clear()
    log_event(user_id, "logout")
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

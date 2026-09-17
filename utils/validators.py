"""
utils/validators.py
--------------------
Pure, reusable validation helpers with no Flask/DB dependencies.

Keeping these as plain functions (rather than inline in routes) means
future modules — e.g. a registration form for proctors/admins — can
reuse the same validation rules.
"""

import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

MIN_PASSWORD_LENGTH = 8


def is_valid_email(email: str) -> bool:
    """Basic RFC-5322-ish email format check."""
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def is_valid_password(password: str) -> bool:
    """Enforce a minimum password length."""
    return bool(password) and len(password) >= MIN_PASSWORD_LENGTH


def validate_registration_form(full_name: str, email: str, password: str, confirm_password: str):
    """
    Validate all registration fields together.

    Returns a list of human-readable error strings. An empty list means
    the form is valid.
    """
    errors = []

    if not full_name or not full_name.strip():
        errors.append("Full name is required.")

    if not email or not email.strip():
        errors.append("Email is required.")
    elif not is_valid_email(email):
        errors.append("Please enter a valid email address.")

    if not password:
        errors.append("Password is required.")
    elif not is_valid_password(password):
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

    if password != confirm_password:
        errors.append("Password and confirmation password do not match.")

    return errors


def validate_login_form(email: str, password: str):
    """Validate login fields. Returns a list of error strings."""
    errors = []

    if not email or not email.strip():
        errors.append("Email is required.")

    if not password:
        errors.append("Password is required.")

    return errors

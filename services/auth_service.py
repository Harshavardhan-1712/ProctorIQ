"""
services/auth_service.py
-------------------------
Business logic for candidate authentication, kept separate from the
Flask routes so that:
  - Routes stay thin (parse request -> call service -> render response).
  - This logic is unit-testable without spinning up Flask test clients.
  - Future modules (e.g. an admin-created-account flow) can reuse it.
"""

from sqlalchemy.exc import IntegrityError

from models import db
from models.user import User


class EmailAlreadyExistsError(Exception):
    """Raised when attempting to register with an email already in use."""
    pass


def get_user_by_email(email: str) -> User | None:
    """Fetch a user by email (case-insensitive)."""
    return User.query.filter(User.email.ilike(email.strip())).first()


def register_user(full_name: str, email: str, password: str) -> User:
    """
    Create a new candidate account.

    Raises:
        EmailAlreadyExistsError: if the email is already registered.
    """
    email = email.strip().lower()

    if get_user_by_email(email):
        raise EmailAlreadyExistsError(f"An account with email '{email}' already exists.")

    user = User(full_name=full_name.strip(), email=email)
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        # Safety net for a race condition (two simultaneous registrations
        # with the same email) that slips past the earlier check.
        db.session.rollback()
        raise EmailAlreadyExistsError(f"An account with email '{email}' already exists.")

    return user


def authenticate_user(email: str, password: str) -> User | None:
    """
    Verify credentials.

    Returns the User object on success, or None if the email doesn't
    exist or the password is incorrect.
    """
    user = get_user_by_email(email)
    if user and user.check_password(password):
        return user
    return None

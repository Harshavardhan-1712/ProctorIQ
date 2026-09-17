"""
routes/public.py
-------------------
Public-facing routes that don't require authentication (Module 6,
Part 6): the enterprise landing page, and the smart root route that
shows it to anonymous visitors while sending logged-in users straight
to their dashboard (or the invigilator dashboard, for that role).

Kept as its own blueprint rather than folded into routes/auth.py since
"marketing page" and "authentication" are different concerns that
happen to both be reachable while logged out.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

from models.user import User
from models.assessment import Assessment, AssessmentResult

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    """
    Root route. Anonymous visitors see the landing page; authenticated
    users are sent straight to the dashboard appropriate to their role
    — this is the one behavior change from Module 1-5 (which always
    redirected to /login), and it's purely additive: anyone who wants
    to log in can still click through from the landing page.
    """
    if current_user.is_authenticated:
        if current_user.is_invigilator():
            return redirect(url_for("invigilator.dashboard"))
        return redirect(url_for("dashboard.dashboard"))

    return render_template("landing.html", stats=_landing_stats())


def _landing_stats() -> dict:
    """
    Real counts pulled from the database for the landing page's
    Statistics section — not made-up marketing numbers.
    """
    try:
        return {
            "candidates": User.query.filter_by(role="candidate").count(),
            "assessments": Assessment.query.filter_by(is_active=True).count(),
            "attempts_completed": AssessmentResult.query.count(),
        }
    except Exception:
        # If the DB isn't ready yet for any reason, the landing page
        # should still render — just with zeros, not a 500 error.
        return {"candidates": 0, "assessments": 0, "attempts_completed": 0}

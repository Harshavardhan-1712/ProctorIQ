"""
services/browser_monitor.py
------------------------------
Server-side counterpart to static/js/browser-monitor.js (Module 4,
Part 4).

The browser-side script detects tab switches, window blur/focus,
fullscreen exits, refresh attempts, copy/paste, right-click, and (best
effort) devtools usage, then POSTs each one to
routes/monitoring.py:/monitoring/browser-event. This module is the
single source of truth for which event_type slugs are valid and what
severity each one carries — routes/monitoring.py should never hardcode
that mapping itself, so a future module can add a new browser event
type (e.g. "screen_share_detected") by editing only this file.
"""

from services.event_logger import SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_CRITICAL

# Every event_type the client is allowed to report, and the severity it
# carries. Anything not in this map is rejected by
# routes/monitoring.py — this is a small allowlist, not a place to
# trust arbitrary client input.
ALLOWED_BROWSER_EVENTS = {
    "tab_switch": SEVERITY_WARNING,
    "window_blur": SEVERITY_WARNING,
    "window_focus": SEVERITY_INFO,
    "fullscreen_exit": SEVERITY_CRITICAL,
    "page_refresh": SEVERITY_WARNING,
    "copy_attempt": SEVERITY_WARNING,
    "paste_attempt": SEVERITY_WARNING,
    "right_click": SEVERITY_WARNING,
    "devtools_detected": SEVERITY_CRITICAL,
}


class InvalidBrowserEventError(Exception):
    """Raised when the client reports an event_type outside the allowlist."""
    pass


def classify_event(event_type: str) -> str:
    """
    Return the severity for a given browser event_type.

    Raises InvalidBrowserEventError for anything not in the allowlist,
    so routes/monitoring.py can respond 400 Bad Request instead of
    silently logging arbitrary client-supplied event types.
    """
    if event_type not in ALLOWED_BROWSER_EVENTS:
        raise InvalidBrowserEventError(f"Unknown browser event type: '{event_type}'")
    return ALLOWED_BROWSER_EVENTS[event_type]

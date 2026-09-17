/**
 * static/js/browser-monitor.js
 * -------------------------------
 * Module 4, Part 4: client-side browser integrity monitoring.
 *
 * Watches for tab switches, window blur/focus, fullscreen exit, page
 * refresh attempts, copy/paste, right-click, and (best effort)
 * developer-tools usage, and reports each one through a caller-supplied
 * `onEvent(eventType, description)` callback.
 *
 * Deliberately framework-agnostic and self-contained (no fetch calls
 * of its own) so it can be reused by any future monitoring page —
 * the page wires `onEvent` to whatever transport it wants (today:
 * POST /monitoring/browser-event, see monitoring.html).
 */

const ExamGuardBrowserMonitor = (function () {
    let active = false;
    let onEvent = function () {};
    let devtoolsCheckInterval = null;

    // Devtools detection is inherently best-effort in a browser sandbox
    // (there's no real API for "is devtools open"). This uses the
    // classic heuristic: measure the gap between outer and inner window
    // dimensions, which grows noticeably when devtools is docked.
    const DEVTOOLS_THRESHOLD_PX = 160;
    let devtoolsWasOpen = false;
    let fullscreenWasEntered = false;

    function handleVisibilityChange() {
        if (!active) return;
        if (document.hidden) {
            onEvent("tab_switch", "Candidate switched to another tab or minimized the window.");
        }
    }

    function handleWindowBlur() {
        if (!active) return;
        onEvent("window_blur", "Exam window lost focus.");
    }

    function handleWindowFocus() {
        if (!active) return;
        onEvent("window_focus", "Exam window regained focus.");
    }

    function handleFullscreenChange() {
    if (!active) return;

    const isFullscreen = !!(
        document.fullscreenElement ||
        document.webkitFullscreenElement
    );

    // Do not treat the initial state (before fullscreen was ever entered)
    // as an exit violation.
    if (!isFullscreen && fullscreenWasEntered) {
        onEvent(
            "fullscreen_exit",
            "Candidate exited fullscreen mode."
        );
    }

    if (isFullscreen) {
        fullscreenWasEntered = true;
    }
}

    function handleBeforeUnload(e) {
        if (!active) return;
        onEvent("page_refresh", "Candidate attempted to refresh or close the page.");
        // Standard "are you sure you want to leave" prompt — also acts
        // as a soft deterrent, not just a detector.
        e.preventDefault();
        e.returnValue = "";
    }

    function handleCopy() {
        if (!active) return;
        onEvent("copy_attempt", "Copy action attempted during the exam.");
    }

    function handlePaste() {
        if (!active) return;
        onEvent("paste_attempt", "Paste action attempted during the exam.");
    }

    function handleContextMenu(e) {
        if (!active) return;
        onEvent("right_click", "Right-click context menu attempted.");
        e.preventDefault();
    }

    function checkDevtools() {
        if (!active) return;
        const widthGap = window.outerWidth - window.innerWidth;
        const heightGap = window.outerHeight - window.innerHeight;
        const isOpen = widthGap > DEVTOOLS_THRESHOLD_PX || heightGap > DEVTOOLS_THRESHOLD_PX;

        if (isOpen && !devtoolsWasOpen) {
            onEvent("devtools_detected", "Browser developer tools usage detected.");
        }
        devtoolsWasOpen = isOpen;
    }

    function start(eventCallback) {
        if (active) return;
        active = true;
        onEvent = eventCallback || onEvent;
        devtoolsWasOpen = false;
        fullscreenWasEntered = false;

        document.addEventListener("visibilitychange", handleVisibilityChange);
        window.addEventListener("blur", handleWindowBlur);
        window.addEventListener("focus", handleWindowFocus);
        document.addEventListener("fullscreenchange", handleFullscreenChange);
        document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
        window.addEventListener("beforeunload", handleBeforeUnload);
        document.addEventListener("copy", handleCopy);
        document.addEventListener("paste", handlePaste);
        document.addEventListener("contextmenu", handleContextMenu);

        devtoolsCheckInterval = setInterval(checkDevtools, 1500);
    }

    function stop() {
        if (!active) return;
        active = false;

        document.removeEventListener("visibilitychange", handleVisibilityChange);
        window.removeEventListener("blur", handleWindowBlur);
        window.removeEventListener("focus", handleWindowFocus);
        document.removeEventListener("fullscreenchange", handleFullscreenChange);
        document.removeEventListener("webkitfullscreenchange", handleFullscreenChange);
        window.removeEventListener("beforeunload", handleBeforeUnload);
        document.removeEventListener("copy", handleCopy);
        document.removeEventListener("paste", handlePaste);
        document.removeEventListener("contextmenu", handleContextMenu);

        if (devtoolsCheckInterval) {
            clearInterval(devtoolsCheckInterval);
            devtoolsCheckInterval = null;
        }
    }

    return { start: start, stop: stop };
})();

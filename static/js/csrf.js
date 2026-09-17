/**
 * static/js/csrf.js
 * --------------------
 * Module 6, Part 16: CSRF protection for JS-driven requests.
 *
 * Flask-WTF's CSRFProtect checks for a valid token on every state-
 * changing request (POST/PUT/PATCH/DELETE) — for traditional <form>
 * submissions that's a hidden input; for fetch()-based JSON calls
 * (which this app uses heavily, in the assessment session page,
 * monitoring page, etc.) it needs an `X-CSRFToken` header instead.
 *
 * Rather than editing every individual fetch() call site across
 * monitoring.html, session.html, capture_photo.html, and others (a
 * lot of surface area to touch and re-test), this file wraps the
 * global `fetch` ONCE so every existing and future fetch() call in
 * the app automatically carries the header for same-origin,
 * state-changing requests — a single, DRY choke point (Part 18).
 */

(function () {
    const tokenMeta = document.querySelector('meta[name="csrf-token"]');
    if (!tokenMeta) return;

    const token = tokenMeta.getAttribute("content");
    const STATE_CHANGING_METHODS = ["POST", "PUT", "PATCH", "DELETE"];
    const originalFetch = window.fetch;

    window.fetch = function (input, init) {
        init = init || {};
        const method = (init.method || "GET").toUpperCase();

        // Only attach to same-origin requests — never send this app's
        // token to a third-party URL.
        const url = typeof input === "string" ? input : input.url;
        const isSameOrigin = !/^https?:\/\//i.test(url) || url.startsWith(window.location.origin);

        if (STATE_CHANGING_METHODS.includes(method) && isSameOrigin) {
            init.headers = init.headers || {};
            if (init.headers instanceof Headers) {
                init.headers.set("X-CSRFToken", token);
            } else {
                init.headers["X-CSRFToken"] = token;
            }
        }

        return originalFetch(input, init);
    };
})();

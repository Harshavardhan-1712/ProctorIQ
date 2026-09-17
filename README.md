# ProctorIQ — AI-Powered Secure Assessment & Intelligent Proctoring Platform

*(Formerly "ExamGuard" — rebranded in Module 5, Part 1. See "Rebranding" below.)*

ProctorIQ is an enterprise-grade Secure Online Examination Monitoring
Platform, in the style of TCS iON, IBM Assessment, Pearson VUE, Mercer
Mettl, or CoCubes.

- **Module 1:** secure candidate registration, login, logout, and a
  protected dashboard.
- **Module 2:** OpenCV-based candidate profile photo capture — live
  webcam preview, capture/retake/save workflow.
- **Module 3:** Haar Cascade face detection & validation — a photo is
  only accepted if it contains exactly one face, with a bounding box
  drawn around it before saving.
- **Module 4:** enterprise UI redesign (sidebar navigation, corporate
  blue/white/slate theme), live camera + browser monitoring during a
  simulated exam session, an integrity-scoring engine, event logging,
  and a Chart.js analytics dashboard.
- **Module 5:** full product rebrand; a complete pre-assessment
  workflow (readiness check → overview → terms → privacy → integrity
  policy → declaration → final confirmation); a real assessment engine
  (question bank, navigation, palette, timer, auto-save, resume,
  auto-submit, scoring, results) with an enterprise exam-taking UI;
  live monitoring wired directly into the assessment session; and a
  configurable policy engine (starting score, penalty weights, risk
  thresholds) read from config instead of hardcoded.
- **Module 6:** role-based access control (candidate/invigilator);
  a live Invigilator Console with pause/resume/terminate session
  control (candidate side reacts in real time); an enterprise landing
  page; a candidate dashboard with real performance analytics (avg.
  score/integrity, trend, history); per-candidate deterministic option
  shuffling; genuine CSRF protection on every state-changing request;
  session-cookie hardening; CSV/JSON session export; and an extended
  seed script covering the full data model.

All six are built to be extended by future modules (MediaPipe-based
head pose/eye gaze/mask detection, a full admin CRUD panel, ML-based
analytics, LangChain report generation, PDF export) with minimal
changes to this code — see "Future Scope" below for what's deliberately
not yet built and why.

## Rebranding (Module 5, Part 1)

| | Before | After |
|---|---|---|
| Product name | ExamGuard | **ProctorIQ** |
| Tagline | "Secure Online Assessment Platform" | **"AI-Powered Secure Assessment & Intelligent Proctoring Platform"** |
| Logo/favicon | Generic Bootstrap shield icon | Custom SVG shield + eye + checkmark mark (`static/favicon.svg`) |

Both the name and tagline are centralized in `config.py`
(`PLATFORM_NAME`, `PLATFORM_TAGLINE`) and injected into every template
via a Flask `context_processor` in `app.py`. **A future rebrand is a
one-line config change**, not a find-and-replace across the codebase.

## Tech Stack

- **Backend:** Python 3.12+, Flask
- **Database:** SQLite
- **ORM:** SQLAlchemy (via Flask-SQLAlchemy)
- **Auth:** Flask-Login + Werkzeug password hashing
- **Computer Vision:** OpenCV (webcam capture + Haar Cascade face detection)
- **Frontend:** HTML5, CSS3, Bootstrap 5, Bootstrap Icons, Chart.js, Jinja2
  (Bootstrap/Icons/Chart.js are vendored locally under `static/vendor/` —
  no external CDN required at runtime)
- **Test data:** Faker (dev-only, via `seed_database.py`)

## Project Structure

```
proctoriq/
├── app.py                  # Application factory + entry point
├── config.py                # Central configuration (branding + policy engine + security)
├── seed_database.py          # Sample assessment + invigilator + Faker candidates + sample sessions
├── requirements.txt
├── instance/
│     proctoriq.db           # SQLite database (auto-created; auto-migrated for older DBs)
├── models/
│     __init__.py            # Shared `db` SQLAlchemy instance
│     user.py                 # User (candidate/invigilator) model — photo_path, integrity_score, role
│     exam_event.py           # ExamEvent model — audit/monitoring log (doubles as MonitoringEvent + Violation)
│     assessment.py           # Assessment, Question(+category/difficulty), Option, AssessmentSession
│                             #   (+pause/terminate fields), CandidateAnswer, AssessmentResult
│     declaration.py          # CandidateDeclaration model
├── routes/
│     auth.py                 # /register, /login, /logout — now role-aware post-login redirect
│     dashboard.py            # /dashboard (+Part 7 stats), /profile, /settings
│     camera.py               # /capture-photo, /video_feed, /capture, /retake, /save-photo, /skip-photo
│     monitoring.py           # /monitoring, /monitoring/start|status|stop, /monitoring/browser-event,
│                             #   /violations, /analytics, /analytics/data, /reports
│     preassessment.py        # /assessment/, /assessment/<id>/readiness..confirm (the 7-step wizard)
│     assessment.py           # /assessment/session/<id>, /answer, /submit, /state, /result, /progress
│     invigilator.py          # /invigilator/* — live roster, session detail, pause/resume/terminate, export
│     public.py               # / — landing page + role-aware redirect
├── services/
│     auth_service.py         # Registration/authentication business logic
│     camera_service.py       # OpenCV webcam wrapper, streaming, capture/save workflow
│     face_detection_service.py  # Haar Cascade face detection & validation
│     monitoring_service.py   # Live face-status + lighting checks (reused by readiness AND live monitoring)
│     browser_monitor.py      # Allowlist + severity classification for client-reported browser events
│     integrity_service.py    # Integrity score engine — reads policy from config, not hardcoded
│     event_logger.py         # Central ExamEvent read/write helpers
│     system_health.py        # Dashboard "System Health" card checks
│     readiness_service.py    # Bundles server-verifiable readiness checks for the wizard
│     assessment_service.py   # Session lifecycle, answers, scoring, pause/resume/terminate,
│                             #   option shuffling, candidate performance stats
├── utils/
│     validators.py           # Form input validation helpers
│     formatting.py           # UTC -> local timestamp display formatting
│     rbac.py                 # @role_required decorator for invigilator/admin routes
├── templates/
│     base.html               # Sidebar app shell (role-conditional nav) + centered auth layout
│     landing.html            # Enterprise public landing page (standalone, not extending base.html)
│     login.html, register.html
│     dashboard.html, profile.html, settings.html
│     capture_photo.html
│     monitoring.html, violations.html, analytics.html, reports.html
│     preassessment/
│         list.html, readiness.html, overview.html, terms.html, privacy.html,
│         integrity_policy.html, declaration.html, confirm.html
│     assessment/
│         session.html         # The enterprise exam-taking UI (Part 10), + paused overlay
│         paused.html          # Fallback page if a candidate lands directly on a paused session
│         result.html
│     invigilator/
│         dashboard.html       # Live Candidates roster with search/filter
│         session_detail.html  # Timeline, violation breakdown, controls, export links
├── static/
│     favicon.svg             # Custom logo/favicon
│     css/style.css           # Enterprise blue/white/slate theme
│     css/landing.css         # Landing-page-specific styles
│     js/browser-monitor.js   # Tab/focus/fullscreen/copy/paste/right-click/devtools detection
│     js/csrf.js              # Global fetch() patch injecting the CSRF header
│     js/main.js
│     vendor/                 # Locally-vendored Bootstrap, Bootstrap Icons, Chart.js (no CDN dependency)
│     uploads/                # Candidate profile photos: uploads/user_<id>.jpg
│         tmp/                # Temp captures awaiting Save/Retake (auto-created)
└── README.md
```

### Why this structure?

- **Blueprint architecture** (`routes/auth.py`, `routes/dashboard.py`) keeps
  route handlers thin and lets future modules register their own
  blueprints in `app.py` with a single import + one line, without
  touching existing auth code.
- **`services/`** holds business logic (registration, authentication)
  separate from Flask request handling, so it's independently testable
  and reusable.
- **`utils/`** holds pure helper functions (validation) with zero
  Flask/DB dependencies.
- **`models/`** exposes a single shared `db` object to avoid circular
  imports as more models (ExamSession, IntegrityScore, EvidenceLog...)
  are added later.
- **`User.photo_path`** is already in the schema (nullable) so the
  OpenCV face-monitoring module can populate it later with zero
  migrations.

## Database Changes for Module 2

**No schema migration is required.** The `User` model already had a
nullable `photo_path` column from Module 1 (provisioned exactly for
this purpose). Module 2 simply starts writing to it:

- Before a photo is captured: `photo_path` is `NULL` → dashboard shows
  a first-initial placeholder avatar.
- After a candidate saves a photo: `photo_path` is set to a path
  relative to `static/`, e.g. `uploads/user_7.jpg` → dashboard renders
  it via `url_for('static', filename=user.photo_path)`.

If you already have an `instance/examguard.db` from Module 1, it works
as-is — just restart the app so `static/uploads/` and
`static/uploads/tmp/` get created.

## Features Implemented (Module 3)

- ✅ Face detection via OpenCV's pre-trained Haar Cascade
  (`haarcascade_frontalface_default.xml`, bundled with `opencv-python-headless`
  — no separate download needed)
- ✅ Every captured frame is converted to grayscale and histogram-equalized
  before detection (improves reliability under uneven webcam lighting)
- ✅ **Accepted only if exactly one face is detected** — zero or multiple
  faces are rejected with a clear, specific message (distinguishes "no
  face" from "N faces detected")
- ✅ A bounding box is drawn around the single detected face, and it's
  this annotated image that gets saved — not the raw, unvalidated frame
- ✅ Only validated images ever reach `static/uploads/`; rejected
  captures are never written to disk at all
- ✅ Redesigned dashboard: a **profile card** (large photo/avatar, name,
  email, Face Verified/Not Verified badge, member-since date) and
  **status cards** (Exam Status, Face Verification, Account Security,
  Registered On)
- ✅ Registration timestamps are now converted from stored UTC to a
  configurable local timezone before display (`DISPLAY_TIMEZONE`,
  default `Asia/Kolkata`) instead of showing raw UTC as if it were
  local time
- ✅ Login/registration forms are always blank on a fresh GET request;
  logout now clears the entire session (not just the Flask-Login keys)
  and dynamic pages are marked `no-store` so the browser's Back button
  can't show stale authenticated/form state after logout
- ✅ Distinct, robust error handling for two different failure modes:
  - **Camera failure** (device disconnected/busy/no permission) — fatal
    for the session, live feed and Capture button are hidden, the
    candidate can still Skip
  - **Face validation failure** (0 or 2+ faces) — recoverable, the live
    feed stays up and the candidate can simply try capturing again

### How face validation fits into the capture workflow

`routes/camera.py`'s `/capture` endpoint now does three steps in order:

1. `services/camera_service.read_current_frame()` — grab one raw frame
   from the webcam (raises `CameraError` on hardware failure → HTTP 503).
2. `services/face_detection_service.validate_and_annotate_face(frame)` —
   detect faces; raises `FaceDetectionError` unless exactly one is found
   (→ HTTP 422, with `face_count` in the JSON body so the front-end
   could show a different message for 0 vs. 2+ if desired).
3. `services/camera_service.save_frame_as_temp(user_id, annotated_frame)` —
   only reached if step 2 succeeded, so nothing invalid is ever written
   to `static/uploads/tmp/`.

`/save-photo` then simply promotes that already-validated temp file to
its permanent location — no re-validation needed, since an invalid
temp file could never have existed in the first place.

`services/face_detection_service.py` has **no Flask or database
dependencies** — it's pure functions operating on numpy frames, so a
future face-verification module (e.g. comparing a live frame against
the saved reference photo) can import `detect_faces()` directly and
reuse the same tuned parameters (`SCALE_FACTOR`, `MIN_NEIGHBORS`,
`MIN_FACE_SIZE`) without going through the web layer at all.

### Database Changes for Module 3

**None.** `User.photo_path` (added in Module 1, used in Module 2) is
reused as-is. "Face Verified" status on the dashboard is derived
directly from whether `photo_path` is set — since Module 3 guarantees
only single-face, validated images are ever saved there, a non-null
`photo_path` *is* proof of face verification. No new column or
migration is required.

## Features Implemented (Module 4)

### Part 1 & 2 — Enterprise UI & Professional Dashboard
- Full frontend redesign: left sidebar (Dashboard, Candidate Profile,
  Exam Monitoring, Violations, Analytics, Reports, Settings, Logout),
  corporate top bar ("ExamGuard — Secure Online Assessment Platform"),
  blue/white/slate palette, Bootstrap Icons, no emoji anywhere
  (verified programmatically in testing — see below)
- Dashboard rebuilt with the 5 required sections: Candidate Profile
  (photo, Candidate ID, name, email, registration time, identity
  status), Exam Monitoring Status (camera/face/browser/session),
  System Health (DB/OpenCV/Flask/camera), Upcoming Exam card with a
  **Launch Secure Exam** button, and a Recent Activity timeline

### Part 3 — Live Camera Monitoring
- `/monitoring` page reuses the existing `/video_feed` MJPEG stream
  (Module 2) and `services/face_detection_service.py` (Module 3) —
  no camera or detection code was duplicated
- `services/monitoring_service.py` classifies each check into
  `single_face` / `no_face` / `multiple_faces` / `camera_error`
- The page polls `/monitoring/status` every 3 seconds; the badge and
  integrity score update live

### Part 4 — Browser Monitoring
- `static/js/browser-monitor.js` detects tab switches, window
  blur/focus, fullscreen exit, page refresh/close attempts, copy,
  paste, right-click, and (best-effort, via the outer/inner window
  size heuristic) devtools usage
- Each event is POSTed to `/monitoring/browser-event`, validated
  against an allowlist in `services/browser_monitor.py`, logged, and
  scored

### Part 5 — Event Logging
- New `ExamEvent` model/table: `id`, `user_id`, `event_type`,
  `severity`, `description`, `timestamp`
- `services/event_logger.py` is the single place that writes/reads
  events; registration, login, logout, face verification, monitoring
  start/stop, face-status transitions, and browser events all log
  through it

### Part 6 — Integrity Score Engine
- `services/integrity_service.py`: every monitoring session starts at
  100 (reset on `/monitoring/start`); deductions are exactly as
  specified — Tab Switch −5, Window Blur −5, No Face −10, Multiple
  Faces −20, Camera Lost −30, Fullscreen Exit −10 — clamped at 0
- Score is persisted on `User.integrity_score`, not just computed on
  the fly, so it displays instantly anywhere in the app
- **Deduplication:** a face-status problem (e.g. no face) only
  deducts once when it *starts*, not on every 3-second poll while it
  persists — recovery is logged as an informational event without
  restoring points, matching how real proctoring systems behave

### Part 7 — Analytics Dashboard
- `/analytics` renders 4 live stat cards + 3 Chart.js charts
  (Violation Distribution doughnut, Monitoring Statistics bar,
  Timeline of Events line), all fed by the `/analytics/data` JSON
  endpoint
- Chart.js is vendored locally (see "Why vendored assets" below) —
  no external CDN needed at runtime

### Part 8 — Privacy & Session Improvements
- `session.clear()` on logout (not just Flask-Login's own keys)
- `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` on
  every dynamic page (static assets excluded) — prevents the browser
  Back button from showing a stale authenticated page after logout
- `autocomplete="off"` on registration/login fields,
  `autocomplete="new-password"` on password fields
- Login/registration forms confirmed blank on every fresh GET request
  (no leftover values, no placeholder pre-fill from a previous account)
- All dashboard/monitoring/violations/analytics/reports/profile/settings
  routes remain `@login_required`, redirecting anonymous users to
  `/login`

### Part 9 — Backend Improvements
- New services added exactly as specified:
  `monitoring_service.py`, `integrity_service.py`, `event_logger.py`,
  `browser_monitor.py` (plus `system_health.py` for the dashboard's
  health card) — routes stay thin orchestration layers; all business
  logic lives in services

### Why vendored front-end assets (not strictly asked for, but worth noting)
Bootstrap, Bootstrap Icons, and Chart.js are served from
`static/vendor/` instead of a CDN. This was found necessary during
testing — some networks (including the sandbox this was built in)
block `cdn.jsdelivr.net`, which silently breaks all styling and
charts with no error shown to the user. Self-hosting these assets
also fits an "enterprise" exam platform that may run on locked-down
corporate networks. If you'd prefer CDN links instead (e.g. to always
get the latest patch versions), swap the `<link>`/`<script>` tags in
`templates/base.html` and `templates/analytics.html` back to the
jsdelivr URLs.

## Database Schema Updates (Module 4)

**New table — `exam_events`:**

| Column       | Type          | Notes                                  |
|--------------|---------------|------------------------------------------|
| `id`         | INTEGER PK    |                                            |
| `user_id`    | INTEGER FK    | → `users.id`                              |
| `event_type` | VARCHAR(50)   | e.g. `tab_switch`, `no_face`, `login`     |
| `severity`   | VARCHAR(20)   | `info` / `warning` / `critical`           |
| `description`| VARCHAR(255)  | Human-readable sentence for the UI        |
| `timestamp`  | DATETIME      | UTC, defaults to `datetime.utcnow()`      |

Created automatically by `db.create_all()` — no manual step needed,
even for a database that already exists from Modules 1–3.

**Modified table — `users`:** one new column, `integrity_score INTEGER
NOT NULL DEFAULT 100`.

Because `db.create_all()` never alters existing tables, `app.py`
includes a small **auto-migration** (`_ensure_schema_up_to_date()`)
that checks for this column via SQLAlchemy's inspector and runs
`ALTER TABLE users ADD COLUMN integrity_score INTEGER NOT NULL DEFAULT 100`
if it's missing. This was tested against a simulated Module 1–3
database and confirmed to upgrade it cleanly with existing rows
correctly defaulting to a score of 100 — **no manual migration step
or database deletion is required** when pulling Module 4 on top of an
older database. (For a project with more frequent schema churn than
this, switching to Flask-Migrate/Alembic would be the next step.)

## Updated Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Browser                                 │
│  ┌───────────────┐  ┌────────────────────┐  ┌──────────────────┐   │
│  │ Auth pages    │  │ App shell (sidebar) │  │ browser-monitor.js│   │
│  │ login/register│  │ dashboard/profile/  │  │ (tab/blur/full-  │   │
│  │               │  │ monitoring/violations│  │  screen/copy/etc)│   │
│  │               │  │ /analytics/reports/  │  │  → POSTs events  │   │
│  │               │  │ settings             │  │                  │   │
│  └───────┬───────┘  └──────────┬───────────┘  └─────────┬────────┘   │
└──────────┼─────────────────────┼───────────────────────┼────────────┘
           │ HTTP                 │ HTTP + fetch()          │ fetch()
┌──────────▼─────────────────────▼───────────────────────▼────────────┐
│                          Flask (app.py)                               │
│  Blueprints: auth_bp | dashboard_bp | camera_bp | monitoring_bp       │
│                                                                        │
│  routes/auth.py ──────► services/auth_service.py ─────► models/user  │
│  routes/dashboard.py ──► services/event_logger.py                    │
│                    ├───► services/integrity_service.py               │
│                    └───► services/system_health.py                   │
│  routes/camera.py ─────► services/camera_service.py ───► OpenCV      │
│                    └───► services/face_detection_service.py ─► OpenCV│
│  routes/monitoring.py ─► services/monitoring_service.py               │
│                    │      (reuses camera_service + face_detection)   │
│                    ├───► services/browser_monitor.py                 │
│                    ├───► services/integrity_service.py               │
│                    └───► services/event_logger.py ──► models/exam_event│
└─────────────────────────────────┬──────────────────────────────────┘
                                   │ SQLAlchemy
                          ┌────────▼─────────┐
                          │  SQLite (instance)│
                          │  users, exam_events│
                          └───────────────────┘
```

## Testing Steps

Automated tests were run against this build using Flask's test client
(plus real OpenCV Haar Cascade detection on real sample images — no
mocked detection results). To reproduce:

1. **Install and run** (see Setup & Run below).
2. **Auth regression:** register a candidate → confirm redirect to
   `/capture-photo`; register a second account with the same email →
   confirm rejection; log in with a wrong password → confirm
   rejection; log in correctly → confirm dashboard access.
3. **Photo capture + face validation:** on `/capture-photo`, verify
   the live feed loads (or fails gracefully with a message if no
   webcam is present); capture a photo with zero or multiple faces in
   frame → confirm a rejection message and that no file is written to
   `static/uploads/`; capture with exactly one face → confirm the
   preview shows a bounding box, then Save → confirm `photo_path` is
   set in the database and the photo appears on the dashboard.
4. **Sidebar navigation:** confirm all 8 sidebar links
   (Dashboard/Candidate Profile/Exam Monitoring/Violations/Analytics/
   Reports/Settings/Logout) load without error.
5. **Live monitoring:** on `/monitoring`, click **Launch Secure Exam**
   → confirm the integrity score resets to 100 and the face-status
   badge updates within a few seconds; cover the camera or step out of
   frame → confirm the badge changes to "No face detected" and the
   score drops by 10 (only once, not repeatedly); switch browser tabs
   → confirm a "Tab Switched" entry appears in the Live Monitoring Log
   and the score drops by 5; click **End Monitoring Session** → confirm
   monitoring stops.
6. **Violations & Reports:** confirm `/violations` lists only
   warning/critical events, and `/reports` lists the full chronological
   history with the final integrity score.
7. **Analytics:** confirm `/analytics` renders 4 stat cards and 3
   charts, with numbers matching the events actually logged.
8. **Privacy/session:** log out, then use the browser Back button →
   confirm the dashboard does NOT reappear from cache; open
   `/register` or `/login` fresh → confirm both forms are blank.
9. **Backward compatibility:** run against a database created by an
   earlier module (Module 1–3) → confirm the app starts cleanly and
   the auto-migration adds `integrity_score` without manual steps.

## Git Commit Message

```
feat(module-4): enterprise UI redesign + live exam monitoring & integrity scoring

- Redesign frontend with sidebar navigation, corporate blue/white/slate
  theme, and Bootstrap Icons; remove all emoji from the UI
- Add live camera monitoring (services/monitoring_service.py) reusing
  the existing camera_service.py and face_detection_service.py
- Add browser-integrity monitoring (static/js/browser-monitor.js +
  services/browser_monitor.py): tab switch, blur/focus, fullscreen
  exit, refresh, copy/paste, right-click, best-effort devtools detection
- Add ExamEvent model + services/event_logger.py for centralized
  audit/monitoring event logging
- Add services/integrity_service.py: 100-point integrity score with
  per-violation deductions, deduplicated across repeated bad states
- Add routes/monitoring.py: /monitoring, /monitoring/start|status|stop,
  /monitoring/browser-event, /violations, /analytics(+/data), /reports
- Add User.integrity_score column with an automatic lightweight
  migration for pre-existing Module 1-3 databases
- Vendor Bootstrap, Bootstrap Icons, and Chart.js locally
  (static/vendor/) instead of loading from a CDN
- Harden session/privacy: full session.clear() on logout, no-store
  cache headers on authenticated pages, autocomplete disabled on
  auth forms
- Preserve all Module 1-3 functionality (verified via full regression
  test suite)
```

## Updated Architecture Diagram (Module 5)

```
┌───────────────────────────────────────────────────────────────────────┐
│                              Browser                                   │
│  Auth pages | App shell (sidebar incl. new "Assessments" nav) |        │
│  Pre-assessment wizard (7 steps) | Assessment session UI               │
│      (question card + palette + live camera + integrity gauge)         │
│      -> reuses browser-monitor.js exactly as Module 4 built it         │
└──────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP + fetch()
┌──────────────────────────────▼──────────────────────────────────────┐
│                          Flask (app.py)                                │
│  Blueprints: auth_bp | dashboard_bp | camera_bp | monitoring_bp |      │
│              preassessment_bp (NEW) | assessment_bp (NEW)              │
│                                                                          │
│  routes/preassessment.py ──► services/readiness_service.py             │
│                          │      └──► services/monitoring_service.py    │
│                          │             (SAME service Module 4 built,   │
│                          │              now also powers readiness)     │
│                          ├──► services/assessment_service.py           │
│                          └──► services/event_logger.py                 │
│                                                                          │
│  routes/assessment.py ──────► services/assessment_service.py           │
│                          ├──► services/integrity_service.py            │
│                          │      (reads policy from config.py, NEW)     │
│                          └──► services/event_logger.py                 │
│                                                                          │
│  Assessment session page's JS calls routes/monitoring.py's EXISTING    │
│  /monitoring/start|status|browser-event endpoints directly —           │
│  no monitoring logic duplicated in routes/assessment.py                │
└──────────────────────────────┬──────────────────────────────────────┘
                                │ SQLAlchemy
                      ┌─────────▼──────────┐
                      │   SQLite (instance)  │
                      │ users, exam_events,   │
                      │ assessments, questions,│
                      │ options, assessment_   │
                      │ sessions, candidate_   │
                      │ answers, assessment_   │
                      │ results, candidate_    │
                      │ declarations (all NEW) │
                      └───────────────────────┘
```

## Features Implemented (Module 5)

### Parts 2-7 — Pre-Assessment Workflow
A strictly linear 7-step wizard (`routes/preassessment.py`), gated by
session state so a candidate can't skip ahead by typing a later URL:

`Identity Verification (reuses Module 2/3's /capture-photo)` → **Readiness
Check** → **Overview** → **Terms & Conditions** → **Privacy Policy** →
**Integrity Policy** → **Declaration** → **Final Confirmation** → assessment starts

- **Readiness Check** (Part 3): 4 checks verified server-side by reusing
  `monitoring_service.py` (Camera Connected, Face Visible, Single Face
  Detected, Good Lighting — the last is a new `check_lighting_status()`
  addition), plus 4 checks done client-side in JS (Browser Supported,
  Fullscreen Enabled, Stable Internet via a timed fetch, Microphone as
  optional). An overall readiness percentage is shown live, and **Start**
  stays disabled until every mandatory check passes.
- **Overview** (Part 4): all 8 requested fields, pulled from the real
  `Assessment` row — nothing hardcoded.
- **Terms/Privacy/Integrity Policy** (Part 5): three focused pages
  covering every topic the spec listed. The Integrity Policy page
  renders its point values **live from `config.py`**, not hardcoded text.
- **Declaration** (Part 6): all 8 required checkboxes; the final "Start
  Assessment" continuation is blocked (both client-side via JS and
  server-side on POST) until every box is checked. A `CandidateDeclaration`
  row is written with a UTC timestamp.
- **Final Confirmation** (Part 7): explains the timer/monitoring/no-pause/
  violations-recorded implications, with Cancel/Start Assessment buttons.

### Parts 8-10 — Assessment Engine + Enterprise UI
A real, working assessment engine (`routes/assessment.py` +
`services/assessment_service.py`), tested against actual scoring math,
not just rendered:

- **Question bank & navigation**: MCQ questions with Previous/Next,
  Mark for Review, and a full question palette (Answered/Current/
  Skipped/Review states, matching Part 10's exact legend)
- **Auto-save**: every option selection and review-flag toggle is
  POSTed and persisted immediately — nothing waits for final submit
- **Resume support**: re-entering the pre-assessment flow for an
  assessment you already have an in-progress attempt for returns you
  to the *same* session with previously saved answers intact, rather
  than burning another attempt (verified in testing)
- **Timer & auto-submit**: the client shows a live countdown, but
  expiry is checked **server-side** on every state poll and on session
  load — a candidate cannot extend time by manipulating client JS
- **Scoring**: correct/incorrect/unanswered counts, percentage,
  pass/fail against `passing_score_percent`, optional negative marking
  — verified against hand-computed expected scores in testing
- **Enterprise UI** (Part 10): header strip (candidate, assessment
  name, live timer, integrity score, camera status, fullscreen status),
  center question card, right sidebar (live camera feed, monitoring
  status, warnings feed, circular integrity gauge), bottom navigation +
  palette. No emojis; corporate blue/white/slate palette throughout.
- **Security**: verified the correct-answer flag (`is_correct`) is
  **never** sent to the browser — only question/option id and text are
  serialized into the client-side JSON. Verified a candidate gets HTTP
  403 attempting to view another candidate's session.

### Part 11 — Live Monitoring, Reused Not Duplicated
The assessment session page calls the **exact same** `/monitoring/start`,
`/monitoring/status`, `/monitoring/browser-event` endpoints Module 4
already built, and loads the same `static/js/browser-monitor.js`. No
camera, face-detection, or browser-monitoring logic was copied or
reimplemented for Module 5.

### Part 13/14 (extended) — Configurable Policy + Risk Labels
- Starting score, all 6 penalty weights (plus 2 forward-compatible
  ones for Part 12's future phone/face-covering detectors), and both
  risk thresholds now live in `config.py` (env-var overridable), read
  by `services/integrity_service.py` via `current_app.config` instead
  of being hardcoded module constants.
- Added `risk_label()` returning the spec's exact **Low / Medium /
  High** terminology (kept `score_status_label()` too, for backward
  compatibility with existing Module 4 templates that already use it).

### Part 19 — Faker-Based Seeding
`seed_database.py` creates one real, curated sample assessment (10
genuine aptitude/reasoning MCQs — Faker is deliberately **not** used
for question content, only for filler candidate accounts) plus a
configurable number of dummy candidates via Faker for UI/analytics
testing. Idempotent — safe to re-run.

## Database Schema (Module 5 additions)

**New tables**, all created automatically by `db.create_all()` (no
migration needed — these are new tables, not new columns on existing
ones):

| Table | Key columns |
|---|---|
| `assessments` | name, description, duration_minutes, passing_score_percent, allowed_attempts, negative_marking_enabled/value, question_pattern, monitoring_enabled, is_active |
| `questions` | assessment_id (FK), text, marks, order |
| `options` | question_id (FK), text, is_correct, order |
| `assessment_sessions` | user_id (FK), assessment_id (FK), started_at, ends_at, submitted_at, status, integrity_score_at_submit |
| `candidate_answers` | session_id (FK), question_id (FK), selected_option_id (FK, nullable), marked_for_review, answered_at — unique on (session_id, question_id) |
| `assessment_results` | session_id (FK, unique), user_id (FK), assessment_id (FK), score, total_marks, percentage, passed, correct/incorrect/unanswered_count, submitted_at |
| `candidate_declarations` | user_id (FK), assessment_id (FK), 8 boolean acknowledgement columns, declared_at |

No changes to `users` or `exam_events` (Module 4's schema) — fully
additive.

## API Endpoints (Module 5 additions)

**Pre-assessment** (`routes/preassessment.py`, prefix `/assessment`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/assessment/` | List active assessments |
| GET | `/assessment/<id>/readiness` | Step 1 page |
| GET | `/assessment/readiness/status` | JSON: server-verifiable readiness checks (polled) |
| POST | `/assessment/<id>/readiness/continue` | Advance to Overview |
| GET / POST | `/assessment/<id>/overview` \| `/terms` \| `/privacy` \| `/integrity-policy` | Steps 2-5 pages + their `/continue` POST siblings |
| GET / POST | `/assessment/<id>/declaration` | Step 6: render form / validate & store |
| GET | `/assessment/<id>/confirm` | Step 7 page |
| GET | `/assessment/<id>/confirm/cancel` | Abort the flow |
| POST | `/assessment/<id>/confirm/start` | Create/resume the AssessmentSession, redirect into the exam |

**Assessment engine** (`routes/assessment.py`, prefix `/assessment`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/assessment/session/<id>` | The exam-taking page |
| GET | `/assessment/session/<id>/state` | JSON: timer/palette/score poll (also enforces server-side expiry) |
| POST | `/assessment/session/<id>/answer` | Save one answer / review flag |
| POST | `/assessment/session/<id>/submit` | Finalize and score |
| GET | `/assessment/session/<id>/result` | Results page |

All 14 routes are `@login_required`; session-ownership is checked on
every session-scoped route (403 if it isn't yours).

## Testing Checklist

Everything below was actually executed against the running app (Flask
test client + real Haar Cascade detection on real images), not just
written and assumed to work:

- [x] Pre-assessment step-gating: jumping directly to `/declaration`
      without completing earlier steps redirects back to Readiness
- [x] Readiness page: server-side camera/face/lighting checks return
      correct JSON; client-side checks (browser/fullscreen/mic/internet)
      verified by inspection of the JS logic
- [x] Overview/Terms/Privacy/Integrity Policy: each step's `/continue`
      correctly advances the session-tracked step and unlocks the next page
- [x] Integrity Policy page renders live values from `config.py`, not
      hardcoded numbers
- [x] Declaration: partial submission (missing checkboxes) rejected
      with an error; full submission stored as a `CandidateDeclaration`
      row with a real timestamp
- [x] Final Confirmation → Start creates an `AssessmentSession`
- [x] Session page loads with the correct question count; **verified
      `is_correct` is never present in the client-side payload**
- [x] Answer auto-save, mark-for-review, and state polling (palette
      answered-count) all verified against direct DB state
- [x] Submission scoring verified against hand-computed expected
      results (7 correct / 2 incorrect / 1 unanswered → exact score match)
- [x] Resume support: re-entering the flow for an assessment with an
      existing in-progress session returns the *same* session id, with
      previously saved answers intact
- [x] Cross-candidate access control: viewing another candidate's
      session returns HTTP 403
- [x] Time-expiry: manually expiring a session's `ends_at` and then
      loading it triggers server-side auto-submit (`status` becomes
      `auto_submitted`)
- [x] Attempt-limit enforcement: a 3rd attempt on a 2-attempt
      assessment is correctly rejected
- [x] Full Module 1-4 regression re-run and passing (registration,
      dedup, login, face capture/validation, live monitoring, integrity
      deductions, analytics, logout + route protection — including all
      new Module 5 routes)
- [x] Rebrand: page titles and branding read from config, not hardcoded,
      confirmed via rendered HTML inspection
- [ ] Full visual/pixel QA of the new pages — screenshots were captured
      via Playwright and are valid, correctly-sized PNGs, but didn't
      render for visual review in this session. Worth a manual look
      before considering the UI signed off.

## Git Commit Message

```
feat(module-5): rebrand to ProctorIQ + full pre-assessment workflow + assessment engine

- Rebrand: ExamGuard -> ProctorIQ, new tagline, custom SVG favicon/logo,
  both centralized in config.py and injected via a context_processor
- Add 7-step pre-assessment workflow (routes/preassessment.py):
  readiness check, overview, terms, privacy, integrity policy,
  declaration, final confirmation - session-gated, cannot be skipped
- Add services/readiness_service.py + monitoring_service.check_lighting_status():
  reuses existing camera/face-detection services for server-verifiable
  readiness checks
- Add a real assessment engine (routes/assessment.py +
  services/assessment_service.py): question navigation, palette,
  auto-save, resume support, server-authoritative timer + auto-submit,
  scoring with optional negative marking
- Add enterprise assessment-taking UI (templates/assessment/session.html):
  header strip, question card, live-camera/monitoring/integrity sidebar,
  question palette - wired to Module 4's existing monitoring endpoints
  (no duplicated camera/browser-monitoring logic)
- New models: Assessment, Question, Option, AssessmentSession,
  CandidateAnswer, AssessmentResult, CandidateDeclaration (all new
  tables, no migration needed for existing databases)
- Move integrity scoring policy (starting score, penalty weights, risk
  thresholds) from hardcoded constants into config.py; add risk_label()
  with Low/Medium/High terminology
- Add seed_database.py: one curated sample assessment (real questions,
  not Faker-generated) + Faker-based dummy candidates for testing
- Verified: correct-answer data never reaches the client; cross-candidate
  session access returns 403; full Module 1-4 regression still passes
- Deferred (see README Future Scope): MediaPipe-based advanced
  proctoring, admin dashboard/RBAC, ML analytics, LangChain reports,
  PDF export, notification drawer, dark mode
```

## Deployment Instructions

This remains a single-process Flask app suitable for a small
department/institution deployment; it has not been changed to require
a different deployment model in Module 5. For anything beyond local
development:

1. **Use a production WSGI server** — the Flask dev server
   (`app.run()`) is not meant for production. Run with Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn -w 1 -b 0.0.0.0:8000 "app:create_app()"
   ```
   Use `-w 1` (single worker) unless/until the webcam-handling code in
   `services/camera_service.py` is adapted for multi-process use — the
   `Camera` singleton assumes one process owns the device.
2. **Set a real `SECRET_KEY`** via environment variable — never use
   the `dev-secret-key-...` default outside local development.
3. **Point `DATABASE_URL` at a real database file location** (or swap
   to Postgres/MySQL by changing the URI — SQLAlchemy makes this a
   config-only change, though `_ensure_schema_up_to_date()`'s raw
   `ALTER TABLE` in `app.py` is SQLite-specific and would need
   adjusting for another engine).
4. **Serve `static/` via a real web server or CDN** in front of Flask
   for production traffic (nginx, or a cloud storage bucket) rather
   than letting Flask serve static files directly.
5. **Run `seed_database.py` once** after first deploy if you want the
   sample assessment available immediately; otherwise assessments can
   be added directly via the database until Part 16's admin UI exists.
6. **HTTPS is required** in any real deployment — camera/microphone
   access via `getUserMedia`-adjacent browser APIs and secure cookies
   both depend on it. This app doesn't terminate TLS itself; put it
   behind a reverse proxy that does.

## Future Scope

Explicitly deferred from this pass, each substantial enough to deserve
its own focused effort rather than a rushed, undertested addition:

- **Part 12 — Advanced AI proctoring**: MediaPipe-based head pose
  estimation, eye gaze tracking, mask/sunglasses/face-covering
  detection, and phone/book/additional-person detection. The
  `PENALTY_WEIGHTS` config already has `phone_detected` and
  `face_covered` entries ready to receive these events the moment a
  `services/pose_estimation_service.py` (or similar) starts emitting them.
- **Part 13 (UI half) — Admin-configurable policy UI**: the *values*
  are already centralized in `config.py` (env-var overridable); what's
  missing is an in-app settings screen to edit them without redeploying.
- **Part 16 — Admin dashboard**: candidate/assessment/question
  management, a monitoring console, session logs, violation reports.
  This needs role-based access control (an `is_admin` flag or a
  separate `Role` model) added first — a real architectural decision
  that shouldn't be bolted on quickly.
- **Part 17 — ML-based analytics**: Pandas/Matplotlib/scikit-learn
  integrity distribution, violation trends, session heatmaps, K-Means
  behavior clustering. Needs a meaningful volume of real session data
  (via `seed_database.py --candidates N` plus scripted attempts) to be
  worth building against.
- **Part 18 — LangChain AI report generation**: needs a decision on
  which LLM/API to call and how credentials are managed; `event_logger`
  and `integrity_service` already expose exactly the structured data
  (not HTML) such a report generator would consume.
- **Part 20 — Notification system**: Bootstrap toast infrastructure +
  a notification drawer, replacing the current flash-message banners.
- **Part 21 — UI polish**: dark mode, skeleton loaders, micro-animations,
  a full accessibility audit (keyboard nav, contrast checking beyond
  the current palette choices).
- **Part 22 — PDF export**: CSV/JSON export of reports is cheap to add
  as a follow-up (reuses `event_logger.get_all_events()` directly);
  PDF needs a rendering library (e.g. WeasyPrint) and template design.

## Backward Compatibility

Confirmed via automated regression testing (not just by inspection):
every Module 1-4 route, service, and template continues to work
unmodified in behavior. The only *changes* to pre-existing files were
additive (new config keys with backward-compatible defaults, new
optional template variables, `score_status_label()` retained alongside
the new `risk_label()`) — no existing function signature, route path,
or database column from Modules 1-4 was removed or altered.

## Updated Architecture Diagram (Module 6)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                  Browser                                   │
│  Landing page (anon) | Candidate app shell | Invigilator console shell     │
│  Assessment session UI -> pause overlay reacts to invigilator actions      │
│  csrf.js patches window.fetch -> every JS POST carries X-CSRFToken         │
└───────────────────────────────────┬──────────────────────────────────────┘
                                     │ HTTP + fetch()
┌───────────────────────────────────▼──────────────────────────────────────┐
│                              Flask (app.py)                                 │
│  Blueprints: auth_bp | dashboard_bp | camera_bp | monitoring_bp |          │
│  preassessment_bp | assessment_bp | invigilator_bp (NEW) | public_bp (NEW)│
│  CSRFProtect(app) wraps every state-changing route automatically           │
│                                                                              │
│  routes/public.py ──────────► role-aware root redirect + landing page      │
│  routes/invigilator.py ─────► utils/rbac.py (role_required decorator)      │
│                          ├──► services/assessment_service.py               │
│                          │      (pause_session/resume_session/             │
│                          │       terminate_session/get_active_sessions)    │
│                          └──► services/event_logger.py                     │
│  routes/assessment.py ──────► services/assessment_service.py               │
│                          │      (shuffled_options — deterministic          │
│                          │       per-candidate option order)               │
│                          └──► checks session.status == "paused" on         │
│                                 every state poll — invigilator actions     │
│                                 are authoritative, never trusted from       │
│                                 the client                                  │
└───────────────────────────────────┬──────────────────────────────────────┘
                                     │ SQLAlchemy
                           ┌──────────▼──────────┐
                           │   SQLite (instance)   │
                           │  + users.role (NEW)    │
                           │  + questions.category/  │
                           │    difficulty (NEW)      │
                           │  + assessment_sessions.  │
                           │    paused_at/invigilator_│
                           │    note/current_question_│
                           │    index (NEW)            │
                           └───────────────────────────┘
```

## Features Implemented (Module 6)

### Part 1 (continued) — Assessment Engine Polish
- **Save** button (explicit save separate from auto-save-on-select) and
  **Clear Response** (genuinely clears a saved answer — required fixing
  a latent bug in the original `save_answer()`, where `None` was
  overloaded to mean both "field not provided" and "clear it", making
  the two indistinguishable; now a dedicated `clear=True` flag)
- Question metadata (marks, difficulty) shown in the question header
- A real progress bar (answered / total) above the palette

### Part 2/3 — Continuous Monitoring + Richer Proctoring Panel
- The right-sidebar panel now shows **AI Engine Status**, **Camera
  FPS** (honestly computed from actual poll cadence, not a fabricated
  number), **Connection Status**, and a running **Violation Counter**
  — all real, derived values, not static placeholders
- MediaPipe-based detection (mask/sunglasses/head-pose/gaze/phone/book)
  remains explicitly **deferred** — see Future Scope

### Part 4 — Invigilator Console
- New `role` column on `User` (candidate/invigilator/admin) with a
  `utils/rbac.py` decorator (`@role_required(...)`) protecting every
  invigilator route — **verified**: a candidate account gets HTTP 403
  on every `/invigilator/*` route
- **Live Candidates dashboard**: every in-progress/paused session,
  with candidate name/email, assessment, real question progress
  (`current_question_index`, tracked via a lightweight fire-and-forget
  endpoint the session page calls on every navigation), server-computed
  time remaining, live integrity score, risk level, and status —
  searchable by name/email, filterable by risk level
- **Session detail view**: full violation timeline scoped to that
  attempt's time window, a violation-type breakdown, and CSV/JSON
  export (Part 13)
- **Pause / Resume / Terminate**, fully functional both directions —
  **verified end-to-end**: invigilator pauses → candidate immediately
  sees a blocking "Assessment Paused" overlay and cannot submit
  answers (400 if attempted) → invigilator resumes → candidate's timer
  is credited back the exact paused duration → invigilator terminates →
  candidate is scored on whatever was answered and shown a real result
- **Honest architecture note** (stated in `routes/invigilator.py`'s
  docstring, not glossed over): this app's `camera_service.py` (Module
  2) assumes one shared physical webcam for the whole Flask process —
  there is no real per-candidate live video feed for an invigilator to
  watch multiple remote candidates simultaneously. True live video
  would need capture moved to each candidate's browser (WebRTC) with a
  server-side relay — a bigger architectural change than fits this
  pass. What the console shows instead is 100% real and multi-candidate-
  safe: every status, score, and violation is a database row, refreshed
  live — it's just not embedded video.

### Part 6 — Enterprise Landing Page
- Hero, live-computed statistics (real DB counts, not made-up
  numbers), features grid, architecture diagram, demo workflow,
  testimonials (explicitly labeled as representative/dummy per the
  spec), FAQ accordion, footer — `templates/landing.html` +
  `static/css/landing.css`
- Root route (`routes/public.py`) is now role-aware: anonymous visitors
  see the landing page; candidates redirect to their dashboard;
  invigilators redirect to their console. **Bug caught and fixed
  during testing**: the post-*login* redirect (as opposed to the root
  route) was still unconditionally sending everyone to the candidate
  dashboard — an invigilator logging in landed on `/dashboard` instead
  of `/invigilator/`. Fixed with a shared `_post_login_redirect()`
  helper in `routes/auth.py`, verified via both the Flask test client
  and a real Playwright browser session.

### Part 7 — Professional Candidate Dashboard
- New "Performance Overview" section: completed-assessment count,
  average score, average integrity score, violation count — all
  computed from real `AssessmentResult`/`AssessmentSession` rows via
  `assessment_service.get_candidate_stats()`, not placeholders
- A simple score-trend bar chart (last up to 8 attempts) and an
  Assessment History table
- Quick Actions panel (Browse Assessments, Update Verification Photo,
  View Report, View Analytics; Certificates explicitly marked "coming
  soon" per the spec's "future" note rather than faked)

### Part 9 (partial) — Question Metadata & Shuffling
- `Question.category` and `Question.difficulty` columns
- **Per-candidate, per-question option shuffling**, seeded from
  `(session.id, question.id)` — **verified deterministic**: calling it
  twice for the same session/question returns the identical order
  (so revisiting a question via Previous/palette never silently
  reorders the options), while different questions/sessions shuffle
  independently

### Part 13 — Report Export
- CSV and JSON export of a candidate's session timeline, from the
  invigilator console (`/invigilator/session/<id>/export.csv|json`) —
  **verified**: correct content-type, correct data, and correctly
  blocked (403) for non-invigilators. PDF export remains deferred (see
  Future Scope).

### Part 14 — Extended Seeding
- `seed_database.py` now also creates one invigilator account
  (`invigilator@proctoriq.test` / `password123`), tags sample questions
  with real categories/difficulties, and creates a handful of sample
  `AssessmentSession` rows (mixing in-progress and completed, with
  attached monitoring events) so the Invigilator Console and Analytics
  pages have real data to demo immediately after seeding — no need to
  manually drive a browser through an assessment first.

### Part 16 — Security
- **Genuine CSRF protection** via Flask-WTF's `CSRFProtect`, covering
  every POST/PUT/PATCH/DELETE route. Traditional `<form>` submissions
  carry the token via a hidden input (added to all 14 POST forms
  across the app); JS `fetch()` calls carry it via an `X-CSRFToken`
  header, injected by `static/js/csrf.js`, which wraps `window.fetch`
  **once** globally rather than requiring every individual fetch()
  call site across `session.html`, `monitoring.html`,
  `capture_photo.html`, etc. to be hand-edited.
  **Verified both directions**: a POST without a token now gets HTTP
  400; a POST carrying a valid token succeeds — tested via the Flask
  test client AND confirmed via a real Playwright browser session
  submitting the registration form with no network failures.
  *(Testing note: this app's own regression test scripts set
  `app.config['WTF_CSRF_ENABLED'] = False` after `create_app()` to
  avoid extracting/passing a token on every one of the dozens of test
  requests — confirmed this override works correctly. Real deployments
  should never set this.)*
- Session cookie hardening in `config.py`: `HTTPONLY=True`,
  `SAMESITE=Lax` always on; `SECURE` is environment-configurable
  (`SESSION_COOKIE_SECURE=true` for any real HTTPS deployment).
- Password policy, input validation, and XSS protection (Jinja's
  autoescaping, on by default and never disabled anywhere in this
  codebase) were already in place from earlier modules and remain
  unchanged — no regressions introduced.

### Part 18 — Code Quality
- `app.py`'s auto-migration was refactored from one-off, per-column
  `if` blocks into a single declarative `(table, column, ADD COLUMN)`
  list — adding the next module's new column is now a one-line list
  entry instead of copy-pasted migration code (DRY, per this Part).
- `utils/rbac.py`'s `role_required()` decorator is reusable by any
  future admin routes, not just the invigilator blueprint.

## Database Schema (Module 6 additions)

**Modified tables** (new columns; all covered by the auto-migration in
`app.py`, tested against a simulated pre-Module-6 database):

| Table | New column(s) |
|---|---|
| `users` | `role VARCHAR(20) DEFAULT 'candidate'` |
| `questions` | `category VARCHAR(80)`, `difficulty VARCHAR(20) DEFAULT 'Medium'` |
| `assessment_sessions` | `paused_at DATETIME`, `invigilator_note VARCHAR(255)`, `current_question_index INTEGER DEFAULT 0` |

**No new tables.** Module 6's spec (Part 10) asks for `AssessmentAttempt`,
`Violation`, and `MonitoringEvent` — these map onto existing tables
rather than duplicating them (documented in `models/assessment.py`'s
docstring):

| Spec name | Actually implemented as |
|---|---|
| `AssessmentAttempt` | `AssessmentSession` (Module 5) |
| `MonitoringEvent` | `ExamEvent` (Module 4) — every observed event |
| `Violation` | `ExamEvent` rows where `severity` is `warning`/`critical` |

Creating separate near-duplicate tables for these would fragment the
audit trail across two places that would need to stay in sync, which
runs directly against Part 18's "no duplicate code" requirement.

**New status values** on `AssessmentSession.status`: `paused` and
`terminated`, alongside the existing `in_progress` / `submitted` /
`auto_submitted`.

## API Endpoints (Module 6 additions)

**Public** (`routes/public.py`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Landing page (anonymous) or role-aware redirect (authenticated) |

**Invigilator** (`routes/invigilator.py`, prefix `/invigilator`, all `@role_required("invigilator", "admin")`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/invigilator/` | Live Candidates dashboard (search/filter) |
| GET | `/invigilator/live-data` | JSON feed of active sessions |
| GET | `/invigilator/session/<id>` | Session detail + violation timeline |
| POST | `/invigilator/session/<id>/pause` | Pause a session |
| POST | `/invigilator/session/<id>/resume` | Resume a paused session |
| POST | `/invigilator/session/<id>/terminate` | Terminate + score as-is |
| GET | `/invigilator/session/<id>/export.csv` | CSV timeline export |
| GET | `/invigilator/session/<id>/export.json` | JSON timeline export |

**Assessment engine additions** (`routes/assessment.py`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/assessment/session/<id>/progress` | Report current question index (invigilator visibility) |

All invigilator routes return 403 for a `role="candidate"` account,
and every candidate-scoped route continues to 403 on cross-candidate
access (unchanged from Module 5, re-verified this round).

## Testing Checklist (Module 6)

- [x] RBAC: candidate gets 403 on `/invigilator/*`; invigilator login
      redirects to `/invigilator/` (both the root route AND the login
      redirect — the login-redirect gap was a real bug, found and fixed)
- [x] Invigilator dashboard lists live sessions with accurate progress/
      time/score/risk; search and risk-filter both verified
- [x] Full pause → candidate blocked → resume → candidate unblocked →
      terminate → candidate scored, cycle verified end-to-end from both
      the candidate's and invigilator's perspective
- [x] Timer credit-back on resume verified (paused duration added to `ends_at`)
- [x] CSV and JSON export verified for content-type, content, and 403
      access control
- [x] Option shuffling verified deterministic (same session+question
      -> same order across repeated calls) and independent across
      different questions
- [x] Clear Response verified to actually null out `selected_option_id`
      in the database (not just visually clear the radio button)
- [x] CSRF: unprotected POST -> 400; token-carrying POST -> success;
      verified via both the test client and a real browser
- [x] Candidate dashboard performance stats verified against real
      `AssessmentResult` data
- [x] Landing page verified to render with zero failed network
      requests and zero JS console/page errors (aside from the expected
      503s from the camera being unavailable in this sandbox)
- [x] Full pre-assessment -> session -> answer/save/next/mark-review/
      clear -> submit flow walked through with a **real Playwright
      browser** (not just the Python test client), and the resulting
      database state (`current_question_index`, `selected_option_id`,
      `marked_for_review`) verified to exactly match the clicks performed
- [x] Full Module 1-5 regression re-run and passing
- [ ] Full visual/pixel QA — screenshots captured (landing, dashboard,
      invigilator console, assessment session) and confirmed to be
      valid, correctly-sized, non-trivial PNGs, but didn't render for
      visual review in this session for a second time. Functional
      correctness is thoroughly verified via the browser-driven DB-state
      checks above; a manual visual look is still worth doing.

## Git Commit Message (Module 6)

```
feat(module-6): invigilator console, RBAC, landing page, CSRF protection

- Add role-based access control: User.role (candidate/invigilator/admin),
  utils/rbac.py's @role_required decorator, role-aware root route AND
  post-login redirect (fixed a gap where login always sent invigilators
  to the candidate dashboard)
- Add Invigilator Console (routes/invigilator.py + templates/invigilator/):
  live candidate roster with search/filter, session detail with violation
  timeline, pause/resume/terminate controls fully wired to the candidate-
  side session state machine, CSV/JSON export
- Add AssessmentSession.status values "paused"/"terminated", paused_at
  (for timer credit-back on resume), invigilator_note, and
  current_question_index (for live invigilator progress visibility)
- Add enterprise landing page (routes/public.py, templates/landing.html,
  static/css/landing.css) with real DB-backed statistics
- Add candidate dashboard Performance Overview: real average score/
  integrity, violation count, trend, assessment history
  (services/assessment_service.get_candidate_stats)
- Add deterministic per-candidate option shuffling (assessment_service.
  shuffled_options), Save/Clear Response controls (fixed a latent bug
  where save_answer() couldn't distinguish "no change" from "clear")
- Add genuine CSRF protection (Flask-WTF): hidden token fields on all
  14 POST forms, global fetch() patching via static/js/csrf.js so
  existing JS call sites needed zero edits; verified both rejection
  and acceptance paths via test client and real browser
- Add session cookie hardening (HttpOnly/SameSite always on, Secure
  configurable) in config.py
- Refactor app.py's schema auto-migration into a single declarative
  column list instead of repeated per-column blocks
- Extend seed_database.py: invigilator account, question categories/
  difficulties, sample in-progress and completed sessions with events
- Verified: full Module 1-5 regression passes; RBAC, pause/resume/
  terminate, shuffling, and CSRF all independently verified correct
- Deferred (see README Future Scope): MediaPipe advanced proctoring,
  full admin CRUD panel, ML analytics, LangChain reports, PDF export
```

## Deployment Instructions (Module 6 additions)

Everything from Module 5's Deployment Instructions still applies. New
for Module 6:

1. **Provision invigilator accounts deliberately.** There is no
   self-service invigilator signup (by design — `role` always defaults
   to `"candidate"` on registration). Run `seed_database.py` for a demo
   account, or set a user's `role` column to `"invigilator"` directly
   in the database for a real deployment, until Part 8's admin panel
   exists to manage this from the UI.
2. **Set `SESSION_COOKIE_SECURE=true`** in any deployment served over
   HTTPS (which, per Module 5's deployment notes, should be all of
   them) — it defaults to `false` so local HTTP development keeps working.
3. **CSRF is on by default and should stay on.** The only place
   `WTF_CSRF_ENABLED=False` belongs is inside test code, never in a
   running deployment's config.
4. **Single-process constraint still applies** (see Module 5's
   Deployment note about `Camera` being a process-wide singleton) —
   this also means the Invigilator Console's "live" data is accurate
   only within that single process/instance; a multi-worker deployment
   would need the monitoring state moved to shared storage (e.g. Redis)
   for the invigilator view to see all candidates' status correctly.

## Future Scope (updated)

Carried over from Module 5, still deferred:
- **Part 2/12 — MediaPipe-based advanced proctoring** (head pose, eye
  gaze, mask/sunglasses/face-covering detection, phone/book/additional-
  person detection). `PENALTY_WEIGHTS` already has `phone_detected` and
  `face_covered` entries ready to receive these events.
- **Part 8 — Full admin CRUD panel** (candidate/assessment/question
  management, bulk import, system configuration UI). The Invigilator
  Console built this round covers live monitoring/control, which is a
  meaningful slice of Part 8, but question-bank editing, candidate
  management, and assessment authoring still need a proper admin UI.
- **Part 11 — ML-based analytics** (Pandas/scikit-learn violation
  trends, behavior clustering, risk prediction). Now genuinely closer
  to feasible — Module 6's seed script produces enough sample session/
  violation data to build and sanity-check against.
- **Part 12 — LangChain AI report generation.**
- **Part 13 (remaining) — PDF export.** CSV/JSON are done; PDF needs a
  rendering library (e.g. WeasyPrint) and a report template.
- **Part 17 — Full accessibility audit.** This round added targeted
  ARIA roles/labels to the assessment session page's option list and
  palette buttons (keyboard-navigable, `role="radiogroup"`), but a
  systematic audit (contrast ratios, full keyboard-nav coverage across
  every page, screen-reader testing) hasn't been done.
- **Part 5 (remaining) — Dark mode, glassmorphism, skeleton loaders,
  micro-animations.** This round added real hover/lift effects on the
  landing page's feature cards and a CSS-transition progress bar, but
  the fuller visual-polish backlog remains open.

## Backward Compatibility (Module 6)

Confirmed via automated regression testing: every Module 1-5 route,
service, and template continues to work unmodified in behavior. Every
change to a pre-existing file was additive — new config keys with
backward-compatible defaults, new optional template variables/blocks,
new columns with safe defaults picked up by the existing auto-migration
pattern. The one intentional *behavior* change (root route showing a
landing page instead of redirecting straight to `/login`) is purely
additive: every path to logging in still works exactly as before, one
click away from the new landing page.

## Features Implemented (Module 7 — Complete Assessment Engine)

Module 7 focused exclusively on completing the candidate examination
workflow, per its explicit scope: no admin dashboard, no AI analytics,
no LangChain, no MediaPipe, no Faker-generated question content, no
new monitoring models — everything below reuses Modules 1-6's existing
services (`camera_service.py`, `monitoring_service.py`,
`browser_monitor.py`, `face_detection_service.py`, `integrity_service.py`,
`event_logger.py`) exactly as they were.

### Parts 1/2 — Real Demo Content
- **Three named, professional assessments**, seeded exactly as
  specified: *Python Programming Basics* (30 min, 10 Q, 20 total
  marks, 12 marks to pass), *Artificial Intelligence Fundamentals*
  (20 min, 8 Q), *Aptitude Assessment* (15 min, 10 Q) — all with
  monitoring enabled, all shown as cards on `/assessment/` with title,
  description, duration, question count, total marks, passing marks,
  monitoring badge, and a Start button.
- **58 real, curated questions** (not Faker/placeholder text) across
  all 8 required categories — Python, Artificial Intelligence, Data
  Structures, DBMS, Operating Systems, Computer Networks, Aptitude,
  OOP — each verified to have exactly 4 options and exactly 1 correct
  answer. The 3 public assessments use 28 of these; the remaining 30
  (Data Structures, DBMS, OS, Networks, OOP) are seeded as **inactive
  "question bank" container assessments** — a deliberate, documented
  design choice (see `seed_database.py`'s module docstring) rather
  than a schema change, since `Question.assessment_id` is a required
  foreign key and building a true many-to-many question bank was out
  of this module's explicit scope.

### Part 3 — Assessment Details Page
- Enhanced (`preassessment/overview.html`, still reachable at the same
  `overview`/`overview_continue` routes for backward compatibility)
  to show every requested field: name, description, duration, question
  count, **total marks**, **passing marks** (absolute-marks value when
  set, else percentage), negative marking, **Camera Required**,
  **Browser Monitoring Enabled**, and a free-text **Assessment
  Instructions** block (new `Assessment.instructions` column).
- New `Assessment.passing_marks` column (nullable Float): when set,
  scoring uses it directly ("12 marks to pass"); when unset, scoring
  falls back to the existing `passing_score_percent` — verified
  **exactly at the boundary** (a score of 12/20 passes, 11/20 fails
  for Python Programming Basics; a percentage-based assessment was
  independently verified the same way).

### Parts 4-6 — Readiness, Terms, Declaration
Unchanged in behavior from Module 5/6 (readiness checks, terms/privacy/
integrity-policy pages, the 8-checkbox declaration) — re-verified
working this round, not rebuilt.

### Parts 7/8/11 — Live Assessment Screen & Question Navigation
- **Five-state question palette**, replacing Module 6's four-state
  version: Not Visited, Visited, Answered, Marked for Review, and
  Answered+Marked (a distinct split-color state) — verified via direct
  DOM inspection in a real browser that the palette classes exactly
  matched a scripted sequence of clicks (answer Q1, navigate to Q2,
  mark Q2 for review, leave Q3-10 untouched).
- **Clear Response** now genuinely clears a saved answer (this
  required fixing a latent bug from Module 5: `save_answer()`
  previously overloaded `None` to mean both "field not sent" and
  "clear it", making the two indistinguishable — now a dedicated
  `clear=True` flag).
- **Save Answer** as an explicit, separate action from auto-save-on-select.
- The right-sidebar monitoring panel (live camera, AI Engine Status,
  Camera FPS, Connection Status, Integrity gauge, violation counter,
  recent-event text, question palette) is now **`position: sticky`**,
  staying in view while scrolling a long question list — verified via
  computed-style inspection in a real browser (`position: sticky`).

### Part 9 — Timer
Unchanged: server-authoritative countdown, 5-minute warning styling,
automatic submission at zero — re-verified this round.

### Part 10 — Live AI Proctoring, Warning Popups
- Every violation (face-status change or browser event) now shows a
  **toast popup** (`static/css/style.css`'s `.eg-toast`), in addition
  to updating the integrity score, the header Warning counter, and the
  sidebar's Recent Event text — verified a toast renders in the DOM
  with real violation text after a simulated event.
- All detection continues to run through the exact same Module 4
  endpoints (`/monitoring/start`, `/monitoring/status`,
  `/monitoring/browser-event`) and `static/js/browser-monitor.js` —
  nothing was rewritten.

### Part 12 — Submission Confirmation
Replaced the plain `confirm()` dialog with a proper Bootstrap modal
showing live counts — Answered, Not Answered, Marked for Review, Not
Visited, current Integrity Score, and Violations — populated from the
same client-side state the palette uses. Verified via DOM inspection
that the modal's numbers exactly matched the actual answer state (1
answered, 9 not answered, 1 marked, 8 not visited, matching the test
sequence above).

### Part 13 — Result Page
Added the two previously-missing fields: **Time Taken** (computed via
a new `assessment_service.time_taken_seconds()`) and **Violations**
(session-scoped count via a new `event_logger.get_violations_in_window()`
helper — also used to refactor the invigilator session-review page,
which had the same time-window filtering logic duplicated inline three
times; now calls the shared helper instead). The candidate's name is
now shown on the result card as well.

### Part 14 — Database
No new tables were needed — `AssessmentSession` already serves as
`AssessmentAttempt`, `CandidateAnswer`, and `AssessmentResult` already
matched exactly. Two new **columns** on the existing `Assessment`
table (`passing_marks`, `instructions`), covered by the existing
auto-migration pattern in `app.py`.

## Database Schema (Module 7 additions)

| Table | New column | Purpose |
|---|---|---|
| `assessments` | `passing_marks FLOAT` (nullable) | Absolute-marks passing threshold, preferred over `passing_score_percent` when set |
| `assessments` | `instructions TEXT` (nullable) | Free-text instructions shown on the Assessment Details page |

No other schema changes. Covered by the existing declarative
auto-migration list in `app.py` — tested against a pre-Module-7
database to confirm both columns get added cleanly with existing rows
defaulting to `NULL` (falls back to percentage-based scoring, exactly
matching pre-Module-7 behavior).

## Testing Checklist (Module 7)

- [x] Assessments page shows exactly the 3 named, active assessments
      as cards with all required fields; the 5 inactive question-bank
      containers never appear
- [x] All 58 seeded questions verified to have exactly 4 options and
      exactly 1 correct answer each (automated integrity check)
- [x] Assessment Details page shows Camera Required, Browser
      Monitoring Enabled, Passing Marks, Total Marks, and Instructions
- [x] Passing-marks scoring verified at the exact boundary (12/20 →
      pass, 11/20 → fail) for Python Programming Basics
- [x] Percentage-based fallback scoring independently verified at its
      own boundary for AI Fundamentals (no `passing_marks` set)
- [x] Five-state palette verified via real-browser DOM inspection
      against a scripted click sequence — classes matched exactly
- [x] Clear Response verified to null out `selected_option_id` in the
      database, not just visually clear the radio button
- [x] Submission modal's live counts verified via DOM inspection to
      exactly match the actual answer/review/visited state
- [x] Toast popup verified to render in the DOM with real violation
      content after a triggered event
- [x] Sticky monitoring panel verified via computed-style inspection
      (`position: sticky` actually applied, not just written in CSS)
- [x] Result page verified to show candidate name, time taken, and a
      session-scoped violations count
- [x] Full Module 1-6 regression re-run and passing: auth, face
      capture/validation, live monitoring, integrity deductions, RBAC,
      pause/resume/terminate, and full route protection after logout
- [x] Zero real JS console/page errors across the full pre-assessment
      → session → submit flow in a real Playwright browser (only the
      expected 503s from the camera being unavailable in this sandbox)

## Git Commit Message (Module 7)

```
feat(module-7): complete the online assessment engine end-to-end

- Seed 3 named, spec-exact candidate-facing assessments (Python
  Programming Basics, AI Fundamentals, Aptitude Assessment) and a
  58-question bank across all 8 required categories, seeded as
  inactive container assessments to avoid a question-bank schema
  change (documented in seed_database.py)
- Add Assessment.passing_marks (absolute-marks threshold, preferred
  over passing_score_percent when set) and Assessment.instructions;
  update assessment_service.submit_session() scoring accordingly,
  verified at the exact pass/fail boundary for both scoring modes
- Enhance the Assessment Details page with Camera Required, Browser
  Monitoring Enabled, Total/Passing Marks, and free-text Instructions
- Rebuild the assessments list as proper cards per the spec's exact
  field list (title, description, duration, questions, total marks,
  passing marks, monitoring badge, Start button)
- Upgrade the question palette to 5 states (Not Visited / Visited /
  Answered / Marked / Answered+Marked), verified via real-browser DOM
  inspection against a scripted interaction sequence
- Fix a latent bug in save_answer() where "no change" and "clear the
  answer" were indistinguishable; add an explicit Clear Response flag
- Replace the plain confirm() submission dialog with a Bootstrap modal
  showing live Answered/Not Answered/Marked/Not Visited/Integrity/
  Violations counts
- Add toast warning popups on every monitoring violation during a live
  assessment, alongside the existing score/counter updates
- Make the right-sidebar monitoring panel position:sticky
- Add Time Taken and a session-scoped Violations count to the Result
  page; add candidate name to the result card
- Add event_logger.get_violations_in_window()/get_events_in_window(),
  removing duplicated inline time-window filtering from the
  invigilator session-review route (used in 3 places previously)
- Add a num display filter (12.0 -> "12") applied everywhere marks
  values are shown to a candidate
- Reused, unmodified: camera_service.py, monitoring_service.py,
  browser_monitor.py, face_detection_service.py, integrity_service.py,
  event_logger.py's core API, all of Modules 1-6's auth/dashboard/RBAC
- Verified: full Module 1-6 regression passes; no new monitoring
  models, no admin dashboard changes, no AI/ML dependencies added
```

## Setup & Run

1. **Create and activate a virtual environment** (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**

   ```bash
   python app.py
   ```

   The database (`instance/examguard.db`) and all tables are created
   automatically on first run — no manual migration step needed for
   Module 1.

4. **Open in your browser:**

   ```
   http://127.0.0.1:5000
   ```

   You'll be redirected to the login page. Click **Register here** to
   create your first candidate account.

## Environment Variables (optional)

| Variable       | Purpose                                  | Default                          |
|----------------|-------------------------------------------|-----------------------------------|
| `SECRET_KEY`   | Flask session-signing key                 | `dev-secret-key-change-in-production` |
| `DATABASE_URL` | SQLAlchemy database URI                   | `sqlite:///instance/examguard.db` |
| `CAMERA_DEVICE_INDEX` | OpenCV `cv2.VideoCapture` device index (useful if a machine has more than one webcam) | `0` |
| `DISPLAY_TIMEZONE` | Timezone used to display timestamps (e.g. registration date) to candidates. Data is always stored in UTC — this only affects what's shown on screen. | `Asia/Kolkata` |

**Set a real `SECRET_KEY` before deploying anywhere beyond your own machine.**

## Features Implemented (Module 1)

- ✅ Registration (full name, email, password, confirm password)
- ✅ Server-side validation (empty fields, email format, password length, password match, duplicate email)
- ✅ Password hashing via Werkzeug (never stored in plain text)
- ✅ Login with hashed-password verification
- ✅ Authenticated session management via Flask-Login
- ✅ Logout (secure session destruction)
- ✅ Protected dashboard route (redirects unauthenticated users to login)
- ✅ Flash messages for all success/error states
- ✅ Clean, responsive Bootstrap 5 UI (blue/white/minimal theme)

## Features Implemented (Module 2)

- ✅ Live webcam preview on the capture page via an OpenCV-powered MJPEG stream
- ✅ Capture the current frame with a single click
- ✅ Review the captured photo before committing — **Retake** discards it and
  returns to the live feed; **Save** commits it
- ✅ Saved photo is written to `static/uploads/user_<id>.jpg` and the path
  stored in `User.photo_path`
- ✅ Profile photo displayed on the dashboard (falls back to a
  first-initial avatar if no photo has been saved yet)
- ✅ Graceful camera-failure handling: if the webcam can't be opened
  (disconnected, in use elsewhere, permission denied), the page shows a
  friendly error instead of crashing, and candidates can **Skip for now**
  and add a photo later from the dashboard
- ✅ Redirect straight from registration into the photo capture flow
  (the candidate is logged in automatically so the protected capture
  page is reachable without a second login)

### How the capture workflow works

1. `GET /capture-photo` renders the page. Its `<img>` preview points at
   `GET /video_feed`, which streams MJPEG frames read live from OpenCV's
   `cv2.VideoCapture`.
2. Clicking **Capture** calls `POST /capture`, which grabs the *current*
   frame and writes it to `static/uploads/tmp/user_<id>_temp.jpg` —
   nothing is saved to the database yet.
3. The page swaps the live `<img>` for a still preview served by
   `GET /temp-photo`, and shows **Retake** / **Save** buttons.
4. **Retake** (`POST /retake`) deletes the temp file and switches back
   to the live feed.
5. **Save** (`POST /save-photo`) moves the temp file to its final,
   stable name (`static/uploads/user_<id>.jpg`) and only then updates
   `User.photo_path` in SQLite, before redirecting to the dashboard.

This "capture → temp file → explicit save" design means a candidate can
retake as many times as they like without ever touching the database
until they're happy with the shot, and a half-finished capture never
leaves the DB in an inconsistent state.

### Why `opencv-python-headless`?

The app runs `cv2.VideoCapture` on the server. `opencv-python-headless`
provides the same video I/O without pulling in GUI/display libraries
that a server doesn't need (and often doesn't have installed). If you
run this on a machine where the Flask process itself doesn't have
access to a physical webcam (e.g. a remote server, a container, or a
cloud VM), `/video_feed` and `/capture` will fail with the graceful
"unable to access the webcam" error described above — this is expected
in that setup, since the server can only see cameras attached to the
machine it's running on. For a real deployment where candidates connect
from their own machines, a future iteration would move image capture
to the browser (`getUserMedia` + a POST endpoint that accepts the
uploaded frame) while still reusing `services/camera_service.py`'s
save/retake/finalize logic.

## Extending for Future Modules

Module 4 was deliberately built so the next wave of proctoring
features — head pose estimation, eye gaze tracking, phone/object
detection, fuller AI-based proctoring, LLM-generated integrity reports
— can be added without touching existing code:

1. **Detection logic** goes in its own `services/<feature>_service.py`
   (e.g. `services/head_pose_service.py`), following the pattern of
   `face_detection_service.py`: pure functions operating on numpy
   frames, no Flask/DB imports. Reuse `services/camera_service.py`'s
   `Camera.get_instance()` / `read_current_frame()` for the frame
   itself — never open a second `cv2.VideoCapture`.
2. **Wire it into monitoring** by importing your new service from
   `routes/monitoring.py` (or a sibling blueprint) alongside the
   existing `monitoring_service.check_face_status()` call — both can
   run against the same captured frame.
3. **Log and score it** the same way every other Module 4 event does:
   call `services/event_logger.log_event(...)` with a new `event_type`
   slug, and — only if it should affect the score — add that slug and
   a point value to `services/integrity_service.DEDUCTIONS`. No schema
   change is needed; `ExamEvent.event_type` is a free-form string.
4. **Browser-side signals** (e.g. a future "screen share detected")
   follow the same path as existing ones: add the slug + severity to
   `services/browser_monitor.ALLOWED_BROWSER_EVENTS`, detect it in
   `static/js/browser-monitor.js`, and POST it to the existing
   `/monitoring/browser-event` endpoint — no new route required.
5. **An LLM-generated integrity report** (Part 11) can be built as a
   new route that calls `event_logger.get_all_events(user_id)` and
   `integrity_service.get_score(user)` and hands that structured data
   to an LLM prompt — both functions already return plain
   dicts/ORM objects, not HTML, so no scraping or reformatting needed.
6. Register any new blueprint in `app.py` exactly like
   `monitoring_bp`; no changes to `routes/auth.py`,
   `services/auth_service.py`, or the `User`/`ExamEvent` models are
   required for any of the above.

## Notes on Security

- Passwords are hashed with Werkzeug's `generate_password_hash` (PBKDF2 by
  default) — plaintext passwords are never persisted.
- Sessions are managed by Flask-Login using signed, HttpOnly cookies.
- All form inputs are validated server-side (client-side `required`
  attributes are a UX convenience only, not a security control).
- Duplicate-email registration is checked both at the application level
  and enforced at the database level (`unique=True`), with an
  `IntegrityError` safety net for race conditions.

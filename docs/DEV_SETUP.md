LevelUp DSA — Developer Setup & Workflow Guide
A step-by-step manual for getting this project running on a new machine, and the
conventions used throughout development. Written so another developer (or future-you
on a new laptop) can go from a fresh clone to a running app without guessing.
---
1. Prerequisites
Python 3.11 or 3.12 (either works fine for this project)
PostgreSQL 18 (or close to it — earlier v16/17 should also work)
Git Bash on Windows — required. PowerShell has caused real problems in this
project (commands like `source` don't exist there) — always use Git Bash for every
command in this guide.
VS Code (recommended, not required)
---
2. Clone the repo
```bash
git clone https://github.com/Joelmaxten/LevelUp-DSA.git
cd LevelUp-DSA
```
3. Check out the working branch
`main` only holds stable, deploy-ready snapshots. Active development happens on
`feature/scaffold` (see Git Workflow below).
```bash
git checkout feature/scaffold
```
4. Create and activate a virtual environment
```bash
python -m venv venv
source venv/Scripts/activate
```
Confirm it's active:
```bash
python --version
```
(the `which python` command can display an odd-looking nested path on some machines —
this is a harmless display quirk; trust `python --version` working correctly instead.)
5. Install dependencies
```bash
pip install -r requirements.txt
```
This recreates the exact same package versions used in development — no need to
`pip install` packages individually.
6. Install & set up PostgreSQL
Download from https://www.postgresql.org/download/windows/ — get PostgreSQL 18,
Windows x86-64 installer.
Run the installer. Defaults are fine for install location, port (5432), and
components. Remember the superuser password you set — you'll need it below.
Skip Stack Builder at the end.
The installer does not add `psql` to your PATH automatically. Fix this once,
permanently:
```bash
echo 'export PATH="$PATH:/c/Program Files/PostgreSQL/18/bin"' >> ~/.bashrc
source ~/.bashrc
psql --version
```
Create the project database:
```bash
psql -U postgres
```
```sql
CREATE DATABASE levelup_dsa_dev;
\q
```
7. Set up environment variables
`.env` is gitignored (it holds real secrets) — it never comes through a clone, and
must be created fresh on every machine.
```bash
cp .env.example .env
```
Open `.env` and fill in your real PostgreSQL password:
```
DATABASE_URL=postgresql://postgres:YOUR_ACTUAL_PASSWORD@localhost:5432/levelup_dsa_dev
```
Every variable `app/config.py` reads is listed in `.env.example`. Only the first
three are needed to boot; the rest unlock features:

| Variable | Needed for | Default |
|---|---|---|
| `FLASK_ENV` | `development` or `production` (production enforces the checks below) | `development` |
| `SECRET_KEY` | signs the session cookie; in production it must be a real random value of 16+ characters or the app refuses to start | dev placeholder |
| `DATABASE_URL` | PostgreSQL connection | local `levelup_dsa_dev` |
| `GEMINI_API_KEY` | roadmap generation, resume feedback, problem framing | empty |
| `YOUTUBE_API_KEY` | fallback video search for roadmap steps | empty |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | live job listings on the resume page; without them the listings box shows "unavailable" | empty |
| `PISTON_API_URL` | code execution (not yet used) | `http://localhost:2000/api/v2/execute` |
| `FAISS_INDEX_PATH` | knowledge-base index location | `data/processed/faiss_index` |
| `UPLOAD_FOLDER` | where resume PDFs are saved | `uploads/resumes` |
| `SESSION_COOKIE_SECURE` | `true`/`false`; Secure flag on the session cookie. Off in development, on in production unless overridden | by mode |
| `ROADMAP_DAILY_LIMIT` | roadmaps one user may generate per rolling 24h | `5` |
| `RESUME_UPLOAD_LIMIT_PER_HOUR` | resume uploads per user per hour (in-process counter) | `10` |
| `RESUME_LISTINGS_LIMIT_PER_HOUR` | `/resume/listings` calls per user per hour (in-process counter) | `30` |

`KAGGLE_USERNAME`/`KAGGLE_KEY` (dataset downloads) and any `AWS_*` entries in a
developer's own `.env` are not read by `config.py`.

Each line of `.env` must be exactly `NAME=value` with no spaces around or inside
the value. python-dotenv is lenient, but a value with a space breaks any tool
that parses the file strictly. To list only the names of bad lines without
printing values, run a small script that tests each line against
`^[A-Z_][A-Z0-9_]*=\S*$` and prints just the variable name.

**Never `source .env`** (or `export $(cat .env)`): the file is for python-dotenv
only, a space or special character in a value makes the shell run it as a command,
and sourcing exports secrets into your shell's environment and history.

Leave the `.env.example` file itself untouched — it's a template with placeholder
values, meant to be committed. Only `.env` (with real values) is gitignored.
8. Create the database tables
The database is empty until you run this once — `models.py` defines the tables, but
they only get created when you tell SQLAlchemy to build them.
```bash
python
```
```python
from dotenv import load_dotenv
load_dotenv()
from app import create_app, db
from app import models   # required — this registers the models with SQLAlchemy
app = create_app()
app.app_context().push()
db.create_all()
exit()
```
Verify it worked:
```bash
psql -U postgres -d levelup_dsa_dev
```
```sql
\dt
```
You should see 18 tables: `users`, `career_paths`, `career_profiles`,
`roadmap_steps`, `user_progress`, `generated_roadmaps`, `roadmap_progress`,
`dsa_nodes`, `dsa_problems`, `dsa_problem_framings`, `user_dsa_activity`,
`node_mastery`, `weakness_profiles`, `user_attempts`, `resumes`, `skill_gaps`,
`job_listings`, `survey_respondents`.
Note: there's no migration tool (like Alembic) in place yet — table creation is
manual via `db.create_all()`. If the schema changes later, existing tables won't
auto-update; they'd need to be dropped and recreated, or a migration tool added.
8b. Seed the Skill DNA Map (DSA topics, problems, career paths)
```bash
python scripts/seed_dsa.py
```
Safe to re-run: it updates rows in place and never deletes. It refuses to write anything if `scripts/verify_dsa_seed.py` (which checks every seeded test case against a reference solution) fails. Until it has run, `/dsa` shows a "hasn't been set up" message.
9. Run the app
```bash
python run.py
```
Visit `http://127.0.0.1:5000` in a browser. You should see the LevelUp DSA landing
page.
---
Git Workflow
Branch structure:
`main` — stable, deploy-ready only. Rarely updated directly.
`dev` — integration branch. Finished, working features get merged here.
`feature/*` — active development happens here (currently `feature/scaffold`).
Normal flow: work on a `feature/*` branch → commit as you go → merge into `dev` once
a piece is solid → merge `dev` into `main` only when something is genuinely
deployable.
```bash
git checkout dev
git pull origin dev
git merge feature/scaffold
git push origin dev
git checkout feature/scaffold   # switch back to keep working
```
---
Testing Conventions Used So Far
API routes (JSON endpoints like `/signup`, `/login`, `/quiz/answer`) are tested
with `curl`, not the browser, since they don't respond to GET requests typed into
a URL bar.
Session-based flows (login, quiz progress) are tested with curl's cookie flags:
`-c cookies.txt` to save a session cookie, `-b cookies.txt` to send it back on the
next request — this proves multi-request session state actually persists, not just
that one request works in isolation.
Every database change is verified directly in `psql` (`\dt` to list tables, `\d
<table>` to inspect columns) — never assumed just because Python ran without
  errors.
Page routes (landing page, signup/login forms) are tested in an actual browser.

### Smoke tests (`scripts/smoke_test_*.py`)

Run each from Git Bash at the project root with `PYTHONPATH=.`, using the venv's
Python. They use Flask's test client against the real development database, create
their own `@example.com` users, and (except where noted) delete what they created.
For these tests run `pip install -r requirements-dev.txt` once (adds fpdf2).

| Script | What it covers | Calls an external service? |
|---|---|---|
| `smoke_test_security.py` | CSRF (missing/wrong/valid token, multipart), cookie flags, production `SECRET_KEY` check, daily roadmap cap, resume rate limits | no |
| `smoke_test_paths.py` | shared career-path picker, `/career/options`, path override, multiple roadmaps, dashboard roadmap list | no (Gemini patched) |
| `smoke_test_progress.py` | roadmap tick/untick, progress counts, dashboard bar; `--keep` leaves a demo user whose login it prints | no |
| `smoke_test_adzuna.py` | live listings: cache, failure handling, median-only salary, `/resume/listings` | no (HTTP patched) |
| `smoke_test_profile_flow.py` | quiz then conversation then `CareerProfile` row; prints rather than counts | no |
| `smoke_test_dsa.py` | skill map unlocking and mastery; needs `seed_dsa.py` first | yes: Gemini (problem framing) |
| `smoke_test_resume.py` | upload, extraction, gap analysis, AI feedback | yes: Gemini |
| `smoke_test_roadmap.py` | `/roadmap/generate` end to end | yes: Gemini |
| `smoke_test_youtube.py` | `/roadmap/<id>/resources` | yes: Gemini and YouTube |

```bash
PYTHONPATH=. venv/Scripts/python.exe scripts/smoke_test_security.py
```

Each prints `[PASS]`/`[FAIL]` per check and exits non-zero on a failure. Run the
last four only deliberately: they spend quota.

### CSRF: required for every new state-changing request

The server rejects any POST/PUT/PATCH/DELETE without a valid `X-CSRF-Token` header
(400 `{"error":"csrf"}`). In the browser, send requests only through the helpers in
`app/static/js/ui.js` (`postJson`, `postForm`, or `request()` with a non-GET
method), which read the token from the `<meta name="csrf-token">` that
`layout.html` renders. Never call `fetch()` directly for a state change, and make
any new page extend `layout.html`. Reads must stay GET and side-effect free. In a
script or test, call `enable_csrf_client(app)` from `scripts/_csrf.py` right after
`create_app()`; the test client then fetches and sends the token like a browser.
With `curl`, GET `/` with `-c cookies.txt`, read the `csrf-token` meta tag, and
send it with `-H "X-CSRF-Token: ..."` plus `-b cookies.txt`.

### Cleaning up test users

`scripts/cleanup_demo_users.py` finds every user whose email ends in
`@example.com` (all smoke-test and demo users) and prints how many rows each owns
per table. It is a dry run unless you add `--delete`, which removes their rows in
foreign-key-safe order, then the users and their uploaded resume files.

```bash
PYTHONPATH=. venv/Scripts/python.exe scripts/cleanup_demo_users.py
PYTHONPATH=. venv/Scripts/python.exe scripts/cleanup_demo_users.py --delete
```

If a new table gets a foreign key to `users`, the script stops and tells you to
add it.
---
Known Gotchas
PowerShell vs Git Bash: commands in this guide (and this project's history)
assume Git Bash. Running the same commands in PowerShell has caused real,
time-consuming confusion before (e.g. `source` doesn't exist in PowerShell) —
always confirm your terminal prompt looks like `user@machine MINGW64 /c/...`
before troubleshooting anything else.
`.env.example` vs `.env`: don't confuse these. `.env.example` is a committed
template with blank/placeholder values. `.env` has your real secrets and must be
created locally on every machine — it is never in git.
Stale `__pycache__`: if model or logic changes don't seem to take effect,
clear cached bytecode before re-testing:
```bash
  find . -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} +
  ```
`from app import models` is required before `db.create_all()` — just importing
`create_app`/`db` is not enough; SQLAlchemy only knows about models that have
actually been imported somewhere.

---
Knowledge Base Rebuild and Script Conventions
Rebuild the FAISS knowledge base index with:
```bash
PYTHONPATH=. python scripts/rebuild_kb.py
```
This needs the local roadmap.sh clone that roadmap_kb_processor.py reads. It
backs up the current index and metadata to `data/processed/backup/` (gitignored)
before overwriting them, rebuilds from the clone, appends the SO Survey
chunks, and asserts the final total. Its survey-chunk count is currently
hardcoded to 10 and will need to change once the career path restructuring
lands (see PROJECT_BIOGRAPHY.md).
Run any script from Git Bash with a `PYTHONPATH=.` prefix (as above), or with
`python -m`, since the project root is not on `sys.path` otherwise — a plain
`python scripts/whatever.py` fails with `ModuleNotFoundError: No module named
'app'`.
The FAISS index and metadata files (`data/processed/faiss_index.faiss`,
`data/processed/faiss_index_meta.pkl`) are tracked in git on purpose — a
demo-day safety net so a fresh clone doesn't need to reclone roadmap.sh and
re-embed just to get roadmap generation working.
Git tips: LF/CRLF warnings from Git on Windows are harmless; use
`git --no-pager` for diffs so a pager doesn't swallow pasted input; `.claude/`
is gitignored; and always `git fetch` before pushing when working across two
folders of the same repo (see PROJECT_BIOGRAPHY.md's Git Housekeeping entry).

---
Known Issues / Deployment Backlog

- **Single process only.** The Adzuna cache, the resume rate limits and the loaded
  FAISS index live in process memory. With several workers each has its own copy
  (limits multiply, caches duplicate); use one worker or move the counters and
  cache to Redis.
- **No migrations.** Tables come from `db.create_all()`; changing a column means
  dropping the table or adding Alembic first.
- **Production checklist:** `FLASK_ENV=production`, a random `SECRET_KEY` of 16+
  characters, HTTPS (the session cookie is Secure by default in production), a
  production WSGI server rather than `app.run`, and `SESSION_COOKIE_SECURE` left
  unset. The Flask debugger must stay off.
- **`.env` hygiene.** Every line must be `NAME=value` with no spaces (see section 7).
- **Real-service smoke tests** (`dsa`, `resume`, `roadmap`, `youtube`) spend Gemini
  and YouTube quota and were not re-run after the CSRF change; they were updated
  to send the token and should be run once before a demo.
- **Test data in the dev database.** Smoke tests run with `--keep`, and older runs,
  leave `@example.com` users behind; use `cleanup_demo_users.py`.
- **The CSRF token is not rotated** on login or logout (the session keeps one
  token). Acceptable for now; rotate on login if the threat model changes.
- **Roadmap v2 verification backlog** and the Cybersecurity / Game Development
  two-phase limitation are listed in PROJECT_BIOGRAPHY.md.
- **Videos depend on KB links.** Mobile and Game Development have the weakest
  coverage and fall back to YouTube search most often.

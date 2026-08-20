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
You should see 12 tables: `users`, `career_paths`, `roadmap_steps`, `user_progress`,
`dsa_nodes`, `dsa_problems`, `user_dsa_activity`, `node_mastery`, `resumes`,
`skill_gaps`, `weakness_profiles`, `user_attempts`.
Note: there's no migration tool (like Alembic) in place yet — table creation is
manual via `db.create_all()`. If the schema changes later, existing tables won't
auto-update; they'd need to be dropped and recreated, or a migration tool added.
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
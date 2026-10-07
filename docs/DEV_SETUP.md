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
| `LLM_PROVIDER` | `gemini`, `bedrock` or `openai_compat` (see `app/pipeline/llm_client.py`) | `gemini` |
| `LLM_BASE_URL` | `openai_compat` only: base URL of an OpenAI-compatible API; requests go to `{LLM_BASE_URL}/chat/completions` | `https://integrate.api.nvidia.com/v1` |
| `NVIDIA_API_KEY`, `GROQ_API_KEY`, `LLM_API_KEY` | `openai_compat` only. The key used is chosen by the host of `LLM_BASE_URL`: `groq.com` -> `GROQ_API_KEY`, `nvidia.com` -> `NVIDIA_API_KEY`, any other host -> `LLM_API_KEY`. Sent only as a bearer header, never logged or put in an error; a missing key gives one error that names the variable. Model IDs come from the usual `ROADMAP_MODEL_ID` / `FAST_MODEL_ID` / `FALLBACK_MODEL_ID` | empty |
| `LLM_TIMEOUT_S_OPENAI_COMPAT` | `openai_compat` only: request timeout in seconds. Precedence: this variable, then an explicitly set `LLM_TIMEOUT_S`, then 300. A roadmap phase on `openai/gpt-oss-20b` took 178 to 197 s, so the 90 s default of the other providers times out | `300` |
| `LLM_REASONING_EFFORT` | `openai_compat` only: sent as `reasoning_effort` (`low`, `medium`, `high`) when set; empty sends nothing. `low` is accepted by the NVIDIA endpoint and cuts output about 5 times, but in one run it made the model mis-copy node ids; see the biography before enabling it for roadmap phases | empty |
| `LLM_MAX_RPM` | `openai_compat` only: client-side requests per minute, shared by every thread (calls wait for a slot, they are never refused) | `30` |
| `LLM_MAX_TPM` | `openai_compat` only: client-side tokens-per-minute budget (input + output tokens over a 60 s window; requests wait for room) for providers that publish no rate headers. `0` = off. Providers that send `x-ratelimit-remaining-tokens` / `x-ratelimit-reset-tokens` (Groq) are paced from those headers regardless: a request whose estimate (prompt characters / 3.5) exceeds the remaining tokens waits for the reset. A 429 waits `retry-after` or the token reset; a 413 (request larger than the per-minute limit) is never retried and raises `kind=too_large` | `0` |
| `ROADMAP_MODE` | `cached` (default) or `full`. In `cached` mode `POST /roadmap/generate-async` serves the reviewed base roadmap in `data/base_roadmaps/` for the chosen path, personalized by one short LLM call, and finishes in seconds; a path with no valid base file falls back to the full generation. `full` always generates from scratch. Any other value counts as `cached`. The synchronous `/roadmap/generate` is never affected | `cached` |
| `LLM_PERSONALIZE_TIMEOUT_S` | seconds the personalization call may take in total (retries included); after that the base roadmap is saved without personalization | `25` |
| `ROADMAP_MODEL_ID`, `FAST_MODEL_ID`, `FALLBACK_MODEL_ID` | model per task (`roadmap` = each roadmap phase, `fast` = folder ordering and resume feedback, `fallback` = tried after a model fails). Empty with `gemini` = built-in Gemini models; required with `bedrock` | empty |
| `ALT_PROVIDER_MODEL_ID` | model to use if the other provider has to take over after the first fails | empty |
| `AWS_REGION` | Bedrock region. Credentials come from the environment (`AWS_BEARER_TOKEN_BEDROCK` or normal AWS credentials), never from code | empty |
| `LLM_TIMEOUT_S` | seconds before one LLM request is abandoned, both providers | `90` |
| `PHASE_CONCURRENCY` | roadmap phases the LLM writes at the same time; `1` = one after another (output unchanged), `3` is the tested alternative | `1` |
| `DUPLICATE_SIMILARITY_THRESHOLD` | cosine similarity at which two steps in different phases count as duplicates and the later phase is rewritten once | `0.80` |
| `WARMUP_ON_START` | load the embedding model and FAISS index in the background when `run.py` starts (also when imported by a WSGI server) | `true` |

`PRICE_PER_MTOK` (in `config.py`, not an env var) is deliberately empty: with no price
configured, call costs are logged and benchmarked as "unknown". Fill it in with real
figures per model ID if you want costs. The `bedrock` provider needs `boto3`, which is
not in `requirements.txt` yet (`pip install boto3`, then pin it).

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
You should see 19 tables (`scenario_attempts`, added for scenarios, is the 19th and is
listed below): `users`, `career_paths`, `career_profiles`,
`roadmap_steps`, `user_progress`, `generated_roadmaps`, `roadmap_progress`,
`dsa_nodes`, `dsa_problems`, `dsa_problem_framings`, `user_dsa_activity`,
`node_mastery`, `weakness_profiles`, `user_attempts`, `resumes`, `skill_gaps`,
`job_listings`, `survey_respondents`, `scenario_attempts`.
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
| `smoke_test_resume_modes.py` | resume modes: ranking unit checks (near-ties, thin-path labelling, insufficient data), `/resume/discover` and `/resume/<id>/analyze` happy paths, 404/400/401, CSRF, rate limits, stored skills reused, `/resume/upload` unchanged, required-skills lists identical to the pre-change snapshot (`scratch/golden/required_skills_before.json`) | no (feedback stubbed; local index and embeddings; needs `requirements-dev.txt` for fpdf2) |
| `smoke_test_quiz.py` | career quiz: question-bank rules (1-3 paths per option, 6+ options per path, separating options for each pair), invariants (every path can be #1, every pair separable, stop rule within the bank), 30 seeded replays against `scratch/golden/quiz_after.json`, all-A/all-B personas; pure, no database | no |
| `smoke_test_async_generation.py` | background generation: `/roadmap/generate-async` 202 and polling to done, progress fields, 409, ownership 404, fixed error codes with no exception text, own app context, daily cap, expiry, CSRF, sync route unchanged | no (generator stubbed) |
| `smoke_test_scenarios.py` | scenarios: validator (pilot file plus 20+ deliberately broken copies), blind-solve prompt leak proof, store, engine (all four question types, shuffle, grading edge cases), unlock / best-score / recommendation rules, every route (401, 403, 404, 409, 400, CSRF, rate limit), `CareerProfile` untouched, page renders, `dsa.html` still renders | no (no LLM, YouTube or Adzuna code is reachable; the blind-solve checker is only exercised with a stub) |
| `smoke_test_cached_roadmaps.py` | cached base roadmaps: loader (valid, stale, corrupt, missing), the build script (dry run, resumable, no overwrite without `--force`, one failing path does not stop the others, environment override beats `.env`), the personalizer (bad indexes dropped, text clipped, overlap removed, injection stays escaped, failure is None, prompt under 3,000 estimated tokens for all 15 real outlines), the async route (cached with and without personalization, full fallback, `ROADMAP_MODE=full`, ownership, CSRF, cap, 409), progress and the switcher on a cached roadmap, a timing table written to `scratch/benchmark_cached.csv`; about 2 minutes | no (every LLM call stubbed, uses the local FAISS index) |
| `smoke_test_llm.py` | `llm_client`: retry on throttling/5xx/timeouts, no retry on access-denied/validation, fallback model, provider switch, schema correction, no secrets or prompt text in errors or logs | no (fake Bedrock client, patched Gemini; hides real credentials and blocks real clients) |
| `smoke_test_generator.py` | roadmap generator with a fake LLM: golden comparison for 3 paths, coverage/duplicate/index/allowlist/shape invariants at concurrency 1 and 3, thread hygiene, failure handling, duplicate rewrite, warm-up | no (fake LLM, local embeddings only; ~1.5 min, mostly model load) |
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

If you change generator behavior ON PURPOSE, recapture the golden files with
`PYTHONPATH=. venv/Scripts/python.exe scripts/smoke_test_generator.py --update-golden`
and review the diff of `scratch/golden/` (the files are tracked although `scratch/` is
gitignored; add changes with `git add -f`).

### Benchmarks and measurement scripts (all local, none call a real model)

| Script | What it does |
|---|---|
| `scripts/benchmark_generator.py [--delay 3]` | runs the generator for 3 paths at `PHASE_CONCURRENCY` 1 and 3 with a stub LLM that sleeps `--delay` seconds per call; prints wall-clock, speed-up and local stage timings (retrieval, post-processing, duplicate check); writes `scratch/benchmark_generator.csv` |
| `scripts/benchmark_llm.py` | compares your configured models on 5 fixed student profiles. DRY RUN by default (prints the plan, no calls). `--run` makes REAL, billable calls and writes `scratch/benchmark_results.csv`; don't run it casually |
| `scripts/measure_duplicate_threshold.py` | re-derives the duplicate-check threshold from the saved real roadmaps in `scratch/` |

Per-stage timings of every real generation are also logged as `roadmap_stage` lines (never any prompt or reply text), and every LLM call as an `llm_call` line.

### Survey skill columns and the resume-mode scripts

`survey_respondents` has three nullable array columns, `dev_envs`, `so_tags` and `office_stack`, added after
the table was first created (there is no migration tool). On a machine whose table predates them:

1. Download the survey CSV: `kaggle datasets download -d aliaslam25/stack-overflow-developer-survey-2025 -f survey_results_public.csv -p data/raw --unzip`
   (needs `KAGGLE_USERNAME` and `KAGGLE_KEY` in `.env`; the file is 140,893,245 bytes and `data/raw/` is gitignored).
2. `PYTHONPATH=. venv/Scripts/python.exe scripts/add_survey_skill_columns.py`: backs the table up to `scratch/`, runs
   `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, fills the columns by row order, verifies every existing field is unchanged
   (it stops without writing if the row counts or any existing field differ), and prints the top 15 values per column.
   Safe to re-run.
3. `resumes.analysis_pending` (BOOLEAN) was added too, for `/resume/discover`:
   `ALTER TABLE resumes ADD COLUMN IF NOT EXISTS analysis_pending BOOLEAN DEFAULT FALSE;`

A fresh database gets all of these from `db.create_all()`. After a rebuild from the CSV with
`so_survey_processor.process()` the new columns are in its output (`SKILL_COLUMNS` maps CSV column to table column).

`scripts/validate_path_fit.py` prints the path-fit ranking for three synthetic resumes with the raw survey and
roadmap numbers behind each row (local only).

### The career quiz: tests, simulation and golden files

- `PYTHONPATH=. venv/Scripts/python.exe scripts/smoke_test_quiz.py` replays 30 seeded random sequences through the real engine and
  compares them with `scratch/golden/quiz_after.json`. **Changing a question, an option signal or the engine changes quiz results on
  purpose-only:** re-run it, read what differs, then recapture with
  `PYTHONPATH=. venv/Scripts/python.exe scripts/smoke_test_quiz.py --capture scratch/golden/quiz_after.json` and `git add -f` the file
  (`scratch/` is gitignored). `quiz_before.json` is the original engine's replay and stays as the reference for
  `scripts/quiz_golden_diff.py`, which prints how many sequences changed their top path, tie group and question count.
- `PYTHONPATH=. venv/Scripts/python.exe scripts/simulate_quiz.py [N]` runs N random sequences (default 1,000) through the current engine and
  the original one (from git) and prints how often each path is #1, how often each pair ends within 1 point, and how many questions are
  asked. Random answers are not a realistic student distribution; use it to see what the quiz can and cannot do.
- The option-to-path mapping in `career_quiz_data.py` is hand-authored judgment. `scripts/generate_quiz_bank_doc.py` rewrites
  `docs/QUIZ_QUESTION_BANK.md` (every question, option and signal, with the old signals of Q1-Q10) after any change.
- Pairs of paths that get special treatment (separating questions, the stop rule) are defined once, in
  `career_path_registry.PATH_PAIRS`.

### Background roadmap generation

- `POST /roadmap/generate-async` (body `{target_career_path}`, CSRF header like every POST) returns 202 `{job_id, mode}` (`mode` is `cached` or `full`, see Base roadmaps below); 409
  `{error: "job_running", job_id}` if you already have an active job; 429 `daily_limit` and the path errors as for
  `/roadmap/generate` (which still exists, unchanged, and still blocks until the roadmap is saved).
- `GET /roadmap/jobs/<job_id>` returns `{status, elapsed_s, mode, phase_done?, phase_total?, roadmap_id?, error_code?}` (a cached job reports 1 part); a job that is
  not yours, unknown or expired is 404. `status` is `queued`, `running`, `done` or `failed`; `error_code` is one of
  `generation_failed`, `save_failed`, `unexpected` (the real exception is in the server log only).
- The roadmap page uses the async endpoints and keeps the job id in `sessionStorage`.
- **Limitation:** jobs live in process memory (`app/pipeline/generation_jobs.py`): a restart loses running jobs, and with several
  worker processes a poll can reach a worker that does not know the job. Run one worker, or move the registry to the
  database or Redis first. A job and a synchronous generation from the same user can run at once.

### Base roadmaps (cached mode)

Writing a full roadmap per student takes minutes and the result barely depends on the student, so each career path now has ONE reviewed
base roadmap, and a student gets a copy plus a short personalization (a summary, a note per phase, up to 8 "Focus" steps and up to 8
"Can skim" steps) from one small LLM call. The personalization never adds or changes steps; if it fails the base is saved without it.

- Files: `data/base_roadmaps/<slug>.json` (for example `cybersecurity.json`, `ui-ux-design.json`), **committed to git**. Each holds
  `metadata` (career path, model, build time, generator settings, a fingerprint of the path's knowledge-base topic inventory), the
  `roadmap` (phases and steps, with videos and resources already attached from the knowledge base) and the generator's `audit`.
- Serving: `app/pipeline/base_roadmaps.py` validates a file before using it (phased shape, `global_step_index` contiguous from 1,
  `topic_refs` inside the path's inventory, no duplicate titles, `videos` and `resources` on every step). A missing, corrupt or invalid
  file counts as missing, so that path uses the full generation. If only the fingerprint no longer matches (the knowledge base changed) the
  file is still served, a warning is logged, and the saved roadmap's `base.stale` is `true`; rebuild with `--force` when that happens.
- What is stored on a cached roadmap: the usual `phases`, plus `personalization` (when it succeeded) and `base`
  (`source`, `model_id`, `built_at`, `stale`) inside the `steps` JSON. Old roadmaps have neither, and the page renders them as before.

Build them yourself (the script is a DRY RUN unless you add `--run`; nothing is called or written without it):

```
python scripts/build_base_roadmaps.py --paths "Cybersecurity"            # dry run: shows the provider, models, plan
python scripts/build_base_roadmaps.py --paths "Cybersecurity" --run      # builds one path
python scripts/build_base_roadmaps.py --all --run                        # every path that has no valid file yet
python scripts/build_base_roadmaps.py --paths "DevOps" --run --force     # rebuild one that already exists
python scripts/build_base_roadmaps.py --review-only                      # rewrite the review document only
```

- The script uses the existing generator with a neutral profile (no personal answers), attaches resources from the knowledge base only
  (no network, no YouTube), validates, and writes atomically. Re-running it skips valid files, so an interrupted run resumes; a path that
  fails is reported and the others continue (exit code 1 at the end). It prints the provider host and the models (never a key) first, and
  turns off failover to a second provider for the run.
- Provider and model come from the environment, and variables set before the command win over `.env`. PowerShell, NVIDIA `openai/gpt-oss-20b`
  (the key is read from `NVIDIA_API_KEY` in `.env`, chosen by the host):

```
$env:LLM_PROVIDER="openai_compat"; $env:LLM_BASE_URL="https://integrate.api.nvidia.com/v1"
$env:ROADMAP_MODEL_ID="openai/gpt-oss-20b"; $env:FAST_MODEL_ID="openai/gpt-oss-20b"; $env:FALLBACK_MODEL_ID="openai/gpt-oss-20b"
python scripts/build_base_roadmaps.py --paths "Cybersecurity" --run
python scripts/build_base_roadmaps.py --all --run
```

- Review: every run writes `docs/BASE_ROADMAP_REVIEW.md` with, for each path, every phase, every step title, and the descriptions of the
  first two steps of each phase. Read it before committing the JSON files. It also shows the summary table columns per path: phases, steps,
  discarded `topic_refs` (invented ids the generator dropped), duplicate warnings (phases rewritten / repeats kept), seconds and model.
- The personalizer uses the `fast` model (`FAST_MODEL_ID`) at runtime, so that variable must point at a model the provider serves.

### Front-end design system (where the tokens and components live)

All styling is in one file, `app/static/css/style.css`, in this order: (1) tokens in `:root` (colours, the `--sp-*` spacing scale,
`--r-*` radii, `--shadow-*`, `--fs-*` type scale, `--ease` / `--t*` motion, `--tap` = 44 px minimum target, `--wrap` content width);
(2) base (reset, the one focus ring, skip link, `.visually-hidden`); (3) components: `.btn` (primary; `.btn-secondary`, `.btn-ghost`,
`aria-busy="true"` for the loading state), `.card`, `.chip` / `.badge`, `.pbar` and `.ring`, `.seg` / `.tabs`, `.empty`, `.skel`,
`.alert`, `.disclosure` (a `<details>` used for every "How this works"); (4) page rules (landing, quiz and goals, roadmap, resume,
dashboard); (5) the legacy "sheet" layout (`.sheet`, `.row`, `.margin`, `.main`), which only the DSA skill-map page and the
legacy career-path picker still use. Do not restyle that last block without opening `/dsa`.

The JS builders for the components are in `app/static/js/ui.js`: `skeleton()`, `alertEl()`, `emptyState()`, `disclosure()`, `pbar()`,
`ring()`, `sectionTabs()` (tabs on a wide screen, accordion on a narrow one), `questionForm()` (option cards, keys 1-9, Enter) and
`questionProgress()`. Page renderers shared by several pages are in `app/static/js/results.js`. Rules for new UI: text only through `el()` /
`textContent`, state-changing requests only through the CSRF helpers, one filled button per screen, and no web fonts or CDNs (the
system font stack is used because no font is bundled; the DSA page still loads D3 from its CDN, as before). Text colours must stay
`--ink` or `--pencil` (both pass 4.5:1 on `--paper`, `--surface` and `--tint`; `scratch/contrast.py` checks the pairs).
`scripts/make_roadmap_preview.py` builds a standalone page from `style.css`, `ui.js` and `results.js`, so it follows these files.

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

### Scenarios (scenario-based practice)

Short work scenarios per career path, shown as a map. Pilot path: Machine Learning Engineering
(`data/scenarios/ml-engineering.json`, 5 scenarios, 22 questions). Page: `/scenarios`; API:
`app/routes/scenarios.py`; rules: `app/pipeline/scenario_engine.py` (pure); loading:
`app/pipeline/scenario_store.py`; checks: `app/pipeline/scenario_validator.py`.

- **New table `scenario_attempts`.** Created by `db.create_all()` (it only adds missing tables, so nothing else is
  touched): id, user_id, path, scenario_id, answers (JSON), score, max_score, passed, shuffle_seed, started_at,
  submitted_at, with an index on (user_id, scenario_id). `submitted_at` NULL means the attempt is unfinished.
- **File format** (schema version 1): top level `schema_version`, `path` (a name in `CAREER_PATHS`), `map`
  (`scene_id`, `theme`, `edges`), `scenarios`. A scenario has `id` (`mle-N`), `order` (1..N), `ladder_stage`
  (`foundations`, `core_decision`, `debugging`, `trade_offs`, `end_to_end`, in that order), `title`, `difficulty`,
  `estimated_minutes`, `background`, `constraints`, `tests_topics`, `map_node` (`x`, `y` in 0..1, `label`) and
  `questions` (`mle-N-qM`). Question types: `single_choice` (`correct` = one id), `multi_select` (`correct` = ids),
  `order` (`correct` = all ids in order), `match` (`items`, `targets`, `correct` = {item id: target id}). Every question
  also needs `explanation`, `why_others_wrong` (one entry per wrong option; `common_mistake` for order and match) and
  `key_justification`.
- **Validate before anything else:** `PYTHONPATH=. python scripts/validate_scenarios.py` checks every file in
  `data/scenarios/`, prints per-file results and exits non-zero on any error. Warnings (all correct answers in one
  position; the longest option being correct in more than 60% of single-choice questions) never fail it. The store
  refuses an invalid file, so it behaves as if it were missing.
- **Blind-solve check** (a model answers without seeing the key; disagreements go to
  `docs/SCENARIO_REVIEW_<path slug>.md` for a human to judge). Dry run by default:
  `PYTHONPATH=. python scripts/blind_solve_scenarios.py`. The real run calls the configured model (one call per
  scenario, one retry for a failed scenario only):
  `PYTHONPATH=. python scripts/blind_solve_scenarios.py --run --paths "Machine Learning Engineering"`.
- **Answer delivery.** The server never sends the key. `POST /scenarios/<id>/start` returns the shuffled public view;
  `POST /scenarios/<id>/answer` locks one question and returns that question's explanation; `POST /scenarios/<id>/submit`
  grades everything on the server. A locked answer cannot be changed (the submit call uses the stored one).
- **Rules.** Scenario 1 is always open; scenario N+1 opens after any submitted attempt on N; the best score is kept;
  10 points per question, all or nothing; pass is 70% or more. The "matches your goal" marker maps the Goals chat's
  `goal` signal to ladder stages (`build_fundamentals` -> foundations and core decisions, `explore` -> foundations,
  `specific_role` and `any_good_company` -> debugging, trade-offs and end to end); it is a hint and never locks anything.
- **Add a path:** write `data/scenarios/<slug>.json` in the format above with a `path` that is in `CAREER_PATHS`; add
  the path's id prefix to `PATH_ID_PREFIX` in `scenario_validator.py`; run the validator; optionally drop a scene at
  `app/static/scenes/<scene_id>.svg` (without one the map shows a gradient); run the blind-solve check and read the
  review file before shipping.
- **Tests:** `PYTHONPATH=. python scripts/smoke_test_scenarios.py` (see the table above).

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
- **Bedrock path untested against real botocore.** `boto3` isn't installed; the path is
  tested with a scripted fake. Install and pin `boto3`, then run `benchmark_llm.py`
  once before relying on it.
- **Parallel generation quality is unmeasured.** `PHASE_CONCURRENCY` stays at 1 until a
  few real roadmaps at 3 have been compared (duplicates, pacing) with `inspect_roadmap.py`.
  The duplicate check catches about 5 of 12 hand-written paraphrases at its 0.80 threshold.
- **A real Gemini request was sent by accident** while writing `smoke_test_llm.py` (see the
  Faster Roadmap Generation entry in PROJECT_BIOGRAPHY.md). Fixed; the test now blocks real clients.
- **Path-fit ranking is validated only on synthetic resumes.** Pairs such as AI and ML score almost the same by design
  (the survey has one "AI/ML engineer" answer), thin paths (fewer than 30 respondents) rest on roadmap content alone,
  and TensorFlow, PyTorch and pandas have no survey data (the 2025 survey dropped those columns), so they only help
  through the roadmap signal. The page says so; check a few real resumes before relying on it.
- **`/resume/<id>/analyze` with a real LLM is untested** (stubbed in the tests and the browser check).
- **Background jobs are in memory.** See "Background roadmap generation" above: one worker process only.
- **`openai_compat` roadmap quality depends on reasoning.** With `LLM_REASONING_EFFORT=low` one run lost the `topic_refs` of
  12 of 22 steps (the model truncated node ids); defaults are unchanged.

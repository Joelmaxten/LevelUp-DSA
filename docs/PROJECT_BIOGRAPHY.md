# LevelUp DSA — Project Biography

A running log of what's been built, why, and what went wrong along the way.
Updated every time a meaningful piece of functionality is added.

---

## Foundation & Version Control

**What was built:** GitHub repo `levelup-dsa` initialized with README, MIT license, Python `.gitignore`. Branching strategy set up: `main` (deployable) → `dev` (integration) → `feature/*` (active work). Python virtual environment created; Flask, Flask-Login, Flask-SQLAlchemy, psycopg2-binary installed. Project folder structure built: `app/` (routes, pipeline, templates, static), `data/`, `docs/`, `tests/`.

**Why it works this way:** `psycopg2-binary` was used instead of plain `psycopg2` — it's pre-compiled, so it doesn't need PostgreSQL dev headers or a C compiler on the dev machine. The `feature → dev → main` branch flow keeps `main` always deployable, even working solo.

---

## Flask Application Skeleton

**What was built:** `app/__init__.py` — a Flask **application factory** (`create_app()`), rather than a global `app = Flask(...)`. `app/config.py` holds all settings (DB URL, API key placeholders) pulled from environment variables via `python-dotenv`, never hardcoded. `run.py` is the entry point.

**Why it works this way:** The factory pattern means the app can be created fresh for tests or different configs later, instead of being a single global object created at import time.

---

## Database Layer — PostgreSQL + SQLAlchemy

**What was built:** PostgreSQL 18 provisioned locally, database `levelup_dsa_dev` created. SQLAlchemy connected via `DATABASE_URL` in `.env`. All 12 tables from the master doc's schema implemented in `app/models.py`:

`Users`, `CareerPaths`, `RoadmapSteps`, `UserProgress`, `DSANodes`, `DSAProblems`, `UserDSAActivity`, `NodeMastery`, `Resumes`, `SkillGap`, `WeaknessProfile`, `UserAttempts`.

**Design decisions:**
- `DSANode.career_paths` and `.prerequisites` use PostgreSQL's native `ARRAY` column type instead of separate join tables — simpler for this project's scale, at the cost of being PostgreSQL-specific (a fair trade-off to be able to explain in an interview).
- `DSAProblem.test_cases` uses a `JSON` column — test cases are naturally a list of input/output pairs.
- `WeaknessProfile` and `UserAttempts` got an auto-increment `id` primary key even though the master doc's schema notation omitted one — simpler to work with in SQLAlchemy than a composite key, without changing what data is tracked.

**Issue faced — tables silently not appearing:**
Ran `db.create_all()` in a Python shell after adding new model classes, got no errors, but `psql \dt` showed the tables weren't actually created.
**Root cause:** commands were accidentally being run in a **PowerShell** terminal instead of Git Bash — confirmed when `source venv/Scripts/activate` failed with "term not recognized" (a bash-only command). PowerShell and Git Bash can look similar but behave differently for this kind of tooling.
**Fix:** Switched back to Git Bash in VS Code, reactivated the venv, cleared `__pycache__`, reran — all tables created and verified correctly via `\dt` and `\d <table>`.

---

## Authentication — Signup, Login, Logout

**What was built:** `bcrypt` password hashing via `set_password()` / `check_password()` methods on the `User` model. `/signup` (validates input, checks duplicate email, hashes password, returns proper HTTP status codes 400/409/201), `/login` (checks credentials, starts a Flask-Login session), `/logout` (`@login_required`, ends the session). All built as a Flask Blueprint in `app/routes/auth.py`.

**Security decisions:**
- Login returns the *same* generic "Invalid email or password" error whether the email doesn't exist or the password is wrong — never reveals which one failed.
- `login_manager.unauthorized_handler` returns a proper JSON 401 instead of Flask-Login's default HTML redirect-to-login-page behavior, since this is a JSON API, not a page-based site.

**Verification:** Tested end-to-end via `curl`, including cookie-based session testing (`-c`/`-b` flags) to prove `login_user()` → `@login_required` → `logout_user()` genuinely works across separate HTTP requests, not just within one process.

---

## Base UI — Layout, Landing Page, Signup/Login Pages

**What was built:** `layout.html` — a Jinja2 base template with navbar, footer, and `{% block %}` slots that other pages fill in, so HTML boilerplate isn't repeated on every page. Dark-themed `style.css`. Landing page (`index.html`). Signup and login pages with real HTML forms that use JavaScript `fetch()` to POST JSON to the existing API routes (no page reload) — necessary because the `/signup` and `/login` routes are JSON APIs, not traditional form-handling routes. Separate `GET` routes added alongside the existing `POST` routes on the same URLs (Flask treats these as distinct).

**Verification:** Full signup → login flow tested in an actual browser, confirmed real users landing in PostgreSQL with bcrypt-hashed passwords.

---

## Adaptive Career Discovery Quiz — Engine

**What was built:** An Akinator-style adaptive quiz, not a fixed questionnaire. `app/pipeline/career_quiz_data.py` holds the question bank (10 questions, options A–D) and career-path data (10 CS career paths) plus an option → career-signal mapping table. `app/pipeline/career_quiz_engine.py` holds the actual logic:
- `apply_answer()` — adds +1 to every career path an answered option signals
- `next_question()` — picks the next question using a **variance-based proxy for information gain**: it looks at the current top-4 leading career paths, simulates how each possible answer option would shift their scores, and picks the question with the most score "spread" among those simulated outcomes
- `should_stop()` — enforces an 8–12 question range, stopping early only if the leader is at least 3 points ahead of 2nd place
- `get_results()` — returns career paths ranked by score, with confidence percentages

**Why a proxy instead of true information gain:** True Bayesian information gain requires calibrated probability distributions from real user data, which doesn't exist yet. The variance-based heuristic is a defensible, explainable approximation — honest about what it is, not oversold as "real" info theory.

**Verification:** Tested with two opposing simulated personas — one answering "A" throughout (technical/analytical), one answering "B" throughout (creative) — and got correctly opposite results (AI/ML Engineering leading vs. UI/UX + Frontend leading), with the engine dynamically choosing different question orders each time rather than a fixed sequence.

**Issue faced — inconsistent results between a plain Python script and the real web server:**
The exact same engine code gave a different "next question" when tested via a direct Python shell (`Q4`) vs. through a live Flask session over HTTP (`Q2`), for the identical first answer.
**Root cause:** Flask's `session` object persists data by serializing it to **JSON** and storing it in a signed cookie. When our `scores` dictionary round-tripped through JSON encode → cookie → JSON decode, its key order changed from the original insertion order (as defined in `CAREER_PATHS`) to alphabetical order. `next_question()`'s tie-breaking logic (`sorted(..., key=scores.get)`) is *stable*, meaning ties are broken by whatever order the dictionary happens to be in — so a different dict order silently produced a different set of "current leaders" among tied scores, which cascaded into a different question choice.
**How it was found:** Added temporary debug `print()` statements to log the scores dict and asked IDs inside the live route, compared the printed (alphabetical) order against the Python shell's (insertion) order — confirmed the mismatch directly rather than guessing.
**Fix:** Replaced the implicit, order-dependent tiebreak with an explicit one: `sorted(session["scores"], key=lambda path: (-session["scores"][path], path))` — sorts by score first, then alphabetically by career path name as a fixed, deterministic tiebreaker that doesn't depend on incidental dictionary ordering.
**Verification:** Reran the same test in both a fresh Python shell and through Flask's real session — both now agree, and the full 9-question flow was tested end-to-end through the actual running server via `curl`, landing on identical results to the original standalone simulation.

---

## Working Across Two Machines

**What changed:** started doing development from a second (fresh) Windows laptop in addition to the main one.

**What was involved:** cloning the repo, recreating the venv, installing PostgreSQL 18 from scratch, recreating `.env` and all 12 tables — none of which travel with `git clone`, since they're either gitignored (`venv/`, `.env`) or external services (the database itself).

**Issue faced — DB connection failing with a confusing error:**
`db.create_all()` failed with `password authentication failed for user "username"`.
**Root cause:** `.env` still had the literal placeholder text `username` from `.env.example`, never replaced with the real `postgres` username and password.
**Fix:** corrected `DATABASE_URL` in `.env` to use real credentials.

**New doc created:** `docs/DEV_SETUP.md` — a full onboarding manual (prerequisites, clone, venv, PostgreSQL install + PATH setup, `.env` setup, table creation, running the app, git workflow, testing conventions, known gotchas). Writing it surfaced the exact same "pasted content didn't actually save" issue from Day 5's `.env.example` bug — the paste landed while the editor tab wasn't properly focused, resulting in a silently empty file. Caught by checking `cat` output before committing, rather than trusting the editor.

**New convention established:** always push before closing a laptop for the day; always pull before starting work on a different machine. Keeps GitHub as the single source of truth across both machines.

---

## Quiz Frontend UI

**What was built:** `app/templates/quiz.html` — the actual interface for the adaptive quiz. Calls `/quiz/start` on page load, dynamically renders whichever question the engine returns as clickable option buttons (nothing hardcoded — it works for any of the 10 questions in any order), and on each click calls `/quiz/answer`, repeating until the response says `finished: true`, at which point it renders the ranked results with confidence percentages.

**Issue faced — 500 error crashing the quiz partway through:**
Mid-quiz, hit a server error: `KeyError: None` on `QUESTIONS[q_id]`.
**Root cause:** the question bank only has 10 questions, but the engine's `MAX_QUESTIONS` constant was set to 12. If a student's answers never triggered the early-confidence stop (the 3-point score-gap rule), the code tried to ask an 11th question that doesn't exist. `next_question()` correctly returned `None` in that case — but the Flask route never checked for that, and tried to look up `None` in the `QUESTIONS` dictionary anyway, crashing.
**Fix:** the route now computes the next question *before* deciding whether to stop, and finishes the quiz if **either** `should_stop()` says so **or** there are simply no questions left (`q_id is None`) — so running out of questions is treated as a valid, expected finish condition, not an error.

**Verification:** completed a full quiz end-to-end in the actual browser (not just curl this time), confirmed the ranked results render correctly with proper styling.

---



---
## RAG Pipeline — Knowledge Base, Embeddings, FAISS Retrieval

**Scope decision:** Rather than pulling all ~90 roles from roadmap.sh, the knowledge base was
deliberately scoped ("Tier 1") to just the quiz's 10 fixed career paths, each enriched with a
few relevant sub-skill topics (e.g. React/Node.js/Git under Software Engineering). Expanding
the quiz itself to support non-traditional career paths (Product Management, DevRel, etc.) was
considered and explicitly deferred — it would require redesigning and re-validating the entire
quiz engine, which is out of the documented spec and not worth the risk/time right now.

**What was built:**
- `app/pipeline/roadmap_kb_processor.py` — maps each of the 10 career paths to specific
  roadmap.sh folders, walks a local clone of the roadmap.sh repo, strips markdown formatting
  and resource-link lists down to clean descriptive text, tags each chunk with its career
  path(s) (a chunk can belong to more than one path, same array pattern as `DSANode.career_paths`).
- `app/pipeline/embedder.py` — loads `all-MiniLM-L6-v2` once (module-level cache) and converts
  text chunks into 384-dimensional vectors via batched encoding.
- `app/pipeline/rag.py` — builds a FAISS `IndexFlatIP` index over L2-normalized embeddings
  (inner product on normalized vectors = cosine similarity), persists the index and chunk
  metadata to disk, and provides `search()` — semantic search with an optional `career_path`
  filter.

**Verification, at each stage:**
- Extraction produced 3,586 real, cleaned chunks across 27 roadmap.sh folders.
- Embedding quality was sanity-checked with cosine similarity *before* running the full batch:
  "React" vs "Vue" (genuinely related) scored 0.59; "React" vs "Cybersecurity" (unrelated)
  scored 0.06 — confirming the model captures real semantic meaning, not noise.
- The full 3,586-chunk batch embedded in ~43 seconds on CPU.
- Retrieval was tested both unfiltered (an ML/AI query returned genuinely relevant results
  spanning multiple folders) and filtered by career path — a Cybersecurity-filtered search on
  an unrelated ML query correctly returned nothing, while the same filter on a genuinely
  cybersecurity-related query returned five strong, correctly-tagged results. Both outcomes
  needed to be checked, since an empty result could have meant either "working correctly, no
  match" or "broken" — only testing both proved which one it was.

**Issue faced — a `.gitignore` rule that silently didn't match:**
The FAISS index files (`data/processed/faiss_index.faiss`, `..._meta.pkl`) showed up as
untracked in `git status`, even though `.gitignore` was supposed to exclude generated index
files.
**Root cause:** the original `.gitignore` rules from Day 1 (`*.index`, `faiss_index/`) were
written before the actual file-naming pattern was known, and didn't match the real filenames
FAISS/pickle actually produced.
**Fix:** replaced the guesswork rules with ones matching the real paths —
`data/processed/*.faiss` and `data/processed/*_meta.pkl`. Caught by checking `git status`
before committing, rather than assuming `.gitignore` was already correct.

---

---

## Post-Quiz Conversation Engine

**What was built:** `app/pipeline/conversation_data.py` — 4 fixed questions (C1-C4) capturing
signals the adaptive career quiz structurally cannot: IT-track preference (traditional vs.
non-traditional tech-adjacent paths — relevant since all 10 `CAREER_PATHS` in the quiz are
traditional CS paths), things to avoid, target company type, and near-term goal. Each
(question, option) maps to a single flat `(signal_key, signal_value)` pair — not a list of
career paths like the quiz's `OPTION_SIGNALS`, since these signals aren't scored, just carried
forward as profile context for the later LLM roadmap prompt.

`app/pipeline/conversation_engine.py` — much simpler than `career_quiz_engine.py`: fixed
question order, no adaptivity, no early-stop logic. Session state stores only an integer index
(never anything derived from iterating the question dict), specifically to avoid a repeat of
the dict-ordering round-trip bug hit in the quiz engine's session handling.

`app/routes/conversation.py` — `/conversation/start` and `/conversation/answer`, mirroring
`quiz.py`'s exact pattern: state lives under its own `session["conversation"]` key (fully
separate from `session["quiz"]`), popped on completion. Added `ValueError` validation on bad
question_id/option pairs, returning a 400 instead of letting a bad lookup crash into a 500 —
the same class of bug as the quiz's earlier `KeyError: None` crash, caught proactively this time
instead of after the fact.

**Issue faced — duplicate blueprint registration:**
`create_app()` crashed with `ValueError: The name 'quiz' is already registered for this
blueprint` when the conversation blueprint was added.
**Root cause:** the quiz blueprint's import + register lines had been accidentally pasted twice
in `app/__init__.py` during editing — unrelated to the new conversation code itself.
**Fix:** removed the duplicate `from app.routes.quiz import quiz_bp` / `app.register_blueprint(quiz_bp)`
pair, confirmed via `app.url_map.iter_rules()` that exactly one set of conversation routes
registered.

**Verification:** Full 4-answer flow tested end-to-end via `curl` with cookie-based session
persistence (`-c`/`-b`), same discipline as quiz testing. Confirmed: each answer advances to the
correct next question; the final answer returns `finished: true` with the exact expected signals
dict (`{"it_track": "non_traditional", "avoid": "repetitive_work", "target_company":
"product_based", "goal": "build_fundamentals"}` for a known answer sequence); starting a new
conversation after completion correctly resets to C1 (proving `session.pop` worked, not just that
the happy path worked); an invalid option returns a 400 with a clear error message instead of a
500 crash.

**Branching note:** built on a dedicated `feature/conversation-engine` branch (off
`feature/scaffold`) rather than directly on `feature/scaffold`, since dataset-processing work was
happening in parallel on a second laptop also based on `feature/scaffold` — avoids two machines
committing to the same branch.

---
## Still To Build

- Career path scoring integration + non-traditional path support
- Roadmap generation via Gemini LLM
- Phase 2 — Resume analyzer
- Phase 3 — Gamified DSA / Skill DNA Map
- Placement Readiness Score
- Deployment to Render
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

## Career Profile — Merging Quiz + Conversation into One Ranked Profile

**What was built:** `app/pipeline/profile_builder.py` combines the quiz's raw career-path
scores with the conversation's signals into one final student profile, with a real, tested
mechanism to let signals adjust the ranking (`ADJUSTMENT_RULES`, keyed by `(signal_key,
signal_value)` -> `{career_path: score_delta}`).

**Design decision — why the adjustment mechanism is empty in production:**
Initially considered a uniform score boost for `it_track: traditional` (reinforcing the
quiz's own direction when a student confirms they want exactly that). Worked through the
math before writing it and found it was wrong: adding a flat +K to every path's score can't
change relative ranking order at all, and actively *flattens* `confidence_pct` (since
`confidence_pct = score / total`, adding K to all 10 numerators while adding 10K to the
shared denominator shrinks the spread, the opposite of the intended effect). Caught and
corrected before any code was written, not after.

Landed on: `it_track: non_traditional` is the only signal with a defensible causal link to
ranking (boost non-traditional career paths) - but non-traditional paths don't exist in
`CAREER_PATHS` yet (deliberately deferred per the RAG pipeline's "Tier 1" scope decision), so
today it's a no-op too. `avoid`, `target_company`, and `goal` have no honest causal story for
*which* of the 10 existing CS paths they should favor - inventing weights for them would be
arbitrary, not derived. They're carried into the profile purely as LLM prompt context, never
touch the ranking.

**Verification, two parts:**
1. Confirmed all three real `it_track` values (`traditional`, `non_traditional`, `open`)
   produce a `career_ranking` byte-identical to the quiz's own `get_results()` - the
   zero-adjustment guarantee that matters for production today.
2. Proved the mechanism itself works correctly by temporarily injecting one fake rule
   (never committed): confirmed score shifted by the exact delta, `confidence_pct` moved in
   the same direction (not stale), and critically that `apply_adjustments()` does NOT mutate
   the quiz's original `scores` dict (it's still live in the session).

## CareerProfile Table + End-to-End Persistence

**What was built:** New `CareerProfile` model (`app/models.py`) - `user_id` FK, `career_ranking`
JSON, `conversation_signals` JSON, `created_at`. 13th table, added via `db.create_all()`,
verified via `\dt` / `\d career_profiles`.

**Design decision - separate table vs. columns on `Users`:**
Considered adding `career_ranking`/`conversation_signals` directly to the `Users` table for
simplicity. Went with a separate table instead, for reasons beyond preference: the master
doc's Class Diagram (section 20) explicitly locks `Student` composition `CareerProfile` as
its own class - a decision already reviewed with the guide, not something to quietly
deviate from. A separate table also preserves history if a student retakes the quiz (same
precedent as the existing `Resume` table - multiple rows per user, not overwritten), and
keeps `Users` scoped to identity/auth only, consistent with every other user-specific table
in the schema (resumes, skill_gaps, weakness_profiles, user_attempts all follow the same
`user_id` FK pattern rather than bolting onto `Users`).

`quiz.py` and `conversation.py` both got `@login_required` (a real gap before this - neither
route enforced authentication), since `CareerProfile.user_id` needs a real logged-in user to
attach to.

**Issue faced - session lifetime gap between quiz and conversation:**
Both routes previously popped their entire session state on completion
(`session.pop("quiz")` / `session.pop("conversation")`). This meant the quiz's raw scores
dict was already gone from the session by the time a student finished the conversation -
`build_profile()` had no way to access both pieces of data at once, because the two flows
never actually overlapped in session state.
**Fix:** quiz now keeps `session["quiz_scores"]` (just the raw scores dict) alive across its
own pop, popped only once the conversation step actually consumes it.
`/conversation/start` now gates entry on `"quiz_scores" in session` (400 if the quiz hasn't
been completed - closes a real gap where nothing previously stopped a student from hitting
`/conversation` out of order). `/conversation/answer` also defensively re-checks the same
condition rather than trusting that a prior request left things as expected.

**Issue faced - duplicate file content from a bad paste:**
After editing `quiz.py`, the app crashed on import with `SyntaxError: invalid decimal
literal` at `}), 200from flask import Blueprint...`.
**Root cause:** the entire file's content had been pasted twice in a row with no separating
newline between the two copies - not a logic bug, a copy-paste mechanics issue.
**Fix:** rewrote the file cleanly via a bash heredoc (`cat > file << 'EOF' ... EOF`) rather
than trying to surgically remove the duplicate, to avoid any risk of a partial-match edit
going wrong. Verified via `wc -l` (should be ~60 lines, not ~120) before re-testing.

**Issue faced - inconsistent curl cookie flags silently losing session state:**
`/quiz/answer` returned `"No quiz in progress"` immediately after `/quiz/start` had just
returned a real question.
**Root cause:** the `/quiz/start` call had used `-b cookies.txt` (read cookie) but not also
`-c cookies.txt` (write updated cookie back). Flask's session lives entirely in the cookie,
so the server's response *did* include an updated session cookie setting
`session["quiz"]` - but without `-c` on that specific call, the updated cookie was never
saved back to the file. The next call still only had the pre-quiz cookie.
**Fix:** always pass `-b` and `-c` together on every call that might read or write session
state, not just on calls expected to change something.

**Verification:** Wrote `scripts/smoke_test_profile_flow.py` - a throwaway smoke test using
Flask's test client instead of manual curl chaining, to drive the full signup -> login ->
9-question adaptive quiz -> 4-question conversation -> DB read-back flow programmatically.
Faster to re-run and more rigorous than one-by-one curl (exercises the real app routes and
session handling, not just isolated function calls). Run twice with different random users,
consistent results both times: quiz correctly self-stopped at 9 questions (confidence gap
threshold hit before `MAX_QUESTIONS`), conversation signals correctly produced zero ranking
change (matching the no-op guarantee above), and the `CareerProfile` row was confirmed via
an independent DB query - not just trusting the API's JSON response.

**Note for later:** the `/conversation/answer` DB-write error handler currently includes
`"detail": str(e)` in its 500 response - useful for dev debugging, but leaks raw exception
text to the client and should be stripped before any public deployment (Render, month 6).

---
---

## Roadmap Generation — RAG Retrieval + Gemini, Personalized Per Student

**What was built:** `app/pipeline/roadmap_generator.py` retrieves FAISS chunks filtered to a
student's #1 ranked career path, builds a prompt combining that context with their
`conversation_signals` (goal, avoid, target_company), and calls Gemini to generate 8-12
structured roadmap steps as JSON. `app/routes/roadmap.py` exposes this as
`POST /roadmap/generate` (login-required), loading the student's latest `CareerProfile` and
persisting the result to a new `GeneratedRoadmap` table.

**Design decision - per-student generation vs. a shared roadmap per career path:**
The master doc's schema for `RoadmapSteps` (`career_path_id` FK, no `user_id`) more naturally
fits a shared, admin-authored roadmap per career path - generated once, reused by every
student on that path. But the master doc's prose (section 8's Online Pipeline) explicitly
describes the LLM generating a "personalized" roadmap per student, and the whole reason
`conversation_signals` were designed as pass-through prompt context rather than ranking
inputs was specifically so they'd shape something downstream. A shared-per-path roadmap
would make `goal`/`avoid`/`target_company` permanently unused, and would make the LLM call
itself decorative - a fixed set of 10 roadmaps could be hand-authored once without any RAG
or generation at all. Went with genuine per-student generation, which meant `RoadmapStep`
was the wrong shape for this data - same reasoning as `CareerProfile` getting its own table
instead of living on `Users`. Created `GeneratedRoadmap` instead (`user_id` FK, `career_path`,
`steps` JSON, `retrieved_chunks` JSON) rather than retrofitting `RoadmapStep`, and left
`RoadmapStep` as-is for a possible future admin-curated-fallback use case, not today's problem.

`retrieved_chunks` stores which FAISS chunks (source + similarity score, not full text)
grounded each generation - not in the original schema, added specifically to make the RAG
anti-hallucination claim ("LLM cannot recommend anything not in retrieved data")
demonstrable after the fact, not just assertable.

**Issue faced - gemini-1.5-flash and the entire google-generativeai package are fully
shut down, not just deprecated:**
First attempt to verify the Gemini API key (`genai.GenerativeModel('gemini-1.5-flash')` via
the `google-generativeai` package) failed with a 404: `models/gemini-1.5-flash is not found
... or is not supported for generateContent`, alongside a `FutureWarning` that the entire
`google-generativeai` package "will no longer be receiving updates or bug fixes."
**Root cause:** confirmed via search - Google fully shut down all Gemini 1.0 and 1.5 models
(not a soft deprecation, genuine 404 on every call), and replaced the whole legacy SDK with a
new unified package, `google-genai`, as of Nov 30, 2025. Both of these postdate when the
master doc's tech stack decision ("Gemini 1.5 Flash") was locked.
**Fix:** `pip uninstall google-generativeai`, `pip install google-genai`. Switched to
`gemini-flash-latest` rather than pinning a specific dated model name like
`gemini-3.5-flash` - deliberately, since we'd just watched a pinned model name get shut out
from under the project with real disruption; an alias tracking "current recommended flash
model" is more resilient to this happening again mid-project.
**Verification:** confirmed working with a real call through the new package before writing
any pipeline code against it. Updated the master doc's Tech Stack table (section 4) to
reflect the actual current model and SDK, with the deviation reason stated inline.

**Issue faced - a newly-registered Flask route silently didn't exist:**
After adding `roadmap_bp` to `app/__init__.py` (import + `register_blueprint`, verified
correct by direct `grep` - no duplication, no indentation error this time), a check of
`app.url_map.iter_rules()` for anything containing "roadmap" returned an empty list, with no
error anywhere.
**Root cause:** stale `__pycache__` - a gotcha this project's own `DEV_SETUP.md` already
documents from earlier work ("if model or logic changes don't seem to take effect, clear
cached bytecode"). Python was serving cached bytecode of `app/__init__.py` from before the
route was added.
**Fix:** `find . -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} +`, then re-ran
the same check - route appeared correctly. A reminder that a documented gotcha from one
feature can silently resurface on a completely unrelated one.

**Verification status - NOT end-to-end tested on this machine:** this laptop has never run
the FAISS index-build step (`rag.py`'s `build_index()`) - the index and its metadata are
gitignored, generated, machine-local data that only exists on the other laptop (per the RAG
pipeline entry above). `faiss-cpu`, `sentence-transformers`, and `pandas` had to be installed
here just to get a clean *import* of `roadmap_generator.py` - confirmed via
`app.url_map.iter_rules()` (route registered) and a plain `import` check (no missing
modules), but the actual retrieval + Gemini call + generated output has never been run for
real anywhere yet. That verification - including a first real look at what Gemini actually
produces for a real student profile - has to happen on the machine with the built index.

---
---

## Single-Machine Migration + First Real Roadmap Generation

**Decision: permanently migrate to one laptop (Aspire) instead of developing across two.**
Working across two machines had been a deliberate setup since early in the project (see
"Working Across Two Machines" above), but splitting RAG/dataset work onto a second laptop
created a real dependency: `/roadmap/generate` couldn't be tested end-to-end on the Aspire
because the FAISS index only existed on the Dell, which wasn't always physically available.
Rather than keep working around that gap, decided to consolidate everything onto the Aspire
going forward.

**Before treating the Dell as retired, ran a full safety check** (not just assumed it was
fine): `git status` (clean), `git log origin/<branch>..<branch> --oneline` on all three
branches - `feature/scaffold`, `dev`, `main` (all empty except one). Found and pushed one
real unpushed commit on `feature/scaffold` (a biography update documenting the Kaggle
downloads from a prior session) that would have been silently lost otherwise - confirming
this check was worth doing, not just a formality.

**Rebuilt the FAISS index fresh on the Aspire** rather than copying files from the Dell:
cloned roadmap.sh (`--depth` not needed in the end - full clone succeeded on retry after one
transient connection failure), re-ran `build_index()`. Produced 3,597 chunks (close to the
original 3,586 - the small difference reflects roadmap.sh's content having shifted slightly
since the original build months ago) in the same ~90 seconds as before. Re-verified retrieval
quality the same way as the original build (filtered search on Full-Stack and Cybersecurity
both returned correctly-tagged, plausible results) before trusting it for real generation.

**Re-downloaded the Kaggle datasets (SO Survey 2025 + India Jobs)** fresh on the Aspire too,
rather than transferring files from the Dell - required re-adding `KAGGLE_USERNAME`/
`KAGGLE_KEY` to this machine's `.env` (gitignored, never travels with git) and
`pip install kaggle`. Both datasets confirmed landed correctly by file size match against the
original download (survey CSV: 140,893,245 bytes, matching the original "~140MB").

## First Real End-to-End Roadmap Generation

**Issue faced - Gemini's free tier returned repeated 503 UNAVAILABLE ("high demand") errors**
on the first two real attempts to call `/roadmap/generate`. Confirmed via search this is a
known, widely-reported, ongoing issue across multiple Gemini model versions and both free and
paid tiers (not specific to this project or this API key) - some reports describe sustained
~37% failure rates over 30-day windows.
**Fix:** added `tenacity`-based retry (3 attempts, exponential backoff, 2-10s) on the primary
model (`gemini-flash-latest`), retrying only on `ServerError` (never on `ClientError`, which
won't succeed on retry regardless). Falls back to a single attempt on `gemini-2.5-flash` if
all primary retries are exhausted, only raising a clean error (surfaced as the route's
existing 502) if both models fail. Decided against auto-retry earlier in the session for
simplicity during dev, then reversed that decision once real testing showed 503s were common
enough to threaten demo reliability - a deliberate, documented change of plan, not an
oversight.

**Verified working, for the first time ever:** full flow (signup -> login -> quiz ->
conversation -> `/roadmap/generate`) via `scripts/smoke_test_roadmap.py`, using the real,
freshly-built index. Quiz ranked "AI / Machine Learning Engineering" #1; conversation signals
(`avoid: repetitive_work`, `target_company: startup`) visibly shaped the generated content -
multiple step descriptions explicitly referenced avoiding repetitive work and startup-specific
concerns, confirming these signals are doing real work in the final output, not sitting
unused. 10 grounded roadmap steps generated; `GeneratedRoadmap` row persisted and
independently verified via direct DB query (not just trusting the API response) - steps
count, `retrieved_chunks` count, and source/score of the first retrieved chunk
(`ai-engineer/introduction`, 0.699 similarity) all correct.

**Deferred, deliberately:** committing the FAISS index files to git as a demo-day safety net
(currently gitignored, regenerable, ~7.3MB total) - a conscious exception to the project's
usual "generated data doesn't belong in version control" rule, justified by demo-reliability
stakes. Not yet done - flagged for later.

---
---

## Kaggle Dataset Processing — India Jobs + SO Survey 2025

**India Jobs dataset processed into PostgreSQL** (`job_listings`, 835 rows). Salary parser
went through three real correction cycles: initial version handled ranges and "Not
specified" but missed several real formats found only by running against the full dataset
(flat single numbers, "Up to X", decimals) - fixed after inspecting actual unparsed rows
rather than trusting the small hand-picked test sample. Added a plausibility ceiling
(₹18L/year) after finding "Pharma Freshers" and "HR Trainee" listings with implausible
36L/33L annual figures - almost certainly source data where "a month" was mislabeled on
what should have been an annual figure. Flagged rather than discarded
(`salary_suspicious` boolean), consistent with the project's tag-don't-filter principle.

Career-path tagging via keyword matching against job titles (not spaCy/NER - titles are too
short for NLP to add value over simple matching, and NER is deliberately reserved for
Phase 2's full-resume parsing). First pass only tagged 35/835 rows; scanning the untagged
rows specifically for tech-adjacent words surfaced a real gap - generic titles like
"Software Engineer," "Programmer," "Trainee Software Engineer" had no matching keyword at
all. Second pass reached 64/835. QA/Testing roles (a large, frequently-recurring category)
deliberately left untagged - no matching career path exists in the quiz's current 10, and
force-fitting them into an ill-fitting bucket (e.g. Backend) would be worse than leaving
them unmapped.

**SO Survey 2025 processed into PostgreSQL** (`survey_respondents`, 2,547 rows), filtered to
India respondents only (5.2% of ~49K total) - a deliberate choice consistent with the
project's explicit tier-2/tier-3 Indian college focus, not a data-availability compromise.
`DevType` mapped to career paths via an exact dictionary (not keyword matching - DevType is
a controlled-vocabulary survey field, so exact mapping is both possible and more accurate).
`Student`, `Architect`, and management/business DevType values deliberately left unmapped,
same reasoning as India Jobs' QA gap. `ConvertedCompYearly` used directly (SO's own
USD-normalized figure) rather than re-parsing `CompTotal`/`Currency` - avoided repeating the
India Jobs salary-parsing effort where it wasn't necessary.

## FAISS Chunk Generation from Survey Skill Data

**Decision reversed mid-session: TF-IDF tested and rejected in favor of plain frequency.**
The master doc names TF-IDF as Phase 1's intended skill-ranking technique, so it was tried
first: computed term-frequency × inverse-document-frequency per skill per career path.
Result was worse than plain frequency, not better - "Dart" scored as the #1 skill for
Full-Stack, Frontend, AND Research (career paths that barely use it), while Cybersecurity's
genuinely common skills (Python, Java, JavaScript) scored 0.0. Root cause: TF-IDF's IDF term
explodes for rare skills when there are very few "documents" (only 10 career paths here) -
a skill used in just 1-2 paths gets its low real frequency massively amplified, drowning out
skills that are genuinely common within a path but also appear elsewhere. TF-IDF needs many
documents to behave well; 10 is too few. Reverted to plain frequency, which had already been
validated as producing sane results (Python dominant in AI/ML and Data Science, Kotlin/Dart
correctly for Mobile, C++/Assembly for Game Dev) before TF-IDF was even tried.

Generated one FAISS chunk per career path (10 total) - natural-language summaries of the top
5 languages, databases, platforms, and frameworks among Indian respondents in that path,
matching the same descriptive-sentence shape as the roadmap.sh chunks (not one chunk per
individual skill mention, which would produce tens of thousands of low-value, near-duplicate,
barely-embeddable single-word chunks). Appended to the existing FAISS index (3,597 -> 3,607
chunks) via direct `index.add()` on the loaded index, reusing `embedder.py`/`rag.py`'s
existing, tested normalization logic rather than reimplementing anything.

**Verified:** a targeted retrieval query correctly surfaced the new Mobile App Development
survey chunk as the top result (0.634 similarity) when filtered to that career path. Reran
`scripts/smoke_test_roadmap.py` against the enlarged index - full pipeline still produced a
clean, grounded roadmap with no code changes needed, confirming `rag.py`'s `search()`
abstraction transparently benefits from additional indexed sources.

---
---

## YouTube Resource Integration — Phase 1 Complete

**What was built:** `app/pipeline/youtube_resources.py` fetches one relevant video per
roadmap step via YouTube Data API v3, using `f"{step_title} tutorial"` as the search query.
`POST /roadmap/<id>/resources` attaches results to an existing `GeneratedRoadmap` - kept
deliberately separate from `/roadmap/generate` itself (same reasoning as why roadmap
generation is separate from conversation completion: an external API's own latency/failure
mode shouldn't be able to jeopardize an already-successful save).

Per-video failures never raise - `fetch_video_for_step` catches `HttpError` and returns
`None` rather than crashing the whole batch, since one bad search shouldn't prevent
resourcing the other 9 steps. Scoped by `user_id` in the query (`filter_by(id=roadmap_id,
user_id=current_user.id)`) so a student can't attach resources to, or discover, another
student's roadmap by guessing IDs.

**Issue faced - indentation bug placing a route decorator inside the previous function:**
`@roadmap_bp.route("/roadmap/<int:roadmap_id>/resources"...)` landed with 4 leading spaces,
inside `generate()`'s body rather than at module level. Same class of bug as the earlier
`quiz.py` duplication and `roadmap_generator.py` misplaced try/except - fixed via full-file
heredoc rewrite rather than a surgical edit, same reliable approach used before. Cleared
`__pycache__` proactively this time before re-testing, rather than only after hitting the
stale-cache symptom again.

**Gap found and fixed - `/roadmap/generate`'s response was missing the roadmap's own DB id.**
A real client needs this to call `/roadmap/<id>/resources` next, but the original response
only included `career_path` and `steps`. Fixed with a small Python patch script using an
explicit `assert content.count(old) == 1` guard before replacing - given two prior manual-
edit mistakes this session, preferred a change that fails loudly if the target text doesn't
match exactly once, over a blind `sed` or manual paste.

**Verified end-to-end twice** via `scripts/smoke_test_youtube.py` (full signup -> quiz ->
conversation -> roadmap generation -> resource attachment): all 10 steps received a
genuine, topically relevant video both runs, results independently confirmed via direct DB
query (not just the API response) - `resource` key present and correctly structured in the
persisted `GeneratedRoadmap.steps` JSON.

**This completes the master doc's entire Phase 1 pipeline for the first time** - quiz,
conversation, career profile, FAISS retrieval (roadmap.sh + SO Survey chunks), Gemini
generation with retry/fallback, and YouTube resourcing, all real, tested, and connected
end to end.

---
---

## Phase 2 — Resume Skill Extraction & Gap Analysis (in progress)

**Issue faced - spaCy's generic NER is unreliable for skill extraction.**
The master doc's plan ("spaCy NER for skill extraction") was tested directly before writing
any pipeline code: `en_core_web_sm`'s statistical NER model misclassified "Python, React" as
`ORG` and "PostgreSQL" as `GPE` (a geopolitical entity) - it has no concept of "programming
language" as an entity category, since that's not one of spaCy's standard NER labels.
**Fix:** switched to spaCy's `PhraseMatcher` (a rule-based, not statistical, matching
component) seeded with a real, already-validated vocabulary - the 141 unique skills already
present across `SurveyRespondent.languages/databases/platforms/webframes`, rather than a
hand-invented list. Verified directly against the exact sentence that broke generic NER: all
four real skills correctly extracted, no false positives. Still genuinely "spaCy" per the
master doc's tech stack (uses spaCy's tokenizer/vocab under the hood), just its rule-based
matching rather than its unreliable statistical model.

**Added a small alias layer** (`skill_aliases.py`) for common abbreviations resumes actually
use (AWS, JS, K8s, Postgres...) that the SO Survey vocabulary only stores under the full
name ("Amazon Web Services (AWS)"). Matched with explicit word-boundary regex
(`\bAWS\b`) after confirming the risk was real - without word boundaries, "js" would
false-positive inside "objects" or "projects". Deliberately left "ml" unaliased (too
ambiguous) rather than silently omitting it.

**Design decision - "required skills" needed real aggregate data, not a hand-curated list.**
Reused the top-skills-per-career-path aggregation already built for FAISS chunk generation
(`so_survey_chunks.py`) as the source of "required skills" for a career path - refactored
the shared logic into `skill_aggregation.py` so both modules import one implementation
rather than duplicating it. Re-verified `so_survey_chunks.py` produced byte-identical output
after the refactor before trusting it.

**Issue faced - naive top-N-per-category produced a noisy, unusable gap list.**
Initial version took the top 10 skills independently from each of 4 categories
(languages/databases/platforms/webframes), for up to 40 "required" skills. Tested against a
real resume and found the gap list included 7 different databases (MySQL, PostgreSQL,
MongoDB, MariaDB, SQLite, Microsoft SQL Server, Redis) and 5 different backend frameworks as
all simultaneously "missing" - technically correct (each genuinely was in some category's
top 10) but not actionable, since these are mostly alternatives to each other, not a real
combined checklist.
**Fix:** `get_required_skills` now ranks all skills across all 4 categories together by
combined real frequency, keeping only the overall top 10 - a skill has to be genuinely
common among real respondents in that path to count as "required", regardless of which
category it happens to belong to. Retested against the same resume: required list dropped
from 38 items to a coherent 10, gap list (`HTML/CSS, MySQL, SQL, TypeScript, npm`) reads as
something a student could actually act on.

**Verified end-to-end** on a generated test PDF (`fpdf2`, not committed - test artifact
only) with known, deliberate content: all 8 real skills correctly extracted (including the
AWS alias), matched/missing split correctly against Full-Stack's real required-skills list.

**Still to build:** PDF upload route, `Resumes`/`SkillGap` table persistence, salary/job
matching (reusing `JobListing`), one LLM call for resume feedback + 30-day action plan, and
the lightweight ATS-friendliness score discussed as a natural Phase 2 extension (deferred
until the core pipeline is fully wired up).

---
---

## Resume Upload Route — Phase 2 Core Flow Complete

**What was built:** `POST /resume/upload` (login-required) - accepts a multipart PDF upload,
validates it (extension check, 5MB `MAX_CONTENT_LENGTH` ceiling set in `config.py`), saves it
under a gitignored `uploads/resumes/` folder with a `secure_filename`-sanitized, UUID-prefixed
name (avoids both path-traversal risk and filename collisions between students/repeated
uploads), runs it through `analyze_resume()` against the student's current `CareerProfile`'s
#1 ranked career path, and persists both a `Resume` row (extracted skills) and a `SkillGap`
row (missing skills, target role).

**Deliberately left for later, not faked:** `Resume.ai_feedback` and `SkillGap.salary_range`
both saved as `None` - the LLM feedback call and salary-matching logic (reusing `JobListing`/
`SurveyRespondent` data) are real, separate pieces of work not yet built, and populating them
with placeholder or approximated data now would misrepresent what's actually done.

**Known, deliberate simplification:** file validation checks the extension only (`.pdf`), not
the actual file signature/magic bytes. A more rigorous version would verify the file's real
content matches its claimed type rather than trusting the extension - flagged as a
reasonable v1 gap, not a silent oversight.

**Issue faced - blueprint registration step was skipped on the first attempt.** Created
`resume.py` but the corresponding import/registration in `app/__init__.py` was never
actually added, despite being reported as done. Caught by asking to see the file's real
contents before testing anything - by now a standard practice in this project, after
multiple prior sessions where a described edit didn't match what was actually on disk.

**Verified end-to-end** via `scripts/smoke_test_resume.py`: full signup -> quiz -> conversation
-> a real multipart file upload through Flask's test client (not just calling
`analyze_resume()` directly, as earlier isolated testing had done) -> correct skill
extraction, correct gap against the real ranked career path, both DB rows independently
confirmed via direct query.

**Still to build for Phase 2:** LLM resume feedback + 30-day action plan (one Gemini call,
reusing the retry/fallback pattern from roadmap generation), salary/job matching against
`JobListing` and `SurveyRespondent`, and the lightweight ATS-friendliness score.

---
---

## Resume LLM Feedback + Shared Gemini Client

**Refactor: extracted retry/fallback logic into `gemini_client.py`**, shared between
`roadmap_generator.py` and the new `resume_feedback.py`, rather than duplicating the same
tenacity retry decorator and fallback-model logic a second time. Re-ran
`scripts/smoke_test_roadmap.py` immediately after the refactor - full roadmap generation
still worked identically, confirming the extraction didn't silently break already-committed,
working code.

**What was built:** `app/pipeline/resume_feedback.py` generates plain-text resume feedback
(3-5 line-level suggestions, a 30-day action plan, keyword suggestions) via one Gemini call,
grounded explicitly in the student's real resume text and real computed skill gap - the
prompt is told not to invent experience, projects, or skills the student didn't mention, same
anti-hallucination principle as roadmap generation. Wired into `/resume/upload`: if Gemini
fails (even after retry+fallback), the upload still succeeds and saves the skill
analysis - only `ai_feedback` is left null - since the skill extraction and gap analysis
don't depend on Gemini at all, and a transient LLM outage shouldn't cost a student their
entire analysis over the one optional piece.

**Verified end-to-end** through the real `/resume/upload` HTTP route (not an isolated
function call): genuinely grounded, well-structured feedback referencing the actual missing
skills (SQL, MySQL, Pip, HTML/CSS), a coherent week-by-week action plan matching them,
correctly persisted and returned in the response. One minor, non-blocking cosmetic issue
noted: keyword suggestions sometimes split "HTML/CSS" into three near-duplicate entries
(HTML/CSS, HTML, CSS) - acceptable, not worth engineering around right now.

**Phase 2 core flow is now fully complete:** upload -> extract -> gap analysis -> LLM
feedback -> persistence, all real and verified. Remaining: salary/job matching (reusing
`JobListing`/`SurveyRespondent`) and the lightweight ATS-friendliness score.

---
---

## Salary & Job Matching — Phase 2 Complete

**Design decision - kept India Jobs and SO Survey salary figures deliberately separate,
not merged into one number.** Initially considered converting SO Survey's USD
(`ConvertedCompYearly`) to INR and averaging with India Jobs' native INR figures into one
combined salary estimate. Reconsidered: the two sources represent genuinely different
populations, not just different currencies - India Jobs is real job *postings* (skews
entry-level/fresher, matching this project's actual audience), SO Survey is
*self-reported compensation from working developers* (skews toward more experience).
Averaging them would silently blend "what a fresher job pays" with "what an experienced
developer earns" into one misleading figure. Landed on: report both, clearly labeled and
separate, with SO Survey's USD also shown as an approximate INR conversion (hardcoded rate,
explicitly flagged as approximate and subject to staleness - same risk class as any
hardcoded external figure in this project, per the earlier Gemini model-name lesson).

**Issue faced - serious outliers in SO Survey compensation data.** First test against a
career path with rich data (Full-Stack) returned a survey salary range of \$1 to
\$9,531,653/year - obviously corrupted self-reported values, not real salaries (no validation
exists on a voluntary survey field). Checked the real distribution via percentiles before
picking a fix: 1st percentile \$58, 5th percentile \$1,162, median \$17,203, 95th percentile
\$92,992, 99th percentile \$319,659, then a 30x jump to the \$9.5M max - confirming genuine,
severe outliers at both tails, not just a naturally wide but real distribution.
**Fix:** trim to the 1st-99th percentile of the full dataset (computed once across all
respondents, not per-career-path, which would have too few points to percentile meaningfully)
before computing any per-path aggregate. Re-verified: min/max moved to a sane \$105-\$319,659
range, count dropped only 9/352 (just the genuine outliers), median stayed identical -
confirming the trim removed only corruption, not real data.

**What was built:** `app/pipeline/salary_matching.py` returns job-posting stats (INR, from
`JobListing`, excluding rows already flagged `salary_suspicious`), survey-respondent stats
(USD + approximate INR, outlier-trimmed), and sample real job listings for a career path.
`format_salary_range_summary()` compresses this into a short string
(e.g. "Postings: Rs126K-380K/yr | Survey (approx): Rs9K-27970K/yr") for
`SkillGap.salary_range`'s `db.String(80)` column; the full structured data is included
separately in the `/resume/upload` API response for a richer frontend display. Used `Rs`
rather than the rupee symbol for DB-column safety, and `K`-suffixed thousands to fit the
80-char limit.

**Verified end-to-end** through the real `/resume/upload` route: confirmed both the
`None`-handling path (a career path with data in only one source, tested earlier with
Cloud/DevOps) and the full dual-source path (both Full-Stack and, in the final route test,
AI/ML Engineering - which turned out to have real India Jobs postings too, checked directly
rather than assumed).

**Phase 2 is now fully complete**: upload, skill extraction, gap analysis, LLM feedback, and
salary/job matching, all real, tested, and wired into one route. Remaining: the lightweight
ATS-friendliness score, discussed as a natural extension once core extraction existed.

---
---

## Lightweight ATS Score — Phase 2 Fully Complete

**What was built:** `app/pipeline/ats_score.py` computes a 0-100 ATS-friendliness score
from signals already available in Phase 2's pipeline - extraction quality, standard section
header presence, contact info detection, and real skill-keyword density against the target
role's required skills. Deliberately NOT a deep PDF layout/structure analysis (detecting
multi-column layouts or table linearization would need far more than `pdfplumber`'s basic
text extraction) - scoped as the lightweight version discussed and deferred earlier, not
the "deeper version" that was explicitly set aside for a separate conversation.

**Issue faced - a single threshold conflated two genuinely different problems.** First
version used one character-count threshold (500) to detect "this PDF might be image-based
and unparseable." Tested against a real, short-but-readable minimal resume and got a
misleading result: the resume scored as if it might be a broken/image-based PDF, when the
actual issue was just thin content - a student reading that message would troubleshoot the
wrong problem entirely (re-exporting the PDF wouldn't have helped; adding more content
would have).
**Fix:** split into two separate thresholds with honest, distinct messages -
`NEAR_ZERO_CHARS` (50, true extraction failure) vs. `SPARSE_CHARS` (500, real but thin
content), each with its own accurate explanation and appropriately different point
deduction (-40 vs -15). Re-tested against the same minimal resume: correct message, smaller
deduction, no longer implying the file itself was the problem.

**Verified** against two deliberately different test resumes - a minimal one (name, one
skills line, no real structure, no contact info: scored 40, every deduction individually
correct and explainable) and a complete one (name, contact info, summary, experience,
skills, education, projects: scored 100) - through the real `/resume/upload` route, not
just the isolated function.

**Phase 2 is now fully complete**: PDF upload, skill extraction (spaCy PhraseMatcher over
real SO Survey vocabulary), gap analysis, LLM feedback with graceful degradation, dual-source
salary/job matching with outlier correction, and ATS scoring - every piece built, tested
against real and edge-case data, and wired into one working route.

---
---

## Frontend Build-Out — Navigation, Dashboard, All Core Pages

**What was built, via a separate Claude Code session:** copied the whole project folder
(including `.git`) so Claude Code could work with full write access while the original
folder stayed untouched as a backup. Built: the missing pages (conversation, career
results, roadmap display with YouTube resources, resume upload, resume results,
dashboard), wired real navigation across the entire user journey (landing -> signup ->
login -> quiz -> conversation -> career results -> roadmap -> resume upload -> resume
results) where previously every page existed in isolation with no links or redirects
between them, and updated `layout.html`'s navbar to link to everything that now exists.

**Password validation added, enforced in both places:** minimum 8 characters, at least one
uppercase letter, one lowercase letter, one number, one special character. Backend
(`app/routes/auth.py`) is the real enforcement point - explicit ASCII character sets
(`string.ascii_uppercase`/`ascii_lowercase`/`digits`/`punctuation`) rather than vague
heuristics like `.isupper()`, specifically so the frontend mirror check can't silently
disagree with the backend on an edge case. Also fixed a pre-existing gap while there:
`request.get_json(silent=True)` with a dict fallback, so malformed/missing JSON on
`/signup` returns a clean 400 instead of crashing with an unhandled 500.

**"Resume where you left off" dashboard behavior:** a returning user with an existing
`CareerProfile`/`GeneratedRoadmap`/`Resume` sees their existing results by default,
with explicit "retake"/"start fresh" options preserved rather than forced.

**Optional free-text preference field** added to the end of the conversation step -
stored in `CareerProfile.conversation_signals` under `additional_notes`, wired into the
roadmap generation prompt as explicitly labeled untrusted input (JSON-escaped, told to the
model as background only, never instructions) - real prompt-injection defense for a
free-text-into-LLM-prompt feature, unprompted.

**Two real backend bugs found and fixed along the way, outside the stated frontend scope:**
1. The Gemini fallback model (`gemini-2.5-flash`, picked earlier this project) had itself
   been retired and was returning 404 - the exact same failure mode as the original
   `gemini-1.5-flash` shutdown. Switched to `gemini-flash-lite-latest` (an alias, not a
   pinned name, same lesson as before).
2. Widened the fallback trigger to include 429 (quota) errors, not just 503s - reasoning:
   free-tier quota is tracked per model, so a 429 on the primary model says nothing about
   whether the fallback model would also fail.

**Verification approach - different from backend work, and deliberately so:** rather than
reading every diff line-by-line before trusting it, verification here was primarily
Joel personally clicking through the real, running app in a browser - the right method for
frontend behavior, which line-by-line code reading can't actually confirm. Diffs for files
outside the stated frontend scope (`gemini_client.py`, `roadmap_generator.py`,
`app/routes/auth.py`) were still read and understood before committing, since those touch
security- and correctness-critical logic that a "does it look right in the browser" check
wouldn't catch.

**Commit process:** the copy folder still had the original repo's full git history and
remote (`.git` was copied along with the files), so it wasn't a fork needing a merge - just
a second working directory of the same repo. Committed and pushed directly from the copy,
then fast-forward-pulled into the original folder to bring both back in sync, with the
original kept as the one true working copy going forward.

---
---

## Standalone Phases — Design Decision (manual picker implemented)

**Issue found:** Resume Analyzer and Roadmap Generation both hard-required an existing
CareerProfile (quiz + conversation completed first), so the three phases couldn't actually
be used independently/in parallel, contradicting the intended product design.

**Decision:** when no CareerProfile exists, ask the user to manually pick a target career
path before analyzing/generating, rather than blocking entirely. The manual pick is
deliberately a one-off, per-request choice — it does NOT create or overwrite a
CareerProfile row, since that table's meaning is specifically "the ranked output of the
quiz," not a single guess. The quiz remains the only path to a real ranked profile.
Schema-wise this required no migration: GeneratedRoadmap.career_path and
SkillGap.target_role were already plain strings, not foreign keys to CareerProfile.

Also identified: new users were being redirected into the quiz after login/signup, which
conflicts with the three-phases-run-independently design — should land on the home page
instead.

Update: the manual career-path picker is now implemented (resolve_target_career_path in app/routes/_util.py). Not yet verified: whether new users now land on the home page instead of the quiz after login/signup.

---

## Phase 3 Stage 1 — Skill DNA Map (Static Structure, No Code Execution Yet)

**What was built, via Claude Code:** the static Skill DNA Map — DSA topics as nodes in a
prerequisite graph, without code submission/execution yet (deliberately deferred to Stage 2,
gated on Piston being set up).

- Seeded ~20-30 canonical, well-established DSA problems (Two Sum, Reverse Linked List,
  Valid Parentheses, Binary Search, etc.) with known-correct test cases rather than having
  the LLM invent problems or test cases from scratch - correctness-critical data isn't
  something an LLM call should originate. Tagged to `DSANode` topics with prerequisite
  relationships reflecting standard DSA learning order (e.g. Linked Lists requires Arrays).
- Topological-sort-based prerequisite logic: a node stays locked until its prerequisites
  reach a mastery threshold.
- An endpoint returning per-node state (locked/unlocked/mastery level) for the current
  user's graph, used to render the D3.js map.
- Career-contextualized problem framing via one Gemini call (reusing `gemini_client.py`):
  the LLM rewrites only the narrative framing of a seeded problem for the student's career
  path (e.g. "your inventory API has a bug in hash map logic" for a Full-Stack student) -
  the underlying problem and its verified test cases are never regenerated or altered by
  the LLM, only the framing text around them.
- Frontend: the Skill DNA Map as an interactive D3.js directed graph - node brightness
  reflects mastery, locked nodes are visually dimmed, clicking an unlocked node shows its
  problem(s) with the career-framed narrative. No submit/run control yet.

**Deliberately excluded from this pass:** Piston integration, code submission/execution,
and the adaptive bandit map - all depend on infrastructure (self-hosted Piston) that isn't
set up yet, and the master doc's own design has the bandit map depend on complete static-map
behavioral data anyway, so it couldn't come first regardless.

**Verification note:** tested and confirmed working in-browser (node lock/unlock states,
prerequisite blocking, and career-framed problem rewrites all checked per the task's
request). Unlike prior entries in this document, this one was not independently reviewed
diff-by-diff before being written up - flagged here for anyone reading back later.

**Still to build for Phase 3:** Stage 2 (Piston setup, code submission/execution, XP and
mastery updates from real solves, streak tracking, hint system) and Stage 3 (the adaptive
bandit map - weakness scoring from behavioral signals, targeted problem spawning), per the
master doc's two-stage design.


---
---
## Knowledge Base v2 — Structured Chunks, Diverse Retrieval, Re-runnable Rebuild

**What was built:** roadmap_kb_processor.py chunks now also carry title,
node_id, folder and resources ([{type, title, url}] parsed from roadmap.sh's
"- [@type@Title](url)" lines); existing text/career_paths/source keys are
unchanged. embedder.py embeds "title. text" when a title exists. rag.py
gained search_diverse() (multi-query, dedupe by source, per-folder cap) and
list_topics(); search()/load_index()/build_index() are unchanged.
scripts/rebuild_kb.py is new and committed: backs up the index to
data/processed/backup/ (gitignored), rebuilds, appends the SO Survey chunks
and asserts the total (3,607 = 3,597 roadmap.sh + 10 survey).

**Findings from inspecting the roadmap.sh clone:**
- The clone is a content-only mirror: no graph/JSON ordering file exists,
  so within-roadmap order cannot be recovered from it.
- 0 of 3,599 files contain H2/H3 headers; every file is already one topic,
  so no re-chunking was needed.
- 92.6% of files have a curated resources block that _clean_markdown used
  to discard. It holds 2,008 video links (99.3% YouTube), 1,800 official
  links and 175 course links.
- Project-idea content exists only in full-stack's 13 "checkpoint" files.
- Course links are too sparse for a per-step course feature (coursera.org
  32, freecodecamp.org 4, udemy.com 1, edx.org 1). Two suspicious domains
  (ransomleak.com 22, inter-git.com 18) appear among "course" links, so the
  video/resource resolver must use a domain allowlist and not trust tags.
- Share of chunks with at least one YouTube video is lowest for Mobile App
  Development (21.1%) and Game Development (27.7%); Full-Stack is 37.2%.
- A general web scraper (Agent-Reach) was considered and rejected: it does
  not cover course sites and conflicts with the locked no-scraping decision.

**Issues faced:** no committed script existed for building the index or the
survey chunks (both were done in a REPL), which is why rebuild_kb.py was
written. The roadmap_generator docstring claiming the FAISS files are
gitignored was stale: they are tracked via explicit un-ignore rules (the
demo-day safety-net exception). Scripts run from Git Bash fail with
ModuleNotFoundError unless PYTHONPATH=. is set.

**Verified:** search() result shape, react/hooks and sql/acid resources in
the loaded metadata, search_diverse() returning 30 distinct sources with no
folder over the cap, list_topics() = 514 for Full-Stack, total chunk count,
and scripts/smoke_test_roadmap.py end to end.

---
---
## Roadmap Generation v2 — Grounded Subtopics, Projects, and Phases

**Step schema:** each step now has title, description, subtopics (real topic
titles), topic_refs (node_ids from the path's topic inventory) and projects
(title, description, difficulty, grounded). Retrieval builds 4-6 queries
from the career path and conversation signals, calls search_diverse(), and
gives Gemini the full list_topics() inventory so it can only reference real
topics. topic_refs are validated against the inventory (invalid ones are
dropped with a warning). The additional_notes untrusted-input handling and
the retrieved_chunks audit are kept.

**Projects decision:** Full-Stack projects are adapted from the 13 checkpoint
files ("grounded": true). Every other path gets LLM-suggested projects marked
"grounded": false. This is a deliberate, documented exception to the
anti-hallucination rule, to be revisited later.

**Bugs found and fixed:** (1) SO Survey chunks have no node_id/title, which
raised KeyError when building the prompt. (2) Query attribution in the audit
used top_k=len(chunks), which made every query match nearly every chunk; it
now uses the same budget as search_diverse. (3) A Full-Stack step's subtopics
contained raw node_ids instead of titles; a post-generation validation now
replaces them with real titles.

**Phases:** the flat 8-12 step cap could not cover a path (271-514 topics),
so generation was split into phases, one Gemini call per phase (about 5
calls per roadmap). Each step gets a global_step_index for progress tracking
later. The first version partitioned topics by keywords in titles. Real
output showed impossible ordering (ML evaluation before Python syntax) and
duplicates (two AI-agents steps). Fix: partition by roadmap.sh folder, one
planning call orders the folders (validated against the real folder names),
duplicate node_ids are removed before grouping (python's copy preferred over
machine-learning's), and each phase receives an exclusion list of topics and
titles already used. Read by eye afterwards: AI/ML now runs Python -> Machine
Learning -> AI Engineer, and Full-Stack runs git-github -> javascript ->
nodejs -> react -> full-stack.

**youtube_resources.py** now handles both the phased shape and old flat
roadmaps; it still fetches one video per step, and its quota note now says a
full roadmap costs roughly 2,000 units (about 5 roadmaps/day).

**Not yet verified:** phases 4-5 of the AI/ML output; topic_ref coverage
percentage against each path's inventory; a grep confirming each duplicate
node_id appears once per roadmap (the investigation reported 7 duplicates
but its breakdown of 4 + 1 + 6 did not add up, so recount); a per-phase check
for raw node_ids in subtopics; and whether the redesigned roadmap page
renders phased and old flat roadmaps correctly in the browser. Known
weaknesses: videos still come from a title search, so some are wrong (a C++
video for a Python step, a Python video for a JavaScript step, an Angular
video for React routing); and Full-Stack's Phase 1 is mostly GitHub feature
topics (Education pack, Gists, Codespaces).

---
---
## Career Path Restructuring — Decisions (implemented; see Career Paths v2 below)

**Target list (15):** Full-Stack Development, AI Engineering, Machine
Learning Engineering, Data Science, Data Analytics, Cybersecurity, Mobile App
Development, Game Development, Backend Engineering, UI/UX Design, Frontend
Development, Cloud Engineering, DevOps, QA & Test Automation, Data
Engineering. Research / Advanced Computing is removed. AI/ML, Data
Science/Analytics, UI/UX+Frontend and Cloud/DevOps are split; the two
Full-Stack and Backend labels are shortened; QA and Data Engineering are new.
SRE was rejected as a third slice of the Cloud/DevOps content.

**Findings from the read-only investigation:** every target path has at least
146 KB chunks (QA is smallest). By its own table, 7 paths have under 30 SO
Survey respondents (UI/UX Design 8, Cybersecurity 12, Game Development 14,
Cloud Engineering 14, AI Engineering 22, QA 22, Data Analytics 25), and no
survey role separates AI engineers from ML engineers. The India Jobs data
cannot ground any split (0-6 title matches per pair) and has no
data-engineering titles. The quiz gave AI/ML 19 of 40 option signals and
Cloud/DevOps only 5. Every existing database row looks like test data (88% of
career profiles and 68% of roadmaps were AI/ML, and nothing says which new
path they would become).

**Decisions:**
- Folder mapping: Full-Stack: full-stack, javascript, react, nodejs,
  git-github. AI Engineering: ai-engineer, ai-agents, prompt-engineering,
  ai-red-teaming, python. Machine Learning Engineering: machine-learning,
  mlops, python. Data Science: python-data-analysis, sql, ai-data-scientist,
  machine-learning. Data Analytics: data-analyst, bi-analyst, power-bi, sql.
  Cybersecurity: cyber-security, devsecops. Mobile: android, ios,
  react-native. Game: game-developer, cpp. Backend Engineering: backend, sql,
  system-design. UI/UX Design: ux-design, design-system, product-design.
  Frontend: frontend, html, css, javascript, typescript, react, nextjs (vue
  and angular dropped as alternatives to React). Cloud Engineering: aws,
  docker, kubernetes, terraform. DevOps: devops, docker, kubernetes, linux.
  QA & Test Automation: python, sql, git-github, api-design, qa. Data
  Engineering: data-engineer, sql, python. ai-product-builder is left out
  until its titles have been reviewed.
- Thin survey data: show whatever data exists. Showing the respondent count
  next to salary and skill figures was proposed but not yet decided.
- Existing derived rows (career profiles, roadmaps, skill gaps, DSA framings)
  are disposable test data: back up with pg_dump, clear, and reseed. No
  migration for the AI/ML rows.

**Staged plan:** (1) central career_path_registry.py, renames, and an interim
quiz mapping (old signals go to both halves of each split; QA and Data
Engineering have no signals and stay reachable through the manual picker);
(2) backup, clear test rows, reseed the career_paths table and DSA node tags;
(3) rebuild the KB, write re-runnable survey/jobs reprocessing scripts,
replace the hardcoded "== 10" survey-chunk assertion in rebuild_kb.py with
the real path count; (4) generate and check roadmaps for the new paths;
(5) redesign the quiz so each similar pair has a question that separates it.
Until stage 5, paired paths tie exactly in the quiz.

**Known limitation:** because each folder becomes one phase, Cybersecurity
and Game Development have only two phases each (Cybersecurity's 302-topic
folder is a single phase). Revisit with per-folder step caps or topic
priority.

---
---
## Git Housekeeping — Diverged Branch After Working in Two Folders

**Issue faced:** pushing feature/conversation-engine was rejected. GitHub had
two biography-only commits that were most likely pushed from the other
project folder. **Fix:** git fetch, compare with git log HEAD..origin/... and
the reverse, git show --stat to confirm the remote commits touched only docs,
then merge (not rebase). The one conflict, in this file, was both sides
inserting text at the same spot; a script that asserted its assumptions
before writing kept both blocks. git merge --abort was the fallback. Lessons:
work from one folder, fetch before pushing, use git --no-pager to stop the
pager swallowing pasted input, and append to .gitignore with printf so the
new line does not glue onto the last one. .claude/ is now gitignored.

---
---
## Career Paths v2 — Registry, 15 Paths, Deeper Roadmaps

**What was built:** the "decisions" entry above was implemented in stages (commits
dd58336, 0ee3202, 415f09a, 3c4bcf8, 07f1479, b6577c3, b782d44).
- **Stage 1** added `app/pipeline/career_path_registry.py`, the single source of
  truth for the 15 paths: for each, its roadmap.sh knowledge-base folders, its
  "supporting" folders (fundamentals tooling such as python/sql/git-github), and
  the SO Survey DevType values that count as a respondent for it. Every module
  that used its own copy of the path list (quiz data, seed data, roadmap
  generator, KB processor) now imports from it. The old 10 were renamed or
  split (Full-Stack and Backend renamed; AI/ML, Data Science/Analytics,
  UI/UX+Frontend and Cloud/DevOps split) and QA & Test Automation and Data
  Engineering were added. Research / Advanced Computing was removed entirely.
- **Stage 2** tagged the DSA nodes for the two new paths and reseeded the 15
  `career_paths` rows (test data was cleared first).
- **Stage 3** moved survey queries to DevType via the registry
  (`survey_queries.py`), added `scripts/relabel_job_listings.py` (maps stored
  `job_listings.career_paths` from the old 10 names to the new 15 and tags
  QA-flavoured titles; dry-run by default, `--apply` writes, idempotent) and made
  `rebuild_kb.py` use the path count instead of a hardcoded 10. The KB was rebuilt
  to 5,100 roadmap.sh chunks plus 15 survey chunks.
- **Stage 4** (roadmap depth): step targets now scale with a folder's topic count
  (denser for a path's primary folders than its supporting ones); topics a step
  does not cite are assigned deterministically to their nearest step as
  `more_topics` (capacity-capped), which gives 100% coverage of the phase's
  inventory; phases get curated display names; subtopics are derived from
  `topic_refs` rather than trusted from the model; and `gemini_client` gained an
  explicit output-token limit and a JSON mode (the default call is unchanged).
  `scripts/inspect_roadmap.py` was added as a read-only report (folder
  composition, coverage, duplicates, node_id leaks) around one real generation.

**Why:** the old 10-path list could not express roles the job data and the
roadmap.sh content actually distinguish, and the same list was copied in several
places, so a rename meant editing all of them.

**Issues faced and root causes:** a phase's Gemini response could be cut off
mid-JSON, so the generator now retries once with the step target reduced to
two-thirds (visible in `roadmap_generator.py`). A DevType can legitimately map to
two paths ("AI/ML engineer" counts for both AI Engineering and Machine Learning
Engineering because the survey has no finer split), so that overlap is
deliberate. Other issues: no issue recorded.

**How verified:** `inspect_roadmap.py` runs against real generations (its report
is the evidence for the coverage claim), `relabel_job_listings.py` prints
before/after tag counts and every QA-matched title for review before anything is
written, and `smoke_test_dsa.py` was updated for the renamed paths.

---
---
## KB-First Video Resolver

**What was built:** `app/pipeline/youtube_resources.py` was rewritten (commit
358ec61). For a phased step, videos and resources are resolved first from the
KB's own per-topic `resources` metadata, with no network call. Videos are picked
round-robin across the step's topics (`topic_refs` first, then `more_topics`),
deduped by video id, 3-4 per step (`MIN_VIDEOS`/`MAX_VIDEOS`). Official then
course links become up to 4 "resources" per step. Only a step still short of 3
videos triggers a YouTube search, capped at 12 searches per roadmap
(`MAX_FALLBACK_SEARCHES`). The roadmap JSON gained `videos`
(`source: "roadmap.sh" | "youtube_search"`) and `resources`; the old single
`resource` key is kept for pages that predate it.

**Why:** the first design spent one 100-unit YouTube search per step, so a
roadmap cost about 2,000 of the 10,000 daily units, and title search returned
wrong videos (a C++ video for a Python step, an Angular video for React routing,
noted in the Roadmap v2 entry). The KB already carries curated links.

**Issues faced and root causes:** (1) only exact watch / youtu.be / embed links
with an 11-character id are accepted; playlists, channels, non-https and
malformed URLs (one real case: a duplicated `?v=` query string) are dropped and
counted by reason. (2) A KB audit found two domains used only for templated,
repeated "course" titles across unrelated topics (`inter-git.com`,
`ransomleak.com`), now in `BLOCKED_DOMAINS`. (3) Folder ordering and subtopic
derivation were adjusted in the same commit (JSON mode for the folder-ordering
call, distinct subtopics). Other issues: no issue recorded.

**How verified:** `scripts/inspect_resources.py` reports link survival, drop
reasons and fallback usage per roadmap. It was a real-API tool, so it is not part
of the smoke-test suite.

---
---
## Roadmap Page Redesign

**What was built:** commit f251b7f reworked `roadmap.html` and `results.js` for the
new step shape: several videos per step, subtopic chips, projects, collapsed
"resources" and "more topics" sections, collapsible phases with expand/collapse
all, and progress placeholders that the next commit filled in.

**Why:** the page was built for one video and a flat list of subtopics; the
generator now returns phases, several videos and more_topics per step, which the
old layout could not show.

**Issues faced and root causes:** no issue recorded.

**How verified:** the commit records no test beyond viewing the page in a browser;
no automated check exists for this page's layout.

---
---
## Roadmap Progress Tracking

**What was built:** commit 1109383 added the `roadmap_progress` table (the 18th
table): one row per COMPLETED step, with a unique constraint on
(user_id, roadmap_id, step_index). `POST /roadmap/<id>/progress` ticks or
un-ticks a step idempotently; `/roadmap/latest`, `/roadmap/<id>` and
`/dashboard/data` return completed counts, and the roadmap page shows per-step
checkboxes, a bar per phase and an overall bar (also on the dashboard).

**Why:** progress was a backlog item, and later feeds the Placement Readiness
Score. A row-per-completed-step design means "done" is just "a row exists", so
un-ticking deletes the row and no step needs a stored false.

**Issues faced and root causes:** a step index means a phased roadmap's
`global_step_index` or an old flat roadmap's `step_number`; the helper
`step_indexes()` in `routes/roadmap.py` returns whichever applies, so one table
serves both shapes. If a roadmap's steps ever shrink, a previously ticked index
can become invalid; those rows are excluded from the recount rather than
deleted. Other issues: no issue recorded.

**How verified:** `scripts/smoke_test_progress.py` (31 checks as of this batch):
phased and flat roadmaps, idempotent tick, un-tick, another user's roadmap
refused, `/dashboard/data` counts, the stale-index shrink case, and the unique
constraint rejecting a direct duplicate insert.

---
---
## Shared Career-Path Picker and Multiple Roadmaps

**What was built:** commit 6d35d83. `GET /career/options` returns a user's top
quiz matches (ties and near-ties within a score margin of 1, capped at 4, from
`app/pipeline/path_matches.py`) plus all 15 paths, and preselects only when there
is exactly one top match. The picker in `ui.js` shows those matches as radio cards
and the other paths in a select, and is used by the roadmap and resume pages.
`resolve_target_career_path(..., allow_override=True)` lets an explicit
`target_career_path` win over the quiz result for roadmap generation and resume
upload only (still validated against the 15; the DSA map keeps the old
behaviour). A student can now keep several roadmaps (a switcher on the roadmap
page, `GET /roadmap/list`, `GET /roadmap/<id>`, and a list on the dashboard).

**Why:** a student who took the quiz could not generate a roadmap for any other
path, and a second generation hid the first.

**Issues faced and root causes:** a native `<select>` displays its first option as
if chosen when no value was set, so the picker sets the value explicitly to
empty whenever there is no preselect (comment in `ui.js`). The old single-select
picker is kept as a legacy mode because `dsa.html` still calls it with its own
options. Other issues: no issue recorded.

**How verified:** `scripts/smoke_test_paths.py` (49 checks as of this batch),
with the Gemini calls patched out.

---
---
## Adzuna Live Listings and Median-Only Salary

**What was built:** commit 7c48144. `app/pipeline/adzuna_listings.py` fetches live
Adzuna (India) listings for a path's search phrase at runtime and stores nothing.
Successful results are cached in-process for 6 hours and a failure for 60 seconds,
with a 5-second request timeout; any error, timeout, non-200 or malformed body
becomes "unavailable" and never raises. It is served by its own endpoint,
`GET /resume/listings`, separate from `/resume/upload` and `/resume/latest`, so a
slow Adzuna call cannot delay the resume analysis. The resume page now shows only
the median salary (the Range row and the stored "sample job postings" block were
removed), though `get_salary_insights` still computes min and max.

**Why:** live listings were the master document's original "Live Jobs" intent and
no Adzuna code existed; showing min/max from mixed-quality data suggested a
precision it did not have.

**Issues faced and root causes:** no issue recorded.

**How verified:** `scripts/smoke_test_adzuna.py` (34 checks as of this batch),
with `requests.get` patched, so no real Adzuna call is made. It covers success,
cache hit and expiry, timeout, HTTP 500, bad JSON, missing keys and the short
failure cache.

---
---
## Hardening Batch — CSRF, Cookies, Limits, Housekeeping

**What was built:**
- **CSRF** (`app/security.py`): a random token stored in the session, rendered into
  `layout.html` as `<meta name="csrf-token">`, and sent by the shared helpers in
  `ui.js` (`request`, `postJson`, `postForm`) as `X-CSRF-Token` on every
  POST/PUT/PATCH/DELETE. A missing or wrong token returns 400 `{"error":"csrf"}`;
  GET is untouched; multipart uploads carry it as a header. Before this, every
  `fetch` for a state change already went through those helpers, so no template
  needed changing.
- **Session cookie** (`config.py`): SameSite=Lax, HttpOnly, Secure from
  `SESSION_COOKIE_SECURE` (off in development, on in production). Production mode
  refuses to start if `SECRET_KEY` is missing, a known placeholder, or under 16
  characters.
- **Error bodies:** every `"detail": str(e)` was removed from the JSON responses and
  the exception is logged server-side. The two 502 handlers that returned raw
  pipeline error text (`/roadmap/generate`, the DSA framing route) now return a
  fixed student-safe message, and `/db-check` no longer prints the exception.
- **Limits:** `POST /roadmap/generate` is capped per user at 5 (`ROADMAP_DAILY_LIMIT`)
  in a rolling 24 hours, counted from `GeneratedRoadmap.created_at` (429
  `daily_limit` with `limit` and `resets_in_minutes`, shown on the roadmap page);
  `/resume/upload` (10/hour) and `/resume/listings` (30/hour) use an in-process
  counter (429 `rate_limited`).
- **Housekeeping:** `requirements.txt` regenerated from the venv; `requirements-dev.txt`;
  `scripts/cleanup_demo_users.py` (dry run by default); `.env.example` gained
  `UPLOAD_FOLDER`.

**Why:** preparing for deployment (see Known Issues / Deployment Backlog in
DEV_SETUP.md). Cookie-session auth with JSON POST routes is exactly what CSRF
targets; the daily cap protects the Gemini and YouTube quotas.

**Issues faced and root causes:** (1) `requirements.txt` was stale: it lacked
packages the code imports (pdfplumber, spaCy, google-api-python-client, tenacity,
fpdf2 for the smoke test) and carried ones it does not, because it was last
generated before those features existed. (2) The `.env` line for `GEMINI_API_KEY`
contains a space in its value, which breaks any shell that tries to `source` the
file (python-dotenv itself parses it); it must be fixed by hand, and `.env` is
never sourced in this project. (3) The rolling cap and the in-process limits are
per-process, so a multi-worker deployment would multiply the in-process ones.

**How verified:** `scripts/smoke_test_security.py` (30 checks): missing, wrong and
valid token on signup, login and quiz start; multipart upload with and without
token; cookie flags; GET routes without a token; the daily cap and its lift once
rows age past 24 hours; both rate limits; production refusing five bad
`SECRET_KEY` values and starting with a good one. All other smoke tests were
updated to fetch the token the way a browser does (`scripts/_csrf.py`) and pass
with CSRF on. In the browser pane, at 1400px and 360px: login, quiz start (POST
200), a roadmap tick (POST 200), the resume page and a multipart upload through
`postForm`; a raw `fetch` without the header was rejected with 400. Not re-run:
`smoke_test_dsa.py`, `_resume.py`, `_roadmap.py` and `_youtube.py` (they call real
Gemini or YouTube); they were updated to use the CSRF client and compile, but
were not executed. `smoke_test_profile_flow.py` (no external calls, no pass
count) ran and completed.

---
---
## Faster Roadmap Generation — LLM Client, Local Speed-Ups, Parallel Phases

**What was built** (batch 3, commits d6b1e3d to the benchmark commit):
- **Safety net first.** `scripts/smoke_test_generator.py` runs `generate_roadmap()` for
  Full-Stack, Machine Learning Engineering and Cybersecurity with a deterministic fake
  LLM (`scripts/_fake_llm.py`, which builds valid replies from the topic list in each
  prompt) and compares the whole output (roadmap and audit) with golden files in
  `scratch/golden/`, captured before any generator change (the files are force-added
  because `scratch/` is gitignored). Invariants checked: every topic covered at most
  once and none lost, no duplicate step titles across phases, `global_step_index`
  contiguous from 1, `topic_refs` inside the phase allowlist, step counts near targets,
  response shape unchanged.
- **`app/pipeline/llm_client.py`**: `generate(task, prompt, system, schema)` for the
  `roadmap`, `fast` and `fallback` tasks. Providers: `gemini` (default; delegates to the
  unchanged `gemini_client` retry/fallback) and `bedrock` (boto3 Converse). Model IDs
  and provider come from config/env. Only transient errors (throttling, 5xx, timeouts)
  are retried, with backoff; access-denied and validation errors are not. After a
  model fails, the fallback model is tried, then the other provider if it is
  configured. One error type, `LLMError` (a `ValueError`, so existing handlers work),
  built from error codes only. With a schema, the reply is validated with
  `jsonschema` and re-asked once with a correction prompt. Each call logs task, model,
  token counts, latency and cost, never prompt or reply text. `PRICE_PER_MTOK` is empty
  by default, so cost shows as unknown. `roadmap_generator.py` and
  `resume_feedback.py` now go through it. `scripts/benchmark_llm.py` compares configured
  models on 5 fixed profiles; it is a dry run unless `--run`, and was never run with it.
- **Local speed-ups, identical results.** `_assign_more_topics` reuses the vectors
  already in the FAISS index instead of re-embedding every topic; the embedding model
  and index are warmed in a background thread by `run.py` (not by `create_app`, so
  tests and the reloader's watcher process are unaffected); `LLM_TIMEOUT_S` (default 90)
  reaches every provider call; per-stage timings are logged (`roadmap_stage`).
- **Parallel phase writers.** `PHASE_CONCURRENCY` (default 1). At 1 the output equals
  the golden files exactly. Above 1, after the planner (folder-order) call the phase
  calls run in a bounded `ThreadPoolExecutor`; each prompt gets the whole plan (all
  phase titles and topic titles) as read-only context instead of the "earlier phases"
  block. Worker threads receive plain data and return parsed steps (no database, no
  Flask context). Retrieval and post-processing stay in the calling thread, and
  `global_step_index` / `step_number` are assigned after all phases return, in plan
  order. A phase that fails after its own retry raises the same `ValueError` as
  before, and only that phase was retried.
- **Cross-phase duplicate check.** After writing, a later phase whose step title equals
  an earlier one (after normalising) or has title-embedding cosine similarity of at
  least 0.80 is rewritten once, alone, with the earlier titles as an exclusion list.
  If it still repeats, the step is kept and a warning logged.

**Why:** a roadmap took 4 to 8 sequential LLM calls, and the local work between them
was a surprise. Measuring first showed that, with the LLM stubbed, a Full-Stack
generation spent about 14 of its 15 seconds re-embedding topics.

**Measured results** (LLM stubbed, warm model, this machine; it is noisy, so ranges):
- Local time per generation, before: Full-Stack 10.2 s, Machine Learning Engineering
  6.9 s, Cybersecurity 9.4 s. After: about 1.2 to 3.5 s, 0.8 to 2.8 s and 0.7 to 2.2 s
  (the final runs were 1.8, 1.0 and 1.1 s; the spread is machine load, and the final
  figures include the new duplicate check). The first request after a restart no longer
  pays the ~20 s model load if the warm-up has finished.
- Output identical: the three golden files match byte for byte, and a comparison of the
  old and new `_assign_more_topics` over all 15 career paths (fake LLM) was identical
  for every path (207 to 471 more_topics placed per path).
- Benchmark (`scripts/benchmark_generator.py`, stub LLM delay 3 s per call):
  Full-Stack 19.7 s at concurrency 1, 10.6 s at 3 (1.85x); Machine Learning
  Engineering 13.2 s to 7.4 s (1.78x); Cybersecurity 9.9 s to 6.9 s (1.43x). The gain is
  bounded by the planner call, which must come first, and by the phase count.
- Duplicate threshold: measured on the 8 real roadmaps saved in `scratch/` (203 steps,
  1,924 cross-phase pairs), 0.80 flags 1 pair, a genuine duplicate ("Local Storage and
  Data Persistence" / "Data Persistence and Local Storage" in Mobile App Development):
  false-positive rate 0.00%. The cost is recall: of 12 hand-written paraphrase pairs it
  catches 5. At 0.75 it would catch 10 of 12 but flag 4 more real pairs (0.21%), which
  are overlapping rather than duplicate steps. The value is
  `DUPLICATE_SIMILARITY_THRESHOLD`.

**Issues faced and root causes:**
- The first run of `smoke_test_llm.py` had no guard against real credentials. A test
  that expects a failure made `llm_client` fail over to the other provider, which was
  "configured" because `GEMINI_API_KEY` is in the real `.env`, so it constructed a real
  Gemini client (one small request) and, in a later check, sent a canary prompt with a
  made-up key. The test now hides all credentials and replaces both the Gemini client
  and `generate_with_retry` with functions that fail for the whole run.
- The same test found that error text quoted reply content (jsonschema's message
  includes the offending value) and Gemini's raw error text; messages now contain
  only error codes and the schema path.
- `boto3` is not installed in the venv, so the Bedrock path is verified only against a
  scripted fake client that mimics botocore's error shape (`response["Error"]["Code"]`).
  Real botocore error classes have not been exercised.
- The fake LLM reuses KB topic names as step titles, and two KB topics share a name
  across folders ("Access Control Lists (ACLs)"), which made the duplicate check
  rewrite a Cybersecurity phase in the benchmark; the benchmark now sets the threshold
  above 1 so it measures concurrency only.
- Real-model quality of parallel output is not measured: it needs a real run of
  `inspect_roadmap.py` at `PHASE_CONCURRENCY` above 1, which this batch did not do.

**How verified:** `smoke_test_generator.py` (121 checks, at concurrency 1 and 3),
`smoke_test_llm.py` (29 checks), `benchmark_generator.py` and
`measure_duplicate_threshold.py`; see DEV_SETUP.md for how to run them.

---
---
---
---
## Resume Modes — "Which Path Fits My Resume?" and the Survey Skill Columns

**What was built** (batch 4):
- **Survey columns.** The original dataset slug was not recorded anywhere in the repo or
  these docs; `kaggle datasets files` on `aliaslam25/stack-overflow-developer-survey-2025`
  showed `survey_results_public.csv` at 140,893,245 bytes, exactly the size this document
  records for the original download, so that is the dataset. After downloading it to
  `data/raw/` (gitignored) the checks passed: the processor's India filter gives 2,547 rows
  (the table has 2,547), and `dev_type` and the four skill lists matched the stored rows on
  every row, in order. **The planned MiscTech/ToolsTech columns do not exist in the 2025
  release** (they were 2024 questions). Its other skill-like columns were added instead,
  as nullable arrays: `dev_envs` (DevEnvsHaveWorkedWith: IDEs and editors), `so_tags`
  (SOTagsHaveWorkedWith: newer technologies such as Pydantic, LangGraph, Ollama) and
  `office_stack` (OfficeStackAsyncHaveWorkedWith: GitHub, Jira, GitLab, Confluence).
  `CommPlatformHaveWorkedWith` and `AIModelsHaveWorkedWith` were left out (communities and
  model names are not resume skills). `scripts/add_survey_skill_columns.py` backs the table
  up to `scratch/`, runs the ALTER TABLE, fills the columns, and verifies every existing
  field is unchanged; the processor now returns the new columns for a rebuild.
- **Vocabulary.** 61 skills were added for path-fit extraction (`skill_vocabulary.py`):
  the new columns minus names that are ordinary words or too generic ("Cursor", "Linear",
  "Zed", ...), plus 15 hand-listed common skills the survey has no column for (Git,
  TensorFlow, PyTorch, Keras, pandas, NumPy, scikit-learn, ...). A second alias table
  (`EXTENDED_SKILL_ALIASES`: sklearn, reactjs, vs code, html5, ...) is used only by the new
  mode. The original vocabulary, alias table and `get_required_skills` are untouched:
  the "does my resume fit my path" required-skills lists were compared with a snapshot taken
  before the change and are identical for all 15 paths.
- **Ranking** (`app/pipeline/path_fit.py`, pure and deterministic). Survey signal for paths
  with at least 30 respondents: lift (share in path / share overall) x share in path, summed
  over the resume's skills, counting only skills at least 10% of the path's respondents list,
  across all seven skill columns (not five, see above). Roadmap signal: a skills summary is
  embedded, the top 30 unfiltered knowledge-base chunks are counted per path and divided by
  the path's total chunks. List A (9 paths) blends the two 50/50 after min-max
  normalisation; List B (6 thin paths: Data Analytics 25 respondents, QA 22, Cybersecurity 12,
  Game 14, Cloud 14, UI/UX 8) uses the roadmap signal only and is labelled so. Fit is shown
  relative to the top of each list; rows within 15% of the top are near-ties; fewer than 3
  recognised skills gives an `insufficient_data` state.
- **Routes.** `POST /resume/discover` (PDF only, no path: saves a Resume row, no SkillGap,
  no salary, no LLM, structure-only ATS score) and `POST /resume/<id>/analyze` (ownership
  checked, stored skills reused, upload-shaped response plus `ats_unavailable`, feedback
  through `llm_client` with graceful degradation). `/resume/upload` is unchanged. Both new
  routes use the CSRF check and share the upload rate-limit bucket.
- **Front end.** Two choices at the top of the resume page. "Which path fits my resume?"
  uploads to `/resume/discover` and shows List A, then List B, near-ties side by side,
  respondent counts, a limits note, and an "Analyze against this path" button per row;
  "Does my resume fit my path?" is the existing flow with the shared picker.

**Why:** a student without a target path had to guess one before getting any resume
feedback.

**Validation on three synthetic resumes** (`scripts/validate_path_fit.py`; weights fixed
beforehand, not tuned):
- (a) Python, SQL, MySQL, Git: Data Engineering 100%, Data Science 92.7% (a near-tie),
  Machine Learning Engineering 70.5%, Backend 56.6%. List B: Cybersecurity 100% (roadmap
  only, 12 respondents), Data Analytics 70%.
- (b) JavaScript, React, Node.js, TypeScript, HTML/CSS: Full-Stack 100%, Frontend 89.0%
  (near-tie), Mobile 57.1%, Backend 46.5%. List B: Cybersecurity 100% and QA 99.4% on very
  little evidence (JavaScript and Node.js named in a few chunks).
- (c) Python, TensorFlow, PyTorch, pandas, Docker: Data Science 100%, Machine Learning
  Engineering 90.8% (near-tie), DevOps 69.4%, Data Engineering 65.4%, AI Engineering 45.3%.
  Data Analytics leads List B at 100%. This resume reaches the right area, but only through
  the roadmap signal: the survey has no TensorFlow/PyTorch/pandas data, so only Python and
  Docker scored in the survey signal (Docker is what lifts DevOps). AI Engineering
  ranks fifth.

**Issues faced and root causes:**
- The MiscTech/ToolsTech columns the plan assumed are not in the 2025 survey, as above.
- `/resume/latest` pairs a user's newest Resume with their newest SkillGap, so a
  discover-only resume would have been shown with an older, unrelated skill gap. Fixed with
  a nullable `resumes.analysis_pending` flag (set by discover, cleared by analyze;
  `latest_resume_analysis` skips pending rows). The column was added to the dev database with
  `ALTER TABLE resumes ADD COLUMN IF NOT EXISTS analysis_pending BOOLEAN DEFAULT FALSE`.
- The PhraseMatcher was cached once per process, so a second vocabulary could not coexist
  with the original; it is now cached per vocabulary.
- The extractor returns the text as it appears in the resume ("python"), not the canonical
  name; the discover route canonicalises names before ranking (mode 2 still reports surface
  forms, unchanged).
- In the test, two Flask test clients used as context managers at once break request-context
  teardown, and the shared hourly upload limit made later checks fail until the counters
  were reset; both were test-harness problems, not app bugs.
- Not checked: ranking quality on real resumes (only synthetic ones), and the real Gemini
  feedback through `/resume/<id>/analyze` (stubbed in tests and in the browser check).

**How verified:** `scripts/smoke_test_resume_modes.py` (46 checks); browser check of both
modes at 1400px and 360px against a dev server with the LLM and Adzuna stubbed
(`scratch/run_stub_server.py`); see DEV_SETUP.md.

---
---
## Still To Build

- Real-model check of parallel generation: run `scripts/inspect_roadmap.py` for a few
  paths at `PHASE_CONCURRENCY` 1 and 3 and compare quality (duplicates, pacing)
- Run `scripts/benchmark_llm.py --run` once a Bedrock model is configured, install and
  pin `boto3`, and set `PRICE_PER_MTOK` from the provider's real price list
- Roadmap v2 verification backlog (see "Not yet verified" in the Roadmap Generation
  v2 entry; not re-checked since the career-path restructuring)
- Phase 3 Stage 2 (Piston, code execution, XP/mastery/streaks) and Stage 3
  (adaptive bandit map)
- Placement Readiness Score (roadmap progress is now stored and can feed it)
- Deployment (see "Known Issues / Deployment Backlog" in DEV_SETUP.md)

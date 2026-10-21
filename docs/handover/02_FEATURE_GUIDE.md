# 02. Feature guide

For each feature: what the student sees, what happens behind it, the key design decisions, and where the code is.
Exact route lists and file sizes are in file 03. Full detail and history: `docs/DEV_SETUP.md` (how it works) and
`docs/PROJECT_BIOGRAPHY.md` (decisions and what was verified).

## 1. Accounts and profile
- **Student sees:** signup (username, email, password), login with username *or* email, show-password toggle, a profile page
  (personal details, profile picture, change password).
- **Behind it:** passwords hashed with bcrypt; Flask-Login sessions; CSRF token on every state-changing request;
  login/password-change rate limits; the profile picture is re-encoded to a 256x256 JPEG (Pillow), so uploaded files are
  never served as-is. After a server restart in development, everyone is logged out (`LOGOUT_ON_RESTART`, a per-start
  `BOOT_ID` stamped on the session at login) because the session cookie is signed and would otherwise survive a restart.
  In production this is off because several workers have different boot ids.
- **Code:** `app/routes/auth.py`, `app/routes/profile.py`, `app/models.py`, `app/__init__.py`.

## 2. Career quiz
- **Student sees:** one question at a time (8 to 14 asked from a bank of 18), then a ranked list of the 15 paths with a
  confidence score each. Tied top paths are shown together as "Your top matches".
- **Behind it:** every answer option signals 1 to 3 career paths; the engine adds up signals, picks the next question
  that best separates the leading paths (a variance proxy; pair-aware for look-alike paths such as Data Science vs Data
  Analytics), and stops early only when the leader is clearly ahead (never before 8 answers, always at 14).
- **Important honesty:** the option-to-path signals are **hand-authored judgement**, not learned from data. The quiz is
  tested for consistency (same answers give same result; opposite answers give opposite results), not for accuracy.
- **Code:** `app/pipeline/career_quiz_data.py` (questions + signals), `career_quiz_engine.py`, `career_path_registry.py`,
  `app/routes/quiz.py`, `docs/QUIZ_QUESTION_BANK.md` (all questions in readable form).

## 3. Goals ("Personalise your plan")
- **Student sees:** three short questions (what to avoid, target company type, main goal) and an optional note, then a
  summary of exactly what was tailored.
- **Behind it:** answers are saved with the quiz result as the career profile. They do **not** change the career match.
  They (a) pick which coding problem variants a student gets, (b) star recommended scenarios, (c) add a personal note to
  the roadmap. The numbering of the questions starts at C2 because an unused question (C1) was removed on purpose.
- **Code:** `app/pipeline/conversation_data.py`, `conversation_engine.py`, `goal_tailoring.py`, `profile_builder.py`,
  `app/routes/conversation.py`.

## 4. Roadmap
- **Student sees:** a phased, step-by-step roadmap for the chosen path, a progress bar, tick boxes per step, videos and
  resources per step, a "complete" moment at 100%, and a list of earlier roadmaps.
- **Behind it:** two modes. (1) *Cached base roadmap* (default): one reviewed JSON file per path (15), personalised with
  one short LLM call that writes the personal note. Fast and predictable. (2) *Full generation*: retrieval from the FAISS
  knowledge base (5,115 chunks, all-MiniLM-L6-v2) plus an LLM call writes a roadmap from scratch, run as a background job.
  Videos come from a knowledge-base-first resolver, with YouTube search as fallback.
- **Code:** `app/pipeline/` roadmap modules, `data/base_roadmaps/`, `app/routes/roadmap.py`; DEV_SETUP sections
  "Background roadmap generation" and "Base roadmaps (cached mode)".

## 5. Resume analyzer
- **Student sees:** upload a PDF and choose a target path (or ask which path fits the resume). Results: skills found,
  skills missing for the target, a resume score, an ATS-style score with reasons, live job listings with a median
  salary, and written feedback.
- **Behind it:** pdfplumber reads the text; a spaCy PhraseMatcher finds skills from a curated skill list (with aliases
  and implied skills, e.g. a framework implies its language); gap analysis compares with the path's required skills;
  Adzuna supplies live listings; one LLM call writes feedback. Skill extraction is deterministic and explainable.
- **Code:** `app/pipeline/` resume modules, `app/routes/resume.py`; BIOGRAPHY sections "Phase 2", "Resume Modes",
  "Resume Fixes", "Lightweight ATS Score".

## 6. Scenarios
- **Student sees:** a game-style level map for the path: 5 levels, each unlocked only after the previous is passed (70%
  or more), with best score and a recommended next one. A scenario is a short workplace situation with decision
  questions (multiple choice and similar), then a coding question.
- **Behind it:** 75 scenarios (5 per path), 340 questions, authored as JSON and checked by a validator and a blind-solve
  checker. An attempt is created on the server with a shuffle seed; answers are saved as they come; the **whole attempt
  is graded on the server**. The unlock rule is enforced server-side (HTTP 403 `scenario_locked`).
- **Code:** `data/scenarios/*.json`, `app/pipeline/` scenario modules, `app/routes/scenarios.py`,
  `app/static/js/scenarios.js`; DEV_SETUP section "Scenarios".

## 7. Coding questions (inside scenarios)
- **Student sees:** an online-assessment screen. Problem on the left; right side has a language picker (Python, C++,
  Java, JavaScript), an editor and tabs for test cases and results. **Run** tests the code against all tests as often as
  wanted (visible tests show input/output; hidden tests show only "a of b passed"). **Submit** locks the answer.
- **Behind it:** 120 problems (8 per path) in 360 variants; the variant a student gets depends on their goal. Code is
  executed by the OneCompiler API (not on the app server). Hidden test inputs never leave the server. Each Run costs
  roughly one OneCompiler credit per test.
- **Code:** `data/scenarios/*.json` (`code_pool`), code runner module in `app/pipeline/`, `app/routes/scenarios.py`
  (`code_run`); DEV_SETUP section "Code questions". Runner modes: `onecompiler` (real), `local` (laptop only, not a
  sandbox), `fake` (tests).

## 8. Gamification
- **Student sees:** level card (Intern to Principal Engineer), XP, daily streak, 14 badges with progress, and a reward
  card after each submitted scenario. No leaderboard, on purpose.
- **Behind it:** nothing is stored; every number is recomputed from submitted attempts and ticked roadmap steps, so it
  cannot drift. XP: 10 per correct question (best attempt per scenario), +20 first pass, +10 for a 100% scenario, +15
  per distinct coding problem solved, +5 per ticked roadmap step. Retrying cannot farm XP.
- **Code:** `app/pipeline/gamification.py`, `app/routes/gamification.py`, `app/static/js/gamification.js`.

## 9. Placement readiness score
- **Student sees:** one 0-100 score on the dashboard with its four parts; "placement ready" at 70.
- **Behind it:** weights roadmap progress 25%, skill match 35%, scenario results 30%, 30-day activity streak 10%. If a
  part is unavailable (for example no scenario file for a path) it is dropped and the others are re-scaled. "Ready" is
  decided on the unrounded score.
- **Honesty:** the weights are a design choice, not derived from data; the score has not been checked against real
  placements.
- **Code:** `app/pipeline/readiness.py`, `app/routes/readiness.py`.

## 10. Dashboard
Shows the saved quiz result, roadmap progress, resume summary, scenarios, level, badges and readiness in one place.
`app/routes/dashboard.py`, `app/static/js/dashboard.js`.

## Cross-cutting
- **LLM layer:** one client, three providers (Gemini default; Amazon Bedrock optional; any OpenAI-compatible API).
- **Security basics:** CSRF on every state-changing request, no `innerHTML`, bcrypt, rate limits, signed cookies,
  server-side grading and unlock checks. `smoke_test_security.py` checks these.
- **Front-end design system:** CSS tokens in `:root`, shared components, no web fonts; see DEV_SETUP "Front-end design system".

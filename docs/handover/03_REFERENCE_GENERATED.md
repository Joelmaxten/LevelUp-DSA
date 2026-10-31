# 03. Reference (machine-generated)

> Generated on 2026-10-31 by `scripts/build_handover_pack.py` from the code and data files.
> **Do not edit by hand.** To refresh it after a change: `PYTHONPATH=. python scripts/build_handover_pack.py`.
> Everything here is read from the app itself (routes, database models, files), so it is exact. Narrative
> explanations are in files 01 and 02; this file is for looking things up.

## 1. Content and numbers

| Fact | Value |
|---|---|
| Career paths | 15 |
| Quiz question bank | 18 questions; a student is asked 8 to 14 |
| Scenarios | 75 (5 per path) |
| Scenario questions | 340 |
| Coding problems | 120 |
| Coding problem variants | 360 |
| Reviewed base roadmaps | 15 files in data/base_roadmaps/ |
| Knowledge-base chunks in the FAISS index | 5115 |
| XP levels | 7: Intern (0), Trainee (100), Junior Engineer (250), Engineer (500), Senior Engineer (850), Lead Engineer (1300), Principal Engineer (2000) |
| Badges | 14 |

**The 15 career paths:** Full-Stack Development; AI Engineering; Machine Learning Engineering; Data Science; Data Analytics; Cybersecurity; Mobile App Development; Game Development; Backend Engineering; UI/UX Design; Frontend Development; Cloud Engineering; DevOps; QA & Test Automation; Data Engineering.

**Scenario content per path**

| Path | Scenarios | Questions | Coding problems | Variants |
|---|---|---|---|---|
| AI Engineering | 5 | 23 | 8 | 24 |
| Backend Engineering | 5 | 23 | 8 | 24 |
| Cloud Engineering | 5 | 23 | 8 | 24 |
| Cybersecurity | 5 | 22 | 8 | 24 |
| Data Analytics | 5 | 23 | 8 | 24 |
| Data Engineering | 5 | 23 | 8 | 24 |
| Data Science | 5 | 22 | 8 | 24 |
| DevOps | 5 | 23 | 8 | 24 |
| Frontend Development | 5 | 23 | 8 | 24 |
| Full-Stack Development | 5 | 22 | 8 | 24 |
| Game Development | 5 | 23 | 8 | 24 |
| Machine Learning Engineering | 5 | 22 | 8 | 24 |
| Mobile App Development | 5 | 22 | 8 | 24 |
| QA & Test Automation | 5 | 23 | 8 | 24 |
| UI/UX Design | 5 | 23 | 8 | 24 |

**Base roadmaps** (`metadata.model_id` says which model wrote the reply that the generator processed)

| Path | Phases | Steps | Model id in the file |
|---|---|---|---|
| AI Engineering | 5 | 36 | claude-opus-5-5 |
| Backend Engineering | 3 | 30 | claude-opus-5-5 |
| Cloud Engineering | 4 | 29 | claude-opus-5-5 |
| Cybersecurity | 2 | 22 | openai/gpt-oss-20b |
| Data Analytics | 4 | 41 | claude-opus-5-5 |
| Data Engineering | 3 | 22 | claude-opus-5-5 |
| Data Science | 3 | 29 | claude-opus-5-5 |
| DevOps | 4 | 26 | claude-opus-5-5 |
| Frontend Development | 6 | 60 | claude-opus-5-5 |
| Full-Stack Development | 5 | 37 | claude-opus-5-5 |
| Game Development | 2 | 16 | claude-opus-5-5 |
| Machine Learning Engineering | 3 | 21 | claude-opus-5-5 |
| Mobile App Development | 3 | 36 | claude-opus-5-5 |
| QA & Test Automation | 5 | 32 | claude-opus-5-5 |
| UI/UX Design | 3 | 29 | claude-opus-5-5 |

## 2. Database tables (18 tables)

The database is PostgreSQL, accessed through SQLAlchemy (`app/models.py`). There are no migrations; tables are created
with `db.create_all()` and one-off scripts in `scripts/` add columns to older databases.

### `career_paths`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `name` | VARCHAR(120) | required |
| `type` | VARCHAR(20) | required |
| `description` | TEXT |  |

### `job_listings`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `job_title` | VARCHAR(300) | required |
| `location` | VARCHAR(200) |  |
| `state` | VARCHAR(100) |  |
| `locality` | VARCHAR(200) |  |
| `annual_salary` | FLOAT |  |
| `salary_suspicious` | BOOLEAN |  |
| `career_paths` | ARRAY |  |
| `source` | VARCHAR(100) |  |

### `step_check_items`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `step_key` | VARCHAR(64) | required |
| `kind` | VARCHAR(20) | required |
| `prompt` | TEXT | required |
| `options` | JSON | required |
| `correct` | VARCHAR(4) | required |
| `evidence` | TEXT | required |
| `source_title` | VARCHAR(200) | required |
| `source_node` | VARCHAR(64) |  |
| `created_at` | DATETIME | required |

### `survey_respondents`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `dev_type` | VARCHAR(200) |  |
| `career_path` | VARCHAR(120) |  |
| `years_code` | FLOAT |  |
| `work_exp` | FLOAT |  |
| `ed_level` | VARCHAR(200) |  |
| `remote_work` | VARCHAR(100) |  |
| `converted_comp_yearly` | FLOAT |  |
| `languages` | ARRAY |  |
| `databases` | ARRAY |  |
| `platforms` | ARRAY |  |
| `webframes` | ARRAY |  |
| `dev_envs` | ARRAY |  |
| `so_tags` | ARRAY |  |
| `office_stack` | ARRAY |  |
| `source` | VARCHAR(100) |  |

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `name` | VARCHAR(120) | required |
| `username` | VARCHAR(20) | unique |
| `email` | VARCHAR(120) | unique, required |
| `password_hash` | VARCHAR(255) | required |
| `created_at` | DATETIME |  |

### `career_profiles`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `career_ranking` | JSON | required |
| `conversation_signals` | JSON | required |
| `created_at` | DATETIME |  |

### `generated_roadmaps`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `career_path` | VARCHAR(120) | required |
| `steps` | JSON | required |
| `retrieved_chunks` | JSON |  |
| `created_at` | DATETIME |  |

### `password_reset_tokens`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `token_hash` | VARCHAR(64) | unique, required |
| `created_at` | DATETIME | required |
| `expires_at` | DATETIME | required |
| `used_at` | DATETIME |  |

### `resumes`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `file_path` | VARCHAR(500) | required |
| `extracted_skills` | ARRAY |  |
| `ai_feedback` | TEXT |  |
| `uploaded_at` | DATETIME |  |
| `analysis_pending` | BOOLEAN |  |

### `roadmap_steps`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `career_path_id` | INTEGER | -> career_paths.id, required |
| `step_number` | INTEGER | required |
| `title` | VARCHAR(200) | required |
| `resource_link` | VARCHAR(500) |  |
| `is_free` | BOOLEAN |  |

### `scenario_attempts`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `path` | VARCHAR(100) |  |
| `scenario_id` | VARCHAR(40) |  |
| `answers` | JSON |  |
| `score` | INTEGER |  |
| `max_score` | INTEGER |  |
| `passed` | BOOLEAN |  |
| `shuffle_seed` | INTEGER |  |
| `started_at` | DATETIME |  |
| `submitted_at` | DATETIME |  |

### `skill_gaps`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `missing_skills` | ARRAY |  |
| `target_role` | VARCHAR(120) |  |
| `salary_range` | VARCHAR(80) |  |

### `user_avatars`

| Column | Type | Notes |
|---|---|---|
| `user_id` | INTEGER | primary key, -> users.id |
| `image` | BLOB | required |
| `mime` | VARCHAR(30) | required |
| `updated_at` | DATETIME |  |

### `user_profiles`

| Column | Type | Notes |
|---|---|---|
| `user_id` | INTEGER | primary key, -> users.id |
| `phone` | VARCHAR(20) |  |
| `college` | VARCHAR(150) |  |
| `branch` | VARCHAR(100) |  |
| `year_of_study` | INTEGER |  |
| `graduation_year` | INTEGER |  |
| `city` | VARCHAR(80) |  |
| `linkedin_url` | VARCHAR(200) |  |
| `github_url` | VARCHAR(200) |  |
| `bio` | VARCHAR(300) |  |
| `updated_at` | DATETIME |  |

### `roadmap_progress`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `roadmap_id` | INTEGER | -> generated_roadmaps.id, required |
| `step_index` | INTEGER | required |
| `completed_at` | DATETIME |  |

### `step_check_attempts`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `roadmap_id` | INTEGER | -> generated_roadmaps.id, required |
| `step_index` | INTEGER | required |
| `mode` | VARCHAR(10) | required |
| `questions` | JSON | required |
| `answers` | JSON |  |
| `score` | INTEGER |  |
| `total` | INTEGER | required |
| `pass_mark` | INTEGER | required |
| `passed` | BOOLEAN |  |
| `started_at` | DATETIME | required |
| `submitted_at` | DATETIME |  |

### `step_reviews`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `roadmap_id` | INTEGER | -> generated_roadmaps.id, required |
| `step_index` | INTEGER | required |
| `required_at` | DATETIME | required |
| `reviewed_at` | DATETIME |  |

### `user_progress`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `user_id` | INTEGER | -> users.id, required |
| `step_id` | INTEGER | -> roadmap_steps.id, required |
| `completed_at` | DATETIME |  |


## 3. HTTP routes (59 routes)

"Login needed" is read from the route's decorator (`@login_required` returns JSON 401; `@page_login_required` redirects
a browser to /login). Every POST, PUT, PATCH and DELETE also needs a CSRF token header.

| Group | Path | Method | Login needed | What it does (from its docstring) |
|---|---|---|---|---|
| (app) | `/` | GET | no | Home page: the phases of the app side by side. |
| (app) | `/conversation` | GET | yes | The Goals page ("Personalise your plan"). |
| (app) | `/dashboard` | GET | yes | Dashboard page: saved quiz result, roadmap, resume, scenarios, level and badges. |
| (app) | `/db-check` | GET | no | Database health check; reports only ok or failed, never an error text. |
| (app) | `/login` | GET | no | Login page. |
| (app) | `/profile` | GET | yes | Profile page. |
| (app) | `/quiz` | GET | yes | Career quiz page. |
| (app) | `/resume` | GET | yes | Resume analyzer page. |
| (app) | `/roadmap` | GET | yes | Roadmap page. |
| (app) | `/scenarios` | GET | yes | Scenarios page: the level map and the scenario player. |
| (app) | `/signup` | GET | no | Signup page. |
| auth | `/forgot-password` | GET | no |  |
| auth | `/forgot-password` | POST | no | Always answers the same way, so the page cannot be used to find out which emails have accounts. |
| auth | `/login` | POST | no | Log in with a username or an email, plus the password. |
| auth | `/logout` | POST | yes | Log out. |
| auth | `/reset-password` | GET | no |  |
| auth | `/reset-password` | POST | no |  |
| auth | `/signup` | POST | no | Create an account (username, email, password). |
| auth | `/signup/username-check` | GET | no | {"available": bool, "error": message or None} for the signup page's live check. |
| career_paths | `/career/options` | GET | yes | The career paths a student can pick from, with the top quiz matches marked. |
| conversation | `/conversation/answer` | POST | yes | Record one Goals answer; the last one also saves the career profile and returns what was tailored. |
| conversation | `/conversation/back` | POST | yes | Step back to the previous question. |
| conversation | `/conversation/start` | POST | yes | Start the Goals questions (needs a finished quiz). |
| dashboard | `/dashboard/data` | GET | yes | Everything the dashboard shows, in one response. |
| gamification | `/gamification` | GET | yes | XP, level, streak and badges, calculated from the student's activity. |
| profile | `/profile` | POST | yes | Body: any of name, username and the DETAIL_FIELDS. |
| profile | `/profile/avatar` | GET | yes | The student's profile picture. |
| profile | `/profile/avatar` | POST | yes | Upload a profile picture (re-encoded to a 256x256 JPEG). |
| profile | `/profile/avatar/delete` | POST | yes | Remove the profile picture. |
| profile | `/profile/data` | GET | yes | The profile page's data: details, picture flag, progress card. |
| profile | `/profile/password` | POST | yes | Change the password (needs the current one; rate-limited). |
| quiz | `/quiz/answer` | POST | yes | Record one quiz answer; returns the next question, or the ranked results when the quiz ends. |
| quiz | `/quiz/back` | POST | yes | Step back one question. |
| quiz | `/quiz/start` | POST | yes | Start a new quiz. |
| readiness | `/readiness` | GET | yes | The placement readiness score and its four components. |
| resume | `/resume/<int:resume_id>/analyze` | POST | yes | Analyze an already-uploaded resume (see /resume/discover) against one career path, without uploading again. |
| resume | `/resume/discover` | POST | yes | "Which career path fits my resume?" - upload a PDF with NO target path. |
| resume | `/resume/latest` | GET | yes | The student's latest saved resume analysis. |
| resume | `/resume/listings` | GET | yes | Live job listings (Adzuna, plus Jooble when configured) for one career path, with search links for LinkedIn/Naukri/Indeed - deliberately NOT part of /resume/upload or /resume/latest's response (see adzuna_listings.py): the fronten |
| resume | `/resume/upload` | POST | yes | Upload a PDF and analyze it against a target career path (skills, gaps, ATS score, feedback, salary). |
| roadmap | `/roadmap/<int:roadmap_id>` | GET | yes | One saved roadmap. |
| roadmap | `/roadmap/<int:roadmap_id>/progress` | POST | yes | Body: {"step_index": int, "done": bool}. |
| roadmap | `/roadmap/<int:roadmap_id>/resources` | POST | yes | Find videos and resources for a roadmap's steps. |
| roadmap | `/roadmap/generate` | POST | yes | Generate a roadmap and wait for it (the older, blocking route). |
| roadmap | `/roadmap/generate-async` | POST | yes | Same checks as POST /roadmap/generate (daily cap, path resolution, index available), but the generation runs in a background thread (app/pipeline/generation_jobs.py): returns 202 {"job_id", "mode"} at once ("cached" when a reviewe |
| roadmap | `/roadmap/jobs/<job_id>` | GET | yes | Status of a background roadmap job. |
| roadmap | `/roadmap/latest` | GET | yes | The student's most recent roadmap. |
| roadmap | `/roadmap/list` | GET | yes | All the student's saved roadmaps. |
| scenarios | `/scenarios/<path_slug>` | GET | yes | The level map for one path: each scenario's state, best score and the recommended one. |
| scenarios | `/scenarios/<scenario_id>/answer` | POST | yes | Locks one question's answer and returns that question's result (with its explanation). |
| scenarios | `/scenarios/<scenario_id>/code/run` | POST | yes | Ungraded run of the student's source against ALL the tests, as often as the student likes. |
| scenarios | `/scenarios/<scenario_id>/start` | POST | yes | Start or resume an attempt (403 scenario_locked if the previous scenario is not passed). |
| scenarios | `/scenarios/<scenario_id>/submit` | POST | yes | Grade the whole attempt on the server; returns the result and the rewards. |
| scenarios | `/scenarios/paths` | GET | yes | The paths that have scenarios. |
| step_checks | `/roadmap/<int:roadmap_id>/steps/<int:step_index>/check/start` | POST | yes |  |
| step_checks | `/roadmap/<int:roadmap_id>/steps/<int:step_index>/check/submit` | POST | yes |  |
| step_checks | `/roadmap/<int:roadmap_id>/steps/<int:step_index>/review` | GET | yes |  |
| step_checks | `/roadmap/<int:roadmap_id>/steps/<int:step_index>/review` | POST | yes |  |
| step_checks | `/roadmap/<int:roadmap_id>/steps/state` | GET | yes |  |

## 4. Code map

### app/ (application root)

| File | Lines | Purpose (first sentence of its docstring) |
|---|---|---|
| `app/__init__.py` | 213 | The application factory (create_app): registers every route, the login gate, error pages and the restart-logout hook. |
| `app/config.py` | 200 | Settings read from environment variables, with development and production modes. |
| `app/mailer.py` | 58 | Minimal email sending for the password-reset link, standard library only (smtplib), so no extra package. |
| `app/models.py` | 369 | The database tables (SQLAlchemy models). |
| `app/security.py` | 88 | Request-level security: CSRF protection and small in-process rate limits. |
| `app/seed_data.py` | 92 | Export and load the two data tables the app cannot run without: survey_respondents (the Stack Overflow survey rows, India only) and job_listings (the processed India jobs). |
| `app/usernames.py` | 46 | Username rules, shared by signup, the profile page and scripts/add_usernames.py. |

### app/routes/ (HTTP routes)

| File | Lines | Purpose (first sentence of its docstring) |
|---|---|---|
| `app/routes/_util.py` | 92 | Small helpers shared by the route files (JSON errors, input checks). |
| `app/routes/auth.py` | 289 | Signup, login and logout. |
| `app/routes/career_paths.py` | 37 | GET /career/options - the single source the shared career-path picker (ui.js's careerPathPicker, in its self-fetching mode) uses to decide what to offer: a profile's top quiz matches (if any), plus the full 15-path list as a fallb |
| `app/routes/conversation.py` | 169 | The Goals questions: start, answer, and saving the career profile. |
| `app/routes/dashboard.py` | 145 | "Resume where you left off": what the current user has already saved, so the dashboard can show their existing results instead of restarting the flow. |
| `app/routes/gamification.py` | 58 | GET /gamification: the student's XP, level, streak and badges (rules in app/pipeline/gamification.py). |
| `app/routes/profile.py` | 278 | The student's own profile: personal details, username, profile picture and password change. |
| `app/routes/quiz.py` | 100 | The career quiz: start and answer. |
| `app/routes/readiness.py` | 78 | GET /readiness: the student's Placement Readiness Score (see app/pipeline/readiness.py for the rules). |
| `app/routes/resume.py` | 382 | Resume upload, analysis and the latest saved result. |
| `app/routes/roadmap.py` | 496 | Roadmap generation, listing, progress and resources. |
| `app/routes/scenarios.py` | 426 | Scenario-based practice: a map of scenarios per career path, each a short work situation with questions. |
| `app/routes/step_checks.py` | 324 | Verified progression routes (see app/pipeline/step_checks.py for how questions are made and checked). |

### app/pipeline/ (logic: quiz, roadmaps, resume, scenarios, gamification, LLM)

| File | Lines | Purpose (first sentence of its docstring) |
|---|---|---|
| `app/pipeline/adzuna_listings.py` | 197 | Live job listings from the Adzuna API for a career path - a runtime call, never stored (this was the master doc's original design intent for "Live Jobs"; no Adzuna-calling code existed anywhere before this module - see the read-on |
| `app/pipeline/ats_score.py` | 239 | Lightweight ATS (Applicant Tracking System) friendliness score - NOT a deep PDF layout/structure analysis (multi-column detection, table linearization, etc. |
| `app/pipeline/base_roadmaps.py` | 150 | Reviewed base roadmaps: one JSON file per career path in data/base_roadmaps/<slug>.json, built offline by scripts/build_base_roadmaps.py and served by POST /roadmap/generate-async in "cached" mode (see app/pipeline/generation_jobs |
| `app/pipeline/career_path_registry.py` | 145 | Single source of truth for the 15 career paths: which roadmap.sh knowledge-base folders ground each one, and which SO Survey 2025 DevType values (survey_respondents.dev_type - a controlled-vocabulary field, kept raw in that column |
| `app/pipeline/career_quiz_data.py` | 279 | Career Discovery quiz data: the 15 CS career paths, the 18-question bank, and the option-to-career-signal mapping. |
| `app/pipeline/career_quiz_engine.py` | 200 | Adaptive career-discovery quiz engine. |
| `app/pipeline/code_runner.py` | 282 | Code-execution adapter for graded code questions. |
| `app/pipeline/code_starters.py` | 65 | Starter code per language for the coding questions. |
| `app/pipeline/conversation_data.py` | 68 | Post-quiz conversation data: a short set of fixed questions capturing signals the adaptive quiz cannot — things to avoid, target company type, and near-term goal. |
| `app/pipeline/conversation_engine.py` | 103 | Engine for the fixed-order post-quiz conversation. |
| `app/pipeline/embedder.py` | 50 | Generates sentence embeddings for knowledge base text chunks using sentence-transformers (all-MiniLM-L6-v2, 384 dimensions). |
| `app/pipeline/gamification.py` | 213 | Gamification: XP, levels, streaks and badges. |
| `app/pipeline/gemini_client.py` | 119 | Shared Gemini call wrapper with retry + fallback, used by both roadmap generation and resume feedback. |
| `app/pipeline/generation_jobs.py` | 194 | Background roadmap generation. |
| `app/pipeline/goal_tailoring.py` | 85 | What the Goals answers change, in plain words, for the "Here's what we'll tailor" card on the Goals page. |
| `app/pipeline/india_jobs_processor.py` | 111 | Processes the India Job Market & Salary dataset (Kaggle) into clean, structured rows ready for PostgreSQL. |
| `app/pipeline/jooble_listings.py` | 104 | Live job listings from the Jooble API for a career path: an optional second source next to Adzuna. |
| `app/pipeline/live_jobs.py` | 81 | All live job listings for a career path in one answer: Adzuna and (when JOOBLE_API_KEY is set) Jooble, asked at the same time, interleaved, with duplicates removed across both, each listing tagged with its source. |
| `app/pipeline/llm_client.py` | 684 | One entry point for every LLM call the app makes: generate(task, prompt, ...). |
| `app/pipeline/path_fit.py` | 255 | "Which career path fits my resume?" - ranks the 15 career paths for a set of resume skills. |
| `app/pipeline/path_matches.py` | 41 | Pure functions over a CareerProfile's ranking - no Flask, no DB. |
| `app/pipeline/profile_builder.py` | 83 | Combines the adaptive quiz's career-path scores with the post-quiz conversation's signals into one final student profile. |
| `app/pipeline/rag.py` | 141 | FAISS-backed retrieval for the RAG pipeline. |
| `app/pipeline/readiness.py` | 107 | Placement Readiness Score. |
| `app/pipeline/resume_analyzer.py` | 131 | Phase 2 core pipeline: extracts text from an uploaded resume PDF, extracts known skills from that text (via resume_skill_extractor.py's PhraseMatcher, seeded with the real SO Survey skill vocabulary), and computes a skill gap agai |
| `app/pipeline/resume_feedback.py` | 125 | Generates LLM-based resume feedback: line-by-line improvement suggestions, a 30-day action plan, and keyword suggestions - per the master doc's Phase 2 report spec. |
| `app/pipeline/resume_skill_extractor.py` | 81 | Extracts known technical skills from resume text using spaCy's PhraseMatcher seeded with real skills from the SO Survey 2025 (India) dataset - not spaCy's generic statistical NER, which was tested and found unreliable for this tas |
| `app/pipeline/roadmap_generator.py` | 1197 | Generates a personalized learning roadmap for a student, structured as PHASES of steps (folder-ordered, foundational -> advanced) rather than one flat list, so a roadmap can realistically span a career path's full topic inventory  |
| `app/pipeline/roadmap_kb_processor.py` | 113 | Extracts and cleans roadmap.sh markdown content for the RAG knowledge base. |
| `app/pipeline/roadmap_personalizer.py` | 211 | Personalizes a reviewed base roadmap for one student with ONE short LLM call (task "fast"), instead of generating a whole roadmap per student. |
| `app/pipeline/salary_matching.py` | 122 | Salary and job-matching data for a target career path, drawn from two distinct sources kept deliberately separate rather than merged into one figure: India Jobs (real job postings, INR, skews entry-level/fresher - this project's a |
| `app/pipeline/scenario_engine.py` | 360 | Scenario engine: what a student may see, how answers are graded, and the unlock / recommendation rules. |
| `app/pipeline/scenario_store.py` | 78 | Loads scenario files from data/scenarios/, validates each one and caches the result. |
| `app/pipeline/scenario_validator.py` | 387 | Validator for scenario files (data/scenarios/<path>.json). |
| `app/pipeline/skill_aggregation.py` | 24 | Shared skill-frequency aggregation over SurveyRespondent rows, used by both FAISS chunk generation (so_survey_chunks.py) and Phase 2's skill-gap computation (resume_analyzer.py). |
| `app/pipeline/skill_aliases.py` | 47 | Common abbreviations/aliases for skills in the SO Survey vocabulary that students' resumes are likely to use instead of the full name. |
| `app/pipeline/skill_matching.py` | 71 | Rules for comparing a resume's skills with a career path's required skills, kept in this one file so they are not scattered across the extractor, the analyzer and the routes. |
| `app/pipeline/skill_vocabulary.py` | 38 | Extra skill names for resume skill extraction in "which path fits my resume" mode, on top of the four survey categories the existing vocabulary is built from (languages, databases, platforms, web frameworks - see resume_analyzer.g |
| `app/pipeline/so_survey_chunks.py` | 63 | Generates FAISS-ready text chunks from SO Survey 2025 (India) respondent data - one chunk per career path, summarizing the most common languages, databases, platforms, and frameworks among respondents in that path. |
| `app/pipeline/so_survey_processor.py` | 93 | Processes the Stack Overflow Developer Survey 2025 into clean, structured rows for PostgreSQL, filtered to India respondents only - this project's target audience is explicitly tier-2/tier-3 Indian engineering colleges (per the ma |
| `app/pipeline/step_checks.py` | 385 | Verified progression: a roadmap step is completed by passing a short check, not by ticking a box. |
| `app/pipeline/survey_queries.py` | 28 | Query helper bridging the 15 career paths to survey_respondents.dev_type. |
| `app/pipeline/warmup.py` | 56 | Background warm-up of the two slow-to-load pieces roadmap generation needs: the sentence-transformer model (about 20 s the first time in a process) and the FAISS index plus chunk metadata. |
| `app/pipeline/youtube_resources.py` | 413 | KB-first video and resource resolver for a generated roadmap. |

### Templates (pages) and static files

| File | Lines |
|---|---|
| `app/templates/conversation.html` | 292 |
| `app/templates/dashboard.html` | 207 |
| `app/templates/error.html` | 31 |
| `app/templates/forgot_password.html` | 55 |
| `app/templates/index.html` | 95 |
| `app/templates/layout.html` | 103 |
| `app/templates/login.html` | 72 |
| `app/templates/profile.html` | 372 |
| `app/templates/quiz.html` | 164 |
| `app/templates/reset_password.html` | 73 |
| `app/templates/resume.html` | 300 |
| `app/templates/roadmap.html` | 578 |
| `app/templates/scenarios.html` | 19 |
| `app/templates/signup.html` | 186 |
| `app/static/js/celebrate.js` | 111 |
| `app/static/js/gamification.js` | 111 |
| `app/static/js/results.js` | 836 |
| `app/static/js/scenario_map.js` | 342 |
| `app/static/js/scenarios.js` | 736 |
| `app/static/js/step_checks.js` | 190 |
| `app/static/js/ui.js` | 540 |
| `app/static/css/style.css` | 1464 |

## 5. Test scripts

| Script | What it checks (first sentence of its docstring) |
|---|---|
| `scripts/smoke_test_adzuna.py` | Smoke test for live Adzuna job listings: app/pipeline/adzuna_listings.py's normalization/caching/failure handling, GET /resume/listings, and the salary-summary medians-only change. |
| `scripts/smoke_test_async_generation.py` | Smoke test for background roadmap generation: POST /roadmap/generate-async, GET /roadmap/jobs/<id> and the in-memory registry in app/pipeline/generation_jobs.py. |
| `scripts/smoke_test_cached_roadmaps.py` | Smoke test for cached base roadmaps + fast personalization. |
| `scripts/smoke_test_code_pools.py` | Smoke test for scenario code pools: the validator rules, materialising a variant, the personalised pick, the effective scenario an attempt sees, that nothing secret reaches the browser, grading with the real reference solutions, a |
| `scripts/smoke_test_code_questions.py` | Smoke test for graded code questions: the code runner adapter, validator, public view, grading and the Run / Check routes. |
| `scripts/smoke_test_gamification.py` | Smoke test for gamification: XP rules (best score only, one-off bonuses, no farming), levels, the IST streak maths, every badge rule, rewards between two summaries, GET /gamification (auth, per-user data, no writes), the rewards o |
| `scripts/smoke_test_generator.py` | Regression test for the roadmap generator (app/pipeline/roadmap_generator.py), with a deterministic fake LLM (scripts/_fake_llm.py) standing in for Gemini / Bedrock. |
| `scripts/smoke_test_jobs.py` | Smoke test for the live job listings: duplicate removal, the optional Jooble source, the combiner (app/pipeline/live_jobs.py) and the LinkedIn / Naukri / Indeed search links. |
| `scripts/smoke_test_llm.py` | Smoke test for app/pipeline/llm_client.py with stubs only: a scripted fake Bedrock client and a patched gemini_client.generate_with_retry. |
| `scripts/smoke_test_password_reset.py` | Smoke test for "forgot password": the emailed single-use link, expiry, rate limits, no account enumeration, and that the new password works and the old one does not. |
| `scripts/smoke_test_paths.py` | Smoke test for the shared career-path picker and multi-roadmap support: app/pipeline/path_matches.py, resolve_target_career_path's allow_override, GET /career/options, GET /roadmap/list, GET /roadmap/<id>, and the dashboard's "roa |
| `scripts/smoke_test_profile.py` | Smoke test for accounts and the profile: username rules, signup with a username, login with a username or an email, the live username check, the profile page and API (details, validation, username change, picture, password change) |
| `scripts/smoke_test_profile_flow.py` | One-off smoke test driving the full quiz -> conversation -> CareerProfile flow through Flask's test client. |
| `scripts/smoke_test_progress.py` | Smoke test for per-step roadmap progress tracking - POST/GET /roadmap/<id>/progress and its effect on /roadmap/latest and /dashboard/data - via Flask's test client. |
| `scripts/smoke_test_quiz.py` | Regression test for the career quiz engine (app/pipeline/career_quiz_engine.py and the data in career_quiz_data.py). |
| `scripts/smoke_test_readiness.py` | Smoke test for the Placement Readiness Score: the pure scoring rules (app/pipeline/readiness.py) and GET /readiness. |
| `scripts/smoke_test_resume.py` | End-to-end smoke test for /resume/upload: signup -> quiz -> conversation (to get a CareerProfile) -> generate a test PDF -> upload it -> verify the skill extraction, gap analysis, and DB persistence all worked. |
| `scripts/smoke_test_resume_modes.py` | Smoke test for the two resume modes: "which path fits my resume?" (POST /resume/discover, POST /resume/<id>/analyze, app/pipeline/path_fit.py) and "does my resume fit my path?" (the existing /resume/upload, which must not change). |
| `scripts/smoke_test_resume_rules.py` | Tests for the resume skill-matching rules (app/pipeline/skill_matching.py) and the ATS content checks (app/pipeline/ats_score.py). |
| `scripts/smoke_test_roadmap.py` | One-off smoke test driving the full quiz -> conversation -> roadmap generation flow through Flask's test client, using the real FAISS index built on this machine. |
| `scripts/smoke_test_salary.py` | Salary insights must not crash when the data tables are empty (a fresh database whose job_listings / survey_respondents were never loaded). |
| `scripts/smoke_test_scenarios.py` | Smoke test for scenario-based gamification: validator, store, engine, progress rules, routes. |
| `scripts/smoke_test_security.py` | Smoke test for the security hardening: CSRF protection, session-cookie flags, production SECRET_KEY check, the roadmap daily cap and the resume rate limits. |
| `scripts/smoke_test_seed.py` | Checks for app/seed_data.py (export/load of survey_respondents and job_listings) and the fresh-clone helpers. |
| `scripts/smoke_test_step_checks.py` | Smoke test for verified progression: roadmap steps completed by passing a check built from the step's own knowledge-base passages (app/pipeline/step_checks.py, app/routes/step_checks.py). |
| `scripts/smoke_test_youtube.py` | Extends the roadmap smoke test to also verify /roadmap/<id>/resources - first real end-to-end test of YouTube resource attachment. |

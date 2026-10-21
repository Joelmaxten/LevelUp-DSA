# 01. System overview

## What LevelUp DSA is

A Flask web application that helps IT engineering students decide which career path to aim for and then practise for
it. Full name used in the README: *LevelUp DSA: Personalized Career Intelligence System with Gamified Scenario
Practice for Students Interested in the IT Sector.* It is aimed at students at tier 2 / tier 3 engineering colleges who
have little access to structured career mentoring.

## The problem (four gaps)

1. No structured career direction: students study randomly without knowing what the industry wants.
2. No clear skill-gap awareness: students do not know what they are missing for a target role.
3. Practice disconnected from real work: algorithm drills say little about the decisions a job involves.
4. No single measure of placement readiness.

## How each part answers a gap

| Gap | Feature |
|---|---|
| Direction | Adaptive career quiz ranks 15 IT paths; Goals page; personalised roadmap |
| Skill gaps | Resume analyzer compares the student's resume skills with what the target path needs |
| Disconnected practice | 75 workplace scenarios (5 per path) that end with a real coding question |
| Readiness | One 0-100 placement readiness score, "ready" at 70 |
| Motivation (supporting) | XP, 7 levels, streak, 14 badges (no leaderboard, by design) |

## The student journey (end to end)

1. **Sign up / log in** (username or email + password).
2. **Career quiz**: 8 to 14 adaptive questions from a bank of 18 → ranked list of the 15 paths with a confidence
   score each. Ties are shown as ties.
3. **Goals**: three short questions (what to avoid, target company type, main goal) + optional note. They do **not**
   change the match. They tailor coding problems, which scenarios are starred, and the roadmap's personal note.
4. **Pick a path**: the student chooses any of the 15 (the top quiz matches are marked; if several tie, the student chooses).
5. **Roadmap**: a reviewed step-by-step roadmap for that path, personalised with one short LLM call; progress is
   tracked step by step. Videos/resources are found per step.
6. **Resume analyzer**: upload a PDF → extracted skills, resume score, ATS-style score, skill gaps vs the target path,
   live job listings, LLM feedback.
7. **Scenarios**: a game-style level map for the path. A level unlocks when the previous one is passed (70%+). Each
   scenario has decision questions and ends with a coding question on an online-assessment style screen.
8. **Dashboard / Profile**: level, XP, streak, badges, readiness score, saved results, personal details.

## Architecture in one picture (describe this as a diagram in the report)

```
Browser (HTML + CSS + vanilla JS, Jinja2 templates, no build step)
   │  JSON over HTTPS-style requests, CSRF token on every state-changing request
   ▼
Flask app  (app/__init__.py: create_app)
   ├─ routes/      thin HTTP layer: auth, quiz, conversation (Goals), roadmap, resume,
   │               scenarios, gamification, readiness, dashboard, profile, career paths
   ├─ pipeline/    the logic: quiz engine, Goals + profile builder, roadmap generation,
   │               resume extraction/gap/ATS, scenario + code engines, gamification, readiness
   ├─ models.py    SQLAlchemy tables  ──►  PostgreSQL
   └─ llm layer    one client, three providers: Gemini (default), Amazon Bedrock, any OpenAI-compatible API
Local data files:  data/scenarios/*.json (15), data/base_roadmaps/*.json (15), FAISS knowledge base (5,115 chunks)
External services: OneCompiler (run code), Adzuna (job listings), YouTube Data API (videos), the LLM provider
```

## Technology choices and the reason for each

| Choice | Why |
|---|---|
| Flask + SQLAlchemy + PostgreSQL | Simple, well-known stack; PostgreSQL for real relational data and JSON columns |
| Vanilla JavaScript, no framework or build | Keeps the project small and runnable by anyone; all dynamic text is set with `textContent` (no `innerHTML`), which removes a class of XSS bugs; a test greps for it |
| FAISS + all-MiniLM-L6-v2 | Local semantic search over the roadmap knowledge base without a paid service |
| spaCy PhraseMatcher + pdfplumber | Deterministic skill extraction from resumes (explainable, no model call) |
| LLM used sparingly | Only for roadmap personalisation (one short call) and resume feedback; content that must be correct (scenarios, problems, base roadmaps) is authored and reviewed, then validated by scripts |
| Hidden tests run on the server | The browser never receives hidden test inputs; code runs in OneCompiler, not on the app server |
| Level unlock enforced on the server | `scenario_locked` (HTTP 403) so it cannot be bypassed from the browser |
| Server-side grading | The whole attempt is graded on the server; the browser only sends answers |

## Where the knowledge base and content came from

- Roadmap knowledge base: roadmap.sh content, Stack Overflow Developer Survey 2025, an India job-market dataset.
- Scenarios, scenario questions, coding problems: authored for the project, then checked by a validator and a
  blind-solve checker (see file 04). 
- Base roadmaps: reviewed JSON files, one per path. One (Cybersecurity) was produced by a different, smaller model;
  see file 03, section 1, and file 04.

## Status

Feature-complete and tested locally. **Not deployed.** No real-user study has been run.

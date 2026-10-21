# LevelUp DSA

**Personalized Career Intelligence System with Gamified Scenario Practice for Students Interested in the IT Sector**

LevelUp DSA is a Flask web platform that helps engineering students decide where to aim and then practise for it. It
combines an adaptive career quiz, a personalised roadmap, a resume analyzer, and gamified workplace scenarios with
real coding questions. It is built for students at tier 2 / tier 3 engineering colleges who lack access to structured
career mentorship.

## Problem It Solves

- No structured career direction: students study randomly without knowing what the industry wants
- No clear skill-gap awareness: students don't know what they are missing for their target role
- Practice that is disconnected from real work: algorithm drills say little about the decisions a job involves
- No single measure of placement readiness

## What You Can Do

| Step | What it does |
|------|--------------|
| **Career quiz** | An adaptive quiz ranks 15 IT career paths for you, with a confidence score for each. |
| **Goals** | Three short questions (what to avoid, target company type, main goal) plus an optional note. They do not change your career match, which comes from the quiz only; they tailor the coding problems, the starred scenarios and the roadmap's personal note. The page shows exactly what was tailored. |
| **Roadmap** | A reviewed, step-by-step roadmap for your chosen path (all 15 paths have one), personalised with one short LLM call, with progress tracking. A full from-scratch generation using retrieval over a knowledge base is also available. |
| **Resume analyzer** | Upload a PDF. The app extracts your skills (pdfplumber + spaCy), scores the resume, compares your skills with what your target path needs, shows live job listings (Adzuna) and gives LLM feedback. |
| **Scenarios** | 75 short workplace situations (5 per path, 340 questions) on a game-style level map. A level unlocks only after you pass the previous one (70% or more). Each scenario ends with a coding question. |
| **Coding questions** | An online-assessment screen: problem on the left; on the right a language picker (Python, C++, Java, JavaScript), an editor and the test cases. Run tests everything as often as you like; Submit locks your answer. Hidden test inputs are never shown. 120 problems, 360 variants, picked to match your goal. |
| **Gamification** | XP, 7 levels (Intern to Principal Engineer), a daily streak, 14 badges and rewards. All of it is calculated from your activity; there is no leaderboard, by design. |
| **Placement readiness score** | One 0-100 score from roadmap progress (25%), skill match (35%), scenario results (30%) and a 30-day streak (10%). You are "placement ready" at 70. |
| **Profile** | Username, personal details, a profile picture and password change. You can log in with your username or your email. |

## Tech Stack

- **Backend:** Flask, Flask-Login, bcrypt, SQLAlchemy
- **Database:** PostgreSQL
- **Frontend:** HTML, CSS and vanilla JavaScript with Jinja2 templates (no front-end build step, no web fonts)
- **AI / ML:** FAISS, sentence-transformers, spaCy, an LLM layer that supports Gemini (default), Amazon Bedrock and any
  OpenAI-compatible API
- **Code execution:** OneCompiler API (many languages); a local runner for development only
- **External APIs:** Adzuna (job listings), YouTube Data API (learning resources)
- **Data:** the roadmap knowledge base is built from roadmap.sh content, the Stack Overflow Developer Survey 2025 and
  an India job-market dataset

## Quick Start

You need Python 3.11 or 3.12, PostgreSQL, and Git Bash on Windows (PowerShell causes problems with these commands).
The full guide, with every setting explained, is in [`docs/DEV_SETUP.md`](docs/DEV_SETUP.md).

```bash
git clone https://github.com/Joelmaxten/LevelUp-DSA.git
cd LevelUp-DSA
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env        # then open .env and set DATABASE_URL, SECRET_KEY and your API keys
```

Create the database once (`CREATE DATABASE levelup_dsa_dev;` in `psql`), then create the tables:

```bash
PYTHONPATH=. python -c "from dotenv import load_dotenv; load_dotenv(); from app import create_app, db; from app import models; app = create_app(); app.app_context().push(); db.create_all()"
PYTHONPATH=. python scripts/add_usernames.py --apply
python run.py
```

Open http://127.0.0.1:5000. Only `DATABASE_URL` and `SECRET_KEY` are needed to start; the keys switch features on:

| Setting | Unlocks |
|---------|---------|
| `GEMINI_API_KEY` | roadmap personalisation, resume feedback |
| `ONECOMPILER_API_KEY` with `CODE_RUNNER=onecompiler` | running and submitting code in all four languages |
| `CODE_RUNNER=local` | development only: runs code with the languages installed on your own machine; it is **not** a sandbox, so never use it on a server |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | live job listings on the resume page |
| `YOUTUBE_API_KEY` | fallback video search for roadmap steps |

`LOGOUT_ON_RESTART` is on in development, so restarting the server logs everyone out.

## Running the Tests

The smoke tests use a real database and do not call paid services (code execution is faked or run locally).

```bash
for s in security profile scenarios code_questions code_pools gamification readiness quiz; do
  echo "== $s"; PYTHONPATH=. python scripts/smoke_test_$s.py 2>&1 | grep -E "checks passed|^FAILED"
done
```

Expected: security 30, profile 79, scenarios 218, code_questions 198, code_pools 118, gamification 49, readiness 70
(69 on a database without the survey table), quiz 33.

## Project Layout

```
app/                Flask app: routes, pipeline logic, templates, static JS and CSS
data/               scenarios (15 JSON files), reviewed base roadmaps, the FAISS knowledge base
scripts/            smoke tests, content builders and one-off maintenance scripts
docs/               DEV_SETUP.md (setup and reference) and PROJECT_BIOGRAPHY.md (what was built, and why)
```

## Project Status

Feature-complete and tested. It has not been deployed; it runs locally. `docs/PROJECT_BIOGRAPHY.md` records every
decision and what was verified.

## Team

Joel Vijaybabu Mhasraj (lead), Karthikeya, Ganesh, Jayavardhana

**Guide:** Dr. B.M. Vidyavathi, Dept. of AIML, BITM Ballari

## License

MIT, see [LICENSE](LICENSE).

# 06. Screenshot guide

Screenshots are the one thing an LLM cannot produce. The project owner (or anyone who can run the app) takes these once
and shares the images; teammates paste them into the report. **Never include the `.env` file, API keys or a real
password in a screenshot.**

## Run the app (project owner's machine; Git Bash on Windows)

```bash
cd /c/LevelUp-DSA2
source venv/Scripts/activate
python run.py
```

Open http://127.0.0.1:5000. Full setup: `docs/DEV_SETUP.md`. For code to run in the coding screen, `.env` needs either
`ONECOMPILER_API_KEY` with `CODE_RUNNER=onecompiler` (uses credits) or `CODE_RUNNER=local` (own machine only).

Use a test account (for example username `demo1`, any email, a throw-away password). Clean test accounts afterwards
with the recipe in DEV_SETUP, "Cleaning up test users".

## Shot list (name files exactly like this)

| File name | URL | How to get it |
|---|---|---|
| `01_home.png` | `/` | Logged out landing page |
| `02_signup.png` | `/signup` | Signup form |
| `03_login.png` | `/login` | Login form |
| `04_quiz_question.png` | `/quiz` | Start the quiz; capture a question mid-way |
| `05_quiz_results.png` | `/quiz` | Finish the quiz; ranked paths with confidence |
| `06_goals.png` | `/conversation` | The three Goals questions |
| `07_goals_summary.png` | `/conversation` | The "what was tailored" summary |
| `08_roadmap.png` | `/roadmap` | A generated roadmap with phases and steps |
| `09_roadmap_progress.png` | `/roadmap` | Tick a few steps; progress bar visible |
| `10_resume_upload.png` | `/resume` | Before upload |
| `11_resume_results.png` | `/resume` | After upload of a sample PDF: skills, gaps, score, jobs |
| `12_scenario_map.png` | `/scenarios` | Level map with one level passed and the next unlocked, the rest locked |
| `13_scenario_question.png` | `/scenarios` | A decision question |
| `14_coding_screen.png` | `/scenarios` | The coding question: problem, language picker, editor |
| `15_coding_run.png` | `/scenarios` | After Run: results tab with "Hidden tests: a of b passed" |
| `16_scenario_result.png` | `/scenarios` | The result and reward card after Submit |
| `17_dashboard.png` | `/dashboard` | Level, XP, streak, badges, readiness |
| `18_profile.png` | `/profile` | Profile page |

Tips: use a 1280-pixel-wide browser window; capture the whole page; use a sample resume that contains no real personal
data; for 12, pass the first scenario of a path first.

## Screen recording for the viva

A 5-7 minute screen recording in this order: signup → quiz → Goals → roadmap → resume → scenario level map → one
scenario with a coding Run and Submit → dashboard. Do not show `.env` or terminals with keys.

## Diagrams (draw, do not photograph)

Ask the LLM for Mermaid or PlantUML source (prompts in file 05) and render at mermaid.live or plantuml.com:
architecture diagram, student journey, ER diagram.

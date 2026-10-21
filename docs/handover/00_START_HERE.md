# 00. Start here: documentation hand-over pack

This folder lets anyone on the team write the project documentation (report, README sections, presentation, viva
notes) **using any LLM** (Claude, ChatGPT, Gemini, a local model), without reading all the code first.

## What is in this folder

| File | What it is | Written by |
|---|---|---|
| `00_START_HERE.md` | This page: how to use the pack, and the rules the LLM must follow | hand |
| `01_SYSTEM_OVERVIEW.md` | What the system is, the problem, the architecture, the end-to-end flow | hand |
| `02_FEATURE_GUIDE.md` | Every feature: what the student sees, what happens behind it, where the code is | hand |
| `03_REFERENCE_GENERATED.md` | Exact counts, database tables, all routes, code map, test suites | **generated from the code** |
| `04_VERIFICATION_AND_LIMITS.md` | What was tested and how, what was NOT verified, honest limitations | hand |
| `05_REPORT_OUTLINE_AND_PROMPTS.md` | Report chapters mapped to sources, plus ready-to-paste prompts | hand |
| `06_SCREENSHOT_GUIDE.md` | How to run the app and which screenshots to take | hand |
| `07_GLOSSARY_AND_FAQ.md` | Terms, and honest answers to likely viva questions | hand |
| `CONTEXT_PACK.md` | **All of the above in one file, ready to paste into an LLM** | generated |

## The fastest way (5 minutes)

1. Open `CONTEXT_PACK.md` and paste the whole file into the LLM chat (about 14,000 tokens; any current model accepts it).
   If the tool takes attachments, attach the file instead.
2. Open `05_REPORT_OUTLINE_AND_PROMPTS.md`, pick the chapter you are writing, and paste its prompt right after.
3. Read the draft against the sources named in the prompt. Fix anything wrong. Do not submit unchecked LLM text.

For deeper chapters (design decisions, evaluation) also attach `docs/PROJECT_BIOGRAPHY.md` (every decision and what was
verified, in order) and `docs/DEV_SETUP.md` (how each part works). They are long; attach only the sections you need.

## Rules for the LLM (the prompts in file 05 repeat these; if you write your own prompt, include them)

1. **Use only facts from the provided files.** If something is not there, write "[NOT IN SOURCES]" instead of guessing.
2. **Never invent numbers**: no accuracy percentages, user counts, response times, survey results or satisfaction
   figures. The project has no real-user data. Counts of content (paths, scenarios, tests) are in file 03.
3. **Do not claim the system is deployed.** It runs locally and has never been deployed.
4. **Do not claim the career quiz is validated against real student outcomes.** Its signals are hand-authored
   judgement; it is tested for internal consistency only (see file 04).
5. **Do not describe the Goals page as changing the career match.** The match comes from the quiz only.
6. **Do not describe a leaderboard, social features, mobile app, or chat bot.** None exist.
7. **Do not mention the "Skill DNA Map", "Piston" or phases 1-3 as they appear in `LevelUp_DSA_Master_Document.md`.**
   That document is an early plan and is out of date (see `docs/README.md`).
8. Keep the tone plain and factual. No marketing words ("revolutionary", "state-of-the-art", "AI-powered" without saying what).

## What to hand to a teammate who does not have the code

- Send them this folder (or just `CONTEXT_PACK.md`), plus screenshots (file 06).
- **Never send the `.env` file or any API key.** The key files are private; teammates do not need them to write documents.
- To let them read the code: GitHub repository Settings, Collaborators, add their GitHub usernames (read access is enough).

## Keeping the pack accurate

File 03 and `CONTEXT_PACK.md` are generated. After any change to the app run:

```bash
PYTHONPATH=. python scripts/build_handover_pack.py          # rewrite both files
PYTHONPATH=. python scripts/build_handover_pack.py --check  # only report whether they are out of date
```

The hand-written files (01, 02, 04, 05, 06, 07) must be updated by a person if a feature changes.

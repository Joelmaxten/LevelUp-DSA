"""
Builds the machine-written parts of the documentation hand-over pack in docs/handover/.

  PYTHONPATH=. python scripts/build_handover_pack.py            # writes the two files below
  PYTHONPATH=. python scripts/build_handover_pack.py --check    # writes nothing; exits 1 if either file is out of date

Writes:
  docs/handover/03_REFERENCE_GENERATED.md   routes, database tables, modules, content counts and test suites, all read
                                            from the code and data files, so they cannot drift from the app
  docs/handover/CONTEXT_PACK.md             00..07 of the pack joined into ONE file, for pasting into any LLM

It needs no database connection, no network and no API key. The hand-written files (00, 01, 02, 04..07) are not touched.
"""
import ast
import glob
import json
import os
import pickle
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

OUT_DIR = ROOT / "docs" / "handover"
GENERATED = OUT_DIR / "03_REFERENCE_GENERATED.md"
CONTEXT = OUT_DIR / "CONTEXT_PACK.md"
HAND_WRITTEN = ["00_START_HERE.md", "01_SYSTEM_OVERVIEW.md", "02_FEATURE_GUIDE.md", "03_REFERENCE_GENERATED.md",
                "04_VERIFICATION_AND_LIMITS.md", "05_REPORT_OUTLINE_AND_PROMPTS.md", "06_SCREENSHOT_GUIDE.md",
                "07_GLOSSARY_AND_FAQ.md"]



# Notes for routes and modules that have no docstring of their own. Keyed by (group, path, method).
ROUTE_NOTES = {
    ("(app)", "/", "GET"): "Home page: the phases of the app side by side.",
    ("(app)", "/conversation", "GET"): "The Goals page (\"Personalise your plan\").",
    ("(app)", "/dashboard", "GET"): "Dashboard page: saved quiz result, roadmap, resume, scenarios, level and badges.",
    ("(app)", "/db-check", "GET"): "Database health check; reports only ok or failed, never an error text.",
    ("(app)", "/login", "GET"): "Login page.",
    ("(app)", "/profile", "GET"): "Profile page.",
    ("(app)", "/quiz", "GET"): "Career quiz page.",
    ("(app)", "/resume", "GET"): "Resume analyzer page.",
    ("(app)", "/roadmap", "GET"): "Roadmap page.",
    ("(app)", "/scenarios", "GET"): "Scenarios page: the level map and the scenario player.",
    ("(app)", "/signup", "GET"): "Signup page.",
    ("gamification", "/gamification", "GET"): "XP, level, streak and badges, calculated from the student's activity.",
    ("auth", "/login", "POST"): "Log in with a username or an email, plus the password.",
    ("auth", "/logout", "POST"): "Log out.",
    ("auth", "/signup", "POST"): "Create an account (username, email, password).",
    ("career_paths", "/career/options", "GET"): "The career paths a student can pick from, with the top quiz matches marked.",
    ("conversation", "/conversation/answer", "POST"): "Record one Goals answer; the last one also saves the career profile and returns what was tailored.",
    ("conversation", "/conversation/start", "POST"): "Start the Goals questions (needs a finished quiz).",
    ("dashboard", "/dashboard/data", "GET"): "Everything the dashboard shows, in one response.",
    ("profile", "/profile/avatar", "GET"): "The student's profile picture.",
    ("profile", "/profile/avatar", "POST"): "Upload a profile picture (re-encoded to a 256x256 JPEG).",
    ("profile", "/profile/avatar/delete", "POST"): "Remove the profile picture.",
    ("profile", "/profile/data", "GET"): "The profile page's data: details, picture flag, progress card.",
    ("profile", "/profile/password", "POST"): "Change the password (needs the current one; rate-limited).",
    ("quiz", "/quiz/answer", "POST"): "Record one quiz answer; returns the next question, or the ranked results when the quiz ends.",
    ("quiz", "/quiz/start", "POST"): "Start a new quiz.",
    ("readiness", "/readiness", "GET"): "The placement readiness score and its four components.",
    ("resume", "/resume/latest", "GET"): "The student's latest saved resume analysis.",
    ("resume", "/resume/upload", "POST"): "Upload a PDF and analyze it against a target career path (skills, gaps, ATS score, feedback, salary).",
    ("roadmap", "/roadmap/<int:roadmap_id>", "GET"): "One saved roadmap.",
    ("roadmap", "/roadmap/<int:roadmap_id>/resources", "POST"): "Find videos and resources for a roadmap's steps.",
    ("roadmap", "/roadmap/generate", "POST"): "Generate a roadmap and wait for it (the older, blocking route).",
    ("roadmap", "/roadmap/jobs/<job_id>", "GET"): "Status of a background roadmap job.",
    ("roadmap", "/roadmap/latest", "GET"): "The student's most recent roadmap.",
    ("roadmap", "/roadmap/list", "GET"): "All the student's saved roadmaps.",
    ("scenarios", "/scenarios/<path_slug>", "GET"): "The level map for one path: each scenario's state, best score and the recommended one.",
    ("scenarios", "/scenarios/<scenario_id>/start", "POST"): "Start or resume an attempt (403 scenario_locked if the previous scenario is not passed).",
    ("scenarios", "/scenarios/<scenario_id>/submit", "POST"): "Grade the whole attempt on the server; returns the result and the rewards.",
    ("scenarios", "/scenarios/paths", "GET"): "The paths that have scenarios.",
}
MODULE_NOTES = {
    "app/__init__.py": "The application factory (create_app): registers every route, the login gate, error pages and the restart-logout hook.",
    "app/config.py": "Settings read from environment variables, with development and production modes.",
    "app/models.py": "The database tables (SQLAlchemy models).",
    "app/routes/_util.py": "Small helpers shared by the route files (JSON errors, input checks).",
    "app/routes/auth.py": "Signup, login and logout.",
    "app/routes/conversation.py": "The Goals questions: start, answer, and saving the career profile.",
    "app/routes/quiz.py": "The career quiz: start and answer.",
    "app/routes/resume.py": "Resume upload, analysis and the latest saved result.",
    "app/routes/roadmap.py": "Roadmap generation, listing, progress and resources.",
}

def first_sentence(text):
    if not text:
        return ""
    text = " ".join(text.strip().split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return (match.group(1) if match else text)[:230]


def module_doc(path):
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except SyntaxError:
        return ""
    return first_sentence(ast.get_docstring(tree))


def line_count(path):
    return sum(1 for _ in open(path, encoding="utf-8", errors="replace"))


def md_escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def routes_section():
    os.environ.setdefault("FLASK_ENV", "development")
    from app import create_app
    import inspect

    app = create_app()
    rows = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        view = app.view_functions[rule.endpoint]
        try:
            source = inspect.getsource(inspect.unwrap(view))
        except (OSError, TypeError):
            source = ""
        login = "yes" if ("@login_required" in source or "@page_login_required" in source) else "no"
        methods = ",".join(sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")))
        blueprint = rule.endpoint.split(".")[0] if "." in rule.endpoint else "(app)"
        summary = ROUTE_NOTES.get((blueprint, str(rule.rule), methods.split(",")[0])) or first_sentence(inspect.getdoc(inspect.unwrap(view)) or "")
        rows.append((blueprint, str(rule.rule), methods, login, summary))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    lines = ["| Group | Path | Method | Login needed | What it does (from its docstring) |", "|---|---|---|---|---|"]
    for blueprint, path, methods, login, summary in rows:
        lines.append(f"| {blueprint} | `{path}` | {methods} | {login} | {md_escape(summary)} |")
    return "\n".join(lines), len(rows)


def tables_section():
    from app import db  # noqa: F401  (importing models registers the tables)
    from app import models  # noqa: F401

    out = []
    tables = db.metadata.sorted_tables
    for table in tables:
        out.append(f"### `{table.name}`")
        out.append("")
        out.append("| Column | Type | Notes |")
        out.append("|---|---|---|")
        for col in table.columns:
            notes = []
            if col.primary_key:
                notes.append("primary key")
            for fk in col.foreign_keys:
                notes.append(f"-> {fk.column.table.name}.{fk.column.name}")
            if col.unique:
                notes.append("unique")
            if not col.nullable and not col.primary_key:
                notes.append("required")
            out.append(f"| `{col.name}` | {md_escape(col.type)} | {', '.join(notes)} |")
        out.append("")
    return "\n".join(out), len(tables)


def modules_section():
    groups = [("app/ (application root)", "app/*.py"), ("app/routes/ (HTTP routes)", "app/routes/*.py"),
              ("app/pipeline/ (logic: quiz, roadmaps, resume, scenarios, gamification, LLM)", "app/pipeline/*.py")]
    out = []
    for title, pattern in groups:
        out.append(f"### {title}")
        out.append("")
        out.append("| File | Lines | Purpose (first sentence of its docstring) |")
        out.append("|---|---|---|")
        for path in sorted(glob.glob(pattern)):
            name = os.path.basename(path)
            if name == "__init__.py" and line_count(path) == 0:
                continue
            out.append(f"| `{path}` | {line_count(path)} | {md_escape(MODULE_NOTES.get(path) or module_doc(path) or '(no docstring)')} |")
        out.append("")
    out.append("### Templates (pages) and static files")
    out.append("")
    out.append("| File | Lines |")
    out.append("|---|---|")
    for pattern in ("app/templates/*.html", "app/static/js/*.js", "app/static/css/*.css"):
        for path in sorted(glob.glob(pattern)):
            out.append(f"| `{path}` | {line_count(path)} |")
    return "\n".join(out)


def content_section():
    from app.pipeline.career_path_registry import CAREER_PATHS
    from app.pipeline.career_quiz_data import QUESTIONS
    from app.pipeline.career_quiz_engine import MAX_QUESTIONS, MIN_QUESTIONS
    from app.pipeline.gamification import BADGES, LEVELS

    scenarios = questions = problems = variants = 0
    per_path = []
    for path in sorted(glob.glob("data/scenarios/*.json")):
        data = json.load(open(path, encoding="utf-8"))
        scs = data.get("scenarios", [])
        qn = sum(len(s.get("questions", [])) for s in scs)
        pr = sum(len(s.get("code_pool", [])) for s in scs)
        va = sum(len(p.get("variants", [])) for s in scs for p in s.get("code_pool", []))
        scenarios += len(scs)
        questions += qn
        problems += pr
        variants += va
        per_path.append((data.get("path", os.path.basename(path)), len(scs), qn, pr, va))
    base = sorted(glob.glob("data/base_roadmaps/*.json"))
    steps_by_path = []
    for path in base:
        data = json.load(open(path, encoding="utf-8"))
        roadmap = data.get("roadmap", {})
        phases = roadmap.get("phases", [])
        steps = sum(len(p.get("steps", [])) for p in phases)
        steps_by_path.append((data.get("metadata", {}).get("career_path", os.path.basename(path)), len(phases), steps,
                              data.get("metadata", {}).get("model_id", "?")))
    try:
        kb_chunks = len(pickle.load(open("data/processed/faiss_index_meta.pkl", "rb")))
    except Exception:
        kb_chunks = "unknown"
    out = ["| Fact | Value |", "|---|---|",
           f"| Career paths | {len(CAREER_PATHS)} |",
           f"| Quiz question bank | {len(QUESTIONS)} questions; a student is asked {MIN_QUESTIONS} to {MAX_QUESTIONS} |",
           f"| Scenarios | {scenarios} ({scenarios // max(len(per_path), 1)} per path) |",
           f"| Scenario questions | {questions} |",
           f"| Coding problems | {problems} |",
           f"| Coding problem variants | {variants} |",
           f"| Reviewed base roadmaps | {len(base)} files in data/base_roadmaps/ |",
           f"| Knowledge-base chunks in the FAISS index | {kb_chunks} |",
           f"| XP levels | {len(LEVELS)}: " + ", ".join(f"{name} ({xp})" for xp, name in LEVELS) + " |",
           f"| Badges | {len(BADGES)} |", ""]
    out.append("**The 15 career paths:** " + "; ".join(CAREER_PATHS) + ".")
    out.append("")
    out.append("**Scenario content per path**")
    out.append("")
    out.append("| Path | Scenarios | Questions | Coding problems | Variants |")
    out.append("|---|---|---|---|---|")
    for row in per_path:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    out.append("")
    out.append("**Base roadmaps** (`metadata.model_id` says which model wrote the reply that the generator processed)")
    out.append("")
    out.append("| Path | Phases | Steps | Model id in the file |")
    out.append("|---|---|---|---|")
    for row in steps_by_path:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def tests_section():
    out = ["| Script | What it checks (first sentence of its docstring) |", "|---|---|"]
    for path in sorted(glob.glob("scripts/smoke_test_*.py")):
        out.append(f"| `{path}` | {md_escape(module_doc(path) or '(no docstring)')} |")
    return "\n".join(out)


def build_generated():
    routes, n_routes = routes_section()
    tables, n_tables = tables_section()
    return f"""# 03. Reference (machine-generated)

> Generated on {date.today().isoformat()} by `scripts/build_handover_pack.py` from the code and data files.
> **Do not edit by hand.** To refresh it after a change: `PYTHONPATH=. python scripts/build_handover_pack.py`.
> Everything here is read from the app itself (routes, database models, files), so it is exact. Narrative
> explanations are in files 01 and 02; this file is for looking things up.

## 1. Content and numbers

{content_section()}

## 2. Database tables ({n_tables} tables)

The database is PostgreSQL, accessed through SQLAlchemy (`app/models.py`). There are no migrations; tables are created
with `db.create_all()` and one-off scripts in `scripts/` add columns to older databases.

{tables}

## 3. HTTP routes ({n_routes} routes)

"Login needed" is read from the route's decorator (`@login_required` returns JSON 401; `@page_login_required` redirects
a browser to /login). Every POST, PUT, PATCH and DELETE also needs a CSRF token header.

{routes}

## 4. Code map

{modules_section()}

## 5. Test scripts

{tests_section()}
"""


def build_context(generated_text):
    parts = []
    for name in HAND_WRITTEN:
        path = OUT_DIR / name
        if name == "03_REFERENCE_GENERATED.md":
            text = generated_text
        elif path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            text = f"# {name}\n\n(missing: this file has not been written yet)\n"
        parts.append(f"\n\n<!-- ===== BEGIN {name} ===== -->\n\n{text.strip()}\n\n<!-- ===== END {name} ===== -->\n")
    header = ("# LevelUp DSA: complete documentation context pack\n\n"
              "This single file joins the files 00 to 07 of `docs/handover/`. It is generated by "
              "`scripts/build_handover_pack.py`; do not edit it by hand. Paste all of it into an LLM, then give the LLM "
              "the task prompt from section 05.\n")
    return header + "".join(parts)


def main():
    check = "--check" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = build_generated()
    context = build_context(generated)
    if check:
        stale = []
        for path, text in ((GENERATED, generated), (CONTEXT, context)):
            # the generated file carries today's date; compare everything except that line
            normal = lambda s: re.sub(r"Generated on \d{4}-\d{2}-\d{2}", "Generated on DATE", s)
            if not path.exists() or normal(path.read_text(encoding="utf-8")) != normal(text):
                stale.append(path.name)
        if stale:
            print("OUT OF DATE:", ", ".join(stale), "- run: PYTHONPATH=. python scripts/build_handover_pack.py")
            return 1
        print("up to date")
        return 0
    GENERATED.write_text(generated, encoding="utf-8")
    CONTEXT.write_text(context, encoding="utf-8")
    words = len(context.split())
    print(f"wrote {GENERATED.relative_to(ROOT)} ({len(generated.splitlines())} lines)")
    print(f"wrote {CONTEXT.relative_to(ROOT)} ({len(context.splitlines())} lines, about {words} words, "
          f"roughly {int(words * 1.4)} tokens)")
    missing = [n for n in HAND_WRITTEN if n != "03_REFERENCE_GENERATED.md" and not (OUT_DIR / n).exists()]
    if missing:
        print("not written yet:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())

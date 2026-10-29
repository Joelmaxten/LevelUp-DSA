"""
One command that makes a fresh clone ready to run, and tells you plainly what is still missing. Safe to run again at any
time (it never deletes anything and only fills tables that are empty).

Before it: Python packages installed (pip install -r requirements.txt), the spaCy model downloaded
(python -m spacy download en_core_web_sm), PostgreSQL running with an empty database created, and .env filled in
(DATABASE_URL and SECRET_KEY at least). See docs/DEV_SETUP.md.

What it does:
 1. checks .env, the spaCy model and the committed search index
 2. connects to the database and creates every table (db.create_all, additive)
 3. creates the resume upload folder
 4. fills survey_respondents and job_listings from data/seed/ when they are empty
 5. prints a status list. Exit code 0 = ready to run; 1 = something above is missing (it says what).

Usage:
    PYTHONPATH=. python scripts/setup_dev.py
    PYTHONPATH=. python scripts/setup_dev.py --check     # report only, change nothing
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

WHY = {"survey_respondents": "The resume analyzer needs it (without it no skills are found).",
       "job_listings": "Salary insights need it."}
REQUIRED_FILES = [Path("data/processed/faiss_index.faiss"), Path("data/processed/faiss_index_meta.pkl")]


def main(argv):
    check_only = "--check" in argv
    problems, notes = [], []

    def line(ok, text):
        print(f"[{'OK' if ok else '!!'}] {text}")

    # 1. local files and settings (values are never printed, only whether they are set)
    env_ok = Path(".env").exists()
    line(env_ok, ".env exists" if env_ok else ".env is missing: copy .env.example to .env and fill it in")
    if not env_ok:
        problems.append(".env")
    for name in ("DATABASE_URL", "SECRET_KEY"):
        is_set = bool(os.environ.get(name, "").strip())
        line(is_set, f"{name} is set" if is_set else f"{name} is not set in .env")
        if not is_set:
            problems.append(name)
    if not os.environ.get("GEMINI_API_KEY", "").strip() and not os.environ.get("RESUME_PROVIDER", "").strip():
        notes.append("no GEMINI_API_KEY (and no RESUME_PROVIDER): roadmap personalisation and resume feedback will be skipped")
    try:
        import spacy.util
        spacy_ok = spacy.util.is_package("en_core_web_sm")
    except Exception:
        spacy_ok = False
    line(spacy_ok, "spaCy model en_core_web_sm is installed" if spacy_ok
         else "spaCy model missing: run  python -m spacy download en_core_web_sm")
    if not spacy_ok:
        problems.append("spaCy model")
    for path in REQUIRED_FILES:
        present = path.exists()
        line(present, f"{path} is present" if present else f"{path} is missing: run  git pull  (it is committed to the repo)")
        if not present:
            problems.append(str(path))
    if problems and any(p in problems for p in ("DATABASE_URL", ".env")):
        print("\nFix the items marked !! above, then run this again.")
        return 1

    # 2-4. database
    from app import create_app, db
    from app.models import JobListing, SurveyRespondent
    from app.seed_data import seed_status

    app = create_app()
    tables = (SurveyRespondent.__table__, JobListing.__table__)
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.exec_driver_sql("select 1")
        except Exception as exc:
            line(False, f"cannot connect to the database ({type(exc).__name__}): is PostgreSQL running, does the database in "
                        "DATABASE_URL exist, is the password right?")
            return 1
        line(True, "connected to the database")
        if not check_only:
            db.create_all()
            line(True, "tables created or already present")
            upload = Path(app.config["UPLOAD_FOLDER"])
            upload.mkdir(parents=True, exist_ok=True)
            line(True, f"upload folder {upload} is ready")
        with db.engine.connect() as conn:
            before = seed_status(conn, tables)
        if any(not count for count in before.values()) and not check_only:
            from scripts.seed_data_tables import seed_all
            seed_all(out=lambda text: print("     " + text))
        with db.engine.connect() as conn:
            after = seed_status(conn, tables)

    for name, count in after.items():
        ok = bool(count)
        line(ok, f"{name}: {count} rows" if ok else
             f"{name} is EMPTY. " + WHY[name] + " Get data/seed/ from the project owner (see data/seed/README.md), "
             "then run this again")
        if not ok:
            problems.append(name)
    for note in notes:
        print(f"[..] {note}")
    print("\nReady: start the app with  python run.py" if not problems else
          f"\nNot ready yet: {', '.join(problems)}.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

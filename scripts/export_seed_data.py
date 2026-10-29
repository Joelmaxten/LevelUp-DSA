"""
Write the two data tables (survey_respondents, job_listings) from YOUR database to data/seed/*.jsonl.gz, so a
teammate's fresh clone can load the same data with scripts/setup_dev.py. Read-only on the database. Run it on the
machine that has the real data, once (and again if you rebuild the tables).

Usage:
    PYTHONPATH=. python scripts/export_seed_data.py

It refuses to write an empty table over an existing file, so running it on a machine without data cannot destroy the
good export. data/seed/ is in .gitignore until you decide whether the data may be published (see data/seed/README.md).
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db  # noqa: E402
from app.models import JobListing, SurveyRespondent  # noqa: E402
from app.seed_data import export_rows, seed_path, write_jsonl_gz  # noqa: E402


def main():
    app = create_app()
    problems = 0
    with app.app_context(), db.engine.connect() as conn:
        for model in (SurveyRespondent, JobListing):
            table = model.__table__
            rows = export_rows(conn, table)
            path = seed_path(table.name)
            if not rows:
                print(f"{table.name}: EMPTY in this database, nothing written"
                      + (f" (the existing {path} is kept)" if path.exists() else ""))
                problems += 1
                continue
            write_jsonl_gz(rows, path)
            print(f"{table.name}: {len(rows)} rows -> {path} ({path.stat().st_size / 1024:.0f} KB)")
    if problems:
        print("\nNot everything was exported: run this on the machine that has the loaded tables.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

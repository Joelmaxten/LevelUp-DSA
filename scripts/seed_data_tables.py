"""
Load the two data tables (survey_respondents, job_listings) from data/seed/*.jsonl.gz into the database. A table that
already has rows is left alone unless you pass --replace. Usually you do not run this directly: scripts/setup_dev.py
does it. See app/seed_data.py for why these tables matter.

Usage:
    PYTHONPATH=. python scripts/seed_data_tables.py            # fill empty tables only
    PYTHONPATH=. python scripts/seed_data_tables.py --replace  # overwrite whatever is there
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db  # noqa: E402
from app.models import JobListing, SurveyRespondent  # noqa: E402
from app.seed_data import load_rows, read_jsonl_gz, seed_path  # noqa: E402


def seed_all(replace=False, out=print):
    """Load every table whose seed file exists. Returns the number of tables that could not be filled."""
    missing = 0
    app = create_app()
    with app.app_context():
        db.create_all()
        for model in (SurveyRespondent, JobListing):
            table, path = model.__table__, seed_path(model.__table__.name)
            if not path.exists():
                out(f"{table.name}: no seed file at {path}")
                missing += 1
                continue
            rows = read_jsonl_gz(path)
            with db.engine.begin() as conn:
                state, number = load_rows(conn, table, rows, replace=replace)
            out(f"{table.name}: {'loaded ' + str(number) + ' rows' if state == 'loaded' else 'already has ' + str(number) + ' rows, left alone (use --replace to overwrite)'}")
    return missing


if __name__ == "__main__":
    sys.exit(1 if seed_all(replace="--replace" in sys.argv) else 0)

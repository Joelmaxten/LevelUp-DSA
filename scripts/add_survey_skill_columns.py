"""
Adds the survey's other skill-like columns to survey_respondents and fills them,
WITHOUT touching any existing field. Re-runnable.

Why: resume-to-path fit (mode 1) needs, per career path, how common each skill is among
respondents. The table only held languages, databases, platforms and web frameworks. The
2025 survey CSV has no MiscTech/ToolsTech columns (those were 2024); its other skill-like
columns are DevEnvsHaveWorkedWith (IDEs/editors), SOTagsHaveWorkedWith (newer technologies
and frameworks) and OfficeStackAsyncHaveWorkedWith (GitHub, Jira, ...). They become the
nullable ARRAY columns dev_envs, so_tags and office_stack.

Steps, each printed:
 1. read the CSV through so_survey_processor.process() (India filter, same row order as the
    original load) and require exactly as many rows as the table has;
 2. back the table up to scratch/survey_respondents_backup_<timestamp>.json;
 3. show the table's columns, ALTER TABLE ... ADD COLUMN IF NOT EXISTS, show them again;
 4. match CSV rows to table rows by position (id order) after proving the existing fields
    (dev_type + the four skill lists) agree on EVERY row, and write the new columns;
 5. verify all rows: old fields unchanged against the backup, new columns populated;
 6. print the top 15 values of each new column.
Stops without writing if the row counts or any existing field disagree.

Usage:
    PYTHONPATH=. python scripts/add_survey_skill_columns.py [path/to/survey_results_public.csv]
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text

from app import create_app, db
from app.models import SurveyRespondent
from app.pipeline.so_survey_processor import SKILL_COLUMNS, process

CSV_DEFAULT = "data/raw/survey_results_public.csv"
NEW_COLUMNS = {"DevEnvsHaveWorkedWith": "dev_envs", "SOTagsHaveWorkedWith": "so_tags", "OfficeStackAsyncHaveWorkedWith": "office_stack"}
OLD_SKILLS = {csv_col: col for csv_col, col in SKILL_COLUMNS.items() if col not in NEW_COLUMNS.values()}
BACKUP_FIELDS = ["id", "dev_type", "career_path", "years_code", "work_exp", "ed_level", "remote_work",
                 "converted_comp_yearly", "languages", "databases", "platforms", "webframes", "source"]


def show_columns(label):
    rows = db.session.execute(text(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'survey_respondents' ORDER BY ordinal_position")).fetchall()
    print(f"\nsurvey_respondents columns {label}:")
    for name, dtype, nullable in rows:
        print(f"  {name:<24} {dtype:<18} nullable={nullable}")


def old_fields_equal(row, csv_row):
    dev = None if pd.isna(csv_row["DevType"]) else csv_row["DevType"]
    if row.dev_type != dev:
        return False
    return all(list(getattr(row, col) or []) == csv_row[csv_col] for csv_col, col in OLD_SKILLS.items())


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else CSV_DEFAULT
    app = create_app()
    with app.app_context():
        df = process(csv_path)
        rows = SurveyRespondent.query.with_entities(*[getattr(SurveyRespondent, f) for f in BACKUP_FIELDS]).order_by(SurveyRespondent.id).all()
        print(f"CSV India rows: {len(df)}; table rows: {len(rows)}")
        if len(df) != len(rows):
            sys.exit("STOP: row counts differ; the CSV is not the one the table was built from.")

        backup = Path("scratch") / f"survey_respondents_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
        backup.parent.mkdir(exist_ok=True)
        backup.write_text(json.dumps([dict(zip(BACKUP_FIELDS, r)) for r in rows], default=str), encoding="utf-8")
        print(f"Backed up {len(rows)} rows to {backup}")

        show_columns("BEFORE")
        for col in NEW_COLUMNS.values():
            db.session.execute(text(f"ALTER TABLE survey_respondents ADD COLUMN IF NOT EXISTS {col} VARCHAR[]"))
        db.session.commit()
        show_columns("AFTER")

        orm_rows = SurveyRespondent.query.order_by(SurveyRespondent.id).all()
        mismatched = [r.id for r, (_, d) in zip(orm_rows, df.iterrows()) if not old_fields_equal(r, d)]
        if mismatched:
            sys.exit(f"STOP: existing fields disagree with the CSV on {len(mismatched)} rows (first ids {mismatched[:5]}); nothing written.")
        print("\nExisting fields (dev_type, languages, databases, platforms, webframes) agree with the CSV on every row.")

        for row, (_, d) in zip(orm_rows, df.iterrows()):
            for csv_col, col in NEW_COLUMNS.items():
                setattr(row, col, d[csv_col])
        db.session.commit()

        after = SurveyRespondent.query.order_by(SurveyRespondent.id).all()
        changed = 0
        for new, old in zip(after, rows):
            old_d = dict(zip(BACKUP_FIELDS, old))
            for f in BACKUP_FIELDS:
                a, b = getattr(new, f), old_d[f]
                if a != b and not (isinstance(a, list) and a == b):
                    changed += 1
        print(f"Verification over {len(after)} rows: existing fields changed = {changed} (must be 0)")
        for col in NEW_COLUMNS.values():
            populated = sum(1 for r in after if getattr(r, col) is not None)
            non_empty = sum(1 for r in after if getattr(r, col))
            print(f"  {col}: populated (not NULL) {populated}/{len(after)}, with at least one value {non_empty}")
        for col in NEW_COLUMNS.values():
            counts = Counter(v for r in after for v in (getattr(r, col) or []))
            print(f"\nTop 15 in {col} ({len(counts)} distinct):")
            for value, n in counts.most_common(15):
                print(f"  {n:>5}  {value}")
        if changed:
            sys.exit("Existing fields changed - restore from the backup.")


if __name__ == "__main__":
    main()

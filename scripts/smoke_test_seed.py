"""
Checks for app/seed_data.py (export/load of survey_respondents and job_listings) and the fresh-clone helpers.
Runs against a throw-away schema in the configured database, so real data is never touched.

Usage:  PYTHONPATH=. python scripts/smoke_test_seed.py
"""
import os
import sys
import tempfile
import uuid

from dotenv import load_dotenv
load_dotenv(".env")

from sqlalchemy import create_engine, text

from app.config import Config
from app.models import JobListing, SurveyRespondent
from app.seed_data import (count_rows, export_rows, load_rows, read_jsonl_gz, seed_path, seed_status, write_jsonl_gz)

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


def survey_rows(n, start=1):
    return [{"id": start + i, "dev_type": "Developer, back-end", "career_path": "Backend",
             "years_code": float(i), "work_exp": float(i), "ed_level": "Bachelor's", "remote_work": "Remote",
             "converted_comp_yearly": 100000.0 + i, "languages": ["Python", "SQL"], "databases": ["PostgreSQL"],
             "platforms": [], "webframes": ["Flask"], "dev_envs": ["VS Code"], "so_tags": None, "office_stack": None,
             "source": "test"} for i in range(n)]


def main():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    schema = "seedtest_" + uuid.uuid4().hex[:8]
    sv, jb = SurveyRespondent.__table__, JobListing.__table__
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.begin() as conn:
            for t in (sv, jb):
                t.create(conn.execution_options(schema_translate_map={None: schema}), checkfirst=False)

        names = {c.name for c in sv.columns}
        rows = survey_rows(2500)
        rows = [{k: v for k, v in r.items() if k in names} for r in rows]

        with engine.begin() as conn:
            check("empty at start", count_rows(conn, sv, schema) == 0)
            state, n = load_rows(conn, sv, rows, schema)
            check("loads into empty table", (state, n) == ("loaded", 2500), (state, n))
            check("count after load", count_rows(conn, sv, schema) == 2500)
            state, n = load_rows(conn, sv, survey_rows(3, 9000), schema)
            check("non-empty table is skipped", (state, n) == ("skipped", 2500), (state, n))
            check("skip leaves data alone", count_rows(conn, sv, schema) == 2500)
            # new rows after a load must not collide with seeded ids
            conn.execution_options(schema_translate_map={None: schema}).execute(
                sv.insert().values(dev_type="x", career_path="Backend"))
            check("sequence moved past max id", count_rows(conn, sv, schema) == 2501)

        # round trip through a file
        with engine.connect() as conn:
            out = export_rows(conn, sv, schema)
        check("export is ordered by id", [r["id"] for r in out] == sorted(r["id"] for r in out))
        check("arrays survive export", out[0]["languages"] == ["Python", "SQL"], out[0]["languages"])
        with tempfile.TemporaryDirectory() as tmp:
            p1, p2 = os.path.join(tmp, "a.jsonl.gz"), os.path.join(tmp, "b.jsonl.gz")
            write_jsonl_gz(out, p1)
            write_jsonl_gz(out, p2)
            check("same data gives identical bytes", open(p1, "rb").read() == open(p2, "rb").read())
            back = read_jsonl_gz(p1)
            check("file round trip equals export", back == out)
            with engine.begin() as conn:
                state, n = load_rows(conn, sv, back, schema, replace=True)
                check("replace reloads", (state, n) == ("loaded", 2501), (state, n))
                check("replace keeps the count", count_rows(conn, sv, schema) == 2501)
                check("ids preserved", [r["id"] for r in export_rows(conn, sv, schema)] == [r["id"] for r in out])

        # drift handling
        with engine.begin() as conn:
            try:
                load_rows(conn, sv, [{"id": 1, "nope": 1}], schema, replace=True)
                check("unknown column raises", False)
            except ValueError as exc:
                check("unknown column raises", "nope" in str(exc))
            check("failed validation deleted nothing", count_rows(conn, sv, schema) == 2501)
            state, n = load_rows(conn, jb, [{"id": 1, "job_title": "Intern"}], schema)
            check("missing columns become NULL", (state, n) == ("loaded", 1), (state, n))
            check("status counts", seed_status(conn, (sv, jb), schema) == {sv.name: 2501, jb.name: 1})

        check("seed path", str(seed_path("job_listings")).endswith("data/seed/job_listings.jsonl.gz"))
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

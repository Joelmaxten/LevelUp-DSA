"""
Export and load the two data tables the app cannot run without: survey_respondents (the Stack Overflow survey rows,
India only) and job_listings (the processed India jobs). The resume analyzer builds its skill vocabulary and each
path's required skills from survey_respondents, so an empty table means a resume finds no skills at all.

The tables are filled from large CSVs that are not in git (data/raw/ is ignored), so a new machine needs another way
to get them: scripts/export_seed_data.py writes them to data/seed/*.jsonl.gz and scripts/seed_data_tables.py loads
them. Everything here takes an open SQLAlchemy connection and an optional schema, so the tests can run against a
throw-away schema and never touch real data.

File format: gzip, one JSON object per line, every column of the table (id included, so row order and ids survive).
"""
import gzip
import json
from pathlib import Path

from sqlalchemy import func, select, text

SEED_DIR = Path("data/seed")
CHUNK = 1000


def seed_path(table_name):
    return SEED_DIR / f"{table_name}.jsonl.gz"


def _bound(conn, schema):
    return conn.execution_options(schema_translate_map={None: schema}) if schema else conn


def count_rows(conn, table, schema=None):
    return _bound(conn, schema).execute(select(func.count()).select_from(table)).scalar()


def export_rows(conn, table, schema=None):
    """Every row of the table as a list of {column: value}, ordered by id."""
    result = _bound(conn, schema).execute(select(table).order_by(table.c.id))
    names = [c.name for c in table.columns]
    return [dict(zip(names, row)) for row in result.fetchall()]


def write_jsonl_gz(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the bytes identical when the data is identical (clean git diffs, repeatable checks)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    return len(rows)


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_rows(conn, table, rows, schema=None, replace=False):
    """Insert rows into the table. Returns ("loaded", n) or ("skipped", existing_count).

    A table that already has rows is left alone unless replace=True. Columns missing from a row become NULL (a seed
    written before a column existed still loads); a column the table does not have raises ValueError, because that
    means the file and the models have drifted apart. The id sequence is moved past the largest id afterwards so new
    rows do not collide."""
    bound = _bound(conn, schema)
    existing = count_rows(conn, table, schema)
    if existing and not replace:
        return "skipped", existing
    known = {c.name for c in table.columns}
    for row in rows:
        unknown = set(row) - known
        if unknown:
            raise ValueError(f"{table.name}: the file has columns the table does not: {sorted(unknown)}")
    if existing:
        bound.execute(table.delete())
    for start in range(0, len(rows), CHUNK):
        bound.execute(table.insert(), rows[start:start + CHUNK])
    qualified = f'"{schema}"."{table.name}"' if schema else f'"{table.name}"'
    conn.execute(text(
        f"SELECT setval(pg_get_serial_sequence('{qualified}', 'id'), (SELECT COALESCE(MAX(id), 1) FROM {qualified}))"))
    return "loaded", len(rows)


def seed_status(conn, tables, schema=None):
    """{table_name: row count, or None when the table does not exist yet}."""
    status = {}
    for table in tables:
        try:
            status[table.name] = count_rows(conn, table, schema)
        except Exception:
            conn.rollback() if hasattr(conn, "rollback") else None
            status[table.name] = None
    return status

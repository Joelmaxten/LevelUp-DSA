"""
Drops the tables of the removed Skill DNA Map (scenario code questions replaced it). The app no longer reads or
writes them; an older database may still have them, with seeded topics and any practice rows.

DRY RUN by default: lists each old table that exists and how many rows it has, and changes nothing.
--drop removes them (children first). This cannot be undone, so take a backup first if you want the rows:
    pg_dump -U postgres -d levelup_dsa_dev -t dsa_nodes -t dsa_problems -t user_dsa_activity -t node_mastery \
        -t dsa_problem_framings -t weakness_profiles -t user_attempts > old_dsa_tables.sql

Usage:
    PYTHONPATH=. python scripts/drop_old_dsa_tables.py            # dry run
    PYTHONPATH=. python scripts/drop_old_dsa_tables.py --drop     # really drop
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

# Children before parents, so foreign keys never block a drop.
OLD_TABLES = ["user_attempts", "weakness_profiles", "node_mastery", "user_dsa_activity", "dsa_problem_framings",
              "dsa_problems", "dsa_nodes"]


def main(argv):
    drop = "--drop" in argv
    app = create_app()
    with app.app_context():
        present = [t for t in OLD_TABLES
                   if db.session.execute(text("SELECT to_regclass(:t)"), {"t": t}).scalar() is not None]
        print(f"{'DROP' if drop else 'DRY RUN'}: {len(present)} of {len(OLD_TABLES)} old skill-map tables exist")
        for table in present:   # names come from OLD_TABLES only, never from input
            rows = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:<22} {rows} row(s)")
        if not drop:
            print("Nothing dropped. Re-run with --drop to remove the tables above.")
            return 0
        try:
            for table in present:
                db.session.execute(text(f"DROP TABLE {table}"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(f"Dropped {len(present)} table(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

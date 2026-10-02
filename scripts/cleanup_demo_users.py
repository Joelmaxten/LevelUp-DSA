"""
Remove the throwaway users the smoke tests (and manual testing) leave behind.

A user counts as a test user if their email ends in @example.com - which covers
the patterns the smoke tests generate (progresstest*, progressother*,
pathstest_*, adzunatest*, dsatest*, resumetest*, roadmaptest*, sectest*,
smoketest*, ytresourcetest*). Real signups should never use that domain.

DRY RUN by default: lists each matching user with how many rows they own in
every table, and changes nothing. Pass --delete to actually delete them (their
rows in every dependent table first, then the user; uploaded resume files on
disk too).

Usage:
    PYTHONPATH=. python scripts/cleanup_demo_users.py            # dry run
    PYTHONPATH=. python scripts/cleanup_demo_users.py --delete   # really delete
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import (
    CareerProfile, GeneratedRoadmap, NodeMastery, Resume, RoadmapProgress, SkillGap,
    User, UserAttempt, UserDSAActivity, UserProgress, WeaknessProfile,
)

EMAIL_SUFFIX = "@example.com"

# Child-first order. roadmap_progress references generated_roadmaps, so it goes before it;
# every other table here references only users (and shared reference data we never touch).
DEPENDENT_MODELS = [
    RoadmapProgress, GeneratedRoadmap, UserAttempt, UserDSAActivity, NodeMastery,
    WeaknessProfile, UserProgress, SkillGap, Resume, CareerProfile,
]


def check_all_user_tables_covered():
    """Fail loudly if a table gets a user_id foreign key later and this script doesn't know it."""
    covered = {m.__tablename__ for m in DEPENDENT_MODELS}
    for table in db.metadata.sorted_tables:
        if table.name == "users":
            continue
        if any(fk.column.table.name == "users" for fk in table.foreign_keys) and table.name not in covered:
            sys.exit(f"cleanup_demo_users.py doesn't know about table '{table.name}' (it references users). "
                     f"Add its model to DEPENDENT_MODELS before running.")


def main():
    delete = "--delete" in sys.argv
    app = create_app()

    with app.app_context():
        check_all_user_tables_covered()
        users = User.query.filter(User.email.ilike(f"%{EMAIL_SUFFIX}")).order_by(User.id).all()
        print(f"{'DELETE' if delete else 'DRY RUN'}: {len(users)} test user(s) matching *{EMAIL_SUFFIX}\n")

        totals = {m.__tablename__: 0 for m in DEPENDENT_MODELS}
        for user in users:
            counts = {m.__tablename__: m.query.filter_by(user_id=user.id).count() for m in DEPENDENT_MODELS}
            for name, n in counts.items():
                totals[name] += n
            nonzero = ", ".join(f"{name}={n}" for name, n in counts.items() if n) or "no rows in other tables"
            print(f"  id={user.id:<5} {user.email:<44} {nonzero}")

        if users:
            print("\nTotals across these users:")
            print("  users=%d, " % len(users) + ", ".join(f"{name}={n}" for name, n in totals.items() if n))

        if not delete:
            print("\nNothing deleted. Re-run with --delete to remove the users above.")
            return

        if not users:
            return

        ids = [u.id for u in users]
        files = [r.file_path for r in Resume.query.filter(Resume.user_id.in_(ids)).all() if r.file_path]
        try:
            for model in DEPENDENT_MODELS:
                model.query.filter(model.user_id.in_(ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        removed = 0
        for path in files:
            if os.path.isfile(path):
                os.remove(path)
                removed += 1
        print(f"\nDeleted {len(ids)} user(s) and their rows; removed {removed} uploaded resume file(s).")


if __name__ == "__main__":
    main()

"""
Adds the username column to the users table, gives every older account a username, and makes usernames unique.
Also creates the new user_profiles and user_avatars tables. Run it ONCE on any database made before the profile
work (the app's User model expects the column, so pages that load a user fail until it exists). Re-runnable.

What it does, each step printed:
 1. ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(20)   (additive, touches no existing value)
 2. for every account with no username: one built from the email (joel.m@x.com -> joel_m, then joel_m2, ...)
 3. CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)
 4. db.create_all() for the two new tables (it never changes existing tables)
Dry run by default: prints what it would do and changes nothing. Add --apply to do it.

Usage:
    PYTHONPATH=. python scripts/add_usernames.py            # dry run
    PYTHONPATH=. python scripts/add_usernames.py --apply
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app, db  # noqa: E402
from app import usernames  # noqa: E402


def main(argv):
    apply = "--apply" in argv
    app = create_app()
    with app.app_context():
        columns = {c["name"] for c in inspect(db.engine).get_columns("users")}
        has_column = "username" in columns
        print(f"users.username column: {'present' if has_column else 'MISSING'}")
        if not has_column:
            print("  -> ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(20)")
            if apply:
                db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(20)"))
                db.session.commit()

        if apply or has_column:
            rows = db.session.execute(text("SELECT id, email, username FROM users ORDER BY id")).all()
        else:
            rows = [(r[0], r[1], None) for r in db.session.execute(text("SELECT id, email FROM users ORDER BY id")).all()]
        taken = {r[2] for r in rows if r[2]}
        missing = [r for r in rows if not r[2]]
        print(f"accounts: {len(rows)}; without a username: {len(missing)}")
        for user_id, email, _ in missing:
            name = usernames.suggest_from_email(email, lambda c: c in taken)
            taken.add(name)
            print(f"  user {user_id}: {name}")
            if apply:
                db.session.execute(text("UPDATE users SET username = :u WHERE id = :i"), {"u": name, "i": user_id})
        if apply:
            db.session.commit()
            db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
            db.session.commit()
            print("unique index ix_users_username: present")
            db.create_all()
            tables = set(inspect(db.engine).get_table_names())
            print(f"user_profiles table: {'present' if 'user_profiles' in tables else 'MISSING'}; "
                  f"user_avatars table: {'present' if 'user_avatars' in tables else 'MISSING'}")
            left = db.session.execute(text("SELECT COUNT(*) FROM users WHERE username IS NULL")).scalar()
            print(f"accounts still without a username: {left}")
            return 0 if left == 0 else 1
        print("Dry run: nothing was changed. Add --apply to do it.")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

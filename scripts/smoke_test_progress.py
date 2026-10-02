"""
Smoke test for per-step roadmap progress tracking - POST/GET
/roadmap/<id>/progress and its effect on /roadmap/latest and
/dashboard/data - via Flask's test client. No Gemini, no YouTube: the two
test roadmaps are inserted directly into the database (a phased one
copied verbatim from scratch/roadmap_QA_Test_Automation.json, and a flat
one derived from it - step_number/title/description only), not generated
through /roadmap/generate.

Usage:
    PYTHONPATH=. python scripts/smoke_test_progress.py [--keep]

By default, every row this script created (including both test users) is
deleted at the end, pass or fail. --keep instead leaves a demo user and
its QA phased roadmap (with the 3 steps this script ticks still marked
done) in the database, and prints the demo user's email and a password
that satisfies the signup password rules, so you can log in and look at
the roadmap page yourself.

Exits non-zero if any check fails.
"""
import json
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.exc import IntegrityError

from scripts._csrf import enable_csrf_client
from app import create_app, db
from app.models import GeneratedRoadmap, RoadmapProgress, User
from app.routes.roadmap import step_indexes

PASSWORD = "SmokeTest#123"  # 8+ chars, upper, lower, digit, special - see auth.py's is_valid_password

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def flatten_to_old_shape(phased_steps):
    """A plain list of {step_number, title, description} only - nothing
    else - simulating a roadmap saved before phases/subtopics/topic_refs/
    projects/videos/resources existed."""
    flat = []
    for phase in phased_steps["phases"]:
        for step in phase["steps"]:
            flat.append({
                "step_number": step.get("global_step_index", len(flat) + 1),
                "title": step.get("title", ""),
                "description": step.get("description", ""),
            })
    return flat


def main():
    keep = "--keep" in sys.argv
    app = create_app()
    enable_csrf_client(app)

    with app.app_context():
        db.create_all()

        scratch_path = Path("scratch/roadmap_QA_Test_Automation.json")
        data = json.loads(scratch_path.read_text(encoding="utf-8"))
        phased_steps = data["roadmap"]
        flat_steps = flatten_to_old_shape(phased_steps)
        career_path = data["career_path"]

        suffix = random.randint(100000, 999999)
        email = f"progresstest{suffix}@example.com"
        other_email = f"progressother{suffix}@example.com"

        user = User(name="Progress Test", email=email)
        user.set_password(PASSWORD)
        other_user = User(name="Progress Other", email=other_email)
        other_user.set_password(PASSWORD)
        db.session.add_all([user, other_user])
        db.session.commit()

        phased_roadmap = GeneratedRoadmap(user_id=user.id, career_path=career_path, steps=phased_steps)
        flat_roadmap = GeneratedRoadmap(user_id=user.id, career_path=career_path, steps=flat_steps)
        other_roadmap = GeneratedRoadmap(user_id=other_user.id, career_path=career_path, steps=phased_steps)
        db.session.add_all([phased_roadmap, flat_roadmap, other_roadmap])
        db.session.commit()
        phased_id, flat_id, other_id = phased_roadmap.id, flat_roadmap.id, other_roadmap.id

        phased_indexes = step_indexes(phased_steps)
        flat_indexes = step_indexes(flat_steps)
        print(f"Phased roadmap id={phased_id}, {len(phased_indexes)} steps.")
        print(f"Flat roadmap id={flat_id}, {len(flat_indexes)} steps.")
        print(f"Other user's roadmap id={other_id} (user_id={other_user.id}).")
        print()

        fresh_id = None

        with app.test_client() as client:
            # ---- unauthenticated ----
            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": phased_indexes[0], "done": True})
            check("unauthenticated POST gives 401", resp.status_code == 401)

            resp = client.post("/login", json={"email": email, "password": PASSWORD})
            check("login succeeds", resp.status_code == 200)

            idx0 = phased_indexes[0]

            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": idx0, "done": True})
            body = resp.get_json()
            check("tick step: 200", resp.status_code == 200)
            check("tick step: completed_steps contains it", bool(body) and idx0 in body["completed_steps"])
            check("tick step: completed_count == 1", bool(body) and body["completed_count"] == 1)
            check("tick step: total_steps matches", bool(body) and body["total_steps"] == len(phased_indexes))

            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": idx0, "done": True})
            body = resp.get_json()
            check("tick again (idempotent): 200", resp.status_code == 200)
            check("tick again (idempotent): count unchanged", bool(body) and body["completed_count"] == 1)

            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": idx0, "done": False})
            body = resp.get_json()
            check("untick: 200", resp.status_code == 200)
            check("untick: completed_count == 0", bool(body) and body["completed_count"] == 0)
            check("untick: completed_steps empty", bool(body) and body["completed_steps"] == [])

            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": idx0, "done": False})
            body = resp.get_json()
            check("untick again (idempotent): 200", resp.status_code == 200)
            check("untick again (idempotent): count still 0", bool(body) and body["completed_count"] == 0)

            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": 999999, "done": True})
            check("invalid step_index gives 400", resp.status_code == 400)

            resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": idx0, "done": "true"})
            check("done as a string gives 400", resp.status_code == 400)

            resp = client.post(f"/roadmap/{other_id}/progress", json={"step_index": phased_indexes[0], "done": True})
            check("another user's roadmap gives 404", resp.status_code == 404)

            to_tick = phased_indexes[:3]
            body = None
            for i in to_tick:
                resp = client.post(f"/roadmap/{phased_id}/progress", json={"step_index": i, "done": True})
                body = resp.get_json()
            check("phased: 3 ticked -> completed_count == 3", bool(body) and body["completed_count"] == 3)
            check("phased: completed_steps sorted and matches", bool(body) and body["completed_steps"] == sorted(to_tick))

            flat_idx0 = flat_indexes[0]
            resp = client.post(f"/roadmap/{flat_id}/progress", json={"step_index": flat_idx0, "done": True})
            body = resp.get_json()
            check("flat: tick via step_number: 200", resp.status_code == 200)
            check("flat: completed_count == 1", bool(body) and body["completed_count"] == 1)
            check("flat: total_steps == len(flat_steps)", bool(body) and body["total_steps"] == len(flat_steps))

            resp = client.get("/roadmap/latest")
            latest = resp.get_json()
            check("/roadmap/latest: 200", resp.status_code == 200)
            check(
                "/roadmap/latest: has completed_steps/completed_count/total_steps",
                bool(latest) and all(k in latest for k in ("completed_steps", "completed_count", "total_steps")),
            )
            check(
                "/roadmap/latest: reflects the newest roadmap (flat)'s progress",
                bool(latest) and latest["roadmap_id"] == flat_id and latest["completed_count"] == 1,
            )

            resp = client.get("/dashboard/data")
            dash = resp.get_json()
            check("/dashboard/data: 200", resp.status_code == 200)
            dash_roadmap = dash.get("roadmap") if dash else None
            check(
                "/dashboard/data: roadmap has nested progress {completed_count, total_steps}",
                bool(dash_roadmap) and isinstance(dash_roadmap.get("progress"), dict)
                and "completed_count" in dash_roadmap["progress"] and "total_steps" in dash_roadmap["progress"],
            )
            check(
                "/dashboard/data: progress.completed_count matches",
                bool(dash_roadmap) and dash_roadmap["progress"]["completed_count"] == 1,
            )
            check(
                "/dashboard/data: no flat completed_steps/completed_count key leaked onto roadmap",
                bool(dash_roadmap) and "completed_steps" not in dash_roadmap and "completed_count" not in dash_roadmap,
            )

            # ---- indexes that become invalid are ignored in counts ----
            fresh_roadmap = GeneratedRoadmap(user_id=user.id, career_path=career_path, steps=flat_steps[:5])
            db.session.add(fresh_roadmap)
            db.session.commit()
            fresh_id = fresh_roadmap.id

            soon_invalid_idx = flat_steps[4]["step_number"]
            resp = client.post(f"/roadmap/{fresh_id}/progress", json={"step_index": soon_invalid_idx, "done": True})
            body = resp.get_json()
            check(
                "shrink-test: ticking a currently-valid index succeeds",
                resp.status_code == 200 and body["completed_count"] == 1,
            )

            fresh = GeneratedRoadmap.query.filter_by(id=fresh_id).first()
            fresh.steps = flat_steps[:2]   # the ticked index (5th step) no longer exists
            db.session.commit()

            still_valid_idx = flat_steps[0]["step_number"]
            resp = client.post(f"/roadmap/{fresh_id}/progress", json={"step_index": still_valid_idx, "done": True})
            body = resp.get_json()
            check(
                "shrink-test: stale ticked index excluded from the recount",
                resp.status_code == 200
                and body["completed_count"] == 1
                and soon_invalid_idx not in body["completed_steps"]
                and still_valid_idx in body["completed_steps"],
            )

        # ---- unique constraint is real: attempt a duplicate insert directly (bypassing the route entirely) ----
        # Index 5 (not one of to_tick's first 3, which are left ticked for --keep's demo).
        dup_index = phased_indexes[5]
        db.session.add(RoadmapProgress(user_id=user.id, roadmap_id=phased_id, step_index=dup_index))
        db.session.commit()
        rejected = False
        try:
            db.session.add(RoadmapProgress(user_id=user.id, roadmap_id=phased_id, step_index=dup_index))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            rejected = True
        check("unique constraint (user_id, roadmap_id, step_index) rejects a duplicate direct insert", rejected)
        # Remove this probe row so it doesn't skew the --keep demo's displayed progress.
        RoadmapProgress.query.filter_by(user_id=user.id, roadmap_id=phased_id, step_index=dup_index).delete()
        db.session.commit()

        # ---- cleanup ----
        if keep:
            cleanup_roadmap_ids = [flat_id, other_id, fresh_id]
            RoadmapProgress.query.filter(RoadmapProgress.roadmap_id.in_(cleanup_roadmap_ids)).delete(synchronize_session=False)
            GeneratedRoadmap.query.filter(GeneratedRoadmap.id.in_(cleanup_roadmap_ids)).delete(synchronize_session=False)
            User.query.filter_by(id=other_user.id).delete()
            db.session.commit()
            print()
            print("--keep: demo user left in place.")
            print(f"  email:      {email}")
            print(f"  password:   {PASSWORD}")
            print(f"  roadmap_id: {phased_id} (QA & Test Automation, phased, 3 steps left ticked)")
        else:
            all_roadmap_ids = [phased_id, flat_id, other_id, fresh_id]
            RoadmapProgress.query.filter(RoadmapProgress.roadmap_id.in_(all_roadmap_ids)).delete(synchronize_session=False)
            GeneratedRoadmap.query.filter(GeneratedRoadmap.id.in_(all_roadmap_ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_([user.id, other_user.id])).delete(synchronize_session=False)
            db.session.commit()
            print()
            print("Cleaned up all test rows (user, roadmaps, progress).")

    print()
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    print(f"{passed}/{total} checks passed.")
    if passed != total:
        print()
        print("Failures:")
        for desc, ok in checks:
            if not ok:
                print(f"  - {desc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

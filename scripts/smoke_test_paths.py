"""
Smoke test for the shared career-path picker and multi-roadmap support:
app/pipeline/path_matches.py, resolve_target_career_path's allow_override,
GET /career/options, GET /roadmap/list, GET /roadmap/<id>, and the
dashboard's "roadmaps" key. Via Flask's test client - every Gemini call
(roadmap generation, resume feedback) is stubbed with unittest.mock.patch,
so nothing here needs GEMINI_API_KEY or a network call. YouTube is never
invoked by anything this script exercises (resourcing is a separate
endpoint this script doesn't call), so nothing YouTube-related needs
stubbing.

Usage:
    PYTHONPATH=. python scripts/smoke_test_paths.py [--keep]

By default, every row this script creates (three users, their roadmaps,
profiles, progress) is deleted at the end, pass or fail. --keep instead
leaves one demo user with a tied-leader CareerProfile and two roadmaps
(QA & Test Automation, Mobile App Development - inserted directly from
their scratch/ JSON files), and prints the demo user's email and a
password that satisfies the signup password rules.

Exits non-zero if any check fails.
"""
import json
import random
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

import sqlalchemy as sa
from fpdf import FPDF

from scripts._csrf import enable_csrf_client
from app import create_app, db
from app.models import CareerProfile, GeneratedRoadmap, Resume, RoadmapProgress, SkillGap, User
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.path_matches import is_unambiguous, top_matches
from app.routes._util import resolve_target_career_path
from app.routes.roadmap import step_indexes

PASSWORD = "SmokeTest#123"

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def make_ranking(scores_by_path):
    """
    A CareerProfile.career_ranking-shaped list ({"career_path", "score",
    "confidence_pct"}, score-descending) from a partial {path: score} map -
    every other CAREER_PATHS member gets score 0. Matches
    profile_builder.rank_scores's exact output shape (confirmed against
    that module and a real database row).
    """
    scores = {p: scores_by_path.get(p, 0) for p in CAREER_PATHS}
    total = sum(scores.values()) or 1
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [{"career_path": p, "score": s, "confidence_pct": round(s / total * 100, 1)} for p, s in ranked]


def flatten_to_old_shape(phased_steps):
    flat = []
    for phase in phased_steps["phases"]:
        for step in phase["steps"]:
            flat.append({
                "step_number": step.get("global_step_index", len(flat) + 1),
                "title": step.get("title", ""),
                "description": step.get("description", ""),
            })
    return flat


def make_test_pdf(path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in ["Jane Doe", "Software Engineer", "", "SKILLS", "Python, SQL, Docker, AWS, Git"]:
        pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def fake_generate_roadmap(career_path, conversation_signals, index, chunks):
    steps = {"phases": [{"phase_number": 1, "title": "Stub Phase", "steps": [
        {"step_number": i + 1, "global_step_index": i + 1, "title": f"Stub Step {i + 1}",
         "description": "stub", "subtopics": [], "topic_refs": [], "projects": [], "more_topics": []}
        for i in range(3)
    ]}]}
    return steps, {"phases": []}


def main():
    keep = "--keep" in sys.argv
    app = create_app()
    enable_csrf_client(app)

    query_log = []

    def _log_query(conn, cursor, statement, parameters, context, executemany):
        query_log.append(statement)

    with app.app_context():
        db.create_all()
        sa.event.listen(db.engine, "before_cursor_execute", _log_query)

        # ---------------------------------------------------------------
        # top_matches / is_unambiguous: pure unit checks, no Flask at all
        # ---------------------------------------------------------------
        p0, p1, p2, p3, p4 = CAREER_PATHS[0], CAREER_PATHS[1], CAREER_PATHS[2], CAREER_PATHS[3], CAREER_PATHS[4]

        tied_ranking = make_ranking({p0: 10, p1: 10, p2: 5})
        tied_matches = top_matches(tied_ranking)
        check("top_matches: tied leaders both included", {m["career_path"] for m in tied_matches} == {p0, p1})
        check("top_matches: non-match (score 5, margin 1) excluded", p2 not in {m["career_path"] for m in tied_matches})
        check("is_unambiguous: False for 2 matches", is_unambiguous(tied_matches) is False)

        clear_ranking = make_ranking({p0: 10, p1: 3})
        clear_matches = top_matches(clear_ranking)
        check("top_matches: clear leader -> exactly 1 match", len(clear_matches) == 1 and clear_matches[0]["career_path"] == p0)
        check("is_unambiguous: True for 1 match", is_unambiguous(clear_matches) is True)
        check("is_unambiguous: False for 0 matches", is_unambiguous([]) is False)

        margin_ranking = make_ranking({p0: 10, p1: 9})
        check("top_matches: margin=1 includes a 1-point gap", len(top_matches(margin_ranking, margin=1)) == 2)
        check("top_matches: margin=0 excludes a 1-point gap", len(top_matches(margin_ranking, margin=0)) == 1)

        cap_scores = {path: 10 for path in CAREER_PATHS[:6]}
        cap_ranking = make_ranking(cap_scores)
        capped = top_matches(cap_ranking, margin=1, max_matches=4)
        check("top_matches: capped at max_matches=4 even with 6 tied", len(capped) == 4)

        bad_path_ranking = [{"career_path": "Not A Real Path", "score": 99, "confidence_pct": 90.0}] + make_ranking({p0: 10})
        bad_path_matches = top_matches(bad_path_ranking)
        check(
            "top_matches: unknown career_path ignored entirely",
            all(m["career_path"] != "Not A Real Path" for m in bad_path_matches) and bad_path_matches[0]["career_path"] == p0,
        )

        # ---------------------------------------------------------------
        # three users
        # ---------------------------------------------------------------
        suffix = random.randint(100000, 999999)
        tied_email = f"pathstest_tied_{suffix}@example.com"
        clear_email = f"pathstest_clear_{suffix}@example.com"
        none_email = f"pathstest_none_{suffix}@example.com"

        tied_user = User(name="Tied Leader", email=tied_email)
        tied_user.set_password(PASSWORD)
        clear_user = User(name="Clear Leader", email=clear_email)
        clear_user.set_password(PASSWORD)
        none_user = User(name="No Profile", email=none_email)
        none_user.set_password(PASSWORD)
        db.session.add_all([tied_user, clear_user, none_user])
        db.session.commit()

        tied_profile = CareerProfile(user_id=tied_user.id, career_ranking=tied_ranking, conversation_signals={})
        clear_profile = CareerProfile(user_id=clear_user.id, career_ranking=clear_ranking, conversation_signals={})
        db.session.add_all([tied_profile, clear_profile])
        db.session.commit()
        tied_profile_id, clear_profile_id = tied_profile.id, clear_profile.id

        def ranking_unchanged(profile_id, before):
            fresh = CareerProfile.query.filter_by(id=profile_id).first()
            return fresh.career_ranking == before

        with app.test_client() as client:
            # ---- /career/options: 401 when logged out ----
            resp = client.get("/career/options")
            check("/career/options: 401 when logged out", resp.status_code == 401)

            # ---- /career/options for each user ----
            client.post("/login", json={"email": tied_email, "password": PASSWORD})
            resp = client.get("/career/options")
            body = resp.get_json()
            check("/career/options (tied): 200", resp.status_code == 200)
            check("/career/options (tied): has_profile true", body["has_profile"] is True)
            check("/career/options (tied): top_matches has 2 entries", len(body["top_matches"]) == 2)
            check("/career/options (tied): preselect is null (ambiguous)", body["preselect"] is None)
            check("/career/options (tied): all_paths has all 15 in registry order", body["all_paths"] == list(CAREER_PATHS))
            client.post("/logout")

            client.post("/login", json={"email": clear_email, "password": PASSWORD})
            resp = client.get("/career/options")
            body = resp.get_json()
            check("/career/options (clear): top_matches has 1 entry", len(body["top_matches"]) == 1)
            check("/career/options (clear): preselect is that one path", body["preselect"] == p0)
            client.post("/logout")

            client.post("/login", json={"email": none_email, "password": PASSWORD})
            resp = client.get("/career/options")
            body = resp.get_json()
            check("/career/options (no profile): has_profile false", body["has_profile"] is False)
            check("/career/options (no profile): top_matches empty", body["top_matches"] == [])
            check("/career/options (no profile): preselect null", body["preselect"] is None)
            client.post("/logout")

        # ---------------------------------------------------------------
        # resolve_target_career_path: direct calls, via test_request_context
        # (it reads flask.request, so it needs a request context, not a
        # live route) - CareerProfile.career_ranking asserted unchanged
        # after every single case below.
        # ---------------------------------------------------------------
        before_tied = list(tied_profile.career_ranking)

        with app.test_request_context("/x", method="POST", json={"target_career_path": p2}):
            path, error = resolve_target_career_path(tied_profile, allow_override=True)
        check("resolve: explicit valid path wins over profile (allow_override=True)", path == p2 and error is None)
        check("resolve: career_ranking unchanged after explicit-valid case", ranking_unchanged(tied_profile_id, before_tied))

        with app.test_request_context("/x", method="POST", json={"target_career_path": "Not A Real Path"}):
            path, error = resolve_target_career_path(tied_profile, allow_override=True)
        check("resolve: invalid explicit path gives 400 invalid_career_path", path is None and error[1] == 400 and error[0].json["error"] == "invalid_career_path")
        check("resolve: career_ranking unchanged after invalid-explicit case", ranking_unchanged(tied_profile_id, before_tied))

        with app.test_request_context("/x", method="POST", json={}):
            path, error = resolve_target_career_path(tied_profile, allow_override=True)
        check("resolve: absent + profile -> profile's first path", path == tied_profile.career_ranking[0]["career_path"] and error is None)
        check("resolve: career_ranking unchanged after absent+profile case", ranking_unchanged(tied_profile_id, before_tied))

        with app.test_request_context("/x", method="POST", json={}):
            path, error = resolve_target_career_path(None, allow_override=True)
        check("resolve: no profile + absent -> 400 career_path_required with options", path is None and error[1] == 400 and error[0].json["error"] == "career_path_required" and error[0].json["options"] == list(CAREER_PATHS))

        with app.test_request_context(f"/x?target_career_path={p2}", method="GET"):
            path, error = resolve_target_career_path(tied_profile, allow_override=False)
        check("resolve: allow_override=False (DSA behavior) ignores an explicit value", path == tied_profile.career_ranking[0]["career_path"] and error is None)
        check("resolve: career_ranking unchanged after allow_override=False case", ranking_unchanged(tied_profile_id, before_tied))

        # ---------------------------------------------------------------
        # /roadmap/generate with a patched generator and an explicit path
        # ---------------------------------------------------------------
        before_clear = list(clear_profile.career_ranking)
        with patch("app.routes.roadmap.generate_roadmap", side_effect=fake_generate_roadmap):
            with app.test_client() as client:
                client.post("/login", json={"email": clear_email, "password": PASSWORD})
                resp = client.post("/roadmap/generate", json={"target_career_path": p3})
                body = resp.get_json()
                check("generate: 201 with explicit path (profile present)", resp.status_code == 201)
                check("generate: GeneratedRoadmap.career_path == chosen path", body and body["career_path"] == p3)
                new_roadmap_id = body["roadmap_id"]
                db_roadmap = GeneratedRoadmap.query.filter_by(id=new_roadmap_id).first()
                check("generate: career_path persisted == chosen path", db_roadmap.career_path == p3)
                client.post("/logout")
        check("generate: career_ranking unchanged after generate with explicit path", ranking_unchanged(clear_profile.id, before_clear))

        # ---------------------------------------------------------------
        # /resume/upload with a patched feedback function
        # ---------------------------------------------------------------
        pdf_path = Path("scratch/_smoke_test_paths_resume.pdf")
        pdf_path.parent.mkdir(exist_ok=True)
        make_test_pdf(pdf_path)

        with patch("app.routes.resume.generate_resume_feedback", return_value="stub feedback"):
            with app.test_client() as client:
                client.post("/login", json={"email": clear_email, "password": PASSWORD})
                with open(pdf_path, "rb") as f:
                    resp = client.post("/resume/upload", data={
                        "resume": (f, "resume.pdf"), "target_career_path": p3,
                    }, content_type="multipart/form-data")
                body = resp.get_json()
                check("resume upload: explicit path used", resp.status_code == 201 and body["target_career_path"] == p3)
                client.post("/logout")

            with app.test_client() as client:
                client.post("/login", json={"email": tied_email, "password": PASSWORD})
                with open(pdf_path, "rb") as f:
                    resp = client.post("/resume/upload", data={"resume": (f, "resume.pdf")}, content_type="multipart/form-data")
                body = resp.get_json()
                check(
                    "resume upload: absent path uses profile's first",
                    resp.status_code == 201 and body["target_career_path"] == tied_profile.career_ranking[0]["career_path"],
                )
                client.post("/logout")
        pdf_path.unlink(missing_ok=True)

        # ---------------------------------------------------------------
        # /roadmap/list, /roadmap/<id>, /roadmap/latest, dashboard "roadmaps"
        # ---------------------------------------------------------------
        scratch_qa = json.loads(Path("scratch/roadmap_QA_Test_Automation.json").read_text(encoding="utf-8"))
        phased_steps = scratch_qa["roadmap"]
        flat_steps = flatten_to_old_shape(phased_steps)

        phased_roadmap = GeneratedRoadmap(user_id=tied_user.id, career_path="QA & Test Automation", steps=phased_steps)
        db.session.add(phased_roadmap)
        db.session.commit()
        flat_roadmap = GeneratedRoadmap(user_id=tied_user.id, career_path="Data Engineering", steps=flat_steps)
        db.session.add(flat_roadmap)
        db.session.commit()
        other_users_roadmap = GeneratedRoadmap(user_id=clear_user.id, career_path=p3, steps=flat_steps[:2])
        db.session.add(other_users_roadmap)
        db.session.commit()

        # Tick a couple of steps on each of tied_user's roadmaps, so the
        # progress counts in /roadmap/list aren't trivially all-zero.
        phased_idx0 = step_indexes(phased_steps)[0]
        flat_idx0 = step_indexes(flat_steps)[0]
        db.session.add_all([
            RoadmapProgress(user_id=tied_user.id, roadmap_id=phased_roadmap.id, step_index=phased_idx0),
            RoadmapProgress(user_id=tied_user.id, roadmap_id=flat_roadmap.id, step_index=flat_idx0),
        ])
        db.session.commit()

        with app.test_client() as client:
            client.post("/login", json={"email": tied_email, "password": PASSWORD})

            query_log.clear()
            resp = client.get("/roadmap/list")
            progress_queries = [s for s in query_log if "roadmap_progress" in s.lower()]
            body = resp.get_json()
            check("/roadmap/list: 200", resp.status_code == 200)
            check("/roadmap/list: newest first", [r["roadmap_id"] for r in body] == [flat_roadmap.id, phased_roadmap.id])
            check("/roadmap/list: exactly ONE grouped roadmap_progress query", len(progress_queries) == 1)
            by_id = {r["roadmap_id"]: r for r in body}
            check("/roadmap/list: phased progress correct", by_id[phased_roadmap.id]["completed_count"] == 1 and by_id[phased_roadmap.id]["total_steps"] == len(step_indexes(phased_steps)))
            check("/roadmap/list: flat progress correct", by_id[flat_roadmap.id]["completed_count"] == 1 and by_id[flat_roadmap.id]["total_steps"] == len(flat_steps))

            # cap of 20: add 25 cheap roadmaps and confirm the list stays <= 20
            extra_ids = []
            for _ in range(25):
                r = GeneratedRoadmap(user_id=tied_user.id, career_path=p4, steps=[{"step_number": 1, "title": "x", "description": "x"}])
                db.session.add(r)
                db.session.commit()
                extra_ids.append(r.id)
            resp = client.get("/roadmap/list")
            check("/roadmap/list: capped at 20", len(resp.get_json()) == 20)
            GeneratedRoadmap.query.filter(GeneratedRoadmap.id.in_(extra_ids)).delete(synchronize_session=False)
            db.session.commit()

            resp = client.get(f"/roadmap/{phased_roadmap.id}")
            check("/roadmap/<id>: 200 for the owner", resp.status_code == 200 and resp.get_json()["roadmap_id"] == phased_roadmap.id)

            resp = client.get(f"/roadmap/{other_users_roadmap.id}")
            check("/roadmap/<id>: 404 for another user's roadmap", resp.status_code == 404)

            resp = client.get("/roadmap/9999999")
            check("/roadmap/<id>: 404 for a nonexistent id", resp.status_code == 404)

            resp = client.get("/roadmap/latest")
            check("/roadmap/latest: unchanged, still 200 with the newest roadmap", resp.status_code == 200 and resp.get_json()["roadmap_id"] == flat_roadmap.id)

            resp = client.get("/dashboard/data")
            body = resp.get_json()
            check("dashboard: 200", resp.status_code == 200)
            check(
                "dashboard: carries 'roadmaps' plus all old top-level keys",
                resp.status_code == 200
                and "roadmaps" in body
                and all(k in body for k in ("career_profile", "roadmap", "resume", "dsa")),
            )
            check("dashboard: roadmaps list matches /roadmap/list's newest-first order", [r["roadmap_id"] for r in body["roadmaps"][:2]] == [flat_roadmap.id, phased_roadmap.id])

            client.post("/logout")

        # ---------------------------------------------------------------
        # cleanup
        # ---------------------------------------------------------------
        if keep:
            # Remove the clear-leader/no-profile users and their rows;
            # keep the tied-leader demo user with its 2 QA/Mobile roadmaps.
            # tied_user also picked up a Resume/SkillGap row from the resume-
            # upload test above - drop those too, so the --keep user starts
            # clean apart from its two roadmaps.
            extra_user_ids = [clear_user.id, none_user.id]
            extra_roadmap_ids = [r.id for r in GeneratedRoadmap.query.filter(GeneratedRoadmap.user_id.in_(extra_user_ids)).all()]
            extra_roadmap_ids.append(other_users_roadmap.id)
            RoadmapProgress.query.filter(RoadmapProgress.roadmap_id.in_(extra_roadmap_ids)).delete(synchronize_session=False)
            GeneratedRoadmap.query.filter(GeneratedRoadmap.id.in_(extra_roadmap_ids)).delete(synchronize_session=False)
            CareerProfile.query.filter_by(id=clear_profile_id).delete()
            Resume.query.filter(Resume.user_id.in_(extra_user_ids + [tied_user.id])).delete(synchronize_session=False)
            SkillGap.query.filter(SkillGap.user_id.in_(extra_user_ids + [tied_user.id])).delete(synchronize_session=False)
            User.query.filter(User.id.in_(extra_user_ids)).delete(synchronize_session=False)

            # Replace the tied user's "Data Engineering" flat roadmap with
            # the Mobile App Development phased one the task asked for.
            scratch_mobile = json.loads(Path("scratch/roadmap_Mobile_App_Development.json").read_text(encoding="utf-8"))
            RoadmapProgress.query.filter_by(roadmap_id=flat_roadmap.id).delete()
            GeneratedRoadmap.query.filter_by(id=flat_roadmap.id).delete()
            mobile_roadmap = GeneratedRoadmap(user_id=tied_user.id, career_path="Mobile App Development", steps=scratch_mobile["roadmap"])
            db.session.add(mobile_roadmap)
            db.session.commit()

            db.session.commit()
            print()
            print("--keep: demo user left in place.")
            print(f"  email:    {tied_email}")
            print(f"  password: {PASSWORD}")
            print(f"  roadmaps: {phased_roadmap.id} (QA & Test Automation), {mobile_roadmap.id} (Mobile App Development)")
        else:
            all_user_ids = [tied_user.id, clear_user.id, none_user.id]
            all_roadmap_ids = [r.id for r in GeneratedRoadmap.query.filter(GeneratedRoadmap.user_id.in_(all_user_ids)).all()]
            RoadmapProgress.query.filter(RoadmapProgress.roadmap_id.in_(all_roadmap_ids)).delete(synchronize_session=False)
            GeneratedRoadmap.query.filter(GeneratedRoadmap.id.in_(all_roadmap_ids)).delete(synchronize_session=False)
            CareerProfile.query.filter(CareerProfile.user_id.in_(all_user_ids)).delete(synchronize_session=False)
            Resume.query.filter(Resume.user_id.in_(all_user_ids)).delete(synchronize_session=False)
            SkillGap.query.filter(SkillGap.user_id.in_(all_user_ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(all_user_ids)).delete(synchronize_session=False)
            db.session.commit()
            print()
            print("Cleaned up all test rows.")

        sa.event.remove(db.engine, "before_cursor_execute", _log_query)

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

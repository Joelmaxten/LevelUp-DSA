"""
Smoke test for the Placement Readiness Score: the pure scoring rules (app/pipeline/readiness.py) and GET /readiness.
No LLM, YouTube or Adzuna call is made. The route section uses Flask's test client and the development database,
and deletes every row it created.

Usage:
    PYTHONPATH=. python scripts/smoke_test_readiness.py

Exits non-zero if any check fails.
"""
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

from app.pipeline import readiness as r
from app.pipeline import scenario_engine as eng

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def close(a, b, tol=1e-9):
    return a is not None and abs(a - b) <= tol


PILOT = json.loads(Path("data/scenarios/ml-engineering.json").read_text(encoding="utf-8"))
SCENARIOS = PILOT["scenarios"]
TODAY = date(2026, 10, 8)


def progress(*scores):
    """compute_progress for submitted attempts [(scenario_id, score)] out of 40 each."""
    return eng.compute_progress(SCENARIOS, [{"scenario_id": s, "score": sc, "max_score": 40} for s, sc in scores])


# ---------------------------------------------------------------- pure rules
def test_pure():
    # components
    check("roadmap component = completed / total", close(r.roadmap_component(5, 10), 0.5))
    check("roadmap component: no steps -> unavailable", r.roadmap_component(0, 0) is None and r.roadmap_component(None, None) is None)
    check("roadmap component is clamped to 1", r.roadmap_component(12, 10) == 1.0)
    check("skill_gap component = acquired / required", close(r.skill_gap_component(3, 4), 0.75))
    check("skill_gap component: no required skills -> unavailable", r.skill_gap_component(0, 0) is None)

    prog = progress(("mle-1", 40), ("mle-2", 20))
    check("dsa = mean of best/max over ALL scenarios, unattempted count as 0 (1 + .5 + 0 + 0 + 0) / 5",
          close(r.dsa_component(SCENARIOS, prog), 0.3))
    check("dsa: nothing attempted is 0.0, not unavailable", r.dsa_component(SCENARIOS, progress()) == 0.0)
    check("dsa: no scenario file for the path -> unavailable (None), never 0",
          r.dsa_component(None, None) is None and r.dsa_component([], {}) is None)
    best = progress(("mle-1", 10), ("mle-1", 40), ("mle-1", 20))
    check("dsa uses the engine's best-score rule (a worse later attempt does not lower it)",
          close(r.dsa_component(SCENARIOS, best), 1 / 5))
    check("dsa: all five perfect = 1.0", close(r.dsa_component(SCENARIOS, progress(*[(s["id"], 40) for s in SCENARIOS])), 1.0))

    # streak window edges: 30 days ending today, inclusive
    check("streak: today counts", close(r.streak_component([TODAY], TODAY), 1 / 30))
    check("streak: 29 days ago is the first day inside the window", close(r.streak_component([TODAY - timedelta(days=29)], TODAY), 1 / 30))
    check("streak: 30 days ago is outside the window", r.streak_component([TODAY - timedelta(days=30)], TODAY) == 0.0)
    check("streak: a future date is not counted", r.streak_component([TODAY + timedelta(days=1)], TODAY) == 0.0)
    check("streak: several events on one day count once", close(r.streak_component([TODAY] * 5, TODAY), 1 / 30))
    check("streak: every day of the window = 1.0", close(r.streak_component([TODAY - timedelta(days=i) for i in range(30)], TODAY), 1.0))
    check("streak: no activity = 0.0 (a real zero)", r.streak_component([], TODAY) == 0.0)

    # all four present: hand-computed
    out = r.compute_readiness(roadmap=(5, 10), skill_gap=(3, 4), scenarios=SCENARIOS, scenario_progress=prog,
                              activity_dates=[TODAY - timedelta(days=i) for i in range(15)], today=TODAY)
    expected = 100 * (0.25 * 0.5 + 0.35 * 0.75 + 0.30 * 0.3 + 0.10 * 0.5)
    check("all components present: score = weighted sum x 100 (rounded to 1 decimal)",
          out["score"] == round(expected, 1) and out["unavailable"] == [] and out["weights"] == r.BASE_WEIGHTS)
    check("result carries every component value", close(out["components"]["roadmap"], 0.5) and close(out["components"]["skill_gap"], 0.75)
          and close(out["components"]["dsa"], 0.3) and close(out["components"]["streak"], 0.5))

    # each component unavailable in turn
    full = {"roadmap": 0.5, "skill_gap": 0.75, "dsa": 0.3, "streak": 0.5}
    for name in full:
        comps = dict(full, **{name: None})
        res = r.combine(comps)
        rest = {k: v for k, v in full.items() if k != name}
        total_w = sum(r.BASE_WEIGHTS[k] for k in rest)
        want = round(100 * sum(r.BASE_WEIGHTS[k] / total_w * v for k, v in rest.items()), 1)
        check(f"{name} unavailable: dropped, weights re-normalised, score {want}",
              res["unavailable"] == [name] and name not in res["weights"] and close(sum(res["weights"].values()), 1.0)
              and res["score"] == want)
        check(f"{name} unavailable: its weight is shared in proportion (ratios between the others unchanged)",
              all(close(res["weights"][a] / res["weights"][b], r.BASE_WEIGHTS[a] / r.BASE_WEIGHTS[b]) for a in rest for b in rest))

    # all unavailable
    none = r.combine({})
    check("all unavailable: no score, not ready, no weights, four names listed",
          none["score"] is None and none["ready"] is False and none["weights"] == {} and len(none["unavailable"]) == 4)
    check("compute_readiness with no data at all: only the streak (a real 0) exists",
          r.compute_readiness(today=TODAY)["score"] == 0.0 and r.compute_readiness(today=TODAY)["unavailable"] == ["roadmap", "skill_gap", "dsa"])

    # weights always sum to 1: every subset of components
    import itertools
    ok = True
    for n in range(1, 5):
        for subset in itertools.combinations(full, n):
            res = r.combine({k: full[k] for k in subset})
            ok = ok and close(sum(res["weights"].values()), 1.0) and sorted(res["weights"]) == sorted(subset)
    check("weights sum to 1 for all 15 non-empty subsets of available components", ok)

    # rounding and threshold
    check("rounding is half-up to one decimal (12.25 -> 12.3, not banker's 12.2)", r._round_1(12.25) == 12.3)
    check("rounding: 69.95 -> 70.0", r._round_1(69.95) == 70.0)
    check("score has at most one decimal", r.combine({"roadmap": 1 / 3})["score"] == 33.3)
    at = r.combine({"roadmap": 0.7})
    check("threshold: exactly 70.0 is ready", at["score"] == 70.0 and at["ready"] is True and at["threshold"] == 70.0)
    below = r.combine({"roadmap": 0.699})
    check("threshold: 69.9 is not ready", below["score"] == 69.9 and below["ready"] is False)
    check("threshold: a raw 69.96 rounds to 70.0 and is shown and judged ready (display and state agree)",
          r.combine({"roadmap": 0.6996})["score"] == 70.0 and r.combine({"roadmap": 0.6996})["ready"] is True)
    check("score bounds: all zeros -> 0.0, all ones -> 100.0",
          r.combine(dict.fromkeys(full, 0.0))["score"] == 0.0 and r.combine(dict.fromkeys(full, 1.0))["score"] == 100.0)
    check("out-of-range inputs are clamped", r.combine({"roadmap": 5, "dsa": -3})["components"] == {
        "roadmap": 1.0, "skill_gap": None, "dsa": 0.0, "streak": None})


# ---------------------------------------------------------------- route
def test_route():
    from app import create_app, db
    from app.models import (CareerProfile, GeneratedRoadmap, Resume, RoadmapProgress, ScenarioAttempt,
                            SkillGap, User)
    from app.pipeline.resume_analyzer import get_required_skills
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    password = "SmokeTest#123"
    user_ids = []

    def login(tag):
        client = app.test_client()
        email = f"ready{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Ready Test", "email": email, "password": password})
        uid = resp.get_json()["user_id"]
        user_ids.append(uid)
        client.post("/login", json={"email": email, "password": password})
        return client, uid

    def add_roadmap(uid, done, total=4, path="Machine Learning Engineering", days_ago=0):
        steps = {"phases": [{"phase_number": 1, "title": "p", "steps": [{"global_step_index": i + 1} for i in range(total)]}]}
        rm = GeneratedRoadmap(user_id=uid, career_path=path, steps=steps)
        db.session.add(rm)
        db.session.flush()
        for i in range(done):
            db.session.add(RoadmapProgress(user_id=uid, roadmap_id=rm.id, step_index=i + 1,
                                           completed_at=datetime.utcnow() - timedelta(days=days_ago)))
        db.session.commit()
        return rm

    def add_attempt(uid, scenario_id, score, days_ago=0):
        db.session.add(ScenarioAttempt(user_id=uid, path="Machine Learning Engineering", scenario_id=scenario_id, answers={},
                                       score=score, max_score=40, passed=score >= 28, shuffle_seed=1,
                                       started_at=datetime.utcnow(), submitted_at=datetime.utcnow() - timedelta(days=days_ago)))
        db.session.commit()

    try:
        with app.app_context():
            db.create_all()
            required = sorted(get_required_skills("Machine Learning Engineering"))

        anon = app.test_client()
        resp = anon.get("/readiness")
        check("logged out: GET /readiness -> 401", resp.status_code == 401)

        # an empty student: only the streak exists
        empty, empty_id = login("e")
        resp = empty.get("/readiness")
        body = resp.get_json()
        check("no data: 200, score 0.0 from the streak alone, three components unavailable, not ready",
              resp.status_code == 200 and body["score"] == 0.0 and body["unavailable"] == ["roadmap", "skill_gap", "dsa"]
              and body["ready"] is False and body["weights"] == {"streak": 1.0})

        # student A: everything present
        alice, alice_id = login("a")
        with app.app_context():
            add_roadmap(alice_id, done=2)                                    # 2 of 4 steps, today
            add_roadmap(alice_id, done=1, total=4, days_ago=29)              # (older roadmap: not the latest one)
            if required:
                k = max(1, len(required) // 2)
                db.session.add(Resume(user_id=alice_id, file_path="x.pdf", extracted_skills=required[:k], analysis_pending=False))
                db.session.add(SkillGap(user_id=alice_id, missing_skills=required[k:], target_role="Machine Learning Engineering"))
            db.session.add(CareerProfile(user_id=alice_id, career_ranking=[{"career_path": "Machine Learning Engineering", "score": 9}],
                                         conversation_signals={}))
            db.session.commit()
            add_attempt(alice_id, "mle-1", 40)
            add_attempt(alice_id, "mle-2", 20)
            add_attempt(alice_id, "mle-2", 10, days_ago=40)                  # old attempt: outside the streak window, best score still 20
        resp = alice.get("/readiness")
        a = resp.get_json()
        # latest roadmap is the second one (1 of 4); the streak days: today (attempts) and 29 days ago (roadmap tick)
        want = r.compute_readiness(
            roadmap=(1, 4), skill_gap=(max(1, len(required) // 2), len(required)) if required else None,
            scenarios=SCENARIOS, scenario_progress=progress(("mle-1", 40), ("mle-2", 20)),
            activity_dates=[datetime.utcnow().date(), datetime.utcnow().date() - timedelta(days=29)],
            today=datetime.utcnow().date())
        check("route: all four components computed from the student's rows (matches the pure result)",
              resp.status_code == 200 and a["score"] == want["score"] and a["components"] == want["components"]
              and a["weights"] == want["weights"])
        check("route: roadmap 1/4, dsa 0.3, streak 2/30", close(a["components"]["roadmap"], 0.25) and close(a["components"]["dsa"], 0.3)
              and close(a["components"]["streak"], 2 / 30))
        if required:
            check("route: skill_gap = required skills the resume has / required skills", close(a["components"]["skill_gap"], max(1, len(required) // 2) / len(required)))
        check("route: the response has only score data (no question text, no user fields)",
              set(a) == {"score", "ready", "threshold", "components", "weights", "unavailable"})

        # student B with perfect data must not change A's score
        bob, bob_id = login("b")
        with app.app_context():
            add_roadmap(bob_id, done=4)
            for s in SCENARIOS:
                add_attempt(bob_id, s["id"], 40)
            db.session.add(CareerProfile(user_id=bob_id, career_ranking=[{"career_path": "Machine Learning Engineering", "score": 9}],
                                         conversation_signals={}))
            db.session.commit()
        b = bob.get("/readiness").get_json()
        check("another student's perfect data is never counted for student A", alice.get("/readiness").get_json() == a)
        check("student B's own data is counted (dsa 1.0, roadmap 1.0)", close(b["components"]["dsa"], 1.0) and close(b["components"]["roadmap"], 1.0))

        # path with no scenario file -> dsa unavailable; with a file but nothing attempted -> dsa 0.0
        with app.app_context():
            db.session.add(CareerProfile(user_id=empty_id, career_ranking=[{"career_path": "Game Development", "score": 5}], conversation_signals={}))
            db.session.commit()
        check("path without a scenario file: dsa is unavailable, not 0", "dsa" in empty.get("/readiness").get_json()["unavailable"])
        with app.app_context():
            db.session.add(CareerProfile(user_id=empty_id, career_ranking=[{"career_path": "Machine Learning Engineering", "score": 9}], conversation_signals={}))
            db.session.commit()
        c = empty.get("/readiness").get_json()
        check("path with a file but nothing attempted: dsa is 0.0 (available)", c["components"]["dsa"] == 0.0 and "dsa" not in c["unavailable"])

        # dashboard page
        html = alice.get("/dashboard").get_data(as_text=True)
        check("dashboard page loads the readiness card without innerHTML",
              "/readiness" in html and "readinessCard" in html and "innerHTML" not in html)
    finally:
        with app.app_context():
            for uid in user_ids:
                RoadmapProgress.query.filter_by(user_id=uid).delete()
                GeneratedRoadmap.query.filter_by(user_id=uid).delete()
                Resume.query.filter_by(user_id=uid).delete()
                SkillGap.query.filter_by(user_id=uid).delete()
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                CareerProfile.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


def main():
    test_pure()
    test_route()
    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for d in failed:
        print(f"FAILED: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

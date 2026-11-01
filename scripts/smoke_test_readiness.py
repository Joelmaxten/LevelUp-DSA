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
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

from app.pipeline import readiness as r
from app.pipeline import scenario_engine as eng

checks = []


@contextmanager
def scenarios_without(file_name):
    """Point the scenario store at a copy of data/scenarios/ that lacks one file, so that path has no scenarios.
    Every career path has a file now, so the 'no scenario file' behaviour can only be tested this way."""
    from app.pipeline import scenario_store as store
    with tempfile.TemporaryDirectory() as tmp:
        for f in Path("data/scenarios").glob("*.json"):
            if f.name != file_name:
                shutil.copy(f, tmp)
        store.set_directory(tmp)
        try:
            yield
        finally:
            store.set_directory(None)


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
    low = r.combine({"roadmap": 0.6996})
    check("threshold: a raw 69.96 is NOT ready but is shown rounded as 70.0 (decision uses the unrounded score)",
          low["score"] == 70.0 and low["ready"] is False)
    check("threshold: a raw 70.04 is ready and shown as 70.0", r.combine({"roadmap": 0.7004})["score"] == 70.0
          and r.combine({"roadmap": 0.7004})["ready"] is True)
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
    app.config["READINESS_SKILL_MODE"] = "resume"     # this section checks the old rule (the resume alone); the modes have their own section
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
              set(a) == {"score", "ready", "threshold", "components", "weights", "unavailable", "skill_gap_detail"})

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
        with scenarios_without("game-development.json"):   # simulate a path that has no scenario file
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


# ---------------------------------------------------------------- dashboard for three user states
def test_dashboard_states():
    import re

    from app import create_app, db
    from app.models import CareerProfile, User
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    user_ids = []
    unsafe = re.compile(r"\.innerHTML|innerHTML\s*=|outerHTML\s*=|insertAdjacentHTML|document\.write")
    scripts_text = "".join(Path(f"app/static/js/{n}").read_text(encoding="utf-8") for n in ("ui.js", "results.js"))
    check("the scripts the dashboard loads never assign HTML (no .innerHTML / insertAdjacentHTML / document.write)", not unsafe.search(scripts_text))

    def new_user(tag, top_path=None):
        client = app.test_client()
        email = f"dash{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Dash Test", "email": email, "password": "SmokeTest#123"})
        uid = resp.get_json()["user_id"]
        user_ids.append(uid)
        client.post("/login", json={"email": email, "password": "SmokeTest#123"})
        if top_path:
            with app.app_context():
                db.session.add(CareerProfile(user_id=uid, career_ranking=[{"career_path": top_path, "score": 9}], conversation_signals={}))
                db.session.commit()
        return client

    states = [
        ("brand-new account (nothing saved)", new_user("n"), {"dsa_unavailable": True, "dsa": None}),
        ("quiz result only (top path has scenarios)", new_user("q", "Machine Learning Engineering"), {"dsa_unavailable": False, "dsa": 0.0}),
        ("quiz result whose top path has no scenario file", new_user("x", "Game Development"), {"dsa_unavailable": True, "dsa": None}),
    ]
    try:
        for label, client, want in states:
            page = client.get("/dashboard")
            html = page.get_data(as_text=True)
            check(f"{label}: GET /dashboard renders the page (200, no redirect)", page.status_code == 200 and "dashboard-box" in html)
            check(f"{label}: page has the readiness card markup and loads /readiness",
                  "readinessCard" in html and 'getJson("/readiness")' in html and "Placement readiness" in html and "not available yet" in html)
            check(f"{label}: page has no HTML assignment", not unsafe.search(html))
            if "no scenario file" in label:   # every path has a file now, so hide Game Development's for this state
                with scenarios_without("game-development.json"):
                    resp = client.get("/readiness")
            else:
                resp = client.get("/readiness")
            body = resp.get_json()
            check(f"{label}: GET /readiness is valid JSON with the full shape",
                  resp.status_code == 200 and resp.mimetype == "application/json"
                  and set(body) == {"score", "ready", "threshold", "components", "weights", "unavailable", "skill_gap_detail"}
                  and body["skill_gap_detail"] is None)
            check(f"{label}: score 0.0 / 100, not ready, roadmap and skill_gap not available",
                  body["score"] == 0.0 and body["ready"] is False and {"roadmap", "skill_gap"} <= set(body["unavailable"])
                  and body["components"]["streak"] == 0.0)
            check(f"{label}: scenarios component is {'unavailable' if want['dsa_unavailable'] else '0.0 (available)'}",
                  ("dsa" in body["unavailable"]) == want["dsa_unavailable"] and body["components"]["dsa"] == want["dsa"])
        # the home page still offers the first-time flow to a new account
        check("home page for a brand-new account still offers the quiz", b"/quiz" in states[0][1].get("/").data)
    finally:
        with app.app_context():
            for uid in user_ids:
                CareerProfile.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


# ---------------------------------------------------------------- the three skill modes (pure)
def test_skill_modes_pure():
    req = ["Python", "SQL", "Docker", "Rust", "MySQL"]
    on_resume = {"SQL", "Rust", "Python"}
    verified = {"Python"}
    unreachable = {"Rust", "MySQL"}                      # nothing on the platform can verify these

    def run(mode, **kw):
        args = dict(required=req, on_resume=on_resume, verified=verified, unreachable=unreachable)
        args.update(kw)
        return r.skill_gap_breakdown(args["required"], args["on_resume"], args["verified"], args["unreachable"], mode)

    check("constants: resume-only credit 0.5, claim-only credit 1.0, default mode blend, three modes",
          r.RESUME_CLAIM_CREDIT == 0.5 and r.CLAIM_ONLY_CREDIT == 1.0 and r.DEFAULT_SKILL_MODE == "blend"
          and r.SKILL_MODES == ("blend", "verified", "resume"))
    b = run("blend")
    status = {i["skill"]: (i["status"], i["counts_for"]) for i in b["items"]}
    check("blend: verified counts 1, resume-only 0.5, unverifiable-and-claimed 1, unverifiable-not-claimed 0, nothing 0",
          status == {"Python": ("verified", 1), "SQL": ("resume_only", 0.5), "Docker": ("missing", 0),
                     "Rust": ("claim_only", 1.0), "MySQL": ("no_content", 0)} and b["value"] == 2.5 and b["required"] == 5)
    check("blend: the counts shown on the card (on your resume 3 of 5, verified 1 of 5)", b["on_resume"] == 3 and b["verified"] == 1)
    v = run("verified")
    check("verified: only the verified skill counts; an unverifiable skill on the resume counts 0 (strict)",
          v["value"] == 1 and {i["skill"]: i["counts_for"] for i in v["items"]}["Rust"] == 0)
    old = run("resume")
    check("resume: the old calculation, a whole number (resume matches / required), verification ignored",
          old["value"] == 3 and isinstance(old["value"], int) and old["mode"] == "resume")
    check("a skill that is both verified and on the resume counts once (1, not 1.5)",
          run("blend", on_resume={"Python"}, unreachable=set())["value"] == 1)
    check("an unverifiable skill that is not on the resume counts 0 in every mode (MySQL)",
          all({i["skill"]: i["counts_for"] for i in run(m)["items"]}["MySQL"] == 0 for m in ("blend", "verified", "resume")))
    check("a reachable skill that is only on the resume counts 0.5 in blend, 0 in verified, 1 in resume (SQL)",
          [{i["skill"]: i["counts_for"] for i in run(m)["items"]}["SQL"] for m in ("blend", "verified", "resume")] == [0.5, 0, 1])
    check("an unverifiable skill on the resume counts 1 in blend, 0 in verified, 1 in resume (Rust)",
          [{i["skill"]: i["counts_for"] for i in run(m)["items"]}["Rust"] for m in ("blend", "verified", "resume")] == [1.0, 0, 1])
    check("mode names are normalised; anything unknown means blend",
          [r.normalise_skill_mode(x) for x in (" Verified ", "RESUME", "blend", "", None, "nonsense")]
          == ["verified", "resume", "blend", "blend", "blend", "blend"])
    check("the weights, the 70 threshold and the re-normalisation are unchanged by the modes",
          r.BASE_WEIGHTS == {"roadmap": 0.25, "skill_gap": 0.35, "dsa": 0.30, "streak": 0.10} and r.READY_THRESHOLD == 70.0)
    half = r.combine({"roadmap": None, "skill_gap": 0.5, "dsa": None, "streak": 0.0})
    check("a fractional skill-gap value feeds the same score maths (0.5 with the others unavailable)",
          close(r.compute_readiness(skill_gap=(2.5, 5))["components"]["skill_gap"], 0.5) and close(half["weights"]["skill_gap"], 35 / 45))


# ---------------------------------------------------------------- the three skill modes (route, stand-in vocabulary)
def test_skill_modes_route():
    """GET /readiness in each mode. The survey table is not needed: the required list and the vocabulary are stand-ins."""
    from unittest.mock import patch

    from app import create_app, db
    from app.models import (GeneratedRoadmap, Resume, RoadmapProgress, ScenarioAttempt, SkillGap, StepCheckAttempt, User)
    from app.routes import readiness as readiness_route
    from app.routes import skills as skills_route
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    user_ids = []
    import os
    check("the configured default (READINESS_SKILL_MODE unset in the environment) is blend; an unknown value also gives blend",
          r.normalise_skill_mode(os.environ.get("READINESS_SKILL_MODE")) == app.config["READINESS_SKILL_MODE"]
          and (os.environ.get("READINESS_SKILL_MODE") or "blend") != "" and r.normalise_skill_mode("x") == "blend")
    required = {"Python", "SQL", "Docker", "Rust", "MySQL", "Caching"}     # Caching is a CONCEPT: it must never count even if listed
    real_vocab = dict(skills_route._vocab_cache)

    def login(tag):
        client = app.test_client()
        email = f"mode{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Mode Test", "email": email, "password": "SmokeTest#123"})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": "SmokeTest#123"})
        return client, user_ids[-1]

    def get(client, mode):
        app.config["READINESS_SKILL_MODE"] = mode
        return client.get("/readiness").get_json()

    def items(body):
        return {i["skill"]: (i["status"], i["counts_for"]) for i in body["skill_gap_detail"]["items"]}

    def snapshot():
        with app.app_context():
            return {m.__tablename__: (m.query.count(), db.session.query(db.func.max(m.id)).scalar())
                    for m in (User, GeneratedRoadmap, StepCheckAttempt, ScenarioAttempt, Resume, SkillGap, RoadmapProgress)}

    try:
        skills_route._vocab_cache["vocab"] = frozenset({"Python", "SQL", "Docker", "Rust", "MySQL", "PostgreSQL"})   # stand-in vocabulary
        with patch.object(readiness_route, "get_required_skills", lambda path: set(required)):
            alice, aid = login("a")
            bob, bid = login("b")
            backend = json.loads(Path("data/base_roadmaps/backend-engineering.json").read_text(encoding="utf-8"))["roadmap"]
            backend["base"] = {"source": "base_roadmap"}
            caching = next(s["global_step_index"] for ph in backend["phases"] for s in ph["steps"] if s["title"] == "Caching and Search Engines")
            with app.app_context():
                rm = GeneratedRoadmap(user_id=aid, career_path="Backend Engineering", steps=backend)
                db.session.add(rm)
                db.session.flush()
                now = datetime.utcnow()
                db.session.add_all([
                    # resume claims Python, SQL and Rust; Docker and MySQL are not claimed
                    Resume(user_id=aid, file_path="x.pdf", extracted_skills=["Python", "SQL", "Rust"], analysis_pending=False),
                    SkillGap(user_id=aid, missing_skills=[], target_role="Backend Engineering"),
                    # a passed scenario with a solved code problem verifies Python; with the step check it verifies the concept Caching
                    ScenarioAttempt(user_id=aid, path="Backend Engineering", scenario_id="bke-2", answers={"bke-2-c1": {"passed": True}},
                                    score=40, max_score=50, passed=True, shuffle_seed=1, started_at=now, submitted_at=now),
                    StepCheckAttempt(user_id=aid, roadmap_id=rm.id, step_index=caching, mode="check", questions=[], total=4, pass_mark=3,
                                     score=4, passed=True, started_at=now, submitted_at=now),
                    # Bob has a resume claiming everything and nothing verified
                    Resume(user_id=bid, file_path="y.pdf", extracted_skills=sorted(required - {"Caching"}), analysis_pending=False),
                    SkillGap(user_id=bid, missing_skills=[], target_role="Backend Engineering")])
                db.session.commit()

            evidence = alice.get("/skills/evidence").get_json()
            by = {s["skill"]: s for s in evidence["skills"]}
            check("setup: Python is a verified tool, Caching a verified CONCEPT (it is not in the required list)",
                  by["Python"]["status"] == "verified" and by["Python"]["kind"] == "tool"
                  and by["Caching"]["status"] == "verified" and by["Caching"]["kind"] == "concept")

            before = snapshot()
            blend = get(alice, "blend")
            d = blend["skill_gap_detail"]
            check("blend: Python verified (1), SQL resume-only (0.5), Rust claim only (1), Docker, MySQL and the concept Caching 0",
                  items(blend)["Python"] == ("verified", 1) and items(blend)["SQL"] == ("resume_only", 0.5)
                  and items(blend)["Docker"] == ("missing", 0) and items(blend)["Rust"] == ("claim_only", 1.0)
                  and items(blend)["MySQL"] == ("no_content", 0))
            check("blend: value 2.5 of 6 -> skill_gap component 0.4167, the counts for the card are on resume 3, verified 1",
                  d["mode"] == "blend" and d["value"] == 2.5 and d["required"] == 6 and close(blend["components"]["skill_gap"], 2.5 / 6)
                  and d["on_resume"] == 3 and d["verified"] == 1 and d["fallback"] is False)
            check("the unreachable label rule: Rust and MySQL (nothing can verify them) and the concept Caching (only tools count here) are "
                  "'no content'; SQL and Docker (the content can verify them) are not",
                  {i["skill"] for i in d["items"] if i["no_content"]} == {"Rust", "MySQL", "Caching"})
            check("a verified CONCEPT adds nothing: Caching is verified as a skill, but listed as required it still counts 0 "
                  "(its name is never treated as a verified tool)",
                  items(blend)["Caching"] == ("no_content", 0) and d["value"] == 2.5 and d["verified"] == 1)
            verified_mode = get(alice, "verified")
            check("verified: only Python counts (1 of 6); Rust, claimed but unverifiable, counts 0 -> component 1/6",
                  verified_mode["skill_gap_detail"]["value"] == 1 and close(verified_mode["components"]["skill_gap"], 1 / 6)
                  and items(verified_mode)["Rust"] == ("claim_only", 0))
            resume_mode = get(alice, "resume")
            check("resume: the old rule (Python, SQL, Rust are on the resume = 3 of 6 -> 0.5), verified ignored",
                  resume_mode["skill_gap_detail"]["value"] == 3 and close(resume_mode["components"]["skill_gap"], 0.5))
            check("the score differs by mode only through the skill-gap part (verified 1/6 < blend 2.5/6 < resume 3/6)",
                  verified_mode["score"] < blend["score"] < resume_mode["score"] and blend["weights"] == resume_mode["weights"])
            check("verified evidence is shown in every mode (Verified: 1 of 5 in resume mode too)",
                  resume_mode["skill_gap_detail"]["verified"] == 1)
            default_body = alice.get("/readiness").get_json()          # the configured mode is still 'resume' from the last get()
            app.config["READINESS_SKILL_MODE"] = "nonsense"
            check("an unknown configured mode behaves as blend", alice.get("/readiness").get_json()["skill_gap_detail"]["mode"] == "blend")
            check("GET /readiness writes nothing in any mode", snapshot() == before)

            b = get(bob, "blend")
            check("another student's claims and evidence are never mixed in: Bob (resume claims all, nothing verified) gets "
                  "0.5 each for the 3 verifiable skills and 1 for the 2 unverifiable ones = 3.5 of 6 (the concept Caching counts 0)",
                  b["skill_gap_detail"]["value"] == 3.5 and b["skill_gap_detail"]["verified"] == 0)
            check("Alice's numbers did not change after Bob was read", get(alice, "blend")["skill_gap_detail"]["value"] == 2.5)

            # evidence cannot be gathered -> the resume-only rule, said so
            real_evidence = skills_route.evidence_for
            try:
                def boom(_uid):
                    raise RuntimeError("SECRET-detail")
                skills_route.evidence_for = boom
                fb = get(alice, "blend")
                check("if the evidence cannot be gathered: blend falls back to the resume-only rule and says so, without exception text",
                      fb["skill_gap_detail"]["fallback"] is True and fb["skill_gap_detail"]["mode"] == "resume"
                      and fb["skill_gap_detail"]["configured_mode"] == "blend" and fb["skill_gap_detail"]["verified"] is None
                      and fb["skill_gap_detail"]["value"] == 3 and "SECRET" not in json.dumps(fb))
                check("in resume mode a failure to gather the evidence is not a fallback (nothing needed it)",
                      get(alice, "resume")["skill_gap_detail"]["fallback"] is False)
            finally:
                skills_route.evidence_for = real_evidence

        # the dashboard card: the words the owner asked for, built with el()/textContent only
        html = alice.get("/dashboard").get_data(as_text=True)
        check("dashboard card: 'On your resume: X of N', 'Verified: Y of N', what each counts for, the labels, and the help text",
              "On your resume: ${d.on_resume} of ${d.required}" in html and "Verified: ${d.verified} of ${d.required}" in html
              and "How each counts" in html and "Claim only: can't be verified here yet" in html
              and "No LevelUp content for this yet" in html and "Concept skills such as Caching or Databases show on your Skills card" in html
              and "innerHTML" not in html)
    finally:
        skills_route._vocab_cache.clear()
        skills_route._vocab_cache.update(real_vocab)
        with app.app_context():
            for uid in user_ids:
                StepCheckAttempt.query.filter_by(user_id=uid).delete()
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                Resume.query.filter_by(user_id=uid).delete()
                SkillGap.query.filter_by(user_id=uid).delete()
                GeneratedRoadmap.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


def main():
    test_pure()
    test_skill_modes_pure()
    test_route()
    test_skill_modes_route()
    test_dashboard_states()
    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for d in failed:
        print(f"FAILED: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

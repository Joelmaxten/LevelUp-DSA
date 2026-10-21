"""
Smoke test for scenario code pools: the validator rules, materialising a variant, the personalised pick, the
effective scenario an attempt sees, that nothing secret reaches the browser, grading with the real reference
solutions, and the Start / Run / Check / Submit routes end to end.

NO PROVIDER CALLS: code runs with this machine's Python (CODE_RUNNER=local) or the fake runner. The route section
uses Flask's test client and the development database, and deletes every row it created.

Usage:
    PYTHONPATH=. python scripts/smoke_test_code_pools.py

Exits non-zero if any check fails.
"""
import copy
import json
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

SCENARIO_DIR = Path("data/scenarios")
FSD = SCENARIO_DIR / "full-stack-development.json"
POOL_PATHS = sorted(f.stem for f in Path("data/scenarios").glob("*.json"))   # every path has a code pool now
SECRET_FIELDS = ("reference_solution", "explanation", "key_justification", "variants", "skills", "why_others_wrong")
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def load(slug):
    return json.loads((SCENARIO_DIR / f"{slug}.json").read_text(encoding="utf-8"))


def scenario_of(data, sid):
    return next(s for s in data["scenarios"] if s["id"] == sid)


# ---------------------------------------------------------------- part 1: content and validator
def test_content():
    from app.pipeline.scenario_validator import validate_scenario_file

    total = 0
    for slug in POOL_PATHS:
        data = load(slug)
        result = validate_scenario_file(data)
        pools = {s["id"]: s.get("code_pool", []) for s in data["scenarios"]}
        total += sum(len(p) for p in pools.values())
        check(f"{slug}: validates with 0 errors and 0 warnings", not result["errors"] and not result["warnings"])
        check(f"{slug}: scenarios 2-5 each have 2 pool problems, scenario 1 none",
              [len(pools[s["id"]]) for s in sorted(data["scenarios"], key=lambda s: s["order"])] == [0, 2, 2, 2, 2])
        check(f"{slug}: each scenario's two problems differ in difficulty and data structure",
              all(len({p["difficulty"] for p in pool}) == 2 and len({p["ds_topic"] for p in pool}) == 2
                  for pool in pools.values() if pool))
        check(f"{slug}: every problem has 3 data variants with 1 visible and 4 hidden tests",
              all(len(p["variants"]) == 3 and all(sum(not t["hidden"] for t in v["tests"]) == 1
                                                   and sum(t["hidden"] for t in v["tests"]) == 4 for v in p["variants"])
                  for pool in pools.values() for p in pool))
    check("all 15 paths have a code pool: 120 problems", len(POOL_PATHS) == 15 and total == 120)
    tags = {sk for slug in POOL_PATHS for s in load(slug)["scenarios"] for p in s.get("code_pool", []) for sk in p["skills"]}
    check("problems are tagged only with skills they really practise (Python, and SQL where a query is mirrored)",
          tags <= {"Python", "SQL"})

    base = load("full-stack-development")

    def broken(description, mutate, expect):
        data = copy.deepcopy(base)
        mutate(data)
        errs = validate_scenario_file(data)["errors"]
        check(f"validator rejects: {description}", any(expect in e for e in errs))

    pool = lambda d: scenario_of(d, "fsd-2")["code_pool"]
    broken("pool id out of sequence", lambda d: pool(d)[1].update(id="fsd-2-c7"), "pool problem id must be fsd-2-c2")
    broken("variant params not matching the prompt placeholders",
           lambda d: pool(d)[0]["variants"][0].update(params={}), "do not match the prompt placeholders")
    broken("a variant with no hidden test",
           lambda d: pool(d)[0]["variants"][1].update(tests=[t for t in pool(d)[0]["variants"][1]["tests"]
                                                             if not t["hidden"]]),
           "needs at least one hidden test")
    broken("two variants with the same inputs",
           lambda d: pool(d)[0]["variants"].__setitem__(2, copy.deepcopy(pool(d)[0]["variants"][0])),
           "identical test inputs")
    broken("an option field on a pool problem", lambda d: pool(d)[0].update(options=[]), "schema")
    broken("difficulty outside 1-3", lambda d: pool(d)[0].update(difficulty=7), "schema")
    broken("more than 4 problems in a pool",
           lambda d: scenario_of(d, "fsd-2").update(code_pool=pool(d) * 3), "schema")
    broken("a placeholder value with a brace", lambda d: pool(d)[0]["variants"][0]["params"].update(season="{x}"),
           "schema")


# ---------------------------------------------------------------- part 2: engine
def test_engine():
    from app.pipeline import code_runner
    from app.pipeline import scenario_engine as engine
    from app.pipeline.scenario_validator import materialize

    data = load("full-stack-development")
    s2 = scenario_of(data, "fsd-2")
    easy, hard = s2["code_pool"]

    q = materialize(easy, 1)
    check("materialize: the variant's placeholder is filled into the prompt",
          "the summer holidays" in q["prompt"] and "{season}" not in q["prompt"])
    check("materialize: tests come from that variant, and the problem-only fields are dropped",
          q["tests"] == easy["variants"][1]["tests"] and not {"variants", "skills", "difficulty"} & set(q)
          and q["type"] == "code")

    pick = engine.choose_code_pick(s2, 12345)
    check("pick: deterministic for the same seed and inputs", pick == engine.choose_code_pick(s2, 12345))
    check("pick: names a pool problem and a valid variant",
          pick["pool_id"] in ("fsd-2-c1", "fsd-2-c2") and 0 <= pick["variant"] < 3 and pick["reasons"])
    seen = {(p["pool_id"], p["variant"]) for p in (engine.choose_code_pick(s2, seed) for seed in range(60))}
    check("pick: across seeds both problems and several variants appear",
          {a for a, _ in seen} == {"fsd-2-c1", "fsd-2-c2"} and len(seen) >= 5)
    check("pick: a scenario without a pool gets None", engine.choose_code_pick(scenario_of(data, "fsd-1"), 1) is None)

    p = engine.choose_code_pick(s2, 7, previous_picks=["fsd-2-c1"])
    check("pick: a problem not had before wins over a repeat", p["pool_id"] == "fsd-2-c2")
    p = engine.choose_code_pick(s2, 7, previous_picks=["fsd-2-c1", "fsd-2-c2"], missing_skills=["SQL"])
    check("pick: once both were had, the choice is open again (resume skill decides here)", p["pool_id"] == "fsd-2-c2")
    p = engine.choose_code_pick(s2, 7, missing_skills=["sql"])
    check("pick: a missing resume skill the problem practises wins, and the reason says so",
          p["pool_id"] == "fsd-2-c2" and "SQL" in p["reasons"][0] and "resume" in p["reasons"][0])
    check("pick: a specific-role goal gets the harder problem",
          all(engine.choose_code_pick(s2, seed, goal="specific_role")["pool_id"] == hard["id"] for seed in range(20)))
    check("pick: a fundamentals goal gets the gentler problem",
          all(engine.choose_code_pick(s2, seed, goal="build_fundamentals")["pool_id"] == easy["id"]
              for seed in range(20)))
    check("pick: after a failed try the easier problem is preferred",
          all(engine.choose_code_pick(s2, seed, last_try_failed=True)["pool_id"] == easy["id"] for seed in range(20)))
    p = engine.choose_code_pick(s2, 3, goal="specific_role", missing_skills=["Python"])
    check("pick: every reason is a plain sentence", all(r.endswith(".") for r in p["reasons"]))

    plain = engine.effective_scenario(s2, {})
    check("effective: no pick -> the scenario unchanged", plain is s2)
    eff = engine.effective_scenario(s2, {engine.PICK_KEY: {"pool_id": "fsd-2-c2", "variant": 2, "reasons": ["r."]}})
    check("effective: the picked problem is the last question, with the pick reason",
          len(eff["questions"]) == len(s2["questions"]) + 1 and eff["questions"][-1]["id"] == "fsd-2-c2"
          and eff["questions"][-1]["pick_reason"] == "r." and s2["questions"][-1]["id"] != "fsd-2-c2")
    for bad in ({"pool_id": "fsd-2-c9", "variant": 0}, {"pool_id": "fsd-2-c1", "variant": 3},
                {"pool_id": "fsd-2-c1", "variant": True}, "junk", None):
        check(f"effective: a bad pick {bad!r} is ignored", engine.effective_scenario(s2, {engine.PICK_KEY: bad}) is s2)

    leaks = []
    for slug in POOL_PATHS:
        for s in load(slug)["scenarios"]:
            for problem in s.get("code_pool", []):
                for v in range(len(problem["variants"])):
                    e = engine.effective_scenario(s, {engine.PICK_KEY: {"pool_id": problem["id"], "variant": v}})
                    blob = json.dumps(engine.public_view(e, 99))
                    tests = problem["variants"][v]["tests"]
                    visible = [{"stdin": t["stdin"], "expected_stdout": t["expected_stdout"]} for t in tests if not t["hidden"]]
                    shown = engine.public_view(e, 99)["questions"][-1]["tests"]
                    # Long hidden inputs must not appear anywhere; very short ones (like "0\n") occur inside other text
                    # by chance, so for those the exact list of tests sent is the check.
                    hidden = [t["stdin"] for t in tests if t["hidden"] and len(t["stdin"]) >= 8]
                    if (shown != visible or any(f'"{f}"' in blob for f in SECRET_FIELDS)
                            or problem["reference_solution"] in blob or problem["explanation"] in blob
                            or any(json.dumps(h)[1:-1] in blob for h in hidden)):
                        leaks.append(f"{problem['id']}/v{v + 1}")
    check("public view: no solution, hidden test, explanation or pool-only field for any of the 360 variants",
          not leaks)

    code_runner_setting = code_runner._setting
    code_runner._setting = lambda name, default="": "local" if name == "CODE_RUNNER" else code_runner_setting(name,
                                                                                                             default)
    try:
        q = materialize(hard, 0)
        runs = code_runner.run_batch(q["reference_solution"], [t["stdin"] for t in q["tests"]])
        result, record = engine.grade_code_result(q, runs, q["reference_solution"])
        check("grading: the reference solution scores 10 on its own tests", result["correct"] and result["awarded"] == 10)
        runs = code_runner.run_batch(q["starter_code"], [t["stdin"] for t in q["tests"]])
        result, _ = engine.grade_code_result(q, runs, q["starter_code"])
        check("grading: the starter code scores 0", not result["correct"] and result["awarded"] == 0)
        check("grading: the locked result carries the student's own source, for a resumed attempt",
              engine.grade_question(q, record)["source"] == q["reference_solution"])
    finally:
        code_runner._setting = code_runner_setting


# ---------------------------------------------------------------- part 3: routes, end to end
def test_routes():
    from app import create_app, db
    from app.models import CareerProfile, ScenarioAttempt, SkillGap, User
    from app.pipeline import scenario_engine as engine
    from app.pipeline import scenario_store as store
    from app.routes.readiness import gather_inputs
    from app.security import reset_rate_limits
    from scripts._csrf import enable_csrf_client
    from datetime import datetime

    app = create_app()
    enable_csrf_client(app)
    app.config["CODE_RUNNER"] = "local"
    store.set_directory(None)
    suffix = random.randint(100000, 999999)
    password = "SmokeTest#123"
    user_ids = []
    data = load("full-stack-development")
    s2 = scenario_of(data, "fsd-2")

    def login(tag):
        client = app.test_client()
        email = f"pool{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Pool Test", "email": email, "password": password})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": password})
        return client, user_ids[-1]

    def unlock(uid):
        """A submitted attempt on fsd-1 opens fsd-2 (scenario N+1 opens after any submitted attempt on N)."""
        with app.app_context():
            db.session.add(ScenarioAttempt(user_id=uid, path=data["path"], scenario_id="fsd-1", answers={},
                                           score=40, max_score=40, passed=True, shuffle_seed=1,
                                           submitted_at=datetime.utcnow()))
            db.session.commit()

    try:
        with app.app_context():
            db.create_all()
        reset_rate_limits()
        alice, aid = login("a")
        unlock(aid)
        started = alice.post("/scenarios/fsd-2/start", json={})
        body = started.get_json()
        questions = body["scenario"]["questions"]
        code_q = questions[-1]
        check("start: 200, and the attempt gets one extra question, a code problem from the pool",
              started.status_code == 200 and len(questions) == len(s2["questions"]) + 1 and code_q["type"] == "code"
              and code_q["id"] in ("fsd-2-c1", "fsd-2-c2"))
        check("start: the code question shows why it was picked", bool(code_q.get("pick_reason")))
        check("start: the code question carries only public fields (plus the offered languages and their starters)",
              set(code_q) == {"id", "type", "prompt", "language", "starter_code", "tests", "pick_reason", "languages", "starters"}
              and len(code_q["tests"]) == 1)
        with app.app_context():
            attempt = db.session.get(ScenarioAttempt, body["attempt_id"])
            stored_pick = (attempt.answers or {}).get(engine.PICK_KEY)
        check("start: the pick is stored on the attempt, server side",
              isinstance(stored_pick, dict) and stored_pick["pool_id"] == code_q["id"])
        again = alice.post("/scenarios/fsd-2/start", json={}).get_json()
        check("start again: the same unfinished attempt and the same problem",
              again["attempt_id"] == body["attempt_id"] and again["scenario"]["questions"][-1] == code_q)

        problem = next(p for p in s2["code_pool"] if p["id"] == code_q["id"])
        solution = problem["reference_solution"]
        run = alice.post(f"/scenarios/fsd-2/code/run", json={"attempt_id": body["attempt_id"],
                                                            "question_id": code_q["id"], "source": solution})
        check("run: the reference solution passes the visible example (local runner)",
              run.status_code == 200 and all(r["passed"] for r in run.get_json()["results"]))
        bad = alice.post(f"/scenarios/fsd-2/code/run", json={"attempt_id": body["attempt_id"],
                                                            "question_id": "fsd-2-c9", "source": solution})
        check("run: a pool problem that was NOT picked for this attempt is refused", bad.status_code == 400)

        checked = alice.post("/scenarios/fsd-2/answer", json={"attempt_id": body["attempt_id"],
                                                             "question_id": code_q["id"], "answer": solution})
        result = checked.get_json()["result"]
        check("check: the reference solution is correct, with hidden tests reported only as counts",
              checked.status_code == 200 and result["correct"] and result["hidden_passed"] == 4
              and result["hidden_total"] == 4 and solution not in json.dumps({k: v for k, v in result.items()
                                                                              if k != "source"}))
        resumed = alice.post("/scenarios/fsd-2/start", json={}).get_json()
        check("resume: the locked code result returns the student's own source",
              resumed["locked"][code_q["id"]]["source"] == solution)

        forged = {q["id"]: None for q in s2["questions"]}
        forged[engine.PICK_KEY] = {"pool_id": "fsd-2-c9", "variant": 0}
        forged[code_q["id"]] = {"passed": True, "visible": [True], "hidden_passed": 4, "hidden_total": 4}
        submitted = alice.post("/scenarios/fsd-2/submit", json={"attempt_id": body["attempt_id"], "answers": forged})
        sub = submitted.get_json()
        code_result = next(r for r in sub["results"] if r["question_id"] == code_q["id"])
        check("submit: the code question counts towards the score (max includes it)",
              submitted.status_code == 200 and sub["max_score"] == 10 * (len(s2["questions"]) + 1)
              and code_result["correct"] and sub["score"] == 10)
        with app.app_context():
            attempt = db.session.get(ScenarioAttempt, body["attempt_id"])
            kept = attempt.answers
        check("submit: a forged _pick from the browser is ignored and the server's pick is kept",
              kept[engine.PICK_KEY]["pool_id"] == code_q["id"])

        retry = alice.post("/scenarios/fsd-2/start", json={}).get_json()
        other = retry["scenario"]["questions"][-1]
        check("retry: a new attempt gets the OTHER problem (not had before on this scenario)",
              retry["attempt_id"] != body["attempt_id"] and other["id"] != code_q["id"]
              and other["id"] in ("fsd-2-c1", "fsd-2-c2"))

        from app.pipeline import readiness
        with app.app_context():
            db.session.add(CareerProfile(user_id=aid, career_ranking=[{"career_path": data["path"]}],
                                         conversation_signals={}))
            db.session.commit()
            inputs = gather_inputs(aid, datetime.utcnow().date())
        dsa = readiness.dsa_component(inputs["scenarios"], inputs["scenario_progress"])
        check("readiness: the live score counts the fsd-2 attempt out of a max that includes its code question",
              abs(dsa - (1 + 10 / sub["max_score"]) / len(data["scenarios"])) < 1e-9)

        bob, bid = login("b")
        unlock(bid)
        with app.app_context():
            db.session.add(SkillGap(user_id=bid, missing_skills=["SQL", "TypeScript"], target_role=data["path"]))
            db.session.commit()
        picked = bob.post("/scenarios/fsd-2/start", json={}).get_json()["scenario"]["questions"][-1]
        check("personalised: a student whose resume lacks SQL gets the SQL-flavoured problem, and is told why",
              picked["id"] == "fsd-2-c2" and "SQL" in picked["pick_reason"])

        carol, cid = login("c")
        unlock(cid)
        with app.app_context():
            db.session.add(ScenarioAttempt(user_id=cid, path=data["path"], scenario_id="fsd-2", answers={},
                                           shuffle_seed=5))
            db.session.commit()
        legacy = carol.post("/scenarios/fsd-2/start", json={}).get_json()
        check("legacy: an unfinished attempt started before code pools still sees the plain scenario",
              len(legacy["scenario"]["questions"]) == len(s2["questions"]))

        dave, did = login("d")
        first = dave.post("/scenarios/fsd-1/start", json={}).get_json()
        check("scenario 1 has no pool, so its attempt has no code question",
              all(q["type"] != "code" for q in first["scenario"]["questions"]))
        with app.app_context():
            check("the scenario routes created no CareerProfile (only the one this test added for Alice)",
                  CareerProfile.query.filter(CareerProfile.user_id.in_(user_ids)).count() == 1)
    finally:
        with app.app_context():
            for uid in user_ids:
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                SkillGap.query.filter_by(user_id=uid).delete()
                CareerProfile.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


def test_readiness_counts_code():
    """The readiness score's scenario component is best_score / max_score per scenario, so a code question that is
    part of the attempt is part of the score automatically. Checked on the pure function."""
    from app.pipeline import readiness
    from app.pipeline import scenario_engine as engine

    data = load("full-stack-development")
    s2 = scenario_of(data, "fsd-2")
    with_code = 10 * (len(s2["questions"]) + 1)
    progress = engine.compute_progress(data["scenarios"], [
        {"scenario_id": "fsd-1", "score": 40, "max_score": 40},
        {"scenario_id": "fsd-2", "score": with_code, "max_score": with_code}])
    value = readiness.dsa_component(data["scenarios"], progress)
    check("readiness: a perfect fsd-2 attempt that includes its code question counts as 1.0 for that scenario",
          abs(value - 2 / len(data["scenarios"])) < 1e-9)
    progress = engine.compute_progress(data["scenarios"], [
        {"scenario_id": "fsd-2", "score": with_code - 10, "max_score": with_code}])
    value = readiness.dsa_component(data["scenarios"], progress)
    check("readiness: failing only the code question lowers the scenario component",
          abs(value - ((with_code - 10) / with_code) / len(data["scenarios"])) < 1e-9)


def test_dashboard_and_pages():
    """The old skill map is gone; the dashboard summarises scenarios instead and no page links to /dsa."""
    from app import create_app, db
    from app.models import CareerProfile, ScenarioAttempt, User
    from scripts._csrf import enable_csrf_client
    from datetime import datetime

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    user_ids = []

    def login(tag):
        client = app.test_client()
        email = f"dash{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Dash Test", "email": email, "password": "SmokeTest#123"})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": "SmokeTest#123"})
        return client, user_ids[-1]

    try:
        new, _ = login("n")
        body = new.get("/dashboard/data").get_json()
        check("dashboard: a new account has no scenario summary (no path yet) and no 'dsa' key",
              body["scenarios"] is None and "dsa" not in body)
        quizzed, qid = login("q")
        with app.app_context():
            db.session.add(CareerProfile(user_id=qid, career_ranking=[{"career_path": "Full-Stack Development"}],
                                         conversation_signals={}))
            db.session.add(ScenarioAttempt(user_id=qid, path="Full-Stack Development", scenario_id="fsd-1",
                                           answers={}, score=40, max_score=40, passed=True, shuffle_seed=1,
                                           submitted_at=datetime.utcnow()))
            db.session.commit()
        summary = quizzed.get("/dashboard/data").get_json()["scenarios"]
        check("dashboard: the quiz path's scenarios are summarised (1 of 5 passed, next one named)",
              summary["path"] == "Full-Stack Development" and summary["passed"] == 1 and summary["total"] == 5
              and summary["started"] and summary["next_title"])
        pages = {p: quizzed.get(p) for p in ("/", "/dashboard", "/roadmap", "/resume", "/scenarios")}
        check("pages: every main page renders and none links to the removed /dsa page",
              all(r.status_code == 200 and 'href="/dsa"' not in r.get_data(as_text=True) for r in pages.values()))
        check("pages: /dsa and /dsa/map no longer exist",
              quizzed.get("/dsa").status_code == 404 and quizzed.get("/dsa/map").status_code == 404)
        templates = " ".join(Path(f"app/templates/{n}").read_text(encoding="utf-8")
                             for n in ("dashboard.html", "roadmap.html", "resume.html", "index.html", "layout.html"))
        check("templates: no link to /dsa left", '"/dsa"' not in templates and "/dsa\"" not in templates)
    finally:
        with app.app_context():
            for uid in user_ids:
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                CareerProfile.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


SECTIONS = [test_content, test_engine, test_routes, test_readiness_counts_code, test_dashboard_and_pages]


def main():
    for section in SECTIONS:
        section()
    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for d in failed:
        print(f"FAILED: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""
Smoke test for scenario-based gamification: validator, store, engine, progress rules, routes.
Stubs only: no LLM, YouTube or Adzuna call is made. The route section uses Flask's test client and
the development database; it deletes every row it created.

Usage:
    PYTHONPATH=. python scripts/smoke_test_scenarios.py

Exits non-zero if any check fails.
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

PILOT = Path("data/scenarios/ml-engineering.json")
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def load_pilot():
    return json.loads(PILOT.read_text(encoding="utf-8"))


def q_of(data, qid):
    for s in data["scenarios"]:
        for q in s["questions"]:
            if q["id"] == qid:
                return q
    raise KeyError(qid)


# ---------------------------------------------------------------- part 1: validator
def test_validator():
    from app.pipeline.scenario_validator import validate_scenario_file

    base = validate_scenario_file(load_pilot())
    check("validator: pilot file has no errors", base["errors"] == [])

    def broken(description, mutate, expect):
        data = load_pilot()
        mutate(data)
        result = validate_scenario_file(data)
        check(f"validator rejects: {description}", any(expect in e for e in result["errors"]))
        return result

    broken("unknown path", lambda d: d.update(path="Underwater Basket Weaving"), "CAREER_PATHS")
    broken("duplicate scenario id", lambda d: d["scenarios"][1].update(id="mle-1"), "duplicate scenario id")
    broken("bad scenario id pattern", lambda d: d["scenarios"][0].update(id="scenario1"), "must match mle-N")
    broken("non-contiguous order", lambda d: d["scenarios"][4].update(order=7), "contiguous")
    broken("ladder stage out of sequence", lambda d: d["scenarios"][0].update(ladder_stage="end_to_end"), "allowed sequence")
    broken("unknown ladder stage", lambda d: d["scenarios"][0].update(ladder_stage="wizardry"), "schema")
    broken("empty explanation", lambda d: q_of(d, "mle-1-q1").update(explanation="  "), "explanation is empty")
    broken("missing key_justification", lambda d: q_of(d, "mle-1-q1").pop("key_justification"), "key_justification")
    broken("single_choice with two correct", lambda d: q_of(d, "mle-1-q1").update(correct=["a", "b"]), "exactly one")
    broken("single_choice correct id not in options", lambda d: q_of(d, "mle-1-q1").update(correct=["z"]), "not in options")
    broken("multi_select with one correct", lambda d: q_of(d, "mle-1-q3").update(correct=["b"]), "at least 2")
    broken("multi_select count contradicts 'which two'", lambda d: q_of(d, "mle-1-q3").update(correct=["b", "d", "e"]), "prompt says")
    broken("order not a permutation", lambda d: q_of(d, "mle-1-q4").update(correct=["c", "d", "a", "e"]), "permutation")
    broken("match items/targets count differs", lambda d: q_of(d, "mle-3-q4")["targets"].pop(), "same number")
    broken("match not a bijection", lambda d: q_of(d, "mle-3-q4")["correct"].update(i2="t2"), "bijection")

    def dup_text(d):
        opts = q_of(d, "mle-1-q1")["options"]
        opts[1]["text"] = opts[0]["text"]
    broken("duplicate option texts", dup_text, "duplicate option texts")

    def all_above(d):
        q_of(d, "mle-1-q1")["options"][2]["text"] = "All of the above"
    broken("'all of the above' option", all_above, "of the above")

    def both(d):
        q_of(d, "mle-1-q1")["options"][2]["text"] = "Both A and B"
    broken("'both A and B' option", both, "of the above")

    def drop_why(d):
        q_of(d, "mle-1-q1")["why_others_wrong"].pop("a")
    broken("why_others_wrong missing a wrong option", drop_why, "missing wrong option a")

    broken("order without common_mistake", lambda d: q_of(d, "mle-1-q4").update(why_others_wrong={}), "common_mistake")
    broken("match without common_mistake", lambda d: q_of(d, "mle-3-q4").update(why_others_wrong={}), "common_mistake")
    broken("edge to unknown scenario", lambda d: d["map"]["edges"].append(["mle-1", "mle-9"]), "unknown scenario id")
    broken("map_node outside [0,1]", lambda d: d["scenarios"][0]["map_node"].update(x=1.4), "outside [0,1]")
    broken("explanation refers to an option letter",
           lambda d: q_of(d, "mle-1-q1").update(explanation="Option b is right because it is continuous."), "option letter")

    def same_position(d):
        for s in d["scenarios"]:
            for q in s["questions"]:
                if q["type"] == "single_choice":
                    ids = [o["id"] for o in q["options"]]
                    q["correct"] = [ids[0]]
    result = validate_scenario_file((lambda d: (same_position(d), d)[1])(load_pilot()))
    check("validator warns when every correct answer is in one position",
          any("position" in w for w in result["warnings"]))
    check("validator: pilot warns about the longest-option bias (warning, not error)",
          any("longest option" in w for w in base["warnings"]) and not base["errors"])

    # script: temp dir with one good and one broken copy -> non-zero exit; good copy alone -> zero
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.json"
        good.write_text(PILOT.read_text(encoding="utf-8"), encoding="utf-8")
        run = subprocess.run([sys.executable, "scripts/validate_scenarios.py", tmp], capture_output=True, text=True)
        check("validate_scenarios.py exits 0 on a good directory", run.returncode == 0)
        bad = load_pilot()
        q_of(bad, "mle-1-q1")["correct"] = ["z"]
        (Path(tmp) / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        (Path(tmp) / "garbage.json").write_text("{not json", encoding="utf-8")
        run = subprocess.run([sys.executable, "scripts/validate_scenarios.py", tmp], capture_output=True, text=True)
        check("validate_scenarios.py exits non-zero when any file has an error", run.returncode != 0)
        check("validate_scenarios.py prints a result per file",
              all(name in run.stdout for name in ("good.json", "bad.json", "garbage.json")))


# ---------------------------------------------------------------- part 2: blind-solve checker
KEY_FIELDS = ("correct", "explanation", "why_others_wrong", "key_justification")


def test_blind_solve():
    from scripts import blind_solve_scenarios as bs

    data = load_pilot()
    # 1. Real fields: no key field's text may appear in any prompt.
    prompts = [bs.build_prompt(s, seed) for s in data["scenarios"] for seed in (0, 1)]
    leaked = []
    for s in data["scenarios"]:
        for q in s["questions"]:
            texts = [q["explanation"], q["key_justification"]] + list(q["why_others_wrong"].values())
            for t in texts:
                if any(t in p for p in prompts):
                    leaked.append((q["id"], t[:40]))
    check("blind prompts contain no explanation, why_others_wrong or key_justification text", not leaked)

    # 2. Sentinels planted in every key field (and an unknown extra field) must never reach a prompt.
    marked = load_pilot()
    for s in marked["scenarios"]:
        for q in s["questions"]:
            q["explanation"] = "SENTINEL_EXPLANATION"
            q["key_justification"] = "SENTINEL_JUSTIFICATION"
            q["why_others_wrong"] = {"common_mistake": "SENTINEL_WRONG"}
            q["future_answer_field"] = "SENTINEL_FUTURE"
            q["correct"] = "SENTINEL_CORRECT"
    all_prompts = "\n".join(bs.build_prompt(s) for s in marked["scenarios"])
    check("no sentinel key text appears in any prompt", "SENTINEL" not in all_prompts)
    view = json.dumps([bs.build_blind_view(s) for s in marked["scenarios"]])
    check("blind view has no key field names", not any(f'"{f}"' in view for f in KEY_FIELDS + ("points",)))

    # 3. Solving with a stub: a perfect stub agrees on everything; one wrong answer is reported.
    calls = []

    def stub_factory(wrong_for=None, fail_first_for=None):
        def generate(task, prompt, system=None, schema=None, **kw):
            calls.append((task, prompt))
            scen = next(s for s in data["scenarios"] if s["title"] in prompt)
            if fail_first_for == scen["id"] and sum(1 for _, p in calls if scen["title"] in p) == 1:
                raise RuntimeError("stub outage")
            answers = []
            for q in scen["questions"]:
                if q["type"] == "match":
                    mapping = dict(q["correct"])
                    if wrong_for == q["id"]:
                        a, b = list(mapping)[:2]
                        mapping[a], mapping[b] = mapping[b], mapping[a]
                    answers.append({"question_id": q["id"], "mapping": [{"item_id": i, "target_id": t} for i, t in mapping.items()]})
                else:
                    sel = list(q["correct"])
                    if wrong_for == q["id"]:
                        sel = sel[::-1] if q["type"] == "order" else [o["id"] for o in q["options"] if o["id"] not in sel][:len(sel)]
                    answers.append({"question_id": q["id"], "selected": sel})
            return {"parsed": {"answers": answers}}
        return generate

    res = {s["id"]: bs.solve_scenario(s, stub_factory()) for s in data["scenarios"]}
    report = bs.build_report(data["path"], data, res)
    check("perfect stub: 22 questions, 0 disagreements", "| **Total** | **22** | **22** | **0** |" in report and "No disagreements" in report)
    check("every stubbed call used task 'roadmap'", all(t == "roadmap" for t, _ in calls))
    check("no stubbed prompt contained a key text", not any("SENTINEL" in p for _, p in calls))

    for qid in ("mle-1-q1", "mle-1-q4", "mle-3-q4", "mle-1-q3"):
        scen = next(s for s in data["scenarios"] if qid.startswith(s["id"] + "-"))
        r = bs.solve_scenario(scen, stub_factory(wrong_for=qid))
        rep = bs.build_report(data["path"], {"scenarios": [scen]}, {scen["id"]: r})
        q = q_of(data, qid)
        check(f"disagreement on {qid} is listed with question, both answers and key_justification",
              f"### {qid}" in rep and q["prompt"] in rep and "**Key answer:**" in rep and "**Model answer:**" in rep
              and q["key_justification"] in rep)

    calls.clear()
    r = bs.solve_scenario(data["scenarios"][1], stub_factory(fail_first_for="mle-2"))
    check("a failed scenario is retried alone (2 calls for that scenario, none for others)",
          r["error"] is None and r["attempts"] == 2 and len(calls) == 2)
    r = bs.solve_scenario(data["scenarios"][1], lambda **kw: (_ for _ in ()).throw(RuntimeError("down")), retries=1)
    check("a scenario that keeps failing is reported, not raised", r["error"] is not None and r["attempts"] == 2)

    # 4. Dry run by default: no import of llm_client, no call, no file written.
    docs_before = sorted(p.name for p in Path("docs").glob("SCENARIO_REVIEW_*"))
    run = subprocess.run([sys.executable, "scripts/blind_solve_scenarios.py"], capture_output=True, text=True,
                         env={**__import__("os").environ, "PYTHONPATH": "."})
    check("dry run prints the plan and says no call was made", run.returncode == 0 and "DRY RUN" in run.stdout and "mle-5" in run.stdout)
    check("dry run writes no review file", docs_before == sorted(p.name for p in Path("docs").glob("SCENARIO_REVIEW_*")))
    run = subprocess.run([sys.executable, "scripts/blind_solve_scenarios.py", "--run"], capture_output=True, text=True,
                         env={**__import__("os").environ, "PYTHONPATH": "."})
    check("--run without --paths refuses (no call)", run.returncode == 2)


# ---------------------------------------------------------------- part 3: store, engine, progress rules
def test_store_engine():
    from app.pipeline import scenario_store as store
    from app.pipeline import scenario_engine as eng

    # store
    check("store lists the pilot path", store.list_paths() == ["Machine Learning Engineering"])
    check("store: slug lookup works", store.get_by_slug("machine-learning-engineering") is not None
          and store.get_by_slug("nope") is None)
    d, sc = store.find_scenario("mle-3")
    check("store: find_scenario returns path data and scenario", d is not None and sc["id"] == "mle-3")
    check("store: unknown scenario id -> (None, None)", store.find_scenario("zzz") == (None, None))
    with tempfile.TemporaryDirectory() as tmp:
        bad = load_pilot()
        q_of(bad, "mle-1-q1")["correct"] = ["z"]
        (Path(tmp) / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        (Path(tmp) / "junk.json").write_text("{nope", encoding="utf-8")
        store.set_directory(tmp)
        check("store refuses invalid and unreadable files (treated as missing)", store.list_paths() == [])
        (Path(tmp) / "good.json").write_text(PILOT.read_text(encoding="utf-8"), encoding="utf-8")
        store.set_directory(tmp)
        check("store loads a valid file from another directory", store.list_paths() == ["Machine Learning Engineering"])
        first = store.get_path("Machine Learning Engineering")
        check("store caches (same object on repeat call)", store.get_path("Machine Learning Engineering") is first)
        store.set_directory(Path(tmp) / "missing")
        check("store: missing directory -> no paths, no error", store.list_paths() == [])
    store.set_directory(None)

    data = load_pilot()
    scenarios = data["scenarios"]

    # public_view never carries a key field
    key_texts = []
    for s in scenarios:
        for q in s["questions"]:
            key_texts += [q["explanation"], q["key_justification"]] + list(q["why_others_wrong"].values())
    blob = json.dumps([eng.public_view(s, seed) for s in scenarios for seed in (1, 2, 3)])
    check("public_view JSON has no key field names",
          not any(f'"{f}"' in blob for f in ("correct", "explanation", "why_others_wrong", "key_justification", "common_mistake")))
    check("public_view JSON has no explanation / justification text", not any(t in blob for t in key_texts))

    # shuffle: deterministic per seed, different across seeds, ids kept
    a, b, c = eng.public_view(scenarios[0], 7), eng.public_view(scenarios[0], 7), eng.public_view(scenarios[0], 8)
    check("shuffle is deterministic for one seed", a == b)
    check("shuffle differs across seeds", a != c and any(
        [o["id"] for o in qa["options"]] != [o["id"] for o in qc["options"]]
        for qa, qc in zip(a["questions"], c["questions"]) if "options" in qa))
    ok_ids = all(sorted(o["id"] for o in qv.get("options", qv.get("items", []))) ==
                 sorted(o["id"] for o in (q.get("options") or q["items"]))
                 for qv, q in zip(a["questions"], scenarios[0]["questions"]))
    check("shuffle keeps the original ids and options", ok_ids)
    mt = eng.public_view(scenarios[2], 5)["questions"][3]
    check("match items and targets are both present", len(mt["items"]) == len(mt["targets"]) == 4)

    # perfect score from the key itself
    perfect = {q["id"]: q["correct"] for s in scenarios for q in s["questions"]}
    for s in scenarios:
        g = eng.grade(s, perfect)
        check(f"perfect answers from the key give 100% on {s['id']}",
              g["percent"] == 100 and g["passed"] and g["score"] == 10 * len(s["questions"]))

    def one(qtype):
        for s in scenarios:
            for q in s["questions"]:
                if q["type"] == qtype:
                    return s, q

    # grading per type
    for qtype in ("single_choice", "multi_select", "order", "match"):
        s, q = one(qtype)
        right = eng.grade_question(q, q["correct"])
        check(f"{qtype}: correct answer awarded 10", right["correct"] and right["awarded"] == 10)
        check(f"{qtype}: result carries explanation, why_others_wrong, correct_answer",
              right["explanation"] and right["why_others_wrong"] and right["correct_answer"] == q["correct"])
        for label, junk in (("missing answer", None), ("empty list", []), ("empty dict", {}), ("number", 7),
                            ("unknown ids", ["zz"] if qtype != "match" else {"zz": "yy"}),
                            ("nested garbage", [["a"], {"b": 1}]), ("string", "a,b")):
            r = eng.grade_question(q, junk)
            check(f"{qtype}: {label} is wrong and does not raise", not r["correct"] and r["awarded"] == 0)

    s, q = one("single_choice")
    wrong_id = next(o["id"] for o in q["options"] if o["id"] not in q["correct"])
    check("single_choice: a wrong id is wrong", not eng.grade_question(q, [wrong_id])["correct"])
    check("single_choice: two ids is wrong", not eng.grade_question(q, [q["correct"][0], wrong_id])["correct"])
    check("single_choice: bare string id accepted", eng.grade_question(q, q["correct"][0])["correct"])
    s, q = one("multi_select")
    check("multi_select: any order of the exact set is right", eng.grade_question(q, list(reversed(q["correct"])))["correct"])
    check("multi_select: partial set is wrong", not eng.grade_question(q, q["correct"][:1])["correct"])
    extra = next(o["id"] for o in q["options"] if o["id"] not in q["correct"])
    check("multi_select: correct set plus an extra is wrong", not eng.grade_question(q, q["correct"] + [extra])["correct"])
    check("multi_select: duplicated ids are wrong", not eng.grade_question(q, q["correct"] + q["correct"][:1])["correct"])
    s, q = one("order")
    check("order: wrong sequence is wrong", not eng.grade_question(q, list(reversed(q["correct"])))["correct"])
    check("order: a missing step is wrong", not eng.grade_question(q, q["correct"][:-1])["correct"])
    s, q = one("match")
    swapped = dict(q["correct"])
    k1, k2 = list(swapped)[:2]
    swapped[k1], swapped[k2] = swapped[k2], swapped[k1]
    check("match: swapped pair is wrong", not eng.grade_question(q, swapped)["correct"])
    check("match: partial mapping is wrong", not eng.grade_question(q, {k1: q["correct"][k1]})["correct"])
    check("match: a list instead of a mapping is wrong", not eng.grade_question(q, list(q["correct"].values()))["correct"])

    sc0 = scenarios[0]
    check("grade: non-dict answers -> all wrong, no raise", eng.grade(sc0, "x")["score"] == 0 and eng.grade(sc0, None)["score"] == 0)
    all_wrong = eng.grade(sc0, {"mle-1-q1": ["a"], "bogus-id": ["b"]})
    check("grade: unknown question ids ignored, missing answers wrong", all_wrong["score"] == 0 and len(all_wrong["results"]) == 4)
    partial = {q["id"]: q["correct"] for q in sc0["questions"]}
    partial["mle-1-q1"] = ["a"]
    gp = eng.grade(sc0, partial)
    check("grade: 3 of 4 correct = 30/40 = 75% passes (>= 70%)", gp["score"] == 30 and gp["max_score"] == 40 and gp["passed"])
    partial["mle-1-q2"] = ["a"]
    gp = eng.grade(sc0, partial)
    check("grade: 2 of 4 = 50% does not pass", gp["percent"] == 50 and not gp["passed"])
    s5 = scenarios[4]
    p5 = {q["id"]: q["correct"] for q in s5["questions"]}
    p5["mle-5-q1"] = list(reversed(p5["mle-5-q1"]))
    p5["mle-5-q2"] = ["zz"]
    check("grade: 3 of 5 = 60% does not pass; the 70% boundary is inclusive",
          not eng.grade(s5, p5)["passed"] and eng.is_passing(7, 10) and not eng.is_passing(6, 10))

    # progress rules
    def att(sid, score, mx=40):
        return {"scenario_id": sid, "score": score, "max_score": mx}

    p = eng.compute_progress(scenarios, [])
    check("progress: scenario 1 open, the rest locked at the start",
          p["mle-1"]["state"] == "open" and all(p[f"mle-{n}"]["state"] == "locked" for n in range(2, 6)))
    p = eng.compute_progress(scenarios, [att("mle-1", 10)])
    check("progress: a failed attempt on N still opens N+1 and marks N attempted",
          p["mle-1"]["state"] == "attempted" and p["mle-2"]["state"] == "open" and p["mle-3"]["state"] == "locked")
    p = eng.compute_progress(scenarios, [att("mle-1", 10), att("mle-1", 40), att("mle-1", 20)])
    check("progress: best score is kept and passed once any attempt passes",
          p["mle-1"]["best_score"] == 40 and p["mle-1"]["state"] == "passed")
    p = eng.compute_progress(scenarios, [att("mle-3", 40)])
    check("progress: a submission on a later scenario does not unlock the ones before it",
          p["mle-2"]["state"] == "locked" and p["mle-3"]["state"] == "passed")
    check("progress: unfinished attempts (no score) are ignored",
          eng.compute_progress(scenarios, [{"scenario_id": "mle-1", "score": None, "max_score": None}])["mle-2"]["state"] == "locked")

    # weak topics and recommendation
    p = eng.compute_progress(scenarios, [att("mle-1", 40), att("mle-2", 10, 40)])
    weak = eng.weak_topics(scenarios, p)
    check("weak topics = tests_topics of scenarios below 70%", weak == scenarios[1]["tests_topics"])
    check("recommended_next without weak topics = first open not passed", eng.recommended_next(scenarios, p, []) == "mle-2")
    check("recommended_next with nothing started = scenario 1",
          eng.recommended_next(scenarios, eng.compute_progress(scenarios, []), []) == "mle-1")
    p = eng.compute_progress(scenarios, [att("mle-1", 10, 40), att("mle-2", 40)])
    check("recommended_next returns the failed earlier scenario over a later open one",
          eng.recommended_next(scenarios, p, eng.weak_topics(scenarios, p)) == "mle-1")
    fab = [dict(scenarios[0], tests_topics=["A"]), dict(scenarios[1], tests_topics=["B"]), dict(scenarios[2], tests_topics=["C"])]
    fprog = {"mle-1": {"state": "passed", "best_score": 40, "max_score": 40},
             "mle-2": {"state": "open", "best_score": None, "max_score": None},
             "mle-3": {"state": "open", "best_score": None, "max_score": None}}
    check("recommended_next prefers an open scenario overlapping weak topics", eng.recommended_next(fab, fprog, ["c"]) == "mle-3")
    check("recommended_next falls back to the first open one when nothing overlaps", eng.recommended_next(fab, fprog, ["zzz"]) == "mle-2")
    done = eng.compute_progress(scenarios, [att(s["id"], 40) for s in scenarios])
    check("recommended_next is None when everything is passed", eng.recommended_next(scenarios, done, []) is None)


# ---------------------------------------------------------------- part 4: routes
def test_routes():
    import random
    import re

    from app import create_app, db
    from app.models import CareerProfile, ScenarioAttempt, User
    from app.pipeline import scenario_engine as eng
    from app.routes import scenarios as routes
    from app.security import reset_rate_limits
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    password = "SmokeTest#123"
    data = load_pilot()
    scenarios = data["scenarios"]
    perfect = {q["id"]: q["correct"] for s in scenarios for q in s["questions"]}
    user_ids = []

    def login(tag):
        client = app.test_client()
        email = f"scen{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Scen Test", "email": email, "password": password})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": password})
        return client, resp.get_json()["user_id"]

    def profile_snapshot(uid):
        with app.app_context():
            return [(p.id, json.dumps(p.career_ranking, sort_keys=True), json.dumps(p.conversation_signals, sort_keys=True),
                     str(p.created_at)) for p in CareerProfile.query.filter_by(user_id=uid).all()]

    def only_code(resp):
        body = resp.get_json()
        return isinstance(body, dict) and set(body) == {"error"}

    try:
        with app.app_context():
            db.create_all()
        reset_rate_limits()

        anon = app.test_client()
        for method, url in (("get", "/scenarios/paths"), ("get", "/scenarios/machine-learning-engineering"),
                            ("post", "/scenarios/mle-1/start"), ("post", "/scenarios/mle-1/answer"),
                            ("post", "/scenarios/mle-1/submit")):
            resp = getattr(anon, method)(url, **({"json": {}} if method == "post" else {}))
            check(f"logged out: {method.upper()} {url} -> 401", resp.status_code in (401, 400) and (
                resp.status_code == 401 or resp.get_json() == {"error": "csrf"}))
        from flask.testing import FlaskClient
        raw = FlaskClient(app, app.response_class, use_cookies=True)   # plain client: adds no CSRF header
        raw.get("/")
        resp = raw.post("/scenarios/mle-1/start", json={})
        check("CSRF is enforced on start (no token -> 400 csrf)", resp.status_code == 400 and resp.get_json() == {"error": "csrf"})
        # logged out with a valid token must be 401 (login check), via the CSRF-aware client
        resp = app.test_client().post("/scenarios/mle-1/start", json={})
        check("logged out with a valid token: start -> 401", resp.status_code == 401)
        check("logged out: GET /scenarios page redirects to login", anon.get("/scenarios").status_code == 302)

        alice, alice_id = login("a")
        bob, bob_id = login("b")

        # a quiz result for alice (read only for the scenario routes)
        with app.app_context():
            db.session.add(CareerProfile(
                user_id=alice_id, career_ranking=[{"career_path": "Machine Learning Engineering", "score": 9}],
                conversation_signals={"goal": "build_fundamentals", "it_track": "open"}))
            db.session.commit()
        before = profile_snapshot(alice_id)

        # paths + map
        resp = alice.get("/scenarios/paths")
        body = resp.get_json()
        check("GET /scenarios/paths lists the pilot and the quiz-ranked path",
              resp.status_code == 200 and body["paths"][0]["slug"] == "machine-learning-engineering"
              and body["quiz_path"] == "Machine Learning Engineering")
        check("paths: a user with no quiz result gets quiz_path null", bob.get("/scenarios/paths").get_json()["quiz_path"] is None)
        resp = alice.get("/scenarios/machine-learning-engineering")
        m = resp.get_json()
        by_id = {s["id"]: s for s in m["scenarios"]}
        check("map: scene, theme, edges and 5 scenarios", resp.status_code == 200 and m["scene_id"] == "ml-engineering"
              and len(m["edges"]) == 4 and len(m["scenarios"]) == 5 and m["theme"])
        check("map: scenario 1 open and recommended, others locked",
              by_id["mle-1"]["state"] == "open" and by_id["mle-1"]["recommended"]
              and all(by_id[f"mle-{n}"]["state"] == "locked" for n in range(2, 6)))
        check("map: matches_goal follows the stored goal (build_fundamentals -> foundations)",
              by_id["mle-1"]["matches_goal"] and not by_id["mle-5"]["matches_goal"])
        bob_map = {s["id"]: s for s in bob.get("/scenarios/machine-learning-engineering").get_json()["scenarios"]}
        check("map: no profile -> matches_goal false everywhere", not any(s["matches_goal"] for s in bob_map.values()))
        serialized = json.dumps(m)
        texts = [q["prompt"] for s in scenarios for q in s["questions"]] + [s["background"] for s in scenarios]
        check("map payload contains no question or background text", not any(t in serialized for t in texts)
              and '"questions"' not in serialized and '"correct"' not in serialized)
        resp = alice.get("/scenarios/no-such-path")
        check("unknown path slug -> 404 fixed code", resp.status_code == 404 and only_code(resp))

        # start
        resp = alice.post("/scenarios/mle-2/start", json={})
        check("start on a locked scenario -> 403", resp.status_code == 403 and resp.get_json() == {"error": "scenario_locked"})
        resp = alice.post("/scenarios/nope/start", json={})
        check("start on an unknown scenario -> 404", resp.status_code == 404 and only_code(resp))
        resp = alice.post("/scenarios/mle-1/start", json={})
        started = resp.get_json()
        attempt_id = started["attempt_id"]
        blob = json.dumps(started)
        key_texts = [q["explanation"] for s in scenarios for q in s["questions"]]
        check("start returns the public view with no key field",
              resp.status_code == 200 and len(started["scenario"]["questions"]) == 4 and started["locked"] == {}
              and not any(f'"{f}"' in blob for f in ("correct", "explanation", "why_others_wrong", "key_justification"))
              and not any(t in blob for t in key_texts))
        again = alice.post("/scenarios/mle-1/start", json={}).get_json()
        check("start reuses the unfinished attempt (same id, same shuffle)",
              again["attempt_id"] == attempt_id and again["scenario"] == started["scenario"])
        with app.app_context():
            check("only one attempt row exists after two starts",
                  ScenarioAttempt.query.filter_by(user_id=alice_id, scenario_id="mle-1").count() == 1)

        # answer (lock a question)
        q1 = scenarios[0]["questions"][0]
        resp = alice.post("/scenarios/mle-1/answer", json={"attempt_id": attempt_id, "question_id": "mle-1-q1", "answer": q1["correct"]})
        res = resp.get_json()["result"]
        check("answer: locking a correct answer returns the result with the explanation",
              resp.status_code == 200 and res["correct"] and res["explanation"] == q1["explanation"])
        resp = alice.post("/scenarios/mle-1/answer", json={"attempt_id": attempt_id, "question_id": "mle-1-q1", "answer": ["a"]})
        check("answer: a locked answer cannot be changed (same stored result)", resp.get_json()["result"]["correct"] is True)
        check("answer: unknown question -> 400", alice.post("/scenarios/mle-1/answer", json={
            "attempt_id": attempt_id, "question_id": "zzz", "answer": []}).status_code == 400)
        check("answer: bad answer type -> 400", alice.post("/scenarios/mle-1/answer", json={
            "attempt_id": attempt_id, "question_id": "mle-1-q2", "answer": 5}).status_code == 400)
        check("answer: other user's attempt -> 404", bob.post("/scenarios/mle-1/answer", json={
            "attempt_id": attempt_id, "question_id": "mle-1-q2", "answer": ["a"]}).status_code == 404)
        resumed = alice.post("/scenarios/mle-1/start", json={}).get_json()
        check("start on resume returns the locked results", list(resumed["locked"]) == ["mle-1-q1"])

        # submit: malformed and ownership
        def submit(client, body, scenario="mle-1"):
            return client.post(f"/scenarios/{scenario}/submit", json=body)

        check("submit: other user's attempt -> 404", submit(bob, {"attempt_id": attempt_id, "answers": {}}).status_code == 404)
        resp = submit(alice, {"attempt_id": attempt_id, "answers": []})
        check("submit: answers not an object -> 400 invalid_answers", resp.status_code == 400 and resp.get_json() == {"error": "invalid_answers"})
        resp = submit(alice, {"attempt_id": "1", "answers": {}})
        check("submit: attempt_id not an integer -> 400", resp.status_code == 400 and only_code(resp))
        resp = submit(alice, {"answers": {}})
        check("submit: missing attempt_id -> 400", resp.status_code == 400)
        resp = alice.post("/scenarios/mle-1/submit", data="not json", content_type="application/json")
        check("submit: non-JSON body -> 400 invalid_body", resp.status_code == 400 and resp.get_json() == {"error": "invalid_body"})
        resp = alice.post("/scenarios/mle-1/submit", json=[1, 2])
        check("submit: JSON list body -> 400", resp.status_code == 400)
        resp = submit(alice, {"attempt_id": attempt_id, "answers": {"x": "y" * 40000}})
        check("submit: oversized body -> 400 body_too_large", resp.status_code == 400 and resp.get_json() == {"error": "body_too_large"})
        resp = alice.post("/scenarios/mle-1/submit", data="{" + "a" * 100, content_type="application/json")
        check("malformed responses never contain exception text", only_code(resp))
        check("submit: another scenario's id with this attempt -> 404",
              submit(alice, {"attempt_id": attempt_id, "answers": {}}, scenario="mle-3").status_code == 404)

        # submit for real: q1 was locked correct; try to "change" it at submit, rest wrong
        wrong = {q["id"]: ["a"] for q in scenarios[0]["questions"]}
        resp = submit(alice, {"attempt_id": attempt_id, "answers": wrong})
        out = resp.get_json()
        check("submit: graded by the server; the locked answer wins over the submitted one",
              resp.status_code == 200 and out["score"] == 10 and out["max_score"] == 40 and not out["passed"]
              and out["results"][0]["correct"] is True)
        check("submit returns explanations and the new map state",
              all(r["explanation"] for r in out["results"]) and {s["id"]: s for s in out["scenarios"]}["mle-2"]["state"] == "open")
        resp = submit(alice, {"attempt_id": attempt_id, "answers": perfect})
        check("submit twice -> 409 already_submitted", resp.status_code == 409 and resp.get_json() == {"error": "already_submitted"})
        check("answer after submit -> 409", alice.post("/scenarios/mle-1/answer", json={
            "attempt_id": attempt_id, "question_id": "mle-1-q2", "answer": ["a"]}).status_code == 409)
        check("a failed attempt still unlocks the next scenario (start mle-2 ok)",
              alice.post("/scenarios/mle-2/start", json={}).status_code == 200)

        # second attempt on mle-1 passes; best score kept; state passed
        new = alice.post("/scenarios/mle-1/start", json={}).get_json()
        check("start after submit creates a fresh attempt", new["attempt_id"] != attempt_id and new["locked"] == {})
        good = {q["id"]: q["correct"] for q in scenarios[0]["questions"]}
        out = submit(alice, {"attempt_id": new["attempt_id"], "answers": good}).get_json()
        check("submit: perfect answers -> 40/40 passed", out["score"] == 40 and out["passed"])
        m = {s["id"]: s for s in alice.get("/scenarios/machine-learning-engineering").get_json()["scenarios"]}
        check("map after: mle-1 passed with best 40/40, mle-2 recommended",
              m["mle-1"]["state"] == "passed" and m["mle-1"]["best_score"] == 40 and m["mle-2"]["recommended"])
        wrong_again = alice.post("/scenarios/mle-1/start", json={}).get_json()
        submit(alice, {"attempt_id": wrong_again["attempt_id"], "answers": {}})
        m = {s["id"]: s for s in alice.get("/scenarios/machine-learning-engineering").get_json()["scenarios"]}
        check("a later worse attempt does not lower the best score", m["mle-1"]["best_score"] == 40 and m["mle-1"]["state"] == "passed")
        check("bob's map is unaffected by alice's attempts",
              {s["id"]: s for s in bob.get("/scenarios/machine-learning-engineering").get_json()["scenarios"]}["mle-2"]["state"] == "locked")

        # every error body is a fixed code only
        errors = [alice.post("/scenarios/mle-3/start", json={}), alice.post("/scenarios/zzz/submit", json={}),
                  alice.get("/scenarios/zzz"), submit(alice, {"attempt_id": 999999999, "answers": {}})]
        check("error responses carry only a fixed error code", all(only_code(r) for r in errors))

        # rate limit
        reset_rate_limits()
        saved = routes.START_LIMIT_PER_HOUR
        routes.START_LIMIT_PER_HOUR = 3
        codes = [bob.post("/scenarios/mle-1/start", json={}).status_code for _ in range(5)]
        routes.START_LIMIT_PER_HOUR = saved
        check("rate limit on start: 4th call -> 429", codes[:3] == [200, 200, 200] and codes[3] == 429 and codes[4] == 429)
        resp = bob.post("/scenarios/mle-1/start", json={})
        check("rate limit is per user (alice unaffected while bob is limited)",
              alice.post("/scenarios/mle-1/start", json={}).status_code == 200)
        reset_rate_limits()
        saved = routes.SUBMIT_LIMIT_PER_HOUR
        routes.SUBMIT_LIMIT_PER_HOUR = 1
        submit(bob, {"attempt_id": 1, "answers": {}})
        resp = submit(bob, {"attempt_id": 1, "answers": {}})
        routes.SUBMIT_LIMIT_PER_HOUR = saved
        check("rate limit on submit: 2nd call -> 429 with Retry-After", resp.status_code == 429 and resp.headers.get("Retry-After"))
        reset_rate_limits()

        check("CareerProfile is unchanged after every scenario call", profile_snapshot(alice_id) == before)
        check("no CareerProfile was created for a user who had none", profile_snapshot(bob_id) == [])
    finally:
        with app.app_context():
            for uid in user_ids:
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                CareerProfile.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


SECTIONS = [test_validator, test_blind_solve, test_store_engine, test_routes]


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

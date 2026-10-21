"""
Smoke test for graded code questions: the code runner adapter, validator, public view, grading and the Run / Check routes.
NO REAL CALLS: the provider is the fake runner, or requests.post replaced by a stub. The route section uses Flask's
test client and the development database; it deletes every row it created and writes only to a temp directory.

Usage:
    PYTHONPATH=. python scripts/smoke_test_code_questions.py

Exits non-zero if any check fails.
"""
import copy
import json
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

PILOT = Path("data/scenarios/ml-engineering.json")
SCENARIO_DIR = Path("data/scenarios")
FAKE_KEY = "sk-fake-test-key-0000"
CLOUDFLARE_HTML = "<html><head><title>Attention Required! | Cloudflare</title></head><body>Sorry, you have been blocked</body></html>"
PROVIDER_TEXT = ["Cloudflare", "Attention Required", "Sorry, you have been blocked"]
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


REFERENCE = "a, b = map(int, input().split())\nprint(a + b)\n"
SECRET_REFERENCE = "SECRET_REFERENCE_MARKER = 1\n" + REFERENCE
TESTS = [
    {"stdin": "1 2\n", "expected_stdout": "3", "hidden": False},
    {"stdin": "5 7\n", "expected_stdout": "12", "hidden": False},
    {"stdin": "10 20\n", "expected_stdout": "30", "hidden": True},
    {"stdin": "-1 1\n", "expected_stdout": "0", "hidden": True},
]


def code_question(qid="mle-1-q5"):
    return {
        "id": qid, "type": "code", "prompt": "Read two integers from one line and print their sum.",
        "language": "python", "starter_code": "# read two integers, print the sum\n", "tests": copy.deepcopy(TESTS),
        "reference_solution": SECRET_REFERENCE, "ds_topic": "array", "points": 10,
        "explanation": "Split the line, convert both parts to int and print their sum.",
        "key_justification": "Basic input parsing and arithmetic.",
    }


def pilot_with_code():
    data = json.loads(PILOT.read_text(encoding="utf-8"))
    data["scenarios"][0]["questions"].append(code_question())
    return data


def result(stdout="", stderr="", exception=None):
    return {"stdout": stdout, "stderr": stderr, "exception": exception}


def scripted(question):
    """A fake runner that decides from a marker comment in the source; it executes nothing."""
    answers = {t["stdin"]: t["expected_stdout"] for t in question["tests"]}

    def fake(source, stdins):
        from app.pipeline.code_runner import CodeRunnerError
        if "# MODE:down" in source:
            raise CodeRunnerError("runner_unavailable")
        if "# MODE:slow" in source:
            raise CodeRunnerError("timeout")
        out = []
        for i, stdin in enumerate(stdins):
            right = answers.get(stdin, "")
            if "# MODE:wrong" in source:
                out.append(result("999"))
            elif "# MODE:err" in source:
                out.append(result("", "Traceback (most recent call last):\n  NameError: nope"))
            elif "# MODE:timeout" in source:
                out.append(result("", "", "Time limit exceeded"))
            elif "# MODE:mixed" in source:     # visible tests right, hidden tests wrong
                out.append(result(right if i < 2 else "999"))
            elif "# MODE:big" in source:
                out.append(result("x" * 5000, "e" * 5000))
            else:
                out.append(result(right + "\n"))
        return out
    return fake


# ---------------------------------------------------------------- part 1: adapter
class FakeResponse:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_adapter():
    import requests
    from app.pipeline import code_runner as cr

    saved_env = {k: os.environ.get(k) for k in ("CODE_RUNNER", "ONECOMPILER_API_KEY")}
    os.environ["CODE_RUNNER"], os.environ["ONECOMPILER_API_KEY"] = "onecompiler", FAKE_KEY
    real_post, calls = requests.post, []

    def install(behaviour):
        calls.clear()

        def post(url, **kw):
            calls.append((url, kw))
            return behaviour(len(calls))
        cr.requests.post = post

    def expect(description, behaviour, code, source="print(1)", stdins=("",)):
        install(behaviour)
        try:
            cr.run_batch(source, list(stdins))
            check(f"adapter: {description}", False)
        except cr.CodeRunnerError as e:
            leaked = any(w in repr(e) + str(e) for w in PROVIDER_TEXT + [FAKE_KEY])
            check(f"adapter: {description} -> {code}", e.code == code and not leaked and str(e) == code)

    def raiser(exc):
        def behaviour(n):
            raise exc
        return behaviour

    try:
        good = [{"status": "success", "exception": None, "stdout": "3\n", "stderr": None, "executionTime": 40,
                 "memoryUsed": 1, "creditsRemaining": 99}] * 2
        install(lambda n: FakeResponse(200, good))
        out = cr.run_batch("print(3)", ["1 2", "3 4"])
        url, kw = calls[0]
        check("adapter: success returns one {stdout, stderr, exception} per stdin",
              out == [result("3\n"), result("3\n")] and all(set(r) == {"stdout", "stderr", "exception"} for r in out))
        check("adapter: posts to the OneCompiler run endpoint with a 15 s timeout",
              url == "https://api.onecompiler.com/v1/run" and kw["timeout"] == 15)
        h = kw["headers"]
        check("adapter: sends X-API-Key, Accept and a browser-style User-Agent (not python-requests)",
              h["X-API-Key"] == FAKE_KEY and h["Accept"] == "application/json" and h["User-Agent"].startswith("Mozilla/5.0")
              and "python-requests" not in h["User-Agent"])
        check("adapter: body is language python, stdin list, one main.py file",
              kw["json"] == {"language": "python", "stdin": ["1 2", "3 4"], "files": [{"name": "main.py", "content": "print(3)"}]})
        check("adapter: the whole batch is one HTTP call", len(calls) == 1)

        install(lambda n: FakeResponse(200, [{"status": "success", "exception": "Time limit exceeded", "stdout": None, "stderr": None}]))
        r = cr.run_batch("while True: pass", [""])[0]
        check("adapter: provider exception text becomes a fixed token, null streams become empty strings",
              r == result("", "", "time_limit"))
        install(lambda n: FakeResponse(200, [{"status": "success", "exception": "Weird provider words", "stdout": "", "stderr": "Traceback..."}]))
        r = cr.run_batch("x", [""])[0]
        check("adapter: an unknown exception becomes 'error'; student stderr is kept", r["exception"] == "error" and r["stderr"] == "Traceback...")
        install(lambda n: FakeResponse(200, {"status": "success", "exception": None, "stdout": "ok", "stderr": ""}))
        check("adapter: a single result object is accepted when one input was sent", cr.run_batch("x", [""]) == [result("ok")])

        expect("a Cloudflare HTML 403 page", lambda n: FakeResponse(403, None, CLOUDFLARE_HTML), "runner_unavailable")
        expect("a 200 with a non-JSON (HTML) body", lambda n: FakeResponse(200, None, CLOUDFLARE_HTML), "runner_unavailable")
        expect("a non-200 JSON error", lambda n: FakeResponse(500, {"message": "boom Cloudflare"}), "runner_unavailable")
        expect("a 429 from the provider", lambda n: FakeResponse(429, {"x": 1}), "runner_unavailable")
        expect("a dict where a list of several results was expected", lambda n: FakeResponse(200, {"stdout": "1"}), "runner_unavailable",
               stdins=("a", "b"))
        expect("a result list of the wrong length", lambda n: FakeResponse(200, [good[0]]), "runner_unavailable", stdins=("a", "b"))
        expect("a list entry that is not an object", lambda n: FakeResponse(200, ["oops"]), "runtime_error")
        expect("a JSON string body", lambda n: FakeResponse(200, "text"), "runner_unavailable")
        expect("a request timeout", raiser(requests.Timeout("secret provider text Cloudflare")), "timeout")
        check("adapter: a timeout is not retried", len(calls) == 1)
        expect("a connect timeout", raiser(requests.ConnectTimeout("x")), "timeout")
        expect("a connection error (after one retry)", raiser(requests.ConnectionError("Cloudflare down")), "runner_unavailable")
        check("adapter: a connection error is retried exactly once (2 calls)", len(calls) == 2)
        expect("another request exception", raiser(requests.RequestException("x")), "runner_unavailable")
        check("adapter: other request errors are not retried", len(calls) == 1)
        install(lambda n: (_ for _ in ()).throw(requests.ConnectionError("x")) if n == 1 else FakeResponse(200, good[:1]))
        check("adapter: a retry that succeeds returns the results", cr.run_batch("x", [""]) == [result("3\n")])

        # caps, checked before any call
        install(lambda n: FakeResponse(200, good))
        for desc, source, stdins in (("source over 8 KB", "x" * (8 * 1024 + 1), ["a"]),
                                     ("more than 10 stdins", "x", ["a"] * 11),
                                     ("one stdin over 2 KB", "x", ["a" * (2 * 1024 + 1)])):
            try:
                cr.run_batch(source, stdins)
                check(f"adapter: {desc} is refused", False)
            except cr.CodeRunnerError as e:
                check(f"adapter: {desc} -> code_too_large without a provider call", e.code == "code_too_large" and not calls)
        install(lambda n: FakeResponse(200, good * 5))
        cr.run_batch("x" * (8 * 1024), ["a" * 2048] * 10)
        check("adapter: exactly at the caps (8 KB, 10 stdins, 2 KB each) is allowed", len(calls) == 1)
        try:
            cr.run_batch("é" * 5000, ["a"])    # 10,000 bytes
            check("adapter: caps count bytes, not characters", False)
        except cr.CodeRunnerError as e:
            check("adapter: caps count bytes, not characters", e.code == "code_too_large")
        check("adapter: an empty stdin list makes no call", cr.run_batch("x", []) == [] and len(calls) == 1)

        os.environ["ONECOMPILER_API_KEY"] = ""
        expect("a missing API key (no call is made)", lambda n: FakeResponse(200, good), "runner_unavailable")
        check("adapter: a missing key sends nothing", calls == [])
        os.environ["ONECOMPILER_API_KEY"] = FAKE_KEY

        # fake runner
        calls_before_fake = len(calls)
        os.environ["CODE_RUNNER"] = "fake"
        cr.set_fake_runner(None)
        check("fake runner: default executes nothing and returns empty results", cr.run_batch("x", ["a", "b"]) == [result(), result()])
        cr.set_fake_runner([result("a", "", None)])
        check("fake runner: a scripted list is returned", cr.run_batch("x", ["q"]) == [result("a")])
        cr.set_fake_runner(lambda s, i: [result("1"), result("2")])
        try:
            cr.run_batch("x", ["only one"])
            check("fake runner: a wrong-length script is an error", False)
        except cr.CodeRunnerError as e:
            check("fake runner: a wrong-length script is an error", e.code == "runner_unavailable")
        check("fake runner makes no HTTP call", len(calls) == calls_before_fake)   # still only the one call from the batch above
        os.environ["CODE_RUNNER"] = "nonsense"
        check("an unknown CODE_RUNNER value means onecompiler", cr.runner_name() == "onecompiler")
        check("the key variable NAME is reported, never a value", cr.api_key_variable() == "ONECOMPILER_API_KEY")
        src = Path("app/pipeline/code_runner.py").read_text(encoding="utf-8")
        check("adapter source never logs or prints", "logging" not in src and "print(" not in src and "logger" not in src)
    finally:
        cr.requests.post = real_post
        cr.set_fake_runner(None)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------- part 2: validator
def test_validator():
    from app.pipeline.scenario_validator import validate_scenario_file

    ok = validate_scenario_file(pilot_with_code())
    check("validator: a file with a valid code question has no errors", ok["errors"] == [])
    base = validate_scenario_file(json.loads(PILOT.read_text(encoding="utf-8")))
    check("validator: the existing pilot file is still valid and unchanged", base["errors"] == [])

    def broken(description, mutate, expect):
        data = pilot_with_code()
        mutate(data["scenarios"][0]["questions"][4])
        res = validate_scenario_file(data)
        check(f"validator rejects code question: {description}", any(expect in e for e in res["errors"]))

    broken("language not python", lambda q: q.update(language="javascript"), "language")
    broken("missing starter_code", lambda q: q.pop("starter_code"), "starter_code")
    broken("missing reference_solution", lambda q: q.pop("reference_solution"), "reference_solution")
    broken("empty reference_solution", lambda q: q.update(reference_solution="   "), "reference_solution")
    broken("unknown ds_topic", lambda q: q.update(ds_topic="trie"), "ds_topic")
    broken("missing ds_topic", lambda q: q.pop("ds_topic"), "ds_topic")
    broken("no tests", lambda q: q.update(tests=[]), "tests")
    broken("more than 10 tests", lambda q: q.update(tests=[{"stdin": str(i), "expected_stdout": "1", "hidden": i % 2 == 0} for i in range(11)]), "tests")
    broken("no hidden test", lambda q: q.update(tests=[dict(t, hidden=False) for t in q["tests"]]), "hidden test")
    broken("no visible test", lambda q: q.update(tests=[dict(t, hidden=True) for t in q["tests"]]), "visible test")
    broken("a test with an extra field", lambda q: q["tests"][0].update(note="x"), "tests")
    broken("a test missing hidden", lambda q: q["tests"][0].pop("hidden"), "hidden")
    broken("hidden not a boolean", lambda q: q["tests"][0].update(hidden="yes"), "hidden")
    broken("empty expected_stdout", lambda q: q["tests"][0].update(expected_stdout="  "), "empty expected_stdout")
    broken("stdin over 2 KB", lambda q: q["tests"][0].update(stdin="a" * 2049), "stdin")
    broken("duplicate tests", lambda q: q["tests"].append(dict(q["tests"][0])), "duplicate tests")
    broken("starter_code over 8 KB", lambda q: q.update(starter_code="x" * 8193), "starter_code")
    broken("code question with options", lambda q: q.update(options=[{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]), "must not have 'options'")
    broken("code question with correct", lambda q: q.update(correct=["a"]), "must not have 'correct'")
    broken("code question with why_others_wrong", lambda q: q.update(why_others_wrong={"a": "x"}), "must not have 'why_others_wrong'")
    broken("empty explanation", lambda q: q.update(explanation=" "), "explanation is empty")
    broken("missing key_justification", lambda q: q.pop("key_justification"), "key_justification")
    broken("wrong question id for its position", lambda q: q.update(id="mle-1-q9"), "must be mle-1-q5")
    broken("points not a positive integer", lambda q: q.update(points=0), "points")
    for topic in ("array", "hash_map", "stack", "queue", "linked_list", "tree", "graph", "heap", "sorting", "string"):
        data = pilot_with_code()
        data["scenarios"][0]["questions"][4]["ds_topic"] = topic
        check(f"validator accepts ds_topic {topic}", validate_scenario_file(data)["errors"] == [])

    # other types are not weakened: they still need correct and why_others_wrong
    for field in ("correct", "why_others_wrong"):
        data = pilot_with_code()
        data["scenarios"][0]["questions"][0].pop(field)
        res = validate_scenario_file(data)
        check(f"validator: a single_choice question without {field} is still rejected", any(field in e for e in res["errors"]))
    data = pilot_with_code()
    data["scenarios"][0]["questions"][0]["type"] = "freeform"
    check("validator: an unknown question type is still rejected", validate_scenario_file(data)["errors"] != [])


# ---------------------------------------------------------------- part 3: public view and grading
def test_engine():
    from app.pipeline import scenario_engine as eng

    data = pilot_with_code()
    scenario = data["scenarios"][0]
    q = scenario["questions"][4]
    view = eng.public_view(scenario, 123)
    code_view = view["questions"][4]
    blob = json.dumps(view)
    check("public view: a code question has exactly id, type, prompt, language, starter_code and tests",
          set(code_view) == {"id", "type", "prompt", "language", "starter_code", "tests"})
    check("public view: only the visible tests, with stdin and expected_stdout only",
          code_view["tests"] == [{"stdin": t["stdin"], "expected_stdout": t["expected_stdout"]} for t in TESTS if not t["hidden"]])
    check("public view (serialized JSON): no reference solution, no hidden test, no explanation or key",
          "SECRET_REFERENCE_MARKER" not in blob and "10 20" not in blob and '"-1 1' not in blob
          and q["explanation"] not in blob and q["key_justification"] not in blob and "reference_solution" not in blob
          and '"hidden"' not in blob and '"correct"' not in blob and "ds_topic" not in blob)

    def graded(runs):
        res, rec = eng.grade_code_result(q, runs, "src")
        return res, rec

    right = [result(t["expected_stdout"] + "\n") for t in TESTS]
    res, rec = graded(right)
    check("grading: all tests pass -> correct, 10 points", res["correct"] and res["awarded"] == 10 and rec["passed"])
    check("grading: the result has the usual shape", {"question_id", "correct", "awarded", "correct_answer", "explanation",
                                                       "why_others_wrong"} <= set(res) and res["question_id"] == q["id"])
    check("grading: correct_answer is the visible example only, never the solution or a hidden test",
          "SECRET_REFERENCE_MARKER" not in json.dumps(res) and "10 20" not in json.dumps(res) and "'1 2'" in res["correct_answer"])
    check("grading: counts for hidden tests only", res["hidden_total"] == 2 and res["hidden_passed"] == 2 and res["visible_passed"] == [True, True])
    wrong = [result("999") for _ in TESTS]
    res, rec = graded(wrong)
    check("grading: wrong output -> 0 points", not res["correct"] and res["awarded"] == 0 and res["hidden_passed"] == 0)
    res, _ = graded([result("", "Traceback...\nNameError")] * 4)
    check("grading: a runtime error (stderr) -> 0 points", not res["correct"] and res["awarded"] == 0)
    res, _ = graded([result("", "", "time_limit")] * 4)
    check("grading: a timeout -> 0 points", not res["correct"] and res["awarded"] == 0)
    res, _ = graded([result("3"), result("12"), result("999"), result("0")])
    check("grading: mixed -> all-or-nothing 0 points, hidden counted 1 of 2",
          not res["correct"] and res["awarded"] == 0 and res["visible_passed"] == [True, True] and res["hidden_passed"] == 1)
    res, _ = graded([result("3", "warning: x"), result("12"), result("30"), result("0")])
    check("grading: any stderr output fails that test even with the right stdout", not res["correct"] and res["visible_passed"] == [False, True])
    res, _ = graded([result("3\n\n"), result("  12  "), result("30\r\n"), result("0")])
    check("grading: surrounding whitespace and CRLF are ignored", res["correct"])
    res, _ = graded([result("3 ")] + [result("")] * 3)
    check("grading: empty output does not pass", res["hidden_passed"] == 0 and not res["correct"])
    res, _ = graded(right[:2])
    check("grading: missing results count as failed tests", not res["correct"] and res["hidden_passed"] == 0)
    res, _ = graded("not a list")
    check("grading: a malformed result list never raises and scores 0", not res["correct"])
    res, _ = graded([None, 5, "x", []])
    check("grading: malformed entries score 0", not res["correct"])
    res, rec = eng.grade_code_result(q, right, "my source")
    check("grading: the stored record has the source and the pass/fail data", rec["source"] == "my source" and rec["passed"] is True)
    again = eng.grade_question(q, rec)
    check("grade_question re-derives the same result from a stored record", again["correct"] and again["awarded"] == 10)
    for forged in (True, "yes", {"passed": True}, {"passed": True, "visible": [False], "hidden_passed": 0, "hidden_total": 2},
                   {"passed": "true", "visible": [], "hidden_passed": 0, "hidden_total": 0}, None, [], 5):
        r = eng.grade_question(q, forged)
        check(f"grade_question: a forged or malformed answer {str(forged)[:40]!r} is not correct", not r["correct"] and r["awarded"] == 0)
    g = eng.grade(scenario, {q["id"]: rec})
    check("grade(): a stored passing record is worth 10 of the scenario's points",
          [r for r in g["results"] if r["question_id"] == q["id"]][0]["awarded"] == 10)
    g = eng.grade(scenario, {q["id"]: "just a source string"})
    check("grade(): a bare string for a code question scores 0", [r for r in g["results"] if r["question_id"] == q["id"]][0]["awarded"] == 0)


# ---------------------------------------------------------------- part 4: routes
def test_routes():
    from app import create_app, db
    from app.models import CareerProfile, ScenarioAttempt, User
    from app.pipeline import code_runner as cr
    from app.pipeline import scenario_store as store
    from app.routes import scenarios as routes
    from app.security import reset_rate_limits
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    password = "SmokeTest#123"
    user_ids = []
    data = pilot_with_code()
    q = data["scenarios"][0]["questions"][4]
    qid = q["id"]
    tmp = tempfile.mkdtemp()
    for f in SCENARIO_DIR.glob("*.json"):
        if f.name != PILOT.name:
            shutil.copy(f, tmp)
    Path(tmp, PILOT.name).write_text(json.dumps(data), encoding="utf-8")
    store.set_directory(tmp)
    app.config["CODE_RUNNER"] = "fake"
    cr.set_fake_runner(scripted(q))

    def login(tag):
        client = app.test_client()
        email = f"code{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Code Test", "email": email, "password": password})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": password})
        return client

    def only_code(resp):
        body = resp.get_json()
        return isinstance(body, dict) and set(body) == {"error"}

    def run_url(sid="mle-1"):
        return f"/scenarios/{sid}/code/run"

    try:
        with app.app_context():
            db.create_all()
        reset_rate_limits()
        anon = app.test_client()
        resp = anon.post(run_url(), json={})
        check("run: logged out -> 401", resp.status_code == 401)
        from flask.testing import FlaskClient
        raw = FlaskClient(app, app.response_class, use_cookies=True)
        raw.get("/")
        resp = raw.post(run_url(), json={})
        check("run: no CSRF token -> 400 csrf", resp.status_code == 400 and resp.get_json() == {"error": "csrf"})

        alice, bob = login("a"), login("b")
        started = alice.post("/scenarios/mle-1/start", json={}).get_json()
        attempt_id = started["attempt_id"]
        blob = json.dumps(started)
        cq = [x for x in started["scenario"]["questions"] if x["id"] == qid][0]
        check("start: the code question reaches the browser as the public view only",
              set(cq) == {"id", "type", "prompt", "language", "starter_code", "tests", "languages", "starters"} and len(cq["tests"]) == 2
              and "SECRET_REFERENCE_MARKER" not in blob and "10 20" not in blob and q["explanation"] not in blob)

        def body(source="# MODE:pass\nprint(1)", **extra):
            return dict({"attempt_id": attempt_id, "question_id": qid, "source": source}, **extra)

        # ---- Run
        resp = alice.post(run_url(), json=body())
        out = resp.get_json()
        check("run: passes both visible examples", resp.status_code == 200 and [r["passed"] for r in out["results"]] == [True, True])
        check("run: only the visible tests are run (2 results, never the hidden ones)", len(out["results"]) == 2)
        check("run: the response has no reference solution, hidden test or explanation",
              "SECRET_REFERENCE_MARKER" not in json.dumps(out) and "10 20" not in json.dumps(out) and q["explanation"] not in json.dumps(out))
        out = alice.post(run_url(), json=body("# MODE:wrong")).get_json()
        check("run: wrong output -> per-test not passed", [r["passed"] for r in out["results"]] == [False, False])
        out = alice.post(run_url(), json=body("# MODE:err")).get_json()
        check("run: stderr is returned for the student", all(r["passed"] is False and "NameError" in r["stderr"] for r in out["results"]))
        out = alice.post(run_url(), json=body("# MODE:timeout")).get_json()
        check("run: a program timeout is reported per test", all(r["exception"] == "time_limit" and not r["passed"] for r in out["results"]))
        out = alice.post(run_url(), json=body("# MODE:big")).get_json()
        check("run: stdout and stderr are truncated to 2 KB",
              all(len(r["stdout"]) <= 2048 + 20 and len(r["stderr"]) <= 2048 + 20 for r in out["results"]) and out["results"][0]["stdout"].startswith("xxx"))
        with app.app_context():
            row = db.session.get(ScenarioAttempt, attempt_id)
            check("run: nothing is stored or locked", not (row.answers or {}))
        resp = alice.post(run_url(), json=body("# MODE:down"))
        check("run: runner failure -> 503 runner_unavailable, fixed body", resp.status_code == 503 and resp.get_json() == {"error": "runner_unavailable"})
        resp = alice.post(run_url(), json=body("# MODE:slow"))
        check("run: provider timeout -> 504 timeout", resp.status_code == 504 and resp.get_json() == {"error": "timeout"})
        resp = alice.post(run_url(), json=body("x" * (8 * 1024 + 1)))
        check("run: source over 8 KB -> 400 code_too_large", resp.status_code == 400 and resp.get_json() == {"error": "code_too_large"})
        check("run: bob cannot use alice's attempt -> 404", bob.post(run_url(), json=body()).status_code == 404)
        check("run: wrong scenario for this attempt -> 404", alice.post(run_url("mle-3"), json=body()).status_code == 404)
        check("run: unknown scenario -> 404", alice.post(run_url("zzz-1"), json=body()).status_code == 404)
        resp = alice.post(run_url(), json=body(question_id="mle-1-q1"))
        check("run: a non-code question id -> 400 invalid_question_id", resp.status_code == 400 and resp.get_json() == {"error": "invalid_question_id"})
        check("run: unknown question id -> 400", alice.post(run_url(), json=body(question_id="nope")).status_code == 400)
        check("run: empty source -> 400 invalid_source", alice.post(run_url(), json=body("  ")).get_json() == {"error": "invalid_source"})
        check("run: source not a string -> 400", alice.post(run_url(), json=body(5)).status_code == 400)
        check("run: bad attempt_id -> 400", alice.post(run_url(), json={"attempt_id": "1", "question_id": qid, "source": "x"}).status_code == 400)
        resp = alice.post(run_url(), data="nope", content_type="application/json")
        check("run: non-JSON body -> 400 invalid_body", resp.status_code == 400 and resp.get_json() == {"error": "invalid_body"})
        resp = alice.post(run_url(), json=body("x" * 40000))
        check("run: oversized body -> 400 body_too_large", resp.status_code == 400 and resp.get_json() == {"error": "body_too_large"})

        saved = routes.CODE_RUN_LIMIT_PER_HOUR
        reset_rate_limits()
        routes.CODE_RUN_LIMIT_PER_HOUR = 2
        codes = [alice.post(run_url(), json=body()).status_code for _ in range(3)]
        routes.CODE_RUN_LIMIT_PER_HOUR = saved
        resp = alice.post(run_url(), json=body())
        check("run: its own rate limit -> third call 429", codes == [200, 200, 429])
        check("run: the default limit is 60 per hour", saved == 60 and routes.CODE_CHECK_LIMIT_PER_HOUR == 30)
        reset_rate_limits()

        # ---- Check
        answer_url = "/scenarios/mle-1/answer"

        def check_body(source, **extra):
            return dict({"attempt_id": attempt_id, "question_id": qid, "answer": source}, **extra)

        for mode in ("# MODE:down", "# MODE:slow"):
            resp = alice.post(answer_url, json=check_body(mode))
            check(f"check: runner failure ({mode[8:]}) returns a fixed code and is not an answer",
                  resp.status_code in (503, 504) and only_code(resp) and resp.get_json()["error"] in ("runner_unavailable", "timeout"))
        with app.app_context():
            row = db.session.get(ScenarioAttempt, attempt_id)
            check("check: a runner failure does NOT lock the answer", qid not in (row.answers or {}))
        resp = alice.post(answer_url, json=check_body("x" * (8 * 1024 + 1)))
        check("check: source over 8 KB -> code_too_large, nothing locked", resp.get_json() == {"error": "code_too_large"})
        check("check: a non-string answer -> 400 invalid_answer", alice.post(answer_url, json=check_body(["a"])).get_json() == {"error": "invalid_answer"})
        check("check: an empty answer -> 400", alice.post(answer_url, json=check_body("  ")).status_code == 400)
        check("check: bob cannot check alice's attempt -> 404", bob.post(answer_url, json=check_body("# MODE:pass")).status_code == 404)
        with app.app_context():
            row = db.session.get(ScenarioAttempt, attempt_id)
            check("check: failed and refused checks left the attempt unlocked", qid not in (row.answers or {}))
        resumed = alice.post("/scenarios/mle-1/start", json={}).get_json()
        check("check: after a runner failure the question is still open on resume", qid not in resumed["locked"])

        saved = routes.CODE_CHECK_LIMIT_PER_HOUR
        reset_rate_limits()
        routes.CODE_CHECK_LIMIT_PER_HOUR = 2
        codes = [alice.post(answer_url, json=check_body("# MODE:down")).status_code for _ in range(3)]
        routes.CODE_CHECK_LIMIT_PER_HOUR = saved
        check("check: its own rate limit applies to code checks (3rd -> 429)", codes == [503, 503, 429])
        reset_rate_limits()

        resp = alice.post(answer_url, json=check_body("# MODE:mixed"))
        res = resp.get_json()["result"]
        rb = json.dumps(res)
        check("check: mixed result locks, 0 points, counts only for hidden tests",
              resp.status_code == 200 and res["correct"] is False and res["awarded"] == 0
              and res["visible_passed"] == [True, True] and res["hidden_total"] == 2 and res["hidden_passed"] == 0)
        check("check: the result shows the explanation but never the solution or the hidden tests",
              res["explanation"] == q["explanation"] and "SECRET_REFERENCE_MARKER" not in rb and "10 20" not in rb and "-1 1" not in rb
              and "'1 2'" in res["correct_answer"])
        with app.app_context():
            row = db.session.get(ScenarioAttempt, attempt_id)
            check("check: the locked record is stored on the attempt", row.answers[qid]["passed"] is False and row.answers[qid]["source"] == "# MODE:mixed")
        resp = alice.post(answer_url, json=check_body("# MODE:pass"))
        check("check: a locked answer cannot be redone (same stored result)", resp.get_json()["result"]["correct"] is False)
        resumed = alice.post("/scenarios/mle-1/start", json={}).get_json()
        check("check: resume returns the locked code result", resumed["locked"][qid]["hidden_passed"] == 0
              and "SECRET_REFERENCE_MARKER" not in json.dumps(resumed))

        # a second attempt for a passing Check
        alice.post("/scenarios/mle-1/submit", json={"attempt_id": attempt_id, "answers": {qid: {"passed": True, "visible": [True, True], "hidden_passed": 2, "hidden_total": 2}}})
        with app.app_context():
            row = db.session.get(ScenarioAttempt, attempt_id)
            check("submit: a forged code record from the client is ignored (stored mixed record wins)",
                  row.submitted_at is not None and row.answers[qid]["passed"] is False and row.score == 0)
        second = alice.post("/scenarios/mle-1/start", json={}).get_json()["attempt_id"]
        check("submit: a new attempt starts after submitting", second != attempt_id)
        resp = alice.post("/scenarios/mle-1/submit", json={"attempt_id": second, "answers": {qid: {"passed": True, "visible": [True, True], "hidden_passed": 2, "hidden_total": 2}}})
        sub = resp.get_json()
        mine = [r for r in sub["results"] if r["question_id"] == qid][0]
        check("submit: a forged passing record for an UNLOCKED code question scores 0", resp.status_code == 200 and mine["awarded"] == 0 and sub["score"] == 0)
        third = alice.post("/scenarios/mle-1/start", json={}).get_json()["attempt_id"]
        resp = alice.post(answer_url, json={"attempt_id": third, "question_id": qid, "answer": "# MODE:pass"})
        res = resp.get_json()["result"]
        check("check: a source that passes every test -> correct, 10 points",
              resp.status_code == 200 and res["correct"] is True and res["awarded"] == 10 and res["hidden_passed"] == 2)
        resp = alice.post("/scenarios/mle-1/submit", json={"attempt_id": third, "answers": {}})
        sub = resp.get_json()
        check("submit: a locked passing code answer counts 10 points",
              sub["score"] == 10 and [r for r in sub["results"] if r["question_id"] == qid][0]["awarded"] == 10 and sub["max_score"] == 50)
        fourth = alice.post("/scenarios/mle-1/start", json={}).get_json()["attempt_id"]
        resp = alice.post(answer_url, json={"attempt_id": fourth, "question_id": qid, "answer": "# MODE:err"})
        check("check: a program that raises -> locked wrong, 0 points", resp.get_json()["result"]["awarded"] == 0)
        alice.post("/scenarios/mle-1/submit", json={"attempt_id": fourth, "answers": {}})
        fifth = alice.post("/scenarios/mle-1/start", json={}).get_json()["attempt_id"]
        resp = alice.post(answer_url, json={"attempt_id": fifth, "question_id": qid, "answer": "# MODE:timeout"})
        check("check: a program timeout -> locked wrong, 0 points", resp.get_json()["result"]["awarded"] == 0)

        # ---- through the real adapter, with the HTTP layer stubbed
        import requests
        app.config["CODE_RUNNER"] = "onecompiler"
        app.config["ONECOMPILER_API_KEY"] = FAKE_KEY
        real_post = cr.requests.post
        alice.post("/scenarios/mle-1/submit", json={"attempt_id": fifth, "answers": {}})
        sixth = alice.post("/scenarios/mle-1/start", json={}).get_json()["attempt_id"]
        try:
            cr.requests.post = lambda url, **kw: FakeResponse(403, None, CLOUDFLARE_HTML)
            for url, payload in ((run_url(), {"attempt_id": sixth, "question_id": qid, "source": "print(1)"}),
                                 (answer_url, {"attempt_id": sixth, "question_id": qid, "answer": "print(1)"})):
                resp = alice.post(url, json=payload)
                text = resp.get_data(as_text=True)

                check(f"{url.split('/')[-1]}: a Cloudflare page -> only the fixed code, no provider text or key",
                      resp.status_code == 503 and resp.get_json() == {"error": "runner_unavailable"}
                      and not any(w in text for w in PROVIDER_TEXT + [FAKE_KEY]))
            cr.requests.post = lambda url, **kw: (_ for _ in ()).throw(requests.Timeout("Cloudflare " + FAKE_KEY))
            resp = alice.post(answer_url, json={"attempt_id": sixth, "question_id": qid, "answer": "print(1)"})
            check("check: provider timeout text never reaches the response",
                  resp.get_json() == {"error": "timeout"} and FAKE_KEY not in resp.get_data(as_text=True))
            with app.app_context():
                check("check: and the answer is still not locked", qid not in (db.session.get(ScenarioAttempt, sixth).answers or {}))
        finally:
            cr.requests.post = real_post
            app.config["CODE_RUNNER"] = "fake"

        # ---- languages: Python, C++, Java, JavaScript on the same stdin -> stdout tests
        from app.pipeline import code_starters
        seen = []
        base = scripted(q)

        def recording(source, stdins, language):
            seen.append(language)
            return base(source, stdins)
        cr.set_fake_runner(recording)
        started = alice.post("/scenarios/mle-1/start", json={}).get_json()
        cq = [x for x in started["scenario"]["questions"] if x["id"] == qid][0]
        check("languages: the start view offers Python, C++, Java and JavaScript (fake runner), in that order",
              started["attempt_id"] == sixth and [lang["id"] for lang in cq["languages"]] == ["python", "cpp", "java", "javascript"])
        check("languages: Python keeps the problem's own starter; C++, Java and JavaScript get the generic templates",
              cq["starters"]["python"] == q["starter_code"]
              and all(cq["starters"][lang] == code_starters.GENERIC_STARTERS[lang] for lang in ("cpp", "java", "javascript")))
        blob = json.dumps(started)
        check("languages: hidden tests are never sent to the browser (exactly the visible tests; no hidden input anywhere)",
              cq["tests"] == [{"stdin": t["stdin"], "expected_stdout": t["expected_stdout"]} for t in TESTS if not t["hidden"]]
              and not any(json.dumps(t["stdin"])[1:-1] in blob for t in TESTS if t["hidden"]))

        def lang_body(language, source="# MODE:pass\nprint(1)"):
            return {"attempt_id": sixth, "question_id": qid, "source": source, "language": language}
        bad = [alice.post(run_url(), json=lang_body(v)) for v in ("cobol", "", 5, None, ["python"], "Python")]
        check("languages: an unknown or malformed language on Run -> 400 invalid_language (allowlist)",
              all(r.status_code == 400 and r.get_json() == {"error": "invalid_language"} for r in bad))
        seen.clear()
        resp = alice.post(run_url(), json=lang_body("java"))
        check("languages: Run passes the chosen language to the runner", resp.status_code == 200 and seen == ["java"])
        seen.clear()
        resp = alice.post(run_url(), json={"attempt_id": sixth, "question_id": qid, "source": "print(1)"})
        check("languages: no language in the body means Python (older clients keep working)", resp.status_code == 200 and seen == ["python"])
        resp = alice.post(answer_url, json={"attempt_id": sixth, "question_id": qid, "answer": "# MODE:pass", "language": "cobol"})
        with app.app_context():
            unlocked = qid not in (db.session.get(ScenarioAttempt, sixth).answers or {})
        check("languages: an unknown language on Check -> 400 invalid_language, and nothing is locked",
              resp.status_code == 400 and resp.get_json() == {"error": "invalid_language"} and unlocked)

        app.config["CODE_RUNNER"] = "local"
        real_which = cr.shutil.which
        cr.shutil.which = lambda name: None          # no g++, javac, java or node on this "machine"
        try:
            resp = alice.post(run_url(), json=lang_body("cpp"))
            offered = [x for x in alice.post("/scenarios/mle-1/start", json={}).get_json()["scenario"]["questions"]
                       if x["id"] == qid][0]["languages"]
        finally:
            cr.shutil.which = real_which
            app.config["CODE_RUNNER"] = "fake"
        check("languages: CODE_RUNNER=local without g++/javac/node offers Python only; C++ -> 400 language_unavailable",
              [lang["id"] for lang in offered] == ["python"] and resp.status_code == 400
              and resp.get_json() == {"error": "language_unavailable"})

        seen.clear()
        js_source = "// MODE:pass\n# MODE:pass\nconsole.log(3);"
        resp = alice.post(answer_url, json={"attempt_id": sixth, "question_id": qid, "answer": js_source, "language": "javascript"})
        res = resp.get_json()["result"]
        check("languages: Check runs every test in the chosen language and the result names it",
              resp.status_code == 200 and seen == ["javascript"] and res["correct"] is True and res["language"] == "javascript")
        with app.app_context():
            stored = db.session.get(ScenarioAttempt, sixth).answers[qid]
        check("languages: the language is stored with the locked answer (server-side record)",
              stored["language"] == "javascript" and stored["source"] == js_source and stored["passed"] is True)
        resumed = alice.post("/scenarios/mle-1/start", json={}).get_json()
        check("languages: a resumed attempt returns the locked language and code",
              resumed["locked"][qid]["language"] == "javascript" and resumed["locked"][qid]["source"] == js_source)
        resp = alice.post(answer_url, json={"attempt_id": sixth, "question_id": qid, "answer": "# MODE:wrong", "language": "python"})
        res = resp.get_json()["result"]
        check("languages: a second Check in another language returns the stored result unchanged",
              res["language"] == "javascript" and res["correct"] is True)
        cr.set_fake_runner(scripted(q))

        # existing behaviour
        resp = alice.post(answer_url, json={"attempt_id": sixth, "question_id": "mle-1-q1", "answer": ["a"]})
        check("other question types still lock through the same route", resp.status_code == 200 and "correct" in resp.get_json()["result"])
        js = Path("app/static/js/scenarios.js").read_text(encoding="utf-8")
        check("scenarios.js: no innerHTML / insertAdjacentHTML / document.write and no direct fetch()",
              not any(w in js for w in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")) and "fetch(" not in js)
        check("scenarios.js: has the code editor, the unavailable message and uses the shared request helper for Run",
              "function buildCode" in js and "Code check unavailable, try again." in js and "/code/run" in js and "await request(" in js)
        check("scenarios.js: 'unavailable' is shown for runner_unavailable only; runtime_error says the code crashed",
              'if (code === "runner_unavailable") return "Code check unavailable, try again.";' in js
              and js.count("Code check unavailable") == 1
              and 'if (code === "runtime_error") return "Your code crashed' in js)
        check("scenarios.js: the OA screen has a language picker and sends the chosen language on Run and Check",
              "oa-lang" in js and "language: lang" in js and "language: input.language()" in js and 'role: "tablist"' in js)
        css = Path("app/static/css/style.css").read_text(encoding="utf-8")
        check("style.css: code editor is monospace, full width, with 44 px (--tap) buttons, two panes from 900 px",
              ".scen-code {" in css and "monospace" in css and "width: 100%" in css
              and ".oa-buttons .btn { min-height: var(--tap);" in css and "@media (min-width: 900px)" in css)
        check("the old skill map page is gone (/dsa -> 404)", alice.get("/dsa").status_code == 404)
    finally:
        cr.set_fake_runner(None)
        store.set_directory(None)
        shutil.rmtree(tmp, ignore_errors=True)
        with app.app_context():
            for uid in user_ids:
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                CareerProfile.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


# ---------------------------------------------------------------- part 5: languages (runner, starters, local mode)
def test_languages():
    import requests
    from app.pipeline import code_runner as cr, code_starters, scenario_engine as engine

    saved_env = {k: os.environ.get(k) for k in ("CODE_RUNNER", "ONECOMPILER_API_KEY")}
    real_post, real_which = requests.post, cr.shutil.which
    try:
        check("languages: the allowlist is exactly python, cpp, java, javascript",
              list(cr.LANGUAGES) == ["python", "cpp", "java", "javascript"] and cr.DEFAULT_LANGUAGE == "python")
        expected = {"python": ("python", "main.py"), "cpp": ("cpp", "main.cpp"), "java": ("java", "Main.java"),
                    "javascript": ("nodejs", "index.js")}
        bodies = {lang: cr._onecompiler_body("src", ["a", "b"], lang) for lang in expected}
        check("languages: OneCompiler gets its own language id and file name per language (nodejs for JavaScript)",
              all(bodies[lang]["language"] == lid and bodies[lang]["files"] == [{"name": name, "content": "src"}]
                  and bodies[lang]["stdin"] == ["a", "b"] for lang, (lid, name) in expected.items()))

        # the adapter, with the HTTP layer stubbed (never a real call)
        os.environ["CODE_RUNNER"], os.environ["ONECOMPILER_API_KEY"] = "onecompiler", FAKE_KEY
        sent = []

        def post(url, **kw):
            sent.append(kw["json"])
            return FakeResponse(200, [{"stdout": "3\n", "stderr": None, "exception": None}])
        cr.requests.post = post
        cr.run_batch("int main(){}", ["1 2"], "cpp")
        check("languages: run_batch sends the language to the provider (cpp, main.cpp)",
              sent and sent[-1]["language"] == "cpp" and sent[-1]["files"][0]["name"] == "main.cpp")
        cr.run_batch("print(1)", ["1 2"])
        check("languages: run_batch without a language is Python (main.py)",
              sent[-1]["language"] == "python" and sent[-1]["files"][0]["name"] == "main.py")
        sent.clear()
        try:
            cr.run_batch("x", ["1"], "cobol")
            refused = False
        except cr.CodeRunnerError as e:
            refused = e.code == "runner_unavailable"
        check("languages: an unknown language never reaches the provider (runner_unavailable, no call)", refused and not sent)
        check("languages: onecompiler and fake offer all four languages",
              cr.available_languages() == list(cr.LANGUAGES))

        # local mode: only installed toolchains
        os.environ["CODE_RUNNER"] = "local"
        cr.shutil.which = lambda name: None
        none = cr.available_languages()
        cr.shutil.which = lambda name: f"/usr/bin/{name}"
        every = cr.available_languages()
        cr.shutil.which = lambda name: "/usr/bin/node" if name == "node" else None
        node_only = cr.available_languages()
        cr.shutil.which = real_which
        check("languages: local offers Python always and C++/Java/JavaScript only when g++ / javac+java / node exist",
              none == ["python"] and every == list(cr.LANGUAGES) and node_only == ["python", "javascript"])
        build, run_cmd = cr._local_commands("cpp", "F")
        check("languages: local C++ compiles main.cpp as C++17 and runs the binary",
              "-std=c++17" in build and build[-1].endswith("main.cpp") and run_cmd == [build[build.index("-o") + 1]])
        build, run_cmd = cr._local_commands("java", "F")
        check("languages: local Java compiles Main.java and runs class Main",
              build[-1].endswith("Main.java") and run_cmd[-1] == "Main")
        build, run_cmd = cr._local_commands("javascript", "F")
        check("languages: local JavaScript runs index.js with node", build is None and run_cmd[-1].endswith("index.js"))
        crash = cr.run_batch("x = 1 / 0\n", [""], "python")[0]
        check("languages: local tracebacks name main.py, never the server's temp folder",
              "ZeroDivisionError" in crash["stderr"] and "main.py" in crash["stderr"] and "levelup-run-" not in crash["stderr"])

        # the starters
        g = code_starters.GENERIC_STARTERS
        check("languages: C++, Java and JavaScript starter templates exist and read all of stdin",
              set(g) == {"cpp", "java", "javascript"} and "cin.rdbuf()" in g["cpp"] and "System.in" in g["java"]
              and "readFileSync(0" in g["javascript"])
        check("languages: every generic starter tells the student to follow the problem's input/output format",
              all(code_starters.FORMAT_NOTE in text for text in g.values()) and "public class Main" in g["java"])
        check("languages: no generic starter prints anything, so it can never pass a test by itself",
              "cout" not in g["cpp"] and "System.out" not in g["java"] and "console.log" not in g["javascript"])
        check("languages: Python uses the problem's own starter",
              code_starters.starter_for("python", {"starter_code": "S"}) == "S" and code_starters.starter_for("cpp", {}) == g["cpp"])
        q = code_question()
        old = engine.grade_question(q, {"passed": False, "visible": [False, False], "hidden_passed": 0, "hidden_total": 2})
        _, record = engine.grade_code_result(q, [], "src", "java")
        check("languages: the engine stores the language on the record; records from before languages mean Python",
              old["language"] == "python" and record["language"] == "java")
    finally:
        cr.requests.post = real_post
        cr.shutil.which = real_which
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


SECTIONS = [test_adapter, test_validator, test_engine, test_routes, test_languages]


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

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


SECTIONS = [test_validator, test_blind_solve]


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

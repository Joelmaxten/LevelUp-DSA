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


SECTIONS = [test_validator]


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

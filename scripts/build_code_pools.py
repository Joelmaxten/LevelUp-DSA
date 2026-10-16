"""
Builds the code_pool of each scenario from the authoring sources in scripts/code_pools/<path slug>.py, and checks
every problem before anything is written.

For every problem and every data variant it:
  1. runs the reference solution on every test input with THIS machine's Python (no provider, no credits), and uses
     its output as the test's expected_stdout;
  2. checks the hand-worked expected output of each visible example against that output;
  3. checks a second, independent implementation (`alt`, written differently) gives the same output on every input;
  4. checks the starter code (what the student starts from) does NOT already pass every test.
Any mismatch stops the build and nothing is written. The written file then goes through the normal scenario
validator.

Usage:
    PYTHONPATH=. python scripts/build_code_pools.py            # check only, writes nothing
    PYTHONPATH=. python scripts/build_code_pools.py --write    # check, then write data/scenarios/<slug>.json
    PYTHONPATH=. python scripts/build_code_pools.py --write --paths full-stack-development data-science
"""
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.scenario_validator import validate_scenario_file  # noqa: E402

SOURCES = ROOT / "scripts" / "code_pools"
SCENARIOS = ROOT / "data" / "scenarios"
TIME_LIMIT_S = 5


def run(source, stdin):
    """(stdout, ok) from running source with this machine's Python."""
    with tempfile.TemporaryDirectory() as folder:
        main = Path(folder) / "main.py"
        main.write_text(source, encoding="utf-8")
        try:
            done = subprocess.run([sys.executable, "-I", str(main)], input=stdin, capture_output=True, text=True,
                                  encoding="utf-8", timeout=TIME_LIMIT_S, cwd=folder)
        except subprocess.TimeoutExpired:
            return "", False
    return done.stdout, done.returncode == 0 and not done.stderr.strip()


def norm(text):
    return text.replace("\r\n", "\n").strip()


def build_problem(pid, spec, problems_out, failures):
    if not callable(spec.get("alt")):
        failures.append(f"{pid}: no independent second implementation ('alt')")
        return
    tests_per_variant = []
    starter_passes_all = True
    for n, variant in enumerate(spec["variants"], 1):
        tests = []
        cases = [(stdin, expected, False) for stdin, expected in variant["visible"]]
        cases += [(stdin, None, True) for stdin in variant["hidden"]]
        for stdin, hand, hidden in cases:
            out, ok = run(spec["solution"], stdin)
            where = f"{pid} variant {n} {'hidden' if hidden else 'visible'} input {stdin[:40]!r}"
            if not ok or not norm(out):
                failures.append(f"{where}: reference solution failed or printed nothing")
                continue
            if hand is not None and norm(hand) != norm(out):
                failures.append(f"{where}: hand-worked {norm(hand)!r} != reference {norm(out)!r}")
            alt = norm(spec["alt"](stdin))
            if alt != norm(out):
                failures.append(f"{where}: independent check {alt!r} != reference {norm(out)!r}")
            s_out, s_ok = run(spec["starter"], stdin)
            if not (s_ok and norm(s_out) == norm(out)):
                starter_passes_all = False
            tests.append({"stdin": stdin, "expected_stdout": norm(out) + "\n", "hidden": hidden})
        tests_per_variant.append({"params": dict(variant.get("params", {})), "tests": tests})
    if starter_passes_all:
        failures.append(f"{pid}: the starter code already passes every test")
    problems_out.append({
        "id": pid, "prompt": spec["prompt"], "language": "python",
        "starter_code": spec["starter"], "reference_solution": spec["solution"],
        "ds_topic": spec["ds_topic"], "difficulty": spec["difficulty"], "skills": list(spec["skills"]),
        "explanation": spec["explanation"], "key_justification": spec["key_justification"],
        "points": 10, "variants": tests_per_variant,
    })


def build_path(slug, write):
    module = importlib.import_module(f"scripts.code_pools.{slug.replace('-', '_')}")
    file = SCENARIOS / f"{slug}.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    failures, counts = [], 0
    by_id = {s["id"]: s for s in data["scenarios"]}
    for sid, specs in module.PROBLEMS.items():
        if sid not in by_id:
            failures.append(f"{slug}: unknown scenario {sid}")
            continue
        pool = []
        for k, spec in enumerate(specs, 1):
            build_problem(f"{sid}-c{k}", spec, pool, failures)
            counts += 1
        by_id[sid]["code_pool"] = pool
    result = validate_scenario_file(data)
    failures += [f"validator: {e}" for e in result["errors"]]
    if failures:
        print(f"FAIL {slug}: {len(failures)} problem(s)")
        for f in failures:
            print("   ", f)
        return False
    tests = sum(len(v["tests"]) for s in data["scenarios"] for p in s.get("code_pool", []) for v in p["variants"])
    print(f"OK   {slug}: {counts} problems, {tests} tests, all checks pass"
          + ("" if result["warnings"] == [] else f" (warnings: {result['warnings']})"))
    if write:
        original = file.read_text(encoding="utf-8")
        if original.count("\n") <= 2:     # keep a one-line file one line, so diffs stay comparable
            text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        else:
            text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        file.write_text(text, encoding="utf-8")
    return True


def main(argv):
    write = "--write" in argv
    if "--paths" in argv:
        slugs = argv[argv.index("--paths") + 1:]
        slugs = [s for s in slugs if not s.startswith("--")]
    else:
        slugs = sorted(p.stem for p in SOURCES.glob("*.py") if not p.stem.startswith("_"))
        slugs = [s.replace("_", "-") for s in slugs]
    ok = all([build_path(s, write) for s in slugs])
    if not write:
        print("Check only: nothing was written. Add --write to update the scenario files.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

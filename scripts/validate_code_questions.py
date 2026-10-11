"""
Runs the reference_solution of every code question in data/scenarios/ against ALL its tests, one runner batch
(= one provider credit) per question, and reports pass/fail per test. Pool problems (a scenario's code_pool) are
checked too: by default only their FIRST data variant (one credit per problem); --all-variants checks every variant.
--max-credits N stops after N provider calls. scripts/build_code_pools.py already ran every variant with this
machine's Python before the files were written; this script confirms the PROVIDER agrees.

DRY RUN by default: nothing is sent; it prints how many credits --run would use. --run calls the configured
code runner (CODE_RUNNER; the key variable ONECOMPILER_API_KEY is only reported as set / not set, never printed).

Usage:
    PYTHONPATH=. python scripts/validate_code_questions.py [--run] [--all-variants] [--max-credits N] [DIR]

Exits 1 if any reference solution fails a test (only possible with --run) or the runner is unavailable.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before the app imports: config reads the environment when imported

from app.pipeline import code_runner, scenario_engine as engine, scenario_store as store
from app.pipeline.scenario_validator import materialize

DEFAULT_DIR = Path("data/scenarios")


def code_questions(directory, all_variants=False):
    store.set_directory(directory)
    out = []
    for path_name, data in store.load_all().items():
        for scenario in data["scenarios"]:
            for q in scenario["questions"]:
                if q["type"] == "code":
                    out.append((path_name, q))
            for problem in scenario.get("code_pool") or []:
                for v in range(len(problem["variants"]) if all_variants else 1):
                    q = materialize(problem, v)
                    q["id"] = f"{problem['id']}/v{v + 1}"
                    out.append((path_name, q))
    return out


def batches(tests):
    """The runner takes at most MAX_STDINS inputs per call; longer test lists need more than one call."""
    step = code_runner.MAX_STDINS
    return [tests[i:i + step] for i in range(0, len(tests), step)]


def main(argv):
    argv = list(argv)
    max_credits = None
    if "--max-credits" in argv:
        i = argv.index("--max-credits")
        max_credits = int(argv[i + 1])
        del argv[i:i + 2]
    args = [a for a in argv[1:] if not a.startswith("--")]
    really_run = "--run" in argv[1:]
    directory = Path(args[0]) if args else DEFAULT_DIR
    questions = code_questions(directory, all_variants="--all-variants" in argv[1:])
    credits = sum(len(batches(q["tests"])) for _, q in questions)

    variable = code_runner.api_key_variable()
    print(f"code runner: {code_runner.runner_name()}")
    print(f"{variable}: {'set' if os.environ.get(variable, '').strip() else 'NOT set'}")
    print(f"{len(questions)} code question(s) in {directory}; a run would use {credits} credit(s) "
          f"(one batch of up to {code_runner.MAX_STDINS} tests per call)"
          + (f", capped at {max_credits} by --max-credits." if max_credits is not None else "."))
    if not really_run:
        for _, q in questions:
            print(f"  {q['id']}: {len(q['tests'])} tests ({sum(t['hidden'] for t in q['tests'])} hidden)")
        print("Dry run: nothing was sent. Add --run to call the provider.")
        return 0

    failed = used = 0
    for path_name, q in questions:
        needed = len(batches(q["tests"]))
        if max_credits is not None and used + needed > max_credits:
            print(f"Stopped at --max-credits {max_credits}; the remaining questions were not checked.")
            break
        try:
            runs = []
            for chunk in batches(q["tests"]):
                runs += code_runner.run_batch(q["reference_solution"], [t["stdin"] for t in chunk])
                used += 1
        except code_runner.CodeRunnerError as error:
            print(f"ERROR {q['id']}: runner {error.code}")
            failed += 1
            continue
        flags = [engine.run_passed(t["expected_stdout"], r) for t, r in zip(q["tests"], runs)]
        bad = [i + 1 for i, ok in enumerate(flags) if not ok]
        print(f"{'OK  ' if not bad else 'FAIL'} {q['id']}: {sum(flags)}/{len(flags)} tests pass"
              + (f" (failing: {', '.join(map(str, bad))})" if bad else ""))
        failed += bool(bad)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

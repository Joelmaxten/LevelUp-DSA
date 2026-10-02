"""
How does the career quiz behave over many random answer sequences? No database, no network.

Runs N random sequences (default 1,000, seeded) through the CURRENT engine and, for comparison,
through the ORIGINAL engine and question bank (the version at commit 4505662, loaded from git), and
prints, for each:
  - how often each of the 15 paths is #1 (as the engine shows it) and in the top-score group;
  - for each pair (career_path_registry.PATH_PAIRS), how often the two end within 1 point of each
    other and exactly equal;
  - the number of questions asked (average and distribution) and how often the quiz stops before
    the maximum.

READ THIS BEFORE DRAWING CONCLUSIONS: random answers are NOT a realistic distribution of students.
Real students answer consistently (a person who likes building interfaces picks the interface
options again and again), so real results are far more concentrated than these. The numbers show
whether the quiz CAN reach every path and CAN tell each pair apart, and how big the structural
bias of the signal table is - not how often real students will see each result.

Usage:
    PYTHONPATH=. python scripts/simulate_quiz.py [N] [--no-old]
"""
import random
import subprocess
import sys
import types
from collections import Counter

from app.pipeline import career_quiz_engine as new_engine
from app.pipeline.career_path_registry import CAREER_PATHS, PATH_PAIRS
from app.pipeline.career_quiz_data import QUESTIONS as NEW_QUESTIONS

OLD_COMMIT = "4505662"
SEED = 20261002


def load_original():
    """The engine and data as they were before the redesign, imported from git into private modules."""
    def show(path):
        return subprocess.run(["git", "show", f"{OLD_COMMIT}:{path}"], capture_output=True, text=True, check=True).stdout

    data = types.ModuleType("quiz_data_original")
    exec(compile(show("app/pipeline/career_quiz_data.py"), "quiz_data_original", "exec"), data.__dict__)
    sys.modules["quiz_data_original"] = data
    source = show("app/pipeline/career_quiz_engine.py").replace(
        "from app.pipeline.career_quiz_data import", "from quiz_data_original import")
    engine = types.ModuleType("quiz_engine_original")
    exec(compile(source, "quiz_engine_original", "exec"), engine.__dict__)
    return engine, data.QUESTIONS


def run_random(engine, questions, rng):
    session = engine.new_session()
    while True:
        question_id = engine.next_question(session)
        if question_id is None:
            break
        engine.apply_answer(session, question_id, rng.choice(list(questions[question_id]["options"])))
        if engine.should_stop(session):
            break
    return session


def summarise(engine, questions, n):
    rng = random.Random(SEED)
    sessions = [run_random(engine, questions, rng) for _ in range(n)]
    maximum = min(engine.MAX_QUESTIONS, len(questions))
    first, group = Counter(), Counter()
    for s in sessions:
        # "#1 as shown": highest score, ties by the engine's own ordering of get_results.
        results = engine.get_results(s)
        first[results[0]["career_path"]] += 1
        best = results[0]["score"]
        for r in results:
            if r["score"] == best:
                group[r["career_path"]] += 1
    pairs = {}
    for a, b in PATH_PAIRS:
        pairs[(a, b)] = (sum(1 for s in sessions if abs(s["scores"][a] - s["scores"][b]) <= 1),
                         sum(1 for s in sessions if s["scores"][a] == s["scores"][b]))
    asked = Counter(len(s["answered"]) for s in sessions)
    return {"first": first, "group": group, "pairs": pairs, "asked": asked, "maximum": maximum,
            "early": sum(c for k, c in asked.items() if k < maximum), "mean": sum(k * c for k, c in asked.items()) / n,
            "bank": len(questions)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 1000
    new = summarise(new_engine, NEW_QUESTIONS, n)
    old = None
    if "--no-old" not in sys.argv:
        engine, questions = load_original()
        old = summarise(engine, questions, n)

    print(f"{n} random answer sequences, seed {SEED}. Random answers are NOT a realistic student distribution (see the module docstring).\n")
    print(f"{'path':<32}" + (f"{'#1 old':>8}{'group old':>10}" if old else "") + f"{'#1 new':>8}{'group new':>10}")
    for p in CAREER_PATHS:
        print(f"{p:<32}" + (f"{old['first'][p]:>8}{old['group'][p]:>10}" if old else "") + f"{new['first'][p]:>8}{new['group'][p]:>10}")
    if old:
        print(f"\npaths never #1: old {sum(1 for p in CAREER_PATHS if not old['first'][p])} of 15, new {sum(1 for p in CAREER_PATHS if not new['first'][p])} of 15")

    print("\npairs ending within 1 point / exactly equal:")
    for pair in PATH_PAIRS:
        line = f"  {pair[0]} / {pair[1]}:"
        if old:
            line += f"  old {old['pairs'][pair][0]}/{n} within 1, {old['pairs'][pair][1]}/{n} equal;"
        line += f"  new {new['pairs'][pair][0]}/{n} within 1, {new['pairs'][pair][1]}/{n} equal"
        print(line)

    print("\nquestions asked:")
    for label, d in (("old", old), ("new", new)):
        if d:
            dist = ", ".join(f"{k}: {c}" for k, c in sorted(d["asked"].items()))
            print(f"  {label}: bank {d['bank']}, maximum {d['maximum']}, mean {d['mean']:.2f}; stopped before the maximum {d['early']}/{n}; distribution {{{dist}}}")


if __name__ == "__main__":
    main()

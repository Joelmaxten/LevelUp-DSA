"""
Regression test for the career quiz engine (app/pipeline/career_quiz_engine.py and the data in
career_quiz_data.py). Pure: no Flask, no database, no network.

It replays 30 seeded random answer sequences through the real engine - at every step the next
question comes from next_question(), the stopping point from should_stop() - and compares, for
each sequence, the questions asked in order, the answers given, the final scores, the ranking
and the stopping point with a golden file in scratch/golden/. It also checks two personas (all
"A" answers and all "B" answers must reach opposite results).

Usage:
    PYTHONPATH=. python scripts/smoke_test_quiz.py                        # compare with GOLDEN_FILE
    PYTHONPATH=. python scripts/smoke_test_quiz.py --capture FILE         # write the replay to FILE
    PYTHONPATH=. python scripts/smoke_test_quiz.py --golden FILE          # compare with another file

Golden files are tracked although scratch/ is gitignored (git add -f).
"""
import json
import random
import sys
from pathlib import Path

from app.pipeline import career_quiz_engine as engine
from app.pipeline.career_quiz_data import CAREER_PATHS, QUESTIONS

GOLDEN_FILE = Path("scratch/golden/quiz_before.json")
SEEDS = list(range(1, 31))

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def play(choose):
    """Runs one quiz. choose(question_id, options) -> option. Returns what happened."""
    session = engine.new_session()
    asked, answers = [], []
    while True:
        question_id = engine.next_question(session)
        if question_id is None:
            break
        option = choose(question_id, list(QUESTIONS[question_id]["options"]))
        engine.apply_answer(session, question_id, option)
        asked.append(question_id)
        answers.append(option)
        if engine.should_stop(session):
            break
    return {"asked": asked, "answers": answers, "answered": len(asked),
            "scores": session["scores"], "ranking": engine.get_results(session), "session": session}


def replay(seed):
    rng = random.Random(seed)
    result = play(lambda qid, options: rng.choice(options))
    result.pop("session")
    return {"seed": seed, **result}


def replay_all():
    return [replay(seed) for seed in SEEDS]


def top_group(ranking):
    best = ranking[0]["score"]
    return [r["career_path"] for r in ranking if r["score"] == best]


def persona_checks():
    a = play(lambda qid, options: "A")
    b = play(lambda qid, options: "B")
    top_a, top_b = top_group(a["ranking"]), top_group(b["ranking"])
    three_a = {r["career_path"] for r in a["ranking"][:3]}
    three_b = {r["career_path"] for r in b["ranking"][:3]}
    print(f"   all-A top: {top_a} (answered {a['answered']}); all-B top: {top_b} (answered {b['answered']})")
    check("persona: all-A and all-B answers reach different top results", not set(top_a) & set(top_b))
    check("persona: all-A and all-B top-3 paths do not overlap (opposite results)", not three_a & three_b)


def main():
    argv = sys.argv[1:]
    golden_file = Path(argv[argv.index("--golden") + 1]) if "--golden" in argv else GOLDEN_FILE
    runs = replay_all()

    if "--capture" in argv:
        target = Path(argv[argv.index("--capture") + 1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(runs), encoding="utf-8")
        print(f"wrote {target} ({len(runs)} sequences)")
        return

    check("replay is deterministic (the same seeds give the same quiz twice)", runs == replay_all())
    check("every replayed quiz asks distinct questions, ends within the bank, and answers are valid options",
          all(len(set(r["asked"])) == len(r["asked"]) <= len(QUESTIONS) and all(o in QUESTIONS[q]["options"] for q, o in zip(r["asked"], r["answers"])) for r in runs))
    check("every quiz asks at least MIN_QUESTIONS and at most the maximum",
          all(engine.MIN_QUESTIONS <= r["answered"] <= min(engine.MAX_QUESTIONS, len(QUESTIONS)) for r in runs))
    check("session state stays JSON-safe", all(json.dumps(r) for r in runs))
    check(f"golden file exists ({golden_file})", golden_file.exists())
    if golden_file.exists():
        golden = json.loads(golden_file.read_text(encoding="utf-8"))
        current = json.loads(json.dumps(runs))
        check(f"all {len(SEEDS)} seeded sequences match the golden file exactly (questions, answers, scores, ranking, stop point)",
              current == golden)
        if current != golden:
            changed = [g["seed"] for g, c in zip(golden, current) if g != c]
            print(f"   sequences that differ: {changed}")
    persona_checks()

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()

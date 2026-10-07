"""
Scenario engine: what a student may see, how answers are graded, and the unlock / recommendation rules.
Pure: no Flask, no database, no network. The scenario dicts are the validated file contents
(see scenario_validator.py); the routes in app/routes/scenarios.py wire this to storage.

Grading is all-or-nothing per question (10 points), and the server alone grades: the student-facing view
(public_view) never contains the key, the explanations or the justification.
"""
import random

POINTS_PER_QUESTION = 10
PASS_PERCENT = 70

STATE_LOCKED, STATE_OPEN, STATE_ATTEMPTED, STATE_PASSED = "locked", "open", "attempted", "passed"


# ---------------------------------------------------------------- student-facing view
def _shuffled(pool, rng):
    pool = [{"id": o["id"], "text": o["text"]} for o in pool]
    rng.shuffle(pool)
    return pool


def public_question(question, seed):
    """One question without any answer field; options/items/targets shuffled deterministically by seed."""
    rng = random.Random(f"{seed}:{question['id']}")
    view = {"id": question["id"], "type": question["type"], "prompt": question["prompt"]}
    if question["type"] == "match":
        view["items"] = _shuffled(question["items"], rng)
        view["targets"] = _shuffled(question["targets"], rng)
    else:
        view["options"] = _shuffled(question["options"], rng)
    return view


def public_view(scenario, seed):
    """The scenario WITHOUT correct, explanation, why_others_wrong or key_justification (whitelist, not deletion)."""
    return {
        "id": scenario["id"],
        "order": scenario["order"],
        "title": scenario["title"],
        "ladder_stage": scenario["ladder_stage"],
        "difficulty": scenario["difficulty"],
        "estimated_minutes": scenario["estimated_minutes"],
        "background": scenario["background"],
        "constraints": list(scenario["constraints"]),
        "tests_topics": list(scenario["tests_topics"]),
        "questions": [public_question(q, seed) for q in scenario["questions"]],
    }


# ---------------------------------------------------------------- grading
def _is_str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _answer_is_correct(question, answer):
    """True only for the exact answer; any malformed answer is simply False. Never raises."""
    qtype, key = question["type"], question["correct"]
    if qtype == "single_choice":
        if isinstance(answer, str):
            answer = [answer]
        return _is_str_list(answer) and len(answer) == 1 and answer == key
    if qtype == "multi_select":
        return (_is_str_list(answer) and len(set(answer)) == len(answer)
                and set(answer) == set(key))
    if qtype == "order":
        return _is_str_list(answer) and answer == key
    if qtype == "match":
        return (isinstance(answer, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in answer.items())
                and answer == key)
    return False


def grade_question(question, answer):
    try:
        correct = bool(_answer_is_correct(question, answer))
    except Exception:
        correct = False
    return {
        "question_id": question["id"],
        "correct": correct,
        "awarded": POINTS_PER_QUESTION if correct else 0,
        "correct_answer": question["correct"],
        "explanation": question["explanation"],
        "why_others_wrong": question["why_others_wrong"],
    }


def grade(scenario, answers):
    """
    answers: {question_id: answer}. Missing questions, unknown ids and wrong shapes are graded wrong.
    Returns {"results": [per-question result], "score", "max_score", "percent", "passed"}.
    """
    if not isinstance(answers, dict):
        answers = {}
    results = [grade_question(q, answers.get(q["id"])) for q in scenario["questions"]]
    score = sum(r["awarded"] for r in results)
    max_score = POINTS_PER_QUESTION * len(results)
    return {
        "results": results,
        "score": score,
        "max_score": max_score,
        "percent": round(100 * score / max_score) if max_score else 0,
        "passed": max_score > 0 and score * 100 >= PASS_PERCENT * max_score,
    }


def is_passing(score, max_score):
    return bool(max_score) and score * 100 >= PASS_PERCENT * max_score


# ---------------------------------------------------------------- progress rules
def compute_progress(scenarios, attempts):
    """
    scenarios: the file's scenario dicts. attempts: submitted attempts only, as dicts with scenario_id, score,
    max_score (unfinished attempts do not count). Returns {scenario_id: {state, best_score, max_score}}.

    Scenario 1 is always open; scenario N+1 opens after any submitted attempt on N; the best score is kept.
    """
    best = {}
    for a in attempts:
        if a.get("score") is None or not a.get("max_score"):
            continue
        current = best.get(a["scenario_id"])
        if current is None or a["score"] > current["score"]:
            best[a["scenario_id"]] = {"score": a["score"], "max_score": a["max_score"]}

    ordered = sorted(scenarios, key=lambda s: s["order"])
    progress = {}
    previous_submitted = True   # scenario 1 has no predecessor
    for s in ordered:
        b = best.get(s["id"])
        if b is not None:
            state = STATE_PASSED if is_passing(b["score"], b["max_score"]) else STATE_ATTEMPTED
        else:
            state = STATE_OPEN if previous_submitted else STATE_LOCKED
        progress[s["id"]] = {"state": state, "best_score": b["score"] if b else None,
                             "max_score": b["max_score"] if b else None}
        previous_submitted = b is not None
    return progress


def weak_topics(scenarios, progress):
    """tests_topics of every scenario whose best score is below the pass mark (order kept, no duplicates)."""
    topics = []
    for s in sorted(scenarios, key=lambda s: s["order"]):
        p = progress.get(s["id"])
        if p and p["best_score"] is not None and not is_passing(p["best_score"], p["max_score"]):
            for t in s["tests_topics"]:
                if t not in topics:
                    topics.append(t)
    return topics


def recommended_next(scenarios, progress, weak=None):
    """
    The first open scenario not yet passed, preferring one whose tests_topics overlap the weak topics.
    "Open" includes attempted-but-not-passed. None when everything is passed (or nothing is open).
    """
    candidates = [s for s in sorted(scenarios, key=lambda s: s["order"])
                  if progress.get(s["id"], {}).get("state") in (STATE_OPEN, STATE_ATTEMPTED)]
    if not candidates:
        return None
    weak_set = {t.lower() for t in (weak or [])}
    if weak_set:
        for s in candidates:
            if any(t.lower() in weak_set for t in s["tests_topics"]):
                return s["id"]
    return candidates[0]["id"]


# conversation_signals["goal"] (the Goals chat) -> the ladder stages worth surfacing first. A hint for the
# "matches your goal" marker only; it never locks or reorders anything.
GOAL_STAGES = {
    "build_fundamentals": {"foundations", "core_decision"},
    "explore": {"foundations"},
    "specific_role": {"debugging", "trade_offs", "end_to_end"},
    "any_good_company": {"debugging", "trade_offs", "end_to_end"},
}


def matches_goal(scenario, goal):
    return scenario["ladder_stage"] in GOAL_STAGES.get(goal, ())

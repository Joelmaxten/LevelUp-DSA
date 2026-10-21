"""
Scenario engine: what a student may see, how answers are graded, and the unlock / recommendation rules.
Pure: no Flask, no database, no network. The scenario dicts are the validated file contents
(see scenario_validator.py); the routes in app/routes/scenarios.py wire this to storage.

Grading is all-or-nothing per question (10 points), and the server alone grades: the student-facing view
(public_view) never contains the key, the explanations or the justification.
"""
import random

from app.pipeline.scenario_validator import materialize

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
    if question["type"] == "code":
        # Whitelist: never reference_solution, hidden tests, explanation or key.
        if question.get("pick_reason"):
            view["pick_reason"] = question["pick_reason"]
        view["language"] = question["language"]
        view["starter_code"] = question["starter_code"]
        view["tests"] = [{"stdin": t["stdin"], "expected_stdout": t["expected_stdout"]}
                         for t in question["tests"] if not t["hidden"]]
        return view
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


# ---------------------------------------------------------------- code questions
# A code question is graded from the code runner's results (app/pipeline/code_runner.py), which the route fetches;
# everything here stays pure. What is stored on the attempt for a locked code question is a "record" the SERVER wrote:
# {"source", "language", "passed", "visible": [bool per visible test], "hidden_passed", "hidden_total"}. "language"
# is the one the route validated and ran (records written before languages existed have none and mean Python).
def run_passed(expected, run):
    """One test passes only if the program raised nothing, wrote nothing to stderr and printed the expected output."""
    if not isinstance(run, dict) or run.get("exception") or str(run.get("stderr") or "").strip():
        return False
    out = str(run.get("stdout") or "").replace("\r\n", "\n").strip()
    return out == str(expected).replace("\r\n", "\n").strip()


def code_example_text(question):
    """The only 'correct answer' shown for a code question: the first visible example, never the solution."""
    visible = [t for t in question["tests"] if not t["hidden"]]
    if not visible:
        return ""
    t = visible[0]
    return f"Example: input {t['stdin'].strip()!r} should print {t['expected_stdout'].strip()!r}"


def code_record(question, run_results, source="", language="python"):
    """The per-test outcome of one Check. Missing or malformed results count as failed tests."""
    runs = list(run_results) if isinstance(run_results, (list, tuple)) else []
    flags = [run_passed(t["expected_stdout"], runs[i] if i < len(runs) else None)
             for i, t in enumerate(question["tests"])]
    visible = [ok for ok, t in zip(flags, question["tests"]) if not t["hidden"]]
    hidden = [ok for ok, t in zip(flags, question["tests"]) if t["hidden"]]
    return {"source": source, "language": language, "passed": bool(flags) and all(flags), "visible": visible,
            "hidden_passed": sum(hidden), "hidden_total": len(hidden)}


def _code_correct(question, answer):
    """True only for a record the server wrote with passed set; a client-supplied value never gets here."""
    return (isinstance(answer, dict) and answer.get("passed") is True
            and isinstance(answer.get("visible"), list) and all(v is True for v in answer["visible"])
            and answer.get("hidden_passed") == answer.get("hidden_total"))


def _code_result(question, record):
    ok = _code_correct(question, record)
    rec = record if isinstance(record, dict) else {}
    visible = [bool(v) for v in rec.get("visible", [])] if isinstance(rec.get("visible"), list) else []
    return {
        "question_id": question["id"],
        "correct": ok,
        "awarded": POINTS_PER_QUESTION if ok else 0,
        "correct_answer": code_example_text(question),
        "explanation": question["explanation"],
        "why_others_wrong": {},
        "visible_passed": visible,
        # The student's own locked source (their code, never the solution), so a resumed attempt can show it.
        "source": rec.get("source") if isinstance(rec.get("source"), str) else "",
        "language": rec.get("language") if isinstance(rec.get("language"), str) and rec.get("language") else "python",
        "hidden_passed": rec.get("hidden_passed") if isinstance(rec.get("hidden_passed"), int) else 0,
        "hidden_total": rec.get("hidden_total") if isinstance(rec.get("hidden_total"), int) else 0,
    }


def grade_code_result(question, run_results, source="", language="python"):
    """(result, record): the usual per-question result (all-or-nothing, 10 points) from the runner's results for
    ALL of the question's tests in order, plus the record to store on the attempt."""
    record = code_record(question, run_results, source, language)
    return _code_result(question, record), record


def grade_question(question, answer):
    if question["type"] == "code":
        return _code_result(question, answer)
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


# ---------------------------------------------------------------- code pools: one personalised problem per attempt
# A scenario may carry a "code_pool" of 1-4 coding problems, each with 1-5 data variants (validated files only).
# When an attempt starts, choose_code_pick() picks ONE problem and ONE variant for this student; the pick is stored
# on the attempt (answers["_pick"], a key no question id can take) and effective_scenario() appends that problem,
# with the variant's tests, as the attempt's last question. Attempts without a pick (older ones) see the plain
# scenario. Everything here is deterministic for the same inputs, so a pick can always be explained and reproduced.
PICK_KEY = "_pick"
HARDER_GOALS = {"specific_role", "any_good_company"}
EASIER_GOALS = {"build_fundamentals", "explore"}


def _norm(text):
    return " ".join(str(text).lower().replace("/", " ").split())


def choose_code_pick(scenario, seed, goal=None, missing_skills=(), previous_picks=(), last_try_failed=False):
    """
    {"pool_id", "variant", "reasons"} for this attempt, or None when the scenario has no code pool.

    Rules, in order: a problem the student has not had before on this scenario wins over a repeat; then each problem
    scores +2 if it practises a skill the resume analysis listed as missing, +1 if its difficulty suits the goal
    from the Goals chat (harder for a specific role, easier for fundamentals), and +1 for the easier problem when the
    student's last try at this scenario did not pass. Ties are broken by the attempt's seed. The data variant is
    chosen by the seed too, so two students rarely see the same numbers.
    """
    pool = scenario.get("code_pool") or []
    if not pool:
        return None
    seen = {p for p in previous_picks if isinstance(p, str)}
    candidates = [p for p in pool if p["id"] not in seen] or list(pool)
    missing = {_norm(m) for m in missing_skills or () if isinstance(m, str) and m.strip()}
    lowest = min(p["difficulty"] for p in candidates)
    highest = max(p["difficulty"] for p in candidates)

    def score(problem):
        points, reasons = 0, []
        hit = [sk for sk in problem["skills"] if _norm(sk) in missing]
        if hit:
            points += 2
            reasons.append(f"It practises {hit[0]}, which your resume analysis listed as a skill to learn.")
        if goal in HARDER_GOALS and problem["difficulty"] == highest and highest > lowest:
            points += 1
            reasons.append("You are aiming for a specific role, so you get the harder problem.")
        if goal in EASIER_GOALS and problem["difficulty"] == lowest and highest > lowest:
            points += 1
            reasons.append("You are building fundamentals, so you get the gentler problem.")
        if last_try_failed and problem["difficulty"] == lowest and highest > lowest:
            points += 1
            reasons.append("Your last try at this scenario did not pass, so you get the easier problem first.")
        return points, reasons

    scored = [(problem, *score(problem)) for problem in candidates]
    best = max(points for _, points, _ in scored)
    tied = [(problem, reasons) for problem, points, reasons in scored if points == best]
    rng = random.Random(f"{seed}:code-pick")
    problem, reasons = tied[rng.randrange(len(tied))]
    if len(candidates) < len(pool) and not reasons:
        reasons = ["You have not had this problem on this scenario before."]
    if not reasons:
        reasons = ["Picked at random from this scenario's problems."]
    variant = random.Random(f"{seed}:{problem['id']}:variant").randrange(len(problem["variants"]))
    return {"pool_id": problem["id"], "variant": variant, "reasons": reasons}


def pick_question(scenario, pick):
    """The materialised code question for a stored pick, or None if the pick no longer matches the file."""
    if not isinstance(pick, dict):
        return None
    problem = next((p for p in scenario.get("code_pool") or [] if p["id"] == pick.get("pool_id")), None)
    variant = pick.get("variant")
    if problem is None or isinstance(variant, bool) or not isinstance(variant, int):
        return None
    if not 0 <= variant < len(problem["variants"]):
        return None
    question = materialize(problem, variant)
    reasons = pick.get("reasons")
    if isinstance(reasons, list) and reasons and isinstance(reasons[0], str):
        question["pick_reason"] = reasons[0]
    return question


def effective_scenario(scenario, answers):
    """The scenario as this attempt sees it: its questions plus the picked code problem (if the attempt has one)."""
    pick = (answers or {}).get(PICK_KEY) if isinstance(answers, dict) else None
    question = pick_question(scenario, pick)
    if question is None:
        return scenario
    out = dict(scenario)
    out["questions"] = list(scenario["questions"]) + [question]
    return out


# ---------------------------------------------------------------- progress rules
def compute_progress(scenarios, attempts):
    """
    scenarios: the file's scenario dicts. attempts: submitted attempts only, as dicts with scenario_id, score,
    max_score (unfinished attempts do not count). Returns {scenario_id: {state, best_score, max_score}}.

    Scenario 1 is always open; scenario N+1 opens only once N is PASSED (best score at or above the pass mark);
    the best score is kept. A scenario whose predecessor is not passed is locked even if it was played before (under
    the older "any attempt unlocks" rule); its best score is still reported.
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
    previous_passed = True   # scenario 1 has no predecessor
    for s in ordered:
        b = best.get(s["id"])
        if not previous_passed:
            state = STATE_LOCKED
        elif b is not None:
            state = STATE_PASSED if is_passing(b["score"], b["max_score"]) else STATE_ATTEMPTED
        else:
            state = STATE_OPEN
        progress[s["id"]] = {"state": state, "best_score": b["score"] if b else None,
                             "max_score": b["max_score"] if b else None}
        previous_passed = state == STATE_PASSED
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

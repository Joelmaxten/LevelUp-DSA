"""
Scenario-based practice: a map of scenarios per career path, each a short work situation with questions.

The server grades. Correct answers, explanations and justifications leave the server only for a question
whose answer the student has already locked (POST /scenarios/<id>/answer), or in the submit response. Locked
answers are stored on the attempt and cannot be changed, so seeing an explanation never lets a student
re-answer that question.

Error bodies are {"error": "<fixed_code>"} only - never exception text. Reads CareerProfile (never writes it).
"""
import os
import secrets
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import CareerProfile, ScenarioAttempt, SkillGap
from app.pipeline import code_runner
from app.pipeline import scenario_engine as engine
from app.pipeline import scenario_store as store
from app.security import rate_limit_hit, rate_limited_response

scenarios_bp = Blueprint("scenarios", __name__)

MAX_BODY_BYTES = 32 * 1024
START_LIMIT_PER_HOUR = 30
ANSWER_LIMIT_PER_HOUR = 300
SUBMIT_LIMIT_PER_HOUR = 30
CODE_RUN_LIMIT_PER_HOUR = 60
CODE_CHECK_LIMIT_PER_HOUR = 30
CODE_OUTPUT_CHARS = 2048     # stdout / stderr of one run shown to the browser
HOUR = 3600
# HTTP status per code_runner error code (the body is only {"error": code}).
RUNNER_STATUS = {"timeout": 504, "runtime_error": 502, "runner_unavailable": 503, "code_too_large": 400}


def _error(code, status):
    return jsonify({"error": code}), status


def _limited(bucket, limit):
    allowed, retry_after = rate_limit_hit(bucket, current_user.id, limit, HOUR)
    return None if allowed else rate_limited_response(retry_after)


def _json_body():
    """(dict, None) or (None, error response). Fixed codes; size-capped before parsing."""
    if (request.content_length or 0) > MAX_BODY_BYTES or len(request.get_data(cache=True)) > MAX_BODY_BYTES:
        return None, _error("body_too_large", 400)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, _error("invalid_body", 400)
    return body, None


def _profile():
    return (CareerProfile.query.filter_by(user_id=current_user.id)
            .order_by(CareerProfile.id.desc()).first())


def _submitted_attempts(scenario_ids):
    rows = (ScenarioAttempt.query
            .filter(ScenarioAttempt.user_id == current_user.id,
                    ScenarioAttempt.scenario_id.in_(list(scenario_ids)),
                    ScenarioAttempt.submitted_at.isnot(None))
            .all())
    return [{"scenario_id": r.scenario_id, "score": r.score, "max_score": r.max_score} for r in rows]


def _map_scenarios(path_data, goal):
    """Per-scenario map entries plus the weak topics. No question text."""
    scenarios = path_data["scenarios"]
    progress = engine.compute_progress(scenarios, _submitted_attempts(s["id"] for s in scenarios))
    weak = engine.weak_topics(scenarios, progress)
    recommended = engine.recommended_next(scenarios, progress, weak)
    entries = []
    for s in sorted(scenarios, key=lambda s: s["order"]):
        p = progress[s["id"]]
        entries.append({
            "id": s["id"], "order": s["order"], "title": s["title"], "ladder_stage": s["ladder_stage"],
            "difficulty": s["difficulty"], "minutes": s["estimated_minutes"], "map_node": s["map_node"],
            "state": p["state"], "best_score": p["best_score"], "max_score": p["max_score"],
            "recommended": s["id"] == recommended,
            "matches_goal": bool(goal) and engine.matches_goal(s, goal),
        })
    return entries, weak


def _new_pick(scenario, seed):
    """The personalised code problem for a new attempt (scenario_engine.choose_code_pick), or None (no pool)."""
    if not scenario.get("code_pool"):
        return None
    profile = _profile()
    goal = (profile.conversation_signals or {}).get("goal") if profile else None
    gap = SkillGap.query.filter_by(user_id=current_user.id).order_by(SkillGap.id.desc()).first()
    missing = list(gap.missing_skills or []) if gap is not None else []
    earlier = (ScenarioAttempt.query
               .filter(ScenarioAttempt.user_id == current_user.id, ScenarioAttempt.scenario_id == scenario["id"],
                       ScenarioAttempt.submitted_at.isnot(None))
               .order_by(ScenarioAttempt.id).all())
    previous = [((a.answers or {}).get(engine.PICK_KEY) or {}).get("pool_id") for a in earlier]
    last_failed = bool(earlier) and earlier[-1].passed is False
    return engine.choose_code_pick(scenario, seed, goal=goal, missing_skills=missing,
                                   previous_picks=[p for p in previous if p], last_try_failed=last_failed)


def _scene_url(scene_id):
    """URL of static/scenes/<scene_id>.svg if that file exists, else None (the page draws a gradient instead)."""
    if os.path.isfile(os.path.join(current_app.static_folder, "scenes", f"{scene_id}.svg")):
        return f"/static/scenes/{scene_id}.svg"
    return None


def _map_payload(path_data):
    profile = _profile()
    goal = (profile.conversation_signals or {}).get("goal") if profile else None
    entries, weak = _map_scenarios(path_data, goal)
    return {
        "path": path_data["path"], "slug": store.slugify(path_data["path"]),
        "scene_id": path_data["map"]["scene_id"], "scene_url": _scene_url(path_data["map"]["scene_id"]), "theme": path_data["map"]["theme"],
        "edges": path_data["map"]["edges"], "scenarios": entries, "weak_topics": weak,
    }


@scenarios_bp.route("/scenarios/paths", methods=["GET"])
@login_required
def list_paths():
    profile = _profile()
    quiz_path = None
    if profile and profile.career_ranking:
        quiz_path = profile.career_ranking[0].get("career_path")
    available = store.load_all()
    return jsonify({
        "paths": [{"name": name, "slug": store.slugify(name), "scenario_count": len(d["scenarios"])}
                  for name, d in available.items()],
        # quiz_path is the student's top quiz match whether or not it has scenarios (null = no quiz result), so the
        # page can say "coming soon" instead of quietly showing another path.
        "quiz_path": quiz_path if isinstance(quiz_path, str) else None,
        "quiz_path_available": quiz_path in available,
    }), 200


@scenarios_bp.route("/scenarios/<path_slug>", methods=["GET"])
@login_required
def path_map(path_slug):
    path_data = store.get_by_slug(path_slug)
    if path_data is None:
        return _error("path_not_found", 404)
    return jsonify(_map_payload(path_data)), 200


@scenarios_bp.route("/scenarios/<scenario_id>/start", methods=["POST"])
@login_required
def start(scenario_id):
    limited = _limited("scenario_start", START_LIMIT_PER_HOUR)
    if limited:
        return limited
    path_data, scenario = store.find_scenario(scenario_id)
    if scenario is None:
        return _error("scenario_not_found", 404)

    scenarios = path_data["scenarios"]
    progress = engine.compute_progress(scenarios, _submitted_attempts(s["id"] for s in scenarios))
    if progress[scenario_id]["state"] == engine.STATE_LOCKED:
        return _error("scenario_locked", 403)

    attempt = (ScenarioAttempt.query
               .filter_by(user_id=current_user.id, scenario_id=scenario_id, submitted_at=None)
               .order_by(ScenarioAttempt.id.desc()).first())
    if attempt is None:
        seed = secrets.randbelow(2 ** 31 - 1)
        pick = _new_pick(scenario, seed)
        attempt = ScenarioAttempt(user_id=current_user.id, path=path_data["path"], scenario_id=scenario_id,
                                  answers={engine.PICK_KEY: pick} if pick else {}, shuffle_seed=seed)
        db.session.add(attempt)
        db.session.commit()

    effective = engine.effective_scenario(scenario, attempt.answers)
    questions = {q["id"]: q for q in effective["questions"]}
    locked = {qid: engine.grade_question(questions[qid], ans)
              for qid, ans in (attempt.answers or {}).items() if qid in questions}
    return jsonify({
        "attempt_id": attempt.id,
        "scenario": engine.public_view(effective, attempt.shuffle_seed),
        "locked": locked,
    }), 200


def _owned_open_attempt(scenario_id, body, lock=False):
    """(attempt, None) or (None, error response): the body's attempt_id must be this user's, for this scenario."""
    attempt_id = body.get("attempt_id")
    if isinstance(attempt_id, bool) or not isinstance(attempt_id, int):
        return None, _error("invalid_attempt_id", 400)
    query = ScenarioAttempt.query.filter_by(id=attempt_id, user_id=current_user.id, scenario_id=scenario_id)
    if lock:
        query = query.with_for_update()
    attempt = query.first()
    if attempt is None:
        db.session.rollback()
        return None, _error("attempt_not_found", 404)
    if attempt.submitted_at is not None:
        db.session.rollback()
        return None, _error("already_submitted", 409)
    return attempt, None


@scenarios_bp.route("/scenarios/<scenario_id>/answer", methods=["POST"])
@login_required
def lock_answer(scenario_id):
    """Locks one question's answer and returns that question's result (with its explanation)."""
    limited = _limited("scenario_answer", ANSWER_LIMIT_PER_HOUR)
    if limited:
        return limited
    _, scenario = store.find_scenario(scenario_id)
    if scenario is None:
        return _error("scenario_not_found", 404)
    body, error = _json_body()
    if error:
        return error
    attempt, error = _owned_open_attempt(scenario_id, body, lock=True)
    if error:
        return error
    scenario = engine.effective_scenario(scenario, attempt.answers)
    question = next((q for q in scenario["questions"] if q["id"] == body.get("question_id")), None)
    if question is None:
        db.session.rollback()
        return _error("invalid_question_id", 400)
    if question["type"] == "code":
        return _check_code(scenario_id, attempt, question, body)
    answer = body.get("answer")
    if not isinstance(answer, (list, dict, str)):
        db.session.rollback()
        return _error("invalid_answer", 400)

    locked = dict(attempt.answers or {})
    if question["id"] not in locked:         # first answer wins; a repeat call just returns the stored result
        locked[question["id"]] = answer
        attempt.answers = locked
        db.session.commit()
    else:
        db.session.rollback()
    return jsonify({"result": engine.grade_question(question, locked[question["id"]])}), 200


def _runner_error(error):
    return _error(error.code, RUNNER_STATUS.get(error.code, 503))


def _check_code(scenario_id, attempt, question, body):
    """
    Locks one Check of a code question against ALL its tests. The student's source is run in one batch; hidden
    tests are only ever reported as counts. A runner failure locks nothing and counts as nothing: the student
    just tries again. The caller holds the attempt row lock; it is released before the (slow) runner call.
    """
    source = body.get("answer")
    if not isinstance(source, str) or not source.strip():
        db.session.rollback()
        return _error("invalid_answer", 400)
    stored = (attempt.answers or {}).get(question["id"])
    if stored is not None:                     # first Check wins; a repeat just returns the stored result
        db.session.rollback()
        return jsonify({"result": engine.grade_question(question, stored)}), 200
    db.session.rollback()                      # no database lock held while the provider runs
    limited = _limited("scenario_code_check", CODE_CHECK_LIMIT_PER_HOUR)
    if limited:
        return limited
    try:
        runs = code_runner.run_batch(source, [t["stdin"] for t in question["tests"]])
    except code_runner.CodeRunnerError as error:
        return _runner_error(error)
    except Exception:
        return _error("runner_unavailable", 503)
    result, record = engine.grade_code_result(question, runs, source)

    attempt, error = _owned_open_attempt(scenario_id, body, lock=True)
    if error:
        return error
    locked = dict(attempt.answers or {})
    if question["id"] not in locked:
        locked[question["id"]] = record
        attempt.answers = locked
        db.session.commit()
    else:                                      # another Check landed first
        db.session.rollback()
        result = engine.grade_question(question, locked[question["id"]])
    return jsonify({"result": result}), 200


def _clip(value):
    value = value if isinstance(value, str) else ""
    return value if len(value) <= CODE_OUTPUT_CHARS else value[:CODE_OUTPUT_CHARS] + " [output cut]"


@scenarios_bp.route("/scenarios/<scenario_id>/code/run", methods=["POST"])
@login_required
def code_run(scenario_id):
    """Ungraded run of the student's source against the VISIBLE tests only. Nothing is stored or locked."""
    limited = _limited("scenario_code_run", CODE_RUN_LIMIT_PER_HOUR)
    if limited:
        return limited
    _, scenario = store.find_scenario(scenario_id)
    if scenario is None:
        return _error("scenario_not_found", 404)
    body, error = _json_body()
    if error:
        return error
    attempt, error = _owned_open_attempt(scenario_id, body)
    if error:
        return error
    scenario = engine.effective_scenario(scenario, attempt.answers)
    db.session.rollback()
    question = next((q for q in scenario["questions"] if q["id"] == body.get("question_id")), None)
    if question is None or question["type"] != "code":
        return _error("invalid_question_id", 400)
    source = body.get("source")
    if not isinstance(source, str) or not source.strip():
        return _error("invalid_source", 400)
    visible = [t for t in question["tests"] if not t["hidden"]]
    try:
        runs = code_runner.run_batch(source, [t["stdin"] for t in visible])
    except code_runner.CodeRunnerError as error:
        return _runner_error(error)
    except Exception:
        return _error("runner_unavailable", 503)
    results = [{"index": i, "passed": engine.run_passed(t["expected_stdout"], run),
                "stdout": _clip(run["stdout"]), "stderr": _clip(run["stderr"]), "exception": run["exception"]}
               for i, (t, run) in enumerate(zip(visible, runs))]
    return jsonify({"results": results}), 200


@scenarios_bp.route("/scenarios/<scenario_id>/submit", methods=["POST"])
@login_required
def submit(scenario_id):
    limited = _limited("scenario_submit", SUBMIT_LIMIT_PER_HOUR)
    if limited:
        return limited
    path_data, scenario = store.find_scenario(scenario_id)
    if scenario is None:
        return _error("scenario_not_found", 404)
    body, error = _json_body()
    if error:
        return error
    submitted = body.get("answers")
    if not isinstance(submitted, dict) or len(submitted) > 50:
        return _error("invalid_answers", 400)
    attempt, error = _owned_open_attempt(scenario_id, body, lock=True)
    if error:
        return error

    scenario = engine.effective_scenario(scenario, attempt.answers)
    answers = {k: v for k, v in submitted.items() if not str(k).startswith("_")}   # the pick is server-side only
    for q in scenario["questions"]:           # a code answer is only ever the server's own Check record
        if q["type"] == "code":
            answers.pop(q["id"], None)
    answers.update(attempt.answers or {})     # answers locked earlier cannot be changed now
    graded = engine.grade(scenario, answers)
    kept = {q["id"]: answers[q["id"]] for q in scenario["questions"] if q["id"] in answers}
    if engine.PICK_KEY in (attempt.answers or {}):
        kept[engine.PICK_KEY] = attempt.answers[engine.PICK_KEY]   # remembered so a retry gets a different problem
    attempt.answers = kept
    attempt.score, attempt.max_score, attempt.passed = graded["score"], graded["max_score"], graded["passed"]
    attempt.submitted_at = datetime.utcnow()
    db.session.commit()

    profile = _profile()
    goal = (profile.conversation_signals or {}).get("goal") if profile else None
    entries, weak = _map_scenarios(path_data, goal)
    return jsonify({
        "attempt_id": attempt.id,
        "results": graded["results"], "score": graded["score"], "max_score": graded["max_score"],
        "percent": graded["percent"], "passed": graded["passed"],
        "weak_topics": weak, "scenarios": entries,
    }), 200

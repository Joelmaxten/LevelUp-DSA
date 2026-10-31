"""
Verified progression routes (see app/pipeline/step_checks.py for how questions are made and checked).

GET  /roadmap/<id>/steps/state                     every step's status: done / open / locked, verified, cooldown, review
POST /roadmap/<id>/steps/<idx>/check/start         {"mode": "check" | "test_out"} -> the questions (never the answers)
POST /roadmap/<id>/steps/<idx>/check/submit        {"attempt_id", "answers": {item id: option id}} -> graded on the server
GET  /roadmap/<id>/steps/<idx>/review              the step's source passages (the remedial review)
POST /roadmap/<id>/steps/<idx>/review              mark the review done, which allows the next attempt

A passed check creates the step's RoadmapProgress row, so progress counts, the readiness score, XP and the completion
banner keep working unchanged.
"""
import hashlib
import random
import threading
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import GeneratedRoadmap, RoadmapProgress, StepCheckAttempt, StepCheckItem, StepReview
from app.pipeline import step_checks as sc
from app.routes._util import iso_utc
from app.security import rate_limit_hit, rate_limited_response

step_checks_bp = Blueprint("step_checks", __name__)

OPEN_ATTEMPT_MINUTES = 30      # an unsubmitted attempt younger than this comes back unchanged on "start"
MIN_ITEMS = 2                  # fewer questions than this and the step cannot be checked (it can be ticked by hand)
_build_lock = threading.Lock()


def _cfg():
    c = current_app.config
    return {"cooldown_s": c["STEP_CHECK_COOLDOWN_S"], "review_after": c["STEP_CHECK_REVIEW_AFTER"]}


def _chunks():
    from app.routes.roadmap import _get_index
    return _get_index()[1]


def roadmap_steps(roadmap):
    """{index: step} plus roadmap order, and the passages of every step (for wrong options)."""
    flat = sc.flat_steps(roadmap.steps)
    lookup = sc.chunk_lookup(_chunks(), roadmap.career_path)
    sources = {idx: sc.step_sources(step, lookup) for idx, step in flat}
    return flat, sources


def _built_items(roadmap, step, sources, all_sources):
    return sc.build_items(sources, all_sources, sc.step_key(roadmap.career_path, step))


# (step_key, roadmap's source fingerprint) -> has a check. Building the questions for every step on every request took
# about 3 s for a 36-step roadmap; the answer never changes for the same step and the same pool of wrong options.
_checkable_cache = {}
_CHECKABLE_CACHE_MAX = 20000


def checkable_indexes(roadmap, flat, sources):
    all_sources = [s for v in sources.values() for s in v]
    pool = hashlib.sha256("|".join(s["node_id"] for s in all_sources).encode("utf-8")).hexdigest()
    out = set()
    for idx, step in flat:
        key = (sc.step_key(roadmap.career_path, step), pool)
        if key not in _checkable_cache:
            if len(_checkable_cache) >= _CHECKABLE_CACHE_MAX:
                _checkable_cache.clear()
            _checkable_cache[key] = len(_built_items(roadmap, step, sources[idx], all_sources)) >= MIN_ITEMS
        if _checkable_cache[key]:
            out.add(idx)
    return out


def ensure_items(roadmap, step, sources, all_sources):
    """The stored questions for this step, made (and stored) on first use. Shared by every student with the same step."""
    key = sc.step_key(roadmap.career_path, step)
    rows = StepCheckItem.query.filter_by(step_key=key).order_by(StepCheckItem.id).all()
    if rows:
        return rows
    with _build_lock:
        rows = StepCheckItem.query.filter_by(step_key=key).order_by(StepCheckItem.id).all()
        if rows:
            return rows
        items = _built_items(roadmap, step, sources, all_sources)
        if current_app.config.get("STEP_CHECK_LLM") and sources:
            llm_items, rejected = sc.generate_llm_items(step, sources)
            current_app.logger.info("step_check_llm step=%s kept=%d rejected=%s", key[:12], len(llm_items), rejected)
            items = llm_items + items
        for it in items:
            db.session.add(StepCheckItem(step_key=key, **it))
        db.session.commit()
        return StepCheckItem.query.filter_by(step_key=key).order_by(StepCheckItem.id).all()


def _history(user_id, roadmap_id):
    attempts, reviews = {}, {}
    for a in StepCheckAttempt.query.filter(StepCheckAttempt.user_id == user_id, StepCheckAttempt.roadmap_id == roadmap_id,
                                           StepCheckAttempt.submitted_at.isnot(None)).order_by(StepCheckAttempt.submitted_at):
        attempts.setdefault(a.step_index, []).append({"passed": a.passed, "mode": a.mode, "submitted_at": a.submitted_at})
    for r in StepReview.query.filter_by(user_id=user_id, roadmap_id=roadmap_id).all():
        reviews.setdefault(r.step_index, []).append({"required_at": r.required_at, "reviewed_at": r.reviewed_at})
    return attempts, reviews


def states_for(roadmap, user_id, flat=None, sources=None):
    if flat is None:
        flat, sources = roadmap_steps(roadmap)
    completed = {r.step_index for r in RoadmapProgress.query.filter_by(user_id=user_id, roadmap_id=roadmap.id).all()}
    attempts, reviews = _history(user_id, roadmap.id)
    return sc.step_states([idx for idx, _ in flat], completed, checkable_indexes(roadmap, flat, sources),
                          attempts, reviews, datetime.utcnow(), _cfg())


def _public_state(state):
    out = dict(state)
    out["cooldown_until"] = iso_utc(state["cooldown_until"]) if state["cooldown_until"] else None
    return out


def _own_roadmap(roadmap_id):
    return GeneratedRoadmap.query.filter_by(id=roadmap_id, user_id=current_user.id).first()


def _progress_payload(roadmap):
    from app.routes.roadmap import completed_on, roadmap_progress
    done, count, total = roadmap_progress(current_user.id, roadmap.id, roadmap.steps)
    return {"completed_steps": done, "completed_count": count, "total_steps": total,
            "completed_on": completed_on(current_user.id, roadmap.id, roadmap.steps)}


@step_checks_bp.route("/roadmap/<int:roadmap_id>/steps/state", methods=["GET"])
@login_required
def steps_state(roadmap_id):
    roadmap = _own_roadmap(roadmap_id)
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404
    enabled = bool(current_app.config.get("VERIFIED_PROGRESS"))
    states = states_for(roadmap, current_user.id) if enabled else {}
    resp = jsonify({"verified_progress": enabled, "steps": {str(k): _public_state(v) for k, v in states.items()}})
    resp.headers["Cache-Control"] = "no-store"   # changes after every attempt; a cached copy showed a passed step as open
    return resp, 200


def _step_or_error(roadmap, step_index):
    flat, sources = roadmap_steps(roadmap)
    steps = dict(flat)
    if step_index not in steps:
        return None, (jsonify({"error": "That step doesn't exist on this roadmap."}), 404)
    return (flat, sources, steps[step_index]), None


@step_checks_bp.route("/roadmap/<int:roadmap_id>/steps/<int:step_index>/check/start", methods=["POST"])
@login_required
def start_check(roadmap_id, step_index):
    if not current_app.config.get("VERIFIED_PROGRESS"):
        return jsonify({"error": "verified_progress_off"}), 404
    roadmap = _own_roadmap(roadmap_id)
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404
    data = request.get_json(silent=True)
    mode = data.get("mode", "check") if isinstance(data, dict) else "check"
    if mode not in ("check", "test_out"):
        return jsonify({"error": "mode must be check or test_out."}), 400
    ok, retry = rate_limit_hit("step_check_start", current_user.id, 60, 3600)
    if not ok:
        return rate_limited_response(retry)

    found, err = _step_or_error(roadmap, step_index)
    if err:
        return err
    flat, sources, step = found
    state = states_for(roadmap, current_user.id, flat, sources)[step_index]
    if state["status"] == "done":
        return jsonify({"error": "already_done"}), 409
    if not state["checkable"]:
        return jsonify({"error": "no_check", "message": "This step has no check; mark it done yourself."}), 409
    if mode == "check" and state["status"] == "locked":
        return jsonify({"error": "locked", "message": "Finish the step before this one, or test out of this step."}), 403
    if mode == "test_out" and state["status"] != "locked":
        return jsonify({"error": "not_locked", "message": "This step is open: take its normal check."}), 400
    if state["review_required"]:
        return jsonify({"error": "review_required", "message": "Review this step's material before trying again."}), 409
    if state["cooldown_until"]:
        wait = max(1, int((state["cooldown_until"] - datetime.utcnow()).total_seconds()) + 1)
        resp = jsonify({"error": "cooldown", "retry_after_seconds": wait,
                        "message": "Take a short break and re-read the step before trying again."})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(wait)
        return resp

    all_sources = [s for v in sources.values() for s in v]
    items = ensure_items(roadmap, step, sources[step_index], all_sources)
    by_id = {it.id: it for it in items}
    cfg = current_app.config
    n, pass_mark = ((cfg["TEST_OUT_QUESTIONS"], cfg["TEST_OUT_PASS"]) if mode == "test_out"
                    else (cfg["STEP_CHECK_QUESTIONS"], cfg["STEP_CHECK_PASS"]))
    n = min(n, len(items))
    pass_mark = min(pass_mark, n)

    cutoff = datetime.utcnow() - timedelta(minutes=OPEN_ATTEMPT_MINUTES)
    attempt = StepCheckAttempt.query.filter(
        StepCheckAttempt.user_id == current_user.id, StepCheckAttempt.roadmap_id == roadmap.id,
        StepCheckAttempt.step_index == step_index, StepCheckAttempt.mode == mode,
        StepCheckAttempt.submitted_at.is_(None), StepCheckAttempt.started_at >= cutoff,
    ).order_by(StepCheckAttempt.id.desc()).first()
    if attempt is None or any(q["item"] not in by_id for q in attempt.questions):
        seen = set()
        for old in StepCheckAttempt.query.filter_by(user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index):
            seen.update(q["item"] for q in old.questions)
        rng = random.Random()
        chosen = sc.choose_questions([{"id": it.id, "kind": it.kind, "source_node": it.source_node} for it in items],
                                     n, seen, rng)
        questions = []
        for item_id in chosen:
            order = [o["id"] for o in by_id[item_id].options]
            rng.shuffle(order)
            questions.append({"item": item_id, "order": order})
        attempt = StepCheckAttempt(user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index, mode=mode,
                                   questions=questions, total=len(questions), pass_mark=pass_mark)
        db.session.add(attempt)
        db.session.commit()

    public = []
    for q in attempt.questions:
        item = by_id[q["item"]]
        text = {o["id"]: o["text"] for o in item.options}
        public.append({"id": item.id, "prompt": item.prompt, "options": [{"id": oid, "text": text[oid]} for oid in q["order"]]})
    return jsonify({"attempt_id": attempt.id, "mode": attempt.mode, "step_index": step_index, "questions": public,
                    "total": attempt.total, "pass_mark": attempt.pass_mark}), 200


@step_checks_bp.route("/roadmap/<int:roadmap_id>/steps/<int:step_index>/check/submit", methods=["POST"])
@login_required
def submit_check(roadmap_id, step_index):
    roadmap = _own_roadmap(roadmap_id)
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("attempt_id"), int) or isinstance(data.get("attempt_id"), bool) \
            or not isinstance(data.get("answers"), dict):
        return jsonify({"error": "attempt_id and answers are required."}), 400
    attempt = StepCheckAttempt.query.filter_by(id=data["attempt_id"], user_id=current_user.id, roadmap_id=roadmap.id,
                                               step_index=step_index).first()
    if attempt is None:
        return jsonify({"error": "Attempt not found."}), 404
    if attempt.submitted_at is not None:
        return jsonify({"error": "already_submitted"}), 409
    answers = {str(k): v for k, v in data["answers"].items() if isinstance(v, str)}
    if len(answers) < attempt.total:
        return jsonify({"error": "unanswered", "message": "Answer every question first."}), 400

    items = {it.id: it for it in StepCheckItem.query.filter(StepCheckItem.id.in_([q["item"] for q in attempt.questions]))}
    as_dicts = {i: {"correct": it.correct} for i, it in items.items()}
    score, results = sc.grade(attempt.questions, answers, as_dicts)
    attempt.answers, attempt.score = answers, score
    attempt.passed = score >= attempt.pass_mark
    attempt.submitted_at = datetime.utcnow()
    db.session.commit()

    if attempt.passed:
        if not RoadmapProgress.query.filter_by(user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index).first():
            db.session.add(RoadmapProgress(user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    state = states_for(roadmap, current_user.id)[step_index]
    if state["review_required"] and not StepReview.query.filter_by(
            user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index, reviewed_at=None).first():
        db.session.add(StepReview(user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index))
        db.session.commit()

    # On a pass the student sees why each answer is right (the source sentence). On a fail only which ones were wrong
    # and which passage to re-read: the next attempt prefers other questions, and showing answers would just be memorised.
    feedback = []
    for r in results:
        item = items.get(r["item"])
        entry = {"id": r["item"], "correct": r["correct"], "source_title": item.source_title if item else None}
        if attempt.passed and item:
            entry["evidence"] = item.evidence
            entry["answer"] = next((o["text"] for o in item.options if o["id"] == item.correct), None)
        feedback.append(entry)
    return jsonify({"passed": attempt.passed, "score": score, "total": attempt.total, "pass_mark": attempt.pass_mark,
                    "mode": attempt.mode, "results": feedback, "state": _public_state(state),
                    **_progress_payload(roadmap)}), 200


@step_checks_bp.route("/roadmap/<int:roadmap_id>/steps/<int:step_index>/review", methods=["GET"])
@login_required
def get_review(roadmap_id, step_index):
    roadmap = _own_roadmap(roadmap_id)
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404
    found, err = _step_or_error(roadmap, step_index)
    if err:
        return err
    _, sources, step = found
    passages = [{"title": s["title"], "text": s["text"],
                 "resources": [{"title": r.get("title"), "url": r.get("url")} for r in s["resources"][:3]
                               if isinstance(r, dict) and str(r.get("url", "")).startswith("https://")]}
                for s in sources[step_index]]
    return jsonify({"step_index": step_index, "title": step.get("title"), "passages": passages}), 200


@step_checks_bp.route("/roadmap/<int:roadmap_id>/steps/<int:step_index>/review", methods=["POST"])
@login_required
def done_review(roadmap_id, step_index):
    roadmap = _own_roadmap(roadmap_id)
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404
    now = datetime.utcnow()
    open_reviews = StepReview.query.filter_by(user_id=current_user.id, roadmap_id=roadmap.id, step_index=step_index,
                                              reviewed_at=None).all()
    if not open_reviews:
        return jsonify({"error": "no_review_required"}), 409
    for r in open_reviews:
        r.reviewed_at = now
    db.session.commit()
    return jsonify({"state": _public_state(states_for(roadmap, current_user.id)[step_index])}), 200

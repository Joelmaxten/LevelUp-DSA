import math
import threading
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import CareerProfile, GeneratedRoadmap, RoadmapProgress
from app.pipeline.rag import load_index
from app.pipeline.roadmap_generator import generate_roadmap
from app.pipeline.youtube_resources import fetch_resources_for_roadmap
from app.routes._util import iso_utc, resolve_target_career_path

MAX_ROADMAP_LIST = 20

roadmap_bp = Blueprint("roadmap", __name__)

FAISS_INDEX_PATH = "data/processed/faiss_index"  # matches config.py's FAISS_INDEX_PATH

# Loaded once per process, not per-request - the index is large and rebuilding
# it on every call would be wasteful. Mirrors embedder.py's module-level model cache.
_index_cache = None
_index_lock = threading.Lock()
_chunks_cache = None


def _get_index():
    global _index_cache, _chunks_cache
    if _index_cache is None:
        with _index_lock:   # the startup warm-up thread and a first request can arrive together
            if _index_cache is None:
                _index_cache, _chunks_cache = load_index(FAISS_INDEX_PATH)
    return _index_cache, _chunks_cache


def step_indexes(steps):
    """
    The ordered list of valid step indexes for a roadmap's "steps" value -
    phased shape: each step's global_step_index; old flat shape: each
    step's step_number. A step missing that key falls back to its 1-based
    position across the WHOLE roadmap (not per-phase), so every step still
    gets a usable index rather than None ending up in the list.
    """
    if isinstance(steps, list):
        flat_steps = steps
        key = "step_number"
    else:
        flat_steps = [step for phase in steps["phases"] for step in phase["steps"]]
        key = "global_step_index"

    return [
        step[key] if step.get(key) is not None else i + 1
        for i, step in enumerate(flat_steps)
    ]


def _progress_counts(valid_indexes, ticked_indexes):
    """
    (completed_steps sorted list, completed_count, total_steps) from a
    pre-computed set of ticked step indexes (already scoped to one
    roadmap) and that roadmap's current valid indexes - the pure part of
    roadmap_progress(), factored out so a caller that already fetched
    RoadmapProgress rows itself (e.g. roadmaps_for_user()'s single grouped
    query across several roadmaps) can reuse the counting logic without
    triggering roadmap_progress()'s own per-roadmap query.
    """
    valid_set = set(valid_indexes)
    completed = sorted(ticked_indexes & valid_set)
    return completed, len(completed), len(valid_indexes)


def roadmap_progress(user_id, roadmap_id, steps):
    """
    (completed_steps sorted list, completed_count, total_steps) for one
    roadmap - queries RoadmapProgress itself (one query). Shared by
    /roadmap/latest, /roadmap/<id>, /roadmap/generate, the progress POST
    endpoint below, and the dashboard's compact progress summary
    (routes/dashboard.py). roadmaps_for_user() below computes the same
    thing for several roadmaps from one grouped query instead of calling
    this once per roadmap - see _progress_counts().

    completed_steps only ever includes indexes that are still valid for
    this roadmap's CURRENT steps value (see step_indexes) - a step_index a
    student ticked before is silently excluded from the count if it no
    longer corresponds to a real step, rather than inflating completed_count
    past total_steps.
    """
    rows = RoadmapProgress.query.filter_by(user_id=user_id, roadmap_id=roadmap_id).all()
    return _progress_counts(step_indexes(steps), {r.step_index for r in rows})


def _roadmap_dict(roadmap):
    """The full single-roadmap response shape - shared by /roadmap/latest
    and /roadmap/<id>, so the two can never drift apart."""
    completed_steps, completed_count, total_steps = roadmap_progress(roadmap.user_id, roadmap.id, roadmap.steps)
    return {
        "roadmap_id": roadmap.id,
        "career_path": roadmap.career_path,
        "steps": roadmap.steps,
        "created_at": iso_utc(roadmap.created_at),
        "completed_steps": completed_steps,
        "completed_count": completed_count,
        "total_steps": total_steps,
    }


def latest_roadmap(user_id):
    """
    The user's most recently generated roadmap as a plain dict, or None. Older
    rows are kept (regenerating never overwrites), this just picks the newest.
    "steps" carries each step's "resource" (YouTube video) if it was attached.
    """
    roadmap = (
        GeneratedRoadmap.query
        .filter_by(user_id=user_id)
        .order_by(GeneratedRoadmap.id.desc())
        .first()
    )
    if roadmap is None:
        return None
    return _roadmap_dict(roadmap)


def roadmaps_for_user(user_id, limit):
    """
    The user's roadmaps, newest first, capped at `limit`:
    [{roadmap_id, career_path, created_at, completed_count, total_steps}].
    Progress for every returned roadmap comes from ONE grouped
    RoadmapProgress query (not one query per roadmap) - rows are split by
    roadmap_id in Python, then _progress_counts() (roadmap_progress()'s
    own pure counting core) does the rest. Shared by /roadmap/list (its
    own cap) and the dashboard's "roadmaps" summary (a smaller cap).
    """
    roadmaps = (
        GeneratedRoadmap.query
        .filter_by(user_id=user_id)
        .order_by(GeneratedRoadmap.id.desc())
        .limit(limit)
        .all()
    )
    roadmap_ids = [r.id for r in roadmaps]

    ticked_by_roadmap = defaultdict(set)
    if roadmap_ids:
        rows = (
            RoadmapProgress.query
            .filter(RoadmapProgress.user_id == user_id, RoadmapProgress.roadmap_id.in_(roadmap_ids))
            .all()
        )
        for row in rows:
            ticked_by_roadmap[row.roadmap_id].add(row.step_index)

    result = []
    for r in roadmaps:
        _, completed_count, total_steps = _progress_counts(step_indexes(r.steps), ticked_by_roadmap[r.id])
        result.append({
            "roadmap_id": r.id,
            "career_path": r.career_path,
            "created_at": iso_utc(r.created_at),
            "completed_count": completed_count,
            "total_steps": total_steps,
        })
    return result


@roadmap_bp.route("/roadmap/latest", methods=["GET"])
@login_required
def get_latest():
    roadmap = latest_roadmap(current_user.id)
    if roadmap is None:
        return jsonify({"error": "No roadmap generated yet."}), 404
    return jsonify(roadmap), 200


@roadmap_bp.route("/roadmap/list", methods=["GET"])
@login_required
def list_roadmaps():
    return jsonify(roadmaps_for_user(current_user.id, limit=MAX_ROADMAP_LIST)), 200


@roadmap_bp.route("/roadmap/<int:roadmap_id>", methods=["GET"])
@login_required
def get_roadmap(roadmap_id):
    roadmap = GeneratedRoadmap.query.filter_by(id=roadmap_id, user_id=current_user.id).first()
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404
    return jsonify(_roadmap_dict(roadmap)), 200


@roadmap_bp.route("/roadmap/generate", methods=["POST"])
@login_required
def generate():
    # Rolling-24h per-user cap, counted from the roadmaps already saved (no extra
    # table). Checked first so a capped user never triggers a Gemini call.
    limit = current_app.config["ROADMAP_DAILY_LIMIT"]
    window_start = datetime.utcnow() - timedelta(hours=24)
    recent = (
        GeneratedRoadmap.query
        .filter(GeneratedRoadmap.user_id == current_user.id, GeneratedRoadmap.created_at > window_start)
        .order_by(GeneratedRoadmap.created_at.asc())
        .all()
    )
    if len(recent) >= limit:
        # The slot that frees up first is the one that falls out of the window next.
        frees_at = recent[len(recent) - limit].created_at + timedelta(hours=24)
        minutes = max(1, math.ceil((frees_at - datetime.utcnow()).total_seconds() / 60))
        return jsonify({"error": "daily_limit", "limit": limit, "resets_in_minutes": minutes}), 429

    profile = (
        CareerProfile.query
        .filter_by(user_id=current_user.id)
        .order_by(CareerProfile.id.desc())
        .first()
    )

    top_career_path, error = resolve_target_career_path(profile, allow_override=True)
    if error:
        return error

    # A user who skipped the quiz has no conversation answers; the prompt
    # already falls back to "not specified" for each missing signal.
    conversation_signals = profile.conversation_signals if profile is not None else {}

    try:
        index, chunks = _get_index()
    except FileNotFoundError:
        return jsonify({
            "error": "Knowledge base index not found on this server. "
                     "The FAISS index must be built before roadmap generation is available."
        }), 503

    try:
        steps, retrieved_chunks_audit = generate_roadmap(
            top_career_path, conversation_signals, index, chunks
        )
    except ValueError:
        current_app.logger.exception("%s failed", request.path)
        return jsonify({"error": "Couldn't generate your roadmap right now. Please try again."}), 502

    roadmap = GeneratedRoadmap(
        user_id=current_user.id,
        career_path=top_career_path,
        steps=steps,
        retrieved_chunks=retrieved_chunks_audit,
    )

    try:
        db.session.add(roadmap)
        db.session.commit()
    except Exception as e:
        current_app.logger.exception("%s failed", request.path)
        db.session.rollback()
        return jsonify({
            "error": "Failed to save your roadmap. Please try again.",
        }), 500

    return jsonify({
        "roadmap_id": roadmap.id,
        "career_path": top_career_path,
        "steps": steps,
        "completed_steps": [],
        "completed_count": 0,
        "total_steps": len(step_indexes(steps)),
    }), 201


@roadmap_bp.route("/roadmap/<int:roadmap_id>/resources", methods=["POST"])
@login_required
def attach_resources(roadmap_id):
    roadmap = GeneratedRoadmap.query.filter_by(
        id=roadmap_id, user_id=current_user.id
    ).first()

    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404

    _, chunks = _get_index()

    try:
        enriched_steps, _resource_stats = fetch_resources_for_roadmap(roadmap.steps, chunks=chunks)
    except Exception as e:
        current_app.logger.exception("%s failed", request.path)
        return jsonify({
            "error": "Failed to fetch YouTube resources.",
        }), 502

    roadmap.steps = enriched_steps

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.exception("%s failed", request.path)
        db.session.rollback()
        return jsonify({
            "error": "Failed to save resources to the roadmap.",
        }), 500

    return jsonify({
        "roadmap_id": roadmap.id,
        "career_path": roadmap.career_path,
        "steps": roadmap.steps,
    }), 200


@roadmap_bp.route("/roadmap/<int:roadmap_id>/progress", methods=["POST"])
@login_required
def update_progress(roadmap_id):
    """
    Body: {"step_index": int, "done": bool}. done=true marks that step
    complete (inserts a RoadmapProgress row if one doesn't already exist);
    done=false marks it incomplete (deletes the row if present). Both are
    idempotent - repeating either call is a no-op the second time, not an
    error.

    The unique constraint on (user_id, roadmap_id, step_index) is the real
    guard against a duplicate row, not the "insert only if missing" check
    above - two concurrent done=true requests for the same step could both
    pass that check before either commits. A resulting IntegrityError means
    someone else's identical insert already won the race, which is exactly
    the state this request wanted anyway, so it's treated as success, not
    an error.
    """
    roadmap = GeneratedRoadmap.query.filter_by(id=roadmap_id, user_id=current_user.id).first()
    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "step_index and done are required."}), 400

    step_index = data.get("step_index")
    done = data.get("done")

    # bool is a subclass of int in Python - excluded explicitly so
    # {"step_index": true, ...} isn't silently accepted as step_index 1.
    if not isinstance(step_index, int) or isinstance(step_index, bool):
        return jsonify({"error": "step_index must be an integer."}), 400
    if not isinstance(done, bool):
        return jsonify({"error": "done must be true or false."}), 400

    valid_indexes = step_indexes(roadmap.steps)
    if step_index not in valid_indexes:
        return jsonify({"error": "That step doesn't exist on this roadmap."}), 400

    if done:
        existing = RoadmapProgress.query.filter_by(
            user_id=current_user.id, roadmap_id=roadmap_id, step_index=step_index
        ).first()
        if existing is None:
            db.session.add(RoadmapProgress(user_id=current_user.id, roadmap_id=roadmap_id, step_index=step_index))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
    else:
        RoadmapProgress.query.filter_by(
            user_id=current_user.id, roadmap_id=roadmap_id, step_index=step_index
        ).delete()
        db.session.commit()

    completed_steps, completed_count, total_steps = roadmap_progress(current_user.id, roadmap_id, roadmap.steps)
    return jsonify({
        "roadmap_id": roadmap_id,
        "completed_steps": completed_steps,
        "completed_count": completed_count,
        "total_steps": total_steps,
    }), 200

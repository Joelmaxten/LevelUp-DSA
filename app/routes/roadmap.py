from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import CareerProfile, GeneratedRoadmap
from app.pipeline.rag import load_index
from app.pipeline.roadmap_generator import generate_roadmap
from app.pipeline.youtube_resources import fetch_resources_for_roadmap

roadmap_bp = Blueprint("roadmap", __name__)

FAISS_INDEX_PATH = "data/processed/faiss_index"  # matches config.py's FAISS_INDEX_PATH

# Loaded once per process, not per-request - the index is large and rebuilding
# it on every call would be wasteful. Mirrors embedder.py's module-level model cache.
_index_cache = None
_chunks_cache = None


def _get_index():
    global _index_cache, _chunks_cache
    if _index_cache is None:
        _index_cache, _chunks_cache = load_index(FAISS_INDEX_PATH)
    return _index_cache, _chunks_cache


@roadmap_bp.route("/roadmap/generate", methods=["POST"])
@login_required
def generate():
    profile = (
        CareerProfile.query
        .filter_by(user_id=current_user.id)
        .order_by(CareerProfile.id.desc())
        .first()
    )

    if profile is None:
        return jsonify({
            "error": "No career profile found. Complete the quiz and conversation first."
        }), 400

    top_career_path = profile.career_ranking[0]["career_path"]

    try:
        index, chunks = _get_index()
    except FileNotFoundError:
        return jsonify({
            "error": "Knowledge base index not found on this server. "
                     "The FAISS index must be built before roadmap generation is available."
        }), 503

    try:
        steps, retrieved_chunks_audit = generate_roadmap(
            top_career_path, profile.conversation_signals, index, chunks
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 502

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
        db.session.rollback()
        return jsonify({
            "error": "Failed to save your roadmap. Please try again.",
            "detail": str(e),
        }), 500

    return jsonify({
        "roadmap_id": roadmap.id,
        "career_path": top_career_path,
        "steps": steps,
    }), 201


@roadmap_bp.route("/roadmap/<int:roadmap_id>/resources", methods=["POST"])
@login_required
def attach_resources(roadmap_id):
    roadmap = GeneratedRoadmap.query.filter_by(
        id=roadmap_id, user_id=current_user.id
    ).first()

    if roadmap is None:
        return jsonify({"error": "Roadmap not found."}), 404

    try:
        enriched_steps = fetch_resources_for_roadmap(roadmap.steps)
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch YouTube resources.",
            "detail": str(e),
        }), 502

    roadmap.steps = enriched_steps

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to save resources to the roadmap.",
            "detail": str(e),
        }), 500

    return jsonify({
        "roadmap_id": roadmap.id,
        "career_path": roadmap.career_path,
        "steps": roadmap.steps,
    }), 200

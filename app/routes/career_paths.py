"""
GET /career/options - the single source the shared career-path picker
(ui.js's careerPathPicker, in its self-fetching mode) uses to decide what
to offer: a profile's top quiz matches (if any), plus the full 15-path
list as a fallback / "choose a different path" option. Read-only - never
creates or modifies a CareerProfile.
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app.models import CareerProfile
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.path_matches import is_unambiguous, top_matches

career_paths_bp = Blueprint("career_paths", __name__)


@career_paths_bp.route("/career/options", methods=["GET"])
@login_required
def get_options():
    profile = (
        CareerProfile.query
        .filter_by(user_id=current_user.id)
        .order_by(CareerProfile.id.desc())
        .first()
    )

    matches = top_matches(profile.career_ranking) if profile is not None else []
    preselect = matches[0]["career_path"] if is_unambiguous(matches) else None

    return jsonify({
        "has_profile": profile is not None,
        "top_matches": matches,
        "preselect": preselect,
        "all_paths": list(CAREER_PATHS),
    }), 200

"""
GET /gamification: the student's XP, level, streak and badges (rules in app/pipeline/gamification.py).

Read-only and per user: every query is filtered by current_user.id, nothing is written. The same gathering is used by
the scenario submit route to report what one submit changed (summary_for(..., exclude_attempt_id=...)).
Errors are fixed codes, never exception text.
"""
from datetime import datetime

from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from app.models import RoadmapProgress, ScenarioAttempt
from app.pipeline import gamification
from app.pipeline import scenario_store as store

gamification_bp = Blueprint("gamification", __name__)


def content_maps():
    """({code question or pool problem id: ds_topic}, {path: [scenario ids]}) from the valid scenario files."""
    code_topics, path_scenarios = {}, {}
    for path, data in store.load_all().items():
        path_scenarios[path] = [s["id"] for s in data["scenarios"]]
        for s in data["scenarios"]:
            for q in s["questions"]:
                if q["type"] == "code":
                    code_topics[q["id"]] = q["ds_topic"]
            for problem in s.get("code_pool") or []:
                code_topics[problem["id"]] = problem["ds_topic"]
    return code_topics, path_scenarios


def summary_for(user_id, today=None, exclude_attempt_id=None):
    rows = (ScenarioAttempt.query
            .filter(ScenarioAttempt.user_id == user_id, ScenarioAttempt.submitted_at.isnot(None))
            .all())
    attempts = [{"id": r.id, "scenario_id": r.scenario_id, "path": r.path, "score": r.score,
                 "max_score": r.max_score, "passed": r.passed, "submitted_at": r.submitted_at,
                 "answers": r.answers or {}}
                for r in rows if r.id != exclude_attempt_id]
    steps = [r.completed_at for r in RoadmapProgress.query.filter(
        RoadmapProgress.user_id == user_id, RoadmapProgress.completed_at.isnot(None)).all()]
    code_topics, path_scenarios = content_maps()
    today = today or gamification.ist_day(datetime.utcnow())
    from app.routes.roadmap import completed_roadmap_count
    return gamification.summarize(attempts, steps, today, code_topics, path_scenarios,
                                  roadmaps_completed=completed_roadmap_count(user_id))


@gamification_bp.route("/gamification", methods=["GET"])
@login_required
def get_gamification():
    try:
        return jsonify(summary_for(current_user.id)), 200
    except Exception:
        current_app.logger.exception("gamification summary failed")
        return jsonify({"error": "gamification_unavailable"}), 500

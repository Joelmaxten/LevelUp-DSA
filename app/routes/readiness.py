"""
GET /readiness: the student's Placement Readiness Score (see app/pipeline/readiness.py for the rules).

This module only gathers the student's own rows (every query is filtered by current_user.id) and hands plain
numbers to the pure functions. Read-only: it never writes anything. Errors are fixed codes, never exception text.
"""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from app.models import CareerProfile, GeneratedRoadmap, Resume, RoadmapProgress, ScenarioAttempt, SkillGap
from app.pipeline import readiness
from app.pipeline import scenario_engine as engine
from app.pipeline import scenario_store as store
from app.pipeline.resume_analyzer import get_required_skills
from app.pipeline.skill_matching import resolve_required
from app.routes.roadmap import roadmap_progress

readiness_bp = Blueprint("readiness", __name__)


def gather_inputs(user_id, today):
    """The keyword arguments for readiness.compute_readiness, from this one user's rows only."""
    latest_roadmap = (GeneratedRoadmap.query.filter_by(user_id=user_id)
                      .order_by(GeneratedRoadmap.id.desc()).first())
    roadmap = None
    if latest_roadmap is not None:
        _, completed, total = roadmap_progress(user_id, latest_roadmap.id, latest_roadmap.steps)
        roadmap = (completed, total)

    skill_gap = None
    resume = (Resume.query.filter_by(user_id=user_id).filter(Resume.analysis_pending.isnot(True))
              .order_by(Resume.id.desc()).first())
    gap = SkillGap.query.filter_by(user_id=user_id).order_by(SkillGap.id.desc()).first()
    if resume is not None and gap is not None and gap.target_role:
        required = get_required_skills(gap.target_role)
        if required:
            skill_gap = (len(resolve_required(required, set(resume.extracted_skills or []))[0]), len(required))

    profile = (CareerProfile.query.filter_by(user_id=user_id).order_by(CareerProfile.id.desc()).first())
    path = None
    if profile is not None and profile.career_ranking:
        path = profile.career_ranking[0].get("career_path")
    elif latest_roadmap is not None:
        path = latest_roadmap.career_path
    path_data = store.get_path(path) if path else None

    scenarios, progress = None, None
    if path_data is not None:
        scenarios = path_data["scenarios"]
        ids = [s["id"] for s in scenarios]
        rows = (ScenarioAttempt.query.filter(ScenarioAttempt.user_id == user_id, ScenarioAttempt.scenario_id.in_(ids),
                                             ScenarioAttempt.submitted_at.isnot(None)).all())
        progress = engine.compute_progress(
            scenarios, [{"scenario_id": r.scenario_id, "score": r.score, "max_score": r.max_score} for r in rows])

    since = datetime.combine(today - timedelta(days=readiness.STREAK_WINDOW_DAYS), datetime.min.time())
    dates = [r.submitted_at.date() for r in ScenarioAttempt.query.filter(
        ScenarioAttempt.user_id == user_id, ScenarioAttempt.submitted_at.isnot(None),
        ScenarioAttempt.submitted_at >= since).all()]
    dates += [r.completed_at.date() for r in RoadmapProgress.query.filter(
        RoadmapProgress.user_id == user_id, RoadmapProgress.completed_at.isnot(None),
        RoadmapProgress.completed_at >= since).all()]

    return {"roadmap": roadmap, "skill_gap": skill_gap, "scenarios": scenarios, "scenario_progress": progress,
            "activity_dates": dates, "today": today}


@readiness_bp.route("/readiness", methods=["GET"])
@login_required
def get_readiness():
    try:
        result = readiness.compute_readiness(**gather_inputs(current_user.id, datetime.utcnow().date()))
    except Exception:
        current_app.logger.exception("readiness score failed")
        return jsonify({"error": "readiness_unavailable"}), 500
    return jsonify(result), 200

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
from app.pipeline import skill_reach
from app.pipeline import scenario_store as store
from app.pipeline.resume_analyzer import get_required_skills
from app.pipeline.skill_matching import resolve_required
from app.routes import skills as skills_route
from app.routes.roadmap import roadmap_progress

readiness_bp = Blueprint("readiness", __name__)


def skill_gap_for(user_id, resume, gap):
    """
    The skill_gap component's (value, required) and the per-skill breakdown the dashboard card shows, per READINESS_SKILL_MODE
    (see app/pipeline/readiness.py). Returns (None, None) when there is nothing to compare. If the evidence cannot be
    gathered, the score falls back to the resume-only rule and the breakdown says so (detail["fallback"]).
    """
    required = sorted(get_required_skills(gap.target_role))
    if not required:
        return None, None
    on_resume = resolve_required(required, set(resume.extracted_skills or []))[0]
    mode = readiness.normalise_skill_mode(current_app.config.get("READINESS_SKILL_MODE", readiness.DEFAULT_SKILL_MODE))
    verified, unreachable, fallback, evidence_failed = set(), set(), False, False
    try:
        summary = skills_route.evidence_for(user_id)
        verified = skill_reach.reachable(required, set(skills_route.verified_tool_names(summary)))
        unreachable = skill_reach.unreachable_everywhere(required, skills_route.content_reach()["all_tools"])
    except Exception:
        current_app.logger.exception("verified skills unavailable; readiness uses the resume only")
        evidence_failed = True
        fallback = mode != "resume"     # the resume-only rule needs no evidence, so nothing falls back there
    breakdown = readiness.skill_gap_breakdown(required, on_resume, verified, unreachable, "resume" if fallback else mode)
    detail = {**breakdown, "configured_mode": mode, "fallback": fallback, "in_score": True, "reason": None,
              "resume_claim_credit": readiness.RESUME_CLAIM_CREDIT, "claim_only_credit": readiness.CLAIM_ONLY_CREDIT}
    if evidence_failed:
        detail["verified"] = None
    return (breakdown["value"], breakdown["required"]), detail


def verified_count_for(user_id, path):
    """
    For a student with NO analysed resume: how many of the path's required skills they have verified, for the dashboard card
    only. It never reaches the score: the skill-gap part stays "not available" for them and the other parts are re-normalised,
    exactly as before (counting it would have lowered every such student's score, see the biography). Returns None when there is
    nothing to show: the mode is "resume" (that mode is unchanged), the path has no required list, or the evidence cannot be
    gathered (nothing depends on it, so no fallback is needed).
    """
    mode = readiness.normalise_skill_mode(current_app.config.get("READINESS_SKILL_MODE", readiness.DEFAULT_SKILL_MODE))
    if mode == "resume":
        return None
    required = sorted(get_required_skills(path))
    if not required:
        return None
    try:
        summary = skills_route.evidence_for(user_id)
        verified = skill_reach.reachable(required, set(skills_route.verified_tool_names(summary)))
        unreachable = skill_reach.unreachable_everywhere(required, skills_route.content_reach()["all_tools"])
    except Exception:
        current_app.logger.exception("verified skills unavailable for the readiness card")
        return None
    breakdown = readiness.skill_gap_breakdown(required, set(), verified, unreachable, "verified")
    for item in breakdown["items"]:
        item["counts_for"] = None          # nothing here counts for the score
    breakdown["value"] = None
    breakdown["mode"] = "none"             # no mode applies: this part is not in the score for this student
    return {**breakdown, "configured_mode": mode, "fallback": False, "in_score": False, "reason": "no_resume", "path": path,
            "resume_claim_credit": readiness.RESUME_CLAIM_CREDIT, "claim_only_credit": readiness.CLAIM_ONLY_CREDIT}


def gather(user_id, today):
    """(the keyword arguments for readiness.compute_readiness, the skill-gap detail for the card), from this one user's rows."""
    latest_roadmap = (GeneratedRoadmap.query.filter_by(user_id=user_id)
                      .order_by(GeneratedRoadmap.id.desc()).first())
    roadmap = None
    if latest_roadmap is not None:
        _, completed, total = roadmap_progress(user_id, latest_roadmap.id, latest_roadmap.steps)
        roadmap = (completed, total)

    profile = (CareerProfile.query.filter_by(user_id=user_id).order_by(CareerProfile.id.desc()).first())
    path = None
    if profile is not None and profile.career_ranking:
        path = profile.career_ranking[0].get("career_path")      # the quiz result first
    elif latest_roadmap is not None:
        path = latest_roadmap.career_path                        # then the latest roadmap's path
    path_data = store.get_path(path) if path else None

    skill_gap, skill_gap_detail = None, None
    resume = (Resume.query.filter_by(user_id=user_id).filter(Resume.analysis_pending.isnot(True))
              .order_by(Resume.id.desc()).first())
    gap = SkillGap.query.filter_by(user_id=user_id).order_by(SkillGap.id.desc()).first()
    if resume is not None and gap is not None and gap.target_role:
        skill_gap, skill_gap_detail = skill_gap_for(user_id, resume, gap)
    elif path:
        # no analysed resume: the score is unchanged (skill_gap stays None); only the card learns the verified count
        skill_gap_detail = verified_count_for(user_id, path)

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

    inputs = {"roadmap": roadmap, "skill_gap": skill_gap, "scenarios": scenarios, "scenario_progress": progress,
              "activity_dates": dates, "today": today}
    return inputs, skill_gap_detail


def gather_inputs(user_id, today):
    """The keyword arguments for readiness.compute_readiness (what the callers before the skill-gap detail existed use)."""
    return gather(user_id, today)[0]


@readiness_bp.route("/readiness", methods=["GET"])
@login_required
def get_readiness():
    try:
        inputs, skill_gap_detail = gather(current_user.id, datetime.utcnow().date())
        result = readiness.compute_readiness(**inputs)
        result["skill_gap_detail"] = skill_gap_detail
    except Exception:
        current_app.logger.exception("readiness score failed")
        return jsonify({"error": "readiness_unavailable"}), 500
    return jsonify(result), 200

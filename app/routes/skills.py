"""
GET /skills/evidence: the student's skill evidence (rules in app/pipeline/skill_evidence.py, data in data/skill_map.json).

Read-only and per user: every query is filtered by current_user.id and nothing is written. This file only gathers the rows
(passed step checks, passed scenarios, solved code problems, the latest resume) and hands them to the pure module.
Errors are fixed codes, never exception text.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from app.models import GeneratedRoadmap, Resume, ScenarioAttempt, StepCheckAttempt
from app.pipeline import scenario_store as store
from app.pipeline import skill_evidence as se
from app.pipeline import step_checks as sc
from app.pipeline.base_roadmaps import slug as path_slug

skills_bp = Blueprint("skills", __name__)
logger = logging.getLogger(__name__)

SKILL_MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "skill_map.json"   # tests may override
_map_cache = {}          # path -> (mtime, prepared map)
_vocab_cache = {}        # "vocab" -> the survey skill vocabulary (static data: read once per process)


def load_skill_map(path=None):
    """The prepared skill map, re-read when the file changes. Raises ValueError/OSError if it is missing or malformed."""
    path = Path(path or SKILL_MAP_PATH)
    stamp = path.stat().st_mtime
    cached = _map_cache.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    prepared = se.prepare_map(json.loads(path.read_text(encoding="utf-8")))
    _map_cache[path] = (stamp, prepared)
    return prepared


def _vocabulary():
    """The resume matcher's skill vocabulary (needs the survey table). Cached: the survey does not change while running."""
    if "vocab" not in _vocab_cache:
        from app.pipeline.resume_analyzer import get_extended_skill_vocabulary
        _vocab_cache["vocab"] = frozenset(get_extended_skill_vocabulary())
    return _vocab_cache["vocab"]


def _matcher(vocab):
    """matcher(text) -> skill names, using the resume skill extractor unchanged; None when there is no vocabulary."""
    if not vocab:
        return None
    from app.pipeline.resume_skill_extractor import extract_skills

    @lru_cache(maxsize=2048)
    def match(text):
        return tuple(extract_skills(text, vocab, extended_aliases=True))

    return match


def content_index():
    """({scenario id: {title, topics}}, {code problem id: {title, skills, ds_topic}}) from the valid scenario files."""
    scenarios, problems = {}, {}
    for _path, data in store.load_all().items():
        for s in data["scenarios"]:
            scenarios[s["id"]] = {"title": s["title"], "topics": s.get("tests_topics") or []}
            code = [q for q in s["questions"] if q.get("type") == "code"] + list(s.get("code_pool") or [])
            for problem in code:
                problems[problem["id"]] = {"title": f"Coding problem in “{s['title']}”", "skills": problem.get("skills") or [],
                                           "ds_topic": problem.get("ds_topic")}
    return scenarios, problems


def _step_evidence(user_id, skill_map, matcher, spelling):
    attempts = (StepCheckAttempt.query
                .filter(StepCheckAttempt.user_id == user_id, StepCheckAttempt.passed.is_(True)).all())
    if not attempts:
        return []
    roadmaps = {r.id: r for r in GeneratedRoadmap.query.filter(
        GeneratedRoadmap.user_id == user_id, GeneratedRoadmap.id.in_({a.roadmap_id for a in attempts})).all()}
    steps_of = {}
    out = []
    for a in attempts:
        roadmap = roadmaps.get(a.roadmap_id)
        if roadmap is None:
            continue
        if roadmap.id not in steps_of:
            steps_of[roadmap.id] = dict(sc.flat_steps(roadmap.steps))
        step = steps_of[roadmap.id].get(a.step_index)
        if not step:
            continue
        slug = path_slug(roadmap.career_path)
        skills = se.skills_for_step(slug, step.get("title"), step.get("subtopics"), skill_map, matcher, spelling)
        if skills:
            out.append(se.evidence_item("test_out" if a.mode == "test_out" else "step_check",
                                        se.step_key(slug, step.get("title")), step.get("title"), a.submitted_at, skills))
    return out


def _scenario_evidence(user_id, skill_map, matcher, spelling):
    scenarios, problems = content_index()
    rows = (ScenarioAttempt.query
            .filter(ScenarioAttempt.user_id == user_id, ScenarioAttempt.submitted_at.isnot(None))
            .order_by(ScenarioAttempt.submitted_at, ScenarioAttempt.id).all())
    passed_at, solved_at = {}, {}
    for r in rows:
        if r.passed and r.scenario_id in scenarios:
            passed_at.setdefault(r.scenario_id, r.submitted_at)
        answers = r.answers if isinstance(r.answers, dict) else {}
        for qid, value in answers.items():
            if qid in problems and isinstance(value, dict) and value.get("passed") is True:
                solved_at.setdefault(qid, r.submitted_at)
    out = []
    for sid, when in passed_at.items():
        info = scenarios[sid]
        skills = se.skills_for_scenario(sid, info["topics"], skill_map, matcher, spelling)
        if skills:
            out.append(se.evidence_item("scenario", sid, info["title"], when, skills))
    for qid, when in solved_at.items():
        info = problems[qid]
        skills = se.skills_for_code(info["skills"], info["ds_topic"], skill_map, spelling)
        if skills:
            out.append(se.evidence_item("code", qid, info["title"], when, skills))
    return out


def _resume_skills(user_id):
    """The newest resume that has extracted skills (a discover-only upload counts). Skills are a claim, never proof."""
    for resume in (Resume.query.filter(Resume.user_id == user_id, Resume.extracted_skills.isnot(None))
                   .order_by(Resume.id.desc()).limit(10).all()):
        if resume.extracted_skills:
            return list(resume.extracted_skills)
    return []


def evidence_for(user_id):
    skill_map = load_skill_map()
    vocab = _vocabulary()
    spelling = {name.lower(): name for name in vocab}
    matcher = _matcher(vocab)
    evidence = (_step_evidence(user_id, skill_map, matcher, spelling)
                + _scenario_evidence(user_id, skill_map, matcher, spelling))
    return se.summarize(evidence, _resume_skills(user_id), skill_map, spelling)


@skills_bp.route("/skills/evidence", methods=["GET"])
@login_required
def get_skill_evidence():
    try:
        return jsonify(evidence_for(current_user.id)), 200
    except Exception:
        current_app.logger.exception("skill evidence failed")
        return jsonify({"error": "skills_unavailable"}), 500

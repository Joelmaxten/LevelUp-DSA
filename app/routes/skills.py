"""
GET /skills/evidence: the student's skill evidence (rules in app/pipeline/skill_evidence.py, data in data/skill_map.json).

Read-only and per user: every query is filtered by current_user.id and nothing is written. This file only gathers the rows
(passed step checks, passed scenarios, solved code problems, the latest resume) and hands them to the pure module.
Errors are fixed codes, never exception text.
"""
import json
import logging
import threading
from functools import lru_cache
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.models import GeneratedRoadmap, Resume, ScenarioAttempt, StepCheckAttempt
from app.pipeline import scenario_store as store
from app.pipeline import skill_evidence as se
from app.pipeline import skill_reach
from app.pipeline import step_checks as sc
from app.pipeline.base_roadmaps import BASE_DIR, slug as path_slug
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.skill_matching import COMPOSITE_SKILLS

skills_bp = Blueprint("skills", __name__)
logger = logging.getLogger(__name__)

SKILL_MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "skill_map.json"   # tests may override
_map_cache = {}          # path -> (mtime, prepared map)
_vocab_cache = {}        # "vocab" -> the survey skill vocabulary (static data: read once per process)
_reach_cache = {}        # "reach" -> (key, what the content can verify): static data, worked out once per process
_reach_lock = threading.Lock()


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


def content_reach():
    """
    What the platform's content can verify, worked out once per process and cached (the content files and the vocabulary do not
    change while the server runs; the cache is rebuilt if the skill map file or the vocabulary changes):
      {"all_tools": every tool skill any step, scenario or code problem of any path can verify,
       "scenarios": {scenario id: {"title", "path", "skills": set of tool skills it (and its code problems) verify}},
       "steps": {lower-case skill: [(career path, step title)] over the base roadmaps}}
    Uses the shared reach logic (app/pipeline/skill_reach.py), the same code as scripts/readiness_reach_report.py.
    """
    skill_map = load_skill_map()
    vocab = _vocabulary()
    key = (Path(SKILL_MAP_PATH).stat().st_mtime, len(vocab))
    with _reach_lock:
        cached = _reach_cache.get("reach")
        if cached and cached[0] == key:
            return cached[1]
        spelling = {name.lower(): name for name in vocab}
        matcher = _matcher(vocab)
        roadmaps = {}
        for path in CAREER_PATHS:
            file = Path(BASE_DIR) / f"{path_slug(path)}.json"
            roadmaps[path] = json.loads(file.read_text(encoding="utf-8")) if file.exists() else None
        files = store.load_all()
        per_source = skill_reach.tools_by_source(skill_map, matcher, spelling, roadmaps, files, CAREER_PATHS, path_slug)
        scenarios = {}
        for path, data in files.items():
            for s in data["scenarios"]:
                found = set(se.skills_for_scenario(s["id"], s.get("tests_topics"), skill_map, matcher, spelling))
                for problem in [q for q in s["questions"] if q.get("type") == "code"] + list(s.get("code_pool") or []):
                    found.update(se.skills_for_code(problem.get("skills"), problem.get("ds_topic"), skill_map, spelling))
                scenarios[s["id"]] = {"title": s["title"], "path": path, "skills": {x for x in found if x not in skill_map["concepts"]}}
        steps = {}
        for path, doc in roadmaps.items():
            for phase in (doc or {}).get("roadmap", {}).get("phases", []):
                for step in phase["steps"]:
                    for skill in se.skills_for_step(path_slug(path), step.get("title"), step.get("subtopics"), skill_map, matcher, spelling):
                        steps.setdefault(skill.lower(), []).append((path, step.get("title") or ""))
        value = {"all_tools": skill_reach.all_tools(per_source), "scenarios": scenarios, "steps": steps}
        _reach_cache["reach"] = (key, value)
        return value


def verified_tool_names(summary):
    """Names of the verified TOOL skills in an evidence summary, strongest first (the summary is sorted by confidence)."""
    return [r["skill"] for r in summary["skills"] if r["kind"] == "tool" and r["status"] == "verified"]


def coverage_for(user_id, names):
    """
    For each skill name (the resume page's matched skills): is it verified, and where on the platform can it be proved?
    {skill: {"verified": bool, "where": [{"type": "step"|"scenario", "title", "url"}], "no_content": bool}}.
    Steps come from the student's latest roadmap; when it has none for a skill, a step of another path's base roadmap is named with
    its path ("in" is that career path, else null); scenarios from the content (the roadmap's path first). Names are compared
    case-insensitively; a composite ("HTML/CSS") is covered by its parts.
    """
    skill_map = load_skill_map()
    vocab = _vocabulary()
    spelling = {name.lower(): name for name in vocab}
    matcher = _matcher(vocab)
    summary = evidence_for(user_id)
    verified = skill_reach.reachable(names, set(verified_tool_names(summary)))     # same rules as the resume comparison
    reach = content_reach()
    covers = skill_reach.reachable(names, reach["all_tools"])

    roadmap = (GeneratedRoadmap.query.filter_by(user_id=user_id).order_by(GeneratedRoadmap.id.desc()).first())
    step_skills = []
    if roadmap is not None:
        slug = path_slug(roadmap.career_path)
        for index, step in sc.flat_steps(roadmap.steps):
            found = se.skills_for_step(slug, step.get("title"), step.get("subtopics"), skill_map, matcher, spelling)
            step_skills.append((index, step.get("title") or "", {x.lower() for x in found}))
    ordered = sorted(reach["scenarios"].items(), key=lambda kv: (roadmap is None or kv[1]["path"] != roadmap.career_path, kv[0]))

    out = {}
    for name in names:
        wanted = {p.lower() for p in COMPOSITE_SKILLS.get(name, ())} or {name.lower()}
        where = []
        for index, title, found in step_skills:
            if wanted & found and len([w for w in where if w["type"] == "step"]) < 2:
                where.append({"type": "step", "title": title, "url": "/roadmap", "in": None})
        if not any(w["type"] == "step" for w in where):      # not in the student's own roadmap: name one base-roadmap step elsewhere
            for part in sorted(wanted):
                elsewhere = reach["steps"].get(part)
                if elsewhere:
                    # best first: the student's own path, then a step whose title names the skill, then content order
                    own = roadmap.career_path if roadmap is not None else None
                    best = min(enumerate(elsewhere), key=lambda e: (e[1][0] != own, part not in e[1][1].lower(), e[0]))[1]
                    where.append({"type": "step", "title": best[1], "url": "/roadmap", "in": best[0]})
                    break
        for _sid, info in ordered:
            if wanted & {x.lower() for x in info["skills"]} and len([w for w in where if w["type"] == "scenario"]) < 2:
                where.append({"type": "scenario", "title": info["title"], "url": "/scenarios", "in": None})
        out[name] = {"verified": name in verified, "where": where, "no_content": name not in covers}
    return out


@skills_bp.route("/skills/coverage", methods=["GET"])
@login_required
def get_skill_coverage():
    """GET /skills/coverage?skill=Python&skill=SQL (up to 30): for the resume page's matched skills. Read-only, own data."""
    names = [n.strip() for n in request.args.getlist("skill") if isinstance(n, str) and 0 < len(n.strip()) <= 80][:30]
    if not names:
        return jsonify({"error": "no_skills"}), 400
    try:
        return jsonify({"skills": coverage_for(current_user.id, list(dict.fromkeys(names)))}), 200
    except Exception:
        current_app.logger.exception("skill coverage failed")
        return jsonify({"error": "skills_unavailable"}), 500


@skills_bp.route("/skills/evidence", methods=["GET"])
@login_required
def get_skill_evidence():
    try:
        return jsonify(evidence_for(current_user.id)), 200
    except Exception:
        current_app.logger.exception("skill evidence failed")
        return jsonify({"error": "skills_unavailable"}), 500

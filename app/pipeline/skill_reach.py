"""
Which required skills can be verified on the platform AT ALL. Pure: no Flask, no database, no network, no spaCy (the matcher is
passed in). The content is passed in as parsed data, so this module reads nothing.

A required skill is "reachable" when some base-roadmap step, scenario or code problem is evidence for it, by the same rules as the
skill evidence feature (app/pipeline/skill_evidence.py: the resume matcher on a step's title and subtopics or a scenario's
tests_topics, plus data/skill_map.json, minus its exclusions; a code problem's own `skills`). Only TOOL skills count, because
concept skills are never in the required list. A composite ("HTML/CSS") needs all its parts and an implying skill counts ("SQL"
via MySQL, PostgreSQL ...), exactly like the resume comparison (skill_matching.resolve_required).

Used by the readiness score (to label required skills "no LevelUp content for this yet") and by scripts/readiness_reach_report.py,
so the dashboard and the report cannot disagree.
"""
from app.pipeline import skill_evidence as se
from app.pipeline.skill_matching import resolve_required

SOURCES = ("steps", "scenarios", "code problems")


def tools_by_source(skill_map, matcher, spelling, roadmaps, scenario_files, career_paths, slug_of):
    """
    {source: {career path: set of TOOL skill names that content of that path can verify}}.
    roadmaps: {career path: parsed base roadmap document, or None}. scenario_files: {career path: parsed scenario file}.
    slug_of(career path) -> the slug used in step keys.
    """
    concepts = skill_map["concepts"]
    out = {source: {path: set() for path in career_paths} for source in SOURCES}
    for path in career_paths:
        doc = roadmaps.get(path)
        if not doc:
            continue
        slug = slug_of(path)
        steps = set()
        for phase in doc["roadmap"]["phases"]:
            for step in phase["steps"]:
                steps.update(se.skills_for_step(slug, step.get("title"), step.get("subtopics"), skill_map, matcher, spelling))
        out["steps"][path] = {s for s in steps if s not in concepts}
    for path, data in scenario_files.items():
        scenarios, problems = set(), set()
        for scenario in data["scenarios"]:
            scenarios.update(se.skills_for_scenario(scenario["id"], scenario.get("tests_topics"), skill_map, matcher, spelling))
            for problem in [q for q in scenario["questions"] if q.get("type") == "code"] + list(scenario.get("code_pool") or []):
                problems.update(se.skills_for_code(problem.get("skills"), problem.get("ds_topic"), skill_map, spelling))
        out["scenarios"][path] = {s for s in scenarios if s not in concepts}
        out["code problems"][path] = {s for s in problems if s not in concepts}
    return out


def respell(required, names):
    """The given tool names spelled the way the required list spells them (case-insensitive match), others unchanged."""
    by_lower = {r.lower(): r for r in required}
    return {by_lower.get(n.lower(), n) for n in names}


def reachable(required, tools):
    """The required skills these tool names verify (composites need every part; an implying skill counts)."""
    matched, _missing, _partial = resolve_required(required, respell(required, tools))
    return matched


def all_tools(per_source):
    """Every tool any source of any path can verify."""
    return set().union(*[tools for by_path in per_source.values() for tools in by_path.values()])


def unreachable_everywhere(required, tools):
    """Required skills that NO step, scenario or code problem of any path can verify ("no LevelUp content for this yet")."""
    return set(required) - reachable(required, tools)

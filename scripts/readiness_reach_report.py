"""
READ-ONLY report: how much of each career path's REQUIRED skill list can a student ever VERIFY on the platform?

Why: the Placement Readiness score's skill-gap part compares a student's skills with the path's required list (the most common
tools among survey respondents, see get_required_skills). If readiness is changed to count only VERIFIED skills, a required
skill that no step check, scenario or coding problem can ever verify would be impossible to earn. This report counts those.

For each career path it prints:
  - N: how many skills are in the required list, and how many of them are spelled exactly as in the survey vocabulary;
  - how many required skills can be verified through (a) base-roadmap steps, (b) scenarios, (c) code problems, and in total,
    both counting only the path's OWN content and counting the content of ALL paths;
  - the share that is reachable (percent);
  - the names of the required skills that no step, scenario or code problem of any path can verify, and the ones only
    reachable through another path's content.
"Can verify" uses the same rules as the skill evidence feature: the resume skill matcher on a step's title and subtopics (or a
scenario's tests_topics), plus data/skill_map.json (additions and exclusions), plus a code problem's own `skills`. Only TOOL
skills count (concept skills are never in the required list). A composite ("HTML/CSS") needs all its parts, and an implied skill
("SQL" via MySQL / PostgreSQL ...) counts, exactly like the resume comparison (resolve_required).

SAFETY: it never writes. The whole run is one database transaction opened with SET TRANSACTION READ ONLY (the database itself
refuses any write) and rolled back at the end. It reads only survey_respondents (to build the required lists and the
vocabulary) and the committed content files. It prints career path names, skill names and counts: no user, email, resume,
roadmap or id is read, so none can be printed.

Usage:
    PYTHONPATH=. python scripts/readiness_reach_report.py                  # all 15 paths
    PYTHONPATH=. python scripts/readiness_reach_report.py --path "DevOps"   # one path
    PYTHONPATH=. python scripts/readiness_reach_report.py > reach.txt       # to keep it (your shell writes the file)
"""
import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("WARMUP_ON_START", "false")   # do not start background threads for a report

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text

from app import create_app, db
from app.pipeline import base_roadmaps, scenario_store as store
from app.pipeline import skill_evidence as se
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.resume_analyzer import get_extended_skill_vocabulary, get_required_skills
from app.pipeline.resume_skill_extractor import extract_skills
from app.pipeline.skill_matching import resolve_required

SKILL_MAP = Path("data/skill_map.json")
SOURCES = ("steps", "scenarios", "code problems")


def make_matcher(vocab):
    if not vocab:
        return None

    @lru_cache(maxsize=4096)
    def match(text_):
        return tuple(extract_skills(text_, vocab, extended_aliases=True))

    return match


def tools_by_source(skill_map, matcher, spelling):
    """{source: {career path: set of TOOL skill names that content of that path can verify}}."""
    concepts = skill_map["concepts"]
    out = {source: {} for source in SOURCES}
    for path in CAREER_PATHS:
        slug = base_roadmaps.slug(path)
        file = Path(base_roadmaps.BASE_DIR) / f"{slug}.json"
        steps = set()
        if file.exists():
            doc = json.loads(file.read_text(encoding="utf-8"))
            for phase in doc["roadmap"]["phases"]:
                for step in phase["steps"]:
                    steps.update(se.skills_for_step(slug, step.get("title"), step.get("subtopics"), skill_map, matcher, spelling))
        out["steps"][path] = {s for s in steps if s not in concepts}
    for path, data in store.load_all().items():
        scenarios, problems = set(), set()
        for scenario in data["scenarios"]:
            scenarios.update(se.skills_for_scenario(scenario["id"], scenario.get("tests_topics"), skill_map, matcher, spelling))
            for problem in [q for q in scenario["questions"] if q.get("type") == "code"] + list(scenario.get("code_pool") or []):
                problems.update(se.skills_for_code(problem.get("skills"), problem.get("ds_topic"), skill_map, spelling))
        out["scenarios"][path] = {s for s in scenarios if s not in concepts}
        out["code problems"][path] = {s for s in problems if s not in concepts}
    for source in SOURCES:
        for path in CAREER_PATHS:
            out[source].setdefault(path, set())
    return out


def reachable(required, tools):
    """The required skills these tool names verify. Names are matched case-insensitively, then resolved like the resume
    comparison (a composite needs all its parts; an implying skill counts)."""
    by_lower = {r.lower(): r for r in required}
    respelled = {by_lower.get(t.lower(), t) for t in tools}
    matched, _missing, _partial = resolve_required(required, respelled)
    return matched


def percent(part, whole):
    return f"{100 * part // whole}%" if whole else "n/a"


def report_path(path, required, per_source, vocab, concepts):
    lines = [f"== {path} =="]
    if not required:
        lines.append("  no required skills (no survey respondents are mapped to this path in this database)")
        return lines, None
    n = len(required)
    in_vocab = [r for r in required if r in vocab]
    lines.append(f"  required skills (N): {n}. Spelled exactly as in the vocabulary: {len(in_vocab)} of {n}"
                 + ("" if len(in_vocab) == n else f"  NOT in the vocabulary: {', '.join(sorted(set(required) - set(in_vocab)))}"))
    clash = sorted(set(required) & set(concepts))
    if clash:
        lines.append(f"  (also a concept name: {', '.join(clash)})")
    lines.append(f"  {'verified through':<26}{'own path':>10}{'all paths':>11}")
    own_union, all_union = set(), set()
    for source in SOURCES:
        own = reachable(required, per_source[source][path])
        everywhere = reachable(required, set().union(*per_source[source].values()))
        own_union |= per_source[source][path]
        all_union |= set().union(*per_source[source].values())
        lines.append(f"  {source:<26}{len(own):>10}{len(everywhere):>11}")
    own_total, all_total = reachable(required, own_union), reachable(required, all_union)
    lines.append(f"  {'reachable in total':<26}{len(own_total):>10}{len(all_total):>11}")
    lines.append(f"  {'share of the list':<26}{percent(len(own_total), n):>10}{percent(len(all_total), n):>11}")
    unreachable = sorted(set(required) - all_total)
    lines.append("  NO step, scenario or code problem of any path can verify: " + (", ".join(unreachable) if unreachable else "(none)"))
    only_elsewhere = sorted(all_total - own_total)
    lines.append("  only another path's content can verify: " + (", ".join(only_elsewhere) if only_elsewhere else "(none)"))
    return lines, (n, len(own_total), len(all_total))


def main():
    parser = argparse.ArgumentParser(description="Read-only report: which required skills can be verified on the platform.")
    parser.add_argument("--path", help="only this career path (exact name, e.g. \"Backend Engineering\")")
    args = parser.parse_args()
    paths = [args.path] if args.path else list(CAREER_PATHS)
    if args.path and args.path not in CAREER_PATHS:
        print(f"Unknown career path {args.path!r}. Choose one of: {', '.join(CAREER_PATHS)}")
        return 2

    skill_map = se.prepare_map(json.loads(SKILL_MAP.read_text(encoding="utf-8")))
    app = create_app()
    with app.app_context():
        db.session.execute(text("SET TRANSACTION READ ONLY"))      # the database refuses any write from here on
        try:
            vocab = frozenset(get_extended_skill_vocabulary())
            required = {path: sorted(get_required_skills(path)) for path in paths}
        finally:
            db.session.rollback()                                  # nothing to commit; end the transaction

    spelling = {name.lower(): name for name in vocab}
    per_source = tools_by_source(skill_map, make_matcher(vocab), spelling)

    if not vocab:
        print("NOTE: survey_respondents is empty in this database: there is no vocabulary and no required list, so the numbers below are empty.\n")
    totals = []
    for path in paths:
        lines, counts = report_path(path, required[path], per_source, vocab, skill_map["concepts"])
        print("\n".join(lines) + "\n")
        if counts:
            totals.append((path, counts))

    if totals:
        print("== Summary (reachable share of the required list) ==")
        print(f"  {'career path':<32}{'N':>3}{'own path':>10}{'all paths':>11}")
        for path, (n, own, everywhere) in totals:
            print(f"  {path:<32}{n:>3}{percent(own, n):>10}{percent(everywhere, n):>11}")
        n_all, own_all, any_all = (sum(c[i] for _, c in totals) for i in range(3))
        print(f"  {'ALL PATHS TOGETHER':<32}{n_all:>3}{percent(own_all, n_all):>10}{percent(any_all, n_all):>11}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
READ-ONLY report for the skill-evidence work. Run it against the database you want to inspect (it uses DATABASE_URL from
your .env). It never writes: the whole run is one database transaction opened with SET TRANSACTION READ ONLY (the
database itself refuses any write) and it is rolled back at the end. It prints counts and skill names only, never a user,
an email, a resume, a roadmap's contents or any id.

It answers three questions:
 1. Which distinct skill names are in survey_respondents, per category, with how many respondents list each?
    (This is the vocabulary the resume matcher uses; data/skill_map.json must spell tools the same way.)
 2. Which tool names used in data/skill_map.json are NOT in that vocabulary (spelling to fix or tool to leave out)?
 3. How many saved roadmaps (generated_roadmaps) carry the "base" marker (copied from a reviewed base roadmap, so their
    step titles match data/skill_map.json) and how many do not? And of all their steps, how many have a title that has
    a curated entry in data/skill_map.json?

Usage:
    PYTHONPATH=. python scripts/vocab_report.py                 # everything
    PYTHONPATH=. python scripts/vocab_report.py --min-count 5   # hide names listed by fewer than 5 respondents
    PYTHONPATH=. python scripts/vocab_report.py > report.txt    # to keep it (this is your shell writing the file)
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("WARMUP_ON_START", "false")   # do not start background threads for a report

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text

from app import create_app, db
from app.models import GeneratedRoadmap, SurveyRespondent
from app.pipeline import base_roadmaps
from app.pipeline.skill_matching import COMPOSITE_SKILLS
from app.pipeline.skill_vocabulary import AMBIGUOUS_SURVEY_NAMES, SUPPLEMENTAL_SKILLS, SURVEY_EXTRA_COLUMNS

SKILL_MAP = Path("data/skill_map.json")
CATEGORIES = ("languages", "databases", "platforms", "webframes") + tuple(SURVEY_EXTRA_COLUMNS)


def normalise(title):
    return re.sub(r"\s+", " ", str(title or "").strip().lower())


def vocabulary_counts():
    """{category: Counter(name -> respondents listing it)}. Reads the arrays; no respondent is identified."""
    counts = {c: Counter() for c in CATEGORIES}
    for row in db.session.query(*[getattr(SurveyRespondent, c) for c in CATEGORIES]).yield_per(500):
        for category, names in zip(CATEGORIES, row):
            counts[category].update(set(names or []))
    return counts


def skill_map_tools(skill_map):
    """The tool (non-concept) skill names the file adds, plus the canonical spellings it lists."""
    concepts = set(skill_map["concepts"])
    names = set(skill_map["canonical"].values())
    for entry in list(skill_map["steps"].values()) + list(skill_map["scenarios"].values()):
        names.update(entry)
    for rule in skill_map["exclude"]:
        names.update(rule.get("skills", []) + ([rule["skill"]] if "skill" in rule else []))
    return sorted(names - concepts)


def roadmap_counts(curated_keys):
    """Counts only: roadmaps by kind and steps with / without a curated skill_map entry."""
    kinds = Counter()
    steps = Counter()
    for career_path, doc in db.session.query(GeneratedRoadmap.career_path, GeneratedRoadmap.steps).yield_per(200):
        if isinstance(doc, dict) and isinstance(doc.get("base"), dict) and doc["base"].get("source") == "base_roadmap":
            kind = "with base marker (copied from a reviewed base roadmap)"
        elif isinstance(doc, dict):
            kind = "no base marker, phased (generated from scratch)"
        else:
            kind = "no base marker, old flat list (generated before phases existed)"
        kinds[kind] += 1
        flat = [s for p in doc.get("phases", []) for s in p.get("steps", [])] if isinstance(doc, dict) else (doc or [])
        slug = base_roadmaps.slug(career_path)
        for step in flat:
            if isinstance(step, dict):
                steps[("with" if kind.startswith("with") else "without", f"{slug}|{normalise(step.get('title'))}" in curated_keys)] += 1
    return kinds, steps


def main():
    parser = argparse.ArgumentParser(description="Read-only vocabulary and roadmap report (counts only).")
    parser.add_argument("--min-count", type=int, default=1, help="hide skill names listed by fewer respondents than this")
    args = parser.parse_args()

    skill_map = json.loads(SKILL_MAP.read_text(encoding="utf-8"))
    curated_keys = set(skill_map["steps"])

    app = create_app()
    with app.app_context():
        db.session.execute(text("SET TRANSACTION READ ONLY"))      # the database refuses any write from here on
        try:
            counts = vocabulary_counts()
            kinds, steps = roadmap_counts(curated_keys)
        finally:
            db.session.rollback()                                  # nothing to commit; end the transaction

    print("== 1. Survey vocabulary (distinct skill names per category) ==")
    everything = set()
    for category in CATEGORIES:
        shown = [(n, c) for n, c in counts[category].most_common() if c >= args.min_count]
        everything.update(counts[category])
        print(f"\n[{category}] {len(counts[category])} distinct names" + (f", showing {len(shown)} with >= {args.min_count} respondents" if args.min_count > 1 else ""))
        for name, count in shown:
            print(f"  {count:5d}  {name}")
    usable = (everything - AMBIGUOUS_SURVEY_NAMES) | SUPPLEMENTAL_SKILLS
    print(f"\nDistinct names over all categories: {len(everything)}. Extended resume vocabulary "
          f"(minus ambiguous names, plus supplemental skills): {len(usable)}.")

    print("\n== 2. Tool names in data/skill_map.json that are not in the vocabulary ==")
    lower = {n.lower() for n in usable} | {part.lower() for parts in COMPOSITE_SKILLS.values() for part in parts}   # HTML, CSS come from the composite rule
    missing = [t for t in skill_map_tools(skill_map) if t.lower() not in lower]
    print("  (none)" if not missing else "\n".join(f"  {t}" for t in missing))
    if not everything:
        print("  NOTE: survey_respondents is empty in this database, so every name is reported missing.")

    print("\n== 3. Saved roadmaps ==")
    total = sum(kinds.values())
    print(f"  roadmaps in total: {total}")
    for kind, n in sorted(kinds.items()):
        print(f"  {n:5d}  {kind}")
    for side in ("with", "without"):
        hit, miss = steps[(side, True)], steps[(side, False)]
        if hit + miss:
            print(f"  steps of roadmaps {side} the base marker: {hit + miss}, of which {hit} have a curated entry "
                  f"in data/skill_map.json ({100 * hit // (hit + miss)}%), {miss} do not")
    return 0


if __name__ == "__main__":
    sys.exit(main())

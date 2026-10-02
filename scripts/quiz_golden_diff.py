"""
Compares two quiz golden files (default: the original engine's quiz_before.json against the redesigned
quiz_after.json) and prints how many of the seeded sequences changed their top path, top-score
group, question count and questions asked. Local only.

    PYTHONPATH=. python scripts/quiz_golden_diff.py [before.json after.json]
"""
import json
import sys
from pathlib import Path

from app.pipeline.career_path_registry import CAREER_PATHS


def top_group(run):
    best = max(run["scores"].values())
    return [p for p in CAREER_PATHS if run["scores"][p] == best]


def main():
    before_file = Path(sys.argv[1]) if len(sys.argv) > 2 else Path("scratch/golden/quiz_before.json")
    after_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scratch/golden/quiz_after.json")
    before = json.loads(before_file.read_text(encoding="utf-8"))
    after = json.loads(after_file.read_text(encoding="utf-8"))
    n = len(before)
    same_questions = sum(1 for b, a in zip(before, after) if b["asked"] == a["asked"])
    first_changed = sum(1 for b, a in zip(before, after) if b["ranking"][0]["career_path"] != a["ranking"][0]["career_path"])
    group_changed = sum(1 for b, a in zip(before, after) if top_group(b) != top_group(a))
    count_changed = sum(1 for b, a in zip(before, after) if b["answered"] != a["answered"])
    tied_before = sum(1 for b in before if len(top_group(b)) > 1)
    tied_after = sum(1 for a in after if len(top_group(a)) > 1)
    print(f"{n} seeded sequences: {before_file.name} -> {after_file.name}")
    print(f"  asked exactly the same questions in the same order: {same_questions}/{n}")
    print(f"  changed the #1 path as displayed:                   {first_changed}/{n}")
    print(f"  changed the top-score group (the tied paths):        {group_changed}/{n}")
    print(f"  changed the number of questions asked:               {count_changed}/{n} "
          f"(mean {sum(b['answered'] for b in before)/n:.1f} -> {sum(a['answered'] for a in after)/n:.1f})")
    print(f"  finished with a shared top score:                    {tied_before}/{n} -> {tied_after}/{n}")
    print("  note: the same seed picks the same random option NUMBER, but the questions are now different, so these are not like-for-like answers.")
    print("  (the new bank has 18 questions, the old one 10)")


if __name__ == "__main__":
    main()

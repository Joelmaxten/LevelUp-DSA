"""
Relabels job_listings.career_paths from the old 10 path names to the new
15 (see app/pipeline/career_path_registry.py), and additionally tags any
row whose job title looks QA/test-flavored with "QA & Test Automation" -
no old path covered QA, since it didn't exist before this restructuring.

Dry-run by default: computes and prints the before/after tag counts and
every job title the QA pattern matched (for false-positive review),
without writing anything. Pass --apply to actually commit the changes.

Idempotent: re-running against already-relabeled rows is safe. A tag not
in OLD_TO_NEW's keys (i.e. already one of the new 15, or something else
entirely) passes through unchanged rather than being dropped, so a second
run doesn't re-translate or lose already-migrated tags; the QA regex
adding an already-present "QA & Test Automation" tag is a no-op (checked
before appending, never duplicated).

Run:  PYTHONPATH=. python scripts/relabel_job_listings.py            (dry run)
      PYTHONPATH=. python scripts/relabel_job_listings.py --apply     (writes)
"""
import argparse
import re
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import JobListing
from app.pipeline.career_path_registry import CAREER_PATHS

# Old path name -> new path name(s). "Research / Advanced Computing" maps to
# [] - the tag is dropped entirely, per the restructuring decision to remove
# that path with no replacement. A tag not found here (already migrated, or
# unrecognized) passes through unchanged - see translate_tags().
OLD_TO_NEW = {
    "Software Engineering / Full-Stack Development": ["Full-Stack Development"],
    "AI / Machine Learning Engineering": ["AI Engineering", "Machine Learning Engineering"],
    "Data Science / Data Analytics": ["Data Science", "Data Analytics"],
    "Backend / Systems Engineering": ["Backend Engineering"],
    "UI/UX + Frontend Development": ["UI/UX Design", "Frontend Development"],
    "Cloud / DevOps": ["Cloud Engineering", "DevOps"],
    "Research / Advanced Computing": [],
    "Cybersecurity": ["Cybersecurity"],
    "Mobile App Development": ["Mobile App Development"],
    "Game Development": ["Game Development"],
}

# Case-insensitive, whole-word/whole-phrase match: qa, sdet, tester,
# testers, "test engineer", "manual testing", "software testing",
# "automation testing", "quality assurance", "quality analyst". Bare
# "test"/"testing" are deliberately NOT matched (too broad - caught
# unrelated physical-testing roles like "Soil and Rock testing
# assistant"). "quality control"/"quality engineer" are deliberately NOT
# matched either - ambiguous with manufacturing/BPO roles. Excludes "call
# quality" (call-centre QA, not software) and "qa/qc" (manufacturing/
# construction quality control) even though "qa" alone would otherwise
# match them.
QA_TITLE_RE = re.compile(
    r"\b(qa|sdet|tester|testers|test engineer|manual testing|software testing|"
    r"automation testing|quality assurance|quality analyst)\b",
    re.IGNORECASE,
)
QA_EXCLUDE_RE = re.compile(r"call quality|qa/qc", re.IGNORECASE)
QA_PATH = "QA & Test Automation"


def is_qa_title(title):
    title = title or ""
    if QA_EXCLUDE_RE.search(title):
        return False
    return bool(QA_TITLE_RE.search(title))


def translate_tags(old_tags):
    new_tags = []
    for old in old_tags:
        for new in OLD_TO_NEW.get(old, [old]):
            if new not in new_tags:
                new_tags.append(new)
    return new_tags


def tag_counts(tag_lists):
    counts = Counter()
    for tags in tag_lists:
        counts.update(tags)
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run, no writes)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = JobListing.query.all()

        before_counts = tag_counts(row.career_paths or [] for row in rows)

        qa_match_titles = Counter()
        not_matched_but_mentions = []  # titles with "test" or "quality" substring, not matched
        planned = []
        for row in rows:
            title = row.job_title or ""
            new_tags = translate_tags(row.career_paths or [])
            matched = is_qa_title(title)
            if matched:
                qa_match_titles[title] += 1
                if QA_PATH not in new_tags:
                    new_tags.append(QA_PATH)
            elif "test" in title.lower() or "quality" in title.lower():
                not_matched_but_mentions.append(title)
            planned.append((row, new_tags))

        after_counts = tag_counts(new_tags for _, new_tags in planned)

        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN (no writes)'}")
        print(f"Total job_listings rows: {len(rows)}")
        print()
        print("BEFORE (old 10-path scheme) tag counts:")
        for p, c in before_counts.most_common():
            print(f"  {c:4d}  {p}")
        print()
        print("AFTER (new 15-path scheme) tag counts:")
        for p in CAREER_PATHS:
            print(f"  {after_counts.get(p, 0):4d}  {p}")
        stray = set(after_counts) - set(CAREER_PATHS)
        if stray:
            print("  UNRECOGNIZED tags still present after translation:", stray)
        total_qa_rows = sum(qa_match_titles.values())
        print()
        print(f"QA-title-pattern matches ({total_qa_rows} rows, {len(qa_match_titles)} distinct titles):")
        for title, count in sorted(qa_match_titles.items()):
            print(f"  {count:3d}x  {title!r}")

        print()
        print(f"Titles containing 'test' or 'quality' that were NOT matched ({len(not_matched_but_mentions)}):")
        for title in sorted(set(not_matched_but_mentions)):
            print(f"  - {title!r}")

        if args.apply:
            for row, new_tags in planned:
                row.career_paths = new_tags
            db.session.commit()
            print()
            print(f"APPLIED: {len(planned)} rows written.")
        else:
            print()
            print("Dry run only - nothing written. Re-run with --apply to write.")


if __name__ == "__main__":
    main()

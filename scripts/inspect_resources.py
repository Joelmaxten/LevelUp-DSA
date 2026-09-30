"""
KB-first resource resolver verification: loads a saved roadmap JSON
(scratch/roadmap_<path>.json, produced by scripts/inspect_roadmap.py) and
runs youtube_resources.fetch_resources_for_roadmap against it entirely
locally - no Flask route, no database read or write. Prints a per-roadmap
report of video/resource resolution: average videos per step, the
0/1/2/3/4+ video-count distribution, the KB video share from topic_refs
vs more_topics, resources per step, and dropped links by reason.

Usage:
    PYTHONPATH=. python scripts/inspect_resources.py <scratch_json_path> [--youtube N] [--show-queries]

--youtube N caps fallback YouTube searches at N (default 0 = KB only, no
network call at all - every search.list call costs 100 YouTube quota
units). --show-queries prints each fallback search's query string and the
videos it returned, for the steps that actually triggered one (capped at
N, in the same phase/step order fetch_resources_for_roadmap uses).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Windows' console defaults to cp1252, which can't encode an emoji in a
# real YouTube video title (observed live) - errors="replace" keeps the
# report printing instead of crashing on one unprintable character.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from app.pipeline.rag import load_index
from app.pipeline.youtube_resources import MIN_VIDEOS, fetch_resources_for_roadmap, resolve_step_from_kb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch_json", help="Path to a scratch/roadmap_<path>.json file")
    parser.add_argument("--youtube", type=int, default=0, help="Max fallback YouTube searches (default 0 = KB only)")
    parser.add_argument("--show-queries", action="store_true", help="Print each fallback query and its returned videos")
    args = parser.parse_args()

    data = json.loads(Path(args.scratch_json).read_text(encoding="utf-8"))
    career_path = data["career_path"]
    roadmap = data["roadmap"]

    index, chunks = load_index("data/processed/faiss_index")
    node_index = {c["node_id"]: c for c in chunks if "node_id" in c}

    # Real resolver call - the authoritative videos/resources per step and
    # overall stats, exactly as production would produce (chunks=None is
    # never used here since we always have the KB loaded).
    enriched, stats = fetch_resources_for_roadmap(roadmap, chunks=chunks, max_fallback_searches=args.youtube)

    # A second, pure/deterministic KB-only pass (no network call - safe to
    # call again) purely to (a) get the topic_refs-vs-more_topics origin
    # split, which resolve_step_from_kb tracks internally but the "videos"
    # dict shape itself doesn't carry, and (b) mirror the real function's
    # own "does this step need a fallback" decision (same MIN_VIDEOS
    # constant, same phase/step order) so --show-queries can report
    # exactly which steps actually triggered the N live searches.
    origin_totals = Counter()
    fallback_trace = []  # (phase, step, query, kb_video_count)
    fallback_attempts_so_far = 0
    for phase in roadmap["phases"]:
        for step in phase["steps"]:
            if not step.get("topic_refs"):
                continue
            kb_videos, _kb_resources, _drop_reasons, origin_counts = resolve_step_from_kb(step, node_index)
            origin_totals.update(origin_counts)
            if len(kb_videos) < MIN_VIDEOS and fallback_attempts_so_far < args.youtube:
                fallback_attempts_so_far += 1
                query = f"{step['title']} {phase['title']} tutorial"
                fallback_trace.append((phase, step, query, len(kb_videos)))

    all_steps = [s for phase in enriched["phases"] for s in phase["steps"]]
    n_steps = len(all_steps)
    video_counts = [len(s.get("videos") or []) for s in all_steps]
    resource_counts = [len(s.get("resources") or []) for s in all_steps]

    print(f"\n{'=' * 90}\n{career_path}  ({args.scratch_json})\n{'=' * 90}")
    print(f"Steps: {n_steps}")

    avg_videos = (sum(video_counts) / n_steps) if n_steps else 0.0
    print(f"Average videos/step: {avg_videos:.2f}")

    bucket_counts = Counter(min(n, 4) for n in video_counts)  # bucket 4 = "4 or more"
    for n in range(5):
        label = str(n) if n < 4 else "4+"
        print(f"  steps with {label} videos: {bucket_counts.get(n, 0)}")

    kb_total = origin_totals["topic_refs"] + origin_totals["more_topics"]
    if kb_total:
        tr_pct = origin_totals["topic_refs"] / kb_total * 100
        mt_pct = origin_totals["more_topics"] / kb_total * 100
        print(f"KB video share: topic_refs {origin_totals['topic_refs']}/{kb_total} ({tr_pct:.1f}%) "
              f"| more_topics {origin_totals['more_topics']}/{kb_total} ({mt_pct:.1f}%)")
    else:
        print("KB video share: no KB videos resolved.")

    avg_resources = (sum(resource_counts) / n_steps) if n_steps else 0.0
    print(f"Average resources/step: {avg_resources:.2f}")

    print(f"\nStats from fetch_resources_for_roadmap: kb_videos_used={stats['kb_videos_used']}, "
          f"fallback_searches_used={stats['fallback_searches_used']}")
    print("Dropped links by reason:")
    if stats["dropped_links_by_reason"]:
        for reason, n in sorted(stats["dropped_links_by_reason"].items(), key=lambda kv: -kv[1]):
            print(f"    {n:4d}  {reason}")
    else:
        print("    (none)")

    steps_under_min = sum(1 for n in video_counts if n < MIN_VIDEOS)
    print(f"\nSteps under MIN_VIDEOS ({MIN_VIDEOS}): {steps_under_min}/{n_steps}")

    if args.show_queries:
        print("\n-- Fallback search queries and results --")
        if not fallback_trace:
            print("  (no fallback searches triggered)")
        step_by_key = {
            (p["phase_number"], s.get("step_number")): s
            for p in enriched["phases"] for s in p["steps"]
        }
        for phase, step, query, kb_video_count in fallback_trace:
            enriched_step = step_by_key.get((phase["phase_number"], step.get("step_number")), step)
            print(f"  Phase {phase['phase_number']} / step {step.get('step_number')}: {step['title']!r} "
                  f"(KB gave {kb_video_count} video(s))")
            print(f"    query: {query!r}")
            found_any = False
            for v in enriched_step.get("videos") or []:
                if v.get("source") == "youtube_search":
                    found_any = True
                    print(f"      -> {v['title']!r}  {v['url']}")
            if not found_any:
                print("      -> (no results returned)")

    print()
    return enriched, stats


if __name__ == "__main__":
    main()

"""
Stage 4 verification: generates one full roadmap for a single career path
using the exact same generate_roadmap() function app/routes/roadmap.py's
/roadmap/generate route calls, with fixed conversation signals, and prints
a diagnostic report (phase/folder composition, coverage, duplicates, raw
node_id leaks, dropped topic_refs, ordering). Read-only: never writes to
the database, never touches an existing file. Saves the full raw
{career_path, roadmap, audit} result as JSON under scratch/ (gitignored).

Folder-per-phase is captured by wrapping (not reimplementing or calling a
second time) roadmap_generator._partition_inventory with a spy during the
one real generate_roadmap() call, so the reported folder composition is
exactly what that specific generation used - not a second, separately
non-deterministic folder-ordering Gemini call that could disagree with it.

Usage:
    PYTHONPATH=. python scripts/inspect_roadmap.py "<career path name>"

If Gemini fails with 429/503 after gemini_client.py's own built-in retry
and fallback, generate_with_retry raises ValueError and this script lets
it propagate (no extra retry loop here) - the caller decides whether to
stop the overall run.
"""
import json
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from app.pipeline.rag import load_index
import app.pipeline.roadmap_generator as rg

FIXED_SIGNALS = {
    "avoid": "repetitive_work",
    "goal": "specific_role",
    "target_company": "product_based",
}

# 21-char nanoid shape roadmap.sh node_ids use - letters, digits, _, -.
NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{21}$")
TITLE_SIMILARITY_THRESHOLD = 0.75

SCRATCH_DIR = Path("scratch")


def looks_like_node_id(s):
    return isinstance(s, str) and bool(NODE_ID_RE.match(s))


def title_similarity(a, b):
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/inspect_roadmap.py "<career path name>"')
        sys.exit(1)
    career_path = sys.argv[1]

    index, chunks = load_index("data/processed/faiss_index")
    node_id_to_folder = {c["node_id"]: c["folder"] for c in chunks if "node_id" in c}

    # Ground-truth pre-generation numbers - pure, deterministic, no Gemini
    # call, safe to compute independently of the real generation below.
    inventory = rg._topic_inventory(career_path, chunks)
    deduped_inventory = rg._dedup_inventory(inventory)
    deduped_size = len(deduped_inventory)
    deduped_by_folder = Counter(t["folder"] for t in deduped_inventory)

    # Spy on _partition_inventory so the phase->folder composition reported
    # below reflects EXACTLY the phase plan the real generation used.
    captured_phase_plan = []
    original_partition = rg._partition_inventory

    def _spy(career_path_arg, inv):
        result = original_partition(career_path_arg, inv)
        captured_phase_plan.append(result)
        return result

    rg._partition_inventory = _spy

    capture_handler = _CaptureHandler()
    rg.logger.addHandler(capture_handler)
    rg.logger.setLevel(logging.WARNING)

    start = time.time()
    try:
        roadmap, audit = rg.generate_roadmap(career_path, FIXED_SIGNALS, index, chunks)
    finally:
        rg._partition_inventory = original_partition
        rg.logger.removeHandler(capture_handler)
    elapsed = time.time() - start

    phase_plan = captured_phase_plan[0] if captured_phase_plan else []
    phase_folder_map = {p["phase_number"]: Counter(t["folder"] for t in p["topics"]) for p in phase_plan}

    phases = roadmap["phases"]

    dropped_ref_warnings = [m for m in capture_handler.records if m.startswith("Dropped invalid topic_ref")]
    subtopic_fix_warnings = [m for m in capture_handler.records if m.startswith("Replaced raw node_id")]
    folder_order_warnings = [m for m in capture_handler.records if "Folder-order response" in m]

    # ---------- Save raw result ----------
    SCRATCH_DIR.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", career_path).strip("_")
    out_path = SCRATCH_DIR / f"roadmap_{safe_name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"career_path": career_path, "roadmap": roadmap, "audit": audit},
            f, indent=2, ensure_ascii=False,
        )

    # ---------- Report ----------
    print(f"\n{'=' * 100}\n{career_path}\n{'=' * 100}")
    print(f"Saved full result to: {out_path}")

    print("\n-- a. Phases (in order) --")
    for p in phases:
        folders = phase_folder_map.get(p["phase_number"], Counter())
        folder_str = ", ".join(f"{f}({n})" for f, n in folders.most_common())
        print(f"  Phase {p['phase_number']}: {p['title']!r} - folders: [{folder_str}] - {len(p['steps'])} steps")

    total_steps = sum(len(p["steps"]) for p in phases)
    print(f"\n-- b. Total steps: {total_steps} | wall-clock: {elapsed:.1f}s --")

    all_refs = set()
    for p in phases:
        for s in p["steps"]:
            all_refs.update(s.get("topic_refs", []))
    coverage_pct = (len(all_refs) / deduped_size * 100) if deduped_size else 0.0
    print(f"\n-- c. Coverage: {len(all_refs)}/{deduped_size} = {coverage_pct:.1f}% --")
    refs_by_folder = Counter(node_id_to_folder.get(r, "UNKNOWN") for r in all_refs)
    for folder, dedup_n in deduped_by_folder.most_common():
        used_n = refs_by_folder.get(folder, 0)
        pct = (used_n / dedup_n * 100) if dedup_n else 0.0
        print(f"    {folder}: {used_n}/{dedup_n} = {pct:.1f}%")

    print("\n-- d. Duplicates --")
    ref_phase_map = defaultdict(set)
    for p in phases:
        for s in p["steps"]:
            for ref in s.get("topic_refs", []):
                ref_phase_map[ref].add(p["phase_number"])
    cross_phase_dupes = {ref: sorted(phs) for ref, phs in ref_phase_map.items() if len(phs) > 1}
    print(f"    node_ids in topic_refs of >1 phase: {cross_phase_dupes or 'none'}")

    all_steps_flat = [(p["phase_number"], s) for p in phases for s in p["steps"]]
    near_dupe_pairs = []
    for i in range(len(all_steps_flat)):
        for j in range(i + 1, len(all_steps_flat)):
            (pi, si), (pj, sj) = all_steps_flat[i], all_steps_flat[j]
            ti, tj = si.get("title", ""), sj.get("title", "")
            sim = title_similarity(ti, tj)
            if ti == tj or sim >= TITLE_SIMILARITY_THRESHOLD:
                near_dupe_pairs.append((pi, ti, pj, tj, sim))
    print(f"    same/near-identical step title pairs (similarity >= {TITLE_SIMILARITY_THRESHOLD}): {len(near_dupe_pairs)}")
    for pi, ti, pj, tj, sim in near_dupe_pairs:
        print(f"      phase {pi} {ti!r}  <->  phase {pj} {tj!r}  (similarity {sim:.2f})")

    print("\n-- e. Raw node_id leaks in subtopics, per phase --")
    total_leaked = 0
    for p in phases:
        leaked = []
        for s in p["steps"]:
            for sub in s.get("subtopics", []):
                if looks_like_node_id(sub):
                    leaked.append((s.get("step_number"), sub))
        total_leaked += len(leaked)
        extra = f" - {leaked}" if leaked else ""
        print(f"    Phase {p['phase_number']} ({p['title']}): {len(leaked)}{extra}")

    print(f"\n-- f. Invalid topic_refs dropped by validation: {len(dropped_ref_warnings)} --")
    for m in dropped_ref_warnings:
        print(f"    {m}")
    if subtopic_fix_warnings:
        print(f"    (also {len(subtopic_fix_warnings)} subtopic node_id->title auto-corrections - see item e)")
    if folder_order_warnings:
        print(f"    Folder-order Gemini response needed a retry/fallback: {folder_order_warnings}")

    print("\n-- g. Phase order (for manual foundational->advanced judgment) --")
    for p in phases:
        folders = phase_folder_map.get(p["phase_number"], Counter())
        print(f"    Phase {p['phase_number']}: {p['title']} - folders: {list(folders.keys())}")

    print("\n-- h. Every step (phase, step#, title, first 3 subtopics, #projects) --")
    for p in phases:
        for s in p["steps"]:
            subtopics = (s.get("subtopics") or [])[:3]
            print(f"    Phase {p['phase_number']} / step {s.get('step_number')}: {s.get('title')!r} "
                  f"| subtopics: {subtopics} | projects: {len(s.get('projects') or [])}")

    print()


if __name__ == "__main__":
    main()

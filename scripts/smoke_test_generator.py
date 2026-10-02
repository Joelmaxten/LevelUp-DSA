"""
Regression test for the roadmap generator (app/pipeline/roadmap_generator.py),
with a deterministic fake LLM (scripts/_fake_llm.py) standing in for Gemini /
Bedrock. No network, no database, no .env values used.

It runs generate_roadmap() for three career paths and compares the complete
output (roadmap + retrieved-chunks audit) with a golden reference saved under
scratch/golden/. The golden files were captured from the generator BEFORE any
speed-up or restructuring, so a refactor that changes any byte of the result
for the same LLM replies fails here.

Usage:
    PYTHONPATH=. python scripts/smoke_test_generator.py
    PYTHONPATH=. python scripts/smoke_test_generator.py --update-golden   # recapture; review the diff!
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

import app.pipeline.roadmap_generator as rg
from app.pipeline import llm_client, rag
from scripts._fake_llm import fake_reply, is_folder_order_prompt, parse_phase_prompt

PATHS = ["Full-Stack Development", "Machine Learning Engineering", "Cybersecurity"]
SIGNALS = {"goal": "any_good_company", "avoid": "repetitive_work", "it_track": "traditional", "target_company": "startup"}
INDEX_PATH = "data/processed/faiss_index"
GOLDEN_DIR = Path("scratch/golden")

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


# What the stub saw: phase title -> {"target": int, "inventory": [node_ids]}, filled from the prompts.
SEEN = {}


def _fake_generate(task, prompt, system=None, schema=None, max_output_tokens=None, json_mode=False):
    """Stands in for llm_client.generate (the generator's only LLM entry point)."""
    if not is_folder_order_prompt(prompt):
        title, target, topics = parse_phase_prompt(prompt)
        SEEN[title] = {"target": target, "inventory": [t[0] for t in topics]}
    return {"text": fake_reply(prompt), "parsed": None, "model_id": "fake", "provider": "fake",
            "input_tokens": None, "output_tokens": None, "latency_s": 0.0, "cost_usd": None,
            "retries": 0, "schema_retry": False}


def stub_llm():
    """Patch llm_client.generate, the call the generator makes."""
    return [patch.object(llm_client, "generate", _fake_generate)]


STEP_KEYS = {"step_number", "title", "description", "topic_refs", "projects", "subtopics", "more_topics", "global_step_index"}
PHASE_KEYS = {"phase_number", "title", "steps"}
AUDIT_PHASE_KEYS = {"phase_number", "title", "queries", "retrieved", "steps"}


def invariants(path, roadmap, audit, expected_topics):
    """Checks every property a valid roadmap must have, independent of the exact wording."""
    phases = roadmap["phases"]
    steps = [s for ph in phases for s in ph["steps"]]
    check(f"{path}: response shape unchanged (roadmap, phase, step and audit keys)",
          set(roadmap) == {"phases"} and set(audit) == {"phases"}
          and all(set(ph) == PHASE_KEYS for ph in phases) and all(set(s) == STEP_KEYS for s in steps)
          and all(set(ap) == AUDIT_PHASE_KEYS for ap in audit["phases"]) and len(audit["phases"]) == len(phases))
    check(f"{path}: phase_number runs 1..N in order", [ph["phase_number"] for ph in phases] == list(range(1, len(phases) + 1)))

    covered = [r for s in steps for r in s["topic_refs"]] + [m["node_id"] for s in steps for m in s["more_topics"]]
    check(f"{path}: every topic is covered at most once (topic_refs + more_topics)", len(covered) == len(set(covered)))
    check(f"{path}: every topic of the path is covered (no topic lost)", set(covered) == expected_topics)

    titles = [s["title"].strip().casefold() for s in steps]
    check(f"{path}: no duplicate step titles across phases", len(titles) == len(set(titles)))
    check(f"{path}: global_step_index is contiguous from 1 in phase order",
          [s["global_step_index"] for s in steps] == list(range(1, len(steps) + 1)))
    check(f"{path}: step_number runs 1..n inside each phase",
          all([s["step_number"] for s in ph["steps"]] == list(range(1, len(ph["steps"]) + 1)) for ph in phases))

    in_allowlist = True
    near_target = True
    for ph in phases:
        seen = SEEN[ph["title"]]
        allowed = set(seen["inventory"])
        for s in ph["steps"]:
            in_allowlist &= set(s["topic_refs"]) <= allowed and {m["node_id"] for m in s["more_topics"]} <= allowed
        near_target &= abs(len(ph["steps"]) - seen["target"]) <= 1
    check(f"{path}: every topic_ref and more_topic is inside its own phase's allowlist", in_allowlist)
    check(f"{path}: step count per phase is within 1 of its target", near_target)
    check(f"{path}: steps carry titles, descriptions, subtopics and 2-3 projects",
          all(s["title"] and s["description"] and s["subtopics"] and 2 <= len(s["projects"]) <= 3 for s in steps))


def warmup_checks():
    """start_warmup(): runs once, honours the flag, survives failures. The loaders are stubbed (no model load)."""
    import time
    from app.config import Config
    from app.pipeline import embedder, warmup
    import app.routes.roadmap as roadmap_routes

    calls = []
    saved_flag, saved_started = Config.WARMUP_ON_START, warmup._started
    try:
        warmup._started = False
        Config.WARMUP_ON_START = False
        check("warm-up: does nothing when WARMUP_ON_START is off", warmup.start_warmup() is None)
        Config.WARMUP_ON_START = True
        with patch.object(embedder, "get_model", lambda: calls.append("model")),                 patch.object(embedder, "embed_chunks", lambda *a, **k: calls.append("encode")),                 patch.object(roadmap_routes, "_get_index", lambda: calls.append("index")):
            thread = warmup.start_warmup()
            check("warm-up: starts a daemon thread", thread is not None and thread.daemon)
            thread.join(5)
            check("warm-up: loads model, first encode and index", calls == ["model", "encode", "index"])
            check("warm-up: a second start in the same process is a no-op", warmup.start_warmup() is None)
        warmup._started = False

        def boom():
            raise RuntimeError("no model")
        with patch.object(embedder, "get_model", boom), patch.object(roadmap_routes, "_get_index", lambda: calls.append("index2")):
            thread = warmup.start_warmup()
            thread.join(5)
            check("warm-up: a failure is swallowed and the next step still runs", "index2" in calls and not thread.is_alive())
    finally:
        Config.WARMUP_ON_START, warmup._started = saved_flag, saved_started


def slug(path):
    return path.replace(" ", "_").replace("&", "and")


def run_path(path, index, chunks):
    SEEN.clear()
    roadmap, audit = rg.generate_roadmap(path, SIGNALS, index, chunks)
    expected = {t["node_id"] for t in rg._dedup_inventory(rg._topic_inventory(path, chunks))}
    return {"career_path": path, "roadmap": roadmap, "audit": audit, "_seen": dict(SEEN), "_expected": expected}


def main():
    update = "--update-golden" in sys.argv
    index, chunks = rag.load_index(INDEX_PATH)

    patches = stub_llm()
    for p in patches:
        p.start()
    try:
        results = {}
        for path in PATHS:
            results[path] = run_path(path, index, chunks)
            SEEN.clear(); SEEN.update(results[path]["_seen"])
            if not update:
                invariants(path, results[path]["roadmap"], results[path]["audit"], results[path]["_expected"])
    finally:
        for p in patches:
            p.stop()

    if not update:
        warmup_checks()
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for path, result in results.items():
        text = json.dumps({k: result[k] for k in ("career_path", "roadmap", "audit")}, ensure_ascii=False)
        golden_file = GOLDEN_DIR / f"golden_{slug(path)}.json"
        if update:
            golden_file.write_text(text, encoding="utf-8")
            print(f"wrote {golden_file} ({len(text):,} chars)")
            continue
        check(f"{path}: golden reference exists", golden_file.exists())
        if golden_file.exists():
            check(f"{path}: output is byte-identical to the golden reference",
                  golden_file.read_text(encoding="utf-8") == text)

    if update:
        return
    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()

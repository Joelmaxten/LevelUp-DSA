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
import threading
import time
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
results_for_dup = None
# Test controls and a log of every call (for the concurrency checks).
CONTROL = {"delay": 0.0, "fail_phase": None, "dup": None}
CALLS = []
INFLIGHT = {"now": 0, "max": 0}
_lock = threading.Lock()


def _apply_dup(record, prompt, text):
    """Optionally plant a duplicate: the seed phase's first step gets seed_title; the dup phase's
    first step gets dup_title for its first `left` replies (so left=1 is fixed by one rewrite)."""
    dup = CONTROL["dup"]
    if not dup or record["kind"] != "phase":
        return text
    steps = json.loads(text)
    if record["title"] == dup["seed_phase"]:
        steps[0]["title"] = dup["seed_title"]
    elif record["title"] == dup["dup_phase"]:
        dup["prompts"].append(prompt)
        if dup["left"] > 0:
            dup["left"] -= 1
            steps[0]["title"] = dup["dup_title"]
    return json.dumps(steps)


def _fake_generate(task, prompt, system=None, schema=None, max_output_tokens=None, json_mode=False):
    """Stands in for llm_client.generate (the generator's only LLM entry point). Thread-safe."""
    import flask
    record = {"thread": threading.current_thread().name, "app_context": flask.has_app_context(),
              "request_context": flask.has_request_context(), "kind": "planner", "title": None,
              "has_plan": "each written separately and at the same time" in prompt,
              "has_exclusion": "EARLIER phases of this same roadmap" in prompt}
    reply = None
    if not is_folder_order_prompt(prompt):
        title, target, topics = parse_phase_prompt(prompt)
        record.update(kind="phase", title=title)
        SEEN[title] = {"target": target, "inventory": [t[0] for t in topics]}
        if CONTROL["fail_phase"] == title:
            reply = "this is not json"
    with _lock:
        CALLS.append(record)
        INFLIGHT["now"] += 1
        INFLIGHT["max"] = max(INFLIGHT["max"], INFLIGHT["now"])
    try:
        if CONTROL["delay"]:
            time.sleep(CONTROL["delay"])
        text = reply if reply is not None else _apply_dup(record, prompt, fake_reply(prompt))
    finally:
        with _lock:
            INFLIGHT["now"] -= 1
    return {"text": text, "parsed": None, "model_id": "fake", "provider": "fake",
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


def run_path(path, index, chunks, concurrency=1):
    SEEN.clear()
    roadmap, audit = rg.generate_roadmap(path, SIGNALS, index, chunks, concurrency=concurrency)
    expected = {t["node_id"] for t in rg._dedup_inventory(rg._topic_inventory(path, chunks))}
    return {"career_path": path, "roadmap": roadmap, "audit": audit, "_seen": dict(SEEN), "_expected": expected}


def as_golden_text(result):
    return json.dumps({k: result[k] for k in ("career_path", "roadmap", "audit")}, ensure_ascii=False)


def concurrency_checks(index, chunks):
    """Things only the parallel path can get wrong: bounds, thread hygiene, prompts, failure handling."""
    import threading
    import flask

    path = "Full-Stack Development"        # 5 phases
    original = (CONTROL["delay"], CONTROL["fail_phase"])
    try:
        # bounded + really parallel
        CONTROL["delay"] = 0.15
        CALLS.clear()
        INFLIGHT.update(now=0, max=0)
        run_path(path, index, chunks, concurrency=3)
        check("concurrency 3: at most 3 phase calls in flight at once", INFLIGHT["max"] <= 3)
        check("concurrency 3: phase calls really overlap (more than 1 in flight)", INFLIGHT["max"] >= 2)
        phase_calls = [c for c in CALLS if c["kind"] == "phase"]
        check("concurrency 3: phase calls run in worker threads, not the main thread",
              phase_calls and all(c["thread"] != threading.main_thread().name for c in phase_calls))
        check("concurrency 3: worker threads have no Flask app or request context",
              all(not c["app_context"] and not c["request_context"] for c in phase_calls))
        check("concurrency 3: the planner call runs first, before any phase call",
              CALLS[0]["kind"] == "planner" and all(c["kind"] == "phase" for c in CALLS[1:]))
        check("concurrency 3: each phase prompt carries the full plan, not an earlier-phases list",
              all(c["has_plan"] and not c["has_exclusion"] for c in phase_calls))
        CONTROL["delay"] = 0
        CALLS.clear()
        run_path(path, index, chunks, concurrency=1)
        later = [c for c in CALLS if c["kind"] == "phase"][1:]
        check("concurrency 1: later phases get the earlier-steps exclusion block, no plan block",
              later and all(c["has_exclusion"] and not c["has_plan"] for c in later))

        # one phase fails twice -> same ValueError as today, only that phase retried
        for conc in (1, 3):
            CALLS.clear()
            CONTROL["fail_phase"] = "JavaScript"
            try:
                run_path(path, index, chunks, concurrency=conc)
                err = None
            except ValueError as exc:
                err = exc
            per_phase = {}
            for c in CALLS:
                if c["kind"] == "phase":
                    per_phase[c["title"]] = per_phase.get(c["title"], 0) + 1
            check(f"concurrency {conc}: a phase that stays invalid raises the usual ValueError",
                  err is not None and "invalid JSON for phase 'JavaScript' after retry" in str(err))
            check(f"concurrency {conc}: only the failing phase was retried (2 calls), every other phase called at most once",
                  per_phase.get("JavaScript") == 2 and all(n == 1 for t, n in per_phase.items() if t != "JavaScript"))
        CONTROL["fail_phase"] = None
    finally:
        CONTROL["delay"], CONTROL["fail_phase"] = original


def duplicate_checks(index, chunks):
    """The cross-phase duplicate check: finder behavior and the rewrite-once policy, at concurrency 1 and 3."""
    import logging
    path = "Full-Stack Development"

    raw = [[{"title": "Introduction to Git"}], [{"title": "Git Basics"}, {"title": "Docker volumes"}, {"title": "git basics!"}]]
    found = rg._find_duplicates(raw, 1, 0.80)
    check("finder: a paraphrase and a punctuation-only variant are flagged, an unrelated title is not",
          sorted(d["step"] for d in found) == [0, 2])
    check("finder: steps inside one phase are never compared with each other",
          rg._find_duplicates([[{"title": "Same title"}, {"title": "Same title"}]], 0, 0.80) == [])
    check("finder: nothing is flagged for the first phase or for empty input",
          rg._find_duplicates([[{"title": "A"}]], 0, 0.80) == [] and rg._find_duplicates([[], [{"title": "B"}]], 1, 0.80) == [])

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())
    handler = Capture()
    logger = logging.getLogger("app.pipeline.roadmap_generator")
    logger.addHandler(handler)
    try:
        for conc in (1, 3):
            base = {"seed_phase": "Git & GitHub", "seed_title": "Introduction to Git", "dup_phase": "JavaScript", "prompts": []}

            # a paraphrased duplicate, fixed by ONE rewrite of the later phase only
            CONTROL["dup"] = {**base, "dup_title": "Git Basics", "left": 1, "prompts": []}
            CALLS.clear(); records.clear()
            result = run_path(path, index, chunks, concurrency=conc)
            per_phase = {}
            for c in CALLS:
                if c["kind"] == "phase":
                    per_phase[c["title"]] = per_phase.get(c["title"], 0) + 1
            prompts = CONTROL["dup"]["prompts"]
            check(f"duplicates, concurrency {conc}: only the later phase is regenerated, once",
                  per_phase.get("JavaScript") == 2 and all(n == 1 for t, n in per_phase.items() if t != "JavaScript"))
            check(f"duplicates, concurrency {conc}: the rewrite prompt lists the earlier titles as an exclusion list",
                  len(prompts) == 2 and "REWRITE NOTICE" not in prompts[0]
                  and "REWRITE NOTICE" in prompts[1] and "Introduction to Git" in prompts[1])
            titles = [s["title"].casefold() for ph in result["roadmap"]["phases"] for s in ph["steps"]]
            check(f"duplicates, concurrency {conc}: the rewritten roadmap no longer repeats the step", "git basics" not in titles)
            invariants(f"duplicates, concurrency {conc}", result["roadmap"], result["audit"], result["_expected"])

            # still duplicated after the rewrite: kept, warned about, nothing dropped
            CONTROL["dup"] = {**base, "dup_title": "Git Basics", "left": 2, "prompts": []}
            CALLS.clear(); records.clear()
            kept = run_path(path, index, chunks, concurrency=conc)
            js = next(ph for ph in kept["roadmap"]["phases"] if ph["title"] == "JavaScript")
            normal_len = len(next(ph for ph in results_for_dup["roadmap"]["phases"] if ph["title"] == "JavaScript")["steps"])
            check(f"duplicates, concurrency {conc}: still duplicated after one rewrite -> the step is kept and a warning logged",
                  js["steps"][0]["title"] == "Git Basics" and any("Kept a step" in m for m in records)
                  and len(js["steps"]) == normal_len)
            check(f"duplicates, concurrency {conc}: no further rewrite after the first",
                  sum(1 for c in CALLS if c["kind"] == "phase" and c["title"] == "JavaScript") == 2)

            # identical title up to case/punctuation
            CONTROL["dup"] = {**base, "dup_title": "introduction to git!", "left": 1, "prompts": []}
            CALLS.clear()
            run_path(path, index, chunks, concurrency=conc)
            check(f"duplicates, concurrency {conc}: a title equal after normalising is caught",
                  sum(1 for c in CALLS if c["kind"] == "phase" and c["title"] == "JavaScript") == 2)
        CONTROL["dup"] = None
        CALLS.clear()
        run_path(path, index, chunks, concurrency=1)
        check("no duplicates in the normal output -> no phase is called twice",
              all(n == 1 for n in [sum(1 for c in CALLS if c["kind"] == "phase" and c["title"] == t) for t in {c["title"] for c in CALLS if c["kind"] == "phase"}]))
    finally:
        logger.removeHandler(handler)
        CONTROL["dup"] = None


def main():
    update = "--update-golden" in sys.argv
    index, chunks = rag.load_index(INDEX_PATH)

    patches = stub_llm()
    for p in patches:
        p.start()
    try:
        results, parallel = {}, {}
        for path in PATHS:
            results[path] = run_path(path, index, chunks, concurrency=1)
            SEEN.clear(); SEEN.update(results[path]["_seen"])
            if not update:
                invariants(path, results[path]["roadmap"], results[path]["audit"], results[path]["_expected"])
        if not update:
            for path in PATHS:
                parallel[path] = run_path(path, index, chunks, concurrency=3)
                SEEN.clear(); SEEN.update(parallel[path]["_seen"])
                invariants(f"{path} [concurrency 3]", parallel[path]["roadmap"], parallel[path]["audit"], parallel[path]["_expected"])
            concurrency_checks(index, chunks)
            global results_for_dup
            results_for_dup = results["Full-Stack Development"]
            duplicate_checks(index, chunks)
    finally:
        for p in patches:
            p.stop()

    if not update:
        warmup_checks()
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for path, result in results.items():
        text = as_golden_text(result)
        golden_file = GOLDEN_DIR / f"golden_{slug(path)}.json"
        if update:
            golden_file.write_text(text, encoding="utf-8")
            print(f"wrote {golden_file} ({len(text):,} chars)")
            continue
        check(f"{path}: golden reference exists", golden_file.exists())
        if golden_file.exists():
            check(f"{path}: output is byte-identical to the golden reference",
                  golden_file.read_text(encoding="utf-8") == text)
            check(f"{path}: concurrency 3 gives the same phase/step structure (the fake's replies don't depend on context, so it is identical)",
                  as_golden_text(parallel[path]) == text)

    if update:
        return
    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()

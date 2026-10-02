"""
How much faster does roadmap generation get with parallel phase writers?

Runs generate_roadmap() for three career paths at PHASE_CONCURRENCY 1 and 3 with a
STUB LLM that just sleeps --delay seconds per call (default 3, a stand-in for real
model latency) and returns valid replies built from the prompt. So the wall-clock
difference is exactly what overlapping the phase calls buys, and the local columns
(retrieval, post-processing, duplicate check) are the real CPU work. The duplicate
check still runs (so its cost is shown) but its threshold is set above 1 so the fake's
repeated KB topic names never trigger a rewrite call. No network, no
credentials, no database.

Usage:
    PYTHONPATH=. python scripts/benchmark_generator.py [--delay 3] [--paths "Full-Stack Development,Cybersecurity"]

Writes scratch/benchmark_generator.csv and prints the same table.
"""
import argparse
import csv
import time
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

import app.pipeline.roadmap_generator as rg
from app.pipeline import embedder, llm_client, rag
from scripts._fake_llm import fake_reply

DEFAULT_PATHS = ["Full-Stack Development", "Machine Learning Engineering", "Cybersecurity"]
SIGNALS = {"goal": "any_good_company", "avoid": "repetitive_work", "it_track": "traditional", "target_company": "startup"}
OUT_CSV = Path("scratch/benchmark_generator.csv")
CONCURRENCIES = (1, 3)
FIELDS = ["career_path", "phases", "concurrency", "llm_delay_s", "llm_calls", "wall_s", "speedup_vs_1",
          "planner_s", "retrieval_s", "post_processing_s", "duplicate_check_s", "local_total_s"]


def make_stub(delay, counter):
    def stub(task, prompt, system=None, schema=None, max_output_tokens=None, json_mode=False):
        counter.append(1)
        time.sleep(delay)
        return {"text": fake_reply(prompt), "parsed": None, "model_id": "stub", "provider": "stub",
                "input_tokens": None, "output_tokens": None, "latency_s": delay, "cost_usd": None,
                "retries": 0, "schema_retry": False}
    return stub


def total_of(timings, marker):
    return sum(seconds for name, seconds in timings if marker in name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=3.0, help="seconds each stubbed LLM call takes")
    parser.add_argument("--paths", default=",".join(DEFAULT_PATHS))
    args = parser.parse_args()
    paths = [p.strip() for p in args.paths.split(",") if p.strip()]

    index, chunks = rag.load_index("data/processed/faiss_index")
    started = time.perf_counter()
    embedder.get_model()
    embedder.embed_chunks([{"text": "warm"}], show_progress=False)
    print(f"(embedding model loaded in {time.perf_counter() - started:.1f}s - one-time cost, excluded from the table)\n")

    rows = []
    for path in paths:
        baseline = None
        for concurrency in CONCURRENCIES:
            calls, timings = [], []
            with patch.object(llm_client, "generate", make_stub(args.delay, calls)):
                t = time.perf_counter()
                roadmap, _ = rg.generate_roadmap(path, SIGNALS, index, chunks, timings=timings, concurrency=concurrency,
                                                 duplicate_threshold=1.01)   # no embedding matches: the fake's titles share KB topic names, and a rewrite would add a call and blur the comparison
                wall = time.perf_counter() - t
            baseline = wall if baseline is None else baseline
            local = (total_of(timings, "retrieval") + total_of(timings, "post-processing") + total_of(timings, "duplicate check"))
            rows.append({
                "career_path": path, "phases": len(roadmap["phases"]), "concurrency": concurrency,
                "llm_delay_s": args.delay, "llm_calls": len(calls), "wall_s": round(wall, 2),
                "speedup_vs_1": round(baseline / wall, 2),
                "planner_s": round(total_of(timings, "plan ("), 2), "retrieval_s": round(total_of(timings, "retrieval"), 2),
                "post_processing_s": round(total_of(timings, "post-processing"), 2),
                "duplicate_check_s": round(total_of(timings, "duplicate check"), 2), "local_total_s": round(local, 2),
            })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    header = f"{'career path':<30} {'phases':>6} {'conc.':>5} {'calls':>5} {'wall s':>7} {'speedup':>8} {'planner':>8} {'retrieval':>10} {'post-proc':>10} {'dup chk':>8} {'local':>7}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['career_path']:<30} {r['phases']:>6} {r['concurrency']:>5} {r['llm_calls']:>5} {r['wall_s']:>7.2f} "
              f"{r['speedup_vs_1']:>7.2f}x {r['planner_s']:>8.2f} {r['retrieval_s']:>10.2f} {r['post_processing_s']:>10.2f} "
              f"{r['duplicate_check_s']:>8.2f} {r['local_total_s']:>7.2f}")
    print(f"\nStub LLM delay: {args.delay}s per call. Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()

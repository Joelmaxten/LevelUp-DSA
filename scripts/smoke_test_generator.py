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
from app.pipeline import gemini_client, rag
from scripts._fake_llm import fake_reply

PATHS = ["Full-Stack Development", "Machine Learning Engineering", "Cybersecurity"]
SIGNALS = {"goal": "any_good_company", "avoid": "repetitive_work", "it_track": "traditional", "target_company": "startup"}
INDEX_PATH = "data/processed/faiss_index"
GOLDEN_DIR = Path("scratch/golden")

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def _fake_gemini(prompt, max_output_tokens=None, json_mode=False, **kwargs):
    return fake_reply(prompt)


def stub_llm():
    """Patch the call the generator makes today (gemini_client.generate_with_retry)."""
    patches = [patch.object(gemini_client, "generate_with_retry", _fake_gemini)]
    if hasattr(rg, "generate_with_retry"):
        patches.append(patch.object(rg, "generate_with_retry", _fake_gemini))
    return patches


def slug(path):
    return path.replace(" ", "_").replace("&", "and")


def run_path(path, index, chunks):
    roadmap, audit = rg.generate_roadmap(path, SIGNALS, index, chunks)
    return {"career_path": path, "roadmap": roadmap, "audit": audit}


def main():
    update = "--update-golden" in sys.argv
    index, chunks = rag.load_index(INDEX_PATH)

    patches = stub_llm()
    for p in patches:
        p.start()
    try:
        results = {path: run_path(path, index, chunks) for path in PATHS}
    finally:
        for p in patches:
            p.stop()

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for path, result in results.items():
        text = json.dumps(result, ensure_ascii=False)
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

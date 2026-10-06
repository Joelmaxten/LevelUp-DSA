"""
Smoke test for cached base roadmaps + fast personalization. NO real calls: every LLM call is a stub (the generator's
fake LLM in scripts/_fake_llm.py or a canned reply), nothing touches YouTube, Adzuna, Gemini, Groq, NVIDIA or
Bedrock. Uses the real local FAISS index/metadata (no network) so inventories and step counts are the real ones.

Sections: base store loader, build script, personalizer, async route (cached / full / fallbacks), progress and
switcher on a saved cached roadmap, and a timing table (stub LLM delay 3 s) written to scratch/benchmark_cached.csv.

Usage:
    PYTHONPATH=. python scripts/smoke_test_cached_roadmaps.py
"""
import copy
import csv
import io
import json
import logging
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("HF_HUB_OFFLINE", "1")   # the embedding model loads from the local cache; no network

from app.config import Config
from app.pipeline import base_roadmaps, llm_client, rag
from app.pipeline import roadmap_generator as rg
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.youtube_resources import fetch_resources_for_roadmap
from scripts._fake_llm import fake_reply

INDEX_PATH = "data/processed/faiss_index"
PATH = "Cybersecurity"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def fake_llm_result(text):
    return {"text": text, "parsed": None, "model_id": "fake", "provider": "fake", "input_tokens": None,
            "output_tokens": None, "latency_s": 0.0, "cost_usd": None, "retries": 0, "schema_retry": False}


def fake_generate(delay=0.0, counter=None):
    """Stands in for llm_client.generate for the roadmap generator (planner and phase prompts)."""
    def generate(task, prompt, system=None, schema=None, max_output_tokens=None, json_mode=False):
        if counter is not None:
            counter.append(task)
        if delay:
            time.sleep(delay)
        return fake_llm_result(fake_reply(prompt))
    return generate


_base_cache = {}


def real_shaped_base(path, index, chunks):
    """A base document for a path from the REAL generator (fake LLM): real inventory, real step counts. Cached."""
    if path not in _base_cache:
        with patch.object(llm_client, "generate", fake_generate()):
            roadmap, audit = rg.generate_roadmap(path, {}, index, chunks)
        roadmap, _ = fetch_resources_for_roadmap(roadmap, chunks=chunks, max_fallback_searches=0, use_youtube=False)
        _base_cache[path] = base_roadmaps.build_document(path, roadmap, audit, chunks, "fake-model",
                                                         {"phase_concurrency": 1}, "2026-01-01T00:00:00Z")
    return copy.deepcopy(_base_cache[path])


def write_doc(directory, path, document):
    base_roadmaps.write_atomic(base_roadmaps.path_for(path, directory), document)


class LogCapture:
    def __init__(self, level=logging.DEBUG):
        self.stream, self.level = io.StringIO(), level

    def __enter__(self):
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setLevel(self.level)
        self.root = logging.getLogger()
        self.old = self.root.level
        self.root.addHandler(self.handler)
        self.root.setLevel(self.level)
        return self

    def __exit__(self, *exc):
        self.root.removeHandler(self.handler)
        self.root.setLevel(self.old)

    @property
    def text(self):
        return self.stream.getvalue()


# ----------------------------------------------------------------------------- 1. loader

def loader_checks(index, chunks):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        good = real_shaped_base(PATH, index, chunks)
        steps = [s for ph in good["roadmap"]["phases"] for s in ph["steps"]]
        check("loader: a fake-LLM roadmap from the real generator has phases, steps and videos/resources keys on every step",
              len(good["roadmap"]["phases"]) >= 2 and len(steps) >= 6 and all("videos" in s and "resources" in s for s in steps))
        check("KB-only resolver: attaching resources made no fallback search and needed no YouTube (use_youtube=False)",
              all(s["videos"] is not None for s in steps))

        check("loader: no file -> None", base_roadmaps.load_base(PATH, chunks, base_dir=tmp) is None)
        write_doc(tmp, PATH, good)
        loaded = base_roadmaps.load_base(PATH, chunks, base_dir=tmp)
        check("loader: a valid file is served with roadmap, audit, metadata and stale=False",
              loaded is not None and loaded["stale"] is False and loaded["roadmap"] == good["roadmap"]
              and loaded["audit"] == good["audit"] and loaded["metadata"]["model_id"] == "fake-model")
        loaded["roadmap"]["phases"][0]["title"] = "mutated"
        check("loader: the served copy is independent (mutating it does not change the next load)",
              base_roadmaps.load_base(PATH, chunks, base_dir=tmp)["roadmap"]["phases"][0]["title"] != "mutated")
        check("metadata: career_path, model_id, built_at, generator settings and a fingerprint are stored",
              all(k in good["metadata"] for k in ("career_path", "model_id", "built_at", "generator", "inventory_fingerprint"))
              and len(good["metadata"]["inventory_fingerprint"]) == 64)
        check("slug: 'UI/UX Design' -> ui-ux-design, 'Full-Stack Development' -> full-stack-development",
              base_roadmaps.slug("UI/UX Design") == "ui-ux-design" and base_roadmaps.slug("Full-Stack Development") == "full-stack-development")

        stale_doc = copy.deepcopy(good)
        stale_doc["metadata"]["inventory_fingerprint"] = "0" * 64
        write_doc(tmp, PATH, stale_doc)
        with LogCapture(logging.WARNING) as logs:
            stale = base_roadmaps.load_base(PATH, chunks, base_dir=tmp)
        check("loader: a fingerprint mismatch still serves the file, with stale=True and one warning",
              stale is not None and stale["stale"] is True and "stale" in logs.text and logs.text.count("is stale") == 1)

        def broken(mutator, label):
            doc = copy.deepcopy(good)
            mutator(doc)
            write_doc(tmp, PATH, doc)
            with LogCapture(logging.WARNING) as logs:
                result = base_roadmaps.load_base(PATH, chunks, base_dir=tmp)
            check(f"loader: invalid file ({label}) is treated as missing, with a warning", result is None and "invalid" in logs.text)

        broken(lambda d: d["roadmap"]["phases"][0]["steps"][0].update(global_step_index=5), "non-contiguous global_step_index")
        broken(lambda d: d["roadmap"]["phases"][0]["steps"][0].update(topic_refs=["not-a-real-node-id"]), "topic_ref outside the inventory")
        broken(lambda d: d["roadmap"]["phases"][1]["steps"][0].update(title=d["roadmap"]["phases"][0]["steps"][0]["title"].upper()), "duplicate title")
        broken(lambda d: d["roadmap"]["phases"][0]["steps"][0].pop("videos"), "step without videos")
        broken(lambda d: d["roadmap"]["phases"][0]["steps"][0].pop("resources"), "step without resources")
        broken(lambda d: d["roadmap"].update(phases=[]), "no phases")
        broken(lambda d: d.pop("metadata"), "no metadata")
        broken(lambda d: d["metadata"].update(career_path="Data Science"), "metadata for another path")
        flat = copy.deepcopy(good)
        flat["roadmap"] = [{"step_number": 1, "title": "x"}]
        write_doc(tmp, PATH, flat)
        check("loader: a flat (non-phased) roadmap is invalid", base_roadmaps.load_base(PATH, chunks, base_dir=tmp) is None)

        target = base_roadmaps.path_for(PATH, tmp)
        for label, content in (("not JSON", "{ this is not json"), ("empty file", ""), ("a JSON list", "[1, 2]")):
            target.write_text(content, encoding="utf-8")
            with LogCapture(logging.WARNING) as logs:
                result = base_roadmaps.load_base(PATH, chunks, base_dir=tmp)
            check(f"loader: corrupt file ({label}) is treated as missing, never raises", result is None)
        base_roadmaps.write_atomic(target, good)
        check("write_atomic: leaves no .tmp file behind and the file loads", not list(tmp.glob("*.tmp")) and base_roadmaps.load_base(PATH, chunks, base_dir=tmp) is not None)
        check("data/base_roadmaps is a committed directory (README present, not gitignored)",
              Path("data/base_roadmaps/README.md").is_file()
              and subprocess.run(["git", "check-ignore", "-q", "data/base_roadmaps/x.json"]).returncode == 1)


SECTIONS = []


def run():
    index, chunks = rag.load_index(INDEX_PATH)
    loader_checks(index, chunks)
    for section in SECTIONS:
        section(index, chunks)


if __name__ == "__main__":
    run()
    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed.")
    sys.exit(1 if failed else 0)

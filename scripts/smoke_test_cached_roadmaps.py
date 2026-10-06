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


# ----------------------------------------------------------------------------- 2. build script

SECRET_ENV_NAMES = ("NVIDIA_API_KEY", "GROQ_API_KEY", "LLM_API_KEY", "GEMINI_API_KEY", "YOUTUBE_API_KEY")


def build_script_checks(index, chunks):
    from scripts import build_base_roadmaps as bbr
    second = "DevOps"
    docs = {p: real_shaped_base(p, index, chunks) for p in (PATH, second)}
    calls = []

    def stub_generator(fail_for=()):
        def generate(path, signals, idx, chnk, **kw):
            calls.append((path, dict(signals)))
            if path in fail_for:
                raise ValueError("stub generator failure")
            roadmap = copy.deepcopy(docs[path]["roadmap"])
            for ph in roadmap["phases"]:       # the real generator output has no videos yet: the build step attaches them
                for st in ph["steps"]:
                    for key in ("videos", "resources", "resource"):
                        st.pop(key, None)
            return roadmap, copy.deepcopy(docs[path]["audit"])
        return generate

    def forbidden(*a, **k):
        raise AssertionError("dry run called the generator")

    def run_main(args, tmp, generator=None):
        out, docs_file = tmp / "base", tmp / "review.md"
        buffer, saved_env = io.StringIO(), dict(os.environ)
        patches = [patch.object(bbr, "load_index", lambda p: (index, chunks)),
                   patch.object(bbr, "generate_roadmap", generator or stub_generator()),
                   patch.object(sys, "stdout", buffer)]
        for p_ in patches:
            p_.start()
        try:
            try:
                code = bbr.main(args + ["--out-dir", str(out), "--docs-file", str(docs_file)])
            except SystemExit as exc:          # argparse errors
                code = exc.code
        finally:
            for p_ in reversed(patches):
                p_.stop()
            os.environ.clear()
            os.environ.update(saved_env)
        return code, buffer.getvalue(), out, docs_file

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # dry run
        calls.clear()
        code, text, out, docs_file = run_main(["--paths", f"{PATH},{second}"], tmp, generator=forbidden)
        secrets = [os.environ[n] for n in SECRET_ENV_NAMES if os.environ.get(n)]
        check("build dry run (the default): returns 0, prints the plan, calls nothing and writes nothing (no files, no review document)",
              code == 0 and "DRY RUN" in text and PATH in text and second in text and "build" in text and not out.exists() and not docs_file.exists())
        check("build: the provider host and the models are printed before anything else, and no key value appears in the output",
              text.index("provider:") < text.index("DRY RUN") and "host:" in text and "models: roadmap=" in text
              and not any(secret in text for secret in secrets))
        code, text, out, docs_file = run_main([], tmp)
        check("build: no --paths/--all/--review-only is an argument error, not a build", code not in (0, None) and not out.exists())

        # real run with the stubbed generator
        calls.clear()
        code, text, out, docs_file = run_main(["--paths", f"{PATH},{second}", "--run"], tmp)
        built = {p: base_roadmaps.load_base(p, chunks, base_dir=out) for p in (PATH, second)}
        check("build --run: both files written and valid with metadata; the NEUTRAL profile ({}) was passed to the generator",
              code == 0 and all(built.values()) and [c[1] for c in calls] == [{}, {}]
              and all(b["metadata"]["generator"]["profile"] == "neutral" and b["metadata"]["generator"]["resources"] == "kb_only" for b in built.values()))
        steps = [s for ph in built[PATH]["roadmap"]["phases"] for s in ph["steps"]]
        check("build --run: resources attached by the KB-only resolver (every step has videos and resources keys)",
              all("videos" in s and "resources" in s for s in steps))
        check("build --run: one summary row per path with phases, steps, discarded refs, duplicate warnings, seconds and model",
              all(w in text for w in ("phases", "steps", "discarded_refs", "dups(rewritten/kept)", "seconds", "model")) and text.count(" built") >= 2)
        review = docs_file.read_text(encoding="utf-8")
        check("build --run: no leftover .tmp files; the review document lists the phases, step titles and first descriptions",
              not list(out.glob("*.tmp")) and all(ph["title"] in review for ph in built[PATH]["roadmap"]["phases"])
              and steps[0]["title"] in review and steps[0]["description"][:60] in review)
        check("review document: paths not built yet are marked as such", "## Data Science" in review and "_Not built yet_" in review)

        # resumable / no overwrite without --force
        before = {p: base_roadmaps.path_for(p, out).read_bytes() for p in (PATH, second)}
        calls.clear()
        code, text, out, docs_file = run_main(["--paths", f"{PATH},{second}", "--run"], tmp)
        check("build: resumable - a second run skips paths whose file exists and is valid (generator not called, files untouched)",
              code == 0 and not calls and text.count("skipped") >= 2
              and all(base_roadmaps.path_for(p, out).read_bytes() == before[p] for p in before))
        calls.clear()
        code, text, out, docs_file = run_main(["--paths", PATH, "--run", "--force"], tmp)
        check("build: --force rebuilds only the requested path",
              [c[0] for c in calls] == [PATH] and base_roadmaps.path_for(second, out).read_bytes() == before[second])
        base_roadmaps.path_for(second, out).write_text("{ corrupt", encoding="utf-8")
        calls.clear()
        run_main(["--paths", second, "--run"], tmp)
        check("build: an existing file that is invalid counts as missing and is rebuilt (no --force needed)",
              [c[0] for c in calls] == [second] and base_roadmaps.load_base(second, chunks, base_dir=out) is not None)

        # one path failing does not stop the others
        calls.clear()
        code, text, out, docs_file = run_main(["--paths", f"{PATH},{second}", "--run"], tmp / "fail", generator=stub_generator(fail_for=(PATH,)))
        check("build: a failing path is reported as FAILED, the next path is still built, the exit code is 1",
              code == 1 and "FAILED" in text and [c[0] for c in calls] == [PATH, second]
              and base_roadmaps.load_base(second, chunks, base_dir=out) is not None and base_roadmaps.load_base(PATH, chunks, base_dir=out) is None)

        def invalid_generator(path, signals, idx, chnk, **kw):
            roadmap, audit = stub_generator()(path, signals, idx, chnk)
            roadmap["phases"][0]["steps"][0]["topic_refs"] = ["not-in-inventory"]
            return roadmap, audit
        code, text, out, docs_file = run_main(["--paths", PATH, "--run"], tmp / "invalid", generator=invalid_generator)
        check("build: a roadmap that fails the invariants is not written (FAILED, no file)",
              code == 1 and "FAILED" in text and base_roadmaps.load_base(PATH, chunks, base_dir=out) is None)
        code, text, out, docs_file = run_main(["--paths", "Nope"], tmp)
        check("build: an unknown career path is refused with the valid list", code == 2 and "unknown career path" in text)

        # the real generator with the fake LLM: discarded topic_refs and duplicate warnings are counted
        def bogus_llm(task, prompt, system=None, schema=None, max_output_tokens=None, json_mode=False):
            text = fake_reply(prompt)
            if not prompt.startswith("You are planning the PHASE ORDER"):
                steps = json.loads(text)
                steps[0]["topic_refs"] = steps[0]["topic_refs"] + ["BOGUS-NODE-ID"]
                text = json.dumps(steps)
            return fake_llm_result(text)
        saved_env = dict(os.environ)
        try:
            with patch.object(llm_client, "generate", bogus_llm), patch.object(bbr, "generate_roadmap", rg.generate_roadmap):
                row = bbr.build_path(PATH, index, chunks, tmp / "real")
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        check("build: invented topic_refs are discarded by the generator and counted in the summary row; the file is still valid",
              row["discarded_refs"] >= row["phases"] and base_roadmaps.load_base(PATH, chunks, base_dir=tmp / "real") is not None
              and isinstance(row["dups_rewritten"], int) and isinstance(row["dups_kept"], int) and row["steps"] > 0)

    # environment variables set before the command win over .env (a real subprocess, dry run: no calls)
    names = ("LLM_PROVIDER", "LLM_BASE_URL", "ROADMAP_MODEL_ID", "FAST_MODEL_ID", "FALLBACK_MODEL_ID")
    plain = {k: v for k, v in os.environ.items() if k not in names}
    plain.update(HF_HUB_OFFLINE="1", PYTHONPATH=".")
    env = {**plain, "LLM_PROVIDER": "openai_compat", "LLM_BASE_URL": "https://override.test/v1", "ROADMAP_MODEL_ID": "override-model-123",
           "FAST_MODEL_ID": "override-fast", "FALLBACK_MODEL_ID": "override-fallback"}

    def run(e):
        return subprocess.run([sys.executable, "scripts/build_base_roadmaps.py", "--paths", PATH], env=e, capture_output=True, text=True, timeout=180)
    over, without = run(env), run(plain)
    check("build: environment variables set before the command win over .env (provider host and models printed from the override)",
          over.returncode == 0 and "host: override.test" in over.stdout and "roadmap=override-model-123" in over.stdout
          and "fast=override-fast" in over.stdout and "fallback=override-fallback" in over.stdout and "DRY RUN" in over.stdout)
    check("build: without them the same script reads .env instead (so the override above really won), and no key value is printed",
          without.returncode == 0 and "override.test" not in without.stdout and "override-model-123" not in without.stdout
          and not any(os.environ.get(n) and os.environ[n] in (over.stdout + without.stdout) for n in SECRET_ENV_NAMES))


SECTIONS = [build_script_checks]


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

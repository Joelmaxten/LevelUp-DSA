"""
Compare the models you have configured on the two LLM jobs the app does: one
roadmap phase and one resume feedback, for 5 fixed sample student profiles.

DRY RUN BY DEFAULT: prints what would be run (profiles, tasks, models, number
of calls) and makes no call and loads nothing. Pass --run to make REAL calls
to the configured provider - that spends quota/money, so it is never part of
any smoke test. Results go to scratch/benchmark_results.csv: whether the
reply passed the schema on the first try, retries, latency, tokens and cost
(cost is empty unless prices are set in config.PRICE_PER_MTOK).

Models compared = the distinct non-empty ROADMAP_MODEL_ID / FAST_MODEL_ID /
FALLBACK_MODEL_ID values (with the gemini provider and none set, the built-in
default model). Each model is run alone: no fallback model, no provider switch.

Usage:
    PYTHONPATH=. python scripts/benchmark_llm.py            # plan only
    PYTHONPATH=. python scripts/benchmark_llm.py --run      # real calls
"""
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from app.config import Config

OUT_CSV = Path("scratch/benchmark_results.csv")
CSV_FIELDS = ["profile", "task", "model_id", "provider", "ok", "first_try_schema_pass", "retries",
              "latency_s", "input_tokens", "output_tokens", "cost_usd", "error_kind"]

PROFILES = [
    {"name": "fresher_fullstack", "career_path": "Full-Stack Development",
     "signals": {"goal": "any_good_company", "avoid": "repetitive_work", "target_company": "startup"},
     "resume": "BTech CSE 2026. Skills: Python, JavaScript, HTML, CSS, Git. Project: personal portfolio site."},
    {"name": "ml_curious", "career_path": "Machine Learning Engineering",
     "signals": {"goal": "high_salary", "avoid": "repetitive_work", "target_company": "product"},
     "resume": "BTech ECE 2025. Skills: Python, NumPy, pandas, scikit-learn. Project: house price predictor."},
    {"name": "security_minded", "career_path": "Cybersecurity",
     "signals": {"goal": "any_good_company", "avoid": "constant_deadlines", "target_company": "mnc"},
     "resume": "BSc IT 2026. Skills: Linux, networking basics, Python scripting. Completed a CTF course."},
    {"name": "data_analyst", "career_path": "Data Analytics",
     "signals": {"goal": "stable_job", "avoid": "repetitive_work", "target_company": "mnc"},
     "resume": "BCom 2025. Skills: Excel, SQL basics, Power BI dashboards. Internship: sales reporting."},
    {"name": "devops_switcher", "career_path": "DevOps",
     "signals": {"goal": "high_salary", "avoid": "constant_deadlines", "target_company": "startup"},
     "resume": "2 years IT support. Skills: Linux, Bash, Docker basics, Git. Wants to move into DevOps."},
]

ROADMAP_STEP_SCHEMA = {
    "type": "array", "minItems": 1,
    "items": {"type": "object", "required": ["title", "description", "topic_refs", "projects"],
              "properties": {"title": {"type": "string"}, "description": {"type": "string"},
                             "topic_refs": {"type": "array", "items": {"type": "string"}},
                             "projects": {"type": "array"}}},
}


def configured_models():
    ids = []
    for name in ("ROADMAP_MODEL_ID", "FAST_MODEL_ID", "FALLBACK_MODEL_ID"):
        value = getattr(Config, name, "")
        if value and value not in ids:
            ids.append(value)
    if not ids and Config.LLM_PROVIDER == "gemini":
        ids = [None]    # None = gemini_client's built-in default model
    return ids


def print_plan(models):
    calls = len(PROFILES) * 2 * len(models)
    print(f"Provider: {Config.LLM_PROVIDER}")
    print(f"Models: {[m or '(gemini default)' for m in models] or 'NONE configured'}")
    print(f"Profiles ({len(PROFILES)}): {', '.join(p['name'] for p in PROFILES)}")
    print("Tasks per profile: roadmap phase (schema-checked JSON), resume feedback (plain text)")
    print(f"Real calls with --run: {len(PROFILES)} x 2 x {len(models)} = {calls}")
    print(f"Output: {OUT_CSV}")


def build_roadmap_prompt(profile, index, chunks):
    import app.pipeline.roadmap_generator as rg
    from app.pipeline.rag import search_diverse
    inventory = rg._topic_inventory(profile["career_path"], chunks)
    by_folder = rg._group_by_folder(rg._dedup_inventory(inventory))
    ordered = sorted(by_folder, key=lambda f: -len(by_folder[f]))            # no LLM call for the order
    phase = rg._merge_small_folders(ordered, by_folder, rg.SUPPORTING_FOLDERS.get(profile["career_path"], set()))[0]
    phase = {"phase_number": 1, **phase}
    queries = rg._build_diverse_queries(profile["career_path"], profile["signals"]) + [f"{profile['career_path']}: {phase['title']}"]
    retrieved = search_diverse(queries, index, chunks, profile["career_path"], total_k=rg.TOTAL_K, per_folder_cap=rg.PER_FOLDER_CAP)
    node_ids = {t["node_id"] for t in phase["topics"]}
    scoped = [c for c in retrieved if c.get("node_id") in node_ids or "node_id" not in c] or retrieved
    return rg._build_prompt(profile["career_path"], phase, scoped, rg._checkpoint_chunks_for_phase(profile["career_path"], phase, chunks),
                            profile["signals"], set(), [], phase["target_steps"])


def build_resume_prompt(profile):
    from app.pipeline.resume_feedback import _build_prompt
    return _build_prompt(profile["resume"], profile["career_path"], ["Git", "Python"], ["Docker", "SQL", "Testing"])


def run(models):
    from app.pipeline import llm_client, rag
    index, chunks = rag.load_index(Config.FAISS_INDEX_PATH)
    rows = []
    original = (Config.ROADMAP_MODEL_ID, Config.FAST_MODEL_ID, Config.FALLBACK_MODEL_ID)
    try:
        for model in models:
            Config.ROADMAP_MODEL_ID = Config.FAST_MODEL_ID = model or ""
            Config.FALLBACK_MODEL_ID = ""    # measure this model alone
            for profile in PROFILES:
                for task, prompt, schema in (
                    ("roadmap", build_roadmap_prompt(profile, index, chunks), ROADMAP_STEP_SCHEMA),
                    ("fast", build_resume_prompt(profile), None),
                ):
                    row = {"profile": profile["name"], "task": "roadmap" if task == "roadmap" else "resume",
                           "model_id": model or "(gemini default)", "provider": Config.LLM_PROVIDER}
                    try:
                        r = llm_client.generate(task, prompt, schema=schema, max_output_tokens=16384 if schema else None)
                        row.update(ok=True, first_try_schema_pass=(not r["schema_retry"]) if schema else "",
                                   retries=r["retries"] + (1 if r["schema_retry"] else 0), latency_s=round(r["latency_s"], 2),
                                   input_tokens=r["input_tokens"], output_tokens=r["output_tokens"],
                                   cost_usd="" if r["cost_usd"] is None else r["cost_usd"], error_kind="")
                    except llm_client.LLMError as exc:
                        row.update(ok=False, first_try_schema_pass=False, retries="", latency_s="", input_tokens="",
                                   output_tokens="", cost_usd="", error_kind=exc.kind)
                    rows.append(row)
                    print(f"{row['model_id']:<30} {row['profile']:<18} {row['task']:<8} ok={row['ok']} latency={row['latency_s']}")
    finally:
        Config.ROADMAP_MODEL_ID, Config.FAST_MODEL_ID, Config.FALLBACK_MODEL_ID = original
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {OUT_CSV} ({len(rows)} rows)")


def main():
    models = configured_models()
    print_plan(models)
    if "--run" not in sys.argv:
        print("\nDRY RUN: no calls were made. Re-run with --run to benchmark for real.")
        return
    if not models:
        sys.exit("No model configured: set ROADMAP_MODEL_ID / FAST_MODEL_ID / FALLBACK_MODEL_ID (or use LLM_PROVIDER=gemini).")
    run(models)


if __name__ == "__main__":
    main()

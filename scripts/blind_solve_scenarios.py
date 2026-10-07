"""
Blind-solve check for scenario files: a model answers every question WITHOUT seeing the key, and every
disagreement with the key is written to docs/SCENARIO_REVIEW_<path slug>.md for a human to adjudicate.
A disagreement means the question may be ambiguous or the key wrong; it does not prove either.

DRY RUN BY DEFAULT: prints the plan and the size of each prompt, makes no call.

Usage:
    PYTHONPATH=. python scripts/blind_solve_scenarios.py                        # dry run, every path
    PYTHONPATH=. python scripts/blind_solve_scenarios.py --paths "Machine Learning Engineering"
    PYTHONPATH=. python scripts/blind_solve_scenarios.py --run --paths "Machine Learning Engineering"

Only the --run form calls the model (llm_client.generate, task "roadmap"). The prompt is built from a
whitelist (build_blind_view), so answer fields cannot reach it; tests/smoke_test_scenarios.py proves that.
A scenario whose reply is missing or malformed is retried on its own (--retries, default 1), never the
whole path.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

from app.pipeline.scenario_validator import load_and_validate

SCENARIO_DIR = Path("data/scenarios")
DOCS_DIR = Path("docs")

SYSTEM = ("You are a careful senior practitioner answering exam questions about a realistic work scenario. "
          "Answer only from the scenario and your own expertise. Reply with JSON only.")

ANSWER_SCHEMA = {
    "type": "object",
    "required": ["answers"],
    "properties": {"answers": {"type": "array", "items": {
        "type": "object",
        "required": ["question_id"],
        "properties": {
            "question_id": {"type": "string"},
            "selected": {"type": "array", "items": {"type": "string"}},
            "mapping": {"type": "array", "items": {
                "type": "object", "required": ["item_id", "target_id"],
                "properties": {"item_id": {"type": "string"}, "target_id": {"type": "string"}}}},
        },
    }}},
}


def slug(path_name):
    return re.sub(r"[^a-z0-9]+", "-", path_name.lower()).strip("-")


def build_blind_view(scenario, seed=0):
    """
    The ONLY thing sent to the model. Built field by field from a whitelist - never by copying the scenario
    and deleting keys - so a new answer field added to the file later cannot leak. Options are shuffled.
    """
    rng = random.Random(f"{seed}:{scenario['id']}")

    def shuffled(pool):
        pool = [{"id": o["id"], "text": o["text"]} for o in pool]
        rng.shuffle(pool)
        return pool

    questions = []
    for q in scenario["questions"]:
        view = {"id": q["id"], "type": q["type"], "prompt": q["prompt"]}
        if q["type"] == "match":
            view["items"], view["targets"] = shuffled(q["items"]), shuffled(q["targets"])
        else:
            view["options"] = shuffled(q["options"])
        questions.append(view)
    return {"title": scenario["title"], "background": scenario["background"],
            "constraints": list(scenario["constraints"]), "questions": questions}


def build_prompt(scenario, seed=0):
    view = build_blind_view(scenario, seed)
    lines = [f"SCENARIO: {view['title']}", "", view["background"], "", "CONSTRAINTS:"]
    lines += [f"- {c}" for c in view["constraints"]]
    lines += ["", "Answer every question below. Reply with JSON: "
              '{"answers": [{"question_id": "...", "selected": ["option id", ...], '
              '"mapping": [{"item_id": "...", "target_id": "..."}]}]}.',
              "Rules: single_choice -> selected has exactly one option id. multi_select -> selected has every "
              "option id that applies (the question says how many when it is a fixed number). order -> selected "
              "lists ALL option ids from first step to last. match -> use mapping (one entry per item, each "
              "target used once) and leave selected empty.", ""]
    for n, q in enumerate(view["questions"], 1):
        lines.append(f"Q{n} [{q['id']}] ({q['type']}): {q['prompt']}")
        if q["type"] == "match":
            lines.append("  Items:")
            lines += [f"    {o['id']}: {o['text']}" for o in q["items"]]
            lines.append("  Targets:")
            lines += [f"    {o['id']}: {o['text']}" for o in q["targets"]]
        else:
            lines += [f"    {o['id']}: {o['text']}" for o in q["options"]]
        lines.append("")
    return "\n".join(lines)


def normalise_reply(question, entry):
    """The model's answer for one question in the same shape as the key, or None if unusable."""
    if not isinstance(entry, dict):
        return None
    if question["type"] == "match":
        mapping = entry.get("mapping")
        if not isinstance(mapping, list):
            return None
        out = {m.get("item_id"): m.get("target_id") for m in mapping if isinstance(m, dict)}
        return out or None
    selected = entry.get("selected")
    if not isinstance(selected, list) or not all(isinstance(s, str) for s in selected) or not selected:
        return None
    return selected


def agrees(question, given):
    key = question["correct"]
    if given is None:
        return False
    if question["type"] == "order":
        return given == key
    if question["type"] == "match":
        return given == key
    return sorted(given) == sorted(key) and len(set(given)) == len(given)


def solve_scenario(scenario, generate, retries=1, seed=0):
    """
    Returns {"answers": {question_id: normalised answer}, "error": None | str, "attempts": n}.
    Only this scenario is re-asked on failure. `generate` is llm_client.generate (or a stub).
    """
    prompt = build_prompt(scenario, seed)
    error = "no attempt"
    for attempt in range(1, retries + 2):
        try:
            result = generate(task="roadmap", prompt=prompt, system=SYSTEM, schema=ANSWER_SCHEMA)
            entries = (result.get("parsed") or {}).get("answers")
            by_id = {e.get("question_id"): e for e in entries if isinstance(e, dict)} if isinstance(entries, list) else {}
            answers = {q["id"]: normalise_reply(q, by_id.get(q["id"])) for q in scenario["questions"]}
            if all(v is not None for v in answers.values()):
                return {"answers": answers, "error": None, "attempts": attempt}
            error = "reply missing or malformed for: " + ", ".join(k for k, v in answers.items() if v is None)
        except Exception as exc:   # LLMError and anything the provider raises; the message may be long, keep the class
            error = f"{type(exc).__name__}: {str(exc)[:200]}"
    return {"answers": {}, "error": error, "attempts": retries + 1}


def _text(question, ids):
    pool = {o["id"]: o["text"] for o in question.get("options", [])}
    return "; ".join(f"{i} ({pool.get(i, '?')})" for i in ids)


def render_answer(question, answer):
    if answer is None:
        return "(no usable answer)"
    if question["type"] == "match":
        items = {o["id"]: o["text"] for o in question["items"]}
        targets = {o["id"]: o["text"] for o in question["targets"]}
        return "; ".join(f"{items.get(i, i)} -> {targets.get(t, t)}" for i, t in answer.items())
    return _text(question, answer)


def build_report(path_name, data, results):
    rows, sections = [], []
    total = agreed = 0
    for scenario in data["scenarios"]:
        res = results[scenario["id"]]
        n = len(scenario["questions"])
        if res["error"]:
            rows.append(f"| {scenario['id']} | {n} | - | - | no result: {res['error']} |")
            sections.append(f"### {scenario['id']}: not solved\n\n{res['error']}\n")
            continue
        total += n
        local_agreed = 0
        for q in scenario["questions"]:
            given = res["answers"][q["id"]]
            if agrees(q, given):
                local_agreed += 1
                continue
            sections.append(
                f"### {q['id']} ({q['type']})\n\n**Question:** {q['prompt']}\n\n"
                f"**Key answer:** {render_answer(q, q['correct'])}\n\n"
                f"**Model answer:** {render_answer(q, given)}\n\n"
                f"**key_justification:** {q['key_justification']}\n")
        agreed += local_agreed
        rows.append(f"| {scenario['id']} | {n} | {local_agreed} | {n - local_agreed} | |")
    summary = (f"# Blind-solve review: {path_name}\n\n"
               "A model answered each question without seeing the key. Each disagreement below needs a human "
               "decision: the question may be ambiguous, or the key may be wrong.\n\n"
               "| Scenario | Questions | Agreed | Disagreed | Note |\n|---|---|---|---|---|\n"
               + "\n".join(rows)
               + f"\n| **Total** | **{total}** | **{agreed}** | **{total - agreed}** | |\n\n")
    return summary + ("## Disagreements\n\n" + "\n".join(sections) if sections else "No disagreements.\n")


def find_files(wanted):
    found = {}
    for f in sorted(SCENARIO_DIR.glob("*.json")):
        data, result = load_and_validate(f)
        if result["errors"]:
            print(f"SKIP {f.name}: invalid ({len(result['errors'])} error(s)); run scripts/validate_scenarios.py")
            continue
        if not wanted or data["path"] in wanted:
            found[data["path"]] = data
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="actually call the model (default: dry run)")
    parser.add_argument("--paths", nargs="+", help="career path names (default for a dry run: all)")
    parser.add_argument("--retries", type=int, default=1, help="extra attempts for a failed scenario (default 1)")
    args = parser.parse_args(argv)

    if args.run and not args.paths:
        print("--run needs --paths (name each path explicitly)")
        return 2
    files = find_files(set(args.paths or []))
    missing = set(args.paths or []) - set(files)
    if missing:
        print("No valid scenario file for: " + ", ".join(sorted(missing)))
        return 2

    for path_name, data in files.items():
        print(f"\n{path_name}: {len(data['scenarios'])} scenarios, "
              f"{sum(len(s['questions']) for s in data['scenarios'])} questions")
        for s in data["scenarios"]:
            print(f"  {s['id']}: {len(s['questions'])} questions, prompt {len(build_prompt(s))} chars, one call")
    if not args.run:
        print("\nDRY RUN: no call made. Add --run --paths \"<path>\" to send these prompts.")
        return 0

    from app.pipeline import llm_client
    for path_name, data in files.items():
        results = {}
        for s in data["scenarios"]:
            results[s["id"]] = solve_scenario(s, llm_client.generate, retries=args.retries)
            print(f"  {s['id']}: " + (results[s["id"]]["error"] or "solved"))
        out = DOCS_DIR / f"SCENARIO_REVIEW_{slug(path_name)}.md"
        out.write_text(build_report(path_name, data, results), encoding="utf-8")
        print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

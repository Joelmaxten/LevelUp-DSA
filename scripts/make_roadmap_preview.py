"""
Standalone, server-free preview of the roadmap page's rendering - for
visually checking roadmapStep/roadmapStepList/phaseHeaderRow changes
without running Flask, logging in, or touching the database. Inlines
app/static/js/ui.js, app/static/js/results.js and app/static/css/style.css
plus one saved roadmap JSON (from scratch/, as produced by
scripts/inspect_roadmap.py) into a single HTML file that calls the SAME
render functions roadmap.html itself uses (roadmapStepList,
hasAllVideoResults, row, el, ...), so what's previewed is exactly what the
real page would produce for that data - not a reimplementation.

Read-only: never writes to the database, never calls Gemini, and never
makes a network call even with --with-resources (see build_preview_from_scratch -
YOUTUBE_API_KEY is deliberately unset in this process before calling the
resolver, so googleapiclient.discovery.build() is never even constructed,
regardless of how that library's own discovery-document fetching behaves).

Usage:
    PYTHONPATH=. python scripts/make_roadmap_preview.py <scratch_json> [--with-resources]
        Writes scratch/preview_<career_path>.html.
        --with-resources runs youtube_resources.fetch_resources_for_roadmap
        with max_fallback_searches=0 first (KB-only, zero network calls),
        so videos/resources/subtopics/more_topics are all present to
        preview. Without it, the roadmap renders exactly as
        inspect_roadmap.py saved it (no videos/resources/subtopics keys
        yet - subtopics IS already in a saved roadmap_generator.py output,
        but videos/resources are only added by the resolver).

    PYTHONPATH=. python scripts/make_roadmap_preview.py --flat-fixture <scratch_json>
        Reduces that saved (phased) roadmap to a flat old-style roadmap -
        a plain list of {step_number, title, description} only, nothing
        else - simulating a roadmap saved before this project had phases,
        subtopics, topic_refs, projects, or resources. Writes
        scratch/flat_fixture_<career_path>.json (itself a valid input to
        this same script) and scratch/preview_flat_fixture_<career_path>.html
        (no resources - old flat steps have no topic_refs to resolve from).
"""

import argparse
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_JS = REPO_ROOT / "app" / "static" / "js" / "ui.js"
RESULTS_JS = REPO_ROOT / "app" / "static" / "js" / "results.js"
STYLE_CSS = REPO_ROOT / "app" / "static" / "css" / "style.css"
SCRATCH_DIR = REPO_ROOT / "scratch"


def _safe_name(career_path):
    return re.sub(r"[^A-Za-z0-9]+", "_", career_path).strip("_")


def build_html(career_path, roadmap_dict, source_note):
    ui_js = UI_JS.read_text(encoding="utf-8")
    results_js = RESULTS_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    roadmap_json = json.dumps(roadmap_dict, ensure_ascii=False)
    banner_style = (
        "background:#fff3cd;border-bottom:2px solid #997404;"
        "padding:0.75rem 1.5rem;font-family:sans-serif;font-size:0.9rem;"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Roadmap preview - {career_path}</title>
<style>
{css}
</style>
</head>
<body class="js">
<div style="{banner_style}">Standalone preview - {source_note}. Not a live page: no login, no server, no network calls.</div>
<main class="page">
<div class="sheet">
  <header class="row row-head">
    <div class="margin"></div>
    <div class="main"><h1 class="page-title">Your roadmap</h1></div>
  </header>
  <div id="roadmap-box"></div>
</div>
</main>
<script>
{ui_js}
</script>
<script>
{results_js}
</script>
<script>
const ROADMAP_DATA = {roadmap_json};
const box = document.getElementById("roadmap-box");
const when = ROADMAP_DATA.created_at ? formatDate(ROADMAP_DATA.created_at) : "";
box.replaceChildren(
    row(
        [el("p", {{ className: "note", text: "Built for" }}), when ? el("p", {{ className: "note", text: "Generated " + when }}) : ""],
        el("h2", {{ className: "path-name" }}, el("span", {{ className: "mark", text: ROADMAP_DATA.career_path }}))
    ),
    roadmapStepList(ROADMAP_DATA.steps, false)
);
console.log("hasAllVideoResults:", hasAllVideoResults(ROADMAP_DATA.steps));
</script>
</body>
</html>
"""


def _write_preview(career_path, steps, source_note, out_name):
    roadmap_dict = {"career_path": career_path, "steps": steps, "created_at": None}
    html = build_html(career_path, roadmap_dict, source_note)
    out_path = SCRATCH_DIR / out_name
    out_path.write_text(html, encoding="utf-8")
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"Wrote {out_path} ({size_kb:.1f} KB)")
    return out_path


def build_preview_from_scratch(scratch_json_path, with_resources):
    data = json.loads(Path(scratch_json_path).read_text(encoding="utf-8"))
    career_path = data["career_path"]
    roadmap = data["roadmap"]

    if with_resources:
        # Force no youtube_client to be built at all inside
        # fetch_resources_for_roadmap, regardless of what's in .env for
        # this machine - guarantees zero network interaction, not just
        # zero fallback searches.
        os.environ.pop("YOUTUBE_API_KEY", None)
        from app.pipeline.rag import load_index
        from app.pipeline.youtube_resources import fetch_resources_for_roadmap

        index, chunks = load_index("data/processed/faiss_index")
        roadmap, stats = fetch_resources_for_roadmap(roadmap, chunks=chunks, max_fallback_searches=0)
        print(
            f"KB-only resolve for {career_path!r}: kb_videos_used={stats['kb_videos_used']}, "
            f"fallback_searches_used={stats['fallback_searches_used']} (must be 0)"
        )

    source_note = f"{'with' if with_resources else 'without'} resources, from {scratch_json_path}"
    return _write_preview(career_path, roadmap, source_note, f"preview_{_safe_name(career_path)}.html")


def build_flat_fixture_and_preview(source_scratch_json_path):
    data = json.loads(Path(source_scratch_json_path).read_text(encoding="utf-8"))
    career_path = data["career_path"]
    roadmap = data["roadmap"]

    flat_steps = []
    for phase in roadmap["phases"]:
        for step in phase["steps"]:
            flat_steps.append({
                "step_number": step.get("global_step_index", len(flat_steps) + 1),
                "title": step.get("title", ""),
                "description": step.get("description", ""),
            })

    fixture_path = SCRATCH_DIR / f"flat_fixture_{_safe_name(career_path)}.json"
    fixture_path.write_text(
        json.dumps({"career_path": career_path, "roadmap": flat_steps}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote flat fixture: {fixture_path} ({len(flat_steps)} steps)")

    source_note = f"flat old-style fixture, reduced from {source_scratch_json_path}"
    return _write_preview(career_path, flat_steps, source_note, f"preview_flat_fixture_{_safe_name(career_path)}.html")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch_json", nargs="?", help="Path to a scratch/roadmap_<path>.json file")
    parser.add_argument("--with-resources", action="store_true", help="Run the KB-only resolver first (zero network calls)")
    parser.add_argument("--flat-fixture", metavar="SOURCE_JSON", help="Build and preview a flat old-style roadmap fixture from a phased scratch JSON")
    args = parser.parse_args()

    SCRATCH_DIR.mkdir(exist_ok=True)

    if args.flat_fixture:
        build_flat_fixture_and_preview(args.flat_fixture)
        return

    if not args.scratch_json:
        parser.error("scratch_json is required unless --flat-fixture is given")

    build_preview_from_scratch(args.scratch_json, with_resources=args.with_resources)


if __name__ == "__main__":
    main()

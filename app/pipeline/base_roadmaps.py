"""
Reviewed base roadmaps: one JSON file per career path in data/base_roadmaps/<slug>.json, built offline by
scripts/build_base_roadmaps.py and served by POST /roadmap/generate-async in "cached" mode (see
app/pipeline/generation_jobs.py). The roadmap itself is the same for every student of a path; only a short
personalization (app/pipeline/roadmap_personalizer.py) is per student.

File shape:
    {"metadata": {"schema_version", "career_path", "model_id", "built_at", "generator": {...settings...},
                  "inventory_fingerprint"},
     "roadmap": {"phases": [...]},          # exactly what generate_roadmap returns, plus videos/resources per step
     "audit":   {"phases": [...]}}          # generate_roadmap's retrieved-chunks audit

load_base() validates a file before it is served (phased shape, contiguous global_step_index from 1, topic_refs
inside the path's inventory, no duplicate titles, every step has "videos" and "resources"). A missing, unreadable,
corrupt or invalid file is treated as missing (None; the reason is logged, never file content). A file whose
fingerprint of the path's KB topic inventory no longer matches is still served, with a warning and stale=True.
"""
import copy
import hashlib
import json
import logging
import os
import re
from pathlib import Path

from app.pipeline import roadmap_generator as rg

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "base_roadmaps"   # tests and the build script may override
_METADATA_KEYS = ("career_path", "model_id", "built_at", "generator", "inventory_fingerprint")


def slug(career_path):
    """'UI/UX Design' -> 'ui-ux-design'."""
    return re.sub(r"[^a-z0-9]+", "-", str(career_path).lower()).strip("-")


def path_for(career_path, base_dir=None):
    return Path(base_dir or BASE_DIR) / f"{slug(career_path)}.json"


def _inventory(career_path, chunks):
    return rg._dedup_inventory(rg._topic_inventory(career_path, chunks))


def inventory_fingerprint(career_path, chunks):
    """sha256 over the sorted (node_id, title, folder) of the path's de-duplicated KB topic inventory."""
    lines = sorted(f"{t['node_id']}|{t['title']}|{t['folder']}" for t in _inventory(career_path, chunks))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def validate_roadmap(roadmap, valid_node_ids=None):
    """List of problems (empty = valid). valid_node_ids None skips the topic_refs allowlist check."""
    problems = []
    if not isinstance(roadmap, dict) or not isinstance(roadmap.get("phases"), list) or not roadmap["phases"]:
        return ["roadmap has no phases list"]
    expected_index, titles = 1, set()
    for p, phase in enumerate(roadmap["phases"], start=1):
        if not isinstance(phase, dict) or not isinstance(phase.get("title"), str) or not phase["title"].strip():
            problems.append(f"phase {p}: no title")
            continue
        if phase.get("phase_number") != p:
            problems.append(f"phase {p}: phase_number is not {p}")
        steps = phase.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"phase {p}: no steps")
            continue
        for step in steps:
            if not isinstance(step, dict):
                problems.append(f"phase {p}: a step is not an object")
                continue
            if step.get("global_step_index") != expected_index:
                problems.append(f"phase {p}: global_step_index {step.get('global_step_index')!r} where {expected_index} was expected")
            expected_index += 1
            title = step.get("title")
            if not isinstance(title, str) or not title.strip():
                problems.append(f"step {expected_index - 1}: no title")
            else:
                key = title.strip().casefold()
                if key in titles:
                    problems.append(f"step {expected_index - 1}: duplicate title")
                titles.add(key)
            if not isinstance(step.get("description"), str) or not step["description"].strip():
                problems.append(f"step {expected_index - 1}: no description")
            refs = step.get("topic_refs")
            if not isinstance(refs, list):
                problems.append(f"step {expected_index - 1}: topic_refs is not a list")
            elif valid_node_ids is not None and any(r not in valid_node_ids for r in refs):
                problems.append(f"step {expected_index - 1}: topic_refs outside the path's inventory")
            if not isinstance(step.get("videos"), list) or not isinstance(step.get("resources"), list):
                problems.append(f"step {expected_index - 1}: missing videos or resources")
    return problems


def validate_document(document, career_path, chunks):
    """(problems, stale) for a parsed file."""
    if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
        return ["no metadata"], False
    meta = document["metadata"]
    problems = [f"metadata lacks {k}" for k in _METADATA_KEYS if k not in meta]
    if meta.get("career_path") != career_path:
        problems.append("metadata is for a different career path")
    if not isinstance(document.get("audit"), dict):
        problems.append("no audit")
    valid_ids = {t["node_id"] for t in _inventory(career_path, chunks)} if chunks is not None else None
    problems += validate_roadmap(document.get("roadmap"), valid_ids)
    stale = chunks is not None and meta.get("inventory_fingerprint") != inventory_fingerprint(career_path, chunks)
    return problems, stale


def load_base(career_path, chunks, base_dir=None):
    """
    The validated base roadmap for a path as {"roadmap", "audit", "metadata", "stale"} (a deep copy, safe to
    modify), or None if there is no usable file. Never raises.
    """
    path = path_for(career_path, base_dir)
    try:
        if not path.is_file():
            return None
        document = json.loads(path.read_text(encoding="utf-8"))
        problems, stale = validate_document(document, career_path, chunks)
    except Exception as exc:
        logger.warning("base roadmap %s unreadable (%s): treated as missing", path.name, type(exc).__name__)
        return None
    if problems:
        logger.warning("base roadmap %s invalid (%d problem(s), first: %s): treated as missing", path.name, len(problems), problems[0])
        return None
    if stale:
        logger.warning("base roadmap %s is stale: the knowledge base inventory for %r changed since it was built; serving it anyway",
                       path.name, career_path)
    return {"roadmap": copy.deepcopy(document["roadmap"]), "audit": copy.deepcopy(document["audit"]),
            "metadata": copy.deepcopy(document["metadata"]), "stale": bool(stale)}


def build_document(career_path, roadmap, audit, chunks, model_id, generator_settings, built_at):
    return {"metadata": {"schema_version": SCHEMA_VERSION, "career_path": career_path, "model_id": model_id,
                         "built_at": built_at, "generator": generator_settings,
                         "inventory_fingerprint": inventory_fingerprint(career_path, chunks)},
            "roadmap": roadmap, "audit": audit}


def write_atomic(path, document):
    """Writes next to the target and renames, so a crash never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)

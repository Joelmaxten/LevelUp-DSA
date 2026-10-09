"""
Validator for scenario files (data/scenarios/<path>.json). Pure: no Flask, no database, no network.

validate_scenario_file(data) -> {"errors": [str], "warnings": [str]}. A file with any error must never be
served (scenario_store refuses it); warnings are advisory. See docs/DEV_SETUP.md for the file format.
"""
import json
import re
from collections import Counter

import jsonschema

from app.pipeline.career_path_registry import CAREER_PATHS

SCHEMA_VERSION = 1
LADDER_STAGES = ["foundations", "core_decision", "debugging", "trade_offs", "end_to_end"]
QUESTION_TYPES = ["single_choice", "multi_select", "order", "match"]
# Id prefix per path (mle-1, mle-1-q2). A path without an entry here cannot have a scenario file yet.
PATH_ID_PREFIX = {"Machine Learning Engineering": "mle", "Cybersecurity": "cyb"}

NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "2": 2, "3": 3, "4": 4, "5": 5}
STATED_NUMBER = re.compile(r"\b(?:which|choose|select|pick)\s+(two|three|four|five|[2-5])\b", re.I)
BANNED_OPTION = re.compile(
    r"^\s*(all of the above|none of the above|both [a-e] and [a-e]|[a-e] and [a-e] (?:both|only))\b", re.I)
LETTER_REFERENCE = re.compile(r"\b(?:options?|choices?|answers?)\s*\(?[a-e]\)?(?![a-z])", re.I)

_ID = {"type": "string", "pattern": r"^[a-z0-9]+$", "maxLength": 12}
_TEXT = {"type": "string", "minLength": 1, "maxLength": 1200}
_OPTIONS = {"type": "array", "minItems": 2, "maxItems": 8,
            "items": {"type": "object", "required": ["id", "text"], "additionalProperties": False,
                      "properties": {"id": _ID, "text": _TEXT}}}

SCHEMA = {
    "type": "object",
    "required": ["schema_version", "path", "map", "scenarios"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "path": {"type": "string", "minLength": 1},
        "map": {
            "type": "object", "required": ["scene_id", "theme", "edges"], "additionalProperties": False,
            "properties": {
                "scene_id": {"type": "string", "pattern": r"^[a-z0-9-]+$"},
                "theme": _TEXT,
                "edges": {"type": "array", "items": {"type": "array", "minItems": 2, "maxItems": 2,
                                                     "items": {"type": "string"}}},
            },
        },
        "scenarios": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "order", "ladder_stage", "title", "difficulty", "estimated_minutes",
                             "background", "constraints", "tests_topics", "map_node", "questions"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "order": {"type": "integer", "minimum": 1},
                    "ladder_stage": {"enum": LADDER_STAGES},
                    "title": _TEXT,
                    "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                    "estimated_minutes": {"type": "integer", "minimum": 1, "maximum": 120},
                    "background": {"type": "string", "minLength": 20, "maxLength": 4000},
                    "constraints": {"type": "array", "items": _TEXT},
                    "tests_topics": {"type": "array", "minItems": 1, "items": _TEXT},
                    "map_node": {
                        "type": "object", "required": ["x", "y", "label"], "additionalProperties": False,
                        "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "label": _TEXT},
                    },
                    "questions": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/question"}},
                },
            },
        },
    },
    "$defs": {
        "question": {
            "type": "object",
            "required": ["id", "type", "prompt", "correct", "explanation", "why_others_wrong", "key_justification"],
            "properties": {
                "id": {"type": "string"},
                "type": {"enum": QUESTION_TYPES},
                "prompt": _TEXT,
                "explanation": {"type": "string"},
                "why_others_wrong": {"type": "object", "additionalProperties": {"type": "string"}},
                "key_justification": {"type": "string"},
                "points": {"type": "integer", "minimum": 1},
            },
            "allOf": [
                {"if": {"properties": {"type": {"enum": ["single_choice", "multi_select", "order"]}}},
                 "then": {"required": ["options"], "properties": {
                     "options": _OPTIONS, "correct": {"type": "array", "items": {"type": "string"}}}}},
                {"if": {"properties": {"type": {"const": "match"}}},
                 "then": {"required": ["items", "targets"], "properties": {
                     "items": _OPTIONS, "targets": _OPTIONS,
                     "correct": {"type": "object", "additionalProperties": {"type": "string"}}}}},
            ],
        }
    },
}


def validate_scenario_file(data):
    errors, warnings = [], []
    try:
        schema_errors = sorted(jsonschema.Draft202012Validator(SCHEMA).iter_errors(data),
                               key=lambda e: [str(p) for p in e.absolute_path])
    except Exception as exc:  # a broken schema must fail loudly, not pass silently
        return {"errors": [f"validator failure: {type(exc).__name__}"], "warnings": []}
    for e in schema_errors:
        where = "/".join(str(p) for p in e.absolute_path) or "(root)"
        errors.append(f"schema: {where}: {e.message[:160]}")
    if errors:
        return {"errors": errors, "warnings": warnings}   # the semantic checks assume the shape is right

    path = data["path"]
    if path not in CAREER_PATHS:
        errors.append(f"path {path!r} is not a name in CAREER_PATHS")
    prefix = PATH_ID_PREFIX.get(path)
    if path in CAREER_PATHS and prefix is None:
        errors.append(f"no id prefix registered for path {path!r} (PATH_ID_PREFIX)")

    scenarios = data["scenarios"]
    ids = [s["id"] for s in scenarios]
    for dup, n in Counter(ids).items():
        if n > 1:
            errors.append(f"duplicate scenario id {dup}")
    for dup, n in Counter(q["id"] for s in scenarios for q in s["questions"]).items():
        if n > 1:
            errors.append(f"duplicate question id {dup}")

    if sorted(s["order"] for s in scenarios) != list(range(1, len(scenarios) + 1)):
        errors.append("scenario order values must be 1..N, contiguous and unique")

    stage_rank = [LADDER_STAGES.index(s["ladder_stage"]) for s in sorted(scenarios, key=lambda s: s["order"])]
    if stage_rank != sorted(stage_rank):
        errors.append("ladder_stage values do not follow the allowed sequence "
                      + " > ".join(LADDER_STAGES) + " in scenario order")

    for s in scenarios:
        sid = s["id"]
        if prefix:
            m = re.fullmatch(rf"{prefix}-(\d+)", sid)
            if not m:
                errors.append(f"{sid}: scenario id must match {prefix}-N")
            elif int(m.group(1)) != s["order"]:
                errors.append(f"{sid}: id number does not equal order {s['order']}")
        node = s["map_node"]
        for axis in ("x", "y"):
            if not 0 <= node[axis] <= 1:
                errors.append(f"{sid}: map_node.{axis}={node[axis]} outside [0,1]")
        for i, q in enumerate(s["questions"], 1):
            if prefix and q["id"] != f"{sid}-q{i}":
                errors.append(f"{q['id']}: question id must be {sid}-q{i}")
            _check_question(q, errors)

    scenario_ids = set(ids)
    for a, b in data["map"]["edges"]:
        for end in (a, b):
            if end not in scenario_ids:
                errors.append(f"map edge references unknown scenario id {end}")

    _warnings(scenarios, warnings)
    return {"errors": errors, "warnings": warnings}


def _check_question(q, errors):
    qid, qtype = q["id"], q["type"]
    for field in ("explanation", "key_justification"):
        if not q[field].strip():
            errors.append(f"{qid}: {field} is empty")
    texts_to_scan = [q["explanation"]] + list(q["why_others_wrong"].values())
    if any(LETTER_REFERENCE.search(t) for t in texts_to_scan):
        errors.append(f"{qid}: explanation text refers to an option letter (options are shuffled)")

    pools = [q["items"], q["targets"]] if qtype == "match" else [q["options"]]
    for pool in pools:
        pool_ids = [o["id"] for o in pool]
        if len(set(pool_ids)) != len(pool_ids):
            errors.append(f"{qid}: duplicate option ids")
        texts = [o["text"].strip().lower() for o in pool]
        if len(set(texts)) != len(texts):
            errors.append(f"{qid}: duplicate option texts")
        for o in pool:
            if BANNED_OPTION.match(o["text"]):
                errors.append(f"{qid}: option {o['id']} is an 'all/none/both of the above' style option")

    wrong = q["why_others_wrong"]
    if qtype in ("single_choice", "multi_select"):
        ids = [o["id"] for o in q["options"]]
        correct = q["correct"]
        if len(set(correct)) != len(correct):
            errors.append(f"{qid}: correct has duplicate ids")
        missing = [c for c in correct if c not in ids]
        if missing:
            errors.append(f"{qid}: correct ids not in options: {missing}")
        if qtype == "single_choice" and len(correct) != 1:
            errors.append(f"{qid}: single_choice needs exactly one correct id (has {len(correct)})")
        if qtype == "multi_select":
            if len(correct) < 2:
                errors.append(f"{qid}: multi_select needs at least 2 correct ids")
            stated = STATED_NUMBER.search(q["prompt"])
            if stated and len(correct) != NUMBER_WORDS[stated.group(1).lower()]:
                errors.append(f"{qid}: prompt says '{stated.group(0)}' but {len(correct)} answers are correct")
        if len(ids) <= len(correct):
            errors.append(f"{qid}: every option is correct")
        wrong_ids = [i for i in ids if i not in correct]
        for i in wrong_ids:
            if not str(wrong.get(i, "")).strip():
                errors.append(f"{qid}: why_others_wrong missing wrong option {i}")
        for i in wrong:
            if i not in wrong_ids:
                errors.append(f"{qid}: why_others_wrong has {i!r}, which is not a wrong option id")
    elif qtype == "order":
        ids = [o["id"] for o in q["options"]]
        if sorted(q["correct"]) != sorted(ids):
            errors.append(f"{qid}: order correct must be a permutation of all option ids")
        if not str(wrong.get("common_mistake", "")).strip():
            errors.append(f"{qid}: order needs why_others_wrong.common_mistake")
    else:  # match
        item_ids = [o["id"] for o in q["items"]]
        target_ids = [o["id"] for o in q["targets"]]
        if len(item_ids) != len(target_ids):
            errors.append(f"{qid}: match needs the same number of items and targets")
        c = q["correct"]
        if sorted(c) != sorted(item_ids):
            errors.append(f"{qid}: match correct must have a key for every item and nothing else")
        elif sorted(c.values()) != sorted(target_ids):
            errors.append(f"{qid}: match correct must map items to targets one-to-one (a bijection)")
        if not str(wrong.get("common_mistake", "")).strip():
            errors.append(f"{qid}: match needs why_others_wrong.common_mistake")


def _warnings(scenarios, warnings):
    positions = []
    singles = longest_correct = 0
    for s in scenarios:
        for q in s["questions"]:
            if q["type"] == "single_choice":
                singles += 1
                ids = [o["id"] for o in q["options"]]
                positions += [ids.index(c) for c in q["correct"] if c in ids]
                longest = max(q["options"], key=lambda o: len(o["text"]))
                if q["correct"] == [longest["id"]]:
                    longest_correct += 1
    if len(positions) >= 4 and len(set(positions)) == 1:
        warnings.append(f"every correct answer is in position {positions[0] + 1}")
    if singles and longest_correct / singles > 0.6:
        warnings.append(f"the longest option is correct in {longest_correct}/{singles} single_choice questions (>60%)")


def load_and_validate(path):
    """(data or None, result) for a file path; unreadable or non-JSON files are an error, not an exception."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return None, {"errors": [f"cannot read file as JSON ({type(exc).__name__})"], "warnings": []}
    return data, validate_scenario_file(data)

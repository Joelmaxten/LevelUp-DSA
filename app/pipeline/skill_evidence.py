"""
Skill evidence: one record per student that says, for every skill, how sure we are that they have it and WHY.
Pure: no Flask, no database, no network, no spaCy. The route (app/routes/skills.py) gathers the rows and passes in the
resume matcher; this module decides everything, like gamification.py. Nothing here is stored: every number is worked out
from rows the app already keeps, so it cannot drift out of sync and any figure can be explained by the evidence behind it.

Evidence sources (all passing evidence only):
  step_check  a roadmap step passed with the normal check                      weight 0.5
  test_out    a roadmap step passed by testing out of it                       weight 0.6
  scenario    a scenario passed (its best attempt passed)                      weight 0.5
  code        a code problem solved (every test passed)                        weight 0.6
The resume is a CLAIM, never proof: a skill only on the resume has confidence 0 and status "unverified".

Confidence = 1 - product(1 - w) over the skill's pieces of evidence. It is computed with exact fractions (not floats), so
"step check + scenario" is exactly 0.70, never 0.6999999.

A skill is "verified" at RULES["verified_at"][kind]: tools at 0.5, concepts at 0.7. Because no single piece of evidence
weighs 0.7 or more, a concept needs two separate pieces of evidence; with one it is "in_progress". Tool skills are verified
by one piece. Kind comes from data/skill_map.json ("concepts" is the fixed list of concept skills; everything else is a tool).

Which skills a step / scenario / code problem is evidence for:
  1. the resume skill matcher (injected as `matcher`, the default and unchanged),
  2. plus the additions in data/skill_map.json (steps keyed "<career path slug>|<normalised title>", scenarios by id,
     code problems by ds_topic and by their own `skills` field),
  3. minus its exclusions (wrong matches, tools that are only one option in a list of alternatives),
  4. spelled one way: the survey vocabulary's spelling wins, then the map's "canonical" table.
One piece of evidence counts once however often it was repeated (the same step on two roadmaps, many attempts at a scenario).
"""
import re
from fractions import Fraction

# The weights and the verification thresholds live together, in this one constant.
RULES = {
    "weights": {"step_check": 0.5, "test_out": 0.6, "scenario": 0.5, "code": 0.6},
    "verified_at": {"tool": 0.5, "concept": 0.7},
}

MAX_CONCEPTS = 30
STATUS_ORDER = {"verified": 0, "in_progress": 1, "unverified": 2}
# Evidence of the same unit counts once, whichever way it was earned: passing a step by check and by test-out is one step.
FAMILY = {"step_check": "step", "test_out": "step", "scenario": "scenario", "code": "code"}


def _frac(value):
    return Fraction(str(value))


WEIGHTS = {source: _frac(w) for source, w in RULES["weights"].items()}
THRESHOLDS = {kind: _frac(t) for kind, t in RULES["verified_at"].items()}


# ---------------------------------------------------------------- the skill map
def normalise_title(title):
    """lower-case, trimmed, runs of spaces collapsed: how step titles are keyed in the map."""
    return re.sub(r"\s+", " ", str(title or "").strip().lower())


def step_key(career_path_slug, title):
    return f"{career_path_slug}|{normalise_title(title)}"


def prepare_map(raw):
    """
    Validates the parsed data/skill_map.json and returns it ready to use (regexes compiled, sets built).
    Raises ValueError with a plain message when the file is malformed, so a bad edit is caught by the smoke test.
    """
    if not isinstance(raw, dict):
        raise ValueError("skill map must be an object")
    concepts = raw.get("concepts")
    if not isinstance(concepts, list) or not concepts or len(set(concepts)) != len(concepts):
        raise ValueError("concepts must be a non-empty list without duplicates")
    if len(concepts) > MAX_CONCEPTS:
        raise ValueError(f"at most {MAX_CONCEPTS} concept skills are allowed, found {len(concepts)}")
    for section in ("canonical", "scenarios", "steps", "code_topics"):
        if not isinstance(raw.get(section), dict):
            raise ValueError(f"{section} must be an object")
    for section in ("scenarios", "steps", "code_topics"):
        for key, skills in raw[section].items():
            if not isinstance(skills, list) or not all(isinstance(s, str) and s for s in skills):
                raise ValueError(f"{section}[{key!r}] must be a list of skill names")
    rules = []
    for rule in raw.get("exclude", []):
        try:
            if "step" in rule:
                rules.append({"step": rule["step"], "skills": {s.lower() for s in rule["skills"]}})
            else:
                rules.append({"skill": rule["skill"].lower(), "when": re.compile(rule["when"]),
                              "unless": re.compile(rule["unless"]) if rule.get("unless") else None})
        except (KeyError, TypeError, AttributeError, re.error) as exc:
            raise ValueError(f"bad exclusion rule {rule!r}: {exc}") from exc
    return {
        "concepts": set(concepts),
        "canonical": {k.lower(): v for k, v in raw["canonical"].items()},
        "scenarios": raw["scenarios"],
        "steps": raw["steps"],
        "code_topics": raw["code_topics"],
        "rules": rules,
    }


def canonical_name(name, skill_map, vocab_spelling=None):
    """One spelling per skill. A concept keeps its own name; otherwise the vocabulary's spelling, then the map's table."""
    if name in skill_map["concepts"]:
        return name
    low = name.lower()
    if vocab_spelling and low in vocab_spelling:
        return vocab_spelling[low]
    return skill_map["canonical"].get(low, name)


def _resolve(text, key, matched, adds, skill_map, vocab_spelling):
    names = {canonical_name(n, skill_map, vocab_spelling) for n in list(matched) + list(adds)}
    for rule in skill_map["rules"]:
        if "step" in rule:
            if key is not None and rule["step"] == key:
                names = {n for n in names if n.lower() not in rule["skills"]}
        elif rule["when"].search(text) and not (rule["unless"] and rule["unless"].search(text)):
            names = {n for n in names if n.lower() != rule["skill"]}
    return sorted(names, key=str.lower)


def _subtopic_text(subtopics):
    return [s for s in (subtopics or []) if isinstance(s, str)]


def skills_for_step(slug, title, subtopics, skill_map, matcher=None, vocab_spelling=None):
    """Skills a roadmap step is evidence for. matcher(text) -> iterable of skill names (the resume matcher), or None."""
    text = "\n".join([str(title or "")] + _subtopic_text(subtopics))
    key = step_key(slug, title)
    matched = matcher(text) if matcher else ()
    return _resolve(text, key, matched, skill_map["steps"].get(key, []), skill_map, vocab_spelling)


def skills_for_scenario(scenario_id, tests_topics, skill_map, matcher=None, vocab_spelling=None):
    """Skills a scenario is evidence for, from its tests_topics."""
    text = "\n".join(_subtopic_text(tests_topics))
    matched = matcher(text) if matcher else ()
    return _resolve(text, None, matched, skill_map["scenarios"].get(scenario_id, []), skill_map, vocab_spelling)


def skills_for_code(problem_skills, ds_topic, skill_map, vocab_spelling=None):
    """Skills a solved code problem is evidence for: its own `skills` field plus the concept for its data-structure topic."""
    adds = list(skill_map["code_topics"].get(ds_topic, []))
    return _resolve("", None, [], list(problem_skills or []) + adds, skill_map, vocab_spelling)


# ---------------------------------------------------------------- the evidence record
def evidence_item(source, unit, title, when, skills):
    """One piece of passing evidence. unit identifies WHAT was passed (a step key, a scenario id, a problem id)."""
    if source not in WEIGHTS:
        raise ValueError(f"unknown evidence source {source!r}")
    return {"source": source, "unit": str(unit), "title": str(title or ""), "when": when, "skills": list(skills or [])}


def _iso(moment):
    if moment is None:
        return None
    return moment.isoformat() + ("Z" if getattr(moment, "tzinfo", None) is None and hasattr(moment, "hour") else "")


def _dedupe(items):
    """One piece per (family, unit): the heaviest source, then the earliest date."""
    best = {}
    for item in items:
        slot = (FAMILY[item["source"]], item["unit"])
        rank = (-WEIGHTS[item["source"]], item["when"] is None, item["when"] or 0)
        if slot not in best or rank < best[slot][0]:
            best[slot] = (rank, item)
    return [item for _, item in best.values()]


def confidence(weights):
    """1 - product(1 - w), exact. No evidence is 0."""
    remaining = Fraction(1)
    for w in weights:
        remaining *= 1 - w
    return 1 - remaining


def summarize(evidence, resume_skills, skill_map, vocab_spelling=None):
    """
    evidence: evidence_item() dicts. resume_skills: the names on the student's latest resume (a claim).
    Returns {skills: [...], counts: {verified, in_progress, unverified}, rules: {weights, verified_at}} with skills sorted by
    confidence (highest first, then name). Each skill: {skill, kind, confidence, status, on_resume, threshold,
    evidence: [{source, title, date, weight}]}. status: "verified" (confidence >= threshold for its kind), "in_progress"
    (some evidence, below the threshold: a concept with one piece), "unverified" (on the resume only).
    """
    per_skill = {}
    for item in _dedupe(evidence):
        for name in item["skills"]:
            per_skill.setdefault(name.lower(), {"skill": name, "items": []})["items"].append(item)

    resume = {}
    for raw in resume_skills or []:
        if isinstance(raw, str) and raw.strip():
            name = canonical_name(raw.strip(), skill_map, vocab_spelling)
            resume.setdefault(name.lower(), name)

    rows = []
    for low in sorted(set(per_skill) | set(resume)):
        entry = per_skill.get(low)
        name = entry["skill"] if entry else resume[low]
        kind = "concept" if name in skill_map["concepts"] else "tool"
        items = sorted(entry["items"], key=lambda i: (-WEIGHTS[i["source"]], i["when"] is None, i["when"] or 0)) if entry else []
        conf = confidence(WEIGHTS[i["source"]] for i in items)
        threshold = THRESHOLDS[kind]
        if not items:
            status = "unverified"
        elif conf >= threshold:
            status = "verified"
        else:
            status = "in_progress"
        rows.append({
            "skill": name, "kind": kind, "confidence": round(float(conf), 4), "status": status,
            "on_resume": low in resume, "threshold": float(threshold),
            "evidence": [{"source": i["source"], "title": i["title"], "date": _iso(i["when"]), "weight": float(WEIGHTS[i["source"]])}
                         for i in items],
        })
    rows.sort(key=lambda r: (-r["confidence"], STATUS_ORDER[r["status"]], r["skill"].lower()))
    return {
        "skills": rows,
        "counts": {status: sum(1 for r in rows if r["status"] == status) for status in STATUS_ORDER},
        "rules": {"weights": dict(RULES["weights"]), "verified_at": dict(RULES["verified_at"])},
    }

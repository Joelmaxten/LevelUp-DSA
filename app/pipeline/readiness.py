"""
Placement Readiness Score. Pure: no Flask, no database, no network. The route (app/routes/readiness.py)
gathers the numbers; everything that decides the score lives here so it can be unit-tested.

Four components, each 0..1 or unavailable (None):
  roadmap     completed roadmap steps / total steps
  skill_gap   what the student's skills count for / skills required. Which skills count depends on READINESS_SKILL_MODE
              (see SKILL_MODES below): the resume only, verified skills only, or a blend of the two
  dsa         mean over the path's scenarios of best_score / max_score (unattempted = 0); unavailable when the
              path has no scenarios at all (that is "no content", not a score of 0)
  streak      days in the last 30 with at least one scenario submission or roadmap step completion / 30

Base weights are roadmap .25, skill_gap .35, dsa .30, streak .10. An unavailable component is dropped and the
remaining weights are re-normalised to sum to 1. The score is 0..100 rounded half-up to one decimal; a student is
"placement ready" at 70.0 or more, judged on the UNROUNDED score (so 69.96 is not ready even though it is shown as
70.0; floating-point noise below 1e-9 is ignored, so a true 70 never reads as 69.999999999).
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

_UNITS = {"roadmap": 25, "skill_gap": 35, "dsa": 30, "streak": 10}   # hundredths: integer sums avoid float drift
BASE_WEIGHTS = {name: units / 100 for name, units in _UNITS.items()}
READY_THRESHOLD = 70.0
STREAK_WINDOW_DAYS = 30

# How the skill_gap component counts the student's skills (READINESS_SKILL_MODE). The component is
# (sum of what each required skill counts for) / N, still 0..1, so the weights above are unchanged.
#   resume    the old rule: a required skill counts 1 when it is on the resume, else 0
#   verified  strict: it counts 1 only when the skill itself is verified (a tool skill with status "verified")
#   blend     verified counts 1; only on the resume counts RESUME_CLAIM_CREDIT; a required skill that nothing on the platform
#             can verify, when it is on the resume, counts CLAIM_ONLY_CREDIT (it cannot be proved here, so the claim is all
#             there can be); neither counts 0
SKILL_MODES = ("blend", "verified", "resume")
DEFAULT_SKILL_MODE = "blend"
RESUME_CLAIM_CREDIT = 0.5
CLAIM_ONLY_CREDIT = 1.0


def _ratio(done, total):
    """done / total clamped to 0..1, or None when there is nothing to measure (total missing or <= 0)."""
    if total is None or done is None or total <= 0:
        return None
    return min(1.0, max(0.0, done / total))


def roadmap_component(completed, total):
    return _ratio(completed, total)


def skill_gap_component(acquired, required):
    return _ratio(acquired, required)


def dsa_component(scenarios, progress):
    """
    scenarios: the path's scenario dicts (None or empty = the path has no scenario file -> unavailable).
    progress: scenario_engine.compute_progress(...) output, which applies the engine's best-score rules.
    """
    if not scenarios:
        return None
    total = 0.0
    for s in scenarios:
        p = (progress or {}).get(s["id"]) or {}
        best, max_score = p.get("best_score"), p.get("max_score")
        if best is not None and max_score:
            total += min(1.0, max(0.0, best / max_score))
    return total / len(scenarios)


def streak_component(activity_dates, today):
    """
    Distinct calendar days with activity among the 30 days ending on `today` (inclusive) / 30. Dates before the
    window and dates in the future do not count. activity_dates: iterable of datetime.date.
    """
    first = today - timedelta(days=STREAK_WINDOW_DAYS - 1)
    days = {d for d in activity_dates if d is not None and first <= d <= today}
    return len(days) / STREAK_WINDOW_DAYS


def _round_1(value):
    return float(Decimal(repr(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def combine(components):
    """
    components: {"roadmap": v|None, "skill_gap": v|None, "dsa": v|None, "streak": v|None}.
    Returns {score, ready, threshold, components, weights, unavailable}. With nothing available there is no
    score (None) and the student is not ready.
    """
    clean = {name: (None if components.get(name) is None else min(1.0, max(0.0, components[name])))
             for name in BASE_WEIGHTS}
    unavailable = [name for name in BASE_WEIGHTS if clean[name] is None]
    present = [name for name in BASE_WEIGHTS if clean[name] is not None]
    total_units = sum(_UNITS[n] for n in present)
    weights = {n: _UNITS[n] / total_units for n in present} if present else {}
    raw = 100 * sum(weights[n] * clean[n] for n in present) if present else None
    score = _round_1(raw) if present else None
    return {
        "score": score,
        "ready": raw is not None and round(raw, 9) >= READY_THRESHOLD,
        "threshold": READY_THRESHOLD,
        "components": clean,
        "weights": weights,
        "unavailable": unavailable,
    }


def compute_readiness(roadmap=None, skill_gap=None, scenarios=None, scenario_progress=None,
                      activity_dates=(), today=None):
    """
    roadmap: (completed_steps, total_steps) or None. skill_gap: (acquired, required) or None.
    scenarios / scenario_progress: see dsa_component. activity_dates + today: see streak_component.
    The streak is always available (zero activity is a real 0, not missing data).
    """
    return combine({
        "roadmap": roadmap_component(*roadmap) if roadmap else None,
        "skill_gap": skill_gap_component(*skill_gap) if skill_gap else None,
        "dsa": dsa_component(scenarios, scenario_progress),
        "streak": streak_component(activity_dates, today) if today is not None else None,
    })


def normalise_skill_mode(value):
    """A valid READINESS_SKILL_MODE, or the default for anything else (case and spaces ignored)."""
    mode = str(value or "").strip().lower()
    return mode if mode in SKILL_MODES else DEFAULT_SKILL_MODE


def skill_gap_breakdown(required, on_resume, verified, unreachable, mode):
    """
    How each required skill counts for the skill_gap component. Pure.
      required     the path's required skills; on_resume / verified / unreachable are sets of those names:
                   on the resume, verified (a tool skill with status "verified"), and not verifiable by any step, scenario
                   or code problem ("no LevelUp content for this yet")
    Returns {mode, required, on_resume, verified, value, items} where value is the numerator for (value, required) and each item
    is {skill, status, counts_for, on_resume, verified, no_content}. status is one of "verified", "claim_only" (nothing can
    verify it, it is on the resume), "resume_only", "no_content" (nothing can verify it, not on the resume) or "missing".
    mode "resume" gives a whole-number value (the old calculation); the others may be fractions.
    """
    mode = normalise_skill_mode(mode)
    items, value = [], 0
    for skill in required:
        is_resume, is_verified, no_content = skill in on_resume, skill in verified, skill in unreachable
        if is_verified:
            status = "verified"
        elif no_content:
            status = "claim_only" if is_resume else "no_content"
        else:
            status = "resume_only" if is_resume else "missing"
        if mode == "resume":
            counts = 1 if is_resume else 0
        elif mode == "verified":
            counts = 1 if is_verified else 0
        else:
            counts = {"verified": 1, "claim_only": CLAIM_ONLY_CREDIT, "resume_only": RESUME_CLAIM_CREDIT}.get(status, 0)
        value += counts
        items.append({"skill": skill, "status": status, "counts_for": counts, "on_resume": is_resume,
                      "verified": is_verified, "no_content": no_content})
    return {"mode": mode, "required": len(required), "on_resume": sum(i["on_resume"] for i in items),
            "verified": sum(i["verified"] for i in items), "value": value, "items": items}

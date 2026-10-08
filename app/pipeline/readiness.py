"""
Placement Readiness Score. Pure: no Flask, no database, no network. The route (app/routes/readiness.py)
gathers the numbers; everything that decides the score lives here so it can be unit-tested.

Four components, each 0..1 or unavailable (None):
  roadmap     completed roadmap steps / total steps
  skill_gap   skills acquired / skills required
  dsa         mean over the path's scenarios of best_score / max_score (unattempted = 0); unavailable when the
              path has no scenarios at all (that is "no content", not a score of 0)
  streak      days in the last 30 with at least one scenario submission or roadmap step completion / 30

Base weights are roadmap .25, skill_gap .35, dsa .30, streak .10. An unavailable component is dropped and the
remaining weights are re-normalised to sum to 1. The score is 0..100 rounded half-up to one decimal; a student is
"placement ready" at 70.0 or more (judged on the rounded score, so the number shown and the state always agree).
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

_UNITS = {"roadmap": 25, "skill_gap": 35, "dsa": 30, "streak": 10}   # hundredths: integer sums avoid float drift
BASE_WEIGHTS = {name: units / 100 for name, units in _UNITS.items()}
READY_THRESHOLD = 70.0
STREAK_WINDOW_DAYS = 30


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
    score = _round_1(100 * sum(weights[n] * clean[n] for n in present)) if present else None
    return {
        "score": score,
        "ready": score is not None and score >= READY_THRESHOLD,
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

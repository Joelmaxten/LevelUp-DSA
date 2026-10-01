"""
Pure functions over a CareerProfile's ranking - no Flask, no DB. Used by
the shared career-path picker (app/routes/career_paths.py) to decide which
of a profile's ranked paths count as "top matches" worth offering as a
quick choice, versus the full 15-path list.
"""

from app.pipeline.career_path_registry import CAREER_PATHS

DEFAULT_MARGIN = 1
DEFAULT_MAX_MATCHES = 4


def top_matches(ranking, margin=DEFAULT_MARGIN, max_matches=DEFAULT_MAX_MATCHES):
    """
    ranking: CareerProfile.career_ranking - a list of {"career_path", "score",
    "confidence_pct"} dicts (confirmed against profile_builder.rank_scores /
    career_quiz_engine.get_results, which both produce this exact shape, and
    a real database row), already sorted score-descending.

    Returns the paths whose score is within `margin` of the (highest-scoring
    valid) leader's score - ties and near-ties - in ranking order, capped at
    `max_matches`. An entry whose career_path isn't a current CAREER_PATHS
    member (e.g. a profile saved under an old path name before a
    restructuring) is ignored - it can't be picked anyway, since
    resolve_target_career_path validates against the same list.

    Returns [] for an empty (or entirely-invalid) ranking.
    """
    valid = [entry for entry in ranking if entry.get("career_path") in CAREER_PATHS]
    if not valid:
        return []

    leader_score = valid[0]["score"]
    matches = [entry for entry in valid if leader_score - entry["score"] <= margin]
    return matches[:max_matches]


def is_unambiguous(matches):
    """True only when there is exactly one top match."""
    return len(matches) == 1

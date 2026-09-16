"""
Combines the adaptive quiz's career-path scores with the post-quiz
conversation's signals into one final student profile.

ADJUSTMENT_RULES maps a (signal_key, signal_value) pair to a dict of
{career_path: score_delta}. As of this writing it is intentionally empty:
the only signal with a real causal link to ranking (it_track ->
non-traditional paths) can't be wired in yet because non-traditional career
paths don't exist in CAREER_PATHS (deliberately deferred - see RAG pipeline
scope decision in PROJECT_BIOGRAPHY.md). The other three signals (avoid,
target_company, goal) have no defensible causal link to *which* of the 10
existing CS paths fits better, so they never adjust score - they are carried
into the profile as plain context for the LLM roadmap prompt instead.

When non-traditional paths are added to CAREER_PATHS, populate this dict -
no other code in this module needs to change.
"""

from app.pipeline.career_quiz_data import CAREER_PATHS

ADJUSTMENT_RULES = {
    # Example of the shape this will take once non-traditional paths exist:
    # ("it_track", "non_traditional"): {"AI Entrepreneur": 2, "Product Manager (Tech)": 2},
}


def apply_adjustments(scores, signals):
    """
    Returns a NEW scores dict with ADJUSTMENT_RULES applied - does not
    mutate the quiz's original scores dict, since that's still owned by the
    quiz session and shouldn't be silently changed out from under it.
    """
    adjusted = dict(scores)

    for signal_key, signal_value in signals.items():
        rule = ADJUSTMENT_RULES.get((signal_key, signal_value))
        if not rule:
            continue
        for path, delta in rule.items():
            if path not in adjusted:
                # Rule references a career path that doesn't exist in
                # CAREER_PATHS yet - fail loudly rather than silently no-op,
                # since a typo'd path name here would otherwise vanish
                # without a trace.
                raise ValueError(
                    f"ADJUSTMENT_RULES references unknown career path: {path!r}"
                )
            adjusted[path] += delta

    return adjusted


def rank_scores(scores):
    """
    Recompute ranking + confidence_pct from a scores dict. Same formula as
    career_quiz_engine.get_results() - kept identical on purpose, so a
    profile built with zero adjustments produces byte-identical output to
    the quiz's own get_results().
    """
    total_signals = sum(scores.values()) or 1
    ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)

    return [
        {
            "career_path": path,
            "score": score,
            "confidence_pct": round((score / total_signals) * 100, 1),
        }
        for path, score in ranked
    ]


def build_profile(quiz_scores, conversation_signals):
    """
    quiz_scores: the quiz session's raw {career_path: score} dict (NOT
        get_results()'s already-ranked output - we need to adjust before
        ranking, not after).
    conversation_signals: the flat signals dict from
        conversation_engine.get_results().

    Returns the merged student profile.
    """
    adjusted_scores = apply_adjustments(quiz_scores, conversation_signals)

    return {
        "career_ranking": rank_scores(adjusted_scores),
        "conversation_signals": conversation_signals,
    }
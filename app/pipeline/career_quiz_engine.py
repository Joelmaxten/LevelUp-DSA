"""
Adaptive career-discovery quiz engine.

Approach: each answered question adds +1 to the score of every career path
it signals. To pick the *next* question, we look at all remaining
unanswered questions and estimate which one would create the most
separation among the currently leading candidates — a variance-based
proxy for information gain, not a full Bayesian calculation.
"""

import statistics

from app.pipeline.career_quiz_data import CAREER_PATHS, QUESTIONS, OPTION_SIGNALS

MIN_QUESTIONS = 8
MAX_QUESTIONS = 12
CONFIDENCE_GAP_THRESHOLD = 3  # top score must lead 2nd place by this much to stop early


def new_session():
    """Return a fresh quiz session state."""
    return {
        "scores": {path: 0 for path in CAREER_PATHS},
        "answered": [],  # list of {"question_id": ..., "option": ...}
        "asked_ids": [],
    }


def apply_answer(session, question_id, option):
    """Update scores based on one answered question, mutates and returns session."""
    signaled_paths = OPTION_SIGNALS.get((question_id, option), [])
    for path in signaled_paths:
        session["scores"][path] += 1

    session["answered"].append({"question_id": question_id, "option": option})
    if question_id not in session["asked_ids"]:
        session["asked_ids"].append(question_id)

    return session


def _estimate_information_gain(session, question_id):
    """
    For an unanswered question, simulate each of its options being picked,
    and measure how much the score *spread* among current top candidates
    would change. Higher spread = more separating power = higher priority.
    """
    current_leaders = sorted(session["scores"], key=session["scores"].get, reverse=True)[:4]

    resulting_top_scores = []
    for option in QUESTIONS[question_id]["options"]:
        signaled_paths = OPTION_SIGNALS.get((question_id, option), [])
        hypothetical_scores = [
            session["scores"][path] + (1 if path in signaled_paths else 0)
            for path in current_leaders
        ]
        resulting_top_scores.append(max(hypothetical_scores))

    if len(resulting_top_scores) < 2:
        return 0
    return statistics.pvariance(resulting_top_scores)


def next_question(session):
    """Pick the unanswered question with the highest estimated information gain."""
    unanswered = [qid for qid in QUESTIONS if qid not in session["asked_ids"]]
    if not unanswered:
        return None

    scored_questions = [
        (qid, _estimate_information_gain(session, qid)) for qid in unanswered
    ]
    scored_questions.sort(key=lambda pair: pair[1], reverse=True)
    return scored_questions[0][0]


def should_stop(session):
    """Decide whether we have enough confidence to stop early."""
    num_answered = len(session["answered"])

    if num_answered < MIN_QUESTIONS:
        return False
    if num_answered >= MAX_QUESTIONS:
        return True

    ranked = sorted(session["scores"].values(), reverse=True)
    top, second = ranked[0], ranked[1]
    return (top - second) >= CONFIDENCE_GAP_THRESHOLD


def get_results(session):
    """Return ranked career paths with confidence percentages."""
    total_signals = sum(session["scores"].values()) or 1
    ranked = sorted(session["scores"].items(), key=lambda pair: pair[1], reverse=True)

    return [
        {
            "career_path": path,
            "score": score,
            "confidence_pct": round((score / total_signals) * 100, 1),
        }
        for path, score in ranked
    ]
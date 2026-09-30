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


def rewind_last_answer(session):
    """
    Undo the most recent answer, so the student can look at it again or change it.
    Returns (question_id, option) of the undone answer, or None if nothing has been
    answered yet.

    Scores and asked_ids are rebuilt by replaying the answers that remain, rather than
    subtracting the undone answer's signals, so they can never drift out of step with
    the answered list. The quiz is adaptive, so changing an earlier answer can change
    which questions come next; that is why only the LAST answer is ever rewound.
    """
    if not session["answered"]:
        return None

    *kept, last = session["answered"]
    fresh = new_session()
    for entry in kept:
        apply_answer(fresh, entry["question_id"], entry["option"])

    session.clear()
    session.update(fresh)
    return last["question_id"], last["option"]


def _estimate_information_gain(session, question_id):
    """
    For an unanswered question, simulate each of its options being picked,
    and measure how much the score *spread* among current top candidates
    would change. Higher spread = more separating power = higher priority.
    """
    current_leaders = sorted(
        session["scores"],
        key=lambda path: (-session["scores"][path], path),
    )[:4]

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
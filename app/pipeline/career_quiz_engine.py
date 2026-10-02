"""
Adaptive career-discovery quiz engine.

Approach: each answered question adds +1 to the score of every career path
it signals. To pick the *next* question, we look at all remaining
unanswered questions and estimate which one would create the most
separation among the currently leading candidates — a variance-based
proxy for information gain, not a full Bayesian calculation.
"""

import statistics

from app.pipeline.career_path_registry import PAIR_PARTNER
from app.pipeline.career_quiz_data import CAREER_PATHS, QUESTIONS, OPTION_SIGNALS

MIN_QUESTIONS = 8
# Derived from the bank, so the maximum can never be a number of questions that does not exist
# (it used to be a fixed 12 with only 10 questions, so it was never reached).
MAX_QUESTIONS = min(14, len(QUESTIONS))
CONFIDENCE_GAP_THRESHOLD = 3  # the leader must be this far ahead of the best path that is not its pair partner to stop early
PAIR_GAP_THRESHOLD = 2        # a leader and its pair partner must be this far apart to stop early, unless no question can separate them


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
    """
    Pick the unanswered question with the highest estimated information gain.

    The one addition to that rule: when the leader and its pair partner (AI/ML, Data Science/
    Data Analytics, ...) are within 1 point of each other and some unasked question can separate
    them, only those separating questions are considered (still ranked by the same estimate).
    Without this the variance proxy, which only looks at the top scores, asked a question that
    could not tell the pair apart in about a fifth of such situations (see
    scripts/simulate_quiz.py).
    """
    unanswered = [qid for qid in QUESTIONS if qid not in session["asked_ids"]]
    if not unanswered:
        return None

    scores = session["scores"]
    leader = _leader(scores)
    partner = PAIR_PARTNER.get(leader)
    if partner is not None and abs(scores[leader] - scores[partner]) <= 1:
        separating = separating_questions(session, leader, partner)
        if separating:
            unanswered = separating

    scored_questions = [
        (qid, _estimate_information_gain(session, qid)) for qid in unanswered
    ]
    scored_questions.sort(key=lambda pair: pair[1], reverse=True)
    return scored_questions[0][0]


def _leader(scores):
    """The top-scoring path; ties are broken alphabetically, explicitly, so the result never depends on dict order."""
    return min(scores, key=lambda path: (-scores[path], path))


def separating_questions(session, path_a, path_b):
    """
    Ids of the questions NOT yet asked that have at least one option signalling exactly one of the two
    paths - i.e. questions whose answer can change the score difference between them.
    """
    return [
        qid for qid in QUESTIONS
        if qid not in session["asked_ids"]
        and any((path_a in OPTION_SIGNALS.get((qid, option), [])) != (path_b in OPTION_SIGNALS.get((qid, option), []))
                for option in QUESTIONS[qid]["options"])
    ]


def should_stop(session):
    """
    Decide whether we have enough confidence to stop early.

    Never before MIN_QUESTIONS answers; always at MAX_QUESTIONS. In between, stop only when
    - the leader is at least CONFIDENCE_GAP_THRESHOLD points ahead of the best path that is NOT its
      pair partner (an AI/ML or Data Science/Analytics-style pair is not a real runner-up: the quiz
      is meant to separate them with its own questions), AND
    - if the leader has a pair partner: they are at least PAIR_GAP_THRESHOLD points apart, or no
      unasked question can separate them any more (asking more would change nothing).
    """
    num_answered = len(session["answered"])

    if num_answered < MIN_QUESTIONS:
        return False
    if num_answered >= MAX_QUESTIONS:
        return True

    scores = session["scores"]
    leader = _leader(scores)
    partner = PAIR_PARTNER.get(leader)
    others = [score for path, score in scores.items() if path not in (leader, partner)]
    if scores[leader] - (max(others) if others else 0) < CONFIDENCE_GAP_THRESHOLD:
        return False

    if partner is not None and scores[leader] - scores[partner] < PAIR_GAP_THRESHOLD:
        return not separating_questions(session, leader, partner)
    return True


def get_results(session):
    """
    Return ranked career paths with confidence percentages. Ties are ordered alphabetically,
    explicitly (not by dict order, which Flask's session rewrites to sorted order anyway).
    Every entry whose score equals the top score also has "tied": true (a single such entry is just
    the winner; more than one is a tie - see tied_top()).
    """
    total_signals = sum(session["scores"].values()) or 1
    ranked = sorted(session["scores"].items(), key=lambda pair: (-pair[1], pair[0]))
    top_score = ranked[0][1]

    results = []
    for path, score in ranked:
        entry = {
            "career_path": path,
            "score": score,
            "confidence_pct": round((score / total_signals) * 100, 1),
        }
        if score == top_score:
            entry["tied"] = True
        results.append(entry)
    return results


def tied_top(results):
    """The paths whose score equals the top score, in registry order (one path when there is no tie)."""
    group = {entry["career_path"] for entry in results if entry.get("tied")}
    return [path for path in CAREER_PATHS if path in group]

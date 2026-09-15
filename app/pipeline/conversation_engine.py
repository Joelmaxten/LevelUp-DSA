"""
Engine for the fixed-order post-quiz conversation. Unlike career_quiz_engine.py,
there is no adaptivity here — questions are asked in a fixed order (C1-C4) and
each answer sets exactly one signal. State stores only an int index, never any
structure derived from iterating CONVERSATION_QUESTIONS, to avoid the dict-order
round-trip issue hit in the quiz engine's session handling.
"""

from app.pipeline.conversation_data import CONVERSATION_QUESTIONS, OPTION_SIGNALS

QUESTION_ORDER = list(CONVERSATION_QUESTIONS)  # ["C1", "C2", "C3", "C4"], fixed at import time


def new_session():
    """Fresh conversation state: no questions answered yet."""
    return {"index": 0, "signals": {}}


def next_question(state):
    """Returns the next question_id to ask, or None if the conversation is finished."""
    idx = state["index"]
    if idx >= len(QUESTION_ORDER):
        return None
    return QUESTION_ORDER[idx]


def apply_answer(state, question_id, option):
    """
    Records the signal for (question_id, option) and advances the index.
    Raises ValueError on an invalid question_id/option pair rather than letting
    a bad KeyError surface later as a 500 (same class of bug as the quiz's
    earlier KeyError: None crash — validate before indexing).
    """
    key = (question_id, option)
    if key not in OPTION_SIGNALS:
        raise ValueError(f"Invalid question_id/option pair: {key}")

    signal_key, signal_value = OPTION_SIGNALS[key]
    state["signals"][signal_key] = signal_value
    state["index"] += 1
    return state


def is_finished(state):
    return state["index"] >= len(QUESTION_ORDER)


def get_results(state):
    """Returns the flat signal dict — no scoring/ranking, unlike the quiz's get_results()."""
    return state["signals"]
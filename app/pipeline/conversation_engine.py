"""
Engine for the fixed-order post-quiz conversation. Unlike career_quiz_engine.py,
there is no adaptivity here — questions are asked in a fixed order (C1-C4) and
each answer sets exactly one signal. State stores only an int index, never any
structure derived from iterating CONVERSATION_QUESTIONS, to avoid the dict-order
round-trip issue hit in the quiz engine's session handling.
"""

import re

from app.pipeline.conversation_data import (
    CONVERSATION_QUESTIONS, MAX_ADDITIONAL_NOTES_CHARS, OPTION_SIGNALS,
)

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


def is_last_question(state):
    """True if the question about to be asked is the final fixed one."""
    return state["index"] == len(QUESTION_ORDER) - 1


def get_results(state):
    """Returns the flat signal dict — no scoring/ranking, unlike the quiz's get_results()."""
    return state["signals"]


def clean_additional_notes(raw):
    """
    Validates and normalizes the optional free-text note. Returns the cleaned
    text, or None if it was omitted/blank (a blank note is "not provided", so
    nothing is stored for it). Raises ValueError with a student-safe message
    if it isn't text or is too long - rejected rather than silently truncated,
    so a student never loses part of what they wrote without knowing.

    Cleaning: normalizes line endings, turns tabs into spaces, drops other
    control / non-printing characters, trims, and collapses runs of blank lines.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("Additional notes must be text.")

    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = "".join(ch for ch in text if ch == "\n" or ch.isprintable())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        return None
    if len(text) > MAX_ADDITIONAL_NOTES_CHARS:
        raise ValueError(
            f"Additional notes must be {MAX_ADDITIONAL_NOTES_CHARS} characters or fewer "
            f"(yours is {len(text)})."
        )
    return text

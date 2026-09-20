"""
"Resume where you left off": what the current user has already saved, so the
dashboard can show their existing results instead of restarting the flow.

Every table here allows multiple rows per user on purpose (retaking the quiz,
regenerating a roadmap, or re-uploading a resume adds a row rather than
overwriting), so "existing result" always means the newest row for that user.
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app.models import CareerProfile, GeneratedRoadmap, Resume, SkillGap
from app.pipeline.conversation_data import (
    ADDITIONAL_NOTES_KEY, ADDITIONAL_NOTES_PROMPT, CONVERSATION_QUESTIONS, OPTION_SIGNALS,
)
from app.routes._util import iso_utc
from app.routes.resume import latest_resume_analysis
from app.routes.roadmap import latest_roadmap

dashboard_bp = Blueprint("dashboard", __name__)


def _latest_career_profile(user_id):
    return (
        CareerProfile.query
        .filter_by(user_id=user_id)
        .order_by(CareerProfile.id.desc())
        .first()
    )


def describe_signals(signals):
    """
    Turns a saved conversation_signals dict (e.g. {"target_company": "startup"})
    back into readable {question, answer} pairs, using the same question/option
    tables the conversation itself used - so no separate label list to keep in sync.
    """
    answers = []
    for question_id in sorted(CONVERSATION_QUESTIONS):
        question = CONVERSATION_QUESTIONS[question_id]
        for option, option_text in question["options"].items():
            signal = OPTION_SIGNALS.get((question_id, option))
            if signal and signals.get(signal[0]) == signal[1]:
                answers.append({"question": question["text"], "answer": option_text})
                break

    # The optional free-text note isn't an option of any question, so it has no
    # entry above - add it (if the student wrote one) as the final item.
    if signals.get(ADDITIONAL_NOTES_KEY):
        answers.append({"question": ADDITIONAL_NOTES_PROMPT, "answer": signals[ADDITIONAL_NOTES_KEY]})
    return answers


def latest_career_profile(user_id):
    profile = _latest_career_profile(user_id)
    if profile is None:
        return None
    return {
        "created_at": iso_utc(profile.created_at),
        "career_ranking": profile.career_ranking,
        "answers": describe_signals(profile.conversation_signals or {}),
    }


def user_has_saved_work(user_id):
    """
    True if the user has any saved career profile, roadmap, or resume analysis.
    Cheap existence checks - the dashboard uses this to decide between showing
    their results and sending a brand-new user into the normal first-time flow.
    """
    return any(
        model.query.filter_by(user_id=user_id).first() is not None
        for model in (CareerProfile, GeneratedRoadmap, Resume, SkillGap)
    )


@dashboard_bp.route("/dashboard/data", methods=["GET"])
@login_required
def dashboard_data():
    return jsonify({
        "career_profile": latest_career_profile(current_user.id),
        "roadmap": latest_roadmap(current_user.id),
        "resume": latest_resume_analysis(current_user.id),
    }), 200

from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user

from app import db
from app.models import CareerProfile
from app.pipeline.conversation_engine import (
    new_session, apply_answer, next_question, is_finished, get_results,
)
from app.pipeline.conversation_data import CONVERSATION_QUESTIONS
from app.pipeline.profile_builder import build_profile

conversation_bp = Blueprint("conversation", __name__)


@conversation_bp.route("/conversation/start", methods=["POST"])
@login_required
def start_conversation():
    if "quiz_scores" not in session:
        return jsonify({"error": "Complete the career quiz before starting the conversation."}), 400

    session["conversation"] = new_session()
    q_id = next_question(session["conversation"])
    session.modified = True

    return jsonify({
        "question_id": q_id,
        "question": CONVERSATION_QUESTIONS[q_id],
    }), 200


@conversation_bp.route("/conversation/answer", methods=["POST"])
@login_required
def answer_conversation():
    if "conversation" not in session:
        return jsonify({"error": "No conversation in progress. Start one first."}), 400

    if "quiz_scores" not in session:
        # Defensive: shouldn't be reachable if /conversation/start gated correctly,
        # but never trust that a prior request left things in the expected state.
        return jsonify({"error": "Quiz scores missing from session. Complete the career quiz first."}), 400

    data = request.get_json()
    question_id = data.get("question_id")
    option = data.get("option")

    if not question_id or not option:
        return jsonify({"error": "question_id and option are required"}), 400

    convo_state = session["conversation"]

    try:
        apply_answer(convo_state, question_id, option)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    q_id = next_question(convo_state)

    if is_finished(convo_state) or q_id is None:
        signals = get_results(convo_state)
        profile = build_profile(session["quiz_scores"], signals)

        career_profile = CareerProfile(
            user_id=current_user.id,
            career_ranking=profile["career_ranking"],
            conversation_signals=profile["conversation_signals"],
        )

        try:
            db.session.add(career_profile)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Session state (conversation + quiz_scores) is deliberately left
            # intact here - the student's answers aren't lost, and this same
            # request can safely be retried once the underlying DB issue is fixed.
            return jsonify({
                "error": "Failed to save your career profile. Please try again.",
                "detail": str(e),
            }), 500

        session.pop("conversation")
        session.pop("quiz_scores")
        session.modified = True

        return jsonify({
            "finished": True,
            "profile": {
                "career_ranking": profile["career_ranking"],
                "conversation_signals": profile["conversation_signals"],
            },
        }), 200

    session["conversation"] = convo_state
    session.modified = True

    return jsonify({
        "finished": False,
        "question_id": q_id,
        "question": CONVERSATION_QUESTIONS[q_id],
    }), 200
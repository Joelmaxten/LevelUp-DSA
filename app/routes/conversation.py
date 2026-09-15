from flask import Blueprint, jsonify, request, session

from app.pipeline.conversation_engine import (
    new_session, apply_answer, next_question, is_finished, get_results,
)
from app.pipeline.conversation_data import CONVERSATION_QUESTIONS

conversation_bp = Blueprint("conversation", __name__)


@conversation_bp.route("/conversation/start", methods=["POST"])
def start_conversation():
    session["conversation"] = new_session()
    q_id = next_question(session["conversation"])
    session.modified = True

    return jsonify({
        "question_id": q_id,
        "question": CONVERSATION_QUESTIONS[q_id],
    }), 200


@conversation_bp.route("/conversation/answer", methods=["POST"])
def answer_conversation():
    if "conversation" not in session:
        return jsonify({"error": "No conversation in progress. Start one first."}), 400

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
        results = get_results(convo_state)
        session.pop("conversation")
        return jsonify({"finished": True, "signals": results}), 200

    session["conversation"] = convo_state
    session.modified = True

    return jsonify({
        "finished": False,
        "question_id": q_id,
        "question": CONVERSATION_QUESTIONS[q_id],
    }), 200
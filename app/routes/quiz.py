from flask import Blueprint, jsonify, session
from flask_login import login_required

from app.pipeline.career_quiz_engine import (
    new_session, apply_answer, next_question, should_stop, get_results,
)
from app.pipeline.career_quiz_data import QUESTIONS

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/quiz/start", methods=["POST"])
@login_required
def start_quiz():
    session["quiz"] = new_session()
    q_id = next_question(session["quiz"])
    session.modified = True

    return jsonify({
        "question_id": q_id,
        "question": QUESTIONS[q_id],
    }), 200


@quiz_bp.route("/quiz/answer", methods=["POST"])
@login_required
def answer_quiz():
    from flask import request

    if "quiz" not in session:
        return jsonify({"error": "No quiz in progress. Start a quiz first."}), 400

    data = request.get_json()
    question_id = data.get("question_id")
    option = data.get("option")

    if not question_id or not option:
        return jsonify({"error": "question_id and option are required"}), 400

    quiz_state = session["quiz"]
    apply_answer(quiz_state, question_id, option)

    q_id = next_question(quiz_state)

    if should_stop(quiz_state) or q_id is None:
        results = get_results(quiz_state)
        # Keep the raw scores dict alive for the conversation step to consume -
        # only the rest of the quiz state (answered/asked_ids) is discarded.
        session["quiz_scores"] = quiz_state["scores"]
        session.pop("quiz")
        session.modified = True
        return jsonify({"finished": True, "results": results}), 200

    session["quiz"] = quiz_state
    session.modified = True

    return jsonify({
        "finished": False,
        "question_id": q_id,
        "question": QUESTIONS[q_id],
    }), 200

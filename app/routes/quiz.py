from flask import Blueprint, jsonify, request, session
from flask_login import login_required

from app.pipeline.career_quiz_engine import (
    new_session, apply_answer, next_question, should_stop, get_results, rewind_last_answer, tied_top,
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
    if "quiz" not in session:
        return jsonify({"error": "No quiz in progress. Start a quiz first."}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    question_id = data.get("question_id")
    option = data.get("option")

    # Every question is mandatory: an answer is the only way forward, so it has to be a
    # real option of a real question that hasn't been answered yet.
    if not question_id or not option:
        return jsonify({"error": "question_id and option are required"}), 400
    if question_id not in QUESTIONS or option not in QUESTIONS[question_id]["options"]:
        return jsonify({"error": "That isn't a valid answer for this question."}), 400

    quiz_state = session["quiz"]
    if question_id in quiz_state["asked_ids"]:
        return jsonify({"error": "That question has already been answered."}), 400

    apply_answer(quiz_state, question_id, option)

    q_id = next_question(quiz_state)

    if should_stop(quiz_state) or q_id is None:
        results = get_results(quiz_state)
        # Keep the raw scores dict alive for the conversation step to consume -
        # only the rest of the quiz state (answered/asked_ids) is discarded.
        session["quiz_scores"] = quiz_state["scores"]
        session.pop("quiz")
        session.modified = True
        # tied_top: every path that shares the top score, in registry order (one path = no tie).
        return jsonify({"finished": True, "results": results, "tied_top": tied_top(results)}), 200

    session["quiz"] = quiz_state
    session.modified = True

    return jsonify({
        "finished": False,
        "question_id": q_id,
        "question": QUESTIONS[q_id],
    }), 200


@quiz_bp.route("/quiz/back", methods=["POST"])
@login_required
def back_quiz():
    """
    Step back one question. The last answer is undone on the server, so the client's
    "Previous" and the server's state can't disagree, and the student re-submits (the
    same answer or a different one) with "Next". Returns the question they're back on
    and the option they had chosen, so it can be shown pre-selected.
    """
    if "quiz" not in session:
        return jsonify({"error": "No quiz in progress. Start a quiz first."}), 400

    quiz_state = session["quiz"]
    undone = rewind_last_answer(quiz_state)
    if undone is None:
        return jsonify({"error": "There is no earlier question."}), 400

    question_id, option = undone
    session["quiz"] = quiz_state
    session.modified = True

    return jsonify({
        "question_id": question_id,
        "question": QUESTIONS[question_id],
        "option": option,
    }), 200

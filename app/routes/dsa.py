"""
Skill DNA Map, Stage 1 (static map): the graph with per-student lock/mastery state,
a node's problems, and each problem's career-contextualised framing. Nothing here
runs or grades code yet; that is Stage 2.

Locks are enforced here, not just drawn by the frontend: a locked node's problems and
framings are refused with 403, so hitting the API directly can't skip a prerequisite.
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    CareerPath, CareerProfile, DSANode, DSAProblem, DSAProblemFraming,
    NodeMastery, UserDSAActivity,
)
from app.pipeline.dsa_graph import (
    LOCKED, MASTERED, MASTERY_THRESHOLD, UNLOCKED, compute_node_states, layer_depths, topological_order,
)
from app.pipeline.dsa_seed_data import POINTS_BY_DIFFICULTY
from app.pipeline.problem_framing import generate_framing
from app.routes._util import resolve_target_career_path

dsa_bp = Blueprint("dsa", __name__)

DIFFICULTY_BY_POINTS = {points: name for name, points in POINTS_BY_DIFFICULTY.items()}
EXAMPLES_SHOWN = 2  # leading test cases shown as worked examples; any further ones stay unseen


def _career_path_for_user():
    profile = (
        CareerProfile.query
        .filter_by(user_id=current_user.id)
        .order_by(CareerProfile.id.desc())
        .first()
    )
    return resolve_target_career_path(profile)


def _load_map(user_id):
    """
    (nodes, states) for this user: nodes in topological order, states as returned by
    compute_node_states. nodes is empty if the DSA tables haven't been seeded.
    """
    nodes = {n.id: n for n in DSANode.query.all()}
    if not nodes:
        return [], {}
    prerequisites = {n.id: list(n.prerequisites or []) for n in nodes.values()}
    mastery = {
        m.node_id: m.mastery_level
        for m in NodeMastery.query.filter_by(user_id=user_id).all()
    }
    order = topological_order(prerequisites)
    return [nodes[i] for i in order], compute_node_states(prerequisites, mastery)


def dsa_progress(user_id):
    """
    Where the user stands on the skill map, for the dashboard: how many topics are mastered,
    whether they've started at all, and the next few open topics to work on (in learning
    order). None if the DSA tables haven't been seeded, so the dashboard can leave the
    section out rather than show an empty one.
    """
    nodes, states = _load_map(user_id)
    if not nodes:
        return None
    mastered = sum(1 for s in states.values() if s["state"] == MASTERED)
    return {
        "mastered": mastered,
        "total": len(nodes),
        "locked": sum(1 for s in states.values() if s["state"] == LOCKED),
        "started": any(s["mastery_level"] > 0 for s in states.values()),
        "next_up": [n.topic for n in nodes if states[n.id]["state"] == UNLOCKED][:3],
    }


def _locked_response(node, state, nodes_by_id):
    blockers = [{"id": p, "topic": nodes_by_id[p].topic} for p in state["blocked_by"]]
    names = ", ".join(b["topic"] for b in blockers)
    return jsonify({
        "error": "node_locked",
        "message": f"{node.topic} is locked. Master {names} first.",
        "blocked_by": blockers,
    }), 403


@dsa_bp.route("/dsa/map", methods=["GET"])
@login_required
def get_map():
    career_path, error = _career_path_for_user()
    if error:
        return error

    nodes, states = _load_map(current_user.id)
    if not nodes:
        return jsonify({
            "error": "The DSA map hasn't been set up on this server yet. Run scripts/seed_dsa.py."
        }), 503

    nodes_by_id = {n.id: n for n in nodes}
    depth = layer_depths({n.id: list(n.prerequisites or []) for n in nodes})

    # Which nodes to highlight: DSANode.career_paths holds CareerPath ids. A path with
    # no CareerPath row (unseeded) just highlights nothing rather than failing.
    path_row = CareerPath.query.filter_by(name=career_path).first()
    path_id = path_row.id if path_row else None

    problem_counts = dict(
        db.session.query(DSAProblem.node_id, db.func.count(DSAProblem.id)).group_by(DSAProblem.node_id).all()
    )
    solved_counts = {
        m.node_id: m.problems_solved
        for m in NodeMastery.query.filter_by(user_id=current_user.id).all()
    }

    payload_nodes = []
    for node in nodes:
        state = states[node.id]
        payload_nodes.append({
            "id": node.id,
            "topic": node.topic,
            "difficulty": node.difficulty,
            "layer": depth[node.id],
            "prerequisites": list(node.prerequisites or []),
            "state": state["state"],
            "mastery_level": state["mastery_level"],
            "blocked_by": [{"id": p, "topic": nodes_by_id[p].topic} for p in state["blocked_by"]],
            "career_relevant": path_id is not None and path_id in (node.career_paths or []),
            "problem_count": problem_counts.get(node.id, 0),
            "problems_solved": solved_counts.get(node.id, 0),
        })

    return jsonify({
        "career_path": career_path,
        "mastery_threshold": MASTERY_THRESHOLD,
        "nodes": payload_nodes,
        "edges": [
            {"source": prereq, "target": node.id}
            for node in nodes for prereq in (node.prerequisites or [])
        ],
        "summary": {
            "mastered": sum(1 for n in payload_nodes if n["state"] == MASTERED),
            "total": len(payload_nodes),
        },
    }), 200


@dsa_bp.route("/dsa/nodes/<int:node_id>/problems", methods=["GET"])
@login_required
def get_node_problems(node_id):
    node = db.session.get(DSANode, node_id)
    if node is None:
        return jsonify({"error": "That topic doesn't exist."}), 404

    nodes, states = _load_map(current_user.id)
    state = states[node.id]
    if state["state"] == LOCKED:
        return _locked_response(node, state, {n.id: n for n in nodes})

    problems = DSAProblem.query.filter_by(node_id=node.id).order_by(DSAProblem.id).all()
    solved_ids = {
        row.problem_id
        for row in UserDSAActivity.query.filter_by(user_id=current_user.id).all()
    }

    return jsonify({
        "node": {
            "id": node.id,
            "topic": node.topic,
            "difficulty": node.difficulty,
            "state": state["state"],
            "mastery_level": state["mastery_level"],
        },
        "problems": [
            {
                "id": problem.id,
                "title": problem.title,
                "difficulty": DIFFICULTY_BY_POINTS.get(problem.points, "Easy"),
                "points": problem.points,
                "description": problem.description,
                "examples": (problem.test_cases or [])[:EXAMPLES_SHOWN],
                "solved": problem.id in solved_ids,
            }
            for problem in problems
        ],
    }), 200


@dsa_bp.route("/dsa/problems/<int:problem_id>/framing", methods=["POST"])
@login_required
def get_problem_framing(problem_id):
    problem = db.session.get(DSAProblem, problem_id)
    if problem is None:
        return jsonify({"error": "That problem doesn't exist."}), 404

    nodes, states = _load_map(current_user.id)
    state = states[problem.node_id]
    if state["state"] == LOCKED:
        return _locked_response(problem.node, state, {n.id: n for n in nodes})

    career_path, error = _career_path_for_user()
    if error:
        return error

    cached = DSAProblemFraming.query.filter_by(problem_id=problem.id, career_path=career_path).first()
    if cached is not None:
        return jsonify({"problem_id": problem.id, "career_path": career_path,
                        "narrative": cached.narrative, "cached": True}), 200

    try:
        narrative = generate_framing(problem.title, problem.node.topic, problem.description, career_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 502

    framing = DSAProblemFraming(problem_id=problem.id, career_path=career_path, narrative=narrative)
    try:
        db.session.add(framing)
        db.session.commit()
    except IntegrityError:
        # Another request cached this (problem, path) while Gemini was thinking. Theirs wins.
        db.session.rollback()
        winner = DSAProblemFraming.query.filter_by(problem_id=problem.id, career_path=career_path).first()
        narrative = winner.narrative if winner else narrative
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to save the problem framing.", "detail": str(e)}), 500

    return jsonify({"problem_id": problem.id, "career_path": career_path,
                    "narrative": narrative, "cached": False}), 200

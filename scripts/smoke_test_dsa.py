"""
Smoke test for the Skill DNA Map backend (Phase 3, Stage 1), through Flask's test
client against the real database (seed it first: scripts/seed_dsa.py). Sets mastery
directly in node_mastery, the way you would by hand, and checks that the lock
states and the server-side lock enforcement follow. Makes one real Gemini call for
the framing check. Deletes the throwaway user and its rows when done.

Run:  python scripts/smoke_test_dsa.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from scripts._csrf import enable_csrf_client
from app import create_app, db
from app import models
from app.pipeline.career_path_registry import FULL_STACK
from app.pipeline.dsa_graph import MASTERY_THRESHOLD

PATH = FULL_STACK

app = create_app()

enable_csrf_client(app)


def set_mastery(user_id, topic, level):
    node = models.DSANode.query.filter_by(topic=topic).one()
    row = models.NodeMastery.query.filter_by(user_id=user_id, node_id=node.id).first()
    if row is None:
        row = models.NodeMastery(user_id=user_id, node_id=node.id)
        db.session.add(row)
    row.mastery_level = level
    db.session.commit()


def states(client):
    resp = client.get("/dsa/map", query_string={"target_career_path": PATH})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {n["topic"]: n for n in resp.get_json()["nodes"]}


def state_of(client):
    return {topic: n["state"] for topic, n in states(client).items()}


with app.app_context():
    assert models.DSANode.query.count() > 0, "run scripts/seed_dsa.py first"

with app.test_client() as client:
    email = f"dsatest{random.randint(10000, 99999)}@example.com"
    assert client.post("/signup", json={"name": "DSA Test", "email": email, "password": "Testpass#123"}).status_code == 201
    assert client.post("/login", json={"email": email, "password": "Testpass#123"}).status_code == 200
    with app.app_context():
        user_id = models.User.query.filter_by(email=email).one().id

    try:
        # --- career path handling (no quiz taken, so the server must ask) ---
        resp = client.get("/dsa/map")
        assert resp.status_code == 400 and resp.get_json()["error"] == "career_path_required"
        resp = client.get("/dsa/map", query_string={"target_career_path": "Underwater Basket Weaving"})
        assert resp.status_code == 400 and resp.get_json()["error"] == "invalid_career_path"
        print("ok: map asks for a career path, rejects an invalid one")

        # --- fresh student: only the root is open ---
        s = state_of(client)
        assert s["Arrays"] == "unlocked", s
        assert all(v == "locked" for t, v in s.items() if t != "Arrays"), s
        data = client.get("/dsa/map", query_string={"target_career_path": PATH}).get_json()
        assert data["mastery_threshold"] == MASTERY_THRESHOLD
        highlighted = sorted(n["topic"] for n in data["nodes"] if n["career_relevant"])
        assert "Hash Maps & Sets" in highlighted and "Graphs" not in highlighted, highlighted
        print(f"ok: fresh student has 1 unlocked node (Arrays), {len(highlighted)} highlighted for Full-Stack")

        # --- server enforces locks, not just the UI ---
        with app.app_context():
            trees = models.DSANode.query.filter_by(topic="Trees").one()
            trees_problem = models.DSAProblem.query.filter_by(node_id=trees.id).first()
            arrays = models.DSANode.query.filter_by(topic="Arrays").one()
            arrays_problem = models.DSAProblem.query.filter_by(node_id=arrays.id).first()
            trees_id, trees_problem_id = trees.id, trees_problem.id
            arrays_id, arrays_problem_id = arrays.id, arrays_problem.id
        resp = client.get(f"/dsa/nodes/{trees_id}/problems")
        assert resp.status_code == 403 and resp.get_json()["error"] == "node_locked", resp.get_json()
        print("ok: locked node's problems refused:", resp.get_json()["message"])
        resp = client.post(f"/dsa/problems/{trees_problem_id}/framing", json={"target_career_path": PATH})
        assert resp.status_code == 403, resp.get_json()
        print("ok: locked problem's framing refused (no Gemini call spent)")

        # --- threshold boundary on the root ---
        with app.app_context():
            set_mastery(user_id, "Arrays", MASTERY_THRESHOLD - 0.01)
        s = state_of(client)
        assert s["Arrays"] == "unlocked" and s["Strings"] == "locked", s
        with app.app_context():
            set_mastery(user_id, "Arrays", MASTERY_THRESHOLD)
        s = state_of(client)
        assert s["Arrays"] == "mastered", s
        opened = sorted(t for t, v in s.items() if v == "unlocked")
        assert opened == ["Hash Maps & Sets", "Linked Lists", "Sorting", "Stacks & Queues", "Strings", "Two Pointers"], opened
        assert s["Sliding Window"] == "locked" and s["Trees"] == "locked", s
        print(f"ok: Arrays at {MASTERY_THRESHOLD - 0.01:.2f} keeps Strings locked; at {MASTERY_THRESHOLD:.2f} it opens {len(opened)} nodes")

        # --- a node with TWO prerequisites needs both ---
        with app.app_context():
            set_mastery(user_id, "Two Pointers", 1.0)
        assert state_of(client)["Sliding Window"] == "locked"
        with app.app_context():
            set_mastery(user_id, "Hash Maps & Sets", 1.0)
        assert state_of(client)["Sliding Window"] == "unlocked"
        print("ok: Sliding Window (needs Two Pointers AND Hash Maps) opens only when both are mastered")

        # --- can't skip ahead by tampering with a deep node ---
        with app.app_context():
            set_mastery(user_id, "Trees", 1.0)       # Recursion / Linked Lists never mastered
        s = state_of(client)
        assert s["Trees"] == "locked" and s["Graphs"] == "locked" and s["Heaps"] == "locked", s
        print("ok: mastery 1.0 on Trees does not open Graphs/Heaps while Trees itself is locked")

        # --- unlocked node: problems are served, examples capped, canonical text intact ---
        resp = client.get(f"/dsa/nodes/{arrays_id}/problems")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["node"]["state"] == "mastered" and len(body["problems"]) == 2
        for problem in body["problems"]:
            assert len(problem["examples"]) <= 2 and problem["description"]
            assert set(problem) == {"id", "title", "difficulty", "points", "description", "examples", "solved"}
        print("ok: unlocked node serves", [p["title"] for p in body["problems"]])

        # --- framing: one real Gemini call, then served from cache ---
        with app.app_context():   # a cached row from an earlier run would hide the generate path
            models.DSAProblemFraming.query.filter_by(problem_id=arrays_problem_id, career_path=PATH).delete()
            db.session.commit()
        resp = client.post(f"/dsa/problems/{arrays_problem_id}/framing", json={"target_career_path": PATH})
        assert resp.status_code == 200, resp.get_json()
        first = resp.get_json()
        assert first["cached"] is False and len(first["narrative"]) > 60
        again = client.post(f"/dsa/problems/{arrays_problem_id}/framing", json={"target_career_path": PATH}).get_json()
        assert again["cached"] is True and again["narrative"] == first["narrative"]
        print("ok: framing generated then cached:\n   ", first["narrative"])

        # --- whole map mastered ---
        with app.app_context():
            for node in models.DSANode.query.all():
                set_mastery(user_id, node.topic, 1.0)
        s = state_of(client)
        assert set(s.values()) == {"mastered"}, s
        print("ok: everything mastered -> every node 'mastered'")
        print("\nALL DSA SMOKE CHECKS PASSED")
    finally:
        with app.app_context():
            models.NodeMastery.query.filter_by(user_id=user_id).delete()
            models.User.query.filter_by(id=user_id).delete()
            db.session.commit()

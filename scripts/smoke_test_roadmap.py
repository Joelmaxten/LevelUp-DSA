"""
One-off smoke test driving the full quiz -> conversation -> roadmap generation
flow through Flask's test client, using the real FAISS index built on this
machine. First real end-to-end test of /roadmap/generate.

roadmap_generator.py now returns a phased roadmap ({"phases": [{"phase_number",
"title", "steps": [...]}]}) instead of a flat step list, so this test's own
job - exercising current behavior, not preserving the old flat shape - means
reading result["steps"]["phases"][*]["steps"] rather than result["steps"]
directly.
"""
import random

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app import models

app = create_app()

with app.app_context():
    db.create_all()

with app.test_client() as client:
    email = f"roadmaptest{random.randint(1000, 9999)}@example.com"

    resp = client.post("/signup", json={
        "name": "Roadmap Test", "email": email, "password": "Testpass#123",
    })
    assert resp.status_code == 201

    resp = client.post("/login", json={"email": email, "password": "Testpass#123"})
    assert resp.status_code == 200

    resp = client.post("/quiz/start")
    data = resp.get_json()
    while True:
        q_id = data["question_id"]
        resp = client.post("/quiz/answer", json={"question_id": q_id, "option": "A"})
        data = resp.get_json()
        if data.get("finished"):
            print("quiz finished. #1 path:", data["results"][0]["career_path"])
            break

    resp = client.post("/conversation/start")
    data = resp.get_json()
    while True:
        q_id = data["question_id"]
        option = sorted(data["question"]["options"].keys())[0]
        resp = client.post("/conversation/answer", json={"question_id": q_id, "option": option})
        data = resp.get_json()
        if data.get("finished"):
            print("conversation finished. signals:", data["profile"]["conversation_signals"])
            break

    print()
    print("Calling /roadmap/generate ...")
    resp = client.post("/roadmap/generate")
    print("Status:", resp.status_code)
    result = resp.get_json()

    if resp.status_code == 201:
        phases = result["steps"]["phases"]
        total_steps = sum(len(phase["steps"]) for phase in phases)
        print("Career path:", result["career_path"])
        print(f"Phases generated: {len(phases)}")
        print(f"Total steps across all phases: {total_steps}")
        print()
        for phase in phases:
            print(f"Phase {phase['phase_number']}: {phase['title']} ({len(phase['steps'])} steps)")
            for step in phase["steps"]:
                print(f"  {step.get('global_step_index')} (phase step {step.get('step_number')}). {step.get('title')}")
                print(f"     {step.get('description')}")
            print()
    else:
        print("ERROR:", result)

"""
One-off smoke test driving the full quiz -> conversation -> CareerProfile
flow through Flask's test client. Not part of the app itself - throwaway
verification script, safe to delete after use or keep for future re-runs.
"""
import random

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app import models
from app.models import CareerProfile, User

app = create_app()

with app.app_context():
    db.create_all()  # no-op if tables already exist

with app.test_client() as client:
    email = f"smoketest{random.randint(1000, 9999)}@example.com"

    resp = client.post("/signup", json={
        "name": "Smoke Test",
        "email": email,
        "password": "testpass123",
    })
    print("signup:", resp.status_code, resp.get_json())
    assert resp.status_code == 201

    resp = client.post("/login", json={"email": email, "password": "testpass123"})
    print("login:", resp.status_code, resp.get_json())
    assert resp.status_code == 200

    # Drive the quiz to completion, always answering "A"
    resp = client.post("/quiz/start")
    data = resp.get_json()
    print("quiz start:", data["question_id"])

    while True:
        q_id = data["question_id"]
        resp = client.post("/quiz/answer", json={"question_id": q_id, "option": "A"})
        data = resp.get_json()
        if data.get("finished"):
            print("quiz finished. top 3 results:", data["results"][:3])
            break
        print("  quiz next:", data["question_id"])

    # Drive the conversation to completion, always picking the first option
    resp = client.post("/conversation/start")
    data = resp.get_json()
    print("conversation start:", resp.status_code, data.get("question_id"))
    assert resp.status_code == 200

    while True:
        q_id = data["question_id"]
        option = sorted(data["question"]["options"].keys())[0]
        resp = client.post("/conversation/answer", json={"question_id": q_id, "option": option})
        data = resp.get_json()
        if data.get("finished"):
            print("conversation finished:")
            print("  career_ranking top 3:", data["profile"]["career_ranking"][:3])
            print("  conversation_signals:", data["profile"]["conversation_signals"])
            break
        print("  conversation next:", data["question_id"])

# Verify the DB row directly - not just trusting the JSON response
with app.app_context():
    user = User.query.filter_by(email=email).first()
    profile = (
        CareerProfile.query
        .filter_by(user_id=user.id)
        .order_by(CareerProfile.id.desc())
        .first()
    )
    print()
    print("DB check - CareerProfile row found:", profile is not None)
    if profile:
        print("  user_id:", profile.user_id)
        print("  career_ranking top 2:", profile.career_ranking[:2])
        print("  conversation_signals:", profile.conversation_signals)
        print("  created_at:", profile.created_at)

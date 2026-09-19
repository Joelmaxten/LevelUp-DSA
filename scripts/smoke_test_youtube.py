"""
Extends the roadmap smoke test to also verify /roadmap/<id>/resources -
first real end-to-end test of YouTube resource attachment.
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
    email = f"ytresourcetest{random.randint(1000, 9999)}@example.com"

    client.post("/signup", json={"name": "YT Test", "email": email, "password": "testpass123"})
    client.post("/login", json={"email": email, "password": "testpass123"})

    resp = client.post("/quiz/start")
    data = resp.get_json()
    while True:
        q_id = data["question_id"]
        resp = client.post("/quiz/answer", json={"question_id": q_id, "option": "A"})
        data = resp.get_json()
        if data.get("finished"):
            break

    resp = client.post("/conversation/start")
    data = resp.get_json()
    while True:
        q_id = data["question_id"]
        option = sorted(data["question"]["options"].keys())[0]
        resp = client.post("/conversation/answer", json={"question_id": q_id, "option": option})
        data = resp.get_json()
        if data.get("finished"):
            break

    resp = client.post("/roadmap/generate")
    print("Roadmap generation status:", resp.status_code)
    result = resp.get_json()

    if resp.status_code != 201:
        print("ERROR generating roadmap:", result)
    else:
        # Fetch the roadmap's actual DB id, since /roadmap/generate's response
        # doesn't currently include it (only career_path + steps).
        from app.models import GeneratedRoadmap
        roadmap_row = GeneratedRoadmap.query.order_by(GeneratedRoadmap.id.desc()).first()

        print("Career path:", result["career_path"])
        print("Roadmap ID:", roadmap_row.id)
        print()
        print("Calling /roadmap/<id>/resources ...")
        resp = client.post(f"/roadmap/{roadmap_row.id}/resources")
        print("Status:", resp.status_code)
        result = resp.get_json()

        if resp.status_code == 200:
            for step in result["steps"]:
                print(f"  {step.get('step_number')}. {step.get('title')}")
                resource = step.get("resource")
                if resource:
                    print(f"     -> {resource['title']}")
                    print(f"        {resource['url']}")
                else:
                    print("     -> No resource found")
        else:
            print("ERROR:", result)

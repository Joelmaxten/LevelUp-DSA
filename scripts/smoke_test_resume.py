"""
End-to-end smoke test for /resume/upload: signup -> quiz -> conversation
(to get a CareerProfile) -> generate a test PDF -> upload it -> verify the
skill extraction, gap analysis, and DB persistence all worked.
"""
import random

from dotenv import load_dotenv
load_dotenv()

from fpdf import FPDF

from app import create_app, db
from app import models

app = create_app()

with app.app_context():
    db.create_all()

# Generate a test resume PDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
resume_text = """John Doe
Software Engineer

SKILLS
Python, JavaScript, React, Node.js, PostgreSQL, MongoDB, Docker, AWS, Git
"""
for line in resume_text.split("\n"):
    pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")
pdf.output("test_resume.pdf")

with app.test_client() as client:
    email = f"resumetest{random.randint(1000, 9999)}@example.com"

    client.post("/signup", json={"name": "Resume Test", "email": email, "password": "Testpass#123"})
    client.post("/login", json={"email": email, "password": "Testpass#123"})

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

    print("Career profile created. Uploading resume...")
    print()

    with open("test_resume.pdf", "rb") as f:
        resp = client.post(
            "/resume/upload",
            data={"resume": (f, "test_resume.pdf")},
            content_type="multipart/form-data",
        )

    print("Status:", resp.status_code)
    result = resp.get_json()
    print("Target career path:", result.get("target_career_path"))
    print("Student skills:", result.get("student_skills"))
    print("Matched skills:", result.get("matched_skills"))
    print("Missing skills:", result.get("missing_skills"))
    print()
    print("AI Feedback:")
    print(result.get("ai_feedback"))

    if resp.status_code == 201:
        from app.models import Resume, SkillGap
        resume_row = Resume.query.get(result["resume_id"])
        skill_gap_row = SkillGap.query.filter_by(user_id=resume_row.user_id).order_by(SkillGap.id.desc()).first()
        print()
        print("DB check - Resume.extracted_skills:", resume_row.extracted_skills)
        print("DB check - SkillGap.missing_skills:", skill_gap_row.missing_skills)
        print("DB check - SkillGap.target_role:", skill_gap_row.target_role)

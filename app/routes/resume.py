import os
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import CareerProfile, Resume, SkillGap
from app.pipeline.resume_analyzer import analyze_resume
from app.pipeline.resume_feedback import generate_resume_feedback
from app.pipeline.salary_matching import get_salary_insights, format_salary_range_summary

resume_bp = Blueprint("resume", __name__)

ALLOWED_EXTENSIONS = {"pdf"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@resume_bp.route("/resume/upload", methods=["POST"])
@login_required
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No file provided. Send it under the 'resume' field."}), 400

    file = request.files["resume"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    profile = (
        CareerProfile.query
        .filter_by(user_id=current_user.id)
        .order_by(CareerProfile.id.desc())
        .first()
    )
    if profile is None:
        return jsonify({
            "error": "No career profile found. Complete the quiz and conversation first."
        }), 400

    target_career_path = profile.career_ranking[0]["career_path"]

    # Unique filename per upload - avoids collisions between students, and
    # between repeated uploads from the same student (Resume allows multiple
    # rows per user, same precedent as CareerProfile/GeneratedRoadmap).
    safe_name = secure_filename(file.filename)
    unique_name = f"{current_user.id}_{uuid.uuid4().hex}_{safe_name}"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file.save(file_path)

    try:
        result = analyze_resume(file_path, target_career_path)
    except Exception as e:
        return jsonify({
            "error": "Failed to analyze resume. The PDF may be unreadable or corrupted.",
            "detail": str(e),
        }), 422

    try:
        feedback = generate_resume_feedback(
            result["extracted_text"], target_career_path,
            result["matched_skills"], result["missing_skills"],
        )
    except ValueError:
        # Same graceful-degradation principle as roadmap generation: if
        # Gemini is unavailable, still save the (already-computed) skill
        # analysis rather than losing the whole upload - feedback can be
        # regenerated later, the skill gap itself doesn't depend on it.
        feedback = None

    resume = Resume(
        user_id=current_user.id,
        file_path=file_path,
        extracted_skills=sorted(result["student_skills"]),
        ai_feedback=feedback,
    )

    salary_insights = get_salary_insights(target_career_path)
    salary_summary = format_salary_range_summary(salary_insights)

    skill_gap = SkillGap(
        user_id=current_user.id,
        missing_skills=sorted(result["missing_skills"]),
        target_role=target_career_path,
        salary_range=salary_summary,
    )

    try:
        db.session.add(resume)
        db.session.add(skill_gap)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to save resume analysis. Please try again.",
            "detail": str(e),
        }), 500

    return jsonify({
        "resume_id": resume.id,
        "target_career_path": target_career_path,
        "student_skills": sorted(result["student_skills"]),
        "matched_skills": sorted(result["matched_skills"]),
        "missing_skills": sorted(result["missing_skills"]),
        "ai_feedback": resume.ai_feedback,
        "salary_insights": salary_insights,
    }), 201
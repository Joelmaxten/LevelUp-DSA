import os
import re
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import CareerProfile, Resume, SkillGap
from app.pipeline.resume_analyzer import analyze_resume, extract_text_from_pdf, get_required_skills
from app.pipeline.resume_feedback import generate_resume_feedback
from app.pipeline.salary_matching import get_salary_insights, format_salary_range_summary
from app.pipeline.ats_score import compute_ats_score
from app.routes._util import iso_utc

resume_bp = Blueprint("resume", __name__)

ALLOWED_EXTENSIONS = {"pdf"}

# Saved files are named f"{user_id}_{uuid4().hex}_{secure_filename(original)}" (see upload_resume).
_SAVED_NAME = re.compile(r"^\d+_[0-9a-f]{32}_(?P<original>.+)$")


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def latest_resume_analysis(user_id):
    """
    The user's most recent resume analysis, in the same shape /resume/upload
    returns (plus resume_id-adjacent extras), or None if they've never uploaded.

    Only the extracted skills, missing skills, target role and AI feedback are
    persisted - matched skills, salary insights and the ATS score are computed
    at upload time and not stored. So they're rebuilt here from what IS stored:
    matched = required skills for the saved target_role AND the saved skills;
    salary from the DB; ATS by re-reading the saved PDF (skipped with None if
    that file is no longer on disk or can't be read).
    """
    resume = Resume.query.filter_by(user_id=user_id).order_by(Resume.id.desc()).first()
    skill_gap = SkillGap.query.filter_by(user_id=user_id).order_by(SkillGap.id.desc()).first()
    if resume is None or skill_gap is None:
        return None

    target_career_path = skill_gap.target_role
    student_skills = set(resume.extracted_skills or [])
    required_skills = get_required_skills(target_career_path)
    matched_skills = required_skills & student_skills

    ats_score = None
    if resume.file_path and os.path.isfile(resume.file_path):
        try:
            text = extract_text_from_pdf(resume.file_path)
            ats_score = compute_ats_score(text, matched_skills, required_skills)
        except Exception:
            ats_score = None  # unreadable now - show everything else rather than fail the whole view

    name_match = _SAVED_NAME.match(os.path.basename(resume.file_path or ""))

    return {
        "resume_id": resume.id,
        "file_name": name_match.group("original") if name_match else None,
        "uploaded_at": iso_utc(resume.uploaded_at),
        "target_career_path": target_career_path,
        "student_skills": sorted(student_skills),
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted(skill_gap.missing_skills or []),
        "ai_feedback": resume.ai_feedback,
        "salary_insights": get_salary_insights(target_career_path),
        "ats_score": ats_score,
    }


@resume_bp.route("/resume/latest", methods=["GET"])
@login_required
def get_latest():
    analysis = latest_resume_analysis(current_user.id)
    if analysis is None:
        return jsonify({"error": "No resume analyzed yet."}), 404
    return jsonify(analysis), 200


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
    ats = compute_ats_score(result["extracted_text"], result["matched_skills"], result["required_skills"])

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
        "ats_score": ats,
    }), 201
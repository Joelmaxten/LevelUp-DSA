import os
import re
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import CareerProfile, Resume, SkillGap
from app.pipeline.adzuna_listings import get_live_listings
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.resume_analyzer import (
    analyze_resume, extract_text_from_pdf, get_pdf_page_count, get_extended_skill_vocabulary, get_required_skills,
)
from app.pipeline.resume_skill_extractor import extract_skills
from app.pipeline.resume_feedback import generate_resume_feedback
from app.pipeline.salary_matching import get_salary_insights, format_salary_range_summary
from app.pipeline.skill_matching import resolve_required
from app.pipeline.ats_score import compute_ats_score, compute_ats_structure_score
from app.pipeline import path_fit
from app.routes._util import iso_utc, resolve_target_career_path
from app.security import rate_limit_hit, rate_limited_response

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
    resume = (
        Resume.query.filter_by(user_id=user_id)
        .filter(Resume.analysis_pending.isnot(True))   # a discover-only upload has no analysis yet
        .order_by(Resume.id.desc()).first()
    )
    skill_gap = SkillGap.query.filter_by(user_id=user_id).order_by(SkillGap.id.desc()).first()
    if resume is None or skill_gap is None:
        return None

    target_career_path = skill_gap.target_role
    student_skills = set(resume.extracted_skills or [])
    required_skills = get_required_skills(target_career_path)
    matched_skills, _, partial_skills = resolve_required(required_skills, student_skills)

    ats_score = None
    if resume.file_path and os.path.isfile(resume.file_path):
        try:
            text = extract_text_from_pdf(resume.file_path)
            ats_score = compute_ats_score(text, matched_skills, required_skills, get_pdf_page_count(resume.file_path))
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
        "partial_skills": partial_skills,
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
    allowed, retry_after = rate_limit_hit(
        "resume_upload", current_user.id, current_app.config["RESUME_UPLOAD_LIMIT_PER_HOUR"], 3600)
    if not allowed:
        return rate_limited_response(retry_after)

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
    # Resolved before the file is saved, so a rejected request leaves nothing on disk.
    target_career_path, error = resolve_target_career_path(profile, allow_override=True)
    if error:
        return error

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
        current_app.logger.exception("%s failed", request.path)
        return jsonify({
            "error": "Failed to analyze resume. The PDF may be unreadable or corrupted.",
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
    ats = compute_ats_score(result["extracted_text"], result["matched_skills"], result["required_skills"], result["page_count"])

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
        current_app.logger.exception("%s failed", request.path)
        db.session.rollback()
        return jsonify({
            "error": "Failed to save resume analysis. Please try again.",
        }), 500

    return jsonify({
        "resume_id": resume.id,
        "target_career_path": target_career_path,
        "student_skills": sorted(result["student_skills"]),
        "matched_skills": sorted(result["matched_skills"]),
        "missing_skills": sorted(result["missing_skills"]),
        "partial_skills": result["partial_skills"],
        "ai_feedback": resume.ai_feedback,
        "salary_insights": salary_insights,
        "ats_score": ats,
    }), 201


def _rate_limited():
    """discover and analyze share the upload bucket: both are the expensive resume actions."""
    allowed, retry_after = rate_limit_hit(
        "resume_upload", current_user.id, current_app.config["RESUME_UPLOAD_LIMIT_PER_HOUR"], 3600)
    return None if allowed else rate_limited_response(retry_after)


def _invalid_path_response():
    return jsonify({
        "error": "invalid_career_path",
        "message": "That isn't one of the available career paths. Choose one from the list.",
        "options": list(CAREER_PATHS),
    }), 400


@resume_bp.route("/resume/discover", methods=["POST"])
@login_required
def discover_resume():
    """
    "Which career path fits my resume?" - upload a PDF with NO target path. Extracts the text
    and skills, ranks every career path (app/pipeline/path_fit.py), and saves a Resume row
    only: no SkillGap, no salary, no LLM call. The ATS score here is the structure-only one
    (no role keyword density, since there is no role yet). POST /resume/<id>/analyze then
    analyzes the stored resume against a path the student picks.
    """
    limited = _rate_limited()
    if limited:
        return limited

    if "resume" not in request.files:
        return jsonify({"error": "No file provided. Send it under the 'resume' field."}), 400
    file = request.files["resume"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    from app.routes.roadmap import _get_index    # the process-wide FAISS index cache
    try:
        index, chunks = _get_index()
    except FileNotFoundError:
        return jsonify({"error": "Knowledge base index not found on this server."}), 503

    unique_name = f"{current_user.id}_{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file.save(file_path)

    try:
        text = extract_text_from_pdf(file_path)
        vocabulary = get_extended_skill_vocabulary()
        by_lower = {name.lower(): name for name in vocabulary}
        found = extract_skills(text, vocabulary, extended_aliases=True)
        skills = sorted({by_lower.get(name.lower(), name) for name in found})
        ats = compute_ats_structure_score(text, get_pdf_page_count(file_path))
        fit = path_fit.fit_for_skills(set(skills), index, chunks)
    except Exception:
        current_app.logger.exception("%s failed", request.path)
        return jsonify({"error": "Failed to analyze resume. The PDF may be unreadable or corrupted."}), 422

    resume = Resume(user_id=current_user.id, file_path=file_path, extracted_skills=skills,
                    ai_feedback=None, analysis_pending=True)
    try:
        db.session.add(resume)
        db.session.commit()
    except Exception:
        current_app.logger.exception("%s failed", request.path)
        db.session.rollback()
        return jsonify({"error": "Failed to save your resume. Please try again."}), 500

    return jsonify({
        "resume_id": resume.id,
        "extracted_skills": skills,
        "ats_structure_score": ats,
        "insufficient_data": fit["insufficient_data"],
        "list_a": fit["list_a"],
        "list_b": fit["list_b"],
        "near_ties": fit["near_ties"],
    }), 201


@resume_bp.route("/resume/<int:resume_id>/analyze", methods=["POST"])
@login_required
def analyze_stored_resume(resume_id):
    """
    Analyze an already-uploaded resume (see /resume/discover) against one career path, without
    uploading again. Same response shape as /resume/upload. Reuses the stored extracted_skills
    (no re-extraction); the PDF is only re-read for the ATS score and the feedback text - if it
    can't be, ats_score is null with ats_unavailable true, and ai_feedback is null.
    """
    limited = _rate_limited()
    if limited:
        return limited

    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    if resume is None:
        return jsonify({"error": "Resume not found."}), 404

    body = request.get_json(silent=True)
    target_career_path = body.get("target_career_path") if isinstance(body, dict) else None
    if not isinstance(target_career_path, str) or target_career_path not in CAREER_PATHS:
        return _invalid_path_response()

    student_skills = set(resume.extracted_skills or [])
    required_skills = get_required_skills(target_career_path)
    matched_skills, missing_skills, partial_skills = resolve_required(required_skills, student_skills)

    text, ats = None, None
    if resume.file_path and os.path.isfile(resume.file_path):
        try:
            text = extract_text_from_pdf(resume.file_path)
            ats = compute_ats_score(text, matched_skills, required_skills, get_pdf_page_count(resume.file_path))
        except Exception:
            current_app.logger.exception("%s could not re-read the saved PDF", request.path)
            text, ats = None, None

    feedback = None
    if text is not None:
        try:
            feedback = generate_resume_feedback(text, target_career_path, matched_skills, missing_skills)
        except ValueError:
            feedback = None   # LLM unavailable: the analysis itself doesn't depend on it

    salary_insights = get_salary_insights(target_career_path)
    skill_gap = SkillGap(
        user_id=current_user.id,
        missing_skills=sorted(missing_skills),
        target_role=target_career_path,
        salary_range=format_salary_range_summary(salary_insights),
    )
    resume.ai_feedback = feedback
    resume.analysis_pending = False

    try:
        db.session.add(skill_gap)
        db.session.commit()
    except Exception:
        current_app.logger.exception("%s failed", request.path)
        db.session.rollback()
        return jsonify({"error": "Failed to save resume analysis. Please try again."}), 500

    return jsonify({
        "resume_id": resume.id,
        "target_career_path": target_career_path,
        "student_skills": sorted(student_skills),
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted(missing_skills),
        "partial_skills": partial_skills,
        "ai_feedback": resume.ai_feedback,
        "salary_insights": salary_insights,
        "ats_score": ats,
        "ats_unavailable": ats is None,
    }), 201


@resume_bp.route("/resume/listings", methods=["GET"])
@login_required
def get_listings():
    """
    Live Adzuna job listings for one career path - deliberately NOT part of
    /resume/upload or /resume/latest's response (see adzuna_listings.py):
    the frontend calls this on its own, after the rest of the analysis is
    already rendered, so a slow/unavailable Adzuna call never delays or
    risks the resume analysis itself.
    """
    allowed, retry_after = rate_limit_hit(
        "resume_listings", current_user.id, current_app.config["RESUME_LISTINGS_LIMIT_PER_HOUR"], 3600)
    if not allowed:
        return rate_limited_response(retry_after)

    career_path = request.args.get("career_path")
    if not isinstance(career_path, str) or career_path not in CAREER_PATHS:
        return jsonify({
            "error": "invalid_career_path",
            "message": "That isn't one of the available career paths. Choose one from the list.",
            "options": list(CAREER_PATHS),
        }), 400

    result = get_live_listings(career_path)
    return jsonify({
        "career_path": career_path,
        "listings": result["listings"],
        "unavailable": result["unavailable"],
    }), 200
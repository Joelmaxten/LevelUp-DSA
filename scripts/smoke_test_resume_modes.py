"""
Smoke test for the two resume modes: "which path fits my resume?" (POST /resume/discover,
POST /resume/<id>/analyze, app/pipeline/path_fit.py) and "does my resume fit my path?" (the
existing /resume/upload, which must not change). Flask test client with CSRF on; the LLM
(generate_resume_feedback) is stubbed everywhere, so no Gemini/Bedrock call is made. The
FAISS index and embedding model are local. Test users and their rows/files are deleted at
the end.

Usage:
    PYTHONPATH=. python scripts/smoke_test_resume_modes.py
"""
import json
import os
import random
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

from fpdf import FPDF

from app import create_app, db
from app.models import Resume, SkillGap, User
from app.pipeline import path_fit
from app.pipeline.ats_score import compute_ats_score, compute_ats_structure_score
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.llm_client import LLMError
from app.pipeline.resume_analyzer import get_required_skills
from app.security import reset_rate_limits
from scripts._csrf import enable_csrf_client

PASSWORD = "SmokeTest#123"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


# ---------------------------------------------------------------- pure ranking checks

def skills_sets(n, with_skill, other=()):
    """n respondents; the first `with_skill` count list every skill in `other`."""
    return [set(other) if i < with_skill else set() for i in range(n)]


def make_stats(paths, overall_sets):
    return path_fit.build_survey_stats(paths, overall_sets)


def ranking_checks():
    # Path "Data" (40 respondents, 30 of them list Python and 20 list SQL), path "Web" (40, 4 list
    # Python, 35 list JavaScript), thin path "Tiny" (10). 500 other respondents.
    data = [{"Python"} | ({"SQL"} if i < 20 else set()) if i < 30 else set() for i in range(40)]
    web = [{"JavaScript"} if i < 35 else set() for i in range(40)]
    web = [s | ({"Python"} if i < 4 else set()) for i, s in enumerate(web)]
    tiny = [{"Python"} for _ in range(10)]
    rest = [{"Git"} for _ in range(500)]
    stats = make_stats({"Data": data, "Web": web, "Tiny": tiny}, data + web + tiny + rest)
    totals = {"Data": 100, "Web": 1000, "Tiny": 50, "Empty": 10}
    hits = [{"career_paths": ["Data"], "title": "Python basics", "text": "python sql"}] * 6 + \
           [{"career_paths": ["Web"], "title": "JS", "text": "javascript"}] * 6 + \
           [{"career_paths": ["Tiny"], "title": "Py", "text": "python"}] * 7
    skills = {"Python", "SQL", "Git"}

    r = path_fit.rank_paths(skills, stats, hits, totals)
    check("ranking: fewer than 3 recognised skills -> insufficient_data, no lists",
          path_fit.rank_paths({"Python", "SQL"}, stats, hits, totals) ==
          {"insufficient_data": True, "list_a": [], "list_b": [], "near_ties": {"a": [], "b": []}})
    check("ranking: paths with 30+ respondents are in list A; a thin path is in list B only if it clears the evidence floor",
          [x["path"] for x in r["list_a"]] == ["Data", "Web"] and [x["path"] for x in r["list_b"]] == ["Tiny"])
    check("ranking: the top row of list A is 100% and rows are ordered by fit",
          r["list_a"][0]["fit_pct"] == 100.0 and all(a["fit_pct"] >= b["fit_pct"] for a, b in zip(r["list_a"], r["list_a"][1:])))
    check("thin paths: rows carry rank, matched skills, respondent count and basis, and NO fit percentage",
          [set(x) for x in r["list_b"]] == [{"rank", "path", "matched_skills", "respondent_count", "basis"}] and r["list_b"][0]["rank"] == 1)
    below = [{"career_paths": ["Tiny"], "title": "Py", "text": "python"}] * (path_fit.THIN_PATH_MIN_HITS - 1)
    check("thin paths: a path just under the evidence floor is not listed, and an empty list_b is a plain empty list",
          path_fit.rank_paths(skills, stats, hits[:12] + below, totals)["list_b"] == [])
    check("thin paths: exactly at the floor is listed",
          [x["path"] for x in path_fit.rank_paths(skills, stats, hits[:12] + below + below[:1], totals)["list_b"]] == ["Tiny"])
    check("ranking: thin paths are labelled 'based on roadmap content only', list A rows are not",
          all(x["basis"] == "based on roadmap content only" for x in r["list_b"])
          and all(x["basis"] == "survey and roadmap content" for x in r["list_a"]))
    check("ranking: every row carries the respondent count",
          [x["respondent_count"] for x in r["list_a"]] == [40, 40] and [x["respondent_count"] for x in r["list_b"]] == [10])
    data_row = r["list_a"][0]
    check("ranking: matched skills are the ones that scored (Python, SQL for Data; Git is in neither path)",
          sorted(data_row["matched_skills"]) == ["Python", "SQL"])

    scores = path_fit.survey_scores(skills, stats)
    check("survey: a skill with share below 10% in a path is ignored (Python in Web is 10%: 4/40 counts, 3/40 would not)",
          "Python" in [m["skill"] for m in scores["Web"]["matched"]])
    thin_web = make_stats({"Web": [{"Python"} if i < 3 else set() for i in range(40)]}, [{"Python"}] * 3 + [set()] * 497)
    check("survey: share below 0.10 is ignored", path_fit.survey_scores({"Python"}, thin_web)["Web"]["score"] == 0)
    lift_stats = make_stats({"A": [{"Common", "Rare"} for _ in range(40)]},
                            [{"Common", "Rare"} for _ in range(40)] + [{"Common"} for _ in range(460)])
    matched = {m["skill"]: m["lift"] for m in path_fit.survey_scores({"Common", "Rare"}, lift_stats)["A"]["matched"]}
    check("survey: lift rewards a distinctive skill over one everybody has", matched["Rare"] > matched["Common"] and abs(matched["Common"] - 1 / 1.0 * (40 / 40) / (500 / 500)) < 1e-9)

    rm = path_fit.roadmap_scores(hits, totals)
    check("roadmap: hits are divided by the path's chunk total, so a big folder doesn't win on volume",
          rm["Data"] > rm["Web"] and rm["Web"] == 6 / 1000)

    near = {"insufficient_data": False}
    ties_stats = make_stats({"P": [{"x"} for _ in range(40)], "Q": [{"x"} for _ in range(40)], "R": [{"x"} if i < 14 else set() for i in range(40)]},
                            [{"x"} for _ in range(94)] + [set() for _ in range(300)])
    ties = path_fit.rank_paths({"x", "y", "z"}, ties_stats, [], {"P": 10, "Q": 10, "R": 10})
    check("near-ties: paths within 15% of the top of a list are flagged together",
          ties["near_ties"]["a"] == ["P", "Q"] and ties["list_a"][2]["path"] == "R" and ties["list_a"][2]["fit_pct"] < 85)
    check("near-ties: nothing is flagged when only one path is close; thin paths never have near-ties",
          r["near_ties"]["a"] == [] and r["near_ties"]["b"] == [])
    check("ranking is deterministic (same input, same output)", path_fit.rank_paths(skills, stats, hits, totals) == r)
    flat = path_fit.rank_paths({"x", "y", "z"}, make_stats({"A": [set()] * 40}, [set()] * 40), [], {"A": 5})
    check("ranking: skills that relate to nothing in the survey or roadmaps -> insufficient_data", flat["insufficient_data"] is True)
    summary = path_fit.skills_summary({"b", "a"})
    check("roadmap text: a sorted, stable skills summary is what gets embedded", summary == "Resume skills: a, b")


# ---------------------------------------------------------------- route checks

def make_pdf(path, skills_line, with_contact=True):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    body = ["Test Student"]
    if with_contact:
        body += ["Email: test.student@example.com", "Phone: +91 98765 43210"]
    body += ["SUMMARY", "Final year student looking for a software role and keen to learn.",
             "SKILLS", skills_line, "EXPERIENCE", "Intern. Built small projects and fixed bugs in a team.",
             "EDUCATION", "BTech Computer Science, 2026.", "PROJECTS", "Portfolio site; a small data notebook."]
    for line in body:
        pdf.cell(0, 8, text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def route_checks(app, tmp_dir):
    suffix = random.randint(100000, 999999)
    emails = [f"modestest{suffix}@example.com", f"modesother{suffix}@example.com"]
    pdf_path = tmp_dir / "resume_a.pdf"
    make_pdf(pdf_path, "Python, SQL, MySQL, Git, TensorFlow, PyTorch, pandas, Docker, JavaScript, React")
    bad_path = tmp_dir / "notes.txt"
    bad_path.write_text("not a pdf")

    def upload(client, path, url, **kw):
        with open(path, "rb") as f:
            return client.post(url, data={"resume": (f, path.name)}, content_type="multipart/form-data", **kw)

    user_ids = []
    try:
        client, other = app.test_client(), app.test_client()   # no `with`: two kept-open request contexts clash
        if True:
            for c, email in ((client, emails[0]), (other, emails[1])):
                resp = c.post("/signup", json={"name": "Modes Test", "email": email, "password": PASSWORD})
                user_ids.append(resp.get_json()["user_id"])
            check("logged out: discover and analyze answer 401",
                  upload(client, pdf_path, "/resume/discover").status_code == 401
                  and client.post("/resume/1/analyze", json={"target_career_path": "DevOps"}).status_code == 401)
            for c, email in ((client, emails[0]), (other, emails[1])):
                c.post("/login", json={"email": email, "password": PASSWORD})

            # CSRF
            resp = upload(client, pdf_path, "/resume/discover", headers={"X-CSRF-Token": ""})
            check("CSRF: discover without a token -> 400 csrf", resp.status_code == 400 and resp.get_json() == {"error": "csrf"})
            resp = client.post("/resume/1/analyze", json={"target_career_path": "DevOps"}, headers={"X-CSRF-Token": "wrong"})
            check("CSRF: analyze with a wrong token -> 400 csrf", resp.status_code == 400 and resp.get_json() == {"error": "csrf"})

            # validation
            check("discover: no file -> 400", client.post("/resume/discover", data={}, content_type="multipart/form-data").status_code == 400)
            resp = upload(client, bad_path, "/resume/discover")
            check("discover: a non-PDF -> 400 'Only PDF'", resp.status_code == 400 and "PDF" in resp.get_json()["error"])

            # discover happy path - the LLM must not be touched
            def no_llm(*a, **k):
                raise AssertionError("discover must not call the LLM")
            with patch("app.routes.resume.generate_resume_feedback", no_llm):
                resp = upload(client, pdf_path, "/resume/discover")
            body = resp.get_json() or {}
            check("discover: 201 with resume_id, extracted_skills, ats_structure_score, list_a, list_b, near_ties, insufficient_data",
                  resp.status_code == 201 and set(body) == {"resume_id", "extracted_skills", "ats_structure_score", "list_a", "list_b", "near_ties", "insufficient_data"})
            skills = body.get("extracted_skills", [])
            check("discover: skills come out under their canonical names, including extended-vocabulary ones (Git, TensorFlow, pandas)",
                  {"Python", "SQL", "MySQL", "Git", "TensorFlow", "PyTorch", "pandas", "Docker", "JavaScript", "React"} <= set(skills))
            check("discover: list A has the 9 paths with survey data (fit_pct rows); list B rows, if any, have a rank and no fit_pct",
                  body["insufficient_data"] is False and len(body["list_a"]) == 9
                  and all(set(r) == {"path", "fit_pct", "matched_skills", "respondent_count", "basis"} for r in body["list_a"])
                  and all(set(r) == {"rank", "path", "matched_skills", "respondent_count", "basis"} for r in body["list_b"]))
            check("discover: ATS result is structure-only (no role keyword reasons)",
                  set(body["ats_structure_score"]) == {"score", "reasons"}
                  and not any("commonly-required" in r for r in body["ats_structure_score"]["reasons"]))
            resume_id = body["resume_id"]
            with app.app_context():
                resume = db.session.get(Resume, resume_id)
                check("discover: saved a Resume row only (skills stored, no feedback, pending) and NO SkillGap row",
                      resume is not None and resume.analysis_pending is True and resume.ai_feedback is None
                      and "Git" in resume.extracted_skills and SkillGap.query.filter_by(user_id=user_ids[0]).count() == 0)
            check("discover: a pending resume does not show up as an analysis in /resume/latest", client.get("/resume/latest").status_code == 404)

            # analyze
            check("analyze: another user's resume -> 404",
                  other.post(f"/resume/{resume_id}/analyze", json={"target_career_path": "DevOps"}).status_code == 404)
            check("analyze: a resume that doesn't exist -> 404", client.post("/resume/99999999/analyze", json={"target_career_path": "DevOps"}).status_code == 404)
            resp = client.post(f"/resume/{resume_id}/analyze", json={"target_career_path": "Underwater Basket Weaving"})
            check("analyze: an invalid path -> 400 invalid_career_path with the options",
                  resp.status_code == 400 and resp.get_json()["error"] == "invalid_career_path" and resp.get_json()["options"] == list(CAREER_PATHS))
            check("analyze: a missing body or path -> 400", client.post(f"/resume/{resume_id}/analyze", json={}).status_code == 400
                  and client.post(f"/resume/{resume_id}/analyze").status_code == 400)

            def extractor_forbidden(*a, **k):
                raise AssertionError("analyze must reuse the stored skills, not extract again")
            with patch("app.routes.resume.extract_skills", extractor_forbidden), \
                    patch("app.routes.resume.get_extended_skill_vocabulary", extractor_forbidden), \
                    patch("app.routes.resume.generate_resume_feedback", return_value="stub feedback") as feedback:
                resp = client.post(f"/resume/{resume_id}/analyze", json={"target_career_path": "Data Science"})
            body = resp.get_json() or {}
            check("analyze: 201, same keys as /resume/upload (plus ats_unavailable), reusing stored skills (extractor never called)",
                  resp.status_code == 201 and set(body) == {"resume_id", "target_career_path", "student_skills", "matched_skills",
                                                             "missing_skills", "ai_feedback", "salary_insights", "ats_score", "ats_unavailable"})
            check("analyze: feedback from the (stubbed) LLM, salary insights, ATS with keyword density",
                  body["ai_feedback"] == "stub feedback" and set(body["salary_insights"]) == {"job_postings", "survey_respondents"}
                  and body["ats_score"] is not None and body["ats_unavailable"] is False and feedback.call_count == 1)
            with app.app_context():
                required = get_required_skills("Data Science")
            check("analyze: matched/missing are computed against the path's required skills from the stored skills",
                  set(body["matched_skills"]) == required & set(skills) and set(body["missing_skills"]) == required - set(skills))
            with app.app_context():
                gap = SkillGap.query.filter_by(user_id=user_ids[0]).order_by(SkillGap.id.desc()).first()
                resume = db.session.get(Resume, resume_id)
                check("analyze: a new SkillGap row for that path; the resume is no longer pending and holds the feedback",
                      gap is not None and gap.target_role == "Data Science" and resume.analysis_pending is False and resume.ai_feedback == "stub feedback")
            latest = client.get("/resume/latest")
            check("analyze: /resume/latest now returns this resume's analysis for the chosen path",
                  latest.status_code == 200 and latest.get_json()["target_career_path"] == "Data Science" and latest.get_json()["resume_id"] == resume_id)

            # a second path on the same stored resume, with the LLM failing and the PDF gone
            def llm_down(*a, **k):
                raise LLMError("down", kind="transient")
            with patch("app.routes.resume.generate_resume_feedback", llm_down):
                resp = client.post(f"/resume/{resume_id}/analyze", json={"target_career_path": "DevOps"})
            check("analyze: LLM failure degrades gracefully (201, ai_feedback null)", resp.status_code == 201 and resp.get_json()["ai_feedback"] is None)
            with app.app_context():
                saved = db.session.get(Resume, resume_id).file_path
            moved = saved + ".moved"
            os.rename(saved, moved)
            try:
                with patch("app.routes.resume.generate_resume_feedback", return_value="x"):
                    resp = client.post(f"/resume/{resume_id}/analyze", json={"target_career_path": "Backend Engineering"})
            finally:
                os.rename(moved, saved)
            body = resp.get_json() or {}
            check("analyze: PDF no longer on disk -> ats_score null with ats_unavailable true, no feedback, still 201",
                  resp.status_code == 201 and body["ats_score"] is None and body["ats_unavailable"] is True and body["ai_feedback"] is None)

            reset_rate_limits()   # the checks above spent most of the hourly upload allowance
            # insufficient data
            sparse = tmp_dir / "sparse.pdf"
            make_pdf(sparse, "Python and some teamwork")
            resp = upload(client, sparse, "/resume/discover")
            body = resp.get_json() or {}
            check("discover: fewer than 3 recognised skills -> insufficient_data true, empty lists, resume still saved",
                  resp.status_code == 201 and body["insufficient_data"] is True and body["list_a"] == [] and body["list_b"] == [] and body["resume_id"])

            # a control resume with generic office skills
            control = tmp_dir / "control.pdf"
            make_pdf(control, "Excel, Word, Tally, typing, and good communication")
            resp = upload(client, control, "/resume/discover")
            body = resp.get_json() or {}
            check("control resume (Excel, Word, Tally): insufficient_data, nothing ranked, no thin-path list",
                  resp.status_code == 201 and body["insufficient_data"] is True and body["list_a"] == [] and body["list_b"] == [])

            # the real ranking on the synthetic developer resumes: no thin path as a headline
            with app.app_context():
                from app.pipeline import rag
                index, chunks = rag.load_index(app.config["FAISS_INDEX_PATH"])
                real = {name: path_fit.fit_for_skills(skills_set, index, chunks) for name, skills_set in {
                    "a": {"Python", "SQL", "MySQL", "Git"},
                    "b": {"JavaScript", "React", "Node.js", "TypeScript", "HTML/CSS"},
                    "c": {"Python", "TensorFlow", "PyTorch", "pandas", "Docker"}}.items()}
            check("real ranking, resumes (a) and (b): Cybersecurity is no longer shown as a headline (not in list B at all)",
                  all("Cybersecurity" not in [r["path"] for r in real[k]["list_b"]] for k in ("a", "b")))
            check("real ranking: the evidence floor leaves (a) and (b) with no thin-path list; (c) keeps only Data Analytics",
                  real["a"]["list_b"] == [] and real["b"]["list_b"] == [] and [r["path"] for r in real["c"]["list_b"]] == ["Data Analytics"])

            # /resume/upload is unchanged
            with patch("app.routes.resume.generate_resume_feedback", return_value="stub feedback"):
                resp = upload(client, pdf_path, "/resume/upload", data=None) if False else None
            with open(pdf_path, "rb") as f, patch("app.routes.resume.generate_resume_feedback", return_value="stub feedback"):
                resp = client.post("/resume/upload", data={"resume": (f, "resume_a.pdf"), "target_career_path": "Data Science"},
                                   content_type="multipart/form-data")
            body = resp.get_json() or {}
            check("upload: still 201 with the original response keys",
                  resp.status_code == 201 and set(body) == {"resume_id", "target_career_path", "student_skills", "matched_skills",
                                                             "missing_skills", "ai_feedback", "salary_insights", "ats_score"})
            extended_only = {"Git", "TensorFlow", "PyTorch", "pandas"}
            check("upload: still uses the ORIGINAL vocabulary (extended-only skills such as Git/TensorFlow are not reported)",
                  not extended_only & {s.lower() if s.islower() else s for s in body["student_skills"]}
                  and not any(s in body["student_skills"] for s in extended_only))
            with app.app_context():
                latest_resume = Resume.query.filter_by(user_id=user_ids[0]).order_by(Resume.id.desc()).first()
                check("upload: the saved Resume is not pending", latest_resume.analysis_pending is not True)

            # rate limits (shared upload bucket)
            app.config["RESUME_UPLOAD_LIMIT_PER_HOUR"] = 2
            reset_rate_limits()
            codes = [client.post("/resume/discover", data={}, content_type="multipart/form-data").status_code for _ in range(3)]
            check("rate limit: the 3rd discover request in the window -> 429", codes == [400, 400, 429])
            reset_rate_limits()
            codes = [client.post(f"/resume/{resume_id}/analyze", json={"target_career_path": "Nope"}).status_code for _ in range(3)]
            check("rate limit: the 3rd analyze request in the window -> 429", codes == [400, 400, 429])
            reset_rate_limits()
    finally:
        with app.app_context():
            for resume in Resume.query.filter(Resume.user_id.in_(user_ids)).all():
                if resume.file_path and os.path.isfile(resume.file_path):
                    os.remove(resume.file_path)
            SkillGap.query.filter(SkillGap.user_id.in_(user_ids)).delete(synchronize_session=False)
            Resume.query.filter(Resume.user_id.in_(user_ids)).delete(synchronize_session=False)
            User.query.filter(User.email.in_(emails)).delete(synchronize_session=False)
            db.session.commit()


def main():
    app = create_app()
    enable_csrf_client(app)
    tmp_dir = Path("scratch/resume_modes_tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    original_limit = app.config["RESUME_UPLOAD_LIMIT_PER_HOUR"]
    try:
        ranking_checks()

        text = "Experience Education Skills\n" + "word " * 120 + "a@b.com +91 98765 43210"
        check("ATS: the structure-only score equals the full score when there are no required skills",
              compute_ats_structure_score(text) == compute_ats_score(text, set(), set()))
        check("ATS: the structure-only score has no keyword-density reason",
              not any("commonly-required" in r for r in compute_ats_structure_score(text)["reasons"]))

        with app.app_context():
            before = json.loads(Path("scratch/golden/required_skills_before.json").read_text(encoding="utf-8"))["required_skills"]
            same = [p for p in CAREER_PATHS if sorted(get_required_skills(p)) == before[p]]
        check(f"mode 2: required-skills lists are identical to the pre-change snapshot for all {len(CAREER_PATHS)} paths", len(same) == len(CAREER_PATHS))

        route_checks(app, tmp_dir)
    finally:
        app.config["RESUME_UPLOAD_LIMIT_PER_HOUR"] = original_limit
        for f in tmp_dir.glob("*"):
            f.unlink()
        tmp_dir.rmdir()

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()

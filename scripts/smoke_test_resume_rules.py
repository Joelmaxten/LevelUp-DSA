"""
Tests for the resume skill-matching rules (app/pipeline/skill_matching.py) and the ATS content checks
(app/pipeline/ats_score.py). No LLM call. The required-list exclusion check reads the development database.

Usage:
    PYTHONPATH=. python scripts/smoke_test_resume_rules.py

Exits non-zero if any check fails.
"""
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fpdf import FPDF

from app.pipeline import ats_score as ats
from app.pipeline.resume_analyzer import extract_text_from_pdf, get_pdf_page_count
from app.pipeline.resume_skill_extractor import extract_skills
from app.pipeline.skill_matching import (
    COMPOSITE_SKILLS, EXCLUDED_TOOLING, IMPLIED_BY, find_composite_parts, resolve_required,
)

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


# ---------- matching ----------
REQ = {"HTML/CSS", "SQL", "Python", "React"}

m, miss, part = resolve_required(REQ, {"HTML", "CSS", "Python"})
check("HTML/CSS is matched when both HTML and CSS are found", "HTML/CSS" in m and "HTML/CSS" not in miss and not part)

m, miss, part = resolve_required(REQ, {"HTML", "Python"})
check("HTML/CSS with only HTML is not matched but is reported as partly matched",
      "HTML/CSS" in miss and part == {"HTML/CSS": {"found": ["HTML"], "missing": ["CSS"]}})
m, miss, part = resolve_required(REQ, {"CSS"})
check("HTML/CSS with only CSS is partly matched, HTML missing", part == {"HTML/CSS": {"found": ["CSS"], "missing": ["HTML"]}})

m, miss, part = resolve_required(REQ, {"Python"})
check("HTML/CSS with neither part is missing and not partial", "HTML/CSS" in miss and "HTML/CSS" not in part)

m, _, _ = resolve_required(REQ, {"HTML/CSS"})
check("the combined name itself still matches directly", "HTML/CSS" in m)

for db in sorted(IMPLIED_BY["SQL"]):
    m, miss, _ = resolve_required({"SQL"}, {db})
    check(f"{db} implies SQL", m == {"SQL"} and not miss)
m, miss, _ = resolve_required({"SQL"}, {"MongoDB", "Redis"})
check("non-SQL databases do not imply SQL", miss == {"SQL"})
check("the implication table is the five SQL databases",
      IMPLIED_BY == {"SQL": frozenset({"MySQL", "PostgreSQL", "SQLite", "Microsoft SQL Server", "MariaDB"})})
m, miss, _ = resolve_required({"MySQL"}, {"PostgreSQL"})
check("implication is one-way: PostgreSQL does not satisfy a required MySQL", miss == {"MySQL"})

# the real resume from the bug report
resume_skills = {"HTML", "CSS", "MySQL", "PostgreSQL", "SQLite", "Node.js", "React", "Python"}
m, miss, part = resolve_required({"HTML/CSS", "SQL", "Python", "React", "Node.js", "Docker"}, resume_skills)
check("bug-report resume: HTML/CSS and SQL are matched, only Docker is missing", miss == {"Docker"} and {"HTML/CSS", "SQL"} <= m)

# ---------- extraction of the parts ----------
check("find_composite_parts: 'HTML, CSS' -> both", find_composite_parts("Skills: HTML, CSS, Python") == {"HTML", "CSS"})
check("find_composite_parts: HTML5 / CSS3 count", find_composite_parts("html5 and css3") == {"HTML", "CSS"})
check("find_composite_parts: only HTML", find_composite_parts("I know HTML well") == {"HTML"})
check("find_composite_parts: no substring false positives", find_composite_parts("xhtmlparser, cssom") == set())
found = extract_skills("Skills: HTML, CSS, MySQL, PostgreSQL, SQLite, Node.js, React, Python, npm",
                       {"HTML/CSS", "SQL", "MySQL", "PostgreSQL", "SQLite", "Node.js", "React", "Python", "npm"})
check("extract_skills returns HTML and CSS separately plus the databases",
      {"HTML", "CSS", "MySQL", "PostgreSQL", "SQLite"} <= found)
m, miss, _ = resolve_required({"HTML/CSS", "SQL", "React"}, found)
check("extractor output + rules: nothing missing for the bug-report resume", not miss)

# ---------- exclusion set ----------
check("the exclusion set holds npm, pip, yarn and the other package managers",
      {"npm", "pip", "yarn", "pnpm", "cargo", "nuget", "composer", "maven", "gradle"} <= EXCLUDED_TOOLING)

try:
    from app import create_app
    from app.pipeline.resume_analyzer import get_required_skills
    from app.pipeline.career_path_registry import CAREER_PATHS
    from app.pipeline.skill_matching import is_excluded_tooling
    app = create_app()
    with app.app_context():
        all_ok = True
        sizes_ok = True
        for p in CAREER_PATHS:
            req = get_required_skills(p)
            all_ok &= not any(is_excluded_tooling(s) for s in req)
            sizes_ok &= len(req) == 10
        check(f"no required list contains a package manager or build tool ({len(CAREER_PATHS)} paths)", all_ok)
        check("every required list still has 10 skills (the excluded names are replaced, not just dropped)", sizes_ok)
except Exception as exc:   # no database: say so rather than silently skipping
    check(f"required-list exclusion check could run (database): {exc}", False)

# ---------- ATS ----------
BULLETS = "\n".join(f"• {b}" for b in [
    "Built a REST API serving 2,000 users with 99% uptime",
    "Reduced page load time by 40% by caching queries",
    "Led a team of 4 to ship 3 features in one quarter",
])
COMPLETE = f"""Jane Doe
jane@example.com | +91 98765 43210 | github.com/janedoe | linkedin.com/in/janedoe
SUMMARY
Backend engineer who ships reliable services.
EXPERIENCE
Software Engineer, Acme - Jun 2023 - Present
{BULLETS}
PROJECTS
Chat app - Jan 2022 - Mar 2022
• Built a realtime chat with 500 concurrent users
EDUCATION
B.Tech Computer Science, 2019 - 2023
SKILLS
Python, SQL, Docker, React, Node.js, Git, Linux, REST, testing, CI
""" + "Extra detail line to pad the content past the sparse threshold. " * 3
MINIMAL = "Experience Education Skills\n" + "word " * 120 + "a@b.com +91 98765 43210"


def deducted(result, fragment):
    return any(r.startswith("-") and fragment in r for r in result["reasons"])


full = ats.compute_ats_structure_score(COMPLETE, 1)
mini = ats.compute_ats_structure_score(MINIMAL, 1)
check("a complete, well-formed resume scores 100", full["score"] == 100)
check("a minimal resume scores clearly lower than a complete one", mini["score"] <= full["score"] - 25)
check("the two do not both score 100", not (full["score"] == 100 and mini["score"] == 100))
check("minimal resume: deductions name numbers, links, dates and long paragraph",
      all(deducted(mini, f) for f in ("No numbers or metrics", "No links", "Few or no dates", "running text")))

check("over 2 pages is deducted", deducted(ats.compute_ats_structure_score(COMPLETE, 3), "3 pages")
      and ats.compute_ats_structure_score(COMPLETE, 3)["score"] == 100 - ats.PAGES_DEDUCTION)
check("2 pages is fine", not deducted(ats.compute_ats_structure_score(COMPLETE, 2), "pages"))
check("unknown page count is reported, not deducted",
      any("Page count could not be read" in r for r in ats.compute_ats_structure_score(COMPLETE)["reasons"])
      and ats.compute_ats_structure_score(COMPLETE)["score"] == 100)

no_numbers = COMPLETE.replace("2,000", "many").replace("99%", "high").replace("40%", "much").replace("4 ", "a ").replace("3 ", "some ").replace("500", "many")
r = ats.compute_ats_structure_score(no_numbers, 1)
check("no numbers in any bullet is deducted", deducted(r, "No numbers or metrics") and r["score"] == 100 - ats.NO_METRICS_DEDUCTION)
check("a bare year in a bullet does not count as a metric",
      deducted(ats.compute_ats_structure_score("• Built the portal in 2023\n" + "x" * 600, 1), "No numbers or metrics"))

weak = COMPLETE.replace("Built a REST API", "Responsible for a REST API").replace("Reduced page", "Worked on page")
r = ats.compute_ats_structure_score(weak, 1)
check("bullets starting with weak phrases are deducted (5 each)", deducted(r, "2 bullets start with a weak phrase") and r["score"] == 90)
many_weak = COMPLETE.replace("Built a REST API", "Responsible for").replace("Reduced page", "Worked on page").replace("Led a team", "Helped a team")
check("the weak-phrase deduction is capped", ats.compute_ats_structure_score(many_weak, 1)["score"] == 100 - ats.WEAK_START_DEDUCTION_MAX)

no_links = COMPLETE.replace("github.com/janedoe", "").replace("linkedin.com/in/janedoe", "")
r = ats.compute_ats_structure_score(no_links, 1)
check("no links is deducted", deducted(r, "No links") and r["score"] == 100 - ats.NO_LINKS_DEDUCTION)

para = COMPLETE.replace("Backend engineer who ships reliable services.", " ".join(["This is a long sentence about my many varied strengths and goals."] * 12))
r = ats.compute_ats_structure_score(para, 1)
check("a very long paragraph is deducted", deducted(r, "running text") and r["score"] == 100 - ats.LONG_PARAGRAPH_DEDUCTION)

no_dates = COMPLETE.replace("2019 - 2023", "").replace("Jun 2023 - Present", "").replace("Jan 2022 - Mar 2022", "")
r = ats.compute_ats_structure_score(no_dates, 1)
check("missing dates is deducted", deducted(r, "Few or no dates") and r["score"] == 100 - ats.NO_DATES_DEDUCTION)

# every check reports a line, and a resume with email + phone shows both
reasons = full["reasons"]
check("every check reports a line: 10 checks -> 10 reasons", len(reasons) == 10)
check("contact info is reported when present (email and phone each get a line)",
      any(r.startswith("Email address found") for r in reasons) and any(r.startswith("Phone number found") for r in reasons))
check("a missing email is still deducted with a reason",
      deducted(ats.compute_ats_structure_score(COMPLETE.replace("jane@example.com", ""), 1), "No email"))
check("compute_ats_score adds one keyword-density line when there are required skills",
      len(ats.compute_ats_score(COMPLETE, {"a"}, {"a", "b"}, 1)["reasons"]) == 11
      and len(ats.compute_ats_score(COMPLETE, set(), set(), 1)["reasons"]) == 10)
check("structure-only equals full when there are no required skills",
      ats.compute_ats_structure_score(COMPLETE, 1) == ats.compute_ats_score(COMPLETE, set(), set(), 1))
check("the score never goes below 0", ats.compute_ats_structure_score("", 5)["score"] >= 0)

# ---------- a real PDF: page count and the text round-trip ----------
with tempfile.TemporaryDirectory() as tmp:
    pdf = FPDF()
    for _ in range(3):
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 10, text="Experience Education Skills", new_x="LMARGIN", new_y="NEXT")
    path = str(Path(tmp) / "three.pdf")
    pdf.output(path)
    check("get_pdf_page_count reads a 3-page PDF", get_pdf_page_count(path) == 3)
    check("get_pdf_page_count returns None for an unreadable file", get_pdf_page_count(str(Path(tmp) / "missing.pdf")) is None)
    check("a 3-page PDF gets the page deduction",
          deducted(ats.compute_ats_structure_score(extract_text_from_pdf(path), get_pdf_page_count(path)), "3 pages"))

failed = [d for d, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)

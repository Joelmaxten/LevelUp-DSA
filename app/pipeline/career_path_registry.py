"""
Single source of truth for the 15 career paths: which roadmap.sh
knowledge-base folders ground each one, and which SO Survey 2025 DevType
values (survey_respondents.dev_type - a controlled-vocabulary field, kept
raw in that column) count as a respondent for each. Every other module
that needs the list of paths, the path->folders mapping, or the
path->devtypes mapping imports it from here instead of holding its own
copy - see docs/PROJECT_BIOGRAPHY.md's "Career Path Restructuring" entry
for how these 15 replaced the old 10, and why (AI/ML, Data
Science/Analytics, UI/UX+Frontend and Cloud/DevOps split; Full-Stack and
Backend renamed; QA & Test Automation and Data Engineering added; Research
/ Advanced Computing removed entirely - it is not carried forward in any
form).

"devtypes" values were checked against a live `SELECT DISTINCT dev_type
FROM survey_respondents` (not retyped from memory) at the time this was
written - every one of them exists verbatim in the database. A DevType can
legitimately appear under two paths (e.g. "AI/ML engineer" - the survey
has no finer-grained split - counts for both AI Engineering and Machine
Learning Engineering; see survey_queries.py). Most DevType values
(Student, Architect, managers/executives, embedded, database
administrator, academic researcher, ...) are deliberately unmapped, same
principle as so_survey_processor.py's own DEVTYPE_TO_CAREER_PATH: forcing
an ill-fitting DevType onto a path would be a worse error than leaving it
unmapped.

Order matters here: it's the order paths are offered in the standalone
career-path picker (resolve_target_career_path) and iterated when seeding
CareerPath rows (scripts/seed_dsa.py).
"""

FULL_STACK = "Full-Stack Development"

CAREER_PATH_REGISTRY = [
    {"name": "Full-Stack Development", "folders": ["full-stack", "javascript", "react", "nodejs", "git-github"],
     "devtypes": ["Developer, full-stack"]},
    {"name": "AI Engineering", "folders": ["ai-engineer", "ai-agents", "prompt-engineering", "ai-red-teaming", "python"],
     "devtypes": ["AI/ML engineer", "Developer, AI apps or physical AI"]},
    {"name": "Machine Learning Engineering", "folders": ["machine-learning", "mlops", "python"],
     "devtypes": ["AI/ML engineer", "Applied scientist"]},
    {"name": "Data Science", "folders": ["python-data-analysis", "sql", "ai-data-scientist", "machine-learning"],
     "devtypes": ["Data scientist"]},
    {"name": "Data Analytics", "folders": ["data-analyst", "bi-analyst", "power-bi", "sql"],
     "devtypes": ["Data or business analyst"]},
    {"name": "Cybersecurity", "folders": ["cyber-security", "devsecops"],
     "devtypes": ["Cybersecurity or InfoSec professional"]},
    {"name": "Mobile App Development", "folders": ["android", "ios", "react-native"],
     "devtypes": ["Developer, mobile"]},
    {"name": "Game Development", "folders": ["game-developer", "cpp"],
     "devtypes": ["Developer, game or graphics"]},
    {"name": "Backend Engineering", "folders": ["backend", "sql", "system-design"],
     "devtypes": ["Developer, back-end"]},
    {"name": "UI/UX Design", "folders": ["ux-design", "design-system", "product-design"],
     "devtypes": ["UX, Research Ops or UI design professional"]},
    {"name": "Frontend Development", "folders": ["frontend", "html", "css", "javascript", "typescript", "react", "nextjs"],
     "devtypes": ["Developer, front-end"]},
    {"name": "Cloud Engineering", "folders": ["aws", "docker", "kubernetes", "terraform"],
     "devtypes": ["Cloud infrastructure engineer"]},
    {"name": "DevOps", "folders": ["devops", "docker", "kubernetes", "linux"],
     "devtypes": ["DevOps engineer or professional", "System administrator"]},
    {"name": "QA & Test Automation", "folders": ["python", "sql", "git-github", "api-design", "qa"],
     "devtypes": ["Developer, QA or test"]},
    {"name": "Data Engineering", "folders": ["data-engineer", "sql", "python"],
     "devtypes": ["Data engineer"]},
]

CAREER_PATHS = [entry["name"] for entry in CAREER_PATH_REGISTRY]

CAREER_PATH_TO_FOLDERS = {entry["name"]: entry["folders"] for entry in CAREER_PATH_REGISTRY}

SURVEY_DEVTYPES = {entry["name"]: entry["devtypes"] for entry in CAREER_PATH_REGISTRY}

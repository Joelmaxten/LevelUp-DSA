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
     "devtypes": ["Developer, full-stack"], "supporting_folders": ["git-github"]},
    {"name": "AI Engineering", "folders": ["ai-engineer", "ai-agents", "prompt-engineering", "ai-red-teaming", "python"],
     "devtypes": ["AI/ML engineer", "Developer, AI apps or physical AI"], "supporting_folders": ["python"]},
    {"name": "Machine Learning Engineering", "folders": ["machine-learning", "mlops", "python"],
     "devtypes": ["AI/ML engineer", "Applied scientist"], "supporting_folders": ["python"]},
    {"name": "Data Science", "folders": ["python-data-analysis", "sql", "ai-data-scientist", "machine-learning"],
     "devtypes": ["Data scientist"], "supporting_folders": ["sql"]},
    {"name": "Data Analytics", "folders": ["data-analyst", "bi-analyst", "power-bi", "sql"],
     "devtypes": ["Data or business analyst"], "supporting_folders": ["sql"]},
    {"name": "Cybersecurity", "folders": ["cyber-security", "devsecops"],
     "devtypes": ["Cybersecurity or InfoSec professional"], "supporting_folders": []},
    {"name": "Mobile App Development", "folders": ["android", "ios", "react-native"],
     "devtypes": ["Developer, mobile"], "supporting_folders": []},
    {"name": "Game Development", "folders": ["game-developer", "cpp"],
     "devtypes": ["Developer, game or graphics"], "supporting_folders": ["cpp"]},
    {"name": "Backend Engineering", "folders": ["backend", "sql", "system-design"],
     "devtypes": ["Developer, back-end"], "supporting_folders": ["sql"]},
    {"name": "UI/UX Design", "folders": ["ux-design", "design-system", "product-design"],
     "devtypes": ["UX, Research Ops or UI design professional"], "supporting_folders": []},
    {"name": "Frontend Development", "folders": ["frontend", "html", "css", "javascript", "typescript", "react", "nextjs"],
     "devtypes": ["Developer, front-end"], "supporting_folders": []},
    {"name": "Cloud Engineering", "folders": ["aws", "docker", "kubernetes", "terraform"],
     "devtypes": ["Cloud infrastructure engineer"], "supporting_folders": []},
    {"name": "DevOps", "folders": ["devops", "docker", "kubernetes", "linux"],
     "devtypes": ["DevOps engineer or professional", "System administrator"], "supporting_folders": ["linux"]},
    {"name": "QA & Test Automation", "folders": ["python", "sql", "git-github", "api-design", "qa"],
     "devtypes": ["Developer, QA or test"], "supporting_folders": ["python", "sql", "git-github"]},
    {"name": "Data Engineering", "folders": ["data-engineer", "sql", "python"],
     "devtypes": ["Data engineer"], "supporting_folders": ["python", "sql"]},
]

CAREER_PATHS = [entry["name"] for entry in CAREER_PATH_REGISTRY]

CAREER_PATH_TO_FOLDERS = {entry["name"]: entry["folders"] for entry in CAREER_PATH_REGISTRY}

SURVEY_DEVTYPES = {entry["name"]: entry["devtypes"] for entry in CAREER_PATH_REGISTRY}

# Which of a path's own folders count as "supporting" rather than "primary"
# for roadmap phase step-count targets (see roadmap_generator.py's
# _folder_step_target) - a fundamentals folder like "python" inside an
# AI/ML-specific path gets a smaller target than the folders that are
# actually the subject of that career path, even though it's a full phase.
SUPPORTING_FOLDERS = {entry["name"]: set(entry["supporting_folders"]) for entry in CAREER_PATH_REGISTRY}

# Human-readable display name for every roadmap.sh folder used by any career
# path above - roadmap_generator.py uses these for phase titles instead of a
# mechanical dash-to-title-case conversion of the raw folder slug. Covers
# every folder that appears in any CAREER_PATH_REGISTRY entry's "folders".
FOLDER_DISPLAY_NAMES = {
    "full-stack": "Full-Stack",
    "javascript": "JavaScript",
    "react": "React",
    "nodejs": "Node.js",
    "git-github": "Git & GitHub",
    "ai-engineer": "AI Engineering",
    "ai-agents": "AI Agents",
    "prompt-engineering": "Prompt Engineering",
    "ai-red-teaming": "AI Red Teaming",
    "python": "Python",
    "machine-learning": "Machine Learning",
    "mlops": "MLOps",
    "python-data-analysis": "Python for Data Analysis",
    "sql": "SQL",
    "ai-data-scientist": "AI & Data Science",
    "data-analyst": "Data Analyst",
    "bi-analyst": "BI Analyst",
    "power-bi": "Power BI",
    "cyber-security": "Cybersecurity",
    "devsecops": "DevSecOps",
    "android": "Android",
    "ios": "iOS",
    "react-native": "React Native",
    "game-developer": "Game Development",
    "cpp": "C++",
    "backend": "Backend",
    "system-design": "System Design",
    "ux-design": "UX Design",
    "design-system": "Design Systems",
    "product-design": "Product Design",
    "frontend": "Frontend",
    "html": "HTML",
    "css": "CSS",
    "typescript": "TypeScript",
    "nextjs": "Next.js",
    "aws": "AWS",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "devops": "DevOps",
    "linux": "Linux",
    "api-design": "API Design",
    "qa": "QA & Testing",
    "data-engineer": "Data Engineering",
}

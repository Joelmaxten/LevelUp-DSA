"""
Common abbreviations/aliases for skills in the SO Survey vocabulary that
students' resumes are likely to use instead of the full name. Not
exhaustive - covers genuinely common cases found during testing, not a
complete abbreviation dictionary. Extend as real gaps are found, same as
the career-path keyword lists in india_jobs_processor.py.
"""

SKILL_ALIASES = {
    "aws": "Amazon Web Services (AWS)",
    "gcp": "Google Cloud",
    "js": "JavaScript",
    "ts": "TypeScript",
    "k8s": "Kubernetes",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "ml": None,  # too ambiguous (could mean many things) - deliberately not aliased
    "node": "Node.js",
    "nextjs": "Next.js",
    "vuejs": "Vue.js",
    "dotnet": ".NET",
    "csharp": "C#",
    "cpp": "C++",
}


# Extra spellings used ONLY by "which path fits my resume" extraction (extract_skills(...,
# extended_aliases=True)), so the original alias table - and therefore the "does my resume fit
# my path" results - stay exactly as they were. Each canonical name must be in the extended
# vocabulary (skill_vocabulary.py); only unambiguous spellings are listed.
EXTENDED_SKILL_ALIASES = {
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "reactjs": "React",
    "react.js": "React",
    "expressjs": "Express",
    "express.js": "Express",
    "nodejs": "Node.js",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "html5": "HTML/CSS",
    "css3": "HTML/CSS",
    "mssql": "Microsoft SQL Server",
    "tailwind": "Tailwind CSS 4",
    "tailwindcss": "Tailwind CSS 4",
    "tf": None,   # TensorFlow, or "terraform", or a typo - too ambiguous
}

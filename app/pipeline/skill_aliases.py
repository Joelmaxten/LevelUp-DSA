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

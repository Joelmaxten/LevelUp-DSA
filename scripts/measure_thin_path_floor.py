"""
Measures the roadmap signal for thin paths (fewer than 30 survey respondents) on three synthetic
developer resumes and two CONTROL resumes with unrelated or very generic skills, to choose the evidence
floor in app/pipeline/path_fit.py (THIN_PATH_MIN_HITS). Local only. Prints, per resume, how many of the
top-30 retrieved knowledge-base chunks are tagged with each thin path (raw count and share of the 30).

    PYTHONPATH=. python scripts/measure_thin_path_floor.py
"""
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.config import Config
from app.pipeline import path_fit, rag

RESUMES = {
    "(a) Python, SQL, MySQL, Git": ["Python", "SQL", "MySQL", "Git"],
    "(b) JavaScript, React, Node.js, TypeScript, HTML/CSS": ["JavaScript", "React", "Node.js", "TypeScript", "HTML/CSS"],
    "(c) Python, TensorFlow, PyTorch, pandas, Docker": ["Python", "TensorFlow", "PyTorch", "pandas", "Docker"],
    "CONTROL 1: Excel, Word, Tally": ["Excel", "Word", "Tally"],
    "CONTROL 2: Excel, Word, PowerPoint, Tally, Typing, Photoshop": ["Excel", "Word", "PowerPoint", "Tally", "Typing", "Photoshop"],
}


def main():
    app = create_app()
    index, chunks = rag.load_index(Config.FAISS_INDEX_PATH)
    with app.app_context():
        stats = path_fit.load_survey_stats()
    thin = sorted(p for p, d in stats["paths"].items() if d["n"] < path_fit.MIN_RESPONDENTS)
    print("thin paths:", ", ".join(f"{p} ({stats['paths'][p]['n']})" for p in thin), "\n")
    print(f"{'resume':<62}" + "".join(f"{p[:11]:>12}" for p in thin) + f"{'max':>6}")
    for label, skills in RESUMES.items():
        hits = rag.search(path_fit.skills_summary(set(skills)), index, chunks, top_k=path_fit.RETRIEVE_K, career_path=None)
        counts = [sum(1 for c in hits if p in c["career_paths"]) for p in thin]
        print(f"{label:<62}" + "".join(f"{n:>12}" for n in counts) + f"{max(counts):>6}")


if __name__ == "__main__":
    main()

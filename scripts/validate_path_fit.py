"""
Runs the path-fit ranking (app/pipeline/path_fit.py) on three synthetic resumes and prints the
results with the numbers behind them. Local only (database read, embedding model, FAISS index);
no external service. The weights are NOT tuned here: this is a read-out, not a calibration.

    (a) Python, SQL, MySQL, Git
    (b) JavaScript, React, Node.js, TypeScript, HTML/CSS
    (c) Python, TensorFlow, PyTorch, pandas, Docker

Usage:
    PYTHONPATH=. python scripts/validate_path_fit.py
"""
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.pipeline import path_fit, rag
from app.config import Config

RESUMES = {
    "(a) Python, SQL, MySQL, Git": {"Python", "SQL", "MySQL", "Git"},
    "(b) JavaScript, React, Node.js, TypeScript, HTML/CSS": {"JavaScript", "React", "Node.js", "TypeScript", "HTML/CSS"},
    "(c) Python, TensorFlow, PyTorch, pandas, Docker": {"Python", "TensorFlow", "PyTorch", "pandas", "Docker"},
}


def main():
    app = create_app()
    index, chunks = rag.load_index(Config.FAISS_INDEX_PATH)
    with app.app_context():
        stats = path_fit.load_survey_stats()
        for label, skills in RESUMES.items():
            hits = rag.search(path_fit.skills_summary(skills), index, chunks, top_k=path_fit.RETRIEVE_K, career_path=None)
            totals = path_fit.load_path_totals(chunks)
            result = path_fit.rank_paths(skills, stats, hits, totals)
            survey = path_fit.survey_scores(skills, stats)
            roadmap = path_fit.roadmap_scores(hits, totals)
            print("=" * 100)
            print(label)
            print("=" * 100)
            print(f"{'LIST A (30+ respondents)':<34}{'fit%':>6} {'resp':>5} {'survey raw':>11} {'roadmap raw':>12}  matched skills (survey)")
            for r in result["list_a"]:
                print(f"{r['path']:<34}{r['fit_pct']:>6.1f} {r['respondent_count']:>5} {survey[r['path']]['score']:>11.3f} {roadmap.get(r['path'], 0):>12.4f}  {', '.join(r['matched_skills']) or '-'}")
            print(f"\nLIST B (thin paths with at least {path_fit.THIN_PATH_MIN_HITS} of {path_fit.RETRIEVE_K} retrieved chunks): rank only, no percentage")
            for r in result["list_b"]:
                print(f"  {r['rank']}. {r['path']} ({r['respondent_count']} respondents)  matched: {', '.join(r['matched_skills']) or '-'}")
            if not result["list_b"]:
                print("  (none)")
            print(f"\nnear-ties A: {result['near_ties']['a'] or 'none'}")
            counts = {}
            for c in hits:
                for p in c["career_paths"]:
                    counts[p] = counts.get(p, 0) + 1
            print("retrieved-chunk counts by path (of 30):", dict(sorted(counts.items(), key=lambda kv: -kv[1])[:8]))
            print()


if __name__ == "__main__":
    main()

"""Regenerates docs/QUIZ_QUESTION_BANK.md from career_quiz_data.py (and the original bank at commit 4505662, for the old -> new signals).
    PYTHONPATH=. python scripts/generate_quiz_bank_doc.py
"""
import sys, subprocess, types, io; sys.path.insert(0, ".")
from app.pipeline.career_quiz_data import QUESTIONS, OPTION_SIGNALS
src = subprocess.run(["git","show","4505662:app/pipeline/career_quiz_data.py"],capture_output=True,encoding="utf-8").stdout
old = types.ModuleType("o"); exec(compile(src,"o","exec"), old.__dict__)
def ab(l): return ", ".join(l) if l else "(none)"
out = io.StringIO()
w = lambda s="": out.write(s + "\n")
w("# Career quiz question bank (after the redesign)")
w()
w("Generated from `app/pipeline/career_quiz_data.py` and the original bank at commit 4505662. The option-to-path")
w("mapping is hand-authored judgment, not derived from data. Regenerate this file if the bank changes.")
w()
w("## New questions (Q11-Q18)")
for q in [f"Q{i}" for i in range(11, 19)]:
    w(); w(f"**{q}. {QUESTIONS[q]['text']}**"); w()
    for o, t in QUESTIONS[q]["options"].items():
        w(f"- {o}. {t} → {ab(OPTION_SIGNALS[(q, o)])}")
w()
w("## Original questions (Q1-Q10): wording unchanged, signals rewritten")
w()
w("Each option signals at most 3 paths now (it was up to 6), the three options that signalled nothing now signal something,")
w("and every pair of split paths gets distinct signals. Old → new for every option (an option marked *same* kept its signals):")
for i in range(1, 11):
    q = f"Q{i}"; w(); w(f"**{q}. {QUESTIONS[q]['text']}**"); w()
    for o, t in QUESTIONS[q]["options"].items():
        o_old, o_new = old.OPTION_SIGNALS[(q, o)], OPTION_SIGNALS[(q, o)]
        if o_old == o_new:
            w(f"- {o}. {t} → *same:* {ab(o_new)}")
        else:
            w(f"- {o}. {t}"); w(f"  - old: {ab(o_old)}"); w(f"  - new: {ab(o_new)}")
open("docs/QUIZ_QUESTION_BANK.md", "w", encoding="utf-8", newline="\n").write(out.getvalue())
print("written", len(out.getvalue().splitlines()), "lines")

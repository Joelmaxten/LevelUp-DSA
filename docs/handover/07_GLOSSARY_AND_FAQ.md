# 07. Glossary and FAQ

## Glossary

| Term | Meaning in this project |
|---|---|
| Career path | One of 15 IT career directions the quiz ranks (list in file 03) |
| Confidence score | A per-path percentage from the quiz engine; a relative ranking, not a probability of success |
| Goals | Three questions after the quiz that tailor practice and the roadmap but do not change the match |
| Roadmap | Phased list of steps to learn for a path; base roadmaps are reviewed JSON files |
| Base roadmap | The reviewed, cached roadmap for a path, personalised by one short LLM call |
| RAG | Retrieval-augmented generation: retrieve relevant text from the knowledge base, then have an LLM write from it |
| FAISS | Library for fast similarity search over vectors; here it indexes 5,115 knowledge-base chunks |
| Embedding (all-MiniLM-L6-v2) | A small model that turns text into vectors so similar text can be found |
| spaCy PhraseMatcher | Rule-based matcher that finds listed skill phrases in resume text |
| ATS score | A lightweight, explainable resume score based on structure and keywords; not a real employer ATS |
| Scenario | A short workplace situation with decision questions and a final coding question |
| Level map | The game-style list of the 5 scenarios of a path; a level unlocks after passing the previous (70%+) |
| Code pool / variant | The set of coding problems for a scenario and the goal-specific versions of each |
| Hidden tests | Test cases whose inputs are never sent to the browser; only "a of b passed" is shown |
| Run / Submit | Run tests the code on all tests, repeatable, nothing locked; Submit locks the answer |
| OneCompiler | Third-party API that executes code in Python, C++, Java, JavaScript |
| XP / level / streak / badge | Gamification values, recomputed from activity, nothing stored |
| Placement readiness | A 0-100 score from roadmap, skill match, scenarios and streak; ready at 70 |
| CSRF | Attack where another site makes your browser send a request; blocked by a token on every state-changing request |
| BOOT_ID | A random value per server start; used to log everyone out after a restart in development |
| Smoke test | A script that exercises the app against a real database and checks results |
| Golden file | A saved expected output a test compares against |

## FAQ (honest answers)

**Why not let an LLM run the whole thing?** Correctness matters for scenarios, problems and roadmaps, and an LLM can be
wrong or inconsistent. Authored, reviewed, validated content is predictable and testable; the LLM is used for two small
personalisation and feedback tasks.

**How accurate is the career quiz?** Unknown. Its signals are hand-authored judgement. It is tested for consistency
(same answers give same result; opposite answers give opposite results) but has not been compared with real outcomes.
Ways to check are listed in file 04.

**Where do the readiness weights come from?** A design choice (25/35/30/10). They are not derived from data.

**Does the Goals page change my career match?** No. It tailors coding problems, starred scenarios and the roadmap note.

**Why can't I see the hidden test inputs?** So answers cannot be hard-coded to the tests. They stay on the server.

**Is user code run on your server?** No. It runs in OneCompiler. A local runner exists for development only and is not a
sandbox, so it must never be used on a server.

**What stops someone skipping a level?** The server checks that the previous scenario was passed and returns 403
`scenario_locked`; the browser cannot bypass it.

**Why no leaderboard?** Privacy, and an almost empty board in a demo.

**How do you prevent XP farming?** XP counts best scores and distinct achievements only.

**How is the password stored?** Hashed with bcrypt, never plain text.

**What happens to uploaded resumes and photos?** Resume text is analysed and results saved; profile pictures are re-encoded
to a small JPEG. (Retention policy for a deployed system is not defined, because it is not deployed.)

**Is it deployed?** No. It runs locally. Production settings exist but have never been run on a server.

**What are the main limitations?** See file 04: unvalidated quiz, no user study, C++/Java through OneCompiler not
confirmed, one weaker base roadmap, curated skill list, no deployment.

**What would you do next?** Check the quiz with a classmate survey and expert review, consider a chat-style quiz with
code-validated scoring (idea only), and deploy.

**Why is there no Skill DNA Map?** It was an early plan, replaced by scenarios and coding questions; the old tables were
dropped. The Master Document still mentions it and is out of date.

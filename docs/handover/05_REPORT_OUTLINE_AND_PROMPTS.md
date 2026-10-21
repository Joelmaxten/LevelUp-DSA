# 05. Report outline and ready-to-paste prompts

**How to use:** paste `CONTEXT_PACK.md` into the LLM first. Then paste the prompt for one chapter. Do one chapter per
message. Check the draft against the listed sources.

## Standard preamble (already inside each prompt below; use it if you write your own)

> You are helping write documentation for a student software project. Use ONLY the facts in the files I gave you. If a
> fact is missing, write [NOT IN SOURCES]. Never invent numbers, user data, accuracy figures or results. The system is
> not deployed and has no real-user data. The quiz is not validated against real outcomes. Plain, factual tone; no
> marketing language.

## Chapter map

| # | Chapter | Main sources |
|---|---|---|
| 1 | Introduction and problem statement | 01 |
| 2 | Objectives and scope | 01, 02 |
| 3 | Literature / related systems (needs outside reading) | 01 (only the gap list); teammates add references |
| 4 | System design and architecture | 01, 03 sections 2-4 |
| 5 | Database design | 03 (tables) |
| 6 | Module description (one section per feature) | 02, 03 |
| 7 | Implementation details and technologies | 01, 02, DEV_SETUP |
| 8 | Testing and results | 04, 03 (test suites) |
| 9 | Limitations and future work | 04 |
| 10 | Conclusion | 01, 04 |
| A | Screenshots | 06 |

## Prompts

### Ch 1 Introduction and problem statement
```
Using only the attached files, write the Introduction chapter (about 600 words): the problem (four gaps), the target
students, and a one-paragraph description of LevelUp DSA. Do not mention results or deployment. Mark anything missing as
[NOT IN SOURCES].
```

### Ch 2 Objectives and scope
```
Write Objectives (5-7 measurable-by-inspection objectives, each tied to a feature) and Scope (what is included: 15 paths,
75 scenarios, 120 coding problems, etc., using the exact numbers in the files; and what is out of scope: deployment,
mobile app, leaderboard, real-user study).
```

### Ch 3 Related work
```
I will supply references myself. Write only a structure for this chapter: headings for (a) career-guidance tools,
(b) coding-practice platforms, (c) resume analyzers, (d) gamification in learning, and (e) the gap LevelUp DSA fills,
using only the four gaps in file 01. Do not invent citations or named products.
```

### Ch 4 System design and architecture
```
Write the System Design chapter: the architecture layers (browser, Flask routes, pipeline logic, database, LLM layer,
external services), the end-to-end student journey, and the technology choices with the reason for each (table in file
01). Then give me the PlantUML or Mermaid source for (1) an architecture diagram and (2) a student-journey flowchart.
Use only components named in the files.
```

### Ch 5 Database design
```
Using the database table list in file 03, write the Database Design chapter: one paragraph per table (purpose, key
columns, relationships), then Mermaid source for an ER diagram. Do not add tables or columns that are not listed.
```

### Ch 6 Module descriptions
```
Write the Module Description chapter, one subsection per feature in file 02 (accounts, quiz, Goals, roadmap, resume
analyzer, scenarios, coding questions, gamification, readiness, dashboard). For each: purpose, inputs, processing,
outputs, key design decision. About 250 words each. State the quiz-signal and readiness-weight limitations where they
apply.
```

### Ch 7 Implementation
```
Write the Implementation chapter: technologies and why, the LLM layer and its three providers, how code is executed
(OneCompiler, hidden tests stay on the server), security measures (CSRF, no innerHTML, bcrypt, rate limits, server-side
grading and unlock), and the content pipeline (authored JSON, validator, blind-solve checker). Cite file names from file
03 where useful.
```

### Ch 8 Testing and results
```
Write the Testing chapter from file 04: the eight smoke-test suites (table with check counts), the other verification
steps, and a clear section "What was not verified". Do NOT report accuracy, user-study or performance numbers; none exist.
```

### Ch 9 Limitations and future work
```
Write Limitations and Future Work from file 04. Keep the "idea, not built" items clearly labelled as future work.
```

### Ch 10 Conclusion
```
Write a 250-word Conclusion: what was built (use exact counts), what was verified, what was not, and the next steps.
No claims of real-world impact.
```

### Slides (10 slides)
```
Make a 10-slide outline for a 7-minute demo: problem, solution, architecture, quiz, roadmap, resume analyzer, scenarios
and coding, gamification and readiness, testing and limits, future work. For each slide give a title, 3 bullets and the
screenshot from file 06 to use.
```

### Viva preparation
```
From files 04 and 07, write 25 likely viva questions with short honest answers. Include the hard ones about quiz
validity, why the LLM is used sparingly, security, and what was not tested.
```

## Checking an LLM draft (do this every time)

1. Search the draft for any number; each must appear in the sources.
2. Search for "deployed", "accuracy", "users", "leaderboard", "Skill DNA", "Piston"; each is a red flag.
3. Make sure limitations are not hidden.

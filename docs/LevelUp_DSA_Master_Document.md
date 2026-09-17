# LevelUp DSA — Complete Master Document

> Everything discussed, decided, designed, and locked across all conversations.
> Last updated: August 2026
> Team: Joel (lead), Karthikeya, Ganesh, Jayavardhana
> Guide: Dr. B.M. Vidyavathi — Dept. of AIML, BITM Ballari

\---

# TABLE OF CONTENTS

1. Project Identity
2. Problem Statement \& SDG
3. Target Audience
4. Tech Stack — Final Decisions
5. Data Sources
6. System Architecture — 5 Layers
7. Database Schema
8. Phase 1 — Career Guidance
9. Phase 2 — Resume Analyzer
10. Phase 3 — Gamified DSA (Skill DNA Map)
11. Placement Readiness Score
12. Algorithms \& Techniques
13. AI/ML Concepts Applied
14. How FAISS Works
15. Development Model
16. Folder Structure
17. Team Task Division
18. Timeline
19. UML Diagrams
20. Class Diagram
21. What We Removed \& Why
22. Key Decisions Locked
23. PPT Mistakes Fixed
24. Interview Preparation — LevelUp DSA
25. Interview Preparation — rPPG Heart Rate Monitor
26. Python Foundations
27. Java Foundations
28. AWS Foundations
29. Future Scope
30. Panel Review — Placement Readiness Assessment

\---

# 1\. PROJECT IDENTITY

**Full title:**
LevelUp DSA: Personalized Career Intelligence System with Gamified Data Structures and Problem Solving for Students Interested in the IT Sector

**Short name:** LevelUp DSA

**Repository:** levelup-dsa (GitHub)

**College:** Ballari Institute of Technology \& Management

**Department:** Artificial Intelligence \& Machine Learning

**Guide / HOD:** Dr. B.M. Vidyavathi

**Team:**

* Joel — Lead, Architecture, Phase 1 pipeline, FAISS, integration
* Karthikeya — Phase 1 frontend, quiz, conversation engine
* Ganesh — Phase 2, resume analyzer, NLP pipeline
* Jayavardhana — Phase 3, D3.js Skill DNA Map, Piston integration

\---

# 2\. PROBLEM STATEMENT \& SDG

## Problem Statement

Students interested in the IT sector, particularly those from tier 2 and tier 3 engineering colleges, face significant challenges in identifying suitable career paths, assessing their placement readiness, and acquiring structured Data Structures and problem-solving skills relevant to industry requirements.

**Four specific problems:**

* No structured career direction — students study randomly without knowing what industry wants
* No clear skill gap awareness — students don't know what they're missing for their target role
* DSA learning is disconnected from real career goals — LeetCode doesn't tell you WHY a topic matters for YOUR path
* No unified measure of placement readiness — students don't know where they stand

## SDG Connections

**SDG 4 — Quality Education:**
Providing inclusive, personalized, structured learning accessible to students at non-tier-1 institutions who lack access to quality career mentorship.

**SDG 8 — Decent Work and Economic Growth:**
Bridging the gap between education and employment by connecting students' learning directly to industry skill requirements and job market data.

\---

# 3\. TARGET AUDIENCE

* Students interested in the IT sector — regardless of branch (CS, IT, ECE, any)
* Specifically targeted at tier 2 and tier 3 Indian engineering colleges
* Students who don't know which tech career path to pursue
* Students wanting non-traditional CS careers — AI Entrepreneur, Product Manager, EdTech, FinTech, AgriTech
* Students preparing for placement season

**Why NOT "CS students":**
Guide pointed out that "CS students" is too limiting. ECE students, IT branch students, diploma holders pivoting to tech — all are valid target users. "Students interested in the IT sector" is broader, more inclusive, and more accurate.

\---

# 4\. TECH STACK — FINAL DECISIONS

|Layer|Technology|Why Chosen|
|-|-|-|
|Backend|Flask (Python)|Jinja2 templating, Flask-Login, SQLAlchemy — all native. FastAPI is for REST APIs, not server-side rendering|
|Auth|Flask-Login + bcrypt|Mature, well-documented, session-based auth|
|Frontend|HTML + CSS + JavaScript + Jinja2|No React needed — server-side rendering sufficient. D3.js handles the only complex UI|
|Visualization|D3.js|Skill DNA Map interactive graph — works natively in JS|
|Database|PostgreSQL + SQLAlchemy ORM|Better free cloud hosting (Render, Railway). Better JSON support than MySQL|
|Vector Store|FAISS (local pip install)|Local library — no API key, no cost, no internet dependency during inference|
|Embeddings|sentence-transformers (all-MiniLM-L6-v2)|22MB, 384 dimensions, 14,200 sentences/sec on CPU, Apache 2.0 license|
|NLP|spaCy|Named Entity Recognition for skill extraction from resumes|
|PDF Parsing|pdfplumber|Resume PDF text extraction|
|LLM|Gemini (gemini-flash-latest, via google-genai SDK)|Free tier via Google AI Studio. gemini-1.5-flash and the entire google-generativeai package were fully shut down/deprecated after this decision was locked — gemini-flash-latest is an alias that tracks Google's current recommended flash model, chosen specifically to be resilient against this happening again|
|Code Execution|Piston (self-hosted)|Self-hosted Docker sandboxed execution. NOT Judge0 API. Coordinator decision|
|Live Jobs|Adzuna API|Live job listings — called at runtime, not stored|
|Resources|YouTube Data API|Curated learning videos per roadmap step — Phase 1 only|
|Data Processing|pandas, NumPy|Cleaning, normalization, frequency analysis|
|Version Control|Git + GitHub|Repo: levelup-dsa|

## Why NOT These Technologies

|Rejected|Reason|
|-|-|
|OpenAI|No free tier|
|LangChain|Abstracts everything — no academic originality. Built RAG manually instead|
|React|Server-side rendering via Jinja2 is sufficient. No need for separate frontend framework|
|FastAPI|Designed for REST APIs. Our project uses server-side HTML rendering|
|MySQL|PostgreSQL chosen — better free hosting support|
|Local LLM (Ollama)|4GB VRAM insufficient|
|Judge0 API|Replaced by self-hosted Piston (coordinator decision)|
|Web scraping|ToS violation — Naukri and Internshala explicitly prohibit it|
|ChromaDB / Pinecone|FAISS is local, free, faster for our scale, better academic credibility|

## Piston — Important Note

Piston is self-hosted — it runs on our own server. Therefore:

* Piston is NOT in External Services
* Piston sits in the Backend Layer under Gamified DSA Engine
* External Services only has: LLM API, Adzuna API, YouTube Data API

\---

# 5\. DATA SOURCES

No web scraping. All legally downloadable.

|Source|Method|License|Goes Into|
|-|-|-|-|
|Stack Overflow Developer Survey|Direct download|ODbL|FAISS (text) + PostgreSQL (numbers)|
|roadmap.sh GitHub|Git clone|MIT|FAISS (roadmap text)|
|Kaggle India Job Dataset|Direct download|Open|FAISS (job descriptions) + PostgreSQL (salary, titles)|
|Adzuna API|Runtime API calls|API|Not stored — live results|
|LinkedIn Economic Graph|PDF download|Free public|PostgreSQL (statistics only)|
|NASSCOM Reports|PDF download|Free public|PostgreSQL (statistics only)|

## What Goes Where

**FAISS (Vector Store) — text content needing semantic search:**

* Job description text
* Roadmap step descriptions
* Skill requirement sentences
* Technology descriptions

**PostgreSQL (Structured Storage) — numbers, categories, names:**

* Salary ranges
* Job titles
* Company names
* Workforce percentages
* Industry statistics
* Student profiles
* Progress data

**Adzuna — live at runtime:**

* Called when student needs live job listings
* Not embedded in FAISS — changes daily

## Why No Scraping

Naukri.com and Internshala both explicitly prohibit automated data extraction in their Terms of Service. Using legally downloadable datasets is ethically correct AND academically stronger — examiners can cite them.

*"We deliberately chose not to scrape job portals as their Terms of Service prohibit automated extraction. Instead we built our knowledge base using publicly available, legally downloadable datasets — Kaggle job posting datasets, Stack Overflow Developer Survey, and roadmap.sh open source content."*

\---

# 6\. SYSTEM ARCHITECTURE — 5 LAYERS

```
Layer 1 — Presentation
└── User interface · Dashboard (HTML + CSS + JS + Jinja2 + D3.js)

Layer 2 — Backend (Flask Server)
├── Career guidance engine      ← Phase 1
├── Resume analysis engine      ← Phase 2
└── Gamified DSA engine         ← Phase 3
    └── Piston (self-hosted)    ← internal, NOT external service

Layer 3 — Intelligence (RAG Pipeline)
├── Knowledge base (curated content)
├── FAISS retriever (semantic search)
└── Augmented prompt (profile + retrieved context)

Layer 4 — Data Layer
├── PostgreSQL    ← structured data, student profiles, job data, salaries
└── FAISS index   ← vector store (embeddings of knowledge base text)

Layer 5 — External Services (API calls over internet)
├── LLM API (Gemini 1.5 Flash)
├── Adzuna API (live job listings)
└── YouTube Data API (learning resources)

Data Sources (feeds into Data Layer offline)
└── SO Survey · roadmap.sh · Kaggle · NASSCOM · LinkedIn Economic Graph
```

## Key Architectural Clarifications

* FAISS = local pip install library → Backend component, NOT external service
* Piston = self-hosted Docker → Backend component, NOT external service
* LLM = Gemini API called over internet → External Service
* Knowledge Base text → FAISS vectors; structured data → PostgreSQL
* FAISS appears in TWO places: Data Layer (storage) and Intelligence Layer (retriever) — same FAISS, two roles

\---

# 7\. DATABASE SCHEMA

|Table|Key Columns|Purpose|
|-|-|-|
|Users|id, name, email, password\_hash, career\_path, total\_points, current\_streak|Central user profile|
|CareerPaths|id, name, type (IT/non-IT), description|All available career paths|
|RoadmapSteps|id, career\_path\_id, step\_number, title, resource\_link, is\_free|Learning steps per path|
|UserProgress|id, user\_id, step\_id, completed\_at|Roadmap completion tracking|
|DSANodes|id, topic, difficulty, career\_paths\[], prerequisites\[]|Skill DNA Map nodes|
|DSAProblems|id, node\_id, title, description, test\_cases, points|Problems per node|
|UserDSAActivity|id, user\_id, problem\_id, solved\_at, points\_earned|DSA solving history|
|NodeMastery|id, user\_id, node\_id, xp\_earned, problems\_solved, mastery\_level|Per-node mastery for brightness|
|Resumes|id, user\_id, file\_path, extracted\_skills, ai\_feedback, uploaded\_at|Resume uploads and feedback|
|SkillGap|id, user\_id, missing\_skills\[], target\_role, salary\_range|Computed skill gap|
|WeaknessProfile|user\_id, node\_id, weakness\_score, is\_bandit\_node, generated\_at|Bandit spawn data|
|UserAttempts|user\_id, node\_id, problem\_id, time\_taken, attempts\_count, hints\_used, is\_correct, attempted\_at|Behavior tracking for weakness computation|

\---

# 8\. PHASE 1 — CAREER GUIDANCE

## Entry Point

Quiz (8-12 questions) + short conversation. NO resume upload in Phase 1.

## Offline Data Pipeline (runs periodically, not on every request)

```
Raw data collected from sources
        ↓
Clean + standardize (pandas)
— Remove duplicates
— Normalize skill names (JS = JavaScript = javascript.js)
— Handle missing values
        ↓
Skill frequency analysis
— Count skill appearances per career path across job postings
— Rank skills by demand percentage
        ↓
Generate embeddings (sentence-transformers)
— Convert text content to 384-dimensional vectors
        ↓
Store in FAISS index (text) + PostgreSQL (structured)
```

## Online Pipeline (per student, real-time)

```
Quiz (8-12 questions: interests, skills, work style, time, goals)
        ↓
Conversation (goals, dislikes, IT vs non-IT, target companies)
        ↓
Assemble student profile
        ↓
Career path scoring (content-based filtering)
        ↓
FAISS query — convert profile to vector, retrieve top-K knowledge base entries
        ↓
Augment prompt = student profile + retrieved context + career path
        ↓
LLM call → generates personalized roadmap (constrained to retrieved data only)
        ↓
YouTube Data API → fetch curated resources per roadmap step
        ↓
Validate output → Save to PostgreSQL → Display to student
```

## Career Paths Supported

**Traditional IT:**
Full Stack Developer, Data Scientist, ML Engineer, DevOps Engineer, Cybersecurity Analyst, Mobile Developer, Backend Developer

**Non-Traditional CS (still technical):**
AI Entrepreneur, Product Manager (Tech), AI in Healthcare, EdTech Specialist, AgriTech Domain Expert, FinTech Analyst, Tech Consultant, UX Researcher

**Removed:** Purely non-technical fields (pure business, pure farming, pure medicine without CS component) — breaks DSA coherence

## RAG Architecture

RAG = Retrieval Augmented Generation

* **Retrieval** — FAISS searches knowledge base for most relevant data
* **Augmentation** — retrieved data combined with student profile into structured prompt
* **Generation** — LLM formats and personalizes into readable roadmap

LLM has no autonomy — cannot recommend anything not in retrieved data. Eliminates hallucination.

**Offline pipeline = building the library. RAG = using the library in real time.**

## Original Contributions in Phase 1

1. Conversation engine — dialogue flow, signal extraction, career path mapping — original Python code
2. Data pipeline — Python scripts for downloading, cleaning, processing datasets
3. Skill frequency analysis — ranks skills by demand per career path
4. Prompt engineering architecture — structured prompts constraining LLM output
5. Career path scoring algorithm — weighted scoring from quiz answers
6. Non-traditional career path support — no existing platform does this

\---

# 9\. PHASE 2 — RESUME ANALYZER

## Two Entry Points

1. **Standalone** — skip Phase 1, go directly to resume upload
2. **Post-roadmap** — complete Phase 1, update resume with new skills, measure growth

## Pipeline

```
Resume PDF upload
        ↓
pdfplumber → extract raw text
        ↓
spaCy NER → identify skills, technologies, experience levels
        ↓
Set difference → skill gap = required skills (PostgreSQL) minus student skills
        ↓
PostgreSQL query → job role matching, company suggestions, salary aggregation
        ↓
Adzuna API → live job listings for matched roles
        ↓
One LLM call → resume improvements + 30-day action plan + keyword suggestions
        ↓
Save skill gap report to student profile → display placement readiness report
```

## Report Contents

* Current skill level — Beginner, Intermediate, Advanced
* Specific skill gap — missing skills ranked by importance
* Job roles student qualifies for RIGHT NOW
* Job roles student is 2-3 months away from qualifying for
* Companies actively hiring — from Adzuna API
* Salary expectation — aggregated from Kaggle + Adzuna
* Line-by-line resume improvement suggestions — from LLM
* 30-day action plan — from LLM

## Original Contributions in Phase 2

1. Skill gap analysis logic — Python set operations — original code
2. Job role matching algorithm — queries our own data, not third-party
3. Salary estimation — aggregated from our own pipeline — India-specific
4. Integration of all five outputs into one placement readiness report — novel

\---

# 10\. PHASE 3 — GAMIFIED DSA (SKILL DNA MAP)

## The Skill DNA Map

Interactive D3.js directed acyclic graph where every node = one DSA topic.

**Visual features:**

* Node brightness = mastery level (dim = not started, glowing = mastered)
* Career path highlighting = nodes critical to student's career path glow amber
* Prerequisite locks = nodes with incomplete prerequisites are dimmed and locked
* Two students with different career paths see completely different highlighted maps

## Two Stage Design — LOCKED

### Stage 1 — Static Map (Learning Phase)

* Same DAG structure for ALL students on same career path
* Prerequisite unlock via topological ordering — cannot access Trees before Arrays
* Career-contextualised problems generated by LLM using student profile from PostgreSQL

  * Full Stack student: "Your inventory API has a bug in hash map logic — fix it"
  * AI Entrepreneur: "Your recommendation system has a cycle in linked list — find it"
* Code submitted to self-hosted Piston — sandboxed Docker execution
* System SILENTLY tracks behavior: time\_taken, accuracy, hints\_used, avoidance

### Stage 2 — Adaptive Bandit Map (unlocks AFTER static map complete)

**Why after completion:**
Complete behavioral data from ENTIRE map gives accurate weakness profile. Partial data gives misleading results.

**Weakness Score Formula:**

```python
weakness\\\\\\\_score = (accuracy\\\\\\\_rate \\\\\\\* 0.5) + (normalized\\\\\\\_time \\\\\\\* 0.3) + (hint\\\\\\\_rate \\\\\\\* 0.2)
```

**Normalization — critical design decision:**
Scores normalized relative to student's OWN performance — not compared to other students. A slow learner with consistent accuracy has LOW weakness score — no bandit. Only genuine weak points trigger bandits.

**Bandit Spawn Trigger:**

```python
BANDIT\\\\\\\_THRESHOLD = 0.7

if weakness\\\\\\\_score >= BANDIT\\\\\\\_THRESHOLD:
    spawn\\\\\\\_bandit(node\\\\\\\_id, student\\\\\\\_id)
```

**Bandit appears on:** Static map (same map, different threat positions per student)

**Bandit question combines:**

* Weak DSA topic (e.g., Trees)
* Student's career path (e.g., Full Stack)
* Industry context (e.g., "You are a backend engineer at a startup...")

**Why bandits on static map:**
Bandits blocking nodes the student can see their classmates already passed = powerful emotional trigger. "Everyone else walked through here freely. You have unfinished business." Game design psychology.

## Gamification Mechanics

|Mechanic|How It Works|
|-|-|
|XP|Easy = 10, Medium = 25, Hard = 50|
|Node Mastery|XP accumulates per node, mastery level increases, node glows brighter|
|Prerequisite Lock|Nodes locked until required predecessors mastered|
|Streaks|Solve one problem daily to maintain, miss = reset|
|Career Relevance|Solving career-critical nodes updates placement readiness score|
|Hint System|One hint per problem, costs XP — forces attempt before revealing|

## Piston — Code Execution

Self-hosted, runs in Docker containers, sandboxed, time and memory limited.

```
Student submits code in browser
        ↓
Flask backend receives code + language + test cases
        ↓
POST request to localhost:2000/api/v2/execute (Piston)
        ↓
Piston runs in isolated container — no filesystem, no network, no system access
        ↓
Returns stdout, stderr, exit code
        ↓
Flask compares against expected output → pass or fail → returned to student
```

## Original Contributions in Phase 3

1. Skill DNA Map — entire D3.js graph, node relationships, prerequisite logic — scratch
2. Career-contextualised problem generation — prompt engineering tying DSA to career scenarios
3. Node mastery algorithm — XP accumulation, brightness calculation, unlock logic
4. Weakness scoring formula — multi-signal, normalized, original weights (0.5, 0.3, 0.2)
5. Bandit spawn logic — threshold detection, weakness profile computation
6. Two-stage design concept — static map first, adaptive map after completion

\---

# 11\. PLACEMENT READINESS SCORE

## Formula

```python
def placement\\\\\\\_readiness(user\\\\\\\_id):
    roadmap    = roadmap\\\\\\\_completion(user\\\\\\\_id)      # Phase 1 — steps completed / total steps
    skill\\\\\\\_gap  = skill\\\\\\\_gap\\\\\\\_closure(user\\\\\\\_id)       # Phase 2 — skills acquired / skills required
    dsa        = dsa\\\\\\\_mastery(user\\\\\\\_id)             # Phase 3 — nodes mastered / total nodes
    streak     = streak\\\\\\\_consistency(user\\\\\\\_id)       # Phase 3 — streak / days since registration

    score = (roadmap   \\\\\\\* 0.25 +
             skill\\\\\\\_gap \\\\\\\* 0.35 +
             dsa       \\\\\\\* 0.30 +
             streak    \\\\\\\* 0.10)

    return round(score, 1)  # 0 to 100
```

## Weight Rationale

* Skill gap (0.35) — highest weight, most directly predicts placement success
* DSA mastery (0.30) — second, technical interviews are DSA heavy
* Roadmap completion (0.25) — direction matters but execution matters more
* Streak (0.10) — consistency signal but not primary predictor

## Threshold

Score > 70 = placement ready

## Dashboard Display

```
Placement Readiness Score: 67/100

Career Direction      ████████░░  78%  Phase 1
Skill Gap Closure     █████░░░░░  52%  ← needs work
DSA Mastery           ███████░░░  68%  Phase 3
Consistency           █████████░  90%  Phase 3

You qualify for: Junior Backend Developer
Next milestone: Close skill gap in Trees and System Design
```

\---

# 12\. ALGORITHMS \& TECHNIQUES

|Algorithm|Phase|Purpose|
|-|-|-|
|TF-IDF / Frequency Analysis|1|Skill demand ranking from scraped data|
|Sentence Embeddings|1|Text to 384-dimensional vector conversion|
|Cosine Similarity via FAISS|1|RAG retrieval — semantic similarity search|
|Content-Based Filtering|1|Career path scoring from quiz answers|
|Named Entity Recognition (NER)|1, 2|Skill extraction from text and resumes|
|Set Difference|2|Skill gap = required skills minus student skills|
|Statistical Aggregation|2|Salary range estimation from datasets|
|DAG + Topological Ordering|3|Skill DNA Map prerequisite unlock logic|
|Weighted Weakness Scoring|3|Multi-signal weakness profile computation|
|Adaptive Threshold Detection|3|Bandit spawn trigger when score ≥ 0.7|
|Prompt Engineering|1, 3|Constrained LLM generation|

\---

# 13\. AI/ML CONCEPTS APPLIED

|Concept|Where|How|
|-|-|-|
|Natural Language Processing|Phase 1, 2|NER extracts skills from text and resumes|
|Text Embeddings|Phase 1|sentence-transformers converts text to dense vectors|
|Information Retrieval|Phase 1|FAISS vector similarity search for RAG|
|Retrieval Augmented Generation|Phase 1|Full RAG pipeline — retrieve, augment, generate|
|Content-Based Filtering|Phase 1|Quiz answers mapped to career paths via weighted scoring|
|Prompt Engineering|Phase 1, 3|Structured prompts constrain LLM output|
|Data Mining|Phase 1|Skill frequency analysis from raw datasets|
|Skill Gap Modeling|Phase 2|Set operations comparing student vs industry skills|
|RL Reward Design Concepts|Phase 3|XP system, streak mechanics, progressive unlocking|

\---

# 14\. HOW FAISS WORKS

## What FAISS Is

Facebook AI Similarity Search — searches through vectors to find the most similar ones to a query. Not keyword matching — it matches meaning.

## Step by Step

**Step 1 — Convert text to vectors:**
sentence-transformers converts any text into 384 numbers. Similar meanings produce similar numbers.

```
"ML engineer"    → \\\\\\\[0.23, -0.41, 0.87, 0.12, ...]
"ML developer"   → \\\\\\\[0.21, -0.39, 0.85, 0.14, ...]  ← very similar
"chef"           → \\\\\\\[-0.44, 0.31, -0.22, 0.67, ...] ← very different
```

**Step 2 — Build index offline:**
All knowledge base text converted to vectors and stored in FAISS index.

**Step 3 — Convert query at runtime:**
Student profile converted to vector using same model.

**Step 4 — Cosine similarity search:**

```
similarity = (A · B) / (|A| × |B|)
Result between -1 and 1
1  = identical meaning
0  = completely unrelated
-1 = opposite meaning
```

**Step 5 — Return top K results:**
FAISS returns indices of most similar vectors. Corresponding documents retrieved and passed to LLM.

## Why Better Than Keyword Search

```
Student says: "I want to build AI startups"

Keyword search: looks for exact words "AI" AND "startups"
FAISS:          finds "AI Entrepreneur roadmap" at 0.94 similarity
                finds "AI in Diagnostics career" at 0.91 similarity
                even without exact keyword match
```

## Why all-MiniLM-L6-v2

Size 22MB, 384 dimensions, 14,200 sentences/second on CPU, Apache 2.0 license. Lightweight, fast, free, academically citable.

## FAISS is NOT External Service

FAISS = pip install library. Runs locally. No API key. No internet needed. Belongs in Backend/Data Layer.

\---

# 15\. DEVELOPMENT MODEL

**Model: Incremental Development Model**

NOT Agile. Guide explicitly rejected Agile.

**Why NOT Agile:**
Agile requires iterative user consultation — sprint reviews, user stories, customer collaboration. We are not consulting end users between development cycles. Calling it Agile without actual user consultation is academically dishonest.

**Why Incremental fits:**

* Requirements and architecture finalised upfront
* System divided into three pre-defined increments (three phases)
* Each increment is independently buildable and testable
* Final product emerges from integrating all three increments
* No going back to change requirements

**Examiner answer:**
*"We follow the Incremental Development Model. Requirements were finalised upfront. The system is divided into three increments corresponding to three phases. Each increment delivers a working subsystem. Our guide noted that Agile requires iterative user consultation which we are not doing — Incremental is the honest and correct model for our project."*

\---

# 16\. FOLDER STRUCTURE

```
levelup-dsa/
├── app/
│   ├── \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py              ← starts Flask app
│   ├── models.py                ← all database table definitions
│   ├── routes/
│   │   ├── auth.py              ← login and signup
│   │   ├── quiz.py              ← career quiz and conversation
│   │   ├── roadmap.py           ← roadmap generation and display
│   │   ├── resume.py            ← resume upload and analysis
│   │   └── dsa.py               ← skill DNA map and problem solving
│   ├── pipeline/
│   │   ├── processor.py         ← data cleaning and skill frequency analysis
│   │   ├── embedder.py          ← sentence-transformers embedding generation
│   │   └── rag.py               ← FAISS index and retrieval logic
│   ├── templates/               ← all HTML files (Jinja2)
│   └── static/                  ← CSS, JavaScript, D3.js skill DNA map
├── venv/                        ← virtual environment
├── requirements.txt             ← all Python dependencies
├── config.py                    ← API keys, database URL
├── run.py                       ← entry point to start the app
└── .gitignore                   ← excludes venv, secrets, \\\\\\\_\\\\\\\_pycache\\\\\\\_\\\\\\\_
```

\---

# 17\. TEAM TASK DIVISION

|Member|Owns|Key Deliverables|
|-|-|-|
|Joel (Lead)|Architecture, Flask setup, auth, integration|GitHub repo, models.py, auth routes, connecting all phases|
|Karthikeya|Phase 1 — quiz, conversation, roadmap display|quiz.py, roadmap.py, career scoring, frontend templates|
|Ganesh|Phase 1 data pipeline + Phase 2 resume analyzer|processor.py, embedder.py, rag.py, resume.py, FAISS index|
|Jayavardhana|Phase 3 — Skill DNA Map + DSA + Piston|dsa.py, D3.js skill DNA map, Piston integration|

\---

# 18\. TIMELINE

|Month|Focus|Deliverables|
|-|-|-|
|1|Foundation|Flask, PostgreSQL, auth, GitHub, virtual environment|
|2|Phase 1 data pipeline|Download datasets, pandas processing, FAISS index|
|3|Phase 1 career guidance|Quiz, conversation engine, career scoring, LLM, roadmap display|
|4|Phase 2 resume analyzer|PDF parsing, NLP, skill gap, salary, Adzuna, LLM feedback|
|5|Phase 3 Gamified DSA|D3.js map, node mastery, Piston, bandit system|
|6|Polish + integration + demo|Bug fixing, UI, connecting phases, report, presentation|

## Claude Code Time Estimates

Total estimated hours: 110 hours

|Hours per day|Total days|Calendar weeks|
|-|-|-|
|1 hr/day|110 days|\~16 weeks|
|2 hrs/day|55 days|\~8 weeks|
|3 hrs/day|37 days|\~5.5 weeks|
|4 hrs/day|28 days|\~4 weeks|
|6 hrs/day|19 days|\~3 weeks|
|8 hrs/day|14 days|2 weeks|

**Recommended: 3-4 hours/day = 4-5 weeks for demo-ready version**

**Priority order for tight timeline:**

1. Phase 1 + Deploy on Render → 2 weeks
2. Phase 2 → 1 week
3. Phase 3 (partial) → remaining time

\---

# 19\. UML DIAGRAMS

## Diagrams Completed

|Diagram|Status|Notes|
|-|-|-|
|Context Diagram (Level 0 DFD)|✅ Done|Student, Admin, LLM, Adzuna, YouTube as external entities|
|Level 1 DFD — Phase 1|✅ Done|Processes 1.1-1.4|
|Level 1 DFD — Phase 2|✅ Done|Processes 2.1-2.5|
|Level 1 DFD — Phase 3a Static Map|✅ Done|Processes 3.1-3.4|
|Level 1 DFD — Phase 3b Bandit Map|✅ Done|Processes 3.5-3.8|
|Use Case Diagram (main)|✅ Done|Student + Admin actors|
|Use Case — Career Guidance Module|✅ Done|4 use cases|
|Use Case — Resume Analysis Module|✅ Done|3 use cases|
|Use Case — Gamified DSA Module|✅ Done|2 use cases with extend|
|Activity Diagram|✅ Done|Three swimlane columns|
|Sequence Diagram — Phase 1|✅ Done|Loop + alt fragments|
|Sequence Diagram — Phase 2|✅ Done||
|Sequence Diagram — Phase 3|✅ Done|Loop + alt + weakness threshold|
|Class Diagram|✅ Done|6 classes, composition + association|
|Layered Architecture Diagram|✅ Done|5 layers|
|System Flowchart (B\&W)|✅ Done|Standard symbols, oval/rect/diamond|
|High-level LTR Block Diagram|✅ Done|Left to right flow|

## Diagram Rules Applied

* Oval = Start/End terminals
* Rectangle = Process/Action
* Diamond = Decision (Yes/No branches)
* Filled circle = Start node (activity diagram)
* Bullseye = End node (activity diagram)
* Solid arrow = synchronous message call
* Dashed arrow = return message
* Loop fragment = repeating sequence
* Alt fragment = conditional sequence
* Filled diamond = Composition relationship
* Open diamond = Association relationship

\---

# 20\. CLASS DIAGRAM

## Six Classes

**Student:**

```
+student\\\\\\\_id: int
+name: string
+current\\\\\\\_career\\\\\\\_path: string
+readiness\\\\\\\_score: float
--
+updateReadinessScore()
```

**CareerProfile:**

```
+profile\\\\\\\_id: int
+intake\\\\\\\_quiz\\\\\\\_data: json
+extracted\\\\\\\_skills: list
+gap\\\\\\\_analysis: json
+career\\\\\\\_path: string
--
+computeSkillGap()
```

**Roadmap:**

```
+roadmap\\\\\\\_id: int
+career\\\\\\\_path: string
+generated\\\\\\\_content: text
+resources: list
+timestamp: datetime
--
+showProgress()
```

**StaticMap:**

```
+node\\\\\\\_id: int
+topic\\\\\\\_name: string
+difficulty: string
+is\\\\\\\_locked: bool
+xp\\\\\\\_reward: int
+attempts\\\\\\\_count: int
--
+checkPrerequisites()
+validateCode()
```

**PerformanceMetric:**

```
+metric\\\\\\\_id: int
+time\\\\\\\_taken: float
+accuracy\\\\\\\_rate: float
+hint\\\\\\\_count: int
+attempts\\\\\\\_count: int
+weakness\\\\\\\_score: float
--
+calculateWeakness()
```

**AdaptiveMap:**

```
+bandit\\\\\\\_id: int
+context\\\\\\\_aware\\\\\\\_problem: text
+industry\\\\\\\_context: string
+spawn\\\\\\\_trigger: float
--
+validateCode()
+spawnBandit()
```

## Relationships

* Student ◆── CareerProfile (Composition — CareerProfile cannot exist without Student)
* Student ◇── StaticMap (Association — 1 to 1)
* CareerProfile ──→ Roadmap (1 to 1..\*)
* StaticMap ──→ PerformanceMetric (1 to 1..\*)
* PerformanceMetric ──→ AdaptiveMap (1 to 1..\*)

## What spawn\_trigger Stores

The weakness score value at the time of bandit creation. Stored for:

1. Explainability — show student WHY bandit appeared
2. Analytics — which nodes most commonly trigger bandits across all students

\---

# 21\. WHAT WE REMOVED \& WHY

|Removed|Reason|
|-|-|
|Web scraping (Naukri, Internshala)|ToS violation — both sites prohibit automated extraction|
|OpenAI API|No free tier|
|MySQL|PostgreSQL chosen — better free cloud hosting|
|Local LLM (Ollama)|4GB VRAM insufficient|
|Resume upload in Phase 1|Phase 1 = quiz + conversation only. Resume = Phase 2 only|
|Non-technical career paths|Pure business, farming, medicine without CS — breaks DSA coherence|
|Judge0 API|Replaced by self-hosted Piston — coordinator decision|
|LLM inside RAG box|LLM is External Service, not backend component|
|FAISS as external service|FAISS is pip install, runs locally — Backend component|
|Knowledge Base as separate box from DB|Lives in PostgreSQL + FAISS together|
|Web scraping label in architecture|Replaced with "Job Data / Resources"|
|Agile/Scrum|No user consultation — guide rejected it|
|Naukri/Internshala as data sources|ToS violation|
|"CS Students" in title|Too limiting — replaced with "Students Interested in the IT Sector"|
|"DSA" in title meaning Algorithms|Guide pointed out students focus on DS and Applications more than Algorithms|
|LangChain|Abstracts away RAG — no academic originality|
|React|Jinja2 server-side rendering sufficient|
|Piston as External Service|Piston is self-hosted — it's internal, part of Backend Layer|

\---

# 22\. KEY DECISIONS LOCKED

1. **No web scraping** — legal datasets only
2. **No training own LLM** — Gemini free tier with RAG constraints
3. **FAISS = local library** — NOT external service
4. **Piston = self-hosted** — internal Backend component — NOT Judge0
5. **YouTube Data API = Phase 1 only** — for roadmap resources, NOT Phase 3
6. **Static map first → complete weakness profile → Bandit map** — NOT partial data
7. **Bandits spawn on static map** — visible, personal, dramatic
8. **Non-traditional CS paths = yes** — purely non-technical = no
9. **Incremental Development Model** — NOT Agile
10. **PostgreSQL only** — NOT MySQL
11. **No LangChain** — RAG built manually
12. **No React** — Jinja2 server-side rendering
13. **Phase 1 entry = quiz + conversation only** — no resume upload in Phase 1
14. **Weakness score normalized to student's own performance** — slow learners NOT penalized

\---

# 23\. PPT MISTAKES FIXED

1. "Laearning Engine" → "Learning Engine" (spelling)
2. Dr. B.M. Vidyavathi listed twice on title slide — remove duplicate
3. Contents slide — "Future scope" missing number — should be 12
4. Slide 21 — "PostgreSQL / MySQL" → PostgreSQL ONLY
5. Slide 9 — "Spainer et al." → "Spanier et al."
6. Architecture diagram — Judge0 moved to External Services → now Piston (self-hosted) in Backend
7. Architecture diagram — LLM moved to External Services
8. Architecture diagram — RAG → LLM arrow must exist
9. Architecture diagram — confusing Database → External Services arrows removed
10. Slide 17 — Methodology slide shows only image, no text — add subtitle

\---

# 24\. INTERVIEW PREPARATION — LEVELUP DSA

## Why You Built It

*"India has over 1.5 million engineering graduates every year. Students at tier 2 and tier 3 colleges lack structured career guidance. They study randomly, don't know their skill gaps, and learn DSA without understanding why it matters for their career. This directly impacts SDG 4 (Quality Education) and SDG 8 (Decent Work). LevelUp DSA addresses both — personalized career guidance and structured, career-connected DSA learning."*

## Personal Angle

*"Being a student at BITM Ballari myself, I have seen this problem firsthand. I wanted to build something designed for the reality of tier 2 and tier 3 colleges — not generic platforms built for IIT students."*

## Three Personal Stories (Practice These)

Prepare before interview:

1. One bug you faced and fixed
2. One design decision you changed midway and why
3. One thing that surprised you during development

## Original Contributions (Say These Cold)

1. Conversation engine — quiz flow, signal extraction, career mapping
2. Career path scoring algorithm — weighted content-based filtering
3. Offline data pipeline — download, clean, process, embed
4. Prompt engineering architecture — constrained LLM generation
5. Skill DNA Map — D3.js DAG, prerequisite logic, mastery system
6. Weakness scoring formula — (accuracy × 0.5) + (time × 0.3) + (hints × 0.2)
7. Career-contextualised problem generation — DSA + career + industry context
8. Placement Readiness Score — original metric from three-phase data

## Scale Answer (Memorize This)

*"Currently using FAISS flat index — O(N) but instant for our scale. At larger scale: switch to HNSW index for approximate search, move Flask behind Gunicorn with multiple workers, add Redis caching for frequent queries, PostgreSQL connection pooling via PgBouncer."*

## Quick Fire Answers

**What is RAG?**
Retrieve relevant context from knowledge base, augment a prompt with that context, generate with LLM. Prevents hallucination by grounding output in verified data.

**What is FAISS?**
Facebook AI Similarity Search — converts text to vectors, finds most semantically similar vectors using cosine similarity. Meaning match, not keyword match.

**What is Skill DNA Map?**
Interactive DAG in D3.js — nodes are DSA topics, prerequisite locks via topological ordering, node brightness = mastery, career-critical nodes highlighted, problems contextualised to career path.

**What is Placement Readiness Score?**
Weighted formula — roadmap 25%, skill gap 35%, DSA 30%, streak 10%. Score above 70 = placement ready.

**Why not LangChain?**
Built RAG manually for academic originality. Can explain every component. LangChain would abstract everything.

**Why Flask over FastAPI?**
Server-side HTML rendering via Jinja2, session-based auth via Flask-Login. FastAPI is for REST APIs — doesn't match our architecture.

**Why not React?**
Jinja2 templates sufficient for server-side rendering. D3.js handles the only complex UI. React adds complexity without benefit.

**Development model?**
Incremental Development Model. Not Agile — no iterative user consultation.

**Why Piston over Judge0?**
Self-hosted — no API rate limits, no external dependency during demo, stronger academic story, free forever.

\---

# 25\. INTERVIEW PREPARATION — rPPG HEART RATE MONITOR

**Full name:** Real-Time Heart Rate Monitor using Remote PhotoPlethysmoGraphy

**Semester:** 5th semester mini project

**SDG:** SDG 3 — Good Health and Well-Being

**Core idea:** Contactless heart rate measurement using only a webcam. No wearable.

## How It Works

1. **Face Detection** — YOLOv8 (ONNX Runtime) detects face bounding box per frame
2. **ROI Extraction** — Forehead and under-eye region — high vascularity, thin skin
3. **Green Channel Signal** — Mean green intensity tracked across frames — oxyhemoglobin absorbs green light most strongly
4. **Signal Processing** — Smoothing pass + Butterworth bandpass filter 0.75-3 Hz (45-180 BPM)
5. **BPM Calculation** — FFT converts to frequency domain — dominant peak × 60 = BPM
6. **Live Dashboard** — Flask streams annotated video via multipart JPEG to browser

## Tech Stack

YOLOv8 (ONNX Runtime), OpenCV, NumPy, SciPy, Flask

## Your Contributions

1. ROI selection — forehead + under-eye coordinate extraction from bounding box
2. Signal processing pipeline — Butterworth filter parameters and smoothing
3. FFT-based BPM calculation — frequency domain peak detection
4. Flask multipart JPEG streaming — live annotated video to browser
5. Camera detection utility — auto detects DroidCam, falls back to webcam

## Why Each Choice

* YOLOv8 over Haar Cascade — better accuracy under varying lighting
* ONNX Runtime — hardware agnostic, no PyTorch needed, faster on CPU
* Butterworth over moving average — passes only 45-180 BPM, removes all noise outside range
* FFT over peak counting — robust to noise spikes, analyzes overall signal pattern
* Green channel — oxyhemoglobin absorbs green most strongly, highest SNR

## Challenges

* Fluorescent flicker at 50 Hz — ensured filter cutoffs don't overlap power line frequencies
* Head movement spikes — discard frames where bounding box shifts beyond threshold
* FFT warmup latency — 10 second warmup with loading indicator before displaying BPM

## Limitations (Be Honest)

* Accuracy degrades under poor lighting
* Less accurate with dark skin tones
* Facial hair covering ROI affects reading
* Error margin 5-10 BPM under non-ideal conditions
* Not a medical device

## Quick Fire

**What is rPPG?** Remote PhotoPlethysmoGraphy — measuring blood volume changes through skin color variations via camera without contact.

**Why green channel?** Oxyhemoglobin absorbs green light most strongly — highest correlation with cardiac blood flow.

**What is FFT?** Fast Fourier Transform — converts time domain signal to frequency domain to identify dominant frequencies.

**What is Butterworth filter?** Bandpass filter passing 0.75-3 Hz — isolates valid heart rate frequencies, removes all noise.

**What is YOLOv8?** You Only Look Once v8 — real-time object detection in single forward pass through neural network.

\---

# 26\. PYTHON FOUNDATIONS

## Four OOP Pillars

**Encapsulation** — hide data using private attributes, expose via methods
**Inheritance** — child class gets parent properties (extends)
**Polymorphism** — same method name, different behaviour per class
**Abstraction** — hide implementation, show only interface (ABC, @abstractmethod)

## Key Concepts

**List comprehension:** `\\\\\\\[x\\\\\\\*\\\\\\\*2 for x in range(10)]`

**Lambda:** `add = lambda x, y: x + y`

**Decorator:** Function wrapping another function — Flask @login\_required uses this

**Exception handling:** try / except / finally

**Generators:** yield — memory efficient, generates values one at a time

## Data Structures

* List — ordered, mutable, duplicates allowed
* Tuple — ordered, immutable
* Dictionary — key-value pairs, mutable
* Set — unordered, no duplicates

## Common Interview Questions

**List vs Tuple?** List is mutable, tuple is immutable. Tuple is faster.

**== vs is?** == checks value equality. is checks same object in memory.

**What is GIL?** Global Interpreter Lock — only one thread executes at a time. Use multiprocessing for CPU-bound tasks.

**Mutable vs immutable?** Mutable: list, dict, set. Immutable: int, float, string, tuple.

\---

# 27\. JAVA FOUNDATIONS

## OOP in Java

* `extends` = inheritance
* `implements` = interface
* `@Override` = method overriding
* `abstract` = abstract class / method
* `static` = class level, shared across all objects

## Access Modifiers

* `public` = everywhere
* `private` = only within class
* `protected` = class + subclasses
* `default` = same package only

## Common Interview Questions

**Abstract class vs Interface?**
Abstract class can have implementations and constructors. Interface only abstract methods (before Java 8). Class can implement multiple interfaces but extend only one abstract class.

**Overloading vs Overriding?**
Overloading = same name, different params, same class, compile time.
Overriding = child redefines parent method, runtime.

**== vs .equals()?**
== checks reference (same object in memory). .equals() checks value (same content).

**JVM vs JDK vs JRE?**
JDK = write and compile. JRE = run programs. JVM = executes bytecode, platform independence.

**Garbage collection?**
JVM automatically frees memory of unreferenced objects. No manual memory management.

\---

# 28\. AWS FOUNDATIONS

## Core Services

**EC2 — Elastic Compute Cloud**
Virtual server. Rent computing power. Pay per use.
Key: Instance types, AMI, Security Groups, Key Pairs.

**S3 — Simple Storage Service**
Object storage. Store any file. Like Google Drive for applications.
Key: Buckets, Objects, Access control, Static website hosting.

**RDS — Relational Database Service**
Managed database. AWS handles backups, updates, scaling.
Supports PostgreSQL, MySQL. Key: Multi-AZ, Read replicas, Automated backups.

**Lambda — Serverless**
Run code without servers. Pay per execution. Max 15 minutes.
Key: Trigger-based, no idle cost, great for small tasks.

**IAM — Identity and Access Management**
Controls who can access what.
Key: Users, Roles, Policies, Principle of least privilege.

**VPC — Virtual Private Cloud**
Your own private network inside AWS.
Key: Public subnet (web servers), Private subnet (databases), Internet Gateway.

## LevelUp DSA on AWS

```
User Browser → Route 53 → EC2 (Flask app)
                              ↓         ↓         ↓
                         RDS PostgreSQL  S3 Bucket  Lambda
                         (student data) (PDFs)    (async)
```

## Common Interview Questions

**S3 vs EBS?**
S3 = object storage, HTTP access, global. EBS = block storage, attached to EC2, like a hard drive.

**Auto scaling?**
Automatically increases/decreases EC2 instances based on traffic.

**CloudFront?**
CDN — caches static content at edge locations globally, faster load times.

**Security Groups vs NACLs?**
Security groups = stateful, instance level. NACLs = stateless, subnet level.

**Serverless?**
No server management. Lambda runs code without provisioning servers.

\---

# 29\. FUTURE SCOPE

1. Fine-tune open source LLM on India-specific career data using QLoRA
2. AI-powered mock interview simulator — verbal DSA questions with evaluation
3. Real-time job matching — notify students when they qualify for new roles
4. Leaderboard — college-wide and batch-wide competitive DSA practice
5. Mobile app — React Native for daily streak maintenance
6. Alumni mentorship integration — connect students with alumni in relevant roles
7. Placement prediction model — estimate placement probability from current score

\---

# 30\. PANEL REVIEW — PLACEMENT READINESS ASSESSMENT

## Context

Evaluated as a resume/portfolio project for campus placement at service-based firms (IBM, Cognizant, Accenture — 4-6 LPA range).

## Score: 7.5 / 10

## Five Critical Fixes Before Interview

**Fix 1 — Deploy Phase 1 on Render (CRITICAL)**
Get quiz → career scoring → roadmap generation working at a live URL. Eliminates AI-fabrication suspicion immediately.

**Fix 2 — Prepare three personal stories (CRITICAL)**
One bug fixed. One design decision changed midway. One surprise during development. Makes project sound genuinely built.

**Fix 3 — Soften Piston claim if not running**
If Piston not actually running locally say: "designed for self-hosted Piston running locally in Docker" — honest and still impressive.

**Fix 4 — Memorize the scale answer (HIGH)**
FAISS flat → HNSW, Flask → Gunicorn + multiple workers, add Redis caching, PostgreSQL connection pooling.

**Fix 5 — Know personal contributions cold (HIGH)**
Three things that are specifically yours — say in 30 seconds without thinking.

## Red Flags to Avoid

* Saying "we built" for everything — interviewer notices
* Cannot explain a specific bug you faced
* Cannot go one level deeper than prepared answers
* Claiming Piston self-hosting without being able to demonstrate
* Saying "I don't know" — say "I understand the concept and am building hands-on experience" instead

\---

# APPENDIX — LITERATURE SURVEY PAPERS

|#|Paper|Authors|Key Technique|Accuracy|Limitation|
|-|-|-|-|-|-|
|1|AI-Powered Career Matching|Jawhar et al. 2025|GPT-4o + structured questionnaire|92% precision|No RAG, hallucination risk, no roadmap|
|2|AI Career Guidance|El-Khalili et al. 2025|Random Forest + Big Five personality|87.3% accuracy|Personality only, ignores job market|
|3|Intelligent Resume Screening|Abhishek et al. 2025|Pyresparser + NLTK + Streamlit|85% accuracy|Recruiter-centric, no student guidance|
|4|Data-Driven Resume Analyzer|Sarumathi et al. 2025|NLP+ML + MongoDB + ReactJS|98% accuracy|Static NLP, no career path connection|
|5|Gamification in DSA|Spanier et al. 2021|3 genres + 2 new abstract genres|N/A|No career connection, underdeveloped field|

## Key Terms from Literature Survey

**GPT-4o** — OpenAI's omni model handling text, images, audio in single model

**Random Forest** — ensemble of decision trees, majority vote for classification

**SMOTE** — Synthetic Minority Oversampling Technique — generates synthetic samples for imbalanced datasets

**Big Five / OCEAN** — Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism personality model

**AUC-ROC** — Area Under ROC Curve — model discrimination ability. 1.0 = perfect, 0.5 = random

**Pyresparser** — Python library for automatic resume parsing and structured extraction

**NLTK** — Natural Language Toolkit — tokenization, stemming, NER, POS tagging

**Tokenization** — breaking text into individual word/sentence units

**GridSearchCV** — exhaustive hyperparameter search to find optimal model settings

**VAI** — Visualization of Abstract Ideas — DSA gamification genre making abstract concepts visual

**EE** — Enhanced Examination — gamifying quizzes with avatars, virtual currency, badges

**SCE** — Social and Collaborative Engagement — multiplayer, collaborative DSA learning

\---

*End of Master Document. Do not change any locked decisions without team + guide consensus.*

*Built with: Python, Flask, PostgreSQL, FAISS, sentence-transformers, spaCy, D3.js, Piston, Gemini API, Adzuna API, YouTube Data API*


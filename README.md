# LevelUp DSA

**Personalized Career Intelligence System with Gamified Data Structures and Problem Solving for Students Interested in the IT Sector**

LevelUp DSA is a Flask-based web platform that combines AI-driven career guidance, resume analysis, and a gamified, adaptive Data Structures & Algorithms learning system — built for students at tier 2/tier 3 engineering colleges who lack access to structured career mentorship.

## Problem It Solves

- No structured career direction — students study randomly without knowing what industry wants
- No clear skill gap awareness — students don't know what they're missing for their target role
- DSA learning disconnected from real career goals
- No unified measure of placement readiness

## Core Phases

| Phase | Description |
|-------|-------------|
| **Phase 1 — Career Guidance** | Quiz + conversational profiling → RAG-based career-path scoring → personalized roadmap generation (Gemini + FAISS) |
| **Phase 2 — Resume Analyzer** | PDF parsing (pdfplumber) + NER skill extraction (spaCy) → skill-gap analysis → live job matching (Adzuna) → LLM feedback |
| **Phase 3 — Gamified DSA** | Interactive Skill DNA Map (D3.js), self-hosted Piston code execution, XP/mastery/streak system, adaptive "bandit" problem spawning based on weakness scoring |

All three phases roll up into a single **Placement Readiness Score**.

## Tech Stack

- **Backend:** Flask, Flask-Login, bcrypt
- **Database:** PostgreSQL + SQLAlchemy
- **Frontend:** HTML / CSS / JS / Jinja2, D3.js
- **AI/ML:** FAISS, sentence-transformers, spaCy, Gemini 1.5 Flash
- **Code Execution:** Self-hosted Piston (Docker)
- **External APIs:** Adzuna (jobs), YouTube Data API (resources)
- **Deployment:** Render + Gunicorn

## Team

| Member | Role |
|--------|------|
| Joel (Lead) | Architecture, Backend Core, Auth, Database, Integration, DevOps |
| Karthikeya | Phase 1 — Career Guidance Frontend & Logic |
| Ganesh | Data Pipeline, RAG/FAISS & Phase 2 Resume Analyzer |
| Jayavardhana | Phase 3 — Gamified DSA (Skill DNA Map) |

**Guide:** Dr. B.M. Vidyavathi, Dept. of AIML, BITM Ballari

## Project Status

🚧 In active development — see `docs/` for architecture and the 50-day build plan.

## Setup

_Coming soon — setup instructions will be added once the Flask app skeleton is in place (Day 1–5)._

## License

MIT — see [LICENSE](LICENSE).

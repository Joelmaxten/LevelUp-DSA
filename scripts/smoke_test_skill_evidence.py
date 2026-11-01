"""
Smoke test for skill evidence: the pure rules (weights, thresholds, one-piece-counts-once, spelling, additions,
exclusions), the curated data/skill_map.json, GET /skills/evidence (401, per-user data, resume-only = unverified, a passed
step check verifies its skill, failed / unfinished attempts count for nothing, no writes, fixed error codes) and the
dashboard card (script loaded, no innerHTML, no direct fetch).

NO EXTERNAL CALLS. The route section uses Flask's test client and the development database and deletes every row it
created. The survey vocabulary is stubbed (the survey table is not needed to run this test); the matcher is the real
resume skill extractor (spaCy).

Usage:
    PYTHONPATH=. python scripts/smoke_test_skill_evidence.py

Exits non-zero if any check fails.
"""
import json
import random
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


T0 = datetime(2026, 10, 20, 9, 30)


def when(days=0):
    return T0 + timedelta(days=days)


# ---------------------------------------------------------------- part 1: pure rules
def test_rules():
    from app.pipeline import skill_evidence as se

    raw = json.loads(Path("data/skill_map.json").read_text(encoding="utf-8"))
    m = se.prepare_map(raw)

    def ev(source, unit, skill, day=0, title="t"):
        return se.evidence_item(source, unit, title, when(day), [skill])

    def row(items, skill, resume=()):
        out = se.summarize(items, list(resume), m)["skills"]
        return next((r for r in out if r["skill"] == skill), None)

    # --- the constant: weights and thresholds together
    check("RULES holds the weights (step 0.5, test-out 0.6, scenario 0.5, code 0.6) and the thresholds (tool 0.5, concept 0.7)",
          se.RULES == {"weights": {"step_check": 0.5, "test_out": 0.6, "scenario": 0.5, "code": 0.6},
                       "verified_at": {"tool": 0.5, "concept": 0.7}})

    # --- the three cases that define the concept rule
    two_scen = row([ev("scenario", "bke-1", "Caching"), ev("scenario", "bke-2", "Caching")], "Caching")
    check("two scenarios verify a concept (0.5 and 0.5 -> 0.75)",
          two_scen["status"] == "verified" and two_scen["confidence"] == 0.75)
    step_scen = row([ev("step_check", "s1", "Caching"), ev("scenario", "bke-2", "Caching")], "Caching")
    check("a step check plus a scenario verify a concept (0.75)",
          step_scen["status"] == "verified" and step_scen["confidence"] == 0.75)
    singles = {src: row([ev(src, "u", "Caching")], "Caching") for src in se.WEIGHTS}
    check("any single piece of evidence never verifies a concept (all four sources are in progress)",
          all(r["status"] == "in_progress" for r in singles.values())
          and [singles[s]["confidence"] for s in ("step_check", "test_out", "scenario", "code")] == [0.5, 0.6, 0.5, 0.6])
    check("no single weight reaches the concept threshold (so a concept always needs two pieces)",
          max(se.WEIGHTS.values()) < se.THRESHOLDS["concept"])
    check("a concept with one piece of evidence is 'in_progress' with that evidence listed",
          singles["step_check"]["status"] == "in_progress" and len(singles["step_check"]["evidence"]) == 1)
    exact = row([ev("step_check", "a", "Caching"), ev("step_check", "b", "Caching")], "Caching")
    check("exact arithmetic: 0.5 + 0.5 -> 0.75, test-out + code -> 0.84",
          exact["confidence"] == 0.75
          and row([ev("test_out", "a", "Caching"), ev("code", "b", "Caching")], "Caching")["confidence"] == 0.84)

    # --- tools
    tool_singles = {src: row([ev(src, "u", "Python")], "Python") for src in se.WEIGHTS}
    check("a tool is verified by one piece of evidence of any source (every weight >= 0.5)",
          all(r["status"] == "verified" and r["kind"] == "tool" for r in tool_singles.values()))
    check("kind: concepts from the map's fixed list, everything else is a tool",
          row([ev("step_check", "a", "Caching")], "Caching")["kind"] == "concept"
          and row([ev("step_check", "a", "SQL")], "SQL")["kind"] == "tool")

    # --- a piece of evidence counts once
    once = row([ev("step_check", "step-1", "Caching", 0), ev("test_out", "step-1", "Caching", 1),
                ev("step_check", "step-1", "Caching", 2)], "Caching")
    check("the same step passed by check, test-out and again counts once (the heaviest: test-out 0.6)",
          len(once["evidence"]) == 1 and once["evidence"][0]["source"] == "test_out" and once["confidence"] == 0.6)
    twice = row([ev("scenario", "bke-1", "Caching", 0), ev("scenario", "bke-1", "Caching", 5)], "Caching")
    check("the same scenario passed twice counts once", len(twice["evidence"]) == 1 and twice["status"] == "in_progress")
    check("a step and a scenario with the same id are different pieces",
          len(row([ev("step_check", "x", "Caching"), ev("scenario", "x", "Caching")], "Caching")["evidence"]) == 2)

    # --- resume = a claim
    out = se.summarize([], ["Rust", "SQL"], m)
    check("resume-only skills are 'unverified' with confidence 0 and no evidence",
          all(r["status"] == "unverified" and r["confidence"] == 0 and r["evidence"] == [] and r["on_resume"] for r in out["skills"])
          and out["counts"] == {"verified": 0, "in_progress": 0, "unverified": 2})
    both = row([ev("step_check", "a", "SQL")], "SQL", resume=["sql"])
    check("a resume claim adds no confidence: verified by the step check alone, on_resume true",
          both["status"] == "verified" and both["confidence"] == 0.5 and both["on_resume"])
    check("a resume claim with the wrong case still lines up with the evidence (one SQL row)",
          [r["skill"] for r in se.summarize([ev("step_check", "a", "SQL")], ["sql", "SQL"], m)["skills"]] == ["SQL"])

    # --- sorting and shape
    mixed = se.summarize([ev("code", "c1", "Python"), ev("step_check", "s1", "Caching"), ev("step_check", "s2", "Git"),
                          ev("step_check", "s3", "Git"), ev("scenario", "x", "SQL")], ["Zed"], m)
    confs = [r["confidence"] for r in mixed["skills"]]
    check("skills come back sorted by confidence, highest first; resume-only last",
          confs == sorted(confs, reverse=True) and mixed["skills"][-1]["skill"] == "Zed" and mixed["skills"][0]["skill"] == "Git")
    check("the result carries the rules so the card can explain them",
          mixed["rules"] == {"weights": se.RULES["weights"], "verified_at": se.RULES["verified_at"]})
    check("evidence dates are ISO strings with a Z (naive UTC); none stays None",
          singles["step_check"]["evidence"][0]["date"] == "2026-10-20T09:30:00Z"
          and se.summarize([se.evidence_item("code", "c", "t", None, ["Python"])], [], m)["skills"][0]["evidence"][0]["date"] is None)

    # --- skills for a step / scenario / problem: matcher + additions - exclusions, one spelling
    fake = lambda words: (lambda text: [w for w in words if w.lower() in text.lower()])
    check("matcher results are respelled: vocabulary spelling first, then the map's table",
          se.skills_for_step("x", "Intro", [], m, lambda t: ["react", "git"], {"react": "React"}) == ["Git", "React"])
    s = se.skills_for_step("backend-engineering", "Caching and Search Engines", ["Caching"], m, None)
    check("a step with a curated entry gets its added skills (key = career path slug + normalised title)", s == ["Caching"])
    check("step keys are normalised: case, outer spaces and repeated spaces do not matter",
          se.skills_for_step("backend-engineering", "  CACHING  and   Search Engines ", [], m, None) == ["Caching"])
    check("the same title on another career path gets nothing (the key includes the path)",
          se.skills_for_step("devops", "Caching and Search Engines", [], m, None) == [])
    check("ReAct does not give React",
          "React" not in se.skills_for_step("ai-engineering", "Tool Use and AI Agents", ["Function Calling", "ReAct"], m,
                                             lambda t: ["React"]))
    check("React Native does not give React, but a text that names React itself keeps it",
          "React" not in se.skills_for_step("mobile-app-development", "React Native Core Components", ["Props"], m, lambda t: ["React"])
          and "React" in se.skills_for_step("x", "React Native and React", [], m, lambda t: ["React"]))
    check("SQL injection does not give SQL, plain SQL does",
          "SQL" not in se.skills_for_scenario("zzz", ["SQL injection", "Web attack defences"], m, lambda t: ["SQL"])
          and "SQL" in se.skills_for_scenario("zzz", ["SQL joins"], m, lambda t: ["SQL"]))
    check("alternatives rule: a tool that is only one option in a step's list is removed (backend 3: MySQL / PostgreSQL / MariaDB)",
          se.skills_for_step("backend-engineering", "Relational Databases, ORMs and Migrations", ["PostgreSQL", "MySQL"], m,
                             lambda t: ["PostgreSQL", "MySQL"]) == ["Databases"])
    check("wrong matches from real survey names are removed: Objective-C / MVVM-C is not C, the word 'make' is not Make, 'Snowflake schema' is not Snowflake",
          "C" not in se.skills_for_step("mobile-app-development", "Swift Memory Management", ["Objective-C", "MVVM-C"], m, lambda t: ["C", "Swift"])
          and "C" in se.skills_for_step("x", "Intro to C", ["Objective-C", "C"], m, lambda t: ["C"])
          and "Make" not in se.skills_for_step("ui-ux-design", "Designing for Action", ["Make it Clear"], m, lambda t: ["Make"])
          and "Make" in se.skills_for_step("x", "Build with Makefile", [], m, lambda t: ["Make"])
          and "Snowflake" not in se.skills_for_step("data-analytics", "Data Modelling", ["Star vs Snowflake Schema"], m, lambda t: ["Snowflake"])
          and "Snowflake" in se.skills_for_step("x", "Snowflake warehouse", [], m, lambda t: ["Snowflake"]))
    check("alternatives rule on real survey names: package managers listed as options are removed (frontend 52), hosting platforms named in the title are kept (frontend 59)",
          se.skills_for_step("frontend-development", "Package Managers and Module Bundlers", ["npm", "pnpm", "Yarn", "Bun"], m,
                             lambda t: ["npm", "pnpm", "Yarn", "Bun"]) == []
          and se.skills_for_step("frontend-development", "Hosting Platforms: Vercel, Netlify and Cloudflare", ["Vercel", "Netlify"], m,
                                 lambda t: ["Vercel", "Netlify", "Cloudflare"]) == ["Cloudflare", "Netlify", "Vercel"])
    check("the survey vocabulary's own spelling wins ('DynamoDB' in a title -> 'Dynamodb'), as the resume matcher spells it",
          (lambda out: "Dynamodb" in out and "DynamoDB" not in out)(
              se.skills_for_step("cloud-engineering", "Managed Databases: RDS, DynamoDB and ElastiCache", [], m,
                                 lambda t: ["DynamoDB"], {"dynamodb": "Dynamodb"})))
    check("curated tool additions that need no matcher: 'Linux Shell' step gets Bash/Shell, the Azure step gets Microsoft Azure",
          {"Linux", "Bash/Shell (all shells)"} <= set(se.skills_for_step("devops", "Linux Shell, Files and Text Processing", [], m, None))
          and "Microsoft Azure" in se.skills_for_step("data-engineering", "Cloud Data Services on AWS, Azure and GCP", [], m, None))
    check("a scenario's curated skills are added and nothing else is invented",
          se.skills_for_scenario("bke-2", ["Caching"], m, None) == ["API design", "Caching", "System design"]
          and se.skills_for_scenario("no-such-scenario", ["Caching"], m, None) == [])
    check("a solved code problem gives its own skills plus the DSA concept for its ds_topic",
          se.skills_for_code(["Python"], "hash_map", m) == ["Data structures and algorithms", "Python"]
          and se.skills_for_code(["SQL"], "unknown_topic", m) == ["SQL"])

    # --- the map file itself
    check("data/skill_map.json is valid, has exactly 30 concepts and every concept is spelled once",
          len(m["concepts"]) == 30 and "Security fundamentals" in m["concepts"] and "Data structures and algorithms" in m["concepts"])
    base = {}
    for f in sorted(Path("data/base_roadmaps").glob("*.json")):
        for ph in json.loads(f.read_text(encoding="utf-8"))["roadmap"]["phases"]:
            for st in ph["steps"]:
                base[se.step_key(f.stem, st["title"])] = st
    check("every curated step key in the map is a real base-roadmap step (none stale, none misspelt)",
          set(raw["steps"]) <= set(base) and len(raw["steps"]) > 400)
    scen_ids = {s["id"] for f in Path("data/scenarios").glob("*.json") for s in json.loads(f.read_text(encoding="utf-8"))["scenarios"]}
    check("every one of the 75 scenarios is mapped and no mapped id is unknown",
          set(raw["scenarios"]) == scen_ids and len(scen_ids) == 75)
    step_rules = [r["step"] for r in raw["exclude"] if "step" in r]
    check("every per-step exclusion points at a real step", set(step_rules) <= set(base))
    used = {s for v in list(raw["steps"].values()) + list(raw["scenarios"].values()) + list(raw["code_topics"].values()) for s in v}
    check("no skill is spelled two ways in the map (case-insensitive duplicates)",
          len({u.lower() for u in used}) == len(used))
    check("fed-2 maps to JavaScript and React; backend step 8 has no Networking",
          set(raw["scenarios"]["fed-2"]) == {"JavaScript", "React"}
          and raw["steps"][se.step_key("backend-engineering", "Web Security Essentials")] == ["Application security"])

    # --- the loader rejects a bad file
    def rejects(mutate):
        bad = json.loads(json.dumps(raw))
        mutate(bad)
        try:
            se.prepare_map(bad)
            return False
        except ValueError:
            return True
    check("the map loader rejects 31 concepts, a broken regex, a malformed list and a missing section",
          rejects(lambda b: b["concepts"].append("One too many"))
          and rejects(lambda b: b["exclude"].append({"skill": "X", "when": "(", "reason": "bad"}))
          and rejects(lambda b: b["steps"].update({"a|b": "Python"}))
          and rejects(lambda b: b.pop("canonical")))

    # --- the shared reach logic (what can be verified at all)
    from app.pipeline import skill_reach as sr
    check("reach: names are compared case-insensitively and respelled the way the required list spells them",
          sr.reachable(["Python", "SQL"], {"python"}) == {"Python"})
    check("reach: a composite needs every part (HTML alone does not verify HTML/CSS)",
          sr.reachable(["HTML/CSS"], {"HTML"}) == set() and sr.reachable(["HTML/CSS"], {"HTML", "CSS"}) == {"HTML/CSS"})
    check("reach: a skill that implies another counts (MySQL verifies the SQL requirement) but SQL does NOT verify a database "
          "requirement: a skill is verified only when that skill itself is verified",
          sr.reachable(["SQL"], {"MySQL"}) == {"SQL"}
          and sr.reachable(["MySQL", "PostgreSQL", "SQLite", "Microsoft SQL Server"], {"SQL"}) == set())
    check("reach: the required skills that nothing can verify", sr.unreachable_everywhere(["Python", "Rust"], {"Python"}) == {"Rust"})
    fake_roadmaps = {"Backend Engineering": {"roadmap": {"phases": [{"steps": [
        {"title": "SQL Queries: Selecting, Joining and Grouping", "subtopics": []}, {"title": "Caching and Search Engines", "subtopics": []}]}]}}}
    fake_scenarios = {"Backend Engineering": {"scenarios": [{"id": "bke-2", "tests_topics": ["Caching"], "questions": [],
                                                              "code_pool": [{"id": "bke-2-c1", "skills": ["Python"], "ds_topic": "hash_map"}]}]}}
    per = sr.tools_by_source(m, None, None, fake_roadmaps, fake_scenarios, ["Backend Engineering", "DevOps"],
                             lambda path: path.lower().replace(" ", "-"))
    check("reach: tools_by_source counts only TOOL skills (concepts like Caching are left out), per source and per path",
          per["steps"]["Backend Engineering"] == {"SQL"} and per["code problems"]["Backend Engineering"] == {"Python"}
          and per["scenarios"]["Backend Engineering"] == set() and per["steps"]["DevOps"] == set()
          and sr.all_tools(per) == {"SQL", "Python"})
    real_roadmaps = {path: json.loads(f.read_text(encoding="utf-8")) for f in sorted(Path("data/base_roadmaps").glob("*.json"))
                     for path in [json.loads(f.read_text(encoding="utf-8"))["metadata"]["career_path"]]}
    real_scenarios = {json.loads(f.read_text(encoding="utf-8"))["path"]: json.loads(f.read_text(encoding="utf-8"))
                      for f in sorted(Path("data/scenarios").glob("*.json"))}
    real = sr.tools_by_source(m, None, None, real_roadmaps, real_scenarios, sorted(real_roadmaps), lambda path: re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-"))
    known_gaps = {"MySQL", "Java", "MongoDB", "C", "PowerShell", "Dart"}
    check("known content gap (see the docs): MySQL, Java, MongoDB, C, PowerShell and Dart cannot be verified by any curated step, scenario "
          "or code problem. If this check starts failing, content was added: update the docs", not (known_gaps & sr.all_tools(real)))
    check("the readiness-reach report and the dashboard use the same reach code (scripts/readiness_reach_report.py imports skill_reach)",
          "skill_reach" in Path("scripts/readiness_reach_report.py").read_text(encoding="utf-8")
          and "skill_reach" in Path("app/routes/skills.py").read_text(encoding="utf-8"))

    # --- purity
    src = Path("app/pipeline/skill_evidence.py").read_text(encoding="utf-8")
    check("skill_evidence.py is pure: no Flask, database, spaCy or network imports",
          not re.search(r"^\s*(from|import)\s+(flask|sqlalchemy|app\.models|app import|spacy|requests)", src, re.M))


# ---------------------------------------------------------------- part 2: routes
def test_routes():
    from app import create_app, db
    from app.models import (GeneratedRoadmap, Resume, RoadmapProgress, ScenarioAttempt, StepCheckAttempt, User)
    from app.routes import skills as route
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    user_ids = []

    def login(tag):
        client = app.test_client()
        email = f"skillev{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Skill Test", "email": email, "password": "SmokeTest#123"})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": "SmokeTest#123"})
        return client, user_ids[-1]

    def base_roadmap(slug):
        doc = json.loads(Path(f"data/base_roadmaps/{slug}.json").read_text(encoding="utf-8"))
        steps = doc["roadmap"]
        steps["base"] = {"source": "base_roadmap"}
        return steps

    def step_index(roadmap, title):
        for ph in roadmap["phases"]:
            for st in ph["steps"]:
                if st["title"] == title:
                    return st["global_step_index"]
        raise KeyError(title)

    def passed_check(uid, roadmap_id, idx, mode="check", passed=True, submitted=True, day=0):
        return StepCheckAttempt(user_id=uid, roadmap_id=roadmap_id, step_index=idx, mode=mode, questions=[], total=4,
                                pass_mark=3, score=4 if passed else 1, passed=passed,
                                submitted_at=when(day) if submitted else None)

    def scenario_attempt(uid, sid, path, passed, answers=None, day=0, submitted=True):
        return ScenarioAttempt(user_id=uid, path=path, scenario_id=sid, answers=answers or {}, score=40 if passed else 10,
                               max_score=50, passed=passed, submitted_at=when(day) if submitted else None)

    def snapshot():
        with app.app_context():
            return {m.__tablename__: (m.query.count(), db.session.query(db.func.max(m.id)).scalar())
                    for m in (User, GeneratedRoadmap, StepCheckAttempt, ScenarioAttempt, Resume, RoadmapProgress)}

    def by_skill(body):
        return {r["skill"]: r for r in body["skills"]}

    real_vocab = dict(route._vocab_cache)
    try:
        route._vocab_cache["vocab"] = frozenset()      # first: no survey vocabulary at all, only the curated map
        anon = app.test_client()
        check("GET /skills/evidence logged out -> 401", anon.get("/skills/evidence").status_code == 401)

        alice, aid = login("a")
        bob, bid = login("b")
        empty = alice.get("/skills/evidence")
        check("a new account has no skills and the rules are returned",
              empty.status_code == 200 and empty.get_json()["skills"] == []
              and empty.get_json()["counts"] == {"verified": 0, "in_progress": 0, "unverified": 0}
              and empty.get_json()["rules"]["verified_at"] == {"tool": 0.5, "concept": 0.7})

        backend, ai = base_roadmap("backend-engineering"), base_roadmap("ai-engineering")
        with app.app_context():
            rb, rai = (GeneratedRoadmap(user_id=aid, career_path="Backend Engineering", steps=backend),
                       GeneratedRoadmap(user_id=aid, career_path="AI Engineering", steps=ai))
            db.session.add_all([rb, rai])
            db.session.flush()
            caching = step_index(backend, "Caching and Search Engines")
            sql_step = step_index(backend, "SQL Queries: Selecting, Joining and Grouping")
            python_step = step_index(ai, "Python Fundamentals")
            agents = step_index(ai, "Tool Use and AI Agents")
            bob_attempt_on_alices_roadmap = passed_check(bid, rb.id, caching)
            db.session.add_all([
                passed_check(aid, rb.id, caching, day=0),                          # Caching 0.5 (concept, one piece)
                passed_check(aid, rb.id, sql_step, mode="test_out", day=1),        # SQL 0.6 verified; Databases 0.6 in progress
                passed_check(aid, rb.id, step_index(backend, "NoSQL Databases"), passed=False),   # failed: counts for nothing
                passed_check(aid, rb.id, step_index(backend, "Designing APIs: REST, GraphQL and gRPC"), submitted=False, passed=False),
                passed_check(aid, rai.id, python_step, day=2),                     # Python via the matcher (stubbed vocabulary later)
                passed_check(aid, rai.id, agents, day=2),                          # ReAct step: must not give React
                bob_attempt_on_alices_roadmap,                                     # Bob's row on Alice's roadmap: ignored
                Resume(user_id=aid, file_path="x.pdf", extracted_skills=["SQL", "Rust", "ReAct"]),
                Resume(user_id=bid, file_path="y.pdf", extracted_skills=["Go"]),
                scenario_attempt(aid, "bke-1", "Backend Engineering", False, day=3),   # failed scenario: nothing
                scenario_attempt(aid, "bke-2", "Backend Engineering", True, day=4,
                                 answers={"bke-2-c1": {"passed": True}}),             # scenario passed + code problem solved
                scenario_attempt(aid, "bke-3", "Backend Engineering", True, day=5, submitted=False),   # unfinished: nothing
            ])
            db.session.commit()

        before = snapshot()
        r1 = alice.get("/skills/evidence")
        body = r1.get_json()
        skills = by_skill(body)

        check("Alice: 200 and skills sorted by confidence", r1.status_code == 200
              and [s["confidence"] for s in body["skills"]] == sorted([s["confidence"] for s in body["skills"]], reverse=True))
        check("a passed step check makes its tool skill verified (SQL by test-out: 0.6, with why)",
              skills["SQL"]["status"] == "verified" and skills["SQL"]["confidence"] == 0.6 and skills["SQL"]["kind"] == "tool"
              and skills["SQL"]["evidence"][0]["source"] == "test_out"
              and skills["SQL"]["evidence"][0]["title"] == "SQL Queries: Selecting, Joining and Grouping"
              and skills["SQL"]["evidence"][0]["date"] == "2026-10-21T09:30:00Z")
        check("the SQL test-out also shows that SQL is on the resume",
              skills["SQL"]["on_resume"] is True)
        check("Caching: step check (0.5) + the passed scenario bke-2 (0.5) = 0.75, verified, both pieces listed",
              skills["Caching"]["status"] == "verified" and skills["Caching"]["confidence"] == 0.75
              and {e["source"] for e in skills["Caching"]["evidence"]} == {"step_check", "scenario"})
        check("a concept with one piece of evidence is in progress (Databases: only the SQL test-out so far)",
              skills["Databases"]["status"] == "in_progress" and skills["Databases"]["kind"] == "concept"
              and len(skills["Databases"]["evidence"]) == 1)
        check("a solved code problem verifies its tool (Python 0.6) and starts the DSA concept (in progress)",
              skills["Python"]["status"] == "verified" and "code" in {e["source"] for e in skills["Python"]["evidence"]}
              and skills["Data structures and algorithms"]["status"] == "in_progress")
        check("a resume-only skill is unverified: Rust has confidence 0, no evidence",
              skills["Rust"]["status"] == "unverified" and skills["Rust"]["confidence"] == 0
              and skills["Rust"]["evidence"] == [] and skills["Rust"]["on_resume"] is True)
        check("failed, unfinished and unpassed attempts give no evidence (NoSQL, APIs, bke-1, bke-3)",
              "API design" in skills and skills["API design"]["evidence"][0]["source"] == "scenario"
              and len(skills["API design"]["evidence"]) == 1
              and all(e["title"] != "NoSQL Databases" for s in body["skills"] for e in s["evidence"])
              and "Concurrency" not in skills)
        check("counts add up to the number of skills",
              sum(body["counts"].values()) == len(body["skills"]))

        # the matcher, with a stubbed vocabulary: Python from the title "Python Fundamentals", React must not come from ReAct
        route._vocab_cache["vocab"] = frozenset({"Python", "SQL", "React"})
        body2 = alice.get("/skills/evidence").get_json()
        skills2 = by_skill(body2)
        check("with a vocabulary the real resume matcher finds Python from the step title 'Python Fundamentals'",
              any(e["title"] == "Python Fundamentals" for e in skills2["Python"]["evidence"]))
        check("the ReAct step does not make React verified, and the resume's 'ReAct' stays a claim only",
              "React" not in skills2 or skills2["React"]["status"] != "verified")
        route._vocab_cache["vocab"] = frozenset()

        # per-user isolation
        rb_body = bob.get("/skills/evidence").get_json()
        check("Bob sees only his own resume skill (Go, unverified), none of Alice's evidence or resume",
              [(s["skill"], s["status"]) for s in rb_body["skills"]] == [("Go", "unverified")])
        check("a step-check row of Bob's that points at Alice's roadmap counts for nothing",
              all(s["status"] != "verified" for s in rb_body["skills"]))
        check("Alice does not see Bob's resume skill", "Go" not in by_skill(alice.get("/skills/evidence").get_json()))

        # no writes
        for _ in range(3):
            alice.get("/skills/evidence")
            bob.get("/skills/evidence")
        check("GET writes nothing: row counts and highest ids of every table are unchanged", snapshot() == before)
        check("only GET is routed (POST -> 405)", alice.post("/skills/evidence", json={}).status_code == 405)

        # fixed error codes
        real = route.evidence_for
        try:
            def boom(_uid):
                raise RuntimeError("SECRET-internal-detail")
            route.evidence_for = boom
            er = alice.get("/skills/evidence")
            check("a failure -> 500 with a fixed code and no exception text",
                  er.status_code == 500 and er.get_json() == {"error": "skills_unavailable"}
                  and "SECRET" not in er.get_data(as_text=True))
        finally:
            route.evidence_for = real
        real_path = route.SKILL_MAP_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bad = Path(tmp) / "skill_map.json"
                bad.write_text("{not json", encoding="utf-8")
                route.SKILL_MAP_PATH = bad
                er = alice.get("/skills/evidence")
                check("a broken skill_map.json -> 500 with a fixed code",
                      er.status_code == 500 and er.get_json() == {"error": "skills_unavailable"})
        finally:
            route.SKILL_MAP_PATH = real_path
        check("the route works again after the map is restored", alice.get("/skills/evidence").status_code == 200)

        # --- where can a skill be proved (the resume page's "Verified / Not yet verified" labels)
        route._vocab_cache["vocab"] = frozenset({"Python", "SQL", "Docker", "Rust", "Git"})        # stand-in vocabulary
        wanted = [("skill", n) for n in ("SQL", "Python", "Docker", "Rust", "HTML/CSS")]
        check("GET /skills/coverage logged out -> 401", anon.get("/skills/coverage?skill=SQL").status_code == 401)
        check("GET /skills/coverage without a skill -> 400 with a fixed code",
              alice.get("/skills/coverage").status_code == 400 and alice.get("/skills/coverage").get_json() == {"error": "no_skills"})
        before_cov = snapshot()
        cov_resp = alice.get("/skills/coverage", query_string=wanted)
        cov = cov_resp.get_json()["skills"]
        check("coverage: verified skills are marked verified (SQL by test-out, Python by a solved code problem)",
              cov_resp.status_code == 200 and cov["SQL"]["verified"] is True and cov["Python"]["verified"] is True)
        check("coverage: a skill only claimed is 'not yet verified' and names where to prove it: Docker -> a step of another path's "
              "roadmap (named with the path) and no scenario",
              cov["Docker"]["verified"] is False and cov["Docker"]["no_content"] is False
              and any(w["type"] == "step" and w["in"] for w in cov["Docker"]["where"]))
        check("coverage: the step named for a skill covered only elsewhere is one whose title names it (Docker -> a Docker step, "
              "not an unrelated step that merely mentions it)",
              all("docker" in w["title"].lower() for w in cov["Docker"]["where"] if w["type"] == "step" and w["in"]))
        check("coverage: a skill the student's own roadmap teaches links to that step (Python Fundamentals, no 'in' path)",
              any(w["type"] == "step" and w["title"] == "Python Fundamentals" and w["in"] is None for w in cov["Python"]["where"]))
        check("coverage: scenarios that cover a skill are listed (SQL) with the scenarios page as the link",
              any(w["type"] == "scenario" and w["url"] == "/scenarios" for w in cov["SQL"]["where"]))
        check("coverage: nothing on the platform covers Rust -> no_content true and no places listed",
              cov["Rust"]["no_content"] is True and cov["Rust"]["where"] == [] and cov["Rust"]["verified"] is False)
        check("coverage: a composite is covered by its parts (HTML/CSS -> HTML and CSS steps), not verified without both parts",
              cov["HTML/CSS"]["verified"] is False and cov["HTML/CSS"]["no_content"] is False and cov["HTML/CSS"]["where"])
        bob_cov = bob.get("/skills/coverage", query_string=[("skill", "SQL"), ("skill", "Python")]).get_json()["skills"]
        check("coverage is per student: Bob has verified nothing", not bob_cov["SQL"]["verified"] and not bob_cov["Python"]["verified"])
        check("coverage writes nothing", snapshot() == before_cov)
        real_ev = route.evidence_for
        try:
            route.evidence_for = boom_ev = lambda _uid: (_ for _ in ()).throw(RuntimeError("SECRET-detail"))
            er = alice.get("/skills/coverage", query_string=[("skill", "SQL")])
            check("coverage: a failure -> 500 with a fixed code and no exception text",
                  er.status_code == 500 and er.get_json() == {"error": "skills_unavailable"} and "SECRET" not in er.get_data(as_text=True))
        finally:
            route.evidence_for = real_ev

        # --- job search: the top verified TOOL skills (at most two) go into the search
        from unittest.mock import patch
        from app.routes import resume as resume_route
        asked = []

        def fake_listings(career_path, skills=()):
            asked.append(list(skills))
            return {"listings": [], "unavailable": False, "sources": ["Adzuna"], "matched_on": list(skills), "search_links": []}
        with patch.object(resume_route, "get_live_job_listings", fake_listings):
            la = alice.get("/resume/listings", query_string={"career_path": "Backend Engineering"})
            lb = bob.get("/resume/listings", query_string={"career_path": "Backend Engineering"})
            route.evidence_for = lambda _uid: (_ for _ in ()).throw(RuntimeError("SECRET-detail"))
            try:
                lf = alice.get("/resume/listings", query_string={"career_path": "Backend Engineering"})
            finally:
                route.evidence_for = real_ev
        check("listings: Alice's top verified TOOL skills are passed to the search (Python, SQL; the verified concept Caching is not)",
              asked[0] == ["Python", "SQL"] and la.get_json()["matched_on"] == ["Python", "SQL"])
        check("listings: a student with nothing verified searches without skills", asked[1] == [] and lb.get_json()["matched_on"] == [])
        check("listings: if the verified skills cannot be gathered the search is plain and the page still answers 200",
              asked[2] == [] and lf.status_code == 200 and "SECRET" not in lf.get_data(as_text=True))
        js_results = Path("app/static/js/results.js").read_text(encoding="utf-8")
        check("resume page script: matched skills show 'Verified' / 'Not yet verified' with 'Prove it' links, the jobs box shows 'Matched on:'; no innerHTML",
              "matchedSkillsWithProof" in js_results and "/skills/coverage" in js_results and '"Not yet verified"' in js_results
              and "Prove it" in js_results and "No LevelUp step or scenario covers this yet." in js_results
              and "Matched on:" in js_results and not re.search(r"\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML|document\.write", js_results))

        # the dashboard card
        html = alice.get("/dashboard").get_data(as_text=True)
        check("/dashboard loads skills.js", "js/skills.js" in html)
        js = Path("app/static/js/skills.js").read_text(encoding="utf-8")
        check("skills.js builds everything with el()/textContent (no innerHTML, no insertAdjacentHTML, no document.write)",
              "innerHTML" not in js and "insertAdjacentHTML" not in js and "document.write" not in js
              and "function skillsCard" in js)
        check("skills.js makes no request of its own (the dashboard fetches through getJson) and sets no inline styles",
              "fetch(" not in js and "XMLHttpRequest" not in js and ".style" not in js)
        dash = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        check("the dashboard fetches /skills/evidence and still renders without it",
              'getJson("/skills/evidence")' in dash and "skills.ok ? skills.data : null" in dash
              and "skills ? skillsCard(skills)" in dash)
        css = Path("app/static/css/style.css").read_text(encoding="utf-8")
        check("the card styles live in style.css and use the existing tokens",
              ".skill-row" in css and ".skill-why" in css
              and not re.search(r"\.skill-[a-z-]+\s*\{[^}]*#[0-9A-Fa-f]{3,6}", css))
        check("the card shows a concept with one piece as 'In progress' and resume-only skills under 'On your resume, not yet verified'",
              "In progress" in js and "On your resume, not yet verified" in js and "Your skills" in js)
    finally:
        route._vocab_cache.clear()
        route._vocab_cache.update(real_vocab)
        with app.app_context():
            for uid in user_ids:
                StepCheckAttempt.query.filter_by(user_id=uid).delete()
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                Resume.query.filter_by(user_id=uid).delete()
                GeneratedRoadmap.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
            db.session.commit()


SECTIONS = [test_rules, test_routes]


def main():
    for section in SECTIONS:
        section()
    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for d in failed:
        print(f"FAILED: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

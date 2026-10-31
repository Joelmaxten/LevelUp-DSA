"""
Smoke test for verified progression: roadmap steps completed by passing a check built from the step's own knowledge-base
passages (app/pipeline/step_checks.py, app/routes/step_checks.py).

Part 1 is pure (question building on all 15 base roadmaps, the model-question verifier, picking, grading, the lock /
cooldown / review rules). Part 2 drives the real routes with the test client on a real AI Engineering roadmap. No model
is called: the optional model-question path is checked with a stub. Deletes every row it created.

Usage:  PYTHONPATH=. python scripts/smoke_test_step_checks.py
"""
import glob
import json
import pickle
import random
import re
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv(".env")

from app import create_app, db
from app.models import GeneratedRoadmap, RoadmapProgress, StepCheckAttempt, StepCheckItem, StepReview, User
from app.pipeline import step_checks as sc
from app.security import reset_rate_limits

PW = "StepCheck#123"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


# ------------------------------------------------------------------------------------------------------- part 1: pure

def pure_checks(meta):
    check("topic_name strips 'What is a'", sc.topic_name("What is a Prompt?") == "Prompt")
    check("topic_name keeps a plain title", sc.topic_name("Tool Invocation") == "Tool Invocation")
    check("singular forms are masked too", sc.mask_title("In programming, a function is reusable.", "Functions") == "In programming, a ____ is reusable."
          and sc.singular("Libraries") == "Library" and sc.singular("Process") == "Process")
    m = sc.mask_title("Acting, also called tool invocation, is the step.", "Acting / Tool Invocation")
    check("mask_title blanks every alias, any case", m == "____, also called ____, is the step.")
    check("mask_title collapses a multi-part name to one blank",
          sc.mask_title("Chain of Thought (CoT) Prompting improves reasoning.", "Chain of Thought (CoT) Prompting")
          == "____ improves reasoning.")
    check("mask_title returns None when the name is absent", sc.mask_title("Nothing here.", "Kubernetes") is None)
    step = {"title": "Python Fundamentals", "topic_refs": ["b", "a"]}
    check("step_key ignores topic_refs order", sc.step_key("X", step) == sc.step_key("X", {"title": "python fundamentals ", "topic_refs": ["a", "b"]}))
    check("step_key differs by path", sc.step_key("X", step) != sc.step_key("Y", step))

    total = bad_shape = name_leak = evidence_missing = prefix_giveaway = it_are = 0
    min_items, deterministic = 99, True
    for f in sorted(glob.glob("data/base_roadmaps/*.json")):
        d = json.load(open(f))
        path = d["metadata"]["career_path"]
        look = sc.chunk_lookup(meta, path)
        flat = sc.flat_steps(d["roadmap"])
        all_src = [s for _, st in flat for s in sc.step_sources(st, look)]
        for _, st in flat:
            src = sc.step_sources(st, look)
            items = sc.build_items(src, all_src, sc.step_key(path, st))
            if sc.build_items(src, all_src, sc.step_key(path, st)) != items:
                deterministic = False
            min_items = min(min_items, len(items))
            texts = {s["node_id"]: s["text"] for s in src}
            for it in items:
                total += 1
                ids = [o["id"] for o in it["options"]]
                it_are += sum(o["text"].startswith("It are ") for o in it["options"])
                if len(ids) != 4 or len({o["text"].lower() for o in it["options"]}) != 4 or it["correct"] not in ids:
                    bad_shape += 1
                if it["evidence"] not in texts.get(it["source_node"], ""):
                    evidence_missing += 1
                name = sc.topic_name(it["source_title"]).lower()
                right = next(o["text"] for o in it["options"] if o["id"] == it["correct"])
                if it["kind"] == "term" and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", it["prompt"].split("\n", 1)[1].lower()):
                    name_leak += 1
                if it["kind"] == "definition":
                    if any(re.search(r"(?<!\w)" + re.escape(al.lower()) + r"(?!\w)", right.lower()) for al in sc.title_aliases(it["source_title"])):
                        name_leak += 1
                    wrong = [o["text"] for o in it["options"] if o["id"] != it["correct"]]
                    if all(sc._pronoun_open(right) != sc._pronoun_open(w) for w in wrong):
                        prefix_giveaway += 1
    check(f"all 15 paths: every step has enough questions for a 6-question test-out (min {min_items}, {total} in all)", min_items >= 6)
    check("every question has 4 distinct options and its answer among them", bad_shape == 0)
    check("every question's evidence sentence is in its source passage", evidence_missing == 0)
    check("no question names the topic it asks about", name_leak == 0)
    check("no definition question is given away by how the options open", prefix_giveaway == 0)
    check("no option reads 'It are' (pronoun agrees with the verb)", it_are == 0)
    check("question building is deterministic", deterministic)

    src = {"node_id": "n1", "title": "Embeddings",
           "text": "Embeddings turn text into vectors of numbers. Texts with similar meaning get vectors that lie close together."}
    by_title = {sc._norm("Embeddings"): src}
    good = {"source": "Embeddings", "question": "What do texts with similar meaning get?",
            "options": ["Vectors that lie close together", "Longer token counts", "Random labels", "Fewer stopwords"],
            "answer_index": 0, "evidence": "Texts with similar meaning get vectors that lie close together."}
    item, why = sc.verify_llm_item(good, by_title)
    check("verifier keeps a supported model question", item is not None and item["kind"] == "llm" and item["correct"] == "a")
    check("verifier: quote not in the passage -> rejected",
          sc.verify_llm_item(dict(good, evidence="Embeddings are always 768 numbers long in every model."), by_title)[1] == "evidence_not_in_source")
    check("verifier: unknown source -> rejected", sc.verify_llm_item(dict(good, source="Other"), by_title)[1] == "unknown_source")
    check("verifier: answer the quote does not support -> rejected",
          sc.verify_llm_item(dict(good, answer_index=2), by_title)[1] in ("answer_not_supported", "ambiguous"))
    check("verifier: two options equally supported -> rejected (ambiguous)",
          sc.verify_llm_item(dict(good, options=["Vectors close together", "Vectors that lie close", "Random labels", "Fewer stopwords"]),
                             by_title)[1] == "ambiguous")
    check("verifier: duplicate options -> rejected",
          sc.verify_llm_item(dict(good, options=["Vectors lie close", "vectors LIE close", "Random labels", "Fewer stopwords"]), by_title)[1] == "duplicate_options")
    check("verifier: answer_index true (a bool) -> rejected", sc.verify_llm_item(dict(good, answer_index=True), by_title)[1] == "bad_answer_index")
    check("verifier: 3 options -> rejected", sc.verify_llm_item(dict(good, options=good["options"][:3]), by_title)[1] == "bad_options")

    pool = [{"id": 1, "kind": "term", "source_node": "x"}, {"id": 2, "kind": "definition", "source_node": "x"},
            {"id": 3, "kind": "term", "source_node": "y"}, {"id": 4, "kind": "llm", "source_node": "z"},
            {"id": 5, "kind": "term", "source_node": "w"}]
    picked = sc.choose_questions(pool, 3, seen_ids={1}, rng=random.Random(1))
    check("picking: model questions first", picked[0] == 4)
    check("picking: one per source before repeating a source", len({next(p["source_node"] for p in pool if p["id"] == i) for i in picked}) == 3)
    check("picking: unseen questions before seen ones", 1 not in picked)
    score, res = sc.grade([{"item": 1}, {"item": 2}], {"1": "a", "2": "c"}, {1: {"correct": "a"}, 2: {"correct": "b"}})
    check("grading counts only exact option ids", score == 1 and [r["correct"] for r in res] == [True, False])

    now = datetime(2026, 10, 31, 12, 0)
    cfg = {"cooldown_s": 120, "review_after": 2}
    st = sc.step_states([1, 2, 3], set(), {1, 2, 3}, {}, {}, now, cfg)
    check("rules: first step open, the rest locked", [st[i]["status"] for i in (1, 2, 3)] == ["open", "locked", "locked"])
    check("rules: a locked step with a check can be tested out of", st[2]["can_test_out"] and not st[1]["can_test_out"])
    st = sc.step_states([1, 2, 3], {1}, {1, 2, 3}, {1: [{"passed": True, "mode": "check", "submitted_at": now}]}, {}, now, cfg)
    check("rules: finishing a step opens the next", st[1]["status"] == "done" and st[1]["verified"] and st[2]["status"] == "open")
    fail = lambda minutes: {"passed": False, "mode": "check", "submitted_at": now - timedelta(minutes=minutes)}
    st = sc.step_states([1], set(), {1}, {1: [fail(1)]}, {}, now, cfg)
    check("rules: a fail one minute ago -> cooldown", st[1]["cooldown_until"] is not None and not st[1]["review_required"])
    st = sc.step_states([1], set(), {1}, {1: [fail(5)]}, {}, now, cfg)
    check("rules: the cooldown ends", st[1]["cooldown_until"] is None)
    st = sc.step_states([1], set(), {1}, {1: [fail(9), fail(5)]}, {}, now, cfg)
    check("rules: two fails in a row -> review required", st[1]["review_required"])
    st = sc.step_states([1], set(), {1}, {1: [fail(9), fail(5)]}, {1: [{"required_at": now, "reviewed_at": now - timedelta(minutes=2)}]}, now, cfg)
    check("rules: a review after the fails clears it", not st[1]["review_required"])
    st = sc.step_states([1], {1}, {1}, {}, {}, now, cfg)
    check("rules: done without a passed check is not verified (hand-ticked)", st[1]["status"] == "done" and not st[1]["verified"])


# ----------------------------------------------------------------------------------------------------- part 2: routes

def main():
    meta = pickle.load(open("data/processed/faiss_index_meta.pkl", "rb"))
    pure_checks(meta)

    from scripts._csrf import enable_csrf_client
    app = create_app()
    app.config.update(VERIFIED_PROGRESS=True, STEP_CHECK_LLM=False, STEP_CHECK_COOLDOWN_S=120, STEP_CHECK_REVIEW_AFTER=2)
    enable_csrf_client(app)
    reset_rate_limits()
    base = json.load(open("data/base_roadmaps/ai-engineering.json"))
    path = base["metadata"]["career_path"]
    suffix = random.randint(100000, 999999)
    emails = [f"stepcheck{suffix}@example.com", f"stepcheck_b{suffix}@example.com"]
    made_keys = []
    try:
        with app.app_context():
            db.create_all()
        a, b = app.test_client(), app.test_client()
        for client, email, uname in ((a, emails[0], f"sca{suffix}"), (b, emails[1], f"scb{suffix}")):
            client.post("/signup", json={"username": uname, "email": email, "password": PW})
            client.post("/login", json={"login": email, "password": PW})
        with app.app_context():
            ua = User.query.filter_by(email=emails[0]).one()
            ub = User.query.filter_by(email=emails[1]).one()
            ra = GeneratedRoadmap(user_id=ua.id, career_path=path, steps=base["roadmap"])
            rb = GeneratedRoadmap(user_id=ub.id, career_path=path, steps=base["roadmap"])
            flat_old = GeneratedRoadmap(user_id=ua.id, career_path=path,
                                        steps=[{"step_number": 1, "title": "Old step", "description": "x"}, {"step_number": 2, "title": "Old two", "description": "y"}])
            db.session.add_all([ra, rb, flat_old])
            db.session.commit()
            rid, rid_b, rid_old = ra.id, rb.id, flat_old.id
            uid_a = ua.id
            idx = [i for i, _ in sc.flat_steps(base["roadmap"])]

        def correct_answers(attempt_id, wrong=False):
            with app.app_context():
                att = db.session.get(StepCheckAttempt, attempt_id)
                out = {}
                for q in att.questions:
                    item = db.session.get(StepCheckItem, q["item"])
                    out[str(item.id)] = next(o["id"] for o in item.options if o["id"] != item.correct) if wrong else item.correct
                return out

        def age_attempts(minutes):
            with app.app_context():
                for att in StepCheckAttempt.query.filter_by(user_id=uid_a, roadmap_id=rid).all():
                    if att.submitted_at:
                        att.submitted_at -= timedelta(minutes=minutes)
                for r in StepReview.query.filter_by(user_id=uid_a, roadmap_id=rid).all():
                    if r.reviewed_at:
                        r.reviewed_at -= timedelta(minutes=minutes)
                db.session.commit()

        s = a.get(f"/roadmap/{rid}/steps/state").get_json()
        check("state: verified progression on", s["verified_progress"] is True)
        check("state: step 1 open, step 2 locked", s["steps"][str(idx[0])]["status"] == "open" and s["steps"][str(idx[1])]["status"] == "locked")
        check("state: every AI Engineering step has a check", all(v["checkable"] for v in s["steps"].values()))
        r = a.post(f"/roadmap/{rid}/progress", json={"step_index": idx[0], "done": True})
        check("old tick on a step with a check -> 409 check_required", r.status_code == 409 and r.get_json()["error"] == "check_required")
        check("check on a locked step -> 403 locked", a.post(f"/roadmap/{rid}/steps/{idx[1]}/check/start", json={}).status_code == 403)
        check("test-out on an open step -> 400", a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={"mode": "test_out"}).status_code == 400)
        check("bad mode -> 400", a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={"mode": "x"}).status_code == 400)
        check("unknown step -> 404", a.post(f"/roadmap/{rid}/steps/9999/check/start", json={}).status_code == 404)

        r = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={})
        start = r.get_json()
        check("start -> 200 with 4 questions, pass mark 3", r.status_code == 200 and start["total"] == 4 and start["pass_mark"] == 3
              and len(start["questions"]) == 4)
        body_text = r.get_data(as_text=True)
        check("the answers never reach the browser", all(k not in body_text for k in ('"correct"', '"evidence"', '"answer"')))
        again = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={}).get_json()
        check("starting again returns the SAME open attempt and questions (no re-rolling)",
              again["attempt_id"] == start["attempt_id"] and again["questions"] == start["questions"])
        with app.app_context():
            key = sc.step_key(path, dict(sc.flat_steps(base["roadmap"]))[idx[0]])
            items_after_first = StepCheckItem.query.filter_by(step_key=key).count()
        check("questions were stored once for the step", items_after_first >= 8)

        r = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/submit", json={"attempt_id": start["attempt_id"], "answers": {}})
        check("submit with no answers -> 400 unanswered", r.status_code == 400)
        res = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/submit",
                     json={"attempt_id": start["attempt_id"], "answers": correct_answers(start["attempt_id"], wrong=True)}).get_json()
        check("all wrong -> not passed, score 0", res["passed"] is False and res["score"] == 0)
        check("a failed attempt shows which passages to re-read but not the answers",
              all("answer" not in x and "evidence" not in x and x["source_title"] for x in res["results"]))
        check("a fail starts the cooldown", res["state"]["cooldown_until"] is not None)
        check("submitting the same attempt twice -> 409",
              a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/submit", json={"attempt_id": start["attempt_id"], "answers": {"1": "a"}}).status_code == 409)
        r = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={})
        check("start during the cooldown -> 429 with Retry-After", r.status_code == 429 and int(r.headers["Retry-After"]) > 0)

        age_attempts(10)
        second = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={}).get_json()
        first_ids = {q["id"] for q in start["questions"]}
        check("after the cooldown a new attempt prefers questions not seen before",
              second["attempt_id"] != start["attempt_id"] and not (first_ids & {q["id"] for q in second["questions"]}))
        res = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/submit",
                     json={"attempt_id": second["attempt_id"], "answers": correct_answers(second["attempt_id"], wrong=True)}).get_json()
        check("a second fail in a row -> review required", res["state"]["review_required"] is True)
        age_attempts(10)
        r = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={})
        check("start while a review is required -> 409 review_required", r.status_code == 409 and r.get_json()["error"] == "review_required")
        rev = a.get(f"/roadmap/{rid}/steps/{idx[0]}/review").get_json()
        check("the review shows the step's source passages", len(rev["passages"]) >= 2 and all(p["text"] for p in rev["passages"]))
        check("review links are https only", all(l["url"].startswith("https://") for p in rev["passages"] for l in p["resources"]))
        r = a.post(f"/roadmap/{rid}/steps/{idx[0]}/review", json={})
        check("marking the review done clears it", r.status_code == 200 and r.get_json()["state"]["review_required"] is False)
        check("a second 'review done' -> 409", a.post(f"/roadmap/{rid}/steps/{idx[0]}/review", json={}).status_code == 409)
        age_attempts(10)

        third = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={}).get_json()
        answers = correct_answers(third["attempt_id"])
        wrong_one = correct_answers(third["attempt_id"], wrong=True)
        first_key = next(iter(answers))
        answers[first_key] = wrong_one[first_key]          # 3 of 4: exactly the pass mark
        res = a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/submit", json={"attempt_id": third["attempt_id"], "answers": answers}).get_json()
        check("3 of 4 passes", res["passed"] is True and res["score"] == 3)
        check("a pass shows each answer and its source sentence", all(x.get("evidence") and x.get("answer") for x in res["results"]))
        check("a pass completes the step (progress row)", idx[0] in res["completed_steps"])
        s = a.get(f"/roadmap/{rid}/steps/state").get_json()["steps"]
        check("step 1 verified, step 2 now open", s[str(idx[0])]["verified"] and s[str(idx[1])]["status"] == "open")
        check("a check on a finished step -> 409 already_done", a.post(f"/roadmap/{rid}/steps/{idx[0]}/check/start", json={}).status_code == 409)
        a.post(f"/roadmap/{rid}/progress", json={"step_index": idx[0], "done": False})
        r = a.post(f"/roadmap/{rid}/progress", json={"step_index": idx[0], "done": True})
        check("re-ticking a step already passed is allowed", r.status_code == 200 and idx[0] in r.get_json()["completed_steps"])

        target = idx[4]
        to = a.post(f"/roadmap/{rid}/steps/{target}/check/start", json={"mode": "test_out"}).get_json()
        check("test-out: 6 questions, 5 needed", to["total"] == 6 and to["pass_mark"] == 5)
        res = a.post(f"/roadmap/{rid}/steps/{target}/check/submit", json={"attempt_id": to["attempt_id"], "answers": correct_answers(to["attempt_id"])}).get_json()
        s = a.get(f"/roadmap/{rid}/steps/state").get_json()["steps"]
        check("passing a test-out completes that locked step", res["passed"] and s[str(target)]["status"] == "done" and s[str(target)]["verified"])
        check("...opens the step after it, and the skipped ones stay to do",
              s[str(idx[5])]["status"] == "open" and s[str(idx[2])]["status"] == "locked")

        check("another student's roadmap state -> 404", b.get(f"/roadmap/{rid}/steps/state").status_code == 404)
        check("another student's check start -> 404", b.post(f"/roadmap/{rid}/steps/{idx[1]}/check/start", json={}).status_code == 404)
        check("another student's attempt on their own roadmap id -> 404",
              b.post(f"/roadmap/{rid_b}/steps/{idx[0]}/check/submit", json={"attempt_id": third["attempt_id"], "answers": {"1": "a"}}).status_code == 404)
        check("another student's review -> 404", b.get(f"/roadmap/{rid}/steps/{idx[0]}/review").status_code == 404)
        bs = b.post(f"/roadmap/{rid_b}/steps/{idx[0]}/check/start", json={}).get_json()
        with app.app_context():
            check("a second student with the same step reuses the stored questions", StepCheckItem.query.filter_by(step_key=key).count() == items_after_first)
        check("...and gets their own attempt", bs["attempt_id"] not in (start["attempt_id"], second["attempt_id"], third["attempt_id"]))

        from flask.testing import FlaskClient
        raw = FlaskClient(app, app.response_class, use_cookies=True)   # the plain client: sends no CSRF header
        with raw.session_transaction() as sess:           # a logged-in session copied from a, but no CSRF header sent
            with a.session_transaction() as src:
                sess.update(dict(src))
        r = raw.post(f"/roadmap/{rid}/steps/{idx[1]}/check/start", json={})
        check("start without a CSRF token -> 400 csrf", r.status_code == 400 and r.get_json() == {"error": "csrf"})

        s_old = a.get(f"/roadmap/{rid_old}/steps/state").get_json()["steps"]
        check("an old roadmap without topic_refs has no checks", not any(v["checkable"] for v in s_old.values()))
        r = a.post(f"/roadmap/{rid_old}/progress", json={"step_index": 1, "done": True})
        check("...and its steps can still be ticked", r.status_code == 200)

        app.config["VERIFIED_PROGRESS"] = False
        check("off switch: state says verified_progress false", a.get(f"/roadmap/{rid}/steps/state").get_json()["verified_progress"] is False)
        check("off switch: start -> 404", a.post(f"/roadmap/{rid}/steps/{idx[1]}/check/start", json={}).status_code == 404)
        check("off switch: old tick works", a.post(f"/roadmap/{rid}/progress", json={"step_index": idx[1], "done": True}).status_code == 200)
        app.config["VERIFIED_PROGRESS"] = True

        # optional model questions: stubbed generator, a step with a fresh key
        llm_step_roadmap = json.loads(json.dumps(base["roadmap"]))
        llm_step_roadmap["phases"][0]["steps"][0]["title"] += f" {suffix}"
        with app.app_context():
            rl = GeneratedRoadmap(user_id=uid_a, career_path=path, steps=llm_step_roadmap)
            db.session.add(rl)
            db.session.commit()
            rid_llm = rl.id
            made_keys.append(sc.step_key(path, llm_step_roadmap["phases"][0]["steps"][0]))
        real = sc.generate_llm_items

        def fake(step, sources, budget_s=30):
            src = sources[0]
            q = {"source": src["title"], "question": f"According to the passage about {src['title']}, which is true?",
                 "options": [sc.definition_sentence(src), "It stores passwords in plain text.", "It replaces every database.", "It needs no input at all."],
                 "answer_index": 0, "evidence": sc.definition_sentence(src)}
            item, _ = sc.verify_llm_item(q, {sc._norm(s["title"]): s for s in sources})
            return ([item] if item else []), []
        sc.generate_llm_items = fake
        app.config["STEP_CHECK_LLM"] = True
        try:
            lq = a.post(f"/roadmap/{rid_llm}/steps/{idx[0]}/check/start", json={}).get_json()
        finally:
            sc.generate_llm_items = real
            app.config["STEP_CHECK_LLM"] = False
        with app.app_context():
            kinds = [db.session.get(StepCheckItem, q["id"]).kind for q in lq["questions"]]
        check("model questions that pass verification are stored and asked first", kinds[0] == "llm")

        page = a.get("/roadmap").get_data(as_text=True)
        check("the roadmap page loads step_checks.js", "js/step_checks.js" in page)
    finally:
        with app.app_context():
            ids = [u.id for u in User.query.filter(User.email.in_(emails)).all()]
            if ids:
                StepCheckAttempt.query.filter(StepCheckAttempt.user_id.in_(ids)).delete(synchronize_session=False)
                StepReview.query.filter(StepReview.user_id.in_(ids)).delete(synchronize_session=False)
                RoadmapProgress.query.filter(RoadmapProgress.user_id.in_(ids)).delete(synchronize_session=False)
                GeneratedRoadmap.query.filter(GeneratedRoadmap.user_id.in_(ids)).delete(synchronize_session=False)
                for u in User.query.filter(User.id.in_(ids)).all():
                    db.session.delete(u)
            for k in made_keys:
                StepCheckItem.query.filter_by(step_key=k).delete(synchronize_session=False)
            db.session.commit()
            reset_rate_limits()

    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

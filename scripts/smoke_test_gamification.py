"""
Smoke test for gamification: XP rules (best score only, one-off bonuses, no farming), levels, the IST streak maths,
every badge rule, rewards between two summaries, GET /gamification (auth, per-user data, no writes), the rewards on
POST /scenarios/<id>/submit, and the dashboard / scenarios pages loading the new script.

NO EXTERNAL CALLS. The route section uses Flask's test client and the development database and deletes every row it
created. Code questions run with this machine's Python (CODE_RUNNER=local) inside the test only.

Usage:
    PYTHONPATH=. python scripts/smoke_test_gamification.py

Exits non-zero if any check fails.
"""
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


TODAY = date(2026, 10, 16)


def at(day_offset, hour=6):
    """A naive-UTC datetime `day_offset` days before TODAY (IST), at `hour` UTC (06:00 UTC = 11:30 IST)."""
    return datetime.combine(TODAY - timedelta(days=day_offset), datetime.min.time()) + timedelta(hours=hour)


def attempt(n, sid, score, max_score=50, path="Full-Stack Development", when=None, answers=None):
    return {"id": n, "scenario_id": sid, "path": path, "score": score, "max_score": max_score,
            "passed": score * 100 >= 70 * max_score, "submitted_at": when or at(0), "answers": answers or {}}


# ---------------------------------------------------------------- part 1: pure rules
def test_rules():
    from app.pipeline import gamification as g

    empty = g.summarize([], [], TODAY)
    check("empty: 0 XP, level 1 Intern, no streak, no badges",
          empty["xp"] == 0 and empty["level"]["level"] == 1 and empty["level"]["title"] == "Intern"
          and empty["streak"] == {"current": 0, "best": 0, "active_today": False}
          and empty["counts"]["badges_earned"] == 0 and len(empty["badges"]) == len(g.BADGES))

    one = g.summarize([attempt(1, "fsd-1", 40)], [], TODAY)
    check("one pass at 40/50: 40 points + 20 first-pass bonus = 60 XP",
          one["xp"] == 60 and one["xp_breakdown"]["first_pass_bonus"] == 20)

    retries = g.summarize([attempt(1, "fsd-1", 40, when=at(0, 3)), attempt(2, "fsd-1", 40, when=at(0, 4)),
                           attempt(3, "fsd-1", 30, when=at(0, 5))], [], TODAY)
    check("no farming: retrying the same scenario with equal or lower scores adds no XP", retries["xp"] == 60)

    better = g.summarize([attempt(1, "fsd-1", 30, when=at(1)), attempt(2, "fsd-1", 50, when=at(0))], [], TODAY)
    check("a better later score counts once: 50 best + 20 pass + 10 perfect = 80",
          better["xp"] == 80 and better["xp_breakdown"]["perfect_bonus"] == 10)

    fail = g.summarize([attempt(1, "fsd-1", 30)], [], TODAY)
    check("a failed attempt earns its points but no pass bonus", fail["xp"] == 30)

    steps = g.summarize([], [at(0), at(0), at(2)], TODAY)
    check("roadmap steps: 5 XP each (current ticks only)", steps["xp"] == 15)

    lv = g.level_for(0)
    check("level 1 shows 100 XP to Trainee", lv["next_at"] == 100 and lv["next_title"] == "Trainee" and lv["progress_pct"] == 0)
    lv = g.level_for(175)
    check("175 XP: level 2 Trainee, halfway to Junior Engineer (250)",
          lv["level"] == 2 and lv["title"] == "Trainee" and lv["progress_pct"] == 50)
    top = g.level_for(99999)
    check("top level: no next level, 100%", top["next_at"] is None and top["progress_pct"] == 100
          and top["title"] == "Principal Engineer")
    check("levels rise with XP thresholds and never skip",
          [g.level_for(f)["level"] for f, _ in g.LEVELS] == list(range(1, len(g.LEVELS) + 1)))

    # ---- streaks
    cur, best = g.streaks({TODAY, TODAY - timedelta(1), TODAY - timedelta(2)}, TODAY)
    check("streak: 3 days ending today -> current 3, best 3", (cur, best) == (3, 3))
    cur, best = g.streaks({TODAY - timedelta(1), TODAY - timedelta(2)}, TODAY)
    check("streak: idle today but active yesterday -> still alive (2)", cur == 2)
    cur, best = g.streaks({TODAY - timedelta(2), TODAY - timedelta(3)}, TODAY)
    check("streak: last active 2 days ago -> broken (0), best kept (2)", (cur, best) == (0, 2))
    days = {TODAY - timedelta(d) for d in (0, 1, 5, 6, 7, 8)}
    check("streak: best is the longest run anywhere (4), current is today's run (2)",
          g.streaks(days, TODAY) == (2, 4))
    check("streak: future dates are ignored", g.streaks({TODAY + timedelta(3)}, TODAY) == (0, 0))
    late = datetime.combine(TODAY - timedelta(1), datetime.min.time()) + timedelta(hours=19)   # 00:30 IST TODAY
    check("streak days use IST: 19:00 UTC yesterday is today in India", g.ist_day(late) == TODAY)
    s = g.summarize([attempt(1, "fsd-1", 40, when=at(1))], [at(0)], TODAY)
    check("streak counts both scenario submits and roadmap ticks", s["streak"]["current"] == 2
          and s["streak"]["active_today"])

    # ---- badges
    codes = {"fsd-2-c1": "hash_map", "fsd-2-c2": "sorting", "fsd-4-c2": "linked_list", "fsd-5-c2": "heap",
             "dsc-2-c1": "hash_map"}
    rec = {"passed": True, "visible": [True], "hidden_passed": 4, "hidden_total": 4}
    lost = {"passed": False, "visible": [False], "hidden_passed": 0, "hidden_total": 4}
    path_ids = {"Full-Stack Development": ["fsd-1", "fsd-2"], "Data Science": ["dsc-1"]}
    attempts = [
        attempt(1, "fsd-1", 20, when=at(3)),
        attempt(2, "fsd-1", 50, when=at(2)),
        attempt(3, "fsd-2", 60, max_score=60, when=at(1), answers={"fsd-2-c1": rec, "_pick": {"pool_id": "fsd-2-c1"}}),
        attempt(4, "fsd-2", 60, max_score=60, when=at(0), answers={"fsd-2-c2": rec}),
        attempt(5, "dsc-1", 10, path="Data Science", when=at(0), answers={"dsc-2-c1": lost}),
    ]
    out = g.summarize(attempts, [], TODAY, codes, path_ids)
    earned = {b["id"] for b in out["badges"] if b["earned"]}
    check("badges: first steps, pass, perfect, first code, comeback, path complete, explorer, 3-day streak",
          {"first_steps", "first_pass", "perfectionist", "first_code", "comeback", "path_complete", "explorer",
           "streak_3"} <= earned)
    check("badges not earned: 5 codes, 3 structures, deep end, 7-day streak, 10 roadmap steps",
          not ({"coder_5", "structures_3", "deep_end", "streak_7", "roadmap_10"} & earned))
    by_id = {b["id"]: b for b in out["badges"]}
    check("locked badges report progress towards their target",
          (by_id["coder_5"]["progress"], by_id["coder_5"]["target"]) == (2, 5)
          and (by_id["structures_3"]["progress"], by_id["structures_3"]["target"]) == (2, 3))
    check("a failed code record does not count as solved", out["counts"]["codes_solved"] == 2)
    check("the _pick entry and unknown answer keys are never counted as code",
          out["xp_breakdown"]["code_bonus"] == 2 * g.XP_RULES["code_solved"])
    check("path_complete needs EVERY scenario of a path passed (Data Science not)",
          by_id["path_complete"]["progress"] == 1)
    deep = g.summarize([attempt(1, "fsd-5", 50, answers={"fsd-5-c2": rec})], [], TODAY, codes, {})
    check("deep end: solving a heap problem earns it", any(b["id"] == "deep_end" and b["earned"] for b in deep["badges"]))
    no_comeback = g.summarize([attempt(1, "fsd-1", 50, when=at(1)), attempt(2, "fsd-1", 10, when=at(0))], [], TODAY)
    check("comeback needs a fail BEFORE the first pass", not next(b for b in no_comeback["badges"]
                                                                 if b["id"] == "comeback")["earned"])
    forged = g.summarize([attempt(1, "fsd-2", 0, answers={"fsd-2-c1": {"passed": "yes"}})], [], TODAY, codes, {})
    check("a record whose passed is not exactly True is not a solve", forged["counts"]["codes_solved"] == 0)
    check("summaries are deterministic", g.summarize(attempts, [], TODAY, codes, path_ids) == out)
    check("attempt order in the input does not matter",
          g.summarize(list(reversed(attempts)), [], TODAY, codes, path_ids) == out)

    # ---- rewards
    before = g.summarize(attempts[:2], [], TODAY, codes, path_ids)
    after = g.summarize(attempts[:3], [], TODAY, codes, path_ids)
    r = g.rewards(before, after)
    check("rewards: XP gained is the difference, new badges listed once",
          r["xp_gained"] == after["xp"] - before["xp"] and r["xp_gained"] > 0
          and {"first_code", "path_complete"} <= {b["id"] for b in r["new_badges"]}
          and "first_pass" not in {b["id"] for b in r["new_badges"]})
    r2 = g.rewards(after, after)
    check("rewards: nothing changed -> 0 XP, no badges, no level-up",
          r2["xp_gained"] == 0 and not r2["new_badges"] and not r2["leveled_up"])
    low = g.summarize([attempt(1, "fsd-1", 40)], [], TODAY)
    high = g.summarize([attempt(1, "fsd-1", 40), attempt(2, "fsd-2", 50)], [], TODAY)
    check("rewards: crossing 100 XP is a level-up to Trainee",
          g.rewards(low, high)["leveled_up"] and g.rewards(low, high)["level"]["title"] == "Trainee")


# ---------------------------------------------------------------- part 2: routes
def test_routes():
    from app import create_app, db
    from app.models import CareerProfile, ScenarioAttempt, User
    from app.pipeline import scenario_store as store
    from scripts._csrf import enable_csrf_client

    app = create_app()
    enable_csrf_client(app)
    app.config["CODE_RUNNER"] = "local"
    store.set_directory(None)
    suffix = random.randint(100000, 999999)
    user_ids = []
    fsd = json.loads(Path("data/scenarios/full-stack-development.json").read_text(encoding="utf-8"))
    s1 = next(s for s in fsd["scenarios"] if s["id"] == "fsd-1")
    s2 = next(s for s in fsd["scenarios"] if s["id"] == "fsd-2")

    def login(tag):
        client = app.test_client()
        email = f"gam{tag}{suffix}@example.com"
        resp = client.post("/signup", json={"name": "Gam Test", "email": email, "password": "SmokeTest#123"})
        user_ids.append(resp.get_json()["user_id"])
        client.post("/login", json={"email": email, "password": "SmokeTest#123"})
        return client, user_ids[-1]

    def right_answers(scenario):
        return {q["id"]: q["correct"] for q in scenario["questions"] if q["type"] != "code"}

    try:
        anon = app.test_client()
        check("GET /gamification logged out -> 401", anon.get("/gamification").status_code == 401)

        alice, aid = login("a")
        g0 = alice.get("/gamification")
        body = g0.get_json()
        check("GET /gamification: a new account has 0 XP, level 1 and 14 locked badges",
              g0.status_code == 200 and body["xp"] == 0 and body["level"]["level"] == 1
              and body["counts"] == {"scenarios_passed": 0, "codes_solved": 0, "badges_earned": 0, "badges_total": 14})

        started = alice.post("/scenarios/fsd-1/start", json={}).get_json()
        sub = alice.post("/scenarios/fsd-1/submit",
                         json={"attempt_id": started["attempt_id"], "answers": right_answers(s1)}).get_json()
        r = sub.get("rewards")
        max1 = 10 * len(s1["questions"])
        check("submit: a perfect first scenario returns rewards (points + pass + perfect bonus)",
              r is not None and r["xp_gained"] == max1 + 20 + 10 and r["xp"] == max1 + 30)
        check("submit: new badges First Steps, Case Closed and Perfectionist",
              {"first_steps", "first_pass", "perfectionist"} <= {b["id"] for b in r["new_badges"]})
        check("submit: the streak is 1 and active today", r["streak"]["current"] == 1 and r["streak"]["active_today"])
        check("submit: the grade is unchanged by the rewards",
              sub["passed"] and sub["score"] == max1 and sub["percent"] == 100)

        again = alice.post("/scenarios/fsd-1/start", json={}).get_json()
        sub2 = alice.post("/scenarios/fsd-1/submit",
                          json={"attempt_id": again["attempt_id"], "answers": right_answers(s1)}).get_json()
        check("submit again with the same score: 0 XP and no new badges (no farming)",
              sub2["rewards"]["xp_gained"] == 0 and not sub2["rewards"]["new_badges"])

        start2 = alice.post("/scenarios/fsd-2/start", json={}).get_json()
        code_q = start2["scenario"]["questions"][-1]
        problem = next(p for p in s2["code_pool"] if p["id"] == code_q["id"])
        alice.post("/scenarios/fsd-2/answer", json={"attempt_id": start2["attempt_id"], "question_id": code_q["id"],
                                                    "answer": problem["reference_solution"]})
        sub3 = alice.post("/scenarios/fsd-2/submit",
                          json={"attempt_id": start2["attempt_id"], "answers": right_answers(s2)}).get_json()
        r3 = sub3["rewards"]
        max2 = 10 * (len(s2["questions"]) + 1)
        check("submit with a solved coding problem: + points + pass + perfect + code bonus, and Hello, World",
              r3["xp_gained"] == max2 + 20 + 10 + 15 and "first_code" in {b["id"] for b in r3["new_badges"]})
        check("crossing 100 XP is reported as a level-up", r3["leveled_up"] and r3["level"]["level"] >= 2)

        g1 = alice.get("/gamification").get_json()
        check("GET /gamification agrees with the rewards", g1["xp"] == r3["xp"] and g1["counts"]["codes_solved"] == 1)

        bob, bid = login("b")
        gb = bob.get("/gamification").get_json()
        check("per user: another student sees only their own (0 XP)", gb["xp"] == 0)

        with app.app_context():
            rows_before = ScenarioAttempt.query.filter(ScenarioAttempt.user_id.in_(user_ids)).count()
        for _ in range(3):
            alice.get("/gamification")
        with app.app_context():
            rows_after = ScenarioAttempt.query.filter(ScenarioAttempt.user_id.in_(user_ids)).count()
            check("GET /gamification writes nothing", rows_before == rows_after
                  and CareerProfile.query.filter(CareerProfile.user_id.in_(user_ids)).count() == 0)

        import app.routes.gamification as route
        real = route.summary_for

        def broken(*a, **k):
            raise RuntimeError("SECRET-DETAIL-do-not-leak")
        route.summary_for = broken
        try:
            st = alice.post("/scenarios/fsd-1/start", json={}).get_json()
            sb = alice.post("/scenarios/fsd-1/submit", json={"attempt_id": st["attempt_id"], "answers": {}})
            body = sb.get_json()
            check("a gamification failure never breaks a submit (rewards is null, grade still returned)",
                  sb.status_code == 200 and body["rewards"] is None and "score" in body)
            ge = alice.get("/gamification")
            check("GET /gamification failure -> 500 with a fixed code and no exception text",
                  ge.status_code == 500 and ge.get_json() == {"error": "gamification_unavailable"}
                  and "SECRET" not in ge.get_data(as_text=True))
        finally:
            route.summary_for = real

        for page in ("/dashboard", "/scenarios"):
            html = alice.get(page).get_data(as_text=True)
            check(f"{page} loads gamification.js", "js/gamification.js" in html)
        js = Path("app/static/js/gamification.js").read_text(encoding="utf-8")
        check("gamification.js builds everything with el()/textContent (no innerHTML)",
              "innerHTML" not in js and "function gamLevelCard" in js and "function gamRewardsCard" in js)
        dash = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        check("dashboard fetches /gamification and still renders without it",
              'getJson("/gamification")' in dash and "gam.ok ? gam.data : null" in dash)
    finally:
        with app.app_context():
            for uid in user_ids:
                ScenarioAttempt.query.filter_by(user_id=uid).delete()
                CareerProfile.query.filter_by(user_id=uid).delete()
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

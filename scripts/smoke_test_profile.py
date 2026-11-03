"""
Smoke test for accounts and the profile: username rules, signup with a username, login with a username or an email,
the live username check, the profile page and API (details, validation, username change, picture, password change),
per-user isolation, CSRF, the friendly 404 / 500 handlers, and the roadmap-complete date and Finish Line badge.

NO EXTERNAL CALLS. Uses Flask's test client and the development database, and deletes every row it created.
Needs scripts/add_usernames.py --apply to have been run once on the database.

Usage:
    PYTHONPATH=. python scripts/smoke_test_profile.py

Exits non-zero if any check fails.
"""
import io
import json
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # before any app import: the config reads the environment when it is imported

checks = []
PW = "SmokeTest#123"


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


# ---------------------------------------------------------------- part 1: pure username rules
def test_username_rules():
    from app import usernames as u

    check("normalize trims and lowercases; non-strings become ''",
          u.normalize("  Joel_M ") == "joel_m" and u.normalize(None) == "" and u.normalize(5) == "")
    valid = ["joel", "joel_m", "a12", "x" * 20]
    invalid = ["jo", "x" * 21, "1joel", "_joel", "joel.m", "joel m", "joël", "jo@el", "admin", "levelup", ""]
    check("valid usernames pass", all(u.is_valid(v) for v in valid))
    check("too short/long, starts with a digit or _, dots, spaces, non-ASCII, '@' and reserved names fail",
          not any(u.is_valid(v) for v in invalid))
    taken = {"joel_m", "joel_m2"}
    check("suggest_from_email: joel.m@x -> joel_m3 when joel_m and joel_m2 are taken",
          u.suggest_from_email("joel.m@x.com", lambda c: c in taken) == "joel_m3")
    odd = [u.suggest_from_email(e, lambda c: False) for e in ["123@x.com", "a@x.com", "..@x.com", "ADMIN@x.com", "x" * 40 + "@y.com"]]
    check(f"suggest_from_email always returns a valid username: {odd}", all(u.is_valid(o) for o in odd))
    check("suggest_from_email never returns a reserved name", odd[3] != "admin" and u.is_valid(odd[3]))


# ---------------------------------------------------------------- part 2: routes
def test_routes():
    from PIL import Image
    from app import create_app, db
    from app.models import GeneratedRoadmap, RoadmapProgress, User, UserAvatar, UserProfile
    from app.security import reset_rate_limits
    from scripts._csrf import enable_csrf_client

    app = create_app()
    app.config["VERIFIED_PROGRESS"] = False   # these checks tick steps directly (smoke_test_step_checks.py covers checks)
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    emails = []

    def signup(client, username, tag, **extra):
        email = f"prof{tag}{suffix}@example.com"
        emails.append(email)
        body = {"email": email, "password": PW, **extra}
        if username is not None:
            body["username"] = username
        return client.post("/signup", json=body), email

    def png_bytes(size=(800, 500), mode="RGBA"):
        buf = io.BytesIO()
        Image.new(mode, size, (200, 30, 30, 120) if mode == "RGBA" else (200, 30, 30)).save(buf, "PNG")
        return buf.getvalue()

    def jpeg_with_gps():
        img = Image.new("RGB", (300, 400), (10, 120, 200))
        exif = Image.Exif()
        exif[0x010F] = "SecretCamera"          # Make
        exif[0x8825] = {1: "N", 2: (12.0, 30.0, 0.0)}   # GPS IFD
        buf = io.BytesIO()
        img.save(buf, "JPEG", exif=exif)
        return buf.getvalue()

    def upload(client, data, name="p.png"):
        return client.post("/profile/avatar", data={"avatar": (io.BytesIO(data), name)}, content_type="multipart/form-data")

    try:
        reset_rate_limits()
        anon = app.test_client()
        ua = f"prof_a{suffix}"
        ub = f"prof_b{suffix}"

        # --- signup
        r, email_a = signup(anon, ua.upper(), "a")
        check("signup with a username -> 201, stored lowercase", r.status_code == 201 and r.get_json()["username"] == ua)
        r, _ = signup(anon, ua, "a2")
        check("signup with a taken username -> 409 with a fixed message",
              r.status_code == 409 and r.get_json()["error"] == "That username is taken. Try another.")
        r, _ = signup(anon, "9bad", "a3")
        check("signup with an invalid username -> 400 with the rule", r.status_code == 400 and "3-20 characters" in r.get_json()["error"])
        r = anon.post("/signup", json={"username": f"prof_c{suffix}", "email": email_a.upper(), "password": PW})
        check("signup with an existing email in other case -> 409", r.status_code == 409)
        r, email_legacy = signup(anon, None, "legacy", name="Legacy Client")
        legacy_username = r.get_json().get("username")
        check(f"older clients sending only 'name' still sign up and get a username from the email ({legacy_username})",
              r.status_code == 201 and legacy_username and legacy_username.startswith("prof"))
        r = anon.post("/signup", json={"email": f"x{suffix}@example.com", "password": PW})
        check("signup with neither username nor name -> 400", r.status_code == 400)
        r, _ = signup(anon, ub, "b")
        check("second user signs up", r.status_code == 201)

        # --- username check
        free = anon.get(f"/signup/username-check?username=free_{suffix}").get_json()
        taken = anon.get(f"/signup/username-check?username={ua.upper()}").get_json()
        bad = anon.get("/signup/username-check?username=ab").get_json()
        check("username-check: free -> available, taken (any case) -> not, invalid -> rule message",
              free == {"available": True, "error": None} and taken["available"] is False
              and "taken" in taken["error"] and bad["available"] is False and "3-20" in bad["error"])
        reset_rate_limits()
        codes = [anon.get("/signup/username-check?username=abc").status_code for _ in range(61)]
        check("username-check is rate-limited (61st call in a minute -> 429)", codes[59] == 200 and codes[60] == 429)
        reset_rate_limits()

        # --- login
        a = app.test_client()
        check("login with the username -> 200", a.post("/login", json={"login": ua, "password": PW}).status_code == 200)
        c2 = app.test_client()
        check("login with the username in capitals -> 200", c2.post("/login", json={"login": ua.upper(), "password": PW}).status_code == 200)
        c3 = app.test_client()
        check("login with the email (any case, old 'email' key) -> 200",
              c3.post("/login", json={"email": email_a.upper(), "password": PW}).status_code == 200)
        r = app.test_client().post("/login", json={"login": ua, "password": "Wrong#1234"})
        r2 = app.test_client().post("/login", json={"login": f"nobody_{suffix}", "password": PW})
        check("wrong password and unknown user give the same 401 message",
              r.status_code == r2.status_code == 401 and r.get_json() == r2.get_json())
        check("login with a missing field -> 400", app.test_client().post("/login", json={"login": ua}).status_code == 400)
        b = app.test_client()
        b.post("/login", json={"login": ub, "password": PW})

        # --- profile auth
        check("GET /profile/data logged out -> 401", anon.get("/profile/data").status_code == 401)
        r = anon.get("/profile")
        check("GET /profile logged out -> redirect to login with next=/profile",
              r.status_code == 302 and r.headers["Location"].endswith("/login?next=/profile"))
        check("GET /profile logged in -> 200", a.get("/profile").status_code == 200)

        # --- navbar
        html = a.get("/dashboard").get_data(as_text=True)
        check("navbar name is a link to /profile showing the username and an initial",
              'href="/profile" class="nav-user"' in html and ua in html and "nav-avatar-initial" in html)

        # --- profile data and updates
        data = a.get("/profile/data").get_json()
        check("profile data: username, email, name, empty details, no picture, progress, no password hash",
              data["username"] == ua and data["email"] == email_a and data["avatar_url"] is None
              and all(v is None for v in data["details"].values()) and data["progress"] is not None
              and "password_hash" not in json.dumps(data))
        good = {"name": "Ravi Kumar", "phone": "+91 98765-43210", "college": "BITM", "branch": "AI & ML",
                "year_of_study": "3", "graduation_year": 2027, "city": "Ballari",
                "linkedin_url": "https://www.linkedin.com/in/ravi", "github_url": "https://github.com/ravi", "bio": "Hi."}
        r = a.post("/profile", json=good)
        d = r.get_json()
        check("save all details -> 200 and every value comes back (year as a number)",
              r.status_code == 200 and d["name"] == "Ravi Kumar" and d["details"]["year_of_study"] == 3
              and d["details"]["graduation_year"] == 2027 and d["details"]["phone"] == "+91 98765-43210")
        bad_cases = [
            ({"phone": "12ab"}, "phone"), ({"phone": "123"}, "phone"),
            ({"year_of_study": 9}, "year_of_study"), ({"graduation_year": "soon"}, "graduation_year"),
            ({"linkedin_url": "javascript:alert(1)"}, "linkedin_url"), ({"github_url": "https://evil.com/github.com"}, "github_url"),
            ({"bio": "x" * 301}, "bio"), ({"name": "  "}, "name"), ({"username": "Bad Name"}, "username"),
        ]
        results = [(a.post("/profile", json=body), field) for body, field in bad_cases]
        check("each invalid field -> 400 naming that field",
              all(r.status_code == 400 and r.get_json().get("field") == f for r, f in results))
        r = a.post("/profile", json={"name": "Changed Name", "phone": "nope"})
        check("a bad field changes nothing else (name not saved alongside an invalid phone)",
              r.status_code == 400 and a.get("/profile/data").get_json()["name"] == "Ravi Kumar")
        a.post("/profile", json={"city": ""})
        check("an empty string clears a field", a.get("/profile/data").get_json()["details"]["city"] is None)
        r = a.post("/profile", json={"username": ub})
        check("changing to another student's username -> 409", r.status_code == 409 and r.get_json()["field"] == "username")
        new_ua = f"prof_new{suffix}"
        r = a.post("/profile", json={"username": new_ua.upper()})
        check("changing the username -> 200, stored lowercase", r.status_code == 200 and r.get_json()["username"] == new_ua)
        check("log in with the new username works; the old one doesn't",
              app.test_client().post("/login", json={"login": new_ua, "password": PW}).status_code == 200
              and app.test_client().post("/login", json={"login": ua, "password": PW}).status_code == 401)
        check("POST /profile without a CSRF token -> 400 csrf",
              a.post("/profile", json={"city": "x"}, headers={"X-CSRF-Token": "wrong"}).status_code == 400)
        check("another student's profile data is their own", b.get("/profile/data").get_json()["username"] == ub
              and b.get("/profile/data").get_json()["details"]["phone"] is None)

        # --- picture
        r = upload(a, png_bytes())
        url = r.get_json().get("avatar_url")
        check("upload a PNG with transparency -> 200 and an avatar URL", r.status_code == 200 and url and url.startswith("/profile/avatar?v="))
        img = a.get("/profile/avatar")
        pic = Image.open(io.BytesIO(img.data))
        check("the stored picture is a 256x256 JPEG, private cache, nosniff",
              img.status_code == 200 and img.mimetype == "image/jpeg" and pic.size == (256, 256) and pic.format == "JPEG"
              and "private" in img.headers["Cache-Control"] and img.headers.get("X-Content-Type-Options") == "nosniff")
        r = upload(a, jpeg_with_gps(), "g.jpg")
        stored = Image.open(io.BytesIO(a.get("/profile/avatar").data))
        check("a JPEG with camera and GPS EXIF is re-encoded without any EXIF",
              r.status_code == 200 and len(stored.getexif()) == 0 and b"SecretCamera" not in a.get("/profile/avatar").data)
        r = upload(a, b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "x.png")
        r2 = upload(a, b"GIF89a" + b"\x00" * 100, "x.gif")
        check("an SVG / non-image or a GIF -> 400 'isn't a JPEG, PNG or WebP'",
              r.status_code == 400 and r2.status_code == 400 and "JPEG, PNG or WebP" in r.get_json()["error"])
        big = png_bytes((4000, 4000), "RGB") + b"\x00" * (4 * 1024 * 1024)
        r = upload(a, big, "big.png")
        check("a picture over 4 MB -> 400", r.status_code == 400 and "4 MB" in r.get_json()["error"])
        r = a.post("/profile/avatar", data={}, content_type="multipart/form-data")
        check("no file -> 400", r.status_code == 400)
        check("the navbar shows the picture once there is one", '<img class="nav-avatar"' in a.get("/dashboard").get_data(as_text=True))
        check("another student without a picture gets 404 for theirs (never someone else's)", b.get("/profile/avatar").status_code == 404)
        check("GET /profile/avatar logged out -> 401", anon.get("/profile/avatar").status_code == 401)
        r = a.post("/profile/avatar/delete")
        check("remove the picture -> 200, then 404", r.status_code == 200 and a.get("/profile/avatar").status_code == 404)

        # --- password
        r = a.post("/profile/password", json={"current_password": "Wrong#1234", "new_password": "NewPass#456"})
        check("wrong current password -> 400 on current_password", r.status_code == 400 and r.get_json()["field"] == "current_password")
        r = a.post("/profile/password", json={"current_password": PW, "new_password": "weak"})
        check("weak new password -> 400 with the password rule", r.status_code == 400 and "at least 8 characters" in r.get_json()["error"])
        r = a.post("/profile/password", json={"current_password": PW, "new_password": PW})
        check("same password -> 400", r.status_code == 400 and r.get_json()["field"] == "new_password")
        r = a.post("/profile/password", json={"current_password": PW, "new_password": "NewPass#456"})
        check("valid change -> 200", r.status_code == 200)
        check("old password no longer logs in, the new one does",
              app.test_client().post("/login", json={"login": new_ua, "password": PW}).status_code == 401
              and app.test_client().post("/login", json={"login": new_ua, "password": "NewPass#456"}).status_code == 200)
        reset_rate_limits()

        # --- error pages
        r = a.get("/no-such-page", headers={"Accept": "text/html,application/xhtml+xml"})
        check("unknown page in a browser -> 404 styled page", r.status_code == 404 and "Page not found" in r.get_data(as_text=True))
        r = a.get("/no-such-page")
        check("unknown URL from fetch()/scripts -> 404 JSON {'error': 'not_found'}", r.status_code == 404 and r.get_json() == {"error": "not_found"})
        check("a route's own 404 JSON is unchanged (roadmap not found)",
              a.get("/roadmap/999999999").get_json() != {"error": "not_found"})

        # --- roadmap complete
        with app.app_context():
            uid = User.query.filter_by(email=email_a).first().id
            base = json.loads(Path("data/scenarios/../base_roadmaps/backend-engineering.json").read_text(encoding="utf-8"))["roadmap"]
            rm = GeneratedRoadmap(user_id=uid, career_path="Backend Engineering", steps=base)
            db.session.add(rm)
            db.session.commit()
            rid = rm.id
            total = sum(len(p["steps"]) for p in base["phases"])
            for i in range(1, total):
                db.session.add(RoadmapProgress(user_id=uid, roadmap_id=rid, step_index=i))
            db.session.commit()
        before = a.get(f"/roadmap/{rid}").get_json()
        badge = lambda: next(x for x in a.get("/gamification").get_json()["badges"] if x["id"] == "finish_line")
        check("one step short: completed_on is null and Finish Line is locked", before["completed_on"] is None and not badge()["earned"])
        r = a.post(f"/roadmap/{rid}/progress", json={"step_index": total, "done": True}).get_json()
        check("ticking the last step returns completed_on", r["completed_count"] == total and r["completed_on"])
        check("GET /roadmap/<id> has completed_on and Finish Line is earned",
              a.get(f"/roadmap/{rid}").get_json()["completed_on"] and badge()["earned"])
        r = a.post(f"/roadmap/{rid}/progress", json={"step_index": 3, "done": False}).get_json()
        check("unticking a step clears completed_on and locks Finish Line again", r["completed_on"] is None and not badge()["earned"])
        page = a.get(f"/roadmap?id={rid}").get_data(as_text=True)
        js = Path("app/static/js/celebrate.js").read_text(encoding="utf-8")
        check("roadmap page loads celebrate.js; it uses el()/textContent only and skips confetti for reduced motion",
              "js/celebrate.js" in page and "innerHTML" not in js and "prefers-reduced-motion" in js)
    finally:
        with app.app_context():
            ids = [u.id for u in User.query.filter(User.email.in_(emails)).all()]
            for model in (RoadmapProgress, GeneratedRoadmap, UserAvatar, UserProfile):
                model.query.filter(model.user_id.in_(ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
        reset_rate_limits()


def test_server_error_page():
    """A crash in a route: the browser gets the styled 500 page, fetch() gets fixed JSON, never the exception text."""
    from app import create_app

    app = create_app()
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["TESTING"] = False

    @app.route("/__boom")
    def boom():
        raise RuntimeError("secret internal detail")

    client = app.test_client()
    html = client.get("/__boom", headers={"Accept": "text/html"})
    api = client.get("/__boom")
    check("500 in a browser -> styled page without the exception text",
          html.status_code == 500 and "Something went wrong" in html.get_data(as_text=True)
          and "secret internal detail" not in html.get_data(as_text=True))
    check("500 from fetch() -> {'error': 'server_error'} only", api.status_code == 500 and api.get_json() == {"error": "server_error"})


def test_goal_tailoring():
    """The Goals page's "what we'll tailor" summary: only real effects, and the quiz's ranking is untouched."""
    from app import create_app, db
    from app.models import CareerProfile, User
    from app.pipeline import scenario_engine as eng
    from app.pipeline.goal_tailoring import tailoring_summary
    from scripts._csrf import enable_csrf_client

    gentle = tailoring_summary({"goal": "build_fundamentals", "avoid": "none", "target_company": "unsure", "it_track": "open"})
    areas = [i["area"] for i in gentle["items"]]
    check("build_fundamentals: gentler coding problems, foundation + core-decision scenarios starred, roadmap uses the goal",
          areas == ["Coding problems", "Scenarios", "Roadmap"] and "gentler" in gentle["items"][0]["text"]
          and "Foundation and core-decision" in gentle["items"][1]["text"])
    check("'avoid: none', 'company: unsure' and a legacy it_track answer (question C1 was removed) add nothing to the roadmap line",
          "avoid" not in gentle["items"][2]["text"] and "aiming" not in gentle["items"][2]["text"]
          and not any("traditional" in i["text"].lower() for i in gentle["items"]))
    hard = tailoring_summary({"goal": "specific_role", "avoid": "repetitive_work", "target_company": "startup", "additional_notes": "x"})
    check("specific_role: harder problems, debugging/trade-off/end-to-end starred, avoid + company + note listed",
          "harder" in hard["items"][0]["text"] and "Debugging, trade-off and end-to-end" in hard["items"][1]["text"]
          and "too much repetitive/routine work" in hard["items"][2]["text"] and "(startup)" in hard["items"][2]["text"]
          and len(hard["items"]) == 3 and hard["items"][2]["text"].endswith("Your note is passed to it as background too."))
    only_note = tailoring_summary({"additional_notes": "x"})["items"]
    check("a note alone gets its own Roadmap line", [i["area"] for i in only_note] == ["Roadmap"] and "Your note" in only_note[0]["text"])
    check("the summary's goal rules match the engine's (easier/harder goals and starred stages)",
          eng.EASIER_GOALS == {"build_fundamentals", "explore"} and eng.HARDER_GOALS == {"specific_role", "any_good_company"}
          and all(set(eng.GOAL_STAGES[g]) for g in ("build_fundamentals", "explore", "specific_role", "any_good_company")))
    check("no answers -> no tailoring lines, but the match note is still there",
          tailoring_summary({})["items"] == [] and "quiz only" in tailoring_summary({})["match_note"])

    app = create_app()
    enable_csrf_client(app)
    email = f"goals{random.randint(100000, 999999)}@example.com"
    client = app.test_client()
    try:
        client.post("/signup", json={"username": f"goals_{random.randint(100000, 999999)}", "email": email, "password": PW})
        client.post("/login", json={"login": email, "password": PW})
        data = client.post("/quiz/start").get_json()
        while True:
            data = client.post("/quiz/answer", json={"question_id": data["question_id"], "option": "A"}).get_json()
            if data.get("finished"):
                quiz_ranking = [(r["career_path"], r["confidence_pct"]) for r in data["results"]]
                break
        picks = {"C2": "B", "C3": "B", "C4": "C"}   # deadlines / product-based / fundamentals
        data = client.post("/conversation/start").get_json()
        check("Goals has 3 questions: it starts at C2 and reports a total of 3 (the old C1 question is gone)",
              data["question_id"] == "C2" and data["total"] == 3)
        old = client.post("/conversation/answer", json={"question_id": "C1", "option": "A"})
        check("an answer to the removed question C1 is refused (400) and nothing is recorded for it",
              old.status_code == 400)
        while True:
            body = {"question_id": data["question_id"], "option": picks[data["question_id"]]}
            data = client.post("/conversation/answer", json=body).get_json()
            if data.get("finished"):
                break
        check("the saved Goals signals have no it_track (only avoid, target_company, goal)",
              "it_track" not in data["profile"].get("conversation_signals", {"it_track": 1}))
        tailoring = data.get("tailoring") or {}
        texts = " ".join(i["text"] for i in tailoring.get("items", []))
        check("finished Goals response carries the tailoring summary for the answers given",
              "gentler" in texts and "constant high-pressure deadlines" in texts and "(product-based company)" in texts)
        check("the career ranking after Goals is exactly the quiz's (the answers never move it)",
              [(r["career_path"], r["confidence_pct"]) for r in data["profile"]["career_ranking"]] == quiz_ranking)
        page = client.get("/conversation").get_data(as_text=True)
        check("Goals page: 'Personalise your plan', says the match comes from the quiz, renders the tailoring card",
              "Personalise your plan" in page and "career match still comes from the quiz" in page
              and "tailoringCard(tailoring)" in page and "innerHTML" not in page)
    finally:
        with app.app_context():
            user = User.query.filter_by(email=email).first()
            if user:
                CareerProfile.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()


def test_restart_logout():
    """A login cookie from an earlier server run is dropped (dev), or kept when LOGOUT_ON_RESTART is off."""
    from app import create_app, db
    from app.models import User
    from scripts._csrf import enable_csrf_client

    first = create_app()
    enable_csrf_client(first)
    email = f"restart{random.randint(100000, 999999)}@example.com"
    client = first.test_client()
    try:
        client.post("/signup", json={"username": f"restart_{random.randint(100000, 999999)}", "email": email, "password": PW})
        check("restart: logged out, /profile/data is 401", client.get("/profile/data").status_code == 401)
        client.post("/login", json={"login": email, "password": PW})
        check("restart: after login on the same run, /profile/data is 200", client.get("/profile/data").status_code == 200)
        cookie = client.get_cookie("session").value

        second = create_app()                      # the server was stopped and started again: new boot id
        check("restart: every start gets its own boot id", first.config["BOOT_ID"] != second.config["BOOT_ID"])
        browser = second.test_client()
        browser.set_cookie("session", cookie)      # the same browser, still holding the old cookie
        check("restart: the old cookie no longer logs you in (401 on the API)", browser.get("/profile/data").status_code == 401)
        page = browser.get("/profile")
        check("restart: a page that needs login sends the browser to /login",
              page.status_code == 302 and "/login" in page.headers["Location"])

        third = create_app()
        enable_csrf_client(third)
        fresh = third.test_client()
        fresh.post("/login", json={"login": email, "password": PW})
        check("restart: logging in again on the new run works", fresh.get("/profile/data").status_code == 200)

        # Off (the production default): the cookie keeps working across a restart.
        kept = create_app()
        kept.config["LOGOUT_ON_RESTART"] = False
        browser = kept.test_client()
        browser.set_cookie("session", cookie)
        check("restart: with LOGOUT_ON_RESTART off the old cookie still works", browser.get("/profile/data").status_code == 200)
        from app.config import ProductionConfig
        check("restart: logout-on-restart is on in development and off in production by default",
              create_app().config["LOGOUT_ON_RESTART"] is True and ProductionConfig.LOGOUT_ON_RESTART is False)
    finally:
        with first.app_context():
            user = User.query.filter_by(email=email).first()
            if user:
                db.session.delete(user)
                db.session.commit()


SECTIONS = [test_username_rules, test_routes, test_server_error_page, test_goal_tailoring, test_restart_logout]


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

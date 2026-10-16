"""Code pool for DevOps (dop-2 .. dop-5). Built and checked by scripts/build_code_pools.py."""
from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- dop-2 Swaad Kitchens
_IO_SEMVER = '''
def main():
    data = sys.stdin.read().split("\\n")
    current = data[0].strip()
    n = int(data[1])
    print(next_version(current, data[2:2 + n]))


main()
'''
_SIG_SEMVER = "def next_version(current, messages):"
_DOC_SEMVER = ("current: 'MAJOR.MINOR.PATCH'. messages: commit messages since that release. A message containing "
               "'BREAKING CHANGE', or whose type ends in '!' before the ':' (like 'feat!:'), is a major bump; else any "
               "message starting 'feat' is minor; else any starting 'fix' is patch. Return the new version, or "
               "'no release'.")


def _alt_semver(stdin):
    rows = stdin.split("\n")
    major, minor, patch = map(int, rows[0].strip().split("."))
    n = int(rows[1])
    msgs = rows[2:2 + n]
    level = 0
    for m in msgs:
        head = m.split(":", 1)[0] if ":" in m else ""
        if "BREAKING CHANGE" in m or head.endswith("!"):
            level = max(level, 3)
        elif m.startswith("feat"):
            level = max(level, 2)
        elif m.startswith("fix"):
            level = max(level, 1)
    if level == 3:
        return f"{major + 1}.0.0"
    if level == 2:
        return f"{major}.{minor + 1}.0"
    if level == 1:
        return f"{major}.{minor}.{patch + 1}"
    return "no release"


_MSGS = ["fix: menu prices rounding", "feat: order tracking map", "docs: readme", "chore: bump deps",
         "feat!: new checkout API", "fix(payments): retry UPI callback", "refactor: kitchen queue",
         "feat(menu): veg filter", "test: add cart tests", "fix: BREAKING CHANGE removes v1 endpoint"]


def _gen_semver(rng, size):
    n = {"small": 2, "medium": 5, "large": 10}[size]
    v = f"{rng.randint(0, 3)}.{rng.randint(0, 12)}.{rng.randint(0, 9)}"
    pool = _MSGS if rng.random() < 0.6 else [m for m in _MSGS if "!" not in m and "BREAKING" not in m]
    return f"{v}\n{n}\n" + "\n".join(rng.choice(pool) for _ in range(n)) + "\n"


_IO_CANARY = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    minutes = [tuple(map(int, data[1 + i].split())) for i in range(n)]
    print(canary_decision(minutes))


main()
'''
_SIG_CANARY = "def canary_decision(minutes):"
_DOC_CANARY = ("minutes: list of (baseline requests, baseline errors, canary requests, canary errors) per minute; "
               "baseline requests are always > 0. Using running totals, from the first minute the canary has served "
               "at least 100 requests: if its error rate is above 2 x the baseline rate + 1 percentage point, return "
               "'ROLLBACK at minute m'. Otherwise return 'PROMOTE', or 'WAIT' if the canary never reached 100 "
               "requests.")


def _alt_canary(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    mins = [list(map(int, r.split())) for r in rows[1:1 + n]]
    for m in range(1, n + 1):
        rb = sum(x[0] for x in mins[:m])
        eb = sum(x[1] for x in mins[:m])
        rc = sum(x[2] for x in mins[:m])
        ec = sum(x[3] for x in mins[:m])
        if rc >= 100 and ec / rc - (2 * eb / rb + 0.01) > 1e-12:
            return f"ROLLBACK at minute {m}"
    return "PROMOTE" if sum(x[2] for x in mins) >= 100 else "WAIT"


def _gen_canary(rng, size):
    n = {"small": 3, "medium": 10, "large": 30}[size]
    bad = rng.random() < 0.5
    rows = []
    for _ in range(n):
        rb, rc = rng.randint(200, 600), rng.randint(10, 60)
        eb = sum(rng.random() < 0.01 for _ in range(rb))
        ec = sum(rng.random() < (0.06 if bad else 0.01) for _ in range(rc))
        rows.append(f"{rb} {eb} {rc} {ec}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dop-2"] = [
    {
        "prompt": ("With releases cut from main many times a week, Swaad Kitchens wants version numbers worked out from "
                   "the commit messages (Conventional Commits) instead of argued about. The first line is the current "
                   "version MAJOR.MINOR.PATCH, the second is n, then n commit messages. Complete `next_version`: a message "
                   "containing `BREAKING CHANGE`, or whose type ends in `!` before the colon (like `feat!: ...`), means a "
                   "major release; otherwise any message starting with `feat` means minor; otherwise any starting with "
                   "`fix` means patch. A major bump resets minor and patch to 0, a minor bump resets patch. Print the new "
                   "version, or `no release`."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_SEMVER, stub(_SIG_SEMVER, _DOC_SEMVER, "current")),
        "solution": program(_IO_SEMVER, _SIG_SEMVER + f'''
    """{_DOC_SEMVER}"""
    major, minor, patch = (int(x) for x in current.split("."))
    bump = 0                                       # 0 none, 1 patch, 2 minor, 3 major
    for message in messages:
        kind = message.split(":", 1)[0] if ":" in message else ""
        if "BREAKING CHANGE" in message or kind.endswith("!"):
            bump = 3
        elif message.startswith("feat"):
            bump = max(bump, 2)
        elif message.startswith("fix"):
            bump = max(bump, 1)
    if bump == 3:
        return f"{{major + 1}}.0.0"
    if bump == 2:
        return f"{{major}}.{{minor + 1}}.0"
    if bump == 1:
        return f"{{major}}.{{minor}}.{{patch + 1}}"
    return "no release"
'''),
        "alt": _alt_semver,
        "explanation": ("The release level is the strongest change among the commits, so one pass keeps the maximum. "
                        "Semantic versioning then tells other teams something useful: a major number change warns them "
                        "an API broke. Parsing the numbers as integers matters: 1.9.0 then 1.10.0, not 1.9.1."),
        "key_justification": "Parse version strings and commit prefixes; keep the highest bump.",
        "variants": variants(
            [({}, [("1.4.2\n2\nfix: null pointer\nfeat: upi qr\n", "1.5.0")]),
             ({}, [("0.9.9\n2\nfeat!: drop v1 api\nfix: typo\n", "1.0.0")]),
             ({}, [("2.0.0\n2\ndocs: readme\nchore: deps\n", "no release")])],
            _gen_semver, 5010,
            extra_hidden=[["1.9.0\n1\nfeat(menu): veg filter\n"], ["3.2.1\n1\nfix: BREAKING CHANGE in auth\n"], ["0.0.0\n0\n"]]),
    },
    {
        "prompt": ("Instead of a Friday-night big bang, new versions now go to a small canary first. Decide whether to "
                   "promote it. The first line is n, then n lines per minute `baseline_requests baseline_errors "
                   "canary_requests canary_errors` (baseline requests are always above 0). Complete `canary_decision` "
                   "using running totals: from the first minute the canary has served at least 100 requests, if its "
                   "error rate is above 2 x the baseline error rate plus 1 percentage point, print `ROLLBACK at minute "
                   "m` and stop. Otherwise print PROMOTE, or WAIT if the canary never reached 100 requests. Compare in "
                   "integers, not floats."),
        "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CANARY, stub(_SIG_CANARY, _DOC_CANARY, '"PROMOTE"')),
        "solution": program(_IO_CANARY, _SIG_CANARY + f'''
    """{_DOC_CANARY}"""
    rb = eb = rc = ec = 0
    for minute, (b_req, b_err, c_req, c_err) in enumerate(minutes, 1):
        rb, eb, rc, ec = rb + b_req, eb + b_err, rc + c_req, ec + c_err
        # ec/rc > 2*eb/rb + 1/100   <=>   100*ec*rb > 200*eb*rc + rb*rc   (all counts positive)
        if rc >= 100 and 100 * ec * rb > 200 * eb * rc + rb * rc:
            return f"ROLLBACK at minute {{minute}}"
    return "PROMOTE" if rc >= 100 else "WAIT"
'''),
        "alt": _alt_canary,
        "explanation": ("Running totals over the minutes give the cumulative error rates; waiting for 100 canary "
                        "requests avoids judging on a handful of calls. Comparing against the baseline at the same time "
                        "separates a bad release from a bad hour. Cross-multiplying keeps the comparison exact."),
        "key_justification": "Cumulative rates over an array with an exact integer comparison.",
        "variants": variants(
            [({}, [("3\n100 1 20 0\n100 1 50 2\n100 2 40 3\n", "ROLLBACK at minute 3")]),
             ({}, [("2\n1000 10 60 1\n1000 10 60 1\n", "PROMOTE")]),
             ({}, [("2\n500 0 30 5\n500 0 30 5\n", "WAIT")])],
            _gen_canary, 5020,
            extra_hidden=[["1\n100 0 100 1\n"], ["1\n100 0 100 2\n"], ["2\n100 50 100 99\n100 50 100 99\n"]]),
    },
]

# ---------------------------------------------------------------- dop-3 Rail Yatra Info
_IO_FLAKY = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    runs = [tuple(data[1 + i].split()) for i in range(n)]
    flaky = find_flaky(runs)
    if not flaky:
        print("NONE")
    for test, rate in flaky:
        print(test, f"{rate}%")


main()
'''
_SIG_FLAKY = "def find_flaky(runs):"
_DOC_FLAKY = ("runs: list of (commit, test, PASS or FAIL). A test is flaky if it both passed and failed on the SAME "
              "commit. Return [(test, fail rate over all its runs as a whole percent rounded down)] sorted by test.")


def _alt_flaky(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for t in sorted({r[1] for r in rows}):
        mine = [r for r in rows if r[1] == t]
        flaky = any({"PASS", "FAIL"} <= {r[2] for r in mine if r[0] == c} for c in {r[0] for r in mine})
        if flaky:
            out.append(f"{t} {100 * sum(r[2] == 'FAIL' for r in mine) // len(mine)}%")
    return "\n".join(out) or "NONE"


def _gen_flaky(rng, size):
    n = {"small": 8, "medium": 30, "large": 60}[size]
    tests = ["t_login", "t_search", "t_pnr", "t_live", "t_alerts", "t_api"]
    flaky = rng.choice(tests)
    rows = []
    for _ in range(n):
        t = rng.choice(tests)
        res = ("FAIL" if rng.random() < 0.2 else "PASS") if t == flaky else ("FAIL" if rng.random() < 0.05 else "PASS")
        rows.append(f"c{rng.randint(1, 4)} {t} {res}")
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_CPATH = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    stages = {}
    for i in range(n):
        name, minutes, deps = data[1 + i].split()
        stages[name] = (int(minutes), [] if deps == "-" else deps.split(","))
    schedule, total = earliest_schedule(stages)
    for name, start, finish in schedule:
        print(name, start, finish)
    print("total", total)


main()
'''
_SIG_CPATH = "def earliest_schedule(stages):"
_DOC_CPATH = ("stages: {name: (minutes, [stages it needs first])}, a DAG; unlimited runners. A stage starts when all "
              "its prerequisites have finished (at 0 if it has none). Return ([(name, start, finish)] sorted by name, "
              "the time the whole pipeline finishes).")


def _alt_cpath(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    st = {}
    for r in rows[1:1 + n]:
        nm, mi, d = r.split()
        st[nm] = (int(mi), [] if d == "-" else d.split(","))
    finish = {}
    while len(finish) < n:
        for nm, (mi, deps) in st.items():
            if nm not in finish and all(d in finish for d in deps):
                finish[nm] = max([finish[d] for d in deps] or [0]) + mi
    out = [f"{nm} {finish[nm] - st[nm][0]} {finish[nm]}" for nm in sorted(st)]
    return "\n".join(out + [f"total {max(finish.values())}"])


_STAGES = ["checkout", "deps", "lint", "build", "unit", "integration", "e2e", "image", "scan", "package", "docs"]


def _gen_cpath(rng, size):
    n = {"small": 4, "medium": 7, "large": 11}[size]
    names = _STAGES[:n]
    rows = []
    for i, nm in enumerate(names):
        deps = rng.sample(names[:i], rng.randint(1, min(2, i))) if i else []
        rows.append(f"{nm} {rng.randint(1, 15)} {','.join(deps) or '-'}")
    rng.shuffle(rows)
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dop-3"] = [
    {
        "prompt": ("One test fails about one run in ten and developers just press rerun. Find the flaky tests from CI "
                   "history. The first line is n, then n lines `commit test result` (PASS or FAIL). Complete "
                   "`find_flaky`: a test is flaky if it both passed and failed on the same commit (the code did not "
                   "change, yet the result did). A test that fails on one commit and passes on a later one is not "
                   "flaky; it was fixed. The program prints `test rate%` (the test's fail rate over all its runs, rounded "
                   "down) for each flaky test, sorted by name, or NONE."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_FLAKY, stub(_SIG_FLAKY, _DOC_FLAKY, "[]")),
        "solution": program(_IO_FLAKY, _SIG_FLAKY + f'''
    """{_DOC_FLAKY}"""
    outcomes, runs_of, fails_of = {{}}, {{}}, {{}}
    for commit, test, result in runs:
        outcomes.setdefault((test, commit), set()).add(result)
        runs_of[test] = runs_of.get(test, 0) + 1
        fails_of[test] = fails_of.get(test, 0) + (result == "FAIL")
    flaky = {{test for (test, _), seen in outcomes.items() if len(seen) == 2}}
    return [(t, 100 * fails_of[t] // runs_of[t]) for t in sorted(flaky)]
'''),
        "alt": _alt_flaky,
        "explanation": ("Grouping results by (test, commit) in a dictionary of sets shows whether one unchanged commit "
                        "produced both outcomes, which is the definition of flaky. Rerunning hides the problem and "
                        "teaches the team to ignore red builds; listing flaky tests with their fail rate lets them be "
                        "quarantined and fixed."),
        "key_justification": "Group results by (test, commit) to separate flaky from broken.",
        "variants": variants(
            [({}, [("5\nc1 t_login PASS\nc1 t_login FAIL\nc2 t_pay FAIL\nc3 t_pay PASS\nc1 t_search PASS\n", "t_login 50%")]),
             ({}, [("3\nc9 t_a FAIL\nc9 t_a FAIL\nc9 t_a FAIL\n", "NONE")]),
             ({}, [("4\nc1 b PASS\nc1 b FAIL\nc2 b PASS\nc1 a FAIL\n", "b 33%")])],
            _gen_flaky, 5110,
            extra_hidden=[["0\n"], ["2\nx t PASS\nx t FAIL\n"], ["4\nc1 z FAIL\nc1 z PASS\nc1 y PASS\nc1 y FAIL\n"]]),
    },
    {
        "prompt": ("The CI pipeline takes 45 minutes. Before buying faster machines, find out where the time goes when "
                   "independent stages run in parallel. The first line is n, then n lines `stage minutes deps` (deps "
                   "comma-separated, or -). Complete `earliest_schedule`, assuming unlimited runners: a stage starts as "
                   "soon as all its prerequisites have finished (at minute 0 if it has none). The program prints `stage "
                   "start finish` for every stage, sorted by name, then `total T`, the minute the whole pipeline "
                   "finishes (the critical path)."),
        "ds_topic": "graph", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CPATH, stub(_SIG_CPATH, _DOC_CPATH, "[], 0")),
        "solution": program(_IO_CPATH, _SIG_CPATH + f'''
    """{_DOC_CPATH}"""
    finish = {{}}

    def done_at(name):                       # memoised depth-first search over prerequisites
        if name not in finish:
            minutes, deps = stages[name]
            finish[name] = max((done_at(d) for d in deps), default=0) + minutes
        return finish[name]

    for name in stages:
        done_at(name)
    schedule = [(n, finish[n] - stages[n][0], finish[n]) for n in sorted(stages)]
    return schedule, max(finish.values())
'''),
        "alt": _alt_cpath,
        "explanation": ("Each stage's earliest finish is its own duration plus the latest finish among its "
                        "prerequisites, a longest-path calculation on the DAG done with memoised recursion. The total is "
                        "the critical path: speeding up any stage off that path saves nothing, so this shows exactly "
                        "which stages are worth optimising or splitting."),
        "key_justification": "Longest path (critical path) in a DAG with memoisation.",
        "variants": variants(
            [({}, [("6\ncheckout 2 -\nbuild 10 checkout\nunit 8 build\nlint 3 checkout\ne2e 15 build\npackage 4 unit,lint,e2e\n",
                    "build 2 12\ncheckout 0 2\ne2e 12 27\nlint 2 5\npackage 27 31\nunit 12 20\ntotal 31")]),
             ({}, [("3\na 5 -\nb 5 -\nc 1 a,b\n", "a 0 5\nb 0 5\nc 5 6\ntotal 6")]),
             ({}, [("1\nonly 9 -\n", "only 0 9\ntotal 9")])],
            _gen_cpath, 5120,
            extra_hidden=[["2\nb 1 a\na 1 -\n"], ["4\nd 1 b,c\nb 10 a\nc 2 a\na 1 -\n"], ["3\nx 0 -\ny 0 x\nz 7 y\n"]]),
    },
]

# ---------------------------------------------------------------- dop-4 Sampark Telecom
_IO_BUDGET = '''
def main():
    data = sys.stdin.read().split("\\n")
    slo = data[0].strip()
    n = int(data[1])
    days = [tuple(map(int, data[2 + i].split())) for i in range(n)]
    allowed, used_pct, freeze = error_budget(slo, days)
    print("allowed", allowed)
    print("used", format(used_pct, ".1f") + "%")
    print("status", "FREEZE" if freeze else "OK")


main()
'''
_SIG_BUDGET = "def error_budget(slo, days):"
_DOC_BUDGET = ("slo: availability target as text with up to 2 decimals, below 100 (like '99.9'). days: list of "
               "(requests, failed). The budget is total requests x (100 - slo) / 100 failures. Return (budget rounded "
               "down to a whole number, percent of the budget used, True if failures have reached the budget).")


def _alt_budget(stdin):
    rows = stdin.split("\n")
    whole, _, frac = rows[0].strip().partition(".")
    bp = int(whole) * 100 + int((frac + "00")[:2])          # basis points of availability
    n = int(rows[1])
    d = [list(map(int, r.split())) for r in rows[2:2 + n]]
    total = sum(x[0] for x in d)
    failed = sum(x[1] for x in d)
    allowed_num = total * (10000 - bp)                      # budget x 10000
    used = 100 * failed * 10000 / allowed_num
    return (f"allowed {allowed_num // 10000}\nused {format(used, '.1f')}%\n"
            f"status {'FREEZE' if failed * 10000 >= allowed_num else 'OK'}")


def _gen_budget(rng, size):
    n = {"small": 3, "medium": 15, "large": 30}[size]
    slo = rng.choice(["99.9", "99.5", "99", "99.95"])
    rows = []
    for _ in range(n):
        req = rng.randint(200000, 900000)
        rows.append(f"{req} {int(req * rng.choice([0.0002, 0.0005, 0.001, 0.003]))}")
    return f"{slo}\n{n}\n" + "\n".join(rows) + "\n"


_IO_ALERTS = '''
def main():
    data = sys.stdin.read().split("\\n")
    window = int(data[0])
    n = int(data[1])
    alerts = []
    for i in range(n):
        second, name = data[2 + i].split()
        alerts.append((int(second), name))
    total, per_name = group_alerts(alerts, window)
    print("incidents", total)
    for name, raw, incidents in per_name:
        print(name, raw, incidents)


main()
'''
_SIG_ALERTS = "def group_alerts(alerts, window):"
_DOC_ALERTS = ("alerts: list of (second, alert name) in time order. An alert opens a new incident for its name unless "
               "an incident for that name was opened less than `window` seconds earlier; otherwise it joins that "
               "incident. Return (total incidents, [(name, raw alerts, incidents)] by raw alerts high to low, ties by "
               "name).")


def _alt_alerts(stdin):
    rows = stdin.split("\n")
    w = int(rows[0])
    n = int(rows[1])
    al = [r.split() for r in rows[2:2 + n]]
    stats = []
    for nm in sorted({x[1] for x in al}):
        times = [int(t) for t, x in al if x == nm]
        opened = []
        for t in times:
            if not opened or t - opened[-1] >= w:
                opened.append(t)
        stats.append((nm, len(times), len(opened)))
    stats.sort(key=lambda s: s[1], reverse=True)
    return "\n".join([f"incidents {sum(s[2] for s in stats)}"] + [f"{a} {b} {c}" for a, b, c in stats])


def _gen_alerts(rng, size):
    n = {"small": 6, "medium": 30, "large": 70}[size]
    names = ["disk_full", "cpu_high", "pod_restart", "latency_p99", "cert_expiry"]
    t, rows = 0, []
    for _ in range(n):
        t += rng.choice([5, 20, 60, 200, 900])
        rows.append(f"{t} {rng.choices(names, weights=[5, 4, 3, 2, 1])[0]}")
    return f"{rng.choice([300, 600, 1800])}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dop-4"] = [
    {
        "prompt": ("Sampark's portal promises 99.9% availability a month; the 0.1% left over is the error budget, and "
                   "once it is spent, risky releases pause. The first line is the SLO (like 99.9, up to two decimals), "
                   "the second is n, then n lines per day `requests failed`. Complete `error_budget`: the budget is "
                   "total requests x (100 - SLO) / 100 failed requests. The program prints `allowed` (the budget rounded "
                   "down), `used x%` (failures as a percent of the budget, one decimal) and `status FREEZE` if failures "
                   "have reached the budget, else `status OK`. Parse the SLO without float rounding."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_BUDGET, stub(_SIG_BUDGET, _DOC_BUDGET, "0, 0.0, False")),
        "solution": program(_IO_BUDGET, _SIG_BUDGET + f'''
    """{_DOC_BUDGET}"""
    whole, _, frac = slo.partition(".")
    slo_bp = int(whole) * 100 + int((frac + "00")[:2])      # '99.9' -> 9990 hundredths of a percent
    total = sum(r for r, _ in days)
    failed = sum(f for _, f in days)
    budget_x10000 = total * (10000 - slo_bp)               # the budget, times 10000, exact
    used_pct = 100 * failed * 10000 / budget_x10000
    return budget_x10000 // 10000, used_pct, failed * 10000 >= budget_x10000
'''),
        "alt": _alt_budget,
        "explanation": ("Summing the days gives the month so far; the budget is the failures the SLO allows. Working in "
                        "hundredths of a percent keeps 99.9 exact (0.1% of 3,000,000 is exactly 3,000). Tying release "
                        "pace to the remaining budget turns 'move fast versus stay stable' into a number both sides "
                        "agreed in advance."),
        "key_justification": "Error budget arithmetic over summed daily counts.",
        "variants": variants(
            [({}, [("99.9\n2\n1000000 300\n2000000 500\n", "allowed 3000\nused 26.7%\nstatus OK")]),
             ({}, [("99.5\n1\n10000 50\n", "allowed 50\nused 100.0%\nstatus FREEZE")]),
             ({}, [("99\n2\n500 1\n500 2\n", "allowed 10\nused 30.0%\nstatus OK")])],
            _gen_budget, 5210,
            extra_hidden=[["99.99\n1\n100000 11\n"], ["99.9\n1\n999 0\n"], ["95\n1\n20 1\n"]]),
    },
    {
        "prompt": ("The on-call engineer gets about 200 alerts a week, mostly repeats of the same few problems. Group "
                   "them to see the real number of incidents. The first line is the window w in seconds, the second is "
                   "n, then n alerts `second name` in time order. Complete `group_alerts`: an alert opens a new incident "
                   "for its name unless that name already opened an incident less than w seconds earlier, in which case "
                   "it joins it. The program prints `incidents total`, then `name raw incidents` per alert name, most "
                   "raw alerts first, ties by name."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_ALERTS, stub(_SIG_ALERTS, _DOC_ALERTS, "0, []")),
        "solution": program(_IO_ALERTS, _SIG_ALERTS + f'''
    """{_DOC_ALERTS}"""
    opened_at, raw, incidents = {{}}, {{}}, {{}}
    for second, name in alerts:
        raw[name] = raw.get(name, 0) + 1
        if name not in opened_at or second - opened_at[name] >= window:
            opened_at[name] = second                     # a new incident opens
            incidents[name] = incidents.get(name, 0) + 1
    per_name = sorted(((n, raw[n], incidents[n]) for n in raw), key=lambda r: (-r[1], r[0]))
    return sum(incidents.values()), per_name
'''),
        "alt": _alt_alerts,
        "explanation": ("Remembering when each alert name last opened an incident (a dictionary) folds repeats into one "
                        "incident in a single pass. Ranking names by raw volume shows which alerts generate noise, "
                        "which are the first candidates to tune, merge or delete."),
        "key_justification": "Time-window de-duplication keyed by alert name.",
        "variants": variants(
            [({}, [("300\n4\n0 disk_full\n50 cpu_high\n100 disk_full\n400 disk_full\n", "incidents 3\ndisk_full 3 2\ncpu_high 1 1")]),
             ({}, [("60\n3\n0 a\n59 a\n60 a\n", "incidents 2\na 3 2")]),
             ({}, [("10\n2\n5 x\n5 y\n", "incidents 2\nx 1 1\ny 1 1")])],
            _gen_alerts, 5220,
            extra_hidden=[["100\n0\n"], ["1\n3\n0 z\n1 z\n2 z\n"], ["500\n4\n0 b\n10 a\n20 b\n30 a\n"]]),
    },
]

# ---------------------------------------------------------------- dop-5 Bharat Bima
_IO_DORA = '''
def main():
    data = sys.stdin.read().split("\\n")
    weeks = int(data[0])
    n = int(data[1])
    deploys = [data[2 + i].split()[1] for i in range(n)]
    m = int(data[2 + n])
    incidents = [tuple(map(int, data[3 + n + i].split())) for i in range(m)]
    per_week, cfr, mttr = dora(weeks, deploys, incidents)
    print("deploys_per_week", format(per_week, ".1f"))
    print("change_failure_rate", format(cfr, ".1f") + "%")
    print("mttr", "-" if mttr is None else format(mttr, ".1f") + " min")


main()
'''
_SIG_DORA = "def dora(weeks, deploys, incidents):"
_DOC_DORA = ("deploys: one result per deployment, 'ok' or 'fail'. incidents: list of (start minute, end minute). "
             "Return (deployments per week, percent of deployments that failed or 0 if none, mean minutes to restore "
             "or None if no incidents).")


def _alt_dora(stdin):
    rows = stdin.split("\n")
    w = int(rows[0])
    n = int(rows[1])
    dep = [rows[2 + i].split()[1] for i in range(n)]
    m = int(rows[2 + n])
    inc = [list(map(int, rows[3 + n + i].split())) for i in range(m)]
    cfr = 100 * dep.count("fail") / len(dep) if dep else 0.0
    mttr = "-" if not inc else format(sum(e - s for s, e in inc) / len(inc), ".1f") + " min"
    return (f"deploys_per_week {format(len(dep) / w, '.1f')}\nchange_failure_rate {format(cfr, '.1f')}%\nmttr {mttr}")


def _gen_dora(rng, size):
    w = {"small": 1, "medium": 4, "large": 12}[size]
    n = rng.randint(0, 6 * w)
    deps = [f"{rng.randint(1, 7 * w)} {'fail' if rng.random() < 0.15 else 'ok'}" for _ in range(n)]
    m = rng.randint(0, 4)
    inc = []
    for _ in range(m):
        s = rng.randint(0, 10000)
        inc.append(f"{s} {s + rng.randint(5, 240)}")
    return f"{w}\n{n}\n" + "\n".join(deps) + ("\n" if deps else "") + f"{m}\n" + "\n".join(inc) + "\n"


_IO_SECRETS = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    findings = scan(data[1:1 + n])
    if not findings:
        print("CLEAN")
    for line_no, kind in findings:
        print("line", line_no, kind)


main()
'''
_SIG_SECRETS = "def scan(lines):"
_DOC_SECRETS = ("Return [(line number from 1, kind)] in line order; on one line check aws_key, then private_key, then "
                "password. aws_key: 'AKIA' followed by 16 characters that are capital letters or digits. private_key: "
                "the line contains '-----BEGIN' and 'PRIVATE KEY-----'. password: 'password' (any case) followed, "
                "after optional spaces, by '=' or ':' and a value that, with spaces and quote marks trimmed, is not "
                "empty and does not start with '${', 'os.environ', 'process.env' or 'getenv'.")


def _alt_secrets(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out = []
    ok = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    for no, ln in enumerate(rows[1:1 + n], 1):
        start = 0
        while True:
            i = ln.find("AKIA", start)
            if i < 0:
                break
            tail = ln[i + 4:i + 20]
            if len(tail) == 16 and all(c in ok for c in tail):
                out.append(f"line {no} aws_key")
                break
            start = i + 1
        if "-----BEGIN" in ln and "PRIVATE KEY-----" in ln:
            out.append(f"line {no} private_key")
        low = ln.lower()
        j = low.find("password")
        if j >= 0:
            rest = ln[j + 8:].lstrip(" ")
            if rest[:1] in ("=", ":"):
                value = rest[1:].strip(" '\"")
                if value and not value.startswith(("${", "os.environ", "process.env", "getenv")):
                    out.append(f"line {no} password")
    return "\n".join(out) or "CLEAN"


_DIFF_LINES = ['aws_key = "AKIAIOSFODNN7EXAMPLE"', "DB_PASSWORD=${DB_PASSWORD}", 'password: "hunter2"',
               "-----BEGIN RSA PRIVATE KEY-----", 'print("hello")', "PASSWORD = os.environ['DB_PASS']",
               "key_id = AKIA1234", "const pwd = 'abc'", "password=", "Password : 'claims@2026'",
               "token = process.env.TOKEN", "# rotate AKIAABCDEFGHIJKLMNOP soon", "-----BEGIN PUBLIC KEY-----"]


def _gen_secrets(rng, size):
    n = {"small": 4, "medium": 12, "large": 30}[size]
    return f"{n}\n" + "\n".join(rng.choice(_DIFF_LINES) for _ in range(n)) + "\n"


PROBLEMS["dop-5"] = [
    {
        "prompt": ("Leadership wants delivery measured with the DORA metrics instead of by feel. The first line is the "
                   "number of weeks, the second is n, then n deployments `day result` (ok or fail); then m, then m "
                   "incidents `start_minute end_minute`. Complete `dora`. The program prints `deploys_per_week` (one "
                   "decimal), `change_failure_rate x%` (failed deployments as a percent, 0.0 if there were none) and "
                   "`mttr x min`, the mean minutes to restore service (one decimal), or `mttr -` with no incidents."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_DORA, stub(_SIG_DORA, _DOC_DORA, "0.0, 0.0, None")),
        "solution": program(_IO_DORA, _SIG_DORA + f'''
    """{_DOC_DORA}"""
    per_week = len(deploys) / weeks
    cfr = 100 * deploys.count("fail") / len(deploys) if deploys else 0.0
    mttr = sum(end - start for start, end in incidents) / len(incidents) if incidents else None
    return per_week, cfr, mttr
'''),
        "alt": _alt_dora,
        "explanation": ("Each metric is a simple ratio over the lists, but the edge cases matter: no deployments must "
                        "not divide by zero, and no incidents means MTTR is undefined, not 0. Tracking speed (frequency) "
                        "together with stability (failure rate, restore time) stops a team from improving one by "
                        "quietly sacrificing the other."),
        "key_justification": "Aggregate ratios over arrays with safe empty cases.",
        "variants": variants(
            [({}, [("2\n4\n1 ok\n3 fail\n8 ok\n10 ok\n2\n100 160\n200 230\n",
                    "deploys_per_week 2.0\nchange_failure_rate 25.0%\nmttr 45.0 min")]),
             ({}, [("1\n0\n0\n", "deploys_per_week 0.0\nchange_failure_rate 0.0%\nmttr -")]),
             ({}, [("3\n2\n1 fail\n2 fail\n1\n0 7\n", "deploys_per_week 0.7\nchange_failure_rate 100.0%\nmttr 7.0 min")])],
            _gen_dora, 5310,
            extra_hidden=[["4\n1\n1 ok\n0\n"], ["1\n3\n1 ok\n1 ok\n1 fail\n1\n10 10\n"], ["2\n0\n1\n5 125\n"]]),
    },
    {
        "prompt": ("A database password reached the claims repository last quarter. Add a secret scan to the pipeline. "
                   "The first line is n, then n added lines from a diff. Complete `scan` and report, in line order (and on "
                   "one line in this order): `aws_key` for `AKIA` followed by 16 capital letters or digits; "
                   "`private_key` for a line containing `-----BEGIN` and `PRIVATE KEY-----`; `password` for the word "
                   "password (any case) followed, after optional spaces, by `=` or `:` and a value that, with spaces and "
                   "quote marks trimmed, is not empty and does not start with `${`, `os.environ`, `process.env` or "
                   "`getenv` (those read the secret from the environment, which is fine). The program prints `line N "
                   "kind` per finding, or CLEAN."),
        "ds_topic": "string", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_SECRETS, stub(_SIG_SECRETS, _DOC_SECRETS, "[]")),
        "solution": "import re\n" + program(_IO_SECRETS, _SIG_SECRETS + f'''
    """{_DOC_SECRETS}"""
    aws = re.compile(r"AKIA[A-Z0-9]{{16}}")
    password = re.compile(r"password *[=:](.*)", re.IGNORECASE)
    safe = ("${{", "os.environ", "process.env", "getenv")
    findings = []
    for number, line in enumerate(lines, 1):
        if aws.search(line):
            findings.append((number, "aws_key"))
        if "-----BEGIN" in line and "PRIVATE KEY-----" in line:
            findings.append((number, "private_key"))
        found = password.search(line)
        if found:
            value = found.group(1).strip(" '\\"")
            if value and not value.startswith(safe):
                findings.append((number, "password"))
    return findings
'''),
        "alt": _alt_secrets,
        "explanation": ("Each rule is a small pattern: a fixed prefix plus a character class and length for AWS keys, "
                        "fixed markers for key files, and 'password = value' with an allow-list for values read from "
                        "the environment. Running it on every change stops a secret before it reaches history, where "
                        "deleting it later no longer helps; a leaked key must be rotated."),
        "key_justification": "Pattern matching on diff lines (regular expressions).",
        "variants": variants(
            [({}, [('5\naws_key = "AKIAIOSFODNN7EXAMPLE"\nDB_PASSWORD=${DB_PASSWORD}\npassword: "hunter2"\n'
                    '-----BEGIN RSA PRIVATE KEY-----\nprint("hello")\n',
                    "line 1 aws_key\nline 3 password\nline 4 private_key")]),
             ({}, [("2\nPASSWORD = os.environ['DB_PASS']\nkey_id = AKIA1234\n", "CLEAN")]),
             ({}, [("2\nPassword : 'claims@2026'\npassword=\n", "line 1 password")])],
            _gen_secrets, 5320,
            extra_hidden=[["1\n-----BEGIN PUBLIC KEY-----\n"], ["1\nx AKIAABCDEFGHIJKLMNOP password=1\n"], ["1\nmy_password = getenv('P')\n"]]),
    },
]

"""Code pool for QA & Test Automation (qat-2 .. qat-5). Built and checked by scripts/build_code_pools.py."""
import json

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- qat-2 Saral Tax
_IO_BVA = '''
def main():
    limits = list(map(int, sys.stdin.read().split()))
    print(" ".join(map(str, boundary_values(limits))))


main()
'''
_SIG_BVA = "def boundary_values(limits):"
_DOC_BVA = ("limits: the upper limits of the income slabs, in any order. Return the test incomes for boundary value "
            "analysis: 0, and for every limit b the values b - 1, b and b + 1 (never below 0), sorted, each once.")


def _alt_bva(stdin):
    lim = [int(x) for x in stdin.split()]
    vals = {0}
    for b in lim:
        for v in (b - 1, b, b + 1):
            if v >= 0:
                vals.add(v)
    return " ".join(map(str, sorted(vals)))


def _gen_bva(rng, size):
    n = {"small": 2, "medium": 5, "large": 9}[size]
    lim = rng.sample([0, 1, 250000, 300000, 500000, 700000, 1000000, 1200000, 1500000, 2400000], n)
    return " ".join(map(str, lim)) + "\n"


_IO_TAX = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    slabs = []
    for i in range(n):
        limit, rate = data[1 + i].split()
        slabs.append((None if limit == "inf" else int(limit), int(rate)))
    m = int(data[1 + n])
    for i in range(m):
        income = int(data[2 + n + i])
        print(income, tax_due(slabs, income))


main()
'''
_SIG_TAX = "def tax_due(slabs, income):"
_DOC_TAX = ("slabs: (upper limit, rate %) in increasing order; the last limit is None (no upper limit). Each slab taxes "
            "only the part of the income inside it. Return the tax in whole rupees, rounded down.")


def _alt_tax(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    sl = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    out = []
    for r in rows[2 + n:2 + n + m]:
        inc = int(r)
        paise = 0
        lower = 0
        for lim, rate in sl:
            upper = inc if lim == "inf" else min(inc, int(lim))
            if upper > lower:
                paise += (upper - lower) * int(rate)
            lower = int(lim) if lim != "inf" else lower
        out.append(f"{inc} {paise // 100}")
    return "\n".join(out)


def _gen_tax(rng, size):
    slabs = "4\n300000 0\n700000 5\n1000000 10\ninf 15\n" if rng.random() < 0.5 else \
        "6\n400000 0\n800000 5\n1200000 10\n1600000 15\n2000000 20\ninf 30\n"
    m = {"small": 3, "medium": 8, "large": 20}[size]
    incomes = [rng.choice([0, 1, 299999, 300000, 300001, 400000, 700001, 1234567, 1600000, 2500000, rng.randint(0, 3000000)])
               for _ in range(m)]
    return slabs + f"{m}\n" + "\n".join(map(str, incomes)) + "\n"


PROBLEMS["qat-2"] = [
    {
        "prompt": ("Tax bugs hide at slab edges: an income exactly at a limit is taxed by the wrong slab. Boundary value "
                   "analysis tests just below, at and just above every edge. The input is one line with the slab upper "
                   "limits, in any order. Complete `boundary_values`: return 0 plus, for each limit b, the values b - 1, "
                   "b and b + 1 (never below 0), each once and sorted. The program prints them on one line."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_BVA, stub(_SIG_BVA, _DOC_BVA, "sorted(limits)")),
        "solution": program(_IO_BVA, _SIG_BVA + f'''
    """{_DOC_BVA}"""
    values = {{0}}
    for b in limits:
        values.update(v for v in (b - 1, b, b + 1) if v >= 0)
    return sorted(values)
'''),
        "alt": _alt_bva,
        "explanation": ("Errors cluster at boundaries (a < written where <= was meant), so three values around each edge "
                        "catch them with very few tests. A set removes overlaps when two limits are close, and sorting "
                        "makes the list easy to review and to turn into a data-driven test."),
        "key_justification": "Boundary value analysis: generate, de-duplicate and sort test inputs.",
        "variants": variants(
            [({}, [("700000 300000\n", "0 299999 300000 300001 699999 700000 700001")]),
             ({}, [("1\n", "0 1 2")]),
             ({}, [("10 11\n", "0 9 10 11 12")])],
            _gen_bva, 10010,
            extra_hidden=[["0\n"], ["5 5\n"], ["2400000 250000 1500000\n"]]),
    },
    {
        "prompt": ("An automated test needs an oracle: an independent way to know the right answer. Write the tax oracle "
                   "for Saral Tax. The first line is n, then n slabs `limit rate` in increasing order (rate is a whole "
                   "percent; the last limit is `inf`); then m, then m incomes in rupees. Complete `tax_due`: each slab "
                   "taxes only the part of the income that falls inside it (this is not a flat rate on the whole "
                   "income). Work in integers and round the tax down to whole rupees. The program prints `income tax` per "
                   "income."),
        "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_TAX, stub(_SIG_TAX, _DOC_TAX, "0")),
        "solution": program(_IO_TAX, _SIG_TAX + f'''
    """{_DOC_TAX}"""
    paise, lower = 0, 0
    for limit, rate in slabs:
        upper = income if limit is None else min(income, limit)
        if upper > lower:
            paise += (upper - lower) * rate        # rupees x percent = paise
        if limit is None or income <= limit:
            break
        lower = limit
    return paise // 100
'''),
        "alt": _alt_tax,
        "explanation": ("Walking the slabs in order and taxing only the slice inside each one is progressive taxation; "
                        "rupees x percent is exactly paise, so integer arithmetic avoids rounding drift. A test suite "
                        "then compares the website's answer for the boundary incomes with this oracle."),
        "key_justification": "Slab-wise accumulation over an ordered array (a test oracle).",
        "variants": variants(
            [({}, [("4\n300000 0\n700000 5\n1000000 10\ninf 15\n3\n250000\n700000\n1200000\n",
                    "250000 0\n700000 20000\n1200000 80000")]),
             ({}, [("2\n100 0\ninf 10\n2\n100\n101\n", "100 0\n101 0")]),
             ({}, [("2\n1000 1\ninf 50\n1\n2999\n", "2999 1009")])],
            _gen_tax, 10020,
            extra_hidden=[["1\ninf 7\n1\n0\n"], ["3\n10 0\n20 10\ninf 20\n1\n35\n"], ["2\n1 100\ninf 0\n1\n50\n"]]),
    },
]

# ---------------------------------------------------------------- qat-3 Ghumakkad Travels
_IO_TRIAGE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for count, message in group_failures(data[1:1 + n]):
        print(count, message)


main()
'''
_SIG_TRIAGE = "def group_failures(messages):"
_DOC_TRIAGE = ("Normalise each failure message: replace every part in single or double quotes with S, then every run of "
               "digits with N. Return [(count, normalised message)] for each distinct one, most frequent first, ties "
               "by message.")


def _normalise_alt(m):
    out, i = [], 0
    while i < len(m):
        c = m[i]
        if c in "'\"":
            j = m.find(c, i + 1)
            if j != -1:
                out.append("S")
                i = j + 1
                continue
        if c.isdigit():
            while i < len(m) and m[i].isdigit():
                i += 1
            out.append("N")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _alt_triage(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    c = {}
    for m in rows[1:1 + n]:
        k = _normalise_alt(m)
        c[k] = c.get(k, 0) + 1
    items = sorted(c.items(), key=lambda kv: kv[0])
    items.sort(key=lambda kv: kv[1], reverse=True)
    return "\n".join(f"{v} {k}" for k, v in items)


_FAILS = ["Timeout after {n} ms waiting for '#pay-btn'", "Element 'Book now' not found", "Expected {n} rooms but got {n}",
          "Timeout after {n} ms waiting for \"#search\"", "Element 'Confirm' not found", "HTTP {n} from /api/hotels/{n}",
          "Date mismatch: expected '2026-{n}-01' got '2026-{n}-02'"]


def _gen_triage(rng, size):
    n = {"small": 4, "medium": 15, "large": 35}[size]
    rows = [rng.choice(_FAILS).replace("{n}", str(rng.randint(1, 5000)), 1).replace("{n}", str(rng.randint(1, 99)))
            for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_ORDER = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    steps = [tuple(data[1 + i].split()) for i in range(n)]
    pairs = hidden_dependencies(steps)
    if not pairs:
        print("ISOLATED")
    for reader, writer, key in pairs:
        print(reader, "<-", writer, key)


main()
'''
_SIG_ORDER = "def hidden_dependencies(steps):"
_DOC_ORDER = ("steps: (test, READ or WRITE, key) in run order. A test depends on another when it READs a key whose "
              "latest write came from a different test and it has not written that key itself earlier. Return the "
              "distinct (reader, writer, key) triples, sorted.")


def _alt_order(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = set()
    for i, (t, op, k) in enumerate(rows):
        if op != "READ":
            continue
        writes = [r for r in rows[:i] if r[1] == "WRITE" and r[2] == k]
        own = any(r[0] == t for r in writes)
        if writes and writes[-1][0] != t and not own:
            out.add((t, writes[-1][0], k))
    return "\n".join(f"{a} <- {b} {c}" for a, b, c in sorted(out)) or "ISOLATED"


def _gen_order(rng, size):
    tests = ["login_test", "search_test", "booking_test", "payment_test", "refund_test", "profile_test"]
    keys = ["session", "cart", "booking_id", "wallet"]
    n = {"small": 6, "medium": 20, "large": 45}[size]
    rows = [f"{rng.choice(tests)} {rng.choice(['READ', 'WRITE'])} {rng.choice(keys)}" for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["qat-3"] = [
    {
        "prompt": ("1,400 tests fail in so many slightly different ways that nobody reads the failures any more. Group "
                   "them. The first line is n, then n failure messages. Complete `group_failures`: replace every quoted "
                   "part ('...' or \"...\") with S, then every run of digits with N, so `Timeout after 3000 ms` and "
                   "`Timeout after 5000 ms` become the same. The program prints `count message` for each distinct "
                   "normalised message, most frequent first, ties by message."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_TRIAGE, stub(_SIG_TRIAGE, _DOC_TRIAGE, "[(1, m) for m in messages]")),
        "solution": "import re\n" + program(_IO_TRIAGE, _SIG_TRIAGE + f'''
    """{_DOC_TRIAGE}"""
    counts = {{}}
    for message in messages:
        shape = re.sub(r"'[^']*'|\\"[^\\"]*\\"", "S", message)     # quoted selectors, names, dates
        shape = re.sub(r"\\d+", "N", shape)                         # timings, ids, counts
        counts[shape] = counts.get(shape, 0) + 1
    return sorted(((c, m) for m, c in counts.items()), key=lambda x: (-x[0], x[1]))
'''),
        "explanation": ("Replacing the parts that change between runs (numbers, quoted values) leaves the shape of each "
                        "failure, and counting shapes turns 1,400 red lines into a handful of distinct problems. Quotes "
                        "go first so a date inside quotes becomes one S, not several N."),
        "key_justification": "Normalise strings with patterns, then count by shape.",
        "alt": _alt_triage,
        "variants": variants(
            [({}, [("3\nTimeout after 3000 ms waiting for '#pay-btn'\nTimeout after 5000 ms waiting for '#pay-btn'\n"
                    "Element 'Book now' not found\n", "2 Timeout after N ms waiting for S\n1 Element S not found")]),
             ({}, [("2\nHTTP 500 from /api/hotels/12\nHTTP 502 from /api/hotels/7\n", "2 HTTP N from /api/hotels/N")]),
             ({}, [("2\nExpected 3 rooms but got 2\nDate mismatch: expected '2026-11-01' got '2026-11-02'\n",
                    "1 Date mismatch: expected S got S\n1 Expected N rooms but got N")])],
            _gen_triage, 10110,
            extra_hidden=[["1\nno numbers here\n"], ["2\nit's 5\nit's 6\n"], ["2\n\"a\" 1\n'b' 22\n"]]),
    },
    {
        "prompt": ("Some tests pass alone but fail in the full run because they quietly rely on data another test left "
                   "behind. Find those hidden dependencies. The first line is n, then n steps in run order, `test READ key` "
                   "or `test WRITE key`. Complete `hidden_dependencies`: a test depends on another when it READs a key "
                   "whose latest write came from a different test, and it has not written that key itself earlier. The "
                   "program prints each distinct `reader <- writer key`, sorted, or ISOLATED."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_ORDER, stub(_SIG_ORDER, _DOC_ORDER, "[]")),
        "solution": program(_IO_ORDER, _SIG_ORDER + f'''
    """{_DOC_ORDER}"""
    last_writer, wrote = {{}}, set()
    found = set()
    for test, op, key in steps:
        if op == "WRITE":
            last_writer[key] = test
            wrote.add((test, key))
        elif key in last_writer and last_writer[key] != test and (test, key) not in wrote:
            found.add((test, last_writer[key], key))      # it reads someone else's leftovers
    return sorted(found)
'''),
        "alt": _alt_order,
        "explanation": ("Tracking the last writer of each key in a dictionary while replaying the run shows exactly which "
                        "test reads another test's data. Each such pair is an isolation bug: the fix is for the reader to "
                        "create its own data (a fixture), so tests pass in any order and in parallel."),
        "key_justification": "Replay steps with a last-writer map to find order dependencies.",
        "variants": variants(
            [({}, [("6\nlogin_test WRITE session\nbooking_test READ session\nbooking_test WRITE cart\npayment_test READ cart\n"
                    "payment_test WRITE session\nrefund_test READ session\n",
                    "booking_test <- login_test session\npayment_test <- booking_test cart\nrefund_test <- payment_test session")]),
             ({}, [("3\na WRITE k\na READ k\nb WRITE k\n", "ISOLATED")]),
             ({}, [("4\na WRITE k\nb WRITE k\nb READ k\nc READ k\n", "c <- b k")])],
            _gen_order, 10120,
            extra_hidden=[["1\nx READ k\n"], ["3\na WRITE k\nb READ k\nb READ k\n"], ["4\nb WRITE k\na WRITE k\nb READ k\nc READ j\n"]]),
    },
]

# ---------------------------------------------------------------- qat-4 Jeevan Raksha
_IO_RISK = '''
def main():
    data = sys.stdin.read().split("\\n")
    budget = int(data[0])
    n = int(data[1])
    features = []
    for i in range(n):
        name, likelihood, impact, minutes = data[2 + i].split()
        features.append((name, int(likelihood), int(impact), int(minutes)))
    chosen, covered, total, used = plan_tests(features, budget)
    for name in chosen:
        print("test", name)
    print("covered_risk", covered, "of", total)
    print("minutes_used", used)


main()
'''
_SIG_RISK = "def plan_tests(features, budget):"
_DOC_RISK = ("features: (name, likelihood 1-5, impact 1-5, minutes to test). Risk = likelihood x impact. Go through "
             "the features by risk high to low (ties: fewer minutes, then name) and test each one that still fits the "
             "remaining minutes. Return (names chosen in that order, risk covered, total risk, minutes used).")


def _alt_risk(stdin):
    rows = stdin.split("\n")
    budget = int(rows[0])
    n = int(rows[1])
    f = [r.split() for r in rows[2:2 + n]]
    f = [(a, int(b) * int(c), int(d)) for a, b, c, d in f]
    f.sort(key=lambda x: x[0])
    f.sort(key=lambda x: x[2])
    f.sort(key=lambda x: x[1], reverse=True)
    left, cov, chosen = budget, 0, []
    for name, risk, mins in f:
        if mins <= left:
            left -= mins
            cov += risk
            chosen.append(f"test {name}")
    return "\n".join(chosen + [f"covered_risk {cov} of {sum(x[1] for x in f)}", f"minutes_used {budget - left}"])


def _gen_risk(rng, size):
    names = ["payments", "claims", "quotes", "policies", "renewals", "profile", "documents", "nominee", "kyc", "reports"]
    n = {"small": 4, "medium": 7, "large": 10}[size]
    rows = [f"{nm} {rng.randint(1, 5)} {rng.randint(1, 5)} {rng.choice([5, 10, 20, 30, 45])}" for nm in rng.sample(names, n)]
    return f"{rng.choice([30, 60, 120])}\n{n}\n" + "\n".join(rows) + "\n"


_IO_CONTRACT = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    contract = [tuple(data[1 + i].split()) for i in range(n)]
    response = json.loads(data[1 + n])
    problems = verify(contract, response)
    print("\\n".join(problems) if problems else "PASS")


main()
'''
_SIG_CONTRACT = "def verify(contract, response):"
_DOC_CONTRACT = ("contract: (dotted path, type) with type one of string, number, boolean, object, array, null. "
                 "response: parsed JSON. Follow each path through objects. Return, in contract order, 'missing PATH' or "
                 "'type PATH expected=T got=U'. true/false are boolean, never number.")

_JSON_TYPES_DOC = "string number boolean object array null"


def _alt_contract(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    con = [r.split() for r in rows[1:1 + n]]
    resp = json.loads(rows[1 + n])

    def kind(v):
        if v is None:
            return "null"
        if v is True or v is False:
            return "boolean"
        if type(v) in (int, float):
            return "number"
        return {str: "string", dict: "object", list: "array"}[type(v)]

    out = []
    for path, t in con:
        cur, ok = resp, True
        for part in path.split("."):
            if type(cur) is dict and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if not ok:
            out.append(f"missing {path}")
        elif kind(cur) != t:
            out.append(f"type {path} expected={t} got={kind(cur)}")
    return "\n".join(out) or "PASS"


def _gen_contract(rng, size):
    contract = ["policy.id string", "policy.premium number", "policy.active boolean", "holder.name string",
                "holder.nominees array", "claims array", "meta object", "policy.end_date null"]
    k = {"small": 3, "medium": 5, "large": 8}[size]
    con = rng.sample(contract, k)
    resp = {"policy": {"id": rng.choice(["P1", 101]), "premium": rng.choice([1200, "1200", 99.5]),
                       "active": rng.choice([True, 1, "yes"]), "end_date": rng.choice([None, "2027-01-01"])},
            "holder": rng.choice([{"name": "Lakshmi", "nominees": []}, {}, {"name": None}]),
            "claims": rng.choice([[], {}, None]), "meta": rng.choice([{}, []])}
    if rng.random() < 0.3:
        del resp["policy"]
    return f"{k}\n" + "\n".join(con) + "\n" + json.dumps(resp) + "\n"


PROBLEMS["qat-4"] = [
    {
        "prompt": ("A release is due in two days with less test time than usual, so the team tests by risk. The first "
                   "line is the minutes available, the second is n, then n features `name likelihood impact minutes` "
                   "(likelihood and impact 1-5). Complete `plan_tests`: risk = likelihood x impact; go through the "
                   "features by risk from high to low (ties: fewer minutes, then name) and test each one that still fits "
                   "the remaining time, skipping any that don't. The program prints `test name` for each chosen feature, "
                   "then `covered_risk x of y` and `minutes_used z`."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_RISK, stub(_SIG_RISK, _DOC_RISK, "[], 0, 0, 0")),
        "solution": program(_IO_RISK, _SIG_RISK + f'''
    """{_DOC_RISK}"""
    ranked = sorted(features, key=lambda f: (-f[1] * f[2], f[3], f[0]))
    left, covered, chosen = budget, 0, []
    for name, likelihood, impact, minutes in ranked:
        if minutes <= left:                 # skip what doesn't fit, keep going
            left -= minutes
            covered += likelihood * impact
            chosen.append(name)
    total = sum(l * i for _, l, i, _ in features)
    return chosen, covered, total, budget - left
'''),
        "explanation": ("Ranking by likelihood x impact and filling the time greedily puts testing where a failure "
                        "would hurt most. Reporting covered risk out of total risk makes the trade-off explicit for the "
                        "release decision, which is more honest than a coverage percentage."),
        "key_justification": "Rank by a risk score, then greedily fill a time budget.",
        "alt": _alt_risk,
        "variants": variants(
            [({}, [("60\n4\npayments 5 5 40\nclaims 4 5 30\nquotes 3 2 10\nprofile 1 1 5\n",
                    "test payments\ntest quotes\ntest profile\ncovered_risk 32 of 52\nminutes_used 55")]),
             ({}, [("10\n2\nb 2 2 5\na 2 2 5\n", "test a\ntest b\ncovered_risk 8 of 8\nminutes_used 10")]),
             ({}, [("5\n1\nkyc 5 5 6\n", "covered_risk 0 of 25\nminutes_used 0")])],
            _gen_risk, 10210,
            extra_hidden=[["0\n1\nx 1 1 0\n"], ["30\n3\na 3 3 20\nb 3 3 10\nc 1 1 10\n"], ["100\n0\n"]]),
    },
    {
        "prompt": ("The end-to-end suite across eight services is slow and flaky. Contract tests check each service's "
                   "response shape on its own instead. The first line is n, then n contract lines `path type` (a dotted "
                   "path through objects; type one of string, number, boolean, object, array, null), then one line of "
                   "JSON: the provider's response. Complete `verify`: report `missing PATH` if the path does not exist, "
                   "or `type PATH expected=T got=U` if the value has the wrong type (true and false are boolean, never "
                   "number), in contract order. The program prints the problems, or PASS."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": "import json\n" + program(_IO_CONTRACT, stub(_SIG_CONTRACT, _DOC_CONTRACT, "[]")),
        "solution": "import json\n" + program(_IO_CONTRACT, '''def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):                 # check bool before number: True is an int in Python
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", dict: "object", list: "array"}[type(value)]


''' + _SIG_CONTRACT + f'''
    """{_DOC_CONTRACT}"""
    problems = []
    for path, expected in contract:
        node, found = response, True
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                found = False
                break
        if not found:
            problems.append(f"missing {{path}}")
        elif json_type(node) != expected:
            problems.append(f"type {{path}} expected={{expected}} got={{json_type(node)}}")
    return problems
'''),
        "explanation": ("Walking each dotted path through nested dictionaries and comparing JSON types is the core of "
                        "consumer-driven contract testing: it fails fast, in seconds, when a provider changes a field, "
                        "without starting all eight services. The bool-before-number check matters because Python treats "
                        "True as the integer 1."),
        "key_justification": "Navigate nested maps by path and check JSON types.",
        "alt": _alt_contract,
        "variants": variants(
            [({}, [('4\npolicy.id string\npolicy.premium number\npolicy.active boolean\nholder.name string\n'
                    '{"policy": {"id": "P1", "premium": "1200", "active": true}, "holder": {}}\n',
                    "type policy.premium expected=number got=string\nmissing holder.name")]),
             ({}, [('2\nclaims array\nmeta object\n{"claims": [], "meta": {}}\n', "PASS")]),
             ({}, [('2\nflag boolean\ncount number\n{"flag": 1, "count": true}\n',
                    "type flag expected=boolean got=number\ntype count expected=number got=boolean")])],
            _gen_contract, 10220,
            extra_hidden=[['1\na.b.c null\n{"a": {"b": {"c": null}}}\n'], ['1\na.b string\n{"a": "text"}\n'],
                          ['1\nx number\n{"x": 2.5}\n']]),
    },
]

# ---------------------------------------------------------------- qat-5 Digital Mandi
_IO_LOAD = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    requests = [tuple(map(int, data[1 + i].split())) for i in range(n)]
    peak, second, errors = load_summary(requests)
    print("peak_rps", peak, "at second", second)
    print("error_rate", f"{100 * errors / n:.2f}%")
    print("verdict", "PASS" if errors * 100 <= n else "FAIL")


main()
'''
_SIG_LOAD = "def load_summary(requests):"
_DOC_LOAD = ("requests: (time in ms since the test started, HTTP status). Group by whole second (time // 1000). Return "
             "(the most requests in one second, that second (the earliest on a tie), number of responses with "
             "status 500 or above).")


def _alt_load(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    r = [list(map(int, x.split())) for x in rows[1:1 + n]]
    secs = sorted({t // 1000 for t, _ in r})
    best = max(secs, key=lambda s: (sum(1 for t, _ in r if t // 1000 == s), -s))
    peak = sum(1 for t, _ in r if t // 1000 == best)
    err = sum(1 for _, s in r if s >= 500)
    return (f"peak_rps {peak} at second {best}\nerror_rate {100 * err / n:.2f}%\n"
            f"verdict {'PASS' if err * 100 <= n else 'FAIL'}")


def _gen_load(rng, size):
    n = {"small": 10, "medium": 60, "large": 150}[size]
    times = sorted(rng.randint(0, 5999) for _ in range(n))
    rows = [f"{t} {rng.choice([200] * 30 + [201, 429, 500, 503])}" for t in times]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_QUEUE = '''
def main():
    data = sys.stdin.read().split()
    service, sla, n = int(data[0]), int(data[1]), int(data[2])
    arrivals = list(map(int, data[3:3 + n]))
    worst, over, finish = bid_queue(arrivals, service, sla)
    print("max_wait", worst)
    print("over_sla", over)
    print("last_finish", finish)


main()
'''
_SIG_QUEUE = "def bid_queue(arrivals, service, sla):"
_DOC_QUEUE = ("arrivals: bid times in ms, in order. One worker handles bids first come, first served; each takes "
              "`service` ms. A bid waits from its arrival until the worker starts it. Return (longest wait, number of "
              "bids that waited more than `sla` ms, time the last bid finishes).")


def _alt_queue(stdin):
    d = stdin.split()
    s, sla, n = int(d[0]), int(d[1]), int(d[2])
    a = [int(x) for x in d[3:3 + n]]
    starts = []
    for i, t in enumerate(a):
        starts.append(t if i == 0 else max(t, starts[-1] + s))
    waits = [st - t for st, t in zip(starts, a)]
    return f"max_wait {max(waits)}\nover_sla {sum(w > sla for w in waits)}\nlast_finish {starts[-1] + s}"


def _gen_queue(rng, size):
    n = {"small": 6, "medium": 40, "large": 150}[size]
    t, a = 0, []
    for _ in range(n):
        t += rng.choice([0, 1, 5, 20, 50, 200])
        a.append(t)
    return f"{rng.choice([10, 25, 40])} {rng.choice([50, 100, 500])} {n}\n" + " ".join(map(str, a)) + "\n"


PROBLEMS["qat-5"] = [
    {
        "prompt": ("A load test fired bids at the auction like the final minute of a sale. Summarise the results. The "
                   "first line is n, then n requests `time_ms status` (time since the test started). Complete "
                   "`load_summary`: group requests by whole second (time // 1000). The program prints `peak_rps r at "
                   "second s` (the busiest second, the earliest on a tie), `error_rate x%` (status 500 or above, two "
                   "decimals) and `verdict PASS` if at most 1% failed, else `verdict FAIL`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_LOAD, stub(_SIG_LOAD, _DOC_LOAD, "len(requests), 0, 0")),
        "solution": program(_IO_LOAD, _SIG_LOAD + f'''
    """{_DOC_LOAD}"""
    per_second, errors = {{}}, 0
    for t, status in requests:
        per_second[t // 1000] = per_second.get(t // 1000, 0) + 1
        errors += status >= 500                 # 429 is throttling, not a server error
    second = min(per_second, key=lambda s: (-per_second[s], s))
    return per_second[second], second, errors
'''),
        "explanation": ("Bucketing timestamps by second in a dictionary gives the throughput curve, and its peak is what "
                        "the auction must survive at closing time. Counting only 5xx as errors keeps deliberate "
                        "throttling (429) separate from real failures; the pass rule is an integer check, not a float."),
        "key_justification": "Bucket events by time in a hash map; summarise peak and errors.",
        "alt": _alt_load,
        "variants": variants(
            [({}, [("5\n0 200\n400 200\n999 500\n1000 200\n2500 200\n", "peak_rps 3 at second 0\nerror_rate 20.00%\nverdict FAIL")]),
             ({}, [("4\n1500 200\n1600 429\n3000 200\n3100 201\n", "peak_rps 2 at second 1\nerror_rate 0.00%\nverdict PASS")]),
             ({}, [("1\n5 503\n", "peak_rps 1 at second 0\nerror_rate 100.00%\nverdict FAIL")])],
            _gen_load, 10310,
            extra_hidden=[["2\n0 200\n1000 200\n"], ["3\n100 500\n200 200\n300 200\n"], ["2\n7000 200\n7999 200\n"]]),
    },
    {
        "prompt": ("At closing time 50,000 traders bid in the last minute. Model one bid-processing worker to see how "
                   "long bids wait. The first line is `service sla n` (ms per bid, the acceptable wait in ms, number of "
                   "bids), the second has the n arrival times in ms, in order. Complete `bid_queue`: the worker takes "
                   "bids first come, first served, each for `service` ms; a bid waits from its arrival until the worker "
                   "starts it. The program prints `max_wait`, `over_sla` (bids that waited longer than the SLA) and "
                   "`last_finish`."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_QUEUE, stub(_SIG_QUEUE, _DOC_QUEUE, "0, 0, arrivals[-1] + service")),
        "solution": "from collections import deque\n" + program(_IO_QUEUE, _SIG_QUEUE + f'''
    """{_DOC_QUEUE}"""
    queue = deque(arrivals)
    free_at = worst = over = 0
    while queue:
        arrived = queue.popleft()               # first come, first served
        start = max(arrived, free_at)
        wait = start - arrived
        worst = max(worst, wait)
        over += wait > sla
        free_at = start + service
    return worst, over, free_at
'''),
        "explanation": ("A FIFO queue with one server is the simplest performance model: each bid starts when it "
                        "arrives or when the worker frees up, whichever is later. When arrivals come faster than "
                        "service, waits grow without limit; the model shows how many workers (or how much faster "
                        "processing) the final minute needs before any load test is run."),
        "key_justification": "Single-server FIFO queue simulation.",
        "alt": _alt_queue,
        "variants": variants(
            [({}, [("100 150 5\n0 10 20 30 500\n", "max_wait 270\nover_sla 2\nlast_finish 600")]),
             ({}, [("10 0 3\n0 10 20\n", "max_wait 0\nover_sla 0\nlast_finish 30")]),
             ({}, [("50 49 2\n0 0\n", "max_wait 50\nover_sla 1\nlast_finish 100")])],
            _gen_queue, 10320,
            extra_hidden=[["5 5 1\n100\n"], ["10 10 3\n0 0 0\n"], ["1 0 4\n0 0 5 5\n"]]),
    },
]

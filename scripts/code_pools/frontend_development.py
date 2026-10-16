"""Code pool for Frontend Development (fed-2 .. fed-5). Built and checked by scripts/build_code_pools.py."""
from urllib.parse import parse_qsl

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- fed-2 Yatra Kosh
_IO_DEBOUNCE = '''
def main():
    data = sys.stdin.read().split()
    delay, n = int(data[0]), int(data[1])
    keys = list(map(int, data[2:2 + n]))
    calls = debounce(keys, delay)
    print("calls", len(calls))
    print("at", " ".join(map(str, calls)) if calls else "-")


main()
'''
_SIG_DEBOUNCE = "def debounce(keys, delay):"
_DOC_DEBOUNCE = ("keys: keystroke times in ms, in order. Each keystroke (re)starts a timer of `delay` ms; the search "
                 "call fires when a timer runs out. A keystroke at or after the moment a timer runs out does not "
                 "cancel it. Return the times the call fires.")


def _alt_debounce(stdin):
    d = stdin.split()
    delay, n = int(d[0]), int(d[1])
    keys = [int(x) for x in d[2:2 + n]]
    fired = []
    pending = None
    for t in keys:
        if pending is not None and t >= pending:
            fired.append(pending)
        pending = t + delay
    if pending is not None:
        fired.append(pending)
    return f"calls {len(fired)}\nat {' '.join(map(str, fired)) or '-'}"


def _gen_debounce(rng, size):
    n = {"small": 6, "medium": 25, "large": 80}[size]
    t, keys = 0, []
    for _ in range(n):
        t += rng.choice([40, 80, 120, 150, 200, 400, 900])
        keys.append(t)
    return f"{rng.choice([150, 250, 300, 500])} {n}\n" + " ".join(map(str, keys)) + "\n"


_IO_QUERY = '''
def main():
    data = sys.stdin.read().split("\\n")
    params = parse_query(data[0].strip())
    if not params:
        print("EMPTY")
    for key in sorted(params):
        print(key + "=" + ",".join(params[key]))


main()
'''
_SIG_QUERY = "def parse_query(url):"
_DOC_QUERY = ("Take the part after the first '?' (or the whole text if there is none) and split it on '&', skipping "
              "empty pieces. Each piece is key=value (no '=' means an empty value). Decode '+' as a space and %XX as "
              "the character with that hex code, in keys and values. Return {key: [values in order]}.")


def _alt_query(stdin):
    url = stdin.split("\n")[0].strip()
    q = url.split("?", 1)[1] if "?" in url else url
    out = {}
    for k, v in parse_qsl(q, keep_blank_values=True):
        out.setdefault(k, []).append(v)
    return "\n".join(f"{k}={','.join(out[k])}" for k in sorted(out)) or "EMPTY"


_PARAMS = ["from=Jaipur", "to=New%20Delhi", "to=Agra", "class=sleeper", "class=3A", "q=a+b", "date=2026-11-01",
           "sort=price", "page=2", "ac", "name=Ravi%20K", "seat=%2B", "from=Kota"]


def _gen_query(rng, size):
    n = {"small": 2, "medium": 5, "large": 9}[size]
    parts = [rng.choice(_PARAMS) for _ in range(n)]
    if rng.random() < 0.3:
        parts.insert(1, "")
    base = rng.choice(["https://yatrakosh.in/search?", "/search?", "?", ""])
    return base + "&".join(parts) + "\n"


PROBLEMS["fed-2"] = [
    {
        "prompt": ("Yatra Kosh's search box called the API on every keystroke. With debouncing, each keystroke "
                   "restarts a timer and the search runs only when the user pauses. The first line is `delay n`, the "
                   "second has n keystroke times in milliseconds, in order. Complete `debounce`: each keystroke starts a "
                   "fresh timer of `delay` ms that replaces the previous one; a call fires when a timer runs out, and a "
                   "keystroke at or after that moment does not cancel it. The program prints `calls k` and `at` with the "
                   "firing times, or `at -`."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_DEBOUNCE, stub(_SIG_DEBOUNCE, _DOC_DEBOUNCE, "[t + delay for t in keys]")),
        "solution": program(_IO_DEBOUNCE, _SIG_DEBOUNCE + f'''
    """{_DOC_DEBOUNCE}"""
    calls = []
    for i, t in enumerate(keys):
        is_last = i == len(keys) - 1
        if is_last or keys[i + 1] >= t + delay:     # nobody typed before this timer ran out
            calls.append(t + delay)
    return calls
'''),
        "alt": _alt_debounce,
        "explanation": ("A keystroke's timer survives only if the next keystroke comes at or after it expires, so one "
                        "look at the next time decides each one. Debouncing turns a burst of typing into one request, "
                        "cutting load on the API and avoiding out-of-order results for half-typed queries."),
        "key_justification": "Debounce as a scan comparing each event with the next.",
        "variants": variants(
            [({}, [("300 6\n0 100 250 700 1100 1350\n", "calls 3\nat 550 1000 1650")]),
             ({}, [("100 3\n0 100 200\n", "calls 3\nat 100 200 300")]),
             ({}, [("500 4\n0 10 20 30\n", "calls 1\nat 530")])],
            _gen_debounce, 7010,
            extra_hidden=[["200 1\n5\n"], ["100 2\n0 99\n"], ["50 3\n0 50 51\n"]]),
    },
    {
        "prompt": ("Users lose their filters when they refresh or share a link, so the search state moves into the URL. "
                   "Write the reading side. The input is one URL or query string. Complete `parse_query`: take the part "
                   "after the first `?` (or the whole line if there is none), split on `&` and skip empty pieces; each "
                   "piece is `key=value` (no `=` means an empty value); decode `+` as a space and `%XX` as the character "
                   "with that hex code. A key can repeat (class=sleeper&class=3A). The program prints `key=v1,v2` per "
                   "key, sorted by key, values in the order they appeared, or EMPTY."),
        "ds_topic": "string", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_QUERY, stub(_SIG_QUERY, _DOC_QUERY, "{}")),
        "solution": program(_IO_QUERY, '''def decode(text):
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == "+":
            out.append(" ")
        elif ch == "%" and i + 2 < len(text) + 0 and all(c in "0123456789abcdefABCDEF" for c in text[i + 1:i + 3]) \\
                and len(text[i + 1:i + 3]) == 2:
            out.append(chr(int(text[i + 1:i + 3], 16)))
            i += 2
        else:
            out.append(ch)
        i += 1
    return "".join(out)


''' + _SIG_QUERY + f'''
    """{_DOC_QUERY}"""
    query = url.split("?", 1)[1] if "?" in url else url
    params = {{}}
    for piece in query.split("&"):
        if not piece:
            continue
        key, _, value = piece.partition("=")
        params.setdefault(decode(key), []).append(decode(value))
    return params
'''),
        "alt": _alt_query,
        "explanation": ("Splitting on '&' and then on the first '=' gives key-value pairs; a dictionary of lists keeps "
                        "repeated keys (multi-select filters) in order. Decoding must happen after splitting, so an "
                        "encoded '&' (%26) inside a value is not mistaken for a separator. URLSearchParams does the same "
                        "in the browser."),
        "key_justification": "Tokenise and percent-decode a query string into a multi-map.",
        "variants": variants(
            [({}, [("https://yatrakosh.in/search?from=Jaipur&to=New%20Delhi&class=sleeper&class=3A&q=a+b\n",
                    "class=sleeper,3A\nfrom=Jaipur\nq=a b\nto=New Delhi")]),
             ({}, [("/search?\n", "EMPTY")]),
             ({}, [("ac&seat=%2B&&note=R%26D\n", "ac=\nnote=R&D\nseat=+")])],
            _gen_query, 7020,
            extra_hidden=[["?a=1&a=2&a=3\n"], ["x=%41%42\n"], ["?k=v=w\n"]]),
    },
]

# ---------------------------------------------------------------- fed-3 Pustak Ghar
_IO_CORS = '''
def main():
    data = sys.stdin.read().split("\\n")
    origins = data[0].split()
    methods = data[1].split()
    n = int(data[2])
    blocked = 0
    for i in range(n):
        origin, method = data[3 + i].split()
        ok = cors_allows(origins, methods, origin, method)
        blocked += not ok
        print(origin, method, "ALLOW" if ok else "BLOCK")
    print("blocked", blocked)


main()
'''
_SIG_CORS = "def cors_allows(origins, methods, origin, method):"
_DOC_CORS = ("origins: allowed origins exactly as scheme://host[:port], or '*' for any. methods: allowed methods. "
             "Return True if this cross-origin request is allowed: the origin matches exactly (or '*' is listed) and "
             "the method is allowed.")


def _alt_cors(stdin):
    rows = stdin.split("\n")
    o = rows[0].split()
    m = rows[1].split()
    n = int(rows[2])
    out, b = [], 0
    for r in rows[3:3 + n]:
        org, meth = r.split()
        ok = ("*" in o or any(org == x for x in o)) and meth in m
        b += 0 if ok else 1
        out.append(f"{org} {meth} {'ALLOW' if ok else 'BLOCK'}")
    return "\n".join(out + [f"blocked {b}"])


_ORIGINS = ["https://shop.pustakghar.in", "http://shop.pustakghar.in", "https://pustakghar.in",
            "https://shop.pustakghar.in:8443", "https://evil.example", "http://localhost:3000"]


def _gen_cors(rng, size):
    n = {"small": 3, "medium": 10, "large": 25}[size]
    allowed = " ".join(rng.sample(_ORIGINS[:4] + ["http://localhost:3000"], rng.randint(1, 3)))
    if rng.random() < 0.15:
        allowed = "*"
    methods = " ".join(rng.sample(["GET", "POST", "PUT", "DELETE"], rng.randint(1, 3)))
    reqs = [f"{rng.choice(_ORIGINS)} {rng.choice(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])}" for _ in range(n)]
    return f"{allowed}\n{methods}\n{n}\n" + "\n".join(reqs) + "\n"


_IO_CLS = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    shifts = [tuple(map(int, data[1 + i].split())) for i in range(n)]
    best, windows = cls(shifts)
    print("cls", f"{best / 10000:.4f}")
    print("windows", windows)


main()
'''
_SIG_CLS = "def cls(shifts):"
_DOC_CLS = ("shifts: (time ms, score in ten-thousandths, had_recent_input 0/1) in time order. Ignore shifts right after "
            "user input. Group the rest into session windows: a shift starts a new window if it comes more than 1000 "
            "ms after the previous counted shift, or more than 5000 ms after the window's first shift. Return (the "
            "largest window sum, number of windows).")


def _alt_cls(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    s = [list(map(int, r.split())) for r in rows[1:1 + n] if r.strip()]
    s = [x for x in s if x[2] == 0]
    windows = []
    for t, v, _ in s:
        if windows and t - windows[-1]["last"] <= 1000 and t - windows[-1]["start"] <= 5000:
            windows[-1]["sum"] += v
            windows[-1]["last"] = t
        else:
            windows.append({"start": t, "last": t, "sum": v})
    best = max((w["sum"] for w in windows), default=0)
    return f"cls {best / 10000:.4f}\nwindows {len(windows)}"


def _gen_cls(rng, size):
    n = {"small": 5, "medium": 20, "large": 50}[size]
    t, rows = 0, []
    for _ in range(n):
        t += rng.choice([50, 200, 400, 900, 1100, 3000])
        rows.append(f"{t} {rng.randint(10, 900)} {1 if rng.random() < 0.15 else 0}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["fed-3"] = [
    {
        "prompt": ("The shop at https://shop.pustakghar.in calls an API on another origin, and the browser blocks it "
                   "unless the API allows that origin. Check the API's CORS settings against real requests. The first "
                   "line lists the allowed origins (exactly scheme://host[:port], or `*` for any), the second the allowed "
                   "methods, the third is n, then n requests `origin method`. Complete `cors_allows`: a request is "
                   "allowed only if the origin matches exactly (http and https, and different ports, are different "
                   "origins) or `*` is listed, and the method is allowed. The program prints `origin method ALLOW|BLOCK` "
                   "per request, then `blocked k`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_CORS, stub(_SIG_CORS, _DOC_CORS, "True")),
        "solution": program(_IO_CORS, _SIG_CORS + f'''
    """{_DOC_CORS}"""
    allowed_origins, allowed_methods = set(origins), set(methods)
    origin_ok = "*" in allowed_origins or origin in allowed_origins     # exact match: scheme, host and port
    return origin_ok and method in allowed_methods
'''),
        "alt": _alt_cors,
        "explanation": ("An origin is the exact triple of scheme, host and port, so set membership on the full string is "
                        "the right test; 'shop.pustakghar.in' over http is a different origin from https. The fix "
                        "belongs on the API, which must list the shop's origin; nothing in the front end can make the "
                        "browser skip this check."),
        "key_justification": "Exact-match set look-ups for an origin and method allow-list.",
        "variants": variants(
            [({}, [("https://shop.pustakghar.in\nGET POST\n3\nhttps://shop.pustakghar.in GET\nhttp://shop.pustakghar.in GET\n"
                    "https://shop.pustakghar.in DELETE\n",
                    "https://shop.pustakghar.in GET ALLOW\nhttp://shop.pustakghar.in GET BLOCK\n"
                    "https://shop.pustakghar.in DELETE BLOCK\nblocked 2")]),
             ({}, [("*\nGET\n2\nhttps://evil.example GET\nhttps://evil.example POST\n",
                    "https://evil.example GET ALLOW\nhttps://evil.example POST BLOCK\nblocked 1")]),
             ({}, [("https://shop.pustakghar.in:8443\nPUT\n1\nhttps://shop.pustakghar.in PUT\n",
                    "https://shop.pustakghar.in PUT BLOCK\nblocked 1")])],
            _gen_cors, 7110,
            extra_hidden=[["http://localhost:3000\nGET\n1\nhttp://localhost:3000 GET\n"], ["a b\nX\n0\n"],
                          ["https://pustakghar.in\nGET\n1\nhttps://shop.pustakghar.in GET\n"]]),
    },
    {
        "prompt": ("Book pages jump as images and ad slots load. Cumulative Layout Shift (CLS) measures this. The first "
                   "line is n, then n layout shifts `time_ms score had_recent_input` (score in ten-thousandths, so 1250 "
                   "is 0.125; had_recent_input is 1 for shifts just after the user clicked or typed). Complete `cls`: "
                   "ignore shifts after input; group the others into session windows, where a shift starts a new window "
                   "if it comes more than 1000 ms after the previous counted shift or more than 5000 ms after the "
                   "window's first shift. CLS is the largest window sum. The program prints `cls` with four decimals and "
                   "`windows k`."),
        "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CLS, stub(_SIG_CLS, _DOC_CLS, "sum(s for _, s, _ in shifts), 1")),
        "solution": program(_IO_CLS, _SIG_CLS + f'''
    """{_DOC_CLS}"""
    best = windows = 0
    start = last = None
    total = 0
    for t, score, had_input in shifts:
        if had_input:
            continue                                  # expected shifts after a click do not count
        if start is None or t - last > 1000 or t - start > 5000:
            windows += 1
            start, total = t, 0
        total += score
        last = t
        best = max(best, total)
    return best, windows
'''),
        "alt": _alt_cls,
        "explanation": ("One pass with the current window's start, last time and sum is enough: a gap over a second or a "
                        "window older than five seconds starts a new one, and CLS keeps the worst window, not the total. "
                        "Reserving space for images and ad slots (width and height, aspect-ratio) is what actually "
                        "removes these shifts."),
        "key_justification": "Session windows over a time-ordered array (CLS definition).",
        "variants": variants(
            [({}, [("5\n100 500 0\n400 300 0\n2000 800 0\n2500 100 1\n2600 200 0\n", "cls 0.1000\nwindows 2")]),
             ({}, [("6\n0 100 0\n900 100 0\n1800 100 0\n2700 100 0\n3600 100 0\n5100 100 0\n", "cls 0.0500\nwindows 2")]),
             ({}, [("2\n10 999 1\n20 1 1\n", "cls 0.0000\nwindows 0")])],
            _gen_cls, 7120,
            extra_hidden=[["1\n0 1250 0\n"], ["3\n0 10 0\n1000 10 0\n2001 10 0\n"], ["3\n0 5 0\n5000 5 0\n5001 5 0\n"]]),
    },
]

# ---------------------------------------------------------------- fed-4 Dhanda Dost
_IO_COVER = '''
def main():
    data = sys.stdin.read().split("\\n")
    target = data[0].strip()
    n = int(data[1])
    rows = [tuple(data[2 + i].split()) for i in range(n)]
    chosen, covered = cover(rows, target)
    for name, version in chosen:
        print(name, version)
    print("browsers", len(chosen))
    print("covered", f"{covered // 10}.{covered % 10}%")


main()
'''
_SIG_COVER = "def cover(rows, target):"
_DOC_COVER = ("rows: (browser, version, share %) with shares like '12.5'. target: percent like '90'. Take browsers by "
              "share, largest first (ties by browser then version), until the total reaches the target. Return (the "
              "chosen (browser, version), total share in tenths of a percent).")


def _tenths(text):
    whole, _, frac = text.partition(".")
    return int(whole) * 10 + int((frac + "0")[:1])


def _alt_cover(stdin):
    rows = stdin.split("\n")
    target = _tenths(rows[0].strip())
    n = int(rows[1])
    items = [r.split() for r in rows[2:2 + n]]
    items.sort(key=lambda x: (x[0], x[1]))
    items.sort(key=lambda x: _tenths(x[2]), reverse=True)
    chosen, total = [], 0
    for b, v, s in items:
        if total >= target:
            break
        chosen.append(f"{b} {v}")
        total += _tenths(s)
    return "\n".join(chosen + [f"browsers {len(chosen)}", f"covered {total // 10}.{total % 10}%"])


def _gen_cover(rng, size):
    names = ["chrome", "safari", "samsung", "firefox", "uc", "opera", "edge", "miui"]
    n = {"small": 4, "medium": 10, "large": 20}[size]
    rows = [f"{rng.choice(names)} {rng.randint(90, 125)} {rng.randint(1, 300) / 10:.1f}" for _ in range(n)]
    return f"{rng.choice(['80', '90', '95', '99.5'])}\n{n}\n" + "\n".join(rows) + "\n"


_IO_BUNDLE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    modules = {}
    for i in range(n):
        name, kb, deps = data[1 + i].split()
        modules[name] = (int(kb), [] if deps == "-" else deps.split(","))
    for entry in data[1 + n].split():
        print(entry, bundle_size(modules, entry))


main()
'''
_SIG_BUNDLE = "def bundle_size(modules, entry):"
_DOC_BUNDLE = ("modules: {name: (size in KB, [modules it imports])}; imports can form cycles. Return the total KB of "
               "every module reachable from entry, counting each module once, including entry itself.")


def _alt_bundle(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    mods = {}
    for r in rows[1:1 + n]:
        nm, kb, d = r.split()
        mods[nm] = (int(kb), [] if d == "-" else d.split(","))
    out = []
    for e in rows[1 + n].split():
        seen = {e}
        changed = True
        while changed:
            changed = False
            for m in list(seen):
                for d in mods[m][1]:
                    if d not in seen:
                        seen.add(d)
                        changed = True
        out.append(f"{e} {sum(mods[m][0] for m in seen)}")
    return "\n".join(out)


_MODULES = ["login", "dashboard", "invoices", "auth", "http", "charts", "datepicker", "i18n", "utils", "pdf", "forms"]


def _gen_bundle(rng, size):
    n = {"small": 5, "medium": 8, "large": 11}[size]
    names = rng.sample(_MODULES, n)
    sizes = {nm: (400 if nm == "charts" else rng.randint(2, 80)) for nm in names}
    rows = []
    for nm in names:
        deps = rng.sample([x for x in names if x != nm], rng.randint(0, 2))
        rows.append(f"{nm} {sizes[nm]} {','.join(deps) or '-'}")
    entries = rng.sample(names, 2)
    return f"{n}\n" + "\n".join(rows) + "\n" + " ".join(entries) + "\n"


PROBLEMS["fed-4"] = [
    {
        "prompt": ("The team argues about which browsers to support. Decide from data. The first line is the target "
                   "share as a percent (like 90 or 99.5), the second is n, then n lines `browser version share` (share as "
                   "a percent with one decimal). Complete `cover`: take browsers in order of share, largest first (ties "
                   "by browser then version), until their combined share reaches the target. Add shares in tenths of a "
                   "percent, not floats. The program prints the chosen `browser version` lines, `browsers k` and "
                   "`covered x%` (one decimal)."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_COVER, stub(_SIG_COVER, _DOC_COVER, "[], 0")),
        "solution": program(_IO_COVER, '''def tenths(text):
    whole, _, frac = text.partition(".")
    return int(whole) * 10 + int((frac + "0")[:1])


''' + _SIG_COVER + f'''
    """{_DOC_COVER}"""
    goal = tenths(target)
    ranked = sorted(rows, key=lambda r: (-tenths(r[2]), r[0], r[1]))
    chosen, total = [], 0
    for browser, version, share in ranked:
        if total >= goal:
            break
        chosen.append((browser, version))
        total += tenths(share)
    return chosen, total
'''),
        "alt": _alt_cover,
        "explanation": ("Sorting by share and taking from the top until the target is reached gives the smallest set "
                        "that covers it (the greedy choice is optimal here because each browser only adds share). Doing "
                        "the sums in tenths keeps 90.0 from turning into 89.99999. It turns a debate into a support "
                        "policy anyone can recheck when the analytics change."),
        "key_justification": "Sort by share, then a cumulative cut-off.",
        "variants": variants(
            [({}, [("90\n6\nchrome 120 60.0\nsafari 17 20.0\nsamsung 23 8.0\nfirefox 121 5.0\nuc 15 4.0\nopera 100 3.0\n",
                    "chrome 120\nsafari 17\nsamsung 23\nfirefox 121\nbrowsers 4\ncovered 93.0%")]),
             ({}, [("50\n2\nb 1 50.0\na 1 50.0\n", "a 1\nbrowsers 1\ncovered 50.0%")]),
             ({}, [("99.5\n2\nx 1 60.2\ny 2 30.1\n", "x 1\ny 2\nbrowsers 2\ncovered 90.3%")])],
            _gen_cover, 7210,
            extra_hidden=[["0\n1\nz 1 5.0\n"], ["10\n3\nc 1 3.3\nc 2 3.3\nc 3 3.4\n"], ["100\n1\nonly 1 100\n"]]),
    },
    {
        "prompt": ("Dhanda Dost's bundle reached 3 MB because the charting library is pulled into the login page. Find "
                   "out what each page really loads. The first line is n, then n lines `module kb imports` (imports "
                   "comma-separated, or -; imports can form cycles), then a line of entry points. Complete `bundle_size`: "
                   "the total size of every module reachable from the entry through imports, each counted once, "
                   "including the entry. The program prints `entry kb` for each entry point, in the order given."),
        "ds_topic": "graph", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_BUNDLE, stub(_SIG_BUNDLE, _DOC_BUNDLE, "modules[entry][0]")),
        "solution": program(_IO_BUNDLE, _SIG_BUNDLE + f'''
    """{_DOC_BUNDLE}"""
    seen, stack = {{entry}}, [entry]
    while stack:                                   # depth-first search; `seen` stops cycles
        for dep in modules[stack.pop()][1]:
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return sum(modules[m][0] for m in seen)
'''),
        "alt": _alt_bundle,
        "explanation": ("Imports form a directed graph, and a page's bundle is everything reachable from its entry. A "
                        "traversal with a visited set counts shared modules once and survives import cycles. Seeing "
                        "'login 445 KB' with charts in it is the evidence for code-splitting charts behind a dynamic "
                        "import on the dashboard."),
        "key_justification": "Graph reachability with a visited set (bundle analysis).",
        "variants": variants(
            [({}, [("5\nlogin 20 auth\nauth 15 http\ndashboard 30 charts,http\ncharts 400 -\nhttp 10 -\nlogin dashboard\n",
                    "login 45\ndashboard 440")]),
             ({}, [("3\na 1 b\nb 2 a\nc 4 a\nc a\n", "c 7\na 3")]),
             ({}, [("2\nlogin 5 utils\nutils 50 -\nutils\n", "utils 50")])],
            _gen_bundle, 7220,
            extra_hidden=[["1\nsolo 9 -\nsolo\n"], ["3\na 1 b,c\nb 1 c\nc 1 -\na\n"], ["2\nx 3 x\ny 4 -\nx y\n"]]),
    },
]

# ---------------------------------------------------------------- fed-5 Sangam Tickets
_IO_CACHE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for i in range(n):
        name = data[1 + i].strip()
        print(name, cache_header(name))


main()
'''
_SIG_CACHE = "def cache_header(name):"
_DOC_CACHE = ("Return the Cache-Control value for a file: .html files get 'no-cache'; files whose name has a content "
              "hash, a part of exactly 8 lowercase hex characters between dots before the extension (app.3f9a1c2b.js), "
              "get 'public, max-age=31536000, immutable'; everything else gets 'public, max-age=3600'.")


def _alt_cache(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out = []
    for nm in rows[1:1 + n]:
        nm = nm.strip()
        parts = nm.split("/")[-1].split(".")
        if nm.endswith(".html"):
            h = "no-cache"
        elif len(parts) >= 3 and any(len(p) == 8 and all(c in "0123456789abcdef" for c in p) for p in parts[1:-1]):
            h = "public, max-age=31536000, immutable"
        else:
            h = "public, max-age=3600"
        out.append(f"{nm} {h}")
    return "\n".join(out)


_FILES = ["index.html", "seats.html", "app.3f9a1c2b.js", "vendor.0d4e5f6a.js", "styles.9c8b7a6d.css",
          "logo.svg", "app.js", "seatmap.ABCDEF12.js", "chunk.12ab34cd.min.js", "fonts/inter.5e6f7a8b.woff2",
          "manifest.json", "img/hall.1a2b3c.png"]


def _gen_cache(rng, size):
    n = {"small": 3, "medium": 8, "large": 12}[size]
    return f"{n}\n" + "\n".join(rng.sample(_FILES, n)) + "\n"


_IO_SEATS = '''
def main():
    data = sys.stdin.read().split("\\n")
    hold = int(data[0])
    n = int(data[1])
    events = []
    for i in range(n):
        t, action, seat, user = data[2 + i].split()
        events.append((int(t), action, seat, user))
    sold, rejected = run_sale(events, hold)
    for seat, user in sold:
        print(seat, user)
    print("rejected", rejected)


main()
'''
_SIG_SEATS = "def run_sale(events, hold):"
_DOC_SEATS = ("events: (second, HOLD|RELEASE|BUY, seat, user) in time order. A hold lasts `hold` seconds (it has "
              "expired at second >= start + hold). HOLD works if the seat is not sold and nobody else holds it "
              "(holding your own seat again restarts the timer). RELEASE works only for the current holder. BUY works "
              "only for the current holder of an unexpired hold, and sells the seat. Anything else is rejected. "
              "Return ([(seat, buyer)] sorted by seat, number of rejected events).")


def _alt_seats(stdin):
    rows = stdin.split("\n")
    hold = int(rows[0])
    n = int(rows[1])
    holds, sold, rej = {}, {}, 0
    for r in rows[2:2 + n]:
        t, a, s, u = r.split()
        t = int(t)
        h = holds.get(s)
        active = h is not None and t < h[1]
        if s in sold:
            rej += 1
        elif a == "HOLD":
            if active and h[0] != u:
                rej += 1
            else:
                holds[s] = (u, t + hold)
        elif a == "RELEASE":
            if active and h[0] == u:
                del holds[s]
            else:
                rej += 1
        else:
            if active and h[0] == u:
                sold[s] = u
            else:
                rej += 1
    return "\n".join([f"{s} {u}" for s, u in sorted(sold.items())] + [f"rejected {rej}"])


def _gen_seats(rng, size):
    n = {"small": 8, "medium": 30, "large": 60}[size]
    seats = [f"{r}{c}" for r in "AB" for c in range(1, 5)]
    users = ["u1", "u2", "u3", "u4"]
    t, rows = 0, []
    for _ in range(n):
        t += rng.choice([1, 5, 30, 120, 400])
        rows.append(f"{t} {rng.choice(['HOLD', 'HOLD', 'BUY', 'RELEASE'])} {rng.choice(seats)} {rng.choice(users)}")
    return f"{rng.choice([300, 600])}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["fed-5"] = [
    {
        "prompt": ("100,000 fans will load the seat map in the same minute, so static files must come from the CDN's "
                   "cache, while a new release must still reach everyone at once. The first line is n, then n file "
                   "paths. Complete `cache_header`: `.html` files get `no-cache` (always revalidate, so a new release "
                   "is picked up); files with a content hash in the name, a part of exactly 8 lowercase hex characters "
                   "between dots before the extension (like `app.3f9a1c2b.js`), get `public, max-age=31536000, "
                   "immutable`; everything else gets `public, max-age=3600`. The program prints `file header` per file."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_CACHE, stub(_SIG_CACHE, _DOC_CACHE, '"public, max-age=3600"')),
        "solution": "import re\n" + program(_IO_CACHE, _SIG_CACHE + f'''
    """{_DOC_CACHE}"""
    if name.endswith(".html"):
        return "no-cache"
    base = name.rsplit("/", 1)[-1]
    if re.search(r"\\.[0-9a-f]{{8}}\\.", base):          # .3f9a1c2b. : the content changes the name
        return "public, max-age=31536000, immutable"
    return "public, max-age=3600"
'''),
        "alt": _alt_cache,
        "explanation": ("A file whose name contains a hash of its content can be cached forever: a new version gets a "
                        "new name. The HTML that references those names must not be cached long, or users keep loading "
                        "the old release. Everything else gets a short, safe lifetime. The rule is a small pattern match "
                        "on the file name."),
        "key_justification": "Classify file names with a pattern to choose cache headers.",
        "variants": variants(
            [({}, [("3\nindex.html\napp.3f9a1c2b.js\nlogo.svg\n",
                    "index.html no-cache\napp.3f9a1c2b.js public, max-age=31536000, immutable\nlogo.svg public, max-age=3600")]),
             ({}, [("2\nseatmap.ABCDEF12.js\nchunk.12ab34cd.min.js\n",
                    "seatmap.ABCDEF12.js public, max-age=3600\nchunk.12ab34cd.min.js public, max-age=31536000, immutable")]),
             ({}, [("1\nimg/hall.1a2b3c.png\n", "img/hall.1a2b3c.png public, max-age=3600")])],
            _gen_cache, 7310,
            extra_hidden=[["1\nfonts/inter.5e6f7a8b.woff2\n"], ["2\nmanifest.json\nseats.html\n"], ["1\nx.0000000a.css\n"]]),
    },
    {
        "prompt": ("On the seat map, a fan holds a seat while paying, and the hold must expire so abandoned seats return "
                   "to the sale. The first line is the hold time in seconds, the second is n, then n events `second "
                   "action seat user` in time order (action HOLD, RELEASE or BUY). Complete `run_sale`: a hold expires at "
                   "second >= start + hold time. HOLD works if the seat is not sold and nobody else holds it (holding "
                   "your own seat again restarts the timer); RELEASE works only for the current holder; BUY works only "
                   "for the current holder of an unexpired hold and sells the seat. Everything else is rejected. The "
                   "program prints `seat buyer` for sold seats, sorted, then `rejected k`."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_SEATS, stub(_SIG_SEATS, _DOC_SEATS, "[], 0")),
        "solution": program(_IO_SEATS, _SIG_SEATS + f'''
    """{_DOC_SEATS}"""
    holder, expires, sold = {{}}, {{}}, {{}}
    rejected = 0
    for t, action, seat, user in events:
        held_by = holder.get(seat) if seat in holder and t < expires[seat] else None   # expired holds vanish
        if seat in sold:
            rejected += 1
        elif action == "HOLD" and held_by in (None, user):
            holder[seat], expires[seat] = user, t + hold
        elif action == "RELEASE" and held_by == user:
            del holder[seat], expires[seat]
        elif action == "BUY" and held_by == user:
            sold[seat] = user
        else:
            rejected += 1
    return sorted(sold.items()), rejected
'''),
        "alt": _alt_seats,
        "explanation": ("Per-seat dictionaries for the holder, the expiry time and the buyer make every event an O(1) "
                        "check. Treating an expired hold as absent, rather than running a cleanup job, means a seat "
                        "frees itself at exactly the right second. The server must enforce this; the seat map in the "
                        "browser only displays it."),
        "key_justification": "State per seat in hash maps with lazy expiry.",
        "variants": variants(
            [({}, [("600\n7\n0 HOLD A1 u1\n10 HOLD A1 u2\n20 BUY A1 u1\n30 HOLD A2 u2\n700 BUY A2 u2\n710 HOLD A2 u3\n720 BUY A2 u3\n",
                    "A1 u1\nA2 u3\nrejected 2")]),
             ({}, [("100\n3\n0 HOLD B1 u1\n50 RELEASE B1 u2\n60 RELEASE B1 u1\n", "rejected 1")]),
             ({}, [("10\n4\n0 HOLD C1 u1\n9 HOLD C1 u1\n18 BUY C1 u1\n19 HOLD C1 u2\n", "C1 u1\nrejected 1")])],
            _gen_seats, 7320,
            extra_hidden=[["5\n2\n0 HOLD Z u\n5 BUY Z u\n"], ["5\n1\n0 BUY Z u\n"], ["60\n3\n0 HOLD A u1\n60 HOLD A u2\n61 BUY A u2\n"]]),
    },
]

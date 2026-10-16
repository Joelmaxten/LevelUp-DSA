"""Code pool for Cybersecurity (cyb-2 .. cyb-5). Built and checked by scripts/build_code_pools.py."""
import html
from itertools import combinations

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- cyb-2 PaisaPe Co-operative Bank
_IO_ESC = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for i in range(n):
        print(escape_html(data[1 + i]))


main()
'''
_SIG_ESC = "def escape_html(text):"
_DOC_ESC = "Return text safe to put inside HTML: ampersand, less-than, greater-than and both quote marks become entities."


def _alt_esc(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    return "\n".join(html.escape(r, quote=True) for r in rows[1:1 + n])


_PAYLOADS = ["<script>alert(1)</script>", "Ramesh & Sons", "\"><img src=x onerror=alert(1)>", "it's fine",
             "5 < 6 > 4", "Savings A/c", "<b>bold</b>", "Tom \"TJ\" Joseph", "&amp; already", "plain text"]


def _gen_esc(rng, size):
    n = {"small": 3, "medium": 8, "large": 20}[size]
    return f"{n}\n" + "\n".join(rng.choice(_PAYLOADS) for _ in range(n)) + "\n"


_IO_IDOR = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    owners = dict(tuple(data[1 + i].split()) for i in range(n))
    m = int(data[1 + n])
    requests = [tuple(data[2 + n + i].split()) for i in range(m)]
    suspects, blocked = audit_requests(owners, requests)
    for customer, count in suspects:
        print(customer, count)
    print("blocked", blocked)


main()
'''
_SIG_IDOR = "def audit_requests(owners, requests):"
_DOC_IDOR = ("owners: {account: owning customer}. requests: list of (logged-in customer, account asked for). A request "
             "for an account the customer does not own (or that does not exist) must be blocked. Return ([(customer, "
             "blocked count)] most first, ties by customer id, total blocked).")


def _alt_idor(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    own = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    reqs = [r.split() for r in rows[2 + n:2 + n + m]]
    bad = [c for c, a in reqs if [a, c] not in own]
    names = sorted(set(bad))
    names.sort(key=lambda c: -bad.count(c))
    return "\n".join([f"{c} {bad.count(c)}" for c in names] + [f"blocked {len(bad)}"])


def _gen_idor(rng, size):
    n = {"small": 4, "medium": 10, "large": 25}[size]
    m = {"small": 6, "medium": 20, "large": 50}[size]
    accounts = [f"SB{1000 + i}" for i in range(n)]
    custs = [f"cust{i}" for i in range(1, n // 2 + 3)]
    owners = {a: rng.choice(custs) for a in accounts}
    reqs = []
    for _ in range(m):
        c = rng.choice(custs)
        mine = [a for a, o in owners.items() if o == c]
        a = rng.choice(mine) if mine and rng.random() < 0.7 else rng.choice(accounts + ["SB9999"])
        reqs.append(f"{c} {a}")
    return (f"{n}\n" + "\n".join(f"{a} {o}" for a, o in owners.items()) + f"\n{m}\n" + "\n".join(reqs) + "\n")


PROBLEMS["cyb-2"] = [
    {
        "prompt": ("The pentest showed that a customer's name or a payee note is shown on the statement page exactly as "
                   "typed, so `<script>` runs in other users' browsers. Encode output before it reaches HTML. The first "
                   "line is n, then n lines of text. Complete `escape_html` so that & becomes `&amp;`, < becomes `&lt;`, "
                   "> becomes `&gt;`, \" becomes `&quot;` and ' becomes `&#x27;`. The program prints each line encoded."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_ESC, stub(_SIG_ESC, _DOC_ESC, "text")),
        "solution": program(_IO_ESC, _SIG_ESC + f'''
    """{_DOC_ESC}"""
    # & first: replacing it later would break the entities created by the other replacements.
    for raw, safe in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;"), ("'", "&#x27;")):
        text = text.replace(raw, safe)
    return text
'''),
        "alt": _alt_esc,
        "explanation": ("Output encoding turns characters with a meaning in HTML into entities, so user text is shown as "
                        "text and never runs. The ampersand must be replaced first, otherwise `&lt;` would become "
                        "`&amp;lt;`. In a real app the template engine does this automatically; the bug appears when "
                        "someone bypasses it, for example by building HTML strings by hand."),
        "key_justification": "Context-aware output encoding (string replacement in a safe order).",
        "variants": variants(
            [({}, [("1\n<script>alert('x')</script>\n", "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;")]),
             ({}, [("2\nRamesh & Sons\nplain\n", "Ramesh &amp; Sons\nplain")]),
             ({}, [("1\n\"><img src=x>\n", "&quot;&gt;&lt;img src=x&gt;")])],
            _gen_esc, 3010,
            extra_hidden=[["1\n&lt;\n"], ["2\n'\n\"\n"], ["1\nno special characters here\n"]]),
    },
    {
        "prompt": ("Statement URLs carried a plain account number, and any logged-in customer could change it to read "
                   "someone else's statement (broken access control). Audit a day of requests. The first line is n, then "
                   "n lines `account customer` (who owns each account); then m, then m lines `customer account` (who "
                   "asked for which statement). Complete `audit_requests`: a request must be blocked unless the customer "
                   "owns that account; unknown accounts are blocked too. The program prints `customer count` for every "
                   "customer with blocked requests, most first, ties by customer id in string order, then `blocked "
                   "total`."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python", "SQL"],
        "starter": program(_IO_IDOR, stub(_SIG_IDOR, _DOC_IDOR, "[], 0")),
        "solution": program(_IO_IDOR, _SIG_IDOR + f'''
    """{_DOC_IDOR}"""
    blocked = {{}}
    for customer, account in requests:
        if owners.get(account) != customer:        # the server checks ownership on EVERY request
            blocked[customer] = blocked.get(customer, 0) + 1
    ranked = sorted(blocked.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked, sum(blocked.values())
'''),
        "alt": _alt_idor,
        "explanation": ("A dictionary from account to owner makes the authorisation check O(1) per request; the fix in "
                        "the app is the same check on the server for every request, not trusting the id in the URL. "
                        "Counting blocked requests per customer shows who was probing, which is what the incident "
                        "review needs."),
        "key_justification": "Object-level authorisation check with an ownership map.",
        "variants": variants(
            [({}, [("2\nA1 c1\nA2 c2\n5\nc1 A1\nc1 A2\nc2 A2\nc3 A1\nc1 A9\n", "c1 2\nc3 1\nblocked 3")]),
             ({}, [("1\nSB1 ravi\n2\nravi SB1\nravi SB1\n", "blocked 0")]),
             ({}, [("2\nX meena\nY meena\n3\nasif X\nasif Y\nbob X\n", "asif 2\nbob 1\nblocked 3")])],
            _gen_idor, 3020,
            extra_hidden=[["1\nA x\n1\ny A\n"], ["2\nA b\nB a\n2\na A\nb B\n"], ["1\nA a\n0\n"]]),
    },
]

# ---------------------------------------------------------------- cyb-3 Tarkash Logistics
_IO_AUTH = '''
def main():
    data = sys.stdin.read().split("\\n")
    k = int(data[0])
    n = int(data[1])
    suspects, compromised = triage(data[2:2 + n], k)
    for ip, count in suspects:
        print("suspect", ip, count)
    for ip, user in compromised:
        print("compromised", ip, user)
    if not suspects and not compromised:
        print("CLEAN")


main()
'''
_SIG_AUTH = "def triage(lines, k):"
_DOC_AUTH = ("lines: 'HH:MM:SS Failed password for USER from IP' or 'HH:MM:SS Accepted password for USER from IP', "
             "in time order. Return ([(ip, failures)] for IPs with at least k failures, most first, ties by ip; "
             "[(ip, user)] for each successful login from an IP that already had k or more failures, in log order).")


def _alt_auth(stdin):
    rows = stdin.split("\n")
    k = int(rows[0])
    n = int(rows[1])
    lines = rows[2:2 + n]
    out, fails = [], {}
    comp = []
    for ln in lines:
        p = ln.split()
        ip, user = p[-1], p[-3]
        if p[1] == "Failed":
            fails[ip] = fails.get(ip, 0) + 1
        elif fails.get(ip, 0) >= k:
            comp.append(f"compromised {ip} {user}")
    sus = sorted(((ip, c) for ip, c in fails.items() if c >= k), key=lambda x: x[0])
    sus.sort(key=lambda x: x[1], reverse=True)
    out = [f"suspect {ip} {c}" for ip, c in sus] + comp
    return "\n".join(out) or "CLEAN"


def _gen_auth(rng, size):
    n = {"small": 8, "medium": 20, "large": 34}[size]
    ips = ["203.0.113.7", "198.51.100.23", "10.0.0.5", "192.0.2.44"]
    users = ["root", "deploy", "ubuntu"]
    lines = []
    for i in range(n):
        t = f"01:{41 + i // 60:02d}:{i % 60:02d}"
        ip = rng.choice(ips)
        kind = "Accepted" if rng.random() < 0.15 else "Failed"
        lines.append(f"{t} {kind} password for {rng.choice(users)} from {ip}")
    return f"{rng.choice([2, 3, 5])}\n{n}\n" + "\n".join(lines) + "\n"


_IO_BURST = '''
def main():
    data = sys.stdin.read().split("\\n")
    k, window = map(int, data[0].split())
    n = int(data[1])
    events = []
    for i in range(n):
        clock, ip = data[2 + i].split()
        h, m, s = map(int, clock.split(":"))
        events.append((h * 3600 + m * 60 + s, ip))
    rows = bursts(events, window, k)
    if not rows:
        print("NONE")
    for ip, peak in rows:
        print(ip, peak)


main()
'''
_SIG_BURST = "def bursts(events, window, k):"
_DOC_BURST = ("events: list of (second of the day, ip) for failed logins, in time order. For each IP find the most "
              "failures inside any window of `window` seconds (times t1..t2 with t2 - t1 < window). Return [(ip, peak)] "
              "for IPs whose peak is at least k, highest first, ties by ip.")


def _alt_burst(stdin):
    rows = stdin.split("\n")
    k, w = map(int, rows[0].split())
    n = int(rows[1])
    ev = []
    for r in rows[2:2 + n]:
        c, ip = r.split()
        h, m, s = map(int, c.split(":"))
        ev.append((h * 3600 + m * 60 + s, ip))
    res = {}
    for ip in {ip for _, ip in ev}:
        ts = [t for t, i in ev if i == ip]
        res[ip] = max(sum(1 for u in ts if start <= u < start + w) for start in ts)
    out = sorted(((ip, p) for ip, p in res.items() if p >= k), key=lambda x: x[0])
    out.sort(key=lambda x: x[1], reverse=True)
    return "\n".join(f"{ip} {p}" for ip, p in out) or "NONE"


def _gen_burst(rng, size):
    n = {"small": 8, "medium": 30, "large": 70}[size]
    ips = ["203.0.113.7", "198.51.100.23", "10.0.0.5"]
    t = 3600
    rows = []
    for _ in range(n):
        t += rng.choice([1, 2, 3, 30, 90])
        rows.append(f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d} {rng.choice(ips)}")
    return f"{rng.randint(3, 8)} {rng.choice([10, 60, 120])}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["cyb-3"] = [
    {
        "prompt": ("The auth log shows thousands of failed root logins and then a success from the same address. Triage "
                   "it. The first line is k, the second is n, then n log lines in time order, each `HH:MM:SS Failed "
                   "password for USER from IP` or `HH:MM:SS Accepted password for USER from IP`. Complete `triage`. The "
                   "program prints `suspect IP count` for every IP with at least k failures (most first, ties by IP in "
                   "string order), then `compromised IP USER` for every successful login from an IP that already had k "
                   "or more failures at that moment, in log order. It prints CLEAN if there is nothing to report."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "Bash/Shell (all shells)"],
        "starter": program(_IO_AUTH, stub(_SIG_AUTH, _DOC_AUTH, "[], []")),
        "solution": program(_IO_AUTH, _SIG_AUTH + f'''
    """{_DOC_AUTH}"""
    failures, compromised = {{}}, []
    for line in lines:
        parts = line.split()
        outcome, user, ip = parts[1], parts[4], parts[6]
        if outcome == "Failed":
            failures[ip] = failures.get(ip, 0) + 1
        elif failures.get(ip, 0) >= k:          # a success right after a brute-force run
            compromised.append((ip, user))
    suspects = sorted(((ip, c) for ip, c in failures.items() if c >= k), key=lambda x: (-x[1], x[0]))
    return suspects, compromised
'''),
        "alt": _alt_auth,
        "explanation": ("Counting failures per IP in a dictionary while reading the log in order lets you test, at the "
                        "moment of each success, whether that address had just been guessing passwords. That pairing "
                        "(many failures, then a success) is the indicator of compromise that turns a noisy log into an "
                        "incident."),
        "key_justification": "Per-key counting while streaming a log in time order.",
        "variants": variants(
            [({}, [("3\n6\n01:41:00 Failed password for root from 203.0.113.7\n01:41:01 Failed password for root from 203.0.113.7\n"
                    "01:41:02 Failed password for root from 203.0.113.7\n01:42:00 Failed password for deploy from 10.0.0.5\n"
                    "01:52:00 Accepted password for root from 203.0.113.7\n07:00:00 Accepted password for deploy from 10.0.0.5\n",
                    "suspect 203.0.113.7 3\ncompromised 203.0.113.7 root")]),
             ({}, [("2\n2\n09:00:00 Accepted password for ops from 10.0.0.9\n09:01:00 Failed password for ops from 10.0.0.9\n",
                    "CLEAN")]),
             ({}, [("1\n3\n02:00:00 Failed password for root from 1.2.3.4\n02:00:01 Failed password for root from 5.6.7.8\n"
                    "02:00:02 Failed password for admin from 5.6.7.8\n", "suspect 5.6.7.8 2\nsuspect 1.2.3.4 1")])],
            _gen_auth, 3110,
            extra_hidden=[["5\n1\n00:00:00 Accepted password for root from 9.9.9.9\n"],
                          ["1\n2\n00:00:00 Failed password for a from 9.9.9.9\n00:00:01 Accepted password for b from 9.9.9.9\n"],
                          ["2\n0\n"]]),
    },
    {
        "prompt": ("A slow attacker spreads guesses out to stay under a simple daily count, so detection looks for bursts "
                   "inside a short window instead. The first line is `k w`, the second is n, then n failed logins `HH:MM:SS "
                   "IP` in time order. Complete `bursts`: for each IP find the largest number of its failures that fall "
                   "inside any w-second window (first and last time less than w seconds apart). Use a sliding window per "
                   "IP, not a scan of every pair. The program prints `IP peak` for IPs whose peak is at least k, highest "
                   "first, ties by IP in string order, or NONE."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_BURST, stub(_SIG_BURST, _DOC_BURST, "[]")),
        "solution": "from collections import deque\n" + program(_IO_BURST, _SIG_BURST + f'''
    """{_DOC_BURST}"""
    recent, peak = {{}}, {{}}
    for t, ip in events:
        q = recent.setdefault(ip, deque())
        q.append(t)
        while t - q[0] >= window:          # drop failures that fell out of the window
            q.popleft()
        peak[ip] = max(peak.get(ip, 0), len(q))
    rows = [(ip, p) for ip, p in peak.items() if p >= k]
    return sorted(rows, key=lambda r: (-r[1], r[0]))
'''),
        "alt": _alt_burst,
        "explanation": ("Keep a queue of recent failure times per IP: push each new failure, pop failures older than "
                        "the window, and the queue length is the count in the window ending now. Each time enters and "
                        "leaves once, so the whole log is O(n). This catches bursts that a per-day count would average "
                        "away."),
        "key_justification": "Sliding-window counting with a per-key deque.",
        "variants": variants(
            [({}, [("3 60\n5\n01:00:00 1.1.1.1\n01:00:10 2.2.2.2\n01:00:30 1.1.1.1\n01:00:59 1.1.1.1\n01:02:00 1.1.1.1\n",
                    "1.1.1.1 3")]),
             ({}, [("2 10\n4\n00:00:00 9.9.9.9\n00:00:10 9.9.9.9\n00:00:20 9.9.9.9\n00:00:21 8.8.8.8\n", "NONE")]),
             ({}, [("2 5\n4\n10:00:00 5.5.5.5\n10:00:01 6.6.6.6\n10:00:02 6.6.6.6\n10:00:04 5.5.5.5\n",
                    "5.5.5.5 2\n6.6.6.6 2")])],
            _gen_burst, 3120,
            extra_hidden=[["1 1\n1\n00:00:00 7.7.7.7\n"], ["3 100\n3\n00:00:00 a\n00:01:39 a\n00:01:40 a\n"], ["1 60\n0\n"]]),
    },
]

# ---------------------------------------------------------------- cyb-4 Arogya Mandir Hospitals
_IO_PATCH = '''
def main():
    data = sys.stdin.read().split("\\n")
    k = int(data[0])
    n = int(data[1])
    rows = []
    for i in range(n):
        host, cvss, exposed, critical = data[2 + i].split()
        rows.append((host, cvss, exposed == "yes", critical == "yes"))
    for host, risk in patch_first(rows, k):
        print(host, risk)


main()
'''
_SIG_PATCH = "def patch_first(rows, k):"
_DOC_PATCH = ("rows: list of (host, CVSS score as text like '9.8', internet-exposed?, patient-critical?). Risk = CVSS x 10 "
              "(an integer), doubled if exposed, doubled again if critical. Return the k riskiest as (host, risk), "
              "highest first, ties by host.")


def _alt_patch(stdin):
    rows = stdin.split("\n")
    k = int(rows[0])
    n = int(rows[1])
    items = []
    for r in rows[2:2 + n]:
        h, c, e, cr = r.split()
        whole, _, frac = c.partition(".")
        risk = int(whole) * 10 + int((frac or "0")[:1])
        risk *= 2 if e == "yes" else 1
        risk *= 2 if cr == "yes" else 1
        items.append((h, risk))
    items.sort(key=lambda x: x[0])
    items.sort(key=lambda x: x[1], reverse=True)
    return "\n".join(f"{h} {r}" for h, r in items[:k])


def _gen_patch(rng, size):
    n = {"small": 5, "medium": 20, "large": 50}[size]
    rows = [f"ws-{i:03d} {rng.randint(10, 100) / 10:.1f} {rng.choice(['yes', 'no'])} {rng.choice(['yes', 'no', 'no'])}"
            for i in range(n)]
    return f"{rng.randint(1, 5)}\n{n}\n" + "\n".join(rows) + "\n"


_IO_SEG = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rules = [tuple(data[1 + i].split()) for i in range(n)]
    source, target = data[1 + n].split()
    hops, reachable = reach(rules, source, target)
    print("BLOCKED" if hops is None else f"hops {hops}")
    print("reachable", " ".join(reachable) if reachable else "-")


main()
'''
_SIG_SEG = "def reach(rules, source, target):"
_DOC_SEG = ("rules: list of (from_zone, to_zone): traffic allowed in that direction. Return (fewest hops from source "
            "to target, or None if it cannot be reached; every zone reachable from source except source itself, "
            "sorted).")


def _alt_seg(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    rules = [tuple(r.split()) for r in rows[1:1 + n]]
    src, dst = rows[1 + n].split()
    dist = {src: 0}
    changed = True
    while changed:
        changed = False
        for a, b in rules:
            if a in dist and (b not in dist or dist[a] + 1 < dist[b]):
                dist[b] = dist[a] + 1
                changed = True
    others = sorted(z for z in dist if z != src)
    first = f"hops {dist[dst]}" if dst in dist else "BLOCKED"
    return f"{first}\nreachable {' '.join(others) or '-'}"


_ZONES = ["guest_wifi", "lobby_pcs", "ward_pcs", "nurse_station", "pharmacy", "billing", "admin", "icu_monitor",
          "lab", "radiology", "vpn"]


def _gen_seg(rng, size):
    n = {"small": 4, "medium": 10, "large": 20}[size]
    rules = set()
    while len(rules) < n:
        a, b = rng.sample(_ZONES, 2)
        rules.add((a, b))
    src, dst = rng.sample(_ZONES, 2)
    return f"{n}\n" + "\n".join(f"{a} {b}" for a, b in sorted(rules)) + f"\n{src} {dst}\n"


PROBLEMS["cyb-4"] = [
    {
        "prompt": ("With one patch window a month, the team must decide which machines to patch first. The first line is "
                   "k, the second is n, then n lines `host cvss exposed critical` (CVSS like 9.8; exposed and critical "
                   "are yes or no). Complete `patch_first`: risk = CVSS x 10 as a whole number, doubled if the host is "
                   "internet-exposed and doubled again if it is patient-critical. Parse the score without floating-point "
                   "surprises. The program prints the k riskiest hosts as `host risk`, highest first, ties by host."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_PATCH, stub(_SIG_PATCH, _DOC_PATCH, "[]")),
        "solution": program(_IO_PATCH, _SIG_PATCH + f'''
    """{_DOC_PATCH}"""
    scored = []
    for host, cvss, exposed, critical in rows:
        whole, _, tenth = cvss.partition(".")
        risk = int(whole) * 10 + int(tenth[:1] or 0)      # '9.8' -> 98 exactly, no float rounding
        if exposed:
            risk *= 2
        if critical:
            risk *= 2
        scored.append((host, risk))
    return sorted(scored, key=lambda r: (-r[1], r[0]))[:k]
'''),
        "alt": _alt_patch,
        "explanation": ("A score that combines severity with exposure and business impact puts an internet-facing ICU "
                        "system ahead of a higher-CVSS machine nobody can reach. Parsing '9.8' into the integer 98 "
                        "avoids float(9.8) * 10 giving 98.00000000000001, and one sort with a composite key ranks them."),
        "key_justification": "Risk scoring then a stable multi-key sort.",
        "variants": variants(
            [({}, [("2\n3\nh1 9.8 no no\nh2 7.5 yes no\nh3 6.0 yes yes\n", "h3 240\nh2 150")]),
             ({}, [("3\n3\nicu 5.0 no yes\nlab 5.0 yes no\nadm 9.9 no no\n", "icu 100\nlab 100\nadm 99")]),
             ({}, [("1\n2\nx 10.0 yes yes\ny 4.2 no no\n", "x 400")])],
            _gen_patch, 3210,
            extra_hidden=[["5\n1\nonly 0.1 no no\n"], ["2\n2\nb 7.0 no no\na 7.0 no no\n"], ["1\n2\np 3.3 yes yes\nq 6.6 yes no\n"]]),
    },
    {
        "prompt": ("Segmentation is meant to keep the guest Wi-Fi away from the ICU monitors, but nobody has checked "
                   "what the firewall rules really allow. The first line is n, then n rules `from_zone to_zone` (traffic "
                   "allowed in that direction only), then one line `source target`. Complete `reach` using a "
                   "breadth-first search over the zones. The program prints `hops h` (the fewest rules an attacker must "
                   "pass through) or BLOCKED, then `reachable` followed by every zone reachable from the source, sorted, "
                   "or `-` if none."),
        "ds_topic": "graph", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_SEG, stub(_SIG_SEG, _DOC_SEG, "None, []")),
        "solution": "from collections import deque\n" + program(_IO_SEG, _SIG_SEG + f'''
    """{_DOC_SEG}"""
    graph = {{}}
    for a, b in rules:
        graph.setdefault(a, []).append(b)
    dist = {{source: 0}}
    queue = deque([source])
    while queue:
        zone = queue.popleft()
        for nxt in graph.get(zone, []):
            if nxt not in dist:                  # BFS: the first visit is the shortest
                dist[nxt] = dist[zone] + 1
                queue.append(nxt)
    reachable = sorted(z for z in dist if z != source)
    return dist.get(target), reachable
'''),
        "alt": _alt_seg,
        "explanation": ("Zones are nodes and allow-rules are directed edges, so 'can the guest network reach the ICU?' "
                        "is graph reachability. Breadth-first search visits zones in order of distance, so the first "
                        "time it reaches the target is the shortest path. The full reachable set shows every zone the "
                        "rules expose, not just the one asked about."),
        "key_justification": "Directed graph reachability with BFS.",
        "variants": variants(
            [({}, [("4\nguest_wifi lobby_pcs\nlobby_pcs ward_pcs\nward_pcs icu_monitor\nadmin icu_monitor\nguest_wifi icu_monitor\n",
                    "hops 3\nreachable icu_monitor lobby_pcs ward_pcs")]),
             ({}, [("2\nicu_monitor guest_wifi\nadmin lab\nguest_wifi icu_monitor\n", "BLOCKED\nreachable -")]),
             ({}, [("3\na b\nb c\na c\na c\n", "hops 1\nreachable b c")])],
            _gen_seg, 3220,
            extra_hidden=[["1\nx y\ny x\n"], ["2\na b\nb a\na a\n"], ["3\na b\nb c\nc a\nb a\n"]]),
    },
]

# ---------------------------------------------------------------- cyb-5 Tarang Pay
STRIDE = "STRIDE"

_IO_STRIDE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    findings = []
    for i in range(n):
        fid, category, likelihood, impact = data[1 + i].split()
        findings.append((fid, category, int(likelihood), int(impact)))
    summary, top = stride_summary(findings)
    for category, count, worst in summary:
        print(category, count, worst)
    print("top", *top) if top else print("top -")


main()
'''
_SIG_STRIDE = "def stride_summary(findings):"
_DOC_STRIDE = ("findings: list of (id, category letter in S T R I D E, likelihood 1-5, impact 1-5). Score = likelihood x "
               "impact. Return ([(category, count, highest score or 0)] in the order S, T, R, I, D, E; (id, score) of "
               "the highest-scoring finding, ties by id, or None).")


def _alt_stride(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    f = [r.split() for r in rows[1:1 + n]]
    out = []
    for c in STRIDE:
        sc = [int(l) * int(i) for _, cat, l, i in f if cat == c]
        out.append(f"{c} {len(sc)} {max(sc) if sc else 0}")
    if f:
        best = min(f, key=lambda x: (-int(x[2]) * int(x[3]), x[0]))
        out.append(f"top {best[0]} {int(best[2]) * int(best[3])}")
    else:
        out.append("top -")
    return "\n".join(out)


def _gen_stride(rng, size):
    n = {"small": 4, "medium": 15, "large": 40}[size]
    rows = [f"F{i + 1:02d} {rng.choice(STRIDE)} {rng.randint(1, 5)} {rng.randint(1, 5)}" for i in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_KNAP = '''
def main():
    data = sys.stdin.read().split("\\n")
    budget = int(data[0])
    n = int(data[1])
    controls = []
    for i in range(n):
        name, cost, reduction = data[2 + i].split()
        controls.append((name, int(cost), int(reduction)))
    best, cost = best_controls(controls, budget)
    print("max_reduction", best)
    print("cost", cost)


main()
'''
_SIG_KNAP = "def best_controls(controls, budget):"
_DOC_KNAP = ("controls: list of (name, cost, yearly loss it removes), in thousands of rupees; each can be bought once. "
             "Return (the largest total reduction within the budget, the smallest total cost that achieves it).")


def _alt_knap(stdin):
    rows = stdin.split("\n")
    budget = int(rows[0])
    n = int(rows[1])
    c = [r.split() for r in rows[2:2 + n]]
    best = (0, 0)
    for k in range(1, n + 1):
        for combo in combinations(c, k):
            cost = sum(int(x[1]) for x in combo)
            red = sum(int(x[2]) for x in combo)
            if cost <= budget and (red > best[0] or (red == best[0] and cost < best[1])):
                best = (red, cost)
    return f"max_reduction {best[0]}\ncost {best[1]}"


def _gen_knap(rng, size):
    n = {"small": 4, "medium": 7, "large": 10}[size]
    budget = rng.randint(10, 60)
    rows = [f"ctrl{i + 1} {rng.randint(2, 25)} {rng.randint(5, 120)}" for i in range(n)]
    return f"{budget}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["cyb-5"] = [
    {
        "prompt": ("The team modelled threats with STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, "
                   "Denial of service, Elevation of privilege). Summarise the findings. The first line is n, then n lines "
                   "`id category likelihood impact`, with category one of S T R I D E and both ratings 1-5. Complete "
                   "`stride_summary`: score = likelihood x impact. The program prints one line per category in the order "
                   "S T R I D E, `category count highest_score` (0 when there are none), then `top id score` for the "
                   "highest-scoring finding, ties by id, or `top -`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_STRIDE, stub(_SIG_STRIDE, _DOC_STRIDE, "[], None")),
        "solution": program(_IO_STRIDE, _SIG_STRIDE + f'''
    """{_DOC_STRIDE}"""
    count = {{c: 0 for c in "STRIDE"}}
    worst = {{c: 0 for c in "STRIDE"}}
    top = None
    for fid, category, likelihood, impact in findings:
        score = likelihood * impact
        count[category] += 1
        worst[category] = max(worst[category], score)
        if top is None or (-score, fid) < (-top[1], top[0]):
            top = (fid, score)
    return [(c, count[c], worst[c]) for c in "STRIDE"], top
'''),
        "alt": _alt_stride,
        "explanation": ("A dictionary per STRIDE letter, pre-filled so empty categories still show 0, summarises the "
                        "model in one pass. Empty categories are worth seeing: zero Repudiation findings in a payments "
                        "app usually means nobody looked, not that there is no risk."),
        "key_justification": "Category tallies in pre-seeded hash maps.",
        "variants": variants(
            [({}, [("4\nF1 S 3 4\nF2 I 5 5\nF3 S 2 2\nF4 D 4 3\n", "S 2 12\nT 0 0\nR 0 0\nI 1 25\nD 1 12\nE 0 0\ntop F2 25")]),
             ({}, [("2\nB E 2 3\nA T 3 2\n", "S 0 0\nT 1 6\nR 0 0\nI 0 0\nD 0 0\nE 1 6\ntop A 6")]),
             ({}, [("1\nX R 1 1\n", "S 0 0\nT 0 0\nR 1 1\nI 0 0\nD 0 0\nE 0 0\ntop X 1")])],
            _gen_stride, 3310,
            extra_hidden=[["0\n"], ["3\nF9 D 5 5\nF10 D 5 5\nF2 S 1 1\n"], ["2\nZ I 2 2\nY I 4 1\n"]]),
    },
    {
        "prompt": ("The review has a fixed security budget and a list of controls, each with a cost and the expected "
                   "yearly loss it removes. Choose the best set. The first line is the budget, the second is n, then n "
                   "lines `control cost reduction` (all in thousands of rupees; each control can be bought once). "
                   "Complete `best_controls` without trying every subset (use dynamic programming over the budget). The "
                   "program prints `max_reduction R`, the largest total reduction that fits the budget, and `cost C`, the "
                   "smallest total cost that achieves R."),
        "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_KNAP, stub(_SIG_KNAP, _DOC_KNAP, "0, 0")),
        "solution": program(_IO_KNAP, _SIG_KNAP + f'''
    """{_DOC_KNAP}"""
    NONE = -1
    best = [NONE] * (budget + 1)       # best[c] = most reduction for spending exactly c
    best[0] = 0
    for _, cost, reduction in controls:
        for c in range(budget, cost - 1, -1):          # backwards: each control used at most once
            if best[c - cost] != NONE and best[c - cost] + reduction > best[c]:
                best[c] = best[c - cost] + reduction
    top = max(best)
    return top, best.index(top)                        # the first index is the cheapest way to reach it
'''),
        "alt": _alt_knap,
        "explanation": ("This is the 0/1 knapsack problem. An array indexed by money spent stores the best reduction for "
                        "each exact spend; looping the budget backwards stops a control being counted twice. The run "
                        "time is O(n x budget) instead of O(2^n) subsets, and the smallest spend that reaches the best "
                        "value is simply the first index holding it."),
        "key_justification": "0/1 knapsack with a one-dimensional DP array.",
        "variants": variants(
            [({}, [("10\n4\nc1 5 40\nc2 4 30\nc3 6 50\nc4 3 25\n", "max_reduction 80\ncost 10")]),
             ({}, [("5\n2\nmfa 6 90\nwaf 7 70\n", "max_reduction 0\ncost 0")]),
             ({}, [("12\n3\nedr 6 60\nbackup 6 60\nsiem 12 120\n", "max_reduction 120\ncost 12")])],
            _gen_knap, 3320,
            extra_hidden=[["0\n1\na 1 5\n"], ["20\n1\na 20 7\n"], ["9\n3\na 3 10\nb 3 10\nc 4 20\n"]]),
    },
]

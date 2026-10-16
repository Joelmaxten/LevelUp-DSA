"""Code pool for UI/UX Design (uxd-2 .. uxd-5). Built and checked by scripts/build_code_pools.py."""
import re

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- uxd-2 Saheli
_IO_TALLY = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    sessions = []
    for i in range(n):
        participant, task, outcome, seconds = data[1 + i].split()
        sessions.append((participant, task, outcome, int(seconds)))
    for task, pct, median in task_results(sessions):
        print(task, f"{pct}%", "-" if median is None else format(median, ".1f"))


main()
'''
_SIG_TALLY = "def task_results(sessions):"
_DOC_TALLY = ("sessions: (participant, task, success|fail|abandon, seconds). Per task, sorted by task: the success "
              "rate as a whole percent rounded down, and the median time of the SUCCESSFUL attempts (the mean of the "
              "two middle values for an even count), or None if nobody succeeded. Return [(task, pct, median)].")


def _alt_tally(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for t in sorted({r[1] for r in rows}):
        mine = [r for r in rows if r[1] == t]
        ok = sorted(int(r[3]) for r in mine if r[2] == "success")
        pct = 100 * len(ok) // len(mine)
        if not ok:
            med = "-"
        else:
            k = len(ok)
            med = format(ok[k // 2] if k % 2 else (ok[k // 2 - 1] + ok[k // 2]) / 2, ".1f")
        out.append(f"{t} {pct}% {med}")
    return "\n".join(out)


def _gen_tally(rng, size):
    n = {"small": 5, "medium": 20, "large": 50}[size]
    tasks = ["signup", "find_article", "log_period", "book_consult"]
    rows = [f"p{rng.randint(1, 12)} {rng.choice(tasks)} {rng.choice(['success', 'success', 'fail', 'abandon'])} "
            f"{rng.randint(15, 240)}" for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_CARDS = '''
def main():
    data = sys.stdin.read().split("\\n")
    participants, threshold = map(int, data[0].split())
    n = int(data[1])
    groups = []
    for i in range(n):
        participant, _, cards = data[2 + i].split()
        groups.append((participant, cards.split(",")))
    for cluster in card_clusters(groups, participants, threshold):
        print(", ".join(cluster))


main()
'''
_SIG_CARDS = "def card_clusters(groups, participants, threshold):"
_DOC_CARDS = ("groups: (participant, [cards in one pile]). Two cards are linked when at least `threshold` percent of "
              "participants put them in the same pile. Clusters are the connected groups of linked cards (a card with "
              "no links is a cluster on its own). Return clusters, each sorted, ordered by their first card.")


def _alt_cards(stdin):
    rows = stdin.split("\n")
    p, t = map(int, rows[0].split())
    n = int(rows[1])
    piles = [r.split()[2].split(",") for r in rows[2:2 + n]]
    who = [r.split()[0] for r in rows[2:2 + n]]
    cards = sorted({c for pile in piles for c in pile})
    label = {c: c for c in cards}
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            together = {who[k] for k, pile in enumerate(piles) if a in pile and b in pile}
            if len(together) * 100 >= t * p:
                old, new = label[b], label[a]
                for c in cards:
                    if label[c] == old:
                        label[c] = new
    groups = {}
    for c in cards:
        groups.setdefault(label[c], []).append(c)
    return "\n".join(", ".join(sorted(g)) for g in sorted(groups.values(), key=lambda g: sorted(g)[0]))


_CARDS = ["periods", "tracker", "pregnancy", "doctors", "video", "articles", "nutrition", "pcos", "payments", "profile"]


def _gen_cards(rng, size):
    p = {"small": 3, "medium": 5, "large": 8}[size]
    cards = rng.sample(_CARDS, {"small": 5, "medium": 7, "large": 10}[size])
    rows = []
    for k in range(1, p + 1):
        shuffled = cards[:]
        rng.shuffle(shuffled)
        cut = sorted(rng.sample(range(1, len(cards)), rng.randint(1, 3)))
        for g, (a, b) in enumerate(zip([0] + cut, cut + [len(cards)])):
            rows.append(f"p{k} g{g} {','.join(shuffled[a:b])}")
    return f"{p} {rng.choice([50, 60, 75])}\n{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["uxd-2"] = [
    {
        "prompt": ("Most people leave Saheli during sign-up and nobody knows why, so the team ran usability tests. "
                   "Summarise them. The first line is n, then n sessions `participant task outcome seconds` (outcome "
                   "success, fail or abandon). Complete `task_results`: per task, sorted by name, the success rate as a "
                   "whole percent rounded down, and the median time of the successful attempts only (the mean of the "
                   "two middle values when there is an even number), to one decimal, or `-` if nobody succeeded. The "
                   "program prints `task pct% median`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_TALLY, stub(_SIG_TALLY, _DOC_TALLY, "[]")),
        "solution": program(_IO_TALLY, _SIG_TALLY + f'''
    """{_DOC_TALLY}"""
    attempts, times = {{}}, {{}}
    for _, task, outcome, seconds in sessions:
        attempts[task] = attempts.get(task, 0) + 1
        if outcome == "success":
            times.setdefault(task, []).append(seconds)
    out = []
    for task in sorted(attempts):
        ok = sorted(times.get(task, []))
        median = None
        if ok:
            mid = len(ok) // 2
            median = ok[mid] if len(ok) % 2 else (ok[mid - 1] + ok[mid]) / 2
        out.append((task, 100 * len(ok) // attempts[task], median))
    return out
'''),
        "explanation": ("Grouping sessions by task gives the completion rate, the first number in any usability report. "
                        "The median time is used rather than the mean because one participant who got stuck for "
                        "minutes would drag a mean far away from the typical experience; and only successful attempts "
                        "count, since a give-up time is not a task time."),
        "key_justification": "Group by task; success rate and median of successful times.",
        "alt": _alt_tally,
        "variants": variants(
            [({}, [("5\np1 signup success 40\np2 signup abandon 90\np3 signup success 60\np4 signup success 50\np1 tracker fail 30\n",
                    "signup 75% 50.0\ntracker 0% -")]),
             ({}, [("2\na consult success 30\nb consult success 45\n", "consult 100% 37.5")]),
             ({}, [("3\nx find success 10\ny find fail 99\nz find abandon 5\n", "find 33% 10.0")])],
            _gen_tally, 11010,
            extra_hidden=[["1\np t fail 1\n"], ["4\na t success 4\nb t success 1\nc t success 3\nd t success 2\n"],
                          ["2\na b success 7\na a success 9\n"]]),
    },
    {
        "prompt": ("Before redesigning Saheli's menus, participants sorted topic cards into piles that made sense to them "
                   "(an open card sort). Find the groups they agree on. The first line is `participants threshold` "
                   "(threshold as a percent), the second is n, then n piles `participant pile_name card,card,...`. "
                   "Complete `card_clusters`: two cards are linked when at least threshold% of participants put them in "
                   "the same pile; clusters are connected groups of linked cards, and a card with no links is a cluster "
                   "of its own. The program prints each cluster as `card, card` (sorted), clusters ordered by their "
                   "first card."),
        "ds_topic": "graph", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CARDS, stub(_SIG_CARDS, _DOC_CARDS, "[[c] for _, pile in groups for c in pile]")),
        "solution": program(_IO_CARDS, _SIG_CARDS + f'''
    """{_DOC_CARDS}"""
    together = {{}}                                  # (card a, card b) -> participants who grouped them
    cards = set()
    for participant, pile in groups:
        cards.update(pile)
        for i, a in enumerate(pile):
            for b in pile[i + 1:]:
                together.setdefault(tuple(sorted((a, b))), set()).add(participant)
    links = {{c: [] for c in cards}}
    for (a, b), people in together.items():
        if len(people) * 100 >= threshold * participants:
            links[a].append(b)
            links[b].append(a)
    seen, clusters = set(), []
    for card in sorted(cards):                      # connected components by depth-first search
        if card in seen:
            continue
        stack, group = [card], []
        seen.add(card)
        while stack:
            c = stack.pop()
            group.append(c)
            for nxt in links[c]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        clusters.append(sorted(group))
    return clusters
'''),
        "explanation": ("Counting, for every pair of cards, how many people piled them together gives a similarity "
                        "matrix; keeping strong pairs as edges and taking connected components turns it into the menu "
                        "groups users expect. It replaces the founders' opinions with evidence of how users think."),
        "key_justification": "Pair co-occurrence, then connected components in a graph.",
        "alt": _alt_cards,
        "variants": variants(
            [({}, [("3 60\n7\np1 g1 periods,tracker\np1 g2 doctors,video\np2 a periods,tracker,pregnancy\np2 b doctors,video\n"
                    "p3 x tracker,pregnancy\np3 y doctors\np3 z video,periods\n", "doctors, video\nperiods, pregnancy, tracker")]),
             ({}, [("2 100\n2\np1 a x,y\np2 b x\n", "x\ny")]),
             ({}, [("1 50\n2\np1 a c,b\np1 b a\n", "a\nb, c")])],
            _gen_cards, 11020,
            extra_hidden=[["1 100\n1\np1 g only\n"], ["2 50\n2\np1 g a,b,c\np2 g c,d\n"], ["4 75\n4\na g x,y\nb g x,y\nc g x\nd g y\n"]]),
    },
]

# ---------------------------------------------------------------- uxd-3 Kisan Rin
_IO_FUNNEL = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    steps = []
    for i in range(n):
        name, reached = data[1 + i].split()
        steps.append((name, int(reached)))
    rows, worst = funnel(steps)
    for name, reached, kept in rows:
        print(name, reached, format(kept, ".1f") + "%")
    print("biggest_drop", worst[0], format(worst[1], ".1f") + "%")


main()
'''
_SIG_FUNNEL = "def funnel(steps):"
_DOC_FUNNEL = ("steps: (step, people who reached it), in form order. kept = reached / previous step's reached x 100 "
               "(the first step is 100). Return ([(step, reached, kept)], (step with the biggest drop = 100 - kept, "
               "that drop)), the earliest step on a tie; the first step never counts as a drop.")


def _alt_funnel(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    s = [r.split() for r in rows[1:1 + n]]
    out, worst = [], None
    for i, (nm, r) in enumerate(s):
        kept = 100.0 if i == 0 else 100 * int(r) / int(s[i - 1][1])
        out.append(f"{nm} {r} {format(kept, '.1f')}%")
        if i and (worst is None or 100 - kept > worst[1] + 1e-12):
            worst = (nm, 100 - kept)
    return "\n".join(out + [f"biggest_drop {worst[0]} {format(worst[1], '.1f')}%"])


def _gen_funnel(rng, size):
    steps = ["open", "personal", "aadhaar", "land", "crop", "bank", "documents", "review", "submit"]
    n = {"small": 3, "medium": 6, "large": 9}[size]
    v, rows = rng.randint(800, 5000), []
    for s in steps[:n]:
        rows.append(f"{s} {v}")
        v = max(1, int(v * rng.uniform(0.35, 0.98)))
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_VALID = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for i in range(n):
        field, _, value = data[1 + i].partition(" ")
        message = check_field(field, value.strip())
        print(field, "OK" if message is None else "- " + message)


main()
'''
_SIG_VALID = "def check_field(field, value):"
_DOC_VALID = ("Return None if valid, else the friendly message. name: not empty -> 'Enter your name'. aadhaar: 12 digits "
              "(spaces allowed between them) -> 'Aadhaar must be 12 digits'. mobile: 10 digits starting with 6-9 -> "
              "'Mobile must be 10 digits starting with 6, 7, 8 or 9'. ifsc: 4 capital letters, a 0, then 6 capital "
              "letters or digits -> 'IFSC looks like SBIN0001234'. acres: a number above 0 with at most 2 decimals -> "
              "'Enter land in acres, like 2.5'.")

_MSGS = {"name": "Enter your name", "aadhaar": "Aadhaar must be 12 digits",
         "mobile": "Mobile must be 10 digits starting with 6, 7, 8 or 9", "ifsc": "IFSC looks like SBIN0001234",
         "acres": "Enter land in acres, like 2.5"}


def _alt_valid(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out = []
    for r in rows[1:1 + n]:
        field, _, value = r.partition(" ")
        v = value.strip()
        if field == "name":
            ok = v != ""
        elif field == "aadhaar":
            d = v.replace(" ", "")
            ok = len(d) == 12 and d.isdigit() and d.isascii()
        elif field == "mobile":
            ok = len(v) == 10 and v.isdigit() and v.isascii() and v[0] in "6789"
        elif field == "ifsc":
            ok = (len(v) == 11 and v[:4].isalpha() and v[:4].isupper() and v[:4].isascii() and v[4] == "0"
                  and all(c.isdigit() or ("A" <= c <= "Z") for c in v[5:]))
        else:
            whole, dot, frac = v.partition(".")
            ok = (whole.isdigit() and whole.isascii() and (not dot or (frac.isdigit() and 1 <= len(frac) <= 2))
                  and float(v) > 0)
        out.append(f"{field} {'OK' if ok else '- ' + _MSGS[field]}")
    return "\n".join(out)


_VALUES = {"name": ["Sakharam Patil", "", "  "], "aadhaar": ["1234 5678 9012", "123456789012", "12345678901", "1234-5678-9012"],
           "mobile": ["9876543210", "5876543210", "98765 43210", "987654321"],
           "ifsc": ["SBIN0001234", "sbin0001234", "SBIN1001234", "HDFC0ABC123", "SBI0001234"],
           "acres": ["2.5", "0", "3", "1.255", "-2", "0.01", "2.", "abc"]}


def _gen_valid(rng, size):
    n = {"small": 5, "medium": 12, "large": 25}[size]
    rows = []
    for _ in range(n):
        f = rng.choice(list(_VALUES))
        rows.append(f"{f} {rng.choice(_VALUES[f])}".rstrip())
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["uxd-3"] = [
    {
        "prompt": ("Analytics say 60% of applicants abandon the loan form, but not where. Build the funnel. The first "
                   "line is n, then n steps `step reached` in form order (people who reached each step). Complete "
                   "`funnel`: kept = reached / reached at the previous step x 100 (100 for the first step). The program "
                   "prints `step reached kept%` per step (one decimal), then `biggest_drop step x%`, the step losing the "
                   "largest share of the people who reached the step before it (the earliest on a tie)."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_FUNNEL, stub(_SIG_FUNNEL, _DOC_FUNNEL, "[(s, r, 100.0) for s, r in steps], (steps[-1][0], 0.0)")),
        "solution": program(_IO_FUNNEL, _SIG_FUNNEL + f'''
    """{_DOC_FUNNEL}"""
    rows, worst = [], None
    for i, (name, reached) in enumerate(steps):
        kept = 100.0 if i == 0 else 100 * reached / steps[i - 1][1]   # relative to the step before
        rows.append((name, reached, kept))
        if i and (worst is None or 100 - kept > worst[1]):
            worst = (name, 100 - kept)
    return rows, worst
'''),
        "explanation": ("Comparing each step with the one before it (not with the first) shows where people actually "
                        "leave. The step with the biggest relative drop is the first place to redesign; a funnel turns "
                        "'60% abandon' into 'the bank details screen loses more than half'."),
        "key_justification": "Step-over-step ratios across an ordered array.",
        "alt": _alt_funnel,
        "variants": variants(
            [({}, [("5\nopen 1000\npersonal 800\nland 700\nbank 300\nsubmit 280\n",
                    "open 1000 100.0%\npersonal 800 80.0%\nland 700 87.5%\nbank 300 42.9%\nsubmit 280 93.3%\nbiggest_drop bank 57.1%")]),
             ({}, [("2\nstart 10\nend 10\n", "start 10 100.0%\nend 10 100.0%\nbiggest_drop end 0.0%")]),
             ({}, [("3\na 100\nb 50\nc 25\n", "a 100 100.0%\nb 50 50.0%\nc 25 50.0%\nbiggest_drop b 50.0%")])],
            _gen_funnel, 11110,
            extra_hidden=[["2\nx 3\ny 1\n"], ["3\na 9\nb 9\nc 3\n"], ["4\na 7\nb 6\nc 5\nd 4\n"]]),
    },
    {
        "prompt": ("Error messages appeared only after submitting, in a red banner at the top. Inline validation tells "
                   "the farmer what to fix, next to the field, in plain words. The first line is n, then n lines `field "
                   "value` (the value may be empty or contain spaces). Complete `check_field` for these fields: name "
                   "must not be empty (`Enter your name`); aadhaar must be 12 digits, spaces allowed between them "
                   "(`Aadhaar must be 12 digits`); mobile must be 10 digits starting with 6, 7, 8 or 9 (`Mobile must be "
                   "10 digits starting with 6, 7, 8 or 9`); ifsc is 4 capital letters, a 0, then 6 capital letters or "
                   "digits (`IFSC looks like SBIN0001234`); acres is a number above 0 with at most 2 decimals (`Enter "
                   "land in acres, like 2.5`). The program prints `field OK` or `field - message`."),
        "ds_topic": "string", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_VALID, stub(_SIG_VALID, _DOC_VALID, "None")),
        "solution": "import re\n" + program(_IO_VALID, _SIG_VALID + f'''
    """{_DOC_VALID}"""
    rules = {{
        "name": (lambda v: v != "", "Enter your name"),
        "aadhaar": (lambda v: re.fullmatch(r"[0-9]{{12}}", v.replace(" ", "")), "Aadhaar must be 12 digits"),
        "mobile": (lambda v: re.fullmatch(r"[6-9][0-9]{{9}}", v), "Mobile must be 10 digits starting with 6, 7, 8 or 9"),
        "ifsc": (lambda v: re.fullmatch(r"[A-Z]{{4}}0[A-Z0-9]{{6}}", v), "IFSC looks like SBIN0001234"),
        "acres": (lambda v: re.fullmatch(r"[0-9]+(\\.[0-9]{{1,2}})?", v) and float(v) > 0, "Enter land in acres, like 2.5"),
    }}
    check, message = rules[field]
    return None if check(value) else message
'''),
        "explanation": ("Each field gets a precise rule (a small pattern) and a message that says how to fix it, shown "
                        "next to that field as soon as it is filled. Accepting spaces in an Aadhaar number, as people "
                        "write it on the card, is kinder than rejecting it; the rule should fit the user, not the "
                        "database."),
        "key_justification": "Field validation with patterns and actionable messages.",
        "alt": _alt_valid,
        "variants": variants(
            [({}, [("5\nname Sakharam Patil\naadhaar 1234 5678 9012\nmobile 5876543210\nifsc sbin0001234\nacres 2.5\n",
                    "name OK\naadhaar OK\nmobile - Mobile must be 10 digits starting with 6, 7, 8 or 9\n"
                    "ifsc - IFSC looks like SBIN0001234\nacres OK")]),
             ({}, [("3\nname\nacres 0\naadhaar 12345678901\n",
                    "name - Enter your name\nacres - Enter land in acres, like 2.5\naadhaar - Aadhaar must be 12 digits")]),
             ({}, [("2\nifsc HDFC0ABC123\nacres 1.255\n", "ifsc OK\nacres - Enter land in acres, like 2.5")])],
            _gen_valid, 11120,
            extra_hidden=[["1\nmobile 9876543210\n"], ["2\nacres 2.\nifsc SBIN1001234\n"], ["1\naadhaar 1234-5678-9012\n"]]),
    },
]

# ---------------------------------------------------------------- uxd-4 Bachat Bank
_IO_STYLES = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = [tuple(data[1 + i].split()) for i in range(n)]
    report, to_fix = style_audit(rows)
    for component, styles in report:
        print(f"{component} {len(styles)}:", " ".join(styles))
    print("to_fix", to_fix)


main()
'''
_SIG_STYLES = "def style_audit(rows):"
_DOC_STYLES = ("rows: (screen, component, style) found across the app. Return ([(component, its distinct styles "
               "sorted)] sorted by component, number of components with more than one style).")


def _alt_styles(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out, fix = [], 0
    for c in sorted({r[1] for r in rows}):
        st = sorted({r[2] for r in rows if r[1] == c})
        fix += len(st) > 1
        out.append(f"{c} {len(st)}: {' '.join(st)}")
    return "\n".join(out + [f"to_fix {fix}"])


def _gen_styles(rng, size):
    n = {"small": 5, "medium": 20, "large": 50}[size]
    comps = {"button": ["primary_blue", "primary_green", "pill_dark"], "date_picker": ["calendar", "dropdowns"],
             "input": ["outlined"], "card": ["flat", "shadow"], "toast": ["top", "bottom"]}
    screens = ["login", "open_account", "transfer", "loans", "cards", "profile"]
    rows = []
    for _ in range(n):
        c = rng.choice(list(comps))
        rows.append(f"{rng.choice(screens)} {c} {rng.choice(comps[c])}")
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_CONTRAST = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for i in range(n):
        fg, bg = data[1 + i].split()
        r = contrast_ratio(fg, bg)
        print(f"{fg} {bg} ratio {r:.2f} normal", "PASS" if r >= 4.5 else "FAIL", "large", "PASS" if r >= 3 else "FAIL")


main()
'''
_SIG_CONTRAST = "def contrast_ratio(fg, bg):"
_DOC_CONTRAST = ("fg, bg: colours '#RRGGBB'. WCAG: each channel c = value / 255, made linear as c / 12.92 if c <= 0.04045 "
                 "else ((c + 0.055) / 1.055) ** 2.4; luminance L = 0.2126 R + 0.7152 G + 0.0722 B; ratio = (lighter L + "
                 "0.05) / (darker L + 0.05).")


def _lum_alt(hexcode):
    vals = []
    for k in range(3):
        c = int(hexcode[1 + 2 * k:3 + 2 * k], 16) / 255
        vals.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    weights = [0.2126, 0.7152, 0.0722]
    return sum(w * v for w, v in zip(weights, vals))


def _alt_contrast(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out = []
    for r in rows[1:1 + n]:
        a, b = r.split()
        la, lb = _lum_alt(a), _lum_alt(b)
        ratio = (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
        out.append(f"{a} {b} ratio {ratio:.2f} normal {'PASS' if ratio >= 4.5 else 'FAIL'} large {'PASS' if ratio >= 3 else 'FAIL'}")
    return "\n".join(out)


def _gen_contrast(rng, size):
    n = {"small": 3, "medium": 8, "large": 20}[size]
    def col():
        return "#" + "".join(f"{rng.choice([0, 17, 51, 102, 119, 136, 153, 204, 238, 255, rng.randint(0, 255)]):02X}" for _ in range(3))
    return f"{n}\n" + "\n".join(f"{col()} {col()}" for _ in range(n)) + "\n"


PROBLEMS["uxd-4"] = [
    {
        "prompt": ("Six product teams designed their own screens, so Bachat Bank has three button styles and two date "
                   "pickers. Audit before building a design system. The first line is n, then n lines `screen component "
                   "style`. Complete `style_audit`. The program prints, per component sorted by name, `component k: "
                   "style style` with its distinct styles sorted, then `to_fix x`, the number of components that have "
                   "more than one style."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_STYLES, stub(_SIG_STYLES, _DOC_STYLES, "[], 0")),
        "solution": program(_IO_STYLES, _SIG_STYLES + f'''
    """{_DOC_STYLES}"""
    styles = {{}}
    for _, component, style in rows:
        styles.setdefault(component, set()).add(style)
    report = [(c, sorted(styles[c])) for c in sorted(styles)]
    return report, sum(1 for _, s in report if len(s) > 1)
'''),
        "explanation": ("A dictionary of sets, from component to the styles seen, makes inconsistency countable. The "
                        "components with more than one style are where a shared design system pays off first, and the "
                        "count gives the teams a measurable target instead of an opinion."),
        "key_justification": "Group into sets per key to measure inconsistency.",
        "alt": _alt_styles,
        "variants": variants(
            [({}, [("5\nlogin button primary_blue\ntransfer button primary_green\nloans button pill_dark\nlogin input outlined\n"
                    "cards date_picker calendar\n",
                    "button 3: pill_dark primary_blue primary_green\ndate_picker 1: calendar\ninput 1: outlined\nto_fix 1")]),
             ({}, [("2\na card flat\nb card flat\n", "card 1: flat\nto_fix 0")]),
             ({}, [("4\nx toast top\ny toast bottom\nx card flat\ny card shadow\n", "card 2: flat shadow\ntoast 2: bottom top\nto_fix 2")])],
            _gen_styles, 11210,
            extra_hidden=[["1\ns c v\n"], ["3\ns b z\ns b a\ns b z\n"], ["2\ns q 1\ns p 2\n"]]),
    },
    {
        "prompt": ("Marketing wants pale grey fee details 'to keep the screen clean', but users must be able to read "
                   "them. Check colour contrast with the WCAG formula. The first line is n, then n lines `#RRGGBB "
                   "#RRGGBB` (text, background). Complete `contrast_ratio`: for each colour, each channel c = value / "
                   "255 is made linear as c / 12.92 if c <= 0.04045, else ((c + 0.055) / 1.055) ** 2.4; luminance L = "
                   "0.2126 R + 0.7152 G + 0.0722 B; ratio = (lighter L + 0.05) / (darker L + 0.05). The program prints "
                   "`fg bg ratio x.xx normal PASS|FAIL large PASS|FAIL` (normal text needs 4.5, large text 3, compared "
                   "before rounding)."),
        "ds_topic": "string", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CONTRAST, stub(_SIG_CONTRAST, _DOC_CONTRAST, "1.0")),
        "solution": program(_IO_CONTRAST, '''def luminance(colour):
    channels = []
    for i in (1, 3, 5):                                   # 'RR', 'GG', 'BB' after the '#'
        c = int(colour[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


''' + _SIG_CONTRAST + f'''
    """{_DOC_CONTRAST}"""
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)
'''),
        "explanation": ("Parsing the hex pairs into channels and applying the WCAG relative-luminance formula gives a "
                        "ratio from 1 to 21. #777777 on white is 4.48: it looks fine to a designer on a good monitor "
                        "but fails for normal text, which is exactly the grey that hides fees. Comparing before "
                        "rounding stops 4.48 being displayed as passing."),
        "key_justification": "Parse hex colour strings and compute WCAG contrast.",
        "alt": _alt_contrast,
        "variants": variants(
            [({}, [("2\n#000000 #FFFFFF\n#777777 #FFFFFF\n",
                    "#000000 #FFFFFF ratio 21.00 normal PASS large PASS\n#777777 #FFFFFF ratio 4.48 normal FAIL large PASS")]),
             ({}, [("1\n#FFFFFF #FFFFFF\n", "#FFFFFF #FFFFFF ratio 1.00 normal FAIL large FAIL")]),
             ({}, [("1\n#FFFFFF #151C4F\n", "#FFFFFF #151C4F ratio 16.02 normal PASS large PASS")])],
            _gen_contrast, 11220,
            extra_hidden=[["1\n#767676 #FFFFFF\n"], ["1\n#0000FF #000000\n"], ["1\n#949494 #FFFFFF\n"]]),
    },
]

# ---------------------------------------------------------------- uxd-5 Sahaj Nagrik
_IO_SUS = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    scores = []
    for i in range(n):
        parts = data[1 + i].split()
        score = sus_score(list(map(int, parts[1:])))
        scores.append(score)
        print(parts[0], format(score, ".1f"))
    print("mean", format(sum(scores) / n, ".1f"))


main()
'''
_SIG_SUS = "def sus_score(answers):"
_DOC_SUS = ("answers: the 10 System Usability Scale answers, each 1-5, item 1 first. Odd-numbered items score answer - "
            "1, even-numbered items score 5 - answer; the SUS score is the total x 2.5 (0-100).")


def _alt_sus(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out, tot = [], 0.0
    for r in rows[1:1 + n]:
        p = r.split()
        a = [int(x) for x in p[1:11]]
        odd = sum(a[0::2]) - 5
        even = 25 - sum(a[1::2])
        s = (odd + even) * 2.5
        tot += s
        out.append(f"{p[0]} {format(s, '.1f')}")
    return "\n".join(out + [f"mean {format(tot / n, '.1f')}"])


def _gen_sus(rng, size):
    n = {"small": 3, "medium": 10, "large": 30}[size]
    rows = []
    for i in range(n):
        good = rng.random() < 0.5
        ans = [rng.choice([4, 5]) if (k % 2 == 0) == good else rng.choice([1, 2, 3]) for k in range(10)]
        rows.append(f"u{i + 1} " + " ".join(map(str, ans)))
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_TREE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    edges = [tuple(data[1 + i].split()) for i in range(n)]
    m = int(data[1 + n])
    for i in range(m):
        target = data[2 + n + i].strip()
        path = menu_path(edges, target)
        if path is None:
            print(f"{target}: NOT FOUND")
        else:
            clicks = len(path) - 1
            print(f"{target}: {' > '.join(path)} (clicks {clicks})" + (" TOO DEEP" if clicks > 3 else ""))


main()
'''
_SIG_TREE = "def menu_path(edges, target):"
_DOC_TREE = ("edges: (parent, child) pairs of a menu tree whose root is 'Home'. Return the list of labels from Home down "
             "to target, or None if target is not in the menu.")


def _alt_tree(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    edges = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    out = []
    for t in rows[2 + n:2 + n + m]:
        t = t.strip()
        if t == "Home":
            path = ["Home"]
        else:
            path, cur = [t], t
            while cur != "Home":
                par = [p for p, c in edges if c == cur]
                if not par:
                    path = None
                    break
                cur = par[0]
                path.insert(0, cur)
        if path is None:
            out.append(f"{t}: NOT FOUND")
        else:
            k = len(path) - 1
            out.append(f"{t}: {' > '.join(path)} (clicks {k})" + (" TOO DEEP" if k > 3 else ""))
    return "\n".join(out)


def _gen_tree(rng, size):
    labels = ["Certificates", "Income", "Caste", "Domicile", "Payments", "Property_Tax", "Water_Bill", "Pay_Online",
              "Receipt", "Track", "Status", "History", "Help", "Contact", "FAQ", "Language", "Profile", "Documents"]
    n = {"small": 5, "medium": 10, "large": 17}[size]
    nodes, edges = ["Home"], []
    for lab in rng.sample(labels, n):
        parent = rng.choice(nodes[-4:] if rng.random() < 0.6 else nodes)
        edges.append(f"{parent} {lab}")
        nodes.append(lab)
    targets = rng.sample(nodes[1:], min(4, n)) + [rng.choice(["Ration_Card", "Home"])]
    return f"{len(edges)}\n" + "\n".join(edges) + f"\n{len(targets)}\n" + "\n".join(targets) + "\n"


PROBLEMS["uxd-5"] = [
    {
        "prompt": ("To show the redesign worked, the team measures usability before and after with the System Usability "
                   "Scale (SUS). The first line is n, then n lines `participant a1 ... a10` (ten answers from 1 to 5). "
                   "Complete `sus_score`: odd-numbered items (1, 3, 5, 7, 9) score answer - 1, even-numbered items score "
                   "5 - answer, and the total is multiplied by 2.5, giving 0 to 100. The program prints `participant "
                   "score` and then `mean`, all to one decimal."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_SUS, stub(_SIG_SUS, _DOC_SUS, "sum(answers) * 2.5")),
        "solution": program(_IO_SUS, _SIG_SUS + f'''
    """{_DOC_SUS}"""
    total = 0
    for i, answer in enumerate(answers):
        total += answer - 1 if i % 2 == 0 else 5 - answer      # index 0 is item 1 (odd, positively worded)
    return total * 2.5
'''),
        "explanation": ("SUS alternates positively and negatively worded statements, so odd and even items are scored in "
                        "opposite directions before adding; the x 2.5 scales 0-40 to 0-100. A score above about 68 is "
                        "usually read as above average, which gives the redesign a number the departments can agree on."),
        "key_justification": "Alternating-index scoring over a fixed-length array.",
        "alt": _alt_sus,
        "variants": variants(
            [({}, [("2\np1 5 1 5 1 5 1 5 1 5 1\np2 3 3 3 3 3 3 3 3 3 3\n", "p1 100.0\np2 50.0\nmean 75.0")]),
             ({}, [("1\nx 1 5 1 5 1 5 1 5 1 5\n", "x 0.0\nmean 0.0")]),
             ({}, [("1\ny 4 2 4 2 4 1 5 2 4 2\n", "y 80.0\nmean 80.0")])],
            _gen_sus, 11310,
            extra_hidden=[["1\nz 5 5 5 5 5 5 5 5 5 5\n"], ["2\na 1 1 1 1 1 1 1 1 1 1\nb 4 4 4 4 4 4 4 4 4 4\n"],
                          ["3\nq 2 3 4 1 5 2 3 4 1 5\nr 5 2 5 2 5 2 5 2 5 2\ns 3 4 3 4 3 4 3 4 3 4\n"]]),
    },
    {
        "prompt": ("Every department wants its service on the home screen, so the menu has grown deep. Check how many "
                   "taps tasks need (a tree test). The first line is n, then n edges `parent child` of the menu tree, "
                   "whose root is `Home` (labels have no spaces); then m, then m target labels. Complete `menu_path`: "
                   "the list of labels from Home down to the target, or None if it is not in the menu. The program "
                   "prints `target: Home > A > B (clicks k)`, adding ` TOO DEEP` when more than 3 clicks are needed, or "
                   "`target: NOT FOUND`."),
        "ds_topic": "tree", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_TREE, stub(_SIG_TREE, _DOC_TREE, "None")),
        "solution": program(_IO_TREE, _SIG_TREE + f'''
    """{_DOC_TREE}"""
    parent = {{child: par for par, child in edges}}     # each item has one parent in a tree
    if target != "Home" and target not in parent:
        return None
    path = [target]
    while path[-1] != "Home":                          # walk up to the root, then reverse
        path.append(parent[path[-1]])
    return path[::-1]
'''),
        "explanation": ("In a tree every node has exactly one parent, so a child-to-parent dictionary lets you walk from "
                        "any label up to the root and reverse the path: O(depth) per question. Depth is the number of "
                        "taps; anything beyond three is where people give up and queue at the office instead."),
        "key_justification": "Parent pointers in a tree; walk up to build the path.",
        "alt": _alt_tree,
        "variants": variants(
            [({}, [("6\nHome Certificates\nCertificates Income\nCertificates Caste\nHome Payments\nPayments Property_Tax\n"
                    "Property_Tax Receipt\n3\nIncome\nReceipt\nWater_Bill\n",
                    "Income: Home > Certificates > Income (clicks 2)\nReceipt: Home > Payments > Property_Tax > Receipt (clicks 3)\n"
                    "Water_Bill: NOT FOUND")]),
             ({}, [("4\nHome A\nA B\nB C\nC D\n1\nD\n", "D: Home > A > B > C > D (clicks 4) TOO DEEP")]),
             ({}, [("1\nHome Help\n2\nHome\nHelp\n", "Home: Home (clicks 0)\nHelp: Home > Help (clicks 1)")])],
            _gen_tree, 11320,
            extra_hidden=[["0\n1\nHome\n"], ["2\nB C\nHome B\n1\nC\n"], ["3\nHome x\nx y\nHome z\n1\nq\n"]]),
    },
]

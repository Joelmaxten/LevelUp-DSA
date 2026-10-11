"""Code pool for Data Analytics (dan-2 .. dan-5). Built and checked by scripts/build_code_pools.py."""
import calendar
from datetime import date, timedelta

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- dan-2 Rangoli Fashions
_IO_BUYERS = '''
def main():
    data = sys.stdin.read().split("\\n")
    month = data[0].strip()
    n = int(data[1])
    orders = [tuple(data[2 + i].split()) for i in range(n)]
    print("buyers", distinct_buyers(orders, month))


main()
'''
_SIG_BUYERS = "def distinct_buyers(orders, month):"
_DOC_BUYERS = ("orders: list of (order_id, customer_id, 'YYYY-MM-DD', status, amount); customer_id '-' is a guest "
               "checkout. Return how many different customers placed a non-cancelled order in `month` ('YYYY-MM').")


def _alt_buyers(stdin):
    rows = stdin.split("\n")
    month = rows[0].strip()
    n = int(rows[1])
    customers = []
    for row in rows[2:2 + n]:
        _, cust, day, status, _ = row.split()
        if day[:7] == month and status != "cancelled" and cust != "-" and cust not in customers:
            customers.append(cust)
    return f"buyers {len(customers)}"


def _gen_buyers(rng, size):
    n = {"small": 8, "medium": 30, "large": 60}[size]
    month = rng.choice(["2026-03", "2026-04"])
    rows = []
    for i in range(1, n + 1):
        cust = "-" if rng.random() < 0.15 else f"c{rng.randint(1, n // 2 + 2)}"
        day = f"2026-{rng.choice(['03', '04', '05'])}-{rng.randint(1, 28):02d}"
        status = rng.choice(["delivered", "delivered", "returned", "cancelled"])
        rows.append(f"o{i} {cust} {day} {status} {rng.randint(3, 40) * 50}")
    return f"{month}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-2"] = [
    {
        "prompt": ("The marketing head asks: 'how many customers bought from us in {month_name}?' Guest checkouts have "
                   "no customer id, cancelled orders do not count, and a customer with several orders is one customer. "
                   "The first line is the month as YYYY-MM, the second is n, then n lines `order_id customer_id date "
                   "status amount` (customer_id is - for a guest). Complete `distinct_buyers`; the program prints "
                   "`buyers k`. In SQL this would be COUNT(DISTINCT customer_id) with the right WHERE clause."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_BUYERS, stub(_SIG_BUYERS, _DOC_BUYERS, "0")),
        "solution": program(_IO_BUYERS, _SIG_BUYERS + f'''
    """{_DOC_BUYERS}"""
    customers = set()
    for _, customer, day, status, _ in orders:
        if day.startswith(month + "-") and status != "cancelled" and customer != "-":
            customers.add(customer)
    return len(customers)
'''),
        "alt": _alt_buyers,
        "explanation": ("Filter first (right month, not cancelled, not a guest), then put customer ids in a set so "
                        "repeats collapse. Counting order rows instead would answer 'how many orders', a different "
                        "metric, which is why the metric definition matters as much as the query."),
        "key_justification": "Distinct counting with a set after filtering.",
        "variants": variants(
            [({"month_name": "March"},
              [("2026-03\n5\no1 c1 2026-03-02 delivered 500\no2 c1 2026-03-09 delivered 300\n"
                "o3 - 2026-03-10 delivered 200\no4 c2 2026-03-11 cancelled 900\no5 c3 2026-02-27 delivered 100\n",
                "buyers 1")]),
             ({"month_name": "April"},
              [("2026-04\n4\no1 c4 2026-04-01 returned 700\no2 c5 2026-04-30 delivered 100\n"
                "o3 c5 2026-04-02 delivered 300\no4 c6 2026-05-01 delivered 50\n", "buyers 2")]),
             ({"month_name": "May"},
              [("2026-05\n3\no1 - 2026-05-03 delivered 400\no2 - 2026-05-04 delivered 400\n"
                "o3 c9 2026-05-05 cancelled 100\n", "buyers 0")])],
            _gen_buyers, 610,
            extra_hidden=[["2026-03\n1\no1 c1 2026-03-31 delivered 10\n"], ["2026-04\n0\n"],
                          ["2026-05\n2\no1 c1 2026-05-01 cancelled 5\no2 c1 2026-05-02 delivered 5\n"]]),
    },
]

_IO_BIG = '''
def main():
    data = sys.stdin.read().split("\\n")
    threshold = int(data[0])
    n = int(data[1])
    orders = []
    for i in range(n):
        order_id, customer, status, amount = data[2 + i].split()
        orders.append((order_id, customer, status, int(amount)))
    rows = big_spenders(orders, threshold)
    if not rows:
        print("NONE")
    for customer, total in rows:
        print(customer, total)


main()
'''
_SIG_BIG = "def big_spenders(orders, threshold):"
_DOC_BIG = ("orders: list of (order_id, customer_id, status, amount). Return (customer_id, delivered total) for every "
            "customer (not guests '-') whose total over DELIVERED orders is at least threshold, highest total first, "
            "ties by customer id in string order.")


def _alt_big(stdin):
    rows = stdin.split("\n")
    threshold = int(rows[0])
    n = int(rows[1])
    items = [r.split() for r in rows[2:2 + n]]
    custs = sorted({c for _, c, s, _ in items if c != "-" and s == "delivered"})
    totals = [(c, sum(int(a) for _, cc, s, a in items if cc == c and s == "delivered")) for c in custs]
    keep = [t for t in totals if t[1] >= threshold]
    keep.sort(key=lambda t: t[1], reverse=True)
    return "\n".join(f"{c} {t}" for c, t in keep) or "NONE"


def _gen_big(rng, size):
    n = {"small": 8, "medium": 30, "large": 70}[size]
    threshold = rng.choice([1000, 2000, 3000])
    rows = []
    for i in range(1, n + 1):
        cust = "-" if rng.random() < 0.1 else f"c{rng.randint(1, max(3, n // 4))}"
        rows.append(f"o{i} {cust} {rng.choice(['delivered', 'delivered', 'cancelled', 'returned'])} "
                    f"{rng.randint(2, 30) * 50}")
    return f"{threshold}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-2"].append({
    "prompt": ("For a loyalty campaign, find customers whose delivered orders add up to at least a threshold. This is "
               "the classic WHERE (filter rows) then HAVING (filter groups) query. The first line is the threshold in "
               "rupees, the second is n, then n lines `order_id customer_id status amount`. Complete `big_spenders`. "
               "Only delivered orders count and guests (-) are ignored. The program prints `customer_id total`, "
               "highest total first, ties by customer id in string order, or NONE."),
    "ds_topic": "sorting", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_BIG, stub(_SIG_BIG, _DOC_BIG, "[]")),
    "solution": program(_IO_BIG, _SIG_BIG + f'''
    """{_DOC_BIG}"""
    totals = {{}}
    for _, customer, status, amount in orders:
        if status == "delivered" and customer != "-":          # WHERE
            totals[customer] = totals.get(customer, 0) + amount   # GROUP BY customer
    rows = [(c, t) for c, t in totals.items() if t >= threshold]  # HAVING
    rows.sort(key=lambda r: (-r[1], r[0]))                         # ORDER BY
    return rows
'''),
    "alt": _alt_big,
    "explanation": ("Row filters (delivered, not a guest) apply before grouping; the threshold applies to each "
                    "group's total, after grouping. Mixing them up, for example dropping orders below the threshold, "
                    "answers a different question. A composite sort key handles the tie rule."),
    "key_justification": "WHERE filters rows, HAVING filters aggregated groups.",
    "variants": variants(
        [({}, [("1000\n5\no1 c1 delivered 600\no2 c2 delivered 1000\no3 c1 delivered 400\no4 c3 cancelled 5000\n"
                "o5 - delivered 2000\n", "c1 1000\nc2 1000")]),
         ({}, [("500\n3\no1 c9 returned 900\no2 c8 delivered 499\no3 c8 delivered 2\n", "c8 501")]),
         ({}, [("100\n2\no1 - delivered 400\no2 c1 cancelled 400\n", "NONE")])],
        _gen_big, 620,
        extra_hidden=[["0\n1\no1 c5 delivered 0\n"], ["300\n2\no1 c2 delivered 300\no2 c10 delivered 300\n"],
                      ["50\n0\n"]]),
})

# ---------------------------------------------------------------- dan-3 Swasthya Pharmacy
_IO_MTD = '''
def main():
    data = sys.stdin.read().split("\\n")
    as_of = data[0].strip()
    n = int(data[1])
    daily = []
    for i in range(n):
        day, revenue = data[2 + i].split()
        daily.append((day, int(revenue)))
    this_month, last_month = month_to_date(daily, as_of)
    print("this_month", this_month)
    print("last_month", last_month)
    if last_month == 0:
        print("change NA")
    else:
        print("change", format(100 * (this_month - last_month) / last_month, ".1f") + "%")


main()
'''
_SIG_MTD = "def month_to_date(daily, as_of):"
_DOC_MTD = ("daily: list of ('YYYY-MM-DD', revenue). as_of: 'YYYY-MM-DD'. Return (revenue from day 1 of as_of's "
            "month up to and including as_of, revenue from day 1 to the same day number of the previous month, or "
            "the whole previous month if it is shorter).")


def _alt_mtd(stdin):
    rows = stdin.split("\n")
    as_of = date.fromisoformat(rows[0].strip())
    n = int(rows[1])
    first = as_of.replace(day=1)
    prev_end = first - timedelta(days=1)
    prev_first = prev_end.replace(day=1)
    prev_cut = prev_first.replace(day=min(as_of.day, calendar.monthrange(prev_end.year, prev_end.month)[1]))
    this = last = 0
    for row in rows[2:2 + n]:
        d, v = row.split()
        d = date.fromisoformat(d)
        if first <= d <= as_of:
            this += int(v)
        if prev_first <= d <= prev_cut:
            last += int(v)
    change = "NA" if last == 0 else format(100 * (this - last) / last, ".1f") + "%"
    return f"this_month {this}\nlast_month {last}\nchange {change}"


def _gen_mtd(rng, size):
    days = {"small": 15, "medium": 45, "large": 75}[size]
    start = date(rng.choice([2025, 2026]), rng.choice([1, 2, 3, 12]), 1) - timedelta(days=rng.randint(20, 40))
    rows = [f"{start + timedelta(days=i)} {rng.randint(20, 90) * 10}" for i in range(days) if rng.random() < 0.9]
    as_of = start + timedelta(days=rng.randint(days // 2, days - 1))
    return f"{as_of}\n{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-3"] = [
    {
        "prompt": ("The report showed October down 30% because it compared a part-month with a full month. Make the "
                   "comparison fair. The first line is the as-of date YYYY-MM-DD, the second is n, then n lines "
                   "`date revenue` (days without sales are simply missing). Complete `month_to_date`: this month runs "
                   "from day 1 to the as-of date; last month runs from day 1 to the same day number, or to its end if "
                   "it is shorter. The program prints `this_month`, `last_month` and `change` as a percentage to one "
                   "decimal (change NA if last month is 0)."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_MTD, stub(_SIG_MTD, _DOC_MTD, "0, 0")),
        "solution": "import calendar\nfrom datetime import date, timedelta\n" + program(_IO_MTD, _SIG_MTD + f'''
    """{_DOC_MTD}"""
    end = date.fromisoformat(as_of)
    start = end.replace(day=1)
    prev_last_day = start - timedelta(days=1)
    prev_start = prev_last_day.replace(day=1)
    days_in_prev = calendar.monthrange(prev_start.year, prev_start.month)[1]
    prev_end = prev_start.replace(day=min(end.day, days_in_prev))
    this_month = last_month = 0
    for day, revenue in daily:
        d = date.fromisoformat(day)
        if start <= d <= end:
            this_month += revenue
        elif prev_start <= d <= prev_end:
            last_month += revenue
    return this_month, last_month
'''),
        "alt": _alt_mtd,
        "explanation": ("Comparing an incomplete period with a complete one invents a fall. Matching the same days in "
                        "both months (month-to-date against the same period last month) compares like with like. "
                        "Date arithmetic, not string handling, takes care of January and short months."),
        "key_justification": "Compare equal periods: month-to-date vs the same days last month.",
        "variants": variants(
            [({}, [("2026-10-03\n5\n2026-09-01 100\n2026-09-02 100\n2026-09-03 100\n2026-09-20 900\n2026-10-01 90\n",
                    "this_month 90\nlast_month 300\nchange -70.0%")]),
             ({}, [("2026-03-31\n3\n2026-02-28 500\n2026-03-30 400\n2026-03-31 200\n",
                    "this_month 600\nlast_month 500\nchange 20.0%")]),
             ({}, [("2026-01-02\n3\n2025-12-01 50\n2025-12-03 70\n2026-01-01 80\n",
                    "this_month 80\nlast_month 50\nchange 60.0%")])],
            _gen_mtd, 630,
            extra_hidden=[["2026-05-10\n1\n2026-05-01 10\n"], ["2024-03-30\n2\n2024-02-29 7\n2024-03-01 7\n"],
                          ["2026-07-15\n2\n2026-07-16 99\n2026-06-15 1\n"]]),
    },
]

_IO_SIMPSON = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        team, segment, delivered, on_time = data[1 + i].split()
        rows.append((team, segment, int(delivered), int(on_time)))
    overall, paradox = simpson_check(rows)
    for team, rate in overall:
        print(team, format(rate, ".1f"))
    print("PARADOX" if paradox else "NO PARADOX")


main()
'''
_SIG_SIMPSON = "def simpson_check(rows):"
_DOC_SIMPSON = ("rows: list of (team, segment, delivered, on_time) for exactly two teams. Return ([(team, overall "
                "on-time %)] sorted by team, paradox), where paradox is True when one team has the strictly higher "
                "on-time rate in every segment both teams serve but the strictly lower overall rate.")


def _alt_simpson(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    teams = sorted({r[0] for r in rows})
    tot = {t: [0, 0] for t in teams}
    seg = {}
    for t, s, d, o in rows:
        tot[t][0] += int(d)
        tot[t][1] += int(o)
        seg.setdefault(s, {}).setdefault(t, [0, 0])
        seg[s][t][0] += int(d)
        seg[s][t][1] += int(o)
    lines = [f"{t} {format(100 * tot[t][1] / tot[t][0], '.1f')}" for t in teams]
    a, b = teams
    common = [s for s in seg if a in seg[s] and b in seg[s]]
    rate = lambda pair: pair[1] / pair[0]
    a_wins = all(rate(seg[s][a]) > rate(seg[s][b]) for s in common)
    b_wins = all(rate(seg[s][b]) > rate(seg[s][a]) for s in common)
    overall_a, overall_b = rate(tot[a]), rate(tot[b])
    paradox = bool(common) and ((a_wins and overall_a < overall_b) or (b_wins and overall_b < overall_a))
    return "\n".join(lines + ["PARADOX" if paradox else "NO PARADOX"])


def _gen_simpson(rng, size):
    segments = {"small": ["city", "rural"], "medium": ["city", "town", "rural"],
                "large": ["city", "town", "rural", "hills"]}[size]
    rows = []
    paradox = rng.random() < 0.5
    for i, segment in enumerate(segments):
        base = 0.95 - 0.1 * i
        for team, share in (("Patna", 1 if i == 0 else 4), ("Ranchi", 4 if i == 0 else 1)):
            delivered = 80 * (share if paradox else 2)
            better = 0.03 if team == "Patna" else 0.0
            on_time = int(delivered * (base + better - rng.random() * 0.02))
            rows.append(f"{team} {segment} {delivered} {on_time}")
    return f"{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-3"].append({
    "prompt": ("Managers say Patna's delivery team is worse than Ranchi's, but Patna does far more of the hard rural "
               "deliveries. Check for Simpson's paradox. The first line is n, then n lines `team segment delivered "
               "on_time`, for exactly two teams. Complete `simpson_check`. The program prints each team's overall "
               "on-time percentage to one decimal (teams sorted by name), then PARADOX if one team has the strictly "
               "higher on-time rate in every segment both teams serve yet the strictly lower overall rate, otherwise "
               "NO PARADOX."),
    "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_SIMPSON, stub(_SIG_SIMPSON, _DOC_SIMPSON, "[], False")),
    "solution": program(_IO_SIMPSON, _SIG_SIMPSON + f'''
    """{_DOC_SIMPSON}"""
    totals, by_segment = {{}}, {{}}
    for team, segment, delivered, on_time in rows:
        d, o = totals.get(team, (0, 0))
        totals[team] = (d + delivered, o + on_time)
        seg = by_segment.setdefault(segment, {{}})
        d, o = seg.get(team, (0, 0))
        seg[team] = (d + delivered, o + on_time)
    a, b = sorted(totals)

    def rate(pair):
        return pair[1] / pair[0]

    common = [s for s in by_segment if a in by_segment[s] and b in by_segment[s]]
    a_better = all(rate(by_segment[s][a]) > rate(by_segment[s][b]) for s in common)
    b_better = all(rate(by_segment[s][b]) > rate(by_segment[s][a]) for s in common)
    paradox = bool(common) and ((a_better and rate(totals[a]) < rate(totals[b]))
                                or (b_better and rate(totals[b]) < rate(totals[a])))
    return [(t, 100 * rate(totals[t])) for t in (a, b)], paradox
'''),
    "alt": _alt_simpson,
    "explanation": ("Group the counts twice, per team and per (segment, team), with dictionaries. When one team "
                    "wins inside every segment but loses overall, the overall figure is driven by the mix of "
                    "segments each team serves, not by performance; comparing within segments is the fair view."),
    "key_justification": "Compare within strata before trusting the aggregate.",
    "variants": variants(
        [({}, [("4\nNorth city 80 76\nNorth rural 320 224\nSouth city 300 270\nSouth rural 100 66\n",
                "North 75.0\nSouth 84.0\nPARADOX")]),
         ({}, [("4\nA city 100 90\nA rural 100 70\nB city 100 80\nB rural 100 60\n", "A 80.0\nB 70.0\nNO PARADOX")]),
         ({}, [("3\nP city 10 9\nQ city 10 8\nQ rural 50 10\n", "P 90.0\nQ 30.0\nNO PARADOX")])],
        _gen_simpson, 640,
        extra_hidden=[["2\nX city 10 5\nY rural 10 9\n"],
                      ["4\nM city 50 45\nM rural 50 20\nN city 50 40\nN rural 50 25\n"],
                      ["2\nAa town 20 10\nBb town 20 10\n"]]),
})

# ---------------------------------------------------------------- dan-4 Sapna Cinemas
_IO_MASK = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for i in range(n):
        name, phone = data[1 + i].split()
        print(mask(name, phone))


main()
'''
_SIG_MASK = "def mask(name, phone):"
_DOC_MASK = ("name: words joined by '_' (e.g. 'Asha_Rao'); phone: 10 digits. Return the initials, each followed by "
             "a dot, then a space, then the phone with every digit but the last four replaced by '*'.")


def _alt_mask(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out = []
    for row in rows[1:1 + n]:
        name, phone = row.split()
        initials = "".join(part[0].upper() + "." for part in name.split("_") if part)
        out.append(initials + " " + "*" * (len(phone) - 4) + phone[-4:])
    return "\n".join(out)


def _gen_mask(rng, size):
    n = {"small": 3, "medium": 10, "large": 30}[size]
    first = ["asha", "Vikram", "Neha", "Rohan", "Fatima", "Joseph", "Meera", "Arjun"]
    last = ["Rao", "Patel", "Shah", "Iyer", "Khan", "Desai"]
    rows = []
    for _ in range(n):
        parts = [rng.choice(first)] + ([rng.choice(last)] if rng.random() < 0.7 else [])
        rows.append("_".join(parts) + " " + str(rng.randint(6000000000, 9999999999)))
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-4"] = [
    {
        "prompt": ("Before sharing booking data with the outside marketing agency, Sapna Cinemas must hide personal "
                   "details. The first line is n, then n lines `name phone`, where the name's words are joined by "
                   "underscores (Asha_Rao) and the phone has 10 digits. Complete `mask` so each line becomes the "
                   "initials in capitals, each followed by a dot, a space, then the phone with all but the last four "
                   "digits replaced by * (Asha_Rao 9876543210 becomes `A.R. ******3210`)."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_MASK, stub(_SIG_MASK, _DOC_MASK, "name + ' ' + phone")),
        "solution": program(_IO_MASK, _SIG_MASK + f'''
    """{_DOC_MASK}"""
    initials = "".join(word[0].upper() + "." for word in name.split("_") if word)
    return initials + " " + "*" * (len(phone) - 4) + phone[-4:]
'''),
        "alt": _alt_mask,
        "explanation": ("Split the name on underscores and keep the first letter of each word; slice the phone so "
                        "only the last four digits stay. Note the starter would share the raw data: sending the "
                        "minimum needed (data minimisation) is the safer default."),
        "key_justification": "String slicing and splitting for data masking.",
        "variants": variants(
            [({}, [("2\nAsha_Rao 9876543210\nVikram 9123456789\n", "A.R. ******3210\nV. ******6789")]),
             ({}, [("1\nmeera_k_iyer 9000012345\n", "M.K.I. ******2345")]),
             ({}, [("2\nArjun_Desai 8888888888\nneha 7012345678\n", "A.D. ******8888\nN. ******5678")])],
            _gen_mask, 710,
            extra_hidden=[["1\nZ 1234567890\n"], ["1\nFatima_Khan 9999990000\n"], ["2\nx_y 1111111111\nP_Q_R 2222222222\n"]]),
    },
]

_IO_MOVING = '''
def main():
    data = sys.stdin.read().split("\\n")
    window, _ = map(int, data[0].split())
    values = list(map(int, data[1].split())) if data[1].strip() else []
    averages = moving_average(values, window)
    print(" ".join(format(a, ".1f") for a in averages) if averages else "NONE")


main()
'''
_SIG_MOVING = "def moving_average(values, window):"
_DOC_MOVING = ("values: daily occupancy percentages. Return the average of each run of `window` consecutive days, "
               "from the first full window to the last day (an empty list if there are fewer days than window).")


def _alt_moving(stdin):
    rows = stdin.split("\n")
    w = int(rows[0].split()[0])
    vals = [int(x) for x in rows[1].split()]
    out = [sum(vals[i - w + 1:i + 1]) / w for i in range(w - 1, len(vals))]
    return " ".join(format(a, ".1f") for a in out) or "NONE"


def _gen_moving(rng, size):
    n = {"small": 8, "medium": 30, "large": 120}[size]
    window = rng.choice([3, 5, 7])
    vals = [rng.randint(20, 100) for _ in range(n)]
    return f"{window} {n}\n" + " ".join(map(str, vals)) + "\n"


PROBLEMS["dan-4"].append({
    "prompt": ("Theatre managers want a smoothed occupancy line, not daily spikes. The first line is `w n`, the "
               "second has n daily occupancy percentages. Complete `moving_average` so that it slides a window of w "
               "days along the series without re-adding the whole window each time. The program prints the w-day "
               "averages from the first full window to the end, space-separated to one decimal, or NONE if there "
               "are fewer than w days."),
    "ds_topic": "queue", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_MOVING, stub(_SIG_MOVING, _DOC_MOVING, "[]")),
    "solution": "from collections import deque\n" + program(_IO_MOVING, _SIG_MOVING + f'''
    """{_DOC_MOVING}"""
    window_values, total, out = deque(), 0, []
    for value in values:
        window_values.append(value)
        total += value
        if len(window_values) > window:
            total -= window_values.popleft()
        if len(window_values) == window:
            out.append(total / window)
    return out
'''),
    "alt": _alt_moving,
    "explanation": ("Keep the last w values in a queue and a running total: add the new day, subtract the day that "
                    "falls out. Each step is O(1), so the whole series is O(n) instead of O(n x w). SQL does the "
                    "same with AVG(...) OVER (ROWS BETWEEN w-1 PRECEDING AND CURRENT ROW)."),
    "key_justification": "Sliding window with a deque and a running sum.",
    "variants": variants(
        [({}, [("3 5\n60 70 80 90 100\n", "70.0 80.0 90.0")]),
         ({}, [("2 4\n50 51 50 51\n", "50.5 50.5 50.5")]),
         ({}, [("4 3\n90 90 90\n", "NONE")])],
        _gen_moving, 720,
        extra_hidden=[["1 3\n5 6 7\n"], ["3 3\n10 20 31\n"], ["5 0\n\n"]]),
})

# ---------------------------------------------------------------- dan-5 Nirmal Purifiers
_IO_COHORT = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        customer, month, complaints = data[1 + i].split()
        rows.append((customer, month, int(complaints)))
    for month, rate in complaints_per_100(rows):
        print(month, format(rate, ".1f"))


main()
'''
_SIG_COHORT = "def complaints_per_100(rows):"
_DOC_COHORT = ("rows: list of (customer_id, install_month 'YYYY-MM', complaints), one per customer. Return "
               "(install_month, complaints per 100 customers installed that month) in month order.")


def _alt_cohort(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for month in sorted({m for _, m, _ in rows}):
        group = [int(c) for _, m, c in rows if m == month]
        out.append(f"{month} {format(100 * sum(group) / len(group), '.1f')}")
    return "\n".join(out)


def _gen_cohort(rng, size):
    n = {"small": 6, "medium": 25, "large": 60}[size]
    months = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
    rows = []
    for i in range(1, n + 1):
        month = rng.choice(months)
        heavy = month >= "2026-01"
        rows.append(f"c{i} {month} {rng.choice([0, 0, 1, 2, 3] if heavy else [0, 0, 0, 1])}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-5"] = [
    {
        "prompt": ("Complaints rose 40%, but more purifiers were also installed. A cohort view separates the two: "
                   "group customers by installation month and compare complaints per 100 customers. The first line "
                   "is n, then n lines `customer_id install_month complaints` (one line per customer). Complete "
                   "`complaints_per_100`; the program prints `month rate` to one decimal for each install month, "
                   "oldest first."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_COHORT, stub(_SIG_COHORT, _DOC_COHORT, "[]")),
        "solution": program(_IO_COHORT, _SIG_COHORT + f'''
    """{_DOC_COHORT}"""
    customers, complaints = {{}}, {{}}
    for _, month, count in rows:
        customers[month] = customers.get(month, 0) + 1
        complaints[month] = complaints.get(month, 0) + count
    return [(month, 100 * complaints[month] / customers[month]) for month in sorted(customers)]
'''),
        "alt": _alt_cohort,
        "explanation": ("Raw complaint counts grow with the installed base; a rate per 100 customers in each "
                        "installation cohort shows whether newer installs genuinely fail more, for example after a "
                        "model launch. Two dictionaries keyed by month give both counts in one pass."),
        "key_justification": "Normalise by cohort size before comparing cohorts.",
        "variants": variants(
            [({}, [("4\nc1 2026-01 2\nc2 2026-01 0\nc3 2026-02 1\nc4 2026-02 3\n", "2026-01 100.0\n2026-02 200.0")]),
             ({}, [("3\nc1 2025-12 0\nc2 2025-12 0\nc3 2025-12 1\n", "2025-12 33.3")]),
             ({}, [("3\nc9 2026-02 1\nc8 2025-11 0\nc7 2026-02 0\n", "2025-11 0.0\n2026-02 50.0")])],
            _gen_cohort, 810,
            extra_hidden=[["1\nc1 2026-03 7\n"], ["2\nc1 2026-01 0\nc2 2026-01 0\n"], ["3\nx 2025-10 1\ny 2025-10 1\nz 2025-10 2\n"]]),
    },
]

_IO_PARETO = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        reason, count = data[1 + i].split()
        rows.append((reason, int(count)))
    for reason, share in vital_few(rows):
        print(reason, format(share, ".1f"))


main()
'''
_SIG_PARETO = "def vital_few(rows):"
_DOC_PARETO = ("rows: list of (reason, count); a reason can appear on several rows. Return (reason, cumulative % of "
               "all complaints) for the fewest top reasons that together reach at least 80%, biggest first, ties by "
               "reason in string order.")


def _alt_pareto(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    totals = {}
    for reason, count in rows:
        totals[reason] = totals.get(reason, 0) + int(count)
    grand = sum(totals.values())
    ordered = sorted(totals, key=lambda r: r)
    ordered = sorted(ordered, key=lambda r: totals[r], reverse=True)
    out, running = [], 0
    for reason in ordered:
        if out and running * 100 >= 80 * grand:
            break
        running += totals[reason]
        out.append(f"{reason} {format(100 * running / grand, '.1f')}")
    return "\n".join(out)


def _gen_pareto(rng, size):
    reasons = ["filter", "leak", "noise", "taste", "app", "billing", "delay", "smell"]
    n = {"small": 5, "medium": 15, "large": 40}[size]
    rows = [f"{rng.choice(reasons)} {rng.randint(1, 40)}" for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dan-5"].append({
    "prompt": ("With three weeks to present, the team should chase the few complaint reasons that cause most of the "
               "volume (a Pareto view). The first line is n, then n lines `reason count` from different systems, so "
               "a reason can appear more than once. Complete `vital_few`: total each reason, order reasons by total "
               "(highest first, ties by name in string order) and keep adding reasons until together they reach at "
               "least 80% of all complaints. The program prints `reason cumulative_percent` to one decimal for each "
               "kept reason."),
    "ds_topic": "sorting", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_PARETO, stub(_SIG_PARETO, _DOC_PARETO, "[]")),
    "solution": program(_IO_PARETO, _SIG_PARETO + f'''
    """{_DOC_PARETO}"""
    totals = {{}}
    for reason, count in rows:
        totals[reason] = totals.get(reason, 0) + count
    grand = sum(totals.values())
    out, running = [], 0
    for reason, count in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        running += count
        out.append((reason, 100 * running / grand))
        if running * 100 >= 80 * grand:       # integer test: no rounding surprises at exactly 80%
            break
    return out
'''),
    "alt": _alt_pareto,
    "explanation": ("Aggregate per reason, sort by total, then accumulate until the running share reaches 80%. "
                    "Comparing running x 100 with 80 x total in integers avoids a float like 79.999 missing the "
                    "cut-off. The result tells the team which two or three causes to investigate first."),
    "key_justification": "Aggregate, sort, then a cumulative cut-off (Pareto).",
    "variants": variants(
        [({}, [("4\nfilter 50\nleak 30\nnoise 15\napp 5\n", "filter 50.0\nleak 80.0")]),
         ({}, [("4\nleak 10\nleak 10\ntaste 25\napp 5\n", "taste 50.0\nleak 90.0")]),
         ({}, [("3\nbilling 10\ndelay 10\nsmell 10\n", "billing 33.3\ndelay 66.7\nsmell 100.0")])],
        _gen_pareto, 820,
        extra_hidden=[["1\nfilter 3\n"], ["2\nb 1\na 4\n"], ["5\nx 20\ny 20\nz 20\nw 20\nv 20\n"]]),
})

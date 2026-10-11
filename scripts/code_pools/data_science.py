"""Code pool for Data Science (dsc-2 .. dsc-5). Built and checked by scripts/build_code_pools.py."""
import math
from datetime import datetime, timedelta, timezone

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- dsc-2 Kitabwala A/B test
_IO_CONV = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        user, variant, bought = data[1 + i].split()
        rows.append((user, variant, int(bought)))
    for variant, users, buyers in conversion_by_variant(rows):
        print(variant, users, buyers, format(100 * buyers / users, ".2f"))


main()
'''
_SIG_CONV = "def conversion_by_variant(rows):"
_DOC_CONV = ("rows: list of (user_id, variant, bought 0/1), one per checkout visit; a user can visit several times. "
             "Return (variant, users, buyers) per variant sorted by variant, counting each user once (a buyer if any "
             "visit bought).")


def _alt_conv(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for variant in sorted({r[1] for r in rows}):
        users = sorted({r[0] for r in rows if r[1] == variant})
        buyers = [u for u in users if any(r[0] == u and r[1] == variant and r[2] == "1" for r in rows)]
        out.append(f"{variant} {len(users)} {len(buyers)} {format(100 * len(buyers) / len(users), '.2f')}")
    return "\n".join(out)


def _gen_conv(rng, size):
    users = {"small": 6, "medium": 20, "large": 45}[size]
    rows = []
    for u in range(1, users + 1):
        variant = rng.choice("AB")
        for _ in range(rng.randint(1, 3)):
            rows.append(f"u{u} {variant} {1 if rng.random() < 0.3 else 0}")
    rng.shuffle(rows)
    return f"{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-2"] = [
    {
        "prompt": ("Kitabwala's experiment log has one row per checkout visit, and many students visit checkout more "
                   "than once, so counting rows inflates both groups. The first line is n, then n lines `user_id "
                   "variant bought` (bought is 1 or 0; a user always stays in one variant). Complete "
                   "`conversion_by_variant` so the program prints one line per variant, sorted by variant name: "
                   "`variant users buyers rate`, where each user counts once, a user is a buyer if any of their "
                   "visits bought, and rate is buyers / users x 100 to two decimals."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_CONV, stub(_SIG_CONV, _DOC_CONV, "[]")),
        "solution": program(_IO_CONV, _SIG_CONV + f'''
    """{_DOC_CONV}"""
    bought_by_user = {{}}
    variant_of = {{}}
    for user, variant, bought in rows:
        variant_of[user] = variant
        bought_by_user[user] = bought_by_user.get(user, 0) or bought
    summary = {{}}
    for user, variant in variant_of.items():
        users, buyers = summary.get(variant, (0, 0))
        summary[variant] = (users + 1, buyers + (1 if bought_by_user[user] else 0))
    return [(variant, *summary[variant]) for variant in sorted(summary)]
'''),
        "alt": _alt_conv,
        "explanation": ("The randomisation unit is the user, so the analysis unit must be the user too. A dictionary "
                        "from user to 'bought at least once' collapses repeat visits; then each variant's users and "
                        "buyers are counted. In SQL this is a GROUP BY user before the GROUP BY variant."),
        "key_justification": "Deduplicate to the randomisation unit before computing rates.",
        "variants": variants(
            [({}, [("5\nu1 A 0\nu2 B 1\nu1 A 1\nu3 A 0\nu4 B 0\n", "A 2 1 50.00\nB 2 1 50.00")]),
             ({}, [("4\nu7 B 0\nu7 B 0\nu8 A 1\nu9 B 1\n", "A 1 1 100.00\nB 2 1 50.00")]),
             ({}, [("6\nu1 A 1\nu1 A 1\nu2 A 0\nu3 A 0\nu4 B 0\nu4 B 1\n", "A 3 1 33.33\nB 1 1 100.00")])],
            _gen_conv, 310,
            extra_hidden=[["2\nu1 A 0\nu1 A 0\n"], ["3\nu5 B 1\nu6 B 1\nu5 B 0\n"], ["2\nx A 1\ny B 0\n"]]),
    },
]

_IO_PEEK = '''
def main():
    data = sys.stdin.read().split("\\n")
    days = int(data[0])
    daily = [tuple(map(int, data[1 + i].split())) for i in range(days)]
    first_day, final_z = peeking_check(daily)
    print("first_significant_day", first_day if first_day else "NEVER")
    print("final_z", format(final_z, ".2f"))


main()
'''
_SIG_PEEK = "def peeking_check(daily):"
_DOC_PEEK = ("daily: list of (visitors_a, buyers_a, visitors_b, buyers_b) per day. Using cumulative totals, compute "
             "the two-proportion z each day. Return (first day number with |z| >= 1.96, or None; z on the last day).")


def _z(va, ba, vb, bb):
    pool = (ba + bb) / (va + vb)
    se = math.sqrt(pool * (1 - pool) * (1 / va + 1 / vb))
    return 0.0 if se == 0 else (bb / vb - ba / va) / se


def _alt_peek(stdin):
    rows = stdin.split("\n")
    days = int(rows[0])
    totals = [0, 0, 0, 0]
    first, z = None, 0.0
    for d in range(1, days + 1):
        totals = [t + int(x) for t, x in zip(totals, rows[d].split())]
        z = _z(*totals)
        if first is None and abs(z) >= 1.96:
            first = d
    return f"first_significant_day {first or 'NEVER'}\nfinal_z {format(z, '.2f')}"


def _gen_peek(rng, size):
    days = {"small": 5, "medium": 14, "large": 30}[size]
    lift = rng.choice([0.0, 0.004, 0.01])
    rows = []
    for _ in range(days):
        va, vb = rng.randint(2800, 3200), rng.randint(2800, 3200)
        ba = sum(rng.random() < 0.04 for _ in range(va))
        bb = sum(rng.random() < 0.04 + lift for _ in range(vb))
        rows.append(f"{va} {ba} {vb} {bb}")
    return f"{days}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-2"].append({
    "prompt": ("A product manager wants to 'check the dashboard every day and stop as soon as it is significant'. "
               "Show what that does. The first line is the number of days, then one line per day `visitors_a "
               "buyers_a visitors_b buyers_b`. Complete `peeking_check`: on each day, add that day to the running "
               "totals and compute the two-proportion z statistic for B minus A, z = (pB - pA) / sqrt(p(1 - p)(1/nA "
               "+ 1/nB)) with p the pooled rate (use z = 0 when the square root is 0). The program prints "
               "`first_significant_day d` (the first day with |z| >= 1.96, or NEVER) and `final_z` to two decimals."),
    "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_PEEK, stub(_SIG_PEEK, _DOC_PEEK, "None, 0.0")),
    "solution": "import math\n" + program(_IO_PEEK, _SIG_PEEK + f'''
    """{_DOC_PEEK}"""
    va = ba = vb = bb = 0
    first, z = None, 0.0
    for day, (a_vis, a_buy, b_vis, b_buy) in enumerate(daily, 1):
        va, ba, vb, bb = va + a_vis, ba + a_buy, vb + b_vis, bb + b_buy
        pooled = (ba + bb) / (va + vb)
        se = math.sqrt(pooled * (1 - pooled) * (1 / va + 1 / vb))
        z = 0.0 if se == 0 else (bb / vb - ba / va) / se
        if first is None and abs(z) >= 1.96:
            first = day
    return first, z
'''),
    "alt": _alt_peek,
    "explanation": ("Running totals (a prefix sum over the days) give the cumulative counts in one pass. Checking "
                    "|z| >= 1.96 every day and stopping at the first hit gives many more false wins than the "
                    "nominal 5%, which is why the sample size is fixed in advance and the test is read once."),
    "key_justification": "Cumulative sums per day; repeated looks inflate false positives.",
    "variants": variants(
        [({}, [("2\n1000 40 1000 40\n1000 40 1000 70\n", "first_significant_day 2\nfinal_z 2.23")]),
         ({}, [("1\n500 20 500 20\n", "first_significant_day NEVER\nfinal_z 0.00")]),
         ({}, [("2\n100 10 100 20\n100 10 100 10\n", "first_significant_day 1\nfinal_z 1.51")])],
        _gen_peek, 320,
        extra_hidden=[["1\n10 0 10 0\n"], ["3\n200 2 200 12\n200 3 200 2\n200 4 200 1\n"], ["1\n50 50 50 0\n"]]),
})

# ---------------------------------------------------------------- dsc-3 Annapurna dashboard
_IO_FAN = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    orders = {}
    for i in range(n):
        order_id, total = data[1 + i].split()
        orders[order_id] = int(total)
    m = int(data[1 + n])
    payments = [tuple(data[2 + n + i].split()) for i in range(m)]
    wrong, right = revenue_both_ways(orders, payments)
    print("joined_sum", wrong)
    print("true_revenue", right)


main()
'''
_SIG_FAN = "def revenue_both_ways(orders, payments):"
_DOC_FAN = ("orders: {order_id: total}. payments: list of (order_id, status), one row per payment ATTEMPT. Return "
            "(the sum you get by joining orders to payments and summing order totals, the true revenue: each order "
            "counted once if it has at least one 'success' attempt).")


def _alt_fan(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    orders = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    pays = [r.split() for r in rows[2 + n:2 + n + m]]
    joined = sum(int(t) for o, t in orders for p, _ in pays if p == o)
    true = sum(int(t) for o, t in orders if ["success"] == [s for p, s in pays if p == o and s == "success"][:1])
    return f"joined_sum {joined}\ntrue_revenue {true}"


def _gen_fan(rng, size):
    n = {"small": 4, "medium": 12, "large": 30}[size]
    orders = [(f"o{i}", rng.choice([240, 380, 515, 900, 1250])) for i in range(1, n + 1)]
    pays = []
    for oid, _ in orders:
        for _ in range(rng.randint(0, 3)):
            pays.append(f"{oid} {rng.choice(['success', 'failed', 'failed'])}")
    rng.shuffle(pays)
    return (f"{n}\n" + "\n".join(f"{o} {t}" for o, t in orders) + f"\n{len(pays)}\n" + "\n".join(pays) + "\n")


PROBLEMS["dsc-3"] = [
    {
        "prompt": ("Annapurna's revenue tile joins orders to order_payments, which has one row per payment attempt, "
                   "and sums order_total. Show the difference. The first line is n, then n lines `order_id total`; then "
                   "m, then m lines `order_id status` (status is success or failed). Complete `revenue_both_ways`. "
                   "The program prints `joined_sum`, the inflated figure from summing the order total once per "
                   "payment row, and `true_revenue`, counting each order once if it has at least one successful "
                   "payment."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_FAN, stub(_SIG_FAN, _DOC_FAN, "0, 0")),
        "solution": program(_IO_FAN, _SIG_FAN + f'''
    """{_DOC_FAN}"""
    joined = 0
    paid = set()
    for order_id, status in payments:
        joined += orders.get(order_id, 0)
        if status == "success":
            paid.add(order_id)
    return joined, sum(orders[o] for o in paid if o in orders)
'''),
        "alt": _alt_fan,
        "explanation": ("A one-to-many join repeats the order row once per payment attempt, so SUM(order_total) "
                        "counts it several times. Collapsing payments to a set of paid order ids first (one row per "
                        "order) and then summing gives the true figure."),
        "key_justification": "Aggregate the many side to one row per key before joining.",
        "variants": variants(
            [({}, [("2\no1 500\no2 300\n3\no1 failed\no1 success\no2 failed\n", "joined_sum 1300\ntrue_revenue 500")]),
             ({}, [("3\na 100\nb 200\nc 50\n2\nb success\nc success\n", "joined_sum 250\ntrue_revenue 250")]),
             ({}, [("1\nx 900\n3\nx success\nx success\nx failed\n", "joined_sum 2700\ntrue_revenue 900")])],
            _gen_fan, 330,
            extra_hidden=[["1\no1 10\n0\n"], ["2\no1 10\no2 20\n1\no2 failed\n"], ["1\nz 5\n2\nz success\nz success\n"]]),
    },
]

_IO_TZ = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        day, clock, amount = data[1 + i].split()
        rows.append((day + " " + clock, int(amount)))
    for day, total in totals_by_ist_date(rows):
        print(day, total)


main()
'''
_SIG_TZ = "def totals_by_ist_date(rows):"
_DOC_TZ = ("rows: list of ('YYYY-MM-DD HH:MM' in UTC, amount). Return (IST date 'YYYY-MM-DD', total) for every "
           "IST date with sales, in date order. IST is UTC + 5 hours 30 minutes.")


def _alt_tz(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    ist = timezone(timedelta(hours=5, minutes=30))
    totals = {}
    for row in rows[1:1 + n]:
        day, clock, amount = row.split()
        moment = datetime.strptime(day + " " + clock, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        local = moment.astimezone(ist).date().isoformat()
        totals[local] = totals.get(local, 0) + int(amount)
    return "\n".join(f"{d} {totals[d]}" for d in sorted(totals))


def _gen_tz(rng, size):
    n = {"small": 6, "medium": 20, "large": 50}[size]
    start = datetime(2026, rng.choice([1, 2, 12]), rng.randint(26, 28))
    rows = []
    for _ in range(n):
        moment = start + timedelta(minutes=rng.randint(0, 6 * 24 * 60))
        rows.append(f"{moment:%Y-%m-%d %H:%M} {rng.choice([120, 340, 560, 999])}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-3"].append({
    "prompt": ("Annapurna stores order times in UTC, but finance reports by Indian date, so late-evening orders land "
               "on the wrong day. The first line is n, then n lines `YYYY-MM-DD HH:MM amount` in UTC. Complete "
               "`totals_by_ist_date`: convert each time to IST (UTC + 5:30) and total the amounts per IST date. "
               "The program prints `date total` for each IST date that has sales, earliest first. Month and year "
               "ends must roll over correctly."),
    "ds_topic": "string", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_TZ, stub(_SIG_TZ, _DOC_TZ, "[]")),
    "solution": "from datetime import datetime, timedelta\n" + program(_IO_TZ, _SIG_TZ + f'''
    """{_DOC_TZ}"""
    totals = {{}}
    for stamp, amount in rows:
        local = datetime.strptime(stamp, "%Y-%m-%d %H:%M") + timedelta(hours=5, minutes=30)
        key = local.strftime("%Y-%m-%d")
        totals[key] = totals.get(key, 0) + amount
    return sorted(totals.items())
'''),
    "alt": _alt_tz,
    "explanation": ("Parse each timestamp, add the fixed +5:30 offset, and only then take the date; anything from "
                    "18:30 UTC onwards belongs to the next Indian day. Using datetime arithmetic, not string slicing, "
                    "makes month and year ends roll over correctly. In SQL the fix is grouping by the converted "
                    "timestamp, e.g. AT TIME ZONE 'Asia/Kolkata'."),
    "key_justification": "Convert to the reporting time zone before truncating to a date.",
    "variants": variants(
        [({}, [("3\n2026-03-01 18:00 100\n2026-03-01 18:30 200\n2026-03-01 23:59 50\n",
                "2026-03-01 100\n2026-03-02 250")]),
         ({}, [("2\n2026-12-31 19:00 700\n2026-12-31 10:00 300\n", "2026-12-31 300\n2027-01-01 700")]),
         ({}, [("2\n2026-02-28 20:15 40\n2026-02-28 05:00 60\n", "2026-02-28 60\n2026-03-01 40")])],
        _gen_tz, 340,
        extra_hidden=[["1\n2026-06-30 18:29 1\n"], ["1\n2026-06-30 18:30 1\n"], ["2\n2024-02-28 19:00 5\n2024-02-29 19:00 6\n"]]),
})

# ---------------------------------------------------------------- dsc-4 Sahyog Dairy
_IO_ERR = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    pairs = [tuple(map(float, data[1 + i].split())) for i in range(n)]
    mae, rmse = error_metrics(pairs)
    print("MAE", format(mae, ".2f"))
    print("RMSE", format(rmse, ".2f"))


main()
'''
_SIG_ERR = "def error_metrics(pairs):"
_DOC_ERR = "pairs: list of (actual, forecast) litres. Return (mean absolute error, root mean squared error)."


def _alt_err(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    diffs = [float(a) - float(f) for a, f in (r.split() for r in rows[1:1 + n])]
    mae = sum(map(abs, diffs)) / n
    rmse = (sum(d ** 2 for d in diffs) / n) ** 0.5
    return f"MAE {format(mae, '.2f')}\nRMSE {format(rmse, '.2f')}"


def _gen_err(rng, size):
    n = {"small": 5, "medium": 20, "large": 60}[size]
    rows = []
    for _ in range(n):
        actual = rng.randint(800, 2400)
        miss = rng.randint(-120, 120) if rng.random() < 0.9 else rng.randint(-600, 600)
        rows.append(f"{actual} {actual + miss}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-4"] = [
    {
        "prompt": ("Sahyog Dairy pays the same cost for every litre of forecast error, in either direction, so it "
                   "should headline mean absolute error; the team also wants RMSE alongside to see how much big misses "
                   "matter. The first line is n, then n lines `actual forecast` for a centre's days. Complete "
                   "`error_metrics`. The program prints `MAE` and `RMSE`, each to two decimals."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_ERR, stub(_SIG_ERR, _DOC_ERR, "0.0, 0.0")),
        "solution": "import math\n" + program(_IO_ERR, _SIG_ERR + f'''
    """{_DOC_ERR}"""
    n = len(pairs)
    mae = sum(abs(a - f) for a, f in pairs) / n
    rmse = math.sqrt(sum((a - f) ** 2 for a, f in pairs) / n)
    return mae, rmse
'''),
        "alt": _alt_err,
        "explanation": ("MAE averages the absolute errors, matching a cost that grows in a straight line with the "
                        "miss. RMSE squares errors before averaging, so one big miss pushes it up much more; when "
                        "RMSE is far above MAE, a few large misses dominate."),
        "key_justification": "MAE for linear costs; RMSE weights large errors more.",
        "variants": variants(
            [({}, [("3\n100 110\n200 190\n300 300\n", "MAE 6.67\nRMSE 8.16")]),
             ({}, [("2\n1000 1000\n1000 1100\n", "MAE 50.00\nRMSE 70.71")]),
             ({}, [("4\n50 60\n50 40\n50 60\n50 40\n", "MAE 10.00\nRMSE 10.00")])],
            _gen_err, 410,
            extra_hidden=[["1\n500 500\n"], ["2\n10 0\n0 10\n"], ["3\n1 2\n1 2\n1 31\n"]]),
    },
]

_IO_POOL = '''
def main():
    data = sys.stdin.read().split("\\n")
    k = float(data[0])
    n = int(data[1])
    rows = []
    for i in range(n):
        district, centre, litres = data[2 + i].split()
        rows.append((district, centre, float(litres)))
    for centre, estimate in pooled_estimates(rows, k):
        print(centre, format(estimate, ".1f"))


main()
'''
_SIG_POOL = "def pooled_estimates(rows, k):"
_DOC_POOL = ("rows: list of (district, centre, litres) daily readings. For each centre return (centre, (n_c * "
             "mean_c + k * mean_d) / (n_c + k)), where mean_c and n_c are the centre's mean and number of days and "
             "mean_d is the mean of all readings in its district. Sort by centre id.")


def _alt_pool(stdin):
    rows = stdin.split("\n")
    k = float(rows[0])
    n = int(rows[1])
    data = [r.split() for r in rows[2:2 + n]]
    out = []
    for centre in sorted({c for _, c, _ in data}):
        mine = [float(v) for _, c, v in data if c == centre]
        district = next(d for d, c, _ in data if c == centre)
        dist = [float(v) for d, _, v in data if d == district]
        est = (sum(mine) + k * (sum(dist) / len(dist))) / (len(mine) + k)
        out.append(f"{centre} {format(est, '.1f')}")
    return "\n".join(out)


def _gen_pool(rng, size):
    centres = {"small": 4, "medium": 8, "large": 14}[size]
    k = rng.choice([2, 3, 5])
    rows = []
    for c in range(1, centres + 1):
        district = rng.choice(["Kanakpur", "Bhimgarh", "Tilwara"])
        base = rng.randint(600, 1800)
        for _ in range(rng.randint(1, 6)):
            rows.append(f"{district} C{c:02d} {base + rng.randint(-150, 150)}")
    return f"{k}\n{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-4"].append({
    "prompt": ("Tilwara's new centres have only a few days of data, so their own averages swing wildly. Sahyog Dairy "
               "will shrink each centre's average towards its district's average, more strongly when the centre has "
               "few days (partial pooling). The first line is k (how many 'days' the district average is worth), the "
               "second is n, then n lines `district centre litres` (a centre is always in one district). Complete "
               "`pooled_estimates`. For each centre the estimate is (n_c x mean_c + k x mean_d) / (n_c + k), where "
               "mean_d is the mean of every reading in that district. Print `centre estimate` to one decimal, sorted "
               "by centre id."),
    "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_POOL, stub(_SIG_POOL, _DOC_POOL, "[]")),
    "solution": program(_IO_POOL, _SIG_POOL + f'''
    """{_DOC_POOL}"""
    centre_sum, centre_days, centre_district = {{}}, {{}}, {{}}
    district_sum, district_days = {{}}, {{}}
    for district, centre, litres in rows:
        centre_sum[centre] = centre_sum.get(centre, 0.0) + litres
        centre_days[centre] = centre_days.get(centre, 0) + 1
        centre_district[centre] = district
        district_sum[district] = district_sum.get(district, 0.0) + litres
        district_days[district] = district_days.get(district, 0) + 1
    out = []
    for centre in sorted(centre_sum):
        district = centre_district[centre]
        mean_d = district_sum[district] / district_days[district]
        estimate = (centre_sum[centre] + k * mean_d) / (centre_days[centre] + k)
        out.append((centre, estimate))
    return out
'''),
    "alt": _alt_pool,
    "explanation": ("Two levels of grouping in dictionaries (per centre and per district) give every mean in one "
                    "pass. A centre with many days keeps an estimate close to its own mean; one with two days is "
                    "pulled strongly towards the district, which is steadier than trusting two readings."),
    "key_justification": "Partial pooling = weighted blend of group and parent means.",
    "variants": variants(
        [({}, [("2\n4\nT C1 100\nT C1 100\nT C2 400\nT C2 400\n", "C1 175.0\nC2 325.0")]),
         ({}, [("1\n3\nK A 1000\nB B 500\nB B 700\n", "A 1000.0\nB 600.0")]),
         ({}, [("3\n2\nD X 90\nD Y 30\n", "X 67.5\nY 52.5")])],
        _gen_pool, 420,
        extra_hidden=[["5\n1\nT Z 10\n"], ["0\n2\nK P 5\nK Q 15\n"], ["2\n3\nA M 1\nA M 2\nA M 3\n"]]),
})

# ---------------------------------------------------------------- dsc-5 Sanjeevani Clinics
_IO_CALLS = '''
def main():
    data = sys.stdin.read().split("\\n")
    capacity, n = map(int, data[0].split())
    rows = []
    for i in range(n):
        appointment, risk = data[1 + i].split()
        rows.append((appointment, int(risk)))
    chosen = call_list(rows, capacity)
    print("\\n".join(chosen) if chosen else "NONE")


main()
'''
_SIG_CALLS = "def call_list(rows, capacity):"
_DOC_CALLS = ("rows: list of (appointment_id, risk percent). Return the ids of the `capacity` highest-risk "
              "appointments, highest first; ties go to the smaller id in string order.")


def _alt_calls(stdin):
    rows = stdin.split("\n")
    capacity, n = map(int, rows[0].split())
    items = [r.split() for r in rows[1:1 + n]]
    items.sort(key=lambda x: x[0])
    items.sort(key=lambda x: int(x[1]), reverse=True)
    return "\n".join(a for a, _ in items[:capacity]) or "NONE"


def _gen_calls(rng, size):
    n = {"small": 8, "medium": 30, "large": 90}[size]
    capacity = rng.randint(2, max(3, n // 4))
    rows = [f"A{i:03d} {rng.randint(1, 60)}" for i in rng.sample(range(1, 999), n)]
    return f"{capacity} {n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-5"] = [
    {
        "prompt": ("The call centre can make only a fixed number of reminder calls, so the list should hold the "
                   "appointments most likely to be missed. The first line is `capacity n`, then n lines "
                   "`appointment_id risk` (risk is the model's no-show probability as a whole percent). Complete "
                   "`call_list`. The program prints the ids to call, one per line, highest risk first; ties go to "
                   "the smaller id in string order. It prints NONE if there are no appointments."),
        "ds_topic": "heap", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_CALLS, stub(_SIG_CALLS, _DOC_CALLS, "[]")),
        "solution": "import heapq\n" + program(_IO_CALLS, _SIG_CALLS + f'''
    """{_DOC_CALLS}"""
    best = heapq.nsmallest(capacity, rows, key=lambda r: (-r[1], r[0]))
    return [appointment for appointment, _ in best]
'''),
        "alt": _alt_calls,
        "explanation": ("Choosing the top `capacity` of n items is a top-k problem: a heap does it in O(n log k) "
                        "without sorting every appointment. Ranking by predicted risk is what turns a model score "
                        "into a decision the call centre can act on."),
        "key_justification": "Top-k selection by score with a deterministic tie-break.",
        "variants": variants(
            [({}, [("2 4\nA1 30\nA2 55\nA3 30\nA4 10\n", "A2\nA1")]),
             ({}, [("3 3\nB7 5\nB2 40\nB9 40\n", "B2\nB9\nB7")]),
             ({}, [("1 2\nC10 12\nC2 12\n", "C10")])],
            _gen_calls, 510,
            extra_hidden=[["5 0\n"], ["2 2\nZ1 1\nZ2 99\n"], ["3 4\nP1 7\nP2 7\nP3 7\nP4 7\n"]]),
    },
]

_IO_PRIOR = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        patient, showed = data[1 + i].split()
        rows.append((patient, int(showed)))
    for patient, rate in prior_no_show(rows):
        print(patient, "NA" if rate is None else format(rate, ".2f"))


main()
'''
_SIG_PRIOR = "def prior_no_show(rows):"
_DOC_PRIOR = ("rows: list of (patient_id, showed 1/0) in appointment date order. For each row return (patient_id, "
              "that patient's no-show rate over their EARLIER appointments only, or None for their first).")


def _alt_prior(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for i, (p, _) in enumerate(rows):
        before = [int(s) for q, s in rows[:i] if q == p]
        out.append(f"{p} " + ("NA" if not before else format(before.count(0) / len(before), ".2f")))
    return "\n".join(out)


def _gen_prior(rng, size):
    n = {"small": 6, "medium": 20, "large": 60}[size]
    patients = [f"P{i}" for i in range(1, {"small": 3, "medium": 6, "large": 12}[size] + 1)]
    rows = [f"{rng.choice(patients)} {0 if rng.random() < 0.25 else 1}" for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["dsc-5"].append({
    "prompt": ("A strong feature for the no-show model is a patient's own history, but it must only use appointments "
               "that happened BEFORE the one being predicted, or the model trains on information it will not have. "
               "The first line is n, then n lines `patient_id showed` (1 showed up, 0 did not), in date order. "
               "Complete `prior_no_show`. For each row, in order, the program prints `patient_id rate`: the share of "
               "that patient's earlier appointments they missed, to two decimals, or NA for their first appointment."),
    "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_PRIOR, stub(_SIG_PRIOR, _DOC_PRIOR, "[]")),
    "solution": program(_IO_PRIOR, _SIG_PRIOR + f'''
    """{_DOC_PRIOR}"""
    seen, missed = {{}}, {{}}
    out = []
    for patient, showed in rows:
        count = seen.get(patient, 0)
        out.append((patient, None if count == 0 else missed.get(patient, 0) / count))
        seen[patient] = count + 1                      # update AFTER using the history: no leakage
        missed[patient] = missed.get(patient, 0) + (1 - showed)
    return out
'''),
    "alt": _alt_prior,
    "explanation": ("Walk the rows in time order with running counts per patient in a dictionary, and read the "
                    "counts before adding the current row. Updating first would leak the outcome being predicted "
                    "into its own feature. In SQL this is a window function over ROWS BETWEEN UNBOUNDED PRECEDING "
                    "AND 1 PRECEDING."),
    "key_justification": "Point-in-time features: read history before updating it.",
    "variants": variants(
        [({}, [("4\nP1 0\nP2 1\nP1 1\nP1 0\n", "P1 NA\nP2 NA\nP1 1.00\nP1 0.50")]),
         ({}, [("3\nP5 1\nP5 1\nP5 0\n", "P5 NA\nP5 0.00\nP5 0.00")]),
         ({}, [("4\nQ 0\nQ 0\nQ 1\nQ 1\n", "Q NA\nQ 1.00\nQ 1.00\nQ 0.67")])],
        _gen_prior, 520,
        extra_hidden=[["1\nP9 0\n"], ["2\nA 1\nB 0\n"], ["3\nR 0\nS 0\nR 0\n"]]),
})

"""Code pool for Data Engineering (den-2 .. den-5). Built and checked by scripts/build_code_pools.py."""
import re
from datetime import date, timedelta

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}


def _hundredths(text):
    whole, _, frac = text.partition(".")
    return int(whole) * 100 + int((frac + "00")[:2])


# ---------------------------------------------------------------- den-2 Swachh Urja
_IO_LOAD = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = [tuple(data[1 + i].split()) for i in range(n)]
    per_meter, duplicates = idempotent_load(rows)
    for meter, readings, total in per_meter:
        print(meter, readings, f"{total // 100}.{total % 100:02d}")
    print("duplicates", duplicates)


main()
'''
_SIG_LOAD = "def idempotent_load(rows):"
_DOC_LOAD = ("rows: list of (meter, timestamp, kWh as text with 2 decimals). The same (meter, timestamp) may arrive more "
             "than once; the LAST copy wins. Return ([(meter, readings, total kWh in hundredths)] sorted by meter, "
             "number of repeated rows).")


def _alt_load(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    final = {}
    for m, ts, kwh in rows:
        final[(m, ts)] = _hundredths(kwh)
    out = []
    for m in sorted({m for m, _ in final}):
        vals = [v for (mm, _), v in final.items() if mm == m]
        out.append(f"{m} {len(vals)} {sum(vals) // 100}.{sum(vals) % 100:02d}")
    return "\n".join(out + [f"duplicates {len(rows) - len(final)}"])


def _gen_load(rng, size):
    n = {"small": 6, "medium": 25, "large": 55}[size]
    rows = []
    for _ in range(n):
        if rows and rng.random() < 0.3:
            m, ts, _ = rng.choice(rows).split()
            kwh = f"{rng.randint(0, 300) / 100:.2f}" if rng.random() < 0.3 else _
        else:
            m = f"MTR{rng.randint(1, 5):02d}"
            ts = f"03-01T{rng.randint(0, 23):02d}:{rng.choice(['00', '15', '30', '45'])}"
            kwh = f"{rng.randint(0, 300) / 100:.2f}"
        rows.append(f"{m} {ts} {kwh}")
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_DAG = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    needs = {}
    for i in range(n):
        task, deps = data[1 + i].split()
        needs[task] = [] if deps == "-" else deps.split(",")
    failed = data[1 + n].strip()
    ran, skipped = run_with_failure(needs, failed)
    print("ran", " ".join(ran))
    print("skipped", " ".join(skipped) if skipped else "-")


main()
'''
_SIG_DAG = "def run_with_failure(needs, failed):"
_DOC_DAG = ("needs: {task: [tasks it depends on]} (a DAG; every task is a key). Tasks run in dependency order, always "
            "the alphabetically first ready task. `failed` runs and fails; every task that depends on it, directly or "
            "indirectly, is skipped. Return (tasks that ran, in run order; skipped tasks, sorted).")


def _alt_dag(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    needs = {}
    for r in rows[1:1 + n]:
        t, d = r.split()
        needs[t] = set() if d == "-" else set(d.split(","))
    failed = rows[1 + n].strip()
    bad = set()
    changed = True
    while changed:
        changed = False
        for t, d in needs.items():
            if t not in bad and (failed in d or d & bad):
                bad.add(t)
                changed = True
    order, done = [], set()
    while len(done) < len(needs):
        t = min(x for x in needs if x not in done and needs[x] <= done)
        done.add(t)
        order.append(t)
    ran = [t for t in order if t not in bad]
    return f"ran {' '.join(ran)}\nskipped {' '.join(sorted(bad)) or '-'}"


_TASKS = ["extract_meters", "extract_outages", "clean", "dedupe", "billing", "alerts", "report", "load_wh", "audit",
          "notify", "archive", "quality"]


def _gen_dag(rng, size):
    n = {"small": 5, "medium": 8, "large": 12}[size]
    names = rng.sample(_TASKS, n)
    rows = []
    for i, t in enumerate(names):
        deps = rng.sample(names[:i], rng.randint(0, min(2, i))) if i else []
        rows.append(f"{t} {','.join(deps) or '-'}")
    failed = rng.choice(names)
    rng.shuffle(rows)
    return f"{n}\n" + "\n".join(rows) + f"\n{failed}\n"


PROBLEMS["den-2"] = [
    {
        "prompt": ("A failed nightly load was rerun and the meters' gateway also re-sends readings, so the same reading "
                   "can arrive twice; loading it twice doubles a customer's bill. Make the load idempotent. The first "
                   "line is n, then n lines `meter timestamp kwh` (kWh with two decimals). Complete `idempotent_load`: "
                   "keep one reading per (meter, timestamp), and if the same key arrives again the later copy replaces "
                   "the earlier one (it may be a correction). Add kWh in whole hundredths, not floats. The program prints "
                   "`meter readings total` per meter, sorted, then `duplicates d` (how many rows were replaced)."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_LOAD, stub(_SIG_LOAD, _DOC_LOAD, "[], 0")),
        "solution": program(_IO_LOAD, _SIG_LOAD + f'''
    """{_DOC_LOAD}"""
    latest = {{}}
    for meter, ts, kwh in rows:
        whole, _, frac = kwh.partition(".")
        latest[(meter, ts)] = int(whole) * 100 + int((frac + "00")[:2])   # an upsert: the key decides, not the row
    totals = {{}}
    for (meter, _), value in latest.items():
        count, total = totals.get(meter, (0, 0))
        totals[meter] = (count + 1, total + value)
    return [(m, *totals[m]) for m in sorted(totals)], len(rows) - len(latest)
'''),
        "alt": _alt_load,
        "explanation": ("Keying readings by (meter, timestamp) in a dictionary is an upsert: loading the same batch "
                        "twice produces the same result, which is what idempotent means. In the warehouse the same idea "
                        "is a MERGE on the natural key. Money and energy stay in integer hundredths so 0.1 + 0.2 never "
                        "becomes 0.30000000000000004."),
        "key_justification": "Upsert on a natural key makes a load safe to rerun.",
        "variants": variants(
            [({}, [("4\nM1 00:15 1.20\nM1 00:30 0.80\nM1 00:15 1.20\nM2 00:15 2.05\n", "M1 2 2.00\nM2 1 2.05\nduplicates 1")]),
             ({}, [("3\nA 01:00 1.20\nA 01:00 1.50\nA 01:15 0.05\n", "A 2 1.55\nduplicates 1")]),
             ({}, [("2\nZ 09:00 0.10\nZ 09:15 0.20\n", "Z 2 0.30\nduplicates 0")])],
            _gen_load, 4010,
            extra_hidden=[["1\nX 00:00 0.00\n"], ["3\nB 1 1.5\nB 1 2.5\nB 1 3.5\n"], ["2\nQ t 10.99\nP t 0.01\n"]]),
    },
    {
        "prompt": ("Twelve cron scripts became one orchestrated DAG, so a failure now stops only the tasks that depend "
                   "on it. The first line is n, then n lines `task deps` (deps comma-separated, or - for none), then the "
                   "name of the task that fails. Complete `run_with_failure`: run tasks in dependency order, always "
                   "picking the alphabetically first task whose dependencies have all finished. The failing task runs "
                   "and fails; every task downstream of it, directly or indirectly, is skipped. The program prints `ran` "
                   "with the tasks that ran in order, then `skipped` with the skipped tasks sorted, or `-`."),
        "ds_topic": "graph", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_DAG, stub(_SIG_DAG, _DOC_DAG, "list(needs), []")),
        "solution": "import heapq\n" + program(_IO_DAG, _SIG_DAG + f'''
    """{_DOC_DAG}"""
    children = {{t: [] for t in needs}}
    waiting = {{t: len(d) for t, d in needs.items()}}
    for t, deps in needs.items():
        for d in deps:
            children[d].append(t)
    skipped, stack = set(), [failed]
    while stack:                                   # everything downstream of the failure
        for child in children[stack.pop()]:
            if child not in skipped:
                skipped.add(child)
                stack.append(child)
    ready = [t for t, w in waiting.items() if w == 0]
    heapq.heapify(ready)
    ran = []
    while ready:
        task = heapq.heappop(ready)
        if task not in skipped:
            ran.append(task)
        for child in children[task]:
            waiting[child] -= 1
            if waiting[child] == 0:
                heapq.heappush(ready, child)
    return ran, sorted(skipped)
'''),
        "alt": _alt_dag,
        "explanation": ("The pipeline is a directed acyclic graph. A topological sort (Kahn's algorithm with a min-heap "
                        "for a deterministic order) gives the run order, and a traversal from the failed task over the "
                        "'is needed by' edges finds everything that must be skipped. Unrelated branches keep running, "
                        "which is the point of an orchestrator over fixed cron times."),
        "key_justification": "Topological order plus downstream traversal in a DAG.",
        "variants": variants(
            [({}, [("5\nextract -\nclean extract\nbill clean\nalert extract\nreport bill\nclean\n",
                    "ran extract alert clean\nskipped bill report")]),
             ({}, [("3\na -\nb -\nc a,b\nb\n", "ran a b\nskipped c")]),
             ({}, [("2\nload -\naudit -\naudit\n", "ran audit load\nskipped -")])],
            _gen_dag, 4020,
            extra_hidden=[["1\nsolo -\nsolo\n"], ["4\nd c\nc b\nb a\na -\na\n"], ["3\nx -\ny x\nz -\nz\n"]]),
    },
]

# ---------------------------------------------------------------- den-3 Bhojan Express
_IO_LATE = '''
def main():
    data = sys.stdin.read().split("\\n")
    event_day, load_day = data[0].split()
    n = int(data[1])
    orders = []
    for i in range(n):
        order, happened, arrived, amount = data[2 + i].split()
        orders.append((order, happened, arrived, int(amount)))
    loaded, late, missing = late_report(orders, event_day, load_day)
    print("loaded", loaded)
    print("late", late)
    print("missing_amount", missing)


main()
'''
_SIG_LATE = "def late_report(orders, event_day, load_day):"
_DOC_LATE = ("orders: list of (order_id, event date, arrival date, amount), dates as YYYY-MM-DD. The load on the night "
             "of load_day contains orders that ARRIVED on or before load_day. For orders that happened on event_day, "
             "return (amount loaded, number that arrived later, their amount).")


def _alt_late(stdin):
    rows = stdin.split("\n")
    ev, ld = rows[0].split()
    n = int(rows[1])
    o = [r.split() for r in rows[2:2 + n]]
    mine = [x for x in o if x[1] == ev]
    loaded = sum(int(x[3]) for x in mine if date.fromisoformat(x[2]) <= date.fromisoformat(ld))
    late = [x for x in mine if date.fromisoformat(x[2]) > date.fromisoformat(ld)]
    return f"loaded {loaded}\nlate {len(late)}\nmissing_amount {sum(int(x[3]) for x in late)}"


def _gen_late(rng, size):
    n = {"small": 6, "medium": 25, "large": 45}[size]
    base = date(2026, 3, 10)
    rows = []
    for i in range(n):
        ev = base + timedelta(days=rng.choice([-1, 0, 0, 0, 1]))
        arr = ev + timedelta(days=rng.choice([0, 0, 0, 1, 2]))
        rows.append(f"o{i + 1} {ev} {arr} {rng.choice([120, 249, 380, 560, 899])}")
    return f"{base} {base + timedelta(days=rng.choice([0, 1]))}\n{n}\n" + "\n".join(rows) + "\n"


_IO_CONTRACT = '''
def main():
    data = sys.stdin.read().split("\\n")
    contract = [tuple(c.split(":")) for c in data[0].split(",")]
    header = data[1].split(",")
    n = int(data[2])
    rows = [data[3 + i].split(",") for i in range(n)]
    problems = check_contract(contract, header, rows)
    print("\\n".join(problems) if problems else "VALID")


main()
'''
_SIG_CONTRACT = "def check_contract(contract, header, rows):"
_DOC_CONTRACT = ("contract: list of (column, type int|decimal|text, nullable y|n). Return problems in this order: "
                 "'missing COL' for contract columns not in the header (contract order), 'unexpected COL' for header "
                 "columns not in the contract (header order), then for each row r (from 1) and each contract column "
                 "present, in contract order: 'row r COL null' if empty and not nullable, else 'row r COL bad_int' or "
                 "'row r COL bad_decimal' if a non-empty value has the wrong type.")


def _alt_contract(stdin):
    rows = stdin.split("\n")
    contract = [c.split(":") for c in rows[0].split(",")]
    header = rows[1].split(",")
    n = int(rows[2])
    data = [r.split(",") for r in rows[3:3 + n]]
    out = [f"missing {c}" for c, _, _ in contract if c not in header]
    out += [f"unexpected {h}" for h in header if h not in [c for c, _, _ in contract]]
    for r, row in enumerate(data, 1):
        for col, typ, nullable in contract:
            if col not in header:
                continue
            v = row[header.index(col)]
            if v == "":
                if nullable == "n":
                    out.append(f"row {r} {col} null")
                continue
            if typ == "int" and not (v.lstrip("-").isdigit() and v.count("-") <= 1 and not v.startswith("--")):
                out.append(f"row {r} {col} bad_int")
            elif typ == "decimal":
                body = v[1:] if v.startswith("-") else v
                parts = body.split(".")
                ok = len(parts) <= 2 and all(p.isdigit() for p in parts) and all(parts)
                if not ok:
                    out.append(f"row {r} {col} bad_decimal")
    return "\n".join(out) or "VALID"


def _gen_contract(rng, size):
    n = {"small": 3, "medium": 8, "large": 18}[size]
    contract = "order_id:int:n,amount:decimal:n,coupon:text:y,city:text:n"
    cols = ["order_id", "amount", "coupon", "city"]
    if rng.random() < 0.4:
        cols.remove(rng.choice(cols))
    if rng.random() < 0.4:
        cols.insert(rng.randint(0, len(cols)), "channel")
    values = {"order_id": ["101", "102", "x7", "", "-3", "1e3"], "amount": ["250.50", "99", "", "12.", "abc", "-7.25"],
              "coupon": ["", "DIWALI50", "FREE"], "city": ["Hyd", "", "Pune"], "channel": ["app", "web"]}
    rows = [",".join(rng.choice(values[c]) for c in cols) for _ in range(n)]
    return f"{contract}\n{','.join(cols)}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["den-3"] = [
    {
        "prompt": ("Finance's revenue is higher than the warehouse's because orders that happen late at night often "
                   "arrive after the 1 am load, so they are missing from that day. Measure it. The first line is "
                   "`event_day load_day`, the second is n, then n lines `order event_date arrival_date amount` (dates "
                   "YYYY-MM-DD). Complete `late_report`: the load on load_day contains orders that arrived on or before "
                   "load_day. For orders that happened on event_day, the program prints `loaded` (amount already in the "
                   "warehouse), `late` (how many arrived after the load) and `missing_amount`."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_LATE, stub(_SIG_LATE, _DOC_LATE, "0, 0, 0")),
        "solution": program(_IO_LATE, _SIG_LATE + f'''
    """{_DOC_LATE}"""
    loaded = late = missing = 0
    for _, happened, arrived, amount in orders:
        if happened != event_day:
            continue
        if arrived <= load_day:            # ISO dates compare correctly as strings
            loaded += amount
        else:
            late += 1
            missing += amount
    return loaded, late, missing
'''),
        "alt": _alt_late,
        "explanation": ("Separating event time from arrival time is the key idea: a load filtered by arrival misses late "
                        "events that belong to an earlier day. Measuring the gap shows whether to reprocess recent "
                        "partitions (a look-back window) instead of loading each day only once."),
        "key_justification": "Event time versus arrival time for late-arriving data.",
        "variants": variants(
            [({}, [("2026-03-10 2026-03-10\n4\no1 2026-03-10 2026-03-10 500\no2 2026-03-10 2026-03-11 300\n"
                    "o3 2026-03-09 2026-03-10 200\no4 2026-03-10 2026-03-12 100\n", "loaded 500\nlate 2\nmissing_amount 400")]),
             ({}, [("2026-03-10 2026-03-11\n2\na 2026-03-10 2026-03-11 90\nb 2026-03-10 2026-03-12 10\n",
                    "loaded 90\nlate 1\nmissing_amount 10")]),
             ({}, [("2026-01-01 2026-01-05\n1\nz 2025-12-31 2026-01-01 70\n", "loaded 0\nlate 0\nmissing_amount 0")])],
            _gen_late, 4110,
            extra_hidden=[["2026-03-10 2026-03-10\n0\n"], ["2026-12-31 2026-12-31\n2\nx 2026-12-31 2027-01-01 5\ny 2026-12-31 2026-12-31 6\n"],
                          ["2026-03-10 2026-03-09\n1\nq 2026-03-10 2026-03-10 40\n"]]),
    },
    {
        "prompt": ("An upstream team renamed a column and the pipeline silently loaded empty amounts. A data contract "
                   "stops that at the door. The first line is the contract, `column:type:nullable` items separated by "
                   "commas (type int, decimal or text; nullable y or n). The second line is the CSV header, the third is "
                   "n, then n CSV rows (no quoting). Complete `check_contract`. Report `missing COL` for contract columns "
                   "absent from the header (contract order), `unexpected COL` for extra header columns (header order), "
                   "then for each row r and each contract column present: `row r COL null` if empty but not nullable, "
                   "otherwise `row r COL bad_int` or `row r COL bad_decimal` for a wrong type (int: optional minus then "
                   "digits; decimal: optional minus, digits, optionally a dot and more digits). Print the problems, or "
                   "VALID."),
        "ds_topic": "string", "difficulty": 2, "skills": ["Python", "SQL"],
        "starter": program(_IO_CONTRACT, stub(_SIG_CONTRACT, _DOC_CONTRACT, "[]")),
        "solution": "import re\n" + program(_IO_CONTRACT, _SIG_CONTRACT + f'''
    """{_DOC_CONTRACT}"""
    pattern = {{"int": re.compile(r"-?\\d+"), "decimal": re.compile(r"-?\\d+(\\.\\d+)?")}}
    names = [c for c, _, _ in contract]
    problems = [f"missing {{c}}" for c in names if c not in header]
    problems += [f"unexpected {{h}}" for h in header if h not in names]
    position = {{h: i for i, h in enumerate(header)}}
    for r, row in enumerate(rows, 1):
        for col, kind, nullable in contract:
            if col not in position:
                continue
            value = row[position[col]]
            if value == "":
                if nullable == "n":
                    problems.append(f"row {{r}} {{col}} null")
            elif kind in pattern and not pattern[kind].fullmatch(value):
                problems.append(f"row {{r}} {{col}} bad_{{kind}}")
    return problems
'''),
        "alt": _alt_contract,
        "explanation": ("Checking the schema (missing and unexpected columns) and then each value's nullability and type "
                        "turns a silent bad load into a clear error before anything is written. fullmatch with a small "
                        "regular expression is a precise type test; '12.' and '1e3' fail on purpose."),
        "key_justification": "Schema and type validation of incoming rows (string patterns).",
        "variants": variants(
            [({}, [("order_id:int:n,amount:decimal:n,coupon:text:y\norder_id,amount,city\n3\n101,250.50,Hyd\n102,,Hyd\nx7,99,Hyd\n",
                    "missing coupon\nunexpected city\nrow 2 amount null\nrow 3 order_id bad_int")]),
             ({}, [("id:int:n,price:decimal:y\nid,price\n2\n1,\n2,10.5\n", "VALID")]),
             ({}, [("qty:int:n\nqty\n3\n-4\n4.0\n\n", "row 2 qty bad_int\nrow 3 qty null")])],
            _gen_contract, 4120,
            extra_hidden=[["a:text:n\nb\n1\nx\n"], ["v:decimal:n\nv\n3\n12.\n-0.5\n.5\n"], ["k:int:y\nk\n1\n\n"]]),
    },
]

# ---------------------------------------------------------------- den-4 Arth Lending
_IO_PSEUDO = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = [tuple(data[1 + i].split()) for i in range(n)]
    out, distinct = pseudonymise(rows)
    for token, phone, amount in out:
        print(token, phone, amount)
    print("distinct", distinct)


main()
'''
_SIG_PSEUDO = "def pseudonymise(rows):"
_DOC_PSEUDO = ("rows: list of (PAN, phone, amount). Replace each PAN with a token P0001, P0002, ... in order of first "
               "appearance (the same PAN always gets the same token) and show only the last 4 phone digits after six "
               "'*'. Return (the new rows, number of distinct PANs).")


def _alt_pseudo(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    seen = []
    out = []
    for pan, phone, amt in rows:
        if pan not in seen:
            seen.append(pan)
        out.append(f"P{seen.index(pan) + 1:04d} ******{phone[-4:]} {amt}")
    return "\n".join(out + [f"distinct {len(seen)}"])


def _gen_pseudo(rng, size):
    n = {"small": 4, "medium": 15, "large": 40}[size]
    pans = ["".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(5)) + str(rng.randint(1000, 9999))
            + rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(max(2, n // 3))]
    phones = {p: str(rng.randint(6000000000, 9999999999)) for p in pans}
    rows = []
    for _ in range(n):
        p = rng.choice(pans)
        rows.append(f"{p} {phones[p]} {rng.randint(5, 200) * 1000}")
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_SCD = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    changes = []
    for i in range(n):
        borrower, day, limit = data[1 + i].split()
        changes.append((borrower, day, int(limit)))
    for borrower, start, end, limit, current in scd2(changes):
        print(borrower, start, end, limit, "Y" if current else "N")


main()
'''
_SIG_SCD = "def scd2(changes):"
_DOC_SCD = ("changes: list of (borrower, effective date YYYY-MM-DD, credit limit), in any order, at most one per "
            "borrower per day. Build type-2 history: per borrower in date order, a change to the same limit as the "
            "current version is ignored; each version is valid from its date up to (not including) the next "
            "version's date, the last one to 9999-12-31. Return [(borrower, valid_from, valid_to, limit, is_current)] "
            "sorted by borrower then valid_from.")


def _alt_scd(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for b in sorted({r[0] for r in rows}):
        mine = sorted((r for r in rows if r[0] == b), key=lambda r: r[1])
        versions = []
        for _, d, lim in mine:
            if not versions or versions[-1][1] != lim:
                versions.append((d, lim))
        for i, (d, lim) in enumerate(versions):
            last = i == len(versions) - 1
            out.append(f"{b} {d} {'9999-12-31' if last else versions[i + 1][0]} {lim} {'Y' if last else 'N'}")
    return "\n".join(out)


def _gen_scd(rng, size):
    borrowers = {"small": 2, "medium": 4, "large": 7}[size]
    rows = []
    for b in range(1, borrowers + 1):
        days = sorted(rng.sample(range(1, 300), rng.randint(1, 5)))
        for d in days:
            day = date(2026, 1, 1) + timedelta(days=d)
            rows.append(f"B{b:03d} {day} {rng.choice([20000, 50000, 50000, 80000, 120000])}")
    rng.shuffle(rows)
    return f"{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["den-4"] = [
    {
        "prompt": ("Analysts want to study repayment behaviour without seeing PAN or phone numbers. Pseudonymise the "
                   "extract so rows for the same borrower can still be linked. The first line is n, then n lines `PAN "
                   "phone amount`. Complete `pseudonymise`: replace each PAN with a token P0001, P0002, ... in order of "
                   "first appearance (the same PAN always gets the same token), and replace the phone with six `*` and "
                   "its last four digits. The program prints `token phone amount` per row, then `distinct k`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_PSEUDO, stub(_SIG_PSEUDO, _DOC_PSEUDO, "rows, 0")),
        "solution": program(_IO_PSEUDO, _SIG_PSEUDO + f'''
    """{_DOC_PSEUDO}"""
    tokens, out = {{}}, []
    for pan, phone, amount in rows:
        if pan not in tokens:
            tokens[pan] = f"P{{len(tokens) + 1:04d}}"   # stable: same PAN, same token, so rows still join
        out.append((tokens[pan], "******" + phone[-4:], amount))
    return out, len(tokens)
'''),
        "alt": _alt_pseudo,
        "explanation": ("A dictionary from PAN to token gives each borrower one stable pseudonym, so analysts can still "
                        "group and join by borrower without ever seeing the real identifier. The mapping table itself "
                        "is the sensitive part and stays in a restricted schema."),
        "key_justification": "Consistent pseudonymisation with a lookup map.",
        "variants": variants(
            [({}, [("3\nABCDE1234F 9876543210 5000\nPQRSX9876Z 9123456789 2000\nABCDE1234F 9876543210 7000\n",
                    "P0001 ******3210 5000\nP0002 ******6789 2000\nP0001 ******3210 7000\ndistinct 2")]),
             ({}, [("1\nZZZZZ0000Z 7000000001 1\n", "P0001 ******0001 1\ndistinct 1")]),
             ({}, [("2\nAAAAA1111A 9999911111 10\nBBBBB2222B 8888822222 20\n",
                    "P0001 ******1111 10\nP0002 ******2222 20\ndistinct 2")])],
            _gen_pseudo, 4210,
            extra_hidden=[["0\n"], ["2\nX 1234567890 5\nX 1234567890 6\n"], ["3\nC 1111111111 1\nB 2222222222 2\nC 1111111111 3\n"]]),
    },
    {
        "prompt": ("Credit limits change over time and risk models need the limit that was true on each past date, so "
                   "the dimension keeps history (slowly changing dimension type 2). The first line is n, then n changes "
                   "`borrower date limit`, in any order, at most one per borrower per day. Complete `scd2`: per borrower "
                   "in date order, ignore a change that repeats the current limit; each version is valid from its date "
                   "up to (not including) the next version's date, and the last one to 9999-12-31. The program prints "
                   "`borrower valid_from valid_to limit current` (Y or N), sorted by borrower then valid_from."),
        "ds_topic": "sorting", "difficulty": 2, "skills": ["Python", "SQL"],
        "starter": program(_IO_SCD, stub(_SIG_SCD, _DOC_SCD, "[]")),
        "solution": program(_IO_SCD, _SIG_SCD + f'''
    """{_DOC_SCD}"""
    out = []
    by_borrower = {{}}
    for borrower, day, limit in sorted(changes, key=lambda c: (c[0], c[1])):
        versions = by_borrower.setdefault(borrower, [])
        if versions and versions[-1][1] == limit:
            continue                                  # no real change: no new version
        versions.append((day, limit))
    for borrower in sorted(by_borrower):
        versions = by_borrower[borrower]
        for i, (day, limit) in enumerate(versions):
            last = i == len(versions) - 1
            out.append((borrower, day, "9999-12-31" if last else versions[i + 1][0], limit, last))
    return out
'''),
        "alt": _alt_scd,
        "explanation": ("Sort the changes by borrower and date, drop changes that repeat the current value, then each "
                        "version's end date is simply the next version's start. Overwriting the row (type 1) would make "
                        "every past loan look like it was approved against today's limit."),
        "key_justification": "Type-2 history built from sorted change events.",
        "variants": variants(
            [({}, [("4\nB1 2026-01-01 50000\nB1 2026-03-01 80000\nB2 2026-02-01 20000\nB1 2026-02-01 50000\n",
                    "B1 2026-01-01 2026-03-01 50000 N\nB1 2026-03-01 9999-12-31 80000 Y\nB2 2026-02-01 9999-12-31 20000 Y")]),
             ({}, [("3\nA 2026-05-01 10\nA 2026-04-01 20\nA 2026-06-01 10\n",
                    "A 2026-04-01 2026-05-01 20 N\nA 2026-05-01 9999-12-31 10 Y")]),
             ({}, [("1\nZ 2026-12-31 5\n", "Z 2026-12-31 9999-12-31 5 Y")])],
            _gen_scd, 4220,
            extra_hidden=[["2\nQ 2026-01-02 1\nQ 2026-01-01 1\n"], ["3\nb 2026-01-01 1\na 2026-01-01 2\nb 2026-01-02 3\n"],
                          ["2\nM 2026-03-01 7\nM 2026-02-01 8\n"]]),
    },
]

# ---------------------------------------------------------------- den-5 NeerSathi
_IO_SILVER = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    raw = [tuple(data[1 + i].split()) for i in range(n)]
    gold, duplicates, invalid = silver_and_gold(raw)
    for sensor, readings, average in gold:
        print(sensor, readings, format(average, ".1f"))
    print("dropped_duplicates", duplicates, "dropped_invalid", invalid)


main()
'''
_SIG_SILVER = "def silver_and_gold(raw):"
_DOC_SILVER = ("raw: list of (sensor, minute, flow) as text. Silver: drop invalid readings (flow not a whole number, "
               "or negative), then keep only the FIRST remaining reading for each (sensor, minute). Gold: per sensor "
               "the number of readings and the mean flow. Return ([(sensor, readings, mean)] sorted by sensor, "
               "duplicates dropped, invalid dropped).")


def _alt_silver(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    valid = [r for r in rows if r[2].isdigit()]
    seen, keep = set(), []
    for s, m, f in valid:
        if (s, m) not in seen:
            seen.add((s, m))
            keep.append((s, int(f)))
    out = []
    for s in sorted({s for s, _ in keep}):
        vals = [f for ss, f in keep if ss == s]
        out.append(f"{s} {len(vals)} {format(sum(vals) / len(vals), '.1f')}")
    return "\n".join(out + [f"dropped_duplicates {len(valid) - len(keep)} dropped_invalid {len(rows) - len(valid)}"])


def _gen_silver(rng, size):
    n = {"small": 6, "medium": 25, "large": 60}[size]
    rows = []
    for _ in range(n):
        if rows and rng.random() < 0.2:
            s, m, _ = rng.choice(rows).split()
        else:
            s, m = f"S{rng.randint(1, 6)}", str(rng.randint(1, 30))
        flow = rng.choice([str(rng.randint(0, 120))] * 5 + ["NaN", "-3"])
        rows.append(f"{s} {m} {flow}")
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_LEAK = '''
def main():
    data = sys.stdin.read().split("\\n")
    window, threshold = map(int, data[0].split())
    n = int(data[1])
    readings = []
    for i in range(n):
        minute, sensor, flow = data[2 + i].split()
        readings.append((int(minute), sensor, int(flow)))
    alerts = leak_alerts(readings, window, threshold)
    if not alerts:
        print("NONE")
    for sensor, minute in alerts:
        print(sensor, minute)


main()
'''
_SIG_LEAK = "def leak_alerts(readings, window, threshold):"
_DOC_LEAK = ("readings: list of (minute, sensor, flow) in time order, sensors interleaved. A sensor alerts the first "
             "time the mean of its last `window` readings is ABOVE threshold (it needs `window` readings first). "
             "Return [(sensor, minute of its first alert)] ordered by minute, then sensor.")


def _alt_leak(stdin):
    rows = stdin.split("\n")
    w, t = map(int, rows[0].split())
    n = int(rows[1])
    rs = [r.split() for r in rows[2:2 + n]]
    alerts = []
    for s in sorted({r[1] for r in rs}):
        hist = [(int(m), int(f)) for m, ss, f in rs if ss == s]
        for i in range(w - 1, len(hist)):
            if sum(f for _, f in hist[i - w + 1:i + 1]) > t * w:
                alerts.append((hist[i][0], s))
                break
    alerts.sort()
    return "\n".join(f"{s} {m}" for m, s in alerts) or "NONE"


def _gen_leak(rng, size):
    n = {"small": 8, "medium": 30, "large": 60}[size]
    sensors = ["P1", "P2", "P3", "P4"]
    leaky = rng.choice(sensors)
    rows = []
    for i in range(n):
        s = rng.choice(sensors)
        base = 40 + (rng.randint(15, 40) if s == leaky and i > n // 2 else 0)
        rows.append(f"{i + 1} {s} {base + rng.randint(-10, 10)}")
    return f"{rng.choice([2, 3, 4])} {rng.choice([45, 50, 55])}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["den-5"] = [
    {
        "prompt": ("NeerSathi lands raw sensor data unchanged (bronze), cleans it (silver) and builds per-sensor tables "
                   "(gold). Write the silver and gold steps. The first line is n, then n raw lines `sensor minute flow`. "
                   "Complete `silver_and_gold`: first drop invalid readings (flow that is not a whole number, such as "
                   "NaN, or that is negative), then keep only the first remaining reading for each (sensor, minute). "
                   "The program prints `sensor readings mean` per sensor (mean to one decimal), sorted, then "
                   "`dropped_duplicates d dropped_invalid i`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_SILVER, stub(_SIG_SILVER, _DOC_SILVER, "[], 0, 0")),
        "solution": program(_IO_SILVER, _SIG_SILVER + f'''
    """{_DOC_SILVER}"""
    invalid = duplicates = 0
    first = {{}}
    for sensor, minute, flow in raw:
        if not flow.isdigit():               # NaN, '-3', '': not a valid non-negative whole number
            invalid += 1
        elif (sensor, minute) in first:
            duplicates += 1
        else:
            first[(sensor, minute)] = int(flow)
    totals = {{}}
    for (sensor, _), flow in first.items():
        count, total = totals.get(sensor, (0, 0))
        totals[sensor] = (count + 1, total + flow)
    gold = [(s, c, t / c) for s, (c, t) in sorted(totals.items())]
    return gold, duplicates, invalid
'''),
        "alt": _alt_silver,
        "explanation": ("Each layer has one job: silver validates and de-duplicates on the (sensor, minute) key, gold "
                        "aggregates per sensor. Counting what was dropped and why makes data quality visible instead of "
                        "silently shrinking the numbers. The raw bronze data stays untouched, so the rules can change "
                        "and be re-applied later."),
        "key_justification": "Validate, de-duplicate on a key, then aggregate (medallion layers).",
        "variants": variants(
            [({}, [("5\nS1 1 10\nS1 1 12\nS1 2 -5\nS1 3 20\nS2 1 NaN\n", "S1 2 15.0\ndropped_duplicates 1 dropped_invalid 2")]),
             ({}, [("3\nA 1 5\nB 1 6\nA 2 6\n", "A 2 5.5\nB 1 6.0\ndropped_duplicates 0 dropped_invalid 0")]),
             ({}, [("3\nZ 9 NaN\nZ 9 30\nZ 9 31\n", "Z 1 30.0\ndropped_duplicates 1 dropped_invalid 1")])],
            _gen_silver, 4310,
            extra_hidden=[["1\nQ 1 NaN\n"], ["2\nP 1 0\nP 1 0\n"], ["3\nb 1 1\na 1 2\na 2 4\n"]]),
    },
    {
        "prompt": ("Engineers want leak alerts within two minutes, but single spikes are noise, so a sensor alerts on a "
                   "sustained rise. The first line is `w threshold`, the second is n, then n readings `minute sensor "
                   "flow` in time order with sensors interleaved. Complete `leak_alerts`: a sensor alerts the first time "
                   "the mean of its last w readings is above the threshold (it needs w readings first). Keep a sliding "
                   "window per sensor. The program prints `sensor minute` for each sensor's first alert, ordered by "
                   "minute then sensor, or NONE."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_LEAK, stub(_SIG_LEAK, _DOC_LEAK, "[]")),
        "solution": "from collections import deque\n" + program(_IO_LEAK, _SIG_LEAK + f'''
    """{_DOC_LEAK}"""
    windows, totals, alerted = {{}}, {{}}, {{}}
    for minute, sensor, flow in readings:
        if sensor in alerted:
            continue
        q = windows.setdefault(sensor, deque())
        q.append(flow)
        totals[sensor] = totals.get(sensor, 0) + flow
        if len(q) > window:
            totals[sensor] -= q.popleft()
        if len(q) == window and totals[sensor] > threshold * window:   # mean > threshold, in integers
            alerted[sensor] = minute
    return sorted(alerted.items(), key=lambda kv: (kv[1], kv[0]))
'''),
        "alt": _alt_leak,
        "explanation": ("A deque and a running total per sensor give the mean of the last w readings in O(1) per reading, "
                        "which is what a streaming job needs. Comparing total > threshold x w avoids floating-point "
                        "means. Requiring a sustained rise filters one-off spikes."),
        "key_justification": "Per-key sliding windows over an interleaved stream.",
        "variants": variants(
            [({}, [("3 50\n5\n1 S1 40\n1 S2 100\n2 S1 60\n2 S2 10\n3 S1 70\n", "S1 3")]),
             ({}, [("2 30\n4\n1 A 31\n2 B 40\n3 A 30\n4 B 21\n", "A 3\nB 4")]),
             ({}, [("2 10\n3\n1 X 10\n2 X 10\n3 X 10\n", "NONE")])],
            _gen_leak, 4320,
            extra_hidden=[["1 0\n1\n5 Q 1\n"], ["3 5\n2\n1 A 100\n2 A 100\n"], ["2 9\n4\n1 B 10\n1 A 10\n2 B 8\n2 A 9\n"]]),
    },
]

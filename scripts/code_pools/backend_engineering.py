"""Code pool for Backend Engineering (bke-2 .. bke-5). Built and checked by scripts/build_code_pools.py."""
from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- bke-2 Tez Parcel
_IO_LIMIT = '''
def main():
    data = sys.stdin.read().split("\\n")
    limit, window = map(int, data[0].split())
    n = int(data[1])
    calls = []
    for i in range(n):
        seller, second = data[2 + i].split()
        calls.append((seller, int(second)))
    allowed, rejected, limited = rate_limit(calls, limit, window)
    print("allowed", allowed)
    print("rejected", rejected)
    print("limited", " ".join(limited) if limited else "NONE")


main()
'''
_SIG_LIMIT = "def rate_limit(calls, limit, window):"
_DOC_LIMIT = ("calls: list of (seller, second) in time order. Fixed windows: second // window. A seller may make at "
              "most `limit` calls per window. Return (allowed count, rejected count, sellers with any rejection "
              "sorted).")


def _alt_limit(stdin):
    rows = stdin.split("\n")
    limit, window = map(int, rows[0].split())
    n = int(rows[1])
    calls = [r.split() for r in rows[2:2 + n]]
    allowed = rejected = 0
    limited = set()
    accepted = []
    for seller, second in calls:
        w = int(second) // window
        used = len([1 for s, ww in accepted if s == seller and ww == w])
        if used < limit:
            accepted.append((seller, w))
            allowed += 1
        else:
            rejected += 1
            limited.add(seller)
    return f"allowed {allowed}\nrejected {rejected}\nlimited {' '.join(sorted(limited)) or 'NONE'}"


def _gen_limit(rng, size):
    n = {"small": 8, "medium": 30, "large": 80}[size]
    limit, window = rng.randint(1, 4), rng.choice([5, 10, 60])
    sellers = [f"s{i}" for i in range(1, {"small": 3, "medium": 5, "large": 9}[size])]
    seconds = sorted(rng.randint(0, window * 4) for _ in range(n))
    rows = [f"{rng.choice(sellers)} {s}" for s in seconds]
    return f"{limit} {window}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-2"] = [
    {
        "prompt": ("Tez Parcel's public API needs a per-seller rate limit so one seller's script cannot flood it. "
                   "Use fixed windows: a call at second t falls in window t // W, and a seller may make at most L "
                   "calls per window. The first line is `L W`, the second is n, then n lines `seller second` in time "
                   "order. Complete `rate_limit`; the program prints `allowed`, `rejected`, then `limited` followed "
                   "by the sellers who had any call rejected, sorted, or NONE."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_LIMIT, stub(_SIG_LIMIT, _DOC_LIMIT, "0, 0, []")),
        "solution": program(_IO_LIMIT, _SIG_LIMIT + f'''
    """{_DOC_LIMIT}"""
    used = {{}}
    allowed = rejected = 0
    limited = set()
    for seller, second in calls:
        key = (seller, second // window)
        if used.get(key, 0) < limit:
            used[key] = used.get(key, 0) + 1
            allowed += 1
        else:
            rejected += 1
            limited.add(seller)
    return allowed, rejected, sorted(limited)
'''),
        "alt": _alt_limit,
        "explanation": ("A counter per (seller, window) in a hash map is the whole algorithm; in production it is "
                        "an INCR on a Redis key that expires with the window, shared by every API server. Fixed "
                        "windows allow a burst at a window edge, which sliding windows or token buckets smooth out."),
        "key_justification": "Fixed-window rate limiting = a counter per (client, window).",
        "variants": variants(
            [({}, [("2 10\n5\ns1 0\ns1 3\ns1 9\ns2 9\ns1 10\n", "allowed 4\nrejected 1\nlimited s1")]),
             ({}, [("1 60\n4\ns2 0\ns1 0\ns2 59\ns1 61\n", "allowed 3\nrejected 1\nlimited s2")]),
             ({}, [("3 5\n3\ns9 1\ns9 2\ns9 3\n", "allowed 3\nrejected 0\nlimited NONE")])],
            _gen_limit, 910,
            extra_hidden=[["1 1\n2\ns1 0\ns1 0\n"], ["1 10\n2\ns10 5\ns2 5\n"], ["2 5\n4\ns1 4\ns1 4\ns1 5\ns1 9\n"]]),
    },
]

_IO_WORKERS = '''
def main():
    data = sys.stdin.read().split("\\n")
    workers, n = map(int, data[0].split())
    jobs = []
    for i in range(n):
        job_id, arrival, duration = data[1 + i].split()
        jobs.append((job_id, int(arrival), int(duration)))
    for job_id, finish in finish_times(jobs, workers):
        print(job_id, finish)


main()
'''
_SIG_WORKERS = "def finish_times(jobs, workers):"
_DOC_WORKERS = ("jobs: list of (job_id, arrival, duration) sorted by arrival. Each job starts at its arrival or when "
                "a worker next becomes free, whichever is later, in this order. Return (job_id, finish time) for "
                "every job, in the input order.")


def _alt_workers(stdin):
    rows = stdin.split("\n")
    workers, n = map(int, rows[0].split())
    free = [0] * workers
    out = []
    for row in rows[1:1 + n]:
        job, arrival, duration = row.split()
        i = free.index(min(free))
        start = max(int(arrival), free[i])
        free[i] = start + int(duration)
        out.append(f"{job} {free[i]}")
    return "\n".join(out)


def _gen_workers(rng, size):
    n = {"small": 6, "medium": 20, "large": 60}[size]
    workers = rng.randint(1, 4)
    arrivals = sorted(rng.randint(0, n * 3) for _ in range(n))
    rows = [f"j{i + 1} {a} {rng.choice([2, 5, 20, 20, 30])}" for i, a in enumerate(arrivals)]
    return f"{workers} {n}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-2"].append({
    "prompt": ("Invoice PDFs take seconds to generate, so Tez Parcel moves them to background workers. The first line "
               "is `workers n`, then n jobs `job_id arrival duration` sorted by arrival time. Jobs are taken in that "
               "order; each starts at its arrival time or as soon as any worker is free, whichever is later, and runs "
               "for its duration. Complete `finish_times` so it always knows which worker frees up first without "
               "scanning every worker. The program prints `job_id finish_time` for each job in input order."),
    "ds_topic": "heap", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_WORKERS, stub(_SIG_WORKERS, _DOC_WORKERS, "[]")),
    "solution": "import heapq\n" + program(_IO_WORKERS, _SIG_WORKERS + f'''
    """{_DOC_WORKERS}"""
    free_at = [0] * workers          # a min-heap of the times each worker becomes free
    out = []
    for job_id, arrival, duration in jobs:
        earliest = heapq.heappop(free_at)
        finish = max(arrival, earliest) + duration
        heapq.heappush(free_at, finish)
        out.append((job_id, finish))
    return out
'''),
    "alt": _alt_workers,
    "explanation": ("A min-heap of 'free at' times gives the worker that frees up first in O(log w); the job starts "
                    "at the later of its arrival and that time. This is how a job queue keeps the API fast: the "
                    "request returns at once and workers drain the queue at their own pace."),
    "key_justification": "A min-heap of worker free times schedules FIFO jobs.",
    "variants": variants(
        [({}, [("2 4\nj1 0 5\nj2 0 3\nj3 1 2\nj4 6 1\n", "j1 5\nj2 3\nj3 5\nj4 7")]),
         ({}, [("1 3\na 0 4\nb 1 1\nc 10 2\n", "a 4\nb 5\nc 12")]),
         ({}, [("3 3\nx 2 9\ny 2 1\nz 2 1\n", "x 11\ny 3\nz 3")])],
        _gen_workers, 920,
        extra_hidden=[["1 1\nsolo 5 5\n"], ["2 3\na 0 10\nb 0 10\nc 0 1\n"], ["4 2\np 0 1\nq 100 1\n"]]),
})

# ---------------------------------------------------------------- bke-3 Annadaan
_IO_CLAIM = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    claims = [tuple(data[1 + i].split()) for i in range(n)]
    winners, rejected = settle_claims(claims)
    for donation, volunteer in winners:
        print(donation, volunteer)
    print("rejected", rejected)


main()
'''
_SIG_CLAIM = "def settle_claims(claims):"
_DOC_CLAIM = ("claims: list of (volunteer, donation) in the order the database committed them. The first claim on a "
              "donation wins. Return ([(donation, winning volunteer)] sorted by donation id, number of rejected "
              "claims).")


def _alt_claim(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    claims = [r.split() for r in rows[1:1 + n]]
    donations = sorted({d for _, d in claims})
    lines = [f"{d} {next(v for v, dd in claims if dd == d)}" for d in donations]
    return "\n".join(lines + [f"rejected {n - len(donations)}"])


def _gen_claim(rng, size):
    n = {"small": 6, "medium": 25, "large": 70}[size]
    donations = [f"d{i}" for i in range(1, n // 2 + 2)]
    rows = [f"v{rng.randint(1, 12)} {rng.choice(donations)}" for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-3"] = [
    {
        "prompt": ("Two volunteers sometimes claim the same donation. The fix is to let the database decide: the first "
                   "committed claim wins and later ones are rejected (for example UPDATE ... WHERE claimed_by IS "
                   "NULL). Model the outcome. The first line is n, then n lines `volunteer donation` in commit order. "
                   "Complete `settle_claims`; the program prints `donation volunteer` for each claimed donation, "
                   "sorted by donation id in string order, then `rejected k`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python", "SQL"],
        "starter": program(_IO_CLAIM, stub(_SIG_CLAIM, _DOC_CLAIM, "[], 0")),
        "solution": program(_IO_CLAIM, _SIG_CLAIM + f'''
    """{_DOC_CLAIM}"""
    owner = {{}}
    rejected = 0
    for volunteer, donation in claims:
        if donation in owner:
            rejected += 1
        else:
            owner[donation] = volunteer
    return sorted(owner.items()), rejected
'''),
        "alt": _alt_claim,
        "explanation": ("'Check then set' in application code races; making the check and the set one atomic step "
                        "(a conditional UPDATE, or a unique constraint) means only the first commit succeeds. Here a "
                        "dictionary plays the database row: a donation is set once and later claims are rejected."),
        "key_justification": "First-writer-wins with an atomic conditional update.",
        "variants": variants(
            [({}, [("4\nv1 d2\nv2 d2\nv3 d1\nv1 d1\n", "d1 v3\nd2 v1\nrejected 2")]),
             ({}, [("2\nv5 d10\nv6 d9\n", "d10 v5\nd9 v6\nrejected 0")]),
             ({}, [("3\nv1 d1\nv1 d1\nv2 d1\n", "d1 v1\nrejected 2")])],
            _gen_claim, 930,
            extra_hidden=[["1\nv9 d9\n"], ["3\nv2 dx\nv3 dy\nv2 dx\n"], ["2\nv1 d1\nv2 d2\n"]]),
    },
]

_IO_POOLQ = '''
def main():
    data = sys.stdin.read().split("\\n")
    size, max_wait, n = map(int, data[0].split())
    requests = []
    for i in range(n):
        request_id, start, duration = data[1 + i].split()
        requests.append((request_id, int(start), int(duration)))
    lost = timed_out(requests, size, max_wait)
    print(" ".join(lost) if lost else "NONE")


main()
'''
_SIG_POOLQ = "def timed_out(requests, size, max_wait):"
_DOC_POOLQ = ("requests: list of (id, start, duration) sorted by start. A pool has `size` connections. Each request "
              "takes the connection that frees up first, at max(start, free time); if that means waiting more than "
              "max_wait it gives up (and uses no connection). Return the ids that gave up, in input order.")


def _alt_poolq(stdin):
    rows = stdin.split("\n")
    size, max_wait, n = map(int, rows[0].split())
    free = [0] * size
    lost = []
    for row in rows[1:1 + n]:
        rid, start, duration = row.split()
        i = min(range(size), key=lambda k: free[k])
        got = max(int(start), free[i])
        if got - int(start) > max_wait:
            lost.append(rid)
        else:
            free[i] = got + int(duration)
    return " ".join(lost) or "NONE"


def _gen_poolq(rng, size):
    n = {"small": 6, "medium": 25, "large": 60}[size]
    pool, wait = rng.randint(1, 4), rng.choice([0, 2, 5])
    starts = sorted(rng.randint(0, n * 2) for _ in range(n))
    rows = [f"r{i + 1} {s} {rng.choice([1, 2, 3, 8, 15])}" for i, s in enumerate(starts)]
    return f"{pool} {wait} {n}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-3"].append({
    "prompt": ("Under load, Annadaan's API threw 'connection pool exhausted' errors. Simulate the pool to see which "
               "requests give up. The first line is `size max_wait n`, then n requests `id start duration` sorted by "
               "start. Each request, in order, takes the connection that becomes free soonest, at max(start, that "
               "free time); if it would have to wait more than max_wait it times out and takes no connection. "
               "Complete `timed_out`; the program prints the ids that timed out, space-separated, or NONE."),
    "ds_topic": "heap", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_POOLQ, stub(_SIG_POOLQ, _DOC_POOLQ, "[]")),
    "solution": "import heapq\n" + program(_IO_POOLQ, _SIG_POOLQ + f'''
    """{_DOC_POOLQ}"""
    free_at = [0] * size             # min-heap of connection free times
    lost = []
    for request_id, start, duration in requests:
        got = max(start, free_at[0])
        if got - start > max_wait:
            lost.append(request_id)  # gives up without taking a connection
            continue
        heapq.heapreplace(free_at, got + duration)
    return lost
'''),
    "alt": _alt_poolq,
    "explanation": ("The pool is a min-heap of the times each connection frees up; the top of the heap is the next "
                    "free connection. A request that would wait longer than the timeout fails fast instead of piling "
                    "up. Long-held connections (slow queries, slow SMS calls inside a transaction) are what drain it."),
    "key_justification": "Model a resource pool as a min-heap of free times.",
    "variants": variants(
        [({}, [("1 2 3\nr1 0 5\nr2 1 2\nr3 5 1\n", "r2")]),
         ({}, [("2 0 3\na 0 3\nb 0 3\nc 1 1\n", "c")]),
         ({}, [("2 5 3\nx 0 4\ny 0 4\nz 2 1\n", "NONE")])],
        _gen_poolq, 940,
        extra_hidden=[["1 0 2\nr1 0 1\nr2 1 1\n"], ["1 0 3\nr1 0 9\nr2 1 1\nr3 2 1\n"], ["3 1 1\nonly 0 1\n"]]),
})

# ---------------------------------------------------------------- bke-4 Vyapar Setu
_IO_LAG = '''
def main():
    data = sys.stdin.read().split("\\n")
    lag = int(data[0])
    n = int(data[1])
    events = []
    for i in range(n):
        kind, t, key = data[2 + i].split()
        events.append((kind, int(t), key))
    for t, key, verdict in replica_reads(events, lag):
        print(t, key, verdict)


main()
'''
_SIG_LAG = "def replica_reads(events, lag):"
_DOC_LAG = ("events: list of ('WRITE' or 'READ', time, key) in order. Reads go to a replica that is `lag` seconds "
            "behind. A READ at time t of a key is 'STALE' if an earlier WRITE to that key happened at w with "
            "t - lag < w <= t, otherwise 'FRESH'. Return (t, key, verdict) for every read, in order.")


def _alt_lag(stdin):
    rows = stdin.split("\n")
    lag = int(rows[0])
    n = int(rows[1])
    events = [r.split() for r in rows[2:2 + n]]
    out = []
    for i, (kind, t, key) in enumerate(events):
        if kind != "READ":
            continue
        t = int(t)
        stale = any(k == "WRITE" and kk == key and t - lag < int(w) <= t for k, w, kk in events[:i])
        out.append(f"{t} {key} {'STALE' if stale else 'FRESH'}")
    return "\n".join(out)


def _gen_lag(rng, size):
    n = {"small": 8, "medium": 25, "large": 60}[size]
    lag = rng.randint(1, 5)
    keys = ["price", "stock", "title", "loom", "saree"]
    t, rows = 0, []
    for _ in range(n):
        t += rng.randint(0, 3)
        rows.append(f"{rng.choice(['WRITE', 'READ', 'READ'])} {t} {rng.choice(keys)}")
    if not any(r.startswith("READ") for r in rows):
        rows.append(f"READ {t} price")
    return f"{lag}\n{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-4"] = [
    {
        "prompt": ("Vyapar Setu sends reads to replicas that run a few seconds behind the primary, so a seller who "
                   "updates a price and reloads may see the old one. Find which reads would be stale. The first line "
                   "is the lag in seconds, the second is n, then n events in order: `WRITE t key` or `READ t key`. A "
                   "read at time t is STALE if an earlier write to the same key happened at time w with t - lag < w "
                   "<= t (the replica has not caught up), otherwise FRESH. Complete `replica_reads`; the program "
                   "prints `t key verdict` for each read, in order."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_LAG, stub(_SIG_LAG, _DOC_LAG, "[]")),
        "solution": program(_IO_LAG, _SIG_LAG + f'''
    """{_DOC_LAG}"""
    last_write = {{}}                 # key -> time of the latest write seen so far
    out = []
    for kind, t, key in events:
        if kind == "WRITE":
            last_write[key] = t
        else:
            w = last_write.get(key)
            out.append((t, key, "STALE" if w is not None and t - lag < w <= t else "FRESH"))
    return out
'''),
        "alt": _alt_lag,
        "explanation": ("Only the latest write to a key matters, so a dictionary from key to last write time answers "
                        "each read in O(1). Reads that land inside the lag window after a write are the ones to route "
                        "to the primary ('read your own writes') for a short time after a user's update."),
        "key_justification": "Track the last write per key; reads within the lag window are stale.",
        "variants": variants(
            [({}, [("3\n4\nWRITE 1 price\nREAD 2 price\nREAD 5 price\nREAD 5 stock\n",
                    "2 price STALE\n5 price FRESH\n5 stock FRESH")]),
             ({}, [("2\n4\nWRITE 10 loom\nREAD 10 loom\nWRITE 11 loom\nREAD 12 loom\n",
                    "10 loom STALE\n12 loom STALE")]),
             ({}, [("1\n3\nWRITE 0 saree\nREAD 1 saree\nREAD 0 title\n", "1 saree FRESH\n0 title FRESH")])],
            _gen_lag, 950,
            extra_hidden=[["0\n2\nWRITE 5 x\nREAD 5 x\n"], ["5\n1\nREAD 3 x\n"], ["2\n3\nWRITE 1 a\nWRITE 4 a\nREAD 4 a\n"]]),
    },
]

_IO_BREAKER = '''
def main():
    data = sys.stdin.read().split("\\n")
    failures, cooldown, n = map(int, data[0].split())
    calls = []
    for i in range(n):
        t, outcome = data[1 + i].split()
        calls.append((int(t), outcome))
    print(" ".join(breaker(calls, failures, cooldown)))


main()
'''
_SIG_BREAKER = "def breaker(calls, failures, cooldown):"
_DOC_BREAKER = ("calls: list of (time, 'ok' or 'fail') in time order; the outcome is what the call WOULD return. "
                "Closed: make the call; after `failures` failures in a row, open until time + cooldown. Open: answer "
                "'SKIP' until that time; the first call at or after it is a trial ('CALL'): ok closes the breaker, "
                "fail opens it again for another cooldown. Return 'CALL' or 'SKIP' for each call.")


def _alt_breaker(stdin):
    rows = stdin.split("\n")
    f, c, n = map(int, rows[0].split())
    state, streak, until, out = "closed", 0, 0, []
    for row in rows[1:1 + n]:
        t, outcome = row.split()
        t = int(t)
        if state == "open" and t < until:
            out.append("SKIP")
            continue
        out.append("CALL")
        if state == "open":
            if outcome == "ok":
                state, streak = "closed", 0
            else:
                until = t + c
            continue
        streak = 0 if outcome == "ok" else streak + 1
        if streak >= f:
            state, until, streak = "open", t + c, 0
    return " ".join(out)


def _gen_breaker(rng, size):
    n = {"small": 8, "medium": 25, "large": 60}[size]
    f, c = rng.randint(1, 4), rng.choice([3, 5, 10])
    t, rows = 0, []
    bad = False
    for _ in range(n):
        t += rng.randint(1, 3)
        if rng.random() < 0.15:
            bad = not bad
        rows.append(f"{t} {'fail' if (bad and rng.random() < 0.9) or rng.random() < 0.1 else 'ok'}")
    return f"{f} {c} {n}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-4"].append({
    "prompt": ("Vyapar Setu's order service calls the inventory service, and when inventory hangs, orders hang too. A "
               "circuit breaker fails fast instead. The first line is `F C n`, then n calls `time outcome` (ok or "
               "fail: what the call would return). Closed: make the call; after F failures in a row the breaker "
               "opens until time + C. Open: answer SKIP for calls before that time; the first call at or after it is "
               "a trial CALL: ok closes the breaker, fail opens it again for another C seconds. Complete `breaker`; "
               "the program prints CALL or SKIP for each call, space-separated."),
    "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_BREAKER, stub(_SIG_BREAKER, _DOC_BREAKER, '["CALL"] * len(calls)')),
    "solution": program(_IO_BREAKER, _SIG_BREAKER + f'''
    """{_DOC_BREAKER}"""
    out = []
    in_a_row, open_until, is_open = 0, 0, False
    for t, outcome in calls:
        if is_open and t < open_until:
            out.append("SKIP")
            continue
        out.append("CALL")
        if is_open:                          # half-open trial call
            if outcome == "ok":
                is_open, in_a_row = False, 0
            else:
                open_until = t + cooldown
            continue
        in_a_row = 0 if outcome == "ok" else in_a_row + 1
        if in_a_row >= failures:
            is_open, open_until, in_a_row = True, t + cooldown, 0
    return out
'''),
    "alt": _alt_breaker,
    "explanation": ("The breaker is a small state machine (closed, open, half-open) walked over the calls in order. "
                    "Skipping calls while open protects the caller's threads and gives the failing service time to "
                    "recover; one trial call decides whether to close again."),
    "key_justification": "Circuit breaker: closed, open, half-open states driven by failures.",
    "variants": variants(
        [({}, [("2 10 6\n1 fail\n2 fail\n5 ok\n12 fail\n13 ok\n14 ok\n", "CALL CALL SKIP CALL SKIP SKIP")]),
         ({}, [("1 3 4\n1 fail\n2 ok\n4 ok\n5 ok\n", "CALL SKIP CALL CALL")]),
         ({}, [("3 5 4\n1 fail\n2 ok\n3 fail\n4 fail\n", "CALL CALL CALL CALL")])],
        _gen_breaker, 960,
        extra_hidden=[["1 1 2\n1 fail\n2 fail\n"], ["2 4 5\n1 fail\n2 fail\n3 ok\n6 ok\n7 fail\n"], ["5 5 1\n1 ok\n"]]),
})

# ---------------------------------------------------------------- bke-5 Shiksha Sopan
_IO_PCT = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    latencies = list(map(int, data[1].split()))
    p50, p95 = percentiles(latencies)
    print("p50", p50)
    print("p95", p95)


main()
'''
_SIG_PCT = "def percentiles(latencies):"
_DOC_PCT = ("latencies: request times in ms. Return (p50, p95) by the nearest-rank method: sort, then the value at "
            "rank ceil(p / 100 x n), counting ranks from 1.")


def _alt_pct(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    vals = sorted(int(x) for x in rows[1].split())

    def nearest(p):
        rank = 1
        while rank * 100 < p * n:
            rank += 1
        return vals[rank - 1]
    return f"p50 {nearest(50)}\np95 {nearest(95)}"


def _gen_pct(rng, size):
    n = {"small": 10, "medium": 40, "large": 150}[size]
    vals = [rng.randint(40, 180) if rng.random() < 0.9 else rng.randint(400, 3000) for _ in range(n)]
    return f"{n}\n" + " ".join(map(str, vals)) + "\n"


PROBLEMS["bke-5"] = [
    {
        "prompt": ("Last year the portal 'looked fine on average' while students waited minutes. Averages hide the "
                   "slow tail; percentiles show it. The first line is n, the second has n request latencies in ms. "
                   "Complete `percentiles` using the nearest-rank method: sort the values and take the one at rank "
                   "ceil(p / 100 x n), counting from 1. The program prints `p50` and `p95`."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_PCT, stub(_SIG_PCT, _DOC_PCT, "0, 0")),
        "solution": program(_IO_PCT, _SIG_PCT + f'''
    """{_DOC_PCT}"""
    ordered = sorted(latencies)
    n = len(ordered)

    def nearest_rank(p):
        rank = -(-p * n // 100)       # ceil(p * n / 100) in integers
        return ordered[max(rank, 1) - 1]
    return nearest_rank(50), nearest_rank(95)
'''),
        "alt": _alt_pct,
        "explanation": ("Sorting once makes any percentile a lookup by rank. Integer ceiling division avoids a "
                        "floating-point rank like 9.000001. The p95 reflects what the slowest 1 in 20 students "
                        "experience, which is what an alert on deadline day should watch."),
        "key_justification": "Nearest-rank percentile from a sorted list.",
        "variants": variants(
            [({}, [("10\n12 15 11 40 13 14 300 16 18 17\n", "p50 15\np95 300")]),
             ({}, [("4\n100 200 300 400\n", "p50 200\np95 400")]),
             ({}, [("1\n77\n", "p50 77\np95 77")])],
            _gen_pct, 1010,
            extra_hidden=[["2\n5 5\n"], ["20\n" + " ".join(str(i) for i in range(20, 0, -1)) + "\n"], ["3\n9 1 5\n"]]),
    },
]

_IO_MERIT = '''
def main():
    data = sys.stdin.read().split("\\n")
    seats, n = map(int, data[0].split())
    applicants = []
    for i in range(n):
        applicant, marks, income = data[1 + i].split()
        applicants.append((applicant, int(marks), int(income)))
    chosen = merit_list(applicants, seats)
    print("\\n".join(chosen) if chosen else "NONE")


main()
'''
_SIG_MERIT = "def merit_list(applicants, seats):"
_DOC_MERIT = ("applicants: list of (id, marks, family income). Return the ids of the `seats` best applicants: higher "
              "marks first, then lower income, then id in string order.")


def _alt_merit(stdin):
    rows = stdin.split("\n")
    seats, n = map(int, rows[0].split())
    apps = [r.split() for r in rows[1:1 + n]]
    apps.sort(key=lambda a: a[0])
    apps.sort(key=lambda a: int(a[2]))
    apps.sort(key=lambda a: int(a[1]), reverse=True)
    return "\n".join(a[0] for a in apps[:seats]) or "NONE"


def _gen_merit(rng, size):
    n = {"small": 8, "medium": 40, "large": 90}[size]
    seats = rng.randint(1, max(2, n // 5))
    ids = rng.sample(range(10000, 99999), n)
    rows = [f"S{i} {rng.randint(70, 100)} {rng.choice([50000, 80000, 120000, 200000])}" for i in ids]
    return f"{seats} {n}\n" + "\n".join(rows) + "\n"


PROBLEMS["bke-5"].append({
    "prompt": ("Each night the portal builds a merit list for a fixed number of scholarships from 2 million "
               "applications, and only the top few hundred matter. The first line is `seats n`, then n lines `id marks "
               "income`. Complete `merit_list` so it picks the best `seats` applicants without sorting all n: higher "
               "marks first, then lower family income, then id in string order. The program prints the chosen ids "
               "in rank order, one per line, or NONE."),
    "ds_topic": "heap", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_MERIT, stub(_SIG_MERIT, _DOC_MERIT, "[]")),
    "solution": "import heapq\n" + program(_IO_MERIT, _SIG_MERIT + f'''
    """{_DOC_MERIT}"""
    best = heapq.nsmallest(seats, applicants, key=lambda a: (-a[1], a[2], a[0]))
    return [applicant for applicant, _, _ in best]
'''),
    "alt": _alt_merit,
    "explanation": ("heapq.nsmallest keeps only `seats` candidates in a heap while scanning, O(n log k) instead of "
                    "sorting all n in O(n log n). The key encodes the published rules in order, so the list is "
                    "deterministic and can be explained to any student who asks."),
    "key_justification": "Top-k with a heap and a rule-ordered composite key.",
    "variants": variants(
        [({}, [("2 4\nA1 90 300000\nA2 95 500000\nA3 90 100000\nA4 80 50000\n", "A2\nA3")]),
         ({}, [("3 3\nB2 70 100\nB1 70 100\nB3 71 900\n", "B3\nB1\nB2")]),
         ({}, [("1 2\nC9 88 5\nC1 88 6\n", "C9")])],
        _gen_merit, 1020,
        extra_hidden=[["3 0\n"], ["5 2\nD1 50 1\nD2 60 1\n"], ["2 3\nE1 99 1\nE2 99 1\nE3 99 1\n"]]),
})

"""Code pool for Full-Stack Development (fsd-2 .. fsd-5). Built and checked by scripts/build_code_pools.py."""
from collections import Counter, OrderedDict

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- fsd-2 ShikshaSetu
_IO_DOUBLE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    bookings = [tuple(data[1 + i].split()) for i in range(n)]
    clashes = double_booked(bookings)
    print("\\n".join(clashes) if clashes else "NONE")


main()
'''
_SIG_DOUBLE = "def double_booked(bookings):"
_DOC_DOUBLE = "bookings: list of (tutor_id, slot). Return the tutor ids with a slot booked more than once, sorted."


def _alt_double(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    seen, clash = [], []
    for row in rows[1:1 + n]:
        if row in seen and row.split()[0] not in clash:
            clash.append(row.split()[0])
        seen.append(row)
    return "\n".join(sorted(clash)) or "NONE"


def _gen_double(rng, size):
    n = {"small": 6, "medium": 20, "large": 60}[size]
    tutors = [f"T{i}" for i in range(1, 13)]
    slots = [f"{d}-{h}" for d in ("MON", "TUE", "WED", "THU", "FRI", "SAT") for h in (16, 17, 18, 19)]
    rows = [f"{rng.choice(tutors)} {rng.choice(slots)}" for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["fsd-2"] = [
    {
        "prompt": ("During {season}, ShikshaSetu's booking table has started showing double bookings. The first line of "
                   "input is n, the number of bookings. Each of the next n lines is `tutor_id slot`, for example "
                   "`T7 MON-17`. Complete `double_booked` so the program prints every tutor id that has the same slot "
                   "booked more than once, in alphabetical (string) order, one per line, each tutor once. If no tutor "
                   "is double-booked, it prints NONE."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_DOUBLE, stub(_SIG_DOUBLE, _DOC_DOUBLE, "[]")),
        "solution": program(_IO_DOUBLE, _SIG_DOUBLE + f'''
    """{_DOC_DOUBLE}"""
    counts = {{}}
    for tutor, slot in bookings:
        counts[(tutor, slot)] = counts.get((tutor, slot), 0) + 1
    return sorted({{tutor for (tutor, slot), n in counts.items() if n > 1}})
'''),
        "alt": _alt_double,
        "explanation": ("Count each (tutor, slot) pair in a dictionary keyed by the pair; any pair seen more than once "
                        "is a double booking. A set removes repeats of the same tutor before sorting. One pass over the "
                        "bookings is O(n), where comparing every booking with every other would be O(n^2)."),
        "key_justification": "A hash map keyed by (tutor, slot) finds duplicates in one pass.",
        "variants": variants(
            [({"season": "exam week"},
              [("5\nT1 MON-17\nT2 MON-17\nT1 MON-17\nT3 TUE-18\nT2 WED-16\n", "T1")]),
             ({"season": "the summer holidays"},
              [("6\nT4 SAT-16\nT9 SAT-16\nT4 SAT-16\nT9 SAT-16\nT9 FRI-18\nT2 FRI-18\n", "T4\nT9")]),
             ({"season": "board-exam month"},
              [("4\nT10 TUE-17\nT2 TUE-17\nT10 TUE-17\nT10 TUE-17\n", "T10")])],
            _gen_double, 210,
            extra_hidden=[["3\nT1 MON-16\nT2 MON-16\nT1 TUE-16\n"], ["1\nT5 WED-19\n"],
                          ["2\nT3 THU-18\nT3 THU-19\n"]]),
    },
]

_IO_TOP = '''
def main():
    data = sys.stdin.read().split("\\n")
    k, m = map(int, data[0].split())
    n = int(data[1])
    reviews = []
    for i in range(n):
        tutor, rating = data[2 + i].split()
        reviews.append((tutor, int(rating)))
    ranked = top_tutors(reviews, k, m)
    if not ranked:
        print("NONE")
    for tutor, average in ranked:
        print(tutor, format(average, ".2f"))


main()
'''
_SIG_TOP = "def top_tutors(reviews, k, m):"
_DOC_TOP = ("reviews: list of (tutor_id, rating). Return up to k (tutor_id, average) pairs for tutors with at least m "
            "reviews, by average high to low, then more reviews first, then tutor id A to Z.")


def _alt_top(stdin):
    rows = stdin.split("\n")
    k, m = map(int, rows[0].split())
    n = int(rows[1])
    tutors = {}
    for row in rows[2:2 + n]:
        t, r = row.split()
        tutors.setdefault(t, []).append(int(r))
    eligible = [(t, rs) for t, rs in tutors.items() if len(rs) >= m]
    eligible.sort(key=lambda x: x[0])
    eligible.sort(key=lambda x: len(x[1]), reverse=True)
    eligible.sort(key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
    out = [f"{t} {format(sum(rs) / len(rs), '.2f')}" for t, rs in eligible[:k]]
    return "\n".join(out) or "NONE"


def _gen_top(rng, size):
    n = {"small": 8, "medium": 30, "large": 80}[size]
    k, m = rng.randint(2, 4), rng.randint(1, 3)
    tutors = [f"T{i}" for i in range(1, {"small": 5, "medium": 9, "large": 14}[size])]
    rows = [f"{rng.choice(tutors)} {rng.randint(1, 5)}" for _ in range(n)]
    return f"{k} {m}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["fsd-2"].append({
    "prompt": ("ShikshaSetu wants a 'top tutors' list for {subject}. The first line is `k m`: show at most k tutors, and "
               "only tutors with at least m reviews. The second line is n, then n lines `tutor_id rating` with ratings "
               "from 1 to 5. Complete `top_tutors`. Order tutors by average rating, highest first; break ties by the "
               "number of reviews (more first), then by tutor id in string order. The program prints `tutor_id "
               "average` with the average to two decimals, or NONE if no tutor qualifies."),
    "ds_topic": "sorting", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_TOP, stub(_SIG_TOP, _DOC_TOP, "[]")),
    "solution": program(_IO_TOP, _SIG_TOP + f'''
    """{_DOC_TOP}"""
    totals, counts = {{}}, {{}}
    for tutor, rating in reviews:
        totals[tutor] = totals.get(tutor, 0) + rating
        counts[tutor] = counts.get(tutor, 0) + 1
    rows = [(tutor, totals[tutor] / counts[tutor], counts[tutor]) for tutor in totals if counts[tutor] >= m]
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return [(tutor, average) for tutor, average, _ in rows[:k]]
'''),
    "alt": _alt_top,
    "explanation": ("Accumulate a total and a count per tutor in dictionaries (the SQL equivalent is GROUP BY tutor "
                    "with HAVING COUNT(*) >= m), then sort once with a composite key: negative average, negative "
                    "count, then id. Sorting on the exact average, not the rounded one, keeps the order honest."),
    "key_justification": "Group-by aggregation followed by a multi-key sort.",
    "variants": variants(
        [({"subject": "physics"}, [("2 2\n6\nT1 5\nT2 4\nT1 3\nT3 5\nT2 5\nT2 3\n", "T2 4.00\nT1 4.00")]),
         ({"subject": "maths"}, [("3 1\n4\nT5 4\nT6 5\nT5 5\nT7 2\n", "T6 5.00\nT5 4.50\nT7 2.00")]),
         ({"subject": "chemistry"}, [("1 3\n5\nT8 5\nT8 4\nT9 5\nT9 5\nT8 3\n", "T8 4.00")])],
        _gen_top, 220,
        extra_hidden=[["2 3\n3\nT1 5\nT2 5\nT1 4\n"], ["5 1\n2\nT4 3\nT3 3\n"], ["2 1\n3\nT2 1\nT1 1\nT3 2\n"]]),
})

# ---------------------------------------------------------------- fsd-3 MandiMitra
_IO_LATEST = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    events = [data[1 + i].split() for i in range(n)]
    payload, ignored = shown_after(events)
    print(payload if payload is not None else "NONE")
    print("ignored", ignored)


main()
'''
_SIG_LATEST = "def shown_after(events):"
_DOC_LATEST = ("events: lists like ['REQ', '3'] or ['RES', '3', 'onion=31']. Return (payload on screen at the end or "
               "None, number of responses ignored as stale).")


def _alt_latest(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    responses = [r.split() for r in rows[1:1 + n] if r.startswith("RES")]
    shown, ignored, newest = None, 0, -1
    for _, rid, payload in responses:
        if int(rid) > newest:
            newest, shown = int(rid), payload
        else:
            ignored += 1
    return f"{shown if shown is not None else 'NONE'}\nignored {ignored}"


def _gen_latest(rng, size):
    count = {"small": 4, "medium": 10, "large": 25}[size]
    crops = ["onion", "tomato", "potato", "chilli", "brinjal"]
    events, pending = [], []
    for rid in range(1, count + 1):
        events.append(f"REQ {rid}")
        pending.append(rid)
        while pending and rng.random() < 0.45:
            r = pending.pop(rng.randrange(len(pending)))
            events.append(f"RES {r} {rng.choice(crops)}={rng.randint(10, 90)}")
    rng.shuffle(pending)
    for r in pending:
        if rng.random() < 0.8:
            events.append(f"RES {r} {rng.choice(crops)}={rng.randint(10, 90)}")
    return f"{len(events)}\n" + "\n".join(events) + "\n"


PROBLEMS["fsd-3"] = [
    {
        "prompt": ("MandiMitra's search box sends a request on every keystroke, and responses can come back out of "
                   "order. The first line is n, then n events in arrival order: `REQ id` when a request is sent (ids "
                   "rise by one each time) and `RES id payload` when its response arrives. The screen should show a "
                   "response only if its id is newer than the response already on screen, so a slow, older response "
                   "never replaces a newer one. Complete `shown_after`. The program prints the payload on screen at "
                   "the end (NONE if nothing was shown), then `ignored k`, the number of stale responses ignored."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_LATEST, stub(_SIG_LATEST, _DOC_LATEST, "None, 0")),
        "solution": program(_IO_LATEST, _SIG_LATEST + f'''
    """{_DOC_LATEST}"""
    shown_id, payload, ignored = 0, None, 0
    for event in events:
        if event[0] != "RES":
            continue
        rid = int(event[1])
        if rid > shown_id:
            shown_id, payload = rid, event[2]
        else:
            ignored += 1
    return payload, ignored
'''),
        "alt": _alt_latest,
        "explanation": ("Remember the id of the response currently on screen and accept a response only when its id "
                        "is larger. This is the same fix as ignoring stale fetches in a React effect: compare against "
                        "the latest request instead of trusting arrival order."),
        "key_justification": "Arrival order is not request order; keep the newest id seen.",
        "variants": variants(
            [({}, [("5\nREQ 1\nREQ 2\nRES 2 tomato=40\nRES 1 tomato=38\nREQ 3\n", "tomato=40\nignored 1")]),
             ({}, [("6\nREQ 1\nRES 1 onion=30\nREQ 2\nREQ 3\nRES 3 onion=33\nRES 2 onion=31\n",
                    "onion=33\nignored 1")]),
             ({}, [("4\nREQ 1\nREQ 2\nRES 1 potato=22\nRES 2 potato=24\n", "potato=24\nignored 0")])],
            _gen_latest, 230,
            extra_hidden=[["2\nREQ 1\nREQ 2\n"], ["3\nREQ 1\nREQ 2\nRES 2 chilli=80\n"],
                          ["5\nREQ 1\nREQ 2\nREQ 3\nRES 3 onion=5\nRES 1 onion=9\n"]]),
    },
]

_IO_CHEAP = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = []
    for i in range(n):
        market, crop, price = data[1 + i].split()
        rows.append((market, crop, int(price)))
    q = int(data[1 + n])
    markets = [data[2 + n + i].strip() for i in range(q)]
    for market, answer in cheapest_per_market(rows, markets):
        print(market, answer if answer else "NONE")


main()
'''
_SIG_CHEAP = "def cheapest_per_market(rows, markets):"
_DOC_CHEAP = ("rows: list of (market, crop, price). For each market in `markets`, in that order, return (market, "
              "'crop price') for its cheapest crop (ties: crop name A to Z), or (market, None) if it has no rows.")


def _alt_cheap(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    data = [r.split() for r in rows[1:1 + n]]
    q = int(rows[1 + n])
    out = []
    for market in rows[2 + n:2 + n + q]:
        market = market.strip()
        mine = [(int(p), c) for mk, c, p in data if mk == market]
        if mine:
            price, crop = min(mine)
            out.append(f"{market} {crop} {price}")
        else:
            out.append(f"{market} NONE")
    return "\n".join(out)


def _gen_cheap(rng, size):
    n = {"small": 6, "medium": 25, "large": 60}[size]
    markets = ["Saranpur", "Kheda", "Dholpur", "Amli", "Rewa", "Sonpur", "Tarna"]
    crops = ["onion", "tomato", "potato", "garlic", "okra", "peas"]
    rows = [f"{rng.choice(markets[:5])} {rng.choice(crops)} {rng.randint(15, 60)}" for _ in range(n)]
    asked = rng.sample(markets, 4)
    return f"{n}\n" + "\n".join(rows) + f"\n{len(asked)}\n" + "\n".join(asked) + "\n"


PROBLEMS["fsd-3"].append({
    "prompt": ("The prices page was making one database query per market (an N+1 pattern). The fix loads every price "
               "row once and groups it in code. The first line is n, then n rows `market crop price`; then q, then q "
               "market names. Complete `cheapest_per_market` without looping over all rows once per market. For each "
               "asked market, in the order asked, the program prints `market crop price` for its cheapest crop "
               "(ties broken by crop name in string order), or `market NONE` if it has no rows."),
    "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_CHEAP, stub(_SIG_CHEAP, _DOC_CHEAP, "[]")),
    "solution": program(_IO_CHEAP, _SIG_CHEAP + f'''
    """{_DOC_CHEAP}"""
    best = {{}}
    for market, crop, price in rows:
        if market not in best or (price, crop) < best[market]:
            best[market] = (price, crop)
    out = []
    for market in markets:
        if market in best:
            price, crop = best[market]
            out.append((market, f"{{crop}} {{price}}"))
        else:
            out.append((market, None))
    return out
'''),
    "alt": _alt_cheap,
    "explanation": ("One pass builds a dictionary from market to its best (price, crop) pair, and each question is "
                    "then a constant-time lookup. Comparing (price, crop) tuples gives the cheapest crop with ties "
                    "broken alphabetically for free. This is what replacing N+1 queries with one grouped query does."),
    "key_justification": "Group once into a hash map, then answer each lookup in O(1).",
    "variants": variants(
        [({}, [("4\nSaranpur onion 30\nSaranpur tomato 25\nKheda tomato 28\nSaranpur potato 25\n2\nSaranpur\n"
                "Dholpur\n", "Saranpur potato 25\nDholpur NONE")]),
         ({}, [("3\nKheda okra 40\nKheda garlic 40\nAmli peas 18\n2\nAmli\nKheda\n",
                "Amli peas 18\nKheda garlic 40")]),
         ({}, [("2\nRewa onion 22\nRewa onion 20\n1\nRewa\n", "Rewa onion 20")])],
        _gen_cheap, 240,
        extra_hidden=[["1\nAmli onion 10\n2\nKheda\nRewa\n"], ["2\nSonpur peas 31\nSonpur okra 31\n1\nSonpur\n"],
                      ["3\nTarna onion 50\nTarna onion 49\nTarna garlic 49\n1\nTarna\n"]]),
})

# ---------------------------------------------------------------- fsd-4 Yatrika
_IO_IDEMP = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    requests = []
    for i in range(n):
        key, amount = data[1 + i].split()
        requests.append((key, int(amount)))
    charged, duplicates = charge_once(requests)
    print("charged", charged)
    print("duplicates", duplicates)


main()
'''
_SIG_IDEMP = "def charge_once(requests):"
_DOC_IDEMP = ("requests: list of (idempotency_key, amount) in arrival order. Charge each key only the first time it "
              "is seen. Return (total charged, number of repeated requests ignored).")


def _alt_idemp(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    items = [r.split() for r in rows[1:1 + n]]
    keys = [k for k, _ in items]
    total = sum(int(a) for i, (k, a) in enumerate(items) if k not in keys[:i])
    return f"charged {total}\nduplicates {n - len(set(keys))}"


def _gen_idemp(rng, size):
    n = {"small": 6, "medium": 25, "large": 70}[size]
    keys = []
    rows = []
    for _ in range(n):
        if keys and rng.random() < 0.35:
            key = rng.choice(keys)
            amount = next(a for k, a in rows if k == key)
        else:
            key = f"bk{rng.randint(1000, 9999)}"
            amount = rng.choice([350, 420, 499, 650, 800, 1200])
            keys.append(key)
        rows.append((key, amount))
    return f"{n}\n" + "\n".join(f"{k} {a}" for k, a in rows) + "\n"


PROBLEMS["fsd-4"] = [
    {
        "prompt": ("In the Diwali rush, Yatrika's payment page is retried by impatient users, so the same booking can "
                   "reach the server several times with the same idempotency key. The first line is n, then n lines "
                   "`key amount` in arrival order. Complete `charge_once` so each key is charged only the first time "
                   "it arrives. The program prints `charged T` (the total actually charged in rupees) and "
                   "`duplicates D` (how many repeated requests were ignored)."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_IDEMP, stub(_SIG_IDEMP, _DOC_IDEMP, "0, 0")),
        "solution": program(_IO_IDEMP, _SIG_IDEMP + f'''
    """{_DOC_IDEMP}"""
    seen = set()
    charged = duplicates = 0
    for key, amount in requests:
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
            charged += amount
    return charged, duplicates
'''),
        "alt": _alt_idemp,
        "explanation": ("Keep the keys already processed in a set; membership checks are O(1), so each retry is "
                        "recognised immediately and charged nothing. A real server stores the key with the first "
                        "response so a retry gets the same answer back."),
        "key_justification": "A set of processed idempotency keys makes retries safe.",
        "variants": variants(
            [({}, [("4\nk1 450\nk2 300\nk1 450\nk3 120\n", "charged 870\nduplicates 1")]),
             ({}, [("5\nbk7 499\nbk7 499\nbk7 499\nbk8 650\nbk8 650\n", "charged 1149\nduplicates 3")]),
             ({}, [("3\nx 100\ny 200\nz 300\n", "charged 600\nduplicates 0")])],
            _gen_idemp, 250,
            extra_hidden=[["1\nsolo 999\n"], ["2\na 10\na 10\n"], ["4\nq 5\nr 6\nq 5\nr 6\n"]]),
    },
]

_IO_LRU = '''
def main():
    data = sys.stdin.read().split("\\n")
    capacity, _ = map(int, data[0].split())
    lookups = data[1].split()
    hits, misses, cache = simulate_lru(capacity, lookups)
    print("hits", hits)
    print("misses", misses)
    print("cache", " ".join(cache) if cache else "EMPTY")


main()
'''
_SIG_LRU = "def simulate_lru(capacity, lookups):"
_DOC_LRU = ("Simulate a least-recently-used cache of the given capacity over the route lookups. Return (hits, misses, "
            "cache contents from most to least recently used).")


def _alt_lru(stdin):
    rows = stdin.split("\n")
    capacity = int(rows[0].split()[0])
    cache, hits, misses = OrderedDict(), 0, 0
    for route in rows[1].split():
        if route in cache:
            hits += 1
            cache.move_to_end(route)
        else:
            misses += 1
            cache[route] = True
            if len(cache) > capacity:
                cache.popitem(last=False)
    order = list(reversed(cache))
    return f"hits {hits}\nmisses {misses}\ncache {' '.join(order) if order else 'EMPTY'}"


def _gen_lru(rng, size):
    n = {"small": 8, "medium": 30, "large": 90}[size]
    capacity = rng.randint(2, 5)
    routes = [f"R{i}" for i in range(1, {"small": 5, "medium": 9, "large": 14}[size])]
    lookups = [rng.choice(routes[: max(2, len(routes) // 2)]) if rng.random() < 0.6 else rng.choice(routes)
               for _ in range(n)]
    return f"{capacity} {n}\n" + " ".join(lookups) + "\n"


PROBLEMS["fsd-4"].append({
    "prompt": ("Yatrika caches seat maps for its busiest routes in memory, holding at most c routes and throwing out "
               "the least recently used one when full. The first line is `c n`; the second line has n route ids "
               "separated by spaces, in lookup order. Complete `simulate_lru`. A lookup is a hit if the route is "
               "cached (it becomes the most recently used); otherwise it is a miss and the route is added, evicting "
               "the least recently used route if the cache would exceed c. The program prints `hits`, `misses`, then "
               "`cache` followed by the cached routes from most to least recently used."),
    "ds_topic": "linked_list", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_LRU, stub(_SIG_LRU, _DOC_LRU, "0, 0, []")),
    "solution": program(_IO_LRU, _SIG_LRU + f'''
    """{_DOC_LRU}"""
    order = []          # most recently used last
    hits = misses = 0
    for route in lookups:
        if route in order:
            hits += 1
            order.remove(route)
        else:
            misses += 1
            if len(order) == capacity:
                order.pop(0)
        order.append(route)
    return hits, misses, list(reversed(order))
'''),
    "alt": _alt_lru,
    "explanation": ("An LRU cache needs two things: a fast 'is it cached?' check and an order of recent use. A list "
                    "works for small caches; the real structure is a hash map pointing into a doubly linked list "
                    "(Python's OrderedDict), which makes both the lookup and the move-to-front O(1)."),
    "key_justification": "LRU = hash map for lookup + linked list for recency order.",
    "variants": variants(
        [({}, [("2 5\nA B A C B\n", "hits 1\nmisses 4\ncache B C")]),
         ({}, [("3 6\nR1 R2 R3 R1 R4 R2\n", "hits 1\nmisses 5\ncache R2 R4 R1")]),
         ({}, [("1 4\nX X Y X\n", "hits 1\nmisses 3\ncache X")])],
        _gen_lru, 260,
        extra_hidden=[["3 3\nR1 R1 R1\n"], ["2 4\nR1 R2 R1 R2\n"], ["4 5\nA B C D E\n"]]),
})

# ---------------------------------------------------------------- fsd-5 Kirana Khata
_IO_KHATA = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    actions = [data[1 + i].split() for i in range(n)]
    balances = replay(actions)
    if not balances:
        print("ALL CLEAR")
    for name, amount in balances:
        print(name, amount)


main()
'''
_SIG_KHATA = "def replay(actions):"
_DOC_KHATA = ("actions: ['ADD', name, amount], ['PAY', name, amount] or ['UNDO'], in the order they were made offline. "
              "UNDO cancels the most recent action not already undone (and does nothing if there is none). Return "
              "(name, balance) for every customer whose balance is not zero, sorted by name.")


def _alt_khata(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    kept = []
    for row in rows[1:1 + n]:
        parts = row.split()
        if parts[0] == "UNDO":
            if kept:
                kept = kept[:-1]
        else:
            kept = kept + [parts]
    names = sorted({p[1] for p in kept})
    out = []
    for name in names:
        bal = sum(int(p[2]) if p[0] == "ADD" else -int(p[2]) for p in kept if p[1] == name)
        if bal != 0:
            out.append(f"{name} {bal}")
    return "\n".join(out) or "ALL CLEAR"


def _gen_khata(rng, size):
    n = {"small": 7, "medium": 25, "large": 60}[size]
    names = ["Ravi", "Meena", "Asif", "Gita", "Joseph", "Lata", "Kiran"]
    rows = []
    for _ in range(n):
        r = rng.random()
        if r < 0.15:
            rows.append("UNDO")
        elif r < 0.6:
            rows.append(f"ADD {rng.choice(names)} {rng.choice([50, 80, 120, 200, 350])}")
        else:
            rows.append(f"PAY {rng.choice(names)} {rng.choice([50, 80, 100, 200])}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["fsd-5"] = [
    {
        "prompt": ("Kirana Khata works offline: a shopkeeper's actions are queued on the phone and replayed in order "
                   "when the network returns. The first line is n, then n actions: `ADD name amount` (credit given), "
                   "`PAY name amount` (money received) or `UNDO` (cancel the most recent action that has not already "
                   "been undone; ignore it if there is none). Complete `replay`. The program prints `name balance` "
                   "for every customer whose balance (credit minus payments) is not zero, sorted by name, or "
                   "ALL CLEAR if every balance is zero."),
        "ds_topic": "stack", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_KHATA, stub(_SIG_KHATA, _DOC_KHATA, "[]")),
        "solution": program(_IO_KHATA, _SIG_KHATA + f'''
    """{_DOC_KHATA}"""
    done = []                       # a stack of applied actions
    for action in actions:
        if action[0] == "UNDO":
            if done:
                done.pop()
        else:
            done.append(action)
    balances = {{}}
    for kind, name, amount in done:
        change = int(amount) if kind == "ADD" else -int(amount)
        balances[name] = balances.get(name, 0) + change
    return [(name, balances[name]) for name in sorted(balances) if balances[name] != 0]
'''),
        "alt": _alt_khata,
        "explanation": ("Undo always cancels the most recent surviving action, which is exactly a stack: push each "
                        "action, pop on UNDO. Replaying the stack afterwards into a dictionary of balances gives each "
                        "customer's total. Order matters, which is why the offline queue must be replayed first in, "
                        "first out."),
        "key_justification": "Undo of the most recent action is a stack pop.",
        "variants": variants(
            [({}, [("5\nADD Ravi 200\nADD Meena 150\nPAY Ravi 50\nUNDO\nPAY Meena 150\n", "Ravi 200")]),
             ({}, [("4\nADD Gita 120\nUNDO\nUNDO\nADD Asif 80\n", "Asif 80")]),
             ({}, [("3\nADD Lata 100\nPAY Lata 100\nPAY Kiran 50\n", "Kiran -50")])],
            _gen_khata, 270,
            extra_hidden=[["2\nADD Ravi 10\nPAY Ravi 10\n"], ["1\nUNDO\n"],
                          ["4\nADD Meena 60\nADD Joseph 40\nUNDO\nUNDO\n"]]),
    },
]

_IO_DUE = '''
def main():
    data = sys.stdin.read().split("\\n")
    today, k = map(int, data[0].split())
    n = int(data[1])
    dues = []
    for i in range(n):
        name, day, amount = data[2 + i].split()
        dues.append((name, int(day), int(amount)))
    ranked = most_overdue(dues, today, k)
    if not ranked:
        print("NONE")
    for name, days, amount in ranked:
        print(name, days, amount)


main()
'''
_SIG_DUE = "def most_overdue(dues, today, k):"
_DOC_DUE = ("dues: list of (name, due_day, amount). A due is overdue when due_day < today. Return up to k "
            "(name, days_overdue, amount): most days overdue first, then larger amount, then name A to Z.")


def _alt_due(stdin):
    rows = stdin.split("\n")
    today, k = map(int, rows[0].split())
    n = int(rows[1])
    items = []
    for row in rows[2:2 + n]:
        name, day, amount = row.split()
        if int(day) < today:
            items.append((name, today - int(day), int(amount)))
    picked = []
    for _ in range(min(k, len(items))):
        best = None
        for it in items:
            if it in picked:
                continue
            if best is None or (it[1], it[2], [-ord(c) for c in it[0]]) > (best[1], best[2], [-ord(c) for c in best[0]]):
                best = it
        picked.append(best)
    return "\n".join(f"{a} {b} {c}" for a, b, c in picked) or "NONE"


def _gen_due(rng, size):
    n = {"small": 6, "medium": 20, "large": 50}[size]
    today, k = rng.randint(20, 40), rng.randint(2, 6)
    names = [f"C{i:02d}" for i in range(1, n + 1)]
    rows = [f"{name} {rng.randint(today - 15, today + 5)} {rng.choice([200, 450, 600, 900, 1500])}" for name in names]
    return f"{today} {k}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["fsd-5"].append({
    "prompt": ("Kirana Khata sends payment reminders, but a shop may only send k a day, so it should remind the "
               "customers who are most overdue. The first line is `today k` (day numbers), the second is n, then n "
               "lines `name due_day amount` (each name appears once). A due is overdue when due_day is before today. "
               "Complete `most_overdue` so the program prints up to k lines `name days_overdue amount`: most days "
               "overdue first, then the larger amount, then name in string order. It prints NONE if nobody is overdue."),
    "ds_topic": "heap", "difficulty": 2, "skills": ["Python", "SQL"],
    "starter": program(_IO_DUE, stub(_SIG_DUE, _DOC_DUE, "[]")),
    "solution": "import heapq\n" + program(_IO_DUE, _SIG_DUE + f'''
    """{_DOC_DUE}"""
    overdue = [(today - day, amount, name) for name, day, amount in dues if day < today]
    best = heapq.nsmallest(k, overdue, key=lambda x: (-x[0], -x[1], x[2]))
    return [(name, days, amount) for days, amount, name in best]
'''),
    "alt": _alt_due,
    "explanation": ("Filter to overdue dues, then take the k best with a heap (heapq.nsmallest with a key of negative "
                    "days, negative amount, name), which is O(n log k) instead of sorting everything. With small n a "
                    "full sort is also correct; the heap matters when n is in the millions and k is small."),
    "key_justification": "Top-k selection with a heap and a composite key.",
    "variants": variants(
        [({}, [("30 2\n4\nAsha 20 500\nBilal 25 900\nChitra 20 700\nDev 31 100\n", "Chitra 10 700\nAsha 10 500")]),
         ({}, [("10 3\n3\nEsha 9 300\nFaiz 2 300\nGopi 9 300\n", "Faiz 8 300\nEsha 1 300\nGopi 1 300")]),
         ({}, [("15 1\n3\nHari 15 900\nIndu 14 50\nJaya 16 700\n", "Indu 1 50")])],
        _gen_due, 280,
        extra_hidden=[["5 3\n2\nKala 5 100\nLeo 9 100\n"], ["8 5\n1\nMani 1 10\n"], ["20 2\n2\nNia 10 400\nOm 10 400\n"]]),
})

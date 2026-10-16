"""Code pool for Mobile App Development (mob-2 .. mob-5). Built and checked by scripts/build_code_pools.py."""
from collections import OrderedDict

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- mob-2 Yaad Dawa
_IO_SCHED = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    medicines = []
    for i in range(n):
        parts = data[1 + i].split()
        medicines.append((parts[0], parts[1:]))
    for time, names in day_schedule(medicines):
        print(time, ", ".join(names))


main()
'''
_SIG_SCHED = "def day_schedule(medicines):"
_DOC_SCHED = ("medicines: list of (name, [times 'HH:MM']). Return one reminder per time, [(time, [names sorted])], in "
              "time order, so an elder gets one alert for everything due at 8 am.")


def _alt_sched(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    times = sorted({t for r in rows for t in r[1:]})
    return "\n".join(f"{t} {', '.join(sorted({r[0] for r in rows if t in r[1:]}))}" for t in times)


_MEDS = ["Metformin", "Amlodipine", "Vitamin_D", "Atorvastatin", "Calcium", "Thyroxine", "Aspirin", "Pantoprazole"]


def _gen_sched(rng, size):
    n = {"small": 3, "medium": 6, "large": 8}[size]
    times = ["06:30", "08:00", "08:00", "13:00", "14:00", "20:00", "21:00", "21:00"]
    rows = [f"{m} " + " ".join(sorted(set(rng.sample(times, rng.randint(1, 3))))) for m in rng.sample(_MEDS, n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_ADH = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    doses = [tuple(data[1 + i].split()) for i in range(n)]
    m = int(data[1 + n])
    taps = [tuple(data[2 + n + i].split()) for i in range(m)]
    per_med, missed = adherence(doses, taps)
    for med, taken, total in per_med:
        print(med, f"{taken}/{total}", f"{100 * taken // total}%")
    for day, time, med in missed:
        print("missed", day, time, med)


main()
'''
_SIG_ADH = "def adherence(doses, taps):"
_DOC_ADH = ("doses and taps: lists of (date, 'HH:MM', medicine). A dose counts as taken if a 'taken' tap for the same "
            "medicine on the same date falls between its time and 120 minutes later (inclusive); each tap counts once, "
            "and doses are matched in time order with the earliest suitable tap. Return ([(medicine, taken, "
            "scheduled)] sorted by medicine, missed doses sorted by date, time, medicine).")


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _alt_adh(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    doses = sorted(tuple(r.split()) for r in rows[1:1 + n])
    m = int(rows[1 + n])
    taps = [tuple(r.split()) for r in rows[2 + n:2 + n + m]]
    used = [False] * len(taps)
    got, tot, missed = {}, {}, []
    for d, t, med in doses:
        tot[med] = tot.get(med, 0) + 1
        best = None
        for i, (dd, tt, mm) in enumerate(taps):
            if not used[i] and dd == d and mm == med and 0 <= _mins(tt) - _mins(t) <= 120:
                if best is None or _mins(tt) < _mins(taps[best][1]):
                    best = i
        if best is None:
            missed.append(f"missed {d} {t} {med}")
        else:
            used[best] = True
            got[med] = got.get(med, 0) + 1
    out = [f"{med} {got.get(med, 0)}/{tot[med]} {100 * got.get(med, 0) // tot[med]}%" for med in sorted(tot)]
    return "\n".join(out + missed)


def _gen_adh(rng, size):
    days = {"small": 1, "medium": 3, "large": 5}[size]
    meds = rng.sample(_MEDS, 2)
    doses, taps = [], []
    for d in range(days):
        day = f"2026-10-{d + 1:02d}"
        for med in meds:
            for t in ["08:00", "21:00"]:
                doses.append(f"{day} {t} {med}")
                r = rng.random()
                if r < 0.6:
                    taps.append(f"{day} {_fmt(_mins(t) + rng.randint(0, 120))} {med}")
                elif r < 0.75:
                    taps.append(f"{day} {_fmt(_mins(t) + rng.randint(121, 200))} {med}")
    rng.shuffle(doses)
    rng.shuffle(taps)
    return f"{len(doses)}\n" + "\n".join(doses) + f"\n{len(taps)}\n" + "\n".join(taps) + "\n"


def _fmt(m):
    return f"{m // 60:02d}:{m % 60:02d}"


PROBLEMS["mob-2"] = [
    {
        "prompt": ("Elderly users find several alarms at the same minute confusing, so Yaad Dawa sends one reminder per "
                   "time listing every medicine due then. The first line is n, then n lines `medicine time time ...` "
                   "(times as HH:MM). Complete `day_schedule`. The program prints one line per time, earliest first: "
                   "`HH:MM name, name`, with the medicine names in alphabetical (string) order."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_SCHED, stub(_SIG_SCHED, _DOC_SCHED, "[(t, [name]) for name, ts in medicines for t in ts]")),
        "solution": program(_IO_SCHED, _SIG_SCHED + f'''
    """{_DOC_SCHED}"""
    due = {{}}
    for name, times in medicines:
        for time in times:
            due.setdefault(time, set()).add(name)
    return [(time, sorted(due[time])) for time in sorted(due)]     # 'HH:MM' strings sort in time order
'''),
        "alt": _alt_sched,
        "explanation": ("Inverting the data, from medicine to times into time to medicines, with a dictionary of sets "
                        "and then sorting the keys gives one alert per time. Zero-padded HH:MM strings sort correctly as "
                        "text. Fewer, clearer notifications matter a lot for users with weak eyesight."),
        "key_justification": "Invert a mapping, then sort keys and values.",
        "variants": variants(
            [({}, [("3\nMetformin 08:00 21:00\nAmlodipine 08:00\nVitamin_D 13:00\n",
                    "08:00 Amlodipine, Metformin\n13:00 Vitamin_D\n21:00 Metformin")]),
             ({}, [("1\nAspirin 20:00\n", "20:00 Aspirin")]),
             ({}, [("2\nb 06:30 06:30\na 06:30\n", "06:30 a, b")])],
            _gen_sched, 9010,
            extra_hidden=[["2\nZinc 23:59\nIron 00:00\n"], ["3\nc 08:00\nb 08:00\na 08:00\n"], ["1\nX 09:00 08:00 10:00\n"]]),
    },
    {
        "prompt": ("Children far away want to know whether their parents took their medicines. The first line is n, then "
                   "n scheduled doses `date HH:MM medicine`; then m, then m taps on 'taken' `date HH:MM medicine`. "
                   "Complete `adherence`: a dose counts as taken if a tap for the same medicine on the same date is "
                   "between its time and 120 minutes later (inclusive); each tap counts once, and doses are matched in "
                   "time order with the earliest suitable tap. The program prints `medicine taken/scheduled pct%` (rounded "
                   "down) per medicine, sorted, then `missed date time medicine` for each missed dose, sorted by date, "
                   "time, medicine."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_ADH, stub(_SIG_ADH, _DOC_ADH, "[], []")),
        "solution": program(_IO_ADH, '''def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


''' + _SIG_ADH + f'''
    """{_DOC_ADH}"""
    taps_by = {{}}                                       # (date, medicine) -> sorted unused tap minutes
    for day, time, med in taps:
        taps_by.setdefault((day, med), []).append(minutes(time))
    for key in taps_by:
        taps_by[key].sort()
    taken, scheduled, missed = {{}}, {{}}, []
    for day, time, med in sorted(doses):
        scheduled[med] = scheduled.get(med, 0) + 1
        start = minutes(time)
        pool = taps_by.get((day, med), [])
        hit = next((i for i, t in enumerate(pool) if start <= t <= start + 120), None)
        if hit is None:
            missed.append((day, time, med))
        else:
            pool.pop(hit)                                # a tap counts once
            taken[med] = taken.get(med, 0) + 1
    per_med = [(m, taken.get(m, 0), scheduled[m]) for m in sorted(scheduled)]
    return per_med, missed
'''),
        "alt": _alt_adh,
        "explanation": ("Grouping taps by (date, medicine) in a dictionary means each dose only looks at its own taps, "
                        "and removing a tap once used stops one tap covering two doses. Reporting missed doses by name and "
                        "time gives the family something to act on, not just a percentage."),
        "key_justification": "Match events to schedules with grouped look-ups and one-time use.",
        "variants": variants(
            [({}, [("3\n2026-10-01 08:00 Metformin\n2026-10-01 21:00 Metformin\n2026-10-01 08:00 Amlodipine\n2\n"
                    "2026-10-01 08:20 Metformin\n2026-10-01 11:00 Amlodipine\n",
                    "Amlodipine 0/1 0%\nMetformin 1/2 50%\nmissed 2026-10-01 08:00 Amlodipine\nmissed 2026-10-01 21:00 Metformin")]),
             ({}, [("1\n2026-10-02 08:00 Calcium\n1\n2026-10-02 10:00 Calcium\n", "Calcium 1/1 100%")]),
             ({}, [("2\n2026-10-03 08:00 Aspirin\n2026-10-03 09:00 Aspirin\n1\n2026-10-03 09:30 Aspirin\n",
                    "Aspirin 1/2 50%\nmissed 2026-10-03 09:00 Aspirin")])],
            _gen_adh, 9020,
            extra_hidden=[["1\n2026-10-01 08:00 X\n1\n2026-10-02 08:00 X\n"], ["1\n2026-10-01 08:00 X\n1\n2026-10-01 07:59 X\n"],
                          ["2\n2026-10-01 08:00 B\n2026-10-01 08:00 A\n0\n"]]),
    },
]

# ---------------------------------------------------------------- mob-3 Rasoi Ghar
_IO_MIG = '''
def main():
    data = sys.stdin.read().split("\\n")
    current, target = map(int, data[0].split())
    n = int(data[1])
    steps = [tuple(map(int, data[2 + i].split())) for i in range(n)]
    print("\\n".join(migration_plan(current, target, steps)))


main()
'''
_SIG_MIG = "def migration_plan(current, target, steps):"
_DOC_MIG = ("steps: available migrations (a, b) from schema version a to b. Return the lines to print: 'UP TO DATE' if "
            "current == target; 'ABORT downgrade' if current > target; else 'run v->v+1' for each version in order, "
            "stopping with 'MISSING v->v+1' and 'ABORT' at the first step that does not exist.")


def _alt_mig(stdin):
    rows = stdin.split("\n")
    cur, tgt = map(int, rows[0].split())
    n = int(rows[1])
    st = [r.split() for r in rows[2:2 + n]]
    if cur == tgt:
        return "UP TO DATE"
    if cur > tgt:
        return "ABORT downgrade"
    out = []
    for v in range(cur, tgt):
        if [str(v), str(v + 1)] in st:
            out.append(f"run {v}->{v + 1}")
        else:
            out += [f"MISSING {v}->{v + 1}", "ABORT"]
            break
    return "\n".join(out)


def _gen_mig(rng, size):
    top = {"small": 5, "medium": 12, "large": 30}[size]
    steps = [f"{v} {v + 1}" for v in range(1, top) if rng.random() < 0.9]
    rng.shuffle(steps)
    cur, tgt = sorted(rng.sample(range(1, top + 1), 2))
    if rng.random() < 0.1:
        cur, tgt = tgt, cur
    return f"{cur} {tgt}\n{len(steps)}\n" + "\n".join(steps) + "\n"


_IO_IMGCACHE = '''
def main():
    data = sys.stdin.read().split("\\n")
    capacity, n = map(int, data[0].split())
    requests = []
    for i in range(n):
        image, kb = data[1 + i].split()
        requests.append((image, int(kb)))
    hits, misses, evictions, cache = image_cache(requests, capacity)
    print("hits", hits, "misses", misses, "evictions", evictions)
    print("cache", " ".join(cache) if cache else "-")


main()
'''
_SIG_IMGCACHE = "def image_cache(requests, capacity):"
_DOC_IMGCACHE = ("requests: (image, size KB) in order. A least-recently-used cache holds at most `capacity` KB. A hit "
                 "makes the image most recent. A miss adds the image as most recent, then evicts the least recent until "
                 "the total fits; an image bigger than the whole cache is never stored. Return (hits, misses, "
                 "evictions, images from most to least recent).")


def _alt_imgcache(stdin):
    rows = stdin.split("\n")
    cap, n = map(int, rows[0].split())
    order = []        # most recent last
    size = {}
    h = m = e = 0
    for r in rows[1:1 + n]:
        img, kb = r.split()
        kb = int(kb)
        if img in order:
            h += 1
            order.remove(img)
            order.append(img)
            continue
        m += 1
        if kb > cap:
            continue
        order.append(img)
        size[img] = kb
        while sum(size[x] for x in order) > cap:
            order.pop(0)
            e += 1
    return f"hits {h} misses {m} evictions {e}\ncache {' '.join(reversed(order)) or '-'}"


def _gen_imgcache(rng, size):
    n = {"small": 8, "medium": 30, "large": 70}[size]
    imgs = {f"step{i}": rng.choice([40, 80, 120, 200, 350]) for i in range(1, {"small": 5, "medium": 10, "large": 15}[size])}
    names = list(imgs)
    reqs = [rng.choice(names[:max(2, len(names) // 3)]) if rng.random() < 0.6 else rng.choice(names) for _ in range(n)]
    return f"{rng.choice([300, 500, 800])} {n}\n" + "\n".join(f"{x} {imgs[x]}" for x in reqs) + "\n"


PROBLEMS["mob-3"] = [
    {
        "prompt": ("After the update, the app crashed on launch for users who had skipped a version, because their local "
                   "database was never migrated step by step. The first line is `current target` (schema versions), the "
                   "second is n, then n available migrations `a b` (from version a to b), in any order. Complete "
                   "`migration_plan`: print `UP TO DATE` if they are equal, `ABORT downgrade` if current is higher, "
                   "otherwise `run v->v+1` for each step in order, and if a step is missing print `MISSING v->v+1` and "
                   "`ABORT` instead of continuing."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_MIG, stub(_SIG_MIG, _DOC_MIG, '["UP TO DATE"]')),
        "solution": program(_IO_MIG, _SIG_MIG + f'''
    """{_DOC_MIG}"""
    if current == target:
        return ["UP TO DATE"]
    if current > target:
        return ["ABORT downgrade"]
    available = set(steps)
    lines = []
    for v in range(current, target):
        if (v, v + 1) not in available:
            return lines + [f"MISSING {{v}}->{{v + 1}}", "ABORT"]   # never jump over a missing step
        lines.append(f"run {{v}}->{{v + 1}}")
    return lines
'''),
        "alt": _alt_mig,
        "explanation": ("Migrations must run in order from the user's version, not only the latest one, because each "
                        "step assumes the previous schema. A set of available steps makes each check O(1), and stopping "
                        "at a gap is safer than crashing halfway with a half-migrated database."),
        "key_justification": "Walk a version range in order with set look-ups.",
        "variants": variants(
            [({}, [("3 6\n3\n5 6\n3 4\n4 5\n", "run 3->4\nrun 4->5\nrun 5->6")]),
             ({}, [("2 5\n2\n2 3\n4 5\n", "run 2->3\nMISSING 3->4\nABORT")]),
             ({}, [("7 7\n0\n", "UP TO DATE")])],
            _gen_mig, 9110,
            extra_hidden=[["5 2\n1\n2 3\n"], ["1 2\n0\n"], ["1 2\n1\n1 2\n"]]),
    },
    {
        "prompt": ("Scrolling the recipe list stutters because step photos are decoded again and again. A memory cache "
                   "with a size limit fixes it. The first line is `capacity n` (KB), then n image requests `image kb` in "
                   "order (an image always has the same size). Complete `image_cache` as a least-recently-used cache: a "
                   "hit makes the image the most recent; a miss adds it as most recent and then evicts the least recent "
                   "images until the total fits; an image bigger than the whole cache is never stored. The program prints "
                   "`hits h misses m evictions e` and `cache` with the images from most to least recent, or `cache -`."),
        "ds_topic": "linked_list", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_IMGCACHE, stub(_SIG_IMGCACHE, _DOC_IMGCACHE, "0, len(requests), 0, []")),
        "solution": "from collections import OrderedDict\n" + program(_IO_IMGCACHE, _SIG_IMGCACHE + f'''
    """{_DOC_IMGCACHE}"""
    cache = OrderedDict()            # a hash map plus a linked list: least recent first
    used = hits = misses = evictions = 0
    for image, kb in requests:
        if image in cache:
            hits += 1
            cache.move_to_end(image)
            continue
        misses += 1
        if kb > capacity:
            continue                 # would evict everything and still not fit
        cache[image] = kb
        used += kb
        while used > capacity:
            _, freed = cache.popitem(last=False)
            used -= freed
            evictions += 1
    return hits, misses, evictions, list(reversed(cache))
'''),
        "alt": _alt_imgcache,
        "explanation": ("An LRU cache needs a fast 'is it cached?' check and an order of use; OrderedDict is a hash map "
                        "over a doubly linked list, so a hit, an insert and an eviction are all O(1). Limiting by bytes, "
                        "not by count, is what keeps a phone with little RAM from being killed, as image libraries like "
                        "Glide and Coil do."),
        "key_justification": "Byte-limited LRU cache with an ordered hash map (linked list).",
        "variants": variants(
            [({}, [("300 5\na 100\nb 150\na 100\nc 100\ne 400\n", "hits 1 misses 4 evictions 1\ncache c a")]),
             ({}, [("100 3\nx 50\ny 50\nx 50\n", "hits 1 misses 2 evictions 0\ncache x y")]),
             ({}, [("10 2\nbig 11\nbig 11\n", "hits 0 misses 2 evictions 0\ncache -")])],
            _gen_imgcache, 9120,
            extra_hidden=[["50 1\nq 50\n"], ["100 4\na 60\nb 60\na 60\nb 60\n"], ["200 4\na 100\nb 100\nc 100\na 100\n"]]),
    },
]

# ---------------------------------------------------------------- mob-4 Paisa Mitra
_IO_VERSION = '''
def main():
    data = sys.stdin.read().split("\\n")
    minimum = data[0].strip()
    n = int(data[1])
    for i in range(n):
        user, version = data[2 + i].split()
        print(user, "FORCE_UPDATE" if is_older(version, minimum) else "OK")


main()
'''
_SIG_VERSION = "def is_older(version, minimum):"
_DOC_VERSION = ("Versions like '3.10.2'. Compare part by part as numbers (so 3.10 is newer than 3.9); a missing part "
                "counts as 0 (3.9 equals 3.9.0). Return True if version is older than minimum.")


def _alt_version(stdin):
    rows = stdin.split("\n")
    mn = rows[0].strip()
    n = int(rows[1])
    out = []
    for r in rows[2:2 + n]:
        u, v = r.split()
        a = [int(x) for x in v.split(".")]
        b = [int(x) for x in mn.split(".")]
        while len(a) < len(b):
            a.append(0)
        while len(b) < len(a):
            b.append(0)
        out.append(f"{u} {'FORCE_UPDATE' if a < b else 'OK'}")
    return "\n".join(out)


def _gen_version(rng, size):
    n = {"small": 4, "medium": 12, "large": 30}[size]
    mn = rng.choice(["3.9.0", "3.10", "4.0.1", "2.12.3"])
    vs = ["3.8.9", "3.9", "3.9.0", "3.10.2", "3.10", "4.0", "4.0.1", "4.0.0.5", "2.12.10", "2.9.99", "10.0", "3.09.1"]
    return f"{mn}\n{n}\n" + "\n".join(f"user{i + 1} {rng.choice(vs)}" for i in range(n)) + "\n"


_IO_ROLL = '''
def main():
    data = sys.stdin.read().split("\\n")
    stages = list(map(int, data[0].split()))
    n = int(data[1])
    users = [data[2 + i].strip() for i in range(n)]
    for user in users:
        b = bucket(user)
        first = next((p for p in stages if b < p), None)
        print(user, b, f"{first}%" if first is not None else "-")
    for p in stages:
        print(f"stage {p}%:", sum(1 for u in users if bucket(u) < p))


main()
'''
_SIG_ROLL = "def bucket(user_id):"
_DOC_ROLL = ("A stable bucket 0-99 for a user: h = 0; for each character c, h = (h x 31 + ord(c)) mod 1000003; the "
             "bucket is h mod 100. The same user must always land in the same bucket, on every phone.")


def _alt_bucket(u):
    h = 0
    for c in u:
        h = (h * 31 + ord(c)) % 1000003
    return h % 100


def _alt_roll(stdin):
    rows = stdin.split("\n")
    stages = [int(x) for x in rows[0].split()]
    n = int(rows[1])
    users = [r.strip() for r in rows[2:2 + n]]
    out = []
    for u in users:
        b = _alt_bucket(u)
        first = [p for p in stages if b < p]
        out.append(f"{u} {b} {str(first[0]) + '%' if first else '-'}")
    for p in stages:
        out.append(f"stage {p}%: {len([u for u in users if _alt_bucket(u) < p])}")
    return "\n".join(out)


def _gen_roll(rng, size):
    n = {"small": 4, "medium": 15, "large": 40}[size]
    stages = rng.choice(["1 5 20 50 100", "10 50", "2 10 25 100", "50"])
    users = [f"u{rng.randint(1000, 99999)}" for _ in range(n)]
    return f"{stages}\n{n}\n" + "\n".join(users) + "\n"


PROBLEMS["mob-4"] = [
    {
        "prompt": ("An old version of Paisa Mitra skips a security check, so it must be forced to update. The first line "
                   "is the minimum supported version, the second is n, then n lines `user version`. Complete "
                   "`is_older`: compare versions part by part as numbers (3.10 is newer than 3.9, which plain string "
                   "comparison gets wrong), treating a missing part as 0 (3.9 equals 3.9.0). The program prints `user "
                   "FORCE_UPDATE` for versions older than the minimum and `user OK` otherwise."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_VERSION, stub(_SIG_VERSION, _DOC_VERSION, "version < minimum")),
        "solution": program(_IO_VERSION, _SIG_VERSION + f'''
    """{_DOC_VERSION}"""
    a = [int(part) for part in version.split(".")]
    b = [int(part) for part in minimum.split(".")]
    length = max(len(a), len(b))
    a += [0] * (length - len(a))                 # 3.9 -> 3.9.0
    b += [0] * (length - len(b))
    return a < b                                 # lists compare element by element, as numbers
'''),
        "alt": _alt_version,
        "explanation": ("Splitting on dots and comparing integer lists fixes the classic bug where '3.10' < '3.9' as "
                        "strings. Padding with zeros makes 3.9 and 3.9.0 equal. The check must run on the server too: "
                        "a client that skips security checks cannot be trusted to enforce its own update."),
        "key_justification": "Parse version strings into integer lists for comparison.",
        "variants": variants(
            [({}, [("3.9.0\n3\nu1 3.10.2\nu2 3.8.9\nu3 3.9\n", "u1 OK\nu2 FORCE_UPDATE\nu3 OK")]),
             ({}, [("4.0.1\n2\na 4.0\nb 4.0.1\n", "a FORCE_UPDATE\nb OK")]),
             ({}, [("2.12.3\n2\nx 2.9.99\ny 10.0\n", "x FORCE_UPDATE\ny OK")])],
            _gen_version, 9210,
            extra_hidden=[["1.0\n1\nz 1.0.0.0\n"], ["3.10\n2\np 3.09.1\nq 3.10.0\n"], ["0.1\n1\nr 0.0.9\n"]]),
    },
    {
        "prompt": ("The new payment flow ships to a small share of users first. Each user needs a stable bucket so the "
                   "same people stay in the rollout as it grows. The first line lists the rollout stages as percents in "
                   "increasing order, the second is n, then n user ids. Complete `bucket`: h starts at 0; for each "
                   "character c, h = (h x 31 + ord(c)) mod 1000003; the bucket is h mod 100. A user is in a stage of p% "
                   "when bucket < p. The program prints `user bucket first_stage%` (the first stage that includes them, "
                   "or `-`), then `stage p%: k` users per stage."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_ROLL, stub(_SIG_ROLL, _DOC_ROLL, "0")),
        "solution": program(_IO_ROLL, _SIG_ROLL + f'''
    """{_DOC_ROLL}"""
    h = 0
    for c in user_id:
        h = (h * 31 + ord(c)) % 1000003          # a polynomial string hash, the same everywhere
    return h % 100
'''),
        "alt": _alt_roll,
        "explanation": ("A deterministic hash of the user id puts everyone in a fixed bucket, so raising the rollout "
                        "from 5% to 20% only adds users and never swaps some out. Python's built-in hash() is randomised "
                        "per process, which is exactly why a hand-written, stable hash is needed here."),
        "key_justification": "Stable hashing to buckets for percentage rollouts.",
        "variants": variants(
            [({}, [("1 5 20 50 100\n3\nasha\nzoya\ndev\n",
                    "asha 54 100%\nzoya 12 20%\ndev 49 50%\nstage 1%: 0\nstage 5%: 0\nstage 20%: 1\nstage 50%: 2\nstage 100%: 3")]),
             ({}, [("10 50\n3\nravi\nmeena\nkiran\n", "ravi 45 50%\nmeena 39 50%\nkiran 67 -\nstage 10%: 0\nstage 50%: 2")]),
             ({}, [("100\n1\npriya\n", "priya 61 100%\nstage 100%: 1")])],
            _gen_roll, 9220,
            extra_hidden=[["50\n1\nu100\n"], ["1 100\n2\nzoya\nzoya\n"], ["25 75\n1\na\n"]]),
    },
]

# ---------------------------------------------------------------- mob-5 Gaon Sehat
_IO_SYNC = '''
def main():
    data = sys.stdin.read().split("\\n")
    capacity, n = map(int, data[0].split())
    events = [data[1 + i].split() for i in range(n)]
    lines, pending = offline_sync(events, capacity)
    for line in lines:
        print(line)
    print("pending", pending)


main()
'''
_SIG_SYNC = "def offline_sync(events, capacity):"
_DOC_SYNC = ("events: ['SAVE', record_id] while offline, or ['SYNC'] when a signal is found. Each SYNC uploads up to "
             "`capacity` of the oldest saved records. Return (one line per SYNC: 'sync k: id id ...' or 'sync k: -', "
             "records still waiting).")


def _alt_sync(stdin):
    rows = stdin.split("\n")
    cap, n = map(int, rows[0].split())
    q, out, k = [], [], 0
    for r in rows[1:1 + n]:
        p = r.split()
        if p[0] == "SAVE":
            q.append(p[1])
        else:
            k += 1
            sent, q = q[:cap], q[cap:]
            out.append(f"sync {k}: {' '.join(sent) or '-'}")
    return "\n".join(out + [f"pending {len(q)}"])


def _gen_sync(rng, size):
    n = {"small": 8, "medium": 30, "large": 80}[size]
    rows, rid = [], 0
    for _ in range(n):
        if rng.random() < 0.7:
            rid += 1
            rows.append(f"SAVE v{rid}")
        else:
            rows.append("SYNC")
    return f"{rng.randint(1, 5)} {n}\n" + "\n".join(rows) + "\n"


_IO_MERGE = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    edits = []
    for i in range(n):
        device, ts, field, value = data[1 + i].split()
        edits.append((device, int(ts), field, value))
    for field, value in merge_record(edits).items():
        print(field, value)


main()
'''
_SIG_MERGE = "def merge_record(edits):"
_DOC_MERGE = ("edits: (device, timestamp, field, value) from phones that were offline, in any order. For the field "
              "'vaccines' the value is a comma-separated list and the result is the union of all lists, sorted. For "
              "every other field the latest timestamp wins; on a tie the larger device id wins. Return {field: value} "
              "with fields in sorted order.")


def _alt_merge(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    out = {}
    for f in sorted({r[2] for r in rows}):
        mine = [r for r in rows if r[2] == f]
        if f == "vaccines":
            vals = sorted({v for r in mine for v in r[3].split(",") if v})
            out[f] = ",".join(vals)
        else:
            win = max(mine, key=lambda r: (int(r[1]), r[0]))
            out[f] = win[3]
    return "\n".join(f"{k} {v}" for k, v in out.items())


def _gen_merge(rng, size):
    n = {"small": 4, "medium": 12, "large": 30}[size]
    fields = {"name": ["Sita", "Seeta", "Sita_Devi"], "village": ["Rampur", "Rampura"], "status": ["pregnant", "delivered"],
              "vaccines": ["BCG", "OPV0", "HepB", "BCG,OPV0", "Penta1", "OPV1,Penta1"], "phone": ["98765", "91234"]}
    rows = []
    for _ in range(n):
        f = rng.choice(list(fields))
        rows.append(f"asha_{rng.choice(['a', 'b', 'c'])} {rng.randint(100, 140)} {f} {rng.choice(fields[f])}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["mob-5"] = [
    {
        "prompt": ("Gaon Sehat must keep working for days without signal: visits are saved on the phone and uploaded "
                   "when a signal appears, oldest first, a few at a time on a weak connection. The first line is "
                   "`capacity n`, then n events, either `SAVE record_id` or `SYNC`. Complete `offline_sync`: each SYNC "
                   "uploads up to `capacity` of the oldest waiting records. The program prints `sync k: id id ...` (or "
                   "`sync k: -`) for each SYNC, then `pending p`."),
        "ds_topic": "queue", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_SYNC, stub(_SIG_SYNC, _DOC_SYNC, "[], 0")),
        "solution": "from collections import deque\n" + program(_IO_SYNC, _SIG_SYNC + f'''
    """{_DOC_SYNC}"""
    outbox, lines = deque(), []
    for event in events:
        if event[0] == "SAVE":
            outbox.append(event[1])
        else:
            sent = [outbox.popleft() for _ in range(min(capacity, len(outbox)))]   # oldest first
            lines.append(f"sync {{len(lines) + 1}}: {{' '.join(sent) if sent else '-'}}")
    return lines, len(outbox)
'''),
        "alt": _alt_sync,
        "explanation": ("An outbox queue keeps records in the order they were made, which matters when a later record "
                        "depends on an earlier one (a visit after a registration). Uploading a few at a time means a "
                        "dropped connection loses at most one small batch, which is simply retried at the next sync."),
        "key_justification": "Offline outbox as a FIFO queue drained in batches.",
        "variants": variants(
            [({}, [("2 7\nSAVE r1\nSAVE r2\nSAVE r3\nSYNC\nSAVE r4\nSYNC\nSYNC\n", "sync 1: r1 r2\nsync 2: r3 r4\nsync 3: -\npending 0")]),
             ({}, [("1 3\nSAVE a\nSAVE b\nSYNC\n", "sync 1: a\npending 1")]),
             ({}, [("5 2\nSAVE x\nSAVE y\n", "pending 2")])],
            _gen_sync, 9310,
            extra_hidden=[["3 1\nSYNC\n"], ["1 4\nSAVE a\nSYNC\nSYNC\nSAVE b\n"], ["2 5\nSAVE a\nSAVE b\nSAVE c\nSAVE d\nSYNC\n"]]),
    },
    {
        "prompt": ("Two ASHA workers sharing a household edited the same record offline, and the server must merge their "
                   "changes without losing a vaccination. The first line is n, then n edits `device timestamp field "
                   "value`, in any order. Complete `merge_record`: for the field `vaccines`, the value is a comma-"
                   "separated list and the result is the union of every list, sorted (a vaccine given is never "
                   "un-given); for every other field the latest timestamp wins, and on a tie the larger device id wins. "
                   "The program prints `field value` for each field, sorted by field."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_MERGE, stub(_SIG_MERGE, _DOC_MERGE, "{f: v for _, _, f, v in edits}")),
        "solution": program(_IO_MERGE, _SIG_MERGE + f'''
    """{_DOC_MERGE}"""
    latest, vaccines = {{}}, set()
    for device, ts, field, value in edits:
        if field == "vaccines":
            vaccines.update(v for v in value.split(",") if v)      # merge, never overwrite
        elif field not in latest or (ts, device) > latest[field][:2]:
            latest[field] = (ts, device, value)                     # last writer wins
    merged = {{f: v for f, (_, _, v) in latest.items()}}
    if any(field == "vaccines" for _, _, field, _ in edits):
        merged["vaccines"] = ",".join(sorted(vaccines))
    return dict(sorted(merged.items()))
'''),
        "alt": _alt_merge,
        "explanation": ("Different fields need different rules: last-writer-wins (comparing (timestamp, device) tuples "
                        "gives a deterministic tie-break) suits a name, but would silently drop a vaccination recorded on "
                        "the other phone. Treating vaccines as a set and merging by union keeps every one; this is the "
                        "idea behind conflict-free replicated data types."),
        "key_justification": "Per-field merge rules: LWW map entries plus a set union.",
        "variants": variants(
            [({}, [("5\nphoneA 100 name Sita\nphoneB 120 name Seeta\nphoneA 130 village Rampur\nphoneB 110 vaccines BCG,OPV0\n"
                    "phoneA 140 vaccines OPV0,HepB\n", "name Seeta\nvaccines BCG,HepB,OPV0\nvillage Rampur")]),
             ({}, [("2\na 100 status pregnant\nb 100 status delivered\n", "status delivered")]),
             ({}, [("1\nx 5 vaccines Penta1\n", "vaccines Penta1")])],
            _gen_merge, 9320,
            extra_hidden=[["2\nb 1 name X\na 2 name Y\n"], ["2\na 1 vaccines BCG\nb 1 vaccines BCG\n"], ["3\na 1 phone 1\na 1 village V\nb 0 phone 2\n"]]),
    },
]

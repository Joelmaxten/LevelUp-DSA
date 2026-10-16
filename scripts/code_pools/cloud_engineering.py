"""Code pool for Cloud Engineering (cle-2 .. cle-5). Built and checked by scripts/build_code_pools.py."""
import ipaddress
import math

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- cle-2 Kirana Konnect
_IO_IAM = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    grants = [tuple(data[1 + i].split()) for i in range(n)]
    m = int(data[1 + n])
    used = [tuple(data[2 + n + i].split()) for i in range(m)]
    unused = unused_grants(grants, used)
    print("\\n".join(" ".join(g) for g in unused) if unused else "LEAST PRIVILEGE OK")


main()
'''
_SIG_IAM = "def unused_grants(grants, used):"
_DOC_IAM = ("grants: list of (role, action, resource) the roles are allowed. used: (role, action, resource) seen in 90 "
            "days of access logs. Return the grants never used, sorted, each once.")


def _alt_iam(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    g = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    u = [r.split() for r in rows[2 + n:2 + n + m]]
    out = sorted({" ".join(x) for x in g if x not in u})
    return "\n".join(out) or "LEAST PRIVILEGE OK"


_ROLES = ["web", "worker", "deploy", "analytics"]
_ACTIONS = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "rds:Connect", "secrets:Read", "ec2:RunInstances"]
_RES = ["photos-bucket", "orders-db", "db-password", "web-fleet"]


def _gen_iam(rng, size):
    n = {"small": 4, "medium": 12, "large": 20}[size]
    grants = {f"{rng.choice(_ROLES)} {rng.choice(_ACTIONS)} {rng.choice(_RES)}" for _ in range(n)}
    grants = sorted(grants)
    used = [g for g in grants if rng.random() < 0.5] + [f"{rng.choice(_ROLES)} s3:GetObject photos-bucket"]
    used = used * rng.randint(1, 2)
    rng.shuffle(used)
    return f"{len(grants)}\n" + "\n".join(grants) + f"\n{len(used)}\n" + "\n".join(used) + "\n"


_IO_CIDR = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    subnets = [tuple(data[1 + i].split()) for i in range(n)]
    m = int(data[1 + n])
    for i in range(m):
        ip = data[2 + n + i].strip()
        print(ip, which_subnet(subnets, ip) or "none")


main()
'''
_SIG_CIDR = "def which_subnet(subnets, ip):"
_DOC_CIDR = ("subnets: list of (name, IPv4 CIDR like '10.0.1.0/24'). Return the name of the subnet containing ip with "
             "the LONGEST prefix (most specific), ties by name, or None. Do the bit arithmetic yourself.")


def _alt_cidr(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    subs = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    out = []
    for ip in rows[2 + n:2 + n + m]:
        ip = ip.strip()
        best = None
        for name, cidr in subs:
            net = ipaddress.ip_network(cidr, strict=False)
            if ipaddress.ip_address(ip) in net:
                key = (-net.prefixlen, name)
                if best is None or key < best:
                    best = key
        out.append(f"{ip} {best[1] if best else 'none'}")
    return "\n".join(out)


def _gen_cidr(rng, size):
    subs = [("vpc", "10.0.0.0/16"), ("public-a", "10.0.1.0/24"), ("private-a", "10.0.2.0/24"),
            ("db", "10.0.2.128/25"), ("public-b", "10.0.11.0/24"), ("mgmt", "10.0.200.0/22")]
    n = {"small": 3, "medium": 5, "large": 6}[size]
    chosen = rng.sample(subs, n)
    m = {"small": 3, "medium": 10, "large": 25}[size]
    ips = [f"10.{rng.choice([0, 0, 0, 1])}.{rng.choice([1, 2, 11, 200, 201, 203, 9])}.{rng.randint(0, 255)}" for _ in range(m)]
    return (f"{n}\n" + "\n".join(f"{a} {b}" for a, b in chosen) + f"\n{m}\n" + "\n".join(ips) + "\n")


PROBLEMS["cle-2"] = [
    {
        "prompt": ("Kirana Konnect is replacing root credentials with roles, and wants each role to keep only what it "
                   "uses. The first line is n, then n grants `role action resource`; then m, then m entries `role action "
                   "resource` from 90 days of access logs (repeats are possible). Complete `unused_grants`. The program "
                   "prints every grant that was never used, sorted, one per line (these are candidates to remove), or "
                   "`LEAST PRIVILEGE OK`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_IAM, stub(_SIG_IAM, _DOC_IAM, "[]")),
        "solution": program(_IO_IAM, _SIG_IAM + f'''
    """{_DOC_IAM}"""
    seen = set(used)                         # O(1) look-ups instead of scanning the log for every grant
    return sorted({{g for g in grants if g not in seen}})
'''),
        "alt": _alt_iam,
        "explanation": ("Putting the used (role, action, resource) triples in a set makes each check O(1); comparing "
                        "grants with real usage is how access analysers propose least-privilege policies. A grant "
                        "nobody used in 90 days is pure risk: if the role's credentials leak, the attacker gets it too."),
        "key_justification": "Set difference between granted and used permissions.",
        "variants": variants(
            [({}, [("3\nweb s3:GetObject photos-bucket\nweb s3:DeleteObject photos-bucket\nworker rds:Connect orders-db\n2\n"
                    "web s3:GetObject photos-bucket\nworker rds:Connect orders-db\n", "web s3:DeleteObject photos-bucket")]),
             ({}, [("1\ndeploy ec2:RunInstances web-fleet\n1\ndeploy ec2:RunInstances web-fleet\n", "LEAST PRIVILEGE OK")]),
             ({}, [("2\nb x r\na x r\n0\n", "a x r\nb x r")])],
            _gen_iam, 6010,
            extra_hidden=[["1\nweb secrets:Read db-password\n1\nworker secrets:Read db-password\n"],
                          ["2\nr a x\nr a x\n0\n"], ["0\n1\nr a x\n"]]),
    },
    {
        "prompt": ("Some of Kirana Konnect's servers ended up in the wrong subnet, so the database was reachable from "
                   "the internet. Work out where each address lives. The first line is n, then n subnets `name cidr` "
                   "(IPv4, like 10.0.1.0/24; subnets may be nested); then m, then m IP addresses. Complete `which_subnet` "
                   "with your own bit arithmetic (convert each address to a 32-bit number and compare the network bits): "
                   "an address belongs to the matching subnet with the longest prefix, ties by name. The program prints "
                   "`ip subnet` or `ip none`."),
        "ds_topic": "string", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CIDR, stub(_SIG_CIDR, _DOC_CIDR, "None")),
        "solution": program(_IO_CIDR, '''def to_int(address):
    a, b, c, d = (int(part) for part in address.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


''' + _SIG_CIDR + f'''
    """{_DOC_CIDR}"""
    address = to_int(ip)
    best = None
    for name, cidr in subnets:
        network, bits = cidr.split("/")
        bits = int(bits)
        mask = 0 if bits == 0 else (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
        if address & mask == to_int(network) & mask:          # same network bits
            key = (-bits, name)
            if best is None or key < best:
                best = key
    return best[1] if best else None
'''),
        "alt": _alt_cidr,
        "explanation": ("An IPv4 address is a 32-bit number and a /n prefix keeps its first n bits, so membership is "
                        "'address AND mask equals network AND mask'. When subnets nest (a /25 database subnet inside a "
                        "/24), the longest prefix is the most specific match, the same rule route tables use."),
        "key_justification": "Parse dotted IPs and match with bit masks (longest prefix).",
        "variants": variants(
            [({}, [("3\nvpc 10.0.0.0/16\nprivate-a 10.0.2.0/24\ndb 10.0.2.128/25\n4\n10.0.2.200\n10.0.2.5\n10.0.9.9\n10.1.0.1\n",
                    "10.0.2.200 db\n10.0.2.5 private-a\n10.0.9.9 vpc\n10.1.0.1 none")]),
             ({}, [("2\nall 0.0.0.0/0\nhome 192.168.1.0/24\n2\n192.168.1.77\n8.8.8.8\n", "192.168.1.77 home\n8.8.8.8 all")]),
             ({}, [("2\nb 10.0.0.0/8\na 10.0.0.0/8\n1\n10.20.30.40\n", "10.20.30.40 a")])],
            _gen_cidr, 6020,
            extra_hidden=[["1\nhost 10.0.0.5/32\n2\n10.0.0.5\n10.0.0.6\n"], ["1\nx 10.0.1.0/24\n1\n10.0.1.255\n"],
                          ["2\nwide 172.16.0.0/12\nnarrow 172.31.0.0/16\n2\n172.31.5.5\n172.15.0.1\n"]]),
    },
]

# ---------------------------------------------------------------- cle-3 Yatri Seva
_IO_COST = '''
def main():
    data = sys.stdin.read().split("\\n")
    k = int(data[0])
    n = int(data[1])
    last = [tuple(data[2 + i].split()) for i in range(n)]
    m = int(data[2 + n])
    this = [tuple(data[3 + n + i].split()) for i in range(m)]
    rows = biggest_increases(last, this, k)
    if not rows:
        print("NO INCREASES")
    for resource, increase in rows:
        print(resource, increase)


main()
'''
_SIG_COST = "def biggest_increases(last, this, k):"
_DOC_COST = ("last, this: lists of (resource, cost in rupees) line items for last month and this month; a resource can "
             "have several lines. Return up to k (resource, increase) with an increase above 0, largest first, ties by "
             "resource. A resource missing last month counts as 0 then.")


def _alt_cost(stdin):
    rows = stdin.split("\n")
    k = int(rows[0])
    n = int(rows[1])
    a = [r.split() for r in rows[2:2 + n]]
    m = int(rows[2 + n])
    b = [r.split() for r in rows[3 + n:3 + n + m]]
    names = sorted({x[0] for x in a + b})
    inc = []
    for nm in names:
        d = sum(int(c) for r, c in b if r == nm) - sum(int(c) for r, c in a if r == nm)
        if d > 0:
            inc.append((nm, d))
    inc.sort(key=lambda x: -x[1])
    return "\n".join(f"{r} {d}" for r, d in inc[:k]) or "NO INCREASES"


_RESOURCES = ["nat-gateway", "rds-primary", "s3-id-photos", "ec2-booking", "cloudwatch-logs", "data-transfer",
              "elb-public", "ebs-snapshots", "lambda-pnr"]


def _gen_cost(rng, size):
    n = {"small": 4, "medium": 12, "large": 25}[size]
    a = [f"{rng.choice(_RESOURCES)} {rng.randint(500, 40000)}" for _ in range(n)]
    b = [f"{rng.choice(_RESOURCES)} {rng.randint(500, 60000)}" for _ in range(n + rng.randint(0, 4))]
    return f"{rng.randint(1, 4)}\n{len(a)}\n" + "\n".join(a) + f"\n{len(b)}\n" + "\n".join(b) + "\n"


_IO_SCALE = '''
def main():
    data = sys.stdin.read().split("\\n")
    capacity, warmup, initial = map(int, data[0].split())
    loads = list(map(int, data[1].split()))
    short_minutes, worst, peak = simulate(loads, capacity, warmup, initial)
    print("shortfall_minutes", short_minutes)
    print("max_shortfall", worst)
    print("peak_instances", peak)


main()
'''
_SIG_SCALE = "def simulate(loads, capacity, warmup, initial):"
_DOC_SCALE = ("loads: requests per second for minutes 1, 2, ... Each running instance serves `capacity`. Each minute "
              "m: instances launched earlier whose ready minute <= m start serving; if load > running x capacity, that "
              "minute is short by the difference; then desired = max(1, ceil(load / capacity)): if desired > running + "
              "launching, launch the difference, ready at m + warmup; if desired < running and nothing is launching, "
              "running drops to desired. Return (short minutes, largest shortfall, most instances running at once).")


def _alt_scale(stdin):
    rows = stdin.split("\n")
    cap, warm, init = map(int, rows[0].split())
    loads = [int(x) for x in rows[1].split()]
    running, pending = init, []
    short = worst = 0
    peak = init
    for m, load in enumerate(loads, 1):
        running += len([t for t in pending if t <= m])
        pending = [t for t in pending if t > m]
        peak = max(peak, running)
        if load > running * cap:
            short += 1
            worst = max(worst, load - running * cap)
        want = max(1, math.ceil(load / cap))
        if want > running + len(pending):
            pending += [m + warm] * (want - running - len(pending))
        elif want < running and not pending:
            running = want
    return f"shortfall_minutes {short}\nmax_shortfall {worst}\npeak_instances {peak}"


def _gen_scale(rng, size):
    n = {"small": 6, "medium": 30, "large": 90}[size]
    loads, base = [], rng.randint(100, 300)
    for m in range(n):
        rush = 4 if n // 3 <= m < n // 2 else 1
        loads.append(base * rush + rng.randint(-50, 50))
    return f"{rng.choice([100, 150, 200])} {rng.randint(1, 5)} {rng.randint(1, 3)}\n" + " ".join(map(str, loads)) + "\n"


PROBLEMS["cle-3"] = [
    {
        "prompt": ("Yatri Seva's bill doubled in a month. Find what grew. The first line is k, the second is n, then n "
                   "line items `resource cost` for last month; then m, then m line items for this month (a resource can "
                   "appear on several lines, in rupees). Complete `biggest_increases`: total each resource per month (a "
                   "resource missing last month counts as 0) and return those whose cost went up. The program prints up "
                   "to k lines `resource increase`, largest first, ties by resource, or `NO INCREASES`."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_COST, stub(_SIG_COST, _DOC_COST, "[]")),
        "solution": program(_IO_COST, _SIG_COST + f'''
    """{_DOC_COST}"""
    change = {{}}
    for resource, cost in this:
        change[resource] = change.get(resource, 0) + int(cost)
    for resource, cost in last:
        change[resource] = change.get(resource, 0) - int(cost)
    grew = [(r, d) for r, d in change.items() if d > 0]
    return sorted(grew, key=lambda x: (-x[1], x[0]))[:k]
'''),
        "alt": _alt_cost,
        "explanation": ("Netting this month against last month per resource in one dictionary, then sorting by the "
                        "increase, points straight at what changed (here often a NAT gateway carrying traffic that "
                        "should use a free gateway endpoint). Investigating the biggest deltas first is how cost reviews "
                        "stay short."),
        "key_justification": "Aggregate per key, then sort by the month-on-month delta.",
        "variants": variants(
            [({}, [("2\n3\nnat-gateway 4000\nrds-primary 20000\ns3-photos 1000\n4\nnat-gateway 30000\nrds-primary 21000\n"
                    "s3-photos 900\nlambda-pnr 2500\n", "nat-gateway 26000\nlambda-pnr 2500")]),
             ({}, [("5\n2\na 100\na 100\n1\na 150\n", "NO INCREASES")]),
             ({}, [("1\n1\nx 10\n2\ny 5\nz 5\n", "y 5")])],
            _gen_cost, 6110,
            extra_hidden=[["3\n0\n1\nnew 1\n"], ["2\n2\nb 1\na 1\n2\nb 3\na 3\n"], ["1\n1\nq 9\n0\n"]]),
    },
    {
        "prompt": ("Autoscaling could not keep up with the morning ticket rush because new servers take minutes to warm "
                   "up. Simulate it. The first line is `capacity warmup initial` (requests per second one instance "
                   "serves, minutes before a new instance serves, instances at the start); the second line has the load "
                   "for each minute. Complete `simulate`: each minute m, instances launched earlier with ready minute <= "
                   "m start serving; the minute is short if load > running x capacity; then desired = max(1, ceil(load / "
                   "capacity)): launch the difference if desired > running + launching (ready at m + warmup), or drop to "
                   "desired if desired < running and nothing is launching. The program prints `shortfall_minutes`, "
                   "`max_shortfall` and `peak_instances`."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_SCALE, stub(_SIG_SCALE, _DOC_SCALE, "0, 0, initial")),
        "solution": "from collections import deque\n" + program(_IO_SCALE, _SIG_SCALE + f'''
    """{_DOC_SCALE}"""
    running, launching = initial, deque()     # ready minutes, oldest first (all launches share the same warmup)
    short = worst = 0
    peak = initial
    for minute, load in enumerate(loads, 1):
        while launching and launching[0] <= minute:
            launching.popleft()
            running += 1
        peak = max(peak, running)
        if load > running * capacity:
            short += 1
            worst = max(worst, load - running * capacity)
        desired = max(1, -(-load // capacity))           # ceil without floats
        if desired > running + len(launching):
            launching.extend([minute + warmup] * (desired - running - len(launching)))
        elif desired < running and not launching:
            running = desired
    return short, worst, peak
'''),
        "alt": _alt_scale,
        "explanation": ("Launched instances join a FIFO queue by ready time; because warm-up is the same for all, the "
                        "front of the queue is always the next to become ready. The simulation shows the cost of "
                        "reacting late: every minute of warm-up during a rush is lost capacity, which is why scheduled "
                        "or predictive scaling (scale before 6 am) beats purely reactive scaling here."),
        "key_justification": "Discrete-time simulation with a FIFO queue of launching instances.",
        "variants": variants(
            [({}, [("100 2 1\n50 250 250 250 50\n", "shortfall_minutes 2\nmax_shortfall 150\npeak_instances 3")]),
             ({}, [("200 1 2\n100 100 100\n", "shortfall_minutes 0\nmax_shortfall 0\npeak_instances 2")]),
             ({}, [("50 3 1\n500\n", "shortfall_minutes 1\nmax_shortfall 450\npeak_instances 1")])],
            _gen_scale, 6120,
            extra_hidden=[["100 1 1\n0 0 0\n"], ["10 1 1\n100 100 100 100\n"], ["100 5 4\n50 50 50 1000 1000\n"]]),
    },
]

# ---------------------------------------------------------------- cle-4 Arogya Records
_IO_RPO = '''
def main():
    data = sys.stdin.read().split("\\n")
    rpo, rto = map(int, data[0].split())
    failure, restore = map(int, data[1].split())
    backups = list(map(int, data[2].split())) if data[2].strip() else []
    loss, downtime = disaster(backups, failure, restore)
    print("data_loss", "all" if loss is None else f"{loss} min")
    print("downtime", downtime, "min")
    print("rpo", "MET" if loss is not None and loss <= rpo else "BREACHED")
    print("rto", "MET" if downtime <= rto else "BREACHED")


main()
'''
_SIG_RPO = "def disaster(backups, failure, restore):"
_DOC_RPO = ("backups: minutes at which a backup or log copy COMPLETED (any order). failure: the minute the database is "
            "lost. restore: minutes the restore takes. Data since the last backup completed at or before the failure "
            "is lost. Return (minutes of data lost, or None if no backup existed; downtime = restore).")


def _alt_rpo(stdin):
    rows = stdin.split("\n")
    rpo, rto = map(int, rows[0].split())
    f, r = map(int, rows[1].split())
    b = [int(x) for x in rows[2].split()]
    before = [x for x in b if x <= f]
    loss = None if not before else f - max(before)
    lines = [f"data_loss {'all' if loss is None else str(loss) + ' min'}", f"downtime {r} min",
             f"rpo {'MET' if loss is not None and loss <= rpo else 'BREACHED'}", f"rto {'MET' if r <= rto else 'BREACHED'}"]
    return "\n".join(lines)


def _gen_rpo(rng, size):
    n = {"small": 3, "medium": 20, "large": 90}[size]
    step = rng.choice([5, 15, 60, 1440])
    backups = sorted(rng.sample(range(0, 3000, step), min(n, len(range(0, 3000, step)))))
    rng.shuffle(backups)
    return f"15 60\n{rng.randint(0, 3000)} {rng.choice([20, 45, 60, 90, 240])}\n" + " ".join(map(str, backups)) + "\n"


_IO_RESERVE = '''
def main():
    data = sys.stdin.read().split("\\n")
    on_demand, reserved = map(int, data[0].split())
    usage = list(map(int, data[1].split()))
    count, cost = best_reservation(usage, on_demand, reserved)
    print("reserve", count)
    print("cost", cost)


main()
'''
_SIG_RESERVE = "def best_reservation(usage, on_demand, reserved):"
_DOC_RESERVE = ("usage: servers needed in each hour. A reserved server costs `reserved` paise every hour whether used or "
                "not; any server above the reserved count costs `on_demand` paise for that hour. Return (the number of "
                "servers to reserve with the lowest total cost, smallest number on a tie; that cost).")


def _alt_reserve(stdin):
    rows = stdin.split("\n")
    od, rs = map(int, rows[0].split())
    use = [int(x) for x in rows[1].split()]
    best = None
    for k in range(0, max(use) + 1):
        cost = k * rs * len(use) + sum(max(0, u - k) for u in use) * od
        if best is None or cost < best[1]:
            best = (k, cost)
    return f"reserve {best[0]}\ncost {best[1]}"


def _gen_reserve(rng, size):
    hours = {"small": 12, "medium": 48, "large": 168}[size]
    base = rng.randint(10, 20)
    use = [base + (rng.randint(0, 12) if 0 <= h % 24 - 18 < 4 else rng.randint(0, 3)) for h in range(hours)]
    od = rng.choice([800, 1000, 1200])
    return f"{od} {int(od * rng.choice([0.4, 0.6, 0.75]))}\n" + " ".join(map(str, use)) + "\n"


PROBLEMS["cle-4"] = [
    {
        "prompt": ("Arogya Records' contracts promise at most 15 minutes of lost data (RPO) and service back within an "
                   "hour (RTO). Check a disaster drill. The first line is `rpo rto` in minutes, the second is `failure "
                   "restore` (the minute the database is lost, and how long the restore takes), the third lists the "
                   "minutes at which backups or log copies completed, in any order. Complete `disaster`: data written "
                   "after the last backup completed at or before the failure is lost. The program prints `data_loss x "
                   "min` (or `data_loss all` if there was no backup yet), `downtime y min`, then `rpo MET` or `rpo "
                   "BREACHED`, and the same for rto."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_RPO, stub(_SIG_RPO, _DOC_RPO, "0, restore")),
        "solution": program(_IO_RPO, _SIG_RPO + f'''
    """{_DOC_RPO}"""
    usable = [b for b in backups if b <= failure]       # a backup finished after the failure cannot help
    loss = failure - max(usable) if usable else None
    return loss, restore
'''),
        "alt": _alt_rpo,
        "explanation": ("Data loss is the gap back to the last completed backup, so only backups at or before the "
                        "failure count; the list need not be sorted, a max does it. Nightly backups give up to a day of "
                        "loss, far over a 15-minute RPO, which is why the contract needs continuous log shipping or a "
                        "replica, not just snapshots."),
        "key_justification": "Filter and max over an array to compute RPO and RTO.",
        "variants": variants(
            [({}, [("15 60\n100 45\n0 30 60 90 120\n", "data_loss 10 min\ndowntime 45 min\nrpo MET\nrto MET")]),
             ({}, [("15 60\n1500 90\n1440 0\n", "data_loss 60 min\ndowntime 90 min\nrpo BREACHED\nrto BREACHED")]),
             ({}, [("15 60\n10 5\n20 30\n", "data_loss all\ndowntime 5 min\nrpo BREACHED\nrto MET")])],
            _gen_rpo, 6210,
            extra_hidden=[["15 60\n50 60\n50\n"], ["5 10\n100 11\n96 94\n"], ["15 60\n0 1\n\n"]]),
    },
    {
        "prompt": ("Twenty servers run around the clock, but the evening peak needs more. Reserved servers are cheaper "
                   "per hour but are paid for every hour, used or not. The first line is `on_demand reserved` (paise per "
                   "server-hour), the second lists the servers needed in each hour. Complete `best_reservation`: with R "
                   "reserved servers, the cost is R x reserved x hours plus on_demand for every server-hour above R. "
                   "Return the R with the lowest cost (smallest R on a tie). Sort the hourly usage once rather than "
                   "recomputing the whole cost for every R. The program prints `reserve R` and `cost C`."),
        "ds_topic": "sorting", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_RESERVE, stub(_SIG_RESERVE, _DOC_RESERVE, "0, 0")),
        "solution": program(_IO_RESERVE, _SIG_RESERVE + f'''
    """{_DOC_RESERVE}"""
    hours = len(usage)
    ordered = sorted(usage)
    extra = sum(usage)                  # server-hours paid on demand when nothing is reserved
    best_r, best_cost = 0, extra * on_demand
    above = hours                       # hours whose usage is at least the next server number
    i = 0
    for r in range(1, ordered[-1] + 1):
        while i < hours and ordered[i] < r:
            i += 1
        above = hours - i               # hours that need server number r
        extra -= above                  # reserving server r removes those on-demand hours
        cost = r * reserved * hours + extra * on_demand
        if cost < best_cost:
            best_r, best_cost = r, cost
    return best_r, best_cost
'''),
        "alt": _alt_reserve,
        "explanation": ("Reserving one more server saves on-demand cost only in the hours that use it. With the hours "
                        "sorted, the count of hours needing at least r servers falls out of a single pass, so every R is "
                        "priced in O(hours log hours) total. The rule of thumb that emerges: reserve a server if it is "
                        "busy for more than reserved / on_demand of the hours."),
        "key_justification": "Sort usage, then sweep reservation levels with running totals.",
        "variants": variants(
            [({}, [("1000 600\n2 2 2 4\n", "reserve 2\ncost 6800")]),
             ({}, [("100 90\n1 1 1 1\n", "reserve 1\ncost 360")]),
             ({}, [("100 100\n0 3\n", "reserve 0\ncost 300")])],
            _gen_reserve, 6220,
            extra_hidden=[["500 400\n5\n"], ["1000 999\n0 0 0\n"], ["100 50\n1 2 3 4\n"]]),
    },
]

# ---------------------------------------------------------------- cle-5 Utsav Live
_IO_DRIFT = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    desired = [tuple(data[1 + i].split()) for i in range(n)]
    m = int(data[1 + n])
    actual = [tuple(data[2 + n + i].split()) for i in range(m)]
    plan = drift_plan(desired, actual)
    print("\\n".join(plan) if plan else "NO CHANGES")


main()
'''
_SIG_DRIFT = "def drift_plan(desired, actual):"
_DOC_DRIFT = ("desired (from code) and actual (in the cloud): lists of (resource, key, value). Return, sorted by "
              "resource then key: 'create R' for resources only desired, 'delete R' for resources only actual, and "
              "'update R KEY old->new' for a resource in both whose key differs (a missing value shows as '-').")


def _alt_drift(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    d = [r.split() for r in rows[1:1 + n]]
    m = int(rows[1 + n])
    a = [r.split() for r in rows[2 + n:2 + n + m]]
    out = []
    for res in sorted({x[0] for x in d} | {x[0] for x in a}):
        dk = {k: v for r, k, v in d if r == res}
        ak = {k: v for r, k, v in a if r == res}
        if not ak:
            out.append((res, "", f"create {res}"))
        elif not dk:
            out.append((res, "", f"delete {res}"))
        else:
            for k in sorted(set(dk) | set(ak)):
                if dk.get(k) != ak.get(k):
                    out.append((res, k, f"update {res} {k} {ak.get(k, '-')}->{dk.get(k, '-')}"))
    return "\n".join(x[2] for x in out) or "NO CHANGES"


def _gen_drift(rng, size):
    res = ["cdn", "origin_bucket", "encoder", "alerts", "dns", "vod_bucket", "api_lb"]
    keys = ["size", "region", "ttl", "versioning", "replicas", "tier"]
    vals = ["small", "large", "mumbai", "60", "300", "on", "off", "2", "4", "standard", "archive"]
    n = {"small": 4, "medium": 10, "large": 20}[size]
    desired = {(rng.choice(res), rng.choice(keys)): rng.choice(vals) for _ in range(n)}
    actual = {}
    for (r, k), v in desired.items():
        if rng.random() < 0.8:
            actual[(r, k)] = v if rng.random() < 0.7 else rng.choice(vals)
    for _ in range(rng.randint(0, 3)):
        actual[(rng.choice(res), rng.choice(keys))] = rng.choice(vals)
    d = [f"{r} {k} {v}" for (r, k), v in desired.items()]
    a = [f"{r} {k} {v}" for (r, k), v in actual.items()]
    return f"{len(d)}\n" + "\n".join(d) + f"\n{len(a)}\n" + "\n".join(a) + "\n"


_IO_MERGE = '''
def main():
    data = sys.stdin.read().split("\\n")
    k = int(data[0])
    feeds = [list(map(int, data[1 + i].split())) if data[1 + i].strip() else [] for i in range(k)]
    playlist, duplicates = merge_feeds(feeds)
    print(" ".join(map(str, playlist)) if playlist else "-")
    print("duplicates", duplicates)


main()
'''
_SIG_MERGE = "def merge_feeds(feeds):"
_DOC_MERGE = ("feeds: k lists of segment timestamps, each already sorted, from different ingest servers; the same "
              "timestamp can arrive from several servers. Return (one sorted playlist with each timestamp once, how "
              "many copies were dropped). Merge them; do not concatenate and re-sort.")


def _alt_merge(stdin):
    rows = stdin.split("\n")
    k = int(rows[0])
    allv = [int(x) for r in rows[1:1 + k] for x in r.split()]
    uniq = sorted(set(allv))
    return f"{' '.join(map(str, uniq)) or '-'}\nduplicates {len(allv) - len(uniq)}"


def _gen_merge(rng, size):
    k = {"small": 2, "medium": 4, "large": 6}[size]
    span = {"small": 30, "medium": 80, "large": 120}[size]
    feeds = []
    for _ in range(k):
        feeds.append(" ".join(map(str, sorted(rng.sample(range(0, span * 2, 2), rng.randint(0, span // 3))))))
    return f"{k}\n" + "\n".join(feeds) + "\n"


PROBLEMS["cle-5"] = [
    {
        "prompt": ("Utsav Live's environments were built by clicking in the console, so nobody can say what changed. "
                   "With infrastructure as code, a plan compares the code with the cloud. The first line is n, then n "
                   "lines `resource key value` from the code; then m, then m lines from the real account. Complete "
                   "`drift_plan`. Sorted by resource then key, list `create R` for resources only in the code, `delete R` "
                   "for resources only in the account, and `update R KEY actual->desired` for each key that differs on a "
                   "resource in both (a missing value shows as `-`). Print the plan, or `NO CHANGES`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_DRIFT, stub(_SIG_DRIFT, _DOC_DRIFT, "[]")),
        "solution": program(_IO_DRIFT, _SIG_DRIFT + f'''
    """{_DOC_DRIFT}"""
    want, have = {{}}, {{}}
    for resource, key, value in desired:
        want.setdefault(resource, {{}})[key] = value
    for resource, key, value in actual:
        have.setdefault(resource, {{}})[key] = value
    plan = []
    for resource in sorted(set(want) | set(have)):
        if resource not in have:
            plan.append(f"create {{resource}}")
        elif resource not in want:
            plan.append(f"delete {{resource}}")
        else:
            for key in sorted(set(want[resource]) | set(have[resource])):
                old, new = have[resource].get(key, "-"), want[resource].get(key, "-")
                if old != new:
                    plan.append(f"update {{resource}} {{key}} {{old}}->{{new}}")
    return plan
'''),
        "alt": _alt_drift,
        "explanation": ("Nested dictionaries (resource, then key) for both sides make the diff a pair of set operations. "
                        "This is what a Terraform plan does: code is the source of truth, and any manual console change "
                        "shows up as drift to be reverted or written back into code."),
        "key_justification": "Diff two nested maps into create, delete and update actions.",
        "variants": variants(
            [({}, [("4\ncdn ttl 60\ncdn tier standard\nencoder size large\ndns ttl 300\n3\ncdn ttl 300\ncdn tier standard\nold_vm size small\n",
                    "update cdn ttl 300->60\ncreate dns\ncreate encoder\ndelete old_vm")]),
             ({}, [("1\nbucket versioning on\n1\nbucket versioning on\n", "NO CHANGES")]),
             ({}, [("1\nlb replicas 2\n2\nlb replicas 2\nlb region mumbai\n", "update lb region mumbai->-")])],
            _gen_drift, 6310,
            extra_hidden=[["0\n0\n"], ["1\na k v\n0\n"], ["2\nx b 1\nx a 2\n2\nx a 3\nx c 4\n"]]),
    },
    {
        "prompt": ("For reliability, each live segment is ingested by several servers, and the recorder must turn their "
                   "feeds into one clean playlist. The first line is k, then k lines, each a sorted list of segment "
                   "timestamps from one server (a line may be empty); the same timestamp can come from several servers. "
                   "Complete `merge_feeds` with a k-way merge using a heap (do not join all lists and re-sort). The "
                   "program prints the merged timestamps once each, in order (or `-`), then `duplicates d`, the number of "
                   "dropped copies."),
        "ds_topic": "heap", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_MERGE, stub(_SIG_MERGE, _DOC_MERGE, "[], 0")),
        "solution": "import heapq\n" + program(_IO_MERGE, _SIG_MERGE + f'''
    """{_DOC_MERGE}"""
    heap = [(feed[0], i, 0) for i, feed in enumerate(feeds) if feed]
    heapq.heapify(heap)
    playlist, duplicates = [], 0
    while heap:
        value, i, j = heapq.heappop(heap)
        if playlist and playlist[-1] == value:
            duplicates += 1                       # the same segment from another server
        else:
            playlist.append(value)
        if j + 1 < len(feeds[i]):
            heapq.heappush(heap, (feeds[i][j + 1], i, j + 1))
    return playlist, duplicates
'''),
        "alt": _alt_merge,
        "explanation": ("A min-heap holding the next timestamp from each feed always yields the globally smallest one, "
                        "so k sorted feeds merge in O(n log k) while streaming, without loading everything first. Equal "
                        "timestamps come out next to each other, which makes dropping replica copies a comparison with "
                        "the last item written."),
        "key_justification": "K-way merge of sorted streams with a min-heap.",
        "variants": variants(
            [({}, [("3\n0 2 4 6\n2 4 8\n6 10\n", "0 2 4 6 8 10\nduplicates 3")]),
             ({}, [("2\n1 3 5\n\n", "1 3 5\nduplicates 0")]),
             ({}, [("2\n\n\n", "-\nduplicates 0")])],
            _gen_merge, 6320,
            extra_hidden=[["1\n7\n"], ["3\n5 5\n5\n5\n"], ["2\n1 2 3\n4 5 6\n"]]),
    },
]

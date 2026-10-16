"""Code pool for Game Development (gam-2 .. gam-5). Built and checked by scripts/build_code_pools.py."""
from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- gam-2 Mehfil Quest
_IO_FSM = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    table = [tuple(data[1 + i].split()) for i in range(n)]
    events = data[1 + n].split()
    states = run_guard(table, events)
    print(" ".join(states) if states else "-")
    print("final", states[-1] if states else "patrol")


main()
'''
_SIG_FSM = "def run_guard(table, events):"
_DOC_FSM = ("table: list of (state, event, next state). The guard starts in 'patrol'. For each event, move to the "
            "listed next state, or stay put if (state, event) is not in the table. Return the state after each event.")


def _alt_fsm(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    t = [r.split() for r in rows[1:1 + n]]
    ev = rows[1 + n].split()
    state, out = "patrol", []
    for e in ev:
        nxt = [c for s, x, c in t if s == state and x == e]
        state = nxt[-1] if nxt else state
        out.append(state)
    return f"{' '.join(out) or '-'}\nfinal {state}"


_TABLE = ["patrol see chase", "chase near attack", "chase lost patrol", "attack hurt flee", "attack far chase",
          "flee healed patrol", "flee cornered attack", "patrol noise search", "search see chase", "search timeout patrol"]
_EVENTS = ["see", "near", "lost", "hurt", "far", "healed", "cornered", "noise", "timeout", "jump"]


def _gen_fsm(rng, size):
    k = {"small": 6, "medium": 8, "large": 10}[size]
    rows = rng.sample(_TABLE, k)
    m = {"small": 5, "medium": 15, "large": 40}[size]
    return f"{k}\n" + "\n".join(rows) + "\n" + " ".join(rng.choice(_EVENTS) for _ in range(m)) + "\n"


_IO_POOL = '''
def main():
    data = sys.stdin.read().split()
    size, lifetime, n = int(data[0]), int(data[1]), int(data[2])
    spawns = list(map(int, data[3:3 + n]))
    spawned, dropped, peak = spark_pool(spawns, size, lifetime)
    print("spawned", spawned, "dropped", dropped, "peak", peak)


main()
'''
_SIG_POOL = "def spark_pool(spawns, size, lifetime):"
_DOC_POOL = ("spawns: times (ms) the spray asks for a spark, in order. The pool has `size` sparks; a spark lives "
             "`lifetime` ms and is back in the pool at time >= start + lifetime. If no spark is free the request is "
             "dropped (no new allocation). Return (spawned, dropped, most sparks alive at once).")


def _alt_pool(stdin):
    d = stdin.split()
    size, life, n = int(d[0]), int(d[1]), int(d[2])
    ts = [int(x) for x in d[3:3 + n]]
    alive, sp, dr, pk = [], 0, 0, 0
    for t in ts:
        alive = [e for e in alive if e > t]
        if len(alive) < size:
            alive.append(t + life)
            sp += 1
        else:
            dr += 1
        pk = max(pk, len(alive))
    return f"spawned {sp} dropped {dr} peak {pk}"


def _gen_pool(rng, size):
    n = {"small": 8, "medium": 40, "large": 150}[size]
    t, ts = 0, []
    for _ in range(n):
        t += rng.choice([0, 1, 2, 5, 20])
        ts.append(t)
    return f"{rng.randint(2, 12)} {rng.choice([30, 60, 100])} {n}\n" + " ".join(map(str, ts)) + "\n"


PROBLEMS["gam-2"] = [
    {
        "prompt": ("The guards' behaviour became a tangle of nested ifs. A state machine is a table instead. The first "
                   "line is n, then n transitions `state event next_state`, then one line of events. Complete "
                   "`run_guard`: the guard starts in `patrol`; for each event it moves to the listed next state, or stays "
                   "where it is if the table has no entry for (state, event). The program prints the state after each "
                   "event, then `final state`."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_FSM, stub(_SIG_FSM, _DOC_FSM, "[]")),
        "solution": program(_IO_FSM, _SIG_FSM + f'''
    """{_DOC_FSM}"""
    moves = {{(state, event): nxt for state, event, nxt in table}}   # the whole behaviour as data
    state, out = "patrol", []
    for event in events:
        state = moves.get((state, event), state)
        out.append(state)
    return out
'''),
        "alt": _alt_fsm,
        "explanation": ("A dictionary keyed by (state, event) replaces the nested conditions: each step is one lookup, "
                        "and adding a behaviour (search after a noise) is a new row, not a new branch in five places. "
                        "Unknown events leave the state alone, which is usually what a game wants."),
        "key_justification": "Finite state machine as a transition table in a hash map.",
        "variants": variants(
            [({}, [("5\npatrol see chase\nchase near attack\nattack hurt flee\nchase lost patrol\nflee healed patrol\n"
                    "see near hurt healed jump\n", "chase attack flee patrol patrol\nfinal patrol")]),
             ({}, [("1\npatrol see chase\nnoise noise\n", "patrol patrol\nfinal patrol")]),
             ({}, [("2\npatrol noise search\nsearch see chase\nnoise see see\n", "search chase chase\nfinal chase")])],
            _gen_fsm, 8010,
            extra_hidden=[["1\npatrol see chase\n\n"], ["2\npatrol a b\nb a patrol\na a a a\n"], ["1\nx y z\ny\n"]]),
    },
    {
        "prompt": ("The magic spray creates up to 500 sparks a second, and allocating each one makes the game stutter. "
                   "An object pool reuses a fixed set instead. The first line is `size lifetime n`, the second has n "
                   "spawn requests (times in ms, in order; several can share a time). Complete `spark_pool`: a spark "
                   "lives `lifetime` ms and returns to the pool at time >= start + lifetime; a request with no free spark "
                   "is dropped. Because every spark lives equally long, the next to return is always the oldest, so a "
                   "queue is enough. The program prints `spawned a dropped b peak c`."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_POOL, stub(_SIG_POOL, _DOC_POOL, "len(spawns), 0, len(spawns)")),
        "solution": "from collections import deque\n" + program(_IO_POOL, _SIG_POOL + f'''
    """{_DOC_POOL}"""
    alive = deque()                    # end times; oldest first, since every spark lives equally long
    spawned = dropped = peak = 0
    for t in spawns:
        while alive and alive[0] <= t:
            alive.popleft()            # back in the pool
        if len(alive) < size:
            alive.append(t + lifetime)
            spawned += 1
        else:
            dropped += 1
        peak = max(peak, len(alive))
    return spawned, dropped, peak
'''),
        "alt": _alt_pool,
        "explanation": ("With a fixed lifetime, sparks expire in the order they were created, so a FIFO queue of end "
                        "times returns sparks in O(1). A pool caps memory and removes per-frame allocation (and the "
                        "garbage-collection pauses that cause the stutter); dropping a spark when the pool is empty is "
                        "invisible to the player."),
        "key_justification": "Object pool with expiry tracked in a FIFO queue.",
        "variants": variants(
            [({}, [("2 100 6\n0 10 50 100 105 120\n", "spawned 4 dropped 2 peak 2")]),
             ({}, [("1 10 3\n0 0 10\n", "spawned 2 dropped 1 peak 1")]),
             ({}, [("5 1000 3\n0 1 2\n", "spawned 3 dropped 0 peak 3")])],
            _gen_pool, 8020,
            extra_hidden=[["1 1 1\n7\n"], ["3 5 6\n0 0 0 0 5 5\n"], ["2 50 4\n0 49 50 99\n"]]),
    },
]

# ---------------------------------------------------------------- gam-3 Rangbaaz Racing
_IO_BATCH = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    objects = [tuple(data[1 + i].split()) for i in range(n)]
    before, after, order = batch_draws(objects)
    print("before", before)
    print("after", after)
    print("order", " ".join(order))


main()
'''
_SIG_BATCH = "def batch_draws(objects):"
_DOC_BATCH = ("objects: list of (name, material) in draw order. One draw call is needed per run of consecutive "
              "objects sharing a material. Return (draw calls now, draw calls after sorting by material, the sorted "
              "names: by material, keeping the original order within a material).")


def _alt_batch(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    before = sum(1 for i, (_, m) in enumerate(rows) if i == 0 or rows[i - 1][1] != m)
    mats = sorted({m for _, m in rows})
    order = [nm for mat in mats for nm, m in rows if m == mat]
    return f"before {before}\nafter {len(mats)}\norder {' '.join(order)}"


def _gen_batch(rng, size):
    n = {"small": 6, "medium": 20, "large": 60}[size]
    mats = ["road", "car", "building", "tree", "sign", "auto"]
    rows = [f"obj{i + 1} {rng.choice(mats[:rng.randint(2, 6)])}" for i in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_TEX = '''
def main():
    data = sys.stdin.read().split("\\n")
    budget = int(data[0])
    n = int(data[1])
    textures = []
    for i in range(n):
        name, kb, priority = data[2 + i].split()
        textures.append((name, int(kb), int(priority)))
    sizes = fit_budget(textures, budget)
    for name, _, _ in textures:
        print(name, sizes[name])
    total = sum(sizes.values())
    print("total", total, "OK" if total <= budget else "OVER")


main()
'''
_SIG_TEX = "def fit_budget(textures, budget):"
_DOC_TEX = ("textures: (name, KB, priority; higher matters more). While the total is over budget, shrink the texture "
            "with the LOWEST priority (ties: larger KB, then name) one mip level: KB becomes max(1, KB // 4). A "
            "texture already at 1 KB can't shrink; stop if none can. Return {name: final KB}.")


def _alt_tex(stdin):
    rows = stdin.split("\n")
    budget = int(rows[0])
    n = int(rows[1])
    tex = [r.split() for r in rows[2:2 + n]]
    size = {t[0]: int(t[1]) for t in tex}
    pri = {t[0]: int(t[2]) for t in tex}
    while sum(size.values()) > budget:
        cands = [nm for nm in size if size[nm] > 1]
        if not cands:
            break
        pick = min(cands, key=lambda nm: (pri[nm], -size[nm], nm))
        size[pick] = max(1, size[pick] // 4)
    total = sum(size.values())
    return "\n".join([f"{t[0]} {size[t[0]]}" for t in tex] + [f"total {total} {'OK' if total <= budget else 'OVER'}"])


def _gen_tex(rng, size):
    n = {"small": 3, "medium": 8, "large": 15}[size]
    names = ["hero", "road", "sky", "buildings", "crowd", "autorickshaw", "signboards", "trees", "water", "lamps",
             "trucks", "billboard", "bridge", "temple", "market"]
    rows = [f"{names[i]} {rng.choice([256, 512, 1024, 2048, 4096])} {rng.randint(1, 9)}" for i in range(n)]
    return f"{rng.randint(300, 6000)}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["gam-3"] = [
    {
        "prompt": ("The profiler shows about 2,000 draw calls a frame on cheap phones. A draw call is needed each time "
                   "the material changes, so drawing objects grouped by material cuts the count. The first line is n, "
                   "then n objects `name material` in their current draw order. Complete `batch_draws`. The program "
                   "prints `before` (draw calls in the current order: one per run of consecutive objects with the same "
                   "material), `after` (draw calls once sorted by material, which is the number of materials) and "
                   "`order` with the names sorted by material, keeping the original order within each material."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_BATCH, stub(_SIG_BATCH, _DOC_BATCH, "len(objects), len(objects), [o[0] for o in objects]")),
        "solution": program(_IO_BATCH, _SIG_BATCH + f'''
    """{_DOC_BATCH}"""
    before = sum(1 for i, (_, mat) in enumerate(objects) if i == 0 or objects[i - 1][1] != mat)
    ordered = sorted(objects, key=lambda o: o[1])              # Python's sort is stable
    after = len({{mat for _, mat in objects}})
    return before, after, [name for name, _ in ordered]
'''),
        "alt": _alt_batch,
        "explanation": ("Counting changes between neighbours gives the current draw calls; a stable sort by material "
                        "groups each material into one run, so the calls drop to the number of materials while objects "
                        "keep their relative order within a group. Engines do this batching (plus texture atlases so "
                        "fewer materials exist) to stay within a phone's budget."),
        "key_justification": "Stable sort to group by key; count runs before and after.",
        "variants": variants(
            [({}, [("6\ncar1 car\nroad1 road\ncar2 car\nroad2 road\nroad3 road\ntree1 tree\n",
                    "before 5\nafter 3\norder car1 car2 road1 road2 road3 tree1")]),
             ({}, [("3\na m\nb m\nc m\n", "before 1\nafter 1\norder a b c")]),
             ({}, [("4\nx 2\ny 1\nz 2\nw 1\n", "before 4\nafter 2\norder y w x z")])],
            _gen_batch, 8110,
            extra_hidden=[["1\nsolo glass\n"], ["2\nb t\na s\n"], ["5\na x\nb y\nc x\nd y\ne x\n"]]),
    },
    {
        "prompt": ("The Old Delhi track crashes 2 GB phones because its textures don't fit in memory. Shrink the least "
                   "important textures until they fit. The first line is the budget in KB, the second is n, then n lines "
                   "`name kb priority` (higher priority matters more). Complete `fit_budget`: while the total is over "
                   "budget, take the texture with the lowest priority (ties: larger KB, then name) and drop it one mip "
                   "level, KB becoming max(1, KB // 4); a texture at 1 KB can't shrink, and if none can, stop. Use a heap "
                   "to find the next texture. The program prints `name kb` in input order, then `total T OK` or `total T "
                   "OVER`."),
        "ds_topic": "heap", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_TEX, stub(_SIG_TEX, _DOC_TEX, "{name: kb for name, kb, _ in textures}")),
        "solution": "import heapq\n" + program(_IO_TEX, _SIG_TEX + f'''
    """{_DOC_TEX}"""
    size = {{name: kb for name, kb, _ in textures}}
    total = sum(size.values())
    heap = [(priority, -kb, name) for name, kb, priority in textures if kb > 1]
    heapq.heapify(heap)
    while total > budget and heap:
        priority, neg_kb, name = heapq.heappop(heap)
        smaller = max(1, size[name] // 4)
        total -= size[name] - smaller
        size[name] = smaller
        if smaller > 1:
            heapq.heappush(heap, (priority, -smaller, name))   # it may need to shrink again
    return size
'''),
        "alt": _alt_tex,
        "explanation": ("A min-heap ordered by (priority, -size, name) always yields the next texture to shrink in O(log "
                        "n), and a shrunk texture goes back in with its new size. One mip level quarters the memory "
                        "(half the width and half the height), so low-priority textures like the sky shrink first while "
                        "the hero car stays sharp."),
        "key_justification": "Greedy shrinking driven by a priority heap.",
        "variants": variants(
            [({}, [("3000\n3\nhero 2048 9\nroad 4096 3\nsky 1024 1\n", "hero 2048\nroad 256\nsky 1\ntotal 2305 OK")]),
             ({}, [("10\n2\na 1 1\nb 1 5\n", "a 1\nb 1\ntotal 2 OK")]),
             ({}, [("1\n2\nx 64 2\ny 64 2\n", "x 1\ny 1\ntotal 2 OVER")])],
            _gen_tex, 8120,
            extra_hidden=[["100\n1\nonly 50 1\n"], ["700\n2\nb 512 1\na 512 1\n"], ["0\n1\nz 2 3\n"]]),
    },
]

# ---------------------------------------------------------------- gam-4 Tara Studios
_IO_TURN = '''
def main():
    data = sys.stdin.read().split("\\n")
    players = data[0].split()
    hands = {}
    for i in range(len(players)):
        parts = data[1 + i].split()
        hands[parts[0]] = parts[1:]
    m = int(data[1 + len(players)])
    moves = [tuple(data[2 + len(players) + i].split()) for i in range(m)]
    accepted, rejected, cheats = referee(players, hands, moves)
    print("accepted", accepted, "rejected", rejected)
    for player, count in cheats:
        print("cheats", player, count)


main()
'''
_SIG_TURN = "def referee(players, hands, moves):"
_DOC_TURN = ("players: turn order (the first player starts). hands: {player: [cards]}. moves: (player, card) as sent "
             "by the clients. A move is valid only if it is that player's turn and the card is in their hand; then the "
             "card leaves the hand and the turn passes on. An invalid move changes nothing. Return (accepted, "
             "rejected, [(player, rejected moves)] for players with any, sorted by player).")


def _alt_turn(stdin):
    rows = stdin.split("\n")
    players = rows[0].split()
    hands = {}
    for i in range(len(players)):
        p = rows[1 + i].split()
        hands[p[0]] = list(p[1:])
    m = int(rows[1 + len(players)])
    moves = [r.split() for r in rows[2 + len(players):2 + len(players) + m]]
    turn, acc, bad = 0, 0, {}
    for p, c in moves:
        if players[turn % len(players)] == p and c in hands[p]:
            hands[p].remove(c)
            turn += 1
            acc += 1
        else:
            bad[p] = bad.get(p, 0) + 1
    lines = [f"accepted {acc} rejected {sum(bad.values())}"] + [f"cheats {p} {bad[p]}" for p in sorted(bad)]
    return "\n".join(lines)


def _gen_turn(rng, size):
    players = ["asha", "bilal", "chen", "deepa"][: rng.randint(2, 4)]
    cards = [f"{r}{s}" for r in ["2", "5", "9", "J", "Q", "K", "A"] for s in "SHDC"]
    rng.shuffle(cards)
    k = {"small": 2, "medium": 4, "large": 6}[size]
    hands = {p: cards[i * k:(i + 1) * k] for i, p in enumerate(players)}
    moves, turn = [], 0
    for _ in range(k * len(players) + rng.randint(0, 6)):
        p = players[turn % len(players)] if rng.random() < 0.7 else rng.choice(players)
        c = rng.choice(hands[p] or cards) if rng.random() < 0.8 else rng.choice(cards)
        moves.append(f"{p} {c}")
        if p == players[turn % len(players)] and c in hands[p]:
            hands[p].remove(c)
            turn += 1
    start_hands = {p: cards[i * k:(i + 1) * k] for i, p in enumerate(players)}
    return (" ".join(players) + "\n" + "\n".join(f"{p} {' '.join(start_hands[p])}" for p in players)
            + f"\n{len(moves)}\n" + "\n".join(moves) + "\n")


_IO_PREDICT = '''
def main():
    data = sys.stdin.read().split("\\n")
    start = int(data[0])
    n = int(data[1])
    events = []
    for i in range(n):
        kind, seq, value = data[2 + i].split()
        events.append((kind, int(seq), int(value)))
    print(" ".join(map(str, predict(start, events))))


main()
'''
_SIG_PREDICT = "def predict(start, events):"
_DOC_PREDICT = ("events: ('INPUT', seq, dx) when the player presses a key (apply it at once and remember it) or ('ACK', "
                "seq, server_x) when the server confirms everything up to seq: take the server's position, forget "
                "inputs up to seq, then replay the inputs still unconfirmed. Return the shown position after each "
                "event.")


def _alt_predict(stdin):
    rows = stdin.split("\n")
    x = int(rows[0])
    n = int(rows[1])
    inputs, out = [], []
    for r in rows[2:2 + n]:
        k, s, v = r.split()
        s, v = int(s), int(v)
        if k == "INPUT":
            inputs.append((s, v))
            x += v
        else:
            inputs = [(a, b) for a, b in inputs if a > s]
            x = v + sum(b for _, b in inputs)
        out.append(x)
    return " ".join(map(str, out))


def _gen_predict(rng, size):
    n = {"small": 5, "medium": 20, "large": 60}[size]
    rows, seq, acked = [], 0, 0
    server = start = rng.randint(-5, 5)
    pending = []
    for _ in range(n):
        if pending and rng.random() < 0.35:
            upto = rng.choice(pending)[0]
            for s, dx in [p for p in pending if p[0] <= upto]:
                server += dx if rng.random() < 0.85 else dx - 1      # the server sometimes corrects (a wall, lag)
            pending = [p for p in pending if p[0] > upto]
            rows.append(f"ACK {upto} {server}")
        else:
            seq += 1
            dx = rng.choice([-3, -1, 1, 2, 5])
            pending.append((seq, dx))
            rows.append(f"INPUT {seq} {dx}")
    return f"{start}\n{len(rows)}\n" + "\n".join(rows) + "\n"


PROBLEMS["gam-4"] = [
    {
        "prompt": ("Players of Patta Mahal cheat by sending moves out of turn or playing cards they don't hold, because "
                   "the clients were trusted. Make the server the referee. The first line lists the players in turn order "
                   "(the first starts), then one line per player `player card card ...` with their hand, then m, then m "
                   "moves `player card` as received. Complete `referee`: a move is valid only if it is that player's turn "
                   "and the card is in their hand; it then leaves the hand and the turn passes on. An invalid move changes "
                   "nothing. The program prints `accepted a rejected r`, then `cheats player count` for each player with "
                   "rejected moves, sorted."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_TURN, stub(_SIG_TURN, _DOC_TURN, "len(moves), 0, []")),
        "solution": program(_IO_TURN, _SIG_TURN + f'''
    """{_DOC_TURN}"""
    hand = {{p: list(cards) for p, cards in hands.items()}}
    turn = accepted = 0
    rejected = {{}}
    for player, card in moves:
        if player == players[turn % len(players)] and card in hand[player]:
            hand[player].remove(card)
            turn += 1
            accepted += 1
        else:
            rejected[player] = rejected.get(player, 0) + 1
    return accepted, sum(rejected.values()), sorted(rejected.items())
'''),
        "alt": _alt_turn,
        "explanation": ("The server keeps the authoritative state (whose turn, which cards each hand holds) in "
                        "dictionaries and checks every move against it. A client can still send anything, but nothing "
                        "it sends changes the game unless the rules allow it, and the rejected count shows who tried."),
        "key_justification": "Authoritative server validation against state held in maps.",
        "variants": variants(
            [({}, [("A B\nA 5H KS\nB 2C\n4\nA 5H\nA KS\nB 2C\nA 9D\n", "accepted 2 rejected 2\ncheats A 2")]),
             ({}, [("x y z\nx 1\ny 2\nz 3\n3\nx 1\ny 2\nz 3\n", "accepted 3 rejected 0")]),
             ({}, [("p q\np AS\nq KH\n2\nq KH\nq KH\n", "accepted 0 rejected 2\ncheats q 2")])],
            _gen_turn, 8210,
            extra_hidden=[["a b\na 1 2\nb 3\n0\n"], ["a b\na 1\nb 2\n3\na 1\na 1\nb 2\n"], ["s t\ns 7 7\nt 8\n3\ns 7\nt 8\ns 7\n"]]),
    },
    {
        "prompt": ("In the 1v1 arena, waiting for the server before moving feels laggy, so the client predicts its own "
                   "moves and corrects them when the server answers. The first line is the start position, the second is "
                   "n, then n events: `INPUT seq dx` (apply dx at once and remember the input) or `ACK seq x` (the "
                   "server's position after processing every input up to seq). Complete `predict`: on an ACK, take the "
                   "server's x, forget inputs up to seq, then re-apply the inputs it has not confirmed yet. Keep the "
                   "unconfirmed inputs in a queue. The program prints the position shown after each event."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_PREDICT, stub(_SIG_PREDICT, _DOC_PREDICT, "[start] * len(events)")),
        "solution": "from collections import deque\n" + program(_IO_PREDICT, _SIG_PREDICT + f'''
    """{_DOC_PREDICT}"""
    pending = deque()                  # unconfirmed inputs, oldest first
    x, shown = start, []
    for kind, seq, value in events:
        if kind == "INPUT":
            pending.append((seq, value))
            x += value                 # predict immediately: no waiting for the server
        else:
            while pending and pending[0][0] <= seq:
                pending.popleft()      # confirmed by the server
            x = value + sum(dx for _, dx in pending)    # reconcile: server truth + replay
        shown.append(x)
    return shown
'''),
        "alt": _alt_predict,
        "explanation": ("Inputs are confirmed in order, so a FIFO queue holds the unconfirmed ones: an ACK pops from the "
                        "front, and replaying what remains on top of the server's position gives the corrected "
                        "prediction. The player sees instant movement, and the server still decides the truth, which "
                        "keeps the game fair."),
        "key_justification": "Client-side prediction with a queue of unacknowledged inputs.",
        "variants": variants(
            [({}, [("0\n6\nINPUT 1 5\nINPUT 2 5\nACK 1 5\nINPUT 3 -2\nACK 2 9\nACK 3 7\n", "5 10 10 8 7 7")]),
             ({}, [("10\n2\nINPUT 1 1\nACK 1 10\n", "11 10")]),
             ({}, [("0\n3\nINPUT 1 2\nINPUT 2 2\nACK 2 4\n", "2 4 4")])],
            _gen_predict, 8220,
            extra_hidden=[["3\n1\nINPUT 1 0\n"], ["0\n4\nINPUT 1 1\nINPUT 2 1\nINPUT 3 1\nACK 1 0\n"], ["-2\n2\nINPUT 1 -3\nACK 1 -5\n"]]),
    },
]

# ---------------------------------------------------------------- gam-5 Dhol Dash
_IO_BOARD = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    runs = []
    for i in range(n):
        player, score = data[1 + i].split()
        runs.append((player, int(score)))
    for rank, player, score in leaderboard(runs):
        print(rank, player, score)


main()
'''
_SIG_BOARD = "def leaderboard(runs):"
_DOC_BOARD = ("runs: (player, score) for every run. Keep each player's best score, order by score high to low (ties "
              "by name), and give equal scores the same rank, skipping the next ranks (1, 1, 3). Return [(rank, "
              "player, best score)].")


def _alt_board(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    best = {}
    for p, s in rows:
        best[p] = max(best.get(p, -1), int(s))
    order = sorted(best.items(), key=lambda kv: kv[0])
    order = sorted(order, key=lambda kv: kv[1], reverse=True)
    out = []
    for i, (p, s) in enumerate(order):
        rank = 1 + sum(1 for _, t in order if t > s)
        out.append(f"{rank} {p} {s}")
    return "\n".join(out)


def _gen_board(rng, size):
    n = {"small": 6, "medium": 25, "large": 60}[size]
    players = ["ritu", "aman", "zoya", "kabir", "meher", "dev", "isha", "om"]
    rows = [f"{rng.choice(players)} {rng.choice([800, 900, 950, 1000, 1000, 1200]) + rng.choice([0, 0, 50])}"
            for _ in range(n)]
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_TIMING = '''
def main():
    data = sys.stdin.read().split("\\n")
    offset = int(data[0])
    beats = list(map(int, data[1].split()))
    taps = list(map(int, data[2].split())) if data[2].strip() else []
    counts, accuracy = judge(beats, taps, offset)
    print("PERFECT", counts["PERFECT"], "GOOD", counts["GOOD"], "OK", counts["OK"], "MISS", counts["MISS"])
    print("accuracy", format(accuracy, ".1f") + "%")


main()
'''
_SIG_TIMING = "def judge(beats, taps, offset):"
_DOC_TIMING = ("beats and taps: times in ms, each in order. Subtract the audio latency `offset` from every tap. For each "
               "beat in order, match the unused tap closest to it within 150 ms (ties: the earlier tap); a gap of 30 "
               "or less is PERFECT, 80 or less GOOD, else OK; no tap is a MISS. Accuracy = (100 x PERFECT + 70 x GOOD "
               "+ 40 x OK) / beats. Return (counts, accuracy).")


def _alt_timing(stdin):
    rows = stdin.split("\n")
    off = int(rows[0])
    beats = [int(x) for x in rows[1].split()]
    taps = [int(x) - off for x in rows[2].split()]
    used = [False] * len(taps)
    c = {"PERFECT": 0, "GOOD": 0, "OK": 0, "MISS": 0}
    for b in beats:
        best = None
        for i, t in enumerate(taps):
            if not used[i] and abs(t - b) <= 150 and (best is None or abs(t - b) < abs(taps[best] - b)):
                best = i
        if best is None:
            c["MISS"] += 1
            continue
        used[best] = True
        g = abs(taps[best] - b)
        c["PERFECT" if g <= 30 else "GOOD" if g <= 80 else "OK"] += 1
    acc = (100 * c["PERFECT"] + 70 * c["GOOD"] + 40 * c["OK"]) / len(beats)
    return f"PERFECT {c['PERFECT']} GOOD {c['GOOD']} OK {c['OK']} MISS {c['MISS']}\naccuracy {format(acc, '.1f')}%"


def _gen_timing(rng, size):
    n = {"small": 6, "medium": 30, "large": 100}[size]
    gap = rng.choice([300, 400, 500])
    beats = [1000 + i * gap for i in range(n)]
    off = rng.choice([0, 20, 45])
    taps = sorted(b + off + rng.randint(-170, 170) for b in beats if rng.random() < 0.9)
    return f"{off}\n" + " ".join(map(str, beats)) + "\n" + " ".join(map(str, taps)) + "\n"


PROBLEMS["gam-5"] = [
    {
        "prompt": ("Dhol Dash's online leaderboard shows every run, so one player fills the top ten. Show each player "
                   "once. The first line is n, then n runs `player score`. Complete `leaderboard`: keep each player's "
                   "best score, order by score from high to low (ties by name), and give equal scores the same rank, "
                   "skipping ranks after a tie (1, 1, 3). The program prints `rank player score` lines."),
        "ds_topic": "sorting", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_BOARD, stub(_SIG_BOARD, _DOC_BOARD, "[(i + 1, p, s) for i, (p, s) in enumerate(runs)]")),
        "solution": program(_IO_BOARD, _SIG_BOARD + f'''
    """{_DOC_BOARD}"""
    best = {{}}
    for player, score in runs:
        best[player] = max(best.get(player, score), score)
    ordered = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
    out = []
    for i, (player, score) in enumerate(ordered):
        rank = out[-1][0] if out and out[-1][2] == score else i + 1      # 1, 1, 3 ("competition" ranking)
        out.append((rank, player, score))
    return out
'''),
        "alt": _alt_board,
        "explanation": ("A dictionary keeps each player's best, a sort with key (-score, name) orders them, and a tie "
                        "copies the previous rank while the position still counts, giving 1, 1, 3. Showing one entry per "
                        "player keeps the board readable and gives more players a reason to climb."),
        "key_justification": "Best-per-key aggregation, then sorting with competition ranking.",
        "variants": variants(
            [({}, [("5\nritu 900\naman 1000\nritu 1000\nzoya 800\naman 950\n", "1 aman 1000\n1 ritu 1000\n3 zoya 800")]),
             ({}, [("2\nom 5\nom 7\n", "1 om 7")]),
             ({}, [("3\nc 10\nb 20\na 30\n", "1 a 30\n2 b 20\n3 c 10")])],
            _gen_board, 8310,
            extra_hidden=[["3\nx 1\ny 1\nz 1\n"], ["4\nb 5\na 5\nc 9\nb 9\n"], ["1\nsolo 0\n"]]),
    },
    {
        "prompt": ("Players on Bluetooth earphones hear the beat late, so the game subtracts their audio latency before "
                   "judging taps. The first line is the offset in ms, the second has the beat times, the third the tap "
                   "times (both in order, ms; the tap line can be empty). Complete `judge`: subtract the offset from each "
                   "tap; for each beat in order, match the unused tap closest to it within 150 ms (ties: the earlier "
                   "tap). A gap of 30 ms or less is PERFECT, 80 or less GOOD, otherwise OK; no tap means MISS. Accuracy "
                   "is (100 x PERFECT + 70 x GOOD + 40 x OK) / beats. The program prints `PERFECT a GOOD b OK c MISS d` "
                   "and `accuracy x%` (one decimal)."),
        "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_TIMING, stub(_SIG_TIMING, _DOC_TIMING,
                                            '{"PERFECT": 0, "GOOD": 0, "OK": 0, "MISS": len(beats)}, 0.0')),
        "solution": program(_IO_TIMING, _SIG_TIMING + f'''
    """{_DOC_TIMING}"""
    adjusted = [t - offset for t in taps]
    used = [False] * len(adjusted)
    counts = {{"PERFECT": 0, "GOOD": 0, "OK": 0, "MISS": 0}}
    lo = 0                                           # taps before lo are too early for every later beat
    for beat in beats:
        while lo < len(adjusted) and adjusted[lo] < beat - 150:
            lo += 1
        best = None
        j = lo
        while j < len(adjusted) and adjusted[j] <= beat + 150:
            if not used[j] and (best is None or abs(adjusted[j] - beat) < abs(adjusted[best] - beat)):
                best = j
            j += 1
        if best is None:
            counts["MISS"] += 1
            continue
        used[best] = True
        gap = abs(adjusted[best] - beat)
        counts["PERFECT" if gap <= 30 else "GOOD" if gap <= 80 else "OK"] += 1
    accuracy = (100 * counts["PERFECT"] + 70 * counts["GOOD"] + 40 * counts["OK"]) / len(beats)
    return counts, accuracy
'''),
        "alt": _alt_timing,
        "explanation": ("Both lists are sorted, so a pointer skips taps that are already too early and only the taps "
                        "inside each beat's ±150 ms window are compared: close to O(beats + taps) instead of comparing "
                        "every pair. Subtracting the measured latency first is what makes Bluetooth players' timing "
                        "fair."),
        "key_justification": "Two-pointer matching of sorted event times within a window.",
        "variants": variants(
            [({}, [("20\n1000 1500 2000 2500\n1025 1600 2300 2510\n", "PERFECT 2 GOOD 1 OK 0 MISS 1\naccuracy 67.5%")]),
             ({}, [("0\n100 200\n\n", "PERFECT 0 GOOD 0 OK 0 MISS 2\naccuracy 0.0%")]),
             ({}, [("0\n500\n400 600\n", "PERFECT 0 GOOD 0 OK 1 MISS 0\naccuracy 40.0%")])],
            _gen_timing, 8320,
            extra_hidden=[["10\n100\n110\n"], ["0\n100 120\n110\n"], ["0\n1000 1100\n1050\n"]]),
    },
]

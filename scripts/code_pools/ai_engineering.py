"""Code pool for AI Engineering (aie-2 .. aie-5). Built and checked by scripts/build_code_pools.py."""
import json
import math

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}

# ---------------------------------------------------------------- aie-2 NyayaSetu
_IO_CHUNK = '''
def main():
    data = sys.stdin.read().split("\\n")
    size, overlap = map(int, data[0].split())
    words = data[1].split()
    starts = chunk_starts(len(words), size, overlap)
    print("chunks", len(starts))
    print(" ".join(map(str, starts)) if starts else "-")


main()
'''
_SIG_CHUNK = "def chunk_starts(word_count, size, overlap):"
_DOC_CHUNK = ("Return the start index of every chunk when a text of word_count words is cut into chunks of `size` "
              "words, each starting size - overlap words after the previous one, stopping once a chunk reaches the "
              "end of the text. An empty text has no chunks.")


def _alt_chunk(stdin):
    rows = stdin.split("\n")
    size, overlap = map(int, rows[0].split())
    n = len(rows[1].split())
    starts = []
    covered = 0
    s = 0
    while n and covered < n:
        starts.append(s)
        covered = min(n, s + size)
        s = s + size - overlap
    return f"chunks {len(starts)}\n{' '.join(map(str, starts)) or '-'}"


_WORDS = ("section act court notice cheque bounce complaint filed within thirty days of receiving information from "
          "the bank under negotiable instruments act the drawer must pay amount otherwise offence punishable").split()


def _gen_chunk(rng, size):
    count = {"small": 9, "medium": 40, "large": 120}[size]
    chunk = rng.randint(3, 12)
    overlap = rng.randint(0, chunk - 1)
    text = " ".join(rng.choice(_WORDS) for _ in range(count))
    return f"{chunk} {overlap}\n{text}\n"


PROBLEMS["aie-2"] = [
    {
        "prompt": ("NyayaSetu's retrieval pipeline cuts long acts into overlapping chunks of words, so a section split "
                   "across a boundary still appears whole in some chunk. The first line is `size overlap` (overlap is "
                   "smaller than size), the second is the text. Complete `chunk_starts`: chunks start at word 0 and "
                   "each next chunk starts size - overlap words later; stop as soon as a chunk reaches the last word. "
                   "The program prints `chunks k` and then the start index of each chunk, space-separated (or - for "
                   "an empty text)."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_CHUNK, stub(_SIG_CHUNK, _DOC_CHUNK, "[]")),
        "solution": program(_IO_CHUNK, _SIG_CHUNK + f'''
    """{_DOC_CHUNK}"""
    starts = []
    start = 0
    step = size - overlap
    while word_count > 0:
        starts.append(start)
        if start + size >= word_count:   # this chunk already reaches the last word
            break
        start += step
    return starts
'''),
        "alt": _alt_chunk,
        "explanation": ("Chunk starts are an arithmetic sequence with step size - overlap; the loop stops when a chunk "
                        "covers the last word, so no near-empty tail chunk is produced. Overlap costs extra chunks "
                        "(more embedding and storage) in exchange for not cutting a clause in half."),
        "key_justification": "Sliding window with step = size - overlap over the word array.",
        "variants": variants(
            [({}, [("4 1\na b c d e f g h i j\n", "chunks 3\n0 3 6")]),
             ({}, [("3 0\nthe drawer must pay the amount now\n", "chunks 3\n0 3 6")]),
             ({}, [("5 2\nsection one hundred thirty eight\n", "chunks 1\n0")])],
            _gen_chunk, 1110,
            extra_hidden=[["4 2\n\n"], ["2 1\nx y z\n"], ["6 5\na b c d e f g\n"]]),
    },
]

_IO_SEARCH = '''
def main():
    data = sys.stdin.read().split("\\n")
    k = int(data[0])
    n = int(data[1])
    docs = {}
    for i in range(n):
        parts = data[2 + i].split()
        docs[parts[0]] = " ".join(parts[1:])
    query = data[2 + n]
    ranked = keyword_search(docs, query, k)
    if not ranked:
        print("NONE")
    for doc_id, score in ranked:
        print(doc_id, score)


main()
'''
_SIG_SEARCH = "def keyword_search(docs, query, k):"
_DOC_SEARCH = ("docs: {doc_id: text}. Words are compared in lower case after stripping .,?!;:()\\\"' from both ends. "
               "A document's score is the sum, over the DISTINCT query words, of how many times that word appears "
               "in it. Return up to k (doc_id, score) with score > 0, highest first, ties by doc_id in string order.")
_PUNCT = ".,?!;:()\"'"


def _alt_search(stdin):
    rows = stdin.split("\n")
    k = int(rows[0])
    n = int(rows[1])
    clean = lambda w: w.lower().strip(_PUNCT)
    docs = []
    for row in rows[2:2 + n]:
        parts = row.split()
        docs.append((parts[0], [clean(w) for w in parts[1:]]))
    query = []
    for w in rows[2 + n].split():
        if clean(w) and clean(w) not in query:
            query.append(clean(w))
    scored = [(d, sum(words.count(q) for q in query)) for d, words in docs]
    scored = [s for s in scored if s[1] > 0]
    scored.sort(key=lambda s: s[0])
    scored.sort(key=lambda s: s[1], reverse=True)
    return "\n".join(f"{d} {s}" for d, s in scored[:k]) or "NONE"


def _gen_search(rng, size):
    n = {"small": 4, "medium": 10, "large": 25}[size]
    k = rng.randint(1, 4)
    rows = []
    for i in range(n):
        words = [rng.choice(_WORDS + ["Section", "138.", "Cheque,", "(bank)"]) for _ in range(rng.randint(3, 9))]
        rows.append(f"d{i + 1} " + " ".join(words))
    query = " ".join(rng.choice(_WORDS + ["Cheque?", "138"]) for _ in range(rng.randint(1, 4)))
    return f"{k}\n{n}\n" + "\n".join(rows) + f"\n{query}\n"


PROBLEMS["aie-2"].append({
    "prompt": ("Lawyers search for exact references like 'Section 138', which pure vector search can miss, so "
               "NyayaSetu adds a keyword score to its hybrid search. The first line is k, the second is n, then n "
               "lines `doc_id text...`, then one query line. Complete `keyword_search`: lower-case words and strip "
               "the characters . , ? ! ; : ( ) \" ' from both ends; a document's score is the sum, over the distinct "
               "query words, of how often each appears in it. The program prints up to k lines `doc_id score` with "
               "score above 0, highest first, ties by doc_id in string order, or NONE."),
    "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_SEARCH, stub(_SIG_SEARCH, _DOC_SEARCH, "[]")),
    "solution": program(_IO_SEARCH, _SIG_SEARCH + f'''
    """{_DOC_SEARCH}"""
    strip = ".,?!;:()\\"'"
    terms = {{w.lower().strip(strip) for w in query.split()}} - {{""}}
    scored = []
    for doc_id, text in docs.items():
        counts = {{}}
        for word in text.split():
            word = word.lower().strip(strip)
            counts[word] = counts.get(word, 0) + 1
        score = sum(counts.get(term, 0) for term in terms)
        if score > 0:
            scored.append((doc_id, score))
    scored.sort(key=lambda s: (-s[1], s[0]))
    return scored[:k]
'''),
    "alt": _alt_search,
    "explanation": ("A word-count dictionary per document (a tiny inverted index) scores a query in time proportional "
                    "to its words. Exact tokens such as '138' match here even when an embedding treats them as noise; "
                    "real systems use BM25, which also discounts very common words, and blend it with vector scores."),
    "key_justification": "Term-frequency scoring with a per-document word-count map.",
    "variants": variants(
        [({}, [("2\n3\ns138 Section 138 cheque bounce notice\ng12 guide cheque deposit\ns420 cheating section 420\n"
                "section 138 cheque\n", "s138 3\ng12 1")]),
         ({}, [("3\n2\na1 Notice. notice, NOTICE\nb2 complaint filed\nnotice notice\n", "a1 3")]),
         ({}, [("1\n2\nx tenant rent\ny landlord\neviction\n", "NONE")])],
        _gen_search, 1120,
        extra_hidden=[["5\n1\nz (bank) bank\nbank\n"], ["2\n2\nq1 act act\nq0 act act\nact\n"], ["1\n1\nw Section\n??\n"]]),
})

# ---------------------------------------------------------------- aie-3 GharSeva
_IO_JSON = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    for i in range(n):
        print(check_output(data[1 + i]))


main()
'''
_SIG_JSON = "def check_output(line):"
_DOC_JSON = ("line: one reply from the model. Return 'VALID', or the first problem found, checked in this order: "
             "'BAD_JSON' (not a JSON object), 'BAD_INTENT' (intent missing or not one of refund, booking_status, "
             "handoff), 'BAD_BOOKING_ID' (booking_id missing, not an integer (true/false do not count) or not > 0).")


def _alt_json(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out = []
    for line in rows[1:1 + n]:
        try:
            obj = json.loads(line)
        except ValueError:
            out.append("BAD_JSON")
            continue
        if type(obj) is not dict:
            out.append("BAD_JSON")
        elif obj.get("intent") not in ("refund", "booking_status", "handoff"):
            out.append("BAD_INTENT")
        elif type(obj.get("booking_id")) is not int or obj["booking_id"] <= 0:
            out.append("BAD_BOOKING_ID")
        else:
            out.append("VALID")
    return "\n".join(out)


def _gen_json(rng, size):
    n = {"small": 4, "medium": 10, "large": 25}[size]
    pool = ['{"intent": "refund", "booking_id": 17}', '{"intent": "booking_status", "booking_id": 3}',
            '{"intent": "handoff", "booking_id": 99}', '{"intent": "refund", "booking_id": 0}',
            '{"intent": "refund", "booking_id": true}', '{"intent": "refund", "booking_id": 2.5}',
            '{"intent": "refund"}', '{"booking_id": 5}', '{"intent": "give_coupon", "booking_id": 5}',
            '["refund", 5]', 'Sure, here you go: {"intent": "refund", "booking_id": 4}',
            '{"intent": "handoff", "booking_id": "12"}', '{"intent": "Refund", "booking_id": 8}', 'null',
            '{"intent": "booking_status", "booking_id": -4}', '{"intent": "refund", "booking_id": 12,}']
    return f"{n}\n" + "\n".join(rng.choice(pool) for _ in range(n)) + "\n"


PROBLEMS["aie-3"] = [
    {
        "prompt": ("GharSeva's assistant must reply with a JSON object before any tool runs, but the model sometimes "
                   "adds chatter or the wrong types, and one bad reply handed a refund to the wrong booking. The first "
                   "line is n, then n model replies, one per line. Complete `check_output` so each reply is checked in "
                   "this order: BAD_JSON if it is not a JSON object, BAD_INTENT if intent is missing or not one of "
                   "refund, booking_status, handoff, BAD_BOOKING_ID if booking_id is missing, not an integer (true "
                   "and false do not count) or not above 0; otherwise VALID. The program prints one verdict per line."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_JSON, stub(_SIG_JSON, _DOC_JSON, '"VALID"')),
        "solution": "import json\n" + program(_IO_JSON, _SIG_JSON + f'''
    """{_DOC_JSON}"""
    try:
        reply = json.loads(line)
    except ValueError:
        return "BAD_JSON"
    if not isinstance(reply, dict):
        return "BAD_JSON"
    if reply.get("intent") not in ("refund", "booking_status", "handoff"):
        return "BAD_INTENT"
    booking = reply.get("booking_id")
    if isinstance(booking, bool) or not isinstance(booking, int) or booking <= 0:
        return "BAD_BOOKING_ID"
    return "VALID"
'''),
        "alt": _alt_json,
        "explanation": ("Never act on model output you have not validated: parse strictly, check the value is an "
                        "object, check each field's allowed values and type, and refuse otherwise. In Python, bool is "
                        "a subclass of int, so true must be rejected explicitly. A schema validator does the same job "
                        "at scale."),
        "key_justification": "Validate structured LLM output strictly before any tool call.",
        "variants": variants(
            [({}, [('4\n{"intent": "refund", "booking_id": 42}\n{"intent": "refund", "booking_id": "42"}\n'
                    'Sure! Here is the JSON: {"intent": "handoff"}\n{"intent": "cancel_all", "booking_id": 7}\n',
                    "VALID\nBAD_BOOKING_ID\nBAD_JSON\nBAD_INTENT")]),
             ({}, [('3\n{"intent": "handoff", "booking_id": true}\n[1, 2]\n{"intent": "booking_status", '
                    '"booking_id": 8}\n', "BAD_BOOKING_ID\nBAD_JSON\nVALID")]),
             ({}, [('2\n{"booking_id": 5}\n{"intent": "refund", "booking_id": 0}\n', "BAD_INTENT\nBAD_BOOKING_ID")])],
            _gen_json, 1210,
            extra_hidden=[['1\n{"intent": "refund", "booking_id": 1e3}\n'], ["1\n\n"],
                          ['1\n{"intent": "refund", "booking_id": 5, "extra": 1}\n']]),
    },
]

_IO_COS = '''
def main():
    data = sys.stdin.read().split("\\n")
    dim, n = map(int, data[0].split())
    query = list(map(float, data[1].split()))
    docs = []
    for i in range(n):
        parts = data[2 + i].split()
        docs.append((parts[0], list(map(float, parts[1:1 + dim]))))
    best = best_match(query, docs)
    print("NONE" if best is None else f"{best[0]} {best[1]:.3f}")


main()
'''
_SIG_COS = "def best_match(query, docs):"
_DOC_COS = ("query: a vector; docs: list of (doc_id, vector). Return (doc_id, cosine similarity) of the most similar "
            "document, skipping zero vectors; similarities equal after rounding to 6 decimals tie, and ties go to "
            "the smaller doc_id in string order. Return None if no document can be scored (or the query is zero).")


def _alt_cos(stdin):
    rows = stdin.split("\n")
    dim, n = map(int, rows[0].split())
    q = [float(x) for x in rows[1].split()]
    qn = math.sqrt(sum(x * x for x in q))
    best = None
    if qn:
        for row in rows[2:2 + n]:
            parts = row.split()
            v = [float(x) for x in parts[1:1 + dim]]
            vn = math.sqrt(sum(x * x for x in v))
            if not vn:
                continue
            sim = sum(a * b for a, b in zip(q, v)) / (qn * vn)
            cand = (round(sim, 6), parts[0])
            if best is None or cand[0] > best[0] or (cand[0] == best[0] and cand[1] < best[1]):
                best = cand
    return "NONE" if best is None else f"{best[1]} {best[0]:.3f}"


def _gen_cos(rng, size):
    dim = {"small": 3, "medium": 5, "large": 8}[size]
    n = {"small": 4, "medium": 12, "large": 30}[size]
    q = [rng.randint(-3, 5) for _ in range(dim)]
    rows = [f"h{i + 1} " + " ".join(str(rng.randint(-4, 6)) for _ in range(dim)) for i in range(n)]
    return f"{dim} {n}\n" + " ".join(map(str, q)) + "\n" + "\n".join(rows) + "\n"


PROBLEMS["aie-3"].append({
    "prompt": ("After someone re-embedded half the help-centre index with a different model, GharSeva's search "
               "stopped making sense. First, check the scoring itself. The first line is `dim n`, the second is the "
               "query vector, then n lines `doc_id v1 ... v_dim`. Complete `best_match` using cosine similarity "
               "(dot product divided by the product of the lengths). Skip documents whose vector is all zeros; treat "
               "similarities equal after rounding to 6 decimals as a tie and break ties by doc_id in string order. "
               "The program prints `doc_id similarity` (3 decimals), or NONE if nothing can be scored."),
    "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_COS, stub(_SIG_COS, _DOC_COS, "None")),
    "solution": "import math\n" + program(_IO_COS, _SIG_COS + f'''
    """{_DOC_COS}"""
    q_len = math.sqrt(sum(x * x for x in query))
    if q_len == 0:
        return None
    best = None
    for doc_id, vector in docs:
        v_len = math.sqrt(sum(x * x for x in vector))
        if v_len == 0:
            continue
        sim = sum(a * b for a, b in zip(query, vector)) / (q_len * v_len)
        key = (-round(sim, 6), doc_id)
        if best is None or key < best[0]:
            best = (key, doc_id, sim)
    return None if best is None else (best[1], best[2])
'''),
    "alt": _alt_cos,
    "explanation": ("Cosine similarity compares direction, not length, so documents of different lengths score "
                    "fairly; normalising once makes it a dot product. It only means something when query and "
                    "documents come from the SAME embedding model, which is why mixing models broke search."),
    "key_justification": "Cosine similarity over vectors, with zero-vector and tie handling.",
    "variants": variants(
        [({}, [("2 3\n1 0\nd1 1 1\nd2 2 0\nd3 0 3\n", "d2 1.000")]),
         ({}, [("3 2\n1 2 2\na 2 4 4\nb 1 2 2\n", "a 1.000")]),
         ({}, [("2 2\n0 1\nx 0 0\ny 1 1\n", "y 0.707")])],
        _gen_cos, 1220,
        extra_hidden=[["2 1\n0 0\nz 1 1\n"], ["2 1\n1 1\nz 0 0\n"], ["2 2\n1 0\np -1 0\nq 0 1\n"]]),
})

# ---------------------------------------------------------------- aie-4 Arogya Vaani
_IO_ROUTE = '''
def main():
    data = sys.stdin.read().split("\\n")
    small_rate, large_rate = map(int, data[0].split())
    n = int(data[1])
    messages = []
    for i in range(n):
        message_id, category, tokens = data[2 + i].split()
        messages.append((message_id, category, int(tokens)))
    small, large, paise = route_cost(messages, small_rate, large_rate)
    print("small", small)
    print("large", large)
    print(f"cost Rs {paise // 100}.{paise % 100:02d}")


main()
'''
_SIG_ROUTE = "def route_cost(messages, small_rate, large_rate):"
_DOC_ROUTE = ("messages: list of (id, category, tokens). 'appointment' messages go to the small model, everything "
              "else to the large one. Each model charges its rate (paise) per STARTED block of 1,000 tokens. Return "
              "(messages to small, messages to large, total cost in paise).")


def _alt_route(stdin):
    rows = stdin.split("\n")
    small_rate, large_rate = map(int, rows[0].split())
    n = int(rows[1])
    small = large = paise = 0
    for row in rows[2:2 + n]:
        _, category, tokens = row.split()
        blocks = math.ceil(int(tokens) / 1000)
        if category == "appointment":
            small += 1
            paise += blocks * small_rate
        else:
            large += 1
            paise += blocks * large_rate
    return f"small {small}\nlarge {large}\ncost Rs {paise // 100}.{paise % 100:02d}"


def _gen_route(rng, size):
    n = {"small": 6, "medium": 25, "large": 70}[size]
    rates = (rng.randint(1, 5), rng.randint(20, 60))
    cats = ["appointment"] * 7 + ["symptoms", "medicine", "report"] * 1
    rows = [f"m{i + 1} {rng.choice(cats)} {rng.randint(50, 4200)}" for i in range(n)]
    return f"{rates[0]} {rates[1]}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["aie-4"] = [
    {
        "prompt": ("About 70% of Arogya Vaani's messages are simple appointment requests, so routing them to a small "
                   "model saves money. The first line is `small_rate large_rate` (paise per started block of 1,000 "
                   "tokens), the second is n, then n lines `id category tokens`. Messages with category appointment go "
                   "to the small model; all others go to the large model. Complete `route_cost`; the program prints "
                   "`small`, `large` (message counts) and `cost Rs X.YY`. Work in whole paise, not floats."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_ROUTE, stub(_SIG_ROUTE, _DOC_ROUTE, "0, 0, 0")),
        "solution": program(_IO_ROUTE, _SIG_ROUTE + f'''
    """{_DOC_ROUTE}"""
    small = large = paise = 0
    for _, category, tokens in messages:
        blocks = (tokens + 999) // 1000          # started blocks, in integers
        if category == "appointment":
            small += 1
            paise += blocks * small_rate
        else:
            large += 1
            paise += blocks * large_rate
    return small, large, paise
'''),
        "alt": _alt_route,
        "explanation": ("Routing by category sends the cheap, repetitive majority to the small model and keeps the "
                        "risky symptom questions on the large one. Integer ceiling division counts started blocks, "
                        "and keeping money in paise avoids floating-point rounding in bills."),
        "key_justification": "Cost routing with integer arithmetic for money.",
        "variants": variants(
            [({}, [("2 30\n3\nm1 appointment 800\nm2 symptoms 2500\nm3 appointment 1000\n",
                    "small 2\nlarge 1\ncost Rs 0.94")]),
             ({}, [("5 50\n2\na symptoms 1001\nb report 1\n", "small 0\nlarge 2\ncost Rs 1.50")]),
             ({}, [("3 40\n2\nx appointment 3000\ny appointment 2999\n", "small 2\nlarge 0\ncost Rs 0.18")])],
            _gen_route, 1310,
            extra_hidden=[["1 99\n0\n"], ["10 100\n1\nz medicine 100000\n"], ["4 25\n1\nq appointment 1\n"]]),
    },
]

_IO_PRF = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    pairs = [tuple(data[1 + i].split()) for i in range(n)]
    precision, recall, f1 = emergency_scores(pairs)
    print("precision", format(precision, ".2f"))
    print("recall", format(recall, ".2f"))
    print("f1", format(f1, ".2f"))


main()
'''
_SIG_PRF = "def emergency_scores(pairs):"
_DOC_PRF = ("pairs: list of (true_label, predicted_label). For the class 'emergency', return (precision, recall, "
            "F1). Any score whose denominator is 0 is 0.0.")


def _alt_prf(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    pred_e = [r for r in rows if r[1] == "emergency"]
    true_e = [r for r in rows if r[0] == "emergency"]
    tp = len([r for r in pred_e if r[0] == "emergency"])
    p = tp / len(pred_e) if pred_e else 0.0
    r = tp / len(true_e) if true_e else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return f"precision {p:.2f}\nrecall {r:.2f}\nf1 {f:.2f}"


def _gen_prf(rng, size):
    n = {"small": 8, "medium": 30, "large": 90}[size]
    labels = ["emergency", "today", "routine"]
    rows = []
    for _ in range(n):
        truth = rng.choices(labels, weights=[1, 2, 5])[0]
        guess = truth if rng.random() < 0.75 else rng.choice(labels)
        rows.append(f"{truth} {guess}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["aie-4"].append({
    "prompt": ("For triage, missing an emergency is far worse than a false alarm, so overall accuracy is the wrong "
               "headline. The first line is n, then n lines `true_label predicted_label` (emergency, today or "
               "routine) from the evaluation set. Complete `emergency_scores` for the emergency class: precision = "
               "TP / predicted emergencies, recall = TP / true emergencies, F1 = their harmonic mean; any score with "
               "a zero denominator is 0. The program prints `precision`, `recall` and `f1` to two decimals."),
    "ds_topic": "array", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_PRF, stub(_SIG_PRF, _DOC_PRF, "0.0, 0.0, 0.0")),
    "solution": program(_IO_PRF, _SIG_PRF + f'''
    """{_DOC_PRF}"""
    tp = fp = fn = 0
    for truth, guess in pairs:
        if guess == "emergency" and truth == "emergency":
            tp += 1
        elif guess == "emergency":
            fp += 1
        elif truth == "emergency":
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return precision, recall, f1
'''),
    "alt": _alt_prf,
    "explanation": ("Counting true positives, false positives and false negatives for one class in a single pass "
                    "gives every metric. Recall is the one to protect for emergencies; F1 = 2TP / (2TP + FP + FN) "
                    "is the harmonic mean written without dividing by zero."),
    "key_justification": "Per-class precision, recall and F1 from a confusion count.",
    "variants": variants(
        [({}, [("5\nemergency emergency\nemergency routine\nroutine emergency\nroutine routine\ntoday emergency\n",
                "precision 0.33\nrecall 0.50\nf1 0.40")]),
         ({}, [("3\nroutine routine\ntoday today\nroutine today\n", "precision 0.00\nrecall 0.00\nf1 0.00")]),
         ({}, [("4\nemergency emergency\nemergency emergency\nemergency today\ntoday today\n",
                "precision 1.00\nrecall 0.67\nf1 0.80")])],
        _gen_prf, 1320,
        extra_hidden=[["1\nemergency emergency\n"], ["2\nemergency routine\nemergency today\n"],
                      ["2\nroutine emergency\ntoday emergency\n"]]),
})

# ---------------------------------------------------------------- aie-5 Mitti Mitra
_IO_GUARD = '''
def main():
    data = sys.stdin.read().split("\\n")
    cap = int(data[0])
    confirmed = set(data[1].split()) - {"-"}
    n = int(data[2])
    orders = []
    for i in range(n):
        order_id, farmer, item, qty, price = data[3 + i].split()
        orders.append((order_id, farmer, item, int(qty), int(price)))
    approved, total = approve_orders(orders, confirmed, cap)
    print("approved", " ".join(approved) if approved else "NONE")
    print("total", total)


main()
'''
_SIG_GUARD = "def approve_orders(orders, confirmed, cap):"
_DOC_GUARD = ("orders: list of (order_id, farmer, item, qty, price) proposed by the assistant. Approve an order only "
              "if the farmer has confirmed (is in `confirmed`) and qty x price <= cap. Return (approved order ids "
              "in input order, their total value).")


def _alt_guard(stdin):
    rows = stdin.split("\n")
    cap = int(rows[0])
    ok_farmers = [f for f in rows[1].split() if f != "-"]
    n = int(rows[2])
    ids, total = [], 0
    for row in rows[3:3 + n]:
        oid, farmer, _, qty, price = row.split()
        value = int(qty) * int(price)
        if farmer in ok_farmers and value <= cap:
            ids.append(oid)
            total += value
    return f"approved {' '.join(ids) or 'NONE'}\ntotal {total}"


def _gen_guard(rng, size):
    n = {"small": 5, "medium": 20, "large": 50}[size]
    farmers = [f"f{i}" for i in range(1, 9)]
    confirmed = rng.sample(farmers, rng.randint(0, 5))
    cap = rng.choice([3000, 5000, 10000])
    rows = [f"o{i + 1} {rng.choice(farmers)} {rng.choice(['urea', 'dap', 'potash', 'seeds'])} {rng.randint(1, 12)} "
            f"{rng.choice([270, 300, 1350, 1400, 900])}" for i in range(n)]
    return f"{cap}\n{' '.join(confirmed) or '-'}\n{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["aie-5"] = [
    {
        "prompt": ("Mitti Mitra's assistant can place fertiliser orders, so every proposed order passes a guard in "
                   "code, not in the prompt. The first line is the per-order cap in rupees, the second lists farmers "
                   "who confirmed by reply (or -), the third is n, then n proposed orders `order_id farmer item qty "
                   "price`. Complete `approve_orders`: approve an order only if its farmer confirmed and qty x price "
                   "is at most the cap. The program prints `approved` followed by the approved ids in input order (or "
                   "NONE), then `total` (their combined value)."),
        "ds_topic": "hash_map", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_GUARD, stub(_SIG_GUARD, _DOC_GUARD, "[o[0] for o in orders], 0")),
        "solution": program(_IO_GUARD, _SIG_GUARD + f'''
    """{_DOC_GUARD}"""
    approved, total = [], 0
    for order_id, farmer, _, qty, price in orders:
        value = qty * price
        if farmer in confirmed and value <= cap:      # set membership: O(1)
            approved.append(order_id)
            total += value
    return approved, total
'''),
        "alt": _alt_guard,
        "explanation": ("An agent's actions with real-world effects need hard checks outside the model: an explicit "
                        "confirmation and a spending limit enforced in code, so a confused or manipulated model cannot "
                        "place orders. The starter approves everything, which is exactly the unsafe default."),
        "key_justification": "Guard tool actions with code-level checks (confirmation, limits).",
        "variants": variants(
            [({}, [("5000\nf1 f3\n3\no1 f1 urea 4 300\no2 f2 urea 1 300\no3 f3 dap 5 1400\n", "approved o1\ntotal 1200")]),
             ({}, [("1000\n-\n2\no1 f1 seeds 1 10\no2 f2 seeds 1 10\n", "approved NONE\ntotal 0")]),
             ({}, [("2700\nf5\n2\no1 f5 urea 9 300\no2 f5 potash 2 1350\n", "approved o1 o2\ntotal 5400")])],
            _gen_guard, 1410,
            extra_hidden=[["100\nf1\n0\n"], ["10\nf1 f2\n1\no9 f2 urea 1 11\n"], ["300\nf4\n1\no1 f4 urea 1 300\n"]]),
    },
]

_IO_PLAN = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    needs = {}
    for i in range(n):
        tool, deps = data[1 + i].split()
        needs[tool] = [] if deps == "-" else deps.split(",")
    order = plan(needs)
    print(" ".join(order) if order is not None else "CYCLE")


main()
'''
_SIG_PLAN = "def plan(needs):"
_DOC_PLAN = ("needs: {tool: [tools that must run before it]}; every listed tool is a key. Return an order to run "
             "every tool so each runs after all its prerequisites, always picking the alphabetically first tool that "
             "is ready; return None if the dependencies contain a cycle.")


def _alt_plan(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    needs = {}
    for row in rows[1:1 + n]:
        tool, deps = row.split()
        needs[tool] = set() if deps == "-" else set(deps.split(","))
    done = []
    while len(done) < len(needs):
        ready = sorted(t for t in needs if t not in done and needs[t] <= set(done))
        if not ready:
            return "CYCLE"
        done.append(ready[0])
    return " ".join(done)


def _gen_plan(rng, size):
    n = {"small": 5, "medium": 10, "large": 18}[size]
    tools = rng.sample(["lookup_item", "check_stock", "confirm_farmer", "get_price", "place_order", "send_receipt",
                        "check_weather", "find_scheme", "translate", "transcribe", "fetch_mandi", "verify_kyc",
                        "check_credit", "book_delivery", "notify_agronomist", "log_action", "rate_reply",
                        "summarise"], n)
    rows = []
    for i, tool in enumerate(tools):
        earlier = tools[:i]
        deps = rng.sample(earlier, rng.randint(0, min(3, len(earlier)))) if earlier else []
        rows.append((tool, deps))
    if rng.random() < 0.3 and n > 2:            # sometimes add a back edge -> a cycle
        a = rows[0]
        rows[0] = (a[0], a[1] + [tools[-1]])
    rng.shuffle(rows)
    return f"{n}\n" + "\n".join(f"{t} {','.join(d) or '-'}" for t, d in rows) + "\n"


PROBLEMS["aie-5"].append({
    "prompt": ("The agent plans several tool calls for one request, and some need others' results first (an order "
               "needs the stock check and the farmer's confirmation). The first line is n, then n lines `tool deps`, "
               "where deps is a comma-separated list of tools that must run first, or - for none. Complete `plan` "
               "using a topological sort: repeatedly run the alphabetically first tool whose prerequisites have all "
               "run. The program prints the tools in run order, space-separated, or CYCLE if no valid order exists."),
    "ds_topic": "graph", "difficulty": 2, "skills": ["Python"],
    "starter": program(_IO_PLAN, stub(_SIG_PLAN, _DOC_PLAN, "list(needs)")),
    "solution": "import heapq\n" + program(_IO_PLAN, _SIG_PLAN + f'''
    """{_DOC_PLAN}"""
    waiting = {{tool: len(deps) for tool, deps in needs.items()}}
    unlocks = {{tool: [] for tool in needs}}
    for tool, deps in needs.items():
        for dep in deps:
            unlocks[dep].append(tool)
    ready = [tool for tool, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        tool = heapq.heappop(ready)
        order.append(tool)
        for nxt in unlocks[tool]:
            waiting[nxt] -= 1
            if waiting[nxt] == 0:
                heapq.heappush(ready, nxt)
    return order if len(order) == len(needs) else None
'''),
    "alt": _alt_plan,
    "explanation": ("Tools and prerequisites form a directed graph; a valid run order is a topological order. Kahn's "
                    "algorithm counts unmet prerequisites per tool and releases tools as their count reaches zero; a "
                    "min-heap makes the choice deterministic. If some tools never become ready, there is a cycle and "
                    "the agent must not run the plan."),
    "key_justification": "Topological sort (Kahn's algorithm) with cycle detection.",
    "variants": variants(
        [({}, [("4\nplace_order check_stock,confirm_farmer\ncheck_stock lookup_item\nlookup_item -\n"
                "confirm_farmer -\n", "confirm_farmer lookup_item check_stock place_order")]),
         ({}, [("3\na b\nb c\nc a\n", "CYCLE")]),
         ({}, [("3\ntranslate transcribe\nreply translate\ntranscribe -\n", "transcribe translate reply")])],
        _gen_plan, 1420,
        extra_hidden=[["1\nsolo -\n"], ["2\nx x\ny -\n"], ["4\nd -\nc -\nb -\na -\n"]]),
})

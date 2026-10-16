"""Code pool for Machine Learning Engineering (mle-2 .. mle-5). Built and checked by scripts/build_code_pools.py."""
from collections import Counter

from scripts.code_pools._kit import program, stub, variants

PROBLEMS = {}


def _fraud_rows(rng, n):
    rows = []
    for _ in range(n):
        fraud = 1 if rng.random() < 0.15 else 0
        score = min(100, max(0, int(rng.gauss(70 if fraud else 25, 18))))
        rows.append(f"{score} {fraud}")
    return rows


# ---------------------------------------------------------------- mle-2 PaySetu fraud
_IO_CONF = '''
def main():
    data = sys.stdin.read().split("\\n")
    threshold = int(data[0])
    n = int(data[1])
    rows = [tuple(map(int, data[2 + i].split())) for i in range(n)]
    tp, fp, fn, tn = confusion(rows, threshold)
    print("TP", tp, "FP", fp, "FN", fn, "TN", tn)
    print("alerts", tp + fp)


main()
'''
_SIG_CONF = "def confusion(rows, threshold):"
_DOC_CONF = ("rows: list of (score 0-100, is_fraud 0/1). A transaction is flagged when score >= threshold. "
             "Return (TP, FP, FN, TN).")


def _alt_conf(stdin):
    rows = stdin.split("\n")
    t = int(rows[0])
    n = int(rows[1])
    pairs = [r.split() for r in rows[2:2 + n]]
    flagged = [int(s) >= t for s, _ in pairs]
    fraud = [y == "1" for _, y in pairs]
    tp = sum(f and y for f, y in zip(flagged, fraud))
    fp = sum(f and not y for f, y in zip(flagged, fraud))
    fn = sum(y and not f for f, y in zip(flagged, fraud))
    tn = n - tp - fp - fn
    return f"TP {tp} FP {fp} FN {fn} TN {tn}\nalerts {tp + fp}"


def _gen_conf(rng, size):
    n = {"small": 10, "medium": 40, "large": 120}[size]
    return f"{rng.choice([40, 50, 60, 70])}\n{n}\n" + "\n".join(_fraud_rows(rng, n)) + "\n"


_IO_PICK = '''
def main():
    data = sys.stdin.read().split("\\n")
    target = int(data[0])
    n = int(data[1])
    rows = [tuple(map(int, data[2 + i].split())) for i in range(n)]
    best = pick_threshold(rows, target)
    if best is None:
        print("NONE")
    else:
        print("threshold", best[0], "precision", best[1], "recall", best[2])


main()
'''
_SIG_PICK = "def pick_threshold(rows, target):"
_DOC_PICK = "Return (threshold, precision %, recall %) or None; percentages rounded down to whole numbers."


def _alt_pick(stdin):
    rows = stdin.split("\n")
    target = int(rows[0])
    n = int(rows[1])
    pairs = [tuple(map(int, r.split())) for r in rows[2:2 + n]]
    total = sum(y for _, y in pairs)
    best = None
    for t in sorted({s for s, _ in pairs}):
        flagged = [y for s, y in pairs if s >= t]
        tp = sum(flagged)
        if flagged and tp * 100 >= target * len(flagged):
            cand = (tp, t, len(flagged))
            if best is None or (cand[0], cand[1]) > (best[0], best[1]):
                best = cand
    if best is None:
        return "NONE"
    tp, t, fl = best
    return f"threshold {t} precision {tp * 100 // fl} recall {tp * 100 // total if total else 0}"


def _gen_pick(rng, size):
    n = {"small": 10, "medium": 40, "large": 120}[size]
    return f"{rng.choice([50, 60, 70, 80])}\n{n}\n" + "\n".join(_fraud_rows(rng, n)) + "\n"


PROBLEMS["mle-2"] = [
    {
        "prompt": ("PaySetu's model gives each UPI transaction a fraud score from 0 to 100, and the fraud team reviews "
                   "every transaction scored at or above a threshold. The first line is the threshold, the second is n, "
                   "then n lines `score is_fraud` (1 if the transaction was later confirmed as fraud). Complete "
                   "`confusion`. The program prints `TP x FP x FN x TN x` and then `alerts k`, the number of flagged "
                   "transactions the team must review."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_CONF, stub(_SIG_CONF, _DOC_CONF, "0, 0, 0, 0")),
        "solution": program(_IO_CONF, _SIG_CONF + f'''
    """{_DOC_CONF}"""
    tp = fp = fn = tn = 0
    for score, fraud in rows:
        flagged = score >= threshold
        if flagged and fraud:
            tp += 1
        elif flagged:
            fp += 1
        elif fraud:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn
'''),
        "alt": _alt_conf,
        "explanation": ("One pass over the scores fills the four cells of the confusion matrix. With 0.2% fraud, "
                        "accuracy is dominated by TN and says almost nothing; the alert count (TP + FP) is the review "
                        "workload, which is what a threshold actually trades against missed fraud (FN)."),
        "key_justification": "Confusion-matrix counting at a decision threshold.",
        "variants": variants(
            [({}, [("50\n5\n80 1\n55 0\n40 1\n10 0\n50 1\n", "TP 2 FP 1 FN 1 TN 1\nalerts 3")]),
             ({}, [("90\n4\n91 0\n89 1\n95 1\n20 0\n", "TP 1 FP 1 FN 1 TN 1\nalerts 2")]),
             ({}, [("30\n3\n5 0\n10 0\n29 1\n", "TP 0 FP 0 FN 1 TN 2\nalerts 0")])],
            _gen_conf, 2010,
            extra_hidden=[["0\n2\n0 0\n0 1\n"], ["101\n2\n100 1\n100 0\n"], ["60\n1\n60 0\n"]]),
    },
    {
        "prompt": ("The fraud team needs at least P% precision, or reviewers drown in false alarms, but wants to catch "
                   "as much fraud as possible. The first line is P, the second is n, then n lines `score is_fraud`. "
                   "Try every distinct score as the threshold (flag score >= threshold). Complete `pick_threshold`: "
                   "among thresholds that flag at least one transaction and reach precision >= P%, choose the one with "
                   "the highest recall; if several tie, the highest threshold. The program prints `threshold t "
                   "precision p recall r` with p and r as whole percentages rounded down, or NONE. Sort once and sweep "
                   "instead of recounting for every threshold."),
        "ds_topic": "sorting", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_PICK, stub(_SIG_PICK, _DOC_PICK, "None")),
        "solution": program(_IO_PICK, _SIG_PICK + f'''
    """{_DOC_PICK}"""
    total_fraud = sum(fraud for _, fraud in rows)
    ordered = sorted(rows, key=lambda r: -r[0])
    best = None                      # (tp, threshold, flagged)
    tp = flagged = 0
    i = 0
    while i < len(ordered):
        score = ordered[i][0]
        while i < len(ordered) and ordered[i][0] == score:   # every row with this score joins together
            tp += ordered[i][1]
            flagged += 1
            i += 1
        if tp * 100 >= target * flagged:                    # precision >= target, in integers
            if best is None or tp > best[0]:                 # more recall wins; a tie keeps the higher threshold
                best = (tp, score, flagged)
    if best is None:
        return None
    tp, score, flagged = best
    recall = tp * 100 // total_fraud if total_fraud else 0
    return score, tp * 100 // flagged, recall
'''),
        "alt": _alt_pick,
        "explanation": ("Sorting by score from high to low means lowering the threshold only ever adds transactions, "
                        "so running counts give precision and recall at every threshold in one sweep: O(n log n) "
                        "instead of O(n^2). Comparing tp x 100 >= P x flagged keeps the precision check exact. Rows "
                        "with the same score must join together, because a threshold cannot split them."),
        "key_justification": "Sort once, sweep thresholds with cumulative counts.",
        "variants": variants(
            [({}, [("60\n6\n90 1\n80 1\n70 0\n60 1\n50 0\n40 1\n", "threshold 40 precision 66 recall 100")]),
             ({}, [("100\n4\n95 1\n90 0\n85 1\n80 1\n", "threshold 95 precision 100 recall 33")]),
             ({}, [("80\n3\n70 0\n60 0\n50 1\n", "NONE")])],
            _gen_pick, 2020,
            extra_hidden=[["50\n2\n40 1\n40 0\n"], ["0\n2\n10 0\n20 0\n"], ["90\n3\n99 1\n99 1\n98 0\n"]]),
    },
]

# ---------------------------------------------------------------- mle-3 BazaarCart
_IO_FOLDS = '''
def main():
    n, initial, horizon = map(int, sys.stdin.read().split()[:3])
    folds = time_folds(n, initial, horizon)
    if not folds:
        print("NONE")
    for k, (train_end, test_start, test_end) in enumerate(folds, 1):
        print(f"fold {k} train 1-{train_end} test {test_start}-{test_end}")


main()
'''
_SIG_FOLDS = "def time_folds(n, initial, horizon):"
_DOC_FOLDS = ("Days are 1..n. Fold 1 trains on days 1..initial and tests on the next `horizon` days; each later fold "
              "moves the cut-off forward by `horizon`. Stop before a test window would go past day n. Return "
              "[(train_end, test_start, test_end)].")


def _alt_folds(stdin):
    n, init, h = map(int, stdin.split()[:3])
    out, k = [], 0
    for end in range(init, n + 1, h):
        if end + h > n:
            break
        k += 1
        out.append(f"fold {k} train 1-{end} test {end + 1}-{end + h}")
    return "\n".join(out) or "NONE"


def _gen_folds(rng, size):
    n = {"small": 20, "medium": 90, "large": 730}[size]
    horizon = rng.choice([1, 7]) if size != "large" else rng.choice([30, 60, 90])
    return f"{n} {rng.randint(n // 4, n // 2)} {horizon}\n"


_IO_LAGS = '''
def main():
    data = sys.stdin.read().split()
    n = int(data[0])
    sales = list(map(int, data[1:1 + n]))
    for day, lag7, roll7 in lag_features(sales):
        print(day, "NA" if lag7 is None else lag7, "NA" if roll7 is None else format(roll7, ".1f"))


main()
'''
_SIG_LAGS = "def lag_features(sales):"
_DOC_LAGS = ("sales[0] is day 1. For each day d return (d, sales 7 days earlier, mean of the 7 days BEFORE d), using "
             "None while fewer than 7 earlier days exist. Never use day d's own sales.")


def _alt_lags(stdin):
    data = stdin.split()
    n = int(data[0])
    s = [int(x) for x in data[1:1 + n]]
    out = []
    for i in range(n):
        if i >= 7:
            out.append(f"{i + 1} {s[i - 7]} {format(sum(s[i - 7:i]) / 7, '.1f')}")
        else:
            out.append(f"{i + 1} NA NA")
    return "\n".join(out)


def _gen_lags(rng, size):
    n = {"small": 9, "medium": 20, "large": 40}[size]
    base = rng.randint(20, 200)
    vals = [max(0, base + rng.randint(-30, 30) + (25 if d % 7 in (5, 6) else 0)) for d in range(n)]
    return f"{n}\n" + " ".join(map(str, vals)) + "\n"


PROBLEMS["mle-3"] = [
    {
        "prompt": ("BazaarCart's offline score was inflated because the data was shuffled before splitting, so the model "
                   "trained on days after the ones it was tested on. Build time-ordered folds instead. The input is "
                   "`n initial horizon`: n days of history, the first training window, and the forecast window. "
                   "Complete `time_folds`: fold 1 trains on days 1..initial and tests on the next `horizon` days; each "
                   "later fold extends training by `horizon` days and tests on the following `horizon` days, stopping "
                   "before a test window runs past day n. The program prints `fold k train 1-a test b-c` per fold, or "
                   "NONE."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_FOLDS, stub(_SIG_FOLDS, _DOC_FOLDS, "[]")),
        "solution": program(_IO_FOLDS, _SIG_FOLDS + f'''
    """{_DOC_FOLDS}"""
    folds = []
    train_end = initial
    while train_end + horizon <= n:
        folds.append((train_end, train_end + 1, train_end + horizon))
        train_end += horizon
    return folds
'''),
        "alt": _alt_folds,
        "explanation": ("An expanding window always trains on the past and tests on the future, exactly as the model "
                        "will be used, so the score cannot benefit from information that would not exist at forecast "
                        "time. Each fold is just index arithmetic on the ordered days."),
        "key_justification": "Time-series validation with expanding, forward-only folds.",
        "variants": variants(
            [({}, [("10 4 2\n", "fold 1 train 1-4 test 5-6\nfold 2 train 1-6 test 7-8\nfold 3 train 1-8 test 9-10")]),
             ({}, [("30 14 7\n", "fold 1 train 1-14 test 15-21\nfold 2 train 1-21 test 22-28")]),
             ({}, [("5 5 1\n", "NONE")])],
            _gen_folds, 2110,
            extra_hidden=[["6 5 1\n"], ["3 1 1\n"], ["100 99 2\n"]]),
    },
    {
        "prompt": ("The forecast is made each evening for the next day, so a feature may only use days that are already "
                   "over. The first line is n, the second has n daily sales (day 1 first). Complete `lag_features`: for "
                   "each day d, the sales 7 days earlier and the mean of the 7 days just before d (days d-7 to d-1), "
                   "never including day d itself; both are NA until 7 earlier days exist. Keep a sliding window instead "
                   "of re-adding 7 numbers every day. The program prints `day lag7 roll7`, with roll7 to one decimal."),
        "ds_topic": "queue", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_LAGS, stub(_SIG_LAGS, _DOC_LAGS, "[]")),
        "solution": "from collections import deque\n" + program(_IO_LAGS, _SIG_LAGS + f'''
    """{_DOC_LAGS}"""
    window, total, out = deque(), 0, []
    for day, value in enumerate(sales, 1):
        if len(window) == 7:
            out.append((day, window[0], total / 7))    # the window holds days day-7 .. day-1 only
        else:
            out.append((day, None, None))
        window.append(value)                          # today joins AFTER its features were built
        total += value
        if len(window) > 7:
            total -= window.popleft()
    return out
'''),
        "alt": _alt_lags,
        "explanation": ("A deque holds exactly the last 7 finished days and a running total gives the mean in O(1) per "
                        "day. The order matters: the features for day d are read before day d is added, which is what "
                        "keeps the target out of its own features (the leakage that inflated the offline score)."),
        "key_justification": "Point-in-time lag and rolling features with a sliding window.",
        "variants": variants(
            [({}, [("9\n10 20 30 40 50 60 70 80 90\n",
                    "1 NA NA\n2 NA NA\n3 NA NA\n4 NA NA\n5 NA NA\n6 NA NA\n7 NA NA\n8 10 40.0\n9 20 50.0")]),
             ({}, [("8\n7 7 7 7 7 7 7 100\n", "1 NA NA\n2 NA NA\n3 NA NA\n4 NA NA\n5 NA NA\n6 NA NA\n7 NA NA\n8 7 7.0")]),
             ({}, [("3\n5 6 7\n", "1 NA NA\n2 NA NA\n3 NA NA")])],
            _gen_lags, 2120,
            extra_hidden=[["1\n0\n"], ["10\n0 0 0 0 0 0 7 0 0 0\n"], ["8\n1 2 3 4 5 6 7 8\n"]]),
    },
]

# ---------------------------------------------------------------- mle-4 VaaniCare
_IO_NGRAM = '''
def main():
    data = sys.stdin.read().split("\\n")
    n, k = map(int, data[0].split())
    for gram, count in top_ngrams(data[1], n, k):
        print(gram, count)


main()
'''
_SIG_NGRAM = "def top_ngrams(text, n, k):"
_DOC_NGRAM = ("Lower-case the text, join its words with '_' and put one '_' at each end. Return the k most frequent "
              "character n-grams as (gram, count), most frequent first, ties in string order.")


def _alt_ngram(stdin):
    rows = stdin.split("\n")
    n, k = map(int, rows[0].split())
    s = "_" + "_".join(rows[1].lower().split()) + "_"
    c = Counter(s[i:i + n] for i in range(len(s) - n + 1))
    ranked = sorted(c.items(), key=lambda kv: kv[0])
    ranked = sorted(ranked, key=lambda kv: kv[1], reverse=True)
    return "\n".join(f"{g} {v}" for g, v in ranked[:k])


_HINGLISH = ["recharge", "nahi", "hua", "paisa", "kat", "gaya", "network", "nahi", "aa", "raha", "sim", "band",
             "bill", "zyada", "aaya", "please", "help", "karo", "data", "khatam"]


def _gen_ngram(rng, size):
    words = {"small": 4, "medium": 12, "large": 40}[size]
    text = " ".join(rng.choice(_HINGLISH) for _ in range(words))
    if rng.random() < 0.5:
        text = text.upper()
    return f"{rng.choice([2, 3, 4])} {rng.randint(2, 6)}\n{text}\n"


_IO_F1 = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    pairs = [tuple(data[1 + i].split()) for i in range(n)]
    per_class, macro = class_f1(pairs)
    for label, f1 in per_class:
        print(label, format(f1, ".2f"))
    print("macro", format(macro, ".2f"))


main()
'''
_SIG_F1 = "def class_f1(pairs):"
_DOC_F1 = ("pairs: list of (true_intent, predicted_intent). For every intent that appears in either column, return "
           "(intent, F1) sorted by intent, and the macro F1 (plain mean over those intents). F1 = 2TP/(2TP+FP+FN), "
           "0 when TP is 0.")


def _alt_f1(stdin):
    rows = [r.split() for r in stdin.split("\n")[1:] if r.strip()]
    labels = sorted({x for r in rows for x in r})
    out, total = [], 0.0
    for lab in labels:
        tp = sum(1 for t, p in rows if t == lab and p == lab)
        fp = sum(1 for t, p in rows if p == lab and t != lab)
        fn = sum(1 for t, p in rows if t == lab and p != lab)
        f = 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)
        total += f
        out.append(f"{lab} {format(f, '.2f')}")
    return "\n".join(out + [f"macro {format(total / len(labels), '.2f')}"])


_INTENTS = ["billing", "network", "recharge_failure", "sim_swap", "plan_change", "roaming"]


def _gen_f1(rng, size):
    n = {"small": 8, "medium": 30, "large": 60}[size]
    rows = []
    for _ in range(n):
        truth = rng.choices(_INTENTS, weights=[6, 5, 4, 1, 3, 1])[0]
        guess = truth if rng.random() < 0.7 else rng.choice(_INTENTS)
        rows.append(f"{truth} {guess}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["mle-4"] = [
    {
        "prompt": ("Hinglish tickets mix spellings like 'nahi', 'nhi' and 'nai', so word features break; character "
                   "n-grams survive them. The first line is `n k`, the second is one ticket. Complete `top_ngrams`: "
                   "lower-case the text, join the words with `_` and add one `_` at the start and end (so `Nahi hua` "
                   "becomes `_nahi_hua_`), then count every run of n consecutive characters. The program prints the k "
                   "most frequent as `gram count`, most frequent first, ties in string order."),
        "ds_topic": "string", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_NGRAM, stub(_SIG_NGRAM, _DOC_NGRAM, "[]")),
        "solution": program(_IO_NGRAM, _SIG_NGRAM + f'''
    """{_DOC_NGRAM}"""
    padded = "_" + "_".join(text.lower().split()) + "_"
    counts = {{}}
    for i in range(len(padded) - n + 1):
        gram = padded[i:i + n]
        counts[gram] = counts.get(gram, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
'''),
        "alt": _alt_ngram,
        "explanation": ("Slide a window of n characters over the padded string and count each slice in a dictionary. "
                        "The underscores mark word edges, so prefixes and suffixes become features too. Spelling "
                        "variants of the same word still share most of their n-grams, which is why character n-gram "
                        "models are a strong, fast baseline for noisy code-mixed text."),
        "key_justification": "Character n-gram counting with string slicing.",
        "variants": variants(
            [({}, [("3 3\nna na\n", "_na 2\nna_ 2\na_n 1")]),
             ({}, [("2 2\nSIM band\n", "_b 1\n_s 1")]),
             ({}, [("4 1\nhua hua hua\n", "_hua 3")])],
            _gen_ngram, 2210,
            extra_hidden=[["2 5\na\n"], ["3 4\nRecharge  NAHI   hua\n"], ["5 2\nbill bill\n"]]),
    },
    {
        "prompt": ("Fraud and SIM-swap tickets are rare, so overall accuracy hides how badly they are routed. Report F1 "
                   "for each intent and the macro average, where every intent counts equally. The first line is n, then "
                   "n lines `true_intent predicted_intent`. Complete `class_f1`: for every intent that appears in either "
                   "column, F1 = 2TP / (2TP + FP + FN), or 0 when TP is 0. The program prints `intent f1` sorted by "
                   "intent, then `macro m`, all to two decimals."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_F1, stub(_SIG_F1, _DOC_F1, "[], 0.0")),
        "solution": program(_IO_F1, _SIG_F1 + f'''
    """{_DOC_F1}"""
    tp, fp, fn = {{}}, {{}}, {{}}
    labels = set()
    for truth, guess in pairs:
        labels.update((truth, guess))
        if truth == guess:
            tp[truth] = tp.get(truth, 0) + 1
        else:
            fp[guess] = fp.get(guess, 0) + 1
            fn[truth] = fn.get(truth, 0) + 1
    per_class = []
    for label in sorted(labels):
        t = tp.get(label, 0)
        f1 = 2 * t / (2 * t + fp.get(label, 0) + fn.get(label, 0)) if t else 0.0
        per_class.append((label, f1))
    macro = sum(f for _, f in per_class) / len(per_class)
    return per_class, macro
'''),
        "alt": _alt_f1,
        "explanation": ("Three dictionaries count true positives, false positives and false negatives per intent in "
                        "one pass. Macro F1 averages the intents equally, so a rare queue that is routed badly pulls "
                        "the score down, where accuracy (dominated by billing) would hide it."),
        "key_justification": "Per-class counting with hash maps; macro averaging for imbalance.",
        "variants": variants(
            [({}, [("4\nbilling billing\nbilling network\nnetwork network\nfraud billing\n",
                    "billing 0.50\nfraud 0.00\nnetwork 0.67\nmacro 0.39")]),
             ({}, [("3\nroaming roaming\nroaming roaming\nsim_swap sim_swap\n", "roaming 1.00\nsim_swap 1.00\nmacro 1.00")]),
             ({}, [("2\nbilling network\nnetwork billing\n", "billing 0.00\nnetwork 0.00\nmacro 0.00")])],
            _gen_f1, 2220,
            extra_hidden=[["1\nx x\n"], ["3\na b\nb b\nc b\n"], ["4\nfraud fraud\nfraud billing\nbilling billing\nbilling billing\n"]]),
    },
]

# ---------------------------------------------------------------- mle-5 DhanSetu
_IO_LABEL = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    loans = []
    for i in range(n):
        parts = data[1 + i].split()
        loans.append((parts[0], list(map(int, parts[1:]))))
    labels = default_labels(loans)
    for loan_id, label in labels:
        print(loan_id, label)
    defaults = sum(label for _, label in labels)
    print("rate", format(100 * defaults / n, ".1f") + "%")


main()
'''
_SIG_LABEL = "def default_labels(loans):"
_DOC_LABEL = ("loans: list of (loan_id, days past due at each month end from month 1 on). Label 1 if the loan was 90 "
              "or more days past due at any of the FIRST 12 month ends, else 0. Return [(loan_id, label)].")


def _alt_label(stdin):
    rows = stdin.split("\n")
    n = int(rows[0])
    out, d = [], 0
    for r in rows[1:1 + n]:
        parts = r.split()
        lab = 1 if max([int(x) for x in parts[1:13]] or [0]) >= 90 else 0
        d += lab
        out.append(f"{parts[0]} {lab}")
    return "\n".join(out + [f"rate {format(100 * d / n, '.1f')}%"])


def _gen_label(rng, size):
    n = {"small": 4, "medium": 15, "large": 40}[size]
    rows = []
    for i in range(n):
        months = rng.choice([12, 12, 14, 18])
        dpd, vals = 0, []
        for _ in range(months):
            dpd = dpd + 30 if rng.random() < 0.15 else (0 if rng.random() < 0.5 else dpd)
            vals.append(min(dpd, 180))
        rows.append(f"L{i + 1:03d} " + " ".join(map(str, vals)))
    return f"{n}\n" + "\n".join(rows) + "\n"


_IO_CAL = '''
def main():
    data = sys.stdin.read().split("\\n")
    n = int(data[0])
    rows = [tuple(map(int, data[1 + i].split())) for i in range(n)]
    for low, high, count, predicted, observed in calibration(rows):
        print(f"{low}-{high} {count} {predicted:.1f} {observed:.1f}")


main()
'''
_SIG_CAL = "def calibration(rows):"
_DOC_CAL = ("rows: list of (predicted default probability as a whole percent 0-100, defaulted 0/1). Bucket b holds "
            "predictions with min(p // 10, 9) == b. For each non-empty bucket in order return (low, high, count, mean "
            "predicted %, observed default %); bucket 9 covers 90-100.")


def _alt_cal(stdin):
    rows = [tuple(map(int, r.split())) for r in stdin.split("\n")[1:] if r.strip()]
    out = []
    for b in range(10):
        group = [(p, y) for p, y in rows if min(p // 10, 9) == b]
        if not group:
            continue
        hi = 100 if b == 9 else b * 10 + 9
        pred = sum(p for p, _ in group) / len(group)
        obs = 100 * sum(y for _, y in group) / len(group)
        out.append(f"{b * 10}-{hi} {len(group)} {pred:.1f} {obs:.1f}")
    return "\n".join(out)


def _gen_cal(rng, size):
    n = {"small": 8, "medium": 40, "large": 120}[size]
    rows = []
    for _ in range(n):
        p = rng.randint(0, 100)
        rows.append(f"{p} {1 if rng.random() < min(1.0, p / 100 * 1.3) else 0}")
    return f"{n}\n" + "\n".join(rows) + "\n"


PROBLEMS["mle-5"] = [
    {
        "prompt": ("DhanSetu defines default as being 90 or more days past due within 12 months of the loan. Older "
                   "loans have more than 12 month-end records, and counting a delinquency in month 14 would label the "
                   "wrong thing. The first line is n, then n lines `loan_id dpd1 dpd2 ...` (days past due at each month "
                   "end). Complete `default_labels`: label 1 if any of the first 12 values is 90 or more, else 0. The "
                   "program prints `loan_id label` for each loan, then `rate x%`, the share of defaults to one decimal."),
        "ds_topic": "array", "difficulty": 1, "skills": ["Python"],
        "starter": program(_IO_LABEL, stub(_SIG_LABEL, _DOC_LABEL, "[(loan_id, 0) for loan_id, _ in loans]")),
        "solution": program(_IO_LABEL, _SIG_LABEL + f'''
    """{_DOC_LABEL}"""
    out = []
    for loan_id, dpd in loans:
        window = dpd[:12]                 # the label window: months 1-12 only
        out.append((loan_id, 1 if any(d >= 90 for d in window) else 0))
    return out
'''),
        "alt": _alt_label,
        "explanation": ("The label must match the definition exactly: slicing the first 12 values keeps later "
                        "delinquencies out. A label that peeks past the window makes older loans look riskier than "
                        "newer ones for no real reason, and the model learns loan age instead of risk."),
        "key_justification": "Label construction over a fixed outcome window (array slicing).",
        "variants": variants(
            [({}, [("3\nL1 0 0 30 60 90 0 0 0 0 0 0 0\nL2 0 0 0 0 0 0 0 0 0 0 0 0\nL3 0 0 0 0 0 0 0 0 0 0 0 89\n",
                    "L1 1\nL2 0\nL3 0\nrate 33.3%")]),
             ({}, [("2\nA 0 0 0 0 0 0 0 0 0 0 0 0 120 150\nB 30 60 90 120 0 0 0 0 0 0 0 0\n", "A 0\nB 1\nrate 50.0%")]),
             ({}, [("1\nZ 90 0 0 0 0 0 0 0 0 0 0 0\n", "Z 1\nrate 100.0%")])],
            _gen_label, 2310,
            extra_hidden=[["1\nQ 0 0 0 0 0 0 0 0 0 0 0 0\n"], ["2\nM 89 89 89 89 89 89 89 89 89 89 89 89 90\nN 0 0 0 0 0 0 0 0 0 0 0 91\n"],
                          ["3\nX 0 0 0 0 0 0 0 0 0 0 0 0\nY 0 0 0 0 0 0 0 0 0 0 0 0\nW 0 0 0 0 0 0 0 0 0 0 0 0\n"]]),
    },
    {
        "prompt": ("Loan officers will read the predicted default probability as a real chance, so it must be "
                   "calibrated. Build a calibration table. The first line is n, then n lines `predicted defaulted` "
                   "(predicted as a whole percent 0-100, defaulted 1 or 0). Complete `calibration`: put each prediction "
                   "in bucket min(p // 10, 9), so the last bucket is 90-100. For each non-empty bucket, in order, the "
                   "program prints `low-high count predicted observed`: the mean predicted percent and the actual "
                   "default percent, both to one decimal."),
        "ds_topic": "hash_map", "difficulty": 2, "skills": ["Python"],
        "starter": program(_IO_CAL, stub(_SIG_CAL, _DOC_CAL, "[]")),
        "solution": program(_IO_CAL, _SIG_CAL + f'''
    """{_DOC_CAL}"""
    buckets = {{}}
    for predicted, defaulted in rows:
        b = min(predicted // 10, 9)
        count, total_p, total_y = buckets.get(b, (0, 0, 0))
        buckets[b] = (count + 1, total_p + predicted, total_y + defaulted)
    out = []
    for b in sorted(buckets):
        count, total_p, total_y = buckets[b]
        high = 100 if b == 9 else b * 10 + 9
        out.append((b * 10, high, count, total_p / count, 100 * total_y / count))
    return out
'''),
        "alt": _alt_cal,
        "explanation": ("Group predictions by bucket in a dictionary and compare the mean prediction with the observed "
                        "rate in each. A calibrated model has the two close in every bucket; a gap shows where its "
                        "probabilities cannot be read as real chances, which matters when officers act on them."),
        "key_justification": "Grouped aggregation into buckets for a calibration table.",
        "variants": variants(
            [({}, [("5\n5 0\n15 0\n12 1\n95 1\n100 1\n", "0-9 1 5.0 0.0\n10-19 2 13.5 50.0\n90-100 2 97.5 100.0")]),
             ({}, [("4\n40 0\n45 1\n41 0\n49 1\n", "40-49 4 43.8 50.0")]),
             ({}, [("3\n0 0\n9 0\n10 1\n", "0-9 2 4.5 0.0\n10-19 1 10.0 100.0")])],
            _gen_cal, 2320,
            extra_hidden=[["1\n100 0\n"], ["2\n89 1\n90 1\n"], ["3\n33 0\n33 0\n33 1\n"]]),
    },
]

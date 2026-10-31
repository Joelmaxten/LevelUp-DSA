"""
Verified progression: a roadmap step is completed by passing a short check, not by ticking a box.

The check for a step is built from the knowledge-base passages the step itself was built from (its topic_refs point at
KB chunks by node_id), so the questions test exactly what the student was told to study. Two kinds of question are made
straight from the passage text, with no model involved, and are therefore grounded by construction:

  term        "Which topic does this describe?  '____ is the step where the agent ...'"   options: topic titles
  definition  "Which statement describes 'Tool Invocation'?"                               options: first sentences
                                                                                           of different passages

Optionally (STEP_CHECK_LLM) a model also writes questions. Every model question must quote, word for word, the sentence
of the passage that supports its answer; verify_llm_item() rejects it unless the quote really is in that passage, the
correct option is supported by the quote, and no wrong option is supported better. Only verified questions are stored.

Everything here is pure (no database, no Flask) except generate_llm_items(), which calls llm_client. The routes in
app/routes/step_checks.py store items and attempts and enforce the rules computed by step_states().
"""
import functools
import hashlib
import json
import random
import re
from datetime import timedelta

OPTION_IDS = ("a", "b", "c", "d")
BLANK = "____"
MAX_SOURCES = 8
MIN_SENTENCE_WORDS = 7
MAX_SENTENCE_WORDS = 45
# Part of every step_key: raise it when build_items() changes, so steps get freshly built questions (old attempts keep
# pointing at the old rows, which stay).
ITEMS_VERSION = 3
PLURAL_VERBS = {"are", "were", "have", "do", "allow", "help", "let", "make", "enable", "provide", "include", "use",
                "store", "perform", "represent", "describe", "refer", "contain", "define", "act", "run", "give"}

STOPWORDS = set("""a an the and or but if then else of to in on at by for with from into onto over under as is are was were be
been being it its this that these those there their they them you your we our he she his her not no can could should would
will may might must do does did done have has had having than so such also very more most less least any all each every
some many much other another same about which what when where who whom how why while because between through during
""".split())


def step_key(career_path, step):
    """Stable id for 'this step of this path' (and this version of the question builder): the same base-roadmap step
    gets the same key for every student."""
    refs = sorted(r for r in (step.get("topic_refs") or []) if isinstance(r, str))
    raw = json.dumps([ITEMS_VERSION, career_path, (step.get("title") or "").strip().lower(), refs], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def flat_steps(steps):
    """[(step_index, step)] in roadmap order, with the same index rule as routes/roadmap.py's step_indexes()."""
    if isinstance(steps, list):
        flat, key = steps, "step_number"
    else:
        flat, key = [s for phase in steps.get("phases", []) for s in phase.get("steps", [])], "global_step_index"
    return [(s.get(key) if s.get(key) is not None else i + 1, s) for i, s in enumerate(flat)]


def chunk_lookup(chunks, career_path=None):
    """{node_id: chunk}. When a node appears more than once, the chunk tagged with this career path wins."""
    found = {}
    for c in chunks:
        node = c.get("node_id") if isinstance(c, dict) else None
        if not node or not c.get("text"):
            continue
        tagged = career_path is not None and career_path in (c.get("career_paths") or [])
        if node not in found or (tagged and career_path not in (found[node].get("career_paths") or [])):
            found[node] = c
    return found


def step_sources(step, lookup, limit=MAX_SOURCES):
    """The KB passages a step was built from: [{node_id, title, text, resources}] in topic_refs order."""
    out, seen = [], set()
    for ref in step.get("topic_refs") or []:
        c = lookup.get(ref)
        if c and ref not in seen and c.get("title"):
            seen.add(ref)
            out.append({"node_id": ref, "title": c["title"].strip(), "text": body_text(c), "resources": c.get("resources") or []})
        if len(out) >= limit:
            break
    return out


def body_text(chunk):
    """The passage without the title that roadmap.sh chunks start with."""
    text, title = (chunk.get("text") or "").strip(), (chunk.get("title") or "").strip()
    if title and text.lower().startswith(title.lower()):
        text = text[len(title):].lstrip(" :-–—\n")
    return re.sub(r"\s+", " ", text).strip()


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def topic_name(title):
    """'What is a Prompt?' -> 'Prompt'; 'What are Embeddings?' -> 'Embeddings'; other titles unchanged."""
    name = re.sub(r"^\s*(what|who)\s+(is|are)\s+(an?\s+|the\s+)?", "", title or "", flags=re.IGNORECASE)
    name = name.strip().rstrip("?").strip()
    return name[:1].upper() + name[1:] if name else (title or "").strip()


def title_aliases(title):
    """'Acting / Tool Invocation (Agents)' -> ['Acting / Tool Invocation (Agents)', 'Acting', 'Tool Invocation', 'Agents'];
    a question title also yields its bare term ('What is a Prompt?' -> 'Prompt')."""
    name = topic_name(title)
    parts = [title, name] + re.split(r"\s*/\s*|\s*\(|\)", name)
    parts += [singular(p) for p in parts]
    return sorted({p.strip() for p in parts if len(p.strip()) >= 3}, key=len, reverse=True)


def singular(name):
    """'Functions' -> 'Function', 'Libraries' -> 'Library'; 'Process', 'Kubernetes'-style words ending in ss/us/is stay."""
    name = (name or "").strip()
    if len(name) > 4 and name.lower().endswith("ies"):
        return name[:-3] + "y"
    if len(name) > 4 and name.lower().endswith("s") and not name.lower().endswith(("ss", "us", "is", "es")):
        return name[:-1]
    return name


def mask_title(sentence, title):
    """Blank out every name of the topic in a sentence. Returns None when nothing was masked or a name survives."""
    masked, hit = sentence, False
    for alias in title_aliases(title):
        pattern = re.compile(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", re.IGNORECASE)
        if pattern.search(masked):
            masked, hit = pattern.sub(BLANK, masked), True
    if not hit:
        return None
    # "____ (____) ____ improves" -> "____ improves": one blank per mention, however many parts the name has
    return re.sub(re.escape(BLANK) + r"(?:[\s()\-/&,]*" + re.escape(BLANK) + r")+", BLANK, masked)


def definition_sentence(source):
    """The first sentence of the passage that is a usable definition (length bounds, mentions the topic by name)."""
    for s in sentences(source["text"])[:3]:
        words = len(s.split())
        if MIN_SENTENCE_WORDS <= words <= MAX_SENTENCE_WORDS:
            return s
    return None


def neutral_description(source):
    """A source's definition sentence with its own name removed, so it can be an option without giving itself away."""
    return _neutral_description(source["title"], source["text"])


@functools.lru_cache(maxsize=20000)
def _neutral_description(title, text):
    source = {"title": title, "text": text}
    s = definition_sentence(source)
    if not s:
        return None
    masked = mask_title(s, source["title"])
    if masked:
        # "Operators are ..." -> "They are ...", "A loop is ..." -> "It is ...": the pronoun agrees with the verb after the name.
        lead = re.match(r"^(?:(?:a|an|the)\s+)?" + re.escape(BLANK) + r"(?:s\b)?\s+(\w+)", masked, flags=re.IGNORECASE)
        pronoun = "They" if lead and lead.group(1).lower() in PLURAL_VERBS else "It"
        masked = re.sub(r"^(?:(?:a|an|the)\s+)?" + re.escape(BLANK) + r"(?:s\b)?", pronoun, masked, flags=re.IGNORECASE)
        masked = re.sub(r"\b(?:a|an|the)\s+" + re.escape(BLANK), "it", masked, flags=re.IGNORECASE)
        return masked.replace(BLANK, "it")
    return s


def _pronoun_open(text):
    """True when a description opens with the pronoun that replaced the topic's name ("It ..." / "They ...")."""
    return text.startswith("It ") or text.startswith("They ")


def _options(correct_text, distractor_texts, rng):
    texts = [correct_text] + distractor_texts[:3]
    if len(texts) < 4 or len({t.lower() for t in texts}) < 4:
        return None, None
    order = list(range(4))
    rng.shuffle(order)
    options = [{"id": OPTION_IDS[pos], "text": texts[i]} for pos, i in enumerate(order)]
    correct_id = OPTION_IDS[order.index(0)]
    return options, correct_id


def build_items(sources, distractor_pool, seed):
    """Questions made straight from the passages (no model). sources: this step's passages; distractor_pool: passages
    of the same roadmap's other steps (wrong options come from this step first, then from those). Deterministic for
    a given seed. Returns [{kind, prompt, options, correct, evidence, source_title, source_node}]."""
    rng = random.Random(seed)
    items = []
    pool = sources + [p for p in distractor_pool if p["node_id"] not in {s["node_id"] for s in sources}]
    for src in sources:
        evidence = definition_sentence(src)
        if not evidence:
            continue
        others = [p for p in pool if p["node_id"] != src["node_id"] and p["title"].lower() != src["title"].lower()]
        near = [p for p in others if p in sources]
        far = [p for p in others if p not in sources]
        rng.shuffle(near)
        rng.shuffle(far)
        candidates = near + far

        masked = mask_title(evidence, src["title"])
        if masked and BLANK in masked:
            titles = []
            for p in candidates:
                name = topic_name(p["title"])
                if name.lower() not in {t.lower() for t in titles} and name.lower() not in masked.lower() \
                        and name.lower() != topic_name(src["title"]).lower():
                    titles.append(name)
            options, correct = _options(topic_name(src["title"]), titles, rng)
            if options:
                items.append({"kind": "term", "prompt": f"Which topic does this describe?\n“{masked}”",
                              "options": options, "correct": correct, "evidence": evidence,
                              "source_title": src["title"], "source_node": src["node_id"]})

        own = neutral_description(src)
        descs = []
        for p in candidates:
            d = neutral_description(p)
            if d and d.lower() != (own or "").lower() and d not in descs:
                descs.append(d)
        if own:
            # Wrong options that open the same way as the right one ("It ..." or not), so the opening gives nothing away.
            same = [d for d in descs if _pronoun_open(d) == _pronoun_open(own)]
            descs = same + [d for d in descs if d not in same]
            options, correct = _options(own, descs, rng)
            names_the_answer = any(re.search(r"(?<!\w)" + re.escape(a.lower()) + r"(?!\w)", own.lower())
                                   for a in title_aliases(src["title"]))
            if options and not names_the_answer and \
                    any(_pronoun_open(o["text"]) == _pronoun_open(own) for o in options if o["id"] != correct):
                items.append({"kind": "definition", "prompt": f"Which statement describes “{topic_name(src['title'])}”?",
                              "options": options, "correct": correct, "evidence": evidence,
                              "source_title": src["title"], "source_node": src["node_id"]})
    return items


# ----------------------------------------------------------------------------------------- model-written questions

def content_words(text):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9+#.\-]*", (text or "").lower()) if w not in STOPWORDS and len(w) > 2}


def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[‘’“”\"']", "", text or "")).strip().lower()


def support(option, evidence):
    """Share of the option's content words that appear in the evidence (0..1)."""
    words = content_words(option)
    return len(words & content_words(evidence)) / len(words) if words else 0.0


def verify_llm_item(item, sources_by_title, min_support=0.5):
    """(item for storage, None) when a model-written question is supported by its source passage, else (None, reason).
    item: {source, question, options: [4 strings], answer_index, evidence}."""
    if not isinstance(item, dict):
        return None, "not_an_object"
    src = sources_by_title.get(_norm(item.get("source")))
    if src is None:
        return None, "unknown_source"
    question, options, evidence = item.get("question"), item.get("options"), item.get("evidence")
    answer = item.get("answer_index")
    if not isinstance(question, str) or not 10 <= len(question) <= 300:
        return None, "bad_question"
    if not isinstance(options, list) or len(options) != 4 or not all(isinstance(o, str) and 2 <= len(o) <= 220 for o in options):
        return None, "bad_options"
    if len({_norm(o) for o in options}) != 4:
        return None, "duplicate_options"
    if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer <= 3:
        return None, "bad_answer_index"
    if not isinstance(evidence, str) or len(evidence.strip()) < 25 or _norm(evidence) not in _norm(src["text"]):
        return None, "evidence_not_in_source"
    scores = [support(o, evidence) for o in options]
    if scores[answer] < min_support:
        return None, "answer_not_supported"
    if any(scores[i] >= scores[answer] for i in range(4) if i != answer):
        return None, "ambiguous"
    stored = [{"id": OPTION_IDS[i], "text": o.strip()} for i, o in enumerate(options)]
    return {"kind": "llm", "prompt": question.strip(), "options": stored, "correct": OPTION_IDS[answer],
            "evidence": evidence.strip(), "source_title": src["title"], "source_node": src["node_id"]}, None


def llm_prompt(step, sources):
    passages = "\n\n".join(f"SOURCE: {s['title']}\n{s['text'][:1200]}" for s in sources[:4])
    return (
        "Write multiple-choice questions that check whether a student understood the passages below.\n"
        "Rules: use ONLY facts stated in the passages; 4 options each, exactly one correct; wrong options must be "
        "plausible but contradicted by or absent from the passage; for each question copy, word for word, the one "
        "sentence from the passage that proves the answer into \"evidence\"; \"source\" is the SOURCE title it came "
        "from. Write 2 questions per source at most, 6 in total at most.\n"
        'Reply with JSON only: {"questions": [{"source": "...", "question": "...", "options": ["...", "...", "...", '
        '"..."], "answer_index": 0, "evidence": "..."}]}\n\n'
        f"STEP: {step.get('title', '')}\n\n{passages}"
    )


def generate_llm_items(step, sources, budget_s=30):
    """Model-written questions that passed verify_llm_item(). Returns (items, rejected reasons). Never raises."""
    from app.pipeline import llm_client
    try:
        reply = llm_client.generate("fast", llm_prompt(step, sources), json_mode=True, budget_s=budget_s)
    except Exception:
        return [], ["llm_failed"]
    parsed = reply.get("parsed") if isinstance(reply, dict) else None
    raw = parsed.get("questions") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return [], ["unparseable"]
    by_title = {_norm(s["title"]): s for s in sources}
    items, rejected = [], []
    for q in raw[:8]:
        item, reason = verify_llm_item(q, by_title)
        if item:
            items.append(item)
        else:
            rejected.append(reason)
    return items, rejected


# ----------------------------------------------------------------------------------------------------- attempts

def choose_questions(items, n, seen_ids, rng):
    """Pick n items: model-written first, then ones this student has not been shown yet, one per source where possible.
    items: [{"id", "kind", "source_node"}]. Returns the chosen ids."""
    def rank(it):
        return (it["id"] in seen_ids, it["kind"] != "llm", rng.random())
    ordered = sorted(items, key=rank)
    chosen, used_sources = [], set()
    for it in ordered:                      # first pass: spread over sources
        if len(chosen) < n and it["source_node"] not in used_sources:
            chosen.append(it["id"])
            used_sources.add(it["source_node"])
    for it in ordered:                      # then fill up
        if len(chosen) < n and it["id"] not in chosen:
            chosen.append(it["id"])
    return chosen


def grade(questions, answers, items_by_id):
    """questions: the attempt's [{item}]; answers: {str(item id): option id}. Returns (score, [{item, correct}])."""
    results, score = [], 0
    for q in questions:
        item = items_by_id.get(q["item"])
        given = answers.get(str(q["item"])) if isinstance(answers, dict) else None
        ok = bool(item) and given == item["correct"]
        score += ok
        results.append({"item": q["item"], "correct": ok, "given": given})
    return score, results


def step_states(indexes, completed, checkable, attempts, reviews, now, cfg):
    """The rules, per step. indexes: roadmap order; completed: set of done indexes; checkable: set of indexes that have
    a check; attempts: {index: [{"passed", "mode", "submitted_at"}] oldest first, submitted only}; reviews: {index:
    [{"required_at", "reviewed_at"}]}. cfg: {cooldown_s, review_after}.
    Returns {index: {status, verified, can_test_out, cooldown_until, review_required, checkable}}.
    status: done | open | locked. A step is open when it is the first step or the step before it is done."""
    states, prev_done = {}, True
    for idx in indexes:
        done = idx in completed
        tries = attempts.get(idx, [])
        verified = any(a["passed"] for a in tries)
        status = "done" if done else ("open" if prev_done else "locked")
        cooldown_until = None
        fails = [a for a in tries if a["passed"] is False]
        if fails and not done:
            until = fails[-1]["submitted_at"] + timedelta(seconds=cfg["cooldown_s"])
            cooldown_until = until if until > now else None
        streak = 0
        last_review = max((r["reviewed_at"] for r in reviews.get(idx, []) if r["reviewed_at"]), default=None)
        for a in reversed(tries):
            if a["passed"] or (last_review and a["submitted_at"] <= last_review):
                break
            streak += 1
        review_required = (not done) and streak >= cfg["review_after"]
        states[idx] = {
            "status": status,
            "verified": done and verified,
            "checkable": idx in checkable,
            "can_test_out": status == "locked" and idx in checkable,
            "cooldown_until": cooldown_until,
            "review_required": review_required,
            "fail_streak": streak,
        }
        prev_done = done
    return states

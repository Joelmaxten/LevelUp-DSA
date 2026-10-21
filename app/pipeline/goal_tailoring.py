"""
What the Goals answers change, in plain words, for the "Here's what we'll tailor" card on the Goals page.

Every line here describes something the app really does with conversation_signals; keep it in step with:
  - scenario_engine.HARDER_GOALS / EASIER_GOALS (which coding problem a scenario leans towards),
  - scenario_engine.GOAL_STAGES (the "Matches your goal" star on scenarios),
  - roadmap_personalizer._SIGNAL_LINES / ADDITIONAL_NOTES_KEY (what the roadmap's personal note is told),
  - roadmap_generator._SIGNAL_QUERY_KEYS (the same signals, for full generation).
The career-path ranking comes from the quiz only (profile_builder.ADJUSTMENT_RULES is empty on purpose), so the
summary says so instead of implying the answers moved it.

tailoring_summary(signals) -> {"items": [{"area", "text"}], "match_note": str}. Pure.
"""
from app.pipeline.conversation_data import ADDITIONAL_NOTES_KEY, CONVERSATION_QUESTIONS, OPTION_SIGNALS
from app.pipeline.scenario_engine import EASIER_GOALS, GOAL_STAGES, HARDER_GOALS

MATCH_NOTE = ("Your career match comes from the quiz only. These answers shape how we help you, "
              "not which path fits you.")

STAGE_WORDS = {
    "foundations": "foundation",
    "core_decision": "core-decision",
    "debugging": "debugging",
    "trade_offs": "trade-off",
    "end_to_end": "end-to-end",
}


def _option_text(key, value):
    """The answer the student picked, as shown to them (for example 'Startup'), or None."""
    for (question_id, option), signal in OPTION_SIGNALS.items():
        if signal == (key, value):
            return CONVERSATION_QUESTIONS[question_id]["options"][option]
    return None


def _join(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def tailoring_summary(signals):
    signals = signals or {}
    items = []
    goal = signals.get("goal")

    if goal in EASIER_GOALS:
        items.append({"area": "Coding problems",
                      "text": "Each scenario's coding question leans towards the gentler of its two problems, "
                              "so you can build confidence first."})
    elif goal in HARDER_GOALS:
        items.append({"area": "Coding problems",
                      "text": "Each scenario's coding question leans towards the harder of its two problems, "
                              "to get you interview-ready."})

    stages = [STAGE_WORDS[s] for s in ("foundations", "core_decision", "debugging", "trade_offs", "end_to_end")
              if s in GOAL_STAGES.get(goal, ())]
    if stages:
        items.append({"area": "Scenarios",
                      "text": f"{_join(stages).capitalize()} scenarios are starred as matching your goal."})

    roadmap_bits = []
    goal_text = _option_text("goal", goal) if goal else None
    if goal_text:
        roadmap_bits.append(f"your goal ({goal_text.lower()})")
    avoid = signals.get("avoid")
    if avoid and avoid != "none":
        text = _option_text("avoid", avoid)
        if text:
            roadmap_bits.append(f"what you want to avoid ({text.lower()})")
    company = signals.get("target_company")
    if company and company != "unsure":
        text = _option_text("target_company", company)
        if text:
            roadmap_bits.append(f"the companies you're aiming for ({text.split(' (')[0].lower()})")
    roadmap_text = ""
    if roadmap_bits:
        roadmap_text = f"Your roadmap's personal note and priority steps take into account {_join(roadmap_bits)}."
    if signals.get(ADDITIONAL_NOTES_KEY):
        roadmap_text += (" Your note is passed to it as background too." if roadmap_text
                         else "Your note is passed to the roadmap as background about you.")
    if roadmap_text:
        items.append({"area": "Roadmap", "text": roadmap_text})

    return {"items": items, "match_note": MATCH_NOTE}

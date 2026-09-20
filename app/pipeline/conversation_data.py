"""
Post-quiz conversation data: a short set of fixed questions capturing signals
the adaptive quiz cannot — IT vs non-traditional interest, things to avoid,
target company type, and near-term goal. Pure data — no logic here.

Unlike career_quiz_data.py, these questions do not map to CAREER_PATHS scores.
They produce a flat signal dict that gets attached to the student profile and
passed as context into the LLM roadmap-generation prompt later.
"""

CONVERSATION_QUESTIONS = {
    "C1": {
        "text": "Are you specifically interested in traditional IT/software roles, "
                "or open to tech-adjacent non-traditional paths (like AI entrepreneurship, "
                "product management, EdTech, FinTech)?",
        "options": {
            "A": "Traditional IT/software roles only",
            "B": "Open to non-traditional tech-adjacent paths",
            "C": "Not sure yet — open to either",
        },
    },
    "C2": {
        "text": "Is there anything you'd specifically want to avoid in your career?",
        "options": {
            "A": "Too much repetitive/routine work",
            "B": "Constant high-pressure deadlines",
            "C": "Heavy people-management responsibility",
            "D": "Nothing specific comes to mind",
        },
    },
    "C3": {
        "text": "What's your target company type?",
        "options": {
            "A": "Startup",
            "B": "Product-based company",
            "C": "Service-based company (TCS/Infosys/Accenture-style)",
            "D": "Not sure yet",
        },
    },
    "C4": {
        "text": "What's your main goal for the next 1-2 years?",
        "options": {
            "A": "Get placed in any good company",
            "B": "Get placed in a specific target role",
            "C": "Build strong fundamentals before placements",
            "D": "Explore before deciding",
        },
    },
}

# Each (question, option) maps to one signal key/value pair.
# Unlike OPTION_SIGNALS in career_quiz_data.py (which maps to a list of career
# paths for scoring), this maps to a single flat tag — these signals are not
# scored against anything, just carried forward as profile context.
OPTION_SIGNALS = {
    ("C1", "A"): ("it_track", "traditional"),
    ("C1", "B"): ("it_track", "non_traditional"),
    ("C1", "C"): ("it_track", "open"),

    ("C2", "A"): ("avoid", "repetitive_work"),
    ("C2", "B"): ("avoid", "high_pressure_deadlines"),
    ("C2", "C"): ("avoid", "people_management"),
    ("C2", "D"): ("avoid", "none"),

    ("C3", "A"): ("target_company", "startup"),
    ("C3", "B"): ("target_company", "product_based"),
    ("C3", "C"): ("target_company", "service_based"),
    ("C3", "D"): ("target_company", "unsure"),

    ("C4", "A"): ("goal", "any_good_company"),
    ("C4", "B"): ("goal", "specific_role"),
    ("C4", "C"): ("goal", "build_fundamentals"),
    ("C4", "D"): ("goal", "explore"),
}

# Optional free-text step after the fixed questions. Stored alongside the flat
# signals above (conversation_signals["additional_notes"]) but, unlike them, it
# has no OPTION_SIGNALS entry: it is user-written text, carried into the LLM
# roadmap prompt as extra context only - never used for ranking.
ADDITIONAL_NOTES_KEY = "additional_notes"
ADDITIONAL_NOTES_PROMPT = "Anything else you'd like us to know?"
MAX_ADDITIONAL_NOTES_CHARS = 500

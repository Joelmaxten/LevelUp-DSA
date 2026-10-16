"""
Gamification: XP, levels, streaks and badges. Pure: no Flask, no database, no network.

Nothing here is stored. Every number is worked out from rows the app already keeps (submitted scenario attempts and
completed roadmap steps), so it can never drift out of sync with them, and any figure can be explained by pointing at
the attempts behind it. The route (app/routes/gamification.py) gathers those rows; this module decides everything.

XP (see XP_RULES): per scenario, the BEST score (10 per correct question), plus a one-off bonus for the first pass and
for a perfect score; a bonus per DIFFERENT coding problem solved; a little per completed roadmap step. Because only the
best score and distinct achievements count, retrying a scenario or re-ticking a step can never farm XP.

Streak: consecutive calendar days (Indian Standard Time) with at least one submitted scenario or completed roadmap step.
A streak is still "alive" today if the last active day was yesterday (you have until midnight to keep it going).
"""
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

XP_RULES = {
    "per_point": 1,             # 10 points per correct question -> 10 XP (best attempt per scenario only)
    "first_pass": 20,           # once per scenario, the first time it is passed
    "perfect": 10,              # once per scenario that was ever scored 100%
    "code_solved": 15,          # once per different coding problem solved
    "roadmap_step": 5,          # per roadmap step currently ticked
}

# (minimum XP, title). Titles follow a career ladder so they mean something to the students.
LEVELS = [
    (0, "Intern"),
    (100, "Trainee"),
    (250, "Junior Engineer"),
    (500, "Engineer"),
    (850, "Senior Engineer"),
    (1300, "Lead Engineer"),
    (2000, "Principal Engineer"),
]

HARD_TOPICS = {"heap", "graph", "tree", "linked_list"}

# id, name, how to earn it (shown to the student), target for the progress bar of a locked badge
BADGES = [
    ("first_steps", "First Steps", "Submit your first scenario.", 1),
    ("first_pass", "Case Closed", "Pass a scenario (70% or more).", 1),
    ("perfectionist", "Perfectionist", "Score 100% on a scenario.", 1),
    ("first_code", "Hello, World", "Solve your first coding problem.", 1),
    ("coder_5", "Code Crafter", "Solve 5 different coding problems.", 5),
    ("structures_3", "Toolbox", "Solve coding problems that use 3 different data structures.", 3),
    ("deep_end", "Deep End", "Solve a heap, graph, tree or linked-list problem.", 1),
    ("comeback", "Comeback", "Pass a scenario after failing it on an earlier try.", 1),
    ("path_complete", "Path Finisher", "Pass every scenario in one career path.", 1),
    ("explorer", "Explorer", "Submit scenarios in 2 different career paths.", 2),
    ("streak_3", "On a Roll", "Keep a 3-day streak.", 3),
    ("streak_7", "Week Warrior", "Keep a 7-day streak.", 7),
    ("roadmap_10", "Step by Step", "Complete 10 roadmap steps.", 10),
    ("finish_line", "Finish Line", "Complete every step of a roadmap.", 1),
]


# ---------------------------------------------------------------- helpers
def ist_day(moment):
    """The calendar day in IST of a naive-UTC datetime (how the app stores times), or of a date as is."""
    if moment is None:
        return None
    if isinstance(moment, datetime):
        aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
        return aware.astimezone(IST).date()
    if isinstance(moment, date):
        return moment
    return None


def level_for(xp):
    """{level (1-based), title, xp, floor, next_at (None at the top), next_title, progress_pct}."""
    index = 0
    for i, (floor, _) in enumerate(LEVELS):
        if xp >= floor:
            index = i
    floor, title = LEVELS[index]
    if index + 1 < len(LEVELS):
        next_at, next_title = LEVELS[index + 1]
        pct = round(100 * (xp - floor) / (next_at - floor))
    else:
        next_at, next_title, pct = None, None, 100
    return {"level": index + 1, "title": title, "xp": xp, "floor": floor, "next_at": next_at,
            "next_title": next_title, "progress_pct": max(0, min(100, pct))}


def streaks(active_days, today):
    """(current streak, best streak) over a set of active days; current counts today or, if today is idle, yesterday."""
    days = sorted({d for d in active_days if d is not None and d <= today})
    best = run = 0
    previous = None
    for d in days:
        run = run + 1 if previous is not None and d - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = d
    current = 0
    if days and today - days[-1] <= timedelta(days=1):
        current = 1
        cursor = days[-1]
        day_set = set(days)
        while cursor - timedelta(days=1) in day_set:
            current += 1
            cursor -= timedelta(days=1)
    return current, best


def _solved_codes(answers, code_topics):
    """{code question id: ds_topic} of the code questions this attempt solved (server-written records only)."""
    out = {}
    if not isinstance(answers, dict):
        return out
    for qid, value in answers.items():
        if qid in code_topics and isinstance(value, dict) and value.get("passed") is True:
            out[qid] = code_topics[qid]
    return out


# ---------------------------------------------------------------- the summary
def summarize(attempts, roadmap_step_days, today, code_topics=None, path_scenarios=None, roadmaps_completed=0):
    """
    attempts: submitted scenario attempts as dicts {id, scenario_id, path, score, max_score, passed, submitted_at,
              answers}, in any order. roadmap_step_days: one completion time (datetime or date) per ticked step.
    code_topics: {code question or pool problem id: ds_topic}. path_scenarios: {path: [scenario ids]}.
    roadmaps_completed: how many of the student's roadmaps have every step ticked.
    Returns {xp, xp_breakdown, level, streak, badges, counts}. Deterministic for the same inputs.
    """
    code_topics = code_topics or {}
    path_scenarios = path_scenarios or {}
    ordered = sorted((a for a in attempts if a.get("max_score")),
                     key=lambda a: (a.get("submitted_at") or datetime.min, a.get("id") or 0))

    best, passed_ever, perfect_ever, failed_before, comebacks = {}, set(), set(), set(), set()
    solved = {}
    paths_tried = set()
    for a in ordered:
        sid = a["scenario_id"]
        score, max_score = a.get("score") or 0, a["max_score"]
        best[sid] = max(best.get(sid, 0), score)
        paths_tried.add(a.get("path"))
        is_pass = bool(a.get("passed"))
        if is_pass:
            if sid in failed_before and sid not in passed_ever:
                comebacks.add(sid)
            passed_ever.add(sid)
        else:
            failed_before.add(sid)
        if score >= max_score:
            perfect_ever.add(sid)
        solved.update(_solved_codes(a.get("answers"), code_topics))
    paths_tried.discard(None)

    steps = len(roadmap_step_days)
    breakdown = {
        "scenario_points": XP_RULES["per_point"] * sum(best.values()),
        "first_pass_bonus": XP_RULES["first_pass"] * len(passed_ever),
        "perfect_bonus": XP_RULES["perfect"] * len(perfect_ever),
        "code_bonus": XP_RULES["code_solved"] * len(solved),
        "roadmap_steps": XP_RULES["roadmap_step"] * steps,
    }
    xp = sum(breakdown.values())

    active = {ist_day(a.get("submitted_at")) for a in ordered} | {ist_day(d) for d in roadmap_step_days}
    current, best_streak = streaks(active, today)

    completed_paths = [p for p, ids in path_scenarios.items() if ids and all(i in passed_ever for i in ids)]
    topics = set(solved.values())
    progress = {
        "first_steps": len(ordered),
        "first_pass": len(passed_ever),
        "perfectionist": len(perfect_ever),
        "first_code": len(solved),
        "coder_5": len(solved),
        "structures_3": len(topics),
        "deep_end": len(topics & HARD_TOPICS),
        "comeback": len(comebacks),
        "path_complete": len(completed_paths),
        "explorer": len(paths_tried),
        "streak_3": best_streak,
        "streak_7": best_streak,
        "roadmap_10": steps,
        "finish_line": roadmaps_completed,
    }
    badges = []
    for badge_id, name, how, target in BADGES:
        have = progress[badge_id]
        badges.append({"id": badge_id, "name": name, "how": how, "earned": have >= target,
                       "progress": min(have, target), "target": target})

    return {
        "xp": xp,
        "xp_breakdown": breakdown,
        "level": level_for(xp),
        "streak": {"current": current, "best": best_streak,
                   "active_today": today in active},
        "badges": badges,
        "counts": {"scenarios_passed": len(passed_ever), "codes_solved": len(solved),
                   "badges_earned": sum(b["earned"] for b in badges), "badges_total": len(badges)},
    }


def rewards(before, after):
    """What changed between two summaries (before and after one submit): XP gained, level-up and new badges."""
    earned_before = {b["id"] for b in before["badges"] if b["earned"]}
    return {
        "xp_gained": after["xp"] - before["xp"],
        "xp": after["xp"],
        "level": after["level"],
        "leveled_up": after["level"]["level"] > before["level"]["level"],
        "new_badges": [{"id": b["id"], "name": b["name"], "how": b["how"]}
                       for b in after["badges"] if b["earned"] and b["id"] not in earned_before],
        "streak": after["streak"],
    }

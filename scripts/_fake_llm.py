"""
Deterministic fake LLM for the roadmap generator tests and benchmark. It reads
the prompt the generator built and answers like a well-behaved model: the
folder-ordering prompt gets the folders back in the order listed, and a phase
prompt gets a JSON array of steps built from the topic inventory in that same
prompt. No network, no randomness, so the same prompt always gives the same
reply.
"""
import json
import re

_FOLDER_LINE = re.compile(r'^- "([^"]+)" \(\d+ topics\)', re.M)
_TOPIC_LINE = re.compile(r"^([A-Za-z0-9_-]{6,})\|(.+)\|([a-z0-9_-]+)$")
_TARGET = re.compile(r"Generate about (\d+) steps")
_PHASE_TITLE = re.compile(r'This call covers ONLY the "(.+?)" phase')

REFS_PER_STEP = 4   # deliberately fewer than a real model gives, so more_topics has leftovers to place


def parse_phase_prompt(prompt):
    """(phase_title, target_steps, [(node_id, title, folder)]) from a phase prompt."""
    title = _PHASE_TITLE.search(prompt).group(1)
    target = int(_TARGET.search(prompt).group(1))
    topics = []
    in_inventory = False
    for line in prompt.split("\n"):
        if line.startswith("Topic inventory for THIS PHASE"):
            in_inventory = True
            continue
        if in_inventory:
            m = _TOPIC_LINE.match(line)
            if m:
                topics.append((m.group(1), m.group(2), m.group(3)))
            elif line.strip() == "":
                break
    return title, target, topics


def is_folder_order_prompt(prompt):
    return prompt.startswith("You are planning the PHASE ORDER")


def fake_reply(prompt):
    """The model's reply text for any prompt the roadmap generator builds."""
    if is_folder_order_prompt(prompt):
        return json.dumps(_FOLDER_LINE.findall(prompt))

    phase_title, target, topics = parse_phase_prompt(prompt)
    grounded = "PROJECT SOURCE MATERIAL" in prompt
    n = max(1, min(target, len(topics)))
    steps = []
    for i in range(n):
        lo, hi = i * len(topics) // n, (i + 1) * len(topics) // n
        group = topics[lo:hi]
        refs = group[:REFS_PER_STEP]
        first_id, first_title, _ = group[0]
        steps.append({
            "step_number": i + 1,
            "title": f"{first_title} [{first_id[:5]}]",
            "description": f"Work through {', '.join(t for _, t, _ in refs)} to build the {phase_title} basics.",
            "topic_refs": [node_id for node_id, _, _ in refs],
            "projects": [
                {"title": f"{first_title} mini project", "description": "Build a small example.",
                 "difficulty": "beginner", "grounded": grounded},
                {"title": f"{first_title} capstone", "description": "Extend it with a real use case.",
                 "difficulty": "intermediate", "grounded": grounded},
            ],
        })
    return json.dumps(steps)

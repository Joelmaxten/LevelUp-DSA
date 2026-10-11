"""Small helpers shared by the code-pool authoring sources (scripts/code_pools/<path>.py)."""
import random

TODO = "    # Write your code here.\n"


def program(read_and_print, function):
    """A whole student-facing program: imports, the function, then the given input/output code."""
    return "import sys\n\n\n" + function.strip("\n") + "\n\n\n" + read_and_print.strip("\n") + "\n"


def stub(signature, docstring, placeholder):
    return f"{signature}\n    \"\"\"{docstring}\"\"\"\n{TODO}    return {placeholder}\n"


def variants(hand_cases, generator, seeds, extra_hidden=()):
    """hand_cases: one [(stdin, expected)] list per variant; hidden inputs come from generator(rng)."""
    out = []
    for i, (params, visible) in enumerate(hand_cases):
        rng = random.Random(seeds + i)
        hidden = [generator(rng, size) for size in ("small", "medium", "large")]
        hidden += list(extra_hidden[i] if i < len(extra_hidden) else [])
        out.append({"params": params, "visible": visible, "hidden": hidden})
    return out


def lines(text):
    return [ln for ln in text.split("\n")]

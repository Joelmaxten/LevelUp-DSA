"""
Prerequisite logic for the Skill DNA Map, kept free of Flask/SQLAlchemy so it can
be tested on plain dicts.

The DSA topics form a directed acyclic graph: an edge P -> N means "P is a
prerequisite of N". A node's state comes from its prerequisites, which themselves
have a state, so nodes are visited in topological order (every prerequisite before
the things that depend on it):

    locked    - some prerequisite is not mastered yet
    unlocked  - every prerequisite is mastered (or there are none), node not mastered yet
    mastered  - unlocked, and mastery_level >= MASTERY_THRESHOLD

A prerequisite counts only if it is itself unlocked, not merely if its stored
mastery number is high. Stage 2 will only ever award mastery on unlocked nodes, so
this never matters in normal use. It matters if a mastery row is edited by hand
in the DB: giving "Trees" a mastery of 1.0 must not open "Graphs" while "Arrays"
is still untouched, because that would let a student skip ahead of a lock.
"""

import heapq

# mastery_level is 0.0-1.0 (NodeMastery.mastery_level). A node counts as mastered,
# and so unlocks what depends on it, from this level up. One knob, used everywhere.
MASTERY_THRESHOLD = 0.7

LOCKED = "locked"
UNLOCKED = "unlocked"
MASTERED = "mastered"


def topological_order(prerequisites):
    """
    prerequisites: {node_id: [prerequisite node ids]}. Returns node ids ordered so
    every node comes after all of its prerequisites (Kahn's algorithm; ties broken
    by id so the order is stable between calls).

    Raises ValueError if a prerequisite id isn't a node, or the graph has a cycle.
    A cycle would otherwise lock its members forever with no visible reason.
    """
    unmet = {}
    dependents = {node_id: [] for node_id in prerequisites}
    for node_id, prereq_ids in prerequisites.items():
        for prereq_id in prereq_ids:
            if prereq_id not in prerequisites:
                raise ValueError(f"Node {node_id} lists unknown prerequisite {prereq_id}.")
            dependents[prereq_id].append(node_id)
        unmet[node_id] = len(set(prereq_ids))

    ready = [node_id for node_id, count in unmet.items() if count == 0]
    heapq.heapify(ready)

    order = []
    while ready:
        node_id = heapq.heappop(ready)
        order.append(node_id)
        for dependent in set(dependents[node_id]):
            unmet[dependent] -= 1
            if unmet[dependent] == 0:
                heapq.heappush(ready, dependent)

    if len(order) != len(prerequisites):
        stuck = sorted(set(prerequisites) - set(order))
        raise ValueError(f"Prerequisite cycle among nodes {stuck}.")
    return order


def layer_depths(prerequisites, order=None):
    """
    {node_id: depth}, where depth is the longest chain of prerequisites leading to
    the node (roots are 0). The map is drawn with one column per depth, so every
    edge points from an earlier column to a later one.
    """
    order = order if order is not None else topological_order(prerequisites)
    depth = {}
    for node_id in order:
        depth[node_id] = 1 + max((depth[p] for p in prerequisites[node_id]), default=-1)
    return depth


def compute_node_states(prerequisites, mastery, threshold=MASTERY_THRESHOLD):
    """
    prerequisites: {node_id: [prerequisite ids]}; mastery: {node_id: mastery_level}
    (a node with no entry has mastery 0). Returns
    {node_id: {"state": ..., "mastery_level": float, "blocked_by": [prerequisite ids]}}
    where blocked_by lists the prerequisites still standing between the student and
    the node (empty unless locked), so the UI can say what to do next.
    """
    states = {}
    for node_id in topological_order(prerequisites):
        level = float(mastery.get(node_id, 0.0) or 0.0)
        blocked_by = [p for p in prerequisites[node_id] if states[p]["state"] != MASTERED]
        if blocked_by:
            state = LOCKED
        elif level >= threshold:
            state = MASTERED
        else:
            state = UNLOCKED
        states[node_id] = {"state": state, "mastery_level": level, "blocked_by": blocked_by}
    return states

"""
Verifies app/pipeline/dsa_seed_data.py without touching the database:

1. Every seeded test case is run through an independent reference solution for its
   problem, and the result must equal expected_output. This is what makes the cases
   "known-correct": the expected values come from the problems' own statements, and
   these separately written solutions must reproduce every one.
2. Structure: each problem maps to a node, titles are unique, every problem has cases,
   prerequisites resolve, the graph is a DAG with no redundant (transitive) edge, and
   career-path names are real.

Run:  python scripts/verify_dsa_seed.py     (exit code 1 on any failure)
"""

import heapq
import os
import sys
from collections import Counter, deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.career_quiz_data import CAREER_PATHS
from app.pipeline.dsa_graph import layer_depths, topological_order
from app.pipeline.dsa_seed_data import NODES, POINTS_BY_DIFFICULTY, PROBLEMS


# ------------------------------------------------------ structure helpers

class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


def to_list(values):
    head = None
    for v in reversed(values):
        head = ListNode(v, head)
    return head


def from_list(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


def to_tree(values):
    """Level-order array (null = missing child) -> TreeNode root."""
    if not values:
        return None
    root = TreeNode(values[0])
    queue, i = deque([root]), 1
    while queue and i < len(values):
        node = queue.popleft()
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            queue.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            queue.append(node.right)
        i += 1
    return root


def from_tree(root):
    if root is None:
        return []
    out, queue = [], deque([root])
    while queue:
        node = queue.popleft()
        if node is None:
            out.append(None)
        else:
            out.append(node.val)
            queue.append(node.left)
            queue.append(node.right)
    while out and out[-1] is None:
        out.pop()
    return out


# ------------------------------------------------- reference solutions
# Deliberately plain and different in approach from what a student would write
# (brute force where cheap), so a wrong expected value can't hide behind a shared bug.

def best_time_to_buy_and_sell_stock(prices):
    return max([0] + [prices[j] - prices[i] for i in range(len(prices)) for j in range(i + 1, len(prices))])


def maximum_subarray(nums):
    return max(sum(nums[i:j]) for i in range(len(nums)) for j in range(i + 1, len(nums) + 1))


def valid_anagram(s, t):
    return Counter(s) == Counter(t)


def longest_common_prefix(strs):
    prefix = ""
    for chars in zip(*strs):
        if len(set(chars)) != 1:
            break
        prefix += chars[0]
    return prefix


def two_sum(nums, target):
    matches = [[i, j] for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] + nums[j] == target]
    assert len(matches) == 1, "statement promises exactly one solution"
    return matches[0]


def contains_duplicate(nums):
    return len(set(nums)) != len(nums)


def valid_palindrome(s):
    cleaned = [c.lower() for c in s if c.isalnum()]
    return cleaned == cleaned[::-1]


def container_with_most_water(height):
    return max(min(height[i], height[j]) * (j - i) for i in range(len(height)) for j in range(i + 1, len(height)))


def merge_sorted_array(nums1, m, nums2, n):
    return sorted(nums1[:m] + nums2[:n])


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def binary_search(nums, target):
    return nums.index(target) if target in nums else -1


def search_insert_position(nums, target):
    return sum(1 for x in nums if x < target)


def longest_substring_without_repeating_characters(s):
    best = 0
    for i in range(len(s)):
        for j in range(i + 1, len(s) + 1):
            if len(set(s[i:j])) == j - i:
                best = max(best, j - i)
    return best


def minimum_size_subarray_sum(target, nums):
    lengths = [j - i for i in range(len(nums)) for j in range(i + 1, len(nums) + 1) if sum(nums[i:j]) >= target]
    return min(lengths, default=0)


def valid_parentheses(s):
    pairs, stack = {")": "(", "]": "[", "}": "{"}, []
    for c in s:
        if c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
        else:
            stack.append(c)
    return not stack


def daily_temperatures(temperatures):
    out = []
    for i, t in enumerate(temperatures):
        out.append(next((j - i for j in range(i + 1, len(temperatures)) if temperatures[j] > t), 0))
    return out


def reverse_linked_list(head):
    prev, cur = None, to_list(head)
    while cur:
        cur.next, prev, cur = prev, cur, cur.next
    return from_list(prev)


def merge_two_sorted_lists(list1, list2):
    return from_list(to_list(sorted(list1 + list2)))


def linked_list_cycle(head, pos):
    nodes = []
    cur = to_list(head)
    while cur:
        nodes.append(cur)
        cur = cur.next
    if pos != -1:
        nodes[-1].next = nodes[pos]
    # Floyd: a fast pointer only catches the slow one if there is a loop.
    slow = fast = nodes[0] if nodes else None
    while fast and fast.next:
        slow, fast = slow.next, fast.next.next
        if slow is fast:
            return True
    return False


def fibonacci_number(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def power_of_two(n):
    return any(2 ** k == n for k in range(0, 31))


def maximum_depth_of_binary_tree(root):
    def depth(node):
        return 0 if node is None else 1 + max(depth(node.left), depth(node.right))
    return depth(to_tree(root))


def invert_binary_tree(root):
    def invert(node):
        if node is not None:
            node.left, node.right = invert(node.right), invert(node.left)
        return node
    return from_tree(invert(to_tree(root)))


def validate_binary_search_tree(root):
    def inorder(node):
        return [] if node is None else inorder(node.left) + [node.val] + inorder(node.right)
    values = inorder(to_tree(root))
    return all(a < b for a, b in zip(values, values[1:]))


def kth_smallest_element_in_a_bst(root, k):
    def inorder(node):
        return [] if node is None else inorder(node.left) + [node.val] + inorder(node.right)
    return inorder(to_tree(root))[k - 1]


def kth_largest_element_in_an_array(nums, k):
    return sorted(nums, reverse=True)[k - 1]


def last_stone_weight(stones):
    heap = [-s for s in stones]
    heapq.heapify(heap)
    while len(heap) > 1:
        y, x = -heapq.heappop(heap), -heapq.heappop(heap)
        if y != x:
            heapq.heappush(heap, -(y - x))
    return -heap[0] if heap else 0


def number_of_islands(grid):
    seen, count = set(), 0
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == "1" and (r, c) not in seen:
                count += 1
                queue = deque([(r, c)])
                seen.add((r, c))
                while queue:
                    y, x = queue.popleft()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == "1" and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            queue.append((ny, nx))
    return count


def find_if_path_exists_in_graph(n, edges, source, destination):
    adjacent = {i: [] for i in range(n)}
    for u, v in edges:
        adjacent[u].append(v)
        adjacent[v].append(u)
    seen, stack = {source}, [source]
    while stack:
        for nxt in adjacent[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return destination in seen


def climbing_stairs(n):
    def ways(k):
        return 1 if k <= 1 else ways(k - 1) + ways(k - 2)
    return ways(n)


def house_robber(nums):
    best = 0
    for mask in range(1 << len(nums)):
        if mask & (mask >> 1):
            continue  # two adjacent houses chosen
        best = max(best, sum(nums[i] for i in range(len(nums)) if mask >> i & 1))
    return best


REFERENCE = {
    "Best Time to Buy and Sell Stock": best_time_to_buy_and_sell_stock,
    "Maximum Subarray": maximum_subarray,
    "Valid Anagram": valid_anagram,
    "Longest Common Prefix": longest_common_prefix,
    "Two Sum": two_sum,
    "Contains Duplicate": contains_duplicate,
    "Valid Palindrome": valid_palindrome,
    "Container With Most Water": container_with_most_water,
    "Merge Sorted Array": merge_sorted_array,
    "Merge Intervals": merge_intervals,
    "Binary Search": binary_search,
    "Search Insert Position": search_insert_position,
    "Longest Substring Without Repeating Characters": longest_substring_without_repeating_characters,
    "Minimum Size Subarray Sum": minimum_size_subarray_sum,
    "Valid Parentheses": valid_parentheses,
    "Daily Temperatures": daily_temperatures,
    "Reverse Linked List": reverse_linked_list,
    "Merge Two Sorted Lists": merge_two_sorted_lists,
    "Linked List Cycle": linked_list_cycle,
    "Fibonacci Number": fibonacci_number,
    "Power of Two": power_of_two,
    "Maximum Depth of Binary Tree": maximum_depth_of_binary_tree,
    "Invert Binary Tree": invert_binary_tree,
    "Validate Binary Search Tree": validate_binary_search_tree,
    "Kth Smallest Element in a BST": kth_smallest_element_in_a_bst,
    "Kth Largest Element in an Array": kth_largest_element_in_an_array,
    "Last Stone Weight": last_stone_weight,
    "Number of Islands": number_of_islands,
    "Find if Path Exists in Graph": find_if_path_exists_in_graph,
    "Climbing Stairs": climbing_stairs,
    "House Robber": house_robber,
}


# ------------------------------------------------------------------ checks

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def check_test_cases():
    total = 0
    for problem in PROBLEMS:
        solve = REFERENCE.get(problem["title"])
        check(solve is not None, f"{problem['title']}: no reference solution")
        check(problem["test_cases"], f"{problem['title']}: no test cases")
        if solve is None:
            continue
        for case in problem["test_cases"]:
            total += 1
            # Copy inputs so a solution mutating them can't affect later cases.
            args = {k: (v[:] if isinstance(v, list) else v) for k, v in case["input"].items()}
            got = solve(**args)
            check(got == case["expected_output"],
                  f"{problem['title']}: input {case['input']} -> reference gives {got!r}, seed says {case['expected_output']!r}")
    extra = set(REFERENCE) - {p["title"] for p in PROBLEMS}
    check(not extra, f"reference solutions with no seeded problem: {sorted(extra)}")
    return total


def check_structure():
    topics = [n["topic"] for n in NODES]
    check(len(topics) == len(set(topics)), "duplicate node topics")
    titles = [p["title"] for p in PROBLEMS]
    check(len(titles) == len(set(titles)), "duplicate problem titles")

    ids = {topic: i for i, topic in enumerate(topics, start=1)}
    prerequisites = {}
    for node in NODES:
        for prereq in node["prerequisites"]:
            check(prereq in ids, f"{node['topic']}: unknown prerequisite {prereq!r}")
        for path in node["career_paths"]:
            check(path in CAREER_PATHS, f"{node['topic']}: {path!r} is not one of CAREER_PATHS")
        prerequisites[ids[node["topic"]]] = [ids[p] for p in node["prerequisites"] if p in ids]

    for problem in PROBLEMS:
        check(problem["node"] in ids, f"{problem['title']}: unknown node {problem['node']!r}")
        check(problem["difficulty"] in POINTS_BY_DIFFICULTY, f"{problem['title']}: bad difficulty")
        check(problem["description"].strip(), f"{problem['title']}: empty description")
    for node in NODES:
        check(any(p["node"] == node["topic"] for p in PROBLEMS), f"{node['topic']}: node has no problems")

    # Every career path should light up at least one node, or its map has no highlight.
    for path in CAREER_PATHS:
        check(any(path in n["career_paths"] for n in NODES), f"career path never highlighted: {path}")

    try:
        order = topological_order(prerequisites)
    except ValueError as error:
        failures.append(f"graph is not a DAG: {error}")
        return
    depth = layer_depths(prerequisites, order)
    check(any(not p for p in prerequisites.values()), "no root node")

    # A redundant edge (A -> C when A -> B -> C already exists) adds clutter, not information.
    reach = {n: set() for n in prerequisites}
    for n in order:
        for p in prerequisites[n]:
            reach[n] |= {p} | reach[p]
    for n, prereqs in prerequisites.items():
        for p in prereqs:
            others = [q for q in prereqs if q != p]
            check(not any(p in reach[q] for q in others),
                  f"redundant edge {topics[p - 1]} -> {topics[n - 1]}")

    print("depths:", {topics[n - 1]: d for n, d in depth.items()})


def main():
    total = check_test_cases()
    check_structure()
    print(f"{len(NODES)} nodes, {len(PROBLEMS)} problems, {total} test cases checked.")
    if failures:
        print(f"\nFAILED ({len(failures)}):")
        for message in failures:
            print(" -", message)
        sys.exit(1)
    print("OK: every expected_output matches its reference solution; graph is a DAG.")


if __name__ == "__main__":
    main()

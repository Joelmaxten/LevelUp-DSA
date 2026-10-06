"""
KB-first video and resource resolver for a generated roadmap. For a phased
step (one with topic_refs), resources are resolved FIRST from the roadmap.sh
KB's own "resources" metadata (parsed by roadmap_kb_processor._extract_resources
from each topic's own markdown file) - no network call needed for most steps.
The YouTube Data API v3 is used only as a fallback, and only for a step that
still has fewer than MIN_VIDEOS after the KB pass (see resolve_step_from_kb
and fetch_resources_for_roadmap). This keeps quota usage low: a typical
~20-30 step roadmap that resolves entirely from the KB costs 0 quota units,
versus the old design's unconditional 1 search (100 units) per step.

Deliberately kept separate from roadmap generation itself (see
PROJECT_BIOGRAPHY.md) - an external API's own latency/failure mode
shouldn't be able to jeopardize an already-successful roadmap save, same
reasoning as why /roadmap/generate is its own endpoint rather than chained
onto /conversation/answer.

Quota note: YouTube Data API v3 free tier is 10,000 units/day; a
search.list call costs 100 units. With the KB-first design and
MAX_FALLBACK_SEARCHES capping fallback search calls per roadmap, a full
roadmap now costs at most MAX_FALLBACK_SEARCHES * 100 = 1,200 units in the
worst case (every step needed a fallback), and typically far less.
"""

import os
import re
from collections import Counter
from urllib.parse import parse_qs, urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# The two domains confirmed spammy in the Part A KB audit: both appear ONLY
# as type="course" links, both with generic templated titles repeated
# across many unrelated topics (e.g. inter-git.com's "Why use Git?" /
# "What is Git?" on dozens of different nodes) - a hallmark of a scraper/
# link-farm site rather than real educational content, and ransomleak.com's
# name itself reads as a malicious/typosquat domain. No other domain found
# in the KB's official/article/course/video resource links looked spammy
# enough to add here (see the Part A report for the full domain survey).
BLOCKED_DOMAINS = {"ransomleak.com", "inter-git.com"}

MIN_VIDEOS = 3
MAX_VIDEOS = 4
MAX_RESOURCES = 4
MAX_FALLBACK_SEARCHES = 12

_VIDEO_ID_RE_11 = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _domain_of(url):
    try:
        netloc = urlparse(url).netloc.lower()
    except (ValueError, AttributeError):
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def video_id_from_url(url):
    """
    Accepts ONLY https://[www.]youtube.com/watch?v=ID,
    https://youtu.be/ID, and https://[www.]youtube.com/embed/ID (ID must be
    exactly 11 chars from [A-Za-z0-9_-], YouTube's own video id shape).
    Returns the id, or None for anything else - playlist links, channel
    links, http (not https), other hosts, malformed ids, or a malformed URL
    (e.g. a duplicated "?v=" query string, observed in the real KB data).
    """
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host == "youtube.com" and parsed.path == "/watch":
        values = parse_qs(parsed.query).get("v")
        candidate = values[0] if values else None
    elif host == "youtu.be":
        candidate = parsed.path.lstrip("/")
    elif host == "youtube.com" and parsed.path.startswith("/embed/"):
        candidate = parsed.path[len("/embed/"):].split("/")[0]
    else:
        return None

    if candidate and _VIDEO_ID_RE_11.match(candidate):
        return candidate
    return None


def _video_drop_reason(url):
    """
    Only called when video_id_from_url() returned None, purely to label WHY
    for the caller's dropped-link stats - mirrors the categories used in
    the Part A video-link audit (watch/youtu.be/embed/playlist/channel/
    other-youtube-form/non-youtube), plus not_https and malformed_url.
    """
    if not isinstance(url, str):
        return "not_a_string"
    if not url.startswith("https://"):
        return "not_https"
    try:
        parsed = urlparse(url)
    except ValueError:
        return "malformed_url"
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host == "youtube.com":
        if parsed.path == "/watch":
            return "missing_or_invalid_v_param"
        if parsed.path.startswith("/embed/"):
            return "invalid_embed_id"
        if parsed.path == "/playlist":
            return "playlist_link"
        if parsed.path.startswith(("/channel/", "/c/", "/@")):
            return "channel_link"
        return "other_youtube_form"
    if host == "youtu.be":
        return "invalid_youtu_be_id"
    return "non_youtube"


def _topic_candidates(topic_order, node_index, topic_refs_set):
    """
    For each node_id in topic_order (topic_refs then more_topics, in that
    combined order - see resolve_step_from_kb), looks it up in node_index
    and splits its KB "resources" into a video candidate list (id, title)
    and an official/course resource candidate list, filtering resource
    links to https-only and not in BLOCKED_DOMAINS. A node_id missing from
    node_index (KB metadata not available - e.g. chunks=None was passed to
    fetch_resources_for_roadmap) is skipped, not an error. topic_refs_set
    is checked (not position) to tell topic_refs topics from more_topics
    ones, so a skip never desyncs the two - see topic_is_ref in the return.
    Returns (topic_titles, topic_video_lists, topic_resource_lists,
    topic_is_ref, drop_reasons).
    """
    topic_titles = []
    topic_video_lists = []
    topic_resource_lists = []
    topic_is_ref = []
    drop_reasons = Counter()

    for node_id in topic_order:
        meta = node_index.get(node_id)
        if meta is None:
            continue
        topic_title = meta.get("title", "")
        vids = []
        res_candidates = []
        for r in meta.get("resources") or []:
            rtype = r.get("type")
            url = r.get("url")
            if rtype == "video":
                vid = video_id_from_url(url)
                if vid is None:
                    drop_reasons[_video_drop_reason(url)] += 1
                    continue
                vids.append((vid, r.get("title")))
            elif rtype in ("official", "course"):
                if not isinstance(url, str) or not url.startswith("https://"):
                    drop_reasons["not_https"] += 1
                    continue
                if _domain_of(url) in BLOCKED_DOMAINS:
                    drop_reasons["blocked_domain"] += 1
                    continue
                res_candidates.append({"type": rtype, "title": r.get("title"), "url": url, "topic": topic_title})
        topic_titles.append(topic_title)
        topic_video_lists.append(vids)
        topic_resource_lists.append(res_candidates)
        topic_is_ref.append(node_id in topic_refs_set)

    return topic_titles, topic_video_lists, topic_resource_lists, topic_is_ref, drop_reasons


def resolve_step_from_kb(step, node_index):
    """
    Resolves a phased step's videos and resources entirely from KB metadata
    (no network call). node_index: {node_id: chunk dict} (chunk has "title"
    and "resources" - see roadmap_kb_processor.extract_chunks).

    Videos: candidate topics are this step's topic_refs (in order) then
    more_topics (in their stored, similarity-sorted order). Selected
    round-robin across topics in up to 2 passes - one video per topic per
    pass - deduped by video id, capped at MAX_VIDEOS. This spreads video
    coverage across a step's topics instead of exhausting one topic's list
    first.

    Resources: up to MAX_RESOURCES items, official-type first then
    course-type (roadmap.sh's own curated tiers), deduped by URL, from
    topic_refs' topics before more_topics' topics.

    Returns (videos, resources, drop_reasons, video_origin_counts).
    drop_reasons is a Counter of why a candidate link was excluded (see
    _video_drop_reason, "not_https", "blocked_domain"; duplicate hits add
    "duplicate_video_id" here too). video_origin_counts is a Counter with
    keys "topic_refs"/"more_topics" - which of the two lists each selected
    video's topic came from (diagnostic only; the "videos" dicts themselves
    don't carry this - see scripts/inspect_resources.py).
    """
    topic_refs = step.get("topic_refs") or []
    topic_order = list(topic_refs) + [t["node_id"] for t in (step.get("more_topics") or [])]
    topic_titles, topic_video_lists, topic_resource_lists, topic_is_ref, drop_reasons = _topic_candidates(
        topic_order, node_index, set(topic_refs)
    )

    n_topics = len(topic_video_lists)
    pointers = [0] * n_topics
    selected_videos = []
    used_video_ids = set()
    video_origin_counts = Counter()

    def _advance_and_take(i):
        while pointers[i] < len(topic_video_lists[i]):
            vid, title = topic_video_lists[i][pointers[i]]
            pointers[i] += 1
            if vid in used_video_ids:
                drop_reasons["duplicate_video_id"] += 1
                continue
            return vid, title
        return None

    for _pass in range(2):
        if len(selected_videos) >= MAX_VIDEOS:
            break
        for i in range(n_topics):
            if len(selected_videos) >= MAX_VIDEOS:
                break
            result = _advance_and_take(i)
            if result is None:
                continue
            vid, title = result
            used_video_ids.add(vid)
            selected_videos.append({
                "title": title,
                "url": f"https://youtube.com/watch?v={vid}",
                "video_id": vid,
                "source": "roadmap.sh",
                "topic": topic_titles[i],
            })
            video_origin_counts["topic_refs" if topic_is_ref[i] else "more_topics"] += 1

    selected_resources = []
    used_urls = set()
    for rtype_priority in ("official", "course"):
        if len(selected_resources) >= MAX_RESOURCES:
            break
        for candidates in topic_resource_lists:
            if len(selected_resources) >= MAX_RESOURCES:
                break
            for r in candidates:
                if r["type"] != rtype_priority:
                    continue
                if r["url"] in used_urls:
                    drop_reasons["duplicate_resource_url"] += 1
                    continue
                used_urls.add(r["url"])
                selected_resources.append(r)
                if len(selected_resources) >= MAX_RESOURCES:
                    break

    return selected_videos, selected_resources, drop_reasons, video_origin_counts


def fetch_video_for_step(step_title, youtube_client=None):
    """
    Returns {"title": ..., "url": ...} for the top matching video, or None
    if nothing was found or the API call failed. Never raises - a missing
    video for one step shouldn't break resourcing the rest of the roadmap.
    Used for the old-roadmap / no-topic_refs fallback path (see
    fetch_resources_for_roadmap) - one unconditional search, as before.
    """
    if youtube_client is None:
        youtube_client = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    query = f"{step_title} tutorial"

    try:
        response = youtube_client.search().list(
            q=query, part="snippet", type="video", maxResults=1,
        ).execute()
    except HttpError:
        return None

    items = response.get("items", [])
    if not items:
        return None

    item = items[0]
    video_id = item["id"]["videoId"]
    return {
        "title": item["snippet"]["title"],
        "url": f"https://youtube.com/watch?v={video_id}",
    }


def _fallback_search_videos(step_title, phase_title, youtube_client, exclude_ids, needed):
    """
    ONE search.list call (maxResults=6, cost 100 quota units), for a step
    that still has fewer than MIN_VIDEOS after the KB pass. Each result is
    validated the same way a KB video id would be (11-char id shape);
    results already present (exclude_ids) are skipped. Never raises - a
    quota or API error just means no fallback videos get added, same as
    fetch_video_for_step's contract.
    """
    query = f"{step_title} {phase_title} tutorial"
    try:
        response = youtube_client.search().list(
            q=query, part="snippet", type="video", maxResults=6,
        ).execute()
    except HttpError:
        return []

    results = []
    for item in response.get("items", []):
        if len(results) >= needed:
            break
        video_id = item.get("id", {}).get("videoId")
        if not video_id or video_id in exclude_ids or not _VIDEO_ID_RE_11.match(video_id):
            continue
        results.append({
            "title": item.get("snippet", {}).get("title", ""),
            "url": f"https://youtube.com/watch?v={video_id}",
            "video_id": video_id,
            "source": "youtube_search",
            "topic": None,
        })
    return results


def fetch_resources_for_roadmap(roadmap, chunks=None, max_fallback_searches=None, use_youtube=True):
    """
    roadmap: a GeneratedRoadmap.steps value - either the current
    {"phases": [{"phase_number", "title", "steps": [...]}]} shape, or an
    older flat list of step dicts (from before roadmap generation was split
    into phases). chunks: the loaded FAISS index metadata (rag.load_index()'s
    second return value) - used to build a node_id -> chunk lookup for
    KB-first resolution; omit only if unavailable (falls back to the old
    single-search behavior for every step, since there's no KB metadata to
    resolve from). max_fallback_searches: override for MAX_FALLBACK_SEARCHES
    (used by scripts/inspect_resources.py's --youtube flag for controlled
    testing) - None uses the module default. use_youtube=False never builds a
    YouTube client (KB-only: no network at all, zero fallback searches, a step
    without topic_refs gets "videos": [] and "resource": None) - used by
    scripts/build_base_roadmaps.py.

    Returns (new_roadmap, stats): new_roadmap is the SAME shape it was
    given. Every phased step with topic_refs gets "videos" (list, KB-first
    then YouTube-search fallback if still under MIN_VIDEOS) and "resources"
    (list, KB official/course links) in addition to its existing keys.
    "resource" is also kept, set to the first video's {"title","url"} (or
    None), so the current page keeps working unmodified. A step with no
    topic_refs (old roadmaps, or a step whose topic_refs were all dropped
    during validation) keeps the OLD behavior exactly: one unconditional
    search, one video, "resource" set, plus "videos": [that video],
    "resources": [].

    stats: {"kb_videos_used", "fallback_searches_used",
    "dropped_links_by_reason"} - a per-roadmap-call total, not per-step.
    """
    fallback_cap = MAX_FALLBACK_SEARCHES if max_fallback_searches is None else max_fallback_searches
    youtube_client = None
    if use_youtube and os.environ.get("YOUTUBE_API_KEY"):
        youtube_client = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    node_index = {c["node_id"]: c for c in chunks if "node_id" in c} if chunks else {}

    stats = {"kb_videos_used": 0, "fallback_searches_used": 0, "dropped_links_by_reason": Counter()}

    def enrich_old_style(step):
        resource = fetch_video_for_step(step["title"], youtube_client=youtube_client) if youtube_client else None
        videos = [{**resource, "video_id": video_id_from_url(resource["url"]), "source": "youtube_search", "topic": None}] if resource else []
        return {**step, "resource": resource, "videos": videos, "resources": []}

    def enrich_phase_step(step, phase_title):
        if not step.get("topic_refs"):
            return enrich_old_style(step)

        videos, resources, drop_reasons, _video_origin_counts = resolve_step_from_kb(step, node_index)
        stats["dropped_links_by_reason"].update(drop_reasons)
        stats["kb_videos_used"] += len(videos)

        if len(videos) < MIN_VIDEOS and youtube_client is not None and stats["fallback_searches_used"] < fallback_cap:
            stats["fallback_searches_used"] += 1
            existing_ids = {v["video_id"] for v in videos}
            extra = _fallback_search_videos(step["title"], phase_title, youtube_client, existing_ids, MIN_VIDEOS - len(videos))
            videos = videos + extra

        first_video = videos[0] if videos else None
        resource = {"title": first_video["title"], "url": first_video["url"]} if first_video else None

        return {**step, "resource": resource, "videos": videos, "resources": resources}

    if isinstance(roadmap, list):
        new_roadmap = [enrich_old_style(step) for step in roadmap]
    else:
        new_roadmap = {
            **roadmap,
            "phases": [
                {**phase, "steps": [enrich_phase_step(step, phase["title"]) for step in phase["steps"]]}
                for phase in roadmap["phases"]
            ],
        }

    stats_out = {
        "kb_videos_used": stats["kb_videos_used"],
        "fallback_searches_used": stats["fallback_searches_used"],
        "dropped_links_by_reason": dict(stats["dropped_links_by_reason"]),
    }
    return new_roadmap, stats_out

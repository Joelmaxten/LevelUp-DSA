"""
Fetches one relevant YouTube video per roadmap step, via the YouTube Data
API v3. Deliberately kept separate from roadmap generation itself (see
PROJECT_BIOGRAPHY.md) - an external API's own latency/failure mode
shouldn't be able to jeopardize an already-successful roadmap save, same
reasoning as why /roadmap/generate is its own endpoint rather than chained
onto /conversation/answer.

Quota note: YouTube Data API v3 free tier is 10,000 units/day; a
search.list call costs 100 units. Roadmap generation now produces a phased
roadmap (5 phases, ~4-8 steps each - typically ~20 steps total, up from the
previous flat 8-12), so a full roadmap now costs roughly 2,000 units to
fully resource - roughly 5 full roadmaps/day on the free tier, down from
~10.
"""

import os

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def fetch_video_for_step(step_title, youtube_client=None):
    """
    Returns {"title": ..., "url": ...} for the top matching video, or None
    if nothing was found or the API call failed. Never raises - a missing
    video for one step shouldn't break resourcing the rest of the roadmap.
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


def fetch_resources_for_roadmap(roadmap):
    """
    roadmap: a GeneratedRoadmap.steps value - either the current
    {"phases": [{"phase_number", "title", "steps": [...]}]} shape, or an
    older flat list of step dicts (from before roadmap generation was split
    into phases). Returns a NEW value of the SAME shape it was given, with
    every step (across every phase, for the current shape) given a
    "resource" key added (a dict from fetch_video_for_step, or None).
    Reuses one YouTube client across all steps rather than rebuilding it
    per call.
    """
    youtube_client = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    def enrich(step):
        resource = fetch_video_for_step(step["title"], youtube_client=youtube_client)
        return {**step, "resource": resource}

    if isinstance(roadmap, list):
        return [enrich(step) for step in roadmap]

    return {
        **roadmap,
        "phases": [
            {**phase, "steps": [enrich(step) for step in phase["steps"]]}
            for phase in roadmap["phases"]
        ],
    }
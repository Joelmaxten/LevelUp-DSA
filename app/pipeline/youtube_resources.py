"""
Fetches one relevant YouTube video per roadmap step, via the YouTube Data
API v3. Deliberately kept separate from roadmap generation itself (see
PROJECT_BIOGRAPHY.md) - an external API's own latency/failure mode
shouldn't be able to jeopardize an already-successful roadmap save, same
reasoning as why /roadmap/generate is its own endpoint rather than chained
onto /conversation/answer.

Quota note: YouTube Data API v3 free tier is 10,000 units/day; a
search.list call costs 100 units. A 10-step roadmap costs 1,000 units to
fully resource - roughly 10 full roadmaps/day on the free tier.
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


def fetch_resources_for_roadmap(steps):
    """
    steps: the list of {step_number, title, description} dicts from a
    GeneratedRoadmap. Returns a NEW list of the same steps, each with a
    "resource" key added (a dict from fetch_video_for_step, or None).
    Reuses one YouTube client across all steps rather than rebuilding it
    per call.
    """
    youtube_client = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    enriched = []
    for step in steps:
        resource = fetch_video_for_step(step["title"], youtube_client=youtube_client)
        enriched.append({**step, "resource": resource})

    return enriched
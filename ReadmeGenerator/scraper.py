"""
Scraper module for GitHub and YouTube data.
"""

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
}

# Headers for the GitHub REST API. A User-Agent is required. Unauthenticated, the
# Search API allows 10 req/min, plenty for the few searches we make per run.
GITHUB_API_HEADERS = {
    "User-Agent": "ReadmeGenerator",
    "Accept": "application/vnd.github+json",
}

# Namespaces used by the YouTube channel RSS feed.
YT_FEED_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

# Cache of resolved channel ids (username -> UC id), committed with the repo so
# normal runs never need to scrape the channel page.
CHANNEL_ID_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "channel_id_cache.json"
)

# Last successful video list per username, committed with the repo. YouTube
# intermittently blocks datacenter IPs (e.g. GitHub Actions runners); falling
# back to this keeps the videos section in the README instead of dropping it.
VIDEO_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "videos_cache.json"
)


def get_pinned(github_user):
    """
    Get pinned projects from a GitHub user profile.
    """
    github_url = f"https://github.com/{github_user}"
    page = requests.get(github_url, timeout=5)
    soup = BeautifulSoup(page.content, "html.parser")
    pinned_data = soup.find_all("div", {"class": "pinned-item-list-item-content"})
    pinned_posts = []

    for post in pinned_data:
        pinned_posts.append(post.find("a")["href"])

    return pinned_posts


def get_projects(github_user, query):
    """
    Get a user's source repositories tagged with a given topic, using the GitHub
    Search API. Results are paginated so they are not capped at a single page.
    """
    api_url = "https://api.github.com/search/repositories"
    search = f"topic:{query} user:{github_user} fork:false"

    items = []
    page = 1
    while True:
        response = requests.get(
            api_url,
            params={
                "q": search,
                "per_page": 100,
                "page": page,
                "sort": "stars",
                "order": "desc",
            },
            timeout=10,
            headers=GITHUB_API_HEADERS,
        )
        data = response.json()
        batch = data.get("items", [])
        items.extend(batch)
        if not batch or len(items) >= data.get("total_count", 0):
            break
        page += 1

    projects_parsed = []
    for repo in items:
        stargazers = repo.get("stargazers_count", 0)
        members = repo.get("forks_count", 0)
        projects_parsed.append(
            {
                "name": repo["name"].replace("-", " ").capitalize(),
                "link": f"/{repo['full_name']}",
                "tags": [query],
                "stargazers": stargazers,
                "members": members,
                "score": stargazers + members * 5,
            }
        )

    return projects_parsed


def _load_json_cache(path):
    """
    Load a JSON cache file, returning an empty dict if missing or corrupt.
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def _save_json_cache(path, cache):
    """
    Persist a JSON cache file next to this module.
    """
    with open(path, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2)
        file.write("\n")


def _resolve_channel_id(youtube_username):
    """
    Resolve a YouTube channel id (UC...) from a handle, custom url or channel id.
    """
    youtube_username = youtube_username.strip("/")

    # Already a bare channel id.
    if re.fullmatch(r"UC[\w-]+", youtube_username):
        return youtube_username

    # Path like "channel/UC..." already contains the id.
    match = re.search(r"channel/(UC[\w-]+)", youtube_username)
    if match:
        return match.group(1)

    url = f"https://www.youtube.com/{youtube_username}"
    page = requests.get(url, timeout=10, headers=HEADERS)
    html = page.content.decode("utf-8", errors="ignore")

    # canonical/og:url always point to the page's own channel; the bare
    # channelId regexes can match another channel on some page variants.
    patterns = [
        r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]+)"',
        r'<meta property="og:url" content="https://www\.youtube\.com/channel/(UC[\w-]+)"',
        r'"(?:channelId|externalId)":"(UC[\w-]+)"',
        r"channel/(UC[\w-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)

    raise ValueError(f"Could not resolve channel id for '{youtube_username}'")


def _fetch_feed(channel_id):
    """
    Fetch and parse the RSS feed for a channel id, or None if it isn't valid
    XML (YouTube answers 404s and errors with an HTML page).
    """
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    page = requests.get(feed_url, timeout=10, headers=HEADERS)
    if page.status_code != 200:
        print(
            f"YouTube feed for {channel_id}: HTTP {page.status_code}",
            file=sys.stderr,
        )
        return None
    try:
        return ET.fromstring(page.content)
    except ET.ParseError as error:
        print(
            f"YouTube feed for {channel_id}: invalid XML ({error}), "
            f"starts with {page.content[:80]!r}",
            file=sys.stderr,
        )
        return None


def get_youtube_data(youtube_username, retries=3):
    """
    Get the latest videos from a YouTube channel using the official RSS feed.
    The resolved channel id is cached on disk; the channel page is only
    scraped when there is no cached id or its feed stops working. If YouTube
    can't be reached at all, the last successful video list is returned.
    """
    cache = _load_json_cache(CHANNEL_ID_CACHE)

    root = None
    channel_id = cache.get(youtube_username)
    if channel_id:
        root = _fetch_feed(channel_id)

    if root is None:
        for attempt in range(retries):
            if attempt:
                time.sleep(2)
            try:
                channel_id = _resolve_channel_id(youtube_username)
            except ValueError as error:
                print(error, file=sys.stderr)
                continue
            root = _fetch_feed(channel_id)
            if root is not None:
                break

    if root is None:
        video_cache = _load_json_cache(VIDEO_CACHE)
        if youtube_username in video_cache:
            print(
                f"YouTube unreachable, using cached videos for '{youtube_username}'",
                file=sys.stderr,
            )
            return video_cache[youtube_username]
        raise ValueError(f"Could not fetch YouTube feed for '{youtube_username}'")

    if cache.get(youtube_username) != channel_id:
        cache[youtube_username] = channel_id
        _save_json_cache(CHANNEL_ID_CACHE, cache)

    video_list = []
    for entry in root.findall("atom:entry", YT_FEED_NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=YT_FEED_NS)
        if not video_id:
            continue

        views = ""
        stats = entry.find(
            "media:group/media:community/media:statistics", YT_FEED_NS
        )
        if stats is not None:
            views = stats.get("views", "")

        video_list.append(
            {
                "title": entry.findtext(
                    "atom:title", default="", namespaces=YT_FEED_NS
                ),
                "id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/0.jpg",
                "published": entry.findtext(
                    "atom:published", default="", namespaces=YT_FEED_NS
                ),
                "viewCountText": views,
            }
        )

    if video_list:
        video_cache = _load_json_cache(VIDEO_CACHE)
        video_cache[youtube_username] = video_list
        _save_json_cache(VIDEO_CACHE, video_cache)

    return video_list

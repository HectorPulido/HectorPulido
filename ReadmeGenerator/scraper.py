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


def _video_entry(video_id, title, published="", views=""):
    """
    Build the video dict used by the README templates.
    """
    return {
        "title": title,
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/0.jpg",
        "published": published,
        "viewCountText": views,
    }


def _fetch_feed(feed_url):
    """
    Fetch and parse an RSS feed URL, or None if it isn't valid XML. YouTube's
    feed endpoint answers errors with an HTML page, and since ~2026 it also
    randomly 404s valid feeds, so failures here are expected and retryable.
    """
    page = requests.get(feed_url, timeout=10, headers=HEADERS)
    if page.status_code != 200:
        print(f"{feed_url}: HTTP {page.status_code}", file=sys.stderr)
        return None
    try:
        return ET.fromstring(page.content)
    except ET.ParseError as error:
        print(
            f"{feed_url}: invalid XML ({error}), "
            f"starts with {page.content[:80]!r}",
            file=sys.stderr,
        )
        return None


def _parse_feed_entries(root):
    """
    Extract the video list from a parsed YouTube RSS feed.
    """
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
            _video_entry(
                video_id,
                entry.findtext("atom:title", default="", namespaces=YT_FEED_NS),
                published=entry.findtext(
                    "atom:published", default="", namespaces=YT_FEED_NS
                ),
                views=views,
            )
        )

    return video_list


def _scrape_playlist_videos(playlist_id, limit=15):
    """
    Scrape a playlist page for its videos (newest first), as a fallback for
    when the RSS feed endpoint is down. Returns None on failure.
    """
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    try:
        page = requests.get(url, timeout=15, headers=HEADERS)
    except requests.RequestException as error:
        print(f"{url}: {error}", file=sys.stderr)
        return None
    if page.status_code != 200:
        print(f"{url}: HTTP {page.status_code}", file=sys.stderr)
        return None

    html = page.content.decode("utf-8", errors="ignore")
    match = re.search(r"ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
    if not match:
        print(f"{url}: no ytInitialData found", file=sys.stderr)
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError as error:
        print(f"{url}: bad ytInitialData ({error})", file=sys.stderr)
        return None

    video_list = []

    def walk(node):
        if isinstance(node, dict):
            # Playlist items are lockupViewModel nodes (older pages used
            # playlistVideoRenderer, kept for compatibility).
            if "lockupViewModel" in node:
                view = node["lockupViewModel"]
                video_id = view.get("contentId", "")
                title = (
                    view.get("metadata", {})
                    .get("lockupMetadataViewModel", {})
                    .get("title", {})
                    .get("content", "")
                )
                if re.fullmatch(r"[\w-]{11}", video_id):
                    video_list.append(_video_entry(video_id, title))
            elif "playlistVideoRenderer" in node:
                view = node["playlistVideoRenderer"]
                video_id = view.get("videoId", "")
                title = "".join(
                    run.get("text", "")
                    for run in view.get("title", {}).get("runs", [])
                )
                if video_id:
                    video_list.append(_video_entry(video_id, title))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return video_list[:limit] or None


def get_youtube_data(youtube_username, retries=3, exclude_shorts=False):
    """
    Get the latest videos from a YouTube channel. With exclude_shorts, only
    long-form uploads are returned (via the channel's auto-generated UULF
    playlist). Sources, in order: the official RSS feed, scraping the playlist
    page, and finally the last successful result cached on disk.
    """
    cache = _load_json_cache(CHANNEL_ID_CACHE)

    channel_id = cache.get(youtube_username)
    if not channel_id:
        for attempt in range(retries):
            if attempt:
                time.sleep(2)
            try:
                channel_id = _resolve_channel_id(youtube_username)
                break
            except (ValueError, requests.RequestException) as error:
                print(error, file=sys.stderr)
        if channel_id:
            cache[youtube_username] = channel_id
            _save_json_cache(CHANNEL_ID_CACHE, cache)

    video_list = None
    if channel_id:
        if exclude_shorts:
            # UULF<id> is the auto-generated "long-form uploads" playlist.
            playlist_id = "UULF" + channel_id[2:]
            feed_url = (
                f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
            )
        else:
            playlist_id = None
            feed_url = (
                f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            )

        for attempt in range(retries):
            if attempt:
                time.sleep(2)
            root = _fetch_feed(feed_url)
            if root is not None:
                video_list = _parse_feed_entries(root)
                break

        if video_list is None and playlist_id:
            video_list = _scrape_playlist_videos(playlist_id)

    if not video_list:
        video_cache = _load_json_cache(VIDEO_CACHE)
        if youtube_username in video_cache:
            print(
                f"YouTube unreachable, using cached videos for '{youtube_username}'",
                file=sys.stderr,
            )
            return video_cache[youtube_username]
        raise ValueError(f"Could not fetch YouTube videos for '{youtube_username}'")

    video_cache = _load_json_cache(VIDEO_CACHE)
    video_cache[youtube_username] = video_list
    _save_json_cache(VIDEO_CACHE, video_cache)

    return video_list

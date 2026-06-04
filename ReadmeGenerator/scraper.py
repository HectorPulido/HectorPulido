"""
Scraper module for GitHub and YouTube data.
"""

import re
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

    match = re.search(r'"(?:channelId|externalId)":"(UC[\w-]+)"', html)
    if not match:
        match = re.search(r"channel/(UC[\w-]+)", html)
    if not match:
        raise ValueError(f"Could not resolve channel id for '{youtube_username}'")

    return match.group(1)


def get_youtube_data(youtube_username):
    """
    Get the latest videos from a YouTube channel using the official RSS feed.
    """
    channel_id = _resolve_channel_id(youtube_username)
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    page = requests.get(feed_url, timeout=10, headers=HEADERS)
    root = ET.fromstring(page.content)

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

    return video_list

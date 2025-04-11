"""
Scraper module for GitHub and YouTube data.
"""

import json
import re

import requests
from bs4 import BeautifulSoup


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
    Get projects from a GitHub user profile based on a query.
    """
    github_url = (
        f"https://github.com/{github_user}?tab=repositories&q={query}&type=source"
    )
    page = requests.get(github_url, timeout=5)

    soup = BeautifulSoup(page.content, "html.parser")
    projects = soup.body.find("ul", {"data-filterable-for": "your-repos-filter"})
    if not projects:
        return []

    projects = projects.find_all("li")
    projects_parsed = []

    for project in projects:
        project_data = {}
        title = project.find("h3").a
        project_data["name"] = title.text.strip().replace("-", " ").capitalize()
        project_data["link"] = title["href"]
        project_data["tags"] = [query]

        impact = project.find("div", class_="f6 color-text-secondary mt-2")

        if impact:
            impact = impact.find_all("a")
            for data in impact:
                project_data[data["href"].split("/")[-1]] = int(data.text.strip())

            if "stargazers" not in project_data:
                project_data["stargazers"] = 0

            if "members" not in project_data:
                project_data["members"] = 0

            project_data["score"] = (
                project_data["stargazers"] + project_data["members"] * 5
            )
        else:
            project_data["score"] = 0

        projects_parsed.append(project_data)

    return projects_parsed


def get_youtube_data(youtube_username):
    """
    Get YouTube data from a user's channel.
    """
    regex = r'""([\sa-zA-Z0-9áéíóúÁÉÍÓÚ]+)""'
    replacement = r'"\1"'

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
    }

    url = f"https://www.youtube.com/{youtube_username}/videos"
    page = requests.get(url, timeout=5, headers=headers)
    html_str = page.content.decode("utf-8")

    json_string = html_str.split("var ytInitialData = ")[-1].split(";</script>")[0]
    cleaned_json_string = json_string.replace("\n", " ").replace("\r", " ")
    cleaned_json_string = re.sub(regex, replacement, cleaned_json_string)
    json_data = json.loads(cleaned_json_string, strict=False)

    video_list = []
    tabs = json_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
    for tab in tabs:
        if tab.get("tabRenderer", {}).get("title", "").lower() not in [
            "videos",
            "vídeos",
            "video",
        ]:
            continue
        for video in tab["tabRenderer"]["content"]["richGridRenderer"]["contents"]:
            video_data = {}
            if "richItemRenderer" not in video:
                continue
            video_data["title"] = video["richItemRenderer"]["content"]["videoRenderer"][
                "title"
            ]["runs"][0]["text"]
            video_data["id"] = video["richItemRenderer"]["content"]["videoRenderer"][
                "videoId"
            ]
            video_data["url"] = f"https://www.youtube.com/watch?v={video_data['id']}"
            video_data["thumbnail"] = (
                f"https://img.youtube.com/vi/{video_data['id']}/0.jpg"
            )
            video_data["published"] = video["richItemRenderer"]["content"][
                "videoRenderer"
            ]["publishedTimeText"]["simpleText"]
            video_data["viewCountText"] = video["richItemRenderer"]["content"][
                "videoRenderer"
            ]["viewCountText"]["simpleText"]
            video_list.append(video_data)
        break
    return video_list

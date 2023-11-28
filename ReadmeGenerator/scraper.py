import requests
from bs4 import BeautifulSoup
import json


def get_pinned(github_user):
    URL = f"https://github.com/{github_user}"
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, "html.parser")
    pinned_data = soup.find_all("div", {"class": "pinned-item-list-item-content"})
    pinned_posts = []

    for post in pinned_data:
        pinned_posts.append(post.find("a")["href"])

    return pinned_posts


def get_projects(github_user, query):
    URL = f"https://github.com/{github_user}?tab=repositories&q={query}&type=source"
    page = requests.get(URL)

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
    initial_data = "var ytInitialData = "
    final_data = ";"

    url = f"https://www.youtube.com/{youtube_username}/videos"
    page = requests.get(url, timeout=5)
    soup = BeautifulSoup(page.content, "html.parser")
    scripts = soup.body.find_all("script")

    videos_data = []

    for script in scripts:
        data = script.encode_contents().decode(errors="replace")
        if initial_data not in data:
            continue
        data = data.replace(initial_data, "").replace(final_data, "")
        tab_renderers = json.loads(data)["contents"]
        tab_renderers = tab_renderers["twoColumnBrowseResultsRenderer"]["tabs"]

        for tab in tab_renderers:
            if "tabRenderer" not in tab:
                continue

            if tab["tabRenderer"]["title"] != "Videos":
                continue

            videos = tab["tabRenderer"]["content"]["richGridRenderer"]["contents"]

            for video in videos:
                if "richItemRenderer" not in video:
                    continue
                video = video["richItemRenderer"]

                if "content" not in video:
                    continue
                video = video["content"]

                if "videoRenderer" not in video:
                    continue
                video = video["videoRenderer"]

                try:
                    video_data = {
                        "title": video["title"]["runs"][0]["text"],
                        "published": video["publishedTimeText"]["simpleText"],
                        "thumbnail": video["thumbnail"]["thumbnails"][-1]["url"],
                        "viewCountText": video["viewCountText"]["simpleText"],
                        "url": f"https://www.youtube.com/watch?v={video['videoId']}",
                    }
                    videos_data.append(video_data)
                except Exception as e:
                    print("Error parsing video data: ", e)
                    continue
    return videos_data

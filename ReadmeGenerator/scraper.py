import requests
from bs4 import BeautifulSoup
import json


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

        impact = project.find("div", class_="f6 text-gray mt-2").find_all("a")
        for data in impact:
            project_data[data["href"].split("/")[-1]] = int(data.text.strip())

        if "stargazers" not in project_data:
            project_data["stargazers"] = 0

        if "members" not in project_data:
            project_data["members"] = 0

        project_data["score"] = project_data["stargazers"] + project_data["members"] * 5

        projects_parsed.append(project_data)

    return projects_parsed

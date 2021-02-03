from scraper import get_projects


def process_title(title, context):
    for key, value in context.items():
        title = title.replace(f"-{key}-", str(value))

    if title.startswith("@"):
        return title[1:]
    return f"## {title}"


def intro(data, context):
    for key, value in context.items():
        data = data.replace(f"-{key}-", str(value))

    return f"# {data}\n"


def description(data, context):
    return f"{data}\n"


def categories(data, context):
    categories = []
    for category in context["categories"]:
        link = f"https://github.com/{context['github_user']}/{context['github_user']}/blob/master/{category['tag']}.md"
        template = f"<a href=\"{link}\">{category['emoji']}</a>"
        categories.append(template)

    categories_text = "\n".join(categories)

    return f"""
<p align="center">
    {categories_text}
</p>
"""


def right_image(data, context):
    return f"""
<a href="{data["link"]}">
    <img align="right" height="auto" width="200" src="{data["image"]}" />
</a>
    """


def tech_stack(data, context):
    title = process_title(data["title"], context)
    tech = "- " + "\n- ".join(data["tech"])
    return f"""
{title}
{tech}
    """


def awesome_projects(data, context):
    title = process_title(data["title"], context)
    projects = context["projects"]
    count = int(data["count"]) if int(data["count"]) <= len(projects) else len(projects)

    projects_data = ""

    for i in range(count):
        project = projects[i]
        link = project["link"]
        url = f"https://github.com{link}"

        emojis = ""
        if data["showEmojis"]:
            emojis = " ".join(
                [context["categories_emoji"][tag] for tag in project["tags"]]
            )

        score = ""
        if data["showScore"]:
            forks = project["members"]
            stars = project["stargazers"]
            score = f"🌿{forks} ⭐{stars}"

        projects_data += f"""- [{project["name"]} {score} {emojis}]({url}) \n"""

    return f"""
{title}
{projects_data}
"""


def extra(data, context):
    return data


def social(data, context):
    title = process_title(data["title"], context)

    social = ""
    for social_icon in data["social"]:
        social += f"""    
<a href="{social_icon["url"]}" target="blank">
    <img align="center" alt="{social_icon["alt"]}" width="30px" src="{social_icon["image"]}" /> &nbsp; &nbsp;
</a>
        """

    return f"""
{title}
<p align="center">
{social}
</p>
    """


def space(data, context):
    return "<br>"


def filter_projects(projects):
    temp_projects = {}
    for project in projects:
        if project["name"] not in temp_projects:
            temp_projects[project["name"]] = project
            continue
        temp_projects[project["name"]]["tags"].append(project["tags"][0])
    return list(temp_projects.values())


def set_config(github_user, categories):
    projects = []
    projects_by_categories = {}
    for category in categories:
        project = get_projects(github_user, category["tag"])
        projects_by_categories[category["tag"]] = project
        projects += project

    projects.sort(reverse=True, key=lambda x: x["score"])
    projects = filter_projects(projects)

    context = {}
    context["projects"] = projects
    context["github_user"] = github_user
    context["categories"] = categories
    context["categories_emoji"] = {x["tag"]: x["emoji"] for x in categories}

    return context


types = {
    "space": space,
    "intro": intro,
    "description": description,
    "categories": categories,
    "rightImage": right_image,
    "techStack": tech_stack,
    "awesomeProjects": awesome_projects,
    "extra": extra,
    "social": social,
}

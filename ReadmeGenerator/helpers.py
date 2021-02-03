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
        link = "https://github.com/{}/{}/blob/master/{}.md".format(
            context["github_user"], context["github_user"], category["tag"]
        )
        template = f"<a href=\"{link}\">{category['emoji']}</a>"
        categories.append(template)

    categories_text = "\n".join(categories)

    return f'<p align="center">\n{categories_text}\n</p>\n'


def right_image(data, context):
    properties = 'align="right" height="auto" width="200"'
    return '<a href="{}">\n<img {} src="{}"/>\n</a>\n'.format(
        data["link"], properties, data["image"]
    )


def tech_stack(data, context):
    title = process_title(data["title"], context)
    tech = "- " + "\n- ".join(data["tech"])
    return f"{title}\n{tech}\n"


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

        projects_data += f'- [{project["name"]} {score} {emojis}]({url}) \n'

    return f"{title}\n{projects_data}\n"


def extra(data, context):
    return data


def social(data, context):
    title = process_title(data["title"], context)

    properties = 'align="center" width="30px"'

    social = ""
    for social_icon in data["social"]:
        social += '<a href="{}" {}>\n<img {} alt="{}" src="{}"/></a>{}'.format(
            social_icon["url"],
            'target="blank"',
            properties,
            social_icon["alt"],
            social_icon["image"],
            " &nbsp; &nbsp;\n",
        )

    return f'{title}\n<p align="center">\n{social}\n</p>\n'


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

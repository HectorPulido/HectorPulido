from scraper import get_projects, get_youtube_data, get_pinned


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


def description(data, _):
    return f"{data}\n"


def get_categories(_, context):
    categories = []
    for category in context["categories"]:
        link = "https://github.com/{}/{}/blob/master/{}.md".format(
            context["github_user"], context["github_user"], category["tag"]
        )
        template = f"<a href=\"{link}\">{category['emoji']}</a>"
        categories.append(template)

    categories_text = "\n".join(categories)

    return f'<p align="center">\n{categories_text}\n</p>\n'


def right_image(data, _):
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
    projects = context["projects"].copy()
    pinned_projects = []

    if data["ignore_pinned"]:
        pinned_projects = context["pinned_projects"]
        for project in projects:
            link = project["link"]
            if any([pinned_project in link for pinned_project in pinned_projects]):
                projects.remove(project)
                continue

    data_count = int(data["count"])
    len_projects = len(projects)

    count = data_count if data_count <= len_projects else len_projects

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
    if "title" in data:
        title = process_title(data["title"], context)
        data = data["data"]
        return f"{title}\n{data}\n"
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


def space(_, __):
    return "<br>"


def youtube_video_list(data, context):
    title = process_title(data["title"], context)
    videos = get_youtube_data(data["user_id"])
    count = int(data["count"]) if int(data["count"]) <= len(videos) else len(videos)

    video_data = ""

    if data["show_thumbnails"]:
        video_data = '<p align="center">'

        if data["show_titles"]:
            for i in range(count):
                video = videos[i]
                video_data += f'<p><a href="{video["url"]}" target="blank"><img align="center" width="100px" src="{video["thumbnail"]}"/>&nbsp; &nbsp;{video["title"]}</a></p>'
        else:
            for i in range(count):
                video = videos[i]
                video_data += f'<a href="{video["url"]}" target="blank"><img align="center" width="200px" src="{video["thumbnail"]}"/></a>&nbsp;&nbsp;\n'

        video_data += "</p>"
    else:
        for i in range(count):
            video = videos[i]
            video_data += f'- [{video["title"]}]({video["url"]}) \n'

    return f"{title}\n{video_data}\n"


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

    context["pinned_projects"] = get_pinned(github_user)

    return context


types = {
    "space": space,
    "intro": intro,
    "description": description,
    "categories": get_categories,
    "rightImage": right_image,
    "techStack": tech_stack,
    "awesomeProjects": awesome_projects,
    "extra": extra,
    "social": social,
    "youtube_video_list": youtube_video_list,
}

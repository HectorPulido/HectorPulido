def process_title(title):
    if title.startswith("@"):
        return title[1:]
    return f"## {title}"

def intro(data, context):
    return f"# {data}\n"

def description(data, context):
    return f"{data}\n"

def categories(data, context):
    return ""

def right_image(data, context):
    return f'''
<a href="{data["image"]}">
    <img align="right" height="auto" width="200" src="{data["link"]}" />
</a>
    '''

def tech_stack(data, context):
    title = process_title(data["title"])
    tech = "- " + "\n- ".join(data["tech"])
    return f'''
{title}
{tech}
    '''

def awesome_projects(data, context):
    return ""

def extra(data, context):
    return data

def social(data, context):
    title = process_title(data["title"])

    social = ""
    for social_icon in data["social"]:
        social += f'''    
<a href="{social_icon["url"]}" target="blank">
    <img align="center" alt="{social_icon["alt"]}" width="30px" src="{social_icon["image"]}" /> &nbsp; &nbsp;
</a>
        '''

    return f'''
{title}
<p align="center">
{social}
</p>
    '''

types = {
    "intro": intro,
    "description": description,
    "categories": categories,
    "rightImage": right_image,
    "techStack": tech_stack,
    "awesomeProjects": awesome_projects,
    "extra": extra,
    "social": social,
}
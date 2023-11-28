import json
from helpers import types, set_config

FILEPATH = "../"
FILENAME_BASE = "config_base.json"
FILENAME_PROJECTS = "config_projects.json"

f = open(FILENAME_BASE, "r", errors="ignore", encoding="utf-8")
data = json.loads(f.read())

readme_file = ""
context = {}

for block in data:
    if block["type"] == "config":
        github_user = block["data"]["githubUser"]
        categories = block["data"]["categories"]
        context = set_config(github_user, categories)
        continue

    readme_file += types[block["type"]](block["data"], context)
    readme_file += "\n\n"

f = open(f"{FILEPATH}README.md", "w", errors="ignore", encoding="utf-8")
f.write(readme_file)
f.close()

f = open(FILENAME_PROJECTS, "r", errors="ignore", encoding="utf-8")
data = json.loads(f.read())

for category in categories:
    current_file = ""
    temp_context = context.copy()
    temp_context["category"] = category["name"]
    temp_context["emoji"] = category["emoji"]
    temp_context["projects"] = [
        x for x in context["projects"] if category["tag"] in x["tags"]
    ]
    for block in data:
        current_file += types[block["type"]](block["data"], temp_context)
        current_file += "\n\n"

    f = open(f"{FILEPATH}{category['tag']}.md", "w", errors="ignore", encoding="utf-8")
    f.write(current_file)
    f.close()

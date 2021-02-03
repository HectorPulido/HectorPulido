import json
from helpers import types

FILENAME = "config.py"
f = open(FILENAME, "r")
data = json.loads(f.read())

readme_file = ""

context = {}
github_user = ""
categories = []

for block in data:
    if block["type"] == "config":
        github_user = block["data"]["githubUser"]
        categories = block["data"]["categories"]
        continue

    readme_file += types[block["type"]](block["data"], context)
    readme_file += "<br />\n\n"

f = open("README.md", "w")
f.write(readme_file)
f.close()
"""
This script generates a README.md file and category-specific markdown files
for a GitHub profile based on a configuration file. It reads the configuration
from a JSON file, processes the data, and generates the markdown files.
"""

import json
import sys

try:
    from helpers import types, set_config
except ImportError:
    from .helpers import types, set_config

FILEPATH = "../"
FILENAME_BASE = "config_base.json"
FILENAME_PROJECTS = "config_projects.json"


def load_json(path):
    """
    Load and parse a JSON file.
    """
    with open(path, "r", errors="ignore", encoding="utf-8") as file:
        return json.loads(file.read())


def write_file(path, content):
    """
    Write text content to a file.
    """
    with open(path, "w", errors="ignore", encoding="utf-8") as file:
        file.write(content)


def render_blocks(blocks, context):
    """
    Render a list of blocks, skipping (and logging) any block that fails so a
    single broken section never aborts the whole README.
    """
    output = ""
    for block in blocks:
        try:
            output += types[block["type"]](block["data"], context)
            output += "\n\n"
        except Exception as error:  # pylint: disable=broad-except
            print(
                f"Skipping block '{block.get('type')}': {error}",
                file=sys.stderr,
            )
    return output


def main():
    """
    Generate the main README and the per-category markdown files.
    """
    base_blocks = load_json(FILENAME_BASE)

    context = {}
    categories = []
    content_blocks = []
    for block in base_blocks:
        if block["type"] == "config":
            context = set_config(
                block["data"]["githubUser"], block["data"]["categories"]
            )
            categories = block["data"]["categories"]
            continue
        content_blocks.append(block)

    write_file(f"{FILEPATH}README.md", render_blocks(content_blocks, context))

    project_blocks = load_json(FILENAME_PROJECTS)
    for category in categories:
        temp_context = context.copy()
        temp_context["category"] = category["name"]
        temp_context["emoji"] = category["emoji"]
        temp_context["projects"] = [
            x for x in context["projects"] if category["tag"] in x["tags"]
        ]
        write_file(
            f"{FILEPATH}{category['tag']}.md",
            render_blocks(project_blocks, temp_context),
        )


if __name__ == "__main__":
    main()

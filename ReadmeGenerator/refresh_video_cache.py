"""
Refresh the on-disk YouTube caches (channel id + latest videos) used by the
README generator. Meant to be run on a schedule from a network YouTube does
not block, so CI (where YouTube 404s datacenter IPs) can build the README
from a fresh cache instead of a stale one.
"""

import json
import sys

try:
    from scraper import get_youtube_data
except ImportError:
    from .scraper import get_youtube_data

FILENAME_BASE = "config_base.json"


def main():
    """
    Refresh the video cache for every youtube_video_list block in the config.
    """
    with open(FILENAME_BASE, "r", errors="ignore", encoding="utf-8") as file:
        blocks = json.load(file)

    failures = 0
    for block in blocks:
        if block["type"] != "youtube_video_list":
            continue
        data = block["data"]
        try:
            videos = get_youtube_data(
                data["user_id"],
                retries=5,
                exclude_shorts=data.get("exclude_shorts", False),
            )
            print(f"{data['user_id']}: cached {len(videos)} videos")
        except ValueError as error:
            print(error, file=sys.stderr)
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

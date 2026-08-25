#!/usr/bin/env python3
"""Refresh the auto-updated writing block in README.md from the blog RSS feed."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import namedtuple
from email.utils import parsedate_to_datetime
from pathlib import Path

START_MARKER = "<!-- posts start -->"
END_MARKER = "<!-- posts end -->"

POST_LIMIT = 5

MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

FEED_URL = "https://serhiichuk.dev/blog/rss.xml"
TIMEOUT_SECONDS = 10
USER_AGENT = "xSAVIKx-profile-readme"

Post = namedtuple("Post", ["title", "url", "date"])


def replace_block(text: str, start: str, end: str, new_content: str) -> str:
    """Replace the region between two markers, leaving the markers in place."""
    start_index = text.find(start)
    if start_index == -1:
        raise ValueError(f"start marker not found: {start}")
    end_index = text.find(end)
    if end_index == -1:
        raise ValueError(f"end marker not found: {end}")
    if end_index < start_index:
        raise ValueError("end marker appears before start marker")
    head = text[: start_index + len(start)]
    tail = text[end_index:]
    return f"{head}\n{new_content}\n{tail}"


def parse_feed(xml_bytes: bytes, limit: int = POST_LIMIT) -> list:
    """Parse RSS 2.0 bytes into Post records, newest first, capped at limit."""
    root = ET.fromstring(xml_bytes)
    posts = []
    for item in root.iterfind("./channel/item"):
        title = item.findtext("title")
        link = item.findtext("link")
        pub_date = item.findtext("pubDate")
        if not (title and link and pub_date):
            continue
        posts.append(
            Post(title.strip(), link.strip(), parsedate_to_datetime(pub_date))
        )
    if not posts:
        raise ValueError("feed contained no usable items")
    posts.sort(key=lambda post: post.date, reverse=True)
    return posts[:limit]


def render(posts: list) -> str:
    """Render Post records as a markdown list, one line each."""
    lines = []
    for post in posts:
        month = MONTHS[post.date.month - 1]
        stamp = f"{post.date.day} {month} {post.date.year}"
        lines.append(f"- [{post.title}]({post.url}) — {stamp}")
    return "\n".join(lines)


def fetch(url: str, timeout: int = TIMEOUT_SECONDS, retries: int = 1) -> bytes:
    """Fetch a URL, retrying once. Raises RuntimeError if every attempt fails."""
    last_error = None
    for _ in range(retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, OSError) as error:
            last_error = error
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", default="README.md", type=Path)
    parser.add_argument("--feed-url", default=FEED_URL)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the rendered block instead of writing the README",
    )
    args = parser.parse_args(argv)

    try:
        posts = parse_feed(fetch(args.feed_url))
    except Exception as error:  # noqa: BLE001 - any failure must leave the README alone
        print(f"error: {error}", file=sys.stderr)
        return 1

    block = render(posts)

    if args.dry_run:
        print(block)
        return 0

    text = args.readme.read_text(encoding="utf-8")
    updated = replace_block(text, START_MARKER, END_MARKER, block)
    if updated != text:
        args.readme.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Refresh the auto-updated writing block in README.md from the blog RSS feed."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import namedtuple
from email.utils import parsedate_to_datetime

START_MARKER = "<!-- posts start -->"
END_MARKER = "<!-- posts end -->"

POST_LIMIT = 5

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

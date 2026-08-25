#!/usr/bin/env python3
"""Refresh the auto-updated writing block in README.md from the blog RSS feed."""

from __future__ import annotations

START_MARKER = "<!-- posts start -->"
END_MARKER = "<!-- posts end -->"


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

# Profile README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `xSAVIKx/xSAVIKx` profile README with a writing section that refreshes itself nightly from the personal blog's RSS feed.

**Architecture:** A hand-written `README.md` is the source of truth for all static copy. A single stdlib-only Python script rewrites exactly one region of it, delimited by HTML comment markers, from `https://serhiichuk.dev/blog/rss.xml`. A scheduled GitHub Action runs the script and commits only when the file actually changed. Any fetch or parse failure aborts before writing, so the published page can never show an empty section.

**Tech Stack:** Python 3 standard library only (`urllib.request`, `xml.etree.ElementTree`, `email.utils`, `argparse`, `unittest`). GitHub Actions. No third-party packages, at runtime or in tests.

**Spec:** `docs/superpowers/specs/2026-08-25-profile-readme-design.md`

## Global Constraints

- **Zero third-party dependencies.** No `requirements.txt`, no `pip install`, no lockfile. This is the central design commitment; a task that adds a dependency has failed. Tests use stdlib `unittest`, not pytest — the spec named no framework, and `unittest` keeps the "clone and run, install nothing" property intact.
- **Single data source:** `https://serhiichuk.dev/blog/rss.xml`. No fallback source. No HTML scraping anywhere.
- **Only the region between `<!-- posts start -->` and `<!-- posts end -->` may be written by automation.** Everything else in `README.md` is hand-written.
- **On any fetch or parse failure, exit non-zero without modifying `README.md`.**
- **Post cap:** 5, newest first.
- **Date rendering:** `9 Jul 2026` — no leading zero on the day, three-letter English month. Month names come from a module-level tuple, never `strftime("%b")`, so output is locale-independent.
- **Voice rules for all copy:** no emoji, no badges, no stats/streak/trophy widgets, no employer name, no job title.
- **Repo must ultimately be published as a public GitHub repo named exactly `xSAVIKx`.**

---

### Task 1: Marker replacement

The pure function that rewrites a delimited region of text. No I/O, no network. Everything else depends on this being exactly right, because a bug here corrupts the hand-written parts of the profile page.

**Files:**
- Create: `scripts/update_writing.py`
- Test: `tests/test_update_writing.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `START_MARKER: str = "<!-- posts start -->"`
  - `END_MARKER: str = "<!-- posts end -->"`
  - `replace_block(text: str, start: str, end: str, new_content: str) -> str` — returns `text` with the region between the markers replaced by `new_content`, markers preserved. Raises `ValueError` if either marker is absent or if `end` precedes `start`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_update_writing.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import update_writing as uw


class TestReplaceBlock(unittest.TestCase):
    def test_replaces_content_between_markers(self):
        text = "before\n<!-- posts start -->\nold\n<!-- posts end -->\nafter\n"
        result = uw.replace_block(text, uw.START_MARKER, uw.END_MARKER, "new")
        self.assertEqual(
            result,
            "before\n<!-- posts start -->\nnew\n<!-- posts end -->\nafter\n",
        )

    def test_preserves_surrounding_text_exactly(self):
        text = "# Title\n\ntrailing  spaces  \n<!-- posts start -->\nx\n<!-- posts end -->\n\n## Elsewhere\n"
        result = uw.replace_block(text, uw.START_MARKER, uw.END_MARKER, "y")
        self.assertTrue(result.startswith("# Title\n\ntrailing  spaces  \n"))
        self.assertTrue(result.endswith("\n\n## Elsewhere\n"))

    def test_is_idempotent(self):
        text = "a\n<!-- posts start -->\nold\n<!-- posts end -->\nb\n"
        once = uw.replace_block(text, uw.START_MARKER, uw.END_MARKER, "new")
        twice = uw.replace_block(once, uw.START_MARKER, uw.END_MARKER, "new")
        self.assertEqual(once, twice)

    def test_replaces_empty_region(self):
        text = "a\n<!-- posts start -->\n<!-- posts end -->\nb\n"
        result = uw.replace_block(text, uw.START_MARKER, uw.END_MARKER, "new")
        self.assertEqual(result, "a\n<!-- posts start -->\nnew\n<!-- posts end -->\nb\n")

    def test_raises_when_start_marker_missing(self):
        with self.assertRaises(ValueError):
            uw.replace_block("no markers here\n", uw.START_MARKER, uw.END_MARKER, "new")

    def test_raises_when_end_marker_missing(self):
        text = "a\n<!-- posts start -->\nb\n"
        with self.assertRaises(ValueError):
            uw.replace_block(text, uw.START_MARKER, uw.END_MARKER, "new")

    def test_raises_when_markers_inverted(self):
        text = "<!-- posts end -->\nmiddle\n<!-- posts start -->\n"
        with self.assertRaises(ValueError):
            uw.replace_block(text, uw.START_MARKER, uw.END_MARKER, "new")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'update_writing'`

- [ ] **Step 3: Write the minimal implementation**

Create `scripts/update_writing.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/update_writing.py tests/test_update_writing.py
git commit -m "feat: add marker-delimited block replacement"
```

---

### Task 2: RSS feed parsing

Turn the feed's bytes into sorted, capped post records. Uses both a captured real fixture (proves it handles the actual feed) and a small inline feed (gives stable exact-value assertions that survive the blog gaining new posts).

**Files:**
- Modify: `scripts/update_writing.py`
- Create: `tests/fixtures/blog-rss.xml`
- Modify: `tests/test_update_writing.py`

**Interfaces:**
- Consumes: nothing from Task 1
- Produces:
  - `Post` — `namedtuple("Post", ["title", "url", "date"])`, where `date` is a timezone-aware `datetime.datetime`
  - `POST_LIMIT: int = 5`
  - `parse_feed(xml_bytes: bytes, limit: int = POST_LIMIT) -> list[Post]` — newest first, capped at `limit`. Raises `ValueError` when the feed yields no usable items; lets `xml.etree.ElementTree.ParseError` propagate on malformed XML.

- [ ] **Step 1: Capture the real feed as a test fixture**

```bash
mkdir -p tests/fixtures
curl -sS --max-time 20 https://serhiichuk.dev/blog/rss.xml -o tests/fixtures/blog-rss.xml
head -c 200 tests/fixtures/blog-rss.xml
```

Expected: an XML declaration followed by `<rss version="2.0">`. If the file is HTML or empty, stop and report — do not proceed with a bad fixture.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_update_writing.py`, above the `if __name__ == "__main__":` block:

```python
MINIMAL_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Yurii Serhiichuk - Blog</title>
    <item>
      <title>Older post</title>
      <link>https://serhiichuk.dev/blog/older/</link>
      <pubDate>Thu, 09 Jul 2026 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Newer post</title>
      <link>https://serhiichuk.dev/blog/newer/</link>
      <pubDate>Fri, 21 Aug 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "blog-rss.xml"


class TestParseFeed(unittest.TestCase):
    def test_extracts_title_and_url(self):
        posts = uw.parse_feed(MINIMAL_FEED)
        self.assertEqual(posts[0].title, "Newer post")
        self.assertEqual(posts[0].url, "https://serhiichuk.dev/blog/newer/")

    def test_sorts_newest_first_regardless_of_feed_order(self):
        posts = uw.parse_feed(MINIMAL_FEED)
        self.assertEqual([p.title for p in posts], ["Newer post", "Older post"])

    def test_parses_rfc_2822_date_as_timezone_aware(self):
        posts = uw.parse_feed(MINIMAL_FEED)
        newest = posts[0].date
        self.assertEqual((newest.year, newest.month, newest.day), (2026, 8, 21))
        self.assertIsNotNone(newest.tzinfo)

    def test_respects_limit(self):
        self.assertEqual(len(uw.parse_feed(MINIMAL_FEED, limit=1)), 1)

    def test_returns_all_items_when_fewer_than_limit(self):
        posts = uw.parse_feed(MINIMAL_FEED, limit=5)
        self.assertEqual(len(posts), 2)

    def test_parses_the_real_captured_feed(self):
        posts = uw.parse_feed(FIXTURE_PATH.read_bytes())
        self.assertEqual(len(posts), uw.POST_LIMIT)
        for post in posts:
            self.assertTrue(post.title)
            self.assertTrue(post.url.startswith("https://"))
            self.assertIsNotNone(post.date.tzinfo)
        dates = [p.date for p in posts]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_raises_on_feed_with_no_items(self):
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
        with self.assertRaises(ValueError):
            uw.parse_feed(empty)

    def test_raises_on_malformed_xml(self):
        with self.assertRaises(ET.ParseError):
            uw.parse_feed(b"<rss><channel><item>unclosed")
```

Add to the imports at the top of the test file:

```python
import xml.etree.ElementTree as ET
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `AttributeError: module 'update_writing' has no attribute 'parse_feed'`

- [ ] **Step 4: Write the minimal implementation**

Add to the imports at the top of `scripts/update_writing.py`:

```python
import xml.etree.ElementTree as ET
from collections import namedtuple
from email.utils import parsedate_to_datetime
```

Add below the existing marker constants:

```python
POST_LIMIT = 5

Post = namedtuple("Post", ["title", "url", "date"])
```

Add at the end of the module:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, 15 tests

- [ ] **Step 6: Commit**

```bash
git add scripts/update_writing.py tests/test_update_writing.py tests/fixtures/blog-rss.xml
git commit -m "feat: parse blog RSS feed into sorted post records"
```

---

### Task 3: Markdown rendering

Turn `Post` records into the exact markdown lines that land in the README. Split from parsing because the output format is a product decision a reviewer may reject on its own.

**Files:**
- Modify: `scripts/update_writing.py`
- Modify: `tests/test_update_writing.py`

**Interfaces:**
- Consumes: `Post` from Task 2
- Produces:
  - `MONTHS: tuple[str, ...]` — `("Jan", "Feb", ..., "Dec")`
  - `render(posts: list) -> str` — newline-joined markdown list, no trailing newline. One line per post: `- [Title](url) — 9 Jul 2026`, using an em dash (`—`, U+2014).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_update_writing.py`, above the `if __name__ == "__main__":` block:

```python
class TestRender(unittest.TestCase):
    def test_renders_one_line_per_post(self):
        rendered = uw.render(uw.parse_feed(MINIMAL_FEED))
        self.assertEqual(len(rendered.splitlines()), 2)

    def test_line_format_matches_spec(self):
        posts = uw.parse_feed(MINIMAL_FEED)
        rendered = uw.render(posts)
        self.assertEqual(
            rendered.splitlines()[0],
            "- [Newer post](https://serhiichuk.dev/blog/newer/) — 21 Aug 2026",
        )

    def test_day_has_no_leading_zero(self):
        rendered = uw.render(uw.parse_feed(MINIMAL_FEED))
        self.assertIn("— 9 Jul 2026", rendered)
        self.assertNotIn("09 Jul", rendered)

    def test_has_no_trailing_newline(self):
        rendered = uw.render(uw.parse_feed(MINIMAL_FEED))
        self.assertFalse(rendered.endswith("\n"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `AttributeError: module 'update_writing' has no attribute 'render'`

- [ ] **Step 3: Write the minimal implementation**

Add below `POST_LIMIT` in `scripts/update_writing.py`:

```python
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
```

Add at the end of the module:

```python
def render(posts: list) -> str:
    """Render Post records as a markdown list, one line each."""
    lines = []
    for post in posts:
        month = MONTHS[post.date.month - 1]
        stamp = f"{post.date.day} {month} {post.date.year}"
        lines.append(f"- [{post.title}]({post.url}) — {stamp}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, 19 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/update_writing.py tests/test_update_writing.py
git commit -m "feat: render posts as dated markdown list"
```

---

### Task 4: Fetching and the CLI

Wire the pure functions together behind a command-line entry point, and implement the failure rule that protects the published page.

**Files:**
- Modify: `scripts/update_writing.py`
- Modify: `tests/test_update_writing.py`

**Interfaces:**
- Consumes: `replace_block`, `parse_feed`, `render`, `START_MARKER`, `END_MARKER`
- Produces:
  - `FEED_URL: str = "https://serhiichuk.dev/blog/rss.xml"`
  - `TIMEOUT_SECONDS: int = 10`
  - `fetch(url: str, timeout: int = TIMEOUT_SECONDS, retries: int = 1) -> bytes` — raises `RuntimeError` after all attempts fail
  - `main(argv: list | None = None) -> int` — returns `0` on success, `1` on fetch or parse failure. Flags: `--readme` (default `README.md`), `--feed-url` (default `FEED_URL`), `--dry-run`.

- [ ] **Step 1: Write the failing tests**

Add to the imports at the top of `tests/test_update_writing.py`:

```python
import io
import tempfile
from contextlib import redirect_stdout
from unittest import mock
```

Append above the `if __name__ == "__main__":` block:

```python
README_TEMPLATE = "# Title\n\n## Writing\n\n<!-- posts start -->\nstale\n<!-- posts end -->\n\n## Elsewhere\n"


class TestFetch(unittest.TestCase):
    def test_retries_once_then_raises(self):
        with mock.patch.object(uw.urllib.request, "urlopen", side_effect=OSError("boom")) as opener:
            with self.assertRaises(RuntimeError):
                uw.fetch("https://example.invalid/feed.xml")
        self.assertEqual(opener.call_count, 2)


class TestMain(unittest.TestCase):
    def _readme(self, text=README_TEMPLATE):
        handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        return Path(handle.name)

    def test_writes_rendered_block_into_readme(self):
        readme = self._readme()
        with mock.patch.object(uw, "fetch", return_value=MINIMAL_FEED):
            exit_code = uw.main(["--readme", str(readme)])
        self.assertEqual(exit_code, 0)
        text = readme.read_text(encoding="utf-8")
        self.assertIn("- [Newer post](https://serhiichuk.dev/blog/newer/) — 21 Aug 2026", text)
        self.assertNotIn("stale", text)
        self.assertIn("## Elsewhere", text)

    def test_leaves_readme_untouched_when_fetch_fails(self):
        readme = self._readme()
        original = readme.read_text(encoding="utf-8")
        with mock.patch.object(uw, "fetch", side_effect=RuntimeError("network down")):
            exit_code = uw.main(["--readme", str(readme)])
        self.assertEqual(exit_code, 1)
        self.assertEqual(readme.read_text(encoding="utf-8"), original)

    def test_leaves_readme_untouched_when_feed_is_empty(self):
        readme = self._readme()
        original = readme.read_text(encoding="utf-8")
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
        with mock.patch.object(uw, "fetch", return_value=empty):
            exit_code = uw.main(["--readme", str(readme)])
        self.assertEqual(exit_code, 1)
        self.assertEqual(readme.read_text(encoding="utf-8"), original)

    def test_dry_run_prints_block_and_does_not_write(self):
        readme = self._readme()
        original = readme.read_text(encoding="utf-8")
        buffer = io.StringIO()
        with mock.patch.object(uw, "fetch", return_value=MINIMAL_FEED):
            with redirect_stdout(buffer):
                exit_code = uw.main(["--readme", str(readme), "--dry-run"])
        self.assertEqual(exit_code, 0)
        self.assertIn("- [Newer post]", buffer.getvalue())
        self.assertEqual(readme.read_text(encoding="utf-8"), original)

    def test_is_idempotent_across_runs(self):
        readme = self._readme()
        with mock.patch.object(uw, "fetch", return_value=MINIMAL_FEED):
            uw.main(["--readme", str(readme)])
            first = readme.read_text(encoding="utf-8")
            uw.main(["--readme", str(readme)])
            second = readme.read_text(encoding="utf-8")
        self.assertEqual(first, second)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `AttributeError: module 'update_writing' has no attribute 'fetch'`

- [ ] **Step 3: Write the minimal implementation**

Add to the imports at the top of `scripts/update_writing.py`:

```python
import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path
```

Add below `MONTHS`:

```python
FEED_URL = "https://serhiichuk.dev/blog/rss.xml"
TIMEOUT_SECONDS = 10
USER_AGENT = "xSAVIKx-profile-readme"
```

Add at the end of the module:

```python
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
```

Note: `replace_block` is deliberately outside the `try`. A missing marker is a bug in the README, not a transient outage — it should fail loudly with a traceback rather than being swallowed as a network error.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, 25 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/update_writing.py tests/test_update_writing.py
git commit -m "feat: add feed fetching and CLI entry point"
```

---

### Task 5: The README itself

All the static copy. This is the actual product; the preceding tasks only keep one section of it fresh.

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: `START_MARKER` / `END_MARKER` from Task 1 — the marker text must match byte for byte
- Produces: a `README.md` that Task 6 runs against

- [ ] **Step 1: Write the README**

Create `README.md` with exactly this content:

```markdown
# Yurii Serhiichuk

Cloud architecture and DevOps.
Google Developer Expert, Cloud.

I make cloud infrastructure cheaper and less exciting to operate. Lately: agents that run production systems, and portable knowledge formats for LLM tooling.

## Selected work

**[sre-agent](https://github.com/xSAVIKx/sre-agent)** — Multi-agent SRE platform: agents that triage and act on production incidents.

**[okf-skills](https://github.com/xSAVIKx/okf-skills)** — Open Knowledge Format: your data's structure as a portable, versioned map, as code.

**[cloudevents/sdk-python](https://github.com/cloudevents/sdk-python)** — Top contributor to the Python SDK for the CNCF CloudEvents spec.

**[AndroidScreencast](https://github.com/xSAVIKx/AndroidScreencast)** — Display and control Android devices from your desktop.

## Writing

<!-- posts start -->
<!-- posts end -->

## Elsewhere

**[serhiichuk.dev](https://serhiichuk.dev)** — best place to reach me

[LinkedIn](https://linkedin.com/in/YuriiSerhiichuk) · [X](https://x.com/xSAVIKx) · [Sessionize](https://sessionize.com/yuriiserhiichuk) · [dev.to](https://dev.to/xsavikx) · [Medium](https://xsavikx.medium.com/)
```

**Critical formatting detail:** the two headline lines ("Cloud architecture and DevOps." and "Google Developer Expert, Cloud.") must render as two lines, not one paragraph. Markdown collapses a single newline, so the first of those lines needs **two trailing spaces** to force a hard break. Add them, and do not let an editor strip trailing whitespace from that line.

- [ ] **Step 2: Verify the hard break survived**

Run: `sed -n '3p' README.md | cat -A | tail -c 40`
Expected: the line ends with `  $` — two spaces before the line terminator. If it ends with just `$`, re-add the two spaces.

- [ ] **Step 3: Verify the markers are byte-identical to the script's constants**

Run: `python3 -c "import sys; sys.path.insert(0, 'scripts'); import update_writing as u; t=open('README.md').read(); assert u.START_MARKER in t and u.END_MARKER in t; print('markers OK')"`
Expected: `markers OK`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "feat: add profile README static content"
```

---

### Task 6: GitHub Actions workflow and first live run

Automate the refresh, then prove the whole thing works end to end against the real feed.

**Files:**
- Create: `.github/workflows/update-readme.yml`
- Modify: `README.md` (by running the script for real)

**Interfaces:**
- Consumes: `scripts/update_writing.py` CLI from Task 4, `README.md` from Task 5
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Do a live dry run against the real feed**

Run: `python3 scripts/update_writing.py --dry-run`
Expected: five markdown lines, newest post first, each of the form `- [Title](https://serhiichuk.dev/blog/...) — 21 Aug 2026`. If this fails, stop and report — do not write the workflow against a broken script.

- [ ] **Step 2: Populate the README for real**

```bash
python3 scripts/update_writing.py
git diff --stat
```

Expected: `README.md` changed, five post lines now sit between the markers.

- [ ] **Step 3: Verify idempotency on the real file**

```bash
BEFORE=$(sha256sum README.md | cut -d' ' -f1)
python3 scripts/update_writing.py
AFTER=$(sha256sum README.md | cut -d' ' -f1)
[ "$BEFORE" = "$AFTER" ] && echo "idempotent OK" || echo "FAIL: second run changed the file"
```

Expected: `idempotent OK`. A second run against unchanged feed content must produce a byte-identical file, or the nightly job will commit noise every night.

- [ ] **Step 4: Create the workflow**

Create `.github/workflows/update-readme.yml`:

```yaml
name: Update README

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run tests
        run: python3 -m unittest discover -s tests -v

      - name: Refresh writing block
        run: python3 scripts/update_writing.py

      - name: Commit if changed
        run: |
          if git diff --quiet -- README.md; then
            echo "No changes to commit."
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add README.md
          git commit -m "chore: refresh writing block"
          git push
```

Notes for the implementer:
- No `actions/setup-python` step: `ubuntu-latest` ships Python 3, and the script has no dependencies to install.
- The `push` trigger combined with the job's own `git push` does **not** cause an infinite loop. GitHub does not trigger workflow runs from commits pushed with the built-in `GITHUB_TOKEN`.
- The test step runs in CI for free — no install needed — and stops a broken script from ever rewriting the published page.

- [ ] **Step 5: Verify the workflow is valid YAML**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/update-readme.yml')); print('valid')"`
Expected: `valid`. If PyYAML is unavailable in the local environment, skip this step — it is a convenience check, not a dependency of the project.

- [ ] **Step 6: Run the full test suite one last time**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, 25 tests

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/update-readme.yml README.md
git commit -m "feat: add nightly README refresh workflow"
```

---

## Publishing (manual, by Yurii)

Not an implementation task — these require account access the implementer does not have.

1. Create a **public** GitHub repo named exactly `xSAVIKx`. The name must match the username for GitHub to render it on the profile page.
2. `git remote add origin git@github.com:xSAVIKx/xSAVIKx.git && git push -u origin main`
3. Confirm https://github.com/xSAVIKx renders the README.
4. In the repo's Actions tab, trigger **Update README** via `workflow_dispatch` once to confirm the scheduled path works with real permissions.

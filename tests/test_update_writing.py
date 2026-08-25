import io
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

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

    def test_normalizes_unknown_offset_pubdate_and_sorts_with_aware_dates(self):
        feed = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>x</title>
    <item>
      <title>Naive date post</title>
      <link>https://example.test/naive/</link>
      <pubDate>Fri, 21 Aug 2026 00:00:00 -0000</pubDate>
    </item>
    <item>
      <title>Aware date post</title>
      <link>https://example.test/aware/</link>
      <pubDate>Sat, 22 Aug 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
        posts = uw.parse_feed(feed)
        self.assertEqual(
            [p.title for p in posts], ["Aware date post", "Naive date post"]
        )
        self.assertIsNotNone(posts[1].date.tzinfo)
        self.assertEqual(posts[1].date.utcoffset().total_seconds(), 0)


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

    def test_escapes_brackets_in_title(self):
        post = uw.Post(
            "Why [brackets] break (links)",
            "https://example.test/a/",
            datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        rendered = uw.render([post])
        self.assertEqual(
            rendered,
            "- [Why \\[brackets\\] break (links)](https://example.test/a/) — 21 Aug 2026",
        )

    def test_percent_encodes_parens_in_url(self):
        post = uw.Post(
            "Title",
            "https://x.dev/a_(b)/",
            datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        rendered = uw.render([post])
        self.assertEqual(
            rendered,
            "- [Title](https://x.dev/a_%28b%29/) — 21 Aug 2026",
        )

    def test_collapses_multiline_title_to_single_line(self):
        post = uw.Post(
            "Line one\nLine two",
            "https://example.test/b/",
            datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        rendered = uw.render([post])
        self.assertEqual(
            rendered,
            "- [Line one Line two](https://example.test/b/) — 21 Aug 2026",
        )
        self.assertEqual(len(rendered.splitlines()), 1)


README_TEMPLATE = "# Title\n\n## Writing\n\n<!-- posts start -->\nstale\n<!-- posts end -->\n\n## Elsewhere\n"


class TestFetch(unittest.TestCase):
    def test_retries_once_then_raises(self):
        with mock.patch.object(uw.urllib.request, "urlopen", side_effect=OSError("boom")) as opener:
            with self.assertRaises(RuntimeError):
                uw.fetch("https://example.invalid/feed.xml")
        self.assertEqual(opener.call_count, 2)

    def test_returns_body_and_passes_timeout_to_urlopen(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = b"<rss>ok</rss>"
        with mock.patch.object(
            uw.urllib.request, "urlopen", return_value=response
        ) as opener:
            result = uw.fetch("https://example.test/feed.xml", timeout=7)
        self.assertEqual(result, b"<rss>ok</rss>")
        self.assertEqual(opener.call_count, 1)
        _, kwargs = opener.call_args
        self.assertEqual(kwargs.get("timeout"), 7)
        response.read.assert_called_once_with(uw.MAX_FEED_BYTES)


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

    def test_passes_feed_url_argument_to_fetch(self):
        readme = self._readme()
        with mock.patch.object(uw, "fetch", return_value=MINIMAL_FEED) as fetch_mock:
            exit_code = uw.main(
                [
                    "--readme",
                    str(readme),
                    "--feed-url",
                    "https://example.test/other.xml",
                ]
            )
        self.assertEqual(exit_code, 0)
        fetch_mock.assert_called_once_with("https://example.test/other.xml")


if __name__ == "__main__":
    unittest.main()

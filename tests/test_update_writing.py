import sys
import unittest
import xml.etree.ElementTree as ET
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


if __name__ == "__main__":
    unittest.main()

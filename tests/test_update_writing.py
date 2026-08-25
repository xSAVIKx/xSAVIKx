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

"""Tests for the shadow concern-block parser (t1037_1).

Covers the format/parser contract in
``aidocs/framework/shadow_concern_format.md``:
- canonical parse, wrap-join round-trip, marker-collision hardening,
- strict (auto-offer) vs forgiving (explicit) trigger paths,
- multi-block "last wins" and the old-complete + new-streaming regression,
- the clipboard payload builder.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_concern_parser.py -v
"""
import os
import sys
import textwrap
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "monitor")
)
from concern_parser import (  # noqa: E402
    Concern,
    DEFAULT_PREAMBLE,
    build_clipboard_payload,
    has_concern_block,
    parse_concerns,
)

OPEN = "===AITASK-CONCERNS==="
CLOSE = "===END-CONCERNS==="


def block(*lines):
    """Wrap concern lines in a complete fenced block."""
    return "\n".join([OPEN, *lines, CLOSE])


class TestParseConcerns(unittest.TestCase):
    def test_canonical_two_items(self):
        text = block(
            "- [high | Step 7 ownership guard] The guard double-commits.",
            "- [medium | parser module] Accumulation is undefined.",
        )
        concerns = parse_concerns(text)
        self.assertEqual(
            concerns,
            [
                Concern("high", "Step 7 ownership guard", "The guard double-commits."),
                Concern("medium", "parser module", "Accumulation is undefined."),
            ],
        )

    def test_wrap_join_round_trip(self):
        """A multi-line body (agent word-boundary wrapping) rejoins to the original.

        The capture is expected to be tmux ``-J``-joined upstream (see the
        capture-join contract in the format spec), so the only newlines the
        parser sees are real, word-boundary breaks — which space-join
        reconstructs. ``break_on_hyphens=False`` faithfully models that (it
        breaks only at whitespace, never mid-word/at a hyphen).
        """
        long_body = (
            "The ownership guard re-runs aitask_pick_own.sh which double-commits "
            "when the lock was already held by this host, producing a redundant "
            "administrative commit on the data branch every single time."
        )
        marker = f"- [high | ownership] {long_body}"
        wrapped = "\n".join(textwrap.wrap(marker, width=40, break_on_hyphens=False))
        # Continuation lines carry no leading "- " (collision hardening).
        self.assertFalse(wrapped.splitlines()[1].lstrip().startswith("- ["))
        text = "\n".join([OPEN, wrapped, CLOSE])
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].priority, "high")
        self.assertEqual(concerns[0].region, "ownership")
        self.assertEqual(concerns[0].body, long_body)

    def test_marker_collision_continuation(self):
        """Body continuation lines that LOOK like markers must not split items."""
        text = block(
            "- [high | parser] The grammar must reject lines such as",
            "  [high | fake] that appear inside a wrapped body, and also",
            "  priority=high region=fake which mimics a key-value marker.",
        )
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)  # exactly one — no spurious split
        self.assertIn("[high | fake]", concerns[0].body)
        self.assertIn("priority=high region=fake", concerns[0].body)

    def test_no_block(self):
        text = "just some agent output\nwith no concern block at all\n"
        self.assertEqual(parse_concerns(text), [])
        self.assertFalse(has_concern_block(text))

    def test_unknown_priority_degrades_to_low(self):
        text = block("- [critical | x] An item with an out-of-range priority.")
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].priority, "low")  # retained, not dropped

    def test_missing_closing_fence(self):
        """parse_concerns is forgiving (EOF); has_concern_block is strict."""
        text = "\n".join(
            [OPEN, "- [high | x] A concern with no closing fence in the capture."]
        )
        self.assertEqual(len(parse_concerns(text)), 1)
        self.assertFalse(has_concern_block(text))

    def test_strict_trigger(self):
        empty = block()  # both fences, no items
        malformed = "\n".join([OPEN, "garbage line, not a marker", CLOSE])
        complete = block("- [low | x] A real concern.")
        # parse_concerns
        self.assertEqual(parse_concerns(empty), [])
        self.assertEqual(parse_concerns(malformed), [])
        self.assertEqual(len(parse_concerns(complete)), 1)
        # has_concern_block
        self.assertFalse(has_concern_block(empty))
        self.assertFalse(has_concern_block(malformed))
        self.assertTrue(has_concern_block(complete))

    def test_old_complete_plus_new_streaming(self):
        """Regression: an old block's close must not satisfy the strict check."""
        old = block("- [high | old] An older, complete review.")
        new_streaming = "\n".join([OPEN, "- [medium | new] A fresh review still"])
        text = old + "\nsome interleaving agent output\n" + new_streaming
        # Strict trigger: the newest open has no close after it -> False.
        self.assertFalse(has_concern_block(text))
        # Forgiving action still yields the newest (partial) block's items.
        newest = parse_concerns(text)
        self.assertEqual(len(newest), 1)
        self.assertEqual(newest[0].region, "new")

    def test_multi_block_last_wins(self):
        first = block("- [high | first] From the first block.")
        second = block("- [low | second] From the second block.")
        text = first + "\n\n" + second
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].region, "second")

    def test_build_clipboard_payload(self):
        c0 = Concern("high", "a", "first concern")
        c1 = Concern("medium", "b", "second concern")
        c2 = Concern("low", "c", "third concern")
        payload = build_clipboard_payload([c0, c2])  # subset, preserves order
        lines = payload.split("\n")
        self.assertEqual(lines[0], DEFAULT_PREAMBLE)
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "- [high | a] first concern")
        self.assertEqual(lines[3], "- [low | c] third concern")
        self.assertNotIn(c1.body, payload)  # unselected concern excluded

    def test_build_clipboard_payload_custom_preamble(self):
        payload = build_clipboard_payload(
            [Concern("low", "r", "b")], preamble="Custom:"
        )
        self.assertTrue(payload.startswith("Custom:\n\n- [low | r] b"))


if __name__ == "__main__":
    unittest.main()

"""Tests for the shadow concern-block parser (t1037_1).

Covers the format/parser contract in
``.claude/skills/aitask-shadow/concern-format.md``:
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
    contains_any_concern_block,
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

    def test_richly_framed_body_round_trip(self):
        """A richly-framed multi-row body (problem + why-it-bites + latitude)
        reassembles to exactly one Concern with the full body intact, and the
        strict auto-offer trigger still fires (t1037_6).

        Guards the producer-instruction intent: bodies now carry the full
        framing, soft-wrap across several rows, and must NOT split or lose the
        motivation when the parser space-joins them back.
        """
        rich_body = (
            "The guard re-runs aitask_pick_own.sh even when Step 4 already "
            "acquired the lock on this host, so every resumed task writes a "
            "second, redundant ownership commit to the data branch. It bites on "
            "the common reclaim path (crash recovery, multi-day tasks), quietly "
            "doubling the commit history. Gating the re-run on whether the lock "
            "is already held would fix it, but the exact condition is the "
            "agent's call."
        )
        marker = f"- [high | Step 7 ownership guard] {rich_body}"
        wrapped = "\n".join(textwrap.wrap(marker, width=72, break_on_hyphens=False))
        # The body wraps across several rows; continuation rows carry no "- ".
        self.assertGreater(len(wrapped.splitlines()), 2)
        self.assertFalse(wrapped.splitlines()[1].lstrip().startswith("- ["))
        text = "\n".join([OPEN, wrapped, CLOSE])
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)  # no spurious split across rows
        self.assertEqual(concerns[0].priority, "high")
        self.assertEqual(concerns[0].region, "Step 7 ownership guard")
        self.assertEqual(concerns[0].body, rich_body)  # motivation intact
        self.assertIn("It bites on", concerns[0].body)  # why-it-bites preserved
        self.assertTrue(has_concern_block(text))  # strict auto-offer still fires

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

    def test_disposition_verdict_trailer_round_trips(self):
        """A body carrying the t1158 disposition/verdict trailer round-trips
        unchanged through parse → clipboard payload.

        The tiered impl review appends ``Disposition: …`` / ``Verified: …`` as
        free text inside the body (not parser fields); the wire format is
        unchanged, so the trailer must survive verbatim end-to-end.
        """
        body = (
            "The new guard drops the falsy-zero case, so an index of 0 is "
            "treated as missing and the first entry is silently skipped. "
            "Disposition: blocking. Verified: CONFIRMED."
        )
        text = block(f"- [high | lib/picker.py:42] {body}")
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].body, body)  # trailer intact after parse
        payload = build_clipboard_payload(concerns)
        self.assertIn(f"- [high | lib/picker.py:42] {body}", payload)

    def test_informational_disposition_trailer_round_trips(self):
        """The t1200 ``informational`` disposition rides in the body too.

        t1200 added a third disposition so the review stops silently omitting
        findings it judges already-handled. Like ``blocking`` / ``follow-up`` it
        is free text inside the body, NOT a parser field — this pins that adding
        the value did not perturb the wire format.
        """
        body = (
            "The plan explicitly accepted the unlocked counter increment, on "
            "the rationale that only the reaper writes it; that holds against "
            "the diff, so I am not asking for a change — flagging it so you can "
            "judge the single-writer assumption yourself. "
            "Disposition: informational. Verified: CONFIRMED."
        )
        text = block(f"- [low | accepted risk] {body}")
        concerns = parse_concerns(text)
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].priority, "low")
        self.assertEqual(concerns[0].region, "accepted risk")
        self.assertEqual(concerns[0].body, body)  # trailer intact after parse
        payload = build_clipboard_payload(concerns)
        self.assertIn(f"- [low | accepted risk] {body}", payload)


class TestShadowDocsNotParserLive(unittest.TestCase):
    """Guard: no shadow sub-procedure doc may embed a *parser-live* example block.

    The shadow agent reads these ``.md`` files at runtime, so their content can
    land in the shadow pane (a file read, or the agent quoting the format).
    Minimonitor parses the shadow pane and forwards a concern block it finds — so
    an embedded example that is itself a complete ``===AITASK-CONCERNS===`` …
    ``- [..]`` … ``===END-CONCERNS===`` block can be mis-forwarded as if it were
    real concerns (the picker then hands the reader the doc's placeholder items
    instead of the agent's actual review — the t1119 live-repro bug). The docs
    must therefore present the format WITHOUT a contiguous open→items→close
    block: name the sentinels inline and show the ``- [priority | region]`` item
    lines separately.

    Two layers of enforcement, because the runtime parser and a live capture see
    the pane differently:

    - :meth:`test_no_doc_is_parser_live` uses ``has_concern_block`` — the runtime
      predicate, which scopes to the **last** fence only (``rfind``). It models
      what the picker parses from the *whole* pane.
    - :meth:`test_no_doc_embeds_any_contiguous_block` uses
      ``contains_any_concern_block`` — the stricter check that inspects **every**
      block, not just the last. A live shadow-pane capture is a bounded *window*,
      so a partial capture can isolate an *earlier* embedded block even when a
      later inline sentinel mention would "mask" it under last-block-wins. This
      is the layer that catches the t1123 regression (``concern-format.md`` was
      "only accidentally safe" — its contiguous block was masked by a trailing
      inline mention, so the last-fence check passed while a partial capture
      could still forward the placeholder).
    """

    SHADOW_DIR = os.path.join(
        os.path.dirname(__file__), "..", ".claude", "skills", "aitask-shadow"
    )

    def _shadow_docs(self):
        import glob

        docs = sorted(glob.glob(os.path.join(self.SHADOW_DIR, "*.md")))
        self.assertTrue(docs, "no shadow docs found — path wrong?")
        return docs

    def test_no_doc_is_parser_live(self):
        offenders = []
        for path in self._shadow_docs():
            with open(path, encoding="utf-8") as fh:
                if has_concern_block(fh.read()):
                    offenders.append(os.path.basename(path))
        self.assertEqual(
            offenders,
            [],
            "shadow doc(s) embed a parser-live concern block — minimonitor could "
            "forward the doc's example as real concerns. Present the format with "
            "inline sentinels + separate item lines instead: " + ", ".join(offenders),
        )

    def test_no_doc_embeds_any_contiguous_block(self):
        """Stronger than the last-fence check: no doc may embed a contiguous
        ``open → items → close`` block *anywhere* (a partial pane capture can
        isolate any one of them, not just the newest). Catches the t1123 hazard.
        """
        offenders = []
        for path in self._shadow_docs():
            with open(path, encoding="utf-8") as fh:
                if contains_any_concern_block(fh.read()):
                    offenders.append(os.path.basename(path))
        self.assertEqual(
            offenders,
            [],
            "shadow doc(s) embed a contiguous concern block somewhere — a partial "
            "shadow-pane capture could isolate it and the picker would forward the "
            "doc's placeholder items. Name the sentinels inline and show the item "
            "lines separately (no open→items→close): " + ", ".join(offenders),
        )

    def test_guard_catches_masked_embedded_block(self):
        """Negative control: reproduce the ``concern-format.md`` masking shape and
        prove the two guards disagree exactly where the live bug lived.

        A real embedded block followed by a *later* inline sentinel mention (the
        mention becomes the last fence) is invisible to the last-fence
        ``has_concern_block`` but visible to ``contains_any_concern_block``. If
        this ever stops holding, the strengthened guard is no longer catching
        what the old one missed.
        """
        masked = (
            "some doc prose\n"
            + block(
                "- [high | region] A real-looking example concern in a doc.",
                "- [low | other] A second example concern.",
            )
            + "\nmore prose describing the format\n"
            # Trailing inline mention: opens AND closes on one line, so it becomes
            # the last fence and masks the block above from the rfind-based check.
            "- Opening: `" + OPEN + "` — Closing: `" + CLOSE + "`.\n"
        )
        # Runtime last-fence predicate is fooled (the t1123 blind spot)…
        self.assertFalse(has_concern_block(masked))
        self.assertEqual(parse_concerns(masked), [])
        # …but the authoring guard sees the embedded block.
        self.assertTrue(contains_any_concern_block(masked))


class TestSplitMarkerJoin(unittest.TestCase):
    """Marker brackets hard-wrapped by an agent TUI's own renderer (t1167).

    Agent TUIs that render markdown themselves break long rows with **literal
    newlines** that ``tmux capture-pane -J`` cannot rejoin. A break landing
    inside ``[priority | region]`` used to drop the whole item silently.
    """

    def test_live_codex_capture_mid_region_split(self):
        """The real capture from t1158's Step 8 review — the reported failure.

        Codex CLI at ~55 columns broke a 53-char full-path region after the
        hyphen in ``impl-review-``. Before this fix: 0 concerns parsed and the
        auto-offer never fired.
        """
        text = block(
            "- [medium | .claude/skills/aitask-shadow/impl-review-",
            "angles.md:12] The angle list is not derived from the guide.",
        )
        concerns = parse_concerns(text)
        self.assertEqual(
            concerns,
            [
                Concern(
                    "medium",
                    ".claude/skills/aitask-shadow/impl-review-angles.md:12",
                    "The angle list is not derived from the guide.",
                )
            ],
        )
        # The auto-offer must now fire — this is the user-visible acceptance
        # signal for the whole task.
        self.assertTrue(has_concern_block(text))

    def test_word_boundary_split_restores_space(self):
        """A prose region broken at a word boundary gets its consumed space back."""
        text = block(
            "- [high | Step 7 ownership",
            "guard] The guard double-commits.",
        )
        self.assertEqual(
            parse_concerns(text),
            [Concern("high", "Step 7 ownership guard", "The guard double-commits.")],
        )

    def test_prose_spaced_slash_split_is_accepted_best_effort(self):
        """Documented cosmetic loss — NOT a latent bug.

        Region reconstruction is explicitly best-effort: a capture cannot tell
        "the renderer consumed a space" from "the token continues". The join
        rule treats a trailing ``/`` as an intra-token break because that is
        exact for paths (the only failure mode observed live). The cost is that
        a *prose* region broken right after a spaced slash loses that space.
        ``region`` is a display label, never a key, so this is accepted — and
        pinned here so a future reader sees it was a decision.
        """
        text = block(
            "- [low | foo /",
            "bar] Prose region with a spaced slash.",
        )
        self.assertEqual(
            parse_concerns(text),
            [Concern("low", "foo /bar", "Prose region with a spaced slash.")],
        )

    def test_at_bound_marker_parses(self):
        """A marker spanning exactly _MAX_MARKER_JOIN_ROWS + 1 rows still parses.

        Pins the bound as intentional: with the over-bound test below, changing
        the constant forces a deliberate decision.
        """
        text = block(
            "- [high | aaaaaaaaaaaaaaaaaaaa/",
            "bbbbbbbbbbbbbbbbbbbb/",
            "cccccccccccccccccccc] Body after a three-row marker.",
        )
        self.assertEqual(
            parse_concerns(text),
            [
                Concern(
                    "high",
                    "aaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbb/cccccccccccccccccccc",
                    "Body after a three-row marker.",
                )
            ],
        )

    def test_over_bound_marker_is_not_parsed(self):
        """Negative control: a 4-row marker exceeds the envelope and is dropped.

        This is the accepted, documented limit — the producer-side short-region
        rule remains the primary defense.
        """
        text = block(
            "- [high | aaaaaaaaaaaaaaaaaaaa/",
            "bbbbbbbbbbbbbbbbbbbb/",
            "cccccccccccccccccccc/",
            "dddddddddddddddddddd] Body after a four-row marker.",
        )
        self.assertEqual(parse_concerns(text), [])
        self.assertFalse(has_concern_block(text))

    def test_unclosed_bracket_never_parses(self):
        """Negative control: a garbage ``- [`` row with no closing bracket at all."""
        text = block(
            "- [high | this bracket never closes",
            "and neither does this row",
        )
        self.assertEqual(parse_concerns(text), [])
        self.assertFalse(has_concern_block(text))

    def test_failed_join_consumes_nothing(self):
        """Negative control: a failed join must not swallow a following item.

        The lookahead commits only on success, and stops early at any row that
        itself starts like a marker — so the valid concern below survives.
        """
        text = block(
            "- [high | unclosed bracket row",
            "- [low | real region] The real concern.",
        )
        self.assertEqual(
            parse_concerns(text),
            [Concern("low", "real region", "The real concern.")],
        )

    def test_body_wrap_still_round_trips(self):
        """Regression guard on the rewritten loop: body continuation is unchanged."""
        text = block(
            "- [medium | parser module] Multi-block accumulation is",
            "undefined when several blocks are present in one capture.",
        )
        self.assertEqual(
            parse_concerns(text),
            [
                Concern(
                    "medium",
                    "parser module",
                    "Multi-block accumulation is undefined when several blocks "
                    "are present in one capture.",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()

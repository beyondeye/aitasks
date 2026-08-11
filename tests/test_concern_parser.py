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
    BlockMeta,
    Concern,
    DEFAULT_PREAMBLE,
    block_head_truncated,
    block_region,
    build_clipboard_payload,
    concern_block_signature,
    contains_any_concern_block,
    has_concern_block,
    has_invalid_round_header,
    is_metadata_only_block,
    needs_addressing,
    parse_block_meta,
    parse_concerns,
    unrecovered_markers,
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


class TestBlockHeadTruncated(unittest.TestCase):
    """The capture window starting *inside* a block (t1187).

    Both runtime entry points key off the LAST opening fence, so a window that
    clipped the opening fence reads exactly like "the shadow raised nothing" —
    a silent false negative. ``block_head_truncated`` names that shape so the UI
    can report a too-shallow capture instead of staying quiet.

    Five of the seven cases must stay ``False``: the predicate's whole value is
    that it does NOT cry wolf on ordinary captures.
    """

    ITEMS = (
        "- [high | Step 7 guard] The guard double-commits the lock.\n"
        "- [medium | parser] Multi-block accumulation is undefined.\n"
    )

    def test_orphan_close_is_truncation(self):
        text = self.ITEMS + CLOSE + "\n"
        self.assertTrue(block_head_truncated(text))

    def test_detection_is_not_recovery(self):
        """Detecting the clip must NOT start parsing the untrusted head region.

        The text above an orphan closing fence can be a shadow doc read into the
        pane, carrying literal example markers (the t1123 hazard) — so the two
        runtime entry points stay silent and the caller re-captures deeper.
        """
        text = self.ITEMS + CLOSE + "\n"
        self.assertEqual(parse_concerns(text), [])
        self.assertFalse(has_concern_block(text))

    def test_complete_block_is_not_truncation(self):
        self.assertFalse(block_head_truncated(block(self.ITEMS.strip())))

    def test_no_fences_at_all_is_not_truncation(self):
        """Negative control: a genuinely concern-free pane is not a clip."""
        self.assertFalse(block_head_truncated("just some agent output\n"))

    def test_streaming_block_is_not_truncation(self):
        """An opening fence with no close yet is mid-stream, not clipped."""
        self.assertFalse(block_head_truncated(OPEN + "\n" + self.ITEMS))

    def test_complete_then_streaming_is_not_truncation(self):
        text = block(self.ITEMS.strip()) + "\n" + OPEN + "\n- [low | x] newer\n"
        self.assertFalse(block_head_truncated(text))

    def test_clipped_older_plus_streaming_newer_is_not_truncation(self):
        """The false positive an ordering-based variant produces.

        "First closing fence has no opening fence before it" is true here — the
        older block WAS clipped — but the newest review is simply still
        streaming and will complete normally. Warning the user to deepen the
        capture window would be noise, so this must read False.
        """
        text = (
            self.ITEMS + CLOSE + "\nprose\n"
            + OPEN + "\n- [low | x] a newer, still-streaming review\n"
        )
        self.assertFalse(block_head_truncated(text))

    def test_clipped_older_plus_complete_newer_is_not_truncation(self):
        """Same family: the newest block is intact, so the runtime parses fine."""
        text = (
            self.ITEMS + CLOSE + "\n"
            + block("- [low | x] a newer, complete review")
        )
        self.assertFalse(block_head_truncated(text))
        self.assertTrue(has_concern_block(text))


class TestDispositionDerivation(unittest.TestCase):
    """`disposition` / `verdict` are derived from the body's terminal trailer (t1274).

    They are NOT marker fields: the shadow's implementation review already ends
    each body with `Disposition: … Verified: …` prose, and widening the
    `[priority | region]` bracket is the documented t1167 drop hazard. Deriving
    also means every block emitted before this existed keeps working.
    """

    def _one(self, body):
        concerns = parse_concerns(block(f"- [medium | region] {body}"))
        self.assertEqual(len(concerns), 1)
        return concerns[0]

    def test_each_disposition_and_verdict_is_derived(self):
        for disposition in ("blocking", "follow-up", "informational"):
            for verdict in ("CONFIRMED", "PLAUSIBLE", "REFUTED"):
                with self.subTest(disposition=disposition, verdict=verdict):
                    c = self._one(
                        f"Real text. Disposition: {disposition}. "
                        f"Verified: {verdict}."
                    )
                    self.assertEqual(c.disposition, disposition)
                    self.assertEqual(c.verdict, verdict)
                    self.assertEqual(c.display_body(), "Real text.")

    def test_case_and_spelling_variants_normalize(self):
        for written, expected in (
            ("follow-up", "follow-up"),
            ("follow up", "follow-up"),
            ("followup", "follow-up"),
            ("INFORMATIONAL", "informational"),
            ("Blocking", "blocking"),
        ):
            with self.subTest(written=written):
                c = self._one(f"Text. Disposition: {written}.")
                self.assertEqual(c.disposition, expected)

    def test_trailer_sentence_order_is_free(self):
        c = self._one("Text. Verified: CONFIRMED. Disposition: follow-up.")
        self.assertEqual((c.disposition, c.verdict), ("follow-up", "CONFIRMED"))
        self.assertEqual(c.display_body(), "Text.")

    def test_absent_trailer_leaves_both_empty_and_body_untouched(self):
        c = self._one("A plain concern with no trailer at all.")
        self.assertEqual((c.disposition, c.verdict), ("", ""))
        self.assertEqual(c.display_body(), c.body)

    def test_unknown_disposition_value_is_not_derived(self):
        c = self._one("Text. Disposition: urgent.")
        self.assertEqual(c.disposition, "")
        self.assertEqual(c.display_body(), c.body)

    def test_prose_mention_is_neither_classified_nor_stripped(self):
        """The anchor is what stops a body *discussing* a disposition from lying.

        Without a terminal anchor this body would be classified `informational`
        and would lose real prose from the row.
        """
        c = self._one(
            "The rubric says Disposition: informational. is for settled "
            "findings, but this one is a genuine defect."
        )
        self.assertEqual(c.disposition, "")
        self.assertEqual(c.display_body(), c.body)

    def test_text_after_the_trailer_means_there_is_no_trailer(self):
        c = self._one("Text. Disposition: blocking. And one more thought.")
        self.assertEqual(c.disposition, "")
        self.assertEqual(c.display_body(), c.body)

    def test_body_stays_canonical_and_forwarding_is_byte_identical(self):
        """The forwarded payload must still carry the trailer verbatim.

        `build_clipboard_payload` re-renders `body`, so stripping the trailer at
        parse time would silently delete the disposition from what the followed
        agent receives.
        """
        line = (
            "- [medium | accepted risk] Automated verification does not cover "
            "the merge. Disposition: informational. Verified: CONFIRMED."
        )
        concerns = parse_concerns(block(line))
        self.assertIn("Disposition: informational.", concerns[0].body)
        payload = build_clipboard_payload(concerns)
        self.assertEqual(payload.splitlines()[2], line)

    def test_needs_addressing_is_false_only_for_informational(self):
        self.assertFalse(needs_addressing(Concern("high", "r", "b", "informational")))
        for disposition in ("blocking", "follow-up", ""):
            with self.subTest(disposition=disposition):
                self.assertTrue(
                    needs_addressing(Concern("high", "r", "b", disposition))
                )

    def test_new_fields_default_so_positional_construction_still_works(self):
        c = Concern("high", "region", "body")
        self.assertEqual((c.disposition, c.verdict), ("", ""))


class TestRegionLessMarker(unittest.TestCase):
    """`- [medium] body` parses with an empty region instead of vanishing (t1274).

    It matches neither `_ITEM` (no `|`) nor the split-marker path (the row does
    contain `]`), so it used to fall through to continuation handling: appended
    to the previous concern's body, or dropped when it was the first item.
    """

    def test_parses_with_an_empty_region(self):
        (c,) = parse_concerns(block("- [medium] a region-less concern"))
        self.assertEqual((c.priority, c.region, c.body),
                         ("medium", "", "a region-less concern"))

    def test_is_not_dropped_as_the_first_item(self):
        concerns = parse_concerns(
            block("- [medium] first item", "- [high | ok] second item")
        )
        self.assertEqual([c.body for c in concerns], ["first item", "second item"])

    def test_is_not_merged_into_the_preceding_concern(self):
        concerns = parse_concerns(
            block("- [high | ok] first item", "- [medium] second item")
        )
        self.assertEqual(len(concerns), 2)
        self.assertEqual(concerns[0].body, "first item")
        self.assertEqual(concerns[1].body, "second item")

    def test_priority_is_the_closed_vocabulary_not_a_word_class(self):
        """Negative control: the collision-hardening guarantee is intact.

        With `\\w+` here, an ordinary wrapped body line carrying bracketed text
        would start a spurious concern. The closed alternation is what prevents
        that, so this must stay a continuation.
        """
        concerns = parse_concerns(
            block("- [high | ok] first item", "- [see below] not a marker")
        )
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].body, "first item - [see below] not a marker")


class TestUnrecoveredMarkers(unittest.TestCase):
    """What the parser could not turn into a concern is reported, not swallowed.

    The remaining losses (an over-bound split, a malformed bracket) stay
    deliberately unrecoverable — widening `_MAX_MARKER_JOIN_ROWS` is the accepted
    t1167 limit. What changes is that they stop being invisible: the picker shows
    the count so the user knows the list is short (t1274).
    """

    def test_over_bound_split_marker_is_reported(self):
        text = block(
            "- [low | aaaa", "bbbb", "cccc", "dddd] over-bound body",
            "- [high | ok] a good one",
        )
        self.assertEqual(len(parse_concerns(text)), 1)
        self.assertEqual(unrecovered_markers(text), ["- [low | aaaa"])

    def test_malformed_and_unclosed_brackets_are_reported(self):
        for bad in ("- [ | region] no priority", "- [medium | never closes"):
            with self.subTest(bad=bad):
                text = block("- [high | ok] a good one", bad)
                self.assertEqual(unrecovered_markers(text), [bad])

    def test_a_well_formed_block_reports_nothing(self):
        text = block(
            "- [high | ok] a good one",
            "  a wrapped continuation line",
            "- [medium] a region-less one",
        )
        self.assertEqual(unrecovered_markers(text), [])

    def test_bracketed_prose_inside_a_body_is_not_reported(self):
        text = block("- [high | ok] a body mentioning [medium | x] inline")
        self.assertEqual(unrecovered_markers(text), [])

    def test_no_block_reports_nothing(self):
        self.assertEqual(unrecovered_markers("just some pane output"), [])


class TestBlockRegion(unittest.TestCase):
    """The raw region a human inspects is the SAME one the parser read (t1293).

    `block_region` exists so the picker can show *what* was lost, not just how
    much. Its value is only trustworthy if it is scoped identically to
    `parse_concerns` / `unrecovered_markers` — otherwise the user would be
    reading a different block than the one that produced the warning.
    """

    def test_returns_the_region_verbatim_including_unrecovered_lines(self):
        text = block(
            "- [low | aaaa", "bbbb", "cccc", "dddd] over-bound body",
            "- [high | ok] a good one",
        )
        region = block_region(text)
        # The lost marker AND its continuation rows — the only thing that shows
        # an over-bound split for what it is, rather than a producer typo.
        self.assertIn("- [low | aaaa", region)
        self.assertIn("dddd] over-bound body", region)
        self.assertIn("- [high | ok] a good one", region)
        for line in unrecovered_markers(text):
            self.assertIn(line, region)

    def test_forgiving_scope_matches_parse_concerns(self):
        """No closing fence — the same EOF tolerance the hotkey path relies on."""
        text = OPEN + "\n- [high | ok] still streaming"
        self.assertEqual(len(parse_concerns(text)), 1)
        self.assertIn("still streaming", block_region(text))

    def test_last_block_wins(self):
        text = "\n".join([
            block("- [high | old] superseded"),
            block("- [high | new] the newest one"),
        ])
        region = block_region(text)
        self.assertIn("the newest one", region)
        self.assertNotIn("superseded", region)

    def test_no_fence_returns_none(self):
        self.assertIsNone(block_region("just some pane output"))


def _states_short_region_rule(text: str) -> bool:
    """True when a producer doc states the short-region rule.

    Whitespace is collapsed first: these are hand-wrapped markdown files, so
    either phrase can straddle a line break (both did, in two of the four
    producers) and a raw substring test would report a false violation.

    Module-level so the drift guard's negative control can exercise it on
    synthetic text without mutating repo files.
    """
    flat = " ".join(text.split())
    return "≤ ~30 chars" in flat and "never a full repo path" in flat


HEADER = "Round: 2 @ 2026-08-11T14:03:27Z"


class TestParseBlockMeta(unittest.TestCase):
    """Round metadata from the block header (t1159_1).

    The header sits in the one slot `_scan_items` already drops (a non-marker
    line before the first item), so every concern-yielding entry point is
    unaffected; `parse_block_meta` is the only reader. Fail-open: `reviewed_at`
    is verbatim and unvalidated.
    """

    def test_header_parses(self):
        text = block(HEADER, "- [high | x] body.")
        self.assertEqual(
            parse_block_meta(text), BlockMeta(2, "2026-08-11T14:03:27Z")
        )

    def test_absent_header_is_none(self):
        self.assertIsNone(parse_block_meta(block("- [high | x] body.")))

    def test_no_block_is_none(self):
        self.assertIsNone(parse_block_meta("just some pane output"))

    def test_no_timestamp_is_empty_not_none(self):
        self.assertEqual(
            parse_block_meta(block("Round: 3", "- [low | y] z.")),
            BlockMeta(3, ""),
        )

    def test_dangling_at_is_empty_not_none(self):
        self.assertEqual(
            parse_block_meta(block("Round: 3 @", "- [low | y] z.")),
            BlockMeta(3, ""),
        )

    def test_leading_blank_lines_are_skipped(self):
        text = block("", "  ", HEADER, "- [high | x] body.")
        self.assertEqual(
            parse_block_meta(text), BlockMeta(2, "2026-08-11T14:03:27Z")
        )

    def test_header_after_an_item_is_none_and_body_joined(self):
        """Pin the corruption mode, not just the None.

        A header emitted after an item is wrap-joined into that item's body by
        the continuation grammar — the round is lost AND the body is polluted.
        Believing a later `Round:` line would report a round the block's
        header slot does not carry, so `None` is correct; the join is the
        producer-facing reason the placement rule exists.
        """
        text = block("- [high | x] body.", HEADER)
        self.assertIsNone(parse_block_meta(text))
        (concern,) = parse_concerns(text)
        self.assertEqual(concern.body, f"body. {HEADER}")

    def test_last_block_wins(self):
        text = (
            block("Round: 1 @ a", "- [high | x] old.")
            + "\nchatter\n"
            + block("Round: 2 @ b", "- [high | x] new.")
        )
        self.assertEqual(parse_block_meta(text), BlockMeta(2, "b"))

    def test_unclosed_newest_block_still_yields_meta(self):
        """Same forgiving region as `parse_concerns` (require_close=False)."""
        text = "\n".join([OPEN, HEADER, "- [high | x] streaming"])
        self.assertEqual(
            parse_block_meta(text), BlockMeta(2, "2026-08-11T14:03:27Z")
        )

    def test_metadata_only_block_is_a_clean_round_record(self):
        """Meta readable; nothing else sees a concern; nothing is 'lost'."""
        text = block(HEADER)
        self.assertEqual(
            parse_block_meta(text), BlockMeta(2, "2026-08-11T14:03:27Z")
        )
        self.assertFalse(has_concern_block(text))
        self.assertEqual(parse_concerns(text), [])
        self.assertEqual(unrecovered_markers(text), [])

    def test_entry_points_are_byte_identical_with_and_without_header(self):
        items = (
            "- [high | x] a body.",
            "- [low | aaaa",  # an unrecovered marker, to cover that path too
        )
        with_header = block(HEADER, *items)
        without = block(*items)
        self.assertEqual(parse_concerns(with_header), parse_concerns(without))
        self.assertEqual(
            has_concern_block(with_header), has_concern_block(without)
        )
        self.assertEqual(
            unrecovered_markers(with_header), unrecovered_markers(without)
        )

    def test_signature_changes_on_a_round_bump_alone(self):
        """The header deliberately perturbs the signature: a round bump must
        re-hash the monitor's freshness badge even with identical items."""
        item = "- [high | x] the same body."
        round_1 = block("Round: 1 @ 2026-08-11T14:03:27Z", item)
        round_2 = block("Round: 2 @ 2026-08-11T14:03:27Z", item)
        self.assertIsNotNone(concern_block_signature(round_1))
        self.assertNotEqual(
            concern_block_signature(round_1), concern_block_signature(round_2)
        )

    def test_oversized_round_reads_as_malformed_not_a_crash(self):
        """`int()` raises past sys.get_int_max_str_digits() (4300 on 3.11+),
        and the round is agent-emitted text — the grammar bounds the digits so
        an absurd run fails the match (meta None) instead of raising through
        the monitor tick / picker callers (the never-raise contract)."""
        oversized = block("Round: " + "1" * 5000 + " @ ts", "- [high | x] b.")
        self.assertIsNone(parse_block_meta(oversized))
        # Boundary: 9 digits parses, 10 reads as malformed.
        self.assertEqual(
            parse_block_meta(block("Round: 999999999", "- [l | y] z.")),
            BlockMeta(999999999, ""),
        )
        self.assertIsNone(
            parse_block_meta(block("Round: 1000000000", "- [l | y] z."))
        )

    def test_round_zero_and_zero_padding_read_as_malformed(self):
        """Rounds are 1-based: `Round: 0` must neither parse nor certify a
        clean round, and a zero-padded round is not a compliant emission."""
        self.assertIsNone(parse_block_meta(block("Round: 0", "- [l | y] z.")))
        self.assertIsNone(parse_block_meta(block("Round: 01", "- [l | y] z.")))
        self.assertFalse(is_metadata_only_block(block("Round: 0 @ ts")))
        # Positive control on the same shapes: round 1 parses and certifies.
        self.assertEqual(
            parse_block_meta(block("Round: 1", "- [l | y] z.")),
            BlockMeta(1, ""),
        )
        self.assertTrue(is_metadata_only_block(block("Round: 1 @ ts")))


class TestHasInvalidRoundHeader(unittest.TestCase):
    """A Round:-shaped header that fails the grammar is investigable, not
    silence (t1159_1 review round 4).

    `parse_block_meta` reads it as absent (fail-open), but consumers must not
    then treat the block as headerless — the producer tried to emit metadata
    and got it wrong.
    """

    def test_grammar_violations_are_flagged(self):
        for bad in ("Round: 0", "Round: 01", "Round: " + "1" * 5000,
                    "Round: -3", "Round: x"):
            with self.subTest(bad=bad):
                text = block(bad + " @ ts")
                self.assertIsNone(parse_block_meta(text))
                self.assertTrue(has_invalid_round_header(text))

    def test_valid_header_is_not_flagged(self):
        self.assertFalse(has_invalid_round_header(block(HEADER)))

    def test_headerless_shapes_are_not_flagged(self):
        self.assertFalse(has_invalid_round_header("no block here"))
        self.assertFalse(
            has_invalid_round_header(block("- [high | x] body."))
        )
        self.assertFalse(has_invalid_round_header(block("plain prose line")))

    def test_streaming_invalid_header_is_flagged(self):
        """Same forgiving region as the other readers."""
        self.assertTrue(
            has_invalid_round_header("\n".join([OPEN, "Round: 0 @ ts"]))
        )

    def test_round_line_after_an_item_is_body_not_header(self):
        self.assertFalse(
            has_invalid_round_header(block("- [high | x] b.", "Round: 0"))
        )


class TestIsMetadataOnlyBlock(unittest.TestCase):
    """Certifying a clean round is stricter than reading its meta (t1159_1).

    `parse_block_meta` is forgiving (streaming-tolerant, prose-blind) because
    display and dedup must work on imperfect captures. Consumers that
    AUTO-CLEAR state (badge, "Clean review" message) need the strict check: a
    still-streaming header-only block may be about to emit items, and a header
    followed by silently-dropped prose is malformed output to investigate.
    """

    def test_certifies_a_complete_header_only_block(self):
        self.assertTrue(is_metadata_only_block(block(HEADER)))

    def test_blank_lines_around_the_header_still_certify(self):
        self.assertTrue(is_metadata_only_block(block("", HEADER, "  ")))

    def test_unclosed_header_only_stream_does_not_certify(self):
        """The forgiving reader sees meta here — the strict one must not
        certify (the block may be about to emit items)."""
        stream = "\n".join([OPEN, HEADER])
        self.assertIsNotNone(parse_block_meta(stream))
        self.assertFalse(is_metadata_only_block(stream))

    def test_header_plus_stray_prose_does_not_certify(self):
        """The scanner drops non-marker prose before the first item, so the
        forgiving path sees nothing lost — but dropped output is not clean."""
        prose = block(HEADER, "stray prose the scanner drops")
        self.assertIsNotNone(parse_block_meta(prose))
        self.assertEqual(parse_concerns(prose), [])
        self.assertEqual(unrecovered_markers(prose), [])
        self.assertFalse(is_metadata_only_block(prose))

    def test_header_plus_items_does_not_certify(self):
        self.assertFalse(
            is_metadata_only_block(block(HEADER, "- [high | x] body."))
        )

    def test_no_block_and_headerless_block_do_not_certify(self):
        self.assertFalse(is_metadata_only_block("no block here"))
        self.assertFalse(is_metadata_only_block(block("- [high | x] body.")))

    def test_malformed_header_does_not_certify(self):
        self.assertFalse(
            is_metadata_only_block(block("Round: " + "1" * 5000 + " @ ts"))
        )

    def test_last_block_wins(self):
        text = block(HEADER, "- [high | x] body.") + "\n" + block(HEADER)
        self.assertTrue(is_metadata_only_block(text))
        reversed_order = block(HEADER) + "\n" + block(HEADER, "- [h | x] b.")
        self.assertFalse(is_metadata_only_block(reversed_order))


class TestProducerShortRegionRule(unittest.TestCase):
    """Every concern-block producer must state the short-region rule (t1187).

    ``concern-format.md`` calls the ≤ ~30-char region rule the **primary
    defense** against the split-marker hazard — keeping the region short means
    the ``[priority | region]`` bracket never wraps at all, so nothing relies on
    the parser's bounded rejoin (t1167). The rule used to live in
    ``impl-challenge.md`` only, leaving all three *plan-review* producers free to
    emit a long full-path region — exactly the shape that broke live.

    The rule is inlined in each producer rather than linked: these are prompt
    files read at runtime, and an extra file read is a rule the agent may skip.
    This guard is what makes that duplication safe.
    """

    SHADOW_DIR = os.path.join(
        os.path.dirname(__file__), "..", ".claude", "skills", "aitask-shadow"
    )
    # Any doc instructing an agent to emit the block carries this phrase.
    PRODUCER_MARKER = "load-bearing for minimonitor's parser"
    KNOWN_PRODUCERS = [
        "impl-challenge.md",
        "plan-assumptions.md",
        "plan-challenge.md",
        "plan-diagnose-errors.md",
    ]

    def _producers(self):
        import glob

        found = {}
        for path in sorted(glob.glob(os.path.join(self.SHADOW_DIR, "*.md"))):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if self.PRODUCER_MARKER in text:
                found[os.path.basename(path)] = text
        return found

    def test_producer_set_is_the_known_set(self):
        """Guards the enumeration itself, so a new producer cannot slip past."""
        self.assertEqual(sorted(self._producers()), self.KNOWN_PRODUCERS)

    def test_every_producer_states_the_short_region_rule(self):
        offenders = [
            name
            for name, text in self._producers().items()
            if not _states_short_region_rule(text)
        ]
        self.assertEqual(
            offenders,
            [],
            "producer doc(s) do not state the short-region rule, so the agent "
            "may emit a full-path region whose bracket hard-wraps and becomes "
            "unparseable to minimonitor: " + ", ".join(offenders),
        )

    def test_guard_flags_a_producer_missing_the_rule(self):
        """Negative control: prove the guard can fail.

        Exercises the predicate on synthetic text rather than editing a repo
        file, so nothing has to be restored afterwards.
        """
        without = (
            "Rules — all " + self.PRODUCER_MARKER + "; match them exactly:\n"
            "- `region` names the plan section / axis the concern targets.\n"
        )
        self.assertFalse(_states_short_region_rule(without))
        with_rule = without + (
            "  MUST stay short (≤ ~30 chars), never a full repo path.\n"
        )
        self.assertTrue(_states_short_region_rule(with_rule))


def _states_region_required_rule(text: str) -> bool:
    """True when a producer doc states that `region` is mandatory.

    Whitespace is collapsed first for the same reason as
    :func:`_states_short_region_rule` — these are hand-wrapped markdown files and
    the phrase straddles a line break in several producers.
    """
    flat = " ".join(text.split())
    return "mandatory and never empty" in flat


class TestProducerRegionRequiredRule(unittest.TestCase):
    """Every producer must state that `region` is mandatory (t1274).

    An empty region leaves the picker row with no title. The parser now tolerates
    the shape rather than losing the item, but tolerance is not permission — this
    is the prevention half, and it mirrors
    :class:`TestProducerShortRegionRule` exactly so both rules fail the build the
    same way.
    """

    SHADOW_DIR = TestProducerShortRegionRule.SHADOW_DIR
    PRODUCER_MARKER = TestProducerShortRegionRule.PRODUCER_MARKER
    KNOWN_PRODUCERS = TestProducerShortRegionRule.KNOWN_PRODUCERS

    _producers = TestProducerShortRegionRule._producers

    def test_producer_set_is_the_known_set(self):
        self.assertEqual(sorted(self._producers()), self.KNOWN_PRODUCERS)

    def test_every_producer_states_the_region_required_rule(self):
        offenders = [
            name
            for name, text in self._producers().items()
            if not _states_region_required_rule(text)
        ]
        self.assertEqual(
            offenders,
            [],
            "producer doc(s) do not state that `region` is mandatory, so the "
            "agent may emit an empty region and the picker row loses its only "
            "title: " + ", ".join(offenders),
        )

    def test_guard_flags_a_producer_missing_the_rule(self):
        """Negative control: prove the guard can fail."""
        without = (
            "Rules — all " + self.PRODUCER_MARKER + "; match them exactly:\n"
            "- `region` names the plan section / axis the concern targets.\n"
        )
        self.assertFalse(_states_region_required_rule(without))
        with_rule = without + "  It is mandatory and never empty.\n"
        self.assertTrue(_states_region_required_rule(with_rule))


#: The bolded pre-emit directive's lead phrase, verbatim. Load-bearing: it is
#: what lets the predicate below tell the two placements apart.
_SUPPRESSION_DIRECTIVE = "**Consult the rejection store before emitting.**"


def _states_rejection_suppression_rule(text: str) -> bool:
    """True when a producer states the suppression rule in BOTH placements.

    Whitespace is collapsed first for the same reason as
    :func:`_states_short_region_rule` — these are hand-wrapped markdown files.
    (A hyphen-wrapped ``previously-rejected`` still fails, correctly: collapsing
    turns it into ``previously- rejected``.)

    Counts rather than membership-tests. The rule lives twice in each producer:
    once in the bolded pre-emit directive at the head of the emit step, once in
    the parser-rules list. A guard that could not tell them apart would stay
    green after the *directive* — the high-attention copy, and the countermeasure
    for an agent skipping the rule — was deleted, leaving only the bullet.
    """
    flat = " ".join(text.split())
    return (_SUPPRESSION_DIRECTIVE in flat
            and flat.count("previously-rejected") >= 2
            and flat.count("aitask_shadow_rejected.sh list") >= 2)


class TestProducerRejectionSuppressionRule(unittest.TestCase):
    """Every producer must state the rejection-suppression rule (t1427_3).

    The user can reject a concern in the picker; t1427_1/t1427_2 persist that to
    ``.aitask-shadow/<task_id>/rejected.md``. Nothing *reads* the store except
    the producers themselves — matching has to be semantic (bodies are re-worded
    between rounds and ``Concern`` has no cross-round identity), so it cannot
    move into ``concern_parser.py``. A producer that drops the rule silently
    re-raises concerns the user already dismissed, which is the exact friction
    t1427 exists to remove.

    Mirrors :class:`TestProducerRegionRequiredRule`, plus one extra negative
    control — see :meth:`test_guard_flags_a_producer_missing_the_rule` and
    :meth:`test_production_assertion_fails_on_a_real_offender`.
    """

    SHADOW_DIR = TestProducerShortRegionRule.SHADOW_DIR
    PRODUCER_MARKER = TestProducerShortRegionRule.PRODUCER_MARKER
    KNOWN_PRODUCERS = TestProducerShortRegionRule.KNOWN_PRODUCERS

    _producers = TestProducerShortRegionRule._producers

    def test_producer_set_is_the_known_set(self):
        self.assertEqual(sorted(self._producers()), self.KNOWN_PRODUCERS)

    def test_every_producer_states_the_rejection_suppression_rule(self):
        offenders = [
            name
            for name, text in self._producers().items()
            if not _states_rejection_suppression_rule(text)
        ]
        self.assertEqual(
            offenders,
            [],
            "producer doc(s) do not state the rejection-suppression rule in "
            "both placements (bolded pre-emit directive AND rules-list entry), "
            "so the agent may re-raise concerns the user already rejected: "
            + ", ".join(offenders),
        )

    def test_guard_flags_a_producer_missing_the_rule(self):
        """Negative control: prove the guard can fail, per placement.

        Exercises the predicate on synthetic text rather than editing a repo
        file — this worktree is shared with concurrent sessions, so a
        mutate-and-restore control could silently overwrite their work.

        The two one-copy cases are the point: they prove the guard is
        placement-aware rather than a plain "both substrings appear somewhere"
        membership test.
        """
        rules_entry = (
            "- **Suppress previously-rejected concerns.** Before emitting, run\n"
            "  `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and\n"
            "  drop anything matching a previously-rejected entry.\n"
        )
        directive = (
            _SUPPRESSION_DIRECTIVE + " Run\n"
            "`./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and drop\n"
            "every previously-rejected concern.\n"
        )
        base = "Rules — all " + self.PRODUCER_MARKER + "; match them exactly:\n"

        # Neither copy.
        self.assertFalse(_states_rejection_suppression_rule(base))
        # Rules-list entry only — the directive was deleted.
        self.assertFalse(_states_rejection_suppression_rule(base + rules_entry))
        # Directive only — the rules-list entry was deleted.
        self.assertFalse(_states_rejection_suppression_rule(base + directive))
        # Both placements present.
        self.assertTrue(
            _states_rejection_suppression_rule(base + directive + rules_entry)
        )

    def test_production_assertion_fails_on_a_real_offender(self):
        """Negative control for the production assertion itself.

        The synthetic control above proves only that the *predicate* can return
        ``False``; it says nothing about how the production test is wired. So
        run **the production method itself** — not a re-implementation of it —
        against a fixture directory holding one compliant and one offending
        producer, and require it to fail naming exactly the offender.

        Calling the method is the whole point. An earlier version of this
        control recomputed the offender list here with a direct call to
        :func:`_states_rejection_suppression_rule`, and was verified **not** to
        work: pasting the wrong predicate into
        :meth:`test_every_producer_states_the_rejection_suppression_rule` (e.g.
        ``_states_region_required_rule``, which all four real producers satisfy)
        left that method vacuously green *and* left the re-implementation green,
        because the mutation never reached it. Only invoking the real method
        couples the two.

        Patching ``SHADOW_DIR`` exercises the real ``_producers`` glob-and-filter
        rather than a replica, and touches no shared file — this worktree is
        shared with concurrent sessions, so a mutate-and-restore control could
        silently overwrite their work.
        """
        import tempfile
        from unittest import mock

        marker_line = "Rules — all " + self.PRODUCER_MARKER + "; match them exactly:\n"
        rules_entry = (
            "- **Suppress previously-rejected concerns.** Run\n"
            "  `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and drop\n"
            "  any previously-rejected entry.\n"
        )
        directive = (
            _SUPPRESSION_DIRECTIVE + " Run\n"
            "`./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and drop\n"
            "every previously-rejected concern.\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "good.md"), "w", encoding="utf-8") as fh:
                fh.write(marker_line + directive + rules_entry)
            # Compliant except the directive was removed.
            with open(os.path.join(tmp, "bad.md"), "w", encoding="utf-8") as fh:
                fh.write(marker_line + rules_entry)
            # Not a producer at all (no marker) — must be ignored, not flagged.
            with open(os.path.join(tmp, "notaproducer.md"), "w", encoding="utf-8") as fh:
                fh.write("Prose with no producer marker and no rule.\n")

            with mock.patch.object(TestProducerRejectionSuppressionRule,
                                   "SHADOW_DIR", tmp):
                # The marker filter still picks exactly the two producers.
                self.assertEqual(sorted(self._producers()), ["bad.md", "good.md"])
                # The real production assertion must fail here, and only here.
                with self.assertRaises(AssertionError) as caught:
                    self.test_every_producer_states_the_rejection_suppression_rule()

        message = str(caught.exception)
        self.assertIn("bad.md", message,
                      "the production assertion failed without naming the "
                      "offending producer")
        self.assertNotIn("good.md", message,
                         "the production assertion flagged the COMPLIANT "
                         "fixture too — its predicate is not the "
                         "suppression-rule one")


_ROUND_HEADER_DIRECTIVE = (
    "**Emit a round header as the first line inside the block.**"
)


def _states_round_header_rule(text: str) -> bool:
    """True when a producer states the round-header rule in BOTH placements.

    Same shape as :func:`_states_rejection_suppression_rule` — whitespace is
    collapsed, and the counts tell the two placements apart (directive + rules
    bullet). The counted tokens use the **placeholder** grammar
    (``Round: <N> @ <timestamp>``), so the concrete example header
    (``Round: 1 @ 2026-08-11T14:03:27Z``) cannot inflate a count and mask a
    deleted rule site. ``zero-concern`` and the ``date -u`` command must also
    appear at both sites (a hyphen-wrapped ``zero-concern`` fails, correctly).
    """
    flat = " ".join(text.split())
    return (_ROUND_HEADER_DIRECTIVE in flat
            and flat.count("Round: <N> @ <timestamp>") >= 2
            and flat.count("zero-concern") >= 2
            and flat.count("date -u +%Y-%m-%dT%H:%M:%SZ") >= 2)


def _retains_omit_block_rule(text: str) -> bool:
    """True when a producer still carries the pre-round omit-when-clean rule.

    The negative half of the t1159_1 replacement: the metadata-only clean-round
    block REPLACED "omit the block entirely" — a producer stating both gives
    the agent contradictory instructions while the positive guard above stays
    green, and an agent following the old rule emits no clean-round record.
    """
    flat = " ".join(text.split())
    return ("omit the block entirely" in flat
            or "omit it entirely" in flat
            or "emit no concern block" in flat)


class TestProducerRoundHeaderRule(unittest.TestCase):
    """Every producer must state the round-header rule (t1159_1).

    Round metadata only exists if the producers emit it — nothing downstream
    can synthesize a round. The rule lives twice in each producer (bolded emit
    directive + rules-list bullet), mirroring the rejection-suppression rule
    and guarded the same way, plus the negative half: the old
    "omit the block when clean" wording must be GONE, because the metadata-only
    clean-round block replaced it and both instructions cannot coexist.
    """

    SHADOW_DIR = TestProducerShortRegionRule.SHADOW_DIR
    PRODUCER_MARKER = TestProducerShortRegionRule.PRODUCER_MARKER
    KNOWN_PRODUCERS = TestProducerShortRegionRule.KNOWN_PRODUCERS

    _producers = TestProducerShortRegionRule._producers

    def test_producer_set_is_the_known_set(self):
        self.assertEqual(sorted(self._producers()), self.KNOWN_PRODUCERS)

    def test_every_producer_states_the_round_header_rule(self):
        offenders = [
            name
            for name, text in self._producers().items()
            if not _states_round_header_rule(text)
        ]
        self.assertEqual(
            offenders,
            [],
            "producer doc(s) do not state the round-header rule in both "
            "placements (bolded emit directive AND rules-list entry), so the "
            "agent may emit blocks without round metadata: "
            + ", ".join(offenders),
        )

    def test_no_producer_retains_the_omit_block_rule(self):
        offenders = [
            name
            for name, text in self._producers().items()
            if _retains_omit_block_rule(text)
        ]
        self.assertEqual(
            offenders,
            [],
            "producer doc(s) still instruct omitting the block on a clean "
            "review — contradicting the metadata-only clean-round rule, so "
            "round numbering silently stalls on clean rounds: "
            + ", ".join(offenders),
        )

    def test_guard_flags_a_producer_missing_the_rule(self):
        """Negative control: prove the guard is placement-aware, per placement.

        Synthetic text, not a mutate-and-restore of a repo file — this worktree
        is shared with concurrent sessions.
        """
        directive = (
            _ROUND_HEADER_DIRECTIVE + " Emit exactly one line of the form\n"
            "`Round: <N> @ <timestamp>`. Obtain the timestamp by running\n"
            "`date -u +%Y-%m-%dT%H:%M:%SZ` — never estimate it. A\n"
            "**zero-concern** review still emits the block.\n"
        )
        rules_entry = (
            "- **Round header.** The first line after the opening fence is\n"
            "  `Round: <N> @ <timestamp>` and nothing else. Get the timestamp\n"
            "  from `date -u +%Y-%m-%dT%H:%M:%SZ`. A **zero-concern** review\n"
            "  still emits the fences with only this header between them.\n"
        )
        base = "Rules — all " + self.PRODUCER_MARKER + "; match them exactly:\n"

        # Neither copy.
        self.assertFalse(_states_round_header_rule(base))
        # Rules-list entry only — the directive was deleted.
        self.assertFalse(_states_round_header_rule(base + rules_entry))
        # Directive only — the rules-list entry was deleted.
        self.assertFalse(_states_round_header_rule(base + directive))
        # Both placements present.
        self.assertTrue(_states_round_header_rule(base + directive + rules_entry))

        # The omit-rule predicate flips on each phrase individually…
        for phrase in ("omit the block entirely", "omit it entirely",
                       "emit no concern block"):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    _retains_omit_block_rule(base + "If clean, " + phrase + ".")
                )
        # …and not on compliant text.
        self.assertFalse(_retains_omit_block_rule(base + directive + rules_entry))

    def test_production_assertion_fails_on_a_real_offender(self):
        """Negative control for the production assertion itself.

        Runs **the production methods themselves** against a fixture directory
        (one compliant producer, one offender each way) — not a re-implemented
        offender scan, which a wrong-predicate mutation would never reach (see
        the rationale on
        :meth:`TestProducerRejectionSuppressionRule.test_production_assertion_fails_on_a_real_offender`).
        Patching ``SHADOW_DIR`` exercises the real ``_producers`` glob-and-filter
        and touches no shared file.
        """
        import tempfile
        from unittest import mock

        marker_line = "Rules — all " + self.PRODUCER_MARKER + "; match them exactly:\n"
        directive = (
            _ROUND_HEADER_DIRECTIVE + " Emit exactly one line of the form\n"
            "`Round: <N> @ <timestamp>`. Obtain the timestamp by running\n"
            "`date -u +%Y-%m-%dT%H:%M:%SZ` — never estimate it. A\n"
            "**zero-concern** review still emits the block.\n"
        )
        rules_entry = (
            "- **Round header.** The first line after the opening fence is\n"
            "  `Round: <N> @ <timestamp>` and nothing else. Get the timestamp\n"
            "  from `date -u +%Y-%m-%dT%H:%M:%SZ`. A **zero-concern** review\n"
            "  still emits the fences with only this header between them.\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "good.md"), "w", encoding="utf-8") as fh:
                fh.write(marker_line + directive + rules_entry)
            # Compliant except the directive was removed.
            with open(os.path.join(tmp, "bad.md"), "w", encoding="utf-8") as fh:
                fh.write(marker_line + rules_entry)
            # Fully rule-stating, but the omit rule survived alongside.
            with open(os.path.join(tmp, "omit.md"), "w", encoding="utf-8") as fh:
                fh.write(marker_line + directive + rules_entry
                         + "- If clean, omit the block entirely and say so.\n")
            # Not a producer at all (no marker) — must be ignored, not flagged.
            with open(os.path.join(tmp, "notaproducer.md"), "w",
                      encoding="utf-8") as fh:
                fh.write("Prose with no producer marker and no rule.\n")

            with mock.patch.object(TestProducerRoundHeaderRule,
                                   "SHADOW_DIR", tmp):
                self.assertEqual(sorted(self._producers()),
                                 ["bad.md", "good.md", "omit.md"])
                with self.assertRaises(AssertionError) as missing:
                    self.test_every_producer_states_the_round_header_rule()
                with self.assertRaises(AssertionError) as retained:
                    self.test_no_producer_retains_the_omit_block_rule()

        message = str(missing.exception)
        self.assertIn("bad.md", message,
                      "the positive assertion failed without naming the "
                      "offending producer")
        self.assertNotIn("good.md", message,
                         "the positive assertion flagged the COMPLIANT fixture")
        omit_message = str(retained.exception)
        self.assertIn("omit.md", omit_message,
                      "the omit-rule assertion failed without naming the "
                      "offending producer")
        self.assertNotIn("good.md", omit_message,
                         "the omit-rule assertion flagged the COMPLIANT fixture")

    def test_every_producer_example_starts_with_a_round_header(self):
        """Each producer's example block leads with a concrete round header.

        The example is what the agent pattern-matches against — a rule stated
        twice but contradicted by the example is a rule the agent may skip.
        The first markdown code fence containing a `- [` item line must open
        with the header, immediately followed by the first item.
        """
        import re as _re

        header_re = _re.compile(
            r"^\s*Round: \d+ @ \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        )

        def fence_bodies(text: str) -> list[list[str]]:
            """Bodies of markdown code fences, walked line-wise.

            A findall over ``` pairs mispairs when a ```bash block precedes
            the example (the closing fence of one block matches as the opening
            fence of the next), so walk the lines and toggle instead.
            """
            bodies: list[list[str]] = []
            current: list[str] | None = None
            for line in text.splitlines():
                if line.strip().startswith("```"):
                    if current is None:
                        current = []
                    else:
                        bodies.append(current)
                        current = None
                elif current is not None:
                    current.append(line)
            return bodies

        for name, text in self._producers().items():
            with self.subTest(producer=name):
                examples = [
                    body for body in fence_bodies(text)
                    if any(line.lstrip().startswith("- [") for line in body)
                ]
                self.assertTrue(examples,
                                f"{name}: no example block with item lines")
                body_lines = [line for line in examples[0] if line.strip()]
                self.assertRegex(body_lines[0].strip(), header_re,
                                 f"{name}: example does not open with a "
                                 "round header")
                self.assertTrue(
                    body_lines[1].lstrip().startswith("- ["),
                    f"{name}: the first item must directly follow the header",
                )


class TestRenderedShadowDocsKeepTheGuarantees(unittest.TestCase):
    """The same guarantees must survive rendering (t1311).

    The shadow skill is templated: at runtime the agent reads
    ``.claude/skills/aitask-shadow-<profile>-/``, not the authoring dir every
    class above inspects. A conditional that dropped the concern-block rules
    from one profile's render — or a template that accidentally joined an
    inline sentinel mention into a contiguous block — would leave those classes
    green while the surface actually executed was broken.

    ``fast`` is the profile whose render strips content (it is the only one
    setting ``shadow_impl_review_tier``), so it is the weakest surface.
    """

    PROFILE = "fast"
    RENDERED_DIR = os.path.join(
        os.path.dirname(__file__), "..", ".claude", "skills",
        "aitask-shadow-%s-" % PROFILE,
    )
    PRODUCER_MARKER = TestProducerShortRegionRule.PRODUCER_MARKER
    KNOWN_PRODUCERS = TestProducerShortRegionRule.KNOWN_PRODUCERS

    @classmethod
    def setUpClass(cls):
        """Render on demand — rendered dirs are gitignored, so a fresh checkout
        has none and an existence check alone would skip silently forever."""
        import subprocess

        repo = os.path.join(os.path.dirname(__file__), "..")
        proc = subprocess.run(
            ["./.aitask-scripts/aitask_skill_render.sh", "aitask-shadow",
             "--profile", cls.PROFILE, "--agent", "claude", "--force"],
            cwd=repo, capture_output=True, text=True,
        )
        cls.rendered_ok = proc.returncode == 0 and os.path.isdir(cls.RENDERED_DIR)

    def setUp(self):
        if not self.rendered_ok:
            self.skipTest(
                "shadow variant could not be rendered (run 'ait setup' to "
                "install minijinja in the framework venv)"
            )

    def _rendered_docs(self):
        import glob

        docs = sorted(glob.glob(os.path.join(self.RENDERED_DIR, "*.md")))
        self.assertTrue(docs, "no rendered shadow docs found — render failed?")
        return docs

    def _rendered_producers(self):
        found = {}
        for path in self._rendered_docs():
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if self.PRODUCER_MARKER in text:
                found[os.path.basename(path)] = text
        return found

    def test_no_rendered_doc_is_parser_live(self):
        offenders = []
        for path in self._rendered_docs():
            with open(path, encoding="utf-8") as fh:
                if has_concern_block(fh.read()):
                    offenders.append(os.path.basename(path))
        self.assertEqual(
            offenders,
            [],
            "rendered shadow doc(s) embed a parser-live concern block: "
            + ", ".join(offenders),
        )

    def test_no_rendered_doc_embeds_any_contiguous_block(self):
        offenders = []
        for path in self._rendered_docs():
            with open(path, encoding="utf-8") as fh:
                if contains_any_concern_block(fh.read()):
                    offenders.append(os.path.basename(path))
        self.assertEqual(
            offenders,
            [],
            "rendered shadow doc(s) embed a contiguous open->items->close block: "
            + ", ".join(offenders),
        )

    def test_rendered_producer_set_is_the_known_set(self):
        """A producer that failed to render is a producer whose rules the agent
        never reads — indistinguishable, at runtime, from one that has none."""
        self.assertEqual(sorted(self._rendered_producers()), self.KNOWN_PRODUCERS)

    def test_every_rendered_producer_states_both_region_rules(self):
        short = [n for n, t in self._rendered_producers().items()
                 if not _states_short_region_rule(t)]
        required = [n for n, t in self._rendered_producers().items()
                    if not _states_region_required_rule(t)]
        self.assertEqual(short, [], "rendered producer(s) lost the short-region "
                                    "rule: " + ", ".join(short))
        self.assertEqual(required, [], "rendered producer(s) lost the "
                                       "region-is-mandatory rule: " + ", ".join(required))

    def test_every_rendered_producer_states_the_suppression_rule(self):
        """A conditional that dropped the rule from one profile's render would
        leave the authoring-dir guard green while the executed surface re-raised
        rejected concerns."""
        offenders = [n for n, t in self._rendered_producers().items()
                     if not _states_rejection_suppression_rule(t)]
        self.assertEqual(
            offenders,
            [],
            "rendered producer(s) lost the rejection-suppression rule in one or "
            "both placements: " + ", ".join(offenders),
        )

    def test_every_rendered_producer_states_the_round_header_rule(self):
        """Same rationale for the round-header rule (t1159_1): the rendered
        tree is the surface the agent actually reads."""
        offenders = [n for n, t in self._rendered_producers().items()
                     if not _states_round_header_rule(t)]
        self.assertEqual(
            offenders,
            [],
            "rendered producer(s) lost the round-header rule in one or both "
            "placements: " + ", ".join(offenders),
        )

    def test_no_rendered_producer_retains_the_omit_block_rule(self):
        """A conditional that resurrected the pre-round omit-when-clean wording
        in one profile's render would contradict the metadata-only rule on the
        executed surface while the authoring guard stayed green."""
        offenders = [n for n, t in self._rendered_producers().items()
                     if _retains_omit_block_rule(t)]
        self.assertEqual(
            offenders,
            [],
            "rendered producer(s) still instruct omitting the block on a clean "
            "review: " + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()

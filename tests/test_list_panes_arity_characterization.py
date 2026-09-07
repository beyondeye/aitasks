"""Characterization of `_LIST_PANES_FORMAT` arity handling (t1705_4 pre-phase).

t1705_4 appends four fields to ``TmuxMonitor._LIST_PANES_FORMAT``
(``@aitask_frozen``, ``@aitask_record``, ``@aitask_standin_ready``,
``pane_dead``). The risk that motivates this file is that the format's failure
mode is **silent absence**: ``_parse_list_panes`` drops any record whose field
count is outside the CLOSED ``_LIST_PANES_ARITIES`` set, so a format change
without a matching arity change blanks every agent list in monitor, minimonitor
and board rather than raising.

The contract pinned here is stricter than "appending is safe":

* the format's own arity parses and every field lands where it is read;
* **appending one field is NOT transparently safe** — the longer row is dropped
  whole. It becomes safe only when ``_LIST_PANES_ARITIES`` is extended in the
  same change. (This is what ``test_monitor_companion_filter.py``'s
  ``test_over_and_under_length_rows_are_rejected`` already asserts from the
  other direction; it is restated here because it is the exact hazard of the
  change this file guards.)
* a field **inserted** before ``history_size`` keeps the arity and therefore
  parses — yielding the WRONG ``history_size``. That is the silent field shift
  the append-never-insert rule exists to prevent, and it is a negative control:
  it demonstrates the hazard, it is not a desirable outcome;
* a trailing empty ``@option`` still yields a full-arity record (the ``strip()``
  regression t1686 fixed — the buffer must not be stripped, or the last row
  loses its final tab).

Every case derives its expectations from ``_LIST_PANES_FORMAT`` /
``_LIST_PANES_ARITIES`` at runtime rather than from a literal count, so the file
keeps its meaning across the arity change it exists to protect: only
``test_current_format_arity_is_the_expected_one`` states the number, and it is
the single line to update.

No live tmux: ``_parse_list_panes`` is fed a scripted ``list-panes`` string and
``_is_companion_process`` is patched to a constant.

Run: python3 tests/test_list_panes_arity_characterization.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

# The suite may run inside a live agent pane; scrub the ambient tmux env so
# TmuxMonitor does not adopt this pane as `exclude_pane` and silently drop a
# fixture row (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.monitor_core import TmuxMonitor  # noqa: E402

#: The arity `_LIST_PANES_FORMAT` currently emits. 15 since t1705_4 appended
#: `@aitask_frozen`, `@aitask_record`, `@aitask_standin_ready` and
#: `#{pane_dead}` to t1686's 11. THE one literal in this file — every other
#: expectation is derived from the format at runtime, so this is the single
#: line to update when the format grows.
CURRENT_ARITY = 15

#: Index of `#{history_size}` in the format. The insert-shift control targets
#: it because it is the first *numerically parsed* field after the block of
#: fixed columns, so a shift is observable as a wrong value rather than only as
#: a wrong string.
HISTORY_INDEX = 9

_AGENT_PID = 1111


def _make_monitor(session: str = "demo") -> TmuxMonitor:
    return TmuxMonitor(
        session=session, multi_session=False, agent_prefixes=["agent-"],
        exclude_pane="",
    )


def _format_fields() -> list[str]:
    """The `#{...}` specs of `_LIST_PANES_FORMAT`, in emission order."""
    return TmuxMonitor._LIST_PANES_FORMAT.split("\t")


def _row_parts(
    *,
    window_name: str = "agent-pick-42",
    pane_id: str = "%1",
    pane_pid: int = _AGENT_PID,
    history_size: str = "500",
) -> list[str]:
    """One full-arity `list-panes` record as a field list.

    Built to the LIVE format length: the fixed columns tmux emits first, then
    an empty string for every remaining field. Deriving the tail from the
    format is what keeps this builder correct across the arity change — a
    builder pinned to a literal count is exactly the vacuous-pass hazard
    `ArityToleranceTests` documents.
    """
    head = [
        "7", window_name, "1", pane_id, str(pane_pid), "python", "80", "24",
        "",              # @aitask_shadow_target
        history_size,    # history_size
    ]
    tail = [""] * (len(_format_fields()) - len(head))
    return head + tail


def _parse(stdout: str, *, ignore_markers: bool = False) -> list:
    """Parse `stdout` with the companion filter's rungs neutralised.

    ``ignore_markers`` additionally silences rung 1
    (:func:`is_live_companion_marker`). Only the insert-shift control needs it —
    see the comment there; every other case leaves the real rule in play.
    """
    mon = _make_monitor()
    with patch("monitor.monitor_core._is_companion_process", lambda pid: False):
        if ignore_markers:
            with patch("monitor.monitor_core.is_live_companion_marker",
                       lambda value: False):
                panes, _shadows = mon._parse_list_panes(stdout, "demo")
        else:
            panes, _shadows = mon._parse_list_panes(stdout, "demo")
    return panes


class FormatArityTests(unittest.TestCase):
    """The format's own arity, and the arity set that admits it."""

    def test_current_format_arity_is_the_expected_one(self):
        """`_LIST_PANES_FORMAT` emits exactly `CURRENT_ARITY` fields.

        The canary for a format edit made without reading this file: change the
        format and this fails first, before the subtler cases below.
        """
        self.assertEqual(
            len(_format_fields()), CURRENT_ARITY,
            "_LIST_PANES_FORMAT changed arity — update CURRENT_ARITY here AND "
            "_LIST_PANES_ARITIES in monitor_core.py, in the same commit",
        )

    def test_current_arity_is_admitted_by_the_arity_set(self):
        """The emitted arity MUST be in `_LIST_PANES_ARITIES`.

        This is the whole hazard of t1705_4 in one assertion. The set is closed
        (`monitor_core.py`: "an unexpected arity is dropped whole"), so a format
        that emits an arity outside it makes `_parse_list_panes` return NOTHING
        for every pane — a total, silent blanking of every agent list rather
        than an error.
        """
        self.assertIn(
            len(_format_fields()), TmuxMonitor._LIST_PANES_ARITIES,
            "the live format's arity is not in the CLOSED set "
            f"{TmuxMonitor._LIST_PANES_ARITIES} — every pane record would be "
            "dropped whole and monitor/minimonitor/board would list no agents",
        )

    def test_full_arity_row_parses_and_every_read_field_lands(self):
        parts = _row_parts(pane_id="%7", pane_pid=4242, history_size="613")
        panes = _parse("\t".join(parts))
        self.assertEqual([p.pane_id for p in panes], ["%7"])
        pane = panes[0]
        self.assertEqual(pane.window_name, "agent-pick-42")
        self.assertEqual(pane.pane_pid, 4242)
        self.assertEqual(pane.current_command, "python")
        self.assertEqual(pane.width, 80)
        self.assertEqual(pane.height, 24)
        self.assertEqual(pane.history_size, 613,
                         "history_size must come from its own index, not a "
                         "neighbour's")

    def test_frozen_fields_land_on_their_own_indices(self):
        """The four t1705_4 fields, each given a DISTINCT value.

        Distinct on purpose: with equal placeholders an off-by-one in the
        parser's index guards is invisible.
        """
        parts = _row_parts(pane_id="%8")
        parts[11] = "7f3a2c1d"   # @aitask_frozen
        parts[12] = "aabbccdd"   # @aitask_record
        parts[13] = "11223344"   # @aitask_standin_ready
        parts[14] = "1"          # pane_dead

        pane = _parse("\t".join(parts))[0]
        self.assertEqual(pane.frozen_record, "7f3a2c1d")
        self.assertEqual(pane.record_id, "aabbccdd")
        self.assertEqual(pane.standin_ready, "11223344")
        self.assertIs(pane.pane_dead, True)

    def test_legacy_row_reads_the_frozen_fields_as_absent(self):
        """A pre-t1705_4 (11-field) record must not look frozen or dead.

        The defaults are what keep every legacy arity meaningful rather than
        merely parseable: `pane_dead` in particular must be False, not a truthy
        empty string, or a legacy record would read as a dead pane.
        """
        pane = _parse("\t".join(_row_parts(pane_id="%9")[:11]))[0]
        self.assertEqual(pane.frozen_record, "")
        self.assertEqual(pane.record_id, "")
        self.assertEqual(pane.standin_ready, "")
        self.assertIs(pane.pane_dead, False)

    def test_pane_dead_zero_is_false_not_truthy(self):
        """`#{pane_dead}` is compared as a STRING — `bool("0")` is True."""
        parts = _row_parts(pane_id="%10")
        parts[14] = "0"
        self.assertIs(_parse("\t".join(parts))[0].pane_dead, False)


class AppendIsNotFreeTests(unittest.TestCase):
    """Appending a field is safe ONLY together with the arity-set extension."""

    def test_one_extra_trailing_field_is_dropped_whole(self):
        """The append hazard, stated positively.

        A row one field longer than the format is NOT truncated to the known
        fields — it is discarded, and the pane vanishes from discovery. This is
        the desired failure mode (loud by absence rather than reinterpreted
        field-by-field), and it is exactly why extending `_LIST_PANES_FORMAT`
        without extending `_LIST_PANES_ARITIES` in the same change blanks every
        agent list.
        """
        parts = _row_parts(pane_id="%3")
        over = parts + ["extra"]
        self.assertNotIn(
            len(over), TmuxMonitor._LIST_PANES_ARITIES,
            "precondition: the over-length arity must be outside the set",
        )
        self.assertEqual(
            _parse("\t".join(over)), [],
            "a row one field longer than the format must be dropped whole, "
            f"not truncated (arity set: {TmuxMonitor._LIST_PANES_ARITIES})",
        )

    def test_short_row_is_dropped_whole(self):
        parts = _row_parts(pane_id="%3")[:8]
        self.assertNotIn(len(parts), TmuxMonitor._LIST_PANES_ARITIES,
                         "precondition: the short arity must be outside the set")
        self.assertEqual(_parse("\t".join(parts)), [],
                         "an under-length record must be rejected, not padded")

    def test_legacy_arities_still_parse(self):
        """Every arity the set admits must actually parse.

        Iterating the set rather than naming 9/10/11 keeps this honest when the
        set grows: a new arity added to the tuple without the parser being able
        to handle it fails here.
        """
        full = _row_parts(pane_id="%9")
        for arity in sorted(TmuxMonitor._LIST_PANES_ARITIES):
            with self.subTest(arity=arity):
                row = full[:arity] if arity <= len(full) else (
                    full + [""] * (arity - len(full))
                )
                self.assertEqual(
                    [p.pane_id for p in _parse("\t".join(row))], ["%9"],
                    f"arity {arity} is in _LIST_PANES_ARITIES but does not parse",
                )


class InsertShiftsSilentlyTests(unittest.TestCase):
    """NEGATIVE CONTROL — an inserted field keeps the arity and corrupts values.

    This is not a behaviour to preserve; it is the hazard that makes "append,
    never insert" a rule. Inserting a column before `history_size` leaves the
    field count untouched, so the closed arity set cannot catch it: the record
    parses cleanly and `history_size` silently reads its left neighbour.
    """

    def test_inserted_field_parses_but_shifts_history_size(self):
        parts = _row_parts(pane_id="%5", history_size="777")
        # Insert immediately before `history_size` and drop the last field so
        # the arity is unchanged — the shift, not a length change, is the point.
        # The inserted value is NUMERIC on purpose: history_size then parses to
        # a plausible wrong number rather than to None, which is the genuinely
        # dangerous shape (a `None` at least reads as "unknown" downstream).
        shifted = parts[:HISTORY_INDEX] + ["24"] + parts[HISTORY_INDEX:]
        shifted = shifted[:len(parts)]
        self.assertEqual(len(shifted), len(parts),
                         "precondition: the insert must not change the arity")

        # `ignore_markers`: shifting right pushes the real history value into
        # the LAST column, which at the pre-t1705_4 arity is
        # `@aitask_monitor_kind` — and a non-empty unparseable marker classifies
        # as a live companion (`monitor_marker_state`: "non-empty but NOT
        # parseable -> present"), so the pane would be filtered out for a reason
        # that has nothing to do with the field shift under test. Silencing that
        # rung keeps the case measuring exactly one thing.
        panes = _parse("\t".join(shifted), ignore_markers=True)
        self.assertEqual([p.pane_id for p in panes], ["%5"],
                         "an inserted field does NOT make the record fail — "
                         "that is the hazard")
        self.assertEqual(
            panes[0].history_size, 24,
            "history_size must have read its left neighbour's value; if this "
            "ever fails, the parser stopped reading history_size positionally "
            "and this control needs rewriting",
        )
        self.assertNotEqual(
            panes[0].history_size, 777,
            "the record's real history value must NOT have survived the shift",
        )


class TrailingEmptyOptionTests(unittest.TestCase):
    """t1686's `strip()` regression: the LAST row's empty option is a field."""

    def test_trailing_empty_option_on_the_last_record_survives(self):
        """tmux emits `…\\t\\n` for a record whose final field is unset.

        `_parse_list_panes` splits `stdout.splitlines()` — deliberately NOT
        `stdout.strip().splitlines()`. A whole-buffer strip eats that final tab,
        the record drops to a rejected arity, and the pane disappears. With the
        four options appended by t1705_4 the format ends in a run of usually
        empty fields, so this is now the common shape, not an edge case.
        """
        row = "\t".join(_row_parts(pane_id="%2"))
        self.assertTrue(row.endswith("\t"),
                        "precondition: the format's last field must be empty "
                        "in this fixture, or the case proves nothing")
        stdout = row + "\n"
        self.assertEqual([p.pane_id for p in _parse(stdout)], ["%2"])

    def test_trailing_empty_option_survives_beside_a_full_row(self):
        """Two records, the empty-tailed one last — the position that breaks."""
        first = "\t".join(_row_parts(pane_id="%1", history_size="10"))
        last = "\t".join(_row_parts(pane_id="%2", history_size="20"))
        stdout = first + "\n" + last + "\n"
        self.assertEqual([p.pane_id for p in _parse(stdout)], ["%1", "%2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

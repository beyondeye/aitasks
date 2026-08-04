"""Tests for the shared shadow seam lifted out of minimonitor (t1216_1).

The seam is the set of shadow helpers both `ait monitor` and `ait minimonitor`
need: the reverse pane lookup, the wrap-joined capture shell-out, the staleness
comparison, a single-shadow refresh with a merge contract, and a cheap
concern-block freshness trigger. They used to live inside `minimonitor_app.py`,
shaped around its "exactly one followed agent" assumption.

Two things are load-bearing here and are tested as such:

- **The lifted helpers are duck-typed on the tmux gateway surface** (`tmux_run` /
  `tmux_run_async`), not on a concrete `TmuxMonitor`. That is what lets both apps
  — and the existing `_FakeMon` stubs across the shadow suite — pass whatever
  monitor they already hold.
- **`refresh_shadow_snapshot` must be safe against an interleaved full refresh.**
  `_shadow_snapshots` is rebuilt by `commit_snapshots` on every full cycle, so a
  naive per-shadow write would clobber it (or be clobbered by it) depending on
  timing. There is one test per binding rule below, each with the negative
  control that proves the guard — not the fixture — is doing the work.

All ordering is deterministic through the injectable `_run_offloaded` seam and
scripted coroutines — no sleeps, no real tmux (per
`aidocs/framework/testing_conventions.md`).

Run: python3 tests/test_shadow_seam.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.concern_parser import (  # noqa: E402
    _SENTINEL_SAFE_COLS,
    concern_block_signature,
)
from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    SHADOW_TARGET_OPTION,
    TmuxMonitor,
    TmuxPaneInfo,
    capture_shadow_text,
    compute_shadow_staleness,
    find_shadow_pane,
    find_shadow_pane_async,
    match_shadow_pane,
    shadow_query_args,
)
from monitor.monitor_shared import format_stale_duration  # noqa: E402
from monitor.prompt_patterns import all_patterns  # noqa: E402

_ACTIVE_CONTENT = "agent output line\nworking..."


def _pane(
    pane_id: str,
    window_name: str = "agent-1",
    category: PaneCategory = PaneCategory.AGENT,
    shadow_target: str = "",
    width: int = 80,
) -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=width, height=24, category=category, session_name="demo",
        shadow_target=shadow_target,
    )


class _FakeMon:
    """Stub exposing only the gateway entries the lifted lookups use.

    Mirrors ``tests/test_minimonitor_concern_action._FakeMon`` on purpose: if the
    lifted helpers ever stop being duck-typed on this surface, this class stops
    working and the existing minimonitor suite breaks with it.
    """

    def __init__(self, sync_list: str = "", async_list: str = "", rc: int = 0) -> None:
        self._sync_list = sync_list
        self._async_list = async_list
        self._rc = rc
        self.sync_calls: list = []
        self.async_calls: list = []

    def tmux_run(self, args, timeout=5.0):
        self.sync_calls.append((args, timeout))
        return (self._rc, self._sync_list)

    async def tmux_run_async(self, args, timeout=5.0):
        self.async_calls.append((args, timeout))
        return (self._rc, self._async_list)


async def _sync_offloaded(fn):
    return fn()


def _make_monitor(panes, shadows, content):
    """Real TmuxMonitor with scripted discovery/capture — no tmux, no sleeps.

    Same construction as ``tests/test_monitor_shadow_status._make_monitor``.
    """
    mon = TmuxMonitor(
        session="demo", multi_session=False, agent_prefixes=["agent-"],
        prompt_patterns=all_patterns(), idle_threshold=5.0,
    )
    mon._run_offloaded = _sync_offloaded
    for p in panes:
        mon._pane_cache[p.pane_id] = p

    async def discover_with_shadows(*, enum_sink=None):
        # Accepts the real seam's enumeration sink (t1326).
        if enum_sink is not None:
            enum_sink.append(frozenset(
                p.session_name for p in list(panes) + list(shadows) if p.session_name))
        return list(panes), list(shadows)

    async def cap_content(pane_id, capture_lines=None, pane=None):
        if pane_id not in content:
            return None
        if pane is None:
            pane = mon._pane_cache.get(pane_id)
        if pane is None:
            return None
        return pane, content[pane_id]

    mon.discover_panes_with_shadows_async = discover_with_shadows
    mon.capture_pane_content_async = cap_content
    return mon


async def _full_refresh(mon):
    """One complete full cycle (produce + commit)."""
    gen, classified = await mon.capture_all_classified_async()
    return mon.commit_snapshots(gen, classified)


# ---------------------------------------------------------------------------
# match_shadow_pane / lookups
# ---------------------------------------------------------------------------

class MatchShadowPaneTests(unittest.TestCase):
    def test_returns_bound_shadow(self):
        out = "%1\t\n%5\t%1\n%6\t%2\n"
        self.assertEqual(match_shadow_pane(out, "%1"), "%5")

    def test_no_match_returns_none(self):
        self.assertIsNone(match_shadow_pane("%1\t\n%6\t%2\n", "%1"))

    def test_whitespace_only_target_is_not_a_shadow(self):
        self.assertIsNone(match_shadow_pane("%5\t   \n", "%1"))

    def test_newest_wins_when_duplicated(self):
        out = "%5\t%1\n%8\t%1\n%3\t%1\n"
        self.assertEqual(match_shadow_pane(out, "%1"), "%8")

    def test_malformed_rows_are_skipped(self):
        out = "no-tab-here\n%8\t%1\n"
        self.assertEqual(match_shadow_pane(out, "%1"), "%8")


class FindShadowPaneTests(unittest.TestCase):
    def test_sync_lookup_uses_gateway_and_matches(self):
        mon = _FakeMon(sync_list="%5\t%1\n")
        self.assertEqual(find_shadow_pane(mon, "%1"), "%5")
        args, _ = mon.sync_calls[0]
        self.assertEqual(args, shadow_query_args())
        self.assertIn(SHADOW_TARGET_OPTION, args[-1])
        self.assertEqual(mon.async_calls, [])  # sync guard issues no await

    async def _async_lookup(self, mon):
        return await find_shadow_pane_async(mon, "%1")

    def test_async_lookup_uses_gateway_and_matches(self):
        mon = _FakeMon(async_list="%5\t%1\n")
        self.assertEqual(asyncio.run(self._async_lookup(mon)), "%5")
        self.assertEqual(mon.sync_calls, [])

    def test_nonzero_rc_is_none(self):
        self.assertIsNone(find_shadow_pane(_FakeMon(sync_list="%5\t%1\n", rc=1), "%1"))
        mon = _FakeMon(async_list="%5\t%1\n", rc=1)
        self.assertIsNone(asyncio.run(self._async_lookup(mon)))

    def test_missing_monitor_is_none(self):
        self.assertIsNone(find_shadow_pane(None, "%1"))
        self.assertIsNone(asyncio.run(find_shadow_pane_async(None, "%1")))


# ---------------------------------------------------------------------------
# capture_shadow_text
# ---------------------------------------------------------------------------

class CaptureShadowTextTests(unittest.TestCase):
    """What the capture actually runs. The rest of the shadow suite stubs this
    out, so the argv (and the t1187 `--deep` fix living in it) is only pinned
    here."""

    def _run_capture(self, **kwargs):
        recorded: dict = {}

        class _FakeProc:
            returncode = 0

            async def communicate(self):
                return (b"captured text", b"")

        async def _fake_exec(*argv, **kw):
            recorded["argv"] = list(argv)
            recorded["env"] = kw.get("env")
            return _FakeProc()

        orig = asyncio.create_subprocess_exec
        asyncio.create_subprocess_exec = _fake_exec
        try:
            out = asyncio.run(capture_shadow_text("%5", **kwargs))
        finally:
            asyncio.create_subprocess_exec = orig
        return out, recorded

    def test_uses_plan_review_depth_and_the_capture_script(self):
        out, rec = self._run_capture()
        self.assertEqual(out, "captured text")
        self.assertEqual(rec["argv"][1:], ["--deep", "--any-pane", "%5"])
        self.assertTrue(rec["argv"][0].endswith("aitask_shadow_capture.sh"))
        self.assertIsNone(rec["env"])  # no override => inherit the environment

    def test_lines_override_sets_plan_capture_lines(self):
        _, rec = self._run_capture(lines=1500)
        self.assertEqual(rec["argv"][1:], ["--deep", "--any-pane", "%5"])
        self.assertEqual(rec["env"]["SHADOW_PLAN_CAPTURE_LINES"], "1500")
        self.assertIn("PATH", rec["env"])  # inherited, not replaced

    def test_opts_out_of_the_wrong_pane_refusal(self):
        """This reader must NOT inherit the helper's wrong-pane guard (t1319).

        `aitask_shadow_capture.sh` refuses an explicit pane id that its own
        pane's `@aitask_shadow_target` contradicts, or that it cannot vouch for
        because the caller sits on a different tmux server. Both are wrong here,
        for two independent reasons:

        1. The guard exists to catch a pane id a *model* transcribed and may
           have truncated. `shadow_pane` comes from `find_shadow_pane`, so there
           is no transcription to protect against.
        2. A TUI run from the user's personal tmux while the framework lives on
           `-L ait` IS a cross-server caller. Since this call sends stderr to
           DEVNULL and maps a non-zero exit to None, that refusal would reach
           the user as a silent "no concerns" rather than as an error.

        `--any-pane` is the single sanctioned opt-out; asserting it here keeps
        it from being dropped, and this docstring keeps it from being copied to
        a caller whose pane id IS model-supplied.
        """
        _, rec = self._run_capture()
        self.assertIn("--any-pane", rec["argv"])

    def test_capture_never_stamps_analyzed_at_from_a_non_shadow_caller(self):
        """The freshness stamp is the SHADOW's own act, not the reader's.

        `aitask_shadow_capture.sh` only stamps `@aitask_shadow_analyzed_at` when
        it runs inside a shadow pane capturing its bound agent. A monitor reading
        a shadow pane runs from a non-shadow pane, so adding this second caller
        must not start stamping — otherwise a monitor's own polling would forever
        mark the shadow "just analyzed" and staleness could never fire.
        """
        _, rec = self._run_capture()
        self.assertNotIn("--stamp", rec["argv"])
        # The guard lives in the script and keys off the CALLER's own pane.
        script = REPO_ROOT / ".aitask-scripts" / "aitask_shadow_capture.sh"
        body = script.read_text(encoding="utf-8")
        self.assertIn('[[ -n "$own_pane" ]] || return 0', body)
        self.assertIn('"$self_target" == "$pane"', body)

    def test_spawn_failure_degrades_to_none(self):
        async def _boom(*a, **k):
            raise OSError("no such file")

        orig = asyncio.create_subprocess_exec
        asyncio.create_subprocess_exec = _boom
        try:
            self.assertIsNone(asyncio.run(capture_shadow_text("%5")))
        finally:
            asyncio.create_subprocess_exec = orig

    def test_nonzero_returncode_degrades_to_none(self):
        class _FailProc:
            returncode = 2

            async def communicate(self):
                return (b"", b"")

        async def _fake_exec(*a, **k):
            return _FailProc()

        orig = asyncio.create_subprocess_exec
        asyncio.create_subprocess_exec = _fake_exec
        try:
            self.assertIsNone(asyncio.run(capture_shadow_text("%5")))
        finally:
            asyncio.create_subprocess_exec = orig


# ---------------------------------------------------------------------------
# compute_shadow_staleness — one test per row of the contract table
# ---------------------------------------------------------------------------

class _StaleMon:
    def __init__(self, stamp="", last_change=None, raises=False):
        self._stamp = stamp
        self._last_change = last_change
        self._raises = raises
        self.lcw_calls: list = []

    async def get_pane_option(self, pane_id, option):
        if self._raises:
            raise RuntimeError("tmux said no")
        return self._stamp

    def get_last_change_wall(self, pane_id):
        self.lcw_calls.append(pane_id)
        return self._last_change


class ComputeShadowStalenessTests(unittest.TestCase):
    EPS = 3.0

    def _run(self, mon):
        return asyncio.run(compute_shadow_staleness(mon, "%5", "%1", self.EPS))

    def test_change_after_analysis_is_stale(self):
        stale, at = self._run(_StaleMon(stamp="1000.0", last_change=1010.0))
        self.assertIs(stale, True)
        self.assertEqual(at, 1000.0)

    def test_no_change_since_analysis_is_current(self):
        stale, at = self._run(_StaleMon(stamp="1000.0", last_change=995.0))
        self.assertIs(stale, False)
        self.assertEqual(at, 1000.0)

    def test_within_epsilon_is_not_stale(self):
        stale, _ = self._run(_StaleMon(stamp="1000.0", last_change=1002.0))
        self.assertIs(stale, False)

    def test_empty_stamp_clears_and_skips_the_last_change_lookup(self):
        """Cost gate: a shadow that never analyzed must not provoke a query."""
        mon = _StaleMon(stamp="", last_change=1010.0)
        stale, at = self._run(mon)
        self.assertIs(stale, False)   # explicit False => caller clears the banner
        self.assertIsNone(at)
        self.assertEqual(mon.lcw_calls, [])

    def test_option_read_failure_preserves(self):
        stale, at = self._run(_StaleMon(raises=True))
        self.assertIsNone(stale)
        self.assertIsNone(at)

    def test_malformed_stamp_preserves(self):
        stale, at = self._run(_StaleMon(stamp="not-a-number", last_change=1010.0))
        self.assertIsNone(stale)
        self.assertIsNone(at)

    def test_unobserved_followed_pane_preserves(self):
        stale, at = self._run(_StaleMon(stamp="1000.0", last_change=None))
        self.assertIsNone(stale)
        self.assertIsNone(at)

    def test_missing_monitor_or_gateway_preserves(self):
        self.assertEqual(self._run(None), (None, None))

        class _Bare:
            pass

        self.assertEqual(self._run(_Bare()), (None, None))

    def test_none_is_distinguishable_from_false(self):
        """The tri-state is the whole point: `None` (preserve) must never be
        conflatable with `False` (clear). A caller doing `if not stale:` would
        silently wipe a standing warning on an unreadable stamp."""
        preserve, _ = self._run(_StaleMon(raises=True))
        clear, _ = self._run(_StaleMon(stamp=""))
        self.assertIsNone(preserve)
        self.assertIs(clear, False)
        self.assertIsNot(preserve, clear)


class FormatStaleDurationTests(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(format_stale_duration(0), "0s")
        self.assertEqual(format_stale_duration(-5), "0s")
        self.assertEqual(format_stale_duration(59.9), "59s")
        self.assertEqual(format_stale_duration(60), "1m00s")
        self.assertEqual(format_stale_duration(125), "2m05s")
        self.assertEqual(format_stale_duration(3600), "1h00m")
        self.assertEqual(format_stale_duration(7565), "2h06m")


# ---------------------------------------------------------------------------
# concern_block_signature
# ---------------------------------------------------------------------------

_OPEN = "===AITASK-CONCERNS==="
_CLOSE = "===END-CONCERNS==="


def _block(*items: str) -> str:
    return "\n".join([_OPEN, *items, _CLOSE]) + "\n"


def _hard_wrap(text: str, width: int) -> str:
    """Re-render text as tmux would WITHOUT -J: break every row at `width`
    (mid-word if that is where the column lands) and pad it out with spaces."""
    out = []
    for line in text.splitlines():
        if not line:
            out.append("")
            continue
        for i in range(0, len(line), width):
            out.append(line[i:i + width].ljust(width))
    return "\n".join(out) + "\n"


_ITEM = "- [high | Step 7 guard] The guard double-commits the lock."


class ConcernBlockSignatureTests(unittest.TestCase):
    def test_none_without_a_complete_block(self):
        self.assertIsNone(concern_block_signature("just some pane output\n"))
        self.assertIsNone(concern_block_signature(_OPEN + "\n" + _ITEM + "\n"))

    def test_returns_a_digest_for_a_complete_block(self):
        self.assertIsInstance(concern_block_signature(_block(_ITEM)), str)

    # -- stable ------------------------------------------------------------

    def test_trailing_row_padding_does_not_change_the_digest(self):
        base = _block(_ITEM)
        padded = "".join(line + "      \n" for line in base.splitlines())
        self.assertEqual(
            concern_block_signature(base), concern_block_signature(padded)
        )

    def test_ansi_colour_runs_do_not_change_the_digest(self):
        base = _block(_ITEM)
        coloured = base.replace("high", "\x1b[31mhigh\x1b[0m").replace(
            _OPEN, "\x1b[1m" + _OPEN + "\x1b[0m"
        )
        self.assertEqual(
            concern_block_signature(base), concern_block_signature(coloured)
        )

    def test_word_boundary_wraps_at_several_widths_agree(self):
        """A body broken only at spaces is exactly recoverable, so the digest
        must be identical at every width — this is the reflow-stability claim."""
        item = "- [high | parser] aaaa bbbb cccc dddd eeee ffff gggg hhhh"
        base = _block(item)
        digests = {concern_block_signature(base)}
        for width in (30, 36, 42, 50):
            wrapped = "\n".join(
                _wrap_on_spaces(line, width) for line in base.splitlines()
            ) + "\n"
            digests.add(concern_block_signature(wrapped))
        self.assertEqual(len(digests), 1, f"digests diverged: {digests}")

    def test_leading_and_trailing_pane_noise_is_ignored(self):
        noisy = "unrelated scrollback\n" + _block(_ITEM) + "later output\n"
        self.assertEqual(
            concern_block_signature(_block(_ITEM)), concern_block_signature(noisy)
        )

    def test_last_block_wins(self):
        older = _block("- [low | old] stale concern.")
        newer = _block(_ITEM)
        self.assertEqual(
            concern_block_signature(older + newer), concern_block_signature(newer)
        )

    # -- discriminating ----------------------------------------------------

    def test_token_boundaries_are_preserved(self):
        """The collision that rules out collapsing whitespace to nothing."""
        a = _block("- [high | parser] needs review")
        b = _block("- [high | parser] needsreview")
        self.assertNotEqual(concern_block_signature(a), concern_block_signature(b))

    def test_changed_priority_region_or_body_changes_the_digest(self):
        base = concern_block_signature(_block("- [high | parser] body text"))
        for variant in (
            "- [low | parser] body text",
            "- [high | picker] body text",
            "- [high | parser] body texts",
        ):
            self.assertNotEqual(
                base, concern_block_signature(_block(variant)), variant
            )

    def test_added_or_removed_item_changes_the_digest(self):
        one = concern_block_signature(_block(_ITEM))
        two = concern_block_signature(_block(_ITEM, "- [low | other] second."))
        self.assertNotEqual(one, two)

    # -- residual, pinned deliberately -------------------------------------

    def test_mid_word_wrap_rehashes_known_residual(self):
        """KNOWN, ACCEPTED behaviour — do not "fix" this into a collision.

        A wrap landing mid-word injects a space that was not in the source, so
        the same block re-rendered at a width that splits a word digests
        differently. The consequence is bounded and fails safe: at most ONE
        spurious re-offer (a badge, plus one toast if the user selects it —
        nothing is lost and nothing is forwarded), never a missed real change.

        The alternative — collapsing whitespace to nothing — removes this
        residual but makes "needs review" and "needsreview" collide, i.e. it
        trades a harmless duplicate for a SILENTLY MISSED concern. That trade is
        rejected; `test_token_boundaries_are_preserved` is the other half of this
        pair, and the two must keep disagreeing.
        """
        base = _block("- [high | parser] antidisestablishmentarianism matters")
        mid_word = _hard_wrap(base, 28)
        self.assertNotEqual(
            concern_block_signature(base), concern_block_signature(mid_word)
        )

    # -- narrow pane -------------------------------------------------------

    def test_narrow_pane_wraps_the_sentinel_and_yields_none(self):
        """Below `_SENTINEL_SAFE_COLS` the fence itself is split across rows, so
        the cheap detector cannot see the block at all. It must report `None`
        rather than guess — the caller falls back to an authoritative capture."""
        # The constant is the SAFE width: at or above it neither fence can wrap.
        self.assertGreater(_SENTINEL_SAFE_COLS, len(_OPEN))
        self.assertGreater(_SENTINEL_SAFE_COLS, len(_CLOSE))
        narrow = _hard_wrap(_block(_ITEM), _SENTINEL_SAFE_COLS - 4)
        self.assertLess(_SENTINEL_SAFE_COLS - 4, len(_OPEN))  # so `_OPEN` splits
        self.assertIsNone(concern_block_signature(narrow))

    def test_at_sentinel_safe_width_the_block_is_still_seen(self):
        """Boundary control: at the documented safe width the fences survive, so
        the `None` above is attributable to the wrap and not to the fixture."""
        wide_enough = _hard_wrap(_block(_ITEM), max(len(_OPEN), _SENTINEL_SAFE_COLS))
        self.assertIsNotNone(concern_block_signature(wide_enough))


def _wrap_on_spaces(line: str, width: int) -> str:
    """Break `line` into rows of at most `width`, only at spaces (what a
    well-behaved renderer does), padding each row like tmux."""
    if len(line) <= width:
        return line
    rows, cur = [], ""
    for word in line.split(" "):
        if cur and len(cur) + 1 + len(word) > width:
            rows.append(cur.ljust(width))
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        rows.append(cur.ljust(width))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# refresh_shadow_snapshot — one test per binding rule
# ---------------------------------------------------------------------------

class ShadowRefreshBasicsTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_updates_the_bound_shadow(self):
        agent, shadow = _pane("%1"), _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)
        self.assertEqual(mon.get_shadow_snapshot("%1").content, "shadow v1")

        content["%9"] = "shadow v2"
        snap = await mon.refresh_shadow_snapshot("%1")
        self.assertIsNotNone(snap)
        self.assertEqual(mon.get_shadow_snapshot("%1").content, "shadow v2")

    async def test_unknown_followed_pane_never_resurrects(self):
        mon = _make_monitor([_pane("%1")], [], {"%1": _ACTIVE_CONTENT})
        await _full_refresh(mon)
        self.assertIsNone(await mon.refresh_shadow_snapshot("%1"))
        self.assertIsNone(mon.get_shadow_snapshot("%1"))

    async def test_refresh_keeps_shadows_out_of_the_pane_cache(self):
        agent, shadow = _pane("%1"), _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow], {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        )
        await _full_refresh(mon)
        await mon.refresh_shadow_snapshot("%1")
        self.assertNotIn("%9", mon._pane_cache)


class ShadowRefreshOrderingTests(unittest.IsolatedAsyncioTestCase):
    """Rule 1 — one total order over shadow writes, keyed by READ time."""

    async def test_late_full_refresh_does_not_clobber_a_newer_shadow_read(self):
        """Full reads first, a shadow refresh reads+merges, full commits LAST.

        The full refresh's data is older, so its wholesale rebuild must NOT win.
        This is the interleaving a commit-time stamp gets wrong.
        """
        agent = _pane("%1")
        other = _pane("%2")
        shadow = _pane("%9", shadow_target="%1")
        other_shadow = _pane("%8", shadow_target="%2")
        content = {
            "%1": _ACTIVE_CONTENT, "%2": _ACTIVE_CONTENT,
            "%9": "shadow v1", "%8": "other v1",
        }
        mon = _make_monitor([agent, other], [shadow, other_shadow], content)
        await _full_refresh(mon)

        # Full refresh READS here (v1 for both shadows) but does not commit yet.
        gen, classified = await mon.capture_all_classified_async()
        # A newer single-shadow read lands while that commit is pending.
        content["%9"] = "shadow v2"
        await mon.refresh_shadow_snapshot("%1")
        lc_after_fast = mon._last_content["%9"]
        lct_after_fast = mon._last_change_time["%9"]

        # Now the older batch commits.
        self.assertIsNotNone(mon.commit_snapshots(gen, classified))

        self.assertEqual(mon.get_shadow_snapshot("%1").content, "shadow v2")
        # Every other key still gets the full refresh's content.
        self.assertEqual(mon.get_shadow_snapshot("%2").content, "other v1")

        # The losing batch must not have written idle bookkeeping either.
        # `_apply_bookkeeping` is the sole writer of `_last_content` /
        # `_last_change_time`; if the batch applied it before the merge, the
        # displayed snapshot would be v2 while `_last_content` held v1 — and the
        # NEXT full refresh would read v2, see a difference, and reset the idle
        # clock on a change that never happened.
        self.assertEqual(mon._last_content["%9"], lc_after_fast)
        self.assertEqual(mon._last_change_time["%9"], lct_after_fast)

    async def test_late_shadow_merge_is_rejected(self):
        """Mirror case: the shadow reads first, the full refresh reads and
        commits, and only then does the merge run. The merge must lose."""
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        prev = mon._shadow_snapshots["%1"]
        stale_seq = mon._next_shadow_write_seq()  # reserved "before" the read

        content["%9"] = "shadow v3"
        await _full_refresh(mon)  # newer read + commit lands first
        self.assertEqual(mon.get_shadow_snapshot("%1").content, "shadow v3")

        # The older in-flight merge now arrives carrying v1.
        _, result = await _classify_for(mon, prev.pane, "shadow v1")
        self.assertIsNone(
            mon._merge_shadow_snapshot("%1", "%9", stale_seq, prev.pane,
                                       "shadow v1", result)
        )
        self.assertEqual(mon.get_shadow_snapshot("%1").content, "shadow v3")

    async def test_discovery_window_interleaving(self):
        """Rule 1's reservation POINT, not just its existence.

        `capture_all_classified_async` awaits discovery before it reads any
        shadow pane. If the batch's write seq were reserved at the top of that
        coroutine (beside the capture generation), a fast refresh that both
        reserved AND read entirely inside the discovery window would out-rank a
        full refresh that reads the same pane afterwards — and the full
        refresh's NEWER content would lose.
        """
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        gate = asyncio.Event()
        released = asyncio.Event()

        async def slow_discovery(*, enum_sink=None):
            released.set()
            await gate.wait()          # suspend INSIDE the discovery await
            return [agent], [shadow]

        mon.discover_panes_with_shadows_async = slow_discovery

        async def full_cycle():
            gen, classified = await mon.capture_all_classified_async()
            return mon.commit_snapshots(gen, classified)

        task = asyncio.create_task(full_cycle())
        await released.wait()

        # A complete fast refresh happens while discovery is still suspended.
        await mon.refresh_shadow_snapshot("%1")
        self.assertEqual(mon.get_shadow_snapshot("%1").content, "shadow v1")

        # Only now does the full refresh get to READ — and it reads newer data.
        content["%9"] = "shadow v9"
        gate.set()
        self.assertIsNotNone(await task)

        self.assertEqual(
            mon.get_shadow_snapshot("%1").content, "shadow v9",
            "the full refresh read AFTER the fast refresh, so its newer content "
            "must win — the batch seq must be reserved past the discovery await",
        )

    async def test_negative_control_shadow_refresh_never_bumps_capture_generation(self):
        """Rule 1's other half: the shadow path must not supersede a full
        refresh. If it reserved from `_capture_generation`, an in-flight
        `commit_snapshots` would start returning None (the t1133
        SupersessionTests would break)."""
        agent, shadow = _pane("%1"), _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        before = mon.capture_generation
        await mon.refresh_shadow_snapshot("%1")            # accepted
        await mon.refresh_shadow_snapshot("%unknown")      # rejected (no entry)
        mon.capture_pane_content_async = _failing_capture
        await mon.refresh_shadow_snapshot("%1")            # failed capture
        self.assertEqual(mon.capture_generation, before)


class ShadowRefreshIdentityTests(unittest.IsolatedAsyncioTestCase):
    """Rule 3 — existence is not identity."""

    async def test_rebound_shadow_is_not_overwritten_by_the_dead_one(self):
        """The late merge must carry a NEWER seq than the committed entry, or the
        seq guard would reject it and this would not test identity at all.

        Interleaving: the full refresh reserves its batch seq and then suspends
        mid-capture; the in-flight refresh of the OLD shadow reserves a higher
        seq while it is suspended; the full refresh then commits the replacement
        under its lower seq. The stale merge therefore passes the seq check, and
        only the pane-identity check stands between a dead pane's content and the
        live replacement.
        """
        agent = _pane("%1")
        old_shadow = _pane("%8", shadow_target="%1")
        new_shadow = _pane("%12", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%8": "old shadow", "%12": "new shadow"}
        mon = _make_monitor([agent], [old_shadow], content)
        await _full_refresh(mon)
        self.assertEqual(mon.get_shadow_snapshot("%1").pane.pane_id, "%8")

        # Discovery now reports the replacement shadow.
        mon.discover_panes_with_shadows_async = _discovery([agent], [new_shadow])
        gate = asyncio.Event()
        reserved = asyncio.Event()
        base_cap = mon.capture_pane_content_async

        async def gated_cap(pane_id, capture_lines=None, pane=None):
            reserved.set()          # the batch seq is already reserved by now
            await gate.wait()
            return await base_cap(pane_id, capture_lines=capture_lines, pane=pane)

        mon.capture_pane_content_async = gated_cap

        async def full_cycle():
            gen, classified = await mon.capture_all_classified_async()
            return mon.commit_snapshots(gen, classified)

        task = asyncio.create_task(full_cycle())
        await reserved.wait()

        # An in-flight refresh of the OLD pane reserves a LATER seq.
        stale_seq = mon._next_shadow_write_seq()

        gate.set()
        self.assertIsNotNone(await task)
        self.assertEqual(mon.get_shadow_snapshot("%1").pane.pane_id, "%12")
        self.assertGreater(stale_seq, mon._shadow_snapshot_seq["%1"])  # seq passes

        _, result = await _classify_for(mon, old_shadow, "old shadow")
        self.assertIsNone(
            mon._merge_shadow_snapshot("%1", "%8", stale_seq, old_shadow,
                                       "old shadow", result)
        )
        snap = mon.get_shadow_snapshot("%1")
        self.assertEqual(snap.pane.pane_id, "%12")
        self.assertEqual(snap.content, "new shadow")

    async def test_negative_control_same_pane_merge_lands(self):
        """Without a rebind the identical late merge IS accepted — proving the
        identity check, not the fixture, blocked the case above."""
        agent = _pane("%1")
        shadow = _pane("%8", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%8": "old shadow"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        seq = mon._next_shadow_write_seq()
        _, result = await _classify_for(mon, shadow, "fresher shadow")
        self.assertIsNotNone(
            mon._merge_shadow_snapshot("%1", "%8", seq, shadow,
                                       "fresher shadow", result)
        )
        self.assertEqual(mon.get_shadow_snapshot("%1").content, "fresher shadow")

    async def test_commit_prefers_discovery_identity_over_a_newer_read(self):
        """Commit-side half of the rebind race.

        A fast refresh of the OLD shadow can land with a seq NEWER than the full
        batch's. If the seq alone decided, the commit would keep that dead pane
        and discard the replacement discovery just found — leaving the map naming
        a shadow that is no longer bound. The seq only arbitrates recency between
        reads of the same pane; identity is discovery's call.
        """
        agent = _pane("%1")
        old_shadow = _pane("%8", shadow_target="%1")
        new_shadow = _pane("%12", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%8": "old shadow", "%12": "new shadow"}
        mon = _make_monitor([agent], [old_shadow], content)
        await _full_refresh(mon)

        # Batch reserves its seq and suspends mid-capture, having discovered %12.
        mon.discover_panes_with_shadows_async = _discovery([agent], [new_shadow])
        gate = asyncio.Event()
        reserved = asyncio.Event()
        base_cap = mon.capture_pane_content_async

        async def gated_cap(pane_id, capture_lines=None, pane=None):
            reserved.set()
            await gate.wait()
            return await base_cap(pane_id, capture_lines=capture_lines, pane=pane)

        mon.capture_pane_content_async = gated_cap

        async def full_cycle():
            gen, classified = await mon.capture_all_classified_async()
            return mon.commit_snapshots(gen, classified)

        task = asyncio.create_task(full_cycle())
        await reserved.wait()

        # A refresh of the OLD pane lands with a LATER seq than the batch.
        later_seq = mon._next_shadow_write_seq()
        _, result = await _classify_for(mon, old_shadow, "old shadow v2")
        self.assertIsNotNone(
            mon._merge_shadow_snapshot("%1", "%8", later_seq, old_shadow,
                                       "old shadow v2", result)
        )
        gate.set()
        self.assertIsNotNone(await task)

        snap = mon.get_shadow_snapshot("%1")
        self.assertEqual(snap.pane.pane_id, "%12", "discovery owns identity")
        self.assertEqual(snap.content, "new shadow")

    async def test_removed_shadow_is_never_resurrected(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        seq = mon._next_shadow_write_seq()
        mon.discover_panes_with_shadows_async = _discovery([agent], [])
        await _full_refresh(mon)
        self.assertIsNone(mon.get_shadow_snapshot("%1"))

        _, result = await _classify_for(mon, shadow, "shadow v1")
        self.assertIsNone(
            mon._merge_shadow_snapshot("%1", "%9", seq, shadow, "shadow v1", result)
        )
        self.assertIsNone(mon.get_shadow_snapshot("%1"))


class ShadowRefreshBookkeepingTests(unittest.IsolatedAsyncioTestCase):
    """Rule 4 — bookkeeping runs only after the merge is accepted."""

    async def test_rejected_merge_leaves_idle_bookkeeping_untouched(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        stale_seq = mon._next_shadow_write_seq()
        content["%9"] = "shadow v3"
        await _full_refresh(mon)

        snap_before = mon.get_shadow_snapshot("%1")
        last_content_before = mon._last_content["%9"]
        last_change_before = mon._last_change_time["%9"]

        # A rejected late merge carrying OLD content must write nothing at all:
        # `_apply_bookkeeping` is the sole writer of `_last_content` /
        # `_last_change_time`, so calling it before the guards would reset the
        # shadow's idle clock and make the NEXT full refresh see a change that
        # never happened.
        _, result = await _classify_for(mon, shadow, "shadow v1")
        self.assertIsNone(
            mon._merge_shadow_snapshot("%1", "%9", stale_seq, shadow,
                                       "shadow v1", result)
        )
        self.assertIs(mon.get_shadow_snapshot("%1"), snap_before)
        self.assertEqual(mon._last_content["%9"], last_content_before)
        self.assertEqual(mon._last_change_time["%9"], last_change_before)

    async def test_next_full_refresh_sees_no_phantom_change_after_a_lost_batch(self):
        """End-to-end consequence of the bug above, at the surface that matters.

        If a losing batch rewrote `_last_content` with its older content, the
        FOLLOWING full refresh would compare the unchanged pane against stale
        bookkeeping, decide it changed, and reset the shadow's idle clock.
        """
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        gen, classified = await mon.capture_all_classified_async()   # reads v1
        content["%9"] = "shadow v2"
        await mon.refresh_shadow_snapshot("%1")                      # reads v2
        mon.commit_snapshots(gen, classified)                        # loses

        settled = mon._last_change_time["%9"]
        await _full_refresh(mon)  # pane still shows v2 — nothing actually changed
        self.assertEqual(
            mon._last_change_time["%9"], settled,
            "an unchanged shadow pane must not have its idle clock reset",
        )

    async def test_negative_control_accepted_merge_does_update_bookkeeping(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)
        before = mon._last_content["%9"]

        content["%9"] = "shadow v2"
        self.assertIsNotNone(await mon.refresh_shadow_snapshot("%1"))
        self.assertNotEqual(mon._last_content["%9"], before)


class ShadowRefreshFailurePolicyTests(unittest.IsolatedAsyncioTestCase):
    """Rule 5 — a fast-refresh failure is "no update", never a hide."""

    async def test_capture_failure_retains_the_previous_snapshot(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)
        snap_before = mon.get_shadow_snapshot("%1")
        last_change_before = mon._last_change_time["%9"]

        mon.capture_pane_content_async = _failing_capture
        self.assertIsNone(await mon.refresh_shadow_snapshot("%1"))

        self.assertIs(mon.get_shadow_snapshot("%1"), snap_before)
        self.assertEqual(mon._last_change_time["%9"], last_change_before)

    async def test_full_refresh_still_removes_a_gone_shadow(self):
        """The retain above is bounded: deletion authority stays with the full
        refresh, so a shadow that really went away still disappears."""
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)

        mon.capture_pane_content_async = _failing_capture
        await mon.refresh_shadow_snapshot("%1")
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))  # retained

        mon = _make_monitor([agent], [shadow], content)
        await _full_refresh(mon)
        mon.discover_panes_with_shadows_async = _discovery([agent], [])
        await _full_refresh(mon)
        self.assertIsNone(mon.get_shadow_snapshot("%1"))     # but not forever


class ShadowStateInvariantTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_capture_all_clears_snapshots_and_their_seqs_together(self):
        """`_shadow_snapshots` and `_shadow_snapshot_seq` are two halves of one
        value; leaving a seq behind for a cleared snapshot would let a stale seq
        veto a later legitimate write."""
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow], {"%1": _ACTIVE_CONTENT, "%9": "shadow v1"}
        )
        await _full_refresh(mon)
        self.assertTrue(mon._shadow_snapshot_seq)

        mon._clear_shadow_snapshots()
        self.assertEqual(mon._shadow_snapshots, {})
        self.assertEqual(mon._shadow_snapshot_seq, {})


async def _failing_capture(pane_id, capture_lines=None, pane=None):
    return None


def _discovery(panes, shadows):
    async def _coro(*, enum_sink=None):
        if enum_sink is not None:
            enum_sink.append(frozenset(
                p.session_name for p in list(panes) + list(shadows)
                if p.session_name))
        return list(panes), list(shadows)
    return _coro


async def _classify_for(mon, pane, content):
    """Produce a ClassifyResult the way `refresh_shadow_snapshot` would."""
    from monitor.monitor_core import _classify_one

    mode = mon.get_compare_mode(pane.pane_id)
    result = await mon._run_offloaded(
        lambda: _classify_one(content, mode, mon.prompt_patterns, pane.category)
    )
    return pane, result


if __name__ == "__main__":
    unittest.main()

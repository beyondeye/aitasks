"""Live-terminal harness for minimonitor's bottom-of-list scroll pin (t1653).

Runs INSIDE a tmux pane, under a real pty, so a real SGR mouse gesture reaches
the real `MiniPaneList` and its real scrollbar. It exists because the headless
suite provably cannot reproduce the bug: `App.run_test` settles layout
synchronously, so `_restore_list_scroll` always ran at `attempt=0` against final
geometry and produced ZERO shortfall at N = 6/12/24/48/96 cards.

WHAT IS AND IS NOT EXERCISED. The harness subclasses `_RefreshHost` from
`tests/test_minimonitor_scroll_preservation.py` — the real `MiniMonitorApp` with
only its tmux-facing collaborators stubbed — and drives the real `_refresh_data()`
on its own interval. `minimonitor_app.main()`'s tmux detection and config load are
therefore NOT exercised; `MiniPaneList`, `_capture_list_scroll`,
`_rebuild_pane_list` and `_restore_list_scroll` all are, in a real terminal, with
real mouse input. That is the boundary this fixture claims and no more.

Instrumentation lives HERE, not in production code: the app writes no traces of
its own, so nothing about this measurement changes what ships.

Two artifacts, both under `--out-dir`:

* ``geometry.json`` — written ONCE, as soon as the list has laid out and
  overflows. Screen-absolute coordinates come from the compositor
  (`app.screen.find_widget(bar).region`), never from a guess, because a
  hard-coded SGR coordinate that misses the thumb produces a silent no-op drag
  that BOTH the legacy and the anchored run would "pass".
* ``trace.jsonl`` — one `{"tick", ...}` line per refresh tick, plus a
  `{"event": "grab"}` line the moment the scrollbar thumb is actually grabbed
  and `{"event": "release"}` when it is let go. The grab line is what lets the
  test tell "the pin held" apart from "the gesture never landed".

``AIT_T1653_LEGACY_PIN=1`` restores the PRE-FIX bottom-pin behaviour (an
`at_bottom` snapshot applied once after the rebuild via
`scroll_end(immediate=True, force=True)`) so the fixture can be shown to
reproduce the drift before it is trusted to show the fix. The replica is
test-local and used only as a negative control, so it cannot produce a false
PASS of the real path.

Usage (the test drives this; see tests/test_minimonitor_bottom_pin_live.py):

    python3 tests/lib/minimonitor_live_harness.py --out-dir DIR [--agents N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Importing the module scrubs TMUX/TMUX_PANE, which is what makes the real
# `on_mount` take its "Not inside tmux" early return — no window rename, no
# refresh timer of its own. This harness owns the tick cadence instead.
import test_minimonitor_scroll_preservation as sp  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402

#: Refresh cadence. Far faster than the production 3s default so a ~30s pane
#: run collects the 10+ post-drag ticks the acceptance criteria ask for.
TICK_SECONDS = 0.5

#: Card-height churn. `_agent_card_text` output is remounted every tick, and a
#: `height: auto` card grows with it, so cycling the line count reproduces the
#: task/gate/concern rows coming and going that made `max_scroll_y` swing
#: 67 -> 73 -> 88 WITHIN a tick in the original trace.
#:
#: The MINIMUM is 1, not 0, and that is load-bearing. With the task/gate caches
#: stubbed, `_agent_card_text` renders a SINGLE row per card, so a 40x40 pane
#: (container 30 rows) needed >30 agents just to overflow at all — measured:
#: 30 cards gave virtual_h == container_h == 30 and max_scroll_y == 0, i.e. a
#: silently vacuous fixture. Two rows per card is also what production looks
#: like once a card carries a task title.
_CHURN_EXTRA_LINES = (1, 2, 1, 3)

#: Period of the OUT-OF-BAND content churn (see `_async_content_churn`).
#: Deliberately not a divisor of TICK_SECONDS so the mutation lands at varying
#: phases of the refresh cycle rather than always at the same settled moment.
ASYNC_CHURN_SECONDS = 0.17


class LiveHarnessApp(sp._RefreshHost):
    """`_RefreshHost` plus tracing, a self-driven tick, and card-height churn."""

    def __init__(self, out_dir: Path, agents: int, legacy: bool) -> None:
        super().__init__([f"%{i}" for i in range(agents)])
        self._out_dir = out_dir
        self._legacy = legacy
        self._tick = 0
        self._geometry_written = False
        self._grabbed_seen = False
        self._geometry_deferred_reason: str | None = None
        self._async_phase = 0
        self._base_text: dict[str, str] = {}
        self._trace_path = out_dir / "trace.jsonl"

    # -- tracing ------------------------------------------------------------

    def _emit(self, record: dict) -> None:
        with self._trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _list(self) -> mm.MiniPaneList:
        return self.query_one("#mini-pane-list", mm.MiniPaneList)

    def _maybe_write_geometry(self, container: mm.MiniPaneList) -> None:
        """Publish the gesture's target once the list has SETTLED and overflows.

        REWRITTEN EVERY TICK, not once. The content churns, so a snapshot taken
        at boot describes a thumb that has since moved and resized; a test aiming
        from it can press the trough instead of the thumb, and the run then looks
        like a lost pin rather than a lost gesture. (Measured: a 1-in-8 failure
        whose signature was `scroll_y == 0` on every tick — the drag never
        happened at all.) The `geometry` EVENT is still emitted only once, so
        "when did it first overflow" stays answerable.

        Deferred until `max_scroll_y > 0` on purpose: before that there is no
        scrollbar to aim at, and a geometry file naming a thumb that does not
        exist is worse than none — the test would compute coordinates, send a
        press into empty space, and see a run that merely looks uneventful.

        Every path that cannot answer says WHY, once, into the trace. A silent
        retry loop here is indistinguishable from "the list never overflowed",
        which is exactly the diagnosis the test needs.
        """
        reason = None
        if container.max_scroll_y <= 0:
            reason = f"max_scroll_y={container.max_scroll_y}"
        bar = container.vertical_scrollbar
        if reason is None:
            try:
                bar_region = tuple(self.screen.find_widget(bar).region)
                list_region = tuple(self.screen.find_widget(container).region)
            except Exception as exc:      # not composited yet
                reason = f"find_widget: {type(exc).__name__}: {exc}"
        if reason is None:
            window_size = bar.window_size or 0
            virtual = bar.window_virtual_size or 0
            if not window_size or virtual <= window_size:
                reason = f"scrollbar not sized: window={window_size} virtual={virtual}"
        if reason is not None:
            if not self._geometry_written and reason != self._geometry_deferred_reason:
                self._geometry_deferred_reason = reason
                self._emit({"event": "geometry_deferred", "tick": self._tick,
                            "reason": reason})
            return
        thumb_size = max(1, int(window_size * window_size / virtual))
        thumb_top = int(bar.position * window_size / virtual)
        # Written ATOMICALLY: this file is now rewritten every tick while the
        # test reads it, so a plain write_text can hand the reader a truncated
        # document.
        payload = json.dumps({
            "list_region": list(list_region),
            "scrollbar_region": list(bar_region),
            "thumb_top": thumb_top,
            "thumb_size": thumb_size,
            "window_size": window_size,
            "window_virtual_size": virtual,
            "max_scroll_y": container.max_scroll_y,
            "agents": len(self._pane_ids),
            "legacy": self._legacy,
            # Diagnostics for the one failure mode that makes every coordinate
            # in this fixture wrong: the app not seeing the pane's real size.
            # Textual falls back to 80x24 when it cannot query the terminal, and
            # that reads exactly like "the pane is 80 wide".
            "app_size": [int(self.size.width), int(self.size.height)],
            "stdout_isatty": sys.stdout.isatty(),
            "term": os.environ.get("TERM", ""),
            "columns_env": os.environ.get("COLUMNS", ""),
        }, indent=2)
        tmp = self._out_dir / "geometry.json.tmp"
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, self._out_dir / "geometry.json")
        if not self._geometry_written:
            self._geometry_written = True
            self._emit({"event": "geometry", "tick": self._tick})

    # -- card-height churn ---------------------------------------------------

    def _agent_card_text(self, snap) -> str:
        base = super()._agent_card_text(snap)
        extra = _CHURN_EXTRA_LINES[self._tick % len(_CHURN_EXTRA_LINES)]
        text = base + "".join(f"\n  churn {i}" for i in range(extra))
        # Recorded here rather than read back off the widget: `MiniPaneCard` is a
        # `Static`, which exposes no public accessor for the text it was built
        # with in Textual 8.2.7 (`.renderable` does not exist), and
        # `_async_content_churn` needs a stable base to grow from.
        self._base_text[snap.pane.pane_id] = text
        return text

    # -- the pre-fix replica (negative control only) -------------------------

    def _capture_list_scroll(self) -> None:
        if not self._legacy:
            return super()._capture_list_scroll()
        # PRE-FIX: a geometry snapshot taken before the rebuild.
        if self._pending_scroll_state is not None:
            return
        try:
            container = self._list()
        except Exception:
            return
        cards = [c for c in container.query(mm.MiniPaneCard)
                 if hasattr(c, "pane_id")]
        if not cards:
            return
        max_y = container.max_scroll_y
        scroll_y = container.scroll_y
        at_bottom = max_y <= 0 or scroll_y >= max_y - 1
        anchor = mm.pick_scroll_anchor(
            [(c.pane_id, c.virtual_region.y) for c in cards], scroll_y)
        if anchor is None:
            return
        anchor_id, delta = anchor
        self._pending_scroll_state = (
            at_bottom, anchor_id, delta, [c.pane_id for c in cards])

    def _restore_list_scroll(self, gen: int, attempt: int = 0) -> None:
        if not self._legacy:
            return super()._restore_list_scroll(gen, attempt)
        # PRE-FIX: apply the snapshot ONCE, with scroll_end(immediate=True).
        if gen != self._scroll_restore_gen:
            return
        state = self._pending_scroll_state
        if state is None:
            return
        try:
            container = self._list()
        except Exception:
            self._abandon_scroll_restore(gen)
            return
        at_bottom, anchor_id, delta, order = state
        live = {c.pane_id: c.virtual_region.y
                for c in container.query(mm.MiniPaneCard)
                if hasattr(c, "pane_id")}
        target = None
        if not at_bottom:
            top = mm.resolve_anchor_target(order, anchor_id, live)
            if top is not None:
                target = top + delta
        try:
            if at_bottom:
                container.scroll_end(animate=False, immediate=True, force=True)
            elif target is not None:
                container.scroll_to(y=target, animate=False, immediate=True,
                                    force=True)
            else:
                container.scroll_to(y=container.max_scroll_y, animate=False,
                                    immediate=True, force=True)
        finally:
            self._pending_scroll_state = None
            self._stop_scroll_lock_timer()
            self.call_after_refresh(self._release_list_scroll_lock, gen)

    # -- lifecycle -----------------------------------------------------------

    def _async_content_churn(self) -> None:
        """Grow/shrink a MOUNTED card OUT OF BAND with the refresh tick.

        This is the axis the rebuild-synchronised churn above cannot model, and
        the one the reported trace shows: `max_scroll_y` was 88 at CAPTURE and 67
        at the restore a tenth of a second later. In production a card's row
        count changes between refreshes — a gate phase row, a concern row or a
        mark glyph arriving from `_refresh_own_live_state` / `_refresh_marks` /
        the gate cache — so the content height moves while NO rebuild and NO
        restore is running, and `validate_scroll_y` clamps `scroll_y` down on
        every shrink with nothing to put it back on the regrow.

        Driven on its own interval, deliberately NOT a divisor of TICK_SECONDS,
        so the mutation lands at varying phases of the refresh cycle instead of
        always at the same settled moment.
        """
        cards = [c for c in self.query("#mini-pane-list MiniPaneCard")
                 if hasattr(c, "pane_id")]
        if not cards:
            return
        self._async_phase += 1
        extra = self._async_phase % 3
        for card in cards[: max(1, len(cards) // 3)]:
            base = self._base_text.get(card.pane_id)
            if base is None:
                continue
            card.update(base + "".join(f"\n  async {i}" for i in range(extra)))

    def on_ready(self) -> None:
        # `on_mount` takes the real app's "Not inside tmux" early return (TMUX is
        # scrubbed at import), so no production timer competes with this one.
        self.set_interval(TICK_SECONDS, self._harness_tick)
        self.set_interval(ASYNC_CHURN_SECONDS, self._async_content_churn)

    async def _harness_tick(self) -> None:
        """Sample the SETTLED state, then drive the next refresh.

        Order matters and is the whole reason this is one method. Sampling
        immediately after `await self._refresh_data()` measures the wrong
        instant: that call returns once `_rebuild_pane_list` has mounted, with
        `call_after_refresh(self._restore_list_scroll, ...)` still queued and the
        layout not yet settled, so `max_scroll_y` reads 0 and every
        `max_scroll_y - scroll_y` assertion built on it would be meaningless.
        Measured while building this fixture: geometry never published at all,
        because that read always landed mid-rebuild.

        So each tick reports the state left by the PREVIOUS tick, a full
        TICK_SECONDS later, and only then starts the next one.
        """
        try:
            container = self._list()
        except Exception:
            container = None

        if container is not None and self._legacy:
            # The negative control must undo BOTH halves of the fix, not just the
            # app's capture/restore. `MiniPaneList.on_mount` now calls `anchor()`,
            # and while `_anchored` is true the compositor re-pins the offset in
            # the arrange pass no matter what `_restore_list_scroll` does — a
            # legacy replica that leaves it set measures the FIX, reports
            # `max_scroll_y - scroll_y == 0`, and silently makes the whole
            # comparison vacuous. (Observed while building this fixture.)
            # Clearing `_anchored` is the exact inverse of that one call: pre-fix
            # `MiniPaneList` never armed an anchor at all.
            container._anchored = False

        if container is not None:
            self._maybe_write_geometry(container)

            grabbed = container.is_vertical_scrollbar_grabbed
            if grabbed and not self._grabbed_seen:
                self._grabbed_seen = True
                self._emit({"event": "grab", "tick": self._tick})
            elif not grabbed and self._grabbed_seen:
                self._grabbed_seen = False
                self._emit({"event": "release", "tick": self._tick})

            self._emit({
                "tick": self._tick,
                "scroll_y": float(container.scroll_y),
                "max_scroll_y": int(container.max_scroll_y),
                # Carried so a non-overflowing fixture reports WHY rather than
                # just failing an assertion on max_scroll_y.
                "cards": len(list(container.query(mm.MiniPaneCard))),
                "container_h": int(container.container_size.height),
                "virtual_h": int(container.virtual_size.height),
                "is_anchored": bool(container.is_anchored),
                "anchor_released": bool(getattr(container, "_anchor_released", None)),
            })

        self._tick += 1
        # Agents come and go without any user gesture — AC2.
        if self._tick % 7 == 0 and len(self._pane_ids) > 20:
            self.set_panes(self._pane_ids[:-1])
        await self._refresh_data()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--agents", type=int, default=40)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    legacy = os.environ.get("AIT_T1653_LEGACY_PIN") == "1"
    LiveHarnessApp(out_dir, args.agents, legacy).run()


if __name__ == "__main__":
    main()

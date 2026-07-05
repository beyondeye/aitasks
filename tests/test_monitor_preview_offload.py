"""Tests for the monitor preview-render UI-thread offload (t1111_5).

The single ``_ansi_to_rich_text`` render of the focused pane used to run on the
Textual event loop inside ``_update_content_preview``; for ANSI-heavy active-agent
output that render is the focus-switch lag. This task offloads the pure render via
the ``_run_offloaded`` seam (t1111_4) and applies ``preview.update`` + scroll
restore back on the loop, guarded by an app-owned ``_preview_render_gen`` token and
a focus-identity check so a late / superseded render (and its deferred scroll
restore) never overwrites the current preview.

All ordering is driven deterministically through the injectable ``_run_offloaded``
seam and gated ``asyncio.Event``s — no sleep-based timing (per
``aidocs/framework/testing_conventions.md``).
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from rich.text import Text  # noqa: E402

from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)
from monitor.monitor_shared import _ansi_to_rich_text  # noqa: E402


def _pane(pane_id: str, window_name: str = "agent-1") -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=80, height=24, category=PaneCategory.AGENT, session_name="demo",
    )


def _snap(pane_id: str, content: str) -> PaneSnapshot:
    return PaneSnapshot(pane=_pane(pane_id), content=content, timestamp=0.0,
                        idle_seconds=0.0, is_idle=False)


async def _sync_offloaded(fn):
    """Run the offloaded fn synchronously (deterministic seam override)."""
    return fn()


def _gate():
    """Return (offload_fn, release_event, calls) where the FIRST offload call
    blocks on the event and later calls run immediately."""
    release = asyncio.Event()
    calls = {"n": 0}

    async def offload(fn):
        calls["n"] += 1
        if calls["n"] == 1:
            await release.wait()
        return fn()

    return offload, release, calls


class _FakeMon:
    """Minimal stand-in exposing only the ``_run_offloaded`` seam that
    ``_apply_preview_render`` reaches through."""

    multi_session = False

    def __init__(self, offload):
        self._run_offloaded = offload


class AnsiBuilderTests(unittest.TestCase):
    """(a) The pure render is offloadable as-is: stable plain text, no crash."""

    def test_plain_text_and_heavy_ansi(self):
        t = _ansi_to_rich_text("\x1b[31mhello\x1b[0m\nworld")
        self.assertIsInstance(t, Text)
        self.assertEqual(t.plain, "hello\nworld")

        # ANSI-heavy multi-line content parses to stable plain text.
        heavy = "\n".join(f"\x1b[3{i % 8}mline{i}\x1b[0m" for i in range(50))
        t2 = _ansi_to_rich_text(heavy)
        self.assertEqual(t2.plain, "\n".join(f"line{i}" for i in range(50)))


class PreviewOffloadTests(unittest.IsolatedAsyncioTestCase):

    async def test_render_equivalence(self):
        """(b) The offloaded apply produces the same Text the synchronous path
        did — same plain content flowing through preview.update."""
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)):
            app._monitor = _FakeMon(_sync_offloaded)
            # Neutralize the mount-time _restore_focus → _update_content_preview
            # callback so it can't append incidental placeholder updates while we
            # drive _apply_preview_render directly.
            app._update_content_preview = lambda: None  # type: ignore[assignment]
            app._focused_pane_id = "%1"
            preview = app.query_one("#content-preview")
            updates: list = []
            preview.update = lambda r: updates.append(r)  # type: ignore[assignment]

            joined = "\x1b[32malpha\x1b[0m\nrun\x1b[31mX\x1b[0m"
            app._preview_render_gen += 1
            gen = app._preview_render_gen
            await app._apply_preview_render(
                "%1", joined, gen, None, joined.split("\n")
            )

            self.assertTrue(updates)
            self.assertIsInstance(updates[-1], Text)
            self.assertEqual(updates[-1].plain, _ansi_to_rich_text(joined).plain)

    async def test_stale_render_discarded_with_negative_control(self):
        """(c) Two renders for the same focused pane resolve out of order: the
        older (superseded) one is refused by the generation guard. Negative
        control (unguarded apply) reproduces the stale clobber."""
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)):
            offload, release, calls = _gate()
            app._monitor = _FakeMon(offload)
            # Neutralize the mount-time _restore_focus → _update_content_preview
            # callback so it can't append incidental placeholder updates while we
            # drive _apply_preview_render directly.
            app._update_content_preview = lambda: None  # type: ignore[assignment]
            app._focused_pane_id = "%1"
            preview = app.query_one("#content-preview")
            updates: list = []
            preview.update = lambda r: updates.append(r)  # type: ignore[assignment]

            joined_a, joined_b = "AAA-old", "BBB-new"
            app._preview_render_gen += 1
            gen_a = app._preview_render_gen  # render A blocks in offload
            task_a = asyncio.create_task(
                app._apply_preview_render("%1", joined_a, gen_a, None, [joined_a])
            )
            while calls["n"] == 0:
                await asyncio.sleep(0)

            # Newer render B (same pane) reserves a higher gen and commits.
            app._preview_render_gen += 1
            gen_b = app._preview_render_gen
            await app._apply_preview_render("%1", joined_b, gen_b, None, [joined_b])
            self.assertEqual(updates[-1].plain, "BBB-new")

            # A resolves late → generation guard refuses it (no clobber).
            release.set()
            await task_a
            self.assertEqual(updates[-1].plain, "BBB-new")

            # Negative control: applying A's render WITHOUT the guard clobbers B.
            preview.update(_ansi_to_rich_text(joined_a))
            self.assertEqual(updates[-1].plain, "AAA-old")

    async def test_focus_moved_during_offload_no_write(self):
        """(e) Focus moves A→B during the render await → A's apply does not touch
        the preview (focus-identity guard), even though its generation is still
        current."""
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)):
            offload, release, calls = _gate()
            app._monitor = _FakeMon(offload)
            # Neutralize the mount-time _restore_focus → _update_content_preview
            # callback so it can't append incidental placeholder updates while we
            # drive _apply_preview_render directly.
            app._update_content_preview = lambda: None  # type: ignore[assignment]
            app._focused_pane_id = "%1"
            preview = app.query_one("#content-preview")
            updates: list = []
            preview.update = lambda r: updates.append(r)  # type: ignore[assignment]

            app._preview_render_gen += 1
            gen = app._preview_render_gen
            task = asyncio.create_task(
                app._apply_preview_render("%1", "content-A", gen, None, ["content-A"])
            )
            while calls["n"] == 0:
                await asyncio.sleep(0)

            # Focus moves away during the offload (generation unchanged).
            app._focused_pane_id = "%2"
            release.set()
            await task

            self.assertEqual(updates, [])

    async def test_deferred_scroll_restore_is_guarded(self):
        """(f) A deferred call_after_refresh scroll restore re-checks the guard at
        EXECUTION time: if the render was superseded before the callback fires, it
        does not scroll the (shared) container. Negative control: an unguarded
        deferred restore fires regardless."""
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)) as pilot:
            app._monitor = _FakeMon(_sync_offloaded)
            # Neutralize the mount-time _restore_focus → _update_content_preview
            # callback so it can't append incidental placeholder updates while we
            # drive _apply_preview_render directly.
            app._update_content_preview = lambda: None  # type: ignore[assignment]
            app._focused_pane_id = "%1"
            preview = app.query_one("#content-preview")
            preview.update = lambda r: None  # type: ignore[assignment]
            scroll = app.query_one("#preview-scroll")
            scroll_calls: list = []
            scroll.scroll_end = lambda animate=False: scroll_calls.append("end")  # type: ignore[assignment]

            app._preview_render_gen += 1
            gen = app._preview_render_gen
            # saved=None → tail-follow → schedules a guarded scroll_end.
            await app._apply_preview_render(
                "%1", "line1\nline2", gen, None, ["line1", "line2"]
            )

            # Supersede the render BEFORE the deferred callback runs.
            app._preview_render_gen += 1
            await pilot.pause()
            self.assertEqual(scroll_calls, [])  # guarded → suppressed

            # Negative control: an UNguarded deferred restore fires even now.
            app.call_after_refresh(lambda: scroll.scroll_end(animate=False))
            await pilot.pause()
            self.assertEqual(scroll_calls, ["end"])

    async def test_no_offload_on_short_circuit_branches(self):
        """(d) The frozen/paused, no-focus, and empty-content branches never
        schedule a render worker (no thread hop when nothing renders)."""
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)):
            scheduled: list = []

            def spy_run_worker(coro, **kw):
                scheduled.append(coro)
                coro.close()
                return None

            app.run_worker = spy_run_worker  # type: ignore[assignment]

            # No focus → header-only path, returns before scheduling.
            app._focused_pane_id = None
            app._update_content_preview()

            # Empty content → empty branch, no render.
            app._snapshots = {"%1": _snap("%1", "")}
            app._focused_pane_id = "%1"
            app._update_content_preview()

            # Frozen: same pane + paused (saved is (False, anchor)).
            app._snapshots = {"%1": _snap("%1", "some content\nhere")}
            app._focused_pane_id = "%1"
            app._last_preview_pane_id = "%1"
            app._preview_scroll_state["%1"] = (False, "anchor")
            app._update_content_preview()

            self.assertEqual(scheduled, [])

    async def test_scheduling_path_via_real_entrypoint(self):
        """(g) The production sync entry point schedules exactly one render worker
        for active non-empty content, hands the render off through it, shows the
        cross-pane placeholder on an actual switch, and skips the placeholder on a
        same-pane re-render."""
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)):
            app._monitor = _FakeMon(_sync_offloaded)
            scheduled: list = []

            def spy_run_worker(coro, **kw):
                scheduled.append(coro)
                return None

            app.run_worker = spy_run_worker  # type: ignore[assignment]
            preview = app.query_one("#content-preview")
            updates: list = []
            preview.update = lambda r: updates.append(r)  # type: ignore[assignment]

            app._snapshots = {"%1": _snap("%1", "hello\nworld")}
            app._focused_pane_id = "%1"
            app._last_preview_pane_id = None  # NOT same pane → a real switch

            app._update_content_preview()

            # Exactly one worker scheduled for the active render.
            self.assertEqual(len(scheduled), 1)
            # Cross-pane switch shows the synchronous placeholder immediately.
            self.assertEqual([u for u in updates if isinstance(u, str) and "…" in u],
                             ["[dim]…[/]"])
            # Driving the scheduled worker applies the real rendered Text.
            await scheduled[0]
            self.assertIsInstance(updates[-1], Text)
            self.assertEqual(updates[-1].plain, "hello\nworld")

            # Same-pane re-render (e.g. 0.3s fast-preview tick): still schedules a
            # render, but emits NO placeholder (avoids flicker).
            scheduled.clear()
            updates.clear()
            app._last_preview_pane_id = "%1"  # same pane, not paused → not frozen
            app._update_content_preview()
            self.assertEqual(len(scheduled), 1)
            self.assertEqual([u for u in updates if isinstance(u, str) and "…" in u], [])
            await scheduled[0]
            self.assertEqual(updates[-1].plain, "hello\nworld")


class NonRenderBranchInvalidationTests(unittest.IsolatedAsyncioTestCase):
    """A render scheduled for pane A must NOT apply after a later
    _update_content_preview() re-entry takes a non-render branch (empty,
    no-focus/missing-snapshot, or frozen/paused) for the SAME focused pane — the
    branch bumps the render token up front, so the stale in-flight render is
    discarded rather than overwriting the (empty)/prompt/frozen view."""

    async def _branch_scenario(self, trigger, *, neg_control: bool = False) -> list:
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)) as pilot:
            # Drain mount-time callbacks (which may fire the real
            # _update_content_preview and bump the render token) so the token
            # values we set below are not perturbed mid-scenario.
            await pilot.pause()
            offload, release, calls = _gate()
            app._monitor = _FakeMon(offload)
            captured: list = []
            app.run_worker = lambda coro, **kw: captured.append(coro) or None  # type: ignore[assignment]
            preview = app.query_one("#content-preview")
            updates: list = []
            preview.update = lambda r: updates.append(r)  # type: ignore[assignment]

            # Schedule a render for pane A (cross-pane) that blocks in the offload.
            app._snapshots = {"%1": _snap("%1", "content-A\nrun")}
            app._focused_pane_id = "%1"
            app._last_preview_pane_id = None
            app._update_content_preview()
            self.assertEqual(len(captured), 1)
            render_gen = app._preview_render_gen
            task = asyncio.create_task(captured[0])
            while calls["n"] == 0:
                await asyncio.sleep(0)

            # Run a non-render branch. With the fix it bumps the render token up
            # front, invalidating the in-flight render.
            trigger(app)
            if neg_control:
                # Simulate the branch NOT invalidating: restore the render's gen so
                # its post-await guard passes and it clobbers the branch's UI.
                app._preview_render_gen = render_gen

            release.set()
            await task
            return updates

    async def test_empty_branch_discards_inflight_render(self):
        def trigger(app):
            app._snapshots = {"%1": _snap("%1", "")}
            app._update_content_preview()  # empty branch

        updates = await self._branch_scenario(trigger)
        self.assertFalse(any(isinstance(u, Text) for u in updates))
        self.assertEqual(updates[-1], "[dim](empty)[/]")

        # Negative control: without the up-front token bump the stale render for A
        # overwrites the (empty) view.
        nc = await self._branch_scenario(trigger, neg_control=True)
        self.assertTrue(any(isinstance(u, Text) and u.plain == "content-A\nrun"
                            for u in nc))

    async def test_no_focus_branch_discards_inflight_render(self):
        # Focus stays on %1 but its snapshot disappears → no-focus/missing-snapshot
        # branch. The render's focus-identity guard still matches (focus unchanged),
        # so ONLY the token bump can discard it.
        def trigger(app):
            app._snapshots = {}
            app._update_content_preview()

        updates = await self._branch_scenario(trigger)
        self.assertFalse(any(isinstance(u, Text) for u in updates))
        self.assertEqual(updates[-1],
                         "[dim]Focus an agent or pane to see its output[/]")

    async def test_frozen_branch_discards_inflight_render(self):
        # Same pane, paused → frozen branch preserves the current view; the stale
        # render must not land (and must not schedule scroll restore).
        def trigger(app):
            app._preview_scroll_state["%1"] = (False, "anchor")  # is_paused
            app._update_content_preview()

        updates = await self._branch_scenario(trigger)
        self.assertFalse(any(isinstance(u, Text) for u in updates))


if __name__ == "__main__":
    unittest.main()

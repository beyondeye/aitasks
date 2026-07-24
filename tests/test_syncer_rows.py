#!/usr/bin/env python3
"""Tests for the syncer TUI's pure multi-repo model helpers (t1138).

Covers the row model, action gating, LRU fetch scheduling, age formatting,
fetch-stamp invariants (negative controls), refresh-request coalescing, action
preflight, and discovery fallback — all without a running Textual app.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import unittest
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "syncer"))

from textual.widgets import (  # noqa: E402
    DataTable,
    Footer,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)

from agent_launch_utils import AitasksSession  # noqa: E402
import syncer_app  # noqa: E402
from syncer_app import (  # noqa: E402
    PENDING_UNSET,
    ActionTarget,
    RowSpec,
    action_allowed_for_ref,
    build_labels,
    build_rows,
    coalesce_request,
    discover_syncer_sessions,
    format_age,
    least_recent_fetch_key,
    resolve_action_target,
    should_stamp_fetch,
    single_repo_rows,
)


def sess(root: str, name: str | None = None, **kwargs) -> AitasksSession:
    path = Path(root)
    return AitasksSession(
        session="", project_root=path, project_name=name or path.name, **kwargs
    )


class BuildRowsTests(unittest.TestCase):
    def test_two_refs_per_repo_in_session_order(self):
        sessions = [sess("/tmp/alpha"), sess("/tmp/beta")]
        rows = build_rows(sessions, build_labels(sessions))
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            [(r.session_key, r.ref_name) for r in rows],
            [
                (sessions[0].key, "main"),
                (sessions[0].key, "aitask-data"),
                (sessions[1].key, "main"),
                (sessions[1].key, "aitask-data"),
            ],
        )
        self.assertEqual([r.project_label for r in rows[:2]], ["alpha", "alpha"])

    def test_row_keys_are_opaque_and_path_independent(self):
        # A project_root containing the old '::' delimiter (or any path text)
        # must not affect row-key validity — keys are positional ids and the
        # mapping back to (session_key, ref) goes through the RowSpec map.
        weird = sess("/tmp/we::ird")
        sessions = [sess("/tmp/alpha"), weird]
        rows = build_rows(sessions, build_labels(sessions))
        self.assertEqual([r.row_key for r in rows], ["r0", "r1", "r2", "r3"])
        for r in rows:
            self.assertNotIn("/", r.row_key)
            self.assertNotIn("::", r.row_key)
        rows_by_key = {r.row_key: r for r in rows}
        self.assertEqual(rows_by_key["r2"].session_key, weird.key)
        self.assertEqual(rows_by_key["r3"].ref_name, "aitask-data")

    def test_colliding_project_names_get_disambiguated_labels(self):
        sessions = [sess("/tmp/a/repo"), sess("/tmp/b/repo")]
        rows = build_rows(sessions, build_labels(sessions))
        labels = {r.project_label for r in rows}
        self.assertEqual(len(labels), 2, f"labels not unique: {labels}")

    def test_single_repo_rows_keep_legacy_keys(self):
        rows = single_repo_rows()
        self.assertEqual(
            [(r.row_key, r.session_key, r.ref_name, r.project_label) for r in rows],
            [("main", "", "main", ""), ("aitask-data", "", "aitask-data", "")],
        )


class ActionGatingTests(unittest.TestCase):
    def test_full_matrix(self):
        self.assertTrue(action_allowed_for_ref("sync_data", "aitask-data"))
        self.assertFalse(action_allowed_for_ref("sync_data", "main"))
        self.assertTrue(action_allowed_for_ref("pull", "main"))
        self.assertFalse(action_allowed_for_ref("pull", "aitask-data"))
        self.assertTrue(action_allowed_for_ref("push", "main"))
        self.assertFalse(action_allowed_for_ref("push", "aitask-data"))
        # Non-row-scoped actions are always allowed.
        self.assertTrue(action_allowed_for_ref("refresh", "main"))
        self.assertTrue(action_allowed_for_ref("toggle_fetch", "aitask-data"))


class LeastRecentFetchKeyTests(unittest.TestCase):
    def setUp(self):
        self.a = sess("/tmp/a")
        self.b = sess("/tmp/b")
        self.c = sess("/tmp/c")
        self.sessions = [self.a, self.b, self.c]

    def test_empty_sessions_returns_none(self):
        self.assertIsNone(least_recent_fetch_key([], {}))

    def test_never_fetched_wins_in_session_order(self):
        stamps = {self.a.key: 100.0}
        self.assertEqual(least_recent_fetch_key(self.sessions, stamps), self.b.key)

    def test_oldest_stamp_wins(self):
        stamps = {self.a.key: 300.0, self.b.key: 100.0, self.c.key: 200.0}
        self.assertEqual(least_recent_fetch_key(self.sessions, stamps), self.b.key)

    def test_tie_breaks_by_session_order(self):
        stamps = {self.a.key: 100.0, self.b.key: 100.0, self.c.key: 100.0}
        self.assertEqual(least_recent_fetch_key(self.sessions, stamps), self.a.key)

    def test_single_session(self):
        stamps = {self.a.key: 100.0}
        self.assertEqual(least_recent_fetch_key([self.a], stamps), self.a.key)

    def test_manual_refresh_defers_repo_to_back_of_queue(self):
        # b is oldest → picked; a manual fetch of b (stamp update) makes a
        # the next pick — the stamp map IS the scheduler.
        stamps = {self.a.key: 200.0, self.b.key: 100.0, self.c.key: 300.0}
        self.assertEqual(least_recent_fetch_key(self.sessions, stamps), self.b.key)
        stamps[self.b.key] = 400.0
        self.assertEqual(least_recent_fetch_key(self.sessions, stamps), self.a.key)

    def test_failed_fetch_does_not_starve_rotation(self):
        # Starvation guard: the app schedules on ATTEMPT stamps. A repo whose
        # fetch failed still got an attempt stamp, so the next tick moves on
        # to the next repo instead of re-picking the failing one forever.
        attempts: dict[str, float] = {}
        # tick 1: a picked (unstamped, first) — fetch FAILS, attempt recorded
        self.assertEqual(least_recent_fetch_key(self.sessions, attempts), self.a.key)
        attempts[self.a.key] = 100.0  # attempt stamp despite failure
        # tick 2: b, not a again
        self.assertEqual(least_recent_fetch_key(self.sessions, attempts), self.b.key)
        attempts[self.b.key] = 160.0
        # tick 3: c — the full registry gets covered
        self.assertEqual(least_recent_fetch_key(self.sessions, attempts), self.c.key)
        attempts[self.c.key] = 220.0
        # tick 4: back to the failing repo — retry cooldown = one full cycle
        self.assertEqual(least_recent_fetch_key(self.sessions, attempts), self.a.key)


class FormatAgeTests(unittest.TestCase):
    def test_never_fetched(self):
        self.assertEqual(format_age(None), "—")

    def test_seconds(self):
        self.assertEqual(format_age(0), "0s")
        self.assertEqual(format_age(59.4), "59s")

    def test_minutes(self):
        self.assertEqual(format_age(60), "1m")
        self.assertEqual(format_age(3599), "59m")

    def test_hours(self):
        self.assertEqual(format_age(3600), "1h")
        self.assertEqual(format_age(3900), "1h5m")

    def test_negative_clamped(self):
        self.assertEqual(format_age(-5), "0s")


class ShouldStampFetchTests(unittest.TestCase):
    def test_local_only_pass_never_stamps(self):
        # Negative control: passive (non-fetch) polling must never refresh
        # the displayed age, whatever the statuses look like.
        self.assertFalse(should_stamp_fetch(False, ["ok", "ok"]))
        self.assertFalse(should_stamp_fetch(False, []))

    def test_fetch_error_never_stamps(self):
        self.assertFalse(should_stamp_fetch(True, ["fetch_error"]))
        self.assertFalse(should_stamp_fetch(True, ["no_remote", "missing_worktree"]))

    def test_successful_fetch_stamps(self):
        self.assertTrue(should_stamp_fetch(True, ["ok", "missing_worktree"]))
        self.assertTrue(should_stamp_fetch(True, ["missing_remote"]))
        self.assertTrue(should_stamp_fetch(True, ["fetch_error", "ok"]))


class CoalesceRequestTests(unittest.TestCase):
    def test_idle_starts_worker(self):
        start, pending = coalesce_request(False, PENDING_UNSET, "keyA", False)
        self.assertTrue(start)
        self.assertIs(pending, PENDING_UNSET)

    def test_active_automatic_replaces_automatic_latest_wins(self):
        start, pending = coalesce_request(True, PENDING_UNSET, "keyA", False)
        self.assertFalse(start)
        self.assertEqual(pending, ("keyA", False))
        start, pending = coalesce_request(True, pending, "keyB", False)
        self.assertFalse(start)
        self.assertEqual(pending, ("keyB", False))

    def test_automatic_tick_never_overwrites_pending_explicit(self):
        # A manual r / post-action target queued while a worker runs must not
        # be silently dropped by the next interval tick.
        _, pending = coalesce_request(True, PENDING_UNSET, "manualRepo", True)
        self.assertEqual(pending, ("manualRepo", True))
        start, pending = coalesce_request(True, pending, "lruRepo", False)
        self.assertFalse(start)
        self.assertEqual(pending, ("manualRepo", True))

    def test_explicit_replaces_automatic_and_explicit(self):
        _, pending = coalesce_request(True, PENDING_UNSET, "lruRepo", False)
        _, pending = coalesce_request(True, pending, "manualA", True)
        self.assertEqual(pending, ("manualA", True))
        _, pending = coalesce_request(True, pending, "manualB", True)
        self.assertEqual(pending, ("manualB", True))  # latest explicit wins

    def test_none_fetch_key_is_a_valid_deferred_request(self):
        start, pending = coalesce_request(True, PENDING_UNSET, None, False)
        self.assertFalse(start)
        self.assertEqual(pending, (None, False))
        self.assertIsNot(pending, PENDING_UNSET)

    def test_completion_sequence_single_followup_no_loop(self):
        # Scripted sequence: request while idle → start; two requests while
        # active → one pending slot (latest wins); completion pops the slot →
        # exactly one follow-up start; second completion with an empty slot →
        # no restart (no self-perpetuating refresh loop).
        active, pending = False, PENDING_UNSET
        starts: list[str | None] = []

        def request(key, explicit, active, pending):
            start, pending = coalesce_request(active, pending, key, explicit)
            if start:
                starts.append(key)
                active = True
            return active, pending

        active, pending = request("a", False, active, pending)
        active, pending = request("b", False, active, pending)
        active, pending = request("c", False, active, pending)
        self.assertEqual(starts, ["a"])
        # Worker for "a" completes → pop pending.
        active = False
        self.assertIsNot(pending, PENDING_UNSET)
        (popped_key, popped_explicit), pending = pending, PENDING_UNSET
        active, pending = request(popped_key, popped_explicit, active, pending)
        self.assertEqual(starts, ["a", "c"])
        # Worker for "c" completes → empty slot → nothing restarts.
        active = False
        self.assertIs(pending, PENDING_UNSET)


class ResolveActionTargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent  # any existing directory
        self.s = AitasksSession(
            session="", project_root=self.tmp, project_name="proj"
        )
        self.by_key = {self.s.key: self.s}
        self.row = RowSpec("r0", self.s.key, "main", "proj")
        self.snap = {"refs": [{"name": "main", "local_ref": "master"}]}

    def test_happy_path_uses_selected_repo_root_and_branch(self):
        target = resolve_action_target(
            self.row, self.by_key, {self.s.key: self.snap}, need_branch=True
        )
        self.assertIsInstance(target, ActionTarget)
        self.assertEqual(target.root, self.tmp)
        self.assertEqual(target.branch, "master")
        self.assertEqual(target.label, "proj")

    def test_missing_session_names_project(self):
        reason = resolve_action_target(self.row, {}, {}, need_branch=True)
        self.assertIsInstance(reason, str)
        self.assertIn("proj", reason)
        self.assertIn("no longer discovered", reason)

    def test_nondir_root_names_path(self):
        gone = AitasksSession(
            session="", project_root=Path("/nonexistent/xyz"), project_name="gone"
        )
        row = RowSpec("r0", gone.key, "main", "gone")
        reason = resolve_action_target(row, {gone.key: gone}, {}, need_branch=True)
        self.assertIsInstance(reason, str)
        self.assertIn("gone", reason)
        self.assertIn("/nonexistent/xyz", reason)

    def test_absent_snapshot_blocks_pull_push(self):
        reason = resolve_action_target(self.row, self.by_key, {}, need_branch=True)
        self.assertIsInstance(reason, str)
        self.assertIn("no status snapshot", reason)

    def test_branch_never_derived_from_another_repos_snapshot(self):
        other_key = "some-other-key"
        reason = resolve_action_target(
            self.row, self.by_key, {other_key: self.snap}, need_branch=True
        )
        self.assertIsInstance(reason, str)  # error, NOT a target with master

    def test_sync_does_not_require_snapshot(self):
        target = resolve_action_target(self.row, self.by_key, {}, need_branch=False)
        self.assertIsInstance(target, ActionTarget)
        self.assertEqual(target.root, self.tmp)
        self.assertIsNone(target.branch)

    def test_single_repo_sync_is_legacy_cwd_relative(self):
        row = RowSpec("aitask-data", "", "aitask-data", "")
        target = resolve_action_target(row, {}, {}, need_branch=False)
        self.assertIsInstance(target, ActionTarget)
        self.assertIsNone(target.root)

    def test_single_repo_pull_uses_snapshot_worktree(self):
        row = RowSpec("main", "", "main", "")
        snap = {"refs": [{"name": "main", "local_ref": "main", "worktree": "."}]}
        target = resolve_action_target(row, {}, {"": snap}, need_branch=True)
        self.assertIsInstance(target, ActionTarget)
        self.assertEqual(target.root, Path("."))
        self.assertEqual(target.branch, "main")

    def test_single_repo_pull_without_snapshot_errors(self):
        row = RowSpec("main", "", "main", "")
        reason = resolve_action_target(row, {}, {}, need_branch=True)
        self.assertEqual(reason, "main worktree not available")


class DiscoverSyncerSessionsTests(unittest.TestCase):
    def test_discovery_failure_falls_back_to_cwd_only(self):
        def boom(**kwargs):
            raise RuntimeError("registry unreadable")

        with mock.patch.object(syncer_app, "discover_aitasks_sessions", boom):
            sessions = discover_syncer_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].project_root, Path.cwd().resolve())

    def test_unregistered_cwd_synthesized_first(self):
        other = AitasksSession(
            session="x", project_root=Path("/tmp/other"), project_name="other"
        )
        with mock.patch.object(
            syncer_app, "discover_aitasks_sessions", lambda **kw: [other]
        ):
            sessions = discover_syncer_sessions()
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].project_root, Path.cwd().resolve())
        self.assertEqual(sessions[1].key, other.key)

    def test_registered_cwd_not_duplicated_and_first(self):
        cwd = Path.cwd().resolve()
        current = AitasksSession(session="here", project_root=cwd, project_name="me")
        other = AitasksSession(
            session="x", project_root=Path("/tmp/other"), project_name="other"
        )
        with mock.patch.object(
            syncer_app, "discover_aitasks_sessions", lambda **kw: [other, current]
        ):
            sessions = discover_syncer_sessions()
        self.assertEqual([s.key for s in sessions], [current.key, other.key])
        self.assertEqual(sessions[0].session, "here")  # the real entry, not synthesized

    def test_stale_registry_rows_dropped(self):
        stale = AitasksSession(
            session="", project_root=Path("/tmp/stale"), project_name="stale",
            is_live=False, is_stale=True,
        )
        with mock.patch.object(
            syncer_app, "discover_aitasks_sessions", lambda **kw: [stale]
        ):
            sessions = discover_syncer_sessions()
        self.assertNotIn(stale.key, [s.key for s in sessions])
        self.assertEqual(len(sessions), 1)  # just the synthesized cwd


# --------------------------------------------------------------- tabbed shell
# The tests below boot the real SyncerApp headlessly (t1223_1). Everything
# above this line is pure-helper coverage that needs no running app.

FAKE_SNAPSHOT = {
    "refs": [
        {"name": "main", "status": "ok", "ahead": 0, "behind": 0,
         "worktree": "/tmp/repo0"},
        {"name": "aitask-data", "status": "ok", "ahead": 1, "behind": 2,
         "worktree": "/tmp/repo0"},
    ]
}

ROW_MAIN, ROW_DATA = 0, 1  # cursor rows within a single repo's TRACKED_REFS


def footer_state(app) -> dict[str, str]:
    """action -> "dim" | "on" for every binding the footer currently shows.

    Keyed by *action*, not by key, so a user's shortcut remap cannot break
    these assertions (check_action is likewise dispatched by action name).
    """
    return {
        key.action: ("dim" if key.has_class("-disabled") else "on")
        for key in app.query_one(Footer).query("FooterKey")
    }


def detail_text(app) -> str:
    return app.query_one("#detail", Static).render().plain


PANE_ORDER = ("tab_branches", "tab_versions", "tab_settings")


async def activate_tab(app, pilot, tab_id: str):
    """Switch tabs the way a user does: focus the bar, then press ←/→.

    Driving this with real keypresses is load-bearing twice over.

    1. Assigning ``TabbedContent.active`` directly while a widget inside the
       *current* pane holds focus is silently reverted by Textual (t1060) — it
       re-syncs `active` back to the pane owning the focused widget — so a naive
       test would keep asserting against Branches and pass for the wrong reason.
    2. Focusing the tab bar is itself a focus change, which triggers Textual's
       own bindings refresh. A helper that focused the bar and then *assigned*
       `active` would get a refreshed footer for free and pass even with
       ``on_tabbed_content_tab_activated`` deleted. Arrow keys move `active`
       without moving focus — the exact case the handler exists for.
    """
    tabbed = app.query_one(TabbedContent)
    tabbed.query_one(Tabs).focus()
    await pilot.pause()
    delta = PANE_ORDER.index(tab_id) - PANE_ORDER.index(tabbed.active)
    for _ in range(abs(delta)):
        await pilot.press("right" if delta > 0 else "left")
        await pilot.pause()
    await pilot.pause()
    assert tabbed.active == tab_id, f"tab switch to {tab_id!r} did not stick"
    return tabbed


class TabbedShellTests(unittest.TestCase):
    """Boots the real SyncerApp with two module seams mocked: discovery (to pin
    ``multi_repo``) and ``snapshot`` (so the threaded refresh worker never
    shells out to git)."""

    def _run(self, coro):
        return asyncio.run(coro)

    @contextlib.asynccontextmanager
    async def booted(self, repos: int = 1):
        sessions = [
            sess(f"/tmp/repo{i}", f"repo{i}") for i in range(repos)
        ]
        with mock.patch.object(
            syncer_app, "snapshot", lambda *a, **kw: dict(FAKE_SNAPSHOT)
        ), mock.patch.object(
            syncer_app, "discover_syncer_sessions", lambda: sessions
        ):
            app = syncer_app.SyncerApp(
                argparse.Namespace(interval=3600, no_fetch=True)
            )
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                yield app, pilot

    # ------------------------------------------------------------ tab shape

    def test_panes_present_and_branches_active_on_start(self):
        async def runner():
            async with self.booted() as (app, _pilot):
                tabbed = app.query_one(TabbedContent)
                self.assertEqual(
                    [pane.id for pane in app.query(TabPane)],
                    ["tab_branches", "tab_versions", "tab_settings"],
                )
                self.assertEqual(tabbed.active, "tab_branches")
        self._run(runner())

    def test_widget_ids_survive_the_tab_wrap(self):
        async def runner():
            async with self.booted() as (app, _pilot):
                # Every pre-refactor query_one() call site resolves by these ids.
                self.assertIsNotNone(app.query_one("#branches", DataTable))
                self.assertIsNotNone(app.query_one("#detail", Static))
                self.assertIsNotNone(app.query_one("#detail_scroll"))
        self._run(runner())

    def test_placeholder_panes_render_their_text(self):
        async def runner():
            async with self.booted() as (app, _pilot):
                self.assertIn(
                    "Framework versions",
                    app.query_one("#versions_placeholder", Static).render().plain,
                )
                self.assertIn(
                    "Cross-repo settings",
                    app.query_one("#settings_placeholder", Static).render().plain,
                )
        self._run(runner())

    # ----------------------------------------------------------- boot focus

    def test_boot_focus_is_the_branch_table(self):
        """Without an explicit focus() the tab bar takes boot focus and the
        arrow keys stop driving the branch cursor."""
        async def runner():
            async with self.booted() as (app, pilot):
                table = app.query_one("#branches", DataTable)
                self.assertIs(app.focused, table)
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(table.cursor_row, ROW_DATA)
        self._run(runner())

    def test_tab_bar_is_two_tabs_away_and_detail_stays_focusable(self):
        """Documents the traversal cost of the tab wrap. The detail pane is
        focusable pre-refactor (that focus is what scrolls a long detail), so
        dropping it from the focus chain to shorten this route would be a
        regression, not a simplification."""
        async def runner():
            async with self.booted() as (app, pilot):
                self.assertTrue(app.query_one("#detail_scroll").can_focus)
                await pilot.press("tab")
                await pilot.pause()
                self.assertIs(app.focused, app.query_one("#detail_scroll"))
                await pilot.press("tab")
                await pilot.pause()
                self.assertIsInstance(app.focused, Tabs)
        self._run(runner())

    # --------------------------------------------------------- tab gating

    def test_branch_actions_allowed_on_branches_tab(self):
        async def runner():
            async with self.booted() as (app, pilot):
                await pilot.press("down")  # aitask-data row
                await pilot.pause()
                self.assertTrue(app.check_action("sync_data", ()))
                self.assertTrue(app.check_action("refresh", ()))
                self.assertTrue(app.check_action("toggle_fetch", ()))
        self._run(runner())

    def test_branch_actions_inert_on_other_tabs_negative_control(self):
        """The load-bearing assertion: every Branches action is `False` on the
        other tabs *even when the selected row would otherwise allow it*.

        Both cursor rows are exercised because `pull`/`push` are ref-denied on
        the aitask-data row and `sync_data` is ref-denied on main — testing one
        row only would let a removed tab check survive on the other. The
        `assertTrue(...allowed...)` guard makes the control self-enforcing: if a
        future change made the baseline inert anyway, this test fails instead of
        silently proving nothing.
        """
        async def runner():
            for cursor, allowed in (
                (ROW_MAIN, ("pull", "push", "refresh", "toggle_fetch")),
                (ROW_DATA, ("sync_data", "refresh", "toggle_fetch")),
            ):
                async with self.booted() as (app, pilot):
                    for _ in range(cursor):
                        await pilot.press("down")
                    await pilot.pause()
                    for action in allowed:
                        self.assertTrue(
                            app.check_action(action, ()),
                            f"baseline broken: {action} already inert on Branches "
                            f"at row {cursor}",
                        )
                    for tab in ("tab_versions", "tab_settings"):
                        await activate_tab(app, pilot, tab)
                        for action in syncer_app.BRANCH_TAB_ACTIONS:
                            self.assertIs(
                                app.check_action(action, ()), False,
                                f"{action} not inert on {tab} at row {cursor}",
                            )
        self._run(runner())

    def test_ref_gating_unchanged_and_distinct_from_tab_gating(self):
        """Row gating keeps returning `None` (dimmed, same tab) — only the tab
        gate returns `False` (removed). The split is deliberate."""
        async def runner():
            async with self.booted() as (app, pilot):
                self.assertIsNone(app.check_action("sync_data", ()))  # main row
                self.assertTrue(app.check_action("pull", ()))
                self.assertTrue(app.check_action("push", ()))
                await pilot.press("down")  # aitask-data row
                await pilot.pause()
                self.assertTrue(app.check_action("sync_data", ()))
                self.assertIsNone(app.check_action("pull", ()))
                self.assertIsNone(app.check_action("push", ()))
        self._run(runner())

    def test_active_tab_degrades_to_branches_without_a_running_app(self):
        """check_action runs pre-mount; the TabbedContent query raises there."""
        sessions = [sess("/tmp/repo0", "repo0")]
        with mock.patch.object(
            syncer_app, "discover_syncer_sessions", lambda: sessions
        ):
            app = syncer_app.SyncerApp(
                argparse.Namespace(interval=3600, no_fetch=True)
            )
        self.assertEqual(app._active_tab(), "tab_branches")
        # ... and the pre-mount call must not raise.
        self.assertIsNone(app.check_action("sync_data", ()))

    # -------------------------------------------------------------- footer

    def test_footer_drops_branch_keys_on_tab_activation(self):
        """←/→ on the tab bar changes no focus, so without the explicit
        refresh_bindings() the footer keeps advertising the inert keys."""
        async def runner():
            async with self.booted() as (app, pilot):
                before = footer_state(app)
                for action in ("refresh", "sync_data", "pull", "push",
                               "toggle_fetch"):
                    self.assertIn(action, before)
                await activate_tab(app, pilot, "tab_versions")
                after = footer_state(app)
                for action in syncer_app.BRANCH_TAB_ACTIONS:
                    self.assertNotIn(
                        action, after, f"{action} still advertised on Versions"
                    )
                self.assertIn("quit", after)  # global actions survive
        self._run(runner())

    def test_footer_and_detail_still_follow_the_row_cursor(self):
        """Regression coverage for the pre-existing
        on_data_table_row_highlighted handler, which does both halves:
        refresh_bindings() (re-dims the footer) and _refresh_detail() (repoints
        the detail pane). The tab wrap must not disturb either."""
        async def runner():
            async with self.booted() as (app, pilot):
                state = footer_state(app)
                self.assertEqual(state["sync_data"], "dim")   # main row
                self.assertEqual(state["pull"], "on")
                self.assertIn("main", detail_text(app))
                await pilot.press("down")
                await pilot.pause()
                state = footer_state(app)
                self.assertEqual(state["sync_data"], "on")    # aitask-data row
                self.assertEqual(state["pull"], "dim")
                self.assertIn("aitask-data", detail_text(app))
        self._run(runner())

    # ------------------------------------------------------ repo-mode shape

    def test_single_repo_layout_unchanged(self):
        async def runner():
            async with self.booted(repos=1) as (app, _pilot):
                table = app.query_one("#branches", DataTable)
                self.assertFalse(app.multi_repo)
                self.assertEqual(len(table.columns), 5)  # no Project column
                self.assertNotIn(
                    "project", [str(k.value) for k in table.columns]
                )
                # Legacy single-repo row keys are the literal ref names.
                self.assertEqual(
                    [str(k.value) for k in table.rows],
                    list(syncer_app.TRACKED_REFS),
                )
        self._run(runner())

    def test_multi_repo_layout_unchanged(self):
        async def runner():
            async with self.booted(repos=2) as (app, _pilot):
                table = app.query_one("#branches", DataTable)
                self.assertTrue(app.multi_repo)
                self.assertEqual(len(table.columns), 6)  # Project column added
                # Opaque positional row keys, one row per repo x ref.
                self.assertEqual(
                    [str(k.value) for k in table.rows],
                    ["r0", "r1", "r2", "r3"],
                )
                self.assertEqual(
                    app.query_one(TabbedContent).active, "tab_branches"
                )
        self._run(runner())


if __name__ == "__main__":
    unittest.main()

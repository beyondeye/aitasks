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
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "syncer"))

from textual.widgets import (  # noqa: E402
    DataTable,
    Footer,
    Input,
    RadioSet,
    SelectionList,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)

import agent_launch_utils  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402
import syncer_app  # noqa: E402
from syncer_app import (  # noqa: E402
    PENDING_UNSET,
    ActionTarget,
    PushTarget,
    RowSpec,
    SettingsRow,
    UpgradeRun,
    UpgradeTarget,
    action_allowed_for_ref,
    build_labels,
    build_rows,
    build_settings_matrix,
    build_version_rows,
    coalesce_request,
    discover_syncer_sessions,
    format_age,
    least_recent_fetch_key,
    resolve_action_target,
    should_stamp_fetch,
    single_repo_rows,
    upgrade_state_cell,
)
from cross_repo_settings import (  # noqa: E402
    OperationValue,
    PushOutcome,
    PushPartialError,
)
from upgrade_screens import (  # noqa: E402
    ForceConfirmScreen,
    HandoffConfirmScreen,
    UpgradeConfirmScreen,
    UpgradeRefusalScreen,
    UpgradeTargetScreen,
)
from settings_screens import (  # noqa: E402
    SettingsDestinationsScreen,
    SettingsLayerScreen,
    SettingsMaskedScreen,
    SettingsPushResultScreen,
    SettingsSourceScreen,
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


class VersionRowModelTests(unittest.TestCase):
    """Pure Versions-tab row model (t1223_3)."""

    def test_one_row_per_repo_with_opaque_positional_keys(self):
        sessions = [sess("/tmp/alpha"), sess("/tmp/beta"), sess("/tmp/gamma")]
        rows = build_version_rows(sessions, build_labels(sessions))
        self.assertEqual([r.row_key for r in rows], ["v0", "v1", "v2"])
        self.assertEqual(
            [r.session_key for r in rows], [s.key for s in sessions]
        )
        # One row per REPO, not per repo×ref (the Branches model's shape).
        self.assertEqual(len(rows), len(sessions))

    def test_labels_are_collision_safe(self):
        # Same basename in two places: labels must still disambiguate.
        sessions = [sess("/tmp/one/proj"), sess("/tmp/two/proj")]
        rows = build_version_rows(sessions, build_labels(sessions))
        labels = [r.project_label for r in rows]
        self.assertEqual(len(set(labels)), 2, labels)

    def test_row_key_lookup_round_trips(self):
        sessions = [sess("/tmp/alpha"), sess("/tmp/beta")]
        rows = build_version_rows(sessions, build_labels(sessions))
        by_key = {r.row_key: r for r in rows}
        self.assertEqual(by_key["v1"].session_key, sessions[1].key)

    def test_empty_session_list(self):
        self.assertEqual(build_version_rows([], {}), [])


class UpgradeStateCellTests(unittest.TestCase):
    """Contract G: the State column never claims an unobserved success."""

    def test_idle_and_missing_render_empty(self):
        self.assertEqual(upgrade_state_cell(None), "")
        self.assertEqual(
            upgrade_state_cell(UpgradeRun(state=syncer_app.UPGRADE_IDLE)), ""
        )

    def test_launched_and_finished_labels(self):
        self.assertEqual(
            upgrade_state_cell(UpgradeRun(state=syncer_app.UPGRADE_LAUNCHED)),
            "upgrading…",
        )
        self.assertEqual(
            upgrade_state_cell(UpgradeRun(state=syncer_app.UPGRADE_FINISHED)),
            "re-check needed",
        )

    def test_no_state_renders_a_success_word(self):
        # Negative control: adding an optimistic "upgraded"/"done" label later
        # must break this.
        rendered = [
            upgrade_state_cell(None),
            upgrade_state_cell(UpgradeRun(state=syncer_app.UPGRADE_IDLE)),
            upgrade_state_cell(UpgradeRun(state=syncer_app.UPGRADE_LAUNCHED)),
            upgrade_state_cell(UpgradeRun(state=syncer_app.UPGRADE_FINISHED)),
        ]
        for text in rendered:
            lowered = text.lower()
            for word in ("success", "upgraded", "done", "complete", "ok"):
                self.assertNotIn(word, lowered, rendered)


class GetTmuxWindowsResultTests(unittest.TestCase):
    """The checked enumeration variant added for the fail-closed activity gate.

    ``get_tmux_windows`` collapses a tmux failure and an genuinely window-less
    session into the same empty list; a safety decision cannot be made from
    that, so the result variant keeps the error.
    """

    def _patched(self, rc: int, out: str):
        return mock.patch.object(
            agent_launch_utils._TMUX, "run", lambda *a, **kw: (rc, out)
        )

    def test_success_parses_index_name_tuples(self):
        with self._patched(0, "1:board\n2:agent-t42-fix\n"):
            windows, err = agent_launch_utils.get_tmux_windows_result("s")
        self.assertEqual(windows, [("1", "board"), ("2", "agent-t42-fix")])
        self.assertIsNone(err)

    def test_success_with_no_windows_is_not_an_error(self):
        # Load-bearing: a real empty session must still classify as idle.
        with self._patched(0, ""):
            windows, err = agent_launch_utils.get_tmux_windows_result("s")
        self.assertEqual(windows, [])
        self.assertIsNone(err)

    def test_failure_reports_a_reason(self):
        # The gateway folds timeout/ENOENT/OSError into rc == -1.
        with self._patched(-1, ""):
            windows, err = agent_launch_utils.get_tmux_windows_result("s")
        self.assertEqual(windows, [])
        self.assertIsNotNone(err)

    def test_legacy_wrapper_returns_only_the_window_list(self):
        # Existing callers keep exactly their old behavior.
        with self._patched(0, "1:board\n"):
            self.assertEqual(
                agent_launch_utils.get_tmux_windows("s"), [("1", "board")]
            )
        with self._patched(-1, ""):
            self.assertEqual(agent_launch_utils.get_tmux_windows("s"), [])


class SettingsMatrixTests(unittest.TestCase):
    """The Settings-tab row model (t1223_5), pure — no running app.

    Rendering and source-eligibility are two different questions answered from
    the same inputs, so both are pinned here rather than inside the TUI tests.
    """

    KEYS = ["A", "B"]

    def matrix(self, diff, unreadable=frozenset()):
        return {
            r.operation: r
            for r in build_settings_matrix(diff, self.KEYS, unreadable)
        }

    # ---- provenance markers

    def test_one_marker_per_provenance_and_conflict_is_literal(self):
        """The amended marker table: local/project/builtin each get their own
        rendering, and `conflict` renders the WORD, never the value behind it —
        the layers and the resolver disagree, so any value would be a guess.

        There is deliberately no `seed` case: t1223_4 established the resolver
        has no seed tier, so a seed marker could never occur."""
        rows = self.matrix({
            "proj": {"A": ov("x/1", "project", project="x/1"), "B": ov("x/1", "project")},
            "loc": {"A": ov("x/2", "local", local="x/2"), "B": ov("x/2", "local")},
            "bui": {"A": ov("x/3", "builtin"), "B": ov("x/3", "builtin")},
            "con": {"A": ov("x/4", "conflict", project="x/9"), "B": ov("x/4", "conflict")},
        })
        self.assertEqual(rows["proj"].cells[0], "x/1")
        self.assertEqual(rows["loc"].cells[0], "x/2 (local)")
        self.assertEqual(rows["bui"].cells[0], "x/3 (default)")
        self.assertEqual(rows["con"].cells[0], "conflict")
        # The value exists but must not leak into the cell.
        self.assertNotIn("x/4", rows["con"].cells[0])

    def test_unreadable_repo_renders_unavailable_in_every_row(self):
        rows = self.matrix(
            {
                "pick": {"A": ov("x/1", "project"), "B": ov("x/1", "project")},
                "qa": {"A": ov("x/2", "local"), "B": ov("x/2", "local")},
            },
            frozenset({"B"}),
        )
        for op in ("pick", "qa"):
            self.assertEqual(rows[op].cells[1], "unavailable")

    def test_missing_cell_renders_unavailable_not_a_crash(self):
        rows = self.matrix({"pick": {"A": ov("x/1", "project")}})
        self.assertEqual(rows["pick"].cells[1], "unavailable")

    # ---- divergence

    def test_divergence_flagging(self):
        """All-equal is not flagged; one differing repo is; a conflict cell
        always is (something in that repo is genuinely wrong)."""
        rows = self.matrix({
            "same": {"A": ov("x/1", "project"), "B": ov("x/1", "local")},
            "diff": {"A": ov("x/1", "project"), "B": ov("x/2", "project")},
            "con": {"A": ov("x/1", "conflict"), "B": ov("x/1", "project")},
        })
        self.assertFalse(rows["same"].divergent)
        self.assertTrue(rows["diff"].divergent)
        self.assertTrue(rows["con"].divergent)

    def test_unreadable_column_is_excluded_from_the_comparison(self):
        """An unreadable repo's agreement is unknowable, so it must not flag
        every row — that would be noise, not signal."""
        rows = self.matrix(
            {"pick": {"A": ov("x/1", "project"), "B": ov("x/9", "project")}},
            frozenset({"B"}),
        )
        self.assertFalse(rows["pick"].divergent)

    # ---- row keys

    def test_row_keys_are_opaque_positional_and_cells_follow_column_order(self):
        rows = build_settings_matrix(
            {"b_op": {"A": ov("x/1", "project"), "B": ov("x/2", "project")},
             "a_op": {"A": ov("x/3", "project"), "B": ov("x/4", "project")}},
            self.KEYS,
        )
        self.assertEqual([r.row_key for r in rows], ["s0", "s1"])
        self.assertEqual([r.operation for r in rows], ["a_op", "b_op"])
        self.assertEqual(rows[0].cells, ("x/3", "x/4"))   # A then B
        by_key = {r.row_key: r for r in rows}
        self.assertEqual(by_key["s1"].operation, "b_op")

    # ---- source eligibility

    def test_source_eligibility_excludes_conflict_and_unavailable(self):
        """`sources` answers "may this be copied?", which is NOT the same
        question as "what does the cell say?".

        A conflict cell has an effective value but no coherent one to
        propagate, and an unreadable repo has none at all. Handing either to
        plan_push would not raise — it matches against `value or ""` — it would
        return malformed_agent_string for every destination, blaming the user's
        choice instead of reporting that no value existed."""
        rows = self.matrix(
            {
                "mixed": {"A": ov("x/1", "conflict"), "B": ov("x/2", "local")},
                "none": {"A": ov("x/1", "conflict"), "B": ov("x/2", "project")},
            },
            frozenset({"B"}),
        )
        self.assertEqual(rows["mixed"].sources, (None, None))  # B unreadable
        self.assertFalse(rows["mixed"].has_source)

        readable = self.matrix({
            "mixed": {"A": ov("x/1", "conflict"), "B": ov("x/2", "local")},
        })
        self.assertEqual(readable["mixed"].sources, (None, "x/2"))
        self.assertTrue(readable["mixed"].has_source)

    def test_source_eligibility_keeps_every_normal_provenance(self):
        rows = self.matrix({
            "op": {"A": ov("x/1", "local"), "B": ov("x/2", "builtin")},
        })
        self.assertEqual(rows["op"].sources, ("x/1", "x/2"))


class PushTargetTests(unittest.TestCase):
    """Source and destination are different questions over the same repos."""

    def target(self):
        return PushTarget(
            operation="pick",
            repos=(("A", "repoA"), ("B", "repoB"), ("C", "repoC")),
            sources=(None, "x/2", "x/3"),   # A ineligible as a source
        )

    def test_source_options_drop_ineligible_repos(self):
        self.assertEqual(
            self.target().source_options(),
            [("B", "repoB", "x/2"), ("C", "repoC", "x/3")],
        )

    def test_destinations_exclude_the_source_but_not_ineligible_repos(self):
        """The AC says destinations are "the OTHER repos" — leaving the source
        in would guarantee a self-targeted noop in the summary.

        But a repo that cannot be a *source* is still a perfectly good
        *destination*: repo A is conflicted, which is exactly the state a
        coherent write fixes. Filtering destinations by source-eligibility
        would silently make it unfixable."""
        dests = self.target().destinations_excluding("B")
        self.assertEqual(dests, [("A", "repoA"), ("C", "repoC")])
        self.assertNotIn("B", [k for k, _ in dests])


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


class Seams:
    """Configurable stand-ins for every impure seam the version/upgrade paths
    touch, with call logs so a test can assert something did **not** happen.

    Without these the suite would issue real ``tmux list-windows`` calls against
    the developer's live session and a real GitHub request — the version tab is
    reached by several tests that are not about versions at all.
    """

    def __init__(self) -> None:
        self.latest: tuple[str | None, str | None] = ("9.9.9", None)
        self.windows: tuple[list[tuple[str, str]], str | None] = ([], None)
        self.windows_queue: list[tuple[list[tuple[str, str]], str | None]] = []
        self.tmux_sessions: list[str] = []
        self.tmux_available = True
        self.spawn_result: tuple[int | None, str | None] = (4242, None)
        self.pane_alive = True
        self.installed: dict[str, str | None] = {}
        self.self_root: Path | None = None
        # -- cross-repo settings seam (t1223_5). Every one of these shells a
        # subprocess or writes another repo's config file, and three existing
        # tests activate the Settings tab for unrelated reasons — unpatched,
        # the suite would run the real resolver against real repos.
        self.diff: dict = {}
        self.diff_queue: list = []          # successive results/exceptions
        self.unreadable_roots: set[str] = set()
        self.plan_outcomes: dict = {}       # session key -> PushOutcome
        self.apply_error: dict = {}         # session key -> exception to raise
        # call logs
        self.launches: list[tuple[str, object]] = []
        self.window_calls: list[str] = []
        self.latest_calls = 0
        self.diff_calls: list[list[str]] = []
        self.probe_calls: list[str] = []
        self.plans: list[tuple[str, str, str, str]] = []
        self.applies: list[tuple[str, str, str, str, bool]] = []

    # -- seam implementations -------------------------------------------
    def get_tmux_windows_result(self, session):
        self.window_calls.append(session)
        if self.windows_queue:
            return self.windows_queue.pop(0)
        return self.windows

    def resolve_latest_version(self, *args, **kwargs):
        self.latest_calls += 1
        return self.latest

    def launch_in_tmux(self, command, config):
        self.launches.append((command, config))
        return self.spawn_result

    def resolve_pane_id_by_pid(self, session, pid):
        return "%7" if self.pane_alive else None

    def read_installed_version(self, root):
        return self.installed.get(str(root))

    def is_self_target(self, root, cwd):
        return self.self_root is not None and Path(root) == Path(self.self_root)

    # -- settings seams --------------------------------------------------
    def diff_across_repos(self, roots):
        self.diff_calls.append([str(r) for r in roots])
        if self.diff_queue:
            nxt = self.diff_queue.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt
        return self.diff

    def read_operation_defaults(self, root):
        self.probe_calls.append(str(root))
        if str(root) in self.unreadable_roots:
            raise syncer_app.DestConfigUnreadable(f"{root} is corrupt")
        return {}

    def plan_push(self, value, dest_root, operation, layer):
        self.plans.append((value, str(dest_root), operation, layer))
        return self.plan_outcomes.get(str(dest_root), PushOutcome(kind="ok"))

    def apply_push(self, value, dest_root, operation, layer, clear_mask=False):
        self.applies.append(
            (value, str(dest_root), operation, layer, clear_mask)
        )
        err = self.apply_error.get(str(dest_root))
        if err is not None:
            raise err


def ov(effective, provenance, *, operation="pick", project=None, local=None):
    """Terse OperationValue builder for matrix fixtures."""
    return OperationValue(
        operation=operation, effective=effective, project_value=project,
        local_value=local, provenance=provenance,
    )


def settings_cells(app, row_key: str) -> list[str]:
    """Rendered Settings-table cells for one row: [diverge, operation, *repos]."""
    table = app.query_one("#settings", DataTable)
    cols = ["diverge", "operation"] + list(app._settings_col_keys)
    return [str(table.get_cell(row_key, col)) for col in cols]


def version_cells(app, row_key: str) -> dict[str, str]:
    """Rendered Versions-table cells for one row, keyed by column."""
    table = app.query_one("#versions", DataTable)
    return {
        col: str(table.get_cell(row_key, col))
        for col in ("project", "installed", "latest", "vstatus", "state")
    }


class _TabbedShellBase(unittest.TestCase):
    """Boot helpers only — deliberately test-free, so the subclasses below
    inherit the fixture without inheriting anybody's tests.

    Boots the real SyncerApp with every impure seam mocked: discovery (to pin
    ``multi_repo``), ``snapshot`` (so the threaded refresh worker never shells
    out to git), and the version/upgrade seams (network, tmux, spawn).

    The leading underscore is load-bearing: it keeps this class out of
    collection, matching the ``GitRepoTestBase`` / ``BrainstormCrewTestBase``
    pattern used elsewhere in this tree."""

    def _run(self, coro):
        return asyncio.run(coro)

    @contextlib.asynccontextmanager
    async def booted(
        self,
        repos: int = 1,
        *,
        sessions: list[AitasksSession] | None = None,
        seams: Seams | None = None,
        no_fetch: bool = True,
    ):
        if sessions is None:
            sessions = [sess(f"/tmp/repo{i}", f"repo{i}") for i in range(repos)]
        seams = seams or Seams()
        with mock.patch.object(
            syncer_app, "snapshot", lambda *a, **kw: dict(FAKE_SNAPSHOT)
        ), mock.patch.object(
            syncer_app, "discover_syncer_sessions", lambda: sessions
        ), mock.patch.object(
            syncer_app, "get_tmux_windows_result", seams.get_tmux_windows_result
        ), mock.patch.object(
            syncer_app, "resolve_latest_version", seams.resolve_latest_version
        ), mock.patch.object(
            syncer_app, "launch_in_tmux", seams.launch_in_tmux
        ), mock.patch.object(
            syncer_app, "resolve_pane_id_by_pid", seams.resolve_pane_id_by_pid
        ), mock.patch.object(
            syncer_app, "read_installed_version", seams.read_installed_version
        ), mock.patch.object(
            syncer_app, "is_self_target", seams.is_self_target
        ), mock.patch.object(
            syncer_app, "get_tmux_sessions", lambda: list(seams.tmux_sessions)
        ), mock.patch.object(
            syncer_app, "is_tmux_available", lambda: seams.tmux_available
        ), mock.patch.object(
            syncer_app, "diff_across_repos", seams.diff_across_repos
        ), mock.patch.object(
            syncer_app, "read_operation_defaults", seams.read_operation_defaults
        ), mock.patch.object(
            syncer_app, "plan_push", seams.plan_push
        ), mock.patch.object(
            syncer_app, "apply_push", seams.apply_push
        ):
            app = syncer_app.SyncerApp(
                argparse.Namespace(interval=3600, no_fetch=no_fetch)
            )
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                yield app, pilot

    @staticmethod
    async def settle(app, pilot):
        """Let thread workers finish and their call_from_thread callbacks run."""
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()

    async def _focus_bar(self, app, pilot):
        bar = app.query_one(TabbedContent).query_one(Tabs)
        bar.focus()
        await pilot.pause()
        return bar


class TabbedShellTests(_TabbedShellBase):
    """The tabbed-shell behaviour itself.

    Split out of ``_TabbedShellBase`` (t1354_4): while these tests lived on the
    shared base, every subclass below re-ran all of them verbatim — 75 duplicate
    ``SyncerApp`` boots, about half this file's runtime, testing nothing the
    base run did not already cover."""

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

    def test_every_pane_holds_a_real_table_no_placeholders_left(self):
        async def runner():
            async with self.booted() as (app, _pilot):
                # t1223_3 replaced the Versions placeholder, t1223_5 the
                # Settings one; neither Static may survive.
                self.assertIsNotNone(app.query_one("#versions", DataTable))
                self.assertIsNotNone(app.query_one("#settings", DataTable))
                self.assertEqual(len(app.query("#versions_placeholder")), 0)
                self.assertEqual(len(app.query("#settings_placeholder")), 0)
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

    # ----------------------------------------- tab bar <-> content nav (t1266)

    def test_down_from_tab_bar_enters_the_active_list(self):
        """Requirement 1: ↓ on the bar lands on the active pane's first row."""
        async def runner():
            async with self.booted(repos=3) as (app, pilot):
                await self._focus_bar(app, pilot)
                await pilot.press("down")
                await pilot.pause()
                branches = app.query_one("#branches", DataTable)
                self.assertIs(app.focused, branches)
                self.assertEqual(branches.cursor_row, 0)

                # Same contract on the second content tab, via its own table.
                await activate_tab(app, pilot, "tab_versions")
                await self.settle(app, pilot)
                await pilot.press("down")
                await pilot.pause()
                versions = app.query_one("#versions", DataTable)
                self.assertIs(app.focused, versions)
                self.assertEqual(versions.cursor_row, 0)
        self._run(runner())

    def test_up_on_first_row_returns_to_the_tab_bar(self):
        """Requirement 2: ↑ at row 0 hands focus back to the bar.

        DataTable's own action_cursor_up consumes the key at the clamped
        boundary, so without the App-level handoff this is a silent no-op.
        """
        async def runner():
            async with self.booted() as (app, pilot):
                table = app.query_one("#branches", DataTable)
                table.focus()
                table.move_cursor(row=0)
                await pilot.pause()
                await pilot.press("up")
                await pilot.pause()
                self.assertIsInstance(app.focused, Tabs)
        self._run(runner())

    def test_up_mid_list_moves_cursor_and_keeps_focus(self):
        """Negative control for requirement 2 — the handoff must NOT fire
        mid-list. The App action raises SkipAction so DataTable's own cursor
        binding still runs."""
        async def runner():
            async with self.booted() as (app, pilot):
                table = app.query_one("#branches", DataTable)
                table.focus()
                table.move_cursor(row=ROW_DATA)
                await pilot.pause()
                await pilot.press("up")
                await pilot.pause()
                self.assertIs(app.focused, table)
                self.assertEqual(table.cursor_row, ROW_MAIN)
        self._run(runner())

    def test_left_right_switch_tabs_while_the_table_holds_focus(self):
        """Requirement 3 from the content table.

        Asserting TabbedContent.active is load-bearing: activating a tab while a
        widget in the current pane holds focus is silently reverted (t1060), so
        an implementation that forgets the focus handoff passes any weaker
        assertion for the wrong reason.
        """
        async def runner():
            async with self.booted() as (app, pilot):
                tabbed = app.query_one(TabbedContent)
                table = app.query_one("#branches", DataTable)
                table.focus()
                await pilot.pause()
                self.assertIs(app.focused, table)

                await pilot.press("right")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_versions")
                # Focus settles on the bar, from which ↓ re-enters content.
                self.assertIsInstance(app.focused, Tabs)

                await pilot.press("left")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_branches")
        self._run(runner())

    def test_left_right_switch_tabs_from_the_detail_pane(self):
        """Requirement 3's "regardless of what holds focus", asserted at the one
        pane that would otherwise swallow ←/→.

        #detail_scroll is a VerticalScroll: its own left/right bindings scroll
        horizontally, so a design relying on SkipAction fall-through would fail
        exactly here. This is also the positive pin for the deliberate trade-off
        that horizontal scrolling of the detail pane is given up.
        """
        async def runner():
            async with self.booted() as (app, pilot):
                tabbed = app.query_one(TabbedContent)
                detail = app.query_one("#detail_scroll")
                detail.focus()
                await pilot.pause()
                self.assertIs(app.focused, detail)

                await pilot.press("right")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_versions")
                self.assertIsInstance(app.focused, Tabs)

                await pilot.press("left")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_branches")
        self._run(runner())

    def test_detail_scroll_keeps_vertical_arrows(self):
        """↑/↓ on the detail pane stay with the pane (SkipAction fall-through);
        only ←/→ are taken over."""
        async def runner():
            async with self.booted() as (app, pilot):
                detail = app.query_one("#detail_scroll")
                detail.focus()
                await pilot.pause()
                for key in ("up", "down"):
                    await pilot.press(key)
                    await pilot.pause()
                    self.assertIs(app.focused, detail, f"{key} stole focus")
                self.assertEqual(
                    app.query_one(TabbedContent).active, "tab_branches"
                )
        self._run(runner())

    def test_tab_switching_wraps_at_both_ends(self):
        """Wrap (not clamp) — inherited by delegating to Tabs._move_tab, so the
        bar and the content panes behave identically."""
        async def runner():
            async with self.booted() as (app, pilot):
                tabbed = app.query_one(TabbedContent)
                table = app.query_one("#branches", DataTable)
                table.focus()
                await pilot.pause()
                for expected in ("tab_versions", "tab_settings", "tab_branches"):
                    await pilot.press("right")
                    await pilot.pause()
                    await pilot.pause()
                    self.assertEqual(tabbed.active, expected)
                # ...and backwards off the front edge.
                await pilot.press("left")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_settings")
        self._run(runner())

    def test_down_from_the_bar_enters_the_settings_table(self):
        """Inverted by t1223_5: Settings is a real, focusable table now, so it
        is registered in TAB_LIST_IDS and ↓ enters it like the other tabs.

        This is the t1267 coordination point — a focusable pane that is NOT in
        TAB_LIST_IDS would silently lose the t1266 priority arrows."""
        async def runner():
            seams = Seams()
            seams.diff = {"pick": {}}
            async with self.booted(repos=2, seams=seams) as (app, pilot):
                await activate_tab(app, pilot, "tab_settings")
                await self.settle(app, pilot)
                bar = await self._focus_bar(app, pilot)
                await pilot.press("down")
                await pilot.pause()
                self.assertIs(app.focused, app.query_one("#settings", DataTable))
                self.assertEqual(
                    app.query_one(TabbedContent).active, "tab_settings"
                )
        self._run(runner())

    def test_up_falls_through_when_the_mapped_list_is_missing(self):
        """The *other* reason _active_list() returns None.

        A tab mapped to a list id that does not resolve is a degraded lookup, not
        a designed no-op: the key must be handed back to the focused widget
        instead of performing the tab-bar handoff. Discriminating against
        test_up_on_first_row_returns_to_the_tab_bar, which does hand off from the
        very same row.
        """
        async def runner():
            async with self.booted() as (app, pilot):
                table = app.query_one("#branches", DataTable)
                table.focus()
                table.move_cursor(row=0)
                await pilot.pause()
                with mock.patch.dict(
                    syncer_app.TAB_LIST_IDS, {"tab_branches": "no_such_widget"}
                ):
                    await pilot.press("up")
                    await pilot.pause()
                    self.assertIs(app.focused, table)
                    # And ↓ from the bar finds nothing to enter, without raising.
                    bar = await self._focus_bar(app, pilot)
                    await pilot.press("down")
                    await pilot.pause()
                    self.assertIs(app.focused, bar)
        self._run(runner())

    def test_arrows_in_an_upgrade_modal_do_not_switch_tabs(self):
        """The modal gate. An App priority binding fires before a pushed modal's
        own binding, so without check_action returning False the upgrade dialog's
        RadioSet and Input would lose their arrow keys."""
        async def runner():
            async with self.booted() as (app, pilot):
                tabbed = app.query_one(TabbedContent)
                app.push_screen(UpgradeTargetScreen("repo0", "0.0.1"))
                for _ in range(4):
                    await pilot.pause()
                self.assertIsInstance(app.screen, UpgradeTargetScreen)

                # RadioSet's ↑/↓ move the highlight (the "-selected" class), not
                # pressed_index — that only changes on space/enter.
                radio = app.screen.query_one("#upgrade_mode", RadioSet)
                radio.focus()
                await pilot.pause()
                self.assertTrue(
                    radio.query_one("#mode_latest").has_class("-selected")
                )
                await pilot.press("down")
                await pilot.pause()
                self.assertTrue(
                    radio.query_one("#mode_pinned").has_class("-selected"),
                    "RadioSet lost ↓ to the App",
                )

                field = app.screen.query_one("#upgrade_version_input", Input)
                field.disabled = False
                field.value = "0.28.0"
                field.focus()
                for _ in range(3):
                    await pilot.pause()
                field.cursor_position = 4
                await pilot.pause()
                await pilot.press("left")
                await pilot.pause()
                self.assertEqual(
                    field.cursor_position, 3, "Input lost ← to the App"
                )

                self.assertEqual(tabbed.active, "tab_branches")
        self._run(runner())

    def test_nav_actions_inert_only_while_a_screen_is_pushed(self):
        async def runner():
            async with self.booted() as (app, pilot):
                for action in syncer_app.NAV_ACTIONS:
                    self.assertIs(
                        app.check_action(action, ()), True, f"{action} on main"
                    )
                app.push_screen(UpgradeTargetScreen("repo0", "0.0.1"))
                for _ in range(4):
                    await pilot.pause()
                for action in syncer_app.NAV_ACTIONS:
                    self.assertIs(
                        app.check_action(action, ()), False, f"{action} in modal"
                    )
        self._run(runner())

    def test_nav_check_action_is_exception_free_before_mount(self):
        """The modal gate carries no try/except on purpose — a swallowed error
        there could only ever fail OPEN and let a priority arrow hijack a modal
        widget. This pins that no guard is needed: screen_stack is safe pre-mount.
        """
        with mock.patch.object(
            syncer_app, "discover_syncer_sessions", lambda: [sess("/tmp/repo0")]
        ):
            app = syncer_app.SyncerApp(
                argparse.Namespace(interval=3600, no_fetch=True)
            )
        for action in syncer_app.NAV_ACTIONS:
            self.assertIs(app.check_action(action, ()), True, action)

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


# ------------------------------------------------------- versions / upgrade
# t1223_3. Every test here asserts on a REFUSAL path as much as on the happy
# one: the upgrade action rewrites another repository's framework files, so
# "did not spawn" is the property that matters most.


def live(root: str, name: str, session: str, **kwargs) -> AitasksSession:
    return AitasksSession(
        session=session, project_root=Path(root), project_name=name, **kwargs
    )


class VersionsTabTests(_TabbedShellBase):
    """Versions-tab loading, gating and rendering."""

    def test_versions_load_lazily_and_share_one_latest_lookup(self):
        async def runner():
            seams = Seams()
            async with self.booted(
                repos=3, seams=seams, no_fetch=False
            ) as (app, pilot):
                await self.settle(app, pilot)
                # Negative control: staying on Branches costs no network call.
                self.assertEqual(seams.latest_calls, 0)
                await activate_tab(app, pilot, "tab_versions")
                await self.settle(app, pilot)
                # ONE shared resolution for THREE rows, not one per repo.
                self.assertEqual(seams.latest_calls, 1)
                self.assertEqual(len(app.query_one("#versions", DataTable).rows), 3)
        self._run(runner())

    def test_fetch_off_makes_no_network_call(self):
        async def runner():
            seams = Seams()
            async with self.booted(
                repos=2, seams=seams, no_fetch=True
            ) as (app, pilot):
                await activate_tab(app, pilot, "tab_versions")
                await self.settle(app, pilot)
                self.assertEqual(seams.latest_calls, 0)
        self._run(runner())

    def test_version_cells_render_installed_latest_and_status(self):
        async def runner():
            seams = Seams()
            seams.installed = {"/tmp/repo0": "0.27.0", "/tmp/repo1": "9.9.9"}
            seams.latest = ("9.9.9", None)
            async with self.booted(
                repos=2, seams=seams, no_fetch=False
            ) as (app, pilot):
                await activate_tab(app, pilot, "tab_versions")
                await self.settle(app, pilot)
                self.assertEqual(
                    version_cells(app, "v0")["installed"], "0.27.0"
                )
                self.assertEqual(version_cells(app, "v0")["vstatus"], "behind")
                self.assertEqual(
                    version_cells(app, "v1")["vstatus"], "up_to_date"
                )
        self._run(runner())

    def test_version_actions_are_inert_off_the_versions_tab(self):
        async def runner():
            async with self.booted(repos=2) as (app, pilot):
                for action in syncer_app.VERSION_TAB_ACTIONS:
                    self.assertIs(
                        app.check_action(action, ()), False,
                        f"{action} should be inert on Branches",
                    )
                await activate_tab(app, pilot, "tab_versions")
                for action in syncer_app.VERSION_TAB_ACTIONS:
                    self.assertIs(app.check_action(action, ()), True, action)
                await activate_tab(app, pilot, "tab_settings")
                for action in syncer_app.VERSION_TAB_ACTIONS:
                    self.assertIs(
                        app.check_action(action, ()), False,
                        f"{action} should be inert on Settings",
                    )
        self._run(runner())

    def test_branch_actions_still_inert_on_versions(self):
        # The new gate must not have disturbed the pre-existing one.
        async def runner():
            async with self.booted(repos=2) as (app, pilot):
                await activate_tab(app, pilot, "tab_versions")
                for action in syncer_app.BRANCH_TAB_ACTIONS:
                    self.assertIs(app.check_action(action, ()), False, action)
        self._run(runner())

    def test_upgrade_is_fail_closed_without_a_running_app(self):
        # `_active_tab()` degrades to "tab_branches", so a pre-mount check
        # makes the framework-rewriting action inert rather than available.
        sessions = [sess("/tmp/repo0", "repo0")]
        with mock.patch.object(
            syncer_app, "discover_syncer_sessions", lambda: sessions
        ):
            app = syncer_app.SyncerApp(
                argparse.Namespace(interval=3600, no_fetch=True)
            )
        self.assertEqual(app._active_tab(), "tab_branches")
        self.assertIs(app.check_action("upgrade", ()), False)
        self.assertIs(app.check_action("recheck_version", ()), False)


class UpgradeActionTests(_TabbedShellBase):
    """The upgrade flow: capture, gate, refuse, force, spawn, hand off.

    Repo roots are real directories: ``_capture_target`` refuses a target whose
    root is not a directory, so fixture paths have to exist for the flow under
    test to be reached at all.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def root(self, name: str) -> str:
        path = Path(self._tmp.name) / name
        path.mkdir(exist_ok=True)
        return str(path)

    @contextlib.asynccontextmanager
    async def on_versions(self, seams: Seams, sessions=None, repos: int = 2):
        async with self.booted(
            repos=repos, sessions=sessions, seams=seams, no_fetch=False
        ) as (app, pilot):
            await activate_tab(app, pilot, "tab_versions")
            await self.settle(app, pilot)
            yield app, pilot

    @staticmethod
    async def choose_version(app, pilot, version: str = "latest"):
        """Dismiss the version prompt with a chosen value."""
        assert isinstance(app.screen, UpgradeTargetScreen), type(app.screen)
        app.screen.dismiss(version)
        await pilot.pause()

    # ------------------------------------------------------------- refusals

    def test_active_target_refuses_and_never_spawns(self):
        async def runner():
            seams = Seams()
            seams.windows = ([("1", "board")], None)
            sessions = [
                live(self.root("repoA"), "repoA", "sessA"),
                live(self.root("repoB"), "repoB", "sessB"),
            ]
            async with self.on_versions(seams, sessions) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                self.assertIsInstance(app.screen, UpgradeRefusalScreen)
                self.assertIn("board", app.screen.query_one("#upgrade_text", Static).render().plain)
                self.assertEqual(seams.launches, [])
        self._run(runner())

    def test_failed_enumeration_refuses_and_never_spawns(self):
        # Load-bearing negative control. get_tmux_windows() reports a tmux
        # failure as [], which detect_target_activity would read as "idle" —
        # feeding the checked variant's error through as `unknown` is the only
        # thing keeping this path fail-closed.
        async def runner():
            seams = Seams()
            seams.windows = ([], "tmux list-windows failed (rc=-1)")
            sessions = [
                live(self.root("repoA"), "repoA", "sessA"),
                live(self.root("repoB"), "repoB", "sessB"),
            ]
            async with self.on_versions(seams, sessions) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                self.assertIsInstance(app.screen, UpgradeRefusalScreen)
                self.assertIn(
                    "tmux-enumeration-failed",
                    app.screen.query_one("#upgrade_text", Static).render().plain,
                )
                self.assertEqual(seams.launches, [])
        self._run(runner())

    def test_registry_only_target_makes_no_tmux_enumeration_call(self):
        # is_live=False repos have no session to interrogate; asking would be a
        # tmux round-trip for a guaranteed-empty answer. Also exercises the
        # captured-target path for a session object that is never re-read.
        async def runner():
            seams = Seams()
            seams.tmux_sessions = []
            sessions = [
                live(self.root("repoA"), "repoA", "sessA"),
                live(self.root("repoB"), "repoB", "sessB", is_live=False),
            ]
            async with self.on_versions(seams, sessions) as (app, pilot):
                table = app.query_one("#versions", DataTable)
                table.move_cursor(row=1)
                await pilot.pause()
                seams.window_calls.clear()
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                # Straight to the confirmation: classified idle without asking.
                self.assertIsInstance(app.screen, UpgradeConfirmScreen)
                self.assertEqual(seams.window_calls, [])
                app.screen.dismiss(True)
                await pilot.pause()
                self.assertEqual(len(seams.launches), 1)
                _cmd, config = seams.launches[0]
                self.assertEqual(config.session, "sessB")
                self.assertEqual(config.cwd, self.root("repoB"))
                self.assertTrue(config.new_session)  # sessB is not running
        self._run(runner())

    # ------------------------------------------------------------- spawning

    def test_idle_live_target_spawns_once_with_the_built_command(self):
        async def runner():
            seams = Seams()
            seams.tmux_sessions = ["sessA"]
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot, "0.29.0")
                self.assertIsInstance(app.screen, UpgradeConfirmScreen)
                app.screen.dismiss(True)
                await pilot.pause()
                self.assertEqual(len(seams.launches), 1)
                command, config = seams.launches[0]
                expected, _ = syncer_app.build_upgrade_command(
                    Path(self.root("repoA")), "0.29.0"
                )
                self.assertEqual(command, expected)
                self.assertEqual(config.cwd, self.root("repoA"))
                self.assertTrue(config.new_window)
                self.assertFalse(config.new_session)  # sessA already running
        self._run(runner())

    def test_cancelling_the_confirmation_never_spawns(self):
        async def runner():
            seams = Seams()
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                app.screen.dismiss(False)
                await pilot.pause()
                self.assertEqual(seams.launches, [])
        self._run(runner())

    def test_captured_target_survives_cursor_and_row_map_mutation(self):
        # The flow spans several modal callbacks. Re-resolving the target in a
        # later one would upgrade whatever the cursor happens to be on by then.
        async def runner():
            seams = Seams()
            sessions = [
                live(self.root("repoA"), "repoA", "sessA"),
                live(self.root("repoB"), "repoB", "sessB"),
            ]
            async with self.on_versions(seams, sessions) as (app, pilot):
                table = app.query_one("#versions", DataTable)
                table.move_cursor(row=0)
                await pilot.pause()
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                self.assertIsInstance(app.screen, UpgradeConfirmScreen)
                # Move the cursor AND repoint the lookup map mid-flow, both
                # pointing at repoB — so EVERY re-resolution path (cursor key
                # lookup and the positional fallback alike) would yield repoB.
                # Only using the captured target still yields repoA.
                table.move_cursor(row=1)
                app._version_rows_by_key = {
                    "v0": app._version_rows[1],
                    "v1": app._version_rows[1],
                }
                await pilot.pause()
                app.screen.dismiss(True)
                await pilot.pause()
                self.assertEqual(len(seams.launches), 1)
                _cmd, config = seams.launches[0]
                self.assertEqual(config.cwd, self.root("repoA"))
                self.assertEqual(config.session, "sessA")
        self._run(runner())

    # ---------------------------------------------------------------- force

    def test_force_aborts_when_the_fresh_probe_disagrees(self):
        # What the user accepts must be the CURRENT state, not what the refusal
        # happened to show a few seconds earlier.
        async def runner():
            seams = Seams()
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            seams.windows_queue = [
                ([("1", "board")], None),                    # initial probe
                ([("1", "board"), ("2", "monitor")], None),  # re-probe
                ([("1", "board"), ("2", "monitor")], None),  # re-shown refusal
            ]
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                self.assertIsInstance(app.screen, UpgradeRefusalScreen)
                app.screen.dismiss("force")
                await pilot.pause()
                # Aborted back to a refusal naming the NEW state, not a force
                # confirmation, and nothing was launched.
                self.assertIsInstance(app.screen, UpgradeRefusalScreen)
                self.assertIn(
                    "monitor", app.screen.query_one("#upgrade_text", Static).render().plain
                )
                self.assertEqual(seams.launches, [])
        self._run(runner())

    def test_force_confirmation_is_a_separate_destructive_step(self):
        async def runner():
            seams = Seams()
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            seams.windows = ([("1", "board")], None)
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                app.screen.dismiss("force")
                await pilot.pause()
                # A second, distinct dialog — force is never the refusal's own
                # default action.
                self.assertIsInstance(app.screen, ForceConfirmScreen)
                self.assertIn(
                    "board", app.screen.query_one("#upgrade_text", Static).render().plain
                )
                self.assertEqual(seams.launches, [])
                app.screen.dismiss(True)
                await pilot.pause()
                self.assertEqual(len(seams.launches), 1)
        self._run(runner())

    def test_cancelling_the_force_confirmation_never_spawns(self):
        async def runner():
            seams = Seams()
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            seams.windows = ([("1", "board")], None)
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                app.screen.dismiss("force")
                await pilot.pause()
                app.screen.dismiss(False)
                await pilot.pause()
                self.assertEqual(seams.launches, [])
        self._run(runner())

    # ----------------------------------------------------------- self-target

    def test_self_target_hands_off_and_never_spawns(self):
        async def runner():
            seams = Seams()
            seams.self_root = Path(self.root("repoA"))
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            with tempfile.TemporaryDirectory() as tmp:
                handoff = str(Path(tmp) / "request.json")
                with mock.patch.dict(
                    os.environ, {"AIT_SYNCER_HANDOFF": handoff}
                ):
                    async with self.on_versions(
                        seams, sessions, repos=1
                    ) as (app, pilot):
                        app.action_upgrade()
                        await pilot.pause()
                        await self.choose_version(app, pilot, "0.29.0")
                        self.assertIsInstance(app.screen, HandoffConfirmScreen)
                        app.screen.dismiss(True)
                        await pilot.pause()
                        self.assertEqual(seams.launches, [])
                        with open(handoff, encoding="utf-8") as fh:
                            payload = json.load(fh)
                        self.assertEqual(
                            set(payload), {"root", "version"}
                        )
                        self.assertEqual(payload["version"], "0.29.0")
                        self.assertEqual(payload["root"], self.root("repoA"))
        self._run(runner())

    def test_self_target_activity_is_advisory_not_a_refusal(self):
        # The syncer's own repo nearly always has live framework windows.
        # Refusing on that basis would leave the exit-then-upgrade handoff —
        # the only safe path for this repo — reachable solely through the
        # destructive force override.
        async def runner():
            seams = Seams()
            seams.self_root = Path(self.root("repoA"))
            seams.windows = ([("1", "board"), ("2", "monitor")], None)
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            with tempfile.TemporaryDirectory() as tmp:
                handoff = str(Path(tmp) / "request.json")
                with mock.patch.dict(
                    os.environ, {"AIT_SYNCER_HANDOFF": handoff}
                ):
                    async with self.on_versions(
                        seams, sessions, repos=1
                    ) as (app, pilot):
                        app.action_upgrade()
                        await pilot.pause()
                        await self.choose_version(app, pilot)
                        self.assertIsInstance(app.screen, HandoffConfirmScreen)
                        body = app.screen.query_one("#upgrade_text", Static).render().plain
                        self.assertIn("board", body)
                        self.assertIn("monitor", body)
                        app.screen.dismiss(True)
                        await pilot.pause()
                        self.assertTrue(Path(handoff).exists())
                        self.assertEqual(seams.launches, [])
        self._run(runner())

    def test_self_target_without_the_wrapper_env_var_refuses(self):
        async def runner():
            seams = Seams()
            seams.self_root = Path(self.root("repoA"))
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            env = {k: v for k, v in os.environ.items()}
            env.pop("AIT_SYNCER_HANDOFF", None)
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                os.environ, env, clear=True
            ):
                async with self.on_versions(
                    seams, sessions, repos=1
                ) as (app, pilot):
                    notices = []
                    with mock.patch.object(
                        app, "notify",
                        lambda msg, **kw: notices.append(str(msg)),
                    ):
                        app.action_upgrade()
                        await pilot.pause()
                        await self.choose_version(app, pilot)
                        await pilot.pause()
                    # Never spawns, never writes, and says what to do instead.
                    self.assertEqual(seams.launches, [])
                    self.assertEqual(list(Path(tmp).iterdir()), [])
                    self.assertTrue(
                        any("ait syncer" in n for n in notices), notices
                    )
        self._run(runner())

    def test_self_target_rule_is_never_force_bypassable(self):
        # A busy self target reaches the handoff confirmation, never the
        # refusal/force pair — so there is no path on which a self repo is
        # spawned into.
        async def runner():
            seams = Seams()
            seams.self_root = Path(self.root("repoA"))
            seams.windows = ([("1", "board")], None)
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            with tempfile.TemporaryDirectory() as tmp:
                with mock.patch.dict(
                    os.environ,
                    {"AIT_SYNCER_HANDOFF": str(Path(tmp) / "request.json")},
                ):
                    async with self.on_versions(
                        seams, sessions, repos=1
                    ) as (app, pilot):
                        app.action_upgrade()
                        await pilot.pause()
                        await self.choose_version(app, pilot)
                        self.assertNotIsInstance(
                            app.screen, UpgradeRefusalScreen
                        )
                        self.assertNotIsInstance(app.screen, ForceConfirmScreen)
        self._run(runner())

    # ------------------------------------------------------------ lifecycle

    def test_lifecycle_never_renders_an_unobserved_success(self):
        async def runner():
            seams = Seams()
            seams.installed = {self.root("repoA"): "0.27.0"}
            seams.latest = ("0.29.0", None)
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot, "0.29.0")
                app.screen.dismiss(True)
                await pilot.pause()
                cells = version_cells(app, "v0")
                self.assertEqual(cells["state"], "upgrading…")
                # The OLD version, marked stale — never the requested one.
                self.assertEqual(
                    cells["installed"], "0.27.0" + syncer_app.STALE_MARKER
                )
                # Pane gone: the result is unknown, not a success.
                seams.pane_alive = False
                app.action_recheck_version()
                await self.settle(app, pilot)
                self.assertEqual(
                    version_cells(app, "v0")["state"], "re-check needed"
                )
        self._run(runner())

    def test_uncapturable_pane_pid_goes_straight_to_result_unknown(self):
        # Without a pid the run can never be observed, so it must not sit in a
        # state the app can never leave.
        async def runner():
            seams = Seams()
            seams.spawn_result = (None, None)
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                app.screen.dismiss(True)
                await pilot.pause()
                self.assertEqual(
                    version_cells(app, "v0")["state"], "re-check needed"
                )
        self._run(runner())

    def test_launch_failure_records_no_run(self):
        async def runner():
            seams = Seams()
            seams.spawn_result = (None, "tmux new-window failed (rc=1)")
            sessions = [live(self.root("repoA"), "repoA", "sessA")]
            async with self.on_versions(seams, sessions, repos=1) as (app, pilot):
                app.action_upgrade()
                await pilot.pause()
                await self.choose_version(app, pilot)
                app.screen.dismiss(True)
                await pilot.pause()
                self.assertEqual(app._upgrades, {})
                self.assertEqual(version_cells(app, "v0")["state"], "")
        self._run(runner())


class SettingsTabTests(_TabbedShellBase):
    """The Settings tab and its push action (t1223_5), against a booted app."""

    def repos(self, n: int = 2) -> list[AitasksSession]:
        return [sess(f"/tmp/srepo{i}", f"srepo{i}") for i in range(n)]

    @staticmethod
    def matrix(sessions, per_op):
        """{op: {session_key: OperationValue}} from a positional spec."""
        return {
            op: {s.key: values[i] for i, s in enumerate(sessions) if values[i]}
            for op, values in per_op.items()
        }

    @contextlib.asynccontextmanager
    async def on_settings(self, seams, sessions=None):
        sessions = sessions if sessions is not None else self.repos()
        async with self.booted(sessions=sessions, seams=seams) as (app, pilot):
            await activate_tab(app, pilot, "tab_settings")
            await self.settle(app, pilot)
            yield app, pilot

    async def drain(self, app, pilot):
        """Settle repeatedly: the push chains two sequential thread workers."""
        for _ in range(5):
            await self.settle(app, pilot)

    async def push(self, app, pilot, source, dests, layer="project"):
        """Drive source -> destinations -> layer, then let the workers run."""
        app.action_push_setting()
        await pilot.pause()
        self.assertIsInstance(app.screen, SettingsSourceScreen)
        app.screen.dismiss(source)
        await pilot.pause()
        self.assertIsInstance(app.screen, SettingsDestinationsScreen)
        app.screen.dismiss(tuple(dests))
        await pilot.pause()
        self.assertIsInstance(app.screen, SettingsLayerScreen)
        app.screen.dismiss(layer)
        await self.drain(app, pilot)

    @staticmethod
    def result_text(app) -> str:
        return app.screen.query_one("#settings_text", Static).render().plain

    # ---- rendering

    def test_settings_cells_render_values_with_provenance_suffixes(self):
        """Render-level: what the user actually sees, suffixes included."""
        sessions = self.repos()
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/1", "project")],
            "qa": [ov("x/2", "local"), ov("x/3", "builtin")],
        })
        async def runner():
            async with self.on_settings(seams, sessions) as (app, _pilot):
                self.assertEqual(
                    settings_cells(app, "s0"), ["", "pick", "x/1", "x/1"]
                )
                self.assertEqual(
                    settings_cells(app, "s1"),
                    ["≠", "qa", "x/2 (local)", "x/3 (default)"],
                )
        self._run(runner())

    # ---- lazy load

    def test_settings_load_lazily(self):
        """Zero cost for a user who never opens the tab; exactly one read when
        they do."""
        seams = Seams()
        async def runner():
            async with self.booted(repos=2, seams=seams) as (app, pilot):
                await self.settle(app, pilot)
                self.assertEqual(seams.diff_calls, [])
                await activate_tab(app, pilot, "tab_settings")
                await self.settle(app, pilot)
                self.assertEqual(len(seams.diff_calls), 1)
        self._run(runner())

    # ---- gating

    def test_settings_actions_are_inert_off_the_settings_tab(self):
        seams = Seams()
        async def runner():
            async with self.booted(repos=2, seams=seams) as (app, pilot):
                for action in syncer_app.SETTINGS_TAB_ACTIONS:
                    self.assertIs(
                        app.check_action(action, ()), False,
                        f"{action} should be inert on Branches",
                    )
                await activate_tab(app, pilot, "tab_versions")
                for action in syncer_app.SETTINGS_TAB_ACTIONS:
                    self.assertIs(
                        app.check_action(action, ()), False,
                        f"{action} should be inert on Versions",
                    )
        self._run(runner())

    def test_push_setting_is_fail_closed_without_a_running_app(self):
        with mock.patch.object(
            syncer_app, "discover_syncer_sessions", lambda: self.repos()
        ):
            app = syncer_app.SyncerApp(
                argparse.Namespace(interval=3600, no_fetch=True)
            )
            self.assertEqual(app._active_tab(), "tab_branches")
            self.assertIs(app.check_action("push_setting", ()), False)

    def test_push_gating_by_row_state(self):
        """The tab gate is not enough: with no selectable row (not loaded yet,
        or an empty matrix) and on an all-conflict row there is no target to
        build, so the key is dimmed rather than live.

        `None`, not `False` — same split the ref gate uses: right tab, wrong
        row."""
        sessions = self.repos()
        seams = Seams()
        seams.diff = {}                       # zero-operation matrix
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                self.assertEqual(app._settings_rows, [])
                self.assertIsNone(app.check_action("push_setting", ()))
                # reload stays available so the user can retry
                self.assertIs(app.check_action("reload_settings", ()), True)

                # An all-conflict row: rows exist, none can be a source.
                seams.diff = self.matrix(sessions, {
                    "pick": [ov("x/1", "conflict"), ov("x/2", "conflict")],
                })
                app.action_reload_settings()
                await self.settle(app, pilot)
                self.assertEqual(len(app._settings_rows), 1)
                self.assertIsNone(app.check_action("push_setting", ()))

                # One usable source is enough to enable it.
                seams.diff = self.matrix(sessions, {
                    "pick": [ov("x/1", "conflict"), ov("x/2", "project")],
                })
                app.action_reload_settings()
                await self.settle(app, pilot)
                self.assertIs(app.check_action("push_setting", ()), True)
        self._run(runner())

    def test_action_push_setting_guards_itself_when_invoked_directly(self):
        """check_action gates the KEY; the action is also called directly (this
        suite does exactly that), so the method re-checks or it would walk into
        a flow with no target."""
        sessions = self.repos()
        seams = Seams()
        seams.diff = {}
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                notices = []
                with mock.patch.object(
                    app, "notify", lambda msg, **kw: notices.append(str(msg))
                ):
                    app.action_push_setting()
                    await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1)  # no modal pushed
                self.assertTrue(any("not loaded" in n for n in notices), notices)

                seams.diff = self.matrix(sessions, {
                    "pick": [ov("x/1", "conflict"), ov("x/2", "conflict")],
                })
                app.action_reload_settings()
                await self.settle(app, pilot)
                notices.clear()
                with mock.patch.object(
                    app, "notify", lambda msg, **kw: notices.append(str(msg))
                ):
                    app.action_push_setting()
                    await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1)
                self.assertTrue(any("usable value" in n for n in notices), notices)
        self._run(runner())

    def test_single_repo_renders_read_only_and_cannot_push(self):
        sessions = self.repos(1)
        seams = Seams()
        seams.diff = self.matrix(sessions, {"pick": [ov("x/1", "project")]})
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                self.assertFalse(app.multi_repo)
                self.assertEqual(settings_cells(app, "s0"), ["", "pick", "x/1"])
                # False, not None: with one repo there is nowhere to push at
                # all, so the key leaves the footer entirely.
                self.assertIs(app.check_action("push_setting", ()), False)
                notices = []
                with mock.patch.object(
                    app, "notify", lambda msg, **kw: notices.append(str(msg))
                ):
                    app.action_push_setting()
                    await pilot.pause()
                self.assertEqual(seams.plans, [])
                self.assertEqual(len(app.screen_stack), 1)
        self._run(runner())

    def test_footer_relabels_the_shared_keys_per_tab(self):
        """`p` and `c` are each bound twice (push/push_setting,
        recheck_version/reload_settings) and the tab gate picks one. Sharing
        them beats inventing uppercase variants — but it only works because
        check_action returns False (drop), and because the activation handler
        calls refresh_bindings(); check_action alone never relabels a footer."""
        seams = Seams()
        async def runner():
            async with self.booted(repos=2, seams=seams) as (app, pilot):
                state = footer_state(app)
                self.assertIn("push", state)              # Branches
                self.assertNotIn("push_setting", state)
                await activate_tab(app, pilot, "tab_versions")
                await self.settle(app, pilot)
                state = footer_state(app)
                self.assertIn("recheck_version", state)
                self.assertNotIn("reload_settings", state)
                self.assertNotIn("push_setting", state)
                await activate_tab(app, pilot, "tab_settings")
                await self.settle(app, pilot)
                state = footer_state(app)
                self.assertIn("reload_settings", state)
                self.assertIn("push_setting", state)
                self.assertNotIn("recheck_version", state)
                self.assertNotIn("push", state)
        self._run(runner())

    def test_the_shared_p_key_falls_through_to_the_right_action_per_tab(self):
        """The load-bearing half of sharing `p`: a REAL keypress must reach
        push_setting on Settings and git-push on Branches.

        Textual only falls through to the next binding for a key whose
        check_action returns False — the tab gate's `False` (drop) rather than
        the ref gate's `None` (dim) is what makes that true here."""
        sessions = self.repos()
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/9", "project")],
        })
        async def runner():
            async with self.booted(sessions=sessions, seams=seams) as (app, pilot):
                # Branches: `p` is git-push, and must NOT open the wizard.
                with mock.patch.object(app, "action_push") as pushed:
                    await pilot.press("p")
                    await pilot.pause()
                    self.assertEqual(pushed.call_count, 1)
                self.assertEqual(len(app.screen_stack), 1)

                await activate_tab(app, pilot, "tab_settings")
                await self.settle(app, pilot)
                # Settings: the same key opens the push wizard instead.
                with mock.patch.object(app, "action_push") as pushed:
                    await pilot.press("p")
                    for _ in range(4):
                        await pilot.pause()
                    self.assertEqual(pushed.call_count, 0)
                self.assertIsInstance(app.screen, SettingsSourceScreen)
        self._run(runner())

    # ---- per-repo degradation

    def test_one_corrupt_repo_does_not_blank_the_tab(self):
        """diff_across_repos aborts globally, so without the shrink-and-retry
        fallback a single broken repo would leave the whole matrix empty."""
        sessions = self.repos(3)
        seams = Seams()
        seams.unreadable_roots = {"/tmp/srepo1"}
        good = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), None, ov("x/2", "project")],
        })
        seams.diff_queue = [syncer_app.DestConfigUnreadable("boom"), good]
        async def runner():
            async with self.on_settings(seams, sessions) as (app, _pilot):
                cells = settings_cells(app, "s0")
                self.assertEqual(cells[2], "x/1")
                self.assertEqual(cells[3], "unavailable")
                self.assertEqual(cells[4], "x/2")
                self.assertEqual(
                    set(app._settings_unreadable), {sessions[1].key}
                )
        self._run(runner())

    def test_a_raced_corruption_costs_only_the_repo_that_raced(self):
        """A repo can break BETWEEN the probe sweep and the retry. Marking
        everything unreadable then would erase provably-good columns — exactly
        the per-repo degradation the fallback exists to provide."""
        sessions = self.repos(3)
        seams = Seams()
        final = self.matrix(sessions, {"pick": [ov("x/1", "project"), None, None]})
        # 1st call raises (repo1 bad), 2nd raises again (repo2 broke since),
        # 3rd succeeds with repo0 alone.
        seams.diff_queue = [
            syncer_app.DestConfigUnreadable("boom"),
            syncer_app.DestConfigUnreadable("boom again"),
            final,
        ]
        state = {"bad": {"/tmp/srepo1"}}

        def probe(root):
            seams.probe_calls.append(str(root))
            if str(root) in state["bad"]:
                raise syncer_app.DestConfigUnreadable(f"{root} is corrupt")
            # repo2 breaks after the first sweep has cleared it
            state["bad"] = {"/tmp/srepo1", "/tmp/srepo2"}
            return {}

        seams.read_operation_defaults = probe
        async def runner():
            async with self.on_settings(seams, sessions) as (app, _pilot):
                cells = settings_cells(app, "s0")
                self.assertEqual(cells[2], "x/1")       # survivor keeps its data
                self.assertEqual(cells[3], "unavailable")
                self.assertEqual(cells[4], "unavailable")
                self.assertEqual(
                    set(app._settings_unreadable),
                    {sessions[1].key, sessions[2].key},
                )
        self._run(runner())

    def test_an_unattributable_failure_blames_no_repo_and_terminates(self):
        """If the sweep finds no offender we have not established that any repo
        is broken, so none is marked — and the loop must still terminate."""
        sessions = self.repos(2)
        seams = Seams()
        seams.diff_queue = [
            syncer_app.DestConfigUnreadable("boom") for _ in range(10)
        ]
        async def runner():
            async with self.on_settings(seams, sessions) as (app, _pilot):
                self.assertEqual(app._settings_unreadable, {})
                self.assertIsNotNone(app._settings_unattributed)
                # Bounded at len(sessions) + 2 attempts, so an unbounded loop
                # fails here instead of hanging.
                self.assertLessEqual(len(seams.diff_calls), len(sessions) + 2)
        self._run(runner())

    def test_a_worker_level_failure_still_unsticks_the_refresh_flag(self):
        """An exception escaping the worker never reaches _finish_settings, so
        `_settings_active` would stay true and every later request would park in
        the pending slot — `c` silently dead for the rest of the session.

        The same hazard `_refresh_worker` documents for cancellation. Found by
        the M7 mutation, which hung instead of failing because the stuck flag
        made the next settle() wait forever."""
        sessions = self.repos()
        seams = Seams()
        seams.diff_queue = [RuntimeError("unexpected boom")]
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                self.assertFalse(
                    app._settings_active, "refresh flag left stuck after a crash"
                )
                # ...and a reload still starts a NEW worker rather than parking.
                seams.diff = self.matrix(sessions, {
                    "pick": [ov("x/1", "project"), ov("x/1", "project")],
                })
                before = len(seams.diff_calls)
                app.action_reload_settings()
                await self.settle(app, pilot)
                self.assertGreater(len(seams.diff_calls), before)
                self.assertEqual(settings_cells(app, "s0")[2], "x/1")
        self._run(runner())

    # ---- push outcomes

    def _two_repo_seams(self, sessions, outcome=None):
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/9", "project")],
        })
        if outcome is not None:
            seams.plan_outcomes[str(sessions[1].project_root)] = outcome
        return seams

    def test_ok_applies_once_with_the_chosen_layer(self):
        sessions = self.repos()
        seams = self._two_repo_seams(sessions)
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                await self.push(
                    app, pilot, sessions[0].key, [sessions[1].key], "local"
                )
                self.assertEqual(len(seams.applies), 1)
                value, root, operation, layer, clear = seams.applies[0]
                self.assertEqual(value, "x/1")
                self.assertEqual(root, "/tmp/srepo1")
                self.assertEqual(operation, "pick")
                self.assertEqual(layer, "local")
                self.assertFalse(clear)
        self._run(runner())

    def test_noop_writes_nothing(self):
        sessions = self.repos()
        seams = self._two_repo_seams(sessions, PushOutcome(kind="noop"))
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                await self.push(app, pilot, sessions[0].key, [sessions[1].key])
                self.assertEqual(seams.applies, [])
                self.assertIn("already matches", self.result_text(app))
        self._run(runner())

    def test_masked_three_way_routing(self):
        """Each branch reaches exactly one call shape — cancel writes nothing,
        local writes local, clear+project clears the mask."""
        sessions = self.repos()
        for choice, expected in (
            ("cancel", None),
            ("local", ("local", False)),
            ("clear", ("project", True)),
        ):
            seams = self._two_repo_seams(
                sessions, PushOutcome(kind="masked", masking_value="x/7")
            )
            async def runner(choice=choice, expected=expected, seams=seams):
                async with self.on_settings(seams, sessions) as (app, pilot):
                    app.action_push_setting()
                    await pilot.pause()
                    app.screen.dismiss(sessions[0].key)
                    await pilot.pause()
                    app.screen.dismiss((sessions[1].key,))
                    await pilot.pause()
                    app.screen.dismiss("project")
                    await self.drain(app, pilot)
                    self.assertIsInstance(app.screen, SettingsMaskedScreen)
                    self.assertIn("x/7", self.result_text(app))
                    app.screen.dismiss(choice)
                    await self.drain(app, pilot)
                    if expected is None:
                        self.assertEqual(seams.applies, [], choice)
                    else:
                        self.assertEqual(len(seams.applies), 1, choice)
                        _v, _r, _o, layer, clear = seams.applies[0]
                        self.assertEqual((layer, clear), expected, choice)
            self._run(runner())

    def test_rejected_names_its_reason_and_a_sibling_still_applies(self):
        sessions = self.repos(3)
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/9", "project"),
                     ov("x/9", "project")],
        })
        seams.plan_outcomes["/tmp/srepo1"] = PushOutcome(
            kind="rejected", reason="model_not_in_dest_catalog"
        )
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                await self.push(
                    app, pilot, sessions[0].key,
                    [sessions[1].key, sessions[2].key],
                )
                self.assertEqual(
                    [a[1] for a in seams.applies], ["/tmp/srepo2"]
                )
                text = self.result_text(app)
                self.assertIn("model_not_in_dest_catalog", text)
                self.assertIn("srepo2", text)
        self._run(runner())

    def test_a_raising_apply_is_reported_and_siblings_still_process(self):
        sessions = self.repos(3)
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/9", "project"),
                     ov("x/9", "project")],
        })
        seams.apply_error["/tmp/srepo1"] = OSError("disk on fire")
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                await self.push(
                    app, pilot, sessions[0].key,
                    [sessions[1].key, sessions[2].key],
                )
                self.assertEqual(len(seams.applies), 2)   # both attempted
                text = self.result_text(app)
                self.assertIn("disk on fire", text)
                self.assertIn("srepo1", text)
        self._run(runner())

    def test_a_raising_plan_is_reported_and_siblings_still_process(self):
        """The planning phase needs the same per-destination boundary as the
        apply phase: an unhandled exception there kills the worker, so the
        summary never opens and later destinations are never considered."""
        sessions = self.repos(3)
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/9", "project"),
                     ov("x/9", "project")],
        })
        real_plan = seams.plan_push

        def exploding_plan(value, dest_root, operation, layer):
            if str(dest_root) == "/tmp/srepo1":
                raise RuntimeError("resolver exploded")
            return real_plan(value, dest_root, operation, layer)

        seams.plan_push = exploding_plan
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                await self.push(
                    app, pilot, sessions[0].key,
                    [sessions[1].key, sessions[2].key],
                )
                self.assertIsInstance(app.screen, SettingsPushResultScreen)
                text = self.result_text(app)
                self.assertIn("resolver exploded", text)
                # The sibling was still planned AND applied.
                self.assertEqual([a[1] for a in seams.applies], ["/tmp/srepo2"])
        self._run(runner())

    def test_push_partial_error_invites_a_retry_not_success_or_failure(self):
        sessions = self.repos()
        seams = self._two_repo_seams(sessions)
        seams.apply_error["/tmp/srepo1"] = PushPartialError(
            "pick", "x/7", OSError("nope")
        )
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                await self.push(app, pilot, sessions[0].key, [sessions[1].key])
                text = self.result_text(app)
                self.assertIn("retry to finish", text)
                self.assertIn("x/7", text)
                self.assertNotIn("applied to", text)
        self._run(runner())

    # ---- source / destination selection

    def test_source_picker_offers_only_usable_repos(self):
        """A conflicted repo has no coherent value to copy. Offering it would
        push None, which plan_push turns into malformed_agent_string for every
        destination — blaming the value instead of saying none existed."""
        sessions = self.repos(3)
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "conflict"), ov("x/2", "local"),
                     ov("x/3", "project")],
        })
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, SettingsSourceScreen)
                self.assertEqual(
                    [k for k, _l, _v in screen._options],
                    [sessions[1].key, sessions[2].key],
                )
                # Preselected = first ELIGIBLE, not column 0.
                self.assertEqual(screen._resolve(), sessions[1].key)
                app.screen.dismiss(screen._resolve())
                await pilot.pause()
                app.screen.dismiss((sessions[2].key,))
                await pilot.pause()
                app.screen.dismiss("project")
                await self.drain(app, pilot)
                self.assertEqual(seams.applies[0][0], "x/2")
                self.assertNotIn(
                    "malformed_agent_string", self.result_text(app)
                )
        self._run(runner())

    def test_the_source_repo_is_never_a_destination(self):
        sessions = self.repos(3)
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/2", "project"),
                     ov("x/3", "project")],
        })
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                await pilot.pause()
                app.screen.dismiss(sessions[1].key)      # source = srepo1
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, SettingsDestinationsScreen)
                self.assertEqual(
                    [k for k, _l in screen._destinations],
                    [sessions[0].key, sessions[2].key],
                )
                screen.dismiss((sessions[0].key, sessions[2].key))
                await pilot.pause()
                app.screen.dismiss("project")
                await self.drain(app, pilot)
                planned = [p[1] for p in seams.plans]
                applied = [a[1] for a in seams.applies]
                self.assertNotIn("/tmp/srepo1", planned)
                self.assertNotIn("/tmp/srepo1", applied)
                self.assertNotIn("srepo1", self.result_text(app))
        self._run(runner())

    def test_a_repo_ineligible_as_a_source_is_still_a_destination(self):
        """Destinations are NOT filtered by source-eligibility: a conflicted
        repo is exactly the one a coherent write fixes."""
        sessions = self.repos()
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/2", "conflict")],
        })
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                await pilot.pause()
                app.screen.dismiss(sessions[0].key)
                await pilot.pause()
                screen = app.screen
                self.assertEqual(
                    [k for k, _l in screen._destinations], [sessions[1].key]
                )
                screen.dismiss((sessions[1].key,))
                await pilot.pause()
                app.screen.dismiss("project")
                await self.drain(app, pilot)
                self.assertEqual([a[1] for a in seams.applies], ["/tmp/srepo1"])
        self._run(runner())

    # ---- wizard keyboard behaviour

    def _wizard_seams(self, sessions):
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/2", "project"),
                     ov("x/3", "project")],
        })
        return seams

    def test_choice_widgets_hold_focus_on_mount(self):
        """Reported: the lists only responded to ↑/↓ after clicking into them.

        Cause: every dialog focused Cancel (the upgrade_screens convention),
        so the arrows landed on a Button that ignores them. Each wizard step
        focuses its CHOICE widget instead, and ↑/↓ move immediately — asserted
        with real keypresses and no click."""
        sessions = self.repos(3)
        seams = self._wizard_seams(sessions)
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                for _ in range(4):
                    await pilot.pause()
                radio = app.screen.query_one("#settings_source", RadioSet)
                self.assertIs(app.focused, radio)
                # ↑/↓ move the highlight without any click first; Space is
                # what commits (measured — arrows leave pressed_index alone).
                self.assertEqual(radio.pressed_index, 0)
                await pilot.press("down")
                await pilot.press("space")
                await pilot.pause()
                self.assertEqual(radio.pressed_index, 1)

                await pilot.press("enter")
                await pilot.pause()
                self.assertIsInstance(app.screen, SettingsDestinationsScreen)
                self.assertIs(
                    app.focused,
                    app.screen.query_one("#settings_dest_list", SelectionList),
                )
        self._run(runner())

    def test_enter_advances_each_step_and_esc_steps_back(self):
        """Enter = forward, Esc = back one step, with the earlier choice still
        selected when you return. Driven entirely by the keyboard."""
        sessions = self.repos(3)
        seams = self._wizard_seams(sessions)
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                for _ in range(4):
                    await pilot.pause()
                # Step 1: choose srepo1 (not the default) and advance.
                await pilot.press("down")
                await pilot.press("space")
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsInstance(app.screen, SettingsDestinationsScreen)

                # Step 2: tick the first destination and advance.
                await pilot.press("space")
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsInstance(app.screen, SettingsLayerScreen)

                # Esc goes BACK to destinations with the tick preserved.
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(app.screen, SettingsDestinationsScreen)
                self.assertEqual(
                    len(app.screen.query_one(
                        "#settings_dest_list", SelectionList).selected),
                    1,
                )
                # Esc again goes back to the source, still on srepo1.
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(app.screen, SettingsSourceScreen)
                self.assertEqual(
                    app.screen.query_one("#settings_source", RadioSet)
                    .pressed_index,
                    1,
                )
                # Esc on step 1 cancels the whole push — nothing planned.
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1)
                self.assertEqual(seams.plans, [])
        self._run(runner())

    def test_enter_on_an_untouched_layer_step_does_not_pick_a_layer(self):
        """The layer is always asked with NO default, so a blind Enter must
        report "choose one" rather than silently writing to project."""
        sessions = self.repos(3)
        seams = self._wizard_seams(sessions)
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                for _ in range(4):
                    await pilot.pause()
                await pilot.press("enter")          # accept default source
                await pilot.pause()
                await pilot.press("space")          # tick a destination
                await pilot.press("enter")
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, SettingsLayerScreen)
                radio = screen.query_one("#settings_layer", RadioSet)
                self.assertIn(radio.pressed_index, (None, -1))  # no default

                await pilot.press("enter")
                await pilot.pause()
                self.assertIs(app.screen, screen)   # did NOT advance
                self.assertIn(
                    "Choose a layer",
                    screen.query_one("#settings_error", Static).render().plain,
                )
                self.assertEqual(seams.plans, [])   # and nothing was planned

                # Select explicitly, then Enter advances and plans.
                await pilot.press("space")
                await pilot.press("enter")
                await self.drain(app, pilot)
                self.assertEqual([p[3] for p in seams.plans], ["project"])
        self._run(runner())

    def test_enter_with_no_destination_ticked_does_not_advance(self):
        sessions = self.repos(3)
        seams = self._wizard_seams(sessions)
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                app.action_push_setting()
                for _ in range(4):
                    await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, SettingsDestinationsScreen)
                await pilot.press("enter")          # nothing ticked
                await pilot.pause()
                self.assertIs(app.screen, screen)
                self.assertIn(
                    "at least one",
                    screen.query_one("#settings_error", Static).render().plain,
                )
        self._run(runner())

    # ---- frozen capture

    def test_the_captured_target_survives_a_mid_flow_row_rebuild(self):
        """The settings row set really is rebuilt on every refresh, so a
        callback that re-read the table could push a DIFFERENT operation than
        the user chose. Both the cursor and the lookup map are repointed at the
        other row while a modal is open."""
        sessions = self.repos()
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "alpha": [ov("x/1", "project"), ov("x/9", "project")],
            "beta": [ov("y/1", "project"), ov("y/9", "project")],
        })
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                table = app.query_one("#settings", DataTable)
                table.move_cursor(row=0)
                await pilot.pause()
                self.assertEqual(app._selected_settings_row().operation, "alpha")

                app.action_push_setting()
                await pilot.pause()
                # Redirect everything the flow could re-read at "beta".
                beta = app._settings_rows_by_key["s1"]
                app._settings_rows_by_key["s0"] = beta
                app._settings_rows = [beta, beta]
                table.move_cursor(row=1)
                await pilot.pause()

                app.screen.dismiss(sessions[0].key)
                await pilot.pause()
                app.screen.dismiss((sessions[1].key,))
                await pilot.pause()
                app.screen.dismiss("project")
                await self.drain(app, pilot)
                self.assertEqual(len(seams.applies), 1)
                self.assertEqual(seams.applies[0][2], "alpha")
                self.assertEqual(seams.applies[0][0], "x/1")
        self._run(runner())

    # ---- t1267: the modals keep their arrow keys

    def test_arrows_in_a_settings_modal_do_not_switch_tabs(self):
        """t1267's coordination point. The t1266 arrows are App-level and
        priority, so they fire before a pushed modal's own bindings; the
        blanket screen-stack gate in check_action is what hands them back."""
        sessions = self.repos(3)
        seams = Seams()
        seams.diff = self.matrix(sessions, {
            "pick": [ov("x/1", "project"), ov("x/2", "project"),
                     ov("x/3", "project")],
        })
        async def runner():
            async with self.on_settings(seams, sessions) as (app, pilot):
                tabbed = app.query_one(TabbedContent)
                app.action_push_setting()
                for _ in range(4):
                    await pilot.pause()
                self.assertIsInstance(app.screen, SettingsSourceScreen)
                for action in syncer_app.NAV_ACTIONS:
                    self.assertIs(app.check_action(action, ()), False, action)

                radio = app.screen.query_one("#settings_source", RadioSet)
                radio.focus()
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_settings")  # not switched
                self.assertIsInstance(app.screen, SettingsSourceScreen)

                app.screen.dismiss(sessions[0].key)
                await pilot.pause()
                self.assertIsInstance(app.screen, SettingsDestinationsScreen)
                sel = app.screen.query_one("#settings_dest_list", SelectionList)
                sel.focus()
                await pilot.pause()
                await pilot.press("down")
                await pilot.press("left")
                await pilot.pause()
                self.assertEqual(tabbed.active, "tab_settings")
                self.assertIsInstance(app.screen, SettingsDestinationsScreen)
        self._run(runner())


if __name__ == "__main__":
    unittest.main()

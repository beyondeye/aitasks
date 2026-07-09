#!/usr/bin/env python3
"""Tests for the syncer TUI's pure multi-repo model helpers (t1138).

Covers the row model, action gating, LRU fetch scheduling, age formatting,
fetch-stamp invariants (negative controls), refresh-request coalescing, action
preflight, and discovery fallback — all without a running Textual app.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "syncer"))

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


if __name__ == "__main__":
    unittest.main()

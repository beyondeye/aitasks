"""Tests for the project-group data model (t1025_1).

Covers the pure / near-pure building blocks added to
``agent_launch_utils.py``:

  - ``validate_project_group_slug`` — accept / reject table, incl. the reserved
    unset sentinel ``-`` being rejected as a user slug.
  - ``_resolve_config_project_group`` — discovery's READ-time config validation
    (D6): valid slug returned; invalid / sentinel / absent -> None.
  - ``_resolve_session_group`` — the tri-state resolution (D1): registry slug
    wins; sentinel -> None with NO config fallback; empty -> validated config
    fallback; empty + invalid config -> None.
  - ``_build_registry_group_lookup`` — path-keyed (D3) so a live session whose
    basename differs from its registered name still matches.
  - ``group_sessions`` — ring + groups derivation (live-out-of-group included,
    stale-in-group kept, stale-out-of-group dropped, no-groups flat fallback).

Run: python3 tests/test_project_groups.py
  or: bash tests/run_all_python_tests.sh
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

import agent_launch_utils  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    PROJECT_GROUP_UNGROUPED_LABEL,
    PROJECT_GROUP_UNSET_SENTINEL,
    AitasksSession,
    _build_registry_group_lookup,
    _resolve_config_project_group,
    _resolve_session_group,
    advance_group_selection,
    advance_selected_group,
    cross_group_ring,
    cross_group_step,
    default_selected_group,
    group_members,
    group_sessions,
    validate_project_group_slug,
)


def _write_config(root: Path, *, group: str | None) -> Path:
    (root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
    cfg = root / "aitasks" / "metadata" / "project_config.yaml"
    body = "project:\n  name: x\n"
    if group is not None:
        body += f"  project_group: {group}\n"
    cfg.write_text(body)
    return root


def _sess(name, group, *, is_live=True, is_stale=False, root=None):
    # Distinct root per name so each session has a unique identity `.key`
    # (t1099) — identity no longer keys on the tmux session name.
    return AitasksSession(
        session=name,
        project_root=Path(root if root is not None else f"/tmp/{name}"),
        project_name=name,
        is_live=is_live,
        is_stale=is_stale,
        project_group=group,
    )


class SlugValidatorTests(unittest.TestCase):
    def test_accepts_valid_slugs(self):
        for s in ["a", "a1", "suite_x", "team-one", "x9_y-z", "0abc"]:
            ok, reason = validate_project_group_slug(s)
            self.assertTrue(ok, f"{s!r} should be valid ({reason})")

    def test_rejects_invalid_slugs(self):
        for s in ["", "-", "_x", "-x", "Foo", "a b", "a:b", "a#b",
                  "a|b", "a'b", '"a"', " x", "x "]:
            ok, _reason = validate_project_group_slug(s)
            self.assertFalse(ok, f"{s!r} should be rejected")

    def test_unset_sentinel_is_not_a_valid_slug(self):
        ok, _ = validate_project_group_slug(PROJECT_GROUP_UNSET_SENTINEL)
        self.assertFalse(ok)


class ConfigGroupReadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_config_group_returned(self):
        root = _write_config(self.tmp / "p", group="suite_a")
        self.assertEqual(_resolve_config_project_group(root), "suite_a")

    def test_absent_group_is_none(self):
        root = _write_config(self.tmp / "p", group=None)
        self.assertIsNone(_resolve_config_project_group(root))

    def test_invalid_config_group_is_none(self):
        # D6: a malformed config value must never leak into the session model.
        root = _write_config(self.tmp / "p", group="Bad Slug")
        self.assertIsNone(_resolve_config_project_group(root))

    def test_sentinel_in_config_is_none(self):
        # The sentinel is registry-only; it is not a valid config value.
        root = _write_config(self.tmp / "p", group=PROJECT_GROUP_UNSET_SENTINEL)
        self.assertIsNone(_resolve_config_project_group(root))

    def test_missing_config_file_is_none(self):
        self.assertIsNone(_resolve_config_project_group(self.tmp / "nope"))


class ResolveSessionGroupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_registry_slug_wins(self):
        root = _write_config(self.tmp / "p", group="from_config")
        self.assertEqual(
            _resolve_session_group(root, "from_registry", {}),
            "from_registry",
        )

    def test_sentinel_means_ungrouped_no_fallback(self):
        # D1: even though the repo config declares a group, the explicit unset
        # sentinel resolves to None and must NOT fall back to the config.
        root = _write_config(self.tmp / "p", group="from_config")
        self.assertIsNone(
            _resolve_session_group(root, PROJECT_GROUP_UNSET_SENTINEL, {})
        )

    def test_empty_registry_falls_back_to_valid_config(self):
        root = _write_config(self.tmp / "p", group="from_config")
        self.assertEqual(_resolve_session_group(root, "", {}), "from_config")
        self.assertEqual(_resolve_session_group(root, None, {}), "from_config")

    def test_empty_registry_invalid_config_is_none(self):
        root = _write_config(self.tmp / "p", group="Bad Slug")
        self.assertIsNone(_resolve_session_group(root, "", {}))

    def test_invalid_registry_value_does_not_leak(self):
        root = _write_config(self.tmp / "p", group=None)
        self.assertIsNone(_resolve_session_group(root, "Bad Slug", {}))


class RegistryGroupLookupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("AITASKS_PROJECTS_INDEX", None)

    def test_lookup_is_keyed_by_realpath(self):
        # D3: registry name differs from directory basename, but the lookup is
        # keyed by realpath so a live session resolves by path regardless.
        proj = self.tmp / "actual_dir"
        (proj / "aitasks" / "metadata").mkdir(parents=True)
        (proj / "aitasks" / "metadata" / "project_config.yaml").write_text("project:\n  name: x\n")
        idx = self.tmp / "projects.yaml"
        idx.write_text(
            "projects:\n"
            "  - name: logical_name\n"
            f"    path: {proj}\n"
            "    project_group: suite_p\n"
        )
        os.environ["AITASKS_PROJECTS_INDEX"] = str(idx)
        lookup = _build_registry_group_lookup()
        self.assertEqual(lookup.get(os.path.realpath(proj)), "suite_p")


class GroupSessionsTests(unittest.TestCase):
    def test_ring_members_plus_live_out_of_group(self):
        a = _sess("a", "g1")
        b = _sess("b", "g1")
        c_live = _sess("c", "g2", is_live=True)
        d_stale = _sess("d", "g2", is_live=False, is_stale=True)
        res = group_sessions([a, b, c_live, d_stale], "g1")
        ring_names = [s.project_name for s in res.ring]
        # g1 members first, then live out-of-group (c); stale out-of-group (d)
        # is dropped from the ring.
        self.assertEqual(ring_names, ["a", "b", "c"])
        self.assertNotIn("d", ring_names)

    def test_stale_in_group_is_kept(self):
        a = _sess("a", "g1", is_live=False, is_stale=True)
        b = _sess("b", "g1")
        res = group_sessions([a, b], "g1")
        self.assertEqual([s.project_name for s in res.ring], ["a", "b"])

    def test_groups_list_sorted_with_ungrouped_last(self):
        sessions = [_sess("a", "zeta"), _sess("b", "alpha"), _sess("c", None)]
        res = group_sessions(sessions, "alpha")
        self.assertEqual(res.groups, ["alpha", "zeta", PROJECT_GROUP_UNGROUPED_LABEL])

    def test_ungrouped_selection_uses_none_bucket(self):
        a = _sess("a", None)
        b = _sess("b", "g1", is_live=True)
        res = group_sessions([a, b], PROJECT_GROUP_UNGROUPED_LABEL)
        # a is the ungrouped member; b is live out-of-group -> both in ring.
        self.assertEqual([s.project_name for s in res.ring], ["a", "b"])

    def test_no_groups_flat_fallback(self):
        sessions = [_sess("a", None), _sess("b", None, is_live=False)]
        res = group_sessions(sessions, None)
        # Everything is ungrouped -> selecting the bucket yields all of them.
        self.assertEqual(res.groups, [PROJECT_GROUP_UNGROUPED_LABEL])
        self.assertEqual([s.project_name for s in res.ring], ["a", "b"])


class DefaultSelectedGroupTests(unittest.TestCase):
    def test_named_session_grouped_returns_its_group(self):
        a, b = _sess("a", "g1"), _sess("b", "g2")
        self.assertEqual(default_selected_group([a, b], b.key), "g2")

    def test_named_session_ungrouped_returns_none_not_first_group(self):
        # The selected session is ungrouped -> None (the ungrouped bucket),
        # NOT a fall-through to the first real group.
        a, b = _sess("a", "g1"), _sess("b", None)
        self.assertIsNone(default_selected_group([a, b], b.key))

    def test_absent_session_falls_back_to_first_group(self):
        sessions = [_sess("a", "zeta"), _sess("b", "alpha")]
        # groups sorted -> ["alpha", "zeta"]; first is "alpha".
        self.assertEqual(default_selected_group(sessions, "nope"), "alpha")

    def test_absent_session_first_group_is_ungrouped_when_no_real_groups(self):
        sessions = [_sess("a", None), _sess("b", None)]
        self.assertEqual(
            default_selected_group(sessions, "__all__"),
            PROJECT_GROUP_UNGROUPED_LABEL,
        )

    def test_empty_sessions_returns_none(self):
        self.assertIsNone(default_selected_group([], "a"))
        self.assertIsNone(default_selected_group([], None))


class AdvanceSelectedGroupTests(unittest.TestCase):
    GROUPS = ["alpha", "zeta", PROJECT_GROUP_UNGROUPED_LABEL]

    def test_forward_wraps(self):
        self.assertEqual(advance_selected_group(self.GROUPS, "alpha", +1), "zeta")
        self.assertEqual(
            advance_selected_group(self.GROUPS, PROJECT_GROUP_UNGROUPED_LABEL, +1),
            "alpha",
        )

    def test_backward_wraps(self):
        self.assertEqual(
            advance_selected_group(self.GROUPS, "alpha", -1),
            PROJECT_GROUP_UNGROUPED_LABEL,
        )
        self.assertEqual(advance_selected_group(self.GROUPS, "zeta", -1), "alpha")

    def test_unknown_current_starts_from_first(self):
        self.assertEqual(advance_selected_group(self.GROUPS, "gone", +1), "zeta")
        self.assertEqual(advance_selected_group(self.GROUPS, None, +1), "zeta")

    def test_empty_groups_returns_current(self):
        self.assertEqual(advance_selected_group([], "x", +1), "x")
        self.assertIsNone(advance_selected_group([], None, +1))


class AdvanceGroupSelectionTests(unittest.TestCase):
    """`advance_group_selection` centralizes group-cycle re-point decisions."""

    def test_repoints_to_first_member_when_selection_outside_new_group(self):
        a, b = _sess("a", "g1"), _sess("b", "g2")
        result = advance_group_selection([a, b], "g2", b.key, +1)
        self.assertIsNotNone(result)
        self.assertEqual(result.selected_group, "g1")
        self.assertEqual(result.repoint_key, a.key)

    def test_keeps_selection_when_it_belongs_to_new_group(self):
        a, b, c = _sess("a", "g1"), _sess("b", "g1"), _sess("c", "g2")
        result = advance_group_selection([a, b, c], "g2", b.key, +1)
        self.assertIsNotNone(result)
        self.assertEqual(result.selected_group, "g1")
        self.assertIsNone(result.repoint_key)

    def test_single_group_returns_none(self):
        a, b = _sess("a", "g1"), _sess("b", "g1")
        self.assertIsNone(advance_group_selection([a, b], "g1", a.key, +1))

    def test_fallback_used_when_target_group_has_no_members(self):
        a, b = _sess("a", "g1"), _sess("b", "g2")
        with patch.object(agent_launch_utils, "group_members", return_value=[]):
            result = advance_group_selection(
                [a, b], "g2", b.key, +1, fallback_key="__all__"
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.selected_group, "g1")
        self.assertEqual(result.repoint_key, "__all__")


class GroupMembersTests(unittest.TestCase):
    """`group_members` returns ONLY the selected group's members (t1036)."""

    def test_members_only_no_out_of_group_append(self):
        a, b = _sess("a", "g1"), _sess("b", "g1")
        c_live, d_other = _sess("c", "g1"), _sess("d", "g2")  # d live, other grp
        members = group_members([a, b, c_live, d_other], "g1")
        # Unlike group_sessions().ring, the live out-of-group d is NOT appended.
        self.assertEqual([s.project_name for s in members], ["a", "b", "c"])

    def test_stale_in_group_is_kept(self):
        a = _sess("a", "g1")
        b = _sess("b", "g1", is_live=False, is_stale=True)
        self.assertEqual(
            [s.project_name for s in group_members([a, b], "g1")], ["a", "b"]
        )

    def test_ungrouped_bucket_selected_by_none_and_label(self):
        a, b = _sess("a", None), _sess("b", "g1")
        self.assertEqual(
            [s.project_name for s in group_members([a, b], None)], ["a"]
        )
        self.assertEqual(
            [s.project_name
             for s in group_members([a, b], PROJECT_GROUP_UNGROUPED_LABEL)],
            ["a"],
        )


class CrossGroupRingTests(unittest.TestCase):
    """`cross_group_ring` flattens all groups into one boundary-crossing walk."""

    def test_group_cycle_order_every_project_once(self):
        # Real groups sort (g1 < g2); ungrouped bucket comes last.
        a, c = _sess("a", "g1"), _sess("c", "g1")
        b = _sess("b", "g2")
        u = _sess("u", None)
        entries = cross_group_ring([a, c, b, u])
        self.assertEqual(
            [e.session for e in entries], ["a", "c", "b", "u"]
        )
        # Each entry tagged with its group; ungrouped normalized to None.
        self.assertEqual(
            [e.group for e in entries], ["g1", "g1", "g2", None]
        )

    def test_includes_stale_in_group_members(self):
        a = _sess("a", "g1")
        d = _sess("d", "g1", is_live=False, is_stale=True)
        b = _sess("b", "g2")
        entries = cross_group_ring([a, d, b])
        self.assertEqual([e.session for e in entries], ["a", "d", "b"])

    def test_empty_sessions(self):
        self.assertEqual(cross_group_ring([]), [])


class CrossGroupStepTests(unittest.TestCase):
    """`cross_group_step` wraps a ±1 step over a cross-group ring."""

    def _ring(self):
        # g1: a, c ; g2: b  -> sequence [a, c, b]
        return cross_group_ring([_sess("a", "g1"), _sess("c", "g1"),
                                 _sess("b", "g2")])

    def _keys(self, ring):
        # Stepping matches on the unique identity key (t1099), not the session
        # name; map name -> key for readable per-session assertions.
        return {e.session: e.key for e in ring}

    def test_forward_within_group(self):
        ring = self._ring()
        t = cross_group_step(ring, self._keys(ring)["a"], +1)
        self.assertEqual((t.session, t.group), ("c", "g1"))

    def test_forward_crosses_boundary(self):
        # Last member of g1 (c) -> first member of g2 (b), group switches.
        ring = self._ring()
        t = cross_group_step(ring, self._keys(ring)["c"], +1)
        self.assertEqual((t.session, t.group), ("b", "g2"))

    def test_forward_wraps_globally(self):
        # Last member of last group (b) -> first member of first group (a).
        ring = self._ring()
        t = cross_group_step(ring, self._keys(ring)["b"], +1)
        self.assertEqual((t.session, t.group), ("a", "g1"))

    def test_backward_crosses_boundary_and_wraps(self):
        # First member of g1 (a) wraps back to last member of last group (b).
        ring = self._ring()
        t = cross_group_step(ring, self._keys(ring)["a"], -1)
        self.assertEqual((t.session, t.group), ("b", "g2"))

    def test_absent_current_starts_from_first(self):
        t = cross_group_step(self._ring(), "gone", +1)
        self.assertEqual(t.session, "c")  # index 0 (a) + 1

    def test_empty_ring_returns_none(self):
        self.assertIsNone(cross_group_step([], "a", +1))


if __name__ == "__main__":
    unittest.main()

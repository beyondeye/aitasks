#!/usr/bin/env python3
"""Tests for lib/trail_links.py — cross-repo linked-trail discovery (t1957_3).

Three layers, three sections:

- the pure relation (``find_linked_trails``) over synthetic exports and a dict
  resolver: all four link directions, root-based ownership (``project.name``,
  registry alias, missing name), and per-member read failures;
- the scan (``scan_linked_trails``) with its three seams patched
  (``_read_registry``, ``_resolve_name``, ``_run_export``): candidate selection,
  self-exclusion, and the rule that nothing is skipped silently;
- end to end: the real ``export`` subprocess in a fixture repo holding a trail
  stored with the real artifact CLI, scanned through the real resolver.

Run: python3 -m pytest tests/test_trail_links.py -q
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import trail_links as tl  # noqa: E402
import trail_schema  # noqa: E402

RX, RY, RZ = "/roots/x", "/roots/y", "/roots/z"
RESOLVE = {"aitasks_reg": RX, "x_alias": RX, "mob_reg": RY, "mob_alias": RY,
           "zproj": RZ}.get


def _doc(*refs):
    return {"waves": [{"entries": [{"task": r} for r in refs]}]}


def _ok(repo="", *xdeps):
    return {"state": "ok", "xdeprepo": repo if xdeps else "",
            "xdeps": list(xdeps)}


def _trail(handle, *members, load_error=""):
    return {"handle": handle, "name": handle, "title": "", "owner_id": "1",
            "load_error": load_error, "members": list(members)}


def _data(trails, tasks=None, local_project="mobile", *, autofill=True,
          **extra):
    """An export dict. Like the real export, ``tasks`` covers every member id
    (as ``_ok()`` unless given); ``autofill=False`` models one that omitted
    some."""
    filled = {}
    if autofill:
        for trail in trails:
            for ref in trail["members"]:
                parsed = tl.parse_ref(ref)
                if parsed:
                    filled[parsed[1]] = _ok()
    filled.update(tasks or {})
    data = {"format": 1, "local_project": local_project, "unreadable": [],
            "scan_errors": [], "trails": trails, "tasks": filled}
    data.update(extra)
    return data


def _export(trails, tasks=None, local_project="mobile", root=RY,
            project="mob_reg", *, autofill=True):
    return tl.ProjectExport(project, root, _data(trails, tasks, local_project,
                                                 autofill=autofill))


def _find(local_doc, local_tasks, exports, local_project="aitasks"):
    return tl.find_linked_trails(local_doc, local_tasks, local_project, RX,
                                 exports, RESOLVE)


class RelationDirectionTests(unittest.TestCase):
    """Each direction on its own yields exactly one link with its reason."""

    def test_fwd_xdeps_with_registry_name_not_project_name(self):
        """A's xdeprepo is the registry name `mob_reg`; B's members use Y's
        `project.name` `mobile`. Both resolve to Y's root, so they match."""
        links, errors = _find(_doc("aitasks#42"), {"42": _ok("mob_reg", "7")},
                              [_export([_trail("art:b", "mobile#7")])])
        self.assertEqual(errors, [])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].handle, "art:b")
        self.assertEqual(links[0].root, RY)
        self.assertEqual(links[0].reasons,
                         ("fwd-xdeps: aitasks#42 xdeps mob_reg#7",))

    def test_fwd_member(self):
        links, _ = _find(_doc("aitasks#42", "mob_reg#t7"), {"42": _ok()},
                         [_export([_trail("art:b", "mobile#7")])])
        self.assertEqual([l.reasons for l in links],
                         [("fwd-member: mob_reg#t7",)])

    def test_rev_xdeps(self):
        links, _ = _find(_doc("aitasks#42"), {"42": _ok()},
                         [_export([_trail("art:b", "mobile#9")],
                                  {"9": _ok("aitasks_reg", "42")})])
        self.assertEqual([l.reasons for l in links],
                         [("rev-xdeps: mobile#9 xdeps aitasks_reg#42",)])

    def test_rev_member(self):
        links, _ = _find(_doc("aitasks#42"), {"42": _ok()},
                         [_export([_trail("art:b", "mobile#9",
                                          "aitasks_reg#42")])])
        self.assertEqual([l.reasons for l in links],
                         [("rev-member: aitasks_reg#42",)])

    def test_several_relations_merge_into_one_sorted_link(self):
        links, _ = _find(_doc("aitasks#42", "mob_reg#7"),
                         {"42": _ok("mob_reg", "7")},
                         [_export([_trail("art:b", "mobile#7",
                                          "aitasks_reg#42")])])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].reasons, (
            "fwd-member: mob_reg#7",
            "fwd-xdeps: aitasks#42 xdeps mob_reg#7",
            "rev-member: aitasks_reg#42"))


class RootBasedOwnershipTests(unittest.TestCase):
    """Ownership is decided by resolved root, never by the name's spelling."""

    def test_string_equal_names_on_different_roots_do_not_link(self):
        """Y's `project.name` collides with X's: B's `aitasks#42` is Y's own
        task 42, not X's — comparing names as strings would link them."""
        links, _ = _find(_doc("aitasks#42"), {"42": _ok()},
                         [_export([_trail("art:b", "aitasks#42")],
                                  local_project="aitasks")])
        self.assertEqual(links, [])

    def test_alias_named_own_member_contributes_its_xdeps(self):
        """B names its own member through the registry alias `mob_alias`; it
        is still B's own, so its xdeps back to A are a rev-xdeps link."""
        links, _ = _find(_doc("aitasks#42"), {"42": _ok()},
                         [_export([_trail("art:b", "mob_alias#7")],
                                  {"7": _ok("aitasks_reg", "42")})])
        self.assertEqual([l.reasons for l in links],
                         [("rev-xdeps: mob_alias#7 xdeps aitasks_reg#42",)])

    def test_export_without_project_name_owns_through_the_resolver(self):
        links, _ = _find(_doc("aitasks#42"), {"42": _ok()},
                         [_export([_trail("art:b", "mob_reg#7")],
                                  {"7": _ok("aitasks_reg", "42")},
                                  local_project="")])
        self.assertEqual([l.reasons for l in links],
                         [("rev-xdeps: mob_reg#7 xdeps aitasks_reg#42",)])

    def test_local_alias_member_is_own(self):
        """A local member spelled with an alias of this repo is own: B's
        cross-repo member naming it is a rev-member link."""
        links, _ = _find(_doc("x_alias#42"), {"42": _ok()},
                         [_export([_trail("art:b", "aitasks_reg#42")])])
        self.assertEqual([l.reasons for l in links],
                         [("rev-member: aitasks_reg#42",)])

    def test_shared_third_repo_member_is_not_a_link(self):
        links, _ = _find(_doc("aitasks#42", "zproj#3"), {"42": _ok()},
                         [_export([_trail("art:b", "mobile#1", "zproj#3")])])
        self.assertEqual(links, [])

    def test_unparseable_and_unresolvable_refs_are_ignored(self):
        links, errors = _find(
            _doc("aitasks#42", "garbage", "Mob#x", "ghost#5", "mob_reg#t7"),
            {"42": _ok()},
            [_export([_trail("art:b", "mobile#7", "not a ref")])])
        self.assertEqual(errors, [])
        self.assertEqual([l.reasons for l in links],
                         [("fwd-member: mob_reg#t7",)])

    def test_trail_that_failed_to_load_is_not_linked(self):
        links, _ = _find(_doc("aitasks#42", "mob_reg#7"), {"42": _ok()},
                         [_export([_trail("art:b", "mobile#7",
                                          load_error="invalid trail")])])
        self.assertEqual(links, [])


class MemberReadFailureTests(unittest.TestCase):
    """An own member whose metadata is unknown is reported, never dropped."""

    def test_unreadable_exported_member_is_partial_and_keeps_other_links(self):
        unreadable = {"state": "unreadable", "detail": "t7_x.md: boom"}
        links, errors = _find(
            _doc("aitasks#42", "mob_reg#8"), {"42": _ok()},
            [_export([_trail("art:b", "mobile#7"), _trail("art:c", "mobile#8")],
                     {"7": unreadable, "8": _ok()})])
        self.assertEqual([l.handle for l in links], ["art:c"])
        self.assertEqual(errors, [tl.ProjectScanError(
            "mob_reg", tl.PARTIAL, "unreadable task(s): t7: t7_x.md: boom")])

    def test_member_omitted_from_the_export_is_partial(self):
        _links, errors = _find(_doc("aitasks#42"), {"42": _ok()},
                               [_export([_trail("art:b", "mobile#7")],
                                        autofill=False)])
        self.assertEqual([(e.kind, e.detail) for e in errors],
                         [(tl.PARTIAL, "unreadable task(s): t7: not exported")])

    def test_missing_member_is_not_a_failure(self):
        _links, errors = _find(_doc("aitasks#42"), {"42": _ok()},
                               [_export([_trail("art:b", "mobile#7")],
                                        {"7": {"state": "missing"}})])
        self.assertEqual(errors, [])

    def test_unreadable_local_member_is_reported_and_others_still_link(self):
        links, errors = _find(
            _doc("aitasks#42", "aitasks#43"),
            {"42": {"state": "unreadable", "detail": "t42_a.md: boom"},
             "43": _ok("mob_reg", "8")},
            [_export([_trail("art:b", "mobile#7"), _trail("art:c", "mobile#8")])])
        self.assertEqual([l.handle for l in links], ["art:c"])
        self.assertEqual(errors, [tl.ProjectScanError(
            "aitasks", tl.LOCAL_UNREADABLE, "t42: t42_a.md: boom")])


def _project_dir(base: Path, name: str, *, marker=True) -> Path:
    root = base / name
    (root / "aitasks" / "metadata").mkdir(parents=True)
    if marker:
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "project:\n  name: x\n", encoding="utf-8")
    return root


def _proc(data=None, *, returncode=0, stdout=None, stderr=""):
    out = (stdout if stdout is not None
           else tl.EXPORT_PREFIX + json.dumps(data) + "\n")
    return subprocess.CompletedProcess([], returncode, out, stderr)


class ScanTests(unittest.TestCase):
    """``scan_linked_trails`` with the registry, resolver and export patched."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="trail_links_scan_")
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))
        self.x = _project_dir(self.base, "x")
        self.y = _project_dir(self.base, "y")
        self.z = _project_dir(self.base, "z")
        self.registry = []
        self.names = {}
        self.exports = {}
        self.export_calls = []
        for name, value in (("_read_registry", self._registry),
                            ("_resolve_name", self._resolve),
                            ("_run_export", self._run)):
            p = patch.object(tl, name, value)
            p.start()
            self.addCleanup(p.stop)

    def _registry(self):
        if isinstance(self.registry, Exception):
            raise self.registry
        return [(name, str(path)) for name, path in self.registry]

    def _resolve(self, name):
        return self.names.get(name, ("NOT_FOUND", "not registered"))

    def _run(self, root):
        self.export_calls.append(root)
        result = self.exports.get(root, _proc(_data([])))
        if isinstance(result, BaseException):
            raise result
        return result

    def _scan(self, doc, tasks, local_project="aitasks"):
        return tl.scan_linked_trails(doc, local_root=str(self.x),
                                     local_project=local_project,
                                     local_tasks=tasks)

    def test_self_and_local_aliases_are_never_candidates(self):
        link = self.base / "x_link"
        link.symlink_to(self.x)
        self.registry = [("aitasks", link), ("mob_reg", self.y)]
        self.names = {"x_alias": ("RESOLVED", str(link))}
        scan = self._scan(_doc("x_alias#42"), {"42": _ok()})
        self.assertEqual(self.export_calls, [str(self.y)])
        self.assertEqual(scan.errors, [])
        self.assertTrue(scan.complete)

    def test_xdeprepo_naming_a_stale_project_is_one_stale_error(self):
        stale = self.base / "moved"
        self.registry = [("mob_reg", stale)]
        self.names = {"mob_reg": ("STALE", str(stale))}
        scan = self._scan(_doc("aitasks#42"), {"42": _ok("mob_reg", "7")})
        self.assertFalse(scan.complete)
        self.assertEqual(scan.links, [])
        self.assertEqual(scan.errors, [
            tl.ProjectScanError("mob_reg", tl.STALE, str(stale))])
        self.assertEqual(self.export_calls, [])

    def test_stale_registry_entry_alone_makes_the_scan_incomplete(self):
        """A registered project the trail does not point at may still hold a
        linked trail, so its stale path is reported, not skipped."""
        stale = self.base / "gone"
        self.registry = [("mob_reg", self.y), ("old_proj", stale)]
        scan = self._scan(_doc("aitasks#42"), {"42": _ok()})
        self.assertEqual(self.export_calls, [str(self.y)])
        self.assertFalse(scan.complete)
        self.assertEqual(scan.errors, [
            tl.ProjectScanError("old_proj", tl.STALE, str(stale))])

    def test_registry_entry_without_a_path_is_reported(self):
        """The strict reader keeps name-only rows (``ait projects list``
        shows them as stale); one the trail does not point at is still a
        project that could not be searched."""
        self.registry = [("mob_reg", self.y), ("broken", "")]
        scan = self._scan(_doc("aitasks#42"), {"42": _ok()})
        self.assertEqual(self.export_calls, [str(self.y)])
        self.assertFalse(scan.complete)
        self.assertEqual(scan.errors, [
            tl.ProjectScanError("broken", tl.STALE, "no path registered")])

    def test_undecodable_local_config_falls_back_instead_of_raising(self):
        """Invalid UTF-8 in project_config.yaml is a decode error, not an
        OSError; the scan must still return a LinkScan."""
        tasks = self.x / "aitasks"
        (tasks / "metadata" / "project_config.yaml").write_bytes(
            b"project:\n  name: \xff\xfe\n")
        with patch.dict(os.environ, {"TASK_DIR": str(tasks)}):
            self.assertEqual(tl._local_project_name(), "")
            scan = tl.scan_linked_trails(_doc("aitasks#42"),
                                         local_root=str(self.x))
        self.assertIsInstance(scan, tl.LinkScan)
        # Without a local name, `aitasks` must resolve to be owned — here it
        # does not, so the scan says so instead of guessing.
        self.assertEqual([(e.project, e.kind) for e in scan.errors],
                         [("aitasks", tl.NOT_FOUND)])

    def test_xdeprepo_naming_an_unknown_project_is_one_not_found_error(self):
        scan = self._scan(_doc("aitasks#42"), {"42": _ok("ghost", "7")})
        self.assertFalse(scan.complete)
        self.assertEqual(scan.links, [])
        self.assertEqual(scan.errors, [
            tl.ProjectScanError("ghost", tl.NOT_FOUND, "not registered")])

    def test_successful_empty_scan_is_complete(self):
        self.registry = [("mob_reg", self.y)]
        scan = self._scan(_doc("aitasks#42"), {"42": _ok()})
        self.assertEqual((scan.links, scan.errors, scan.complete), ([], [], True))

    def test_export_failures_are_reported_per_project(self):
        self.registry = [("a", self.y), ("b", self.z),
                         ("c", _project_dir(self.base, "c")),
                         ("d", _project_dir(self.base, "d"))]
        self.exports = {
            str(self.y): subprocess.TimeoutExpired(["x"], 30),
            str(self.z): _proc(returncode=1, stderr="Traceback\nBoom: bad\n"),
            str(self.base / "c"): _proc(stdout="not json"),
            str(self.base / "d"): _proc(_data([]) | {"format": 2}),
        }
        scan = self._scan(_doc("aitasks#42"), {"42": _ok()})
        self.assertFalse(scan.complete)
        self.assertEqual([(e.project, e.kind) for e in scan.errors], [
            ("a", tl.TIMEOUT), ("b", tl.EXPORT_FAILED),
            ("c", tl.EXPORT_FAILED), ("d", tl.EXPORT_FAILED)])
        self.assertEqual(scan.errors[1].detail, "Boom: bad")

    def test_export_record_is_found_among_interpreter_noise(self):
        """PyPy prints cpyext diagnostics to stdout when PyYAML's C extension
        loads; only the prefixed record line is the export's result."""
        self.registry = [("mob_reg", self.y), ("z", self.z)]
        noise = "(_common_types_metatype, 9088, 128, 128)\n"
        self.exports = {
            str(self.y): _proc(stdout=noise + tl.EXPORT_PREFIX
                               + json.dumps(_data([])) + "\n"),
            str(self.z): _proc(stdout=noise + tl.EXPORT_PREFIX + "{broken\n"),
        }
        scan = self._scan(_doc("aitasks#42"), {"42": _ok()})
        self.assertEqual([(e.project, e.kind) for e in scan.errors],
                         [("z", tl.EXPORT_FAILED)])

    def test_partial_export_keeps_its_links(self):
        self.registry = [("mob_reg", self.y)]
        self.names = {"mob_reg": ("RESOLVED", str(self.y))}
        self.exports = {str(self.y): _proc(_data(
            [_trail("art:b", "mobile#7"), _trail("art:bad", load_error="x")],
            unreadable=["t3_x.md"], scan_errors=["_b0/old0.tar.gz: bad"]))}
        scan = self._scan(_doc("aitasks#42", "mob_reg#7"), {"42": _ok()})
        self.assertEqual([l.handle for l in scan.links], ["art:b"])
        self.assertFalse(scan.complete)
        self.assertEqual(len(scan.errors), 1)
        err = scan.errors[0]
        self.assertEqual((err.project, err.kind), ("mob_reg", tl.PARTIAL))
        for needle in ("t3_x.md", "old0.tar.gz", "art:bad"):
            self.assertIn(needle, err.detail)

    def test_unreadable_registry_still_searches_direct_names(self):
        self.registry = PermissionError("registry: permission denied")
        self.names = {"mob_reg": ("RESOLVED", str(self.y))}
        self.exports = {str(self.y): _proc(_data([_trail("art:b", "mobile#7")]))}
        scan = self._scan(_doc("aitasks#42"), {"42": _ok("mob_reg", "7")})
        self.assertEqual([l.handle for l in scan.links], ["art:b"])
        self.assertEqual([e.kind for e in scan.errors], [tl.REGISTRY_UNREADABLE])
        self.assertFalse(scan.complete)

    def test_registry_and_direct_name_on_one_root_export_once(self):
        link = self.base / "y_link"
        link.symlink_to(self.y)
        self.registry = [("mob_reg", self.y)]
        self.names = {"mob_alias": ("RESOLVED", str(link))}
        self._scan(_doc("aitasks#42"), {"42": _ok("mob_alias", "7")})
        self.assertEqual(self.export_calls, [str(self.y)])

    def test_member_in_an_unlistable_child_dir_is_unreadable_not_missing(self):
        """Path.glob would read a locked ``t42/`` as empty, i.e. "task
        missing"; the lookup must say it could not tell."""
        tasks = self.x / "aitasks"
        child_dir = tasks / "t42"
        child_dir.mkdir()
        (child_dir / "t42_3_c.md").write_text(
            "---\nxdeprepo: mob_reg\nxdeps: [7]\n---\n", encoding="utf-8")
        child_dir.chmod(0o000)
        self.addCleanup(child_dir.chmod, 0o755)
        if os.access(child_dir, os.R_OK):
            self.skipTest("running with permissions that ignore mode 000")
        with patch.dict(os.environ, {"TASK_DIR": str(tasks)}):
            meta = tl.lookup_task_meta("42_3")
        self.assertEqual(meta["state"], "unreadable")
        self.assertIn("t42", meta["detail"])

    def test_unlistable_active_dir_is_not_overridden_by_an_archived_copy(self):
        """Active files take precedence: when the active ``t42/`` cannot be
        listed, an archived ``t42_3`` without dependencies is not the answer
        — the active copy may carry the xdeps that link the trail."""
        tasks = self.x / "aitasks"
        child_dir = tasks / "t42"
        child_dir.mkdir()
        (child_dir / "t42_3_c.md").write_text(
            "---\nxdeprepo: mob_reg\nxdeps: [7]\n---\n", encoding="utf-8")
        archived = tasks / "archived" / "t42"
        archived.mkdir(parents=True)
        (archived / "t42_3_c.md").write_text("---\nstatus: Done\n---\n",
                                             encoding="utf-8")
        child_dir.chmod(0o000)
        self.addCleanup(child_dir.chmod, 0o755)
        if os.access(child_dir, os.R_OK):
            self.skipTest("running with permissions that ignore mode 000")
        self.registry = [("mob_reg", self.y)]
        self.exports = {str(self.y): _proc(_data([_trail("art:b", "mobile#7")]))}
        with patch.dict(os.environ, {"TASK_DIR": str(tasks)}):
            meta = tl.lookup_task_meta("42_3")
            scan = tl.scan_linked_trails(_doc("aitasks#42_3"),
                                         local_root=str(self.x),
                                         local_project="aitasks")
        self.assertEqual(meta["state"], "unreadable")
        self.assertEqual(scan.links, [])
        self.assertFalse(scan.complete)
        self.assertEqual([e.kind for e in scan.errors], [tl.LOCAL_UNREADABLE])

    def test_unlistable_loose_archive_is_not_overridden_by_a_bundle_copy(self):
        """Within the archive, loose files precede bundles: a bundle hit is not
        the answer when the loose ``archived/t42/`` could not be listed."""
        tasks = self.x / "aitasks"
        loose = tasks / "archived" / "t42"
        loose.mkdir(parents=True)
        (loose / "t42_3_c.md").write_text(
            "---\nxdeprepo: mob_reg\nxdeps: [7]\n---\n", encoding="utf-8")
        bundle = tasks / "archived" / "_b0" / "old0.tar.zst"
        bundle.parent.mkdir()
        payload = b"---\nstatus: Done\n---\n"
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo("t42_3_c.md")
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
        bundle.write_bytes(subprocess.run(
            ["zstd", "-q", "-c"], input=buf.getvalue(), capture_output=True,
            check=True).stdout)
        loose.chmod(0o000)
        self.addCleanup(loose.chmod, 0o755)
        if os.access(loose, os.R_OK):
            self.skipTest("running with permissions that ignore mode 000")
        with patch.dict(os.environ, {"TASK_DIR": str(tasks)}):
            meta = tl.lookup_task_meta("42_3")
        self.assertEqual(meta["state"], "unreadable")
        self.assertIn("t42", meta["detail"])

    def test_malformed_local_member_is_reported_and_other_links_kept(self):
        """Read from disk: t42 is malformed (its xdeps would have linked Y's
        trail), t43 is fine and the trail's `zproj#3` links Z's trail."""
        tasks = self.x / "aitasks"
        (tasks / "t42_broken.md").write_text(
            "---\nxdeprepo: mob_reg\nxdeps: [7\n---\n", encoding="utf-8")
        (tasks / "t43_fine.md").write_text("---\nstatus: Ready\n---\n",
                                           encoding="utf-8")
        self.registry = [("mob_reg", self.y), ("zproj", self.z)]
        self.names = {"zproj": ("RESOLVED", str(self.z))}
        self.exports = {
            str(self.y): _proc(_data([_trail("art:b", "mobile#7")])),
            str(self.z): _proc(_data([_trail("art:c", "zp#3")],
                                     local_project="zp")),
        }
        with patch.dict(os.environ, {"TASK_DIR": str(tasks)}):
            scan = tl.scan_linked_trails(
                _doc("aitasks#42", "aitasks#43", "zproj#3"),
                local_root=str(self.x), local_project="aitasks")
        self.assertEqual([l.handle for l in scan.links], ["art:c"])
        self.assertFalse(scan.complete)
        self.assertEqual(len(scan.errors), 1)
        self.assertEqual(scan.errors[0].kind, tl.LOCAL_UNREADABLE)
        self.assertIn("t42", scan.errors[0].detail)


# --- End to end ---------------------------------------------------------------

TS = "2026-10-13T10:00:00Z"

#: The board's PyPy fast-path interpreter (``ait setup`` installs it here).
PYPY = os.path.expanduser("~/.aitask/pypy_venv/bin/python")


def _trail_doc(owner: str, members: list[str]) -> dict:
    """A minimal schema-valid trail (same shape as test_trail_gather's
    make_trail; the version is derived, never hardcoded)."""
    entries = [{"entry_id": f"e{i}", "task": ref, "topic": ref, "position": i,
                "classification": "core", "snapshot": {"status": "Ready"},
                "rationale": "because", "confidence": "medium"}
               for i, ref in enumerate(members, start=1)]
    return {
        "schema_version": (trail_schema.load_schema()["properties"]
                           ["schema_version"]["const"]),
        "trail_id": "trail-links-fixture",
        "title": "Linked fixture trail",
        "owner": owner,
        "scope": {"kind": "topic", "topics": []},
        "generation": {"generated_at": TS,
                       "generator": {"agent_string": "test/agent"},
                       "input_digest": "a" * 64,
                       "inputs": [{"ref": members[0], "kind": "task_file"}]},
        "freshness": {"state": "current", "checked_at": TS},
        "narrative": {"problem_statement": "p", "recommendation_summary": "r"},
        "waves": [{"wave_id": "w1", "ordinal": 1, "title": "Wave 1",
                   "purpose": "test wave", "entries": entries}],
        "evidence": [{"evidence_id": "ev1", "source_type": "board_state",
                      "ref": "board", "observed_at": TS, "summary": "s"}],
    }


class EndToEndTests(unittest.TestCase):
    """The real export subprocess against fixture repos whose trails are
    stored with the real artifact CLI, scanned through the real resolver."""

    Y_NAME = "t1957fixy"
    X_REG = "t1957localx"
    X_PROJECT = "t1957xname"     # X's project.name differs from its registry name

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="trail_links_e2e_")
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))
        saved = {k: os.environ.get(k) for k in (
            "TASK_DIR", "PLAN_DIR", "ARCHIVED_DIR", "AITASKS_PROJECTS_INDEX",
            "XDG_CACHE_HOME")}
        self.addCleanup(self._restore_env, saved)
        for key in ("TASK_DIR", "PLAN_DIR", "ARCHIVED_DIR"):
            os.environ.pop(key, None)
        self.registry_file = self.base / "projects.yaml"
        os.environ["AITASKS_PROJECTS_INDEX"] = str(self.registry_file)
        os.environ["XDG_CACHE_HOME"] = str(self.base / "cache")
        self.x = self._repo("x", self.X_PROJECT, git=False)
        self._task(self.x, "42")
        original = os.getcwd()
        self.addCleanup(os.chdir, original)
        os.chdir(self.x)

    @staticmethod
    def _restore_env(saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _git(self, root: Path, *args):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}
        subprocess.run(["git", "-C", str(root), *args], check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _repo(self, dirname: str, project_name: str | None, *, git=True) -> Path:
        root = self.base / dirname
        (root / "aitasks" / "metadata").mkdir(parents=True)
        (root / "aitasks" / "archived").mkdir()
        config = (f"project:\n  name: {project_name}\n" if project_name
                  else "project:\n  git_remote: none\n")
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            config, encoding="utf-8")
        if git:
            (root / ".aitask-scripts").symlink_to(SCRIPTS_DIR)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test")
        return root

    @staticmethod
    def _task(root: Path, task_id: str, *, archived=False, **meta) -> None:
        lines = ["---", "status: Ready", "priority: low", "effort: low"]
        for key, value in meta.items():
            lines.append(f"{key}: {value}")
        lines += ["---", "body", ""]
        directory = root / "aitasks" / ("archived" if archived else "")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"t{task_id}_task.md").write_text("\n".join(lines),
                                                       encoding="utf-8")

    def _store_trail(self, root: Path, owner_id: str, owner_ref: str,
                     members: list[str], handle: str) -> None:
        doc = _trail_doc(owner_ref, members)
        trail_schema.validate_trail(doc)   # a bad fixture is a setup error
        blob = self.base / f"{handle.replace(':', '_')}.json"
        blob.write_text(json.dumps(doc), encoding="utf-8")
        # `ait artifact create` refuses to stage an owner file with
        # uncommitted changes, so commit the task tree first.
        self._git(root, "add", "-A", "aitasks")
        self._git(root, "commit", "-q", "-m", "fixture: tasks")
        proc = subprocess.run(
            [str(root / ".aitask-scripts" / "aitask_artifact.sh"), "create",
             owner_id, str(blob), "--kind", "implementation_trail",
             "--handle", handle],
            capture_output=True, text=True, cwd=root, env=os.environ.copy(),
            timeout=120)
        if proc.returncode != 0:
            raise RuntimeError("fixture: artifact create failed: "
                               + proc.stdout + proc.stderr)

    def _register(self, *entries) -> None:
        lines = ["projects:"]
        for name, path in entries:
            lines += [f"  - name: {name}", f"    path: {path}"]
        self.registry_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _export(self, root: Path) -> dict:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "lib" / "trail_links.py"),
             "export"], capture_output=True, text=True, cwd=root,
            env={**os.environ, "TASK_DIR": "aitasks"}, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        [record] = [line for line in proc.stdout.splitlines()
                    if line.startswith(tl.EXPORT_PREFIX)]
        return json.loads(record[len(tl.EXPORT_PREFIX):])

    def _y_with_reverse_dep(self, project_name, member_name) -> Path:
        """Y's trail lists its own t7, which xdeps back to X's t42."""
        y = self._repo("y", project_name)
        self._task(y, "5")
        self._task(y, "7", xdeprepo=self.X_REG, xdeps="[42]")
        self._store_trail(y, "5", f"{member_name}#5",
                          [f"{member_name}#5", f"{member_name}#7"],
                          "art:fixy-trail")
        return y

    def test_export_reports_members_and_active_and_archived_metadata(self):
        y = self._repo("y", self.Y_NAME)
        self._task(y, "5")
        self._task(y, "7", xdeprepo="other", xdeps="[t3]")
        self._task(y, "9", archived=True, xdeprepo="other2", xdeps="[4]")
        self._store_trail(y, "5", f"{self.Y_NAME}#5",
                          [f"{self.Y_NAME}#5", f"{self.Y_NAME}#7",
                           f"{self.Y_NAME}#9", "other#3"], "art:fixy-trail")
        data = self._export(y)
        self.assertEqual(data["local_project"], self.Y_NAME)
        self.assertEqual((data["unreadable"], data["scan_errors"]), ([], []))
        [trail] = data["trails"]
        self.assertEqual(trail["handle"], "art:fixy-trail")
        self.assertEqual(trail["load_error"], "")
        self.assertEqual(trail["members"], sorted(
            [f"{self.Y_NAME}#5", f"{self.Y_NAME}#7", f"{self.Y_NAME}#9",
             "other#3"]))
        self.assertEqual(data["tasks"], {
            "3": {"state": "missing"},
            "5": _ok(),
            "7": _ok("other", "3"),
            "9": _ok("other2", "4"),
        })

    def test_export_without_project_name_succeeds(self):
        y = self._repo("y", None)
        data = self._export(y)
        self.assertEqual((data["local_project"], data["trails"]), ("", []))

    @unittest.skipUnless(os.access(PYPY, os.X_OK), "no PyPy runtime installed")
    def test_export_spawned_from_pypy_is_read(self):
        """The board runs on PyPy, so the scan's ``sys.executable`` can be
        PyPy, whose PyYAML import prints to stdout before the record."""
        y = self._repo("y", self.Y_NAME)
        with patch.object(sys, "executable", PYPY):
            export, errors = tl._collect_export(self.Y_NAME, str(y))
        self.assertEqual(errors, [])
        self.assertEqual(export.data["local_project"], self.Y_NAME)

    def _scan_x(self):
        return tl.scan_linked_trails(_doc(f"{self.X_PROJECT}#42"))

    def test_reverse_dependency_found_when_the_other_repo_has_no_project_name(self):
        y = self._y_with_reverse_dep(None, self.Y_NAME)
        self._register((self.Y_NAME, y), (self.X_REG, self.x))
        scan = self._scan_x()
        self.assertEqual(scan.errors, [])
        self.assertTrue(scan.complete)
        self.assertEqual(scan.links, [tl.LinkedTrail(
            project=self.Y_NAME, root=str(y), handle="art:fixy-trail",
            name="Linked fixture trail",
            reasons=(f"rev-xdeps: {self.Y_NAME}#7 xdeps {self.X_REG}#42",))])

    def test_reverse_dependency_found_through_a_registry_alias(self):
        alias = f"{self.Y_NAME}alias"
        y = self._y_with_reverse_dep(self.Y_NAME, alias)
        self._register((self.Y_NAME, y), (alias, y), (self.X_REG, self.x))
        scan = self._scan_x()
        self.assertTrue(scan.complete, scan.errors)
        self.assertEqual([l.reasons for l in scan.links],
                         [(f"rev-xdeps: {alias}#7 xdeps {self.X_REG}#42",)])

    def test_forward_dependency_found(self):
        self._task(self.x, "42", xdeprepo=self.Y_NAME, xdeps="[7]")
        y = self._repo("y", self.Y_NAME)
        self._task(y, "5")
        self._task(y, "7")
        self._store_trail(y, "5", f"{self.Y_NAME}#5",
                          [f"{self.Y_NAME}#5", f"{self.Y_NAME}#7"],
                          "art:fixy-trail")
        self._register((self.Y_NAME, y))
        scan = self._scan_x()
        self.assertTrue(scan.complete, scan.errors)
        self.assertEqual(
            [l.reasons for l in scan.links],
            [(f"fwd-xdeps: {self.X_PROJECT}#42 xdeps {self.Y_NAME}#7",)])

    def test_corrupt_archive_makes_the_scan_incomplete(self):
        """A corrupt bundle could hide a trail owner or a member's xdeps:
        the scan must say so, never report a definitive result."""
        y = self._y_with_reverse_dep(self.Y_NAME, self.Y_NAME)
        bundle = y / "aitasks" / "archived" / "_b0"
        bundle.mkdir()
        (bundle / "old0.tar.gz").write_bytes(b"not a gzip stream")
        self._register((self.Y_NAME, y), (self.X_REG, self.x))
        scan = self._scan_x()
        self.assertEqual(len(scan.links), 1)     # what could be read is kept
        self.assertFalse(scan.complete)
        self.assertEqual([(e.project, e.kind) for e in scan.errors],
                         [(self.Y_NAME, tl.PARTIAL)])
        self.assertIn("old0.tar.gz", scan.errors[0].detail)

    def test_inaccessible_archive_holding_the_owner_makes_the_scan_incomplete(self):
        """The trail's owner is archived, and the archive directory cannot be
        listed: Path.glob would read it as empty and the scan as complete."""
        y = self._y_with_reverse_dep(self.Y_NAME, self.Y_NAME)
        owner = y / "aitasks" / "t5_task.md"
        owner.rename(y / "aitasks" / "archived" / owner.name)
        archived = y / "aitasks" / "archived"
        archived.chmod(0o000)
        self.addCleanup(archived.chmod, 0o755)
        if os.access(archived, os.R_OK):
            self.skipTest("running with permissions that ignore mode 000")
        self._register((self.Y_NAME, y), (self.X_REG, self.x))
        scan = self._scan_x()
        self.assertEqual(scan.links, [])
        self.assertFalse(scan.complete)
        self.assertEqual([(e.project, e.kind) for e in scan.errors],
                         [(self.Y_NAME, tl.PARTIAL)])
        # Paths in an export are relative to that project's root.
        self.assertIn("aitasks/archived: [Errno 13]", scan.errors[0].detail)

    def test_undecodable_export_output_is_an_export_failure(self):
        """Subprocess output is decoded leniently: undecodable bytes from an
        export must become an error row, never an exception in the worker."""
        fake = self.base / "fake_export.py"
        fake.write_text(
            "import sys\n"
            "sys.stdout.buffer.write(b'\\xff\\xfe noise\\n')\n"
            "sys.stderr.buffer.write(b'Boom \\xff\\n')\n"
            "sys.exit(1)\n", encoding="utf-8")
        y = self._repo("y", self.Y_NAME, git=False)
        with patch.object(tl, "_THIS_FILE", str(fake)):
            export, errors = tl._collect_export(self.Y_NAME, str(y))
        self.assertIsNone(export)
        self.assertEqual([(e.kind, e.detail) for e in errors],
                         [(tl.EXPORT_FAILED, "Boom �")])

    def test_malformed_archived_owner_makes_the_scan_incomplete(self):
        y = self._y_with_reverse_dep(self.Y_NAME, self.Y_NAME)
        (y / "aitasks" / "archived" / "t20_owner.md").write_text(
            "---\nartifacts: [unclosed\n---\n", encoding="utf-8")
        self._register((self.Y_NAME, y), (self.X_REG, self.x))
        scan = self._scan_x()
        self.assertFalse(scan.complete)
        self.assertEqual([(e.project, e.kind) for e in scan.errors],
                         [(self.Y_NAME, tl.PARTIAL)])
        self.assertIn("t20_owner.md", scan.errors[0].detail)


if __name__ == "__main__":
    unittest.main()

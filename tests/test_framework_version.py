#!/usr/bin/env python3
"""Tests for the headless framework-version model (t1223_2).

Covers version reading, latest-version resolution (offline degradation and
process-group cleanup), semver comparison, self-target detection, activity
classification (widened busy set + fail-closed classifier), shell-safe
upgrade-command construction (structural and executed), and the atomic
handoff-request write — all against fixture roots, never cwd, and without
any tmux calls.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

import framework_version as fv  # noqa: E402


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fv_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make_root(self, version_text=None, name="repo"):
        root = self.tmp / name
        (root / ".aitask-scripts").mkdir(parents=True)
        if version_text is not None:
            (root / ".aitask-scripts" / "VERSION").write_text(version_text)
        return root


class ReadInstalledVersionTests(TempDirTestCase):
    def test_valid_file(self):
        root = self.make_root("0.28.0\n")
        self.assertEqual(fv.read_installed_version(root), "0.28.0")

    def test_missing_version_file(self):
        root = self.make_root(None)
        self.assertIsNone(fv.read_installed_version(root))

    def test_missing_scripts_dir(self):
        root = self.tmp / "empty_root"
        root.mkdir()
        self.assertIsNone(fv.read_installed_version(root))

    def test_blank_file(self):
        root = self.make_root("   \n")
        self.assertIsNone(fv.read_installed_version(root))

    def test_whitespace_and_v_prefix_stripped(self):
        root = self.make_root("  v0.28.0  \n")
        self.assertEqual(fv.read_installed_version(root), "0.28.0")

    @unittest.skipIf(os.geteuid() == 0, "root ignores file permissions")
    def test_unreadable_returns_none(self):
        root = self.make_root("0.28.0\n")
        version_file = root / ".aitask-scripts" / "VERSION"
        version_file.chmod(0)
        self.addCleanup(version_file.chmod, stat.S_IRUSR | stat.S_IWUSR)
        self.assertIsNone(fv.read_installed_version(root))


class VersionStatusTests(unittest.TestCase):
    def test_up_to_date(self):
        self.assertEqual(fv.version_status("0.28.0", "0.28.0"), "up_to_date")

    def test_short_and_long_forms_equal(self):
        self.assertEqual(fv.version_status("1.2", "1.2.0"), "up_to_date")

    def test_behind(self):
        self.assertEqual(fv.version_status("0.27.3", "0.28.0"), "behind")

    def test_ahead(self):
        self.assertEqual(fv.version_status("0.29.0", "0.28.0"), "ahead")

    def test_none_sides(self):
        self.assertEqual(fv.version_status(None, "0.28.0"), "unknown")
        self.assertEqual(fv.version_status("0.28.0", None), "unknown")
        self.assertEqual(fv.version_status(None, None), "unknown")

    def test_non_numeric_component(self):
        self.assertEqual(fv.version_status("0.28.x", "0.28.0"), "unknown")
        self.assertEqual(fv.version_status("0.28.0", "latest"), "unknown")
        self.assertEqual(fv.version_status("", "0.28.0"), "unknown")


class ResolveLatestVersionTests(TempDirTestCase):
    def write_stub(self, body):
        stub = self.tmp / "stub_release.sh"
        stub.write_text("github_resolve_latest_version() {\n%s\n}\n" % body)
        return stub

    def test_success(self):
        stub = self.write_stub('    echo "0.29.1"')
        self.assertEqual(
            fv.resolve_latest_version(helper=stub), ("0.29.1", None)
        )

    def test_helper_failure_degrades(self):
        stub = self.write_stub('    echo "NOTFOUND" >&2\n    return 3')
        version, reason = fv.resolve_latest_version(helper=stub)
        self.assertIsNone(version)
        self.assertEqual(reason, "NOTFOUND")

    def test_unparseable_output_degrades(self):
        stub = self.write_stub('    echo "garbage output"')
        version, reason = fv.resolve_latest_version(helper=stub)
        self.assertIsNone(version)
        self.assertIn("unparseable", reason)

    def test_missing_helper_degrades(self):
        version, reason = fv.resolve_latest_version(
            helper=self.tmp / "does_not_exist.sh"
        )
        self.assertIsNone(version)
        self.assertTrue(reason)

    def test_timeout_degrades_and_kills_grandchild(self):
        pidfile = self.tmp / "grandchild.pid"
        stub = self.write_stub(
            "    sleep 60 &\n"
            "    echo $! > %s\n"
            "    wait" % shlex.quote(str(pidfile))
        )
        start = time.monotonic()
        version, reason = fv.resolve_latest_version(timeout=0.5, helper=stub)
        elapsed = time.monotonic() - start
        self.assertIsNone(version)
        self.assertIn("timeout", reason)
        self.assertLess(elapsed, 10.0)
        # The process-group kill must take the sleep grandchild down too —
        # a plain child kill would leave it running for 60s.
        pid = int(pidfile.read_text().strip())
        for _ in range(40):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            os.kill(pid, 9)
            self.fail("grandchild sleep survived the timeout kill")


class IsSelfTargetTests(TempDirTestCase):
    def test_same_path(self):
        root = self.make_root()
        self.assertTrue(fv.is_self_target(root, root))

    def test_symlink_resolves_to_same_realpath(self):
        root = self.make_root()
        link = self.tmp / "link"
        link.symlink_to(root)
        self.assertTrue(fv.is_self_target(link, root))
        self.assertTrue(fv.is_self_target(root, link))

    def test_trailing_slash(self):
        root = self.make_root()
        self.assertTrue(fv.is_self_target(str(root) + "/", root))

    def test_different_path(self):
        root = self.make_root(name="repo_a")
        other = self.make_root(name="repo_b")
        self.assertFalse(fv.is_self_target(root, other))


class DetectTargetActivityTests(unittest.TestCase):
    def test_no_windows_idle(self):
        self.assertEqual(fv.detect_target_activity("s", []), "idle")

    def test_plain_shells_idle(self):
        windows = [("0", "zsh"), ("1", "vim"), ("2", "bash")]
        self.assertEqual(fv.detect_target_activity("s", windows), "idle")

    def test_known_tui_busy(self):
        windows = [("0", "zsh"), ("1", "board")]
        self.assertEqual(
            fv.detect_target_activity("s", windows), "busy:board"
        )

    def test_agent_window_busy(self):
        windows = [("0", "agent-syncfix-pull")]
        self.assertEqual(
            fv.detect_target_activity("s", windows), "busy:agent-syncfix-pull"
        )

    def test_create_window_busy(self):
        windows = [("0", "create-t42")]
        self.assertEqual(
            fv.detect_target_activity("s", windows), "busy:create-t42"
        )

    def test_widened_registry_names_busy(self):
        # brainstorm / minimonitor / git are NOT in the switcher subset but
        # ARE framework TUIs (tui_registry.TUI_NAMES); brainstorm-<N> is the
        # per-task prefix. All must block an upgrade.
        for name in ("brainstorm", "minimonitor", "git", "brainstorm-42"):
            self.assertEqual(
                fv.detect_target_activity("s", [("0", name)]),
                "busy:" + name,
            )

    def test_mixed_lists_only_offenders_in_order(self):
        windows = [
            ("0", "zsh"), ("1", "syncer"), ("2", "vim"),
            ("3", "agent-t99-fix"),
        ]
        self.assertEqual(
            fv.detect_target_activity("s", windows),
            "busy:syncer,agent-t99-fix",
        )

    def test_registry_failure_prefix_hit_still_busy(self):
        with mock.patch.dict(sys.modules, {"tui_registry": None}):
            self.assertEqual(
                fv.detect_target_activity("s", [("0", "agent-x")]),
                "busy:agent-x",
            )

    def test_registry_failure_is_fail_closed_never_idle(self):
        # Negative control: with the registry unavailable, windows that
        # cannot be classified must yield unknown — a fallback returning
        # "idle" would silently disable the mixed-version safety control.
        with mock.patch.dict(sys.modules, {"tui_registry": None}):
            result = fv.detect_target_activity(
                "s", [("0", "zsh"), ("1", "board")]
            )
        self.assertEqual(result, "unknown:tui-registry-unavailable")
        self.assertNotEqual(result, "idle")

    def test_registry_failure_no_windows_unknown(self):
        with mock.patch.dict(sys.modules, {"tui_registry": None}):
            self.assertEqual(
                fv.detect_target_activity("s", []),
                "unknown:tui-registry-unavailable",
            )


NASTY_ROOTS = [
    "has space",
    "dol$lar",
    "semi;colon",
    "a && b",
    "sq'uote",
    'dq"uote',
    "back`tick",
]


class BuildUpgradeCommandTests(TempDirTestCase):
    def test_quoting_structural(self):
        # Tokenize the WHOLE command with shlex, then split the token list
        # on the standalone `&&` token — never the raw string, which a
        # quoted path containing ` && ` would defeat.
        for nasty in NASTY_ROOTS:
            root = self.tmp / nasty
            command, parts = fv.build_upgrade_command(root, "1.2.3")
            tokens = shlex.split(command)
            self.assertEqual(
                tokens.count("&&"), 1, "root %r: %r" % (nasty, tokens)
            )
            split_at = tokens.index("&&")
            expected_ait = str(root / "ait")
            self.assertEqual(
                tokens[:split_at], [expected_ait, "upgrade", "1.2.3"]
            )
            self.assertEqual(tokens[split_at + 1:], [expected_ait, "setup"])
            self.assertEqual(parts, [shlex.quote(expected_ait), "1.2.3"])

    def test_rejects_invalid_versions(self):
        for bad in ("", "; rm -rf /", "1.2.3; ls", "$(id)", "v1.2.3"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                fv.build_upgrade_command("/tmp/repo", bad)

    def test_accepts_valid_versions(self):
        for good in ("latest", "1.2", "0.28.0"):
            command, parts = fv.build_upgrade_command("/tmp/repo", good)
            self.assertIn("upgrade %s &&" % good, command)
            self.assertEqual(parts[1], good)


class FailureChainTests(TempDirTestCase):
    """Execute the built command against stub `ait` binaries: proves the
    `&&` prevents `setup` after a failed upgrade, and that quoting survives
    a real shell in roots containing special characters."""

    def make_stub_root(self, name, exit_code):
        root = self.tmp / name
        root.mkdir(parents=True)
        log = root / "calls.log"
        (root / "ait").write_text(
            "#!/usr/bin/env bash\n"
            'echo "$1" >> %s\n'
            "exit %d\n" % (shlex.quote(str(log)), exit_code)
        )
        (root / "ait").chmod(0o755)
        return root, log

    def read_log(self, log):
        return log.read_text().split() if log.exists() else []

    def test_failed_upgrade_blocks_setup(self):
        root, log = self.make_stub_root("failing", exit_code=1)
        command, _ = fv.build_upgrade_command(root, "1.2.3")
        result = subprocess.run(command, shell=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.read_log(log), ["upgrade"])

    def test_successful_upgrade_runs_setup_in_order(self):
        root, log = self.make_stub_root("passing", exit_code=0)
        command, _ = fv.build_upgrade_command(root, "1.2.3")
        result = subprocess.run(command, shell=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.read_log(log), ["upgrade", "setup"])

    def test_executed_quoting_in_nasty_roots(self):
        for nasty in NASTY_ROOTS:
            root, log = self.make_stub_root(
                Path("nasty") / nasty, exit_code=0
            )
            command, _ = fv.build_upgrade_command(root, "latest")
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True
            )
            self.assertEqual(
                result.returncode, 0,
                "root %r: %s" % (nasty, result.stderr),
            )
            self.assertEqual(
                self.read_log(log), ["upgrade", "setup"], "root %r" % nasty
            )


class HandoffRequestTests(TempDirTestCase):
    def test_build_exact_keys_and_absolute_root(self):
        request = fv.build_handoff_request("relative/repo", "0.28.0")
        self.assertEqual(set(request), {"root", "version"})
        self.assertTrue(os.path.isabs(request["root"]))
        self.assertEqual(request["version"], "0.28.0")

    def test_build_rejects_invalid_version(self):
        with self.assertRaises(ValueError):
            fv.build_handoff_request("/tmp/repo", "1.2.3; ls")

    def assert_no_temp_residue(self):
        leftovers = [
            p.name for p in self.tmp.iterdir()
            if p.name.startswith(".handoff.")
        ]
        self.assertEqual(leftovers, [])

    def test_write_round_trips_without_residue(self):
        target = self.tmp / "request.json"
        request = {"root": "/tmp/repo", "version": "latest"}
        fv.write_handoff_request(target, request)
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), request)
        self.assert_no_temp_residue()

    def test_serialization_failure_cleans_temp(self):
        target = self.tmp / "request.json"
        with self.assertRaises(TypeError):
            fv.write_handoff_request(target, {"root": {1, 2}})
        self.assertFalse(target.exists())
        self.assert_no_temp_residue()

    def test_replace_failure_cleans_temp(self):
        target = self.tmp / "request.json"
        target.mkdir()  # os.replace onto an existing directory fails
        with self.assertRaises(OSError):
            fv.write_handoff_request(
                target, {"root": "/tmp/repo", "version": "latest"}
            )
        self.assert_no_temp_residue()


if __name__ == "__main__":
    unittest.main(verbosity=2)

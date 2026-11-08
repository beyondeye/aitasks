"""Tests for lib/relations_config.py (t1981_3): loader, surgical edits, project-name rule.

Run: python3 tests/test_relations_config.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"))

import relations_config as rc  # noqa: E402
import yaml  # noqa: E402

COMMENTED = """\
# Top comment that must survive.
project:
  # name comment
  git_remote: https://example.com/x.git

codeagent_coauthor_domain: aitasks.io  # trailing comment
tmux:
  monitor:
    refresh_seconds: 3
  # indented comment
  git_tui: lazygit
"""


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="relations-config-")
        self.root = Path(self._tmp.name) / "repo"
        (self.root / "aitasks" / "metadata").mkdir(parents=True)
        self.cfg = self.root / "aitasks" / "metadata" / "project_config.yaml"
        self._env = mock.patch.dict(os.environ, {
            "AITASKS_PROJECTS_INDEX": str(Path(self._tmp.name) / "projects.yaml"),
            "HOME": self._tmp.name, "AIT_PYTHON": sys.executable})
        self._env.start()
        os.environ.pop("TASK_DIR", None)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def registry(self, *names, path=None):
        path = path or self.root
        lines = [f"- name: {n}\n  path: {path}\n" for n in names]
        Path(os.environ["AITASKS_PROJECTS_INDEX"]).write_text("".join(lines))


class LoadTests(Base):
    def test_defaults_and_absent_key(self):
        self.cfg.write_text("project:\n  name: p\n")
        cfg = rc.load(self.root)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.enabled_key, "absent")
        self.assertEqual((cfg.max_jobs_per_day, cfg.job_timeout_s, cfg.settle_s, cfg.candidate_cap),
                         (40, 600, 120, 25))
        self.assertTrue(cfg.trigger_enabled("fold"))

    def test_values_and_invalid_knobs(self):
        self.cfg.write_text("relations:\n  enabled: true\n  max_jobs_per_day: -3\n  settle_s: 0\n"
                            "  job_timeout_s: abc\n  triggers: {fold: false}\n")
        cfg = rc.load(self.root)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.max_jobs_per_day, 40)  # nonsense -> default
        self.assertEqual(cfg.settle_s, 0)           # 0 is meaningful for settle
        self.assertEqual(cfg.job_timeout_s, 600)
        self.assertFalse(cfg.trigger_enabled("fold"))
        self.cfg.write_text("relations:\n  enabled: yes-please\n")
        self.assertEqual((rc.load(self.root).enabled, rc.load(self.root).enabled_key), (False, "invalid"))

    def test_unreadable_config_is_disabled(self):
        self.cfg.write_text("relations: [unclosed\n")
        self.assertFalse(rc.load(self.root).enabled)


class EditTests(Base):
    def test_insert_into_existing_block_keeps_comments(self):
        self.cfg.write_text(COMMENTED)
        rc.seed_project_name(self.root, "myproj")
        text = self.cfg.read_text()
        self.assertIn("# Top comment that must survive.", text)
        self.assertIn("  # name comment", text)
        self.assertIn("aitasks.io  # trailing comment", text)
        self.assertEqual(yaml.safe_load(text)["project"]["name"], "myproj")
        self.assertEqual(text.count("project:"), 1)

    def test_append_block_and_replace_value(self):
        self.cfg.write_text(COMMENTED)
        rc.set_enabled(self.root, True)
        self.assertIs(yaml.safe_load(self.cfg.read_text())["relations"]["enabled"], True)
        rc.set_enabled(self.root, False)
        text = self.cfg.read_text()
        self.assertIs(yaml.safe_load(text)["relations"]["enabled"], False)
        self.assertEqual(text.count("enabled:"), 1)

    def test_existing_relations_block_without_enabled(self):
        self.cfg.write_text("relations:\n  # knobs\n  max_jobs_per_day: 5\n  triggers:\n    fold: false\n"
                            "other: 1\n")
        rc.set_enabled(self.root, True)
        data = yaml.safe_load(self.cfg.read_text())
        self.assertEqual(data["relations"], {"enabled": True, "max_jobs_per_day": 5,
                                             "triggers": {"fold": False}})
        self.assertEqual(data["other"], 1)

    def test_nested_key_with_same_name_is_not_touched(self):
        self.cfg.write_text("relations:\n  triggers:\n    enabled: 7\n")
        rc.set_enabled(self.root, True)
        data = yaml.safe_load(self.cfg.read_text())
        self.assertEqual(data["relations"]["triggers"], {"enabled": 7})
        self.assertIs(data["relations"]["enabled"], True)

    def test_flow_style_block_refused_untouched(self):
        self.cfg.write_text("relations: {max_jobs_per_day: 5}\n")
        before = self.cfg.read_text()
        with self.assertRaisesRegex(rc.ConfigWriteError, "unsupported_shape"):
            rc.set_enabled(self.root, True)
        self.assertEqual(self.cfg.read_text(), before)

    def test_readback_guard_refuses_a_wrong_edit(self):
        self.cfg.write_text("relations:\n  enabled: false\n")
        before = self.cfg.read_text()
        with mock.patch.object(rc, "edit_nested", lambda text, b, k, v: text + "extra: 1\n"):
            with self.assertRaisesRegex(rc.ConfigWriteError, "readback_mismatch"):
                rc.set_enabled(self.root, True)
        self.assertEqual(self.cfg.read_text(), before)

    def test_symlinked_config_is_written_through(self):
        real = Path(self._tmp.name) / "real_config.yaml"
        real.write_text("project:\n  name: p\n")
        self.cfg.symlink_to(real)
        rc.set_enabled(self.root, True)
        self.assertTrue(self.cfg.is_symlink())
        self.assertIs(yaml.safe_load(real.read_text())["relations"]["enabled"], True)

    def test_name_that_yaml_would_retype_is_quoted(self):
        self.cfg.write_text("other: 1\n")
        rc.seed_project_name(self.root, "123")
        self.assertEqual(yaml.safe_load(self.cfg.read_text())["project"]["name"], "123")


class ProjectNameTests(Base):
    def test_existing_valid_name_is_kept(self):
        self.cfg.write_text("project:\n  name: keepme\n")
        self.registry("other")
        self.assertEqual(rc.resolve_project_name(self.root), ("kept", "keepme"))

    def test_invalid_existing_name_refuses(self):
        self.cfg.write_text("project:\n  name: Bad Name\n")
        with self.assertRaisesRegex(rc.ProjectUnresolved, "invalid project.name"):
            rc.resolve_project_name(self.root)

    def test_one_registry_binding_is_seeded(self):
        self.cfg.write_text("other: 1\n")
        self.registry("myrepo")
        self.assertEqual(rc.resolve_project_name(self.root), ("seeded", "myrepo"))
        self.assertEqual(yaml.safe_load(self.cfg.read_text())["project"]["name"], "myrepo")

    def test_zero_or_several_bindings_refuse_untouched(self):
        self.cfg.write_text("other: 1\n")
        before = self.cfg.read_text()
        with self.assertRaisesRegex(rc.ProjectUnresolved, "no registry entry"):
            rc.resolve_project_name(self.root)
        self.registry("a", "b")
        with self.assertRaisesRegex(rc.ProjectUnresolved, "several names"):
            rc.resolve_project_name(self.root)
        self.assertEqual(self.cfg.read_text(), before)

    def test_incomplete_registry_refuses(self):
        self.cfg.write_text("other: 1\n")
        os.mkdir(os.environ["AITASKS_PROJECTS_INDEX"])  # unreadable as a file
        with self.assertRaisesRegex(rc.ProjectUnresolved, "could not be read completely"):
            rc.resolve_project_name(self.root)

    def test_cli_set_enabled_true_refuses_without_name(self):
        self.cfg.write_text("other: 1\n")
        with mock.patch("sys.stdout") as out:
            rc_code = rc.main(["set-enabled", str(self.root), "true"])
        self.assertEqual(rc_code, 1)
        self.assertNotIn("relations", yaml.safe_load(self.cfg.read_text()))
        self.assertTrue(any("PROJECT_UNRESOLVED:" in str(c) for c in out.write.call_args_list))


if __name__ == "__main__":
    unittest.main()

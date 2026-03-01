"""Unit tests for config_utils.py layered config loading/saving (t268_3).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_config_utils.py -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "aiscripts", "lib"))
from config_utils import (
    deep_merge,
    export_all_configs,
    import_all_configs,
    load_layered_config,
    local_path_for,
    save_local_config,
    save_project_config,
    split_config,
)


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge(unittest.TestCase):
    def test_scalar_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 99})

    def test_nested_dict_merge(self):
        base = {"s": {"x": 1, "y": 2}}
        override = {"s": {"y": 99, "z": 3}}
        result = deep_merge(base, override)
        self.assertEqual(result, {"s": {"x": 1, "y": 99, "z": 3}})

    def test_list_replacement(self):
        base = {"items": [1, 2, 3]}
        override = {"items": [10, 20]}
        result = deep_merge(base, override)
        self.assertEqual(result, {"items": [10, 20]})

    def test_base_keys_preserved(self):
        base = {"a": 1, "b": 2}
        override = {"c": 3}
        result = deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})

    def test_override_keys_added(self):
        base = {}
        override = {"new": "value"}
        result = deep_merge(base, override)
        self.assertEqual(result, {"new": "value"})

    def test_empty_override(self):
        base = {"a": 1}
        result = deep_merge(base, {})
        self.assertEqual(result, {"a": 1})

    def test_empty_base(self):
        override = {"a": 1}
        result = deep_merge({}, override)
        self.assertEqual(result, {"a": 1})

    def test_both_empty(self):
        self.assertEqual(deep_merge({}, {}), {})

    def test_deeply_nested(self):
        base = {"l1": {"l2": {"l3": {"val": "old", "keep": True}}}}
        override = {"l1": {"l2": {"l3": {"val": "new"}}}}
        result = deep_merge(base, override)
        self.assertEqual(result["l1"]["l2"]["l3"]["val"], "new")
        self.assertTrue(result["l1"]["l2"]["l3"]["keep"])

    def test_no_mutation_of_inputs(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        base_copy = {"a": {"b": 1}}
        override_copy = {"a": {"c": 2}}
        deep_merge(base, override)
        self.assertEqual(base, base_copy)
        self.assertEqual(override, override_copy)

    def test_dict_overrides_scalar(self):
        base = {"a": "string"}
        override = {"a": {"nested": True}}
        result = deep_merge(base, override)
        self.assertEqual(result, {"a": {"nested": True}})

    def test_scalar_overrides_dict(self):
        base = {"a": {"nested": True}}
        override = {"a": "string"}
        result = deep_merge(base, override)
        self.assertEqual(result, {"a": "string"})


# ---------------------------------------------------------------------------
# local_path_for
# ---------------------------------------------------------------------------


class TestLocalPathFor(unittest.TestCase):
    def test_config_json(self):
        result = local_path_for("aitasks/metadata/board_config.json")
        self.assertEqual(result, Path("aitasks/metadata/board_config.local.json"))

    def test_models_json(self):
        result = local_path_for("models_claude.json")
        self.assertEqual(result, Path("models_claude.local.json"))

    def test_path_object(self):
        result = local_path_for(Path("/tmp/test_config.json"))
        self.assertEqual(result, Path("/tmp/test_config.local.json"))


# ---------------------------------------------------------------------------
# load_layered_config
# ---------------------------------------------------------------------------


class TestLoadLayeredConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, name: str, data: dict) -> Path:
        p = self.d / name
        with open(p, "w") as f:
            json.dump(data, f)
        return p

    def test_both_files_exist(self):
        project = self._write("cfg.json", {"a": 1, "b": 2})
        local = self._write("cfg.local.json", {"b": 99, "c": 3})
        result = load_layered_config(project, local)
        self.assertEqual(result, {"a": 1, "b": 99, "c": 3})

    def test_only_project(self):
        project = self._write("cfg.json", {"a": 1})
        local = self.d / "cfg.local.json"  # does not exist
        result = load_layered_config(project, local)
        self.assertEqual(result, {"a": 1})

    def test_only_local(self):
        project = self.d / "cfg.json"  # does not exist
        local = self._write("cfg.local.json", {"b": 2})
        result = load_layered_config(project, local)
        self.assertEqual(result, {"b": 2})

    def test_neither_exists(self):
        result = load_layered_config(
            self.d / "cfg.json", self.d / "cfg.local.json"
        )
        self.assertEqual(result, {})

    def test_neither_exists_with_defaults(self):
        result = load_layered_config(
            self.d / "cfg.json",
            self.d / "cfg.local.json",
            defaults={"x": 42},
        )
        self.assertEqual(result, {"x": 42})

    def test_defaults_merged_under_project(self):
        project = self._write("cfg.json", {"a": 1})
        result = load_layered_config(
            project, self.d / "cfg.local.json", defaults={"a": 0, "d": 5}
        )
        self.assertEqual(result, {"a": 1, "d": 5})

    def test_invalid_json_raises(self):
        bad = self.d / "bad.json"
        bad.write_text("not json {{{")
        with self.assertRaises(json.JSONDecodeError):
            load_layered_config(bad)

    def test_auto_derive_local_path(self):
        project = self._write("cfg.json", {"a": 1})
        self._write("cfg.local.json", {"a": 99})
        result = load_layered_config(project)  # local_path=None
        self.assertEqual(result, {"a": 99})

    def test_nested_merge_through_layers(self):
        project = self._write(
            "cfg.json", {"settings": {"theme": "dark", "refresh": 5}}
        )
        local = self._write(
            "cfg.local.json", {"settings": {"refresh": 2}}
        )
        result = load_layered_config(project, local)
        self.assertEqual(
            result, {"settings": {"theme": "dark", "refresh": 2}}
        )


# ---------------------------------------------------------------------------
# save_project_config / save_local_config
# ---------------------------------------------------------------------------


class TestSaveConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_writes_valid_json(self):
        path = self.d / "out.json"
        save_project_config(path, {"key": "value"})
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data, {"key": "value"})

    def test_creates_parent_dirs(self):
        path = self.d / "sub" / "dir" / "out.json"
        save_project_config(path, {"a": 1})
        self.assertTrue(path.exists())

    def test_trailing_newline(self):
        path = self.d / "out.json"
        save_project_config(path, {"a": 1})
        content = path.read_text()
        self.assertTrue(content.endswith("\n"))

    def test_indent_two(self):
        path = self.d / "out.json"
        save_project_config(path, {"a": 1})
        content = path.read_text()
        self.assertIn("  ", content)

    def test_overwrites_existing(self):
        path = self.d / "out.json"
        save_project_config(path, {"old": True})
        save_project_config(path, {"new": True})
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data, {"new": True})

    def test_save_local_config_works(self):
        path = self.d / "cfg.local.json"
        save_local_config(path, {"user": "pref"})
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data, {"user": "pref"})


# ---------------------------------------------------------------------------
# split_config
# ---------------------------------------------------------------------------


class TestSplitConfig(unittest.TestCase):
    def test_partition_by_user_keys(self):
        merged = {"columns": [1, 2], "settings": {"refresh": 2}}
        proj, user = split_config(merged, user_keys={"settings"})
        self.assertEqual(proj, {"columns": [1, 2]})
        self.assertEqual(user, {"settings": {"refresh": 2}})

    def test_partition_by_project_keys(self):
        merged = {"columns": [1], "order": [2], "settings": {"a": 1}}
        proj, user = split_config(
            merged, project_keys={"columns", "order"}
        )
        self.assertEqual(proj, {"columns": [1], "order": [2], "settings": {"a": 1}})
        self.assertEqual(user, {})

    def test_overlap_goes_to_user(self):
        merged = {"a": 1, "b": 2}
        proj, user = split_config(
            merged, project_keys={"a", "b"}, user_keys={"b"}
        )
        self.assertEqual(proj, {"a": 1})
        self.assertEqual(user, {"b": 2})

    def test_unknown_keys_go_to_project(self):
        merged = {"known": 1, "unknown": 2}
        proj, user = split_config(merged, user_keys={"known"})
        self.assertEqual(proj, {"unknown": 2})
        self.assertEqual(user, {"known": 1})

    def test_no_keys_specified(self):
        merged = {"a": 1, "b": 2}
        proj, user = split_config(merged)
        self.assertEqual(proj, {"a": 1, "b": 2})
        self.assertEqual(user, {})

    def test_no_mutation(self):
        merged = {"a": {"nested": True}}
        proj, user = split_config(merged, user_keys={"a"})
        user["a"]["nested"] = False
        self.assertTrue(merged["a"]["nested"])


# ---------------------------------------------------------------------------
# export_all_configs / import_all_configs
# ---------------------------------------------------------------------------


class TestExportImport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmpdir.name)
        self.meta = self.d / "metadata"
        self.meta.mkdir()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_config(self, name: str, data: dict) -> Path:
        p = self.meta / name
        with open(p, "w") as f:
            json.dump(data, f)
        return p

    def test_discovers_config_files(self):
        self._write_config("board_config.json", {"cols": [1]})
        self._write_config("models_claude.json", {"models": []})
        # Non-matching file should be excluded
        (self.meta / "labels.txt").write_text("ui\nbackend\n")

        out = self.d / "export.json"
        bundle = export_all_configs(out, self.meta)
        self.assertIn("board_config.json", bundle["files"])
        self.assertIn("models_claude.json", bundle["files"])
        self.assertNotIn("labels.txt", bundle["files"])

    def test_export_structure(self):
        self._write_config("board_config.json", {"a": 1})
        out = self.d / "export.json"
        bundle = export_all_configs(out, self.meta)
        self.assertIn("_export_meta", bundle)
        self.assertEqual(bundle["_export_meta"]["version"], 1)
        self.assertEqual(bundle["_export_meta"]["file_count"], 1)
        self.assertIn("files", bundle)

    def test_bad_json_gets_error(self):
        (self.meta / "bad_config.json").write_text("{invalid")
        out = self.d / "export.json"
        bundle = export_all_configs(out, self.meta)
        self.assertIn("bad_config.json", bundle["files"])
        self.assertEqual(bundle["files"]["bad_config.json"]["_error"], "invalid JSON")

    def test_import_writes_files(self):
        self._write_config("board_config.json", {"a": 1})
        out = self.d / "export.json"
        export_all_configs(out, self.meta)

        # Import into a fresh dir
        dest = self.d / "dest"
        dest.mkdir()
        written = import_all_configs(out, dest)
        self.assertIn("board_config.json", written)
        with open(dest / "board_config.json") as f:
            data = json.load(f)
        self.assertEqual(data, {"a": 1})

    def test_import_no_overwrite(self):
        self._write_config("board_config.json", {"a": 1})
        out = self.d / "export.json"
        export_all_configs(out, self.meta)

        dest = self.d / "dest"
        dest.mkdir()
        (dest / "board_config.json").write_text('{"existing": true}')
        written = import_all_configs(out, dest, overwrite=False)
        self.assertNotIn("board_config.json", written)
        with open(dest / "board_config.json") as f:
            data = json.load(f)
        self.assertTrue(data["existing"])

    def test_import_overwrite(self):
        self._write_config("board_config.json", {"a": 1})
        out = self.d / "export.json"
        export_all_configs(out, self.meta)

        dest = self.d / "dest"
        dest.mkdir()
        (dest / "board_config.json").write_text('{"existing": true}')
        written = import_all_configs(out, dest, overwrite=True)
        self.assertIn("board_config.json", written)
        with open(dest / "board_config.json") as f:
            data = json.load(f)
        self.assertEqual(data, {"a": 1})

    def test_import_path_traversal_raises(self):
        bundle = {
            "_export_meta": {"version": 1, "file_count": 1},
            "files": {"../evil.json": {"bad": True}},
        }
        evil_bundle = self.d / "evil.json"
        with open(evil_bundle, "w") as f:
            json.dump(bundle, f)

        with self.assertRaises(ValueError):
            import_all_configs(evil_bundle, self.meta)

    def test_import_skips_error_entries(self):
        bundle = {
            "_export_meta": {"version": 1, "file_count": 1},
            "files": {
                "good_config.json": {"a": 1},
                "bad_config.json": {"_error": "invalid JSON", "_raw": "..."},
            },
        }
        bundle_path = self.d / "bundle.json"
        with open(bundle_path, "w") as f:
            json.dump(bundle, f)

        dest = self.d / "dest"
        dest.mkdir()
        written = import_all_configs(bundle_path, dest)
        self.assertIn("good_config.json", written)
        self.assertNotIn("bad_config.json", written)

    def test_import_missing_files_key_raises(self):
        bundle_path = self.d / "bad_bundle.json"
        with open(bundle_path, "w") as f:
            json.dump({"no_files": True}, f)

        with self.assertRaises(ValueError):
            import_all_configs(bundle_path, self.meta)

    def test_round_trip(self):
        self._write_config("board_config.json", {"cols": [1, 2], "s": {"r": 5}})
        self._write_config("codeagent_config.json", {"defaults": {"pick": "claude"}})
        self._write_config("models_claude.json", [{"name": "opus"}])

        out = self.d / "export.json"
        export_all_configs(out, self.meta)

        dest = self.d / "restored"
        dest.mkdir()
        written = import_all_configs(out, dest)
        self.assertEqual(len(written), 3)

        for name in written:
            with open(self.meta / name) as f:
                original = json.load(f)
            with open(dest / name) as f:
                restored = json.load(f)
            self.assertEqual(original, restored)


if __name__ == "__main__":
    unittest.main()

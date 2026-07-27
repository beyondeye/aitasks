"""Unit tests for the cross-repo settings seam (t1223_4).

Covers contract E (config_utils merge-mode import + atomic writes) and
contract D (cross_repo_settings provenance / diff / push).

Every fixture is a repo root under tempfile.mkdtemp() — never cwd — because the
whole point of this seam is that an answer describes one specific root.

Run: bash tests/run_all_python_tests.sh
  or: python3 tests/test_cross_repo_settings.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
_LIB = REPO_ROOT / ".aitask-scripts" / "lib"
sys.path.insert(0, str(_LIB))

import config_utils  # noqa: E402
import cross_repo_settings as crs  # noqa: E402
from config_utils import (  # noqa: E402
    ConfigImportPartialError,
    ConfigMergeError,
    import_all_configs,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def meta(self, name="dest") -> Path:
        d = self.tmp / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_json(self, path: Path, data) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def snapshot(self, path: Path) -> tuple[bytes, int]:
        """Bytes + inode. os.replace always changes the inode, so inode
        stability is a sharper 'this file was not touched' probe than bytes."""
        return path.read_bytes(), os.stat(path).st_ino


def make_repo(root: Path, project: dict | None = None, local: dict | None = None,
              models: dict[str, list[str]] | None = None,
              wrapper: bool = True) -> Path:
    """Build a minimal aitasks repo fixture at `root`.

    `wrapper=True` installs a stub aitask_codeagent.sh implementing the real
    resolution chain (local -> project -> builtin) *and honoring the same env
    overrides the real one does*, so the isolation tests exercise a faithful
    target rather than a compliant one.
    """
    meta = root / "aitasks" / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    if project is not None:
        (meta / "codeagent_config.json").write_text(
            json.dumps({"defaults": project}, indent=2) + "\n", encoding="utf-8"
        )
    if local is not None:
        (meta / "codeagent_config.local.json").write_text(
            json.dumps({"defaults": local}, indent=2) + "\n", encoding="utf-8"
        )
    for agent, names in (models or {"claudecode": ["opus5", "sonnet5"]}).items():
        (meta / f"models_{agent}.json").write_text(
            json.dumps({"models": [{"name": n, "cli_id": n} for n in names]},
                       indent=2) + "\n",
            encoding="utf-8",
        )
    if wrapper:
        scripts = root / ".aitask-scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        sh = scripts / "aitask_codeagent.sh"
        sh.write_text(
            '#!/usr/bin/env bash\n'
            'set -u\n'
            '# Mirrors lib/agent_string.sh: these are caller overrides.\n'
            'METADATA_DIR="${METADATA_DIR:-${TASK_DIR:-aitasks}/metadata}"\n'
            'DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus5}"\n'
            'op="$2"\n'
            'for f in "$METADATA_DIR/codeagent_config.local.json" '
            '"$METADATA_DIR/codeagent_config.json"; do\n'
            '  if [[ -f "$f" ]]; then\n'
            '    v=$(python3 -c "import json,sys;'
            'd=json.load(open(sys.argv[1]));'
            'print(d.get(\'defaults\',{}).get(sys.argv[2],\'\'))" '
            '"$f" "$op" 2>/dev/null) || true\n'
            '    if [[ -n "$v" ]]; then echo "AGENT_STRING:$v"; exit 0; fi\n'
            '  fi\n'
            'done\n'
            'echo "AGENT_STRING:$DEFAULT_AGENT_STRING"\n',
            encoding="utf-8",
        )
        sh.chmod(0o755)
    return root


# ---------------------------------------------------------------------------
# Contract E — argument validation (tests 1-3)
# ---------------------------------------------------------------------------


class ArgumentValidationTests(TempDirCase):
    def test_bundle_and_input_path_together_raises(self):
        dest = self.tmp / "nope"
        with self.assertRaises(ValueError):
            import_all_configs("x.json", dest, bundle={"files": {}})
        self.assertFalse(dest.exists(), "validation must precede any FS access")

    def test_neither_bundle_nor_input_path_raises(self):
        dest = self.tmp / "nope"
        with self.assertRaises(ValueError):
            import_all_configs(metadata_dir=dest)
        self.assertFalse(dest.exists())

    def test_merge_without_overwrite_raises(self):
        dest = self.tmp / "nope"
        with self.assertRaises(ValueError):
            import_all_configs(bundle={"files": {}}, metadata_dir=dest, merge=True)
        self.assertFalse(dest.exists(), "no metadata dir may be created")

    def test_missing_metadata_dir_raises(self):
        with self.assertRaises(ValueError):
            import_all_configs(bundle={"files": {}})

    def test_bundle_without_files_key_raises(self):
        with self.assertRaises(ValueError):
            import_all_configs(bundle={"nope": 1}, metadata_dir=self.meta())


# ---------------------------------------------------------------------------
# Contract E — merge semantics (tests 4-9, 16)
# ---------------------------------------------------------------------------


class MergeSemanticsTests(TempDirCase):
    def test_only_the_pushed_key_changes(self):
        """Bundle carries all 10 files; only 1 is selected."""
        meta = self.meta()
        names = [f"m{i}_config.json" for i in range(10)]
        for n in names:
            self.write_json(meta / n, {"defaults": {"op": f"v-{n}"}})
        before = {n: self.snapshot(meta / n) for n in names}

        import_all_configs(
            bundle={"files": {n: {"defaults": {"op": "NEW"}} for n in names}},
            metadata_dir=meta, overwrite=True, merge=True,
            selected_files=[names[0]],
        )

        self.assertEqual(
            json.loads((meta / names[0]).read_text())["defaults"]["op"], "NEW"
        )
        for n in names[1:]:
            self.assertEqual(
                self.snapshot(meta / n), before[n],
                f"{n} must be byte- and inode-identical",
            )

    def test_unrelated_top_level_key_survives(self):
        meta = self.meta()
        target = self.write_json(
            meta / "codeagent_config.json",
            {"defaults": {"pick": "a/b"}, "custom": {"keep": True}},
        )
        import_all_configs(
            bundle={"files": {"codeagent_config.json":
                              {"defaults": {"explore": "c/d"}}}},
            metadata_dir=meta, overwrite=True, merge=True,
        )
        data = json.loads(target.read_text())
        self.assertEqual(data["custom"], {"keep": True})
        self.assertEqual(data["defaults"], {"pick": "a/b", "explore": "c/d"})

    def test_nested_sibling_survives_deep_merge(self):
        """Discriminates deep_merge from a shallow dict.update()."""
        meta = self.meta()
        target = self.write_json(meta / "a_config.json", {"a": {"x": 1, "y": 2}})
        import_all_configs(
            bundle={"files": {"a_config.json": {"a": {"x": 9}}}},
            metadata_dir=meta, overwrite=True, merge=True,
        )
        self.assertEqual(json.loads(target.read_text()), {"a": {"x": 9, "y": 2}})

    def test_malformed_destination_fails_closed(self):
        meta = self.meta()
        target = meta / "a_config.json"
        target.write_text("{not json", encoding="utf-8")
        before = self.snapshot(target)

        with self.assertRaises(json.JSONDecodeError):
            import_all_configs(
                bundle={"files": {"a_config.json": {"k": 1}}},
                metadata_dir=meta, overwrite=True, merge=True,
            )
        self.assertEqual(self.snapshot(target), before)

    def test_malformed_destination_not_selected_does_not_raise(self):
        meta = self.meta()
        (meta / "bad_config.json").write_text("{not json", encoding="utf-8")
        import_all_configs(
            bundle={"files": {"bad_config.json": {"k": 1},
                              "good_config.json": {"k": 2}}},
            metadata_dir=meta, overwrite=True, merge=True,
            selected_files=["good_config.json"],
        )
        self.assertEqual(
            json.loads((meta / "good_config.json").read_text()), {"k": 2}
        )

    def test_type_conflict_both_directions(self):
        meta = self.meta()
        cases = [
            ({"defaults": {"a": 1}}, {"defaults": "oops"}),   # dict <- scalar
            ({"defaults": "oops"}, {"defaults": {"a": 1}}),   # scalar <- dict
        ]
        for existing, incoming in cases:
            with self.subTest(existing=existing):
                target = self.write_json(meta / "c_config.json", existing)
                before = self.snapshot(target)
                with self.assertRaises(ConfigMergeError) as ctx:
                    import_all_configs(
                        bundle={"files": {"c_config.json": incoming}},
                        metadata_dir=meta, overwrite=True, merge=True,
                    )
                self.assertNotIsInstance(ctx.exception, json.JSONDecodeError)
                self.assertIn("defaults", str(ctx.exception))
                self.assertEqual(self.snapshot(target), before)

    def test_whole_file_shapes(self):
        meta = self.meta()

        # list into a MISSING destination: round-trip parity, must not raise
        import_all_configs(
            bundle={"files": {"models_x.json": [{"name": "a"}]}},
            metadata_dir=meta, overwrite=True, merge=True,
        )
        self.assertEqual(
            json.loads((meta / "models_x.json").read_text()), [{"name": "a"}]
        )

        # list into a list destination: replace
        import_all_configs(
            bundle={"files": {"models_x.json": [{"name": "b"}]}},
            metadata_dir=meta, overwrite=True, merge=True,
        )
        self.assertEqual(
            json.loads((meta / "models_x.json").read_text()), [{"name": "b"}]
        )

        # list into a dict destination: conflict
        self.write_json(meta / "d_config.json", {"defaults": {}})
        with self.assertRaises(ConfigMergeError):
            import_all_configs(
                bundle={"files": {"d_config.json": [1, 2]}},
                metadata_dir=meta, overwrite=True, merge=True,
            )

        # directory at the config path: typed, not IsADirectoryError
        (meta / "e_config.json").mkdir()
        with self.assertRaises(ConfigMergeError):
            import_all_configs(
                bundle={"files": {"e_config.json": {"k": 1}}},
                metadata_dir=meta, overwrite=True, merge=True,
            )

        # destination holding `null`
        (meta / "f_config.json").write_text("null", encoding="utf-8")
        with self.assertRaises(ConfigMergeError):
            import_all_configs(
                bundle={"files": {"f_config.json": {"k": 1}}},
                metadata_dir=meta, overwrite=True, merge=True,
            )

    def test_merge_into_missing_destination(self):
        meta = self.meta()
        written = import_all_configs(
            bundle={"files": {"new_config.json": {"defaults": {"pick": "a/b"}}}},
            metadata_dir=meta, overwrite=True, merge=True,
        )
        self.assertEqual(written, ["new_config.json"])
        self.assertTrue((meta / "new_config.json").is_file())


# ---------------------------------------------------------------------------
# Contract E — atomicity, staging, modes, symlinks (tests 10-13)
# ---------------------------------------------------------------------------


class AtomicWriteTests(TempDirCase):
    def temps(self, d: Path) -> list[Path]:
        return [p for p in d.iterdir() if p.name.endswith(".tmp")]

    def test_failed_replace_leaves_original_and_no_residue(self):
        meta = self.meta()
        target = self.write_json(meta / "a_config.json", {"k": "old"})
        before = self.snapshot(target)

        with mock.patch.object(config_utils, "_os_replace",
                               side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                config_utils.save_project_config(target, {"k": "new"})

        self.assertEqual(self.snapshot(target), before)
        self.assertEqual(self.temps(meta), [], "no .tmp residue")

    def test_stage1_failure_writes_nothing(self):
        meta = self.meta()
        good = self.write_json(meta / "good_config.json", {"k": "old"})
        (meta / "bad_config.json").write_text("{not json", encoding="utf-8")
        before = self.snapshot(good)

        with self.assertRaises(json.JSONDecodeError):
            import_all_configs(
                bundle={"files": {"good_config.json": {"k": "new"},
                                  "bad_config.json": {"k": "new"}}},
                metadata_dir=meta, overwrite=True, merge=True,
            )
        self.assertEqual(self.snapshot(good), before)
        self.assertEqual(self.temps(meta), [])

    def test_stage3_partial_application_is_visible(self):
        """A commit failure after file 1 landed must not read as 'nothing changed'."""
        meta = self.meta()
        a = self.write_json(meta / "a_config.json", {"k": "old"})
        b = self.write_json(meta / "b_config.json", {"k": "old"})
        b_before = self.snapshot(b)
        real = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("commit failed")
            return real(src, dst)

        with mock.patch.object(config_utils, "_os_replace", side_effect=flaky):
            with self.assertRaises(ConfigImportPartialError) as ctx:
                import_all_configs(
                    bundle={"files": {"a_config.json": {"k": "new"},
                                      "b_config.json": {"k": "new"}}},
                    metadata_dir=meta, overwrite=True, merge=True,
                )

        self.assertEqual(ctx.exception.written, ["a_config.json"])
        self.assertEqual(json.loads(a.read_text())["k"], "new", "file 1 landed")
        self.assertEqual(self.snapshot(b), b_before, "file 2 untouched")
        self.assertEqual(self.temps(meta), [])

    def test_mode_is_preserved(self):
        meta = self.meta()
        for mode in (0o644, 0o600):
            with self.subTest(mode=oct(mode)):
                target = self.write_json(meta / f"m{mode}_config.json", {"k": 1})
                os.chmod(target, mode)
                import_all_configs(
                    bundle={"files": {target.name: {"k": 2}}},
                    metadata_dir=meta, overwrite=True, merge=True,
                )
                self.assertEqual(
                    stat.S_IMODE(os.stat(target).st_mode), mode,
                    "an atomic rewrite must not change the file's mode",
                )

    def test_symlinked_target_is_followed_not_replaced(self):
        meta = self.meta()
        backing = self.write_json(self.tmp / "real" / "backing.json", {"k": "old"})
        link = meta / "linked_config.json"
        link.symlink_to(backing)

        config_utils.save_project_config(link, {"k": "new"})

        self.assertTrue(link.is_symlink(), "the link itself must survive")
        self.assertEqual(json.loads(backing.read_text())["k"], "new",
                         "the write must reach the backing file")


# ---------------------------------------------------------------------------
# Contract E — selection parity and traversal (tests 14-15)
# ---------------------------------------------------------------------------


class SelectionAndTraversalTests(TempDirCase):
    BUNDLE = {"files": {"a_config.json": {"k": "a"}, "b_config.json": {"k": "b"}}}

    def test_selected_files_parity_between_entry_points(self):
        path_meta, bundle_meta = self.meta("via_path"), self.meta("via_bundle")
        bundle_file = self.write_json(self.tmp / "bundle.json", self.BUNDLE)

        via_path = import_all_configs(
            bundle_file, path_meta, selected_files=["a_config.json"]
        )
        via_bundle = import_all_configs(
            bundle=self.BUNDLE, metadata_dir=bundle_meta,
            selected_files=["a_config.json"],
        )

        self.assertEqual(via_path, via_bundle)
        self.assertEqual(
            (path_meta / "a_config.json").read_bytes(),
            (bundle_meta / "a_config.json").read_bytes(),
        )
        for m in (path_meta, bundle_meta):
            self.assertFalse((m / "b_config.json").exists(),
                             "the non-selected file must not be written")

    def test_traversal_in_bundle_name_raises(self):
        with self.assertRaises(ValueError):
            import_all_configs(
                bundle={"files": {"../evil.json": {"k": 1}}},
                metadata_dir=self.meta(),
            )

    def test_traversal_after_good_name_writes_nothing_in_merge_mode(self):
        meta = self.meta()
        with self.assertRaises(ValueError):
            import_all_configs(
                bundle={"files": {"good_config.json": {"k": 1},
                                  "../evil.json": {"k": 2}}},
                metadata_dir=meta, overwrite=True, merge=True,
            )
        self.assertFalse((meta / "good_config.json").exists(),
                         "staging means the earlier good file is not written")

    def test_unselected_traversal_name_still_raises(self):
        """Guard precedes the selection filter — long-standing behavior."""
        with self.assertRaises(ValueError):
            import_all_configs(
                bundle={"files": {"a_config.json": {"k": 1},
                                  "../evil.json": {"k": 2}}},
                metadata_dir=self.meta(), selected_files=["a_config.json"],
            )


# ---------------------------------------------------------------------------
# Contract D — provenance (tests 18-21)
# ---------------------------------------------------------------------------


class ProvenanceTests(TempDirCase):
    def test_truth_table(self):
        cases = [
            ("project only", {"pick": "claudecode/opus5"}, None,
             crs.PROVENANCE_PROJECT, "claudecode/opus5"),
            ("local only", None, {"pick": "claudecode/sonnet5"},
             crs.PROVENANCE_LOCAL, "claudecode/sonnet5"),
            ("both, local wins", {"pick": "claudecode/opus5"},
             {"pick": "claudecode/sonnet5"},
             crs.PROVENANCE_LOCAL, "claudecode/sonnet5"),
        ]
        for label, project, local, provenance, effective in cases:
            with self.subTest(label):
                root = make_repo(self.tmp / label.replace(" ", "_").replace(",", ""),
                                 project=project, local=local)
                got = crs.read_operation_defaults(root)["pick"]
                self.assertEqual(got.provenance, provenance)
                self.assertEqual(got.effective, effective)

    def test_builtin_when_key_in_neither_layer(self):
        """Unioned across repos, a repo lacking the key resolves to builtin."""
        a = make_repo(self.tmp / "a", project={"pick": "claudecode/opus5"})
        b = make_repo(self.tmp / "b", project={"explore": "claudecode/opus5"})
        diff = crs.diff_across_repos([a, b])
        self.assertEqual(
            diff["explore"][crs.repo_key(a)].provenance, crs.PROVENANCE_BUILTIN
        )

    def test_conflict_when_resolver_disagrees_with_layers(self):
        root = make_repo(self.tmp / "c", project={"pick": "claudecode/opus5"})
        with mock.patch.object(crs, "resolve_agent_string",
                               return_value="claudecode/sonnet5"):
            got = crs.read_operation_defaults(root)["pick"]
        self.assertEqual(got.provenance, crs.PROVENANCE_CONFLICT)
        self.assertEqual(got.effective, "claudecode/sonnet5")
        self.assertEqual(got.project_value, "claudecode/opus5",
                         "both raw values stay visible; neither is guessed at")

    def test_seed_config_does_not_influence_anything(self):
        """Negative control for the dropped `seed` tier.

        The real resolver has no seed step (--agent-string -> local -> project ->
        builtin), so a seed/ file must be inert.
        """
        root = make_repo(self.tmp / "s", project={"pick": "claudecode/opus5"})
        (root / "seed").mkdir()
        (root / "seed" / "codeagent_config.json").write_text(
            json.dumps({"defaults": {"pick": "codex/gpt5_6_terra",
                                     "seedonly": "codex/gpt5_6_terra"}}),
            encoding="utf-8",
        )
        got = crs.read_operation_defaults(root)
        self.assertEqual(got["pick"].provenance, crs.PROVENANCE_PROJECT)
        self.assertEqual(got["pick"].effective, "claudecode/opus5")
        self.assertNotIn("seedonly", got, "seed keys are not operations")

    def test_launch_mode_keys_are_excluded(self):
        root = make_repo(self.tmp / "lm", project={
            "pick": "claudecode/opus5",
            "brainstorm-explorer": "claudecode/opus5",
            "brainstorm-explorer-launch-mode": "headless",
        })
        ops = set(crs.read_operation_defaults(root))
        self.assertEqual(ops, {"pick", "brainstorm-explorer"})


# ---------------------------------------------------------------------------
# Contract D — push outcomes (tests 22-25, 30)
# ---------------------------------------------------------------------------


class PushOutcomeTests(TempDirCase):
    def test_noop_when_effective_already_matches(self):
        root = make_repo(self.tmp / "n", project={"pick": "claudecode/opus5"})
        out = crs.plan_push("claudecode/opus5", root, "pick", "project")
        self.assertEqual(out.kind, "noop")

    def test_masked_only_for_project_layer(self):
        root = make_repo(
            self.tmp / "m",
            project={"pick": "claudecode/opus5"},
            local={"pick": "claudecode/sonnet5"},
            models={"claudecode": ["opus5", "sonnet5", "haiku4_5"]},
        )
        masked = crs.plan_push("claudecode/haiku4_5", root, "pick", "project")
        self.assertEqual(masked.kind, "masked")
        self.assertEqual(masked.masking_value, "claudecode/sonnet5")

        # The same push to the local layer is unobstructed — nothing masks it.
        self.assertEqual(
            crs.plan_push("claudecode/haiku4_5", root, "pick", "local").kind, "ok"
        )

    def test_each_rejection_reason_fires_only_for_its_own_cause(self):
        good = make_repo(self.tmp / "r_good", project={"pick": "claudecode/opus5"})

        # malformed: bad shape, and an unsupported agent
        for bad in ("not-an-agent-string", "Claudecode/opus5", "nope/opus5", ""):
            with self.subTest(value=bad):
                out = crs.plan_push(bad, good, "pick", "project")
                self.assertEqual(out.reason, crs.REASON_MALFORMED_AGENT_STRING)

        # model absent from the destination's own catalog
        out = crs.plan_push("claudecode/absent_model", good, "pick", "project")
        self.assertEqual(out.reason, crs.REASON_MODEL_NOT_IN_DEST_CATALOG)

        # unreadable destination config
        broken = make_repo(self.tmp / "r_broken", project={"pick": "claudecode/opus5"})
        (broken / "aitasks" / "metadata" / "codeagent_config.json").write_text(
            "{not json", encoding="utf-8"
        )
        out = crs.plan_push("claudecode/sonnet5", broken, "pick", "project")
        self.assertEqual(out.reason, crs.REASON_DEST_CONFIG_UNREADABLE)

        # a well-formed, in-catalog value against a healthy repo is not rejected
        self.assertFalse(
            crs.plan_push("claudecode/sonnet5", good, "pick", "project").is_rejected
        )

    def test_corrupt_destination_shapes_are_typed_not_silently_resolved(self):
        """The shell resolver exits 0 with the builtin default for a corrupt
        config, so trusting it would return ok/noop and write into a broken repo.
        """
        meta_name = "aitasks/metadata"
        shapes = {
            "malformed": lambda p: p.write_text("{not json", encoding="utf-8"),
            "null": lambda p: p.write_text("null", encoding="utf-8"),
            "directory": lambda p: p.mkdir(),
        }
        for label, corrupt in shapes.items():
            with self.subTest(shape=label):
                root = make_repo(self.tmp / f"corrupt_{label}",
                                 project={"pick": "claudecode/opus5"})
                target = root / meta_name / "codeagent_config.json"
                if target.exists():
                    target.unlink()
                corrupt(target)
                out = crs.plan_push("claudecode/sonnet5", root, "pick", "project")
                self.assertEqual(out.reason, crs.REASON_DEST_CONFIG_UNREADABLE)

        # a corrupt model catalog is also typed, not an escaping JSONDecodeError
        root = make_repo(self.tmp / "corrupt_catalog",
                         project={"pick": "claudecode/opus5"})
        (root / meta_name / "models_claudecode.json").write_text(
            "{not json", encoding="utf-8"
        )
        out = crs.plan_push("claudecode/sonnet5", root, "pick", "project")
        self.assertEqual(out.reason, crs.REASON_DEST_CONFIG_UNREADABLE)

    def test_apply_push_clear_mask_removes_override_and_prunes(self):
        root = make_repo(
            self.tmp / "cm",
            project={"pick": "claudecode/opus5"},
            local={"pick": "claudecode/sonnet5"},
        )
        local_path = root / "aitasks" / "metadata" / "codeagent_config.local.json"

        crs.apply_push("claudecode/sonnet5", root, "pick", "project",
                       clear_mask=True)

        self.assertFalse(local_path.exists(),
                         "an emptied local file is deleted, as save_codeagent does")
        project = json.loads(
            (root / "aitasks" / "metadata" / "codeagent_config.json").read_text()
        )
        self.assertEqual(project["defaults"]["pick"], "claudecode/sonnet5")

    def test_apply_push_clear_mask_keeps_other_local_keys(self):
        root = make_repo(
            self.tmp / "cm2",
            project={"pick": "claudecode/opus5"},
            local={"pick": "claudecode/sonnet5", "explore": "claudecode/opus5"},
        )
        local_path = root / "aitasks" / "metadata" / "codeagent_config.local.json"
        crs.apply_push("claudecode/sonnet5", root, "pick", "project",
                       clear_mask=True)
        local = json.loads(local_path.read_text())
        self.assertEqual(local["defaults"], {"explore": "claudecode/opus5"})

    def test_clear_mask_failure_leaves_effective_value_unchanged(self):
        """The write order is the contract: project first, then clear local.

        Reversing it would drop the override and swing the effective value to
        something the user never chose.
        """
        root = make_repo(
            self.tmp / "partial",
            project={"pick": "claudecode/opus5"},
            # A second local key keeps the file alive after `pick` is removed, so
            # the clear goes through save_local_config rather than unlink.
            local={"pick": "claudecode/sonnet5", "explore": "claudecode/opus5"},
        )
        before = crs.read_operation_defaults(root)["pick"].effective
        project_path = root / "aitasks" / "metadata" / "codeagent_config.json"
        observed: dict[str, str] = {}

        def fail_clear(path, data):
            # Pins the ORDER directly: by the time the clear runs, the project
            # write must already be on disk. Under the reverse order this reads
            # the old value and the assertion below fails.
            observed["project_at_clear_time"] = json.loads(
                project_path.read_text()
            )["defaults"]["pick"]
            raise OSError("disk full")

        with mock.patch.object(crs, "save_local_config", side_effect=fail_clear):
            with self.assertRaises(crs.PushPartialError) as ctx:
                crs.apply_push("claudecode/haiku4_5", root, "pick", "project",
                               clear_mask=True)

        self.assertEqual(
            observed["project_at_clear_time"], "claudecode/haiku4_5",
            "project layer must be written BEFORE the local mask is cleared",
        )

        self.assertEqual(ctx.exception.applied, "project")
        self.assertEqual(ctx.exception.failed, "clear_local")
        self.assertEqual(ctx.exception.masking_value, "claudecode/sonnet5")

        after = crs.read_operation_defaults(root)["pick"]
        self.assertEqual(after.effective, before,
                         "the mask still applies, so nothing the repo uses moved")

        # And a retry converges.
        crs.apply_push("claudecode/haiku4_5", root, "pick", "project",
                       clear_mask=True)
        self.assertEqual(
            crs.read_operation_defaults(root)["pick"].effective,
            "claudecode/haiku4_5",
        )


# ---------------------------------------------------------------------------
# Contract D — diff and identity (test 26)
# ---------------------------------------------------------------------------


class DiffTests(TempDirCase):
    def test_groups_by_operation_and_flags_divergence(self):
        a = make_repo(self.tmp / "d_a", project={"pick": "claudecode/opus5",
                                                 "qa": "claudecode/sonnet5"})
        b = make_repo(self.tmp / "d_b", project={"pick": "claudecode/sonnet5",
                                                 "qa": "claudecode/sonnet5"})
        c = make_repo(self.tmp / "d_c", project={"pick": "claudecode/opus5",
                                                 "qa": "claudecode/sonnet5"})
        diff = crs.diff_across_repos([a, b, c])

        self.assertEqual(set(diff), {"pick", "qa"})
        self.assertEqual(len(diff["pick"]), 3)
        self.assertEqual(
            len({v.effective for v in diff["qa"].values()}), 1, "qa agrees"
        )
        self.assertEqual(
            len({v.effective for v in diff["pick"].values()}), 2, "pick diverges"
        )

    def test_repo_key_matches_aitasks_session_key(self):
        """Drifting apart would force the syncer to add a mapping layer."""
        from agent_launch_utils import AitasksSession

        root = make_repo(self.tmp / "k", project={"pick": "claudecode/opus5"})
        link = self.tmp / "k_link"
        link.symlink_to(root)
        for candidate in (root, link):
            with self.subTest(path=candidate.name):
                session = AitasksSession(
                    session="s", project_root=Path(candidate),
                    project_name=candidate.name,
                )
                self.assertEqual(crs.repo_key(candidate), session.key)


# ---------------------------------------------------------------------------
# Contract D — cross-root isolation (tests 27, 28, 28b, 28c)
# ---------------------------------------------------------------------------


HOSTILE_ENVS = {
    "absolute TASK_DIR": lambda decoy: {"TASK_DIR": str(decoy)},
    "relative non-default TASK_DIR": lambda decoy: {"TASK_DIR": "mytasks"},
    "METADATA_DIR": lambda decoy: {"METADATA_DIR": str(decoy / "metadata")},
    "DEFAULT_AGENT_STRING": lambda decoy: {"DEFAULT_AGENT_STRING": "codex/decoy"},
}


class CrossRootIsolationTests(TempDirCase):
    """Every value must describe its own root, whatever the ambient env says.

    These are the tests that would catch a regression to the static MODEL_FILES
    map or to an inherited resolver environment — neither of which shows up in
    an ordinary fixture test, because fixtures normally leave the vars unset.
    """

    def setUp(self):
        super().setUp()
        # A third tree, deliberately populated with values neither root uses.
        self.decoy = make_repo(self.tmp / "decoy",
                               project={"pick": "codex/decoy"},
                               models={"codex": ["decoy"]})
        (self.decoy / "mytasks" / "metadata").mkdir(parents=True)

    def test_read_path_isolation(self):
        a = make_repo(self.tmp / "iso_a", project={"pick": "claudecode/opus5"})
        b = make_repo(self.tmp / "iso_b", project={"pick": "claudecode/sonnet5"})

        for label, build in HOSTILE_ENVS.items():
            with self.subTest(env=label):
                with mock.patch.dict(os.environ, build(self.decoy)):
                    self.assertEqual(
                        crs.read_operation_defaults(a)["pick"].effective,
                        "claudecode/opus5",
                    )
                    self.assertEqual(
                        crs.read_operation_defaults(b)["pick"].effective,
                        "claudecode/sonnet5",
                    )

    def test_catalog_path_isolation(self):
        """plan_push is the only consumer of the model catalog.

        Divergent per-root catalogs are what make this discriminating: with
        identical catalogs, reading the wrong repo's file gives the right answer
        by luck.
        """
        a = make_repo(self.tmp / "cat_a", project={"pick": "claudecode/opus5"},
                      models={"claudecode": ["alpha1"]})
        b = make_repo(self.tmp / "cat_b", project={"pick": "claudecode/opus5"},
                      models={"claudecode": ["beta1"]})

        for label, build in HOSTILE_ENVS.items():
            with self.subTest(env=label):
                with mock.patch.dict(os.environ, build(self.decoy)):
                    self.assertEqual(
                        crs.plan_push("claudecode/beta1", a, "pick", "project").reason,
                        crs.REASON_MODEL_NOT_IN_DEST_CATALOG,
                        "beta1 is not in root A's catalog",
                    )
                    self.assertFalse(
                        crs.plan_push("claudecode/beta1", b, "pick",
                                      "project").is_rejected,
                        "beta1 IS in root B's catalog",
                    )
                    self.assertEqual(
                        crs.plan_push("claudecode/alpha1", b, "pick", "project").reason,
                        crs.REASON_MODEL_NOT_IN_DEST_CATALOG,
                    )
                    self.assertFalse(
                        crs.plan_push("claudecode/alpha1", a, "pick",
                                      "project").is_rejected,
                    )

    def test_resolver_env_scrubs_every_documented_override(self):
        env = crs.resolver_env()
        for var in crs.RESOLVER_ENV_OVERRIDES:
            self.assertNotIn(var, env)

    def test_supported_agents_match_shell(self):
        """Drift guard: the Python agent set vs SUPPORTED_AGENTS in the shell."""
        text = (_LIB / "agent_string.sh").read_text(encoding="utf-8")
        match = re.search(r"^SUPPORTED_AGENTS=\(([^)]*)\)", text, re.M)
        self.assertIsNotNone(match, "SUPPORTED_AGENTS not found in agent_string.sh")
        self.assertEqual(set(match.group(1).split()), set(config_utils.MODEL_FILES))


if __name__ == "__main__":
    unittest.main()

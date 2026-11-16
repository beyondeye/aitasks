"""Tests for docs-screenshot recipes (t2278_2).

`website/screenshots/recipe.py` loads, validates and writes the recorded route
to one screenshot (`scenes/<id>.yaml`). No tmux is needed here: sessions are
plain objects carrying a journal.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_recipe.py -v
"""
import dataclasses
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))
sys.path.insert(0, os.path.dirname(__file__))

from screenshots import recipe as rc  # noqa: E402
from test_check_screenshots import SpecOwnerTests  # noqa: E402

GOOD = """\
id: scene_a
output: aitasks_scene_a.svg
title: aitasks board
size: [126, 44]
dataset: base
setup: []
launch: ./ait board
steps:
  - wait: 3 children
  - keys: [x]
  - wait_gone: Loading
expect:
  - t12_1 cart summary widget
illustrates: The board with a parent expanded.
"""


def journal(*entries):
    return [dict({"ok": True}, **e) for e in entries]


CLEAN = journal(
    {"kind": "setup", "command": "./ait update --batch 14 --status Implementing"},
    {"kind": "launch", "command": "./ait board"},
    {"kind": "wait", "text": "3 children"},
    {"kind": "keys", "keys": ["x"]},
    {"kind": "shot", "scene": "scene_a", "output": "aitasks_scene_a.svg", "title": "aitasks board"},
    {"kind": "keys", "keys": ["q"]},          # after the shot: not part of the route
)


def fake_session(entries=CLEAN, origin="discovery"):
    return types.SimpleNamespace(id="deadbeef", origin=origin, journal=list(entries),
                                 size=(126, 44), dataset="base")


def save_kwargs(**over):
    kwargs = dict(scene="scene_a", output="aitasks_scene_a.svg",
                  expect=["t12_1 cart summary widget"], illustrates="A parent expanded.")
    kwargs.update(over)
    return kwargs


class ScenesCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        self.addCleanup(tmp.cleanup)
        self.scenes = Path(tmp.name) / "scenes"
        self.scenes.mkdir()

    def spec(self, stem, text):
        path = self.scenes / f"{stem}.yaml"
        path.write_text(text, encoding="utf-8")
        return path


class LoadTests(ScenesCase):
    def test_good_recipe_loads(self):
        recipe = rc.load(self.spec("scene_a", GOOD))
        self.assertEqual((recipe.id, recipe.output, recipe.size),
                         ("scene_a", "aitasks_scene_a.svg", (126, 44)))
        self.assertEqual(recipe.steps, (("wait", "3 children", None), ("keys", ("x",), None),
                                        ("wait_gone", "Loading", None)))
        self.assertEqual(recipe.window_title, "aitasks board")

    def test_a_wait_may_carry_its_own_timeout(self):
        text = GOOD.replace("- wait: 3 children", "- wait: {text: 3 children, timeout: 120}")
        self.assertEqual(rc.load(self.spec("scene_a", text)).steps[0],
                         ("wait", "3 children", 120.0))

    def test_trailing_comment_on_output_is_accepted(self):
        """The parent design's own example line (child 1's contract)."""
        text = GOOD.replace("output: aitasks_scene_a.svg",
                            "output: aitasks_scene_a.svg   # relative to website/static/imgs/")
        self.assertEqual(rc.load(self.spec("scene_a", text)).output, "aitasks_scene_a.svg")

    def test_each_validation_rule(self):
        cases = {
            "unknown key": GOOD + "backend: textual\n",
            "missing illustrates": GOOD.replace("illustrates: The board with a parent expanded.\n", ""),
            "missing expect": GOOD.replace("expect:\n  - t12_1 cart summary widget\n", ""),
            "empty expect": GOOD.replace("expect:\n  - t12_1 cart summary widget\n", "expect: []\n"),
            "size not two ints": GOOD.replace("size: [126, 44]", "size: [126]"),
            "size not positive": GOOD.replace("size: [126, 44]", "size: [126, 0]"),
            "size bool": GOOD.replace("size: [126, 44]", "size: [true, 44]"),
            "unknown dataset": GOOD.replace("dataset: base", "dataset: nowhere"),
            "empty launch": GOOD.replace("launch: ./ait board", 'launch: ""'),
            "setup not a list": GOOD.replace("setup: []", "setup: ./ait lock 12"),
            "unknown step kind": GOOD.replace("- keys: [x]", "- click: '#board'"),
            "step with two kinds": GOOD.replace("- keys: [x]", "- {keys: [x], wait: y}"),
            "empty keys": GOOD.replace("- keys: [x]", "- keys: []"),
            "empty wait": GOOD.replace("- wait: 3 children", "- wait: ''"),
            "id not the file stem": GOOD.replace("id: scene_a", "id: scene_b"),
            "output escapes imgs": GOOD.replace("aitasks_scene_a.svg", "../x.svg"),
            "not a mapping": "- a\n- b\n",
            "dataset not a string": GOOD.replace("dataset: base", "dataset: []"),
            "dataset a mapping": GOOD.replace("dataset: base", "dataset: {a: 1}"),
            "wait mapping without timeout": GOOD.replace("- wait: 3 children",
                                                         "- wait: {text: 3 children}"),
            "wait timeout not a number": GOOD.replace(
                "- wait: 3 children", "- wait: {text: 3 children, timeout: soon}"),
            "wait timeout zero": GOOD.replace(
                "- wait: 3 children", "- wait: {text: 3 children, timeout: 0}"),
            "wait timeout bool": GOOD.replace(
                "- wait: 3 children", "- wait: {text: 3 children, timeout: true}"),
            "wait mapping extra key": GOOD.replace(
                "- wait: 3 children", "- wait: {text: 3 children, timeout: 9, x: 1}"),
        }
        for name, text in cases.items():
            with self.subTest(rule=name):
                with self.assertRaises(rc.RecipeError):
                    rc.load(self.spec("scene_a", text))

    def test_loader_refuses_every_line_the_checker_reader_refuses(self):
        """The checker reads `id:` / `output:` without YAML. Whatever that
        reader refuses, the loader refuses, so the two accept the same set."""
        for _cls, line in SpecOwnerTests.REJECTED:
            key = line.split(":", 1)[0]
            good_line = next(ln for ln in GOOD.splitlines() if ln.startswith(key + ":"))
            with self.subTest(line=line):
                with self.assertRaises(rc.RecipeError):
                    rc.load(self.spec("scene_a", GOOD.replace(good_line, line)))

    def test_control_the_swapped_line_is_what_gets_refused(self):
        """The sweep above swaps one line into GOOD; GOOD itself must load, or
        every row would 'pass' for an unrelated reason."""
        rc.load(self.spec("scene_a", GOOD))

    def test_load_all_refuses_a_duplicate_output(self):
        self.spec("scene_a", GOOD)
        self.spec("scene_b", GOOD.replace("id: scene_a", "id: scene_b"))
        with self.assertRaises(rc.RecipeError) as ctx:
            rc.load_all(self.scenes)
        self.assertIn("already owned", str(ctx.exception))

    def test_load_all_of_a_missing_dir_is_empty(self):
        self.assertEqual(rc.load_all(self.scenes / "nope"), {})


class FromSessionTests(unittest.TestCase):
    def test_clean_discovery_session_becomes_a_recipe(self):
        recipe = rc.from_session(fake_session(), **save_kwargs(title="aitasks board"))
        self.assertEqual(recipe.setup, ("./ait update --batch 14 --status Implementing",))
        self.assertEqual(recipe.launch, "./ait board")
        # Only what happened before the shot is the route.
        self.assertEqual(recipe.steps, (("wait", "3 children", None), ("keys", ("x",), None)))
        self.assertEqual((recipe.size, recipe.dataset), ((126, 44), "base"))

    def test_a_wait_given_more_than_the_default_keeps_its_budget(self):
        """Discovery allowed 120 s; a replay that fell back to the default
        would fail on a state that is slow but reachable."""
        entries = [dict(e) for e in CLEAN]
        entries[2]["timeout"] = 120.0                       # the wait
        entries.insert(3, {"kind": "wait_gone", "ok": True, "text": "Loading", "timeout": 30.0})
        entries.insert(4, {"kind": "wait", "ok": True, "text": "quick", "timeout": 2.0})
        recipe = rc.from_session(fake_session(entries), **save_kwargs())
        self.assertEqual(recipe.steps[:3], (("wait", "3 children", 120.0),
                                            ("wait_gone", "Loading", None),
                                            ("wait", "quick", None)))

    def test_a_replay_session_cannot_be_saved(self):
        with self.assertRaises(rc.RecipeError) as ctx:
            rc.from_session(fake_session(origin="replay"), **save_kwargs())
        self.assertIn("inspection", str(ctx.exception))

    def test_a_journal_with_a_failed_step_cannot_be_saved(self):
        """Also when the failure is followed by steps that worked: there is no
        step filtering, the route has to be walked cleanly."""
        entries = list(CLEAN)
        entries.insert(2, {"kind": "wait", "ok": False, "text": "never"})
        with self.assertRaises(rc.RecipeError) as ctx:
            rc.from_session(fake_session(entries), **save_kwargs())
        self.assertIn("failed step", str(ctx.exception))

    def test_a_failed_setup_cannot_be_saved(self):
        entries = journal({"kind": "setup", "command": "false"}) + list(CLEAN)
        entries[0]["ok"] = False
        with self.assertRaises(rc.RecipeError):
            rc.from_session(fake_session(entries), **save_kwargs())

    def test_no_launch_or_no_shot_for_the_scene(self):
        no_launch = [e for e in CLEAN if e["kind"] != "launch"]
        with self.assertRaises(rc.RecipeError):
            rc.from_session(fake_session(no_launch), **save_kwargs())
        with self.assertRaises(rc.RecipeError):
            rc.from_session(fake_session(), **save_kwargs(scene="other_scene",
                                                          output="other.svg"))


class WriteTests(ScenesCase):
    def recipe(self, **over):
        return dataclasses.replace(
            rc.from_session(fake_session(), **save_kwargs(title="aitasks board")), **over)

    def test_round_trip(self):
        written = self.recipe(illustrates="A parent expanded: its children, each with a ↳.")
        path = rc.write(written, self.scenes)
        self.assertEqual(rc.load(path), written)
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertIn("id: scene_a", lines)
        self.assertIn("output: aitasks_scene_a.svg", lines)

    def test_wait_timeout_round_trips(self):
        written = self.recipe(steps=(("wait", "Report ready", 120.0), ("keys", ("x",), None),
                                     ("wait_gone", "Loading", 45.5)))
        path = rc.write(written, self.scenes)
        self.assertEqual(rc.load(path).steps, written.steps)
        self.assertIn("timeout: 120\n", path.read_text())

    def test_commands_stay_on_one_line(self):
        long_command = "./ait update --batch 14 " + "--label x " * 30
        path = rc.write(self.recipe(setup=(long_command.strip(),)), self.scenes)
        self.assertIn(f"- {long_command.strip()}\n", path.read_text())

    def test_existing_recipe_is_refused_without_replace(self):
        path = rc.write(self.recipe(), self.scenes)
        before = path.read_bytes()
        with self.assertRaises(rc.RecipeError):
            rc.write(self.recipe(launch="./ait trails"), self.scenes)
        self.assertEqual(path.read_bytes(), before)

    def test_replace_rewrites_the_route_and_keeps_the_ownership(self):
        path = rc.write(self.recipe(), self.scenes)
        rc.write(self.recipe(launch="./ait trails"), self.scenes, replace=True)
        loaded = rc.load(path)
        self.assertEqual((loaded.launch, loaded.output), ("./ait trails", "aitasks_scene_a.svg"))

    def test_replace_may_not_change_the_output(self):
        path = rc.write(self.recipe(), self.scenes)
        before = path.read_bytes()
        with self.assertRaises(rc.RecipeError):
            rc.write(self.recipe(output="other.svg"), self.scenes, replace=True)
        self.assertEqual(path.read_bytes(), before)

    def test_an_output_owned_by_another_scene_is_refused(self):
        rc.write(self.recipe(), self.scenes)
        with self.assertRaises(rc.RecipeError):
            rc.write(self.recipe(id="scene_b"), self.scenes)
        self.assertFalse((self.scenes / "scene_b.yaml").exists())

    def test_a_recipe_that_does_not_read_back_never_replaces_a_working_one(self):
        path = rc.write(self.recipe(), self.scenes)
        before = path.read_bytes()
        with mock.patch.object(rc, "dump", return_value="id: scene_a\noutput: [broken\n"):
            with self.assertRaises(rc.RecipeError):
                rc.write(self.recipe(launch="./ait trails"), self.scenes, replace=True)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.scenes.iterdir()), ["scene_a.yaml"])

    def test_the_shipped_recipes_load(self):
        shipped = Path(__file__).resolve().parent.parent / "website" / "screenshots" / "scenes"
        recipes = rc.load_all(shipped)
        self.assertIn("board_child_tasks", recipes)
        self.assertEqual(recipes["board_child_tasks"].output, "aitasks_board_child_tasks.svg")


if __name__ == "__main__":
    unittest.main()

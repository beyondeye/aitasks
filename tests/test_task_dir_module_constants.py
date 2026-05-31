"""Regression: module-load metadata-dir constants honor TASK_DIR (t881).

Three TUI modules previously hardcoded ``Path("aitasks")`` at module load,
ignoring the ``TASK_DIR`` env override — the same latent class fixed by t877
for the userconfig.yaml readers. They only diverge when ``TASK_DIR`` is set
(tests, non-default layouts); default production is unaffected because the TUIs
``cd`` to the repo root with ``TASK_DIR`` unset.

  - settings_app.METADATA_DIR        -> CODEAGENT_CONFIG / BOARD_CONFIG / ...
  - aitask_board.TASKS_DIR           -> USERCONFIG_FILE / METADATA_FILE / ...
  - agent_model_picker.METADATA_DIR  -> MODEL_FILES

All three now route through ``config_utils.task_dir()`` / ``metadata_dir()``,
which read ``os.environ.get("TASK_DIR", "aitasks")``.

These tests follow the t877 decoy-vs-real pattern in
``test_shortcut_label_case.py::TaskDirOverrideTests``: with ``TASK_DIR`` unset
the constants resolve under the hardcoded ``aitasks`` default (decoy); with
``TASK_DIR`` set to a sentinel they resolve under the override (real). The
per-consumer constants are evaluated at module load, so each is probed in a
fresh subprocess — that guarantees import-time resolution with the override in
place and keeps the parent interpreter's module cache unpolluted (other test
files import these same modules).

Run: bash tests/run_all_python_tests.sh
  or: python3 tests/test_task_dir_module_constants.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = REPO_ROOT / ".aitask-scripts"
_LIB = _SCRIPTS / "lib"
_BOARD = _SCRIPTS / "board"
_SETTINGS = _SCRIPTS / "settings"

sys.path.insert(0, str(_LIB))
import config_utils  # noqa: E402

_SENTINEL = "scratch_taskdir"


def _probe(module: str, exprs: list[str], task_dir: str | None) -> list[str]:
    """Import `module` in a fresh subprocess and return str() of each expr.

    `task_dir` sets TASK_DIR for the child (None leaves it unset). A subprocess
    is used because the constants under test are evaluated at module load, so
    the override must be present before the import — and it avoids mutating the
    parent interpreter's already-imported copies of these modules.
    """
    code = (
        "import json\n"
        f"import {module} as m\n"
        f"print(json.dumps([str(eval(e)) for e in {exprs!r}]))\n"
    )
    env = dict(os.environ)
    if task_dir is None:
        env.pop("TASK_DIR", None)
    else:
        env["TASK_DIR"] = task_dir
    extra = [str(_SCRIPTS), str(_LIB), str(_BOARD), str(_SETTINGS)]
    if env.get("PYTHONPATH"):
        extra.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(extra)
    out = subprocess.check_output(
        [sys.executable, "-c", code], env=env, text=True, cwd=str(REPO_ROOT)
    )
    # Take the last stdout line in case the module prints at import time.
    return json.loads(out.strip().splitlines()[-1])


class HelperTests(unittest.TestCase):
    """config_utils.task_dir()/metadata_dir() honor TASK_DIR (per-call)."""

    def setUp(self) -> None:
        self._prev = os.environ.get("TASK_DIR")

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("TASK_DIR", None)
        else:
            os.environ["TASK_DIR"] = self._prev

    def test_override_is_honored(self) -> None:
        os.environ["TASK_DIR"] = "scratch"
        self.assertEqual(config_utils.task_dir(), Path("scratch"))
        self.assertEqual(config_utils.metadata_dir(), Path("scratch") / "metadata")

    def test_default_when_unset(self) -> None:
        os.environ.pop("TASK_DIR", None)
        self.assertEqual(config_utils.task_dir(), Path("aitasks"))
        self.assertEqual(config_utils.metadata_dir(), Path("aitasks") / "metadata")


class SettingsAppConstantTests(unittest.TestCase):
    """settings_app metadata constants follow TASK_DIR (config export/import)."""

    def test_default_is_aitasks(self) -> None:
        meta, board, profiles = _probe(
            "settings_app",
            ["m.METADATA_DIR", "m.BOARD_CONFIG", "m.PROFILES_DIR"],
            None,
        )
        self.assertEqual(meta, str(Path("aitasks") / "metadata"))
        self.assertEqual(board, str(Path("aitasks") / "metadata" / "board_config.json"))
        self.assertEqual(profiles, str(Path("aitasks") / "metadata" / "profiles"))

    def test_override_is_honored(self) -> None:
        meta, board, profiles = _probe(
            "settings_app",
            ["m.METADATA_DIR", "m.BOARD_CONFIG", "m.PROFILES_DIR"],
            _SENTINEL,
        )
        base = Path(_SENTINEL) / "metadata"
        self.assertEqual(meta, str(base))
        self.assertEqual(board, str(base / "board_config.json"))
        self.assertEqual(profiles, str(base / "profiles"))


class BoardConstantTests(unittest.TestCase):
    """aitask_board path constants follow TASK_DIR (board email/userconfig)."""

    def test_default_is_aitasks(self) -> None:
        tasks, userconfig, meta = _probe(
            "aitask_board",
            ["m.TASKS_DIR", "m.USERCONFIG_FILE", "m.METADATA_FILE"],
            None,
        )
        self.assertEqual(tasks, str(Path("aitasks")))
        self.assertEqual(
            userconfig, str(Path("aitasks") / "metadata" / "userconfig.yaml")
        )
        self.assertEqual(meta, str(Path("aitasks") / "metadata" / "board_config.json"))

    def test_override_is_honored(self) -> None:
        tasks, userconfig, meta = _probe(
            "aitask_board",
            ["m.TASKS_DIR", "m.USERCONFIG_FILE", "m.METADATA_FILE"],
            _SENTINEL,
        )
        self.assertEqual(tasks, str(Path(_SENTINEL)))
        self.assertEqual(
            userconfig, str(Path(_SENTINEL) / "metadata" / "userconfig.yaml")
        )
        self.assertEqual(meta, str(Path(_SENTINEL) / "metadata" / "board_config.json"))


class ModelPickerConstantTests(unittest.TestCase):
    """agent_model_picker MODEL_FILES follow TASK_DIR."""

    def test_default_is_aitasks(self) -> None:
        meta, claudecode = _probe(
            "agent_model_picker",
            ["m.METADATA_DIR", "m.MODEL_FILES['claudecode']"],
            None,
        )
        self.assertEqual(meta, str(Path("aitasks") / "metadata"))
        self.assertEqual(
            claudecode, str(Path("aitasks") / "metadata" / "models_claudecode.json")
        )

    def test_override_is_honored(self) -> None:
        meta, claudecode = _probe(
            "agent_model_picker",
            ["m.METADATA_DIR", "m.MODEL_FILES['claudecode']"],
            _SENTINEL,
        )
        self.assertEqual(meta, str(Path(_SENTINEL) / "metadata"))
        self.assertEqual(
            claudecode, str(Path(_SENTINEL) / "metadata" / "models_claudecode.json")
        )


if __name__ == "__main__":
    unittest.main()

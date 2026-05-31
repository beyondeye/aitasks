---
Task: t881_honor_task_dir_in_tui_module_load_metadata_dirs.md
Base branch: main
plan_verified: []
---

# Plan: Honor `TASK_DIR` in TUI module-load metadata-dir constants (t881)

## Context

Three Python TUI modules hardcode `Path("aitasks")` (or `Path("aitasks")/"metadata"`)
as **module-load-time constants**, ignoring the `TASK_DIR` env override. This is
the same latent class fixed by t877 for the two `userconfig.yaml` readers: harmless
in default production (TUIs `cd` to the repo root with `TASK_DIR` unset, so
`aitasks` resolves correctly), but wrong under a `TASK_DIR` override (tests,
non-default layouts) — config export/import, board email reads, and the model
picker all target the wrong tree.

The canonical fix pattern is `userconfig_persist._userconfig_path()`:
`os.environ.get("TASK_DIR", "aitasks")`. The task asks for a **single shared
helper** so the default cannot drift again.

## Affected constants (the only `Path("aitasks")` in each file)

- `.aitask-scripts/settings/settings_app.py:79` — `METADATA_DIR` (feeds
  `CODEAGENT_CONFIG`, `BOARD_CONFIG`, `PROJECT_CONFIG`, `PROFILES_DIR`,
  `LOCAL_PROFILES_DIR`).
- `.aitask-scripts/board/aitask_board.py:56` — `TASKS_DIR` (feeds
  `METADATA_FILE`, `TASK_TYPES_FILE`, `USERCONFIG_FILE`, `EMAILS_FILE`).
- `.aitask-scripts/lib/agent_model_picker.py:36` — `METADATA_DIR` (feeds
  `MODEL_FILES`).

## Approach

### 1. Add the shared helper to `config_utils.py`

`config_utils.py` already `import os` and is imported by **all three** consumers —
the natural single home. Add two small functions (mirroring
`userconfig_persist._userconfig_path()`):

```python
def task_dir() -> Path:
    """Base task directory, honoring the ``TASK_DIR`` env override.

    Defaults to ``aitasks`` (relative to cwd) when ``TASK_DIR`` is unset, which
    matches the framework default and the path TUIs use after chdir-ing to the
    repo root. Tests and non-default layouts set ``TASK_DIR`` so module-load
    constants resolve against the right tree. Mirrors
    ``userconfig_persist._userconfig_path()``.
    """
    return Path(os.environ.get("TASK_DIR", "aitasks"))


def metadata_dir() -> Path:
    """The ``<task_dir>/metadata`` directory, honoring ``TASK_DIR``."""
    return task_dir() / "metadata"
```

### 2. Route the three constants through the helper

Keep them as module-load constants (per the task's "simplest fix" guidance);
only swap the hardcoded base. Behavior is byte-identical when `TASK_DIR` is unset.

- `settings_app.py`: add `metadata_dir` to the existing `from config_utils import (...)`
  block; `METADATA_DIR = metadata_dir()`.
- `aitask_board.py`: add `task_dir` to the existing `from config_utils import ...`
  line; `TASKS_DIR = task_dir()`.
- `agent_model_picker.py`: change `from config_utils import _load_json` →
  `from config_utils import _load_json, metadata_dir`; `METADATA_DIR = metadata_dir()`.

No circular-import risk: `config_utils` imports only stdlib + `yaml`.

### 3. Regression tests — new file `tests/test_task_dir_module_constants.py`

Auto-discovered by `tests/run_all_python_tests.sh` (`test_*.py` glob). sys.path
adds `.aitask-scripts`, `.aitask-scripts/lib`, `.aitask-scripts/board`,
`.aitask-scripts/settings` (mirroring `test_settings_shortcuts_tab.py`).

Following the t877 **decoy-vs-real** pattern
(`test_shortcut_label_case.py::TaskDirOverrideTests`):

- **Helper test:** with `TASK_DIR=scratch`, assert `config_utils.task_dir() ==
  Path("scratch")` and `metadata_dir() == Path("scratch")/"metadata"`; with
  `TASK_DIR` unset, assert the `aitasks` default. (Per-call, no reload needed.)
- **Per-consumer tests (one each):** set `os.environ["TASK_DIR"]` to a sentinel,
  `importlib.reload(module)`, and assert the *derived* file constant points under
  the override, not the `aitasks` decoy — e.g.
  `aitask_board.USERCONFIG_FILE == Path("<sentinel>")/"metadata"/"userconfig.yaml"`,
  `settings_app.BOARD_CONFIG == Path("<sentinel>")/"metadata"/"board_config.json"`,
  `agent_model_picker.MODEL_FILES["claudecode"] == Path("<sentinel>")/"metadata"/"models_claudecode.json"`.
  `tearDown` restores the prior `TASK_DIR` and reloads each module once more so
  the default-baseline state leaks to no other test. Reload is safe — these
  modules only build `Path` constants at import (no file reads).

## Verification

```bash
# New regression test (and the t877 sibling it mirrors)
python3 tests/test_task_dir_module_constants.py
python3 tests/test_shortcut_label_case.py

# Full Python suite — confirm no import/constant regressions in the 3 modules
bash tests/run_all_python_tests.sh

# Lint touched shell? None — all changes are Python. (shellcheck N/A here.)
```

Manual sanity: `TASK_DIR=foo python3 -c "import sys; sys.path[:0]=['.aitask-scripts/lib']; import config_utils; print(config_utils.metadata_dir())"`
→ `foo/metadata`; unset → `aitasks/metadata`.

## Notes / cross-agent

Changes are Python TUI internals (Claude-source tree). No skill/`.md.j2` edits,
no goldens. The fix has no Codex/OpenCode skill analog — no follow-up ports needed.

## Step 9 (Post-Implementation)

Single-task flow on current branch: review (Step 8) → commit
(`bug: ... (t881)`) → plan-file commit → upstream-defect & manual-verify
follow-up offers (Steps 8b/8c) → archive (`aitask_archive.sh 881`) → push.

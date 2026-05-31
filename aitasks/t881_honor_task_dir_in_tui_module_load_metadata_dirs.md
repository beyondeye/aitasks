---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui, python]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 16:48
updated_at: 2026-05-31 17:16
---

## Origin

Spawned from t877 during Step 8b review. t877 fixed the two `userconfig.yaml`
readers (`keybinding_registry`, `shortcuts_mixin`) that ignored `TASK_DIR` by
delegating them to the canonical `userconfig_persist._userconfig_path()`.
Diagnosis surfaced the same latent pattern in three other module-load constants
that t877's scope (its `file_references`) did not cover.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:79 — METADATA_DIR = Path("aitasks")/"metadata" hardcoded at module load, ignoring TASK_DIR; makes config export/import (config_utils.export_all_configs/import_all_configs, themselves correct via the caller-provided base) target the wrong metadata dir under a TASK_DIR override.`
- `.aitask-scripts/board/aitask_board.py:56 — TASKS_DIR = Path("aitasks") hardcoded at module load, ignoring TASK_DIR; USERCONFIG_FILE (board email read) then resolves the wrong file under a TASK_DIR override.`
- `.aitask-scripts/lib/agent_model_picker.py:36 — METADATA_DIR = Path("aitasks")/"metadata" hardcoded at module load, ignoring TASK_DIR; same latent TUI module-load pattern as the two above.`

## Diagnostic context

All three are the same class as t877: latent test-isolation / non-default-layout
correctness issues, harmless in default production where TUIs `cd` to the repo
root with `TASK_DIR` unset (so `aitasks` resolves correctly). They only diverge
when `TASK_DIR` is set (tests, non-default layouts). Note `config_utils.py:247,380`
themselves are correct — they derive `meta_path = Path(metadata_dir)` from a
caller-supplied base; the latent divergence lives in the *caller* (`settings_app`).

Because these are module-load-time module constants (not per-call resolvers),
the simplest fix is to make them `TASK_DIR`-aware, mirroring
`userconfig_persist._userconfig_path()`:
`os.environ.get("TASK_DIR", "aitasks")`.

## Suggested fix

Route the three module-load constants through a `TASK_DIR`-aware base
(`os.environ.get("TASK_DIR", "aitasks")`) — ideally a single shared helper so
the default cannot drift again. Add a regression test per consumer (set
`TASK_DIR`, assert the right metadata dir / userconfig file is read), following
the t877 decoy-vs-real pattern in `tests/test_keybinding_registry.sh` case 10
and `tests/test_shortcut_label_case.py::TaskDirOverrideTests`.

---
Task: t877_userconfig_path_ignores_task_dir_in_keybinding_registry_and_.md
Worktree: (none — profile 'fast', current branch)
Branch: main (current)
Base branch: main
---

# t877 — Honor `TASK_DIR` in the `userconfig.yaml` readers

## Context

`aitasks/metadata/userconfig.yaml` is resolved inconsistently across the lib
modules that read it:

- `userconfig_persist._userconfig_path()` (the documented single persistence
  layer) honors the `TASK_DIR` env override: `os.environ.get("TASK_DIR",
  "aitasks") / "metadata" / "userconfig.yaml"`.
- `keybinding_registry._userconfig_path()` (`:32-33`) hardcodes
  `Path("aitasks/metadata/userconfig.yaml")`.
- `shortcuts_mixin._resolve_uppercase_key()` (`:59`) hardcodes
  `load_yaml_config(Path("aitasks/metadata/userconfig.yaml"))`.

In production this is harmless (TUIs `cd` to repo root, `TASK_DIR` unset →
all three agree on `aitasks`). The divergence only bites when `TASK_DIR` is
set (tests, non-default layouts): the two hardcoded readers read the *wrong*
file while `userconfig_persist`/`shortcut_persist` read the right one. This
masked an override under test during t868's verification of t865.

**Fix:** make both readers delegate to `userconfig_persist._userconfig_path()`
— the single source of truth. No circular-import risk: `userconfig_persist`
imports only stdlib + `yaml`, never `keybinding_registry`/`shortcuts_mixin`.
Precedent: `shortcut_persist.py` already imports the private siblings
`_atomic_dump`/`_load_full` from `userconfig_persist`, so importing
`_userconfig_path` matches the established convention.

## Changes

### 1. `.aitask-scripts/lib/keybinding_registry.py` — `_userconfig_path()` (`:32-33`)

Delegate to the canonical resolver. Use a **local** (function-scoped) import
so this module's import stays yaml-free — it deliberately defers `import yaml`
(see the comment at the `load_user_overrides` body) so tests can import it
before yaml is on `sys.path`. A top-level `import userconfig_persist` would
eagerly pull yaml and break that intent.

```python
def _userconfig_path() -> Path:
    """Resolve userconfig.yaml via the canonical persistence layer.

    Delegates to ``userconfig_persist._userconfig_path`` so the ``TASK_DIR``
    env override is honored identically to the single writer of this file
    (tests / non-default layouts set ``TASK_DIR``). Imported locally to keep
    yaml off this module's import path until a read actually happens — see the
    deferred ``import yaml`` in ``load_user_overrides``.
    """
    from userconfig_persist import _userconfig_path as _canonical_path

    return _canonical_path()
```

`from pathlib import Path` stays (still used in the `-> Path` annotation).

### 2. `.aitask-scripts/lib/shortcuts_mixin.py` — `_resolve_uppercase_key()` (`:59`)

Add to the existing top-level import block (alongside
`from config_utils import load_yaml_config`):

```python
from userconfig_persist import _userconfig_path
```

A top-level import is fine here: `shortcuts_mixin` already pulls yaml
transitively via `from config_utils import load_yaml_config` (config_utils
imports yaml at module top), so no new eager-import cost.

Replace the hardcoded path at `:59`:

```python
cfg = load_yaml_config(_userconfig_path())
```

Remove the now-unused `from pathlib import Path` (`:31`) — `Path` has no other
use in the file after this change.

### 3. Regression tests

**`tests/test_keybinding_registry.sh`** — add a case proving `TASK_DIR` is
honored. Build a decoy at the default `aitasks/metadata/userconfig.yaml` and
the real file at `<TASK_DIR>/metadata/userconfig.yaml`; assert
`load_user_overrides()` reads the `TASK_DIR` one:

```bash
# --- Case 10: TASK_DIR override is honored (t877) ---
WORK="$TMPROOT/case10"
mkdir -p "$WORK/aitasks/metadata" "$WORK/scratch/metadata"
printf 'shortcuts:\n  board:\n    pick_task: DECOY\n' > "$WORK/aitasks/metadata/userconfig.yaml"
printf 'shortcuts:\n  board:\n    pick_task: REAL\n'  > "$WORK/scratch/metadata/userconfig.yaml"
OUT=$(
  cd "$WORK"
  PYTHONPATH="$LIB_DIR" TASK_DIR=scratch "$AITASK_PYTHON" -c '
import keybinding_registry as kr
kr._reset_for_tests()
ov = kr.load_user_overrides()
assert ov == {"board": {"pick_task": "REAL"}}, ov
print("OK")
'
)
assert_eq "case10: keybinding_registry honors TASK_DIR override" "OK" "$OUT"
```

**`tests/test_shortcut_label_case.py`** — add a `TaskDirOverrideTests(_Fixture)`
class: write a decoy `shortcut_label_case: upper` at the default location and
`shortcut_label_case: preserve` under a `scratch/` dir, set
`os.environ["TASK_DIR"]="scratch"` (restore in `finally`), `refresh_label_case()`,
and assert `_resolve_uppercase_key()` is `False` (i.e. read the `TASK_DIR` file,
not the decoy).

Both tests fail on the current code (read the decoy) and pass after the fix.

## Out of scope (note as upstream defects, do NOT fix here)

- `config_utils.py:247,380` are **correct** — they derive
  `meta_path = Path(metadata_dir)` from a caller-supplied base.
- The same "hardcode `Path("aitasks")` at module load, ignoring `TASK_DIR`"
  pattern exists in *callers/other consumers* outside this task's scope:
  `settings_app.py:79` (`METADATA_DIR`), `aitask_board.py:56` (`TASKS_DIR` →
  `USERCONFIG_FILE` email read), `agent_model_picker.py:36`. Different
  consumers, not in t877's `file_references`; flag for a possible follow-up.

## Verification

```bash
bash tests/test_keybinding_registry.sh        # new case10 passes
python3 tests/test_shortcut_label_case.py      # new TaskDirOverrideTests passes
bash tests/test_shortcut_label_case.py 2>/dev/null || true
# Sanity: existing coverage still green
bash tests/test_userconfig_writer_collision.sh
bash tests/test_last_used_labels.sh
```

No skill/`.md.j2`/golden changes (pure lib code) → no `aitask_skill_verify.sh`
or golden regeneration needed. No new lib added to ait's source chain → no
`test_scaffold.sh` update needed.

## Step 9 reference

Post-implementation: commit code (`bug: ... (t877)`), consolidate + commit the
plan file, then archival/merge per task-workflow Step 9 (working on current
branch — no worktree to clean up).

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, no deviations.
  - `keybinding_registry._userconfig_path()` now delegates to
    `userconfig_persist._userconfig_path()` via a function-local import (keeps
    the module's import yaml-free, matching its deferred-`import yaml` design).
  - `shortcuts_mixin._resolve_uppercase_key()` reads via the canonical
    `_userconfig_path()` (top-level import alongside `config_utils`, which
    already pulls yaml); removed the now-unused `from pathlib import Path`.
  - Added regression tests: `tests/test_keybinding_registry.sh` case 10
    (`load_user_overrides()` honors `TASK_DIR`) and
    `tests/test_shortcut_label_case.py::TaskDirOverrideTests`
    (`shortcut_label_case` read from the `TASK_DIR` file, not the decoy).
- **Deviations from plan:** None.
- **Issues encountered:** None. Both new tests confirmed red-on-old /
  green-on-new by stashing the lib fix: the python test cleanly FAILs and the
  bash case10 aborts under `set -e` (python assertion) — both detect the bug.
- **Key decisions:** Delegation over replicating the `TASK_DIR` logic — single
  source of truth, the task's stated preference. Local import in
  `keybinding_registry` (not top-level) deliberately preserves its yaml-free
  import path; top-level is fine in `shortcuts_mixin` because `config_utils`
  already imports yaml at module load. Importing the private `_userconfig_path`
  is consistent with the existing `shortcut_persist` → `userconfig_persist`
  (`_atomic_dump`/`_load_full`) precedent. No circular import (`userconfig_persist`
  imports only stdlib + yaml).
- **Upstream defects identified:**
  - `.aitask-scripts/settings/settings_app.py:79 — METADATA_DIR = Path("aitasks")/"metadata" hardcoded at module load, ignoring TASK_DIR; makes config export/import (config_utils.export_all_configs/import_all_configs, themselves correct via the caller-provided base) target the wrong metadata dir under a TASK_DIR override.`
  - `.aitask-scripts/board/aitask_board.py:56 — TASKS_DIR = Path("aitasks") hardcoded at module load, ignoring TASK_DIR; USERCONFIG_FILE (board email read) then resolves the wrong file under a TASK_DIR override.`
  - `.aitask-scripts/lib/agent_model_picker.py:36 — METADATA_DIR = Path("aitasks")/"metadata" hardcoded at module load, ignoring TASK_DIR; same latent TUI module-load pattern as the two above.`

  All three are the same class as t877 (latent test-isolation / non-default-layout
  correctness, harmless in default production where TUIs chdir to repo root with
  TASK_DIR unset) but are different consumers outside t877's `file_references`.
  Candidate for a single follow-up that routes these module-load constants
  through a TASK_DIR-aware resolver.

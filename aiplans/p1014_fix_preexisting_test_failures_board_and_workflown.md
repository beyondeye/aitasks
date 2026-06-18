---
Task: t1014_fix_preexisting_test_failures_board_and_workflown.md
Base branch: main
plan_verified: []
---

# Plan: t1014 — Fix two pre-existing test failures (board-load + task-workflown parity)

## Context

Two pre-existing test failures were surfaced (not caused) during t635_11.
Neither relates to the gate framework; both are fixed independently here.

Root causes (both diagnosed and fixes verified during planning):

1. **Board-load failures** (`tests/test_settings_shortcuts_tab.py`,
   `tests/test_shortcut_scopes.py`). The shortcut-scope sweep loads each TUI
   module via `importlib.util.spec_from_file_location` + `exec_module` **without
   registering the module in `sys.modules`**. Under Python 3.14, `@dataclass`
   (`.aitask-scripts/board/aitask_board.py:75`) processing string annotations
   (the file has `from __future__ import annotations`) calls
   `dataclasses._is_type`, which does `sys.modules.get(cls.__module__).__dict__`.
   Because `aitask_board` was never put in `sys.modules`, that lookup returns
   `None` → `AttributeError: 'NoneType' object has no attribute '__dict__'`, so
   the board fails to load and its `board` scope is never registered.
   (The earlier-reported `ModuleNotFoundError: task_yaml` is a red herring — the
   sweep's `_ensure_import_paths()` already adds `board/` to `sys.path`, so
   `task_yaml` resolves; the dataclass error is the true failure.)

2. **task-workflown parity drift** (`tests/test_skill_render_task_workflown.sh`
   Test 1). `task-workflown` is the **active** experimental staging copy of
   `task-workflow` consumed by `aitask-pickn` (see
   `aidocs/framework/pickn_workflown_experiment.md`) — not obsolete, so we
   **sync**, not retire. Production added `gate-recording.md` (t635_2); the
   staging copy never received it. Test 1 asserts top-level **file-list** parity
   between the two dirs, and `gate-recording.md` is the *only* file-list
   difference (no extra files in `task-workflown` either).

## Changes

### 1. `.aitask-scripts/lib/shortcut_scopes.py` — register module in `sys.modules`

In `_load_and_register()`, register the module under its manifest name **before**
`exec_module`, and pop it on failure so a half-initialized module is never left
registered. This is the standard pattern for `spec_from_file_location` loading
and is what `dataclasses._is_type` requires. Manifest names are unique
(`aitask_board`, `brainstorm_app`, …) so there are no collisions; the board runs
as `__main__` in normal use, so this only affects the no-instantiation sweep.

```python
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module          # <-- enables dataclass annotation resolution under py3.14
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        sys.modules.pop(module_name, None)     # <-- don't leave a broken module registered
        failed.append(module_name)
        sys.stderr.write(...)                  # (unchanged)
        return
```

The existing try/except already wraps `exec_module`; the edit moves
`module_from_spec` + the new `sys.modules[...]=` assignment out of the `try`
(they cannot fail meaningfully) and adds the `pop` in the `except`. A short
inline comment explains *why* registration is needed (py3.14 dataclass
annotation resolution), so a future reader doesn't "clean it up".

### 2. Add `.aitask-scripts/.../task-workflown/gate-recording.md`

Copy `task-workflow/gate-recording.md` verbatim into
`.claude/skills/task-workflown/gate-recording.md`. It is plain markdown (no Jinja),
renders unchanged, and restores file-list parity. `task-workflown`'s SKILL does
not reference the Gate Recording Procedure (its experimental gates are a separate
mechanism), so the file is inert there — exactly the "complete source file set"
the parity test guards.

## Out of scope (noted, not actioned)

14 *content*-level diffs exist between the two trees' shared files (e.g.
`agent-attribution.md`, `crash-recovery.md`). These are intentional experimental
divergence + production-moved-ahead drift; the experiment doc explicitly defers
any production merge to a separate follow-up. Test 1 checks file lists only, so
these are not in scope for t1014.

## Verification

All three named tests green:

```bash
python3 tests/test_settings_shortcuts_tab.py
python3 tests/test_shortcut_scopes.py
bash tests/test_skill_render_task_workflown.sh
```

Plus, to confirm no regression in the sweep helper and skill rendering:

```bash
./.aitask-scripts/aitask_skill_verify.sh        # skill render/goldens sanity
```

(Spot-verified during planning: with the `sys.modules` registration the board
imports cleanly via the sweep; `gate-recording.md` is the sole file-list drift.)

See **Step 9 (Post-Implementation)** of the task-workflow for cleanup, archival,
and merge.

## Risk

### Code-health risk: low
- `sys.modules` registration during the sweep persists TUI modules under their
  manifest names in the importing process (Settings tab / test runner). The board
  runs as `__main__` in real use, so no name collision with a running app ·
  severity: low · → mitigation: TBD (none needed)

### Goal-achievement risk: low
- None identified. Both root causes were reproduced and both fixes verified
  against the exact failing tests during planning.

## Final Implementation Notes

- **Actual work done:** Exactly the two planned changes.
  1. `.aitask-scripts/lib/shortcut_scopes.py` `_load_and_register()`: register
     the module in `sys.modules` (`sys.modules[module_name] = module`) before
     `exec_module`, and `sys.modules.pop(module_name, None)` in the failure
     branch. A 7-line inline comment documents *why* (py3.14 dataclass string-
     annotation resolution) so it isn't "cleaned up" later.
  2. Copied `task-workflow/gate-recording.md` → `task-workflown/gate-recording.md`
     verbatim to restore Test 1 file-list parity.
- **Deviations from plan:** None.
- **Issues encountered:** None — the planning-time spot-verification predicted the
  outcome exactly. The reported `ModuleNotFoundError: task_yaml` symptom was a red
  herring; the real failure was the py3.14 `dataclasses._is_type` `AttributeError`,
  which only surfaces when the swept module is absent from `sys.modules`.
- **Key decisions:** Chose **sync** over **retire** for `task-workflown` because it
  is active experimental staging consumed by `aitask-pickn` (per
  `aidocs/framework/pickn_workflown_experiment.md`), not obsolete. Kept the fix in
  the shared sweep helper (`_load_and_register`) rather than per-module, so every
  swept TUI benefits and the board doesn't need a workaround.
- **Upstream defects identified:** None. (Observation, not a defect: 14 shared
  files differ in *content* between `task-workflow` and `task-workflown`. This is
  intentional experimental divergence + production-moved-ahead drift; the
  experiment doc explicitly defers any production merge to a separate follow-up.
  Test 1 checks file lists only, so it is out of scope for t1014.)

## Verification results (post-implementation)

- `python3 tests/test_settings_shortcuts_tab.py` → OK (22 tests)
- `python3 tests/test_shortcut_scopes.py` → OK (6 tests)
- `bash tests/test_skill_render_task_workflown.sh` → 21/21 passed
- `./.aitask-scripts/aitask_skill_verify.sh` → OK (12 templates, 3 agents)
- `bash tests/test_skill_render_aitask_pickn.sh` → 37/37 passed

---
priority: medium
effort: low
depends: [t718_1]
issue_type: performance
status: Implementing
labels: [performance, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:30
updated_at: 2026-04-30 14:29
---

## Context

Parent task **t718** (`aitasks/t718_pypy_optional_runtime_for_tui_perf.md`) introduces opt-in PyPy support for long-running Textual TUIs. Sibling **t718_1** (must be archived first — already declared as a sibling dependency) lands the infrastructure: `lib/python_resolve.sh` exposes `require_ait_python_fast()` with the auto-PyPy-when-installed precedence, and `aitask_setup.sh --with-pypy` builds the PyPy venv at `~/.aitask/pypy_venv/`.

This task wires **only the long-running Textual TUIs** to the fast path. Short-lived CLI scripts (`aitask_pick.sh`, `aitask_create.sh`, etc.) stay on CPython to avoid the ~150-300 ms PyPy warmup penalty. Monitor/minimonitor stay on CPython because their bottleneck is `fork+exec(tmux)` (sibling task t719 addresses that separately) — PyPy gives ~0% there.

The task description in the parent originally listed `aitask_stats.sh` as a touchpoint; per user clarification during planning that was a typo (the stats CLI is a one-shot, not a TUI). The actual long-running stats TUI is `aitask_stats_tui.sh`. Also per user clarification, `aitask_brainstorm_tui.sh` (originally omitted) is included in the fast-path list.

## Key Files to Modify

Switch a single line in each of the following from `require_ait_python` to `require_ait_python_fast`:

1. `.aitask-scripts/aitask_board.sh` (line 12)
2. `.aitask-scripts/aitask_codebrowser.sh` (line 12)
3. `.aitask-scripts/aitask_settings.sh` (line 12)
4. `.aitask-scripts/aitask_stats_tui.sh` (line 12)
5. `.aitask-scripts/aitask_brainstorm_tui.sh` (line 12)

Each of these is a 5-line edit at most (the current literal is `PYTHON="$(require_ait_python)"`; change to `PYTHON="$(require_ait_python_fast)"`).

## Files to **explicitly NOT modify** (must remain on `require_ait_python`)

Confirm via `git diff --stat` after editing that these are untouched:

- `.aitask-scripts/aitask_monitor.sh`
- `.aitask-scripts/aitask_minimonitor.sh`
- `.aitask-scripts/aitask_stats.sh` (one-shot CLI — PyPy warmup hurts here)
- All `aitask_brainstorm_*.sh` siblings except `aitask_brainstorm_tui.sh` (status, archive, init, delete, apply_initializer — these are short-lived helpers)
- All `aitask_crew_*.sh` (crew runner / dashboard / report / status / logview — short-lived helpers)
- `aitask_diffviewer.sh` — TUI but transitional (per CLAUDE.md will be folded into brainstorm later); keep on CPython for now to limit blast radius. The fast-path migration for diffviewer can ride along with the brainstorm integration when it lands.
- `aitask_explain_context.sh`, any other `require_ait_python` callers found in the global grep.

## Reference Files for Patterns

- The original `require_ait_python` call sites (e.g. `aitask_board.sh:12`) — same shape across all 5 fast-path TUIs.
- Sibling t718_1's plan file `aiplans/p718/p718_1_pypy_infrastructure_setup_resolver.md` — confirms the function's contract before relying on it.

## Implementation Plan

**Step 1 — Verify t718_1 has landed.** Sanity check that `require_ait_python_fast` is defined in `lib/python_resolve.sh` and exported (or callable from sourced scope) before editing any launcher:

```bash
grep -n "require_ait_python_fast" .aitask-scripts/lib/python_resolve.sh
```

If absent, stop — t718_1 is the dependency and must be archived first.

**Step 2 — Edit the 5 launchers** (single-line edits each):

```bash
sed -i.bak 's/require_ait_python)/require_ait_python_fast)/' \
    .aitask-scripts/aitask_board.sh \
    .aitask-scripts/aitask_codebrowser.sh \
    .aitask-scripts/aitask_settings.sh \
    .aitask-scripts/aitask_stats_tui.sh \
    .aitask-scripts/aitask_brainstorm_tui.sh
rm -f .aitask-scripts/aitask_*.sh.bak
```

(Use the manual `Edit` tool per file in practice — the `sed` above is shown for clarity but `set -euo pipefail` + the explicit edit tool is preferred.)

**Step 3 — Confirm untouched scripts.** Run `git diff --stat` and verify only the 5 files above changed. Cross-check `.aitask-scripts/aitask_monitor.sh` and `.aitask-scripts/aitask_minimonitor.sh` still call `require_ait_python` (not the fast variant).

**Step 4 — `shellcheck`** all 5 modified scripts:

```bash
shellcheck .aitask-scripts/aitask_board.sh \
           .aitask-scripts/aitask_codebrowser.sh \
           .aitask-scripts/aitask_settings.sh \
           .aitask-scripts/aitask_stats_tui.sh \
           .aitask-scripts/aitask_brainstorm_tui.sh
```

## Verification Steps

1. With PyPy **not** installed (no `--with-pypy` setup step): `./ait board` launches under CPython exactly as before. Behavior is identical because `require_ait_python_fast` falls through to `require_ait_python` when PyPy is missing.
2. With PyPy installed (`./ait setup --with-pypy` already run): `./ait board` auto-launches under PyPy. Verify with a one-liner inside the launcher (or by adding `--debug` to print `sys.implementation.name`):
   ```python
   import sys; print(f"impl={sys.implementation.name}")
   ```
3. With PyPy installed but `AIT_USE_PYPY=0 ./ait board`: launches under CPython (override).
4. With `AIT_USE_PYPY=1` but PyPy not installed: launcher errors with the message from t718_1's `require_ait_pypy` (`die`).
5. Monitor/minimonitor unchanged: `./ait monitor` and `./ait minimonitor` still use CPython regardless of `AIT_USE_PYPY` (because they don't call `require_ait_python_fast`).
6. Visual smoke test: launch each of the 5 modified TUIs under PyPy and confirm rendering, scroll, and basic input works (no missing-deps errors). The `pip install` step in t718_1's `setup_pypy_venv` brought in `textual`, `pyyaml`, `linkify-it-py`, `tomli` — these are the only deps the 5 TUIs touch beyond stdlib.

## Notes for sibling tasks

- This task's diff is intentionally tiny: 5 single-line `require_ait_python` → `require_ait_python_fast` edits. Resist the urge to "clean up" or refactor adjacent code — keeps the revert clean per the parent's acceptance criterion.
- t718_3 (documentation) lands after this task and will document the user-visible behavior (auto-PyPy when installed, `AIT_USE_PYPY=0` to disable). No CLAUDE.md edits in *this* task.
- If a manual-verification sibling (t718_4) is created during parent planning, the smoke tests in this task's "Verification Steps" feed directly into its checklist.

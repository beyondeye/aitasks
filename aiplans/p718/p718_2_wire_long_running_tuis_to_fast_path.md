---
Task: t718_2_wire_long_running_tuis_to_fast_path.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_1_pypy_infrastructure_setup_resolver.md, aitasks/t718/t718_3_documentation_pypy_runtime.md
Archived Sibling Plans: aiplans/archived/p718/p718_1_*.md (after t718_1 archives)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: t718_2 — Wire long-running TUIs to require_ait_python_fast

## Context

Second of three children. **Depends on t718_1** being archived first (provides
`require_ait_python_fast` in `lib/python_resolve.sh`). This task is a focused
5-line edit: each long-running Textual TUI launcher swaps its
`require_ait_python` call for `require_ait_python_fast`. After this lands,
once a user has run `ait setup --with-pypy`, the named TUIs auto-route through
PyPy.

## Files modified (exactly 5)

1. `.aitask-scripts/aitask_board.sh` — line 12
2. `.aitask-scripts/aitask_codebrowser.sh` — line 12
3. `.aitask-scripts/aitask_settings.sh` — line 12
4. `.aitask-scripts/aitask_stats_tui.sh` — line 12
5. `.aitask-scripts/aitask_brainstorm_tui.sh` — line 12

Each edit:

```diff
-PYTHON="$(require_ait_python)"
+PYTHON="$(require_ait_python_fast)"
```

## Files explicitly NOT modified (verify in git diff)

- `.aitask-scripts/aitask_monitor.sh`
- `.aitask-scripts/aitask_minimonitor.sh`
- `.aitask-scripts/aitask_stats.sh` (one-shot CLI)
- `.aitask-scripts/aitask_diffviewer.sh` (transitional per CLAUDE.md — folds into brainstorm later)
- All other `aitask_*.sh` callers of `require_ait_python` (brainstorm helpers other than `_tui`, crew helpers, explain_context, etc.)

If `git diff --stat` after the edits shows any file outside the 5-element list above, that is a scope violation — revert the extra change.

## Implementation steps

### 1. Pre-flight: confirm t718_1 has landed

```bash
grep -n "^require_ait_python_fast" .aitask-scripts/lib/python_resolve.sh
```

Must return a line. If missing, t718_1 has not been archived yet — abort and
escalate.

### 2. Edit each launcher

Use the `Edit` tool per file with this exact replacement:
- old_string: `PYTHON="$(require_ait_python)"`
- new_string: `PYTHON="$(require_ait_python_fast)"`

(All 5 launchers happen to use the identical literal at line 12, confirmed by
grep during planning. If any drift is found, fall back to per-file inspection.)

### 3. Lint

```bash
shellcheck .aitask-scripts/aitask_board.sh \
           .aitask-scripts/aitask_codebrowser.sh \
           .aitask-scripts/aitask_settings.sh \
           .aitask-scripts/aitask_stats_tui.sh \
           .aitask-scripts/aitask_brainstorm_tui.sh
```

### 4. Verify scope

```bash
git diff --stat
# Should show exactly the 5 files above. No others.

git diff -- .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh
# Should be empty.
```

## Verification (this task)

1. **Without PyPy installed:** `./ait board` launches via CPython exactly as before. (`require_ait_python_fast` falls through to `require_ait_python`.) Visual smoke: TUI renders normally.
2. **With PyPy installed (`./ait setup --with-pypy` already run):** `./ait board` auto-launches under PyPy. Verify by adding a temporary `print(sys.implementation.name)` to `board/aitask_board.py`'s startup, OR by running:
   ```bash
   AIT_USE_PYPY=1 ~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name)"
   ```
   …and trusting the resolver. Repeat for codebrowser, settings, stats_tui, brainstorm_tui.
3. **`AIT_USE_PYPY=0 ./ait board`** (with PyPy installed) launches under CPython.
4. **`AIT_USE_PYPY=1 ./ait board`** (without PyPy installed) errors with the message from `require_ait_pypy`.
5. **`AIT_USE_PYPY=1 ./ait monitor`** (with PyPy installed) **still uses CPython** — monitor doesn't call the fast variant.
6. `shellcheck` clean on all 5 modified files.

## Notes for sibling tasks

- t718_3 (documentation) lands after this — at that point both the user-facing surface (`AIT_USE_PYPY` and `--with-pypy`) and the implementation are stable.
- Resist the urge to expand scope: do **not** add a new launcher to the fast path during this task even if it seems natural. New fast-path adoption is a separate decision that belongs in its own task.

## Step 9 (Post-Implementation)

Standard child-task archival per `task-workflow/SKILL.md` Step 9.

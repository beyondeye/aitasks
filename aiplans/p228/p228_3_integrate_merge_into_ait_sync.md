---
Task: t228_3_integrate_merge_into_ait_sync.md
Parent Task: aitasks/t228_improved_task_merge_for_board.md
Sibling Tasks: aitasks/t228/t228_1_*.md, aitasks/t228/t228_2_*.md, aitasks/t228/t228_4_*.md, aitasks/t228/t228_5_*.md
Branch: (current branch - no worktree)
Base branch: main
---

# Plan: t228_3 — Integrate Merge into ait sync

## Goal

Modify `aiscripts/aitask_sync.sh` to call `aitask_merge.py` during `do_pull_rebase()` for each conflicted task/plan file, enabling auto-resolution of metadata conflicts.

## Verification Notes (from plan verification)

1. **PYTHONPATH required:** `aitask_merge.py` does `from task_yaml import ...` — must set `PYTHONPATH="$SCRIPT_DIR/board"` when invoking
2. **Multi-commit rebase loop:** `rebase --continue` can trigger new conflicts for subsequent commits — need a loop
3. **`GIT_EDITOR=true`:** Needed for `git rebase --continue` to avoid editor popup
4. **Existing Test 5 (CONFLICT):** Has body differences → merge returns PARTIAL (exit 2) → stays CONFLICT. No regression.

## Steps

### 1. Update batch output protocol comment (top of file)

Add `AUTOMERGED` to the documented statuses.

### 2. Add Python detection + merge support variables (after sourcing libs)

```bash
_MERGE_PYTHON=""
_MERGE_SCRIPT="$SCRIPT_DIR/board/aitask_merge.py"
_init_merge_python() {
    local venv_py="$HOME/.aitask/venv/bin/python"
    if [[ -x "$venv_py" ]]; then
        _MERGE_PYTHON="$venv_py"
    elif command -v python3 &>/dev/null; then
        _MERGE_PYTHON="python3"
    fi
}
_init_merge_python
```

### 3. Add `try_auto_merge()` function

Always uses `--batch` flag for the merge script (sync handles interactivity itself). Sets `PYTHONPATH="$SCRIPT_DIR/board"` for the `task_yaml` import.

### 4. Modify `do_pull_rebase()` with auto-merge-first flow

- Try auto-merge before aborting or opening editor
- Loop on `rebase --continue` for multi-commit rebases
- Use `GIT_EDITOR=true` for rebase continue
- Fall through to interactive editor for remaining unresolved files

### 5. Update help text

Add `AUTOMERGED` to `show_help()`.

### 6. Add auto-merge tests

- Test 12: AUTOMERGED — frontmatter-only conflict (boardcol + labels)
- Test 13: AUTOMERGED — priority/effort uses remote default in batch
- Test 14: CONFLICT preserved when body differs (partial merge)

## Final Implementation Notes

- **Actual work done:** Modified `aiscripts/aitask_sync.sh` (+144 lines) to call `aitask_merge.py` during rebase conflict resolution. Added `--rebase` flag to `aiscripts/board/aitask_merge.py` (+11 lines) to swap LOCAL/REMOTE sides during rebase (git inverts them). Added 3 new tests to `tests/test_sync.sh` (+196 lines). All 34 sync tests pass, all 43 merge tests pass, shellcheck clean.
- **Deviations from plan:** Three significant discoveries during implementation: (1) During `git rebase`, conflict marker sides are inverted — LOCAL=upstream, REMOTE=our commits. Added `--rebase` flag to merge script to swap sides. (2) After auto-merge resolves to content identical to HEAD, `git rebase --continue` fails with "nothing to commit". Added `_rebase_advance()` helper that falls back to `rebase --skip`. (3) Python's `__pycache__` bytecode creation during merge script execution interferes with `git rebase --continue` in test environments (dirty working tree). Added `PYTHONDONTWRITEBYTECODE=1` to the merge invocation.
- **Issues encountered:** The `__pycache__` interference was the most subtle bug — `git rebase --continue` fails when Python bytecode files are created in a tracked `__pycache__` directory during conflict resolution. In production repos this isn't an issue (`.gitignore` excludes `__pycache__`), but the defensive `PYTHONDONTWRITEBYTECODE=1` prevents it everywhere.
- **Key decisions:** (1) `AUTOMERGED` batch output takes priority over `SYNCED`/`PULLED` — it replaces the normal status to signal that auto-merge occurred. (2) The merge script always runs with `--batch` flag from sync (sync handles interactivity itself). (3) `git pull --rebase` stdout is now suppressed (`&>/dev/null`) to prevent git conflict messages from leaking into batch output.
- **Notes for sibling tasks:** The `--rebase` flag is important for t228_4 (board TUI integration) if the board also uses rebase for sync. The `PYTHONDONTWRITEBYTECODE=1` pattern should be used whenever running Python scripts during git operations. The `_rebase_advance()` helper (continue → skip fallback) is reusable. Test setup via `setup_sync_repos()` copies `__pycache__/` — if future tests have similar issues, consider adding `.gitignore` to the test repos.

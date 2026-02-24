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

## Steps

### 1. Add Python Detection (top of script, after sourcing libs)

```bash
# Auto-merge support (best-effort — falls back gracefully if unavailable)
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

### 2. Add `try_auto_merge()` Function

```bash
# try_auto_merge <conflicted_files_newline_separated>
# Attempts auto-merge for each task/plan file using Python merge script.
# Outputs remaining unresolved files (newline-separated) to stdout.
# Returns 0 if ALL resolved, 1 if any remain unresolved.
try_auto_merge() {
    local conflicted="$1"
    local unresolved=""
    local resolved_count=0
    local batch_flag=""
    [[ "$BATCH_MODE" == true ]] && batch_flag="--batch"

    if [[ -z "$_MERGE_PYTHON" ]] || [[ ! -f "$_MERGE_SCRIPT" ]]; then
        echo "$conflicted"
        return 1
    fi

    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        case "$f" in
            aitasks/*.md|aiplans/*.md)
                local file_path merge_exit=0
                file_path="$(_resolve_conflict_path "$f")"
                "$_MERGE_PYTHON" "$_MERGE_SCRIPT" "$file_path" $batch_flag 2>/dev/null || merge_exit=$?
                if [[ $merge_exit -eq 0 ]]; then
                    task_git add "$f" 2>/dev/null || true
                    resolved_count=$((resolved_count + 1))
                    iinfo "Auto-merged: $f"
                else
                    unresolved="${unresolved}${unresolved:+$'\n'}$f"
                fi
                ;;
            *)
                unresolved="${unresolved}${unresolved:+$'\n'}$f"
                ;;
        esac
    done <<< "$conflicted"

    if [[ -z "$unresolved" ]]; then
        iinfo "Auto-merged $resolved_count file(s)"
        return 0
    else
        [[ $resolved_count -gt 0 ]] && iinfo "Auto-merged $resolved_count file(s), $(($(echo "$unresolved" | wc -l))) remain"
        echo "$unresolved"
        return 1
    fi
}
```

### 3. Modify `do_pull_rebase()` (lines 196-242)

Replace the conflict handling block. New flow:

```
if [[ $pull_exit -ne 0 ]]; then
    conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)

    if [[ -n "$conflicted" ]]; then
        # Try auto-merge first
        local remaining
        remaining=$(try_auto_merge "$conflicted") || true
        local merge_rc=$?

        if [[ $merge_rc -eq 0 ]]; then
            # All conflicts auto-resolved
            if task_git rebase --continue 2>/dev/null; then
                if [[ "$BATCH_MODE" == true ]]; then
                    batch_out "AUTOMERGED"
                else
                    info "All conflicts auto-merged successfully"
                fi
                return 0
            else
                # Rebase continue failed (shouldn't happen if merge was clean)
                task_git rebase --abort 2>/dev/null || true
                batch_out "ERROR:rebase_continue_after_automerge"
                return 1
            fi
        else
            # Some files unresolved — fall through to existing logic
            if [[ "$BATCH_MODE" == true ]]; then
                task_git rebase --abort 2>/dev/null || true
                local conflict_list
                conflict_list=$(echo "$remaining" | tr '\n' ',' | sed 's/,$//')
                batch_out "CONFLICT:${conflict_list}"
                exit 0
            else
                # Interactive: open editor for remaining unresolved files only
                warn "Remaining conflicts in:"
                echo "$remaining" | while IFS= read -r f; do echo "  - $f"; done
                # ... (existing editor loop, but using $remaining instead of $conflicted)
            fi
        fi
    fi
fi
```

### 4. Update Batch Output Protocol Comment

Add `AUTOMERGED` to the documented statuses at the top of the script.

## Key Considerations

- `try_auto_merge` is best-effort: if Python is unavailable, it returns 1 and passes all files through as unresolved
- The `GIT_EDITOR=true` trick may be needed for `git rebase --continue` when all conflicts are resolved (to skip the editor for the commit message)
- Must handle the case where `git rebase --continue` triggers another conflict (sequential commits during rebase)

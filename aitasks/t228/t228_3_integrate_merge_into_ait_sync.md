---
priority: high
effort: medium
depends: [t228_2]
issue_type: feature
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 09:14
updated_at: 2026-02-24 10:31
---

## Integrate merge script into ait sync rebase flow

### Context

The Python auto-merge script (t228_2) needs to be called by `ait sync` during the rebase conflict resolution flow. This task modifies `aitask_sync.sh` to invoke the merge script for each conflicted task/plan file before falling through to manual resolution.

Part of t228 "Improved Task Merge for ait sync". Depends on t228_2.

### Key Files to Modify

- `aiscripts/aitask_sync.sh` — Modify `do_pull_rebase()` function (lines 189-254)

### Reference Files for Patterns

- `aiscripts/aitask_board.sh` lines 8-32 — Python venv detection pattern to reuse
- `aiscripts/aitask_sync.sh` lines 189-254 — Current `do_pull_rebase()` implementation
- `aiscripts/board/aitask_merge.py` — The merge script to call (from t228_2)

### Implementation Plan

#### 1. Add Python/venv Detection

At the top of `aitask_sync.sh`, add venv detection (reuse pattern from `aitask_board.sh`):

```bash
VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    MERGE_PYTHON="$VENV_PYTHON"
else
    MERGE_PYTHON="${PYTHON:-python3}"
    # Don't fail if python unavailable — merge is best-effort
    command -v "$MERGE_PYTHON" &>/dev/null || MERGE_PYTHON=""
fi
MERGE_SCRIPT="$SCRIPT_DIR/board/aitask_merge.py"
```

#### 2. Add Auto-Merge Function

Create `try_auto_merge()` function:

```bash
try_auto_merge() {
    # Called after rebase conflict detected, before aborting or opening editor
    # Iterates conflicted files, runs merge script for task/plan files
    # Returns 0 if all resolved, 1 if any remain unresolved

    local conflicted="$1"
    local unresolved=""
    local resolved_count=0

    if [[ -z "$MERGE_PYTHON" ]] || [[ ! -f "$MERGE_SCRIPT" ]]; then
        return 1  # No merge capability, fall through
    fi

    while IFS= read -r f; do
        # Only attempt merge on task/plan files
        case "$f" in
            aitasks/*.md|aiplans/*.md)
                local merge_out merge_exit=0
                local file_path="$(_resolve_conflict_path "$f")"
                merge_out=$("$MERGE_PYTHON" "$MERGE_SCRIPT" "$file_path" --batch 2>/dev/null) || merge_exit=$?

                if [[ $merge_exit -eq 0 ]]; then
                    task_git add "$f" 2>/dev/null || true
                    resolved_count=$((resolved_count + 1))
                else
                    unresolved="${unresolved:+$unresolved,}$f"
                fi
                ;;
            *)
                unresolved="${unresolved:+$unresolved,}$f"
                ;;
        esac
    done <<< "$conflicted"

    if [[ -z "$unresolved" ]]; then
        return 0  # All resolved
    else
        echo "$unresolved"  # Output remaining unresolved files
        return 1
    fi
}
```

#### 3. Modify `do_pull_rebase()`

Insert the auto-merge step between conflict detection and the existing resolution logic:

```
After line 201 (if conflicted files detected):
  1. Call try_auto_merge "$conflicted"
  2. If returns 0 (all resolved):
     - git rebase --continue
     - In batch mode: output "AUTOMERGED" instead of "CONFLICT:..."
     - In interactive mode: print "All conflicts auto-merged"
  3. If returns 1 (some unresolved):
     - Use the returned unresolved file list instead of original conflicted list
     - Continue with existing logic (batch: CONFLICT:<unresolved>, interactive: open $EDITOR)
```

#### 4. Add `AUTOMERGED` to Batch Output Protocol

Update the comment at the top of the script documenting batch output to include:
```
AUTOMERGED                 Conflicts detected but all auto-resolved
```

#### 5. Interactive Mode Enhancements

In interactive mode, when some files are auto-merged and some aren't:
- Print: "Auto-merged N file(s). Remaining conflicts in:"
- Only open `$EDITOR` for truly unresolved files

### Verification Steps

1. Run existing `tests/test_sync.sh` — all 11 tests must pass (no regressions)
2. Manual test with two clones:
   - Clone A: change `boardcol: now` → `boardcol: next` on a task
   - Clone B: change `labels: [ui]` → `labels: [ui, api]` on same task
   - Run `./ait sync --batch` on clone B → should output `AUTOMERGED`
   - Verify merged file has `boardcol: next` (local) and `labels: [ui, api]` (merged)
3. Test graceful fallback: rename venv temporarily, verify sync falls back to `CONFLICT:`

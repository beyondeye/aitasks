---
Task: t28_allow_to_remove_file_refs_in_task_create.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Allow removing file references in aitask_create (t28)

## Context

In `aitask_create.sh`, the file reference loop (lines 641-663) only offers "Add file reference" and "Done with files". Once a file reference is added to the current session, it cannot be removed — the user must manually edit the task file after creation. This task adds a "Remove file reference" option to the fzf menu.

## File to Modify

- `aitask_create.sh` — function `get_task_definition()` (lines 621-675)

## Implementation

### 1. Track added file references in an array (scoped per file-ref round)

Reset the array at the **start of the inner file reference loop** (just before `while true` at line 641), NOT before the outer loop. This ensures only files added in the current description+files round are removable — files added in a previous round are not shown.

```bash
local -a current_round_refs=()
# existing: while true; do
```

### 2. Update the fzf menu to include a "Remove file reference" option

Change the fzf menu at line 643 to dynamically include the remove option only when there are file references to remove:

```bash
local menu_opts="Add file reference\nDone with files"
if [[ ${#current_round_refs[@]} -gt 0 ]]; then
    menu_opts="Add file reference\nRemove file reference\nDone with files"
fi
add_file=$(echo -e "$menu_opts" | fzf --prompt="Add file? " --height=8 --no-info)
```

### 3. When a file is added, also track it in the array

After the existing `success "Added: $selected_file"` line (661), add:
```bash
current_round_refs+=("$selected_file")
```

### 4. Handle "Remove file reference" selection

After the existing "Done with files" check (lines 645-647), add a new elif block:

```bash
elif [[ "$add_file" == "Remove file reference" ]]; then
    # Let user pick which file ref to remove
    local remove_file
    remove_file=$(printf '%s\n' "${current_round_refs[@]}" | fzf --prompt="Remove which file? " --height=12 --no-info)

    if [[ -n "$remove_file" ]]; then
        # Remove from task_desc (the file path is on its own line)
        task_desc=$(echo "$task_desc" | grep -vxF "$remove_file")
        # Remove from tracking array
        local -a new_refs=()
        for ref in "${current_round_refs[@]}"; do
            [[ "$ref" != "$remove_file" ]] && new_refs+=("$ref")
        done
        current_round_refs=("${new_refs[@]}")
        success "Removed: $remove_file" >&2
    fi
```

## Verification

1. Run `./aitask_create.sh` and go through the task creation flow
2. Add 2-3 file references
3. Verify "Remove file reference" option appears in the menu
4. Select "Remove file reference" and verify the fzf picker shows only session-added files
5. Remove one file and verify the success message
6. Verify the menu still shows "Remove file reference" if refs remain
7. Remove all refs and verify the option disappears from the menu
8. Complete task creation and verify the removed file is not in the output

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned — added `current_round_refs` array, dynamic fzf menu, and removal logic via `grep -vxF`
- **Deviations from plan:** None
- **Issues encountered:** None — straightforward implementation, syntax check passed
- **Key decisions:** Scoped removable refs per file-reference round (not per session) per user requirement; used `grep -vxF` for exact line match removal from `task_desc`

---
Task: t377_improve_check_for_contributions.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask_contribute.sh` script detects local changes vs a source repo to generate contribution issues. Currently, **clone/project mode** uses `git diff --name-only main` which conflates committed and uncommitted changes, and misses untracked files entirely. **Downstream mode** uses HTTP fetch + local file comparison, which inherently catches everything. The task asks for explicit, flexible control over what kind of changes are detected.

## Implementation Plan

### Step 1: Add `--change-mode` CLI flag to `aitask_contribute.sh`

**File:** `.aitask-scripts/aitask_contribute.sh`

1. Add variable after line 39:
   ```bash
   ARG_CHANGE_MODE=""
   ```

2. Add to `parse_args()` (around line 778):
   ```bash
   --change-mode) ARG_CHANGE_MODE="$2"; shift 2 ;;
   ```

3. Add validation after the `--target` validation block (after line 797):
   ```bash
   if [[ -n "$ARG_CHANGE_MODE" ]]; then
       case "$ARG_CHANGE_MODE" in
           all|committed|uncommitted) ;;
           *) die "Unknown change mode: $ARG_CHANGE_MODE (supported: all, committed, uncommitted)" ;;
       esac
   fi
   ```

4. Add `--change-mode` to `show_help()` in the Options section.

### Step 2: Update `list_changed_files()` (lines 440-470)

Replace the clone/project branch (lines 447-449) with mode-aware logic:

```bash
if [[ "$mode" == "clone" || "$mode" == "project" ]]; then
    local change_mode="${ARG_CHANGE_MODE:-all}"
    case "$change_mode" in
        all)
            { git diff --name-only main -- "${dirs[@]}" 2>/dev/null
              git ls-files --others --exclude-standard -- "${dirs[@]}" 2>/dev/null
            } | sort -u
            ;;
        committed)
            git diff --name-only main..HEAD -- "${dirs[@]}" 2>/dev/null || true
            ;;
        uncommitted)
            { git diff --name-only HEAD -- "${dirs[@]}" 2>/dev/null
              git ls-files --others --exclude-standard -- "${dirs[@]}" 2>/dev/null
            } | sort -u
            ;;
    esac
else
    # Downstream mode
    if [[ -n "$ARG_CHANGE_MODE" && "$ARG_CHANGE_MODE" != "all" ]]; then
        warn "--change-mode '$ARG_CHANGE_MODE' is ignored in downstream mode (always compares against upstream)"
    fi
    # (existing downstream logic unchanged)
fi
```

### Step 3: Extract `_generate_synthetic_diff()` helper and update `generate_diff()`

Extract the synthetic diff pattern (currently in downstream mode lines 490-498) into a reusable helper:

```bash
_generate_synthetic_diff() {
    local filepath="$1"
    if [[ ! -f "$filepath" ]]; then
        warn "File not found: $filepath"
        return
    fi
    echo "diff --git a/$filepath b/$filepath"
    echo "--- /dev/null"
    echo "+++ b/$filepath"
    local line_count
    line_count=$(wc -l < "$filepath" | tr -d ' ')
    echo "@@ -0,0 +1,$line_count @@"
    sed 's/^/+/' "$filepath"
}
```

Update `generate_diff()` clone/project branch (lines 479-480) to handle modes and untracked files:

```bash
if [[ "$mode" == "clone" || "$mode" == "project" ]]; then
    local change_mode="${ARG_CHANGE_MODE:-all}"
    for filepath in "${file_list[@]}"; do
        filepath="$(echo "$filepath" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        if [[ ! -f "$filepath" ]]; then
            warn "File not found: $filepath"
            continue
        fi
        if ! git ls-files --error-unmatch "$filepath" &>/dev/null; then
            # Untracked file: synthetic diff
            _generate_synthetic_diff "$filepath"
        else
            case "$change_mode" in
                all)         git diff main -- "$filepath" 2>/dev/null || true ;;
                committed)   git diff main..HEAD -- "$filepath" 2>/dev/null || true ;;
                uncommitted) git diff HEAD -- "$filepath" 2>/dev/null || true ;;
            esac
        fi
    done
fi
```

Also refactor downstream mode's new-file handling to use `_generate_synthetic_diff()`.

### Step 4: Update `build_issue_body()` file status column (line 581)

Replace hardcoded `Modified` with dynamic status:

```bash
local file_status="Modified"
if ! git show "main:$filepath" >/dev/null 2>&1; then
    file_status="New"
fi
echo "| \`$filepath\` | $file_status |"
```

### Step 5: Add `change_mode` to metadata (after line 633)

```bash
echo "change_mode: ${ARG_CHANGE_MODE:-all}"
```

### Step 6: Update SKILL.md — Add Step 2b

**File:** `.claude/skills/aitask-contribute/SKILL.md`

Add **Step 2b: Change Detection Mode** between Step 2 and Step 3:

- Only shown for clone/project modes (skip for downstream)
- Use `AskUserQuestion` with options: "All changes" (default), "Committed only", "Uncommitted only"
- Pass `--change-mode <mode>` to all subsequent `--list-changes`, `--dry-run`, and final invocations

### Step 7: Add tests to `tests/test_contribute.sh`

Extend test setup to include:
- Uncommitted (unstaged) modifications on the working branch
- Untracked new files

Add tests:
- `--change-mode all` returns committed + uncommitted + untracked files
- `--change-mode committed` returns only committed files (not uncommitted or untracked)
- `--change-mode uncommitted` returns only uncommitted + untracked files (not committed)
- Invalid `--change-mode` value is rejected
- Untracked files produce `--- /dev/null` in diff output
- File status table shows "New" for new files, "Modified" for modified files

### Step 8: Run shellcheck and existing tests

```bash
shellcheck .aitask-scripts/aitask_contribute.sh
bash tests/test_contribute.sh
```

## Critical Files

- `.aitask-scripts/aitask_contribute.sh` — Core changes (6 locations)
- `.claude/skills/aitask-contribute/SKILL.md` — Add Step 2b
- `tests/test_contribute.sh` — New change-mode tests

## Verification

1. `shellcheck .aitask-scripts/aitask_contribute.sh` passes
2. `bash tests/test_contribute.sh` passes (existing + new tests)
3. Manual spot-check: run `--list-changes --area scripts --change-mode committed` from a branch with both committed and uncommitted changes

## Step 9 (Post-Implementation)

Archive task and plan per the task-workflow.

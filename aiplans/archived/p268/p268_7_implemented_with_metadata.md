---
Task: t268_7_implemented_with_metadata.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_8_documentation.md
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md, p268_2_config_infrastructure.md, p268_3_common_config_library.md, p268_4_board_config_split.md, p268_5_tui_integration.md, p268_6_settings_tui.md, p268_9_refresh_code_models_skill.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Tasks completed by code agents currently have no record of *which* agent/model performed the implementation. This makes it hard to track quality across different models. This task adds `implemented_with` frontmatter tracking — the codeagent wrapper sets an env var before exec-ing the agent, the skill reads it during task claim, and the field flows through all parsing/writing/display code.

## Implementation Steps

### Step 1: Set `AITASK_AGENT_STRING` env var in wrapper (`aiscripts/aitask_codeagent.sh`)

**File:** `aiscripts/aitask_codeagent.sh`, `cmd_invoke()` function (lines 303-324)

In `cmd_invoke()`, the agent string is already resolved inside `build_invoke_command()` (line 244: `agent_string=$(resolve_agent_string "$operation")`). However, `build_invoke_command()` stores it locally. The simplest approach: resolve the agent string directly in `cmd_invoke()` before exec, and export it.

**Change at line 322 (before `exec "${CMD[@]}"`)**:
```bash
# Resolve and export agent string for skill tracking
local agent_string
agent_string=$(resolve_agent_string "$operation")
export AITASK_AGENT_STRING="$agent_string"

exec "${CMD[@]}"
```

### Step 2: Add `--implemented-with` flag to `aitask_update.sh`

**File:** `aiscripts/aitask_update.sh`

**2a. Add batch variables (after line 55):**
```bash
BATCH_IMPLEMENTED_WITH=""
BATCH_IMPLEMENTED_WITH_SET=false
```

**2b. Add global current value (after line 76):**
```bash
CURRENT_IMPLEMENTED_WITH=""
```

**2c. Add help text (in show_help, around lines 130-168).**

**2d. Add flag parsing in `parse_args()` (after line 197):**
```bash
--implemented-with) BATCH_IMPLEMENTED_WITH="$2"; BATCH_IMPLEMENTED_WITH_SET=true; shift 2 ;;
```

**2e. Add parsing in `parse_yaml_frontmatter()` (after line 342):**
```bash
implemented_with) CURRENT_IMPLEMENTED_WITH="$value" ;;
```

**2f. Add reset in `parse_yaml_frontmatter()` (after line 274):**
```bash
CURRENT_IMPLEMENTED_WITH=""
```

**2g. Add parameter to `write_task_file()` (line 401-421):**
- Add `local implemented_with="${20:-}"` after line 420

**2h. Add conditional write in `write_task_file()` body (after line 472, contributor_email block):**
```bash
if [[ -n "$implemented_with" ]]; then
    echo "implemented_with: $implemented_with"
fi
```

**2i. Add to `run_batch_mode()` (around lines 1329-1339):**
```bash
# Process implemented_with
local new_implemented_with="$CURRENT_IMPLEMENTED_WITH"
if [[ "$BATCH_IMPLEMENTED_WITH_SET" == true ]]; then
    new_implemented_with="$BATCH_IMPLEMENTED_WITH"
fi
```
And add `"$new_implemented_with"` as 20th arg to `write_task_file` call (line 1360-1364).

**2j. Add to `has_update` check (after line 1224):**
```bash
[[ "$BATCH_IMPLEMENTED_WITH_SET" == true ]] && has_update=true
```

**2k. Update `handle_child_task_completion()` (lines 670-722):**
- Save/restore: add `local saved_implemented_with="$CURRENT_IMPLEMENTED_WITH"` (after line 685) and `CURRENT_IMPLEMENTED_WITH="$saved_implemented_with"` (after line 722)
- Add `"$CURRENT_IMPLEMENTED_WITH"` as 20th arg to `write_task_file` call (line 694-699)

### Step 3: Add `extract_implemented_with()` to `task_utils.sh`

**File:** `aiscripts/lib/task_utils.sh` (after `extract_contributor_email()`, after line 386)

Follow the exact same pattern as `extract_contributor_email()`:
```bash
extract_implemented_with() {
    local file_path="$1"
    local in_yaml=false
    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break; else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^implemented_with:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"
    echo ""
}
```

### Step 4: Display in board TUI (`aiscripts/board/aitask_board.py`)

**File:** `aiscripts/board/aitask_board.py`, `TaskDetailPanel.compose()` (after line 1552, contributor block)

```python
if meta.get("implemented_with"):
    yield ReadOnlyField(f"[b]Implemented with:[/b] {meta['implemented_with']}", classes="meta-ro")
```

The board loads frontmatter via Python YAML parsing — unknown keys are automatically available in the `meta` dict, so no loader changes needed.

### Step 5: Update task-workflow SKILL.md

**File:** `.claude/skills/task-workflow/SKILL.md`

After the "Claim task ownership" step succeeds (after `OWNED:<task_id>` is parsed), add a new sub-step **"Record implementing agent"**:

```markdown
- **Record implementing agent:**

  Determine the agent string to record as `implemented_with` in the task frontmatter:

  1. **Check `AITASK_AGENT_STRING` env var** — if set (by the codeagent wrapper), use its value directly.

  2. **If not set, self-detect:**
     - Identify which code agent CLI you are running in: `claude`, `gemini`, `codex`, or `opencode`
     - Identify your current model ID from your system context (e.g., for Claude Code: the "exact model ID" from the system message, like `claude-opus-4-6`)
     - Read the corresponding model config file: `aitasks/metadata/models_<agent>.json`
     - Find the model entry whose `cli_id` matches your model ID
     - Extract the `name` field from that entry (e.g., `opus4_6`)
     - Construct the agent string as `<agent>/<name>` (e.g., `claude/opus4_6`)
     - If no matching entry is found, use `<agent>/<model_id>` as fallback (e.g., `claude/claude-opus-4-6`) — the raw model ID from the system context

  3. **Write to frontmatter:**
     ```bash
     ./aiscripts/aitask_update.sh --batch <task_num> --implemented-with "<agent_string>" --silent
     ```
```

This ensures `implemented_with` is populated whether the skill was launched via the codeagent wrapper or directly from a CLI.

### Step 6: Verify compatibility

- `ait ls` — `aitask_ls.sh` doesn't parse `implemented_with`, unknown YAML keys are ignored. No changes needed.
- Existing tasks without the field — `CURRENT_IMPLEMENTED_WITH` defaults to empty, `write_task_file` only writes it if non-empty. No impact.

## Verification Steps

1. Run `./aiscripts/aitask_codeagent.sh invoke task-pick 42 --dry-run` — should show `DRY_RUN:` output (env var only set on non-dry-run path, but verify no errors)
2. Run `./aiscripts/aitask_update.sh --batch 268_7 --implemented-with "claude/opus4_6"` — field should appear in task frontmatter
3. Run `./aiscripts/aitask_update.sh --batch 268_7 --implemented-with ""` — field should be removed
4. Run `./ait board` — task detail for t268_7 should show "Implemented with: claude/opus4_6"
5. Run `./ait ls` — should work normally with tasks that have the new field
6. Verify existing tasks without `implemented_with` are unaffected

## Final Implementation Notes

- **Actual work done:** Implemented all 5 planned steps: (1) env var export in codeagent wrapper, (2) `--implemented-with` flag in aitask_update.sh with full YAML parsing/writing/save-restore support, (3) `extract_implemented_with()` in task_utils.sh, (4) display in board TUI detail panel, (5) "Record implementing agent" sub-step in task-workflow SKILL.md with env var + self-detection fallback.
- **Deviations from plan:** None — all steps implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:**
  - Field is placed after `contributor_email` and before `created_at` in frontmatter output order
  - Self-detection fallback in SKILL.md uses the model ID from system context and looks it up in `models_<agent>.json` — if no match, falls back to raw model ID (e.g., `claude/claude-opus-4-6`)
  - The env var `AITASK_AGENT_STRING` is only set on the non-dry-run path in `cmd_invoke()` (dry-run exits before the export)
- **Notes for sibling tasks:**
  - t268_8 (documentation) should document:
    - The `implemented_with` frontmatter field and its format (`<agent>/<model_name>`)
    - How it's populated (env var from wrapper, or self-detection in skill)
    - The `--implemented-with` flag in `ait update`
    - Display in board TUI task detail panel

## Step 9 (Post-Implementation)

After implementation and review, archive task and plan per task-workflow Step 9.

---
Task: t480_1_add_explore_operation_to_codeagent.md
Parent Task: aitasks/t480_improve_aitaskexplore_integration.md
Sibling Tasks: aitasks/t480/t480_2_add_explore_shortcut_to_tui_switcher.md
Archived Sibling Plans: (none yet)
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Add `explore` operation to code agent system

## Steps

### 1. Add `explore` to SUPPORTED_OPERATIONS

**File:** `.aitask-scripts/aitask_codeagent.sh` line 24

Change:
```bash
SUPPORTED_OPERATIONS=(pick explain batch-review qa raw)
```
To:
```bash
SUPPORTED_OPERATIONS=(pick explain batch-review qa explore raw)
```

Place `explore` before `raw` since `raw` is the catch-all passthrough.

### 2. Add `explore)` cases to `build_invoke_command()`

**File:** `.aitask-scripts/aitask_codeagent.sh` lines 518-589

Add `explore)` case in each agent block, following the same pattern as `pick`/`explain`/`qa`:

**claudecode block (after `qa)` at line 532):**
```bash
                explore)
                    CMD+=("/aitask-explore")
                    ;;
```

**geminicli block (after `qa)` at line 551):**
```bash
                explore)
                    CMD+=("/aitask-explore")
                    ;;
```

**codex block (after `qa)` at line 566):**
```bash
                explore)
                    CMD+=("\$aitask-explore")
                    ;;
```

**opencode block (after `qa)` at line 583):**
```bash
                explore)
                    CMD+=("--prompt" "/aitask-explore")
                    ;;
```

### 3. Update help text

**File:** `.aitask-scripts/aitask_codeagent.sh` line 644

Change:
```
Operations: pick, explain, batch-review, qa, raw
```
To:
```
Operations: pick, explain, batch-review, qa, explore, raw
```

### 4. Add to OPERATION_DESCRIPTIONS

**File:** `.aitask-scripts/settings/settings_app.py` lines 116-127

Add after the `"raw"` entry:
```python
    "explore": "Model used for interactive codebase exploration (launched via TUI switcher shortcut 'x')",
```

### 5. Update seed defaults

**File:** `seed/codeagent_config.json`

Add `"explore": "claudecode/opus4_6"` to the defaults object.

### 6. Update live config

**File:** `aitasks/metadata/codeagent_config.json`

Add `"explore": "claudecode/opus4_6"` between `"raw"` and `"brainstorm-explorer"`.

## Verification

1. `ait codeagent invoke explore --dry-run` should output a valid command
2. `ait codeagent --help` should list `explore` in operations
3. `python -c "from settings.settings_app import OPERATION_DESCRIPTIONS; print(OPERATION_DESCRIPTIONS['explore'])"` should work

## Final Implementation Notes
- **Actual work done:** All 6 planned changes implemented exactly as specified — no deviations needed
- **Deviations from plan:** None. All line numbers and patterns were accurate
- **Issues encountered:** None
- **Key decisions:** Placed `explore` before `raw` in SUPPORTED_OPERATIONS since `raw` is the catch-all. Used `opus4_6` as default model (same as `pick`) since explore is a high-value interactive session
- **Notes for sibling tasks:** The `explore` operation is now fully registered. t480_2 can use `ait codeagent invoke explore` in the TUI switcher. The operation does NOT pass args (unlike pick/explain/qa) — it just launches `/aitask-explore` with no arguments

## Step 9 (Post-Implementation)

Archive task and push changes per shared workflow.

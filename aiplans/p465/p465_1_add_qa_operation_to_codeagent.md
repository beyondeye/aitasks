---
Task: t465_1_add_qa_operation_to_codeagent.md
Parent Task: aitasks/t465_launch_qa_from_codebrowser.md
Sibling Tasks: aitasks/t465/t465_2_*.md, aitasks/t465/t465_3_*.md, aitasks/t465/t465_4_*.md
Archived Sibling Plans: aiplans/archived/p465/p465_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add "qa" operation to codeagent system

## Step 1: Update SUPPORTED_OPERATIONS in aitask_codeagent.sh

File: `.aitask-scripts/aitask_codeagent.sh`, line 24

```bash
# Change:
SUPPORTED_OPERATIONS=(pick explain batch-review raw)
# To:
SUPPORTED_OPERATIONS=(pick explain batch-review raw qa)
```

## Step 2: Add qa cases to build_invoke_command()

File: `.aitask-scripts/aitask_codeagent.sh`, lines 518-576

Add `qa)` case after `explain)` in each agent's case block:

**claudecode** (after line ~528):
```bash
qa)
    # claude --model <id> "/aitask-qa <args>"
    CMD+=("/aitask-qa ${args[*]}")
    ;;
```

**geminicli** (after line ~544):
```bash
qa)
    CMD+=("/aitask-qa ${args[*]}")
    ;;
```

**codex** (after line ~556):
```bash
qa)
    CMD+=("\$aitask-qa ${args[*]}")
    ;;
```

**opencode** (after line ~570):
```bash
qa)
    CMD+=("--prompt" "/aitask-qa ${args[*]}")
    ;;
```

## Step 3: Update help text

File: `.aitask-scripts/aitask_codeagent.sh`

Find the line listing operations in help and add `qa`. Also update the examples section.

## Step 4: Add qa to seed/codeagent_config.json

File: `seed/codeagent_config.json`

Add `"qa": "claudecode/sonnet4_6"` to the defaults object.

## Step 5: Add qa to runtime codeagent_config.json

File: `aitasks/metadata/codeagent_config.json`

Add `"qa": "claudecode/sonnet4_6"` to the defaults object.

## Step 6: Add qa to OPERATION_DESCRIPTIONS in settings_app.py

File: `.aitask-scripts/settings/settings_app.py`, after line 119

```python
"qa": "Model used for QA analysis on completed tasks (used when launching QA from the Code Browser history)",
```

## Verification

- `ait codeagent resolve qa` → AGENT:claudecode, BINARY:claude
- `ait codeagent --dry-run invoke qa 42` → expected command with /aitask-qa
- `ait settings` → qa appears in Agent Defaults tab

## Step 9: Post-Implementation

Follow standard archival workflow.

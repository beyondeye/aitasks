---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [codebrowser, qa]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-25 12:56
updated_at: 2026-03-25 13:26
completed_at: 2026-03-25 13:26
---

## Context

The codebrowser TUI history screen needs the ability to launch `/aitask-qa` for completed tasks. Before that can work, the codeagent system (`aitask_codeagent.sh`) must support "qa" as a first-class operation, and the configuration/settings must include it.

This is the foundation task for the parent t465. The history screen QA launch (t465_3) depends on this.

## Key Files to Modify

- `.aitask-scripts/aitask_codeagent.sh` — Add `qa` to `SUPPORTED_OPERATIONS` array (line 24), add `qa)` case to `build_invoke_command()` for all 4 agent types (claudecode, geminicli, codex, opencode), update help text
- `seed/codeagent_config.json` — Add `"qa": "claudecode/sonnet4_6"` to defaults object
- `aitasks/metadata/codeagent_config.json` — Add `"qa": "claudecode/sonnet4_6"` to defaults object
- `.aitask-scripts/settings/settings_app.py` — Add `"qa"` entry to `OPERATION_DESCRIPTIONS` dict (after the "raw" entry, line ~119)

## Reference Files for Patterns

- `.aitask-scripts/aitask_codeagent.sh` lines 518-576: existing `build_invoke_command()` — follow the same pattern as `explain` for each agent type
- `.aitask-scripts/settings/settings_app.py` lines 115-125: `OPERATION_DESCRIPTIONS` dict — follow existing format

## Implementation Plan

1. In `aitask_codeagent.sh` line 24, change `SUPPORTED_OPERATIONS=(pick explain batch-review raw)` to `SUPPORTED_OPERATIONS=(pick explain batch-review raw qa)`
2. In `build_invoke_command()`, add `qa)` case after `explain)` for each agent:
   - claudecode: `CMD+=("/aitask-qa ${args[*]}")`
   - geminicli: `CMD+=("/aitask-qa ${args[*]}")`
   - codex: `CMD+=("\$aitask-qa ${args[*]}")`
   - opencode: `CMD+=("--prompt" "/aitask-qa ${args[*]}")`
3. Update help text to list qa in supported operations
4. Add `"qa": "claudecode/sonnet4_6"` to both seed and runtime codeagent_config.json
5. Add `"qa": "Model used for QA analysis on completed tasks (used when launching QA from the Code Browser history)"` to OPERATION_DESCRIPTIONS

## Verification Steps

- `ait codeagent resolve qa` should return AGENT:claudecode, BINARY:claude
- `ait codeagent --dry-run invoke qa 42` should print the expected command
- `ait settings` should show "qa" in the Agent Defaults tab

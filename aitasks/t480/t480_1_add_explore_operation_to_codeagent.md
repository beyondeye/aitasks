---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [aitask_explore, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-30 12:19
updated_at: 2026-03-30 21:44
---

## Summary

Register `explore` as a recognized codeagent operation so `ait codeagent invoke explore` works end-to-end. This enables the TUI switcher (child 2) to launch explore sessions with the user's configured agent/model.

## Context

The `/aitask-explore` skill is one of the most important skills but currently requires manual shell setup. This child task adds the backend plumbing — the `explore` operation in the code agent system — so it can be invoked programmatically like `pick`, `explain`, `qa`, etc.

Parent task t480 adds a TUI switcher shortcut that calls `ait codeagent invoke explore`. This child must be completed first so that command exists.

## Key Files to Modify

1. **`.aitask-scripts/aitask_codeagent.sh`**
   - Line 24: Add `explore` to `SUPPORTED_OPERATIONS` array
   - `build_invoke_command()` (lines 518-589): Add `explore)` case to each agent block following the `pick`/`explain`/`qa` pattern:
     - claudecode: `CMD+=("/aitask-explore")`
     - geminicli: `CMD+=("/aitask-explore")`
     - codex: `CMD+=("\$aitask-explore")`
     - opencode: `CMD+=("--prompt" "/aitask-explore")`
   - Line 644 (help text): Add `explore` to the operations list

2. **`.aitask-scripts/settings/settings_app.py`**
   - Lines 116-127 (`OPERATION_DESCRIPTIONS`): Add entry:
     ```python
     "explore": "Model used for interactive codebase exploration (launched via TUI switcher shortcut 'x')",
     ```

3. **`seed/codeagent_config.json`**
   - Add `"explore": "claudecode/opus4_6"` to defaults (opus — high-value interactive session like pick)

4. **`aitasks/metadata/codeagent_config.json`**
   - Add `"explore": "claudecode/opus4_6"` between `raw` and `brainstorm-*` entries

## Reference Files for Patterns

- `.aitask-scripts/aitask_codeagent.sh` — see how `pick`, `explain`, `qa` operations are defined in `build_invoke_command()` (lines 518-589) and `SUPPORTED_OPERATIONS` (line 24)
- `.aitask-scripts/settings/settings_app.py` — see `OPERATION_DESCRIPTIONS` dict (lines 116-127) for the existing operation descriptions
- `seed/codeagent_config.json` — current seed defaults structure

## Verification Steps

1. Run `ait codeagent invoke explore --dry-run` — should output the correct command (e.g., `claude --model claude-opus-4-6 /aitask-explore`)
2. Check `ait codeagent --help` — should list `explore` in operations
3. Verify `seed/codeagent_config.json` has the explore entry
4. Verify `aitasks/metadata/codeagent_config.json` has the explore entry

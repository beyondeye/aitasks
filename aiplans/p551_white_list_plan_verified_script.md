---
Task: t551_white_list_plan_verified_script.md
Base branch: main
plan_verified: []
---

# Plan: Whitelist `aitask_plan_verified.sh` for code agents

## Context

Recent commits (`000012e3`, `8d26cbbb`, `78547da0`) introduced a new helper
script `./.aitask-scripts/aitask_plan_verified.sh` used by the task-workflow
skill's plan-verification path (see `.claude/skills/task-workflow/planning.md`
and `profiles.md`). The script is not yet in any agent whitelist, so it will
trigger a permission prompt the first time `plan_preference: verify` runs.
Task t551 asks for it to be added to the seed whitelists (Claude Code,
OpenCode, Gemini CLI) as well as the currently installed whitelists in this
repo.

Out of scope: Codex CLI (not a whitelist-based agent in this repo) and
OpenCode's installed whitelist (the live `opencode.json` is gitignored via
`.opencode/.gitignore`; only the seed is tracked).

## Files to Modify

1. **`seed/claude_settings.local.json`** — JSON `permissions.allow` array.
   Add `"Bash(./.aitask-scripts/aitask_plan_verified.sh:*)"` alongside
   `aitask_plan_externalize.sh` / `aitask_verified_update.sh`.

2. **`seed/opencode_config.seed.json`** — JSON `permission.bash` object.
   Add `"./.aitask-scripts/aitask_plan_verified.sh *": "allow"` alongside
   the same two neighbors.

3. **`seed/geminicli_policies/aitasks-whitelist.toml`** — append a new
   `[[rule]]` block with
   `commandPrefix = "./.aitask-scripts/aitask_plan_verified.sh"` near the
   existing `aitask_verified_update.sh` / `aitask_plan_externalize.sh`
   rule blocks.

4. **`.claude/settings.local.json`** — installed Claude Code whitelist.
   Same addition as seed #1.

5. **`.gemini/policies/aitasks-whitelist.toml`** — installed Gemini CLI
   whitelist. Same addition as seed #3.

## Rationale for Placement

Each file already contains the sibling scripts `aitask_plan_externalize.sh`
and `aitask_verified_update.sh`. Placing the new entry next to these keeps
the whitelist ordering local/related and makes future diffs easier to read.

## Verification

- `grep -n aitask_plan_verified seed/claude_settings.local.json
  seed/opencode_config.seed.json seed/geminicli_policies/aitasks-whitelist.toml
  .claude/settings.local.json .gemini/policies/aitasks-whitelist.toml` —
  expect exactly one match in each of the 5 files.
- `python3 -c 'import json; json.load(open("seed/claude_settings.local.json"))'`
  and same for `.claude/settings.local.json` and
  `seed/opencode_config.seed.json` — confirm each JSON file still parses.
- Visual diff check to ensure each TOML rule block follows the surrounding
  format (toolName, commandPrefix, decision, priority) and each JSON entry
  preserves trailing-comma / no-trailing-comma conventions of that file.

## Step 9 (Post-Implementation)

Standard task-workflow archival: commit with
`chore: Whitelist aitask_plan_verified.sh (t551)`, then archive via
`./.aitask-scripts/aitask_archive.sh 551`.

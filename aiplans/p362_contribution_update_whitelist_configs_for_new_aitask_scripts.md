---
Task: t362_contribution_update_whitelist_configs_for_new_aitask_scripts.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Update whitelist configs for new aitask scripts (t362)

## Context

Contributor (beyondeye) submitted issue #4 with whitelist updates for newly added scripts (aitask_codeagent, aitask_codemap, aitask_contribute, aitask_lock_diag, aitask_opencode_models, aitask_pr_close, aitask_pr_import, aitask_sync) and removal of obsolete entries (aitask_clear_old, aitask_reviewmode_scan). The contribution was based on v0.9.0 — some seed files already have partial updates, so we apply only the missing changes.

## Analysis: Current State vs Contribution

### File 1: `.claude/settings.local.json` — NEEDS ALL CHANGES
- Replace `aitask_clear_old.sh` with: `aitask_claim_id.sh`, `aitask_codeagent.sh`, `aitask_codemap.sh`, `aitask_contribute.sh`
- Add `aitask_lock_diag.sh` (after absolute-path lock.sh line 37)
- Add `aitask_opencode_models.sh` (after aitask_archive.sh line 41)
- Add `aitask_pr_close.sh`, `aitask_pr_import.sh`, `aitask_sync.sh` (after absolute-path issue_import line 47)
- Remove `aitask_reviewmode_scan.sh` (line 52) — script was removed from codebase, replaced by `aitask_reviewguide_scan.sh` (which is already whitelisted)
- Add `./aiscripts/` entries at end (before closing bracket)

### File 2: `.gemini/policies/aitasks-whitelist.toml` — NEEDS ALL CHANGES
- Replace `aitask_clear_old.sh` rule with: claim_id, codeagent, codemap, contribute
- Add `aitask_lock_diag.sh` and `aitask_opencode_models.sh` rules (after lock regex rule)
- Add `aitask_pr_close.sh`, `aitask_pr_import.sh`, `aitask_sync.sh` rules (after issue_import regex rule)
- Remove `aitask_reviewmode_scan.sh` rule (script no longer exists)

### File 3: `seed/claude_settings.local.json` — PARTIAL (needs 4 entries)
Already has: claim_id, lock_diag, pr_close, pr_import, sync
Missing: `aitask_codeagent.sh`, `aitask_codemap.sh`, `aitask_contribute.sh` (after claim_id), `aitask_opencode_models.sh` (after aitask_ls.sh)

### File 4: `seed/geminicli_policies/aitasks-whitelist.toml` — NEEDS ALL CHANGES
Same as `.gemini/policies/` — identical structure.

### File 5: `seed/opencode_config.seed.json` — PARTIAL (needs 4 entries)
Already has: claim_id, lock_diag, pr_close, pr_import, sync
Missing: `aitask_codeagent.sh`, `aitask_codemap.sh`, `aitask_contribute.sh` (after claim_id), `aitask_opencode_models.sh` (after aitask_ls.sh)

## Scripts NOT in Whitelists (by design)

These scripts exist in `.aitask-scripts/` but are intentionally excluded from all whitelists because they are user-initiated or legacy:
- `aitask_board.sh` — launches TUI board (interactive)
- `aitask_codebrowser.sh` — interactive code browser
- `aitask_install.sh` — one-time installation
- `aitask_settings.sh` — settings management
- `aitask_setup.sh` — one-time project setup
- `aitask_stats_legacy.sh` — superseded by `aitask_stats.sh`

The contribution covers all agent-invoked scripts correctly.

## Implementation Steps

### Step 1: Edit `.claude/settings.local.json`
1. Replace `"Bash(./.aitask-scripts/aitask_clear_old.sh:*)"` with 4 entries (claim_id, codeagent, codemap, contribute)
2. Add `"Bash(./.aitask-scripts/aitask_lock_diag.sh:*)"` after the absolute-path lock.sh entry
3. Add `"Bash(./.aitask-scripts/aitask_opencode_models.sh:*)"` after aitask_archive.sh
4. Add pr_close, pr_import, sync entries after the absolute-path issue_import entry
5. Remove `aitask_reviewmode_scan.sh` entry
6. Add `./aiscripts/` entries before closing bracket

### Step 2: Edit `.gemini/policies/aitasks-whitelist.toml`
1. Replace `aitask_clear_old.sh` rule with 4 rules (claim_id, codeagent, codemap, contribute)
2. Add lock_diag and opencode_models rules after the lock regex rule
3. Add pr_close, pr_import, sync rules after issue_import regex rule
4. Remove aitask_reviewmode_scan.sh rule

### Step 3: Edit `seed/claude_settings.local.json`
1. Add codeagent, codemap, contribute entries after claim_id
2. Add opencode_models entry after aitask_ls.sh

### Step 4: Edit `seed/geminicli_policies/aitasks-whitelist.toml`
Same changes as Step 2.

### Step 5: Edit `seed/opencode_config.seed.json`
1. Add codeagent, codemap, contribute entries after claim_id
2. Add opencode_models entry after aitask_ls.sh

## Verification
- Validate JSON syntax: `python3 -c "import json; json.load(open('.claude/settings.local.json'))"`
- Validate seed JSON: `python3 -c "import json; json.load(open('seed/claude_settings.local.json'))"`
- Validate opencode JSON: `python3 -c "import json; json.load(open('seed/opencode_config.seed.json'))"`
- Verify TOML files are syntactically correct (visual check of structure)
- `git diff --stat` to confirm all 5 files were modified

## Final Implementation Notes
- **Actual work done:** Applied all whitelist changes from the contribution across 5 config files. The main configs (.claude/settings.local.json, .gemini/) needed all changes; the seed files only needed 4 new entries each (codeagent, codemap, contribute, opencode_models) since other changes were already applied.
- **Deviations from plan:** None — all changes applied as planned.
- **Issues encountered:** None.
- **Key decisions:** Confirmed that 6 scripts (board, codebrowser, install, settings, setup, stats_legacy) are intentionally excluded from whitelists as they are user-initiated or legacy scripts not called by AI agents.

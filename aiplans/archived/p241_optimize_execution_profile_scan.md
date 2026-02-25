---
Task: t241_optimize_execution_profile_scan.md
Branch: main
Base branch: main
---

## Context

Execution profile selection at the start of skills currently requires 4+ LLM tool calls: one `ls` to list profile files, then one `Read` per profile to extract `name` and `description`. With 3 profiles, that's 4 tool calls just to build an AskUserQuestion. A single bash helper script can do this in 1 call.

## Plan

### 1. Create `aiscripts/aitask_scan_profiles.sh`

New helper script that scans all profile YAML files and outputs their metadata in structured format.

**Modes:**
- Default (no args): List all valid profiles
- `--auto`: Auto-select using priority: `remote` > single profile > first alphabetically

**Output format (pipe-delimited):**
```
PROFILE|<filename>|<name>|<description>
```

For `--auto` mode:
```
AUTO_SELECTED|<filename>|<name>|<description>
```

Error cases:
- `NO_PROFILES` — no YAML files found
- `INVALID|<filename>` — file has invalid/missing name field (skipped in listing, fatal in `--auto`)

**YAML parsing:** Use `grep`/`sed` to extract `name:` and `description:` fields (profiles are flat YAML, no complex structures needed).

### 2. Update 4 interactive skills (identical Step 0a)

Files:
- `.claude/skills/aitask-pick/SKILL.md`
- `.claude/skills/aitask-explore/SKILL.md`
- `.claude/skills/aitask-fold/SKILL.md`
- `.claude/skills/aitask-review/SKILL.md`

Replace the current Step 0a with new version that:
1. Runs `./aiscripts/aitask_scan_profiles.sh`
2. Parses `PROFILE|...` lines
3. If 0 profiles → skip
4. If 1 profile → auto-load, display message
5. If multiple → build AskUserQuestion from parsed data
6. After selection, read only the chosen profile: `cat aitasks/metadata/profiles/<filename>`

### 3. Update 2 autonomous skills (near-identical Step 1)

Files:
- `.claude/skills/aitask-pickrem/SKILL.md`
- `.claude/skills/aitask-pickweb/SKILL.md`

Replace Step 1 "Load Execution Profile" to use `--auto` mode.

### 4. Update task-workflow Step 3b

Update the null `active_profile` fallback branch to reference `aitask_scan_profiles.sh`.

### 5. Add to Claude permission whitelists

Add `Bash(./aiscripts/aitask_scan_profiles.sh:*)` to `.claude/settings.local.json` and `seed/claude_settings.local.json`.

### 6. Create `tests/test_scan_profiles.sh`

22 automated tests covering all modes, edge cases, invalid YAML, etc.

### 7. Make script executable, run shellcheck

## Final Implementation Notes
- **Actual work done:** All 7 plan steps implemented as planned. Created helper script, updated 7 skill files, added permission whitelist entries, created comprehensive test suite.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `PROFILES_DIR` env var override in the script for testability (tests set it to temp dirs). Invalid profiles output to stderr in `--auto` mode (so LLM stdout parsing is clean) but to stdout in list mode (so LLM sees warnings alongside results).

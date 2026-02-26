---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-26 15:01
updated_at: 2026-02-26 15:11
---

## Context

The codebrowser TUI and aitask-explain skill create run directories under `aiexplains/` but never clean up stale data automatically. Multiple runs for the same source directory accumulate indefinitely.

## Task

Create a new bash script `aiscripts/aitask_explain_cleanup.sh` that removes stale aiexplain run directories, keeping only the newest per source directory key.

## Key Files to Modify

- `aiscripts/aitask_explain_cleanup.sh` — CREATE: the core cleanup script
- `ait` — ADD `explain-cleanup` command routing (line ~129, near `explain-runs`)
- `seed/claude_settings.local.json` — ADD whitelist entry
- `.claude/settings.local.json` — ADD whitelist entry

## Reference Files for Patterns

- `aiscripts/aitask_explain_runs.sh` — follow same script conventions (set -euo pipefail, terminal_compat.sh, safety checks)
- `aiscripts/codebrowser/explain_manager.py:29-34` — `_dir_to_key()` for naming convention reference

## Implementation Details

**Modes:**
- `--target DIR` (default: `aiexplains/`), `--all` (both `aiexplains/` and `aiexplains/codebrowser/`), `--dry-run`, `--quiet`

**Algorithm:**
1. List all subdirectories in target
2. Parse each name:
   - `<key>__<YYYYMMDD_HHMMSS>` → extract key and timestamp via regex `^(.+)__([0-9]{8}_[0-9]{6})$`
   - Bare `<YYYYMMDD_HHMMSS>` (15 chars) → group under `_bare_timestamp_`
3. Group by key. For groups with 2+ entries, keep newest (sort by timestamp), delete rest
4. Safety: `realpath` validation under `aiexplains/`, verify `files.txt`/`raw_data.txt` presence
5. Output: `CLEANED: N` on last line (machine-parseable)

**Dispatcher integration:** Add `explain-cleanup` to `ait` (near line 129 where `explain-runs` is routed).

**Settings:** Add `"Bash(./aiscripts/aitask_explain_cleanup.sh:*)"` to both settings files.

## Verification

1. `shellcheck aiscripts/aitask_explain_cleanup.sh`
2. `./aiscripts/aitask_explain_cleanup.sh --dry-run --all` — should list stale dirs without deleting
3. `./aiscripts/aitask_explain_cleanup.sh --all` — should clean 10+ stale dirs
4. `./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser` — should work on specific dir

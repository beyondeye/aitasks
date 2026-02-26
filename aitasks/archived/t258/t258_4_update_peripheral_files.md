---
priority: medium
effort: low
depends: [t258_3]
issue_type: feature
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-26 15:02
updated_at: 2026-02-26 16:40
completed_at: 2026-02-26 16:40
---

## Context

After the cleanup script (t258_1), extract script changes (t258_2), and explain_manager.py updates (t258_3) are complete, several peripheral files need updating to reflect the new naming convention and cleanup capabilities.

## Task

Update the following files for consistency with the new naming and cleanup system:
1. `aiscripts/aitask_explain_runs.sh` — add cleanup mode, scan codebrowser, improve display
2. `.claude/skills/aitask-explain/SKILL.md` — document new naming and auto-cleanup

## Key Files to Modify

- `aiscripts/aitask_explain_runs.sh`
- `.claude/skills/aitask-explain/SKILL.md`

## Implementation Details

### aitask_explain_runs.sh

**Add `--cleanup-stale` mode:**
```bash
# In parse_args():
--cleanup-stale)
    MODE="cleanup-stale"
    shift
    ;;
# In main():
cleanup-stale) exec "$SCRIPT_DIR/aitask_explain_cleanup.sh" --all ;;
```

**Update `list_runs()` (lines 18-42):**
- Also scan `aiexplains/codebrowser/*/files.txt` to show codebrowser runs
- Display section headers: "=== Top-level runs ===" and "=== Codebrowser runs ==="

**Update `interactive()` display (lines 104-115):**
- Parse dir_key from keyed directory names for better display:
```bash
local display_name="$run_name"
if [[ "$run_name" =~ ^(.+)__([0-9]{8}_[0-9]{6})$ ]]; then
    local key="${BASH_REMATCH[1]}"
    local ts="${BASH_REMATCH[2]}"
    display_name="${key} @ ${ts}"
fi
```

**Update help text:** Add `--cleanup-stale` documentation.

### SKILL.md

- Line 193: Change "Each run creates an isolated directory under `aiexplains/<timestamp>/`" → "Each run creates an isolated directory under `aiexplains/<dir_key>__<timestamp>/` where `dir_key` is derived from the common parent directory of analyzed files"
- After Step 3 gather command: Add note that stale runs are automatically cleaned up
- Step 6 Cleanup: Add note that stale cleanup is automatic; manual cleanup removes the latest run entirely

## Verification

1. `shellcheck aiscripts/aitask_explain_runs.sh`
2. `./aiscripts/aitask_explain_runs.sh --list` — verify both top-level and codebrowser runs shown
3. `./aiscripts/aitask_explain_runs.sh --cleanup-stale` — verify delegates to cleanup script
4. Review SKILL.md changes for accuracy

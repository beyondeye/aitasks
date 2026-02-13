---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 02:45
updated_at: 2026-02-13 10:45
---

## Bug

The atomic task ID counter (`aitask_claim_id.sh --claim`) is failing when called from the `aitask-create` Claude Code skill during finalization via `aitask_create.sh --batch --finalize`. Both t110 and t111 creation fell back to local scan:

```
Warning: Remote ID counter unavailable, falling back to local scan
```

This means the atomic counter mechanism introduced in t108 is not working in practice, at least when invoked from Claude Code's skill workflow.

## Root Cause Investigation

Possible causes to check:
1. **`aitask-ids` branch not initialized on remote** — `ait setup` may not have been run after t108 was implemented, or the branch wasn't pushed. Check: `git ls-remote --heads origin aitask-ids`
2. **Script path issue** — `aitask_claim_id.sh` may not be found or not executable when called from `aitask_create.sh` in the skill context
3. **Git remote not accessible** — network or auth issues when running inside Claude Code
4. **Error swallowed by `2>/dev/null`** — the claim call in `finalize_draft()` and `run_batch_mode()` uses `2>/dev/null` which hides the actual error. Need to see the real error message
5. **Working directory issue** — the script assumes it can find `origin` remote from the current working directory, which may differ in the skill context

## Required Fixes

### 1. Debug and fix the root cause
- Run `./aiscripts/aitask_claim_id.sh --claim` manually and see if it works
- Run `./aiscripts/aitask_claim_id.sh --peek` to check counter state
- Check if `aitask-ids` branch exists: `git ls-remote --heads origin aitask-ids`
- If branch doesn't exist, run `./aiscripts/aitask_claim_id.sh --init`
- Test finalization end-to-end: create draft then finalize

### 2. Remove silent fallback to local scan
The current fallback in `aitask_create.sh` silently falls back to local scan when the atomic counter fails:

```bash
claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>/dev/null) || {
    warn "Remote ID counter unavailable, falling back to local scan" >&2
    claimed_id=$(get_next_task_number_local)
}
```

This defeats the purpose of atomic IDs. Instead:
- **In batch mode (called from skills):** Fail with a clear error message telling the user to finalize via `ait create` (interactive) which can handle the setup
- **In interactive mode:** Offer to run `ait setup` to initialize the counter, or let user choose local-scan fallback explicitly
- Keep `get_next_task_number_local()` as a function but only use it when there's genuinely no remote (pure local repo)

### 3. Improve error visibility
- Don't suppress stderr with `2>/dev/null` on the claim call — let the actual error propagate
- Add a `--verbose` or `--debug` flag to `aitask_claim_id.sh` for troubleshooting

## Reference Files

- aiscripts/aitask_claim_id.sh (the atomic counter script)
- aiscripts/aitask_create.sh (lines ~484-488 and ~1179-1182 — the fallback logic)
- tests/test_claim_id.sh (tests pass in isolation but may not reflect real usage)
- aiplans/archived/p108_force_git_pull_at_start_of_task_create.md

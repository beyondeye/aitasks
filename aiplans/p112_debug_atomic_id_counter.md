---
Task: t112_debug_atomic_id_counter.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Debug Atomic ID Counter (t112)

## Context

The atomic task ID counter (`aitask_claim_id.sh --claim`) fails when called from the `aitask-create` skill. Both t110 and t111 fell back to local scan with "Remote ID counter unavailable".

**Root cause confirmed:** The `aitask-ids` branch was never initialized on the remote. `git ls-remote --heads origin aitask-ids` returns empty, and `--claim` fails with "Failed to fetch 'aitask-ids' from origin."

## Implementation Steps

### Step 1: Initialize the counter branch

Run `./aiscripts/aitask_claim_id.sh --init` to create the `aitask-ids` branch on the remote. Verify with `--peek` and `--claim`.

### Step 2: Fix fallback logic in `aitask_create.sh`

**Principle:** Local-scan fallback is **dangerous** in multi-PC/multi-user repos (can cause duplicate task IDs). It must never happen silently. It requires:
- **In batch mode** (called from skills / `--batch --commit`): **Fail hard** with a clear error telling the user to run `ait setup`. No fallback.
- **In interactive mode** (terminal available): Show a clear **DANGER** warning about duplicate ID risk, then require explicit user consent before falling back to local scan.

#### 2a: `finalize_draft()` (lines 484-488)

This function is called from both interactive and batch contexts. Use `[[ -t 0 ]]` to detect terminal availability.

Replace:
```bash
claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>/dev/null) || {
    # Fallback to local scan if counter not available
    warn "Remote ID counter unavailable, falling back to local scan" >&2
    claimed_id=$(get_next_task_number_local)
}
```

With:
```bash
local claim_stderr
claim_stderr=$(mktemp)
claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>"$claim_stderr") || {
    local claim_err
    claim_err=$(cat "$claim_stderr")
    rm -f "$claim_stderr"

    if [[ -t 0 ]]; then
        # Interactive mode: warn and ask for consent
        echo "" >&2
        warn "Atomic ID counter failed: ${claim_err:-unknown error}" >&2
        warn "*** DANGER: Local scan fallback can cause DUPLICATE task IDs ***" >&2
        warn "*** when multiple PCs or users work on the same repository.  ***" >&2
        warn "Run 'ait setup' to initialize the atomic counter instead." >&2
        echo "" >&2
        printf "Use local scan anyway? (y/N): " >&2
        local answer
        read -r answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            claimed_id=$(get_next_task_number_local)
        else
            die "Aborted. Run 'ait setup' to initialize the atomic counter."
        fi
    else
        # Batch/non-interactive mode: fail hard
        die "Atomic ID counter failed: ${claim_err:-unknown error}. Run 'ait setup' to initialize the counter."
    fi
}
rm -f "$claim_stderr" 2>/dev/null
```

#### 2b: `run_batch_mode()` (lines 1179-1182)

This is always batch mode — fail hard, no fallback.

Replace:
```bash
claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>/dev/null) || {
    warn "Remote ID counter unavailable, falling back to local scan" >&2
    claimed_id=$(get_next_task_number_local)
}
```

With:
```bash
local claim_stderr
claim_stderr=$(mktemp)
claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>"$claim_stderr") || {
    local claim_err
    claim_err=$(cat "$claim_stderr")
    rm -f "$claim_stderr"
    die "Atomic ID counter failed: ${claim_err:-unknown error}. Run 'ait setup' to initialize the counter."
}
rm -f "$claim_stderr" 2>/dev/null
```

### Step 3: Add `--debug` flag to `aitask_claim_id.sh`

**File:** `aiscripts/aitask_claim_id.sh`

Add a `--debug` flag that shows verbose output for each step (fetch, read counter, push). When `--debug` is passed, don't suppress stderr on git operations. This helps future troubleshooting without needing to edit the script.

## Files to Modify

1. `aiscripts/aitask_create.sh` — Lines 484-488 and 1179-1182 (error visibility + consent-gated fallback)
2. `aiscripts/aitask_claim_id.sh` — Add `--debug` flag

## Verification

1. Run `./aiscripts/aitask_claim_id.sh --init` and verify branch creation
2. Run `./aiscripts/aitask_claim_id.sh --peek` to confirm counter value
3. Run `./aiscripts/aitask_claim_id.sh --claim` to test successful claim
4. Run tests: `bash tests/test_claim_id.sh`
5. Verify error path: test with a simulated failure to confirm error message is visible and batch mode fails hard

## Final Implementation Notes

- **Actual work done:** All 3 steps implemented as planned. Initialized the `aitask-ids` branch on remote (counter started at 123 = max(113) + 10 buffer). Fixed both `finalize_draft()` and `run_batch_mode()` fallback logic. Added `--debug` flag to `aitask_claim_id.sh`. Updated Test 11 in `test_draft_finalize.sh` to verify the new hard-failure behavior.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** Test 11 ("Finalize without network") expected the old silent-fallback behavior. Updated to verify the new hard-failure behavior (exit code 1, error mentioning `ait setup`, draft preserved).
- **Key decisions:** Used `[[ -t 0 ]]` (terminal detection) in `finalize_draft()` to distinguish interactive vs batch contexts, since the function is called from both paths. Verified that existing Claude Code skills don't need updates — `aitask-create` skill already documents "draft preserved on failure" which remains correct, and child-task-creating skills (`aitask-create2`, `aitask-pick`) never use the atomic counter.

## Step 9 (Post-Implementation)

Archive task and plan files per aitask-pick workflow.

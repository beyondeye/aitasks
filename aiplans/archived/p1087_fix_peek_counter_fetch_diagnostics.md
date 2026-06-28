---
Task: t1087_fix_peek_counter_fetch_diagnostics.md
Base branch: main
plan_verified: []
---

# t1087 - Fix `peek_counter` fetch diagnostics

## Context

`peek_counter()` in `.aitask-scripts/aitask_claim_id.sh` still used the old
fetch path that discarded `git fetch` stderr and collapsed real fetch failures
into a misleading `ait setup` hint when no local `aitask-ids` branch existed.
The claim path was already fixed in t1077 with `remote_branch_state()`, which
uses `git ls-remote` to distinguish a genuinely absent remote branch from
network/auth/FETCH_HEAD failures without writing `.git/FETCH_HEAD`.

## Implementation Plan

1. Update `.aitask-scripts/aitask_claim_id.sh::peek_counter()` to mirror the
   t1077 claim-path diagnostic split:
   - fetch with `refs/heads/$BRANCH:refs/remotes/origin/$BRANCH`
   - capture fetch stderr instead of redirecting it away
   - call `remote_branch_state()` when fetch fails
   - keep local fallback behavior, but warn with the real diagnostic before
     printing the local counter
   - only suggest `ait setup` when the remote branch is genuinely absent and no
     local branch can be read
2. Extend `tests/test_claim_id.sh` with `--peek` regressions using the same
   PATH-shadowing `git` shim pattern already used for the claim-path tests.
3. Verify with syntax checks and the full claim-id suite.

## Verification

- `bash -n .aitask-scripts/aitask_claim_id.sh`
- `bash -n tests/test_claim_id.sh`
- `bash tests/test_claim_id.sh`
- `git diff --check -- .aitask-scripts/aitask_claim_id.sh tests/test_claim_id.sh`

## Risk

### Code-health risk: medium
- Touches the shared task ID helper, but only the read-only peek path; behavior
  follows the existing t1077 claim-path helper and is covered by focused
  regressions. -> mitigation: none

### Goal-achievement risk: low
- The failure modes are explicit and covered by tests for present, absent,
  unreachable, and local-fallback remote states. -> mitigation: none

## Final Implementation Notes

- **Actual work done:** Updated `peek_counter()` to fetch the remote counter
  branch with an explicit refspec, capture fetch stderr, derive diagnostics via
  `remote_branch_state()`, and preserve local fallback while surfacing the real
  fetch/unreachable-origin problem. Added four `--peek` tests covering local
  fallback, fetch failure with no local branch, unreachable origin, and the
  genuinely uninitialized remote-branch case.
- **Deviations from plan:** None.
- **Issues encountered:** The Codex model detection command needed a stricter
  `grep '^model[[:space:]]*='` pattern because `model_reasoning_effort` also
  begins with `model`; metadata was recorded with the corrected
  `codex/gpt5_5` agent string.
- **Key decisions:** Keep the setup hint only on the absent-remote-branch path,
  matching the t1077 claim-path ownership of setup diagnostics. For local
  fallback, warn with the real diagnostic and then print only the numeric local
  counter on stdout.
- **Upstream defects identified:** None.

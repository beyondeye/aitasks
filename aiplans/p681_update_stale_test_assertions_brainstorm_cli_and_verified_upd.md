---
Task: t681_update_stale_test_assertions_brainstorm_cli_and_verified_upd.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix two stale test assertions

## Context

The t658 macOS audit identified two test assertions that have drifted from
production behavior. Both reproduce on Linux:

1. **`tests/test_brainstorm_cli.sh:201`** — asserts `status: init` immediately
   after `aitask_brainstorm_init.sh`. Production code in
   `.aitask-scripts/brainstorm/brainstorm_session.py` writes `status: init` at
   line 94 then transitions to `active` at line 153 before returning. The
   correct expected value post-init is `active`. Confirmed locally:
   ```
   FAIL: session status is init (expected 'init', got 'active')
   ```

2. **`tests/test_verified_update_flags.sh:49`** — asserts the resolution of
   `--cli-id claude-opus-4-6` produces `claudecode/opus4_6`. Root cause of
   intermittent failure is **not** "hardcoded model" as the task description
   suggests — it's that `aitask_resolve_detected_agent.sh:25-29` honors the
   `AITASK_AGENT_STRING` env var as a fast-path override, **before** parsing
   `--cli-id`. When the test runs inside a Claude Code session that exports
   `AITASK_AGENT_STRING=claudecode/opus4_7_1m`, the resolver returns the env
   value and ignores the explicit cli-id, breaking the test. Reproduced locally:
   ```
   $ AITASK_AGENT_STRING=claudecode/opus4_7_1m bash .aitask-scripts/aitask_verified_update.sh \
       --agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 5 --silent
   UPDATED:claudecode/opus4_7_1m:test_414_flags:100
   ```
   With the env var unset, the test passes. The test's intent is to verify
   `--cli-id` resolution semantics, so the env var MUST be cleared in the test.

## Implementation

### Fix 1: `tests/test_brainstorm_cli.sh`

Update line 201 assertion expected value from `init` → `active`, and update
the label to match.

```diff
-    assert_eq "session status is init" "init" "$status"
+    assert_eq "session status is active after init" "active" "$status"
```

### Fix 2: `tests/test_verified_update_flags.sh`

Add an `unset AITASK_AGENT_STRING` near the top of the script (after
`set -e`) so the resolver's env-var fast-path doesn't override the
test's explicit `--cli-id`/`--agent-string` arguments. This is a one-line
change that makes the test deterministic regardless of the calling
environment (Claude Code session, CI, plain shell).

```diff
 set -e

+# Clear env-var fast-path so resolver honors --cli-id / --agent-string flags.
+unset AITASK_AGENT_STRING
+
 SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

## Files to modify

- `tests/test_brainstorm_cli.sh` (line 201)
- `tests/test_verified_update_flags.sh` (top of file, after `set -e`)

## Verification

1. Run the brainstorm test — must report `PASS: 31, FAIL: 0`:
   ```bash
   bash tests/test_brainstorm_cli.sh
   ```
2. Run the verified-update test — must pass both with and without the env
   var set:
   ```bash
   bash tests/test_verified_update_flags.sh
   AITASK_AGENT_STRING=claudecode/opus4_7_1m bash tests/test_verified_update_flags.sh
   ```
   Both invocations must report `Results: 6 passed, 0 failed`.

## Step 9: Post-Implementation

Standard archival flow — no separate branch (working on `main`). Code commit
uses `test:` prefix with `(t681)` suffix. Plan file commit uses `ait:` prefix.

## Final Implementation Notes

- **Actual work done:** Two surgical edits as planned. `tests/test_brainstorm_cli.sh:201` updated to expect `active` (label updated to match: "session status is active after init"). `tests/test_verified_update_flags.sh` got a 3-line block (`unset AITASK_AGENT_STRING` plus a 1-line comment) inserted between `set -e` and the `SCRIPT_DIR=` assignment.
- **Deviations from plan:** None. Both edits applied verbatim.
- **Issues encountered:** During pre-edit `git status`, an unrelated WIP diff was visible in `.aitask-scripts/aitask_setup.sh` (textual upgrade messaging — not part of t681). It was confirmed with the user and excluded from this commit.
- **Key decisions:** Diagnosis of failure 2 corrected the root-cause framing in the task description: the issue is not a "hardcoded model string" but the `AITASK_AGENT_STRING` env-var fast-path in `aitask_resolve_detected_agent.sh:25-29` overriding the explicit `--cli-id`. Fix in the test (rather than in the resolver) was chosen because the resolver's env-var fast-path is intentional behavior used elsewhere; tests need to be hermetic against it.
- **Upstream defects identified:**
  - `aitask_resolve_detected_agent.sh:25-29` — `AITASK_AGENT_STRING` env-var fast-path silently overrides explicit `--cli-id` / `--agent` arguments. Likely intentional as a session-level cache, but it produces surprising behavior when callers pass an explicit cli-id and expect deterministic resolution. Worth a separate task to either (a) gate the fast-path on the absence of explicit `--cli-id` / `--agent-string`, or (b) document the override precedence in the script header so future test authors know to clear the env var.
- **Verification:** Ran `bash tests/test_brainstorm_cli.sh` → `PASS: 31, FAIL: 0`. Ran `bash tests/test_verified_update_flags.sh` and `AITASK_AGENT_STRING=claudecode/opus4_7_1m bash tests/test_verified_update_flags.sh` → both `Results: 6 passed, 0 failed, 6 total`, confirming the unset is effective.

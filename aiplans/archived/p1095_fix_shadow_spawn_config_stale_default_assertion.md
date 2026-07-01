---
Task: t1095_fix_shadow_spawn_config_stale_default_assertion.md
Worktree: .
Branch: main
Base branch: main
---

# Implementation Plan

## Summary

Fix the stale regression test in `tests/test_shadow_spawn_config.sh` by making
the claudecode-specific assertions use an explicit
`--agent-string claudecode/opus4_8`, rather than relying on the project's
configurable `defaults.shadow`, which now resolves to `codex/gpt5_5`.

## Implementation Steps

1. Update the first dry-run block in `tests/test_shadow_spawn_config.sh`.
   - Replace the stale "Default agent" comment with an explicit claudecode
     comment.
   - Add `--agent-string claudecode/opus4_8` to the `%5 986_5` invocation.
   - Rename assertions from `default shadow ...` to `claudecode shadow ...`.

2. Keep the Codex-specific assertions unchanged.
   - The later Codex block already validates that the shadow operation launches
     through Codex's relaxed/default mode.
   - Do not update `aitasks/metadata/codeagent_config.json`; the current
     `shadow` default is the behavior that exposed the stale test.

3. Keep staging path-scoped.
   - The worktree contains unrelated local changes in gate/orchestrator files
     and untracked directories.
   - Stage only `tests/test_shadow_spawn_config.sh` for the code commit and this
     plan file for the plan commit.

## Verification

- Run `bash tests/test_shadow_spawn_config.sh`; expected result:
  `15/15 passed, 0 failed`.
- Run `bash tests/test_skillrun_codex_planmode.sh` to confirm Codex shadow still
  bypasses the plan-mode wrapper.
- Review `git diff -- tests/test_shadow_spawn_config.sh` before committing.

## Risk

### Code-health risk: low

- Single test-file edit, no production behavior changes. * severity: low *
  -> mitigation: None needed

### Goal-achievement risk: low

- Explicit dry-runs confirm claudecode still emits `/aitask-shadow`, while the
  configurable default resolves to Codex. Pinning the claudecode assertion
  directly addresses the stale assumption. * severity: low * -> mitigation:
  None needed

## Step 9 Notes

After implementation and review, commit code as
`bug: Fix shadow spawn config test assertion (t1095)`, commit this plan
separately with `./ait git`, run the declared gates, and archive with
`./.aitask-scripts/aitask_archive.sh 1095` only after gates pass.

## Final Implementation Notes

- **Actual work done:** Updated the stale claudecode-specific shadow spawn
  assertions in `tests/test_shadow_spawn_config.sh` to pass
  `--agent-string claudecode/opus4_8` explicitly, so the test no longer depends
  on the configurable `defaults.shadow` value.
- **Deviations from plan:** None.
- **Issues encountered:** The original regression reproduced as `13/15 passed`
  with two failures because the configured `shadow` default resolves to
  `codex/gpt5_5`. Explicit claudecode dry-run output still emitted
  `/aitask-shadow`, confirming the test should pin that agent string.
- **Key decisions:** Production config and launcher code were left unchanged;
  the fix is limited to test intent.
- **Verification:** `bash tests/test_shadow_spawn_config.sh` passed
  `15/15`; `bash tests/test_skillrun_codex_planmode.sh` passed `13/13`.
- **Upstream defects identified:** None

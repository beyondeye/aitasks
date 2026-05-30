---
Task: t861_add_codex_request_user_input_feature_flag.md
Worktree: /home/ddt/Work/aitasks
Branch: main
Base branch: main
---

# Task 861: Add Codex Request-User-Input Feature Flag

## Summary

Add Codex CLI's `default_mode_request_user_input` feature flag to the aitasks Codex setup pipeline so new `.codex/config.toml` files include it and existing configs receive it on `ait setup` reruns without overwriting unrelated settings.

## Implementation Steps

1. Update `seed/codex_config.seed.toml` to add:
   ```toml
   [features]
   default_mode_request_user_input = true
   ```
2. Keep `install.sh::install_seed_codex_config` unchanged because it already copies `seed/codex_config.seed.toml` into `aitasks/metadata/codex_config.seed.toml`.
3. Keep `.aitask-scripts/aitask_setup.sh::merge_codex_settings` unchanged unless tests reveal a defect; its current deep merge adds missing nested tables and preserves existing scalar values.
4. Update `tests/test_agent_instructions.sh` so `create_codex_staging` includes the new `[features]` block in its mock seed.
5. Extend setup integration assertions to verify:
   - Fresh `.codex/config.toml` creation includes `[features]`.
   - Fresh `.codex/config.toml` creation includes `default_mode_request_user_input = true`.
   - Existing `.codex/config.toml` files retain custom settings while receiving the missing feature flag.
   - Rerunning setup does not duplicate `default_mode_request_user_input`.

## Verification

- Run `bash tests/test_agent_instructions.sh`.
- Confirm the test suite covers fresh config creation, existing config merge behavior, preservation of unrelated settings, and idempotency.

## Step 9 Reference

After implementation and review, follow the aitask workflow Step 9 for archival and cleanup. This task uses the current branch under the `fast` profile, so no task branch merge or worktree cleanup is expected.

## Assumptions

- The desired flag belongs in project-level `.codex/config.toml`, not user-level `~/.codex/config.toml`.
- Existing user values should win if a user already set `features.default_mode_request_user_input`.
- No Codex skill workflow behavior changes are included in this task.

## Final Implementation Notes

- **Actual work done:** Added the Codex feature flag to `seed/codex_config.seed.toml` and expanded setup integration coverage for fresh config creation, existing config merge behavior, and rerun idempotency.
- **Deviations from plan:** None.
- **Issues encountered:** None. The existing TOML deep-merge path handled the new nested `[features]` table without script changes.
- **Key decisions:** Preserved the current merge behavior where existing user scalar values win over seed values, including if a user already configured `features.default_mode_request_user_input`.
- **Upstream defects identified:** None.
- **Verification:** `bash tests/test_agent_instructions.sh` passed with `65 / 65` assertions.

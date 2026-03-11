---
Task: t365_1_opencode_runtime_provider_mapping_fix.md
Parent Task: aitasks/t365_verified_stats_for_same_model_different_providers.md
Sibling Tasks: aitasks/t365/t365_2_*.md through t365_5_*.md
Archived Sibling Plans: (none yet - this is the first child)
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

OpenCode model self-detection currently mixes at least two identity schemes for GPT-family models: runtime/provider-qualified ids such as `openai/gpt-5.4`, and catalog entries derived from `opencode/*` ids such as `zen_gpt_5_4`. That mismatch can cause task attribution and verified-score updates to land on the wrong model/provider entry.

## Implementation Plan

1. Inspect `.aitask-scripts/aitask_opencode_models.sh` and the current `aitasks/metadata/models_opencode.json` naming rules to identify where provider identity is collapsed or rewritten unsafely.
2. Decide the stored-entry rule for OpenCode models so provider identity is preserved well enough for self-detection and verified-score attribution.
3. Update `.aitask-scripts/aitask_opencode_models.sh` to emit the corrected naming/identity scheme while preserving existing verified data during merge.
4. Update `.claude/skills/task-workflow/procedures.md` so OpenCode self-detection uses exact-match first, explicit alias mapping second, and raw fallback last.
5. Update `aitasks/metadata/models_opencode.json` and `seed/models_opencode.json` as needed for the new identity rules.
6. Add regression tests to `tests/test_codeagent.sh` for GPT 5.4 provider mismatch and for safe fallback behavior.

## Verification

- `bash tests/test_codeagent.sh`
- Manual inspection that OpenCode GPT-family attribution no longer falls through to `zen_gpt_5_4` when the provider does not match

## Final Implementation Notes

- **Actual work done:** Replaced the legacy `zen_*` naming scheme for `opencode/*` models with explicit `opencode_*` names in `.aitask-scripts/aitask_opencode_models.sh`, updated the checked-in OpenCode model metadata to match, added the missing `openai_gpt_5_4` entry, clarified the OpenCode attribution rule in `.claude/skills/task-workflow/procedures.md`, and extended `tests/test_codeagent.sh` with a GPT 5.4 provider-specific regression case.
- **Deviations from plan:** In addition to the naming/detection cleanup, I also performed a one-time historical data repair by moving the existing `gpt-5.4` verified stats from `opencode_gpt_5_4` to `openai_gpt_5_4`. This was necessary because the user verified in `ait settings` that the already-recorded feedback was still attached to the wrong provider row.
- **Issues encountered:** The checked-in metadata had two separate problems: legacy `zen_*` naming for `opencode/*` entries, and a missing `openai/gpt-5.4` row despite that provider now being discoverable from `opencode models --verbose`.
- **Key decisions:** Treated `AITASK_AGENT_STRING` as the primary source of truth when set by `ait codeagent`, and aligned stored OpenCode names with the actual provider namespace from `cli_id` instead of preserving the older `zen_*` alias. Preserved verified data by `cli_id` during discovery-script merges so renames do not wipe feedback history.
- **Notes for sibling tasks:** `t365_2` should treat the repaired `openai_gpt_5_4` history as the correct provider-specific baseline. If later work needs to support legacy archived values like `opencode/zen_gpt_5_4`, keep that as a read-time compatibility mapping rather than reintroducing `zen_*` as the primary stored naming scheme.

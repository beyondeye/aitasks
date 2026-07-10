---
Task: t1146_add_gpt5_6_sol_terra_luna_models.md
Worktree: .
Branch: main
Base branch: main
---

# Implementation Plan: Add GPT-5.6 Sol/Terra/Luna Models

## Context

Task `t1146` adds GPT-5.6 Sol, Terra, and Luna support to aitasks model registries for the `codex` and `opencode` code-agent surfaces.

Official docs checked during exploration:

- Codex model docs list `codex -m gpt-5.6-sol`, `codex -m gpt-5.6-terra`, and `codex -m gpt-5.6-luna`.
- OpenAI API model docs list `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`, with `gpt-5.6` as an alias for Sol. The registry should use explicit IDs, not aliases.

Existing local state:

- `aitasks/metadata/models_codex.json` and `seed/models_codex.json` include `gpt5_5`, `gpt5_4`, and older GPT entries, but no GPT-5.6 entries.
- `aitasks/metadata/models_opencode.json` and `seed/models_opencode.json` include provider-prefixed GPT-5.5 entries for both `openai/` and `opencode/`, but no GPT-5.6 entries.
- `opencode models --verbose` is available locally but currently does not list GPT-5.6 entries, so the implementation should add them deliberately rather than relying on discovery.
- `.aitask-scripts/aitask_codeagent.sh` already formats `gpt-5.6-sol` as `Codex/GPT5.6-Sol` and provider-prefixed OpenCode IDs as `OpenCode/GPT 5.6 Sol`. Formatter changes should not be needed.

## Files to Modify

1. `aitasks/metadata/models_codex.json`
   - Add three Codex entries near the existing GPT model entries:
     - `gpt5_6_sol` -> `gpt-5.6-sol`
     - `gpt5_6_terra` -> `gpt-5.6-terra`
     - `gpt5_6_luna` -> `gpt-5.6-luna`
   - Initialize `verified` and `verifiedstats` consistently with other new Codex entries.
   - Preserve all existing `verified`, `verifiedstats`, and `usagestats` data.

2. `seed/models_codex.json`
   - Mirror the same three Codex entries.

3. `aitasks/metadata/models_opencode.json`
   - Add six provider-prefixed OpenCode entries, mirroring the GPT-5.5 provider pattern:
     - `openai_gpt_5_6_sol` -> `openai/gpt-5.6-sol`
     - `openai_gpt_5_6_terra` -> `openai/gpt-5.6-terra`
     - `openai_gpt_5_6_luna` -> `openai/gpt-5.6-luna`
     - `opencode_gpt_5_6_sol` -> `opencode/gpt-5.6-sol`
     - `opencode_gpt_5_6_terra` -> `opencode/gpt-5.6-terra`
     - `opencode_gpt_5_6_luna` -> `opencode/gpt-5.6-luna`
   - Mark these entries `status: "active"` so they are selectable through the OpenCode agent, matching the previous GPT-5.5 support pattern.
   - Use notes consistent with current entries, including context and provider:
     - OpenAI provider: `GPT-5.6 Sol (1050k context, openai provider)` or, if matching current OpenAI-provider GPT notes exactly is preferred, use `400k context`. Before editing, compare the existing GPT-5.4/GPT-5.5 OpenAI provider context values and choose the convention that matches the closest model family.
     - OpenCode provider: `GPT-5.6 Sol (1050k context, opencode provider)` and equivalent Terra/Luna notes.
   - Preserve existing verified history and status fields on all current entries.

4. `seed/models_opencode.json`
   - Mirror the same six OpenCode entries.

5. `tests/test_agent_string.sh`
   - Add a focused assertion that `get_cli_model_id codex gpt5_6_sol` returns `gpt-5.6-sol`.
   - Optionally add Terra/Luna assertions if this keeps the test concise.

6. `tests/test_resolve_detected_agent.sh`
   - Add exact-match assertions:
     - `--agent codex --cli-id gpt-5.6-sol` -> `AGENT_STRING:codex/gpt5_6_sol`
     - `--agent opencode --cli-id openai/gpt-5.6-sol` -> `AGENT_STRING:opencode/openai_gpt_5_6_sol`
     - `--agent opencode --cli-id gpt-5.6-sol` -> suffix-match `AGENT_STRING:opencode/openai_gpt_5_6_sol` or the first matching provider entry. Verify the resolver's actual provider tie-breaker before finalizing this assertion.

7. `tests/test_codeagent.sh`
   - Extend list-models/coauthor coverage:
     - `list-models codex` shows `MODEL:gpt5_6_sol` and `CLI_ID:gpt-5.6-sol`.
     - `coauthor codex/gpt5_6_sol` emits `AGENT_COAUTHOR_NAME:Codex/GPT5.6-Sol`.
     - `coauthor opencode/openai_gpt_5_6_sol` emits `AGENT_COAUTHOR_NAME:OpenCode/GPT 5.6 Sol`.
   - Add a dry-run invoke check only if existing coverage makes it cheap and stable.

8. Optional docs/changelog candidates
   - `CHANGELOG.md` and `CHANGELOG_HUMANIZED.md` are release-managed and should not be edited unless this repo convention expects unreleased entries during implementation.
   - `website/content/docs/installation/updating-model-lists.md` and `website/content/docs/skills/aitask-add-model.md` should be checked only if the implementation changes OpenCode manual-add behavior. If the task only updates registries/tests, no docs update is required.

## Implementation Steps

1. Re-check model registry ordering and schemas.
   - Use `jq` to inspect the first/nearby entries in the Codex and OpenCode model files.
   - Decide OpenCode note context convention by comparing `openai_gpt_5_5`, `opencode_gpt_5_5`, and GPT-5.4 entries.

2. Update JSON registries with a structured JSON tool.
   - Prefer a short `jq` transformation or a repo-local helper if available.
   - Do not hand-edit large JSON arrays in a way that risks corrupting history fields.
   - After writing, run `jq .` on all four changed model files.

3. Add Codex entries.
   - Insert or append entries for `gpt5_6_sol`, `gpt5_6_terra`, and `gpt5_6_luna`.
   - Initialize:
     ```json
     "verified": {
       "batch-review": 0,
       "pick": 0,
       "explain": 0
     },
     "verifiedstats": {}
     ```
   - Do not copy `verifiedstats` or `usagestats` from `gpt5_5`.

4. Add OpenCode entries.
   - Add `openai_*` and `opencode_*` variants for Sol/Terra/Luna.
   - Initialize:
     ```json
     "status": "active",
     "verified": {
       "batch-review": 0,
       "pick": 0,
       "explain": 0
     },
     "verifiedstats": {}
     ```
   - Keep provider-prefixed `cli_id` values exactly as OpenCode expects.

5. Sync seed files.
   - Either run the same transformation against seed files or copy the metadata files to the seed mirrors if no environment-specific history makes that unsafe.
   - Confirm only intended differences remain.

6. Update tests.
   - Add assertions in `tests/test_agent_string.sh`, `tests/test_resolve_detected_agent.sh`, and `tests/test_codeagent.sh`.
   - Use existing assertion helpers and style.
   - Avoid tests that require live Codex/OpenCode binaries; use dry-run, resolver, and coauthor/list-models surfaces.

7. Run verification.
   - `jq . aitasks/metadata/models_codex.json aitasks/metadata/models_opencode.json seed/models_codex.json seed/models_opencode.json`
   - `bash tests/test_agent_string.sh`
   - `bash tests/test_resolve_detected_agent.sh`
   - `bash tests/test_codeagent.sh`
   - If time permits, run `bash tests/test_add_model.sh` to ensure existing model-add helper behavior is unchanged.

8. Review diffs carefully.
   - Verify no existing verification or usage history was removed.
   - Verify no unrelated task-data files are staged.
   - Confirm no changes were made to defaults unless explicitly chosen during implementation.

9. Step 9 cleanup reference.
   - After implementation and user review, follow task-workflow Step 8 for separate code/task-data commits.
   - After commits, follow task-workflow Step 9 for gate execution, archival, and push.

## Verification

Run:

```bash
jq . aitasks/metadata/models_codex.json aitasks/metadata/models_opencode.json seed/models_codex.json seed/models_opencode.json
bash tests/test_agent_string.sh
bash tests/test_resolve_detected_agent.sh
bash tests/test_codeagent.sh
bash tests/test_add_model.sh
```

Expected outcomes:

- JSON validation succeeds for all changed model files.
- Codex model lookup resolves GPT-5.6 Sol/Terra/Luna model names to exact CLI IDs.
- OpenCode model lookup resolves provider-prefixed GPT-5.6 entries.
- Coauthor formatting displays readable GPT-5.6 Sol/Terra/Luna labels.
- Existing GPT-5.5 verified/usage stats remain unchanged.

## Implementation Progress

- Added Codex GPT-5.6 Sol, Terra, and Luna entries to metadata and seed registries.
- Added OpenCode OpenAI-provider and OpenCode-provider GPT-5.6 Sol, Terra, and Luna entries to metadata and seed registries.
- Added regression coverage for Codex lookup, Codex/OpenCode detected-agent resolution, model listing, and coauthor labels.
- Verification passed:
  - `jq . aitasks/metadata/models_codex.json aitasks/metadata/models_opencode.json seed/models_codex.json seed/models_opencode.json`
  - `bash tests/test_agent_string.sh`
  - `bash tests/test_resolve_detected_agent.sh`
  - `bash tests/test_codeagent.sh`
  - `bash tests/test_add_model.sh`

## Final Implementation Notes

- **Actual work done:** Added GPT-5.6 Sol, Terra, and Luna entries to Codex model registries and mirrored them into seed templates. Added OpenCode `openai/` and `opencode/` provider entries for the same model family, also mirrored into seed templates. Added focused regression tests for Codex model lookup, detected-agent resolution, list-models output, and Codex/OpenCode coauthor display.
- **Deviations from plan:** Kept `aitask-add-model` behavior unchanged. The implementation added OpenCode registry entries directly because local `opencode models --verbose` did not yet list GPT-5.6, while the existing GPT-5.5 support pattern already uses active provider-prefixed entries for both OpenAI and OpenCode providers.
- **Issues encountered:** The first task creation attempt failed under the sandbox while updating git/task-ID metadata, leaving a malformed draft task file; that artifact was removed and committed separately on the task-data branch before implementation. Codex model self-detection needed a stricter `model =` grep because the documented command also matched `model_reasoning_effort`; attribution was recorded as `codex/gpt5_5` after narrowing the config read.
- **Key decisions:** Used explicit model IDs (`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`) rather than the `gpt-5.6` alias. Marked new OpenCode entries active to make them selectable, matching the prior GPT-5.5 support pattern. Did not promote any GPT-5.6 model to defaults.
- **Upstream defects identified:** None

## Risk

### Code-health risk: low
- The implementation touches shared model registries and shell tests, but the runtime path already supports arbitrary registry entries and the formatter already handles GPT-5.6 suffixes. The main code-health risk is accidental JSON corruption or loss of existing verified/usage history. Mitigation is structured JSON editing plus `jq` validation and diff review. · severity: low · -> mitigation: in-plan validation

### Goal-achievement risk: medium
- OpenCode discovery currently does not list GPT-5.6 locally even though official OpenAI docs list the models. Adding active provider-prefixed entries follows the existing GPT-5.5 support pattern, but a live OpenCode launch could still fail if the provider rejects the model before OpenCode updates its catalog. Mitigation is to keep the implementation explicit in tests and avoid claiming live-provider validation unless actually run. · severity: medium · -> mitigation: in-plan verification

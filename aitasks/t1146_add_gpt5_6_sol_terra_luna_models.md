---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, codexcli, opencode, models]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-07-10 19:30
updated_at: 2026-07-10 19:35
---

Add support for the GPT-5.6 Sol, Terra, and Luna model family in the aitasks code-agent model registries for both Codex and OpenCode.

## Exploration findings

- Current model registries include GPT-5.5 but do not include GPT-5.6 entries:
  - `aitasks/metadata/models_codex.json`
  - `aitasks/metadata/models_opencode.json`
  - `seed/models_codex.json`
  - `seed/models_opencode.json`
- Official OpenAI docs confirm these model IDs:
  - `gpt-5.6-sol`
  - `gpt-5.6-terra`
  - `gpt-5.6-luna`
- Codex docs show the direct CLI form:
  - `codex -m gpt-5.6-sol`
  - `codex -m gpt-5.6-terra`
  - `codex -m gpt-5.6-luna`
- API docs list `gpt-5.6-sol` as the Sol model ID and `gpt-5.6` as its alias. Prefer explicit model IDs in the registry rather than aliases, matching the existing registry convention.
- `aitask_add_model.sh` currently supports `claudecode` and `codex`, and intentionally rejects `opencode` with a pointer to `/aitask-refresh-code-models`.
- OpenCode models are normally discovered by `.aitask-scripts/aitask_opencode_models.sh`, which runs `opencode models --verbose`, converts provider-qualified CLI IDs into names, preserves existing verified/usage history, and marks missing entries as `status: unavailable`.
- Existing OpenCode GPT models use provider-prefixed IDs such as `openai/gpt-5.5` and `opencode/gpt-5.5`, with names like `openai_gpt_5_5` and `opencode_gpt_5_5`.

## Implementation scope

1. Add Codex registry entries for:
   - name `gpt5_6_sol`, cli_id `gpt-5.6-sol`
   - name `gpt5_6_terra`, cli_id `gpt-5.6-terra`
   - name `gpt5_6_luna`, cli_id `gpt-5.6-luna`
2. Add or refresh OpenCode registry entries for GPT-5.6 Sol/Terra/Luna using the established provider-prefixed convention.
   - If `opencode models --verbose` exposes them, prefer running/using the existing discovery flow and sync the result to seed.
   - If discovery is not available in the implementation environment, make an explicit design decision before adding manual OpenCode entries. Preserve the current provider-prefix naming convention and do not break the unavailable-model preservation behavior.
3. Sync all changed registry entries into `seed/models_codex.json` and `seed/models_opencode.json`.
4. Do not promote any GPT-5.6 model to default unless the implementation plan explicitly chooses that as a separate step. If promoting, update only the relevant `codeagent_config.json` defaults and seed mirror.
5. Review whether `aitask-add-model` should remain Codex-only for OpenAI models or whether it should support a narrow OpenCode manual-add mode. If changed, update the skill docs, helper validation, and tests accordingly.
6. Update user-facing docs only where they list current supported model examples or model-update behavior.

## Verification targets

- `bash tests/test_add_model.sh`
- `bash tests/test_agent_string.sh`
- `bash tests/test_codeagent.sh`
- Add or update focused tests so:
  - `get_cli_model_id codex gpt5_6_sol` resolves to `gpt-5.6-sol`.
  - `ait codeagent list-models codex` shows the new GPT-5.6 entries.
  - OpenCode GPT-5.6 entries resolve when active and unavailable entries remain blocked with the existing error path.
  - coauthor display formatting handles GPT-5.6 Sol/Terra/Luna cleanly for both Codex and OpenCode.
  - seed and metadata model files stay valid JSON and remain in sync for the new entries.

## References checked during exploration

- Official Codex models docs: https://developers.openai.com/codex/models/
- Official OpenAI API models docs: https://platform.openai.com/docs/models

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-10T16:35:32Z status=pass attempt=1 type=human

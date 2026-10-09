---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [codeagent, models, model_selection]
assigned_to: dario-e@beyond-eye.com
anchor: 1916
followup_kind: carry_over
created_at: 2026-10-09 16:00
updated_at: 2026-10-09 16:12
---

## Origin

Carried over from t1927, which made code-agent model supersession systematic
(no longer limited to former framework defaults) for `claudecode` and `codex`.
OpenCode was deliberately deferred: the user chose a follow-up after the
OpenCode registry refresh (t1919, landed dfa4d47b1).

Current state (as of t1927):
- `.aitask-scripts/lib/model_supersessions.json` has no `opencode` section.
- `aitask_add_model.sh` `validate_agent` refuses `opencode` for every
  subcommand, including `record-supersession`.
- The add-model skill Notes and `website/content/docs/commands/codeagent.md`
  (Superseded model defaults) state that OpenCode models have no lineages yet —
  update both when this lands.

## Why it needs its own design

OpenCode model names are provider-prefixed
(`opencode_claude_opus_4_5`, `openai_gpt_5_4`, `opencode_gpt_5_1`, …).
`model_supersession.family()` takes the leading letters, so every OpenCode
model is family `opencode` (or `openai`): the `WARN:family` guard and the
shipped-table contract test (`test_every_edge_is_registered_acyclic_and_same_family`
in `tests/test_model_supersession.py`) give no protection. Many entries are
`status: unavailable`; `load_registry` already excludes those from offers.

## Goal

1. Decide how OpenCode lineages are recorded: let `record-supersession`
   accept `opencode` (and only that subcommand — `add-json`/`promote-config`
   stay refused, since OpenCode models are CLI-discovered), or a dedicated path.
2. Define family/lineage for provider-prefixed names (e.g. compare after the
   `<provider>_` / `<provider>_<vendor>_` prefix: `opencode_claude_opus_4_5` →
   `opencode_claude_opus_4_6`), and update the family guard + contract test.
3. Backfill lineages against the refreshed `models_opencode.json`, each edge
   dry-run reviewed and confirmed by the user (same flow as t1927 step 4).
4. Decide whether `aitask_opencode_models.sh` / `aitask-refresh-code-models`
   should propose edges when a refresh adds a successor.

## Verification

- `python3 tests/test_model_supersession.py`, `bash tests/test_add_model.sh`,
  `bash tests/test_install_superseded_models.sh`.
- `ait codeagent check-superseded --report` offers an OpenCode successor for a
  config using a superseded OpenCode model.

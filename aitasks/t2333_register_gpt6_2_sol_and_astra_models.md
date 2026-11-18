---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, codex, opencode, models]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-18 22:57
updated_at: 2026-11-18 22:58
---

## Goal

Register OpenAI's new **GPT-6.2 Sol** and **GPT-6.2 Astra** models for the
`codex` and `opencode` code agents. Record them as successors of the
GPT-6.1 Sol and GPT-6 Astra models, so `ait upgrade` offers them to projects
that still use the older models.

## Evidence the models are live (checked 2026-11-18)

- **Codex** (`~/.codex/models_cache.json`, codex-cli 0.170.0):
  - `gpt-6.2-sol`: "Fast, go-to model for coding and everyday work."
  - `gpt-6.2-astra`: "Our most capable model for complex coding and professional work."
  - The same cache now describes `gpt-6.1-sol` and `gpt-6-astra` as "Previous generation".
- **OpenCode** (`opencode models --refresh`):
  - `openai/gpt-6.2-astra`, `openai/gpt-6.2-astra-fast`, `openai/gpt-6.2-astra-ultrafast`
  - `openai/gpt-6.2-sol`, `openai/gpt-6.2-sol-fast`, `openai/gpt-6.2-sol-ultrafast`
  - `opencode/gpt-6.2-astra`, `opencode/gpt-6.2-sol`

Re-check both before implementing.

## Scope

### 1. Codex registry

- Run `./.aitask-scripts/aitask_add_model.sh add-json --agent codex` for:
  - `gpt6_2_sol` / `gpt-6.2-sol`
  - `gpt6_2_astra` / `gpt-6.2-astra`

  Write notes in the same style as the existing GPT-6 entries.
- Confirm that both `seed/models_codex.json` and
  `aitasks/metadata/models_codex.json` get the new entries. The two files are
  currently in sync.
- Record two supersessions with `aitask_add_model.sh record-supersession --agent codex`:
  - `gpt6_1_sol` → `gpt6_2_sol`
  - `gpt6_astra` → `gpt6_2_astra`

  The edges go to `.aitask-scripts/lib/model_supersessions.json`. Follow the
  existing chain `gpt6_sol` → `gpt6_1_sol`.

### 2. OpenCode registry

- Run `ait opencode-models --sync-seed`, which updates both the metadata and
  seed `models_opencode.json`.
  - A dry run on 2026-11-18 showed that a **full refresh** also adds 18 entries
    unrelated to this task:
    - `*_flex` variants: `openai_gpt_5_4`, `5_5`, `5_6_{luna,sol,terra}`,
      `6_1_{sol,terra}`, `6_{astra,luna,sol}`
    - `opencode_claude_fable_5_2`
    - `opencode_gemini_4_{carbon,hydrogen}`
    - `opencode_hy4_flash_free`, `opencode_iceman_free`,
      `opencode_inkling_2_small_free`, `opencode_longcat_2_5_free`,
      `opencode_muse_ember_1_0`
  - It also marks `opencode_glm_5_3_flash_free` and
    `opencode_nemotron_3_ultra_free` as unavailable.
  - t2159 also did a full refresh. **Decide in planning** whether to accept the
    full refresh (the precedent, which keeps the registry honest) or to add only
    the 8 GPT-6.2 entries.
- Record these opencode supersession edges with `record-supersession --agent opencode`.
  An edge must stay within one provider, model line and variant.
  - `openai_gpt_6_1_sol` → `openai_gpt_6_2_sol`
  - `openai_gpt_6_1_sol_fast` → `openai_gpt_6_2_sol_fast`
  - `openai_gpt_6_1_sol_ultrafast` → `openai_gpt_6_2_sol_ultrafast`
  - `openai_gpt_6_astra` → `openai_gpt_6_2_astra` (plus the `_fast` and `_ultrafast` edges)
  - `opencode_gpt_6_1_sol` → `opencode_gpt_6_2_sol`
  - `opencode_gpt_6_astra` → `opencode_gpt_6_2_astra`

### 3. Default promotion (decide in planning)

The `shadow` and `discuss` ops currently default to `codex/gpt6_1_sol`. Codex
now labels 6.1 Sol "Previous generation". If the defaults move to
`codex/gpt6_2_sol`, follow the t1886 precedent (commit 95f0394cb) and use
`aitask_add_model.sh promote-config --agent codex --name gpt6_2_sol --ops shadow,discuss`.
Then update everything that names the old default:

- `seed/codeagent_config.json` and `aitasks/metadata/codeagent_config.json`
- `website/content/docs/commands/codeagent.md`: the op/default table at lines
  ~61-62
- `tests/lib/codeagent_defaults.sh`: the comment at ~107 that names
  `codex/gpt6_1_sol`
- `tests/test_codeagent_relations.sh:63`: it iterates over `codex/gpt6_1_sol`.
  Check whether it should follow the new default.

Run `website/check_links.py --build` if any website page changes.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_relations.sh`, and
  any add-model / supersession / opencode-models tests (`ls tests | grep -iE "model|supersession"`).
- `ait codeagent` resolves `codex/gpt6_2_sol`, `codex/gpt6_2_astra` and
  `opencode/openai_gpt_6_2_sol` without error.
- The seed and metadata registries stay in sync. Compare the name sets of each
  seed/metadata pair.

## Related precedents

- t2159 (aff353fe0): registered GPT-6.1 Terra and GPT-6 Astra, and refreshed the OpenCode registry.
- t1886 (95f0394cb): registered gpt6_1_sol and promoted it to the shadow/discuss default.
- t1919: refreshed the OpenCode registry and kept usage counters across the refresh.

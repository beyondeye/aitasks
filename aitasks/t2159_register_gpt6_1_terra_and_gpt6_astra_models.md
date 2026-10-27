---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, models, codex, opencode]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-27 08:28
updated_at: 2026-10-27 08:29
---

## Goal

Register OpenAI's new **GPT-6.1 Terra** model for the `codex` and `opencode`
agents, and close the adjacent codex gap for **GPT-6 Astra** found while
exploring.

## Findings (explore, 2026-10-27)

- **Codex catalog.** codex-cli 0.164.0's live catalog
  (`~/.codex/models_cache.json`) lists `gpt-6.1-terra` (display "GPT-6.1
  Terra", description "GPT-6.1 Terra Codex model.", priority 3, context 500k /
  max 872k, `fast` speed tier) and `gpt-6-astra` ("Frontier intelligence for the
  most demanding work.", priority 2). Neither is in
  `aitasks/metadata/models_codex.json` or `seed/models_codex.json`, so a codex
  session running either self-detects to the `unregistered_*` fallback.
- **OpenCode discovery.** After `opencode models --refresh`, the CLI lists
  `openai/gpt-6.1-terra` and `openai/gpt-6.1-terra-fast`. There is **no**
  `opencode/gpt-6.1-terra` (Zen provider) yet.
- **Astra composer animation.** The twinkling-dots mitigation
  (`-c tui.whimsy=false -c tui.effects.starfield=false`, see
  `website/content/docs/installation/known-issues.md`) is passed on every codex
  launch regardless of model, so `gpt6_astra` needs nothing model-specific.
- **No promotion.** `shadow`/`discuss` stay on `codex/gpt6_1_sol`. The website
  docs only list per-op defaults (`website/content/docs/commands/codeagent.md`),
  so no doc change is needed.

## Scope

### 1. Codex registration (`aitask_add_model.sh add-json`)

Dry-run each first, then apply. `add-json` writes both
`aitasks/metadata/models_codex.json` and `seed/models_codex.json`.

- `--agent codex --name gpt6_1_terra --cli-id gpt-6.1-terra`
- `--agent codex --name gpt6_astra --cli-id gpt-6-astra`

Write `--notes` in the existing codex entries' style, grounded in the catalog
descriptions above — do not invent capability claims.

### 2. Codex lineage

```bash
./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run --agent codex --old gpt5_6_terra --new gpt6_1_terra
```

`gpt5_6_terra` currently has no successor (no `gpt6_terra` exists). Do not record
any lineage for `gpt6_astra`: it is a new tier with no predecessor.

### 3. Full OpenCode registry refresh

```bash
./.aitask-scripts/aitask_opencode_models.sh --dry-run      # compare to the delta below
./.aitask-scripts/aitask_opencode_models.sh --sync-seed    # writes metadata + seed
```

The script refreshes the whole registry at once. That is by design; the user
chose the full refresh. Expected delta as of 2026-10-27 (**re-derive it**:
provider listings change):

- **New, active (10):** `openai_gpt_6_1_terra`, `openai_gpt_6_1_terra_fast`,
  `openai_gpt_6_1_sol_ultrafast`, `opencode_beam_free`,
  `opencode_deepseek_v4_1_flash_free`, `opencode_flint_40b_free`,
  `opencode_gemini_4_argon`, `opencode_glm_5_3_flash_free`,
  `opencode_muse_wonder_1_0`, `opencode_nemotron_3_5_super_vl_free`
- **Newly unavailable (10):** `opencode_claude_sonnet_4`,
  `opencode_deepseek_v4_flash`, `opencode_deepseek_v4_flash_vision_exp`,
  `opencode_exo_free`, `opencode_fledge_alpha_free`,
  `opencode_ling_3_0_flash_fin_free`, `opencode_ling_3_1_flash_free`,
  `opencode_longcat_2_5_preview_free`,
  `opencode_muse_spark_1_3_contributor_free`, `opencode_space_bunny_free`

Checked during explore: no test and no `codeagent_config.json` (metadata or
seed) pins any newly-unavailable name. Only `model_supersessions.json` refers to
some of them, and the supersession resolver already skips unavailable nodes
(`.aitask-scripts/lib/model_supersession.py`, `offer_target`). Re-run the grep
against the actual delta before committing. The same class of breakage hit
t1871 and is still open in t1909.

### 4. OpenCode lineage (`record-supersession` accepts `--agent opencode`)

- `openai_gpt_5_6_terra` → `openai_gpt_6_1_terra`
- `openai_gpt_5_6_terra_fast` → `openai_gpt_6_1_terra_fast`

`opencode_gpt_5_6_terra` gets no successor, because no Zen-provider
`gpt-6.1-terra` exists yet.

## Out of scope

- Lineage for the other models the refresh adds (e.g. `gemini_4_argon`,
  `muse_wonder_1_0`). Leave these to the `aitask-refresh-code-models` Step 6b
  flow.
- Promoting any of the new models to an op default.

## Verification

- `bash tests/test_add_model.sh`, `bash tests/test_opencode_models_merge.sh`,
  `python3 -m pytest tests/test_model_supersession.py` (or the aggregate runner
  with `--test-dir`).
- `./ait codeagent` resolution of `codex/gpt6_1_terra`, `codex/gpt6_astra` and
  `opencode/openai_gpt_6_1_terra` succeeds (no `unavailable`/`unregistered`
  error).
- `jq` check that metadata and seed agree on the new entries.

## Commit notes

`aitasks/metadata/models_*.json` live on the task-data branch. Commit them with
`./ait git` and an explicit `-- <path>` pathspec. A concurrent session had
uncommitted changes in the data worktree during explore (`SYNC_FAILED:dirty_worktree`).
Commit `seed/` and `.aitask-scripts/lib/model_supersessions.json` with plain
`git`, naming the paths.

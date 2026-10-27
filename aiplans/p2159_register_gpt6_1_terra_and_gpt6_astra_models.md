---
Task: t2159_register_gpt6_1_terra_and_gpt6_astra_models.md
Base branch: main
Output branch: main
---

# Plan: Register GPT-6.1 Terra and GPT-6 Astra (codex) + full OpenCode registry refresh (t2159)

## Context

codex-cli 0.164.0's live catalog (`~/.codex/models_cache.json`, re-read
2026-10-27) lists `gpt-6.1-terra` ("GPT-6.1 Terra Codex model.", priority 3,
500k/872k context) and `gpt-6-astra` ("Frontier intelligence for the most
demanding work.", priority 2). Neither is registered in
`aitasks/metadata/models_codex.json` / `seed/models_codex.json`, so a codex
session on either self-detects to `unregistered_*`, and
`./ait codeagent check codex/gpt6_1_terra` / `codex/gpt6_astra` fail today with
`Unknown model` (baseline confirmed). On the OpenCode side,
`openai/gpt-6.1-terra` and `openai/gpt-6.1-terra-fast` are discoverable but
unregistered (`opencode/openai_gpt_6_1_terra` → `Unknown model`).

The user chose a **full** OpenCode registry refresh (not a targeted add). This
task registers the models, records lineage, and promotes nothing.

Work runs on the current branch (`main`, profile `fast`) — no worktree.

## Re-derived facts (plan-time, 2026-10-27)

- **Codex dry-runs succeed:** `add-json --dry-run` for `gpt6_1_terra` appends
  to both metadata and seed. `record-supersession --dry-run --assume-registered
  --agent codex --old gpt5_6_terra --new gpt6_1_terra` → `RECORDED`. No seed op
  default uses `gpt5_6_terra` (no `BLOCKED:in_seed`).
- **OpenCode delta = exactly the task's expected delta.** `aitask_opencode_models.sh
  --dry-run` (139 models: 107 active, 32 unavailable) vs current metadata (129:
  107 active, 22 unavailable):
  - new, active (10): `openai_gpt_6_1_sol_ultrafast`, `openai_gpt_6_1_terra`,
    `openai_gpt_6_1_terra_fast`, `opencode_beam_free`,
    `opencode_deepseek_v4_1_flash_free`, `opencode_flint_40b_free`,
    `opencode_gemini_4_argon`, `opencode_glm_5_3_flash_free`,
    `opencode_muse_wonder_1_0`, `opencode_nemotron_3_5_super_vl_free`
  - active → unavailable (10): `opencode_claude_sonnet_4`,
    `opencode_deepseek_v4_flash`, `opencode_deepseek_v4_flash_vision_exp`,
    `opencode_exo_free`, `opencode_fledge_alpha_free`,
    `opencode_ling_3_0_flash_fin_free`, `opencode_ling_3_1_flash_free`,
    `opencode_longcat_2_5_preview_free`,
    `opencode_muse_spark_1_3_contributor_free`, `opencode_space_bunny_free`
  - dropped entirely: none; unavailable → active: none.
  - no `opencode/gpt-6.1-terra` (Zen) exists → `opencode_gpt_5_6_terra` gets no successor.
- **Pin check:** no test, `codeagent_config.json` (metadata or seed) or
  `codeagent_config.local.json` pins any newly-unavailable name. Only
  `.aitask-scripts/lib/model_supersessions.json` names three of them
  (`opencode_claude_sonnet_4`, `opencode_deepseek_v4_flash` as old nodes;
  `opencode_muse_spark_1_3_contributor_free` as a successor). The shipped-table
  contract (`edge_contract_problems`) is structural — any registered status
  counts — and `offer_target` skips unavailable nodes, so these edges stay valid.
- **`--sync-seed` is `cp metadata → seed`.** `seed/models_opencode.json` is
  byte-identical to the metadata file today (precedent t1919), so the copy keeps
  that convention.
- **OpenCode lineage dry-runs succeed** (`--assume-registered`):
  `openai_gpt_5_6_terra → openai_gpt_6_1_terra` and
  `openai_gpt_5_6_terra_fast → openai_gpt_6_1_terra_fast` → `RECORDED`
  (same line, same variant `terra` / `terra_fast`). The recorder requires the
  successor to be *available*, so these must run **after** the refresh.
- **Concurrent sessions:** the data worktree (`.aitask-data`) carries another
  session's uncommitted edits to `t1854_12` task/plan files; `main` carries
  uncommitted `goengines/` edits. All commits below name explicit paths.

## Implementation steps

Run from the repo root. Order matters: each `record-supersession` validates
against the real registry, so it runs after the registration it depends on.

1. **Codex: register `gpt6_1_terra`** (writes metadata + seed):
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --dry-run --agent codex \
     --name gpt6_1_terra --cli-id gpt-6.1-terra \
     --notes "GPT-6.1 Terra Codex model, successor to GPT-5.6 Terra"
   # review diff, then the same without --dry-run
   ```
   Notes are grounded in the catalog description ("GPT-6.1 Terra Codex model.")
   plus the lineage this task records — no invented capability/cost claims.

2. **Codex: register `gpt6_astra`:**
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --dry-run --agent codex \
     --name gpt6_astra --cli-id gpt-6-astra \
     --notes "Frontier-intelligence GPT-6 model for the most demanding work"
   # review diff, then apply
   ```
   Grounded in the catalog description ("Frontier intelligence for the most
   demanding work."). No model-specific launch flags: the twinkling-dots
   mitigation is already passed on every codex launch.

3. **Codex lineage** (no lineage for `gpt6_astra` — new tier, no predecessor):
   ```bash
   ./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run --agent codex --old gpt5_6_terra --new gpt6_1_terra
   ./.aitask-scripts/aitask_add_model.sh record-supersession --agent codex --old gpt5_6_terra --new gpt6_1_terra
   ```

4. **Full OpenCode refresh:**
   ```bash
   ./.aitask-scripts/aitask_opencode_models.sh --dry-run    # re-derive; compare to the delta above
   ./.aitask-scripts/aitask_opencode_models.sh --sync-seed  # writes metadata (CAS) + cp to seed
   ```
   If the dry-run delta differs from the one recorded above (provider listings
   move), re-run the pin grep (step 6) against the *actual* delta before
   continuing, and record the difference in Final Implementation Notes.

5. **OpenCode lineage:**
   ```bash
   ./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run --agent opencode --old openai_gpt_5_6_terra --new openai_gpt_6_1_terra
   ./.aitask-scripts/aitask_add_model.sh record-supersession --agent opencode --old openai_gpt_5_6_terra --new openai_gpt_6_1_terra
   ./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run --agent opencode --old openai_gpt_5_6_terra_fast --new openai_gpt_6_1_terra_fast
   ./.aitask-scripts/aitask_add_model.sh record-supersession --agent opencode --old openai_gpt_5_6_terra_fast --new openai_gpt_6_1_terra_fast
   ```
   If any call fails, stop and report actual on-disk state (`./ait git status
   --short -- aitasks/metadata/models_*.json`; `git status --short -- seed/
   .aitask-scripts/lib/model_supersessions.json`) rather than the exit status.

6. **Pin re-check against the applied delta** — for every newly-unavailable name
   (and its `cli_id`), grep `tests/`, `seed/`, `aitasks/metadata/codeagent_config*.json`,
   `.aitask-scripts/`, excluding `models_opencode.json`. Expected hits: only the
   three `model_supersessions.json` edges noted above (structurally valid).

Out of scope (per task): lineage for the other refresh additions (e.g.
`gemini_4_argon`, `muse_wonder_1_0`, `gpt_6_1_sol_ultrafast`); promoting any
model to an op default; website docs (only per-op defaults are documented).

## Verification

- Agent-string resolution (previously `Unknown model`):
  ```bash
  for a in codex/gpt6_1_terra codex/gpt6_astra opencode/openai_gpt_6_1_terra opencode/openai_gpt_6_1_terra_fast; do
    ./ait codeagent check "$a"; echo "rc=$?"; done
  ./ait codeagent --agent-string codex/gpt6_1_terra --dry-run invoke raw   # expect -m gpt-6.1-terra
  ./ait codeagent --agent-string codex/gpt6_astra   --dry-run invoke raw   # expect -m gpt-6-astra
  ```
- Detection maps the CLI id to the registered name (not `unregistered_*`):
  `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent codex --cli-id gpt-6.1-terra`
  (and `gpt-6-astra`; opencode `openai/gpt-6.1-terra`).
- Metadata/seed agreement:
  `jq` compare `{name,cli_id,notes}` of the two new codex entries across
  `aitasks/metadata/models_codex.json` and `seed/models_codex.json`;
  `cmp aitasks/metadata/models_opencode.json seed/models_opencode.json`.
- Supersession offers: `./ait codeagent check-superseded --report` runs clean.
- Tests (exit status checked, no pipes):
  - `bash tests/test_add_model.sh`
  - `bash tests/test_opencode_models_merge.sh`
  - `python3 -m pytest tests/test_model_supersession.py` (includes the
    shipped-table contract against `seed/models_*.json`)
  - `bash tests/test_install_superseded_models.sh` (copies the real table)
  - `bash tests/test_resolve_detected_agent.sh`, `bash tests/test_codeagent.sh`
    (read the real registries)
  - `bash tests/test_codeagent_resume_session.sh` — planned as a known
    pre-existing failure (t1909), but it passes 40/40: t1949 already derived its
    opencode model from a fixture registry (see Final Implementation Notes).

## Commits (Step 8)

- **Code (main, plain git, named paths):**
  `git commit -F - -- seed/models_codex.json seed/models_opencode.json .aitask-scripts/lib/model_supersessions.json`
  with subject `feature: Register GPT-6.1 Terra and GPT-6 Astra models and refresh OpenCode registry (t2159)`;
  then `git show --stat <sha>`.
- **Registry (task-data branch):**
  `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register codex gpt6_1_terra/gpt6_astra and refresh opencode registry" aitasks/metadata/models_codex.json aitasks/metadata/models_opencode.json`
  (both paths required; parse the outcome contract).
- **Plan:** `./.aitask-scripts/aitask_task_commit.sh -m "ait: Update plan for t2159" aiplans/p2159_register_gpt6_1_terra_and_gpt6_astra_models.md`.

Then Step 9 (Post-Implementation): gates, archival, push via `./ait git push`.

## Risk

### Code-health risk: low
- The full OpenCode refresh marks 10 entries unavailable; a hidden pin on one of them in a test or config would make the launcher refuse it (the t1871 / t1909 class) · severity: low (plan-time grep found none; the only references are structurally-valid supersession edges) · → mitigation: none — covered by step 6's re-grep against the applied delta
- Concurrent sessions have uncommitted edits in both the data worktree (`t1854_12`) and `main` (`goengines/`); a bare commit would sweep them in · severity: low · → mitigation: none — every commit names explicit paths
- `--sync-seed` copies the metadata file (including local usage/verified counters) over the seed · severity: low (seed is byte-identical to metadata today; precedent t1919) · → mitigation: none

### Goal-achievement risk: low
- The `gpt6_1_terra` catalog description is thin ("GPT-6.1 Terra Codex model."), so its notes could drift into invented capability claims · severity: low · → mitigation: none — notes are restricted to the catalog text plus the recorded lineage

## Final Implementation Notes
- **Actual work done:** All six implementation steps ran as planned, in order.
  - `add-json` registered `codex/gpt6_1_terra` (`gpt-6.1-terra`, notes "GPT-6.1 Terra Codex model, successor to GPT-5.6 Terra") and `codex/gpt6_astra` (`gpt-6-astra`, notes "Frontier-intelligence GPT-6 model for the most demanding work") in `aitasks/metadata/models_codex.json` and `seed/models_codex.json`.
  - `record-supersession` recorded `codex/gpt5_6_terra → gpt6_1_terra`.
  - `aitask_opencode_models.sh --sync-seed` refreshed the full registry: 139 models (107 active, 32 unavailable); the seed is byte-identical to the metadata file. A re-derived dry-run immediately before applying was identical to the plan-time delta: 10 new active, 10 active → unavailable, nothing dropped, nothing revived.
  - `record-supersession` recorded `opencode/openai_gpt_5_6_terra → openai_gpt_6_1_terra` and `openai_gpt_5_6_terra_fast → openai_gpt_6_1_terra_fast`.
  - The pin re-check against the applied delta (word-bounded on both the name and the `cli_id`, across `tests/` incl. fixtures, `seed/`, `.aitask-scripts/`, `codeagent_config*.json`) found only the three expected structural edges in `model_supersessions.json`.
- **Verification evidence:**
  - Before the change, `ait codeagent check` on `codex/gpt6_1_terra`, `codex/gpt6_astra` and `opencode/openai_gpt_6_1_terra` failed with `Unknown model`. After it, all three plus `opencode/openai_gpt_6_1_terra_fast` print `OK`.
  - `--dry-run invoke raw` emits `-m gpt-6.1-terra`, `-m gpt-6-astra` and `--model openai/gpt-6.1-terra`.
  - `aitask_resolve_detected_agent.sh` returns `AGENT_STRING:codex/gpt6_1_terra`, `codex/gpt6_astra` and `opencode/openai_gpt_6_1_terra`, not the `unregistered_*` fallback.
  - The new codex entries agree between metadata and seed (`jq` diff empty). `ait codeagent check-superseded --report` reports "No superseded code-agent model defaults."
  - Tests: `test_add_model.sh` 142/142, `test_opencode_models_merge.sh` 32/32, `test_install_superseded_models.sh` 23/23, `test_resolve_detected_agent.sh` 55/55, `test_codeagent.sh` all passed, `pytest tests/test_model_supersession.py` 57 passed (including the shipped-table contract against `seed/`), `test_codeagent_resume_session.sh` 40/40.
- **Deviations from plan:** None in the implementation. One verification expectation was wrong: `test_codeagent_resume_session.sh` was planned as a known t1909 failure, but it passes.
- **Issues encountered:** The first delta computation used `join` and failed on locale sort order; it was redone in Python. The plan-time `\b` pin grep also matched `claude-sonnet-4-6`, because PCRE `\b` treats `-` as a boundary; the implementation-time grep used explicit lookarounds instead.
- **Key decisions:**
  - Codex notes use only the catalog descriptions plus the lineage this task records.
  - No lineage for `gpt6_astra` (a new tier) or for the other refresh additions (per task scope).
  - `opencode_gpt_5_6_terra` gets no successor because no Zen-provider `gpt-6.1-terra` exists.
- **Upstream defects identified:** None
- **Stale task observed (not a code defect):** t1909 ("unpin opencode model in resume-session test") describes `tests/test_codeagent_resume_session.sh:107-112` pinning `opencode/openai_gpt_5_2`. That pin no longer exists: commit 4d1a9f93c (t1949) derives the model via `codeagent_active_model` from a fixture registry (now line 125), and the test passes 40/40. t1909 is still `Ready` and appears already resolved.

---
Task: t2333_register_gpt6_2_sol_and_astra_models.md
Base branch: main
Output branch: main
---

# t2333: Register GPT-6.2 Sol / Astra (codex + opencode), promote shadow/discuss

## Context

OpenAI released GPT-6.2 Sol and GPT-6.2 Astra. Both are live, re-checked on 2026-11-18:
- codex-cli 0.170.0 `~/.codex/models_cache.json` lists `gpt-6.2-sol` and `gpt-6.2-astra`, and now
  calls `gpt-6.1-sol` "Previous generation".
- `opencode models` lists `openai/gpt-6.2-{sol,astra}{,-fast,-ultrafast}` and `opencode/gpt-6.2-{sol,astra}`.

The models need registering in both agents' registries. They also need supersession edges, so that
`ait upgrade` offers them to projects that still use the older models.

Decisions made with the user during planning:
- **OpenCode: accept the full refresh** (the t2159 precedent). The dry run adds 26 entries: the 8
  GPT-6.2 ones plus 18 unrelated ones (`*_flex`, `opencode_claude_fable_5_2`, `gemini_4_{carbon,hydrogen}`,
  free models). It also marks `opencode_glm_5_3_flash_free` and `opencode_nemotron_3_ultra_free` as
  unavailable. No config or profile references those two models.
- **Promote** the shadow and discuss defaults from `codex/gpt6_1_sol` to `codex/gpt6_2_sol`
  (the t1886 precedent).

Work happens on the current branch, `main`. The worktree already holds unrelated changes from another
session (`task-workflow-remote-`, `.codex/config.toml`), so every commit names its paths explicitly.

## Implementation steps

All registry writes go through the existing helpers, `.aitask-scripts/aitask_add_model.sh` and
`.aitask-scripts/aitask_opencode_models.sh`. No JSON is edited by hand except one notes field (step 2).

1. **Codex registry: add both models.** `add-json` writes to both `seed/models_codex.json` and
   `aitasks/metadata/models_codex.json` (confirmed with a dry run):
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --agent codex --name gpt6_2_sol \
     --cli-id gpt-6.2-sol --notes "Latest GPT-6.2 workhorse model for coding and everyday agentic work"
   ./.aitask-scripts/aitask_add_model.sh add-json --agent codex --name gpt6_2_astra \
     --cli-id gpt-6.2-astra --notes "Frontier-intelligence GPT-6.2 model for the most demanding work, successor to GPT-6 Astra"
   ```
2. **Drop "Latest" from the old Sol note.** `gpt6_1_sol` reads "Latest GPT-6.1 workhorse…". Change it
   to "GPT-6.1 workhorse model for coding and everyday agentic work" in both codex JSON files, using a
   targeted `jq` update that keeps the rest of each file unchanged. Then check with `git diff` that
   only that one line changed in each file.
3. **Promote the defaults.** This also records `gpt6_1_sol → gpt6_2_sol`; the dry run showed it
   writes `RECORDED:codex/gpt6_1_sol->codex/gpt6_2_sol`:
   ```bash
   ./.aitask-scripts/aitask_add_model.sh promote-config --agent codex --name gpt6_2_sol --ops shadow,discuss
   ```
   It writes `seed/codeagent_config.json`, `aitasks/metadata/codeagent_config.json` and
   `.aitask-scripts/lib/model_supersessions.json`.
4. **Codex Astra supersession:**
   ```bash
   ./.aitask-scripts/aitask_add_model.sh record-supersession --agent codex --old gpt6_astra --new gpt6_2_astra
   ```
5. **OpenCode full refresh.** It writes both the metadata and the seed `models_opencode.json`, and
   keeps the usage counters (t1919):
   ```bash
   ./.aitask-scripts/aitask_opencode_models.sh --sync-seed
   ```
   Then check that all 8 GPT-6.2 names are present and `active` in both files, and that the two files
   hold the same set of names.
6. **OpenCode supersession edges.** Eight edges, each within one provider, model line and variant:
   `record-supersession --agent opencode --old <o> --new <n>` for
   - `openai_gpt_6_1_sol` → `openai_gpt_6_2_sol`; same for `_fast` and `_ultrafast`
   - `openai_gpt_6_astra` → `openai_gpt_6_2_astra`; same for `_fast` and `_ultrafast`
   - `opencode_gpt_6_1_sol` → `opencode_gpt_6_2_sol`
   - `opencode_gpt_6_astra` → `opencode_gpt_6_2_astra`

   No 6.2 `_flex` variant exists, so no flex edges are recorded.
7. **Update everything that names the old default:**
   - `website/content/docs/commands/codeagent.md:61-62`: change `codex/gpt6_1_sol` to `codex/gpt6_2_sol`
     in the shadow and discuss rows.
   - `tests/lib/codeagent_defaults.sh:107`: update the comment to `codex/gpt6_2_sol`.
   - `tests/test_codeagent_relations.sh:63`: **leave unchanged.** It uses `codex/gpt6_1_sol` only as
     an arbitrary non-claudecode agent string to test the `UNSUPPORTED_AGENT` refusal. That model stays
     registered, and the test does not follow the default.
   - `aidocs/benchmarks/shadow_q/pilot_report.md` records a past measurement and is left unchanged.
     The Astra starfield suppression (`.aitask-scripts/lib/agent_string.sh`) applies to every Codex
     launch, so it needs no change for the new Astra model.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_relations.sh`, `bash tests/test_codeagent_discuss.sh`,
  `bash tests/test_add_model.sh`, `bash tests/test_install_superseded_models.sh`,
  `bash tests/test_opencode_models_merge.sh`, `bash tests/test_opencode_models_reserved.sh`,
  `bash tests/test_codex_model_detect.sh`.
- `bash tests/run_all_python_tests.sh --test-dir` on a scratch dir holding `test_model_supersession.py` and
  `test_settings_superseded_models.py`, or run each with `python3 -m pytest`. Read only the final verdict line.
- Resolve checks: `./.aitask-scripts/aitask_codeagent.sh resolve shadow` and `… resolve discuss` show
  `codex/gpt6_2_sol`. `--agent-string codex/gpt6_2_astra --dry-run` and
  `--agent-string opencode/openai_gpt_6_2_sol --dry-run` invocations resolve without error.
- Seed and metadata stay in sync: compare the sorted `.models[].name` sets of each pair (codex, opencode).
  Supersessions JSON parses, and every new edge's target is registered.
- `cd website && python3 check_links.py --build`, because a website page changed.

## Commits

- Code: `git commit -m "feature: Register GPT-6.2 Sol/Astra models and promote shadow/discuss to gpt6_2_sol (t2333)" --`
  naming exactly: `seed/models_codex.json`, `seed/models_opencode.json`, `seed/codeagent_config.json`,
  `.aitask-scripts/lib/model_supersessions.json`, `website/content/docs/commands/codeagent.md`,
  `tests/lib/codeagent_defaults.sh`.
- Task data: `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register GPT-6.2 models in project metadata (t2333)"`
  with `aitasks/metadata/models_codex.json`, `aitasks/metadata/models_opencode.json` and
  `aitasks/metadata/codeagent_config.json`.
- Then Step 9 (Post-Implementation): archival via the shared workflow.

## Risk

### Code-health risk: low
None identified. The changes are data-only, written through the existing registry helpers. Each
helper validates its edge or entry, and the verification step checks seed/metadata parity.

### Goal-achievement risk: low
None identified. Both CLIs confirm the models are live (re-checked 2026-11-18). The user made both
decisions the task left to planning (full OpenCode refresh; promote the default).

## Final Implementation Notes
- **Actual work done:** All 7 plan steps were done as written. Codex: `gpt6_2_sol` and `gpt6_2_astra` were added to both seed and metadata registries. The `gpt6_1_sol` note lost its "Latest" prefix. shadow/discuss were promoted to `codex/gpt6_2_sol` (seed and metadata config). Two codex supersessions were recorded: `gpt6_1_sol→gpt6_2_sol` (by promote-config) and `gpt6_astra→gpt6_2_astra`. OpenCode: a full `--sync-seed` refresh (165 models: 131 active, 34 unavailable) plus 8 supersession edges (openai sol/astra × base/_fast/_ultrafast, opencode sol/astra). Website op table and the test-helper comment were updated.
- **Deviations from plan:** None. `tests/test_codeagent_relations.sh:63` was left unchanged on purpose, as planned. `ait opencode-models` is not routed by this checkout's `./ait` dispatcher, so the script was called directly as `.aitask-scripts/aitask_opencode_models.sh --sync-seed`.
- **Issues encountered:** `tests/test_codex_model_detect.sh` is not a regression test. It is a live probe that runs `codex exec` against every registered model, 64 billed calls. It "failed" calibration because no model self-reports its exact ID. That is a known limitation (and the reason the self-detection procedure reads `~/.codex/config.toml` instead). Its ground-truth runs confirmed that `gpt-6.2-sol` and `gpt-6.2-astra` both answer. The refresh also picked up an upstream note rewording for `opencode_deepseek_v4_1_flash` ("DeepSeek V4.1 Flash 1017 …"). That is OpenCode's own data, accepted as part of the full refresh.
- **Key decisions:** The user chose the full OpenCode refresh (t2159 precedent) and the default promotion (t1886 precedent). No `_flex` edges were recorded, because OpenCode offers no 6.2 flex variant. Usage counters were preserved by the refresh (only 3 lines removed from the metadata file: the note rewording and 2 status flips).
- **Upstream defects identified:** None

---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [codeagent, models]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1916
followup_kind: carry_over
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 17:01
updated_at: 2026-10-09 11:11
---

## Origin

Carried over from t1916 (register claudecode/haiku5_5). The user chose to keep
t1916 claudecode-only and do the OpenCode side as a separate full refresh.

## Goal

Run the OpenCode discovery path so `models_opencode.json` (metadata + seed)
reflects what OpenCode currently offers, including `opencode/claude-haiku-5-5`.

```bash
./.aitask-scripts/aitask_opencode_models.sh --dry-run --sync-seed   # review
./.aitask-scripts/aitask_opencode_models.sh --sync-seed
```

(or the `aitask-refresh-code-models` skill, which owns this path).

## Expected scope (measured 2026-10-08, opencode 1.18.34, scratch-copy run)

A full run against the current registry would:

- add ~30 entries, among them `opencode_claude_haiku_5_5`,
  `opencode_claude_opus_5_5`, `opencode_claude_sonnet_5_5`, several
  `openai_gpt_6*` / `opencode_gpt_6*`, `opencode_grok_4_7`,
  `opencode_mistral_large_4`, `opencode_qwen3_8_*`, `opencode_deepseek_v4_1_flash`,
  and several `*_free` models;
- flip 3 to `unavailable`: `opencode_mimo_v2_5_free`,
  `opencode_muse_spark_1_2_contributor_free`, `opencode_union_alpha`.

The measurement depends on the provider list at the time, so re-run the dry run;
these numbers will drift.

## Coordination

- t1912 moves `usagestats`/`verifiedstats` off `aitask-data` and touches
  `models_*.json` — check its state before committing.
- Metadata goes through `./.aitask-scripts/aitask_task_commit.sh`; the seed goes
  through `git commit -- seed/models_opencode.json`.

## Verification

- `./.aitask-scripts/aitask_codeagent.sh list-models opencode` lists
  `opencode_claude_haiku_5_5`.
- Existing `verified`/`verifiedstats` are preserved (the script keeps them for
  models that are still present).
- `jq .` succeeds on both files.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T08:11:20Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-09T08:32:53Z status=pass attempt=1 type=human

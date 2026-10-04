---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, models, claudecode, codexcli]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-04 15:45
updated_at: 2026-10-04 17:13
---

## Goal

Register two newly released models and promote each to default in every place
its predecessor is the default today:

| agent | model | `name` | `cli_id` | replaces as default |
|---|---|---|---|---|
| claudecode | Claude Sonnet 5.5 | `sonnet5_5` | `claude-sonnet-5-5` | `claudecode/sonnet5` |
| claudecode | Claude Sonnet 5.5 (explicit 1M) | `sonnet5_5_1m` | `claude-sonnet-5-5[1m]` | — (register only) |
| codex | GPT-6.1 Sol | `gpt6_1_sol` | `gpt-6.1-sol` | `codex/gpt6_sol` |

`sonnet5` and `gpt6_sol` stay registered and usable. Only their role as default
moves.

## CLI IDs: verified, re-check before writing

Verified on 2026-10-04, after the user upgraded both CLIs:

- **Codex CLI 0.160.0.** `codex debug models` (live catalog) lists
  `gpt-6.1-sol` / "GPT-6.1-Sol" / "Latest workhorse model for coding and everyday
  work", visibility `list`. It now describes `gpt-6-sol` as "Previous generation
  workhorse model". Note: `~/.codex/models_cache.json` was stale (client 0.154.0)
  and did **not** list it. Use `codex debug models`, not the cache file.
- **Claude Code 2.1.288.** The bundled model catalog has
  `{id:"claude-sonnet-5-5", family:"sonnet", display_name:"Sonnet 5.5"}` with a
  1M native context window, 128K max output and adaptive thinking (disabled
  thinking is rejected). It also contains the `claude-sonnet-5-5[1m]` variant.

**Precondition:** before any write, re-run `codex debug models | jq -r
'.models[].slug'` and confirm `gpt-6.1-sol` is still present. If it is missing,
stop and ask; do not register an ID the CLI does not offer.

### Why `sonnet5_5_1m` too

This mirrors `opus5_5_1m` (t1884). A Claude Code session started on the `[1m]`
variant self-detects `cli_id=claude-sonnet-5-5[1m]`. With no registry entry, it
resolves to the reserved fallback `claudecode/unregistered_claude_sonnet_5_5_1m`,
which the stats writers (`aitask_usage_update.sh` / `aitask_verified_update.sh`
via `ensure_model_exists`) reject. Defaults promote to the plain `sonnet5_5`,
never the `_1m` entry, the same as Opus 5.5.

Suggested notes, worded from the CLI catalog data above. Do not invent vendor
claims:
- `sonnet5_5`: "Best speed/intelligence balance, 1M context, 128K output, adaptive thinking always on"
- `sonnet5_5_1m`: "Best speed/intelligence balance, 1M context (explicit [1m] variant), 128K output, adaptive thinking always on"
- `gpt6_1_sol`: "Latest GPT-6.1 workhorse model for coding and everyday agentic work"

## Where the predecessors are default today

`aitasks/metadata/codeagent_config.json` (`.defaults`):
- `claudecode/sonnet5` → **7 ops:** `explain`, `batch-review`, `qa`, `raw`,
  `work-report`, `brainstorm-comparator`, `brainstorm-initializer`
- `codex/gpt6_sol` → **2 ops:** `shadow`, `discuss`

`seed/codeagent_config.json` (`.defaults`):
- `claudecode/sonnet5` → **5 ops:** `explain`, `work-report`, `batch-review`,
  `qa`, `raw` (the seed has no brainstorm keys, and `promote-config` silently
  skips keys that are missing)
- `codex/gpt6_sol` → `shadow`, `discuss`

No script under `.aitask-scripts/` names `sonnet5` or `gpt6_sol`. **No
`DEFAULT_AGENT_STRING` change:** the hardcoded fallback in
`.aitask-scripts/lib/agent_string.sh` is `claudecode/opus5_5`, and
`roadmap_run.py` defaults to opus too. Do **not** run
`promote-default-agent-string`.

## Implementation

All registry and config writes go through the helper
`.aitask-scripts/aitask_add_model.sh` (atomic tempfile + `jq` validation +
`mv`; `--dry-run` prints unified diffs). The `/aitask-add-model` skill wraps it.
Do not hand-edit the JSON.

1. **Register** (each call writes both `aitasks/metadata/models_<agent>.json`
   and `seed/models_<agent>.json`). Dry-run first, review, then apply:
   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode --name sonnet5_5    --cli-id claude-sonnet-5-5      --notes "..."
   ./.aitask-scripts/aitask_add_model.sh add-json --agent claudecode --name sonnet5_5_1m --cli-id 'claude-sonnet-5-5[1m]' --notes "..."
   ./.aitask-scripts/aitask_add_model.sh add-json --agent codex      --name gpt6_1_sol   --cli-id gpt-6.1-sol            --notes "..."
   ```
2. **Promote** (patches both the metadata and the seed config):
   ```bash
   ./.aitask-scripts/aitask_add_model.sh promote-config --agent claudecode --name sonnet5_5 \
     --ops explain,batch-review,qa,raw,work-report,brainstorm-comparator,brainstorm-initializer
   ./.aitask-scripts/aitask_add_model.sh promote-config --agent codex --name gpt6_1_sol --ops shadow,discuss
   ```
   The dry-run must show exactly **7 + 5 = 12** sonnet value changes and
   **2 + 2 = 4** sol value changes, with every `from` value equal to
   `sonnet5` / `gpt6_sol`. Re-derive the op list from `.defaults` at
   implementation time (`jq -r '.defaults | to_entries[] |
   select(.value=="claudecode/sonnet5") | .key'`). If it differs from the
   list above, use the live list.
3. **Hand edits** (the helper does not touch these):
   - `website/content/docs/commands/codeagent.md`: the default rows for
     `explain`, `work-report`, `batch-review`, `qa` and `raw` (~lines 54–64)
     change to `claudecode/sonnet5_5`. The `shadow` and `discuss` rows
     (~61–62) change to `codex/gpt6_1_sol`. The example JSON (~186–188)
     changes from `sonnet5` to `sonnet5_5`.
   - `website/content/docs/tuis/codebrowser/how-to.md:199`: the `qa` default
     changes to `claudecode/sonnet5_5`.
   - `tests/test_codeagent.sh:539-542` (Test 28): it asserts the literal
     `AGENT_STRING:claudecode/sonnet5` for `resolve explain`, and the file
     installs the seed config, so the promotion turns it red. Convert it to
     the t1318 derive idiom with `codeagent_config_default` /
     `codeagent_resolve_field` from `tests/lib/codeagent_defaults.sh`, as
     t1865 did for the rest of the file. Do not swap one literal for another.
   - `tests/lib/codeagent_defaults.sh:107`: change the comment "defaults.shadow
     is codex/gpt6_sol today" to `codex/gpt6_1_sol`.
   - Leave as is: `tests/test_codeagent_work_report.sh:11` (a historical "left
     this file red after t1241/t1242 promoted…" note, not a current-default
     claim). Also leave the `sonnet5` / `gpt6_sol` strings in
     `tests/test_agent_freeze.py`, `test_brainstorm_crew.py`,
     `test_launch_agent_string_env.py`, `test_pick_launch_argv.py`,
     `test_cross_repo_*.py` and `tests/lib/branch_mode_repo.py`: they are
     fixture data, and the old models stay registered. If any of these turns
     red, that is a real finding, not expected churn.
   - `aidocs/codeagents/claudecode_builtin_prompts.md` documents Claude Code's
     own built-in prompts (`low-sonnet5`). It is out of scope.
4. Run `cd website && python3 check_links.py --build` after the doc edits
   (CLAUDE.md rule).

## Verification

- Baseline at exploration time (all green): `tests/test_codeagent.sh` 199/199,
  `tests/test_codeagent_work_report.sh` 29/29, `tests/test_codeagent_discuss.sh`
  35/35. Re-run all three plus `tests/test_add_model.sh`,
  `tests/test_shadow_spawn_learner.sh`, `tests/test_resolve_detected_agent.sh`.
- `bash tests/run_all_python_tests.sh`: read only the last-line verdict.
- Behaviour:
  - `./.aitask-scripts/aitask_codeagent.sh resolve explain` gives
    `AGENT_STRING:claudecode/sonnet5_5` and `CLI_ID:claude-sonnet-5-5`.
  - `resolve shadow` and `resolve discuss` give `codex/gpt6_1_sol` and
    `gpt-6.1-sol`.
  - Every other op is unchanged versus `HEAD` (compare `.defaults` with `jq`).
- Self-detection: `aitask_resolve_detected_agent.sh` gives
  `claudecode/sonnet5_5_1m` for `--agent claudecode --cli-id
  'claude-sonnet-5-5[1m]'` (not an `unregistered_*` fallback) and
  `codex/gpt6_1_sol` for `--agent codex --cli-id gpt-6.1-sol`.
- Verify against the **committed** revisions (`git show <sha>:path`,
  `./ait git show <sha>:path`), not only the live files.

## Commit layout

Path-scoped commits only. Never use a bare `git commit` on the shared `main`.
- **Task-data branch:** `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register sonnet5_5/sonnet5_5_1m/gpt6_1_sol and promote to default (tNN)" aitasks/metadata/models_claudecode.json aitasks/metadata/models_codex.json aitasks/metadata/codeagent_config.json`
- **main:** `git commit -m "feature: ... (tNN)" -- seed/models_claudecode.json seed/models_codex.json seed/codeagent_config.json website/content/docs/commands/codeagent.md website/content/docs/tuis/codebrowser/how-to.md tests/test_codeagent.sh tests/lib/codeagent_defaults.sh`.
  The commit body must call out the **seed behaviour change**: freshly seeded
  projects now default the sonnet ops to `sonnet5_5` and shadow/discuss to
  `gpt6_1_sol`.

Check for concurrent sessions first: `git status --porcelain -- <main paths>`
and `./ait git status --porcelain -- <data paths>` must both be empty before
writing (see t1866's handoff barrier).

## Out of scope

- **OpenCode.** OpenCode models are provider-gated and CLI-discovered, and
  `aitask_add_model.sh` refuses `--agent opencode`. Use
  `ait opencode-models --sync-seed` (the `aitask-refresh-code-models` skill) as
  a separate task if OpenCode should pick up Sonnet 5.5 / GPT-6.1. Do not
  "reconcile" the catalogs (see t1866/t1867).
- **`gpt-6-astra`.** The Codex catalog also lists it ("Frontier intelligence for
  the most demanding work"), and it is not in `models_codex.json`. It was not
  requested; it is a candidate follow-up, not part of this task.
- Refreshing `aidocs/framework/model_reference_locations.md` is owned by t1341.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-04T14:13:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-04T16:35:52Z status=pass attempt=1 type=human

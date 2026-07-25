---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [backend]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-25 23:10
updated_at: 2026-07-25 23:11
---

Register **Opus 5** and **Sonnet 5** in the `claudecode` code-agent model
registry and promote **Opus 5** to the operational default wherever Opus 4.8
is currently the default. Scope is the `claudecode` agent only.

Use the existing **`aitask-add-model`** skill / `.aitask-scripts/aitask_add_model.sh`
helper (subcommands `add-json`, `promote-config`, `promote-default-agent-string`)
as the primary machinery — do not hand-edit the registry JSON. Preview every
change with `--dry-run` first.

## Model decisions (pinned)

- **Opus 5** — register a **single** entry `opus5` → cli_id `claude-opus-5`.
  Opus 5 ships with **1M input context by default**, so do **NOT** add a
  separate `opus5_1m` / `claude-opus-5[1m]` variant (unlike the opus4_7 /
  opus4_8 pattern, which had two entries). One entry only. Notes should mention
  the 1M-context-by-default behaviour.
- **Sonnet 5** — register `sonnet5` → cli_id `claude-sonnet-5`. There is no
  Sonnet 5 in the registry yet (current highest is `sonnet4_6`).

## Promotion (Opus 5 → default)

Promote `opus5` to default for every op currently defaulting to `opus4_8`.
As of exploration, in the **live** `codeagent_config.json` those ops are:
`pick`, `explore`, `learn`, `trail`, `brainstorm-explorer`,
`brainstorm-synthesizer`, `brainstorm-module_decomposer`,
`brainstorm-module_merger`, `brainstorm-module_syncer`. In **seed**
`codeagent_config.json`: `pick`, `explore`, `shadow`, `learn`, `trail`
(note `shadow` differs from live). **Re-derive the exact op set at
implementation time** by scanning both config files for `claudecode/opus4_8`
values — do not blindly trust this snapshot.

Also update `DEFAULT_AGENT_STRING` (currently `claudecode/opus4_8`) via
`promote-default-agent-string` — this patches
`.aitask-scripts/lib/agent_string.sh` and the resolution-chain note in
`.aitask-scripts/aitask_codeagent.sh`.

## Registry / seed sync

Registry files live in two places that must stay in sync: the task-data-branch
copy under `aitasks/metadata/models_claudecode.json` +
`codeagent_config.json`, and the `seed/` copies. The helper writes both;
verify both after apply. Commit registry/config on the task-data branch via
`./ait git`, and seed + source-code changes on `main` via plain `git`
(see the aitask-add-model skill's commit-grouping in Step 6).

## Manual-review surface (NOT patched by the helper)

Per `aidocs/framework/model_reference_locations.md`, these reference the model
string / default and must be reviewed & updated by hand:

- `aidocs/codeagents/claudecode_tools.md` — display name + cli_id
- `tests/test_codeagent.sh` — model-resolution assertions
- `tests/test_brainstorm_crew.py` — default agent_string fixtures
- `website/content/docs/commands/codeagent.md` — user-facing docs
- `aidocs/framework/model_reference_locations.md` — the audit doc itself is
  **stale** (still cites `opus4_7` / `opus4_7_1m` as the default). Refresh its
  line references and default-string values to match this change.

## Acceptance criteria

- `opus5` (single entry, `claude-opus-5`) and `sonnet5` (`claude-sonnet-5`)
  registered in both live and seed `models_claudecode.json`; **no** `opus5_1m`
  entry created.
- All ops that were on `claudecode/opus4_8` (re-derived at impl time) now
  default to `claudecode/opus5` in both live and seed `codeagent_config.json`.
- `DEFAULT_AGENT_STRING` = `claudecode/opus5` in `lib/agent_string.sh`, with
  the resolution-chain note in `aitask_codeagent.sh` updated to match.
- Manual-review files above reviewed and updated; audit doc refreshed.
- `bash tests/test_add_model.sh`, `bash tests/test_codeagent.sh`, and
  `bash tests/test_agent_string.sh` pass; `python tests/test_brainstorm_crew.py`
  passes.

## Out of scope

- `codex` and `opencode` agents (opencode is provider-gated / CLI-discovered).
- Porting to other code-agent trees is a no-op unless an agent-specific surface
  changes; suggest a separate follow-up only if needed.

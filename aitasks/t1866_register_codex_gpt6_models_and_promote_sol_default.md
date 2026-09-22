---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [codeagent, codexcli, docs]
gates: [risk_evaluated]
created_at: 2026-09-22 23:16
updated_at: 2026-09-22 23:16
---

## Goal

Register the two newly released Codex GPT-6 models — **Sol** and **Luna** — in
the codex model registry, and promote `codex/gpt6_sol` as the default agent
string everywhere `codex/gpt5_6_terra` is the current default.

| model | `name` | `cli_id` |
|---|---|---|
| GPT-6 Sol | `gpt6_sol` | `gpt-6-sol` |
| GPT-6 Luna | `gpt6_luna` | `gpt-6-luna` |

Terra is **not** removed — it stays registered and usable. Only its role as a
default is taken over by Sol.

## Exploration findings

The existing `gpt5_6_sol` / `gpt5_6_terra` / `gpt5_6_luna` entries are the
**5.6** generation. GPT-6 is a new generation, so these are new registry
entries, not edits to the existing ones.

### Where terra is the current default

`codex/gpt5_6_terra` appears as a default in exactly two operations, both in
`aitasks/metadata/codeagent_config.json` under `.defaults`:

- `shadow` — the advisory companion agent for a followed session
- `discuss` — advisory discussion of brainstorm proposals

No other operation defaults to terra, and there is no `DEFAULT_AGENT_STRING`
change to make: that fallback is `claudecode`-only
(`aidocs/framework/model_reference_locations.md:191` — codex promotion touches
`codeagent_config.json` + seed and nothing else).

### Seed config — decided scope

`seed/codeagent_config.json` currently has `shadow` and `discuss` set to
`claudecode/opus5`. **Per the requester's explicit instruction, these flip to
`codex/gpt6_sol` as well** — new projects bootstrapped by `ait setup` should get
GPT-6 Sol as their shadow/discuss default. `promote-config` already patches the
seed file automatically (it patches only keys that already exist, and both keys
exist there), so this needs no extra step — but it is a deliberate behaviour
change for freshly seeded projects and should be called out in the commit.

## Implementation

All writes go through the existing helper — do not hand-edit the JSON:
`.aitask-scripts/aitask_add_model.sh` (atomic tempfile + `jq` validation + `mv`,
with `--dry-run` producing unified diffs). The `/aitask-add-model` skill wraps
it and is the preferred entry point.

1. **Register both models** (updates `aitasks/metadata/models_codex.json` and
   `seed/models_codex.json` in one call each):

   ```bash
   ./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
     --agent codex --name gpt6_sol --cli-id gpt-6-sol \
     --notes "<one-line description of GPT-6 Sol>"
   ./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
     --agent codex --name gpt6_luna --cli-id gpt-6-luna \
     --notes "<one-line description of GPT-6 Luna>"
   ```

   Review the diffs, then re-run without `--dry-run`.

2. **Promote Sol** for the two terra ops (patches both the metadata config and
   the seed config):

   ```bash
   ./.aitask-scripts/aitask_add_model.sh promote-config --dry-run \
     --agent codex --name gpt6_sol --ops shadow,discuss
   ```

   Confirm the diff shows **four** changed values — `shadow` and `discuss` in
   `aitasks/metadata/codeagent_config.json` (from `codex/gpt5_6_terra`) and in
   `seed/codeagent_config.json` (from `claudecode/opus5`). Then apply.

3. **Do NOT run `promote-default-agent-string`** — it is `claudecode`-only and
   refuses `codex`.

4. **Update the user-facing docs table by hand** — the helper does not touch it:
   `website/content/docs/commands/codeagent.md:61-62` lists the `shadow` and
   `discuss` defaults as `codex/gpt5_6_terra`. Both rows become
   `codex/gpt6_sol`. Run `python3 check_links.py --build` from `website/` after
   the edit, per CLAUDE.md.

## Verification

- `./.aitask-scripts/aitask_codeagent.sh resolve shadow` and
  `... resolve discuss` both report `AGENT_STRING:codex/gpt6_sol` with
  `CLI_ID:gpt-6-sol`.
- `jq '.models[].name' aitasks/metadata/models_codex.json` lists `gpt6_sol` and
  `gpt6_luna`; the same holds for `seed/models_codex.json`.
- `jq '.defaults.shadow, .defaults.discuss' seed/codeagent_config.json` both
  print `codex/gpt6_sol`.
- `bash tests/run_all_python_tests.sh` — read only the last line for the
  verdict. The terra strings in `tests/test_agent_freeze.py` and
  `tests/test_agent_sessions_*.py` are **fixture data**, not default
  assertions; terra stays registered, so they are expected to keep passing. If
  any of them goes red, that is a real finding, not expected churn.
- `bash tests/test_add_model.sh`.

## Out of scope — OpenCode is t1867

OpenCode models are provider-gated and CLI-discovered, and
`aitask_add_model.sh` deliberately **refuses** `--agent opencode`. OpenCode
registration is **not** part of this task; it is now owned by **t1867**
(`refresh_opencode_model_registry_gpt6_astra_and_5_6_variants`), which runs the
full `ait opencode-models --sync-seed` discovery refresh.

Note the two tasks register **different** GPT-6 models, and that is correct:
Codex CLI and OpenCode expose different provider catalogs. This task registers
`gpt-6-sol` and `gpt-6-luna` for Codex; OpenCode offers **only**
`opencode/gpt-6-astra` and has no `gpt-6-sol` or `gpt-6-luna` at all. Do not
"reconcile" the two lists.

t1867 changes no operation defaults — `shadow` / `discuss` remain this task's
business. The two can land in either order.

## Commit layout

Two groups, per the `aitask-add-model` skill:

- **Task-data branch** (`aitask_task_commit.sh`, naming every path):
  `aitasks/metadata/models_codex.json`, `aitasks/metadata/codeagent_config.json`
- **main** (`git commit -- <paths>`, never a bare commit):
  `seed/models_codex.json`, `seed/codeagent_config.json`,
  `website/content/docs/commands/codeagent.md`

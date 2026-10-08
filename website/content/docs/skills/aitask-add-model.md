---
title: "/aitask-add-model"
linkTitle: "/aitask-add-model"
weight: 56
description: "Register a known code-agent model in models_<agent>.json and optionally promote it to default"
maturity: [stabilizing]
depth: [advanced]
---

Register a single, already-known code-agent model in the framework's model registry and optionally promote it to default across `codeagent_config.json`, the `seed/` template, and the hardcoded `DEFAULT_AGENT_STRING`. Companion to [`/aitask-refresh-code-models`](../aitask-refresh-code-models/).

**Usage:**
```
/aitask-add-model
/aitask-add-model --agent claudecode --name opus4_7_1m --cli-id 'claude-opus-4-7[1m]' --notes "1M context" --promote --promote-ops pick,explore,brainstorm-explorer
/aitask-add-model --dry-run ...
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## When to Use This Skill

Use `/aitask-add-model` when you already know the model you want to register — a vendor just announced it, or you've decided to promote a specific variant to default. Unlike [`/aitask-refresh-code-models`](../aitask-refresh-code-models/), this skill skips web research and writes deterministic, per-invocation changes.

| Concern | `/aitask-refresh-code-models` | `/aitask-add-model` |
|---------|------------------------------|---------------------|
| Discovery | Web research (WebSearch + WebFetch) | Known inputs from user or CLI flags |
| Scope | All agents, all models found upstream | One agent, one model per invocation |
| Writes | Model registry only | Model registry + optional promotion writes |
| Dry-run | No | Yes (`--dry-run`) |

## Two Modes

### Add mode (default)

Appends the model entry to `aitasks/metadata/models_<agent>.json` with empty `verified` / `verifiedstats`, syncs to `seed/models_<agent>.json`, and commits both files separately (metadata via `./ait git`, seed via plain `git`).

### Promote mode (`--promote`)

Everything add-mode does, plus:

- Updates `aitasks/metadata/codeagent_config.json` for the ops listed in `--promote-ops`
- Syncs to `seed/codeagent_config.json`
- For `claudecode` only: rewrites `DEFAULT_AGENT_STRING` in `.aitask-scripts/aitask_codeagent.sh`
- For `claudecode` + `pick`: updates `aidocs/codeagents/claudecode_tools.md` line 5
- Records that the model the promotion retires from the seed defaults is superseded by the new one, in `.aitask-scripts/lib/model_supersessions.json`, so `ait upgrade` offers the new model to projects still using the old one (see [Superseded model defaults]({{< relref "/docs/commands/codeagent#superseded-model-defaults" >}}))

### Supersession rules

A recorded supersession is global — every operation still using the old model is offered the new one — so the preview reports, per replaced model, what will be recorded:

- **Recorded** when the promotion moves every seed operation off the old model. A matching `_1m` variant pair is recorded alongside when both variants are registered.
- **Refused** when the old model stays the seed default of another operation (a partial promotion), when the old model already has a different successor, when the new edge would close a cycle, or when the new model is not registered. The skill then offers to add the remaining operations, to promote without recording a supersession (`--no-supersession`), or to abort. Nothing is written by a refused apply.
- `record-supersession` declares a lineage without a promotion: one a partial promotion could not record (once no seed default uses the old model), or the successor of a model that was never a default (for example `haiku4_5` → `haiku5_5`): `./.aitask-scripts/aitask_add_model.sh record-supersession --agent <agent> --old <old> --new <new>`.
- Existing entries are never overwritten, and a cross-agent replacement (for example a `claudecode` model replaced by a `codex` one) is not recorded.

## Supported Agents

| Agent | Add-mode | Promote-mode | Notes |
|-------|----------|--------------|-------|
| `claudecode` | yes | yes (full) | Owns `DEFAULT_AGENT_STRING` |
| `codex` | yes | yes (limited) | Promotion only touches config + seed |
| `opencode` | no | no | Use [`/aitask-refresh-code-models`](../aitask-refresh-code-models/) — OpenCode models are gated by provider availability |

## Manual-Review List

Promote-mode writes are intentionally limited to configuration and hardcoded defaults — the skill does NOT edit prose docs or test fixtures, since those require human curation. After every real promote, the skill emits a manual-review list pointing at files that still reference the old default:

- `tests/test_codeagent.sh` — default-sensitive assertions
- `tests/test_brainstorm_crew.py` — brainstorm agent defaults
- `website/content/docs/commands/codeagent.md` — defaults table + hardcoded-default line
- `aidocs/framework/model_reference_locations.md` — full audit with per-file tags

Run the suggested follow-up edits manually to complete the rollout.

## Key Behaviors

- **Idempotent** — Running `add-json` a second time with the same inputs fails with a clear "already exists" error. No silent no-op.
- **Atomic** — Every file write goes through tempfile + `mv`; failures leave the filesystem untouched.
- **Dry-run** — `--dry-run` prints `diff -u` per-file and exits without writing or committing.
- **Preserves verified history** — Existing `verified` and `verifiedstats` blocks for other models are never overwritten.

## Drift detection

Drift between `.claude/skills/` (source of truth) and the four wrapper trees that ship to other code agents is now caught automatically by [`/aitask-audit-wrappers`](../../development/skills/aitask-audit-wrappers/). After adding or modifying a skill in `.claude/skills/aitask-*/SKILL.md`, run that skill to keep all agent trees in sync.

## Related

- [`/aitask-refresh-code-models`](../aitask-refresh-code-models/) — Discover and refresh models via web research
- [`/aitask-audit-wrappers`](../../development/skills/aitask-audit-wrappers/) — Sibling framework-development skill that audits skill wrappers and helper-script whitelists
- [`ait codeagent`](../../commands/codeagent/) — Uses the model files and config files managed by this skill
- [Settings TUI](../../tuis/settings/) Models tab — Visual editor for model configurations

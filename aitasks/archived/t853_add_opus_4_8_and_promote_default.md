---
priority: high
effort: low
depends: [852]
issue_type: feature
status: Done
labels: [framework, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-29 09:31
updated_at: 2026-05-30 21:36
completed_at: 2026-05-30 21:36
---

## Goal

Register Claude **Opus 4.8** in the Claude Code model registry and promote it
to the framework default wherever Opus 4.7 (1M) is currently default.

Opus 4.8 has **1M context by default**, so add a **single** registry entry
`opus4_8` with cli_id `claude-opus-4-8` — no separate `[1m]` variant (unlike
the 4.7 pair `opus4_7` / `opus4_7_1m`).

## Depends on

t852 — the `promote-default-agent-string` helper must be fixed first, otherwise
the promote step dies on a stale anchor.

## Approach — use the `aitask-add-model` skill

Drive this through the dedicated skill (`/aitask-add-model`) / helper rather
than hand-editing JSON. Inputs:

- `--agent claudecode`
- `--name opus4_8`
- `--cli-id claude-opus-4-8`
- `--notes` one-line (e.g. "Most capable model, 1M context default, complex
  reasoning + agentic coding, adaptive thinking")
- `--promote`
- `--promote-ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer`

These are exactly the ops currently set to `claudecode/opus4_7_1m` in
`aitasks/metadata/codeagent_config.json`. (The other ops — explain,
batch-review, qa, raw, and the sonnet-backed brainstorm roles — stay on
sonnet4_6 and must NOT be changed.)

## Files the skill writes

- `aitasks/metadata/models_claudecode.json` + `seed/models_claudecode.json`
  (add-json)
- `aitasks/metadata/codeagent_config.json` + `seed/codeagent_config.json`
  (promote-config; seed only has the canonical 6 ops so brainstorm keys are
  silently skipped there — intended)
- `.aitask-scripts/lib/agent_string.sh` `DEFAULT_AGENT_STRING` →
  `claudecode/opus4_8` (promote-default-agent-string, after t852)

## Verification

- Always run the three `--dry-run` previews first and review diffs.
- `bash tests/test_add_model.sh`, `bash tests/test_agent_string.sh`,
  `bash tests/test_codeagent.sh` pass (test_codeagent may need fixture updates
  — those are handled in the follow-up docs/test task if out of scope here).
- After apply, `./.aitask-scripts/aitask_codeagent.sh` default resolution
  returns `claudecode/opus4_8`.
- Commit in the skill's two groups: registry+config via `./ait git`
  (task-data branch); seed + `lib/agent_string.sh` via plain `git` (main).

## Out of scope (see follow-up task)

The skill explicitly flags manual-review files it does NOT patch — docs and
test fixtures referencing the default model string. Those are handled in the
dependent documentation task.

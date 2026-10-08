---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, models, model_selection]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 16:44
updated_at: 2026-10-08 16:54
---

## Goal

Claude Haiku 5.5 is now available in Claude Code. Register it in the aitasks
model registry as `claudecode/haiku5_5` so it can be selected for operations
(settings TUI / agent picker, `--agent-string claudecode/haiku5_5`) and so a
Haiku 5.5 session self-detects to a real registry entry (attribution for
`implemented_with`, verified/usage stats) instead of an `unregistered_*`
fallback.

This is **add-only** — no operation in `aitasks/metadata/codeagent_config.json`
or `seed/codeagent_config.json` defaults to Haiku today, so there is no
promotion, no `DEFAULT_AGENT_STRING` change in `lib/agent_string.sh`, and no
default-sensitive test edits. Precedent: `sonnet5_5_1m` was registered
add-only in t1886 (95f0394cb).

## Precondition — confirm the exact CLI id (blocking)

The cli_id is **not yet confirmed**. Expected: `claude-haiku-5-5` (pattern of
`claude-opus-5-5` / `claude-sonnet-5-5`), but it could carry a date suffix
(like `claude-haiku-4-5-20251001`) or have a `[1m]` sibling.

- The locally installed Claude Code 2.1.288 binary contains
  `claude-opus-5-5` and `claude-sonnet-5-5` strings but **no**
  `claude-haiku-5*` string at exploration time (2026-10-08); npm latest is
  2.1.293. Upgrade Claude Code and/or check Anthropic's models docs.
- Self-detection (`aitask_resolve_detected_agent.sh --cli-id`, see
  `.claude/skills/task-workflow/model-self-detection.md`) matches the
  system-message model id **verbatim**, so a wrong cli_id silently
  mis-attributes every Haiku 5.5 run. Do not guess — verify, and ideally
  confirm by launching `claude --model <id>` once.
- If a 1M-context `[1m]` variant exists, register it as a separate entry
  `haiku5_5_1m` (same convention as `opus5_5_1m` / `sonnet5_5_1m`).

## Implementation

Use the existing add-model flow (skill `aitask-add-model`, helper
`.aitask-scripts/aitask_add_model.sh add-json`) — do not hand-edit JSON:

1. `add-json --agent claudecode --name haiku5_5 --cli-id <verified id>
   --notes "<short description, style of the sonnet5_5 notes>"` — appends to
   `aitasks/metadata/models_claudecode.json` with zero-history
   `verified`/`verifiedstats` and syncs `seed/models_claudecode.json`.
   Run with `--dry-run` first.
2. Keep `haiku4_5` registered (predecessors are never removed).
3. Commit per the skill's path-scoped commit strategy (metadata via
   `aitask_task_commit.sh`, seed via plain `git commit -- <path>`).

## Supersession entry (conditional on t1910)

t1910 (status Implementing; its changes were uncommitted in the shared
worktree at exploration time) introduces
`.aitask-scripts/lib/model_supersessions.json` and edits
`aitask_add_model.sh` and the `aitask-add-model` skill. A
`claudecode: haiku4_5 → haiku5_5` entry would let users who deliberately set
an operation to `haiku4_5` be offered the upgrade.

- If t1910 has landed when this task is picked: decide whether a
  non-default-model supersession belongs in that file (check t1910's
  semantics — it was designed around superseded *defaults*) and add it via
  whatever mechanism t1910 shipped.
- If t1910 has not landed: do **not** touch its uncommitted files; send a
  note to t1910 (`./ait note 1910 --from <this id> ...`) instead.

## OpenCode

OpenCode Claude entries (`opencode/claude-haiku-4-5` etc. in
`models_opencode.json`) are discovered via `aitask_opencode_models.sh` /
`aitask-refresh-code-models`, not added by `aitask-add-model` (it refuses
opencode). Run the opencode discovery once to see whether
`opencode/claude-haiku-5-5` is offered; if so let the discovery path register
it. Codex has no Claude models — out of scope.

## Coordination

- t1912 (Ready) moves `usagestats`/`verifiedstats` off `aitask-data` and
  touches `models_*.json` — check its state before committing to avoid a
  merge conflict on the same file.

## Verification

- `./.aitask-scripts/aitask_codeagent.sh list-models claudecode` lists
  `haiku5_5`.
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode
  --cli-id <id>` resolves to `claudecode/haiku5_5`.
- `jq . aitasks/metadata/models_claudecode.json seed/models_claudecode.json`
  succeeds; metadata and seed entries are identical.
- `bash tests/test_add_model.sh` and `bash tests/test_codeagent.sh` pass.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-08T13:55:04Z status=pass attempt=1 type=human

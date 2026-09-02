---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, claudecode, model_selection]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-02 09:17
updated_at: 2026-09-02 09:19
---

Register the new Claude model **Fable 5.1** for the `claudecode` code agent (register-only — do NOT promote to default).

Mirrors t966, which registered `fable5` the same way.

## Model identity
- name: `fable5_1`
- cli_id: `claude-fable-5-1`
- notes: one-line description (e.g. "Fable 5.1 — latest-generation Fable model")

Confirm the exact `cli_id` and a suitable `notes` string against current Claude model docs before writing. Registry naming convention: dots become underscores (`opus4_7_1m`, `fable5`), so Fable 5.1 → `fable5_1`.

If a 1M-context variant is announced, register it as a **separate** entry (`fable5_1_1m` / `claude-fable-5-1[1m]`) — the bracketed suffix is part of the `cli_id` and must never be stripped, per `aidocs/framework/model_reference_locations.md` §1.

## Scope (register-only)
Use the existing mechanism — the `aitask-add-model` skill / `.aitask-scripts/aitask_add_model.sh add-json` subcommand — which writes both copies atomically:
- `aitasks/metadata/models_claudecode.json`
- `seed/models_claudecode.json`

The new entry gets empty `verified: {}` / `verifiedstats: {}`, matching the other recently-added models (`opus4_7`, `opus4_8`, `fable5`, `opus5`, `sonnet5`).

Run `add-json --dry-run` first and review the unified diff before applying.

## Explicitly out of scope
Register-only touches §1 of `aidocs/framework/model_reference_locations.md` and nothing else. Do **not**:
- run `promote-config` (`aitasks/metadata/codeagent_config.json` / `seed/codeagent_config.json`)
- run `promote-default-agent-string` (`.aitask-scripts/lib/agent_string.sh:26` `DEFAULT_AGENT_STRING`, `.aitask-scripts/aitask_codeagent.sh:654` resolution-chain note)
- edit `aidocs/codeagents/claudecode_tools.md`, `website/content/docs/commands/codeagent.md`, or any default-sensitive test

No source change is needed for attribution: `.aitask-scripts/aitask_resolve_detected_agent.sh` matches `cli_id` directly out of `models_claudecode.json`, so `implemented_with` resolves to `claudecode/fable5_1` as soon as the entry lands.

## Verification
- `./.aitask-scripts/aitask_codeagent.sh list-models claudecode` shows `fable5_1`
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id claude-fable-5-1` prints `AGENT_STRING:claudecode/fable5_1` (not `AGENT_STRING_FALLBACK:`)
- `bash tests/test_add_model.sh` and `bash tests/test_install_merge.sh` still pass
- Both registry copies stay byte-identical in their `models` array

## Commit split
Per the `aitask-add-model` skill: `aitasks/metadata/models_claudecode.json` goes to the task-data branch via `./ait git`; `seed/models_claudecode.json` goes to `main` via plain `git`.

## Related (not folded — distinct scope)
- **t967** — `claudecode/fable5` sessions launched with `--model claude-fable-5` fall back to Opus 4.8 via the content-safety auto-switch. The same behaviour will likely apply to `fable5_1`; that investigation stays on t967.
- **t1150** — Fable's prose emitted in the same turn as an `AskUserQuestion` can be invisible; already mitigated by the skills' visibility rule.

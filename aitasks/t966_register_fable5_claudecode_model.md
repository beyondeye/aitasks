---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [config, codeagent]
created_at: 2026-06-10 16:53
updated_at: 2026-06-10 16:53
---

Register the new Claude model **Fable 5** for the `claudecode` code agent (register-only — do NOT promote to default).

## Model identity
- name: `fable5`
- cli_id: `claude-fable-5`
- notes: e.g. "Fable 5 — latest-generation Claude model"

(Confirm the exact cli_id and a suitable one-line `notes` description against current Claude model docs before writing.)

## Scope (register-only)
Use the existing mechanism — the `aitask-add-model` skill / `.aitask-scripts/aitask_add_model.sh add-json` subcommand — to append the entry to:
- `aitasks/metadata/models_claudecode.json`
- `seed/models_claudecode.json` (kept in sync by the helper)

The new entry gets empty `verified: {}` / `verifiedstats: {}`, matching the other recently-added models.

## Explicitly out of scope (NOT this task)
No default/config/doc/test changes — i.e. do NOT touch:
- `aitasks/metadata/codeagent_config.json` / `seed/codeagent_config.json`
- `.aitask-scripts/lib/agent_string.sh` (`DEFAULT_AGENT_STRING`)
- `.aitask-scripts/aitask_codeagent.sh` resolution-chain note
- `aidocs/codeagents/claudecode_tools.md`
- `tests/test_codeagent.sh`, `tests/test_brainstorm_crew.py`, `website/content/docs/commands/codeagent.md`

(Those are promote-mode touchpoints; a separate follow-up task can promote Fable 5 to default if/when desired.)

## Verification
- `claudecode/fable5` parses and resolves: `get_cli_model_id claudecode fable5` → `claude-fable-5` (via `.aitask-scripts/lib/agent_string.sh`).
- Both JSON files remain valid JSON and stay in sync.
- An agent string like `claudecode/fable5` is accepted by `aitask_codeagent.sh` (invokes `claude --model claude-fable-5`).
- Run `bash tests/test_codeagent.sh` and any model-registry tests to confirm no default-sensitive assertions broke (they shouldn't, since defaults are untouched).

## Notes
- `aitask-refresh-code-models` (web auto-discovery) could also register Fable 5, but this task does it manually/deterministically via `aitask-add-model`.
- Per CLAUDE.md: do the change for the Claude Code agent first; suggest follow-up tasks to register Fable 5 for the Codex/OpenCode agents (`models_codex.json` / `models_opencode.json`) if applicable.

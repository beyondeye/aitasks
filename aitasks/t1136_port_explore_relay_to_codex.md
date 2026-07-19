---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codeagent, codexcli]
gates: [risk_evaluated]
anchor: 1120
created_at: 2026-07-07 00:20
updated_at: 2026-07-07 00:20
boardidx: 170
---

## Context

t1120_4 added the chat-native explore operation for Claude Code only:
`ait codeagent invoke explore-relay --headless` dispatches
`claude --print /aitask-explorechat` with `--allowedTools` and engine-owned
`BASH_*_TIMEOUT_MS` exports. The codex branch currently refuses with
"explore-relay is not yet supported for codex (Claude Code only; port
tracked as a follow-up task)" in
`.aitask-scripts/aitask_codeagent.sh` (`build_invoke_command`).

Port the operation to Codex CLI, per the CLAUDE.md skill-porting rule.

## Scope

- Skill surface: adapt `.claude/skills/aitask-explorechat/SKILL.md` into the
  Codex tree (`.agents/skills/` shared root — see
  `aidocs/framework/skill_authoring_conventions.md`). The skill is static
  (no `.j2`, no profile variants).
- Dispatch: replace the codex refusal in `aitask_codeagent.sh` with a real
  headless argv (codex equivalent of print mode + tool allowlisting + the
  tool-timeout budget). Preserve the env preconditions
  (`CHATLINK_RELAY_DIR`, `CHATLINK_BUG_REPORT_FILE`) and the headless-only
  refusal semantics.
- Verify the codex Bash-tool timeout story: the relay helper blocks up to
  540 s per question; the claudecode dispatch solves this with
  `BASH_DEFAULT_TIMEOUT_MS`/`BASH_MAX_TIMEOUT_MS=630000`. Codex needs an
  equivalent (or a documented reduced `--timeout` budget).
- Tests: extend `tests/test_codeagent_explore_relay.sh` — the codex case
  moves from "refuses" to exact-argv dry-run asserts; keep a live smoke leg
  (env-gated) mirroring the claudecode one.

## References

- Archived plan: `aiplans/archived/p1120/p1120_4_chat_native_explore.md`
  (esp. Final Implementation Notes — env contract, timeout proof, argv
  ordering gotcha).
- Protocol: `aidocs/chat/qa_relay_protocol.md` (§Task payload).

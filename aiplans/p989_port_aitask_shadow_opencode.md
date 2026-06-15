---
Task: t989_port_aitask_shadow_opencode.md
Worktree: (none - current branch, profile 'fast')
Branch: main
plan_verified:
  - codex/gpt-5 @ 2026-06-15
---

# Plan: t989 - Port `/aitask-shadow` to OpenCode

## Summary

Add the missing OpenCode surfaces for the existing Claude `/aitask-shadow`
command. Keep `.claude/skills/aitask-shadow/SKILL.md` as the source of truth and
add only thin OpenCode wrappers, so the command is discoverable/invocable in
OpenCode without duplicating the dispatcher or its sub-procedure files.

## Implementation

1. Create `.opencode/commands/aitask-shadow.md` using the canonical OpenCode
   command wrapper shape:
   - frontmatter description copied from the Claude source skill
   - include `.opencode/skills/opencode_tool_mapping.md`
   - forward `$ARGUMENTS`
   - read/follow `.claude/skills/aitask-shadow/SKILL.md`
2. Create `.opencode/skills/aitask-shadow/SKILL.md` as the OpenCode skill
   wrapper:
   - `name: aitask-shadow`
   - source-of-truth pointer to the Claude skill
   - OpenCode adaptation pointer to `.opencode/skills/opencode_tool_mapping.md`
   - argument contract `/aitask-shadow <followed_pane_id> [<source_task_id>]`
3. Generate the wrappers with `aitask_audit_wrappers.sh apply-wrapper` so they
   match the repository's wrapper templates.

## Verification

- Run `./.aitask-scripts/aitask_skill_verify.sh`.
- Run `./.aitask-scripts/aitask_audit_wrappers.sh discover` and confirm there is
  no remaining `GAP:opencode-skill:aitask-shadow` or
  `GAP:opencode-command:aitask-shadow`.
- Confirm OpenCode helper permissions are already present for
  `aitask_shadow_capture.sh`, `aitask_shadow_context.sh`, and
  `aitask_explain_context.sh`.
- If OpenCode can run in the local environment, perform a harmless invocation
  check; otherwise record the local limitation and rely on static wrapper
  verification.

## Assumptions

- `t986_4` remains the source of truth for the shadow skill.
- `t988` is a parallel Codex port and is not required for this OpenCode port.
- Launcher code, Claude skill behavior, helper scripts, and OpenCode permissions
  stay unchanged unless verification exposes drift.

## Risk

### Code-health risk: low

- Adds two thin generated wrappers and does not fork the Claude source skill or
  alter helper scripts, launcher code, permissions, or shared workflow logic.

### Goal-achievement risk: low

- OpenCode discoverability is covered by the canonical command wrapper path, and
  helper/script resolution is covered by existing whitelist and skill verification
  checks.

### Planned mitigations

- None.

## Final Implementation Notes

- Created `.opencode/commands/aitask-shadow.md` with the canonical OpenCode
  command wrapper body.
- Created `.opencode/skills/aitask-shadow/SKILL.md` with the canonical OpenCode
  skill wrapper body.
- Verified `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Verified `aitask_audit_wrappers.sh discover` no longer reports
  `aitask-shadow` gaps.
- Verified helper whitelist audits for `aitask_shadow_capture.sh`,
  `aitask_shadow_context.sh`, and `aitask_explain_context.sh` emit no missing
  entries.
- Verified `opencode --help` and `opencode run --help` outside the sandbox; the
  installed CLI exposes top-level `--prompt` and `run --command` invocation
  surfaces.

---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [claudeskills, codexcli, opencode]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-07-01 10:36
updated_at: 2026-07-01 11:22
---

## Context

`aitask-learn-skill` generates a static Claude Code skill from gathered content
(a file, URL, repo path, or captured tmux pane). The shared generation core is
`.claude/skills/aitask-learn-skill/generate.md`.

Two gaps were found while reviewing that skill:

### 1. No cross-agent wrapper generation

`generate.md` only ever writes `.claude/skills/<name>/SKILL.md`. It does NOT
offer to create the corresponding wrapper surfaces for the other supported code
agents:
- Codex CLI: `.agents/skills/<name>/SKILL.md`
- OpenCode: `.opencode/skills/<name>/SKILL.md` and `.opencode/commands/<name>.md`

For a plain (non-`.j2`) skill these wrappers are just the standard thin
(~10–20 line) delegating stubs that point at the canonical Claude file (the
OpenCode command `@`-includes it) — see
`aidocs/framework/skill_authoring_conventions.md`. Because a learned skill is
always a plain static skill, there is nothing to keep in sync afterward: a
Claude-side edit propagates transitively through the stubs. So generating them
up front is cheap and safe.

The framework's own `aitask-*` wrappers are maintained by
`aitask_audit_wrappers.sh`, but that script is scoped to `aitask-*` skills only
and is not invoked by the learn flow — evaluate whether its stub-emitting logic
can be reused for user-generated skills, or whether a small dedicated helper is
cleaner. Prefer reusing the canonical stub shape over reinventing it.

### 2. `git add` / commit is unconditional

`generate.md` step 7 unconditionally runs:
```bash
git add .claude/skills/<name>/
git commit -m "feature: Add /<name> skill learned from <source_label>"
```
There is no prompt or opt-out. Staging and committing should be the user's
choice — some users will want to review the generated skill before committing,
or stage it themselves.

## Acceptance Criteria

- **Optional cross-agent wrappers:** After generating the Claude Code SKILL.md,
  `aitask-learn-skill` asks the user (AskUserQuestion) whether to also emit the
  Codex CLI and OpenCode wrapper stubs for the new skill. On yes, generate the
  correct thin delegating stubs (`.agents/skills/<name>/SKILL.md`,
  `.opencode/skills/<name>/SKILL.md`, `.opencode/commands/<name>.md`) matching
  the conventions in `aidocs/framework/skill_authoring_conventions.md`. Reuse
  the existing canonical stub shape / `aitask_audit_wrappers.sh` logic where
  practical rather than a parallel reimplementation.
- **Optional commit:** The `git add` / commit in step 7 becomes optional —
  ask the user whether to stage+commit, stage only, or leave everything
  uncommitted for them to handle. Default should not silently commit.
- Any generated wrappers are included in (or excluded from) the staging/commit
  decision consistently with the SKILL.md.
- Because the shadow spawn-learner reuses this whole skill (`/aitask-learn-skill
  <pane_id>`), confirm the new prompts behave sensibly (or are skippable) in
  that spawned/advisory path; do not break the non-interactive expectations of
  that entry point.
- Update `generate.md`'s header comment / Output line ("...committed...") to
  reflect that committing is now optional.

## Notes / open questions

- Decide whether the wrapper-generation prompt and the commit prompt are one
  combined question or two. Two of the AskUserQuestion prompts already exist in
  the flow; keep prompt count minimal.
- The wrappers must use whatever the current canonical stub template is — read
  it at implementation time, do not hardcode from this description.
- Cross-check the CLAUDE.md convention that skill changes are done in the Claude
  version first; here the generated wrappers ARE the port, so no separate
  port-aitask is needed for the generated skill itself. (The edits to
  `aitask-learn-skill` itself, however, may need porting to the Codex/OpenCode
  copies of that skill — evaluate.)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T08:30:19Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-01T08:30:20Z status=pass attempt=1 type=human

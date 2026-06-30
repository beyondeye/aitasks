---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1071_2]
issue_type: chore
status: Implementing
labels: [shadow, claudeskills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-06-30 11:16
updated_at: 2026-06-30 16:51
---

Port the `aitask-learn-skill` skill (Claude version landed in t1071_2) to the other
supported code-agent trees, per CLAUDE.md ("done in the Claude Code version first …
suggest separate aitasks to update the corresponding skills/commands in the other
supported coding agents").

## Source of truth
- `.claude/skills/aitask-learn-skill/SKILL.md` and
  `.claude/skills/aitask-learn-skill/generate.md` (static, user-invocable; source
  resolution for tmux pane id / file / URL / repo, + shared generate core).

## Port targets (SKILL.md wrappers only — `generate.md` NOT copied)
- **Codex:** `.agents/skills/aitask-learn-skill/SKILL.md`.
- **OpenCode:** `.opencode/skills/aitask-learn-skill/SKILL.md` and the command stub
  `.opencode/commands/aitask-learn-skill.md` (note: `.opencode/commands/` is PLURAL —
  confirmed on disk).

## AC correction — do NOT copy `generate.md` (explicit deviation)
The original AC said to also copy `generate.md` into each tree. That is the wrong
shape for a wrapper port and was corrected before implementation:
- Hand-authored wrapper skills are **SKILL.md-only** in the Codex/OpenCode trees
  (confirmed on disk: `aitask-reviewguide-import` has no sub-procedure copies;
  `aitask-shadow`'s five `plan-*.md` sub-procedures live only in the Claude tree).
  The sub-procedure `.md` files that *do* appear under `.agents/skills/` /
  `.opencode/skills/` belong solely to `.j2`-**rendered** skills (auto-generated),
  not hand-authored static wrappers.
- The wrapper redirect already covers `generate.md`: the Codex/OpenCode agent
  follows the Claude `SKILL.md`, whose Step 3 reads `generate.md` (same-dir relative
  reference → `.claude/skills/aitask-learn-skill/generate.md`). Copying it into the
  other trees would create a divergent duplicate that drifts from the source.

## Notes
- Model the port shape on the existing `aitask-reviewguide-import` copies in both trees.
- The skill shells out to shared framework helpers (`aitask_shadow_capture.sh`,
  `lib/repo_fetch.sh`) that exist in all trees — no per-agent helper rewrite needed.
- Static skill: plain SKILL.md, no `.j2`/goldens/stub machinery.

## Verification
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- The Codex and OpenCode wrappers redirect to the Claude source's `SKILL.md` and the
  correct tool-mapping file; OpenCode command stub present under `.opencode/commands/`.
- No `generate.md` copied into `.agents/skills/` or `.opencode/skills/` (by design).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T13:51:21Z status=pass attempt=1 type=human

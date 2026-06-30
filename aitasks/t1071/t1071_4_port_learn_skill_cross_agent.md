---
priority: medium
effort: medium
depends: [t1071_2]
issue_type: chore
status: Ready
labels: [shadow, claudeskills]
anchor: 1071
created_at: 2026-06-30 11:16
updated_at: 2026-06-30 11:16
---

Port the `aitask-learn-skill` skill (Claude version landed in t1071_2) to the other
supported code-agent trees, per CLAUDE.md ("done in the Claude Code version first …
suggest separate aitasks to update the corresponding skills/commands in the other
supported coding agents").

## Source of truth
- `.claude/skills/aitask-learn-skill/SKILL.md` and
  `.claude/skills/aitask-learn-skill/generate.md` (static, user-invocable; source
  resolution for tmux pane id / file / URL / repo, + shared generate core).

## Port targets
- **Codex:** `.agents/skills/aitask-learn-skill/SKILL.md` (+ `generate.md`).
- **OpenCode:** `.opencode/skills/aitask-learn-skill/SKILL.md` (+ `generate.md`) and
  the command stub `.opencode/commands/aitask-learn-skill.md` (note: `.opencode/commands/`
  is PLURAL — confirmed on disk).

## Notes
- Model the port shape on the existing `aitask-reviewguide-import` copies in both trees.
- The skill shells out to shared framework helpers (`aitask_shadow_capture.sh`,
  `lib/repo_fetch.sh`) that exist in all trees — no per-agent helper rewrite needed.
- Static skill: plain SKILL.md, no `.j2`/goldens/stub machinery.

## Verification
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- The Codex and OpenCode copies match the Claude source's flow; OpenCode command stub
  present under `.opencode/commands/`.

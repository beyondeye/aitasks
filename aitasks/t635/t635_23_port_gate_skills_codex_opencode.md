---
priority: low
effort: low
depends: [t635_22, 635_11]
issue_type: chore
status: Ready
labels: [gates, claudeskills]
created_at: 2026-06-16 19:06
updated_at: 2026-06-16 19:06
---

## Context

t635_11 shipped two NEW **plain Claude skills** (no profile-aware `.md.j2`, since
they have zero profile-varying behavior):

- `.claude/skills/aitask-run-gates/SKILL.md` — conversational front of the gate
  orchestrator (`aitask_run_gates.sh` / `ait gates run`).
- `.claude/skills/aitask-gate-template/SKILL.md` — verifier authoring scaffold
  (contract + copy-me script).

Because they are plain skills (not Jinja closures), they do NOT auto-render to the
other agents — they need manual ports per the CLAUDE.md cross-agent guidance.

## Scope

Port both skills to:
- **Codex CLI:** `.agents/skills/aitask-run-gates/SKILL.md` and
  `.agents/skills/aitask-gate-template/SKILL.md` (mirror `.agents/skills/aitask-shadow/`).
- **OpenCode:** `.opencode/commands/aitask-run-gates.md` +
  `.opencode/skills/...` and the same for aitask-gate-template (mirror the
  existing aitask-shadow opencode surfaces).

Adapt agent-specific tool/command wording as needed. Verify with
`./.aitask-scripts/aitask_skill_verify.sh` and any cross-agent parity checks.

## Reference

Claude source of truth: `.claude/skills/aitask-run-gates/SKILL.md`,
`.claude/skills/aitask-gate-template/SKILL.md`. Pattern exemplar (a plain skill
with all 3 agent surfaces): `aitask-shadow`.

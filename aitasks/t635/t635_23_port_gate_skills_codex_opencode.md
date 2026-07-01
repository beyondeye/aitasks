---
priority: low
effort: low
depends: [t635_22, 635_11, t635_19]
issue_type: chore
status: Ready
labels: [gates, claudeskills]
created_at: 2026-06-16 19:06
updated_at: 2026-07-01 07:20
---

## Context

t635_11 (and t635_19) shipped NEW **plain Claude skills** (no profile-aware
`.md.j2`, since they have zero profile-varying behavior):

- `.claude/skills/aitask-run-gates/SKILL.md` — conversational front of the gate
  orchestrator (`aitask_run_gates.sh` / `ait gates run`).
- `.claude/skills/aitask-gate-template/SKILL.md` — verifier authoring scaffold
  (contract + copy-me script; t635_19 added the **procedure/agent verifier** variant).
- `.claude/skills/aitask-gate-docs-updated/SKILL.md` — **first concrete
  procedure-backed gate skill** (t635_19). Until it is ported, the `docs_updated`
  procedure gate is **Claude-only** (the task-workflow dispatch resolves the gate
  skill in the running agent's tree).

Because they are plain skills (not Jinja closures), they do NOT auto-render to the
other agents — they need manual ports per the CLAUDE.md cross-agent guidance.

## Scope

Port all three skills to:
- **Codex CLI:** `.agents/skills/aitask-run-gates/SKILL.md`,
  `.agents/skills/aitask-gate-template/SKILL.md`,
  `.agents/skills/aitask-gate-docs-updated/SKILL.md` (mirror `.agents/skills/aitask-shadow/`).
- **OpenCode:** `.opencode/commands/aitask-run-gates.md` + `.opencode/skills/...`
  and the same for `aitask-gate-template` and `aitask-gate-docs-updated` (mirror the
  existing aitask-shadow opencode surfaces).

Adapt agent-specific tool/command wording as needed. Verify with
`./.aitask-scripts/aitask_skill_verify.sh` and any cross-agent parity checks.

**Out of scope (belongs to the procedure_gate_generalization follow-up, NOT here):**
making the task-workflow Step-8/Step-9 dispatch *resolution* formally agent-aware,
and per-gate code-agent/model selection + its settings-TUI surface. This task only
ports the skill FILES so the wrappers exist in each agent tree; once they do,
`docs_updated` stops being Claude-only.

## Reference

Claude source of truth: `.claude/skills/aitask-run-gates/SKILL.md`,
`.claude/skills/aitask-gate-template/SKILL.md`,
`.claude/skills/aitask-gate-docs-updated/SKILL.md`. Pattern exemplar (a plain skill
with all 3 agent surfaces): `aitask-shadow`.

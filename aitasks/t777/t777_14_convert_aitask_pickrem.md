---
priority: medium
effort: high
depends: [t777_13]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:01
updated_at: 2026-05-17 12:01
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-pickrem` (remote/non-interactive Claude Web variant) SKILL.md to templated pattern across all 4 agents.

**Largest per-skill conversion** because pickrem heavily consumes remote-only profile keys: `force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status` (see `aitasks/metadata/profiles/remote.yaml`).

## Key Files to Modify

- `.claude/skills/aitask-pickrem/SKILL.md.j2` (new) — template (largest)
- `.claude/skills/aitask-pickrem/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-pickrem/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-pickrem.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-pickrem.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: per t777_3 design, Gemini/OpenCode stubs live in the command-wrapper files, NOT in `<agent_root>/skills/aitask-pickrem/SKILL.md`. Rendered variants land at `.gemini/skills/aitask-pickrem-<profile>-/SKILL.md` and `.opencode/skills/aitask-pickrem-<profile>-/SKILL.md` (trailing-hyphen convention, gitignored) and are reached via the stub's Read-and-follow instruction.

## Implementation Plan

1. Grep SKILL.md for "Profile check:" blocks AND each of the remote-only key names listed above.
2. Convert each branch to `{% if profile.<key> %}…{% else %}…{% endif %}`. For multi-value enums (e.g. `done_task_action: archive|skip|ask`), use the `{% if … == "X" %}…{% elif … == "Y" %}…{% endif %}` pattern.
3. Agent-specific branches as needed (likely fewer interactive prompts since this is the headless variant).
4. Wrap literal `{{`/`{%` in `{% raw %}`.
5. Frontmatter `name: aitask-pickrem-{{ profile.name }}`.
6. Author 4 stubs.

## Verification Steps

1. `ait skill verify` passes.
2. `ait skill render pickrem --profile remote --agent claude` produces expected output with all decisions pre-resolved from remote.yaml.
3. Confirm NO `AskUserQuestion` instructions remain in the rendered output for `remote` profile (the whole point of remote mode is non-interactive).
4. Stub-dispatch end-to-end on all 4 agents.

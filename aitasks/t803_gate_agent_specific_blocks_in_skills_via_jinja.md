---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-19 16:41
updated_at: 2026-05-19 16:41
boardidx: 30
---

## Problem

When `aitask-wrap` runs under Codex CLI (and Gemini / OpenCode), Step 1b
"Check for Recent Claude Plans" executes `ls -t ~/.claude/plans/*.md` —
a Claude-Code-only directory. The `.agents/skills/aitask-wrap/SKILL.md`
and `.opencode/skills/aitask-wrap/SKILL.md` wrappers both delegate to
`.claude/skills/aitask-wrap/SKILL.md` as their source of truth, so every
non-Claude agent currently runs this Claude-only step. The scan returns
nothing useful and only adds latency / confusion.

The user's secondary observation ("why check for plans when wrap covers
changes generated outside an existing task?") is by design: a Claude
user can `EnterPlanMode` outside the aitasks framework (plan saved to
`~/.claude/plans/`), implement the plan, then later `aitask-wrap` —
Step 1b lets that stray plan inform the intent analysis. The behavior
is correct **for Claude Code only**.

## Goal

Once **t777** templated-skill infrastructure is in place, agent-specific
blocks should be gated at render time via `{% if agent == "claude" %}`
rather than executed unconditionally at runtime. The engine already
exposes the `agent` variable to jinja templates (see
`.aitask-scripts/lib/skill_template.py:71` — `env.render_str(...,
agent=agent_name)`), so this is purely an authoring change.

## Scope

### Part A — Convert aitask-wrap to the templated stub-skill pattern

`aitask-wrap` is **not** in the current t777 child set
(t777_9..t777_15 cover review / fold / qa / pr-import / revert /
pickrem / pickweb only). This task fills that gap. Follow the same
procedure used by t777_6 (pilot) / t777_8 (explore conversion):

- Author `.claude/skills/aitask-wrap/SKILL.md.j2`.
- Create per-profile rendered siblings (`aitask-wrap-default-`,
  `aitask-wrap-fast-`, `aitask-wrap-remote-` as applicable).
- Replace the hand-written delegation wrappers in `.agents/skills/`
  and `.opencode/skills/` with the rendered outputs.
- Wrap Step 1b ("Check for Recent Claude Plans", lines ~84–119 in
  the current `.claude/skills/aitask-wrap/SKILL.md`) in
  `{% if agent == "claude" %}` so non-Claude renders omit it entirely.
- Verify with `./.aitask-scripts/aitask_skill_verify.sh`.

### Part B — Audit other shared skills for runtime "If running in Claude Code" guards

Search results from `grep -rn "If running in Claude Code\|~/.claude/plans" .claude/skills/` show at least these surfaces:

- `task-workflow/planning.md` line ~292 — plan-externalization is
  guarded by "**If running in Claude Code,** execute the Plan
  Externalization Procedure ...". Other code agents skip the step at
  runtime by reading the prose guard.
- `task-workflow/plan-externalization.md` — entire procedure is
  Claude-Code-only (`~/.claude/plans/<random>.md` semantics).
- Variants under `task-workflow-fast-/`, `task-workflow-default-/`
  carry the same prose.

Once their host skills are templated, these runtime guards should
migrate to jinja conditionals so non-Claude renders simply do not
contain the block. Until those skills are converted, leave the runtime
guard in place.

The deliverable for Part B is an **audit document** (or follow-up
sibling tasks) cataloging:
- Every occurrence of "If running in Claude Code" or other
  agent-name-mention runtime guards across `.claude/skills/`.
- Whether the host skill is already templated (`.j2` exists) or still
  hand-written.
- For templated ones: a jinja-gating PR/task. For not-yet-templated
  ones: a note to be addressed when that skill is converted.

## Dependencies

- Hard dependency on t777 templated-skill infra: t777_1 (renderer +
  paths), t777_2 (`aitask_skill_render.sh`), t777_3 (stub-skill
  design), t777_22 (recursive walker), t777_26 (template completeness).
- Should run after the in-flight t777 sibling conversions
  (t777_9..t777_15) to follow the established pattern; can be done
  before t777_18 (docs update) so docs reflect the final state.

## Out of scope

- Removing the `~/.claude/plans/` scan logic itself — it remains useful
  for Claude Code users. The fix is gating, not removal.
- Refactoring `~/.claude/plans/` scanning into a script encapsulation
  (separate concern; could be a follow-up if encapsulation per
  `feedback_archive_encapsulation` is desired).

## Acceptance

- A Codex/Gemini/OpenCode user running `aitask-wrap` sees no
  references to `~/.claude/plans/`, no "Check for Recent Claude
  Plans" step, no Claude-Code-specific prose in the rendered SKILL.md.
- The Claude Code render of `aitask-wrap` retains Step 1b unchanged
  in behavior.
- `aitask_skill_verify.sh` passes for all four agent renders.
- Audit document committed (or follow-up tasks created) covering
  remaining runtime "If running in Claude Code" guards in the
  skill tree.

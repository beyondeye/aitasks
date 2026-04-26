---
priority: high
effort: medium
depends: [t650_2]
issue_type: bug
status: Postponed
labels: [agentcrew, ait_brainstorm]
created_at: 2026-04-26 14:18
updated_at: 2026-04-26 14:19
---

## Context

Bug 2 of parent t650 — **fallback** for the heartbeat fix. **Pick this child only if t650_2's verification step 2 or 3 fails** (i.e., agents still don't emit periodic heartbeats after the procedure-reference rewrite). If t650_2 succeeds end-to-end, mark this child Done with a "not needed" note in the plan and archive it without code changes.

This child applies a more aggressive rewrite: replace the procedure references in the 6 brainstorm templates with **literal `ait crew status …` shell command lines**, using the `${CREW_ID}` / `${AGENT_NAME}` context-variable pattern (mirroring how `task-workflow` declares context variables once and references them via placeholders throughout). Eliminates the implicit `_instructions.md` lookup entirely.

**Initial status: Postponed.** The implementer should change status to Implementing only after confirming t650_2 did not fix the issue.

## Key Files to Modify

- **NEW:** `.aitask-scripts/brainstorm/templates/_context_variables.md` — shared include declaring `${CREW_ID}` / `${AGENT_NAME}` and where to find their literal values.
- All 6 templates under `.aitask-scripts/brainstorm/templates/`:
  - `initializer.md`, `explorer.md`, `comparator.md`, `detailer.md`, `patcher.md`, `synthesizer.md`

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/templates/_section_format.md` — example of a shared include consumed via `<!-- include: _section_format.md -->`. The new `_context_variables.md` should follow the same pattern.
- `.aitask-scripts/lib/agentcrew_utils.sh` `resolve_template_includes()` (line 145) — the inline mechanism, already invoked in `aitask_crew_addwork.sh` line 162. **No code change to addwork is needed** — this is purely a template change.
- `.claude/skills/task-workflow/SKILL.md` "Context Requirements" table — the declare-once-reference-everywhere pattern this child mirrors.
- `aitask_crew_addwork.sh` lines 207–252 — the `_instructions.md` writer that bash-interpolates literal `${CREW_ID}` / `${AGENT_NAME}` values per agent. The agent reads those literal values from `_instructions.md` and substitutes them into the `${CREW_ID}` / `${AGENT_NAME}` placeholders in the work2do.

## Implementation Plan

1. **Create the shared include** `.aitask-scripts/brainstorm/templates/_context_variables.md`:
   ```markdown
   ### Context Variables

   Throughout this template the following placeholders refer to your concrete
   crew identifier and agent name:

   - `${CREW_ID}` — your crew identifier (e.g. `brainstorm-635`)
   - `${AGENT_NAME}` — your agent name (e.g. `initializer_bootstrap`)

   The literal values are written into your `_instructions.md` file. Read it
   first, then substitute the values every time you run a command in the
   "Checkpoint" / "Completion" blocks below.
   ```

2. **Add the include directive** to each of the 6 templates, just below the level-1 `# Task: <name>` heading and above the existing `## Input` section:
   ```markdown
   <!-- include: _context_variables.md -->
   ```

3. **Replace the procedure-reference lines** (from t650_2) with explicit literal shell commands. For every Checkpoint:
   ```
   ### Checkpoint 1
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat --message "Phase 1 complete — imported proposal loaded"`
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --progress 20`
   - Run: `ait crew command list --crew ${CREW_ID} --agent ${AGENT_NAME}`
   ```
   For Completion:
   ```
   ## Completion
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --status Completed`
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --progress 100`
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat --message "Initialization complete"`
   ```

## Verification Steps

1. **Include-resolution check:** after the changes, run `ait crew addwork` to write a test agent and inspect `<crew_worktree>/<agent>_work2do.md`. Confirm:
   - The Context Variables block appears as inlined content (not the literal `<!-- include: _context_variables.md -->` directive).
   - Each Checkpoint contains explicit `ait crew status …` lines with `${CREW_ID}` and `${AGENT_NAME}` literals (intentionally not substituted — the agent binds them by reading `_instructions.md`).

2. **Manual end-to-end (same as t650_2):** re-run brainstorm bootstrap on a small proposal, watch `<crew_worktree>/initializer_bootstrap_alive.yaml`, confirm `last_heartbeat` advances at every Checkpoint (4 + 1 = 5 advances) and the agent is not marked DEAD by `agentcrew_runner.py`.

3. If t650_2 already succeeded and this child was picked by mistake, archive without code changes (set status Done, plan-note "not needed — t650_2 sufficient").

## Out of scope (intentionally)

- No changes to `aitask_crew_addwork.sh` (no template substitution engine — the existing `resolve_template_includes` machinery handles include inlining; the `${CREW_ID}` / `${AGENT_NAME}` placeholders are intentionally bound at the agent's read time, not at template-write time).
- No change to `heartbeat_timeout_minutes` default.

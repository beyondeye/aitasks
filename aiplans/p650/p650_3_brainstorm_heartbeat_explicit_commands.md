---
Task: t650_3_brainstorm_heartbeat_explicit_commands.md
Parent Task: aitasks/t650_brainstorm_bugs.md
Sibling Tasks: aitasks/t650/t650_1_ait_crew_whitelist.md, aitasks/t650/t650_2_brainstorm_heartbeat_procedure_reference.md
Archived Sibling Plans: (none yet)
Worktree: (none — running on main per profile)
Branch: main
Base branch: main
---

# Plan: t650_3 — heartbeat fix attempt B (explicit shell commands, fallback)

## Context

**Fallback only — pick this child only if t650_2's verification fails** (i.e., agents still don't emit periodic heartbeats after the procedure-reference rewrite). If t650_2 succeeds end-to-end, mark this child Done with "not needed — t650_2 sufficient" appended to Final Implementation Notes and archive without code changes.

This child applies a more aggressive rewrite to the same 6 brainstorm templates: replace the procedure references from t650_2 with **literal `ait crew status …` shell command lines**, using the `${CREW_ID}` / `${AGENT_NAME}` context-variable pattern. This eliminates the implicit `_instructions.md` lookup entirely — the work2do file shows the agent the exact command to run, and the agent only needs to substitute the two variable values from `_instructions.md`.

Mirrors the declare-once-reference-everywhere pattern of `task-workflow/SKILL.md`'s "Context Requirements" table — context variables are bound at agent read time (not template write time), so no substitution engine is added to `aitask_crew_addwork.sh`.

**Initial status:** Postponed. Implementer should change to Implementing only after confirming t650_2 did not fix the issue.

## Concrete edits

### 1. Create `.aitask-scripts/brainstorm/templates/_context_variables.md` (NEW)

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

This follows the existing shared-include convention demonstrated by `_section_format.md`. Inlined at write time by `resolve_template_includes()` in `.aitask-scripts/lib/agentcrew_utils.sh:145` (already invoked by `aitask_crew_addwork.sh:162`). **No code change to addwork is needed.**

### 2. Add include directive to each of the 6 templates

Just below the level-1 `# Task: <name>` heading and above the existing `## Input` section:

```markdown
<!-- include: _context_variables.md -->
```

### 3. Replace each Checkpoint and Completion block

For every Checkpoint (replacing the procedure-reference lines from t650_2):

```
### Checkpoint 1
- Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat --message "Phase 1 complete — imported proposal loaded"`
- Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --progress 20`
- Run: `ait crew command list --crew ${CREW_ID} --agent ${AGENT_NAME}`
```

For every Completion:
```
## Completion
- Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --status Completed`
- Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --progress 100`
- Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat --message "Initialization complete"`
```

Apply to all 6 templates: `initializer.md`, `explorer.md`, `comparator.md`, `detailer.md`, `patcher.md`, `synthesizer.md`.

## CLI verification

The CLI surface was confirmed by reading `.aitask-scripts/agentcrew/agentcrew_status.py`:
- `heartbeat --message "<msg>"` is valid (see `cmd_heartbeat`, line 172, and parser at line 271–273).
- `set --status <s>` and `set --progress <N>` are valid (see `cmd_set`, line 87, and parser at line 264–265).
- `command list --crew <id> --agent <name>` is valid (separate `aitask_crew_command.sh` subcommand).

## Verification

1. **Include-resolution check:** after the changes, run `ait crew addwork` to write a test agent and inspect `<crew_worktree>/<agent>_work2do.md`. Confirm:
   - The Context Variables block appears as inlined content (not the literal `<!-- include: _context_variables.md -->` directive).
   - Each Checkpoint contains explicit `ait crew status …` lines with `${CREW_ID}` and `${AGENT_NAME}` literals (intentionally not substituted — the agent binds them by reading `_instructions.md`).

2. **Manual end-to-end (same as t650_2):** re-run brainstorm bootstrap on a small proposal, watch `<crew_worktree>/initializer_bootstrap_alive.yaml`, confirm `last_heartbeat` advances at every Checkpoint (4 + 1 = 5 advances) and the agent is not marked DEAD by `agentcrew_runner.py`.

3. **If t650_2 already succeeded and this child was picked by mistake:** archive without code changes (set status Done, plan-note "not needed — t650_2 sufficient").

## Out of scope (intentionally)

- No changes to `aitask_crew_addwork.sh` — the existing `resolve_template_includes` machinery already handles include inlining; the `${CREW_ID}` / `${AGENT_NAME}` placeholders are intentionally bound at the agent's read time, not at template write time. Per parent t650 user feedback: "instead of using a template substitution engine, [use] CREW_ID and AGENT_NAME as context variable[s] — we use this technique for execution profiles in task-workflow and it is working".
- No change to `heartbeat_timeout_minutes` default.

## Notes for sibling tasks

If both t650_2 and t650_3 fail, the next escalation is raising `heartbeat_timeout_minutes` from 5 → 10/15 in `agentcrew_runner.py:854` and `agentcrew_status.py:210` — but only as a separate follow-up task, not in this child.

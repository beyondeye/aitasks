---
priority: high
effort: medium
depends: [t650_1]
issue_type: bug
status: Implementing
labels: [agentcrew, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-26 14:18
updated_at: 2026-04-26 16:46
---

## Context

Bug 2 of parent t650 — first attempt at the heartbeat fix.

The brainstorm initializer (and 5 sibling agents) get marked DEAD by `agentcrew_runner.py` after 5 minutes of work because they never refresh `_alive.yaml` after the startup heartbeat. Confirmed timeline: `last_heartbeat: 2026-04-26 09:52:07` → marked dead at 09:57:16 (exactly 300 s — the default `heartbeat_timeout_minutes`).

**Root cause:** the templates use pseudo-verb shorthand at each Checkpoint (`report_alive`, `update_progress`, `check_commands`, `update_status`). These are not real skill names and not shell commands. The translation table to real `ait crew status …` calls lives in a *separate* file (`<agent>_instructions.md`, written by `aitask_crew_addwork.sh` lines 207–252). Agents have to read it, mentally substitute, and run the resulting command — and they unreliably do so.

This child takes the **less invasive** approach: replace each pseudo-verb with an explicit reference to the named procedure in `_instructions.md`. No new include file, no shell-command duplication, no template substitution engine. Mirrors the pattern `task-workflow/SKILL.md` uses for downstream procedures (e.g., "Execute the Manual Verification Procedure (see `manual-verification.md`)").

**Sibling t650_3** holds a more aggressive fix in reserve (literal shell commands with `${CREW_ID}`/`${AGENT_NAME}` context-variable include) — pick it only if this child's verification step 2 fails.

## Key Files to Modify

All under `.aitask-scripts/brainstorm/templates/`:

- `initializer.md` (4 Checkpoints + Completion)
- `explorer.md` (3 Checkpoints + Completion)
- `comparator.md` (3 Checkpoints + Completion)
- `detailer.md` (3 Checkpoints + Completion)
- `patcher.md` (verify count when editing)
- `synthesizer.md` (verify count when editing)

## Reference Files for Patterns

- `aitask_crew_addwork.sh` lines 207–252 — the source of truth for the procedure names referenced in `_instructions.md` (sections: "Status Updates", "Progress Reporting", "Heartbeat / Alive Signal", "Reading Commands").
- `.claude/skills/task-workflow/SKILL.md` — examples of "Execute the X Procedure (see `<file>.md`)" phrasing for explicit procedure references.

## Pseudo-verb → procedure-reference map

| Pseudo-verb (current) | Procedure section in `_instructions.md` |
|---|---|
| `report_alive: "<msg>"` | "Heartbeat / Alive Signal" |
| `update_progress: <N>` | "Progress Reporting" |
| `check_commands` | "Reading Commands" |
| `update_status: <status>` | "Status Updates" |

## Implementation Plan

For each of the 6 templates:

1. For every `### Checkpoint N` block currently shaped like:
   ```
   ### Checkpoint 1
   - report_alive: "Phase 1 complete — imported proposal loaded"
   - update_progress: 20
   - check_commands
   ```
   replace with:
   ```
   ### Checkpoint 1
   - Execute the **Heartbeat / Alive Signal** procedure from your `_instructions.md` with message: "Phase 1 complete — imported proposal loaded"
   - Execute the **Progress Reporting** procedure from your `_instructions.md` with progress: 20
   - Execute the **Reading Commands** procedure from your `_instructions.md`
   ```

2. For the `## Completion` block currently shaped like:
   ```
   ## Completion
   - update_status: Completed
   - update_progress: 100
   - report_alive: "Initialization complete"
   ```
   replace with:
   ```
   ## Completion
   - Execute the **Status Updates** procedure from your `_instructions.md` with status: Completed
   - Execute the **Progress Reporting** procedure from your `_instructions.md` with progress: 100
   - Execute the **Heartbeat / Alive Signal** procedure from your `_instructions.md` with message: "Initialization complete"
   ```

Preserve every other line in each template — only the pseudo-verb lines change.

## Verification Steps

1. **Static check:** for every template, grep for `report_alive\|update_progress\|check_commands\|update_status` — should return zero matches after the rewrite.

2. **Manual end-to-end:** re-run a brainstorm bootstrap on a small imported proposal:
   ```bash
   # Pick any small markdown proposal as input; ensure ait brainstorm bootstraps a fresh crew
   ait brainstorm bootstrap --proposal-file <small_proposal.md> --task <some_task_id>
   ```
   Watch `<crew_worktree>/initializer_bootstrap_alive.yaml` — `last_heartbeat` should advance at every Checkpoint (4 advances during work + 1 at completion).

3. **DEAD check:** during the same run, the agent should NOT be flagged as `Error / "Heartbeat timeout — agent presumed dead"` by `agentcrew_runner.py`. Check `_status.yaml` and the `ait brainstorm` status tab.

4. **If verification step 2 or 3 fails (heartbeats still not emitted reliably):** do NOT iterate inside this child. Close it as inconclusive (Done with a "fix did not stick" note in the plan), and pick up t650_3 to apply the more aggressive fix.

## Out of scope (intentionally)

- No changes to `aitask_crew_addwork.sh` (no template substitution engine).
- No new include files.
- No changes to `_instructions.md` content (the procedures are already documented there).
- No change to `heartbeat_timeout_minutes` default.

---
Task: t650_2_brainstorm_heartbeat_procedure_reference.md
Parent Task: aitasks/t650_brainstorm_bugs.md
Sibling Tasks: aitasks/t650/t650_1_ait_crew_whitelist.md, aitasks/t650/t650_3_brainstorm_heartbeat_explicit_commands.md
Archived Sibling Plans: (none yet)
Worktree: (none — running on main per profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-26 16:48
---

# Plan: t650_2 — heartbeat fix attempt A (procedure reference)

## Context

First attempt at the heartbeat fix described in parent t650.

The 6 brainstorm agent templates (`initializer/explorer/comparator/detailer/patcher/synthesizer.md`) use pseudo-verbs at each Checkpoint:
```
- report_alive: "..."
- update_progress: <N>
- check_commands
- update_status: <status>   # in Completion blocks
```

These are not real skill names and not shell commands. The translation to real `ait crew status …` calls lives in `<agent>_instructions.md` (written per-agent by `aitask_crew_addwork.sh` lines 207–252). Agents have to read it, mentally substitute, and run the resulting command — and they unreliably do so. Result: no periodic heartbeat → `_alive.yaml.last_heartbeat` stays frozen at startup → `agentcrew_runner.py` marks the agent Error / "Heartbeat timeout — agent presumed dead" at the 5-minute mark.

This child takes the **less invasive** approach: replace each pseudo-verb with an explicit reference to the named procedure section in `_instructions.md`. No new include file, no shell-command duplication, no template substitution engine. Mirrors the pattern `task-workflow/SKILL.md` uses ("Execute the X Procedure (see `<file>.md`)").

If this child's verification fails, sibling **t650_3** holds a more aggressive fix in reserve (literal shell commands with `${CREW_ID}`/`${AGENT_NAME}` context-variable include).

## Pseudo-verb → procedure-reference map

| Pseudo-verb (current) | Procedure section in `_instructions.md` |
|---|---|
| `report_alive: "<msg>"` | "Heartbeat / Alive Signal" |
| `update_progress: <N>` | "Progress Reporting" |
| `check_commands` | "Reading Commands" |
| `update_status: <status>` | "Status Updates" |

The procedure-section names match the existing `## H2` headers in the lifecycle-instructions block emitted by `aitask_crew_addwork.sh` (lines 207–252).

## Rewrite pattern

For every Checkpoint block currently shaped like:
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

For every Completion block currently shaped like:
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

## Files to edit (6)

All under `.aitask-scripts/brainstorm/templates/`:

| File | Pseudo-verb lines (counted from grep) |
|---|---|
| `initializer.md` | 4 Checkpoints + Completion (lines 86–88, 101–103, 118–120, 136–138, 142–143) |
| `explorer.md` | 3 Checkpoints + Completion (lines 128–131, 145–148, 160–163, 186–187) |
| `comparator.md` | 3 Checkpoints + Completion (lines 70–72, 83–85, 97–99, 103–104) |
| `detailer.md` | 3 Checkpoints + Completion (lines 107–109, 125–127, 139–141, 145–146) |
| `patcher.md` | grep before editing — `report_alive\|update_progress\|check_commands\|update_status` |
| `synthesizer.md` | grep before editing — same |

## Verification

1. **Static check:** `grep -E "report_alive|update_progress|check_commands|update_status" .aitask-scripts/brainstorm/templates/*.md` — should return zero matches after the rewrite.

2. **Manual end-to-end:** re-run a brainstorm bootstrap on a small imported proposal. Watch `<crew_worktree>/initializer_bootstrap_alive.yaml` — `last_heartbeat` should advance at every Checkpoint (4 advances during work + 1 at completion).

3. **DEAD check:** during the same run, the agent should NOT be flagged as `Error / "Heartbeat timeout — agent presumed dead"` by `agentcrew_runner.py`. Inspect `_status.yaml` and the `ait brainstorm` status tab.

4. **If verification step 2 or 3 fails (heartbeats still not emitted reliably):** do NOT iterate inside this child. Close it Done with a "fix did not stick" note appended to "Final Implementation Notes" below, then pick up `/aitask-pick 650_3` to apply the more aggressive fix.

## Out of scope (intentionally)

- No changes to `aitask_crew_addwork.sh` (no template substitution engine).
- No new include files.
- No changes to `_instructions.md` content (the procedures are already documented there).
- No change to `heartbeat_timeout_minutes` default.

## Notes for sibling tasks

If this child succeeds: t650_3 should be archived without code changes (mark Done, plan-note "not needed — t650_2 sufficient"). If this child fails: t650_3 builds on this child's structure but replaces the procedure-reference lines with explicit shell commands.

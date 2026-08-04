---
priority: medium
effort: medium
depends: [1041]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1041]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-22 09:30
updated_at: 2026-08-04 17:29
completed_at: 2026-08-04 17:29
boardcol: tests
boardidx: 1094
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1041

## Verification Checklist

- [x] In a real crew worktree with all member agents Completed but a stale _crew_status.yaml (Running/80), `ait crew report --crew <id>` shows Completed and 100%. — PASS 2026-08-04 17:21 auto: fixture crew persisted Running/80 + member Completed; 'ait crew report summary --crew stale' -> Completed / 100%, 'report list' and 'crew status get' agree; persisted file unchanged (derive-on-read)
- [x] `ait crew dashboard` (TUI) shows the derived status/progress in BOTH the crew list (CrewCard) and the detail view for that same stale crew. — PASS 2026-08-04 17:21 auto: live 'ait crew dashboard' in tmux (200x45) - CrewCard shows 'stale Completed 100%' and detail view header shows 'Completed 100%' for the same stale crew
- [x] `ait crew cleanup --crew <id>` cleans a crew whose persisted status is stale-Running but whose member agents are all terminal (Completed/Aborted/Error). — PASS 2026-08-04 17:21 auto: 'ait crew cleanup --crew stale --batch' -> CLEANED:stale, worktree removed, despite persisted Running/80; negctrl (member Running, persisted Completed) -> NOT_TERMINAL:busy:members_not_terminal, worktree kept
- [x] A Killing crew with a live runner still shows Killing in the dashboard; once the runner stops (or heartbeat goes stale), it rolls forward to the derived terminal state. — PASS 2026-08-04 17:21 auto: persisted Killing + live runner -> Killing/40% in list+detail; stale heartbeat (10m) -> Aborted; fresh heartbeat again -> Killing; status=stopped w/ fresh heartbeat -> Aborted
- [x] An all-aborted crew is reported as Aborted (not Completed) and is cleanup-eligible. — PASS 2026-08-04 17:21 auto: all-Aborted crew (persisted Running/80) -> CREW_STATUS:Aborted and CLEANED:aborted; negctrl mixed Completed+Aborted -> Completed/50%

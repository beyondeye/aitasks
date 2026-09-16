---
priority: medium
effort: medium
depends: [1809]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1809]
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: manual_verification
created_at: 2026-09-16 12:12
updated_at: 2026-09-16 12:39
completed_at: 2026-09-16 12:39
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1809

## Verification Checklist

- [x] Start `ait board` from a linked worktree (git worktree add --detach + aitask_init_data.sh --link-worktree) and confirm the By-Trail banner no longer reads "(drift unavailable: ref_outside_project)" for a trail that is CURRENT in the primary checkout — PASS 2026-09-16 12:39 auto: board in linked worktree (detached + --link-worktree) opens a CURRENT trail with banner '… · lite', no drift-unavailable suffix; pre-fix control worktree (c1a9e5843^) shows '(drift unavailable: ref_outside_project)' for the same trail
- [x] Confirm the same trail's By-Trail drift verdict in the linked worktree matches what the primary checkout shows for it (same verdict, not merely "no error") — PASS 2026-09-16 12:39 auto: aitask_trail_gather.sh drift output byte-identical (verdict, DRIFT reasons, DIGEST) primary vs linked worktree for all 9 trails (5 CURRENT, 4 STALE); board banners identical for the TUI-checked trail
- [x] Start `ait board` in the primary checkout and confirm By-Trail drift still renders normally (control — the change must not alter the layout that already worked) — PASS 2026-09-16 12:39 auto: primary checkout board banner for the same trail renders CURRENT (no suffix); CLI drift for all 9 trails unchanged, no errors
- [x] Pick a task under a worktree-mode profile (create_worktree: true) and confirm drift/roadmap checks work inside the created aiwork/ worktree — PASS 2026-09-16 12:39 auto: reproduced the Step 7 fork layout (git worktree add -b aitask/<scratch> aiwork/<scratch> main + --link-worktree) without claiming a real task; trail drift byte-identical to primary for 9 trails, and backlog-roadmap generate (11 plan_file refs) + drift -> CURRENT with inputs identical to primary

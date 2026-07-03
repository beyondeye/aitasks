---
Task: t1118_5_manual_verification_mobile_shadow_agent_driving_over_applink.md
Parent Task: aitasks/t1118_mobile_shadow_agent_driving_over_applink.md
Sibling Tasks: aitasks/t1118/t1118_1_*.md, aitasks/t1118/t1118_2_*.md, aitasks/t1118/t1118_3_*.md, aitasks/t1118/t1118_4_*.md
Archived Sibling Plans: aiplans/archived/p1118/p1118_*_*.md
Worktree: aiwork/t1118_5_manual_verification_mobile_shadow_agent_driving_over_applink
Branch: aitask/t1118_5_manual_verification_mobile_shadow_agent_driving_over_applink
Base branch: main
---

# Plan: End-to-end manual verification (t1118_5)

`issue_type: manual_verification` — dispatched to the interactive checklist
runner (task-workflow Step 3 Check 3); the checklist is seeded in the task
file. Runs after t1118_3, t1118_4 (local) and `aitasks_mobile#32_2` (cross-repo
UI) land.

## Setup notes for the session

- Real device paired to `ait applink`, three pairings exercised across items:
  `full`, `monitor_control`, `read_only`.
- A live followed agent in tmux (e.g. a claude session on a scratch task) and a
  shadow spawned beside it — spawn from the mobile app for the spawn items,
  from minimonitor `e` for the desktop-regression item.
- For the staleness item: after the shadow's read, send fresh input to the
  followed agent so it produces new output, then confirm the stale banner AND
  that it persists across several status ticks (non-stamping invariant).
- For the forwarding item: pick ≥2 concerns with multi-line bodies so the
  bracketed-paste (stage-only) behavior is observable — text staged in the
  agent's input, submitted only on explicit Enter from the key bar.

## Checklist

Seeded in the task file (one item per verified behavior, tagged with the
origin child). Each must reach Pass / Fail / Skip / Defer in the runner.

## Post-implementation

Archival fires the parent-archival check (last child of t1118); parent t1118
and the cross-repo parent `aitasks_mobile#32` should both be complete at that
point.

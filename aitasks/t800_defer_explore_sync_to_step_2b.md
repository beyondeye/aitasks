---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_explore, skill_optiomizations]
created_at: 2026-05-19 15:19
updated_at: 2026-05-19 15:19
---

Defer the `aitask_pick_own.sh --sync` call in `/aitask-explore` from the upfront Step 0 to the top of Step 2b (Related Task Discovery).

## Why

The sync (best-effort `git pull --ff-only` + stale-lock cleanup) is only load-bearing right before scanning existing tasks (related-task discovery) and assigning a new task ID. Running it upfront delayed the first `AskUserQuestion` ("What would you like to explore?") by the round-trip cost of the pull, with no benefit during the exploration phase itself.

Moving the sync into Step 2b removes that latency without changing correctness:
- Step 2b still gets a fresh tree before scanning for overlapping tasks.
- Step 3 (task creation) still assigns the new task ID against current state.
- The eventual handoff to task-workflow Step 4 performs its own sync before lock acquisition.

The call remains best-effort and non-blocking (no network → continue silently).

## Scope

- Source-of-truth edit: `.claude/skills/aitask-explore/SKILL.md.j2`
- All 12 closure targets (4 agents × 3 profiles) re-rendered via `aitask_skill_render.sh`
- `aitask_skill_verify.sh` passes

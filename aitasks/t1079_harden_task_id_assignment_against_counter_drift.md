---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, git]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-26 07:48
updated_at: 2026-06-29 11:56
boardidx: 40
---

Make task-ID assignment robust against **counter drift**, so `ait create` can
never hand out an ID that is <= an existing task ID (which produces duplicate
`t<id>_*.md` files and breaks `resolve_task_file` with "Multiple task files
found").

## Problem

Parent IDs come from the `aitask-ids` CAS counter branch
(`aitask_claim_id.sh --claim`; `next_id.txt`). The CAS push correctly prevents
two machines claiming the **same** number simultaneously, but **nothing enforces
the invariant `counter >= max(existing task IDs)`**, and there is no self-heal.
Any ID that enters the task set without advancing *this* counter silently leaves
it behind, after which it hands out duplicates.

Drift sources (all observed/over reasoned during a live incident 2026-06-25/26):
- **Manual `git mv` renumbering** of a task bumps the file's ID without claiming
  from the counter.
- **Multi-machine local-counter divergence:** the local-only claim path
  (`claim_local`) advances only the local `aitask-ids` branch; reconciliation to
  the remote is best-effort and one-way (`try_push_local_to_remote` only fires
  when the remote branch is *absent*). A machine that ever claimed locally can
  leave the shared remote counter behind the real task set.
- Any out-of-band task creation.

Live symptom: the counter handed out 1075 (collided with an existing
`t1075_install_sh`), then a concurrent session claimed 1077 which collided with a
manually-renamed `t1077`. Result was two task files sharing one ID and
`resolve_task_file` failing.

## Proposed fix

1. **Self-healing claim (core).** In `aitask_claim_id.sh`, hand out
   `max(counter_value, scan_max_task_id + 1)` (using `scan_max_task_id` from
   `lib/archive_scan.sh`, scanning active **and** archived), and advance the
   counter to `handed_out + 1`. This makes the counter incapable of returning an
   ID <= an existing task ID regardless of how drift occurred. Apply to both the
   remote-CAS path and `claim_local`.
2. **Post-claim collision guard (defense in depth).** In `aitask_create.sh`
   finalization, after claiming ID N, if `aitasks/tN_*.md` or an archived
   `tN_*.md` already exists, re-claim (bounded loop) and warn instead of writing a
   duplicate.
3. **`--resync` command.** Add `aitask_claim_id.sh --resync` that sets the counter
   to `max(current, scan_max + 1)` via the same CAS push, and wire it into
   `ait setup` (and/or a health/doctor check) so drift self-corrects on routine
   runs.
4. **Safe renumber helper (optional).** A small `ait` helper that claims a fresh
   ID from the counter and `git mv`s a task to it atomically, so manual
   renumbering can't reintroduce drift. (The self-heal in #1 makes manual renames
   non-fatal, but the helper removes the footgun.)

## Coordination

Same file as **t1077** (`fix_id_counter_fetch_failure_diagnostics`), but a
**different bug**: t1077 fixes misleading *fetch-failure diagnostics / error
messaging*; this task fixes the *drift / duplicate-ID correctness invariant*.
They should be implemented coherently (both touch `aitask_claim_id.sh`). See
t1077; this task is the correctness counterpart. (Reverse link added on t1077.)

## Acceptance criteria

- Claiming **never** returns an ID <= the max existing task ID (active or
  archived). Regression test: set the counter below the real max, claim, assert
  the returned ID is `max+1` and the counter advanced past it.
- `aitask_create.sh` never writes a duplicate `t<id>` file: test with a
  pre-existing `tN`, force a claim of `N`, assert the guard re-claims and the new
  file gets a unique ID.
- `--resync` repairs a drifted counter (test: counter below max -> resync ->
  counter = max+1), idempotent when already healthy.
- Works in both remote-CAS and local-only counter modes; CAS race retry behavior
  preserved.
- A bidirectional coordination note exists between this task and t1077.

## Reference

Live incident diagnosis 2026-06-25/26: counter (`next_id`) had fallen to the
current max task ID, so the next claim collided. Root cause confirmed as the
missing `counter >= max(task ids)` invariant + no self-heal, with manual renames
and multi-machine local-counter divergence as the drift sources.

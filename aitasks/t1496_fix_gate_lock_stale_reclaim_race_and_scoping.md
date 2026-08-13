---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1507]
assigned_to: dario-e@beyond-eye.com
anchor: 1171
followup_kind: upstream_defect
implemented_with: claudecode/fable5
created_at: 2026-08-12 14:40
updated_at: 2026-08-13 11:57
---

## Origin

Spawned from t1485 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_gate.sh:129-147 — stale-lock reclaim is not single-winner: a contender stats the old dir, decides "stale", then mv's whatever is at that path, which can be another contender's freshly-created live lock, yielding two simultaneous holders and duplicate/lost ledger attempt numbers (reproduced 3/25 rounds against unmodified code); the "Single-winner reclaim: rename is atomic" comment at :134 is only true when no third state change intervenes between stat and mv`
- `.aitask-scripts/aitask_gate.sh:122 — the gate mutex path /tmp/aitask_gate_lock_<key> is neither repo-scoped nor env-overridable, so two aitasks checkouts on one machine share a lock namespace for the same task id and serialize (or corrupt) each other's unrelated gate appends`
- `tests/test_parallel_child_create.sh:76-77,180-182,214,220 — same fixed-/tmp-lock collision t1485 fixed for the gate suite: hard-coded /tmp/aitask_child_lock_100 (pre-created, backdated, stat-shimmed and rmdir'd) against aitask_create.sh:331-333, so two concurrent runs of that file read each other's locks as foreign`

## Diagnostic context

t1485 gave `tests/test_gate_lock_characterization.sh` a per-run task-id
namespace so two concurrent runs stop colliding on `/tmp/aitask_gate_lock_*`.
That fix works — 4-way concurrent runs pass 46/46 each, with four disjoint
`9<pid>` id families observed in `/tmp`. But one post-fix concurrent round
still showed 2 failures in **Test 6b** (stale reclaim under contention):
`attempt=1` present twice, `attempt=2` absent.

That is **not** a residual path collision: those assertions read each run's own
`mktemp -d` fixture, which was never shared between runs. It was traced to a
race in production `acquire_gate_lock` and reproduced with a **from-scratch
script that never reads the characterization file**, driving unmodified
`aitask_gate.sh` — 3/25 rounds anomalous, with two distinct symptoms:
`blocks=1` (a lost ledger block) and `attempt1=2 attempt2=0` (two holders
computing the same next attempt).

Mechanism. Both contenders `stat` the same stale dir and both compute
`age > 120`. Contender A `mv`s it to its quarantine, `rmdir`s it, `continue`s,
and its `mkdir` succeeds — A now holds a **fresh** lock at that path. Contender
B, still acting on the staleness verdict it computed from the **old** dir, then
runs `mv "$lock_dir" "$stale_dest_B"` — which moves **A's live lock** away. B
`rmdir`s it and `mkdir`s its own. Both A and B are now inside the critical
section. `mv` is atomic on the *path*, not on the inode that was `stat`ed, so
the single-winner property the comment claims does not hold once a third state
change lands between `stat` and `mv`.

Note this is a *different* window from the one t1188 closed: t1188 fixed the
case where `stat` **fails** (lock vanished → retry immediately, pinned by
Test 7). Here `stat` **succeeds** on a dir that is then replaced.

t1485 deliberately left the failing assertion intact — it is correctly
reporting a real defect, and t1485's scope was test isolation only (the
test-only approach was an explicit user decision).

## Suggested fix

Bind the reclaim decision to the directory **identity**, not just the path:
`registry_lock.sh:38-70` already models this in-repo — it writes `pid` / `owner`
token files into the lock dir and steals only a provably-dead holder. Reusing
that shape (or at minimum re-verifying the dir's inode/mtime immediately before
the `mv`, and treating any change as "not stale — retry") would make the reclaim
genuinely single-winner. The same helper shape also fixes
`aitask_create.sh:331-333`.

For the scoping bullet, consider deriving the lock base from a repo identity
(and/or honouring an env override), which would additionally give tests a
documented isolation seam instead of forcing them to encode uniqueness in the
task id.

Bullet 3 is a self-contained test fix and can be done independently: apply the
same per-run id namespace t1485 used (see
`tests/test_gate_lock_characterization.sh` for the `GATE_LOCK_BASE` + `ID_BASE`
pattern, and prove it with a pre-edit concurrent negative control).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T06:45:44Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-13T08:11:35Z status=pass attempt=1 type=human

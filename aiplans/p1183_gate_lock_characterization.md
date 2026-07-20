---
Task: t1183_gate_lock_characterization.md
Base branch: main
plan_verified: []
---

# t1183 — Gate lock characterization tests

## Context

t635_30 will replace the gate-mutex key derivation in
`.aitask-scripts/aitask_gate.sh` — today `local key="${task_id//\//_}"` (raw
argument, at `:152`, `:187`, `:649`) — with a key derived from the **resolved
task file** (`_gate_lock_key <resolved-file>` = basename sans `.md`, per
`aiplans/p635/p635_30_task_gate_editing_surface.md` §1). That mutex guards every
ledger `append` and every claim-time `materialize-active`. This task pins the
**current** mutual-exclusion behavior with characterization tests so the swap is
provably safe: after t635_30 lands, exactly the key-derivation assertions flip
and everything else must stay green.

## Empirical finding — task premise correction (AC deviation, made explicit)

The task's Goal item 2 states that `append t635_30` and `append 635_30` "take
different locks and do not mutually exclude". **Verified false as written**: in
`cmd_append` the file is resolved (`resolve_task_file`, `aitask_gate.sh:148`)
*before* the lock is computed/acquired (`:187-188`), and `resolve_task_file`
(`lib/task_utils.sh:594`) never strips a `t` prefix — a `t`-spelled id matches
neither the child regex nor the parent glob (`ls aitasks/tt…_*.md`) and **dies
with "No task file found" before any lock is taken** (verified live:
`aitask_gate.sh status t1183` → rc 1). The board even strips the `t` itself
(`aitask_board.py:5911`). So cross-spelling concurrency is unreachable via the
CLI today.

The *real* divergence t635_30 fixes is **raw-argument key vs resolved-file key**
— directly observable without concurrency by pre-holding a lock directory:

- today: holding `/tmp/aitask_gate_lock_<raw-id>` blocks `append <raw-id>`;
  holding `/tmp/aitask_gate_lock_<file-basename>` does **not**;
- after t635_30: exactly reversed.

The tests pin that pair (the characterization payload), plus one test
documenting that the `t`-spelling dies at resolve. The task file's Goal item 2
will be updated to record this corrected premise (explicit AC update, committed
via `./ait git`).

**Upstream defect found (for Step 8b):** `lib/archive_utils.sh:53`
(`archive_path_for_id`) does `bundle=$(( task_id / 100 ))` — a non-numeric id
(e.g. `t1183`) crashes with `t1183: unbound variable` under `set -u`, printing
noise before `resolve_task_file`'s friendly die.

## Implementation

**One new file: `tests/test_gate_lock_characterization.sh`** (no production
changes). Conventions: `set -u`, `PASS/FAIL/TOTAL` + `tests/lib/asserts.sh`,
fixture-in-mktemp with `TASK_DIR=aitasks` cwd — mirroring
`tests/test_gate_active_gates.sh:31-79` (`new_fixture` / `run_gate` helpers).
Fixture: registry `gates.yaml` with one machine gate `tests_pass`, profile
`profiles/fast.yaml` (`default_gates: [tests_pass]`), tasks
`t98765N_x.md` with `gates: [tests_pass]`.

The lock path is hardcoded `/tmp/aitask_gate_lock_<key>` (not TMPDIR-scoped),
so use distinctive task ids (987651–987655) and clean up
`/tmp/aitask_gate_lock_*98765*` in the exit trap. `acquire_gate_lock` is
non-reentrant (`aitask_gate.sh:70-91`) — no test nests acquisitions.

### Tests

1. **Same-spelling exclusion holds today (must survive t635_30).** Launch 4
   concurrent `append 987651 tests_pass pass` background jobs; `wait`. Assert:
   exactly 4 `gate:tests_pass` markers in the task file; attempts 1–4 each
   present exactly once (attempt auto-increment runs under the lock, so
   serialization ⇒ distinct attempts, and a lost update ⇒ a missing block);
   lock dir absent afterwards (normal-exit release).

2. **Key = raw argument (the assertion pair t635_30 flips).**
   - **2a (raw key honored, fail-closed exhaustion):** pre-create fresh
     `/tmp/aitask_gate_lock_987652`; `append 987652 tests_pass pass` → nonzero
     exit; stderr contains `Failed to acquire gate append lock for 987652 after
     20 attempts` (pins the 20-attempt budget and that a held lock ⇒ `die`, not
     proceed-unlocked); no `## Gate Runs` section written; the **held lock dir
     still exists** (die never removes a lock it doesn't own). ~6s runtime.
   - **2b (file-derived key NOT honored today):** release 2a's dir; pre-create
     `/tmp/aitask_gate_lock_t987652_x` (the resolved-basename key t635_30 will
     adopt); `append 987652 tests_pass pass` → exit 0, block written
     immediately. After t635_30, 2a and 2b swap outcomes — that is the exact
     flip the task asks for.

3. **Cross-spelling status quo + alias-introduction tripwire:** `append
   t987652 tests_pass pass` → nonzero exit; stderr contains `No task file
   found`; marker count on t987652 unchanged (still 1 from 2b); no
   `/tmp/aitask_gate_lock_t987652` dir was ever created (dies pre-lock).
   Verified: p635_30 introduces **no** spelling normalization, so exactly one
   accepted spelling exists per task today and cross-alias concurrency is
   unreachable. This test is deliberately a **tripwire**: if t635_30 (or any
   later change) makes the `t`-spelling resolvable, this test fails loudly and
   its documented replacement (see flip contract below) must be added — an
   **alias lock-convergence test**: pre-hold
   `/tmp/aitask_gate_lock_<resolved-basename>` and assert *every* accepted
   spelling blocks, plus a live cross-spelling concurrent-append serialization
   check (all blocks land, attempts unique). The suite structurally cannot go
   stale on alias introduction.

4. **`materialize-active` shares the same raw-argument lock as `append`
   (same-spelling serialization across verbs):** pre-create
   `/tmp/aitask_gate_lock_987653`; `materialize-active 987653 --profile
   aitasks/metadata/profiles/fast.yaml` → nonzero, stderr contains `Failed to
   acquire gate append lock` (~6s). Negative control (guarded on a resolvable
   python, `PY` pattern from `tests/test_gate_ledger.sh:25`): after releasing
   the dir, the same call succeeds with `MATERIALIZED:tests_pass` — proving the
   lock alone caused the failure.

4b. **Live append/materialize contention (lost-update detector, deterministic;
   PY-guarded):** the pre-held probe in 4 pins the shared *key* but cannot
   catch a read/write ordering bug that loses an update under real
   interleaving — `materialize-active` shells out to `aitask_update.sh`, which
   rewrites the **entire frontmatter** inside the critical section, so an
   append landing mid-materialize without mutual exclusion would drop a ledger
   block or the tuple. Overlap is made **deterministic by holding the lock
   ourselves** rather than relying on process timing:
   1. `mkdir /tmp/aitask_gate_lock_987653` (test holds the mutex).
   2. Launch in background BOTH `materialize-active 987653 --profile
      fast.yaml` and 2 × `append 987653 tests_pass pass`. All three must spin
      in the retry loop — neither verb can touch the file before acquiring the
      lock.
   3. After sleeping ~1s (well inside the 6s retry budget), **assert
      contention actually happened**: the task file still has no
      `## Gate Runs` section and no `active_gates:` key — proof all three
      contenders are blocked, not already finished.
   4. `rmdir` the held lock; `wait` for all three.
   5. Assert the serialized outcome: both ledger blocks present with attempts
      1–2 each exactly once; `active_gates:` tuple present; file still parses
      (`aitask_gate.sh status 987653` exits 0); no lock dir left behind.
   Step 3 is what elevates this above a best-effort race: a pass is impossible
   without the contenders having provably retried under contention. (Skip with
   a note if no python resolves; adds ~1s runtime.)

5. **Lock released on `die` via the `trap release_gate_lock EXIT` path:**
   `AIT_GATES_BACKEND=python AIT_PYTHON="$(command -v false)" append 987654
   tests_pass pass` → the python delegate fails while the lock is held →
   `die "python gate_ledger append failed"` (nonzero, stderr asserted); assert
   `/tmp/aitask_gate_lock_987654` is **absent** afterwards (the EXIT trap
   released it).

6. **Stale-lock reclaim (>120s):** pre-create `/tmp/aitask_gate_lock_987655`
   and backdate it (`touch -t 202001010000`, BSD/GNU-portable); `append 987655
   tests_pass pass` → exit 0; stderr contains `Removing stale gate lock`;
   block written; lock dir gone afterwards.

Total runtime ≈ 15s (two ~6s exhaustion tests; the rest sub-second).

### Explicit flip contract (t635_30)

Recorded verbatim in the test file's header comment so the t635_30 implementer
has the checklist in-file:

| Test | Today | After t635_30 (`_gate_lock_key <resolved-file>`) |
|---|---|---|
| 1 (same-spelling concurrent appends) | pass | **must still pass** |
| 2a (held raw-id lock blocks) | blocks → die | **flips**: no longer blocks |
| 2b (held file-basename lock ignored) | proceeds | **flips**: blocks → die |
| 3 (t-spelling dies at resolve) | pass | must still pass while no alias is introduced; if aliases ever resolve, this test fails → replace per the tripwire note with the alias lock-convergence test |
| 4 / 4b (materialize shares lock; deterministic contention) | pass | must still pass — the held-lock key in 4/4b moves from raw id to file basename in lockstep with 2a/2b |
| 5 (trap release on die) / 6 (stale reclaim) | pass | **must still pass** |

### Task-file AC update

Edit `aitasks/t1183_gate_lock_characterization.md` Goal item 2 to record the
corrected premise (t-spelling dies at resolve; the pinned divergence is
raw-vs-resolved-file key derivation via pre-held lock dirs). Commit with
`./ait git` (`ait:` prefix).

## Verification

- `bash tests/test_gate_lock_characterization.sh` → all PASS.
- Negative control of the characterization itself: temporarily hand-edit
  `aitask_gate.sh:187` to a file-derived key and confirm tests 2a/2b **fail**
  (the suite actually detects the t635_30-shaped change), then revert. This is
  a manual sanity check during implementation, not a committed change.
- `shellcheck tests/test_gate_lock_characterization.sh` clean.
- Run `bash tests/test_gate_ledger.sh` and `bash tests/test_gate_active_gates.sh`
  to confirm no interference (shared `/tmp` lock namespace).

## Step 9 (Post-Implementation)

Standard flow: review/commit (`test: Add gate lock characterization tests
(t1183)`), gate orchestrator run (`./ait gates run 1183` — `risk_evaluated` is
the active gate), archival via `aitask_archive.sh 1183`.

## Risk

### Code-health risk: low
- Test-only change (one new self-contained file); no production paths touched. · severity: low · → mitigation: TBD
- Hardcoded `/tmp` lock namespace could collide with parallel suites; mitigated by distinctive 98765x ids + trap cleanup. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The task's stated premise for AC item 2 was empirically wrong; the plan pins the actually-observable divergence (raw vs file-derived key) and updates the AC explicitly, so the t635_30 flip contract is preserved. · severity: low · → mitigation: covered in-plan by the negative-control verification step

No mitigation follow-up tasks planned: this task is itself the "before"
mitigation for t635_30, both dimensions are low, and the in-plan negative
control covers the mischaracterization concern.

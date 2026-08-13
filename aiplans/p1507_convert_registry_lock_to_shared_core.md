---
Task: t1507_convert_registry_lock_to_shared_core.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1507 — Convert `registry_lock.sh` onto the shared `stale_lock.sh` core

## Context

t1496 fixed an observe-then-destruct steal race in the gate/child mutex by
building `lib/stale_lock.sh`: all lock-directory mutations (identity publish,
owner-checked release, reclaim observation + destruction) are serialized under a
`<lock_dir>.gc` guard, so a staleness verdict is always acted on in the same
guarded section it was formed in.

That landed as a **second** mutex library beside `lib/registry_lock.sh`, which
still carries the identical latent defect — t1496's own plan recorded it as an
upstream defect:

```
.aitask-scripts/lib/registry_lock.sh:52-58 — same observe-then-destruct steal
shape t1496 fixed (holder observed dead, then mv acts on whatever is at the
path); latent two-holder window under contention for ait projects / ait attach
```

Concretely, `registry_lock_acquire` reads `$dir/pid`, decides the holder is
dead, and *then* `mv`s whatever is at `$dir` — with no serialization between the
observation and the destructive act. A contender that re-published a fresh live
lock in that window gets displaced, putting two holders in the critical section.

**Outcome:** one mutex protocol remains in the tree. `registry_lock.sh` becomes
a thin API-preserving adapter over `stale_lock.sh`, so its five consumer
families inherit the single-winner reclaim for free and nothing else changes.

## Consumers (the full blast radius)

| Consumer | Lock path | Timeout |
|---|---|---|
| `aitask_projects.sh` (`registry_lock_or_die`) | `${REGISTRY_FILE}.lockd` | default 10 |
| `lib/attachment_lock.sh` → `aitask_attach.sh`, `aitask_artifact.sh` | `<data-worktree>/attachments/.attach.lock` | `ATTACH_LOCK_TIMEOUT` (30) |
| `aitask_agent_marks.sh` | `${MARKS_FILE}.lockd` | caller-supplied |
| `aitask_shadow_rejected.sh` | `${STORE_FILE}.lockd` | caller-supplied |
| `aitask_gate.sh cmd_sync_registry` | `/tmp/aitask_gate_registry_sync` | 10 |

All five source `lib/terminal_compat.sh` before `registry_lock.sh`, so
`stale_lock.sh`'s `warn()` dependency is already satisfied at every call site.

Lock paths stay exactly where they are: these are **fixed shared locations**
(per-user config dir, data worktree, `/tmp`), deliberately *not* candidates for
`ait_lock_dir`'s per-repo scoping. Only the mutex protocol converges.

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_timeout_and_silence]` **Before editing the lib**, add three
   characterization assertions to `tests/test_registry_lock.sh` and run the file
   against unmodified HEAD — they must **pass first**, which is what makes them
   a real pin rather than a description of whatever the rewrite happens to do:
   - acquire against a live holder returns 1 only once the integer clock reaches
     `start_second + timeout` — **measured from a second boundary**, see the
     note below;
   - a dead-holder steal still succeeds within `timeout=1`;
   - the live-holder busy path writes **nothing** to stderr (capture stderr to a
     file, assert it is empty) — `tests/test_shadow_rejected.sh:503` and
     `tests/test_agent_marks_concurrency.sh:116` both pin
     `assert_eq … "LOCK_BUSY" "$out"` on `2>&1`-captured output, so any new
     stderr line on that path is a consumer-visible break.

   **Measuring the deadline soundly (do not skip — a naive elapsed check cannot
   fail).** The timeout is quantized by `date +%s`: `deadline = start_second +
   timeout`, polled against whole seconds. A call entered at wall-clock `10.999`
   with `timeout=1` sets `deadline=11` and may legitimately return at `11.001` —
   a 2 ms wait — while `t1-t0` still reads `1`. An `elapsed -ge timeout` check
   built on `date +%s` therefore measures the same rounded quantity it is meant
   to bound and would pass for an implementation that returns in milliseconds.

   Align the start to a tick first; after a boundary the integer delta becomes a
   genuine real-time bound, and it stays portable (no GNU-only `date +%s.%N`, no
   bash-5 `$EPOCHREALTIME`):

   ```bash
   # registry_lock's deadline is whole-second-quantized (see above), so start
   # the measurement immediately after a tick — otherwise the second-delta is
   # not a bound on anything.
   wait_for_second_boundary() {
       local s0; s0=$(date +%s)
       while [[ "$(date +%s)" == "$s0" ]]; do sleep 0.01; done
   }

   wait_for_second_boundary
   t0=$(date +%s)
   rc=0; registry_lock_acquire "$d" 2 2>"$errf" || rc=$?
   t1=$(date +%s); elapsed=$(( t1 - t0 ))
   ```

   Assert the **lower bound only**: `elapsed >= 2` — never reports busy before
   its own deadline. This direction is immune to host load: a descheduled
   process only waits longer, which can never turn a passing run into a failure.

   Use `timeout=2`, not `1`: the 0.05 s poll granularity is then well inside the
   band, so the test is not decided by scheduler jitter.

   **Deliberately no wall-clock upper bound here.** "Returns within ~timeout" is
   not a property the old code has — it makes no real-time promise at all — and
   any `elapsed <= N` assertion is decided by scheduling: this suite runs with
   up to 4 parallel workers alongside other agents, so a correct process paused
   for more than a second would fail it spuriously. The behavior an upper bound
   was standing in for (a re-arm that hands each outer pass a *fresh full*
   budget instead of the remaining time) is a property of the new code only, is
   not characterizable against HEAD at all, and is pinned deterministically —
   with no clock in the assertion — by the re-arm test in the new test set below.

   Record the HEAD-green run in the plan's implementation notes, then proceed.
   Re-run after the rewrite: identical results are the acceptance signal for the
   timeout→retry-budget mapping.

### 1. Rewrite `.aitask-scripts/lib/registry_lock.sh` as an adapter

Keep the file, the load guard `_AIT_REGISTRY_LOCK_LOADED`, the function names,
the module-level `_registry_lock_dir` / `_registry_lock_token` state (the unit
test reads the token), and the EXIT trap. Replace the body with delegation:

```bash
_AIT_REGISTRY_LOCK_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/stale_lock.sh
source "$_AIT_REGISTRY_LOCK_SELF/stale_lock.sh"

# One value pair: the poll interval and its reciprocal. stale_lock budgets
# ATTEMPTS; registry_lock's API budgets SECONDS — these convert between them.
_REGISTRY_LOCK_SLEEP=0.05
_REGISTRY_LOCK_ATTEMPTS_PER_SEC=20

_registry_lock_dir=""
_registry_lock_token=""

# registry_lock_acquire <lock_dir> [timeout_secs=10] [label]
registry_lock_acquire() {
    local dir="$1" timeout="${2:-10}" label="${3:-lock $1}"
    local deadline remaining retries
    deadline=$(( $(date +%s) + timeout ))
    while :; do
        remaining=$(( deadline - $(date +%s) ))
        (( remaining < 0 )) && remaining=0
        # Re-arm from the REMAINING time each pass: stale_lock's budget is a
        # retry count, and a burst of dead-holder reclaims spends it without
        # sleeping. Returning on the first exhaustion would break this API's
        # contract ("busy only after the deadline"); re-arming from what is
        # left also stops the last pass from overshooting it.
        retries=$(( remaining * _REGISTRY_LOCK_ATTEMPTS_PER_SEC ))
        # Floor of 2: one reclaim consumes an attempt without acquiring, so a
        # zero/short timeout must still get the follow-up mkdir that the old
        # `continue`-after-steal loop gave it.
        (( retries < 2 )) && retries=2
        if stale_lock_acquire "$dir" "$retries" "$_REGISTRY_LOCK_SLEEP" "$label"; then
            _registry_lock_dir="$dir"
            _registry_lock_token="$STALE_LOCK_TOKEN"
            # shellcheck disable=SC2064  # expand $dir now, on purpose
            trap "registry_lock_release '$dir'" EXIT
            return 0
        fi
        (( $(date +%s) >= deadline )) && return 1
    done
}

# registry_lock_release <lock_dir> — ALWAYS returns 0 (see below).
registry_lock_release() {
    local dir="$1"
    [[ -n "$_registry_lock_dir" && "$dir" == "$_registry_lock_dir" ]] || return 0
    stale_lock_release "$dir" "$_registry_lock_token" \
        || warn "registry_lock: '$dir' not fully released"
    _registry_lock_dir=""
    _registry_lock_token=""
    trap - EXIT
    return 0
}

# registry_lock_describe <lock_dir> — passthrough to stale_lock_describe, so a
# caller can name a wedged lock/guard in its own busy message.
registry_lock_describe() { stale_lock_describe "$1"; }
```

Rewrite the header comment: state that this is now an adapter, that the
`.gc`-guarded single-winner reclaim is inherited from `stale_lock.sh`, and
record the three deliberate boundary deltas below.

### 2. The deliberate semantic deltas (documented in the header)

1. **Timeout → retry budget.** The API keeps its `timeout_secs`; the deadline
   loop makes it a strict superset of `stale_lock`'s retry budget. Invariant
   preserved: acquire returns 1 **only** once the deadline has passed — never
   proceed unlocked, never report busy early.

   State the contract precisely, because it is coarser than it looks and the
   adapter must preserve it *including* its coarseness: the deadline is
   **quantized to whole seconds** by `date +%s` (`deadline = start_second +
   timeout`), so the guarantee is "never reports busy before the integer clock
   reaches `start_second + timeout`" — **not** "waits at least `timeout` seconds
   of real time". A call entered late in a second can legitimately return almost
   immediately. Keeping `date +%s` (rather than promoting the deadline to a
   high-resolution clock) is deliberate: it is the existing behavior, it is
   portable, and changing it is out of scope for a consolidation task.
2. **Release always returns 0.** `stale_lock_release` returns 1 on a retained
   lock/guard, but every caller is `set -euo pipefail` and calls
   `registry_lock_release` bare, after the protected mutation has already
   committed — propagating there would abort the script mid-flow. The adapter
   surfaces retention as a `warn` and returns 0.
3. **Tokenless-age reclaim is newly reachable** (`_STALE_LOCK_WINDOW`, 120s).
   registry_lock's own locks always carry a pid file, and under the `.gc` guard
   the publish is atomic, so a tokenless dir can only be a legacy/foreign lock —
   never a holder mid-acquire. This is strictly safer than the old code, which
   treated a tokenless dir as live and waited out the whole timeout.

Two properties are preserved unchanged and must be tested: the **EXIT trap**
installed at acquire (callers rely on it — `with_attach_lock` in particular),
and the **single-active-lock-per-process** guard in release (a mismatched dir is
a silent no-op).

### 3. Preserve the busy path's silence

`aitask_shadow_rejected.sh` and `aitask_agent_marks.sh` both pin
`assert_eq … "LOCK_BUSY" "$out"` on output captured with `2>&1`, so the
live-holder exhaustion path must emit **nothing** on stderr. `stale_lock` warns
only when it actually reclaims or retains, so this holds — the adapter must not
add its own exhaustion warn. Pin it with an assertion rather than leaving it to
chance.

### Post-phase (risk mitigations)

1. `[guard_wedge_recovery]` After the conversion is green, prove and document
   the newly inherited wedge failure mode as one named unit:
   - **Test** (in `tests/test_registry_lock.sh`): with a stale lock present and
     a leaked `<lock>.gc` guard held by nobody, `registry_lock_acquire` fails
     closed within its timeout — returns 1, does **not** reclaim the stale lock,
     and leaves both dirs intact. This is the behavior the old `mv`-based steal
     could not provide, and it is also the behavior that wedges a lock, so it
     must be pinned deliberately rather than discovered in production.
   - **Surface**: `registry_lock_describe <lock_dir>` (passthrough to
     `stale_lock_describe`) so a caller can name the wedged lock and guard;
     assert it names the lock dir, the holder pid, and a present `.gc`.
   - **Docs**: state the manual recovery — "remove `<lock_dir>.gc` when no
     reclaim is running" — in the `registry_lock.sh` header and in the lock
     bullet of `aidocs/framework/shell_conventions.md`, so the silent
     `ait projects add` bootstrap path (`… >/dev/null 2>&1 || true`) has a
     documented cure.

## Files

- `.aitask-scripts/lib/registry_lock.sh` — rewritten as the adapter (above).
- `tests/test_registry_lock.sh` — source `terminal_compat.sh` first (the lib now
  needs `warn()`, exactly as `tests/test_stale_lock.sh` does); keep cases 1–5
  verbatim as the preserved-contract pins; add the new cases below.
- `tests/test_registry_lock_single_winner.sh` — **new**, modeled on
  `tests/test_gate_lock_single_winner.sh`: production concurrency through a real
  consumer (`ait projects`, the t1073 scenario).
- `aidocs/framework/shell_conventions.md` — the lock bullet currently reads
  "`lib/registry_lock.sh` is the separate persistent registry mutex;
  consolidation onto this core is a planned follow-up." Rewrite: it is now an
  adapter over the same core, with caller-chosen fixed lock paths (not
  `ait_lock_dir`-scoped), and name the wedged-`.gc` manual recovery.

No consumer script changes: the API is unchanged.

## New test cases

**`tests/test_registry_lock.sh`** (added after the existing five):

- Guard hygiene: no `$d.gc` remains after acquire, and none after release.
- Single-winner reclaim: a leaked `$d.gc` guard makes acquire fail closed
  against a stale lock — the lock is **not** reclaimed while the guard is held
  (this is the invariant the old `mv`-based steal could not provide).
- **A re-published live lock is never displaced (structural).** Seed `$d` with a
  dead pid (the verdict material a contender would form), hold `$d.gc`
  externally (stand-in for another contender inside the guarded reclaim
  section), then overwrite `$d`'s `pid`/`owner` with a **live** holder and a new
  token — the republish, already done. `registry_lock_acquire "$d" 1` must
  return 1 and leave both files byte-identical.
- **The interleaving itself, forced (deterministic, with a negative control).**
  This is the exact defect the task exists to close, so it gets a construction
  that cannot pass by scheduling luck. `_stale_lock_reclaim_under_gc` calls
  `_stale_lock_pid_alive` immediately after reading the holder pid and
  `_stale_lock_rm_verified` immediately after the verdict — that gap *is* the
  observe→destruct window. Park a contender in it:

  ```bash
  # Contender A, in a subshell: declare the holder dead, then block until the
  # test releases it — i.e. verdict formed, destruction not yet performed.
  ( _stale_lock_pid_alive() { touch "$PARKED"; while [[ -e "$HOLD" ]]; do sleep 0.01; done; return 1; }
    registry_lock_acquire "$d" 10; ... ) &
  ```

  While A is parked, the main process attempts `registry_lock_acquire "$d" 1`.
  Assert:
  - B **fails** (A holds `.gc`, so B can neither reclaim nor publish) and `$d`
    still carries the original dead pid — B never got the chance to re-publish;
  - releasing the barrier lets A finish, and A's token is the sole `owner`.

  **Negative control (must FAIL the property).** Run the identical barrier
  construction against a fixture stub carrying the *old* observe-then-`mv` body
  with the same park hook. There B is not excluded: it reclaims and publishes a
  fresh **live** lock while A is parked, and A's `mv` then moves that live lock
  away — two holders. Assert the negative control **does** lose the fresh lock.
  A negative control that passes the property means the construction does not
  discriminate and the whole case is worthless — fail loudly if so.
- Tokenless lock: fresh → waited on and acquire fails; backdated past the 120s
  window → reclaimed.
- **Deadline re-arm uses the remaining time, not a fresh full budget** — the
  deterministic counterpart to the wall-clock lower bound, with no clock in any
  assertion. Rename-and-wrap the real function (the deterministic-shim pattern
  `tests/test_stale_lock.sh` and `tests/test_gate_lock_single_winner.sh`
  already use), recording the retry budget each outer pass requests and forcing
  an early exhaustion so the loop must re-arm:

  ```bash
  src="$(declare -f stale_lock_acquire)"
  eval "_real_stale_lock_acquire${src#stale_lock_acquire}"   # keep the original
  stale_lock_acquire() { printf '%s\n' "$2" >> "$BUDGETS"; sleep 0.01; return 1; }
  ```

  With `timeout=3`, assert on `$BUDGETS` alone:
  - the first budget is exactly `timeout × 20` (60) — the full window;
  - at least two budgets were requested, i.e. the loop re-armed rather than
    returning on the first exhaustion (a fail here reads "outer loop did not
    re-arm before the deadline"; it needs two 0.01 s calls inside 3 s, so only
    a multi-second freeze could reach it);
  - the last budget is **strictly less** than the first, and the sequence is
    non-increasing — the budget tracks the shrinking remaining time. A fresh
    full budget per pass shows up as a constant `60`, which this fails on.

  Restore the real function afterwards so later cases exercise the lock for
  real.
- Release under a foreign token leaves the lock intact **and still returns 0**
  (delta 2), and clears our module state.
- `registry_lock_describe` names the lock dir, the holder pid, and a present
  guard.

**`tests/test_registry_lock_single_winner.sh`** (new): an isolated registry via
`AITASKS_PROJECTS_INDEX`, plus K fake project roots (each just
`aitasks/metadata/project_config.yaml`).

- *Live holder never displaced*: seed `${REGISTRY_FILE}.lockd` with a live PID
  and a backdated mtime; `ait projects add` must die "Registry is locked by
  another ait process", leave the holder's `pid`/`owner` untouched, and write
  nothing to the registry.
- *K contenders through one stale lock serialize*: seed the lock with a
  **dead pid** — not a tokenless dir. The old code skips the steal outright when
  the pid file is missing (`[[ -n "$holder" ]] && ! kill -0 …`, treating it as
  live), so a tokenless seed would exercise only the *new* age-reclaim path and
  say nothing about the path both implementations share. Then run K=4 concurrent
  `ait projects add <root_i>` and assert exactly K registry entries (a lost
  update yields fewer), **exactly one** `Reclaiming … from dead holder pid`
  across all contenders' stderr, and no lock or `.gc` dir left behind.

  **What this test is and is not.** It is a production-level check that the
  adapter serializes real `ait projects` read-modify-writes under a burst (the
  t1073 scenario) — its failure mode is a lost update, which is what t1073 was
  about. It is **not** the pin for the observe-then-`mv` race: nothing in a
  free-running race forces one contender to form a staleness verdict and act on
  it *after* another has reclaimed and re-published, so it can pass against
  racy code. That pin is the forced-interleaving case above; the two are
  complementary and neither substitutes for the other.

## Verification

```bash
bash tests/test_registry_lock.sh                 # unit contract
bash tests/test_registry_lock_single_winner.sh   # new: ait projects contention
bash tests/test_stale_lock.sh                    # core unchanged
bash tests/test_gate_lock_single_winner.sh       # core's other consumer
bash tests/test_agent_marks_concurrency.sh       # consumer: LOCK_BUSY + contention
bash tests/test_shadow_rejected.sh               # consumer: LOCK_BUSY/exit-4 split + negative control
bash tests/test_attach_local_backend.sh          # consumer: attach lock, no leak
bash tests/test_archive_shadow_prune.sh          # fixture that copies registry_lock.sh
bash tests/test_projects_cmd.sh                  # ait projects regression
shellcheck .aitask-scripts/lib/registry_lock.sh
```

The fixture in `test_archive_shadow_prune.sh` copies `registry_lock.sh` into a
fake repo; `setup_fake_aitask_repo` already copies `stale_lock.sh`
unconditionally, so the new `source` resolves — its fixture pre-check will fail
loudly if that ever stops being true. `test_shadow_rejected.sh`'s negative
control replaces `registry_lock.sh` wholesale with a no-op stub and needs no
change.

Step 9 (Post-Implementation) handles merge and archival.

## Risk

### Code-health risk: medium
- Every mutex in the tree except the task-ownership lock now funnels through one
  adapter: five consumer families (`ait projects`, `ait attach` /
  artifact-manifest transactions, agent marks, shadow rejections, `ait gates
  sync-registry`) inherit any regression in ~40 lines of new code · severity:
  medium (residual — the pre-phase pins the preserved contract before the
  rewrite, but the fan-out itself is inherent to consolidation) ·
  → mitigation: inline pre-phase characterize_timeout_and_silence
- New inherited failure mode: `stale_lock`'s `.gc` guard is fail-closed and
  never auto-broken, so a process killed inside the guard's few-file-op window
  wedges that lock permanently until removed by hand. The old code left only a
  pid-carrying dir, which the next contender reclaimed automatically. Worst
  case is silent: `ait projects add` runs on every tmux bootstrap as
  `… >/dev/null 2>&1 || true` · severity: medium (residual — the post-phase
  pins the fail-closed behavior and documents the manual cure; it does not
  make the wedge self-healing, which is the price of a guard that never steals)
  · → mitigation: inline post-phase guard_wedge_recovery
- Stderr surface widens on the reclaim path (`stale_lock` warns where the old
  lib was silent) next to two consumer suites that pin `LOCK_BUSY` on
  `2>&1`-captured output · severity: low (residual — the pre-phase asserts the
  busy path stays silent) ·
  → mitigation: inline pre-phase characterize_timeout_and_silence
- `.gc` guard dirs now appear beside caller-chosen lock paths, including inside
  the data worktree (`attachments/.attach.lock.gc`). Attach stages explicit
  paths (`task_git add -- "${stage[@]}"`), never `-A`, and the guard is removed
  within the acquire/release call, so exposure is a sub-second window ·
  severity: low · → mitigation: none

### Goal-achievement risk: low
- The adapter shape is prescribed and mechanically checkable; the only designed
  part is the wall-clock-timeout → retry-budget mapping, where a wrong deadline
  re-arm would make a caller report busy earlier than it does today ·
  severity: low (residual — the pre-phase measures the mapping against HEAD
  first, so a divergence is an assertion failure, not a field report) ·
  → mitigation: inline pre-phase characterize_timeout_and_silence

### Planned mitigations
- timing: pre-phase | name: characterize_timeout_and_silence | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "adapter fan-out across five consumers" + "stderr surface widens" and goal-achievement "timeout→retry-budget mapping" | desc: pin the current whole-second-quantized deadline behavior (measured from a tick boundary, lower bound only — an upper bound is scheduling-decided, so the re-arm behavior it proxied for is pinned separately by a clock-free shim test on the new code), the dead-holder steal, and the stderr silence of the busy path, as assertions that pass against HEAD before the rewrite and must pass identically after
- timing: post-phase | name: guard_wedge_recovery | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "leaked .gc guard wedges the lock with no auto-recovery" | desc: test that a leaked guard makes acquire fail closed without reclaiming, add the registry_lock_describe passthrough, and document the manual `rm <lock>.gc` recovery in the lib header and shell_conventions.md

## Final Implementation Notes

- **Actual work done:** Exactly the planned four files, no consumer script
  changes (the API is unchanged). `.aitask-scripts/lib/registry_lock.sh` 88 →
  144 lines, now delegating to `stale_lock_acquire` / `stale_lock_release` with
  a deadline loop that converts the API's seconds into the core's retry budget,
  re-arming from the *remaining* time each pass; `registry_lock_describe` added
  as a `stale_lock_describe` passthrough. `tests/test_registry_lock.sh` 15 → 51
  assertions. `tests/test_registry_lock_single_winner.sh` added (15
  assertions). `aidocs/framework/shell_conventions.md`: the "consolidation onto
  this core is a planned follow-up" sentence replaced by an adapter bullet
  documenting the three boundary deltas, the caller-chosen fixed lock paths, the
  five consumer families, and the wedged-`.gc` manual recovery.

  **Pre-phase (`characterize_timeout_and_silence`) executed as specified.** The
  three characterization assertions were written first and run against the
  *unmodified* lib: 19/19 green. They were then re-run against the adapter:
  19/19, identical. HEAD-greenness was re-verified after the fixture fix below
  by extracting `git show HEAD:.aitask-scripts/lib/registry_lock.sh` (confirmed
  the old implementation: 88 lines, `mv "$dir"` at :55, zero `stale_lock`
  references) into an isolated tree with copies of the test, asserts,
  `terminal_compat.sh` and `stale_lock.sh` — 19/19 there too. The deadline
  assertion was additionally probed for discrimination: forcing `timeout=0`
  against a live holder yields `elapsed=0` and the assertion FAILS, so it is not
  one of the vacuous checks the plan warns about.

  **Post-phase (`guard_wedge_recovery`) executed as specified**: case 9 pins the
  leaked-guard fail-closed behavior (returns 1, no reclaim, both dirs intact)
  and asserts `registry_lock_describe` names the lock dir, the holder pid and
  the guard; the manual `rm <lock_dir>.gc` cure is documented in the lib header
  and in `shell_conventions.md`.

- **Deviations from plan:** None in scope. One clarification: the plan listed
  the structural "re-published live lock is never displaced" case and the forced
  interleaving as separate cases; the structural one is largely subsumed by the
  interleaving case, but it was implemented anyway (case 9b) since it costs ~15
  lines and can genuinely fail (it would catch a reclaim under a held guard or a
  displaced live holder). Both are present.

- **Issues encountered:** The converted suite appeared to hang — 2 m 4 s wall
  time with 0.2 s of CPU. Tracing with `PS4='+ $EPOCHREALTIME '` located a 60.0 s
  gap immediately after `kill 879056` / `wait 879056` in **case 3, pre-existing
  and unmodified since t1073**. See the upstream-defect bullet below. After the
  fixture fix the suite runs in ~4 s (11 s with all new cases).

- **Key decisions:**
  - *Timeout mapping.* The deadline loop re-arms from the remaining time rather
    than calling the core once with `timeout × 20` retries. A burst of
    dead-holder reclaims consumes the core's budget **without sleeping**, so a
    single call could exhaust long before the deadline and report busy early —
    the one thing this API's timeout promises not to do. A floor of 2 retries
    preserves the old `continue`-after-steal behavior for zero/short timeouts.
  - *`if` blocks, not `(( … )) && x=y`.* Every caller is `set -euo pipefail`; a
    false `(( … ))` at statement level returns 1 and would abort the caller
    mid-flow. The old code used `if` for exactly this reason and the adapter
    matches it.
  - *Release still returns 0.* Propagating `stale_lock_release`'s retention
    failure would abort five `set -e` consumers *after* their protected mutation
    had already committed. Retention is surfaced as a `warn` instead; case 14
    pins the contract.
  - *No exhaustion warn in the adapter.* `aitask_shadow_rejected.sh` and
    `aitask_agent_marks.sh` both pin an exact `LOCK_BUSY` on `2>&1`-captured
    output, so the busy path must stay silent on stderr. Case 6 asserts it
    rather than leaving it to inspection. This is why the wedge hint is exposed
    as `registry_lock_describe` (opt-in, caller-invoked) instead of being warned
    automatically.
  - *Negative control for the race pin.* Case 11 reproduces the pre-conversion
    acquire body in the fixture with a park hook at the same seam and asserts
    the old algorithm **loses** a re-published live lock (`owner == "a-old-token"`
    exactly — not `!= "b-fresh-token"`, which an A that never acquired would
    satisfy vacuously through a missing file). It passes, so case 10
    discriminates.

- **Upstream defects identified:**
  - `tests/test_registry_lock.sh:58-64 (pre-fix) — dead-PID fixture built as
    `sleep 60 & kill $!; wait $!` races bash's fork→exec window: a signal sent
    microseconds after `&` is lost, and the `wait` (load-bearing — only reaping
    makes the PID answer `kill -0` with failure; a zombie still answers
    success) then blocks for the child's full 60 s. Pre-existing since t1073 and
    passing only by scheduling luck; fixed here to `bash -c 'echo $$'` because
    this task adds a second instance of the same construction. The same
    `sleep N & kill $!` shape near a `wait` is worth sweeping for elsewhere in
    `tests/`.

- **Verification:** `test_registry_lock` 51/51; `test_registry_lock_single_winner`
  15/15; `test_stale_lock`, `test_gate_lock_single_winner`,
  `test_agent_marks_concurrency` PASSED; `test_shadow_rejected` 130/130;
  `test_attach_local_backend` 41/41; `test_archive_shadow_prune` 26/26;
  `test_projects_cmd` 42/42; `test_artifact_cli` 82/82; `test_attach_meta`
  42/42; `test_gates_sync_registry` 93/93; `shellcheck` clean (SC1091
  source-following info only, as elsewhere in the tree).

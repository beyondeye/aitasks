---
Task: t2167_merge_lock_waiter_backoff_and_release_starvation.md
Base branch: main
Output branch: main
---

# t2167 — merge-lock waiter: long jittered poll + release-side starvation fix

## Context

`aitask_merge_task.sh begin` waits for the Step 9 merge mutex with a 50 ms poll
copied from `registry_lock.sh` (`lib/merge_lock.sh:78-79`), roughly 20
attempts/s per waiter. Every attempt takes the `.gc` guard and runs the
holder-liveness probe (`_merge_lock_liveness_seam` → `merge_lock_liveness` →
`lock_holder_liveness`) **inside** the guard (`stale_lock.sh`
`_stale_lock_reclaim_under_gc`). The merge lock is held for minutes, so the poll
wastes resources. It is also a correctness defect (merged t2156): N waiters keep
the guard nearly always occupied. The holder's `finish`/`abort` →
`stale_lock_release` gets only 40×50 ms of guard tries and gives up, so the lock
leaks with a live holder. That is what happened in macOS Case 2: 3 of 51 merges
landed, then the run wedged.

Intended outcome:
- one waiter polls about every 30 s;
- `--wait-secs` semantics stay the same;
- other `stale_lock.sh` callers are untouched;
- a waiter blocked on a live holder never takes the guard;
- under the guard, a waiter never runs the expensive probe on a holder it has
  not already judged dead, so the release cannot be starved, including in the
  window where a holder appears;
- a same-session `begin` retry still re-enters its own reservation.

## Design decisions

1. **Poll interval: 30 s base, uniform jitter of ±25% (22.5–37.5 s).**
   Computed in ms using `RANDOM` inline (no `$(...)` subshell, so no RANDOM
   reseed issue). The first attempt is immediate.
2. **One "attempt" is one short burst.** `stale_lock_acquire "$dir" 3 0.05`:
   the attempt plus up to two reclaims. This is exactly today's `wait_secs=0`
   shape. The waiting loop moves out of `merge_lock_acquire` into
   `cmd_begin`, which already owns `WAITING` progress and the test seams.
3. **Timeout clamp.** Before each sleep:
   `remaining = deadline - now` (integer seconds, from `date +%s`).
   - If `remaining <= 0`, stop.
   - Otherwise emit one `WAITING:<holder>:<elapsed>`, then sleep
     `min(jittered_ms, remaining*1000)` and attempt again.
   The last attempt therefore lands at the deadline. The maximum overrun is
   under 1 s plus one attempt, never a whole interval. `--wait-secs 0` gives
   exactly one attempt and no `WAITING` line.
4. **Release-side fix (t2156 option 3, "probe outside the guard, decide under
   it"), with instance gating.** Two parts. The first alone is not enough
   (review finding: holder appears after the pre-check):
   - **(a) Unguarded pre-probe.** Read the holder **instance key**
     `K = "<pid>|<owner>"` using builtin `read` (no forks), probe
     `merge_lock_liveness`, then re-read the key.
     - If the dir exists, the key is stable, and the verdict is `alive` or
       `unknown`: return busy **without touching the guard**.
     - If the verdict is `dead` with a stable non-empty key: remember it in
       `_merge_lock_dead_key=K`.
     - If the lock is absent, or the key changed during the probe:
       `_merge_lock_dead_key=""`.
   - **(b) Instance-gated guarded seam.** `_merge_lock_liveness_seam` (it runs
     under the guard on every failed `mkdir`, including internal retries) first
     re-reads the on-disk key with builtin `read`.
     - Only when it equals `_merge_lock_dead_key` does it run the expensive
       `merge_lock_liveness` probe, and reclaim on `dead`.
     - Any other instance returns "do not displace" with **no probe**. That
       covers a holder published after the pre-check, one met on an internal
       retry, and one replaced mid-attempt.
   - Under the guard, a live holder therefore costs two builtin `read`s and
     never a `ps`/`bsdinfo` probe. The destructive decision is still formed
     and acted on in one guarded section, because the dead pre-verdict only
     *permits* a guarded re-probe and never replaces it.
   - A key collision (pid reuse) only costs one guarded probe, never a wrong
     reclaim. A newly published holder that is in fact dead is left for the
     next poll's pre-probe.
   - Behaviour for a partial publish (pid present, owner empty, holder dead)
     is preserved: the key `"<pid>|"` matches on both reads, so the lock is
     still reclaimed as today.

   - Consequences:
     - While a live holder is established, merge waiters never take the guard.
     - In the transition window (lock absent at pre-probe, published before
       `mkdir`), a waiter takes the guard only for builtin reads plus
       `mkdir`/`rmdir`, never the expensive probe. Guard occupancy from
       waiters stays at the level of the core's own bookkeeping, which the
       40×50 ms release budget was designed for.
     - The shared core (`stale_lock.sh`) is **unchanged**, so no other caller
       is affected. Guarded sections (`force-release`) do not use the seam.
5. **Same-owner re-entry is preserved, and made immediate** (review finding).
   - Today, when acquire fails, `cmd_begin:167-168` falls through to the merge
     if `merge_lock_authorize "$dir" "$task_id"` passes: same task id plus the
     same session anchor. A repeated `begin` from the owning session (for
     example after a lost response) therefore re-enters its reservation and
     returns `MERGE_OK`.
   - The new loop keeps that. After **every** failed attempt it runs
     `merge_lock_authorize … && acquired=1`.
   - Today a same-session retry with `--wait-secs 120` waited the full 120 s
     on itself before the fallback fired. Now it re-enters at the first
     attempt. That is a deliberate improvement, recorded in the notes.
   - A different session with the same task id still fails
     `NOT_OWNER_SESSION` and gets `BUSY`.
6. **Test seam `AIT_MERGE_LOCK_POLL_MS`** (integer ms) sets the base interval.
   It is honoured **only** when the `.ait_merge_test_seams` marker exists,
   exactly like `AIT_MERGE_LOCK_DISABLED`, and warns "TEST SEAM ACTIVE". The
   production default is not shortened.

## Pre-phase (risk mitigations)

- **baseline_suites** — before any edit, run `bash tests/test_merge_lock_broker.sh`,
  `bash tests/test_merge_lock_concurrency.sh` and
  `bash tests/test_merge_broker_rendered_verdicts.sh` on the untouched tree and
  record pass counts. Do not stash; the tree is clean.
- **measure_before** — `git archive HEAD .aitask-scripts | tar -x` into a
  scratchpad dir. Run one waiter
  `bash -x <copy>/aitask_merge_task.sh begin tB main aitask/x --wait-secs 60`
  against a lock held by a live anchor (fixture repo +
  `AITASKS_LOCK_DIR` scratch). Count `lock_holder_liveness` xtrace lines, which
  equal liveness probes. That gives attempts/min.

## Implementation steps

### 1. `.aitask-scripts/lib/merge_lock.sh`
- Replace `_MERGE_LOCK_SLEEP` / `_MERGE_LOCK_ATTEMPTS_PER_SEC` with:
  - `_MERGE_LOCK_POLL_SECS=30` (waiter cadence);
  - `_MERGE_LOCK_ATTEMPT_RETRIES=3` and `_MERGE_LOCK_ATTEMPT_SLEEP=0.05`
    (the in-attempt burst: guard-busy / reclaim fast retries).
- Add `merge_lock_poll_delay_ms <base_ms>`. It sets global
  `_MERGE_LOCK_POLL_DELAY_MS = base*3/4 + ((RANDOM<<15|RANDOM) % (base/2+1))`.
  It is a global and not an echo, so the caller avoids a subshell.
- Add `_merge_lock_instance_key <lock_dir>`. It sets global
  `_MERGE_LOCK_KEY="<pid>|<owner>"` via
  `{ IFS= read -r p < "$d/pid"; } 2>/dev/null`. That is a builtin read with
  no fork, and empty when the file is missing.
- Rework `_merge_lock_liveness_seam` (decision 4b): read the instance key and
  compare it to `_merge_lock_dead_key`.
  - If they differ, `return 0` (do not displace, no probe).
  - If they match, re-probe `merge_lock_liveness` and `return 1` only on
    `dead`.
- Rework `merge_lock_acquire <task_id> <out_branch> <task_branch> [label]` into
  a single attempt:
  - set up the identity/seam globals as today;
  - reset `_merge_lock_dead_key=""`;
  - run the unguarded pre-probe (decision 4a);
  - run `stale_lock_acquire "$dir" "$_MERGE_LOCK_ATTEMPT_RETRIES" "$_MERGE_LOCK_ATTEMPT_SLEEP" "$label"`.
  - Keep the existing t1598 "no markerless-guard window" comment.
- Header:
  - update the `Provides:` signature;
  - rewrite **delta 4** to "SECONDS BUDGET, LONG JITTERED POLL": the lock is
    held for minutes, so registry_lock's ms cadence does not carry over; one
    attempt is a burst; the clamp rule; per-caller scope;
  - add **delta 6**, "NO EXPENSIVE PROBE UNDER THE GUARD FOR A HOLDER NOT
    ALREADY JUDGED DEAD". It covers:
    - the t2156 starvation;
    - the unguarded pre-probe, which can only lead to no action;
    - instance gating of the guarded seam, which covers a holder published
      after the pre-probe and holders met on internal retries;
    - that the destructive verdict is still re-formed under the guard.

### 2. `.aitask-scripts/aitask_merge_task.sh` (`cmd_begin`)
- Add `_seam_poll_ms()`. It echoes `AIT_MERGE_LOCK_POLL_MS` when it is set,
  matches `^[0-9]+$`, and `_test_seams_enabled` is true, with a warn.
  Otherwise it echoes `$(( _MERGE_LOCK_POLL_SECS * 1000 ))`.
- Replace the `slice=2` loop with the decision-3 loop:
  ```bash
  poll_ms="$(_seam_poll_ms)"; start=$(date +%s); deadline=$(( start + wait_secs )); acquired=0
  _try() {  # one attempt, then the same-owner re-entry fallback (decision 5)
      merge_lock_acquire "$task_id" "$out_branch" "$task_branch" "merge lock" && return 0
      merge_lock_authorize "$dir" "$task_id" >/dev/null 2>&1
  }
  _try && acquired=1
  while [[ "$acquired" -eq 0 ]]; do
      now=$(date +%s); remaining=$(( deadline - now ))
      [[ "$remaining" -gt 0 ]] || break
      holder=...; progress "WAITING:$holder:$(( now - start ))"
      merge_lock_poll_delay_ms "$poll_ms"; ms=$_MERGE_LOCK_POLL_DELAY_MS
      (( ms > remaining*1000 )) && ms=$(( remaining*1000 ))
      sleep "$(( ms/1000 )).$(printf '%03d' $(( ms%1000 )))"
      _try && acquired=1
  done
  [[ "$acquired" -eq 1 ]] || { verdict "BUSY:${holder:-unknown}:$(( $(date +%s) - start ))"; exit 0; }
  ```
  - `_try` is written inline in `cmd_begin` (or as a small local helper);
    the sketch only shows its shape.
  - `holder` is re-read for the verdict, as today.
  - The loop is errexit-safe: `merge_lock_acquire` and `merge_lock_authorize`
    only ever run in `&&` / condition context.
- Update the header comment block on the seams to list `AIT_MERGE_LOCK_POLL_MS`.

### 3. Tests
- **`tests/test_merge_lock_broker.sh`**, new cases. Seams stay **off** unless
  stated, so the production 30 s default is under test.
  - **Case 19, timeout clamp.**
    - A holds the lock. B runs `begin --wait-secs 3`.
    - Expect `BUSY:tA:` and wall-clock elapsed ≤ 3+2 s, not ~30 s.
    - Expect exactly one `WAITING:` line, since one poll is clamped to the
      budget.
    - `--wait-secs 0`: expect `BUSY`, zero `WAITING` lines, and an elapsed of
      ≤ 1 s.
  - **Case 20, released just before the deadline.**
    - A holds the lock. Start B `begin --wait-secs 5` in the background, with
      stderr to a file.
    - Wait (bounded poll) for B's `WAITING:` line, then `finish tA`.
    - Expect B to report `MERGE_OK:` within 5+2 s. This proves the final
      attempt at the deadline acquires a lock freed mid-sleep, even under the
      production interval.
  - **Case 21, the seam is marker-gated.**
    - Without the marker, `AIT_MERGE_LOCK_POLL_MS=200` with `--wait-secs 2`
      gives one `WAITING` line.
    - With the marker, it gives several (≥3).
  - **Bounded rendezvous, used by Cases 22 and 22c.** Every FIFO the test
    reads from or writes to is opened **read-write** in the test first
    (`exec {fd}<>"$fifo"`):
    - the opposite side's `open()` never blocks;
    - every test-side read is `read -t 20 -r tok <&$fd`, and a timeout is an
      explicit FAIL ("rendezvous never reached"), never a hang;
    - writes to the waiter go through the test's own fd as `printf 'x\n'`.
    - **Every signal, in both directions, is one newline-terminated line**:
      `r1` readiness, `P`/`D` tokens, `g1`/`g2` releases. The test holds each
      FIFO open read-write, so no EOF ever arrives, and an unterminated byte
      makes the bounded `read` time out even though the rendezvous was
      reached. Grep the test for `printf [^']*> *"\?\$\?r` and bare
      `printf x` before running it.

    The waiter reports on a **single** result FIFO with one token per event:
    `P` when it enters a `lock_holder_liveness` probe, and `D` when
    `merge_lock_acquire` returns. Whatever the code does, a token arrives or
    the bounded read fails. No mutation can turn the case into a hang.
  - **Case 22, release-starvation regression (deterministic, no sleeps).**
    Lib-level, in the Case-9 inner-script shape.
    - The holder acquires via `merge_lock_acquire` under a live anchor.
    - A background waiter script sources the lib and overrides
      `lock_holder_liveness` to `printf 'P\n' > "$R"; read -r _ < "$G"; printf alive`.
      It calls `merge_lock_acquire` once, then runs `printf 'D\n' > "$R"`.
    - The test runs a bounded read of the first token.
      - Assert it is `P`, meaning the waiter is parked inside a probe. This
        is the case's precondition.
      - A `D` means the waiter never probed, so the scenario was not built.
        That is a FAIL with that message, not a pass.
    - **Case 22b.** While the waiter is parked, assert the guard dir
      `"$LOCKD.gc"` is **absent**, i.e. the probe is unguarded.
    - The holder calls `merge_lock_release`. Expect rc 0 and the lock dir
      gone. Then send `G` and do a bounded reap.
    - **Red control.** Run it against an isolated scratch copy of the lib
      with **both** the unguarded pre-probe **and** the instance gating
      removed. That is the original defect: the seam probes any holder
      under the guard.
      - Expected: token `P` with the guard present (22b fails), and release
        rc 1 (22 fails).
      - Removing only the pre-probe is *not* a valid control. The gated seam
        would then decline to probe, the token would be `D`, and the
        precondition assert fails instead. Record both outcomes.
  - **Case 22c, holder published after the pre-probe (review finding;
    deterministic, two FIFO rendezvous, no sleeps).** The waiter inner script
    sources the lib and makes two overrides:
    - It wraps `stale_lock_acquire`, using the
      `eval "_orig_… $(declare -f …)"` shape from `test_create_email_lock.sh`.
      On its first call the wrapper does `printf 'x\n' > r1; read -r _ < g1`, then
      calls the original. That parks the waiter **after** the absent-lock
      pre-probe and **before** the core.
    - It overrides `lock_holder_liveness` to `printf 'P\n' > r2; read -r _ < g2; printf alive`,
      which parks inside any probe. After `merge_lock_acquire` returns, the
      script runs `printf 'D\n' > r2`.
    - All test-side reads use the bounded-rendezvous helper above.
    The test then:
    1. starts the waiter with the lock **absent**, and does a bounded read of
       `r1`;
    2. has another session acquire, via
       `broker <repo> <anchorA> begin tA main aitask/tclean` → `MERGE_OK`;
    3. writes `g1`, and does a bounded read of one token from `r2`;
    4. asserts the token is `D`: the waiter returned without probing. With
       the gating reverted it is `P`, meaning the waiter is parked in a probe
       under the guard;
    5. runs `broker … finish tA` and asserts `RELEASED`, not
       `RETAINED:release_failed`, with the lock dir gone;
    6. on `P`, writes `g2` to unpark, then does a bounded reap.

    The red run is recorded against a scratch copy with the seam gating
    removed (pre-probe kept). It must produce `P` and `RETAINED`,
    reproducing the review's finding.
  - **Case 23, same-owner re-entry (review finding).**
    - Session A runs `begin tA … --wait-secs 0` twice with no `finish` in
      between: both return `MERGE_OK`.
    - Session A, with `--wait-secs 5`, returns `MERGE_OK` in ≤ 2 s, because
      it re-enters immediately instead of waiting on itself.
    - Session B (a different anchor) on the **same** task id `tA`, with
      `--wait-secs 1`, gets `BUSY:tA:` and is refused.
    - Then A runs `finish tA` and gets `RELEASED`.
- **`tests/test_merge_lock_concurrency.sh` Case 2.** Run workers with
  `AIT_MERGE_LOCK_POLL_MS=500` (the marker is already on in this file), with a
  comment: a short poll keeps N=51 fast and maximises waiter pressure on the
  holder's release. The production cadence is covered by broker Cases 19/20.
  All existing assertions stay unchanged.
- Existing `--wait-secs 1/5` cases keep their meaning without the seam.
  Case 4's dead-anchor reclaim still happens on the immediate first attempt,
  because the pre-check says `dead`.

### 4. Docs / procedure
- **`.claude/skills/task-workflow/merge-broker.md`:**
  - Under `## Entry`, state that the broker re-tries about every 30 s
    (jittered), makes a final attempt at the deadline and prints one
    `WAITING` line per poll.
  - Add the **shell-tool timeout** rule, worded agent-neutrally per
    documentation conventions: `begin` can block for the whole
    `--wait-secs` budget plus the merge itself. If your shell tool enforces
    a per-command timeout, give this call one of at least
    `--wait-secs` + 120 s (240 s for 120, 420 s for 300).
  - Why this matters: a timeout that kills `begin` after it acquired the lock
    leaves a held reservation the agent does not know it owns. The same note
    goes on `begin / BUSY` "Wait and retry".
  - Regenerate the golden `tests/golden/procs/task-workflow/merge-broker-default.md`
    and any other golden whose render closure includes merge-broker.md, per
    `skill_authoring_conventions.md`. Run `aitask_skill_verify.sh`.
- `website/content/docs/concepts/locks.md` describes waiting only
  qualitatively ("progress reported while waiting"), so it needs no change.
  Re-check during implementation.
- `stale_lock.sh` is not edited.

### 5. Measure after
Rerun the measure_before harness against the working tree and record before
and after attempts/min in Final Implementation Notes. The expectation is about
1,200/min (the probe-reaching iterations of 20/s) before, and about 2–3/min
after, with zero guarded probes.

## Post-phase (risk mitigations)
- **post_shellcheck** — `shellcheck .aitask-scripts/aitask_merge_task.sh .aitask-scripts/lib/merge_lock.sh`
  and both test files clean. Then re-run the three suites plus
  `tests/test_stale_lock.sh` and `tests/test_create_email_lock.sh`, which
  share the core and must stay green.

## Verification
- `bash tests/test_merge_lock_broker.sh`, `bash tests/test_merge_lock_concurrency.sh`
  (Case 2 N=51) and `bash tests/test_merge_broker_rendered_verdicts.sh` pass on
  Linux.
- Case 22/22b is green, and red against a scratch copy with **both** the
  pre-probe and the instance gating removed. Neither variant hangs, because
  every rendezvous read is bounded.
- Case 22c is green, and red (`P` + `RETAINED`) against a scratch copy with
  the seam gating removed.
- Case 23 is green. The existing Case 8 (non-owner refusals) stays green.
- `./.aitask-scripts/aitask_skill_verify.sh` and the skill-render golden tests
  pass.
- **macOS: no host in-session.** Record this explicitly and create a
  manual-verification follow-up at Step 8c: Case 2 with all 51 merges landing
  and no leaked holder, and no Case 12/13 cascade. It must not be marked done
  here.
- Step 9 (Post-Implementation): current-branch mode, archive via
  `aitask_archive.sh 2167`, which deletes folded t2156.

## Risk

### Code-health risk: medium
- The waiter path of a load-bearing concurrency primitive changes. The
  unguarded pre-probe is a new read outside invariant 1's guard, and the
  instance-gated seam adds a cross-step global (`_merge_lock_dead_key`)
  between the pre-probe and the guarded verdict · severity: medium · →
  mitigation: inline pre-phase baseline_suites
- A `merge_lock_acquire` signature change could hit an unseen caller ·
  severity: low · → mitigation: inline post-phase post_shellcheck. Grep
  confirms `cmd_begin` is the sole caller.

### Goal-achievement risk: medium
- macOS (where t2156 reproduced) cannot be verified in-session · severity:
  medium · → mitigation: TBD (handled by the Step 8c manual-verification
  follow-up, not a risk mitigation)
- The red proof of the release fix could be vacuous if the rendezvous does not
  actually park the waiter inside or outside the guard as claimed · severity:
  low · → mitigation: TBD (built into plan step 3: Case 22b plus the recorded
  red run against a scratch copy)

Reassessed after the inline confirmations: levels unchanged (code-health
medium; goal-achievement medium, held there by the macOS gap).

### Planned mitigations
- timing: pre-phase | name: baseline_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — waiter-path change in a load-bearing primitive | desc: run the three merge suites on the untouched tree and record pass counts before editing
- timing: post-phase | name: post_shellcheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — signature change / shared-core collateral | desc: shellcheck changed scripts+tests, re-run merge suites plus test_stale_lock.sh and test_create_email_lock.sh

## Post-Review Changes

### Change Request 1 (2026-10-30 11:40)
- **Requested by user:** `AIT_MERGE_LOCK_POLL_MS` passed `^[0-9]+$` and reached bash arithmetic raw. `08` aborted begin with "value too great for base" (exit 1, no verdict), and `0500` was read as octal (320 ms).
- **Changes made:**
  - `_seam_poll_ms` now length-bounds the value to `^[0-9]{1,7}$` (a 20-digit value would otherwise wrap) and normalises it with `$(( 10#$v ))` before use. The warn prints the normalised value.
  - Broker Case 21 adds `08` and `0500`: exit 0, `BUSY`, read as decimal. It also adds an over-long value, which is ignored and gets the production cadence.
  - Mutant M4 (the pre-fix seam) fails those 5 new asserts, reproducing `08` → exit 1 with no verdict.
- **Files affected:** `.aitask-scripts/aitask_merge_task.sh`, `tests/test_merge_lock_broker.sh`

## Final Implementation Notes
- **Actual work done:**
  - `lib/merge_lock.sh`:
    - `merge_lock_acquire` is now ONE attempt: an unguarded pre-probe, then `stale_lock_acquire "$dir" 3 0.05`.
    - New helpers `_merge_lock_instance_key` (builtin `read`, no fork) and `merge_lock_poll_delay_ms` (sets a global; jitter range [0.75, 1.25] × base).
    - `_merge_lock_liveness_seam` is instance-gated on `_merge_lock_dead_key`.
    - Constants: `_MERGE_LOCK_POLL_SECS=30`, `_MERGE_LOCK_ATTEMPT_RETRIES=3`, `_MERGE_LOCK_ATTEMPT_SLEEP=0.05`.
    - Header: delta 4 rewritten, and delta 6 added for the two-layer starvation fix.
  - `aitask_merge_task.sh`:
    - `cmd_begin` uses the clamped jittered poll loop.
    - `_begin_attempt` is one acquire plus the same-owner `merge_lock_authorize` re-entry.
    - New `_seam_poll_ms`: `AIT_MERGE_LOCK_POLL_MS`, marker-gated, length-bounded, base 10.
  - Tests:
    - Broker Cases 19–23 added (19 timeout clamp, 20 final attempt at the deadline, 21 seam gating plus leading zeros, 22/22b/22c starvation regressions with a bounded FIFO rendezvous, 23 same-owner re-entry).
    - Concurrency Case 2 now runs with `AIT_MERGE_LOCK_POLL_MS=500`.
  - Docs: `merge-broker.md` documents the cadence and the shell-timeout rule (`--wait-secs` + 120 s). The golden and the 3 committed `remote` prerenders are regenerated.
- **Measurements:** one waiter against a live holder, 60 s, counting xtrace lines.
  - Before (HEAD via `git archive`): 1,043 `lock_holder_liveness` probes and 1,043 guard takes in 61 s (about 1,025/min, all under the guard), 26 WAITING lines.
  - After: 4 probes in 60 s (all unguarded), 0 guard takes, 3 WAITING lines.
- **Test results (Linux):**
  - Baseline before any edit: broker 100/100, concurrency 30/30, rendered-verdicts 25/25.
  - After: broker 135/135, concurrency 30/30 (Case 2: 51/51 merges, lock FREE afterwards, 7 s), rendered-verdicts 25/25, `test_stale_lock.sh` 134/134, `test_create_email_lock.sh` 78/78, `test_skill_render_task_workflow.sh` 361/361, `aitask_skill_verify.sh` OK.
  - shellcheck `-x` is clean. Only the pre-existing SC1091 info notes remain.
- **Red controls (isolated scratch copies of the working tree; none hung):**
  - M1, pre-probe and gating both removed (the t2156 defect): fails 22b (guard held), 22 (`RETAINED:release_failed`), and 22c (`P` + `RETAINED`).
  - M2, gating removed only: fails 22c only (`P` + `RETAINED`), the review's finding.
  - M3, pre-probe removed only: fails 22's precondition (`D`), plus Case 4. Without the pre-probe no dead key is ever set, so a dead holder is never reclaimed; the pre-probe is load-bearing for reclaim too.
  - M4, the pre-fix seam parser: fails the 5 new leading-zero / over-long asserts in Case 21.
- **Deviations from plan:**
  - Case 22's holder acquires and releases through the broker (`begin`/`finish`), not through `merge_lock_acquire`/`merge_lock_release`. That is end-to-end and stronger.
  - The FIFOs use fixed fds (5–8) instead of `exec {fd}<>`, because the framework's floor is bash 4.0 and `{fd}` needs 4.1.
  - FIFO names are prefixed `fifo22*`: the first draft's `r22` collided with `new_repo r22`'s directory.
  - When the pre-probe sees the holder key change during the probe, the attempt returns busy instead of entering the core (nothing to decide).
- **Issues encountered:**
  - The FIFO/repo name collision above, caught on the first run (instant TIMEOUT from a bad fd).
  - Review: leading-zero and octal handling of `AIT_MERGE_LOCK_POLL_MS`, fixed in Change Request 1.
- **Key decisions:**
  - Poll base 30 s with ±25% jitter.
  - The release fix lives entirely in the merge-lock adapter (`stale_lock.sh` is untouched, so its other callers keep their short polls and 40×50 ms release budget).
  - Same-session re-entry is now immediate instead of after the whole budget.
  - **macOS was NOT verified in-session** (no host); it goes to a manual-verification follow-up.
- **Upstream defects identified:** None

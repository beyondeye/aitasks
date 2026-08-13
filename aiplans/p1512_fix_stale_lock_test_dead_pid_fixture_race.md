---
Task: t1512_fix_stale_lock_test_dead_pid_fixture_race.md
Worktree: (none — current-branch mode, profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1512 — Fix the `test_stale_lock.sh` dead-PID fixture race

## Context

`tests/test_stale_lock.sh:111-113` builds its dead-PID fixture as
`sleep 60 &` / `kill "$dead_pid"` / `wait "$dead_pid"`. The `kill` fires
microseconds after `&`, inside bash's fork→exec window, where the signal can be
lost. The `wait` is load-bearing — only reaping makes the PID answer `kill -0`
with failure, since a zombie still answers success — so when the signal is
dropped the suite blocks for the child's full 60 s.

This is the same construction t1507 removed from `tests/test_registry_lock.sh`
(case 3). t1512 was spawned from t1507's Step 8b review as the one remaining
genuine instance found by that task's tree-wide sweep.

**The defect reproduced live on this box during planning** — this is not a
theoretical race:

```
$ time bash tests/test_stale_lock.sh
Results: 79/79 passed, 0 failed
real 1m2.805s   user 0m0.174s   sys 0m0.132s
```

The file header documents `Expected runtime: ~10s`. 62 s wall against 0.17 s of
user CPU is the lost-`kill` → blocked-`wait` signature: near-zero CPU rules out
spinning and points at a blocked `wait`. The suite passes — slowly — exactly as
the task predicted.

**Intended outcome:** the fixture becomes deterministic, the file returns to its
documented ~10 s runtime, and the anti-pattern's rationale lives in exactly one
place instead of three drifting copies.

## Approach

`dead_pid_fixture` already exists in **two** files, and its rationale comment has
already drifted (6 lines in `test_registry_lock.sh:76-82`, 3 lines in
`test_registry_lock_single_winner.sh:69-72`). Rather than add a third copy,
promote it to a shared test lib — same granularity as the existing 14-line
`tests/lib/venv_python.sh`.

### Step 1 — New file `tests/lib/proc_fixtures.sh`

Process-fixture helpers for the shell test suite, with an idempotent load guard
matching the `venv_python.sh` pattern:

```bash
#!/usr/bin/env bash
# tests/lib/proc_fixtures.sh — process fixtures for the shell test suite.
#
# Source via the absolute $PROJECT_DIR path, alongside tests/lib/asserts.sh:
#     . "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

if [[ -z "${_AIT_PROC_FIXTURES_LOADED:-}" ]]; then
    _AIT_PROC_FIXTURES_LOADED=1

    # A PID that has already exited AND been reaped. Command substitution waits
    # for the child, so there is no zombie — `kill -0` succeeds on a zombie, so
    # only a reaped PID answers with failure — and there is no signal to lose.
    #
    # Do NOT write this as `sleep 60 & dead_pid=$!; kill "$dead_pid"; wait
    # "$dead_pid"`. That `kill` fires microseconds after `&`, inside bash's
    # fork->exec window, where the signal can be dropped; the load-bearing
    # `wait` then blocks for the child's full 60s. Observed live in t1507
    # (2m04s wall against 0.2s of CPU) and again in t1512 (62s vs a documented
    # ~10s). Such a construction passes only by scheduling luck.
    dead_pid_fixture() { bash -c 'echo $$'; }
fi
```

### Step 2 — Fix the racy fixture in `tests/test_stale_lock.sh`

Source the lib next to the existing `asserts.sh` source (line 19):

```bash
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"
```

Replace lines 111-113 (`--- dead-PID holder is reclaimed with warn ---`):

```bash
sleep 60 &
dead_pid=$!
kill "$dead_pid" 2>/dev/null; wait "$dead_pid" 2>/dev/null
```

with:

```bash
dead_pid="$(dead_pid_fixture)"
```

Nothing else in that block changes — the assertion at line 123 still interpolates
`$dead_pid` into `"Reclaiming dead lock from dead holder pid $dead_pid"`, which a
reaped PID satisfies identically.

### Step 3 — De-duplicate the two existing copies

In `tests/test_registry_lock.sh` and `tests/test_registry_lock_single_winner.sh`:
delete the local `dead_pid_fixture` definition and its comment block, and add the
`proc_fixtures.sh` source line next to the existing `asserts.sh` source (lines 33
and 29 respectively). Call sites are unchanged (7 uses and 2 uses).

### Step 4 — Record the re-sweep result

The task asks for a tree-wide re-sweep. **It has already been run during
planning** — the result is recorded here so the requirement is closed, not
deferred.

Sweep: every `sleep N &` under `tests/`, then every `kill` / `wait` within 12
lines. 17 background sleeps across 8 files. Findings:

| Site | Verdict |
|---|---|
| `test_stale_lock.sh:111` | **The defect.** Fixed by Step 2. |
| `test_agent_marks_concurrency.sh:105`, `test_gates_sync_registry.sh:390`, `test_registry_lock.sh:62/140/217/331`, `test_registry_lock_single_winner.sh:77`, `test_gate_lock_single_winner.sh:76`, `test_shadow_rejected.sh:57`, `test_crash_recovery_pid_anchor.sh:331/368/450/531/586` | **Safe — live-holder fixtures.** The `sleep` is *meant* to stay alive for the assertion; the `kill`/`wait` is teardown that runs only after a subprocess invocation and assertions have executed, far outside the fork→exec window. |
| `test_agent_marks_concurrency.sh:126` (`sleep 0 &` + `wait`) | **Safe — no `kill` at all.** `sleep 0` self-terminates, so there is no signal to lose. Left as-is; normalizing it to `dead_pid_fixture` is cosmetic and out of scope. |

No second genuine instance exists. A grep-based source guard was considered and
rejected: legitimate live-holder fixtures use the identical `sleep N &` … `kill`
token sequence, so any guard tight enough to avoid false positives is trivially
evaded by a blank line — the rationale comment in the shared lib is the durable
enforcement. (Consistent with the "docs over a narrow source scan guard" rule.)

## Verification

1. **Positive control already established.** Pre-fix baseline recorded above:
   62.8 s wall / 0.17 s user CPU, 79/79 passed.
2. **Fixture correctness** (already probed in planning — re-confirm after the
   move): `dead_pid_fixture` returns a PID for which `kill -0` fails, across
   several invocations.
3. **The fix**:
   ```bash
   time bash tests/test_stale_lock.sh
   ```
   Expect `79/79 passed, 0 failed` and wall time back near the documented ~10 s
   — the assertion count must not change, and the 60 s gap must be gone.
   Run it 3× to confirm the timing is stable rather than lucky.
4. **No regression in the de-duplicated files**:
   ```bash
   bash tests/test_registry_lock.sh
   bash tests/test_registry_lock_single_winner.sh
   ```
   Both must pass with their pre-change assertion counts (captured before
   editing, compared after).
5. **Lint**: `shellcheck tests/lib/proc_fixtures.sh`.
6. No runner collision to worry about: `run_all_python_tests.sh` discovers only
   `test_*.py`, and bash tests are run individually — a new `tests/lib/*.sh`
   is never auto-collected.

## Risk

### Code-health risk: low

- Removing the local `dead_pid_fixture` from two currently-passing test files
  could break them if the source path or ordering is wrong · severity: low ·
  → mitigation: Verification step 4
- No production code is touched; blast radius is 4 test-only files, and the
  change removes duplication rather than adding structure.

### Goal-achievement risk: low

- None identified. The defect was reproduced live, the replacement fixture was
  probed directly, and the re-sweep requirement is closed inside this plan with
  its evidence rather than deferred.

## Post-Implementation

Step 9 handles cleanup, gate verification (`risk_evaluated`), and archival.
Current-branch mode: no worktree or branch cleanup is required.

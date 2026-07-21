---
Task: t1188_fix_gate_lock_stale_reclaim_toctou.md
Base branch: main
plan_verified: []
---

# t1188 — Fix gate-lock stale-reclaim TOCTOU + archive_utils non-numeric-id crash

## Context

While building t1183's gate-lock characterization suite, one run showed a lost
ledger append (3/4 blocks). Code inspection identified the only in-script path
that can remove a live lock: in `acquire_gate_lock`
(`.aitask-scripts/aitask_gate.sh:80-88`), if the lock dir vanishes between the
`-d` check and `stat`, the `|| echo "0"` fallback maps the failure to epoch
mtime, computing age≈now → "stale" → `rmdir` of a lock another process may have
just re-acquired → double-hold → lost append. The same pattern exists in
`acquire_child_lock` (`.aitask-scripts/aitask_create.sh:314-338`).

Separately, `archive_path_for_id` (`.aitask-scripts/lib/archive_utils.sh:53`)
does `$(( task_id / 100 ))` on the raw id; a t-prefixed id (e.g.
`aitask_gate.sh status t1183`) makes bash treat `t1183` as a variable name and
crash the subshell with `t1183: unbound variable` noise under `set -u`, before
`resolve_task_file`'s friendly "No task file found" die.

## Fix 1 — TOCTOU-safe staleness check in both lock helpers

Files: `.aitask-scripts/aitask_gate.sh` (`acquire_gate_lock`, lines 71–92) and
`.aitask-scripts/aitask_create.sh` (`acquire_child_lock`, lines 314–338).
Same transformation in both (they differ only in lock-dir prefix, sleep
interval, and warn wording — preserve those):

Replace the staleness block inside the `while ! mkdir` loop:

```bash
if [[ -d "$lock_dir" ]]; then
    local lock_mtime lock_age
    if lock_mtime=$(stat -c %Y "$lock_dir" 2>/dev/null || stat -f %m "$lock_dir" 2>/dev/null); then
        lock_age=$(( $(date +%s) - lock_mtime ))
        if [[ "$lock_age" -gt 120 ]]; then
            # Single-winner reclaim: rename is atomic, so only one waiter
            # can claim the stale dir, and a lock re-acquired at this path
            # after the rename is never touched. Preflight rm clears any
            # quarantine dir leaked by a dead PID-reused process (mv onto
            # an existing dir would nest instead of replacing).
            local stale_dest="${lock_dir}.stale.$$"
            rm -rf "$stale_dest" 2>/dev/null || true
            if mv "$lock_dir" "$stale_dest" 2>/dev/null; then
                warn "Removing stale gate lock for $key (age: ${lock_age}s)"
                rmdir "$stale_dest" 2>/dev/null || true
            fi
            continue
        fi
    else
        # Lock vanished between -d and stat — retry mkdir immediately.
        continue
    fi
fi
sleep 0.3
```

Two changes vs the task's minimal suggested fix, stated explicitly:

1. **stat-fail → `continue`** (the suggested fix): a vanished dir is "lock
   released — retry mkdir now", never age≈∞. This closes the identified
   TOCTOU.
2. **`mv`-then-`rmdir` instead of bare `rmdir`** (small extension): with a
   *genuinely* stale lock and ≥2 waiters, both could pass the age check and the
   loser's unconditional `rmdir` could remove the lock the winner had already
   reclaimed-and-re-acquired — the same defect class through a different door.
   Atomic rename makes reclaim single-winner with a 2-line delta, keeps
   `release_gate_lock`/`release_child_lock` untouched (no files inside the lock
   dir, `rmdir` semantics preserved), and keeps characterization test 6 passing
   (the winner still warns and reclaims). A residual microsecond window remains
   (stat→mv against a release+re-acquire on a >120s-old lock); an owner-token
   scheme was **considered and rejected** — it cannot close that window either
   (check-then-remove is inherent to mkdir locks), and it would change release
   semantics (`rmdir` fails on non-empty dirs) and break the pinned test 6
   fixture. Crashed-winner leak of `<lock>.stale.<pid>` dirs in /tmp is
   harmless (never matches the lock path), and the preflight `rm -rf` of the
   PID-namespaced destination makes the quarantine collision-proof: only a
   dead prior process with a reused PID could have left that exact path, so
   removing it is safe, and `mv` then always creates a fresh destination
   instead of nesting into a stale one.

## Fix 2 — numeric guard in archive path helpers

File: `.aitask-scripts/lib/archive_utils.sh`.

- `archive_path_for_id()` (line 49): before the arithmetic, add
  `[[ "$task_id" =~ ^[0-9]+$ ]] || return 0` (empty output, rc 0 — callers do
  bare `$(...)` assignments under `set -e`, so a nonzero return would kill
  them).
- `_find_archive_for_task()` (line 153) and `_search_numbered_then_legacy()`
  (line 194): after `zst_path=$(archive_path_for_id ...)`, add
  `[[ -z "$zst_path" ]] && return 0` so the empty path can't degenerate into a
  relative `.tar.gz` probe.
- `search_archived_task()` in `.aitask-scripts/lib/archive_scan.sh` (lines
  116–133) has the same edge: it derives
  `gz_path="${zst_path%.tar.zst}.tar.gz"` from a possibly-empty `zst_path`.
  Wrap the two numbered-archive probes (`zst_path` + `gz_path` blocks) in
  `if [[ -n "$zst_path" ]]; then … fi`; the legacy fallback below them still
  runs (its `t<id>_` pattern simply matches nothing for a non-numeric id), so
  the function's `NOT_FOUND` contract is unchanged.

Out of scope: `archive_bundle`/`archive_dir` share the arithmetic but are only
called with filename-derived numeric ids (`aitask_zip_old.sh`,
`aitask_migrate_archives.sh`); no non-numeric path reaches them.

Result: `aitask_gate.sh status t1183` (and any non-numeric id) fails with only
the friendly `No task file found` die from `resolve_task_file`.

## Fix 3 — test extensions

`tests/test_gate_lock_characterization.sh`:

- **Test 3** (t-spelling tripwire): add
  `assert_not_contains "t-spelling resolve failure is noise-free" "unbound variable" "$out"`
  — per the task's AC ("extend test 3's assertion to require stderr free of
  'unbound variable' once fixed").
- **New test 6b** — stale-reclaim race hardening: fixture task `987657`
  (add to `make_task` loop and `LOCK_DIRS`); `mkdir` its lock dir,
  `touch -t 202001010000` it, launch **2 concurrent** `append` contenders with
  per-contender stderr logs, `wait`, then assert: marker_count == 2, each
  attempt present exactly once, lock dir released, and the stderr logs contain
  ≥1 "Removing stale gate lock" warn (dump logs on anomaly, as tests 1/4b do).
  Extend `cleanup()` to also `rm -rf "${d}.stale."*` for each lock dir.
- **New test 7** — deterministic vanished-dir stat-failure path (the original
  TOCTOU trigger, directly): fixture task `987658`. Build a `stat` shim at
  `$TMP/bin/stat` placed first in PATH for this one invocation:

  ```sh
  #!/bin/sh
  case "$*" in
    *aitask_gate_lock_987658*) rmdir /tmp/aitask_gate_lock_987658 2>/dev/null; exit 1 ;;
    *) exec /usr/bin/stat "$@" ;;
  esac
  ```

  Pre-create the lock dir with a **fresh** mtime, then run
  `PATH="$TMP/bin:$PATH" append 987658 …`: `mkdir` fails, `-d` succeeds, the
  shim removes the dir and fails both `stat` calls — exactly the observed
  race. Assert: append **succeeds**, the ledger block lands, and stderr does
  **NOT** contain "Removing stale gate lock" (fixed code retries `mkdir`
  immediately; the old `|| echo "0"` fallback would classify age≈now as stale
  and warn). `stat` appears only once in `aitask_gate.sh` (the staleness
  check), so the shim cannot perturb anything else; the resolve-real-stat
  branch keeps any other caller (e.g. test harness helpers) working.

`tests/test_parallel_child_create.sh`:

- **New test 3b** — mirrored deterministic stat-failure test for
  `acquire_child_lock` (so a wrong edit to the mirrored helper can't hide
  behind the gate-lock tests): pre-create `/tmp/aitask_child_lock_100` with a
  **fresh** mtime, build the same `stat` shim keyed on
  `*aitask_child_lock_100*` (rmdir + exit 1; pass-through otherwise), and run
  the Test-3-style `--batch --parent 100 --commit` create with
  `PATH="$shim_dir:$PATH"`. Assert: creation succeeds, the child file exists,
  and output does **NOT** contain "Removing stale child lock". `stat` appears
  only once in `aitask_create.sh` (the staleness check at line 329), and the
  shim passes every other invocation through, so helper scripts and git
  subprocesses that inherit the PATH are unaffected. Resolve the real stat
  path (`command -v stat`) **before** prepending the shim dir and embed it in
  the shim (don't hardcode `/usr/bin/stat` — this suite has macOS fallbacks).
  Apply the same real-stat-resolution detail to the gate-lock test 7 shim.

`tests/test_archive_utils.sh`:

- Group C: `assert_eq "path(non-numeric) -> empty" "" "$(archive_path_for_id t1183 "archived")"`.
- Group F: same-shaped assertion for `_find_archive_for_task t1183 <dir>` → empty.

`tests/test_archive_scan.sh`:

- Add an assertion that `search_archived_task t1183 <archived_dir>` emits
  `NOT_FOUND` with no `unbound variable` stderr noise (covers the
  `archive_scan.sh` guard).

## Risk

### Code-health risk: medium
- The two lock helpers sit on load-bearing concurrent-writer paths (gate ledger
  appends, child creation); a subtle regression in the retry loop would surface
  as rare flakes, not deterministic failures · severity: medium · → mitigation:
  existing t1183 characterization suite (tests 1, 2a/2b, 4, 4b, 5, 6 pinned) +
  new test 6b + bounded soak in verification
- The stale-reclaim mv/rm dance is new concurrency-adjacent code; a mistake
  there would surface only when a genuinely stale lock meets multiple waiters ·
  severity: low · → mitigation: test 6b exercises exactly that scenario
  deterministically (pre-aged lock + 2 contenders)

### Goal-achievement risk: low
- The original lost-append anomaly was observed once and never reproduced
  (150+ soak rounds); the fix closes the only identified in-script live-lock
  removal path but cannot be proven to have caused that specific anomaly ·
  severity: low · → mitigation: tests 1/4b now dump contender stderr on
  anomaly, so any recurrence is diagnosable

## Verification

1. `bash tests/test_gate_lock_characterization.sh` — all tests incl. new 6b
   (stale-reclaim race), new 7 (deterministic stat-fail path via PATH shim),
   and extended test 3 pass.
2. Bounded soak: run the suite 5 consecutive rounds — no anomaly, no DIAG
   output (quantified bound, not an open-ended soak).
3. `bash tests/test_archive_utils.sh` and `bash tests/test_archive_scan.sh` —
   including the new non-numeric assertions.
4. `bash tests/test_parallel_child_create.sh` — covers `acquire_child_lock`
   incl. its existing stale-lock reclaim case (line ~178) and the new
   mirrored stat-shim test 3b.
5. `./.aitask-scripts/aitask_gate.sh status t1183` → stderr free of
   "unbound variable", exits with the friendly resolver error only.
6. `shellcheck .aitask-scripts/aitask_gate.sh .aitask-scripts/aitask_create.sh .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/archive_scan.sh` — no new findings.

Then proceed to Step 9 (Post-Implementation) for gates, archival, and cleanup
per the task-workflow skill.

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. TOCTOU-safe staleness
  check in `acquire_gate_lock` (`.aitask-scripts/aitask_gate.sh`) and
  `acquire_child_lock` (`.aitask-scripts/aitask_create.sh`): stat failure now
  means "lock vanished — retry mkdir immediately", and stale reclaim goes
  through an atomic `mv` to a PID-namespaced quarantine (preflight `rm -rf`
  prevents nesting into a leaked dir), so reclaim is single-winner and release
  semantics are untouched. Numeric guard in `archive_path_for_id`
  (`lib/archive_utils.sh`) plus empty-path guards in `_find_archive_for_task`,
  `_search_numbered_then_legacy`, and `search_archived_task`
  (`lib/archive_scan.sh`). Tests: extended characterization test 3
  (no "unbound variable" noise), new test 6b (stale reclaim under contention),
  new test 7 and parallel-child-create test 3b (deterministic vanished-dir
  stat-failure via a PATH `stat` shim keyed on the lock path, real stat
  resolved before shimming), non-numeric assertions in `test_archive_utils.sh`
  (Groups C/F) and `test_archive_scan.sh` (Test 10).
- **Deviations from plan:** One shape adjustment: the plan's
  `[[ -z "$zst_path" ]] && return 0` guard in `_search_numbered_then_legacy`
  would have skipped that function's legacy-archive fallback, so the numbered
  probes were wrapped in `if [[ -n "$zst_path" ]]` instead — same treatment as
  `search_archived_task`, legacy fallback preserved. `_find_archive_for_task`
  kept the early return (it has no legacy fallback).
- **Issues encountered:** None — all suites passed first run: characterization
  46/46 (plus a clean 5-round soak, no DIAG), archive_utils 48/48,
  archive_scan 25/25, parallel_child_create 24/24. Shellcheck reports only
  pre-existing info/style findings in untouched lines.
- **Key decisions:** Owner-token staleness was considered and rejected
  (documented in the plan): it cannot close the residual check-then-remove
  window inherent to mkdir locks, and it would change release semantics
  (`rmdir` fails on non-empty dirs) and break the pinned test 6 fixture. The
  atomic-rename reclaim was added beyond the task's minimal suggested fix
  because the two-waiter reclaim race is the same defect class (removing a
  lock another process just re-acquired) through a different door.
- **Upstream defects identified:** None

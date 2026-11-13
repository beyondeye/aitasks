---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tests, test_infrastructure, tmp_cleanup]
created_at: 2026-11-13 11:41
updated_at: 2026-11-13 11:41
---

## Context

t2290 added `tests/lib/tmpdir_guard.sh`. It runs a test phase under a private
per-run `TMPDIR` (`ait_<label>_<pid>_XXXXXX`), reports leftovers and removes
the dir on normal exit and on INT/TERM/HUP. On a signal it first stops the
phase's own process group.

A **SIGKILLed** guarding shell runs no handler, so its guard dir stays behind.
The phase's process group (pytest/xdist workers, nested test shells) may also
outlive it. Today `tmpdir_guard_begin` only REPORTS such dirs (owner pid gone)
and never deletes them. That was a deliberate scope cut in t2290: deleting
safely needs liveness evidence for possibly still-running workers.

## Goal

Reclaim those dirs automatically, deleting one only with positive evidence that
nothing still uses it. Otherwise retain it and report the reason.

## Design sketch (from the t2290 review)

- Per-run metadata in a sibling file `<dir>.meta`, outside the guarded dir so
  it is never reported as a leftover. It holds the owner pid and one
  `pgid:<n>` line per phase. `tmpdir_guard_end` removes it with the dir.
- Remove a candidate only when ALL of these hold:
  1. it is older than 60 min;
  2. its `.meta` parses (otherwise retain);
  3. the owner pid is dead;
  4. every recorded pgid has no live member (`kill -0 -- -<pgid>`); a reused
     pgid reads as alive, which is the fail-safe direction;
  5. no process has its cwd or an open fd under the dir: a `/proc/*/cwd` and
     `/proc/*/fd/*` scan of own-uid processes, or `lsof +D` without `/proc`.
     When neither is available, retain (`liveness unverifiable`).
- Retained dirs are reported with a reason: `owner alive` / `pgid N alive` /
  `in use by pid M` / `no meta` / `liveness unverifiable`.
- Residual, to document: a process with no fd and no cwd in the dir, outside
  every recorded pgid, that will later write there by path name, cannot be
  detected.

## Tests (extend tests/test_tmpdir_guard.sh)

Age dirs with `touch -d '2 hours ago'`. Cases:
- dead owner with dead pgids is swept;
- live owner is retained;
- **dead wrapper plus a surviving `setsid` writer whose cwd is the dir**:
  retained with `in use by pid`, and swept once the writer is killed;
- live recorded pgid is retained;
- no `.meta` is retained;
- a dir younger than 60 min is untouched;
- `/proc` hidden via a test seam plus no `lsof` gives `liveness unverifiable`.

## References

- `tests/lib/tmpdir_guard.sh` (the "NOT COVERED" header section)
- `aiplans/archived/p2290_stop_tests_and_helpers_leaking_tmp_dirs.md`

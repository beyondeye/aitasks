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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2301** id=2026-11-22T09:45:03Z.f21f64ff10e850adafcc51c1 from=t2301 from_verified=yes at=2026-11-22T09:45:03Z base=d5680956ecce76e61ba2456f933d0e1056605205 base_branch=main dirty=yes host=omg16
>
> | t2301 (commit d5680956e) implemented this task's goal: tmpdir_guard_begin now
> | reclaims guard dirs left by SIGKILLed runs only on positive evidence, and
> | otherwise keeps them and reports a reason.
> | 
> | Covered (tests/lib/tmpdir_guard.sh, KILLED RUNS header; tests in
> | tests/test_tmpdir_guard.sh):
> | - per-run metadata in a private control dir .<dirname>.ait_guard_meta/meta
> |   (not <dir>.meta as sketched here);
> | - dead owner by pid + start-time token; every recorded pgid empty;
> | - no process with cwd/fd/environ/cmdline under the dir (/proc; lsof +w as
> |   root otherwise); complete proc view (hidepid);
> | - nothing mounted below; no socket file inside;
> | - retained dirs reported with reasons (no-metadata, owner-unverified,
> |   pgid-live, held:<pid>, holder-unverified:<n>, mounted, socket, ...).
> | 
> | Differences from this task's sketch:
> | 1. no 60-minute age threshold — t2301 relies on evidence instead;
> | 2. no dedicated setsid-writer test (a writer that left the pgid is caught by
> |    the cwd/fd/environ holder scan, cases u/v);
> | 3. the "no /proc and no lsof" path (verdict no-holder-scan) exists but has
> |    no test.
> | 
> | Claim, as of d5680956e: this task can likely be closed as covered by t2301,
> | or narrowed to the differences above. Advisory only.

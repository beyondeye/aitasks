---
priority: medium
effort: medium
depends: [1696]
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
created_at: 2026-09-04 17:02
updated_at: 2026-09-04 17:02
---

## Problem

The `aitask-locks` branch is not self-cleaning. Locks whose owning process is
long dead stay on the branch indefinitely and keep counting as "held" for every
consumer that reads them.

Measured on `omg16`, 2026-09-04 — 12 locks on the branch, **9 of them stale**
(pid absent from `/proc`):

```
t259      locked 2026-02-26 17:27   STALE (pid dead)   <- 6 months
t1555_2   locked 2026-08-18 11:29   STALE
t1576     locked 2026-08-18 18:12   STALE
t1687     locked 2026-09-02 14:25   STALE
t1688     locked 2026-09-02 14:50   STALE
t1692     locked 2026-09-02 17:17   STALE
t1696     locked 2026-09-02 22:31   STALE
t1697     locked 2026-09-02 22:33   STALE
t1699     locked 2026-09-03 09:37   STALE  (released by hand during this session)
```

Only 3 were held by live `/aitask-pick` sessions.

## Why it matters beyond tidiness

A stale lock is not inert — it changes framework behaviour:

- **`aitask_sync.sh`**: the pre-sync sweep refuses to commit a file whose task is
  locked, adding it to `PROTECTED_DIRTY`. With the remote ahead, that triggers
  the `protected_dirty` deferral (`aitask_sync.sh:1278`) and sync exits 0 without
  rebasing. A dead session's lock can therefore block sync **forever**, and looks
  identical to a live session's lock while doing it.
- **`ait lock`**: exit 14 ("liveness could not be established") for another
  session of the user's own, requiring `--unlock` or `--force` by hand.
- It inflates the blocked set that t1696's diverged-state deadlock feeds on (see
  the "Related: stale locks widen the blocked set" section there).

`t1699`'s stale lock was a live contributor to the `protected_dirty` deferral
observed in t1696 on this box.

## Note on liveness detection

The lock record already carries everything a reaper needs — `pid`,
`pid_starttime`, `pid_starttime_kind`, `hostname` — and `aitask_lock.sh` already
knows how to evaluate them (that is what distinguishes exit 13 from exit 14).
Checking `pid_starttime` as well as `pid` matters: a bare pid check calls a
reused pid live. What is missing is a caller that *acts* on the verdict.

## Constraints

- **Only same-host locks are decidable.** `hostname` is recorded; a lock from a
  different host cannot have its pid probed and must never be reaped on liveness
  grounds. Any age-based rule for those is a separate decision, not an
  assumption to slip in.
- Must fail closed: unverifiable liveness means "leave it", never "reap it".
  Compare `ait lock --list --batch`, which already distinguishes a trustworthy
  snapshot (`LOCKS_OK`) from an unreadable one.
- Reaping races a session that is starting up; whatever is chosen needs the same
  care as the existing lock acquisition path.

## Open questions (not prescriptive)

- Automatic on some existing path (lock acquisition, `ait sync` pre-sweep,
  board/monitor startup) vs. an explicit `ait lock --reap` the user runs?
- Should `aitask_sync.sh`'s sweep treat a *provably dead* same-host lock as
  unlocked, so a stale lock stops producing `protected_dirty` even before any
  reaping lands? That alone would remove the sync-blocking consequence.
- Should `ait lock --list` mark staleness in its output? Today a dead lock and a
  live one are visually identical, which is why 9 of these accumulated unnoticed.

## Acceptance criteria

1. A same-host lock whose pid is dead (or whose `pid_starttime` does not match) is
   distinguishable from a live one through a supported interface, not only by
   reading YAML by hand.
2. A stale same-host lock no longer causes `aitask_sync.sh` to add its files to
   `PROTECTED_DIRTY`.
3. A lock on a different host, or one whose liveness cannot be established, is
   left alone — with a test that pins the fail-closed direction.
4. Reaping (however triggered) is safe against a concurrently starting session.

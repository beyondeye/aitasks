---
Task: t1073_fix_project_group_loss_unlocked_registry_race.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Fix project-group loss from unlocked concurrent registry rewrites (t1073)

## Context

Project-group assignments (settings TUI "Project Groups" tab) silently reset to
ungrouped after a PC restart — all at once, permanently. Root cause (confirmed by
reproduction during exploration):

- Group membership lives **only** in `~/.config/aitasks/projects.yaml` (the 5th
  `project_group` field). Neither repo mirrors it in `project_config.yaml`, so
  once the registry value is lost there is no config-fallback to heal it.
- Every registry mutation in `.aitask-scripts/aitask_projects.sh` is an
  **unlocked whole-file read-modify-write**: read the entire file
  (`list_registry_entries` → Python parser), rebuild, `atomic_write` (temp +
  `mv`). `atomic_write` prevents *torn* files but does **nothing** about
  **lost updates** between two processes.
- `cmd_add` fires **automatically and silently** on every tmux session bootstrap
  (`.aitask-scripts/lib/tmux_bootstrap.sh:106` →
  `aitask_projects.sh add "$root" >/dev/null 2>&1 || true`). The reporter's
  workflow (`ait ide` in aitasks, then fanning out other-project TUIs via the
  TUI switcher's `_ensure_session_live`) bursts many of these concurrently,
  especially right after a restart.

**Reproduced:** with a temp registry, 10 concurrent `aitask_projects.sh add`
calls (5 on `aitasks`) left `aitasks`'s `last_opened` at its original value —
all 5 updates silently lost. A bootstrap `add` that snapshotted the registry
before groups were assigned and committed its whole-file view afterward
overwrites **all** groups in one write, matching the "all assignments wiped"
symptom.

## Goal / outcome

Make every registry mutation safe under concurrency so a bootstrap `add` (or any
writer) can never clobber a concurrent writer's changes — groups and
`last_opened` bumps all survive a restart burst.

## Approach (recommended)

Serialize the read-modify-write critical section of **every** mutating verb in
`aitask_projects.sh` behind a **portable `mkdir`-based mutex** on a lock
directory derived from the registry path. `mkdir` is atomic on POSIX and needs
no extra binary — `flock` is intentionally avoided because it is not installed
by default on macOS/BSD, which the framework supports
(`aidocs/framework/shell_conventions.md`, `sed_macos_issues.md`).

**Design invariants (from review):**
1. **Never proceed unlocked.** A mutation either holds exclusive ownership or
   **fails safely** — it does not write. On acquire failure the verb `die`s; the
   silent bootstrap `add` is invoked as `… >/dev/null 2>&1 || true`
   (`tmux_bootstrap.sh:106`), so a `die` there is already swallowed and simply
   skips the harmless `last_opened` refresh — **no clobber, no unlocked write**.
2. **Owner-token release.** Release deletes the lock **only if this process still
   owns it** (its unique token still matches the on-disk token). If our lock was
   stolen (we were presumed dead), we never delete the current owner's lock.
3. **Steal only a provably-dead holder.** A held lock is stolen **only** when its
   recorded PID is dead (`kill -0` fails) — **never** based on age. A live but
   slow holder is waited on, then we fail safely on timeout. Stealing is atomic
   (rename-then-remove) so two stealers can't both evict and double-own.

Place the primitive in a small **sourceable lib** `.aitask-scripts/lib/registry_lock.sh`
(double-source guard `_AIT_REGISTRY_LOCK_LOADED`), sourced by `aitask_projects.sh`.
A lib (not inline) is chosen specifically so the primitive can be **unit-tested in
isolation** (the reviewer asked for timeout/stale/own-release tests). It is **not**
added to `./ait`'s source-on-startup chain (only `aitask_projects.sh` sources it,
from its own real `SCRIPT_DIR`), so `tests/lib/test_scaffold.sh` needs no change.

### File 1 — `.aitask-scripts/lib/registry_lock.sh` (new)

Functions are parameterized by lock-dir path so tests can point them at a temp
dir. One active lock per process (globals `_registry_lock_dir` / `_registry_lock_token`).

```bash
registry_lock_acquire() {        # <lock_dir> [timeout_secs=10]  → 0 held / 1 busy
    local dir="$1" timeout="${2:-10}"
    local token="$$-${RANDOM}-${RANDOM}-$(date +%s)"   # unique per acquisition
    local deadline=$(( $(date +%s) + timeout ))
    while ! mkdir "$dir" 2>/dev/null; do
        local holder; holder=$(cat "$dir/pid" 2>/dev/null || echo "")
        # Steal ONLY a provably-dead holder, atomically (rename then remove so
        # two stealers can't both evict a live lock). Missing/empty pid =
        # just-acquired holder mid-write → treat as live, wait (never steal).
        if [[ -n "$holder" ]] && ! kill -0 "$holder" 2>/dev/null; then
            local dead="$dir.dead.$$.$RANDOM"
            mv "$dir" "$dead" 2>/dev/null && rm -rf "$dead"
            continue
        fi
        (( $(date +%s) >= deadline )) && return 1   # busy, live holder → FAIL SAFELY
        sleep 0.05
    done
    printf '%s\n' "$$"    > "$dir/pid"
    printf '%s\n' "$token" > "$dir/owner"
    _registry_lock_dir="$dir"; _registry_lock_token="$token"
    trap 'registry_lock_release "$_registry_lock_dir"' EXIT
    return 0
}

registry_lock_release() {        # <lock_dir>  — removes ONLY if we still own it
    local dir="$1"
    [[ -n "${_registry_lock_dir:-}" && "$dir" == "$_registry_lock_dir" ]] || return 0
    local on_disk; on_disk=$(cat "$dir/owner" 2>/dev/null || echo "")
    if [[ "$on_disk" == "$_registry_lock_token" ]]; then
        rm -rf "$dir" 2>/dev/null || true
    fi   # else: our lock was stolen — leave the current owner's lock intact
    _registry_lock_dir=""; _registry_lock_token=""
    trap - EXIT
}
```

No `stat`/mtime shim is needed (age is never used) — one fewer portability
surface than the rejected design.

### File 2 — `.aitask-scripts/aitask_projects.sh`

**(a) Source the lib and define the lock-dir** (lock dir derives from
`REGISTRY_FILE`, so it follows `AITASKS_PROJECTS_INDEX` overrides):

```bash
source "$SCRIPT_DIR/lib/registry_lock.sh"
REGISTRY_LOCK_DIR="${REGISTRY_FILE}.lockd"
```

Each mutating verb wraps its critical section as:

```bash
registry_lock_acquire "$REGISTRY_LOCK_DIR" || die "Registry is locked by another ait process — try again."
# ... list_registry_entries → rebuild → atomic_write ...
registry_lock_release "$REGISTRY_LOCK_DIR"
```

The `EXIT` trap set in `acquire` guarantees release even if a `die` fires mid
critical-section.

**(b) Wrap each mutating verb's read→rebuild→write in the lock.** Acquire
immediately **before** the authoritative `list_registry_entries` that feeds the
write, release after `atomic_write`. The functions:

- `cmd_add` (the hot bootstrap path)
- `cmd_update` (repoint, ~line 445)
- `set_registry_group` (~line 731) — group set/unset
- `rename_registry_group` (~line 753)
- the `group sync` branch in `cmd_group` (~line 845)
- `cmd_remove` and `cmd_prune` — **acquire the lock only around the final
  mutate**, *after* their interactive `read -r` confirmation, and re-read the
  registry inside the lock. This avoids holding the mutex across a human-thinking
  prompt (which would stall concurrent bootstrap `add`s). The `EXIT` trap still
  guarantees release if the user aborts mid-write.

**(c) No-op write elision in `cmd_add`** (defensive, reduces churn): after
building `body`, if it is byte-identical to the current file, skip
`atomic_write`. This cuts the number of bootstrap rewrites during a restart
burst (the common case: `last_opened` already today, nothing changed), shrinking
the contention window. Safe — eliding an identical write is a pure no-op.

### File 3 — `tests/test_registry_lock.sh` (new) — unit tests of the primitive

Sources `lib/registry_lock.sh` directly and drives the functions against a temp
lock dir (no registry needed). Self-contained `assert_eq`/`assert` helpers,
PASS/FAIL summary, matching existing `tests/test_*.sh` style. Cases (the ones the
reviewer asked for):

1. **Basic acquire/release** — acquire succeeds (dir + `pid` + `owner` created);
   release removes the dir.
2. **Live holder → acquire FAILS, does not steal, does not proceed** — pre-create
   the lock dir with a `pid` of a **live** background process; `registry_lock_acquire
   "$dir" 1` returns **1** within ~the timeout, and the dir is **untouched** (not
   stolen). Asserts invariant #1 + #3.
3. **Dead holder → acquire STEALS** — pre-create the lock dir with a `pid` of a
   **dead** PID (start `sleep`, capture PID, kill it); acquire returns 0 and now
   owns the dir.
4. **Release does NOT delete another process's lock** — acquire (token A), then
   overwrite `$dir/owner` with a different token (simulating our lock having been
   stolen while we were presumed dead); call `registry_lock_release "$dir"` and
   assert the dir **still exists** (we must not delete the new owner's lock).
   Asserts invariant #2.
5. **EXIT trap releases own lock** — acquire in a subshell that exits; assert the
   dir is gone afterward.

### File 4 — `tests/test_registry_concurrency.sh` (new) — black-box, real entry point

Tests the outermost surface that can break (per testing conventions). Uses a temp
`AITASKS_PROJECTS_INDEX` and two throwaway dirs each with
`aitasks/metadata/project_config.yaml`. Cases:

1. **Concurrent `add` preserves all groups** — seed registry with two entries
   both `project_group: team_a`; fire N concurrent `add`s for both repos; assert
   `project_group: team_a` count == 2 afterward.
2. **Concurrent `add` preserves all `last_opened` bumps** — assert every targeted
   entry's `last_opened` advanced (the exact failure reproduced in exploration:
   pre-fix this is lost — serialization guarantees all survive).
3. **`group set` racing bootstrap `add`s survives** — fire several `add`s
   concurrently with a `group set`; loop a handful of trials; assert the group
   persists every trial.

Cases 1–2 reproduce the demonstrated lost-update and **fail without the lock**;
they pass once mutations serialize.

### Linting / goldens

- `shellcheck .aitask-scripts/aitask_projects.sh .aitask-scripts/lib/registry_lock.sh` clean.
- No `.j2`/skill/closure surfaces touched → no goldens regeneration, no
  cross-agent skill port needed.

## Risk

### Code-health risk: medium
- Introduces a locking primitive into a hot, load-bearing path (bootstrap
  `cmd_add` runs on every session launch). A lock-primitive bug could deadlock or
  delete the wrong holder's lock. · severity: medium · → mitigation: handled
  in-task by the three review invariants — **fail-safe on timeout (never proceed
  unlocked)**, **owner-token release (delete only if still owner)**, **steal only
  a dead PID, atomically** — each directly covered by a `test_registry_lock.sh`
  case (live-holder-fails, dead-holder-steals, release-doesn't-delete-others).
- `EXIT` trap interaction: `aitask_projects.sh` must not already rely on a
  different `EXIT` trap. · severity: low · → mitigation: grep for an existing
  `trap … EXIT` before adding; the trap is set on acquire / cleared on release.
- PID reuse: a dead holder's PID reused by an unrelated live process blocks
  stealing → we fail safely (wait/timeout) rather than evict. · severity: low ·
  → mitigation: accepted — fail-safe is the correct conservative behavior; the
  unique owner token still prevents wrong-owner deletion.

### Goal-achievement risk: low
- The fix directly serializes the proven race; the concurrency test reproduces
  the demonstrated lost-update (fails pre-fix, passes post-fix), so delivery is
  verifiable. · severity: low · → mitigation: None needed.

### Planned mitigations
None — the identified code-health risks are mitigated **in-task** via the three
fail-safe invariants and proven by `tests/test_registry_lock.sh` (unit) +
`tests/test_registry_concurrency.sh` (black-box). No separate before/after tasks
warranted.

## Verification

1. `bash tests/test_registry_lock.sh` → PASS (basic, live-holder-fails,
   dead-holder-steals, release-doesn't-delete-others, EXIT-trap-release).
2. `bash tests/test_registry_concurrency.sh` → PASS (groups + `last_opened`
   survive concurrent `add`/`group set`).
3. Sanity that the concurrency test catches the bug: temporarily stub
   `registry_lock_acquire` to a no-op `return 0` (so writes proceed unserialized)
   → cases 1–2 FAIL; restore → PASS.
4. `shellcheck .aitask-scripts/aitask_projects.sh .aitask-scripts/lib/registry_lock.sh`
   → no new findings.
5. Manual smoke: against a temp `AITASKS_PROJECTS_INDEX`, run the exploration's
   10-concurrent-`add` loop and confirm both groups **and** both `last_opened`
   dates survive.
6. Existing registry tests still pass (e.g.
   `bash tests/test_registry_reader_parity.sh` and any `ait projects` tests) —
   the parser/serialization round-trip is unchanged.

## Post-implementation (Step 9)

Single-file code change + one new test on the current branch (no worktree).
Commit code as `bug: ... (t1073)`; commit plan via `./ait git`. Merge approval,
then archive t1073.

## Final Implementation Notes

- **Actual work done:** Added `.aitask-scripts/lib/registry_lock.sh` (portable
  `mkdir` mutex with the three fail-safe invariants) and wrapped every registry
  read-modify-write in `aitask_projects.sh` — `cmd_add`, `cmd_remove`,
  `cmd_update`, `set_registry_group`, `rename_registry_group`, and the
  `group sync` branch. Added no-op write elision to `cmd_add`. Added
  `tests/test_registry_lock.sh` (14 assertions) and
  `tests/test_registry_concurrency.sh` (black-box).
- **Deviations from plan:** `cmd_prune` needed no direct lock wrapping — it
  deletes via `cmd_remove --force`, which is now lock-wrapped (sequential
  acquire/release per removal, no nesting). Added `mkdir -p` of the lock dir's
  parent in `registry_lock_or_die` so a first-ever write (registry parent dir
  absent) can still acquire.
- **Issues encountered:** shellcheck flagged SC2155 (split `local` decl in the
  lib) and SC2154 (`_registry_lock_token` set by the sourced lib — silenced with
  a scoped disable in the test). Both resolved; only benign SC1091
  source-follow infos remain (pervasive repo-wide).
- **Key decisions:** `mkdir` mutex over `flock` (flock absent on macOS/BSD by
  default). Lock placed in a sourceable lib specifically so the primitive is
  unit-testable in isolation. Interactive verbs (`remove`/`prune`) acquire the
  lock only AFTER their confirmation prompt and re-read inside the lock, so the
  mutex is never held across human-thinking time.
- **Upstream defects identified:** None. The root cause (unlocked whole-file
  read-modify-write) was within this task's own scope (`aitask_projects.sh`);
  no separate pre-existing defect in another module was surfaced.

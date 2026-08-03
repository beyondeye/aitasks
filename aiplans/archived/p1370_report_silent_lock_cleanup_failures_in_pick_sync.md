---
Task: t1370_report_silent_lock_cleanup_failures_in_pick_sync.md
Worktree: (none — current-branch mode, profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# t1370 — Report silent lock-cleanup failures in pick sync

## Context

`sync_remote()` in `.aitask-scripts/aitask_pick_own.sh` is the pre-task-selection
step every pick / explore / fold / review / pr-import runs. Today it reads:

```bash
sync_remote() {
    task_sync
    "$SCRIPT_DIR/aitask_lock.sh" --cleanup 2>/dev/null || true
}
```

t1269 rewrote line 142 (`task_sync`) to classify its failure, expose
`TASK_SYNC_*` globals, warn on stderr, and surface `SYNC_FAILED:<reason>`.
**Line 143 was deliberately left out of that scope.** Both its stderr *and* its
exit status are discarded, so a failed stale-lock sweep is indistinguishable
from a successful one.

Lock cleanup is what releases locks abandoned by dead sessions. When it silently
fails, stale locks accumulate and the next pick reports `LOCK_FAILED` for a task
nobody is working on, pushing the user toward a force-unlock they should not
need. This is the mirror image of the bug t1269 fixed.

### What exploration found (all four reproduced in a scratch repo)

1. **`cleanup_locks()` already warns — nobody can hear it.**
   `aitask_lock.sh:448` calls `warn "Failed to push stale lock cleanup after
   $MAX_RETRIES attempts"`, which `2>/dev/null` throws away.

2. **`cleanup_locks()` aborts with exit 1 on the ordinary every-pick path.**
   `aitask_lock.sh:396`:
   ```bash
   lock_files=$(git ls-tree "$current_tree_hash" | grep '_lock\.yaml' | awk '{print $4}')
   ```
   The script runs `set -euo pipefail`. When the lock branch holds **no** lock
   files, `grep` exits 1, `pipefail` propagates it, and `set -e` kills the shell
   *before* the `[[ -z "$lock_files" ]]` guard on the next line can return 0.
   Verified end-to-end: `--init`, no locks → `rc=1`, no output. Removing
   `|| true` without fixing this would emit a warning on **every pick** in any
   project where nothing is currently locked.
   The same hazard exists at `aitask_lock.sh:406`
   (`tid=$(echo "$lf" | grep -oE '^t[0-9]+' | sed 's/t//')`) — one stray
   non-`t<N>` file on the lock branch aborts the sweep.

3. **Every failure path returns 0.** Verified: stale lock + a remote that
   rejects the push → 5 retries, warn, `rc=0`.

4. **The retry loop discards the real cause.** `aitask_lock.sh:443` is
   `git fetch origin "$BRANCH" --quiet 2>/dev/null || break`. Verified with a
   remote that rejects the push *and* becomes unreadable: the run took **0s**
   (a single push attempt), yet reported "Failed to push stale lock cleanup
   after 5 attempts" — the wrong diagnosis, with no connectivity hint.

**Intended outcome:** a failed sweep is loud and correctly classified, the pick
still proceeds (`aitask_pick_own.sh` exits 0 — cleanup stays best-effort), and
the success / nothing-to-do paths stay completely silent.

## Design decisions

**Contract:** `--cleanup` remains best-effort *for the caller* (never blocks a
pick) but becomes **honest about its own outcome** via exit codes. Unlike
t1269's in-process `TASK_SYNC_*` globals, cleanup runs in a **separate
process** — exit code + stderr are the return value.

**New `aitask_lock.sh --cleanup` exit contract:**

| Code | Meaning |
|------|---------|
| `0`  | Completed — no remote, branch absent, nothing stale, or all stale locks removed |
| `11` | The lock branch could not be **read** — initial fetch/rev-parse, or the mid-retry refresh. Names how many stale locks (if already identified) were left in place |
| `12` | The branch stayed readable, but the removal push was rejected on all `MAX_RETRIES` attempts |

`11` matches the script's existing `LOCK_ERROR:fetch_failed` / `die_code 11`
convention for "cannot reach origin" (`lock_branch_exists_on_remote`,
`aitask_lock.sh:57-72`). Splitting 11/12 on **read vs write** is what makes the
hint correct: 11 sends the user to connectivity recovery, 12 to a push retry.
Concern 4 above is precisely a case that today lands in the wrong bucket.

**Reuse:** fetch-failure disambiguation reuses the canonical classifier
`_task_push_classify` (`lib/task_utils.sh:440`, already sourced by
`aitask_lock.sh:26`), plus `_task_push_first_line` (`:423`) and
`_task_push_reason_hint` (`:477`) with its `$2` retry-command parameter — which
exists for exactly this reuse. Empirically verified git texts:

- branch absent → `fatal: couldn't find remote ref aitask-locks`
- unreachable → `does not appear to be a git repository` +
  `Could not read from remote repository.` → classifies `remote_unreachable`

`LC_ALL=C` must be pinned on these fetches: `task_utils.sh` applies it only
inside `_ait_data_git`, and `cleanup_locks` calls bare `git`.

**Rejected alternatives:**
- *Probe with `lock_branch_exists_on_remote` before fetching* — cleanly
  tri-state, but adds a second network round-trip to **every pick**. Classifying
  the single `git fetch`'s stderr gives the same answer for free.
- *Add a `LOCK_CLEANUP_FAILED:<reason>` token to `--sync` stdout* (symmetry with
  t1269's `SYNC_FAILED:`). Rejected: `SYNC_FAILED:` exists because the pick
  skill's Step 0c parses it. No skill would act on a cleanup token, so it buys
  nothing while forcing edits to SKILL.md + `.md.j2` + goldens across 3 agents ×
  4 profiles. A stderr warning meets the AC.
- *Keep `grep` and append `|| true` to the pipeline* — works, but the awk form
  removes the whole class of failure rather than patching one instance
  (structural fix over fragile invariant).
- *Reuse `_task_push_reason_hint` for the `push_failed` case* — its nearest code
  (`diverged`) says "reconcile with `ait syncer`", which is **wrong** for the
  lock branch (the syncer reconciles the task-data branch). Partial reuse only,
  where the failure mode genuinely overlaps.

**Silence policy** (mirrors `_task_push_warn` / `_task_sync_warn`): warn only
when something is actually at risk. This runs on every pick.

## Implementation

### 1. `.aitask-scripts/aitask_lock.sh` — remove the pipefail aborts

**1a. Lock-file listing** (`:396`) — drop `grep`; `awk` exits 0 on no match:

```bash
    local lock_files
    # awk, not grep: an empty lock branch makes `grep` exit 1, which under
    # `set -euo pipefail` kills the sweep before the emptiness guard below.
    lock_files=$(git ls-tree "$current_tree_hash" | awk '$4 ~ /_lock\.yaml$/ {print $4}')
```

**1b. Task-ID extraction** (`:404-406`) — same hazard; use parameter expansion,
no subprocess:

```bash
        # t109_lock.yaml -> 109. Parameter expansion, not a grep pipeline:
        # a stray non-t<N> file would make `grep -oE` exit 1 and abort.
        local tid="${lf#t}"
        tid="${tid%%_*}"
        [[ "$tid" =~ ^[0-9]+$ ]] || { debug "Skipping unrecognized lock file: $lf"; continue; }
```

### 2. `.aitask-scripts/aitask_lock.sh` — make `cleanup_locks()` honest

Document the contract above `cleanup_locks()` (`:380`):

```bash
# --- Cleanup: remove stale locks for archived tasks ---
#
# Best-effort for callers (aitask_pick_own.sh never lets it block a pick), but
# honest about its own outcome — a swallowed failure lets stale locks pile up
# until a later pick reports LOCK_FAILED for a task nobody is working on.
#
# Exit contract:
#   0   completed: no remote, lock branch absent, nothing stale, or all stale
#       locks removed
#   11  the lock branch could not be READ (initial fetch/rev-parse, or the
#       mid-retry refresh) — any identified stale locks were left in place
#   12  the branch stayed readable but the removal push was rejected on all
#       MAX_RETRIES attempts
```

Shared warn helper, placed just above `cleanup_locks()`:

```bash
# Internal: report a lock branch we could not read. Reuses the canonical push
# classifier so the wording matches task_sync's for the same git failure.
#   $1 = captured git stderr ("" when undeterminable)
#   $2 = stale locks already identified and left in place ("" when none/unknown)
_cleanup_warn_unreadable() {
    local git_err="${1:-}" stale_count="${2:-}" reason detail="" left
    reason="$(_task_push_classify "" "$git_err")"
    if [[ "$reason" == "unknown" && -n "$git_err" ]]; then
        detail=" (git: $(_task_push_first_line "$git_err"))"
    fi
    if [[ -n "$stale_count" && "$stale_count" != "0" ]]; then
        left="${stale_count} stale lock(s) left in place"
    else
        left="stale lock cleanup did not run"
    fi
    warn "could not read the '$BRANCH' lock branch — ${left}; $(_task_push_reason_hint "$reason" "./ait lock --cleanup")${detail}"
}
```

Replace the initial fetch block (`:386-389`):

```bash
    # Disambiguate "branch genuinely absent" (nothing to clean) from "cannot
    # read origin" (cleanup did not run). LC_ALL=C keeps git's message
    # parseable — task_utils.sh pins it only inside _ait_data_git.
    local fetch_err=""
    if ! fetch_err="$(LC_ALL=C git fetch origin "$BRANCH" --quiet 2>&1)"; then
        case "$fetch_err" in
            *"couldn't find remote ref"*|*"not our ref"*)
                debug "Lock branch '$BRANCH' not on remote — nothing to clean up"
                return 0
                ;;
        esac
        _cleanup_warn_unreadable "$fetch_err" ""
        return 11
    fi
```

Guard the two `rev-parse` calls (`:391-393`) — `parent_hash=` is unguarded today:

```bash
    local parent_hash current_tree_hash
    if ! parent_hash=$(git rev-parse "origin/$BRANCH" 2>/dev/null) ||
       ! current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}" 2>/dev/null); then
        _cleanup_warn_unreadable "" ""
        return 11
    fi
```

Rewrite the retry tail (`:430-449`) so a refresh failure is not misreported as
push exhaustion, and so the attempt count is truthful:

```bash
    local attempt=0

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))

        local new_tree_hash commit_hash_new
        new_tree_hash=$( { git ls-tree "$current_tree_hash" | grep -vE "	(${filter_pattern})$" || true; } | git mktree )
        commit_hash_new=$(echo "ait: Cleanup ${#stale_files[@]} stale lock(s)" | \
            git commit-tree "$new_tree_hash" -p "$parent_hash")

        if git push origin "$commit_hash_new:refs/heads/$BRANCH" 2>/dev/null; then
            success "Cleaned up ${#stale_files[@]} stale lock(s)"
            return 0
        fi

        # Re-fetch and rebuild on retry (tree may have changed). A failure HERE
        # is a read failure, not push exhaustion: reporting it as 12 would send
        # the user to a push-retry hint for a connectivity problem.
        debug "Push failed during cleanup, retrying..."
        sleep "0.$((RANDOM % 4 + 1))"
        if ! fetch_err="$(LC_ALL=C git fetch origin "$BRANCH" --quiet 2>&1)"; then
            _cleanup_warn_unreadable "$fetch_err" "${#stale_files[@]}"
            return 11
        fi
        if ! parent_hash=$(git rev-parse "origin/$BRANCH" 2>/dev/null) ||
           ! current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}" 2>/dev/null); then
            _cleanup_warn_unreadable "" "${#stale_files[@]}"
            return 11
        fi
    done

    warn "failed to remove ${#stale_files[@]} stale lock(s) after ${attempt} push attempt(s) — they remain on the '$BRANCH' branch; retry './ait lock --cleanup', or clear one with './ait lock --unlock <task_id>'"
    return 12
}
```

Propagate the code from the dispatcher (`:550-552`):

```bash
    --cleanup|cleanup)
        cleanup_rc=0
        cleanup_locks || cleanup_rc=$?
        exit "$cleanup_rc"
        ;;
```

### 3. `.aitask-scripts/aitask_pick_own.sh` — stop discarding the outcome

Replace `sync_remote()` (`:140-143`):

```bash
# Outcome of the most recent lock_cleanup call. Like task_sync, lock_cleanup
# always returns 0 — a failed sweep must never block a pick — so read these
# when the outcome matters.
LOCK_CLEANUP_STATUS=""   # ok | failed
LOCK_CLEANUP_REASON=""   # branch_unreadable | push_failed | invoke_failed

# --- Sync with remote (best-effort) ---
sync_remote() {
    task_sync
    lock_cleanup
}

# Sweep locks abandoned by finished sessions. Best-effort but never silent:
# a swallowed failure lets stale locks pile up until a later pick reports
# LOCK_FAILED for a task nobody is actually working on.
lock_cleanup() {
    LOCK_CLEANUP_STATUS=""
    LOCK_CLEANUP_REASON=""

    local out="" rc=0
    # Combined capture: on success the child's progress notices are dropped
    # (our stdout is a machine contract, and a successful housekeeping sweep is
    # not worth reporting); on failure everything it said is forwarded.
    out="$("$SCRIPT_DIR/aitask_lock.sh" --cleanup 2>&1)" || rc=$?

    if [[ $rc -eq 0 ]]; then
        LOCK_CLEANUP_STATUS="ok"
        return 0
    fi

    LOCK_CLEANUP_STATUS="failed"
    case $rc in
        11) LOCK_CLEANUP_REASON="branch_unreadable" ;;
        12) LOCK_CLEANUP_REASON="push_failed" ;;
        *)  LOCK_CLEANUP_REASON="invoke_failed" ;;
    esac
    [[ -n "$out" ]] && printf '%s\n' "$out" >&2
    _lock_cleanup_warn "$rc"
    return 0
}

# Internal: name the consequence. aitask_lock.sh already reported the specific
# git failure (forwarded above); this adds why the user should care.
_lock_cleanup_warn() {
    local rc="$1" what
    case "$LOCK_CLEANUP_REASON" in
        branch_unreadable) what="stale lock cleanup did not complete" ;;
        push_failed)       what="stale locks could not be removed" ;;
        *)                 what="stale lock cleanup failed (aitask_lock.sh --cleanup exited ${rc})" ;;
    esac
    warn "${what} — locks abandoned by finished sessions may persist, and a later pick can report LOCK_FAILED for a task nobody is working on; inspect with './ait lock --list'"
}
```

Update the header comment (`:11-36`) to note that sync-only mode reports cleanup
failures on stderr while still exiting 0.

**Deliberate behavior change:** the child's stdout progress lines
(`Removing N stale lock(s)...` / `Cleaned up N stale lock(s)` — `info`/`success`
write to **stdout**, verified) are no longer leaked into `aitask_pick_own.sh`'s
output. That is a latent bug fix: in `--sync` mode they polluted the structured
stdout the pick skill parses (asserted to be exactly `SYNCED` in
`tests/test_task_push.sh:818`). `ait lock --cleanup` still shows them.

### 4. Tests

**`tests/test_task_lock.sh`** — add after Test 12, reusing `setup_paired_repos`
(already copies `aitask_lock.sh` + libs). The file runs `set -e`, so every
invocation needs `|| rc=$?`. Add one local helper:

```bash
# Install a pre-receive hook on the bare remote. $2 = extra sh to run before
# rejecting (used to make the remote unreadable mid-retry).
reject_pushes() {
    local tmpdir="$1" pre="${2:-}"
    printf '#!/bin/sh\n%s\necho "rejected by test hook" >&2\nexit 1\n' "$pre" \
        > "$tmpdir/remote.git/hooks/pre-receive"
    chmod +x "$tmpdir/remote.git/hooks/pre-receive"
}
```

| # | Fixture | Assert |
|---|---|---|
| A | `--init`, **no locks at all** | rc `0`, **empty stderr** — regression test for the pipefail abort; fails against today's code (`rc=1`) |
| B | one live, non-stale lock | rc `0`, empty stderr |
| C | stale lock (archived task), healthy remote | rc `0`, empty stderr, lock gone from the branch |
| D | reachable remote, **no `--init`** (branch absent) | rc `0`, empty stderr — must not regress into 11 |
| E | `git remote set-url origin /nonexistent/repo.git` | rc `11`, stderr contains `lock branch` and `remote unreachable` |
| F | stale lock + `reject_pushes` | rc `12`, stderr contains `1 stale lock(s)` and `5 push attempt(s)`, lock **still on** the branch (~2s: 5 retries with sleeps) |
| G | stale lock + `reject_pushes "$d" 'mv HEAD HEAD.disabled 2>/dev/null'` | rc `11` (**not** 12), stderr contains `remote unreachable` and `1 stale lock(s) left in place` |
| H | stray `notalock_lock.yaml` on the branch alongside a stale `t1` lock | rc `0`, stale `t1` removed — regression test for the `tid=` pipefail abort |

G is the concern-4 regression test: today it takes 0s, returns 0, and claims
"after 5 attempts". The `mv HEAD` trick was verified to make the follow-up fetch
fail with `does not appear to be a git repository` → classifies
`remote_unreachable`.

**`tests/test_task_push.sh`** — the `--sync` contract lives here (Test 23).
- Add `cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/` +
  `chmod +x` to `setup_pick_own_cli` (`:801`). Today the scaffold omits it, so
  the cleanup call fails with exit 127 and is swallowed — with this change that
  would surface as a spurious `invoke_failed` warning.
- **Test 24 — silence negative control:** healthy repo, `--sync` → exit 0,
  stdout exactly `SYNCED`, stderr contains no `Warning:`.
- **Test 25 — failure is forwarded, non-blocking:** stale lock + `reject_pushes`
  → `--sync` exits **0**, stdout unchanged, stderr contains both the forwarded
  `1 stale lock(s)` line and the consequence
  `LOCK_FAILED for a task nobody is working on`.

**Harness-can-fail check** (before committing): revert each fix in turn and
confirm the matching test actually fails —
(i) restore the `grep` listing → A fails;
(ii) restore `return 0` for push exhaustion → F fails;
(iii) restore `|| break` in the retry loop → G fails;
(iv) restore `2>/dev/null || true` in `sync_remote` → Test 25 fails.

### 5. Docs

- `website/content/docs/commands/lock.md` — extend the `--cleanup` table row and
  add a short paragraph documenting the exit contract (0 / 11 / 12) and the
  user-visible change: `ait lock --cleanup` now exits non-zero and warns when it
  cannot read the lock branch or cannot push its removals, instead of exiting 0
  silently.
- `website/content/docs/development/_index.md:117-118` — note that `--cleanup`
  reports failures rather than exiting 0 unconditionally.

Current-state prose only, per `aidocs/framework/documentation_conventions.md`.

## Verification

```bash
shellcheck .aitask-scripts/aitask_lock.sh .aitask-scripts/aitask_pick_own.sh
bash -n .aitask-scripts/aitask_lock.sh .aitask-scripts/aitask_pick_own.sh
bash tests/test_task_lock.sh
bash tests/test_task_push.sh
```

Live acceptance in this repo (real entry point, not just units):

```bash
# Healthy path: silent, exit 0, clean stdout contract
./.aitask-scripts/aitask_pick_own.sh --sync            # -> exactly "SYNCED", no warning
./.aitask-scripts/aitask_lock.sh --cleanup; echo "rc=$?"   # -> rc=0 (today: rc=1 when nothing is locked)

# Failure path (throwaway clone, NOT this checkout):
#   git remote set-url origin /nonexistent/repo.git
#   ./.aitask-scripts/aitask_pick_own.sh --sync; echo "rc=$?"
#   -> rc=0, stdout SYNC_FAILED:remote_unreachable,
#      stderr names the unreadable lock branch + the LOCK_FAILED consequence
```

AC mapping: AC1 ("a `--cleanup` failure emits a warning naming what was left
uncleaned, while `aitask_pick_own.sh` still exits 0") = tests E/F/G + Test 25 +
the live failure check. AC2 ("a successful cleanup, and a cleanup with nothing
to do, stay silent") = the empty-stderr negative controls A/B/C/D + Test 24.

## Post-Review Changes

### Change Request 1 (2026-08-03 07:45)

- **Requested by user:** The retry fetch mapped *every* failed `git fetch` to
  exit 11, while the initial-fetch block treats `couldn't find remote ref` /
  `not our ref` as the normal branch-absent case and returns 0. A branch deleted
  after a rejected push but before the refresh would therefore emit a misleading
  "unreadable branch" warning, contradicting the documented `0 = branch absent`
  contract. Reuse the absent-branch case at the retry site and add a test that
  deletes the branch during the retry cycle.

- **Changes made:** Confirmed and fixed. Extracted the absent-branch test into
  `_cleanup_branch_absent()` in `aitask_lock.sh` and branched **both** fetch
  sites on it, so the two can no longer drift apart. The retry site now returns
  0 silently when the branch is gone. This also closes a worse second-order
  effect the concern implies: had the loop continued, the next attempt's
  `git push <commit>:refs/heads/aitask-locks` would have **recreated the deleted
  branch from our rebuilt tree, resurrecting every lock it held**. Added
  Test 12h2, which rejects the push from a `pre-receive` hook that also deletes
  the branch, and asserts exit 0, empty stderr, and that the branch stays
  deleted. The hook must `unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY
  GIT_ALTERNATE_OBJECT_DIRECTORIES` first — git otherwise refuses with "ref
  updates forbidden inside quarantine environment", and the fixture silently
  fails to delete anything. Negative control: removing the branch-absent case
  from the retry site alone reproduces the reported bug exactly (exit 11 plus a
  "could not read the lock branch … reason unknown" warning).

- **Files affected:** `.aitask-scripts/aitask_lock.sh`,
  `tests/test_task_lock.sh`.

## Final Implementation Notes

- **Actual work done:** As planned, plus two additions found during
  implementation (below). `cleanup_locks()` in `.aitask-scripts/aitask_lock.sh`
  gained a documented exit contract (0 / 11 / 12), two `set -euo pipefail`
  aborts were removed (lock listing → `awk`; task-id extraction → parameter
  expansion), both `git fetch` sites classify their stderr via the canonical
  `_task_push_classify`, and the retry-loop fetch no longer misreports a read
  failure as push exhaustion. `sync_remote()` in `aitask_pick_own.sh` was
  replaced with `lock_cleanup()` + `_lock_cleanup_warn()`, which capture the
  child's output, classify the exit code, forward its diagnosis, and add the
  consequence — always returning 0. 9 new tests in `tests/test_task_lock.sh`
  (63/63) and 2 in `tests/test_task_push.sh` (126/126). Docs updated in
  `website/content/docs/commands/lock.md` (new "Stale Lock Cleanup" section) and
  `website/content/docs/development/_index.md`.

- **Deviations from plan:**
  1. **The dispatcher calls `cleanup_locks` bare, not `cleanup_locks || rc=$?`.**
     The planned guarded form was wrong: invoking a function on the left of `||`
     puts it in a condition context, which **disables `set -e` for the entire
     function body**. That silently re-introduced the failure class this task
     exists to remove — an unexpected non-zero command mid-sweep would no longer
     abort, and the function would carry on with bogus state. A bare call under
     `set -e` propagates the exact return code (verified: `return 11` → script
     exits 11) *and* keeps `set -e` live inside. This was caught only because
     negative control (i) failed to discriminate.
  2. **`_cleanup_branch_absent()` was extracted** (review round 2) so both fetch
     sites share one absent-branch test — see Post-Review Changes.

- **Issues encountered:**
  - The first negative control passed when it should have failed, which is what
    exposed deviation 1. A passing negative control means the test does not
    discriminate; it was treated as a defect in the implementation, not the test.
  - The Test 12h2 fixture initially deleted nothing: a `pre-receive` hook
    inherits a quarantine environment in which git refuses ref updates ("ref
    updates forbidden inside quarantine environment"). The hook must
    `unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY
    GIT_ALTERNATE_OBJECT_DIRECTORIES` first. Without that the test would have
    passed vacuously.
  - `git` error text is locale-dependent and `task_utils.sh` pins `LC_ALL=C`
    only inside `_ait_data_git`; both new fetches pin it explicitly.

- **Key decisions:**
  - Exit codes split on **read vs write** (11 = branch unreadable, 12 = removal
    push rejected), because that is what makes the recovery hint correct — a
    connectivity failure must not be sent to a push-retry hint.
  - No `LOCK_CLEANUP_FAILED:` token was added to `--sync` stdout. No skill would
    act on it, and it would force edits to SKILL.md + `.md.j2` + goldens across
    3 agents × 4 profiles. A stderr warning meets the acceptance criteria.
  - The child's stdout progress notices are dropped at the `aitask_pick_own.sh`
    call site. They previously leaked into the structured stdout the pick skill
    parses; the negative control confirmed `SYNCED` was being corrupted to
    `Removing 1 stale lock(s)...\nSYNCED` whenever a sweep had work to do.
  - Every quiet path is pinned with an **empty-stderr** negative control,
    because this code runs on every pick and a spurious warning would be worse
    than the silence it replaces.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_lock.sh:362` — `list_locks()` has the same
    `set -euo pipefail` abort as the one fixed in `cleanup_locks()`:
    `lock_files=$(git ls-tree "$current_tree_hash" | grep '_lock\.yaml' | awk …)`
    exits 1 when the lock branch holds no lock files, so `ait lock --list`
    aborts before printing its "No active locks" message. Left untouched as
    out of scope; it is exactly the pattern the confirmed `after` mitigation
    task audits for.

## Post-implementation

Per **Step 9** of the task-workflow skill: current-branch mode (profile `fast`,
`create_worktree: false`), so there is no branch/worktree merge or cleanup. Run
the gate orchestrator (`./ait gates run 1370` — active set is
`[risk_evaluated]`), then archive with
`./.aitask-scripts/aitask_archive.sh 1370`.

## Risk

### Code-health risk: medium

- The change makes a previously-inert exit status **load-bearing on the hot
  path** (every pick), and exploration found two latent `set -euo pipefail`
  aborts inside the very function whose status we start trusting. A third,
  unfound one would turn into a warning on every pick. · severity: medium ·
  → mitigation: t1381 `audit_pipefail_grep_assignment_aborts` (after). In-scope:
  awk/parameter-expansion rewrites remove the whole class here rather than
  patching instances, and negative-control tests A/B/C/D assert **empty stderr**
  on all four quiet paths — any residual abort fails the suite
- `ait lock --cleanup` gains a non-zero exit contract, user-visible for anyone
  scripting it (exit 11 when offline instead of 0). Blast radius verified small:
  the only in-repo call sites are `aitask_pick_own.sh:143` and
  `tests/test_task_lock.sh:265` (which discards the status), plus the
  interactive command. · severity: low · → mitigation: documented in `lock.md`
  as part of this change
- Classifying git's stderr text is locale-sensitive; `LC_ALL=C` is pinned on
  both fetches, matching the `_ait_data_git` precedent. · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low

- None identified. Both AC bullets map to named tests, the root cause was read
  from source rather than inferred, and all four failure modes (plus the git
  error texts the classifier keys on) were reproduced in a scratch repo before
  planning.

### Planned mitigations
- timing: after | name: audit_pipefail_grep_assignment_aborts | created: t1381 | type: chore | priority: medium | effort: medium | addresses: code-health — a third, unfound `set -euo pipefail` abort | desc: Audit `.aitask-scripts/` for `x=$(cmd | grep …)` assignments that abort the script when grep matches nothing under `set -euo pipefail`, fix them, and add a guard test; t1370 found two in `cleanup_locks()` alone.

Also spawned at Step 8b: **t1378** — `list_locks()` (`aitask_lock.sh:362`) carries
the same pipefail abort, so `ait lock --list` exits 1 without output whenever
nothing is locked. It is the one confirmed instance; t1381 covers the sweep.

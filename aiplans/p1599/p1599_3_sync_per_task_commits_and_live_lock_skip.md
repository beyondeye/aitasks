---
Task: t1599_3_sync_per_task_commits_and_live_lock_skip.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_4_sweep_latent_unscoped_commits_and_tripwire.md
Archived Sibling Plans: aiplans/archived/p1599/p1599_1_scope_pick_own_claim_commit.md, aiplans/archived/p1599/p1599_2_scope_fold_mark_commit_and_guard_amend.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 17:32
---

# p1599_3 — `aitask_sync.sh`: per-task commits + live-lock skip

## Context

Parent: t1599. The **highest-risk** child, and the only one whose fix is a
policy change rather than path-scoping.

`aitask_sync.sh:176-177` stages `aitasks/ aiplans/` wholesale and then commits
the **entire index** under `ait: Auto-commit task changes before sync`. Measured
on the live `aitask-data` branch: **18 of 66** sync auto-commits carry more than
two task/plan files. Unlike t1599_1 and t1599_2, this sweep is *intentional* —
its job is to leave the worktree clean so the later `pull --rebase` can run — so
scoping alone is not the answer.

This session **re-verified the plan against the current tree**. The design holds;
the corrections below are folded into the steps.

### Verification findings (this pass)

**Confirmed exactly as written:** `auto_commit` add/commit at `:176-177`;
`check_remote` at `:154-162` (runs before `auto_commit`, so this path only ever
executes with a remote present); `do_pull_rebase`'s non-conflict branch emitting
`ERROR:pull_rebase_failed` + `return 1` at `:421`/`:425`; `main()` exiting 1 at
`:504`; `do_push`'s swallow-and-retry at `:456-470`; the lock YAML field set
(`task_id`, `locked_by`, `locked_at`, `hostname`, `pid`, `pid_starttime`,
`pid_starttime_kind`); `check_lock()` failing **open** across absent-branch,
fetch-failure and empty-branch alike; `run_sync_batch` never reading
`returncode`; `auto_commit` being best-effort and always returning 0.

**Corrected line references** (the plan's were stale):

| claim | actual |
|---|---|
| lock YAML schema `aitask_lock.sh:270-276` | **`:289-299`** |
| `check_lock()` `:378-401` | **`:408-431`** |
| `list_locks()` `:414` | **`:454-502`** (helpers `:440-452`) |
| `--list` dispatch `:724-726` | **`:778-780`** (top-level `case` at `:757-806`) |
| `aitask_board.py:11467-11503` | **`:12252-12296`** (`_run_sync`) |
| `syncer_app.py:2116-2160` | **`:2114-2172`** |
| `plant_lock` `test_crash_recovery_pid_anchor.sh:40-145` | **`:106-126`** |
| `setup_branch_mode_repos` `test_sync_branch_mode_automerge.sh:47-76` | **`:47-99`** |

**Three substantive gaps the original plan did not cover** — each is now a step:

1. **Cross-host liveness is unsound as specified (Step 5).**
   `lock_holder_liveness()` takes `(pid, starttime, kind)` and has **no hostname
   parameter and no host awareness**. Handed a foreign machine's PID it probes
   the *local* process table and returns a fabricated `alive`/`dead`. A
   coincidentally-absent local PID yields `dead` → "commit it" → we commit a
   file another machine's live session owns, which is precisely the defect this
   task exists to remove. The guard already exists at `aitask_lock.sh:244-248`
   and must be replicated.
2. **The canonical scoped-commit seam already exists (Step 3).**
   `task_git_commit_scoped()` (`lib/task_utils.sh:206-244`) is the framework's
   one scoped-commit helper — `0` committed / `2` verified nothing to commit /
   `1` failed — already used by t1599_1 (`aitask_pick_own.sh:470`) and t1599_2
   (`aitask_fold_mark.sh:758`). Use it; do not hand-roll `add` + `commit -o`.
3. **The tri-state lock-branch probe already exists (Step 6).**
   `lock_branch_exists_on_remote()` (`aitask_lock.sh:71-79`) returns `0` exists /
   `1` reachable-but-absent / `2` unreachable — exactly the three states Step 6
   needs. Derive the statuses from it rather than inventing a parallel probe.

**Audit result required by the task's Step 1 — the token contract, now settled.**
`parse_sync_output()` (`sync_action_runner.py:87-140`) takes the **first
non-empty stdout line**, matches `CONFLICT:` / `ERROR:` prefixes, then an
**exact whole-line** match against `{SYNCED, PUSHED, PULLED, NOTHING,
AUTOMERGED, NO_NETWORK, NO_REMOTE}`, and **fails closed**: an unrecognised line
*or empty stdout* becomes `STATUS_ERROR`. In the syncer that is not merely red —
`STATUS_ERROR` calls `_capture_failure` (`syncer_app.py:2154`) and arms
`action_agent_resolve`, i.e. it **offers to spawn a code agent** to fix the
"failure". Consequences:

- A **no-commit run needs no new token.** It still ends at the existing Step-9
  verdicts (`SYNCED`/`PUSHED`/`PULLED`/`NOTHING`); only the number of local
  commits changes.
- A **deferred rebase does.** Falling through to `NOTHING` would report "already
  up to date" while the remote is ahead and we deliberately skipped — the exact
  silent-non-sync failure mode to avoid. Introduce **`DEFERRED:<reason>`**,
  parsed like `CONFLICT:` and rendered `severity="warning"` in both TUIs (never
  `error`, so no failure capture and no agent-resolution offer).
- The new `auto_commit` **must keep never aborting**: under `set -euo pipefail` a
  stray non-zero exits the script with no stdout, which every consumer reads as
  `ERROR: empty output from sync script`.

### Concurrency model (added after review — Steps 3a and 5a)

Two TOCTOU hazards were raised in review and both verified. They share a root
cause: **`.aitask-data` is a single worktree with a single index, shared by every
concurrent session on the machine**, and `task_git()` (`task_utils.sh:194-202`)
does no locking at all. `aitask_init_data.sh:249-266` refuses a second checkout
of `aitask-data`, and per-task worktrees symlink to the same directory
(`lib/data_symlinks.sh:4`), so `.git/worktrees/-aitask-data/index` really is one
file. `assert_data_worktree_clean` (`task_utils.sh:121-149`) is a *state* check
for six git-dir sentinels — it says nothing about another session's staged
entries or about `index.lock` contention.

**Hazard A — lock-snapshot race.** `--list --batch` yields one fetched snapshot.
A session can acquire a task lock and begin editing *after* enumeration but
*before* that task's group commit, so the sweep still commits live work. Verified
window: the claim acquires its lock at `aitask_pick_own.sh:359`, writes the file
via `aitask_update.sh` at `:457`, and only commits at `:624` — hundreds of
milliseconds.

**Hazard B — shared index.** `task_git_commit_scoped` stages every path it is
given. If another session has that path staged-but-uncommitted, our `add`
replaces its index entry and a `reset` would unstage it — this sync would
destroy in-flight index state while trying not to swallow it.

**The framework already has the primitives.** `lib/stale_lock.sh` is a generic
machine-local mkdir mutex: `ait_lock_dir <name>` (`:144-179`),
`stale_lock_acquire` (`:495`), `stale_lock_release` (`:680`, owner-token gated).
It is fail-safe by construction — a live PID is never displaced, a dead one is
reclaimed. `lib/registry_lock.sh` adapts it to a seconds budget with an EXIT-trap
auto-release (`:102`, `:129`, `:146`) and already has six callers.
`lib/attachment_lock.sh` is the direct precedent for this exact problem: it
scopes a lock to the data worktree and `aitask_attach.sh` / `aitask_artifact.sh`
perform every `task_git add` / `reset` / `commit` only inside it.

There is **no** `GIT_INDEX_FILE` / `read-tree` / `write-tree` precedent anywhere
in the tree, so the private-temp-index alternative is rejected: it would be a
novel technique for a problem the existing mutex solves.

## Ownership

Owns `.aitask-scripts/aitask_sync.sh` and `.aitask-scripts/aitask_lock.sh`.
The wire-protocol change additionally requires `lib/sync_action_runner.py` and
its two TUI consumers (unowned by any sibling; the task's Step 1 mandates this
audit). Do **not** touch `aitask_pick_own.sh` (t1599_1), `aitask_fold_mark.sh`
(t1599_2), or t1599_4's sweep targets.

Two corrections to the parent's framing, still accurate: `aitask_pick_own.sh
--sync` does **not** call this script (it calls `task_sync` +
`aitask_lock.sh --cleanup`), and `aitask_sync.sh` has no `--sync` flag. The
sweep fires from `ait sync` (`ait:234`, which `exec`s), the board TUI, and the
syncer TUI.

---

## Step 1 — Pre-phase: pin the existing token contract, and settle one primitive

**Spike first (blocking for Steps 3 / 5a) — DONE, results below.**

Confirmed empirically (scratch repo, git plumbing):

- `git commit -o -m <msg> -- <path>` **does record a pure deletion** with no
  `add` and no `rm --cached`. The `rm --cached` fallback is therefore not
  needed. Afterwards the worktree is **clean** — the same property that makes a
  cleanliness-based quarantine release wrong (Step 7c).
- A two-path `-- <new> <orig>` commit **does record the add+delete pair**, but
  only once `<new>` has been staged: an untracked `<new>` fails the whole commit
  with `error: pathspec '<new>' did not match any file(s) known to git`, rc 1.
  This is exactly the untracked-only staging rule of Step 3.
- `git hash-object -- <path>` → rc 0 + hash when present; **rc 128, stderr, no
  stdout** when absent. Confirms Step 5a.3: existence must be decided by
  `[ -e ]`, never by this command's failure.
- `git rev-parse --verify --quiet HEAD:<path>` → rc 0 + hash when present,
  **rc 1 with no output** when absent. Confirms the Step 5a.4 probe.
- `-z` rename bytes verified as `R` `SP` `SP` `<new>` `\0` `<orig>` `\0` — the
  `<new>`-then-`<orig>` ordering the plan assumed. Confirmed.

**Two corrections the spike forced** — see Steps 2 and 3.

Then, before touching `auto_commit`, run `tests/test_sync.sh` and
`tests/run_all_python_tests.sh --test-dir tests` and record the baseline.
`test_sync.sh` asserts **exact trimmed equality** on `NOTHING`/`PUSHED`/
`PULLED`/`SYNCED`/`AUTOMERGED`/`NO_REMOTE` at ~11 call sites, and
`test_sync_action_runner.py:90-94` pins unknown-token → `ERROR`. These are the
control: any change that alters an existing verdict must show up here.

## Step 2 — Parse the dirty set with a NUL-delimited porcelain

`git status --porcelain` (no `-z`) renders a rename on **one line naming two
paths** and C-quotes any path containing a space. Archive moves are exactly that
shape, so it is not a corner case.

Use `task_git status --porcelain -z -uall -- aitasks/ aiplans/` (`status` is on
`_ait_git_subcmd_is_readonly`'s allowlist, so the wedged-worktree guard passes)
and parse NUL-delimited. **Ordering trap:** with `-z` a rename emits `<new>`
first, then `<orig>` — the reverse of the arrow display — and quoting is gone.
Pin it in a test.

**Correction from the Step-1 spike: `-uall` is mandatory, not cosmetic.** git's
default `-unormal` **collapses an untracked directory to the directory itself**:
a new child task shows as `?? aitasks/t99/`, not `?? aitasks/t99/t99_1_child.md`.
`aitasks/t99/` has no derivable task id, so under Step 4 it would be classified
**ownerless and silently skipped** — a new child task would never be
auto-committed. `aitasks/t<P>/` is precisely the shape a parent's first child
creates, so this is a common case, not a corner. Pin it with a test that a new
child task file inside a new `aitasks/t<P>/` directory is committed.

## Step 3 — Group by owning task id

Owner derivation (new, local to `aitask_sync.sh` — no sibling needs it, and
`resolve_task_file`/`resolve_plan_file` in `task_utils.sh` are the *inverse*
mapping): `aitasks/t<N>_*.md`, `aitasks/t<P>/t<P>_<C>_*.md`, `aitasks/archived/…`,
`aiplans/p<N>_*.md`, `aiplans/p<P>/p<P>_<C>_*.md`.

For a rename resolve the owner of **both** paths: same owner (the archive case)
→ group normally; **different owners → skip and report as an ambiguous
cross-task rename.** Never guess an owner for an entry that legitimately names
two.

**Correction from the Step-1 spike: an `R` entry only appears when BOTH halves
are staged.** An ordinary worktree move that nobody has staged — the realistic
shape for the dirty tree this sweep scans — presents as two independent entries,
` D <orig>` and `?? <new>`, which resolve to the same owner and group correctly
on their own. `R` therefore shows up mainly when another session is mid-`add`
(e.g. `aitask_archive.sh` between its `add` and its `commit`), and Step 3a then
defers that group as `staged_elsewhere` anyway. So the `R` branch exists to
**parse correctly and refuse to mis-attribute**, not as the path by which
archive moves normally get committed — the tests must cover both shapes and must
not assume an archive move arrives as `R`.

Commit each group through **`task_git_commit_scoped "<msg>" "${paths[@]}"`**
under a message naming its real task. Handle its full return contract — `2`
(verified nothing to commit) is a normal outcome, not a failure; `1` is a failed
commit and must be reported and counted as protected-dirty.

**Extend the seam rather than forking it (Hazard B).** `task_git_commit_scoped`
stages *every* path it is given, but its own comment (`task_utils.sh:226-227`)
says the `add` exists **only** so an untracked path can be named by a pathspec —
`commit -o -- <path>` takes worktree content and needs no staging for a tracked
file. Add an **opt-in fourth mode flag defaulting to today's behaviour** so
t1599_1's and t1599_2's call sites are untouched (`aitask_pick_own.sh:470`,
`aitask_fold_mark.sh:758`), under which the helper stages **only paths git does
not already track** (`git ls-files --error-unmatch`). Sync passes that mode, so a
tracked file another session may have staged is never re-staged by the sweep.

## Step 3a — Serialize the commit phase on the shared index (Hazard B)

Hold a machine-local mutex across the **entire** enumerate → classify → commit
phase, following `attachment_lock.sh`'s precedent:

```bash
lock_dir="$(ait_lock_dir data_index)"
registry_lock_acquire "$lock_dir" 15 "sync auto-commit" || { ... }
```

`registry_lock_acquire` installs its own EXIT trap (`registry_lock.sh:129`), so
the lock releases on normal exit and a hard-killed holder is reclaimed by
`stale_lock.sh`'s dead-PID logic. **Fail closed:** on acquisition failure commit
nothing, mark the whole run `protected_dirty` with reason `lock_contended`, and
report — never sweep unlocked. (No commit was made, so nothing is withheld from
the remote and `publication_blocked` does not apply.)
This is `feedback_mutex_fail_safe_owner_token` applied literally.

**State plainly what this does not buy.** A lock only sync respects serializes
sync against *other syncs* (CLI + board + syncer, a real and frequent case) and
establishes the named lock other index writers can migrate to. It does **not**
serialize sync against the claim path, `aitask_gate.sh`, or attach/artifact —
those take different locks or none. Closing that gap means every `.aitask-data`
index writer adopting `data_index`, which reaches outside this child's ownership
and is carried as a follow-up.

**Index-aware group policy, inside the lock:**

- Before committing a group, probe for foreign staged entries:
  `task_git diff --cached --name-only -z -- "${paths[@]}"` (`diff` is on
  `_ait_git_subcmd_is_readonly`, `task_utils.sh:83-85`, so this works even mid-
  rebase). **Non-empty → defer the whole group**, reason `staged_elsewhere`.
  Never `add`, never `reset` a path someone else staged.
- Record which paths *this run* staged (the untracked ones). On a failed group
  commit, unstage **only those** — `task_git reset -q -- <those paths>`, the
  established path-scoped form used at 15 existing sites, all of which likewise
  run under a lock. A path left staged blocks the rebase exactly like an unstaged
  one, so this cleanup is required; restricting it to paths with no prior index
  entry is what makes it safe.
- `task_git add` / `reset` / `commit` all **die** while the worktree is mid-rebase
  (neither allowlist covers them) and `die` is `exit 1` with no `batch_out` —
  which the parser reads as `ERROR: empty output`. `auto_commit` runs at
  `main()` step 3, before any rebase of ours, but a *previous* run can have left
  the worktree wedged. Probe the six git-dir sentinels up front and, if wedged,
  emit `DEFERRED:worktree_wedged` and return cleanly rather than letting `die`
  exit the script silently.

## Step 4 — Never auto-commit an ownerless path

Anything with no derivable task id — `aitasks/metadata/*`, artifacts, stray
files — is **skipped and reported**, never swept into a residual commit.
`aitasks/metadata/stats_config.json` has four commits in its entire history and
**three are swallows** (`da9dfeb89`, `c4445b4eb`, `442c65179`); a residual commit
would leave that exact case unfixed. Add `--commit-unowned` as an explicit
opt-in.

**Verified caveat, and it is load-bearing:** the original plan asserted these
files "stay dirty until the session that changed them commits them". That does
**not** hold — `board_config.json`'s and `stats_config.json`'s writers never
commit them (the settings/board TUIs write only; the project layer is git-tracked
while the user layer is the gitignored `.local.json`). So an ownerless dirty file
has **no session that will ever clear it**, and via Step 7 it becomes a
*permanent* rebase deferral. Skipping is still correct — committing another
session's half-finished state is the defect — but the deferral report **must** be
prescriptive: name each blocking file and print the exact remedy
(`./ait git add <path> && ./ait git commit -m "…"`, or `--commit-unowned`).

## Step 5 — Live-lock skip, via the canonical seams

Reuse `lock_holder_liveness()` / `is_lock_holder_alive()` in `lib/pid_anchor.sh`
(the t1466 gate). **Do not reimplement liveness.** `lock_holder_liveness` prints
`alive`/`dead`/`unknown` on **stdout** and always exits 0 — capture stdout, never
`$?`. `is_lock_holder_alive` collapses `dead` and `unknown` into one false, so it
is **unusable here**; call `lock_holder_liveness` directly.

Fetch the lock branch **once**: extend `aitask_lock.sh --list` with a `--batch`
form emitting `LOCK:<id>|<email>|<host>|<pid>|<starttime>|<kind>`. `list_locks()`
(`:454-502`) already does exactly one `git fetch` up front and then pure local
plumbing, so this is an output-format addition, not a new scan. Leave the human
output **unchanged** — `aitask_board.py:2099-2120` (`refresh_lock_map`)
regex-parses that prose line.

Flag placement: the `--debug` pre-parse loop (`:752-755`) only strips flags
*before* the verb, so the `--list|list)` arm (`:778-780`) must consume `--batch`
itself.

**Per-verdict routing:** `dead` → commit (the recovery case); `alive` → skip;
`unknown` → **skip**. Fail safe.

**Cross-host guard (mandatory — see Verification finding 1).** Before consulting
liveness, replicate `aitask_lock.sh:244-248`: only when the lock's `hostname` is
non-empty, `!= "unknown"`, and equal to `get_hostname()` is the PID comparable.
Otherwise the verdict is **`unknown` → skip**. A foreign or `unknown` hostname is
not comparable, and two machines both reporting `unknown` compare equal.

## Step 5a — Compare-and-swap the lock snapshot and the content (Hazard A)

A single fetched snapshot is a *decision at a point in time*; committing from it
later is a TOCTOU. Four measures, in order — each is cheap, and together they
make the decision and the committed bytes refer to the same state:

1. **Order the two reads so they fail safe.** Do the dirty scan (Step 2)
   **first** and the lock enumeration (Step 5) **second**. A lock acquired while
   we were scanning is then visible to us. The reverse order — enumerate, then
   scan — is silently unsafe and is the ordering to avoid.

2. **CAS the snapshot immediately before the commit phase, inside the Step-3a
   mutex.** Re-run `aitask_lock.sh --list --batch` and recompute the verdict for
   **every eligible group's task**. Drop and report any group whose verdict
   changed (`lock_acquired_during_scan`). Compare per-task rather than on the raw
   branch SHA: an unrelated lock/unlock elsewhere in the repo would otherwise
   abort every sync on a busy branch. Have `--batch` also emit a
   `LOCKS_REF:<sha>` line (`git rev-parse origin/$BRANCH`, two lines beside the
   existing `git rev-parse origin/$BRANCH^{tree}` at `aitask_lock.sh:466`) so the
   whole-snapshot comparison is available when a caller wants it.

3. **CAS the path STATE, not just a hash.** A blob hash is only defined for a
   path that exists. The eligible set deliberately contains paths that do not:
   a **deletion**, and the **old half of a same-owner archive rename** (Step 3
   groups both halves, and with `-z` the rename emits `<new>` then `<orig>`).
   For those, `hash-object` has no valid value and `HEAD:<path>` will not
   resolve after the commit — so record a two-valued state per path:

   | state | recorded when | recorded value |
   |---|---|---|
   | `present` | `[ -e "$_AIT_DATA_WORKTREE/$path" ]` | `_ait_data_git hash-object -- <path>` |
   | `absent` | the path does not exist in the data worktree | — |

   **Existence decides the state; a `hash-object` failure never does.**
   `_ait_data_git` (`task_utils.sh:73-80`) is the documented read-only wrapper
   that skips the state assertion (`hash-object` is on neither allowlist). If the
   path exists but hashing fails, that is an **error** — drop the group as
   unverifiable; it is not evidence of absence.

   Re-derive the state immediately before the group's commit and require it to
   equal the recorded one — same state, and for `present` the same hash. Any
   transition (`present`→`absent`, `absent`→`present`, or a changed hash) means
   the path moved under us → drop the group, reason `content_changed`. The
   `absent`→`present` direction matters: a deleted file recreated by another
   session is exactly the case a hash-only check cannot see.

4. **Guard publication, per state.** After each group commit, probe
   `task_git rev-parse --verify --quiet HEAD:<path>` and require:

   - recorded `present:<h>` → the probe **succeeds** and equals `<h>`;
   - recorded `absent` → the probe **fails** (the path is absent from the commit,
     which is what records the deletion / the rename's source side).

   Either violation means the commit captured a racing edit in the window
   between the re-check and git snapshotting the path.

   **Record it as `publication_blocked` — a SEPARATE outcome from
   protected-dirty.** The two are orthogonal and must not share a flag:

   | outcome | meaning | blocks |
   |---|---|---|
   | `protected_dirty` | files we could not commit are still dirty | the **rebase** — and only matters when `remote_ahead > 0` |
   | `publication_blocked` | we made a commit whose content we cannot vouch for | the **push** — regardless of `remote_ahead` |

   Conflating them makes the guard inert in its own primary scenario: the race
   acquires a lock on `refs/heads/aitask-locks`, which never advances
   `origin/aitask-data`, so `remote_ahead == 0` is the normal case and a
   rebase-gated deferral would detect the mismatch and then push it anyway.

   **The bad commit is not un-made, and that is deliberate.** Reversing it would
   mean `reset --soft/--mixed HEAD^`, which moves HEAD and leaves the content in
   the *shared* index — Hazard B, against a path another session is actively
   writing. Rejected.

   The in-memory flag alone is **not sufficient**: it dies with the process,
   while the commit persists. Step 7c makes the hold durable.

**Residual, stated honestly.** Full mutual exclusion requires the *claim* side to
hold the same `data_index` lock across acquire → write → commit, and that
sequence lives in `aitask_pick_own.sh` (t1599_1), outside this child's ownership.
What remains after the four measures above is a sub-millisecond window that
cannot publish: it is caught by measure 4 and converted into a reported
deferral. Closing it entirely is the follow-up named in `### Planned mitigations`.

## Step 6 — Three lock-availability statuses; do NOT fail open

`check_lock` (`:408-431`) and `list_locks` (`:454-502`) both fail **open**:
"no locks" today covers a genuinely absent branch, a network failure, and an
empty branch alike. Sweeping in that state recreates the cross-session swallow —
an outage can easily coincide with a live editor.

Derive the three statuses from the **existing tri-state probe**
`lock_branch_exists_on_remote()` (`:71-79`), which `lock_task`/`unlock_task`
already use for `die_code 10` vs `11`. `check_lock` never calls it; `--batch`
must:

**The status answers exactly one question — "is this snapshot trustworthy?" — and
nothing about any particular task.** Whether a *given* task is held is answered
by the `LOCK:` lines, per task. Keeping a separate global "no locks anywhere"
status invites conflating the two (it did: an early draft used it as a per-task
precondition in Step 7c, so an unrelated live lock on tY pinned tX). So there is
no `LOCKS_NONE`; a readable branch with zero locks is `LOCKS_OK` with zero
`LOCK:` lines.

| probe | status | meaning | action |
|---|---|---|---|
| `0`, tree readable | `LOCKS_OK` | snapshot trustworthy; zero or more `LOCK:` lines follow | route **per task**: a task with no `LOCK:` line has no holder |
| `1` | `LOCKS_UNINITIALIZED` | lock branch does not exist — no task in this repo *can* be locked | commit all owned groups |
| `2`, or fetch/`ls-tree` failure after a `0` | `LOCKS_UNAVAILABLE` | branch exists but unreadable | **skip every task-owned file and report**; commit nothing |

An unreadable lock branch is not evidence of no locks. Availability-over-safety
is an **explicit** `--assume-unlocked` operator choice, never a silent
consequence of an outage.

## Step 7 — Protect the rebase

This is the invariant `auto_commit` actually exists to maintain. Verified: with
an unstaged change `git pull --rebase` refuses (rc 128), `do_pull_rebase`'s
non-conflict branch emits `ERROR:pull_rebase_failed` and `main()` exits 1
(`:504`) — so one correctly-protected file would block fetch/pull/push for the
CLI and both TUIs.

**Stashing is rejected.** `git stash` / `rebase.autoStash` would move another
live session's in-flight edits into a stash they do not know about — the t635_33
hazard. Never stash a file being protected *because* another session owns it.

**Two early exits, evaluated in this order.** Hold both outcome sets (count +
reasons + holders + paths) in script-scope variables set during grouping —
`auto_commit`'s stdout is not a return channel and it must keep returning 0.
Commit every eligible group as normal and always run the read-only fetch, then:

1. **`publication_blocked` non-empty — this run's detections *plus* every entry
   still held from the Step-7c quarantine file → skip `do_pull_rebase` AND `do_push`,
   emit `DEFERRED:publication_blocked:<detail>`, exit 0 — regardless of
   `remote_ahead`.** This must be checked **first** and must not be gated on
   `remote_ahead`: the modelled race advances only `refs/heads/aitask-locks`, so
   `remote_ahead == 0` is precisely the case in which a raced commit exists and
   the push would otherwise succeed.
2. **`protected_dirty` non-empty and `remote_ahead > 0`** → skip
   `do_pull_rebase` and `do_push`, emit `DEFERRED:protected_dirty:<detail>`
   naming count/reason/holder, exit 0. (Pushing is skipped too: with the remote
   ahead and no rebase the push would be rejected anyway.)
3. Otherwise continue normally. `protected_dirty` with `remote_ahead == 0` is
   **not** a deferral — `do_push` needs no clean tree, so eligible local commits
   still publish. That asymmetry is the whole reason the two outcomes are
   tracked separately.

Deferring is also right on its own merits: rebasing the shared data branch
underneath a live session's uncommitted work is the clobber hazard that argues
for leaving reconciliation to the owning session.

**Staging detail:** governed by Step 3a — only untracked paths are staged, only
inside the `data_index` mutex, and only paths this run staged are ever unstaged.
A path left staged blocks the rebase exactly like an unstaged one, which is why
the cleanup exists; scoping it to paths with no prior index entry is what keeps
it from destroying another session's staged work.

## Step 7b — Carry both deferral outcomes into `do_push`

The Step-7 guard alone is not enough. `remote_ahead` is sampled once, from the
step-5 fetch (`main()` `:490-495`). On a branch several sessions push to in
parallel the remote can advance *after* that fetch, so a run that correctly saw
`remote_ahead == 0` still reaches `do_push` and gets rejected. Today's retry
(`:456-470`) runs `task_git pull --rebase --quiet 2>/dev/null || true` — with
protected files the rebase refuses (rc 128), `|| true` **swallows** it, the
un-rebased push is rejected again, and the run reports `ERROR:push_failed`,
blaming the push for a failure the protected files caused and bypassing the
protection.

Consult both outcome sets in `do_push`:

- **`publication_blocked` set** → `do_push` must not be reached at all; the
  Step-7 guard exits first. Keep a defensive check here anyway (return the
  deferred outcome without pushing) so a future caller that reorders `main()`
  cannot silently publish a raced commit — the guard's correctness should not
  depend on one call site's ordering.
- **`protected_dirty` set, push rejected** → do NOT `pull --rebase`, do NOT
  retry; emit `DEFERRED:protected_dirty:` and return the deferred outcome
  (exit 0). Local commits publish on a later run.
- **both unset** → today's fetch + rebase + retry, unchanged.

While here, stop the retry path swallowing a genuine rebase failure: check the
rebase's exit status and route on it rather than blind-retrying a push that
cannot succeed. Blind-retrying is what turns a diagnosable cause into
`ERROR:push_failed`.

## Step 7c — Durable publication quarantine (cross-invocation)

`publication_blocked` is script-scope state; the raced commit is not. Without
persistence the hold lasts exactly one run: the next CLI / board / syncer sync
finds the path still dirty and still locked, classifies it `protected_dirty`,
sees `remote_ahead == 0`, takes Step 7 case 3 — and pushes the commit run 1
withheld. "A later run will wait until the owner commits" is an assumption, not
a transition, and must be enforced.

**Store it in the data worktree's git dir**, not in `aitasks/`:
`<gitdir>/ait-sync-quarantine`, with `<gitdir>` from `_ait_data_gitdir()`
(`task_utils.sh:50-67`). That location is untracked, per-repo, per-machine, and
never itself becomes a dirty task file — putting this state under `aitasks/`
would make it the very ownerless-dirty-file problem of Step 4.

**Key by `(path, blob)`, never by commit SHA.** A later `pull --rebase` rewrites
the commit's SHA, which would silently invalidate a SHA-keyed entry and release
the quarantine. One line per entry:

```
<path>|<quarantined_blob>|<task_id>|<first_seen_epoch>
```

Read and write it **inside the Step-3a mutex**, so concurrent syncs cannot race
on it.

**A clean worktree is NOT settlement — this is the trap.** `commit -o` commits
the *worktree* content, so immediately after the race the worktree equals the
suspect HEAD blob and the path is **clean by construction**. Dirtiness therefore
cannot distinguish "the racing session finished" from "the racing session is
still live and simply has not committed yet" — a release keyed on cleanliness
fires on run 1 and defeats the whole mechanism.

**Release rule — settlement requires an ownership transition.** Release an entry
when either:

1. **Superseded.** `task_git rev-parse --verify --quiet HEAD:<path>` **≠**
   `<quarantined_blob>` — a later commit landed on top, so publishing now
   publishes history rather than a tip. Independent of any lock.
2. **Ownership released *and* state verified — all three, never any.** The first
   two are **separate questions** and must not be merged: "is the snapshot
   trustworthy?" is global, "is *this* task held?" is per-task. Requiring a
   global no-locks-anywhere verdict would hold tX's entry for as long as any
   unrelated tY is locked — a normal state, blocking every push indefinitely for
   no safety benefit.
   - **the snapshot is trustworthy:** status is `LOCKS_OK` or
     `LOCKS_UNINITIALIZED` — i.e. **not** `LOCKS_UNAVAILABLE`. An unreadable lock
     branch is not evidence the holder is gone. Other tasks' locks are
     irrelevant here; their presence is exactly what `LOCKS_OK` allows. **And**
   - **this entry's `<task_id>` has no live-or-unknown holder:** no `LOCK:` line
     names it, or `lock_holder_liveness` returns `dead` for it — reusing the
     Step-5 seam **including the cross-host guard**, so a foreign or `unknown`
     hostname yields `unknown`, which counts as *held*. **And**
   - **the path is settled:** `task_git status --porcelain -- <path>` is empty,
     so nothing further is pending on disk.

**Age NEVER releases an entry.** An automatic expiry fires in exactly the states
clause 2 refuses to release on — a live holder, an `unknown` cross-host holder,
an unreadable lock branch — so a session that legitimately runs longer than the
window would have its raced content published merely because time passed. That
is the cross-session swallow this whole task exists to prevent, re-entering
through the escape hatch. Clauses 1 and 2 are the **only** automatic releases.

`AIT_SYNC_QUARANTINE_WARN_AGE` (default 24h) therefore **escalates the report,
it does not release** — the name says so deliberately, since a `MAX_AGE` reads
as a release deadline. Past it, the Step-9 line becomes a prominent warning
naming the path, the task, the current holder and the age, stating the
trade-off in both directions (publishing possibly-half-written content vs.
continuing to withhold every push), and printing the exact
`--release-quarantine` command.

**Termination is a human decision, by design.** There is no automatic
guarantee: a permanently `unknown` holder can hold an entry indefinitely.
`--release-quarantine` is the only escape, and that is the point — it makes the
safety-versus-availability call explicit and attributable instead of letting a
timer make it silently. What keeps this from being a silent wedge is the
escalating report: the state is re-announced on **every** run with the command
that ends it.

**Deferred option if the availability cost bites.** The hold is all-or-nothing,
so one raced commit withholds unrelated task data for as long as it is held. A
narrower variant is possible and is recorded here rather than built: at push
time, scan `@{u}..HEAD` for the first commit whose `<path>` blob equals the
quarantined blob and push `<that commit>^` instead, publishing everything before
it. It is deliberately **not** in scope now — it reintroduces a SHA resolution
the `(path, blob)` keying avoids, and a wrong resolution publishes exactly what
is being withheld. Revisit only if operators actually hit the stall.

**Availability cost, stated rather than engineered around.** While an entry is
held, the run publishes *nothing* — not just the raced commit. Withholding only
the offending commit (pushing `<raced>^`) would need a SHA the `(path, blob)`
keying deliberately avoids, and a wrong resolution there publishes the very
bytes being withheld. The full hold is accepted instead: the guard fires only in
a genuinely rare sub-millisecond window, and `--release-quarantine` is the
operator's explicit way out. Partial publication is a deliberate non-goal (see
Step 7c for the sketch and why it is deferred).

**While any entry is held:** skip `do_push` and emit
`DEFERRED:publication_blocked:` exactly as Step 7 case 1 does — the persisted
entries feed the same guard, so run 2 behaves identically to run 1 without
re-detecting the race. The rebase is *not* blocked by quarantine alone (it does
not publish anything); only `protected_dirty` blocks that, under its own rule.

## Step 8 — Wire the `DEFERRED:` token end to end

Four files, two languages — a token added in one and missed in another degrades
silently to a red `unknown status` error:

1. `aitask_sync.sh` — emit via `batch_out`; update **both** copies of the batch
   protocol doc (header comment `:12-21` and `show_help` `:63-72`).
2. `lib/sync_action_runner.py` — `STATUS_DEFERRED = "DEFERRED"` beside the other
   wire constants (`:57-65`); parse the `DEFERRED:` prefix alongside `CONFLICT:`
   (`:110-116`); carry the detail in a **new `deferred_reason` field** on
   `SyncResult` (`:79-84`) — not `error_message`, which would make a benign
   outcome read as an error to anything inspecting the dataclass.

   **Wire format:** `DEFERRED:<reason>[:<detail>]`, split on the **first** colon
   only, so `<reason>` is one of a closed set — `publication_blocked`,
   `protected_dirty`, `worktree_wedged`, `locks_unavailable`, `lock_contended` —
   and `<detail>` is free text that may itself contain colons. Pin the closed
   reason set in a test the way the token set is pinned, so a shell-side reason
   with no Python counterpart is caught rather than rendered as raw text.
3. `board/aitask_board.py` `_run_sync` (`:12252-12296`) — an
   `elif status == STATUS_DEFERRED` branch, `severity="warning"`, falling
   through to the normal refresh.
4. `syncer/syncer_app.py` `_on_data_sync_done` (`:2122-2172`) — same branch,
   `severity="warning"`, and **no `_capture_failure`** (a deferral is not a
   failure and must not arm the agent-resolution offer).
5. `website/content/docs/commands/sync.md` — the batch-token table at `:40-48`,
   plus the new `--assume-unlocked`, `--commit-unowned` and
   `--release-quarantine` flags and a short description of the quarantine state
   a user may see reported across several runs.

## Step 9 — Report

Report every skipped file with its reason — live lock / unknown liveness / locks
unavailable / ownerless / ambiguous rename / staged elsewhere / content changed /
failed group commit — naming the holder where known.

Report `publication_blocked` **separately from** the skip list: nothing was
skipped there, a commit was made and is being withheld from the remote. Name the
paths, say the withheld commit is local-only, and state the **enforced** release
conditions from Step 7c — a later commit superseding the content, or the owning
task's lock ceasing to have a live holder with the path settled — naming the
current holder, plus — past `AIT_SYNC_QUARANTINE_WARN_AGE` — the escalated
warning and the literal `--release-quarantine` command. Do not describe it
as data loss. Because the quarantine is durable and re-reported on every run
until it clears, this line must read as a standing state, not a one-off event.

**Write the report to stderr in both modes.** In batch mode stdout is the data
channel: `parse_sync_output` reads the *first non-empty line*, so a report line
there would be consumed as the status. The script already has `warn`/`iinfo_err`
for exactly this.

---

### Post-phase (risk mitigations)

1. `[prescriptive_deferral_report]` Make the Step-9 report **prescriptive, not
   just descriptive**. For every skipped file, emit its reason, its holder where
   known, and the exact command that clears it: for a live/unknown-lock skip,
   name the holding task and session; for an **ownerless** skip, print
   `./ait git add <path> && ./ait git commit -m "ait: Update <basename>"` and
   mention `--commit-unowned`; for `LOCKS_UNAVAILABLE`, name `--assume-unlocked`.
   When the run also defers (Step 7 / 7b), the `DEFERRED:` line and the stderr
   report must both say **why the sync did not happen and what ends it** — an
   ownerless deferral does not self-clear. Test: the ownerless-skip case asserts
   the remedy command appears in stderr.

2. `[sync_token_contract_test]` Add a test that **derives** the emitted-token set
   rather than restating it: extract every literal passed to `batch_out` in
   `.aitask-scripts/aitask_sync.sh`, strip any `:<detail>` suffix, and assert each
   resulting token is recognised by `parse_sync_output` (i.e. round-trips to a
   status that is not `STATUS_ERROR`/`unknown status`). This closes the
   4-file/2-language protocol split structurally: a token added to the shell and
   missed in `sync_action_runner.py` fails the suite instead of degrading to a red
   error in both TUIs. Guard it with a negative control — a deliberately bogus
   token must make the assertion fail.

## Verification

Fixture: `tests/test_sync_branch_mode_automerge.sh:47-99` (`setup_branch_mode_repos`
— bare remote, clone, orphan `aitask-data` branch + worktree, full `cp -r` of
`.aitask-scripts`). Lock seeding: `plant_lock` (`tests/test_crash_recovery_pid_anchor.sh:106-126`).

**Two fixture gaps to close first** (verified — the composition is otherwise
sound, both use `$tmpdir/remote.git` + `$tmpdir/local`):

- `plant_lock`'s `git rev-parse origin/aitask-locks` is **unguarded** and the sync
  fixture never creates that branch. Run `./.aitask-scripts/aitask_lock.sh --init`
  from `$tmpdir/local` first — the fixture already copies the whole
  `.aitask-scripts`, so it works out of the box.
- The sync fixture has **no `bin/hostname` shim**. Port the 5-line
  `TEST_HOSTNAME` shim from `test_crash_recovery_pid_anchor.sh:74-79` — without
  it the Step-5 cross-host guard cannot be driven deterministically in either
  direction.

Tests:

- live lock → file skipped and left dirty
- stale/dead lock → file committed
- `unknown` liveness → skipped
- **cross-host lock → skipped even when the local PID is absent** (the
  discriminating case for the Step-5 guard: plant a lock with a foreign
  `hostname` and a PID that does not exist locally; pre-guard this reads `dead`
  and commits)
- **`hostname: unknown` → skipped** (two machines both reporting it compare equal)
- mixed locked + unlocked → correct partition in ONE run
- nothing eligible → clean no-op, no commit created (`rev-list --count`
  unchanged, the `tests/test_gate_record.sh:100-107` idiom)
- rename/move grouping — a same-owner archive move (committed) and an ambiguous
  cross-task rename (skipped + reported); assert the `-z` `<new>\0<orig>`
  ordering explicitly. (Their **CAS-state** dimension is covered separately
  below — grouping and state-tracking are independent failure modes.)
- a path containing a space (proves the `-z` parser)
- ownerless file → skipped and reported, NOT committed; the report names the
  remedy command
- `LOCKS_UNAVAILABLE` → nothing committed; `LOCKS_UNINITIALIZED` → committed;
  `--assume-unlocked` → committed; `--commit-unowned` → committed
- **`LOCKS_OK` with unrelated locks present** → an owned, *unlocked* group is
  still committed. Pins that the status is a trustworthiness verdict and not a
  global gate: the presence of a lock on tY must not suppress tX.
- **rebase protection:** remote-ahead branch + one live-locked dirty file →
  exit **0** with `DEFERRED:protected_dirty:`, NOT `ERROR:pull_rebase_failed`,
  and the fetch still happened. Control: nothing protected → the rebase runs.
- **protected-dirty does NOT block a push when the remote has not advanced:**
  one live-locked dirty file, `remote_ahead == 0`, plus an eligible owned file →
  the eligible commit **is pushed** and the run does not defer. This pins the
  asymmetry between the two outcomes in the direction opposite to the
  publication test, so neither guard can be widened into the other.
- **push-retry race:** inject through a documented git seam — a `pre-push` hook
  in the fixture's data repo that, on its first invocation, pushes a commit from
  a sibling clone to the same remote. Our push is then genuinely rejected exactly
  once, deterministically entering `do_push`'s retry path. Protected → exit **0**
  with `DEFERRED:protected_dirty:`, not `ERROR:push_failed`; unprotected → the
  existing rebase+retry succeeds.
- **`auto_commit` never aborts:** with a malformed/unreadable lock blob planted,
  assert the run still emits a recognised token on stdout (never empty output).
  Separately, leave the data worktree wedged (`rebase-merge` sentinel present)
  and assert `DEFERRED:worktree_wedged`, not empty output.

**CAS path states (Step 5a.3 / 5a.4).** A hash-only check is blind to these, so
each is required:

- **deletion** — a tracked, owned, unlocked file deleted from the worktree:
  committed, recorded `absent`, and `HEAD:<path>` absent afterwards
- **same-owner archive move** — assert the `-z` `<new>\0<orig>` ordering, that
  `<new>` is recorded `present` and `<orig>` `absent`, and that the commit
  contains the add+delete pair
- **`absent`→`present` (the discriminating case a hash-only CAS cannot see)** —
  a path classified as deleted, then recreated before the commit: the group must
  be dropped with reason `content_changed`
- **`present`→`absent`** — an eligible file deleted before the commit: likewise
  dropped
- **unverifiable ≠ absent** — a path that exists but whose hashing fails must
  drop the group as an error, never be treated as `absent`

**Hazard A — the race, at the real boundary.** A `pre-commit` hook is the *wrong*
seam here and must not be used: for `commit --only`, git runs `prepare_index()`
and writes the tree **before** `prepare_to_commit()` invokes `pre-commit`, so a
hook that rewrites the file cannot change the committed bytes — the recorded hash
still matches, the publication guard never fires, and the test passes while
proving nothing.

Use the framework's existing **marker-gated seam** pattern instead
(`aitask_merge_task.sh:23-58`, gated on `<lock_base>/.ait_merge_test_seams`), so
the hook is inert in production by construction. Add two named seam points to
`aitask_sync.sh`, each a no-op unless the marker file exists:

| seam point | fires | proves |
|---|---|---|
| `pre_commit_phase` | after the dirty scan + first lock enumeration, **before** the 5a.2 re-enumeration | measure 2 |
| `pre_group_commit` | after the 5a.3 re-check, **immediately before** `task_git_commit_scoped` | measures 3 + 4 |

- **measure 2:** the `pre_commit_phase` seam runs `aitask_lock.sh --lock <tX>`.
  Assert the tX group is dropped with reason `lock_acquired_during_scan` and
  never committed.
- **measures 3 + 4, with `remote_ahead == 0` — the case a rebase-gated guard
  misses.** The `pre_group_commit` seam locks tX **and rewrites**
  `aitasks/tX_*.md`; the commit then genuinely captures the raced bytes. Set the
  fixture up so the **data branch has not advanced** (`origin/aitask-data`
  untouched — only `origin/aitask-locks` moved), which is the natural shape of
  this race and the state in which `do_push` would otherwise succeed. Assert
  exit **0** with `DEFERRED:publication_blocked:`, the report naming tX, and —
  the assertion that matters — that the raced bytes did **not reach the remote**
  on this run: read the path back out of the bare remote
  (`git -C "$TMP/remote.git" show <ref>:<path>`) and require the pre-race
  content, and assert `origin/aitask-data` did not advance.

  **This test must FAIL against a `remote_ahead`-gated deferral** — build it that
  way deliberately, since that inert-guard shape is exactly the defect being
  fixed and an assertion that passes under it proves nothing.

- **quarantine survives the process (two-run regression).** Continue the run
  above, with the seam marker **removed** so no new race can be detected, and the
  owner still holding the lock and still not having committed:
  - **run 2** → exit **0** with `DEFERRED:publication_blocked:`, and
    `origin/aitask-data` **still has not advanced**. The hold must come from the
    persisted entry, not from a fresh detection.
  - **negative control (proves persistence is load-bearing):** delete
    `<gitdir>/ait-sync-quarantine` between run 1 and run 2 → run 2 **pushes** and
    `origin/aitask-data` advances. Without this control, run 2's assertion would
    also pass if something incidental happened to block the push.
  - **release, clause 1:** the owner commits their version, then **run 3** →
    `HEAD:<path>` no longer equals the quarantined blob, the entry is released,
    the push happens, `origin/aitask-data` advances, and the quarantine file is
    empty.
  - **the natural clean-worktree, live-lock case stays quarantined — the
    discriminating test for the release rule.** After the race the path is clean
    *by construction* (`commit -o` committed the worktree bytes), and the owner's
    lock is still held by a live holder. Assert the entry is **still held** and
    nothing is pushed. **This test must FAIL against a cleanliness-only release
    clause**, which is the shape being rejected.
  - **release, clause 2 (ownership transition):** with the path clean, now make
    the lock stop being live — unlock it, or plant a `dead` PID anchor — and
    assert the next run releases and pushes. Both halves of clause 2 are
    required, so also assert the mirror: lock gone but path **dirty** → still
    held; path clean but lock **live** → still held (the case above).
  - **an unrelated live lock does NOT hold the entry — the scoping regression.**
    tX's quarantine, tX safely released (unlocked or its holder provably dead)
    and its path settled, while **tY remains live-locked**. Assert the entry
    clears and the run **pushes**. This must FAIL against a release gated on a
    global no-locks-anywhere verdict, which is the shape being rejected.
  - **`LOCKS_UNAVAILABLE` does not release:** with the path settled and tX's lock
    unreadable because the lock branch is unreachable, assert the entry is still
    held — an unreadable branch is not evidence the holder is gone.
  - **cross-host holder does not release:** a lock whose `hostname` is foreign
    yields `unknown` liveness, which counts as held → still quarantined.
  - **rebase-robustness:** advance `origin/aitask-data` from a sibling clone so
    the held commit is rebased and its SHA changes, then assert the entry is
    **still held** — the discriminating case for `(path, blob)` keying over
    SHA keying.
  - **age does NOT release — the expiry regression.** Stamp an entry older than
    `AIT_SYNC_QUARANTINE_WARN_AGE` while its holder is **still live**, and
    assert the entry is **still held**, nothing is pushed, and the report
    escalates: it names the holder and the age and contains the literal
    `--release-quarantine` command. Repeat for the two other unsafe states —
    an `unknown` cross-host holder, and `LOCKS_UNAVAILABLE` — since those are
    exactly the cases an expiry would have auto-published. **This test must FAIL
    against an age-based release.**
  - **`--release-quarantine`** empties the file and the next push succeeds —
    the only escape, and the one the escalated report points at.
- **negative control 1:** marker absent → tX is committed and pushed normally.
- **negative control 2:** the seam fires but writes **byte-identical** content →
  the hash still matches, so the run pushes normally. This proves the guard
  discriminates on content rather than on the seam having fired.

**Hazard B — foreign staged entry survives untouched.**
Stage `aitasks/tY_*.md` from a second process with content `C1`, leave the
worktree at `C2`, then run the sweep.

- **success path:** assert the tY group is deferred with reason
  `staged_elsewhere`, no commit names tY, and `git diff --cached` for tY is
  **byte-identical to `C1`** before and after the run
- **failure path:** force the group's commit to fail (a `pre-commit` hook exiting
  non-zero for that path) and assert the same byte-identical index invariant —
  i.e. the failure cleanup unstages only what this run staged
- **untracked-only staging:** a *tracked*, unstaged, unlocked, owned file is
  committed **without** ever being `git add`-ed. Assert on the **shared** index
  directly — `git diff --cached --name-only -- <path>` against
  `.git/worktrees/-aitask-data/index` is empty both before and after the run,
  while the commit does contain the path. Do **not** inspect the index from a
  `pre-commit` hook: under `commit --only` git points `GIT_INDEX_FILE` at a
  temporary index for the hook, so the hook cannot see the shared one.
- **mutex fail-closed:** hold `ait_lock_dir data_index` from a second process for
  longer than the acquire budget and assert the sweep commits **nothing**,
  reports the contention, and still exits 0

**Negative controls (required).** The bystander/ownerless assertions must FAIL
against the pre-fix `add aitasks/ aiplans/`.

Test conventions per `tests/test_lock_force.sh`; source `tests/lib/test_scaffold.sh`
then `tests/lib/asserts.sh`. Assertion argument order is
`assert_contains <desc> <needle> <haystack>`. If any test body runs inside a
`( … )` subshell, opt into the file-backed counters (`assert_counters_init` +
`assert_counters_load`) per CLAUDE.md.

Also run `shellcheck .aitask-scripts/aitask_sync.sh .aitask-scripts/aitask_lock.sh`
and `bash tests/run_all_python_tests.sh --test-dir tests` for the
`sync_action_runner` tests.

## Implementation notes (deviations and findings)

All steps landed. Deviations from the approved plan, each deliberate:

1. **`task_git_commit_scoped` got `--no-stage`, not a "stage only untracked"
   mode.** The plan had the helper decide which paths to stage; instead the
   sweep stages its own untracked paths and the helper stages nothing. Same
   guarantee — a tracked path another session may have staged is never
   re-staged — but staging and *unstaging* then have ONE owner, so the failure
   path can unstage exactly what this run staged without re-deriving the set.
   The default is unchanged, so t1599_1's and t1599_2's call sites are
   untouched (both suites pass).

2. **The wedged-worktree probe had to move to the top of `main()`.** In
   `auto_commit` it was unreachable: `check_remote` runs first and does
   `task_git remote get-url origin &>/dev/null`. `remote` is on neither
   allowlist, so `assert_data_worktree_clean` die()s — and `&>/dev/null`
   swallows the message, so the script exited 1 with empty stdout AND empty
   stderr, which is exactly the `ERROR: empty output` case the probe exists to
   prevent. Found by the test, not by reading.

3. **`git status --porcelain -z` output must go to a FILE.** Bash discards NUL
   bytes in command substitution, so `$(git status -z)` silently loses every
   separator it exists for.

4. **`-uall` is mandatory** (Step 2) and **an `R` entry only appears when both
   halves are staged** (Step 3) — both forced by the Step-1 spike; the step
   text carries the detail.

5. **The `DEFERRED:` reason set is three, not five.** `locks_unavailable` and
   `lock_contended` are per-file skip reasons that surface in the stderr report
   and roll up into `protected_dirty` on the wire. The derived token-contract
   test is what exposed the over-declaration.

6. **Step 6 emits `LOCKS_OK`, and `LOCKS_NONE` does not exist.** A global
   "nothing is locked" token invites being used as a per-task precondition; a
   readable branch with no locks is `LOCKS_OK` with zero `LOCK:` lines.

7. **The `DEFERRED:` parse branch fails CLOSED** (raised at Step-8 review).
   As first written it accepted any `DEFERRED:<reason>`, so a shell-side typo
   became a benign `severity="warning"` in both TUIs — and the syncer
   deliberately skips its failure capture for a deferral, so a real sync failure
   would have been silently suppressed. `parse_sync_output` now rejects a reason
   outside `DEFERRED_REASONS` (and an empty one) as `STATUS_ERROR`, matching the
   unknown-status branch beside it. Three tests pin it: an unknown reason, an
   empty reason, and the positive half that every declared reason still
   round-trips.

8. **Concurrent-session entanglement (raised at Step-8 review), resolved.**
   Mid-implementation `lib/task_utils.sh` briefly carried both this task's
   `--no-stage` hunk and t1658_2's uncommitted data-worktree ladder, so
   committing the file whole would have bundled foreign in-flight work — the
   exact defect t1599 exists to fix — and that work was itself failing
   `test_desync_state.py`. The plan was to stage only this task's hunks and
   verify the result in isolation. Before that was needed, t1658_2 landed
   (`a31f2b350`), so `task_utils.sh` now diffs to this task's change alone and
   the previously-failing test passes. Every suite was re-run against the
   advanced HEAD, since that commit rewrote `_ait_detect_data_worktree`, which
   this sweep consumes via `_AIT_DATA_WORKTREE` and `_ait_data_gitdir`.

9. **Delimiter losslessness (raised at Step-8 review) — CONFIRMED and fixed.**
   The dirty scan was parsed NUL-safely and then immediately thrown back into
   delimited strings, undoing the point of `-z`:
   - the grouped path list was **newline-joined**, so a legal path such as
     `aitasks/t60_line\nbreak.md` split into two bogus paths, missed in
     `PATH_STATE`, and under `set -u` aborted the whole script — reproduced:
     `STDOUT=[] rc=1`, `PATH_STATE[$p]: unbound variable`, file left dirty. That
     is precisely the empty-stdout `ERROR` this sweep exists to avoid.
   - the persisted quarantine record was `<path>|<blob>|<task>|<epoch>`, so a
     `|` in a path corrupted it. Reproduced against the pre-fix build: run 2
     **published the withheld commit** (`PUSHED`) — the unsafe release.

   Fixes: the grouping now carries paths as **array elements** (parallel
   `ent_path`/`ent_owner`, no delimiter — bash strings cannot hold NUL, so there
   is no safe delimiter to pick), and the quarantine record percent-encodes
   `%`, `|` and newline in the path (decoding `%25` last so an encoded literal
   does not decode twice). Every `PATH_STATE` read is `:-` guarded so a future
   miss degrades to "skip this group" instead of killing the script.

   Regressions: `test_sync_auto_commit_scoping.sh` Test 14b (newline and pipe
   filenames each committed under their own task, stdout a real token, nothing
   left dirty) and `test_sync_deferral_and_quarantine.sh` Test 18b (the record
   stores the encoded path, is exactly one line, and run 2 still holds it —
   which can only pass if the decode side is right). Both verified to FAIL
   against a rebuilt delimiter-joined control.

### Fixture work (tests/lib/sync_fixture.sh)

Extracted so both suites share one definition. Beyond the two gaps the plan
predicted (no lock branch, no `bin/hostname` shim), three more surfaced:

- sibling clones must use `git clone --branch aitask-data`. Checking out `main`
  first materialises the `aitasks` **symlink** it carries, and a later
  `git add -A` commits that symlink over the real directory, destroying every
  task file on the branch.
- a `pre-push` hook must `unset GIT_DIR GIT_WORK_TREE …` first. Git exports them
  into hooks, so the sibling clone fails, its `cd` fails, and the hook's edits
  land in the hook's own cwd — the repo's data worktree — surfacing much later
  as an inexplicable "cannot pull with rebase: You have unstaged changes".
- every fixture nests under one per-run base dir removed by an `EXIT` trap.
  Each repo carries a full copy of `.aitask-scripts`; an early leaking run left
  136 directories and several GB in `/tmp`.

### Verification performed

- `tests/test_sync_auto_commit_scoping.sh` — 36 assertions
- `tests/test_sync_deferral_and_quarantine.sh` — 52 assertions
- `tests/test_sync_action_runner.py` — 29 (incl. the derived token contract
  and the fail-closed deferral-reason tests)
- Regression: `test_sync.sh` (42), `test_sync_branch_mode_automerge.sh` (17),
  `test_task_lock.sh` (93), `test_stale_lock.sh` (134),
  `test_crash_recovery_pid_anchor.sh` (78), `test_lock_force.sh` (16),
  `test_lock_diag.sh` (9), `test_registry_lock.sh`,
  `test_pick_own_scoped_commit.sh`, `test_create_email_lock.sh`,
  `test_fold_mark.sh`, `test_no_raw_tmux.sh` — all pass
- `shellcheck` clean on `aitask_sync.sh`; `aitask_lock.sh` has only its
  pre-existing SC2086 in `cleanup_locks`

**Negative controls actually run** (each a mutated copy of the tree; every one
behaved as the plan claimed):

| control | result |
|---|---|
| pre-fix `add aitasks/ aiplans/` + bare commit | **18 of 32** fail, including the bystander, ownerless and foreign-staged-index assertions |
| publication guard gated on `remote_ahead` | Test 5 fails — reports `PUSHED` and the raced bytes reach the remote |
| cleanliness-only quarantine release | Test 10 fails — releases on run 1 and publishes |
| age-based quarantine release | Test 13 fails — publishes the raced content |
| `DEFERRED:` removed from the parser | the derived token-contract test fails |
| newline-joined grouping + unencoded quarantine record | Test 14b and Test 18b fail; the record control **publishes the withheld commit** |

Full Python suite: **6313 passed, 1 failed** at the time of the first run; the
single failure was t1658_2's then-uncommitted work (`data_symlinks.sh` missing
from a fixture's copy list) and passes now that it has landed.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.

## Risk

### Code-health risk: high

- `auto_commit` grows from 13 lines to a substantial routine (porcelain parse,
  owner grouping, lock enumeration, liveness routing) while `main()` runs under
  `set -euo pipefail`; a single unguarded non-zero exits the script with **no
  stdout**, which every consumer classifies as `ERROR: empty output` and the
  syncer escalates into an agent-resolution offer · severity: high · → mitigation: addressed in Step 1 + the `auto_commit`-never-aborts test in Verification
- Cross-host liveness: `lock_holder_liveness()` has no hostname awareness and
  will probe the local process table for a foreign PID, so without the Step-5
  guard a coincidentally-absent local PID reads `dead` and we commit a file
  another machine's live session owns — re-creating the exact defect · severity: high · → mitigation: addressed in Step 5 + the cross-host discriminating test
- The wire-protocol change spans 4 files in 2 languages; a token added in one and
  missed in another degrades silently to a red `unknown status` error · severity: medium · → mitigation: inline post-phase sync_token_contract_test
- The Hazard A tests depend on two new marker-gated seams inside
  `aitask_sync.sh`; a seam left reachable in production, or one placed at the
  wrong boundary, would either be a live hazard or a test that proves nothing
  (the `pre-commit` variant this plan rejects was exactly the latter) · severity: medium · → mitigation: addressed in Verification by copying `aitask_merge_task.sh:23-58`'s marker gate verbatim, plus negative control 2 (seam fires, identical bytes → normal push), which fails if the seam is mis-placed
- The sweep now takes a machine-local mutex and performs multi-stage CAS inside
  it; a mutex bug (retained lock, wrong fail direction) would stall every sync on
  the machine rather than one run · severity: medium · → mitigation: addressed in Step 3a by reusing `registry_lock.sh` (EXIT-trap release + dead-PID reclaim) rather than a new primitive, plus the mutex fail-closed test

### Goal-achievement risk: medium

- Ownerless files (`aitasks/metadata/stats_config.json`, `board_config.json`)
  have **no session that ever commits them** — verified: their writers only
  write. The plan's premise that they "stay dirty until the session that changed
  them commits them" does not hold, so an ownerless dirty file becomes a
  *permanent* rebase deferral, blocking all task-data sync until a human
  intervenes — a worse outcome than the swallow it replaces · severity: high · → mitigation: metadata_writers_commit_own_files (structural), inline post-phase prescriptive_deferral_report (actionability)
- `list_locks()` fails open in all three availability states today; if the
  tri-state probe is not wired, `LOCKS_UNAVAILABLE` silently degrades to
  `LOCKS_OK` and the sweep proceeds during an outage · severity: medium · → mitigation: addressed in Step 6 + the `LOCKS_UNAVAILABLE` test
- The lock status answers a **global** question ("is the snapshot trustworthy?")
  while eligibility and quarantine release are **per-task**; using one for the
  other over-blocks (an unrelated live lock pinning every push) or under-blocks · severity: medium · → mitigation: addressed by dropping the global `LOCKS_NONE` token in Step 6 so the conflation is not expressible, plus the tX-released-while-tY-live regression
- The publication hold is **durable on-disk state** with its own release rule; a
  clause that fires too eagerly publishes the raced bytes it exists to withhold
  (a cleanliness-only clause fires immediately, since `commit -o` leaves the path
  clean by construction), while one that never fires wedges every push on the
  machine · severity: high · → mitigation: addressed in Step 7c by requiring a verified ownership transition rather than cleanliness — and by tests that pin both directions, including ones written to fail against a cleanliness-only clause and against an age-based release
- **A held quarantine has no automatic termination and blocks every push, not
  just the raced commit.** A permanently `unknown` holder can hold it
  indefinitely; the only escape is a human running `--release-quarantine`. This
  is a deliberate safety-over-availability choice — an automatic expiry would
  publish raced bytes in exactly the states clause 2 refuses to release on —
  but the availability cost is real and unbounded in the worst case · severity: high · → mitigation: bounded by the escalating per-run report (Step 9) that names the holder, the age and the exact command, so the state is always visible and actionable rather than a silent wedge; the narrower partial-publication variant is sketched in Step 7c and deliberately deferred
- The run now has two orthogonal non-success outcomes (`protected_dirty`,
  `publication_blocked`) with different blocking semantics; merging them, or
  gating the publication one on `remote_ahead`, makes the integrity guard inert
  in exactly the scenario it exists for · severity: high · → mitigation: addressed in Steps 5a.4 / 7 / 7b by tracking them separately, plus the `remote_ahead == 0` test written to fail against a rebase-gated deferral
- Steps 3, 5a.3 and 5a.4 all rest on `commit -o -- <path>` recording a deletion
  and a two-path add+delete pair. If it does not, archive moves and deletions
  silently fail to commit while the CAS reports success · severity: medium · → mitigation: addressed by the Step 1 spike, which settles the primitive empirically before anything depends on it
- Residual TOCTOU: the `data_index` mutex is respected only by this sweep, and
  the claim path's acquire → write → commit sequence (`aitask_pick_own.sh`) is
  outside this child's ownership, so mutual exclusion is incomplete. Steps 5a.1-4
  reduce the window to a sub-millisecond one that cannot publish, but do not
  eliminate it · severity: medium · → mitigation: data_index_lock_adoption

### Planned mitigations
- timing: after | name: metadata_writers_commit_own_files | type: bug | priority: high | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — ownerless metadata files have no session that commits them, so an ownerless dirty file becomes a permanent rebase deferral | desc: make the settings TUI and board commit their own `aitasks/metadata/*` writes via `task_git_commit_scoped`, giving every tracked config edit an owner that clears it
- timing: post-phase | name: prescriptive_deferral_report | type: enhancement | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a deferral that does not self-clear must be actionable rather than mysterious | desc: every skipped file's report line names its reason, its holder, and the exact command that clears it; the DEFERRED line says what ends the deferral
- timing: after | name: data_index_lock_adoption | type: bug | priority: high | effort: high | inline_risk: high | added_complexity: high | addresses: code-health + goal-achievement — the `data_index` mutex introduced in Step 3a is respected only by this sweep, leaving mutual exclusion incomplete | desc: make every `.aitask-data` index writer take the shared `data_index` lock — the claim path's acquire→write→commit in `aitask_pick_own.sh`, `aitask_gate.sh`, and the attach/artifact transactions — closing the residual TOCTOU that Steps 5a.1-4 only narrow
- timing: post-phase | name: sync_token_contract_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the wire protocol spans 4 files in 2 languages and a missed token degrades silently to a red error | desc: derive the emitted-token set from `batch_out` literals and assert `parse_sync_output` recognises each, with a negative control

## Final Implementation Notes

- **Actual work done:** `auto_commit` replaced by a per-task sweep — NUL-safe
  `-z -uall` scan, owner grouping, live-lock skip via `lock_holder_liveness`
  with a cross-host guard, a `data_index` mutex over the whole classify→commit
  phase, snapshot + path-state CAS, a publication guard with a durable
  quarantine, and a prescriptive stderr report. `aitask_lock.sh` gained
  `--list --batch` with an availability verdict; `task_git_commit_scoped` gained
  an opt-in `--no-stage`; `DEFERRED` was wired through
  `sync_action_runner.py` + both TUIs + the website docs. Three new test files
  (36 + 52 assertions) plus 29 Python assertions.

- **Deviations from plan:** `--no-stage` rather than a "stage only untracked"
  mode in the helper, so staging and unstaging have one owner; the
  wedged-worktree probe moved to the top of `main()` (it was unreachable in
  `auto_commit` — `check_remote` die()s first with its message swallowed);
  `LOCKS_NONE` dropped in favour of `LOCKS_OK`; the `DEFERRED` reason set is
  three, not five. Each is argued in "Implementation notes" above.

- **Issues encountered:** four review findings, all confirmed and fixed — the
  `remote_ahead`-gated publication guard (inert in its own scenario), the
  cleanliness-only quarantine release (fires immediately, since `commit -o`
  leaves the path clean by construction), the age-based release (publishes
  exactly what the hold withholds), and delimiter losslessness (a newline in a
  path aborted the script with empty stdout; a `|` corrupted the quarantine
  record and published a withheld commit). Also: `git status` collapses
  untracked directories without `-uall`, bash drops NUL in command
  substitution, and git exports `GIT_DIR` into hooks.

- **Key decisions:** reuse the existing `stale_lock.sh`/`registry_lock.sh` mutex
  rather than a private temp index (no `GIT_INDEX_FILE` precedent in the tree);
  key the quarantine by `(path, blob)` so a rebase cannot invalidate it; make
  termination an explicit operator decision (`--release-quarantine`) rather than
  a timer; accept an all-or-nothing publication hold and record the narrower
  partial-publication variant as deferred.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_sync.sh:1078 — interactive conflict loop runs
    \`task_git add "$f" 2>/dev/null || true\` while the data worktree is
    mid-rebase; \`add\` is on neither allowlist so \`assert_data_worktree_clean\`
    calls \`die\` (exit 1), killing the \`echo | while\` subshell after the first
    file with the diagnostic swallowed by \`2>/dev/null\`. The sibling site at
    \`:940\` handles it correctly with \`AIT_GIT_SKIP_STATE_CHECK=1\`.`

- **Notes for sibling tasks:**
  - `task_git_commit_scoped` now takes an optional leading `--no-stage`. The
    default is unchanged, so t1599_4's mechanical `add` + bare `commit` →
    `commit -m <msg> -- <paths>` conversions are unaffected.
  - `aitask_lock.sh --list --batch` is the machine-readable lock snapshot; its
    verdict answers "is this snapshot trustworthy", never "is task X held".
    The human `--list` is load-bearing for `aitask_board.py`'s `refresh_lock_map`.
  - `tests/lib/sync_fixture.sh` is a reusable branch-mode fixture with a lock
    branch and a hostname shim. Three traps it encodes: clone siblings with
    `--branch aitask-data` (checking out `main` first materialises the `aitasks`
    symlink, which a later `git add -A` commits over the real directory);
    `unset GIT_DIR` at the top of any git hook; and nest every fixture under one
    base dir removed by an `EXIT` trap.
  - For t1599_4's tripwire: `aitask_sync.sh` no longer contains an unscoped
    `task_git commit`.

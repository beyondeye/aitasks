---
Task: t1560_1_merge_mutex_and_broker_script.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Sibling Tasks: aitasks/t1560/t1560_2_*.md, aitasks/t1560/t1560_3_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1560_1 — Merge mutex + broker script

## Context

Step 9's end-of-task merge is the only mutating operation in the pipeline with
zero serialization. It runs in the shared repo root, so every concurrently-merging
task drives one HEAD, one index and one working tree. The parent plan
`aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md` is the design of
record — its §1, §1a, §1b, §2, §2a and §3 are this task's specification. Three
design decisions were settled with the user before planning and must not be
re-litigated: parameterize `lib/stale_lock.sh` rather than fork it; hold the
mutex through verification and cleanup; decompose into three children.

This child ships the whole mechanism and is **provable end-to-end without
touching a single skill file** — which is why it goes first.

## Pre-phase (risk mitigations)

### characterize_stale_lock_callers

**Before any edit to `lib/stale_lock.sh`**, capture a baseline:

```bash
for t in test_stale_lock test_gate_lock_single_winner \
         test_registry_lock_single_winner test_parallel_child_create test_task_lock; do
  bash "tests/$t.sh" > "/tmp/baseline_$t.txt" 2>&1; echo "$t rc=$?"
done
```

Re-run the identical set once the seams land and diff. `lib/stale_lock.sh` is a
hardened primitive with three production callers (gate-ledger appends,
child-task numbering, the project/attach registry lock); the seams are default-off
precisely so this diff is empty. A non-empty diff is a defect in the seam, not a
test to update.

## Implementation

### Step 1 — Three opt-in seams in `.aitask-scripts/lib/stale_lock.sh`

Read the file's header first (t1496/t1507 invariants) and do not relax any of
them. All three seams default off; with all unset the file must behave exactly as
today.

| Seam | Default | Effect when set |
|---|---|---|
| `STALE_LOCK_IDENTITY_PID` | `$$` | value written into `<lock_dir>/pid` at publish time |
| `_STALE_LOCK_LIVENESS_FN` | unset | called as `<fn> <lock_dir>` at the top of `_stale_lock_reclaim_under_gc`; **sole** authority on the holder verdict (exit 0 = do not displace, 1 = reclaim), bypassing both the `kill -0` branch and the 120s tokenless-age branch |
| `STALE_LOCK_PUBLISH_FN` | unset | called as `<fn> <lock_dir>` **inside the `.gc` guard**, right after `pid`/`owner` are written and read-back-verified and before the guard is dropped; a nonzero return is a publish failure and takes the existing unwind-and-fail-closed path |

The third seam is required because the guard is released *inside*
`stale_lock_acquire` (currently `stale_lock.sh:207`) before it returns — a caller
cannot make its own identity files atomic with the acquisition from the outside.

Shape of the liveness seam, inserted after the existing
`[[ -d "$lock_dir" ]] || return 0` line:

```bash
if [[ -n "${_STALE_LOCK_LIVENESS_FN:-}" ]]; then
    if "$_STALE_LOCK_LIVENESS_FN" "$lock_dir"; then
        return 1                       # holder alive or undecidable: never displace
    fi
    warn "Reclaiming $label from dead holder"
    if _stale_lock_rm_verified "$lock_dir"; then return 0; else return 1; fi
fi
```

### Step 2 — `.aitask-scripts/lib/merge_lock.sh` (the adapter)

Same shape as `lib/registry_lock.sh`, including its "deliberate boundary deltas"
header convention — state what this adapter changes relative to the core and why,
and do not restate the core's invariants.

- Sets `STALE_LOCK_IDENTITY_PID` from `lib/pid_anchor.sh::get_session_anchor_pid`
  — the same session identity `aitask_lock.sh` anchors task locks to.
- Liveness fn reads the lock's recorded `pid` / `anchor_token` / `anchor_kind`
  and calls `lock_holder_liveness`: `dead` → reclaim; `alive` **or** `unknown` →
  never displace.
- Publish fn writes, under the guard, verified on read-back: `anchor_token`,
  `anchor_kind`, `task_id`, `output_branch`, `task_branch`, `acquired_at`.
- Lock name: one **global** lock per repo, `ait_lock_dir merge`. Two tasks
  merging into different output branches still share one HEAD, index and working
  tree, so a per-branch lock would not exclude them.

Only `state` (`merging` / `conflict` / `verifying`) is written after acquire, and
it is purely advisory — no decision reads it.

### Step 3 — `.aitask-scripts/aitask_merge_task.sh` (the broker)

```
begin <task_id> <output_branch> <task_branch> [--wait-secs N]
finish <task_id>
abort  <task_id>
cleanup <task_id> <task_name> --task-complete [<worktree_path>]
status
force-release [--abort-merge | --reset-hard] [--yes]
```

**Exit status is disjoint from the verdict** (the repo's `ait gates run`
contract): exit 0 = a verdict was produced, including `BUSY` and
`MERGE_CONFLICT`; nonzero = infrastructure failure only. Exactly one verdict line
on **stdout**; `WAITING:<holder_task>:<elapsed>` progress on **stderr**.

`begin` verdicts: `MERGE_OK:<sha>` · `MERGE_CONFLICT:<paths-csv>` ·
`MERGE_FAILED:<msg>` · `BUSY:<holder_task>:<waited>` · `PREFLIGHT_MISSING:<b>` ·
`UNSAFE_OUTPUT_BRANCH:<v>` · `PREFLIGHT_FOREIGN_WORKTREE:<path>` ·
`DIRTY_TREE:<n>` · `STALE_MERGE_RESIDUE` · `NO_SESSION_ANCHOR` ·
`LOCK_UNAVAILABLE:<reason>`.

Critical section, in order, after the lock is held:

1. `MERGE_HEAD` residue check → `STALE_MERGE_RESIDUE`, **release**;
2. dirty tracked tree (`git status --porcelain -uno`) → `DIRTY_TREE:<n>`, release;
3. pre-flight — fully-qualified `refs/heads/$output_branch`, and the
   foreign-worktree comparison against `git rev-parse --show-toplevel`, moved
   verbatim from the current Step 9 (including "reject only when the paths
   differ" — the repo root is itself listed in the porcelain output);
4. `git checkout "$output_branch" --` + `git symbolic-ref --short HEAD` assert;
5. `git merge "$task_branch"`, conflicts read from
   `git diff --name-only --diff-filter=U`.

Lock **retained** on `MERGE_OK` / `MERGE_CONFLICT` / `MERGE_FAILED`; released on
every pre-merge refusal. That retention is the behaviour change that fixes the
conflict-parked hazard.

Bind every user-authored branch name to a shell variable — never substitute the
literal. `git checkout "dev$(id)" --` executes `id`; `git checkout "$b" --` does
not.

#### 3a. The cross-process ownership contract (parent plan §1a)

`begin`, `finish` and `abort` are separate processes, so `STALE_LOCK_TOKEN`
cannot be the capability.

**The capability is required at acquire time so it exists at release time.**
`begin` refuses with `NO_SESSION_ANCHOR` when `get_session_anchor_pid` returns
the UNKNOWN sentinel, naming both remedies (`AIT_AGENT_PID`, tmux).

`finish` / `abort` / `cleanup` check, in order:

1. `<lock_dir>/task_id` == the `<task_id>` argument, else
   `NOT_HOLDER:<holder_task>`, nothing released.
2. `lock_anchor_is_self <anchor_pid> <anchor_token> <anchor_kind>` returns 0,
   else `NOT_OWNER_SESSION:<holder_task>:<anchor_pid>`. **A task-id match is
   never sufficient on its own** — two unidentifiable sessions on one task id
   would both pass, and the second would free the first's live reservation.
   `lock_anchor_is_self` is a literal triple comparison, not a liveness verdict,
   so a genuine holder proves identity on macOS too.
3. Only then read `<lock_dir>/owner` and pass it to `stale_lock_release`, which
   re-reads and re-compares it **under the `.gc` guard** — a lock reclaimed in
   between is a safe no-op.

`finish` verdicts: `RELEASED` · `NOT_HELD` · `NOT_HOLDER:<t>` ·
`NOT_OWNER_SESSION:<t>:<pid>` · `RETAINED:<reason>`.

**Incomplete acquisition is its own state.** A lock dir with no `task_id` can
never be matched by `finish` and is never auto-reclaimed. `status` reports
`HOLDER_INCOMPLETE:<anchor_pid>|<liveness>` and names `force-release`.

#### 3b. `abort` branches on the observed state

`git merge` fails **before** creating `MERGE_HEAD` for a whole class of errors
(unrelated histories, "local changes would be overwritten", a ref that is not
something we can merge), and `git merge --abort` on that state exits non-zero —
which on a path whose only job is to release would strand the reservation.

| observed state | action | verdict |
|---|---|---|
| `MERGE_HEAD` present | `git merge --abort`, then **verify** `MERGE_HEAD` gone, `-uno` clean, HEAD attached to `$output_branch` | `ABORTED` (release) / `ABORT_FAILED:<msg>` (lock **kept**) |
| no `MERGE_HEAD`, unmerged index | report only — do not discard a state we did not create | `ABORT_UNSAFE:unmerged_index_no_merge_head:--reset-hard` (lock **kept**) |
| no `MERGE_HEAD`, tree clean, HEAD attached | nothing to abort | `RELEASED_NO_MERGE` (release) |
| no `MERGE_HEAD`, tree dirty or HEAD detached | report — never hand a detached HEAD to the next caller | `ABORT_UNSAFE:<state>:--reset-hard` (lock **kept**) |

State is **verified after the action, never assumed from its exit status**.
`ABORT_UNSAFE` carries its own `<remedy_flag>` so callers echo it rather than
hardcoding one.

#### 3c. `force-release` — the one terminating remedy

- **Dry-run by default.** Without `--yes` it only prints the resolved lock dir,
  holder task, anchor pid + liveness verdict, and the tree residue found — the
  destructive-step preflight before anything is touched.
- **Never break a live holder.** `alive` → `REFUSED_LIVE_HOLDER:<task>:<pid>`,
  nothing done, saying what to do instead. It is for `dead` and `unknown` only.
- **Two distinct remedies**, and the dry-run report names which applies:

  | observed state | remedy | after |
  |---|---|---|
  | `MERGE_HEAD` present | `--abort-merge` → `git merge --abort` | verify `MERGE_HEAD` gone, `-uno` clean, HEAD attached |
  | unmerged index, **no** `MERGE_HEAD` (or a dirty tree blocking checkout) | `--reset-hard` → `git reset --hard HEAD`, after printing the exact `git status --porcelain` blast radius | verify `-uno` clean, HEAD attached |
  | clean tree | neither flag | verify HEAD attached |

  A mismatched flag is **refused, not attempted**: `--abort-merge` with no
  `MERGE_HEAD` → `WRONG_REMEDY:no_merge_head` naming `--reset-hard`.
  Recovery that does not reach a verified-clean tree → `RECOVERY_FAILED:<msg>`,
  lock **kept**, and the dry-run report carries a precise manual repair sequence
  as the terminal rung.
- Only then remove the lock dir (bypassing the owner-token check — that bypass is
  the point of "force") → `FORCE_RELEASED:<prev_task>`.

#### 3d. `cleanup` (parent plan §2a)

- **`--task-complete` required**, else `CLEANUP_REQUIRES_COMPLETION`, nothing
  changed. Deleting `aitask/<task_name>` on a path that leaves the task in-flight
  would destroy the branch its resume must re-merge.
- Same authorization as `finish`/`abort`.
- `aitask/<task_name>` must equal the recorded `task_branch`, else
  `TARGET_MISMATCH:<recorded>`.
- Path **derived** from the `worktree <path>` line of the same porcelain record
  whose branch is `refs/heads/aitask/<task_name>` — a moved worktree makes the
  conventional guess wrong and the failure would be a silent `rm -rf` of the
  wrong path. The positional argument is a fallback only.
- Guarded, verified removal in the `task-abort.md:57-88` shape: `git worktree
  remove` → on failure report, do **not** `rm -rf` blindly; `git worktree prune`;
  `git branch -d` → on "not fully merged", report rather than escalating to `-D`.
- Verdicts: `CLEANED` · `CLEANED_PARTIAL:<what_remains>` (**keeps** the
  reservation) · the three refusal verdicts · `TARGET_MISMATCH:<recorded>`.

### Step 4 — Test-only seams

Honoured **only** when `AITASKS_LOCK_DIR` is set, so they are unreachable in a
real user environment. Warn on stderr when either is active.

- `AIT_MERGE_LOCK_DISABLED=1` — skip the acquire. Makes the red proof reachable
  and "the guard actually gates" executable rather than a hand mutation.
- `AIT_MERGE_BROKER_HOOK=<cmd>` — run inside the critical section between the
  checkout and the merge. Tests rendezvous on FIFOs through it (a blocking read
  is a deterministic rendezvous), so **no test sleeps to reproduce a race**.

### Step 5 — Helper whitelist, all five touchpoints

`aitask_merge_task.sh` is skill-invoked (t1560_2 wires it into Step 9), so per
`aidocs/framework/aitasks_extension_points.md:163-184` it needs one entry in each
of `.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`. `lib/merge_lock.sh` is sourced, not invoked —
**no** entries. No `ait` dispatcher subcommand.

### Step 6 — Export the verdict vocabulary for t1560_2

t1560_2 must assert mechanically that every verdict gets a Step 9 branch. Provide
a stable list (a `--list-verdicts` verb, or a single clearly-delimited comment
block the sibling's test can parse) rather than leaving it to be transcribed.

## Post-phase (risk mitigations)

### wedge_recovery_probe

Test case 7 below, promoted to a named phase: drive the unresolvable-anchor path
to a wedged merge lock and assert `status` names the holder with its liveness
verdict and `force-release` clears it — proving the recovery ladder **terminates**
rather than documenting a hazard.

## Verification

`aidocs/framework/testing_conventions.md:10,18` mandates the enumeration below.

**Fixture rule for every recovery assertion:** mergeability is a property of the
fixture, so "the lock works again" is always proved by a task whose branch merges
**cleanly** into `<output_branch>` — never by re-running the branch whose merge
produced the residue. Keep three shapes on hand: cleanly-mergeable, conflicting,
unrelated-history.

| # | Case | Assertion |
|---|---|---|
| 1 | Red proof, mutex disabled | A parks between checkout and merge (FIFO hook); B merges; A resumes → A's merge commit's tree **contains B's file**. With the mutex enabled: B reports `BUSY:tA`, A's commit is clean |
| 1n | Negative control for 1 | The mutation must reach the *merge-contamination* assertion, not trip an earlier one — assert the named failing case |
| 2 | N = 51 concurrent callers | each runs `begin … --wait-secs <budget>` and on `BUSY` **retries to completion** up to a bounded cap, then `finish`es. Assert exactly 51 `MERGE_OK`, 51 merge commits, one per logical caller; zero nonzero exits; and **at least one** `BUSY`/`WAITING` naming a real holder (else vacuous). Exhausting the cap is a failure |
| 3 | Conflict-parked reservation | A stops at `MERGE_CONFLICT`; B does **not** enter, its report names A's task id; after A's `abort`, B proceeds |
| 4 | Stale-holder recovery | anchor = an `AIT_AGENT_PID` fixture process; killed mid-section → exactly **one** waiter reclaims. Live-anchored → never displaced; `unknown` → never displaced |
| 5 | Guard gates | removing the acquire (documented seam) makes case 1 and case 3 fail |
| 6 | Callers unchanged | the five baseline test files still pass, diffed against the pre-phase capture |
| 7 | Wedge recovery terminates | unresolvable anchor → never auto-reclaimed; `status` names it; `force-release --yes` clears it. Live holder → `REFUSED_LIVE_HOLDER`, lock intact. `MERGE_HEAD` + no flag → `RESIDUE_PRESENT`, lock intact; `--abort-merge` → verified clean + released. **Both residue states separately**: unmerged-index-without-`MERGE_HEAD` (plant by conflicting a merge then removing `.git/MERGE_HEAD`) → `--abort-merge` returns `WRONG_REMEDY:no_merge_head` lock **kept**, `--reset-hard --yes` reaches a verified-clean tree and releases. Every rung's "usable again" proof is a `begin` from a **different, cleanly mergeable task** |
| 8 | Non-owner release refused | (a) B's `finish`/`abort`/`cleanup` vs A's lock → `NOT_HOLDER:tA`, intact, A can still `finish`. (b) same task id, caller that cannot prove its anchor → `NOT_OWNER_SESSION`, intact. (c) same task id, provably different live session → `NOT_OWNER_SESSION`. (d) planted dir with no `task_id` → `HOLDER_INCOMPLETE`, cleared by `force-release --yes`. (e) `begin` with no anchor → `NO_SESSION_ANCHOR`, nothing locked |
| 8b | Non-conflict merge failure | task **U** with a history unrelated to `<output_branch>` → `git merge` fails before `MERGE_HEAD` → `MERGE_FAILED`; `abort` → `RELEASED_NO_MERGE` (**not** `ABORT_FAILED`). Usable-again proof comes from a **different, cleanly mergeable task V** — re-running U would fail identically forever. Plus planted no-`MERGE_HEAD`-but-unmerged-index → `ABORT_UNSAFE`, lock **kept** |
| 8c | Verification window does not strand the lock | scripted caller mimicking Step 9: `begin` → **injected failing verification command** → "release and stop" branch → `finish` **without** cleanup. Lock free, merge commit intact, `aitask/<task_name>` + worktree still present. Re-run `begin` on that retained branch → `MERGE_OK` with **no new commit** |
| 9 | Publish is atomic with acquire | `STALE_LOCK_PUBLISH_FN` returning nonzero → `stale_lock_acquire` unwinds, **no** lock dir left behind, contender's next attempt succeeds |
| 10 | Cleanup authorization + partial failure | no `--task-complete` → `CLEANUP_REQUIRES_COMPLETION`, branch+worktree intact, following `begin` still reaches `MERGE_OK`. Non-owner → refused. `<task_name>` ≠ recorded `task_branch` → `TARGET_MISMATCH`. **Moved** worktree still found. Undeletable worktree / unmerged branch → `CLEANED_PARTIAL:<remains>`, reservation **still held** |

Also: `shellcheck .aitask-scripts/aitask_merge_task.sh .aitask-scripts/lib/merge_lock.sh .aitask-scripts/lib/stale_lock.sh`.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge per the shared workflow's Step 9.

## Non-goals

- No Step 9 / skill edits — **t1560_2**.
- No website docs — **t1560_3**.
- No fetch added to Step 9 (**t1393**); no edit-time file-overlap advice
  (**t1343** / **t1344**); no change to push behaviour.

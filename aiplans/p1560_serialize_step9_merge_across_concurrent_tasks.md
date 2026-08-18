---
Task: t1560_serialize_step9_merge_across_concurrent_tasks.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1560 — Serialize the Step 9 merge across concurrent tasks

**Decomposition plan.** This parent designs the mechanism and splits into three
children; no code lands under this task itself.

### Pre-phase (risk mitigations)

- **characterize_stale_lock_callers** — carried into `t1560_1`'s plan as its
  first step, before any edit to `lib/stale_lock.sh`: capture a baseline run of
  `tests/test_stale_lock.sh`, `test_gate_lock_single_winner.sh`,
  `test_registry_lock_single_winner.sh`, `test_parallel_child_create.sh` and
  `test_task_lock.sh`, then diff the same runs once the seams land.

## Context

Step 9's end-of-task merge is the only mutating operation in the whole pipeline
with **zero serialization**. It runs in the *shared repo root* (`SKILL.md:745`
explicitly says "not from `aiwork/<task_name>/`"), so every concurrently-merging
task drives one HEAD, one index and one working tree:

```bash
git checkout "$output_branch" --
git symbolic-ref --short HEAD
git merge "aitask/<task_name>"
```

The existing pre-flight cannot detect the race by design — `SKILL.md:758`
deliberately permits "the current tree is already on the output branch", which is
exactly the state both racing agents are in — and `symbolic-ref` only proves HEAD
is attached, not that *we* attached it. The damaging outcome is not repo
corruption (git's own `index.lock` prevents that) but **misattributed content**:
a conflict-parked merge leaves the shared tree reserved by nobody, so the second
agent's merge commit absorbs the first agent's half-resolved conflict work.

Nothing existing covers it: `grep -rn flock` returns nothing; `aitask_lock.sh`
excludes two sessions from *the same task ID*, not two different tasks from the
shared root; `lib/stale_lock.sh`'s adapters guard the gate ledger, child-task
numbering, the project registry and attach transactions — **no caller guards the
merge**.

**Outcome:** one broker process owns the critical section end-to-end behind a
session-anchored mutex, a conflict-parked merge keeps the tree reserved until the
human is done, and a queued agent can tell the user *which task* it is waiting on.

## Design (settled with the user before planning)

### 1. Mutex core — parameterize `lib/stale_lock.sh`, do not fork it

The reservation must survive **between agent turns**: each Bash tool call is a
separate short-lived process, so `stale_lock.sh`'s `$$` + `kill -0` holder
identity dies the instant `begin` returns and the next contender would reclaim a
tree that is still being conflict-resolved.

Three **opt-in, default-off** seams are added to `lib/stale_lock.sh`; with all
three unset the file behaves exactly as today, so `aitask_gate.sh`,
`aitask_create.sh` and `lib/registry_lock.sh` are untouched:

| Seam | Default | Effect when set |
|---|---|---|
| `STALE_LOCK_IDENTITY_PID` | `$$` | value written into `<lock_dir>/pid` at publish time |
| `_STALE_LOCK_LIVENESS_FN` | unset | called as `<fn> <lock_dir>` at the top of `_stale_lock_reclaim_under_gc`; **sole** authority on the holder verdict (exit 0 = do not displace, 1 = reclaim), bypassing both the `kill -0` branch and the 120s tokenless-age branch |
| `STALE_LOCK_PUBLISH_FN` | unset | called as `<fn> <lock_dir>` **inside the `.gc` guard**, immediately after `pid`/`owner` are written and read-back-verified and before the guard is dropped; a nonzero return is a publish failure and takes the existing unwind-and-fail-closed path |

The third seam exists because the guard is released *inside*
`stale_lock_acquire` (`stale_lock.sh:207`) before it returns — so a caller
cannot make its own identity files atomic with the acquisition from the outside.
Everything a later process needs to reason about the holder is therefore written
by the publish fn, under the guard, verified on read-back: `anchor_token`,
`anchor_kind`, `task_id`, `output_branch`, `task_branch`, `acquired_at`. Only
`state` (`merging` / `conflict` / `verifying`) is written afterwards, and it is
purely advisory — no decision reads it.

`lib/merge_lock.sh` is the adapter (same shape as `lib/registry_lock.sh` — that
file's header documents the "deliberate boundary deltas" convention to follow).
It sets `STALE_LOCK_IDENTITY_PID` from `lib/pid_anchor.sh::get_session_anchor_pid`
— the same session identity `aitask_lock.sh` anchors task locks to — and supplies
a liveness fn that reads the lock's recorded `pid` / `anchor_token` /
`anchor_kind` and calls `lock_holder_liveness`:

- `dead` → reclaim (single-winner, under the existing `.gc` guard);
- `alive` **or** `unknown` → never displace. "Cannot tell" is never rounded up to
  "go ahead" — the rule `pid_anchor.sh` already documents and `locks.md` already
  publishes for task locks.

Lock name: **one global lock per repo**, `ait_lock_dir merge`. Two tasks merging
into *different* output branches still share the same HEAD, index and working
tree, so a per-branch lock would not exclude them. `ait_lock_dir` is already
per-user, per-repo and `AITASKS_LOCK_DIR`-overridable.

**When the anchored session dies mid-conflict** the next contender's liveness fn
reports `dead` and reclaims — but the tree still holds `MERGE_HEAD` and a
conflicted index, so `begin` refuses with `STALE_MERGE_RESIDUE` rather than
merging on top of it. **When the anchor is unresolvable** (no tmux pane, no
`AIT_AGENT_PID`) the verdict is `unknown` and the lock is *never* auto-reclaimed.

### 1a. Who may release — the cross-process ownership contract

`begin`, `finish` and `abort` are three **separate processes**, so
`STALE_LOCK_TOKEN` (an in-process value) cannot be the capability. The durable
capability is the identity triple the publish fn wrote under the guard, and
`finish` / `abort` **must** re-derive and check it before releasing:

**The capability is required at acquire time, so that it exists at release
time.** `begin` refuses outright when `get_session_anchor_pid` returns the
UNKNOWN sentinel: `NO_SESSION_ANCHOR`, nothing locked, with the remedy named
(export `AIT_AGENT_PID`, or run the agent under tmux — the two rungs of the
`pid_anchor.sh` ladder). Handing out a reservation whose owner cannot later be
proven is what creates the hole below; refusing it is the producer-side half of
the consumer guard. This only affects worktree-mode profiles — a shared-checkout
profile never invokes the broker at all.

1. **Task match (the between-tasks discriminator).** `<lock_dir>/task_id` must
   equal the `<task_id>` argument. Anything else → `NOT_HOLDER:<holder_task>`,
   exit 0, **nothing released**. This alone is what stops task B's `finish` from
   freeing task A's live reservation.
2. **Session match — fail closed, no `unknown` escape hatch.**
   `lock_anchor_is_self <anchor_pid> <anchor_token> <anchor_kind>`
   (`lib/pid_anchor.sh:224`) must return 0. It is a literal pid+token+kind
   comparison, *not* a liveness verdict, so it succeeds for a genuine holder on
   macOS too (where `lock_holder_liveness` would only ever say `unknown` for the
   weak `ps` token). Anything else — a different session, or a caller that cannot
   name its own anchor — is refused: `NOT_OWNER_SESSION:<holder_task>:<anchor_pid>`,
   nothing released, pointing at `force-release`.

   **Task-id match must never be sufficient on its own.** Two *unidentifiable*
   sessions working the same task id would both pass a task-only check, and the
   second would free the first's live reservation. Appealing to "`aitask_lock.sh`
   already excludes that" is circular: `locks.md` documents the anchor-less lock
   as precisely the **claimable** row, so the case where the merge capability is
   weakest is the case where the task lock is weakest too. The residual
   unprovable-owner situations therefore route to the human via `force-release`,
   which has its own live-holder refusal — never to an automatic release.
3. **Token, re-read not remembered.** Only then does the broker read
   `<lock_dir>/owner` and hand it to `stale_lock_release`, which re-reads and
   re-compares `owner` **under the `.gc` guard** before removing anything
   (`stale_lock.sh:266-275`). So a lock reclaimed between our read and the
   release is a safe no-op — the reader never deletes a new owner's lock.

`finish` verdicts: `RELEASED` · `NOT_HELD` · `NOT_HOLDER:<t>` ·
`NOT_OWNER_SESSION:<t>:<pid>` · `RETAINED:<reason>` (a genuinely undeletable
lock — surfaced, never reported as success).

**`abort` branches on the actual merge state — it must not assume `MERGE_HEAD`
exists.** `git merge` fails *before* creating `MERGE_HEAD` for a whole class of
errors (unrelated histories, "local changes would be overwritten by merge", a
ref that is not something we can merge), and `git merge --abort` on that state
exits non-zero with "there is no merge to abort" — which, on a path whose only
job is to release, would strand the reservation permanently. After the same three
authorization checks:

| observed state | action | verdict |
|---|---|---|
| `MERGE_HEAD` present | `git merge --abort`, then **verify** `MERGE_HEAD` gone, `git status --porcelain -uno` clean, HEAD attached to `$output_branch` | `ABORTED` (release) / `ABORT_FAILED:<msg>` (lock **kept**) |
| no `MERGE_HEAD`, index has unmerged paths | report only — do **not** silently discard a state we did not create | `ABORT_UNSAFE:unmerged_index_no_merge_head:--reset-hard` (lock **kept**) |
| no `MERGE_HEAD`, tree clean, HEAD attached | nothing to abort; the merge failed before touching anything | `RELEASED_NO_MERGE` (release) |
| no `MERGE_HEAD`, tree dirty or HEAD detached | report — never hand a detached HEAD or a dirty tree to the next caller | `ABORT_UNSAFE:<state>:--reset-hard` (lock **kept**) |

Plus the three refusal verdicts. The state is **verified after the action, not
assumed from its exit status**.

**`ABORT_UNSAFE` carries its own remedy flag** —
`ABORT_UNSAFE:<state>:<remedy_flag>` — so the rendered workflow echoes the flag
the broker named instead of re-deriving it. The broker is the single source of
the state→remedy mapping; a skill that hardcodes one command will eventually name
the wrong one for the state it is in, which is exactly how a user gets sent to a
`WRONG_REMEDY` refusal.

**Incomplete acquisition is its own state.** If `<lock_dir>/task_id` is missing,
no `finish` can ever match it and no contender will ever reclaim it (`unknown`
anchor). `status` reports `HOLDER_INCOMPLETE:<anchor_pid>|<liveness>` rather than
`FREE` or a normal holder line, and names `force-release` as the remedy. The
guarded publish above makes this state unreachable through the normal path, so
its test **plants** the directory shape directly.

### 1b. `force-release` — the one terminating remedy

A recovery instruction that leaves the next `begin` at `STALE_MERGE_RESIDUE` has
not terminated. `force-release [--abort-merge] [--yes]` therefore does all of it,
in this order, and refuses rather than half-acting:

- **Dry-run by default.** Without `--yes` it only *prints* the resolved lock dir,
  the holder task, the anchor pid and its liveness verdict, and the tree residue
  it found — the destructive-step preflight (resolved target + blast radius)
  before anything is touched.
- **Never break a live holder.** If liveness is `alive`, refuse:
  `REFUSED_LIVE_HOLDER:<task>:<pid>`, exit 0, nothing done, and say what to do
  instead (let that session run `finish` / `abort`, or stop it). `force-release`
  is for `dead` and `unknown` only. This is the same "a live PID is never
  displaced" invariant the automatic path obeys, raised to the manual path.
- **Clear the tree, not just the directory — and branch on the observed state,
  exactly as `abort` does.** `git merge --abort` requires `MERGE_HEAD`; applying
  it to an unmerged index that has no `MERGE_HEAD` fails for the very reason
  `abort` bailed out, and a recovery path that can fail the same way as the thing
  it recovers is not a ladder. So the two states get **two distinct, separately
  confirmed remedies**, and the dry-run report *names which one applies* rather
  than making the human guess:

  | observed state | remedy | after |
  |---|---|---|
  | `MERGE_HEAD` present | `--abort-merge` → `git merge --abort` | verify `MERGE_HEAD` gone, `-uno` clean, HEAD attached to a branch |
  | unmerged index, **no** `MERGE_HEAD` (or a dirty tree blocking checkout) | `--reset-hard` → `git reset --hard HEAD`, after printing the exact `git status --porcelain` blast radius it will discard | verify `-uno` clean, HEAD attached |
  | clean tree | neither flag needed | verify HEAD attached |

  A mismatched flag is refused, not attempted: `--abort-merge` with no
  `MERGE_HEAD` → `WRONG_REMEDY:no_merge_head` naming `--reset-hard`, nothing
  touched. Recovery that does not reach a verified-clean tree →
  `RECOVERY_FAILED:<msg>` with the lock **kept**, and the dry-run report carries a
  precise manual repair sequence as the terminal rung, so even total failure has a
  documented human exit.
- Only then remove the lock dir (bypassing the owner-token check — that bypass is
  the whole point of "force") → `FORCE_RELEASED:<prev_task>`.

`abort`'s `ABORT_UNSAFE` message points at whichever of these two remedies
matches the state it observed — never unconditionally at `--abort-merge`.

### 2. `.aitask-scripts/aitask_merge_task.sh` — the broker

```
begin <task_id> <output_branch> <task_branch> [--wait-secs N]
finish <task_id>
abort  <task_id>
cleanup <task_id> <task_name> [<worktree_path>]
status
force-release [--abort-merge | --reset-hard] [--yes]
```

**Exit status is disjoint from the verdict** (the repo's `ait gates run`
contract): exit 0 = a verdict was produced, including `BUSY` and
`MERGE_CONFLICT`; nonzero = infrastructure failure only. Exactly one verdict line
on **stdout**; `WAITING:<holder_task>:<elapsed>` progress goes to **stderr** so a
long queue is legible without polluting the data channel.

`begin` verdicts: `MERGE_OK:<sha>` · `MERGE_CONFLICT:<paths-csv>` ·
`MERGE_FAILED:<msg>` · `BUSY:<holder_task>:<waited>` · `PREFLIGHT_MISSING:<b>` ·
`UNSAFE_OUTPUT_BRANCH:<v>` · `PREFLIGHT_FOREIGN_WORKTREE:<path>` ·
`DIRTY_TREE:<n>` · `STALE_MERGE_RESIDUE` · `NO_SESSION_ANCHOR` ·
`LOCK_UNAVAILABLE:<reason>`.

Critical section, in order, after the lock is held:
1. `MERGE_HEAD` residue check → `STALE_MERGE_RESIDUE`, **release**;
2. dirty tracked tree (`git status --porcelain -uno`) → `DIRTY_TREE:<n>`, release
   (Step 8 has already committed, so a clean tree is the norm);
3. pre-flight — fully-qualified `refs/heads/$output_branch`, and the
   foreign-worktree comparison against `git rev-parse --show-toplevel` (the
   *existing* Step 9 logic, moved verbatim, including "reject only when the paths
   differ");
4. `git checkout "$output_branch" --` + `symbolic-ref` assert;
5. `git merge "$task_branch"`, conflicts read from
   `git diff --name-only --diff-filter=U`.

The lock is **retained** on `MERGE_OK` / `MERGE_CONFLICT` / `MERGE_FAILED` and
released on every pre-merge refusal. That retention is the behaviour change that
fixes the conflict-parked hazard.

### 2a. `cleanup` — authorized, record-derived, and honest about partial failure

`cleanup <task_id> <task_name> --task-complete [<worktree_path>]` runs **while
the lock is still held** and is not a thin wrapper around three unguarded git
calls:

- **Completion is required, not assumed.** Without `--task-complete` it refuses
  with `CLEANUP_REQUIRES_COMPLETION` and changes nothing. Deleting
  `aitask/<task_name>` on a path that leaves the task in-flight would destroy the
  branch its resume must re-merge (see §4a).
- **Same authorization as `finish`/`abort`** (task match + provable session
  match, same refusal verdicts), so a stray caller cannot delete another task's
  worktree or branch.
- **Target validation.** `aitask/<task_name>` must equal the `task_branch` the
  publish fn recorded; otherwise `TARGET_MISMATCH:<recorded>` and nothing is
  removed.
- **Path derived, not trusted.** The directory comes from the `worktree <path>`
  line of the *same* `git worktree list --porcelain` record whose branch is
  `refs/heads/aitask/<task_name>` — a moved worktree makes the conventional
  `aiwork/<task_name>` guess wrong, and the failure would be a silent `rm -rf` of
  the wrong path. The positional argument is a fallback only.
- **Guarded, verified removal** in the shape `task-abort.md:57-88` already uses:
  `git worktree remove` → on failure, report and do **not** `rm -rf` blindly;
  `git worktree prune`; `git branch -d` → on "not fully merged", report rather
  than escalating to `-D`.
- Verdicts: `CLEANED` · `CLEANED_PARTIAL:<what_remains>` · the three refusal
  verdicts · `TARGET_MISMATCH:<recorded>`. `CLEANED_PARTIAL` **keeps the
  reservation** — the workflow must surface exactly what remains and offer
  "retry cleanup" / "proceed anyway (releases the reservation, leaves
  \<remains\>)", so the ladder terminates without ever reporting success for a
  partial cleanup.

**The mutex is held through verification and cleanup**, released only by `finish`.
Justification (Scope §3 demands one): releasing after the merge commit does not
merely make `./ait gates run`'s verdict unattributable — it lets another task
`checkout` + `merge` **into the working tree the build is reading**, so the run is
racing a mutating tree, not just measuring `main + A + B`. The cost is
serialization of multi-minute test runs; it is paid for by the `--wait-secs`
budget, the stderr `WAITING` progress, and a `status` probe that lets the merge
prompt name the task it is queued behind.

### 3. Test-only seams (both honoured **only** when `AITASKS_LOCK_DIR` is set)

- `AIT_MERGE_LOCK_DISABLED=1` — skip the acquire. This is what makes AC 1's red
  proof *reachable* and AC 5's "the guard actually gates" *executable* rather than
  a mutation performed by hand.
- `AIT_MERGE_BROKER_HOOK=<cmd>` — run inside the critical section between the
  checkout and the merge. Tests rendezvous on FIFOs through it, so the
  interleaving is deterministic and **no test sleeps to reproduce a race**.

### 4. Step 9 control flow — one branch per verdict, no fall-through

The rendered Step 9 must define **every** transition; a verdict with no branch is
how an agent ends up running `./ait gates run` after a refused `begin`, or
holding the reservation forever after a failed merge. The governing invariant,
stated in the skill text itself:

> Every path on which the broker reported the lock **held** ends in exactly one
> `finish` or `abort`. Every path on which it is **not** held calls neither, and
> never proceeds to verification, cleanup or archival.

| `begin` verdict | Lock | Step 9 branch |
|---|---|---|
| `MERGE_OK:<sha>` | held | verification block (§4a decides whether cleanup runs) → `finish` |
| `MERGE_CONFLICT:<paths>` | held | show the paths; ask "Resolve conflicts now" / "Abort the merge". Resolve → user resolves + commits → verification block (§4a) → `finish`. Abort → `abort <task_id>` → **end the workflow**, task stays in-flight (re-enterable at `POSTIMPL`). The reservation is held throughout — this is the hazard the task exists to fix |
| `MERGE_FAILED:<msg>` | held | surface `<msg>`, run `abort <task_id>` and branch on **its** verdict (`RELEASED_NO_MERGE` is the normal outcome here — the merge failed before `MERGE_HEAD` existed; `ABORT_UNSAFE:<state>:<remedy_flag>` means the lock is still held and a human must run `force-release <remedy_flag> --yes` — **echo the flag the broker named**, never a hardcoded one, or the user is sent to a `WRONG_REMEDY` refusal). **Stop** either way: no verification, no cleanup, no archival |
| `BUSY:<holder>:<waited>` | not held | name the holding task; ask "Wait and retry" / "Stop here". Retry → re-run `begin` (bounded — after 3 declines, stop). Stop → end the workflow, task stays in-flight |
| `STALE_MERGE_RESIDUE` | not held | surface the residue and the `force-release --abort-merge --yes` remedy; **stop** |
| `DIRTY_TREE:<n>` | not held | list the modified tracked files; stop and ask the user to commit or stash. No automatic retry |
| `PREFLIGHT_MISSING:<b>` | not held | the **existing** Step 9 "branch missing locally" prompt (fetch / create / pick another / abort) |
| `PREFLIGHT_FOREIGN_WORKTREE:<p>` | not held | the **existing** "held by another worktree" prompt, naming `<p>` |
| `UNSAFE_OUTPUT_BRANCH:<v>` | not held | stop and report — existing behaviour, unchanged |
| `NO_SESSION_ANCHOR` | not held | stop; explain the anchor requirement and both remedies (`AIT_AGENT_PID`, tmux) |
| `LOCK_UNAVAILABLE:<reason>` | not held | infrastructure problem — surface and stop |
| **nonzero exit** | not held | infrastructure failure — STOP and diagnose; do **not** fall through to any branch above (the same rule Step 9 already states for `ait gates run`) |

Cleanup verdicts branch too: `CLEANED` → `finish`; `CLEANED_PARTIAL:<remains>` →
surface, offer retry / proceed-anyway, then `finish`; any refusal verdict →
surface as a defect and still `finish` (the reservation must not outlive the
session).

#### 4a. The verification window — the longest stretch the lock spans

`MERGE_OK` hands control to Step 9's existing `./ait gates run` block, and that
block's own outcomes (`fail` → "fix and re-run, repeat until it passes";
`error` / `blocked` → "do not proceed to archival"; `pending` → wait for a human)
can run indefinitely. Because the reservation deliberately spans this window,
**every one of those outcomes needs a release decision** — and `abort` is *not*
the answer on any of them: the merge commit already exists on `<output_branch>`
and `git merge --abort` cannot undo a completed merge.

| verification outcome | branch |
|---|---|
| all `pass` / `skip`, or `gates_out` shows no declared gates and `verify_build` passed | `cleanup` → `finish` — the normal path |
| `fail` **caused by this task** | fix and re-run **while holding** — that is the whole point of the reservation, since nothing else can move the tree under the re-run. After each failed re-run, ask: "keep the reservation and keep fixing" / "release and stop here" (the latter takes the in-flight exit below) |
| `fail` pre-existing / unrelated | existing `./ait gate fail … --reason` record + plan note, then `cleanup --task-complete` → `finish` |
| `error` (verifier infrastructure), `blocked:`, `pending` (human sign-off) | these are not minutes-scale. Surface, **skip cleanup entirely**, `finish` to release, and end the workflow with the task in-flight. `finish` here is a *release*, not a success claim — the skill must say plainly that the merge landed and archival is pending |
| `gates_rc` nonzero (infrastructure) | same as above: surface, skip cleanup, `finish`, stop. Never archive |

**Cleanup is a completion step, never an in-flight one.** `cleanup` deletes
`aitask/<task_name>` and its worktree, so running it on a path that leaves the
task in-flight would destroy the very branch the resume needs — the promised
idempotent re-reservation would find no branch to merge, and the shared
workflow's own `POSTIMPL` route (which states that re-cutting the branch "would
fail outright — `aitask/<task_name>` already exists") would be reasoning about a
branch that is gone. So **every in-flight exit above retains the branch and the
worktree** and calls `finish` alone.

The broker enforces the rule rather than trusting the caller to remember it:
`cleanup` requires an explicit `--task-complete` and otherwise refuses with
`CLEANUP_REQUIRES_COMPLETION`, changing nothing. That assertion is still
caller-supplied — the second line of defence is t1560_2's rendered-verdict test,
which fails the build if a rendered branch reaches `cleanup` on a row this table
marks in-flight.

**Releasing early is then recoverable, because `begin` is idempotent.** A
`POSTIMPL` re-entry re-runs `begin` against the retained `aitask/<task_name>`;
`git merge` of an already-merged branch reports "Already up to date" and exits 0,
so the broker returns `MERGE_OK:<head_sha>` with no new commit and the tree is
**re-reserved** for the retried verification. That is what keeps the verdict
attributable across the release/resume boundary, and it is why "release and come
back" is a safe branch rather than a loophole.

### 5. Step 9 wiring — and one thing the task expected that is not needed

The prompt-drift surface is cheaper than `t1560`'s Scope §4 assumed:
`workflow_phase.py:103` matches on the **prefix** `Proceed with merge of code
changes into`, and `tests/test_workflow_phase_prompt_drift.sh:60,104` grep/
match that same prefix. Appending a "queued behind t\<N\>" clause to the **end**
of the question therefore requires **no change** to either file — the child must
*prove* that with an added assertion, not assume it, and must not reword the
prefix. The non-skippable banner stays intact: the mutex serializes the merge, it
does not become a reason to auto-approve it.

## Children

Three children; `t1560_2` and `t1560_3` depend on `t1560_1`.

### t1560_1 — merge mutex + broker script (all five behavioural ACs)

`lib/stale_lock.sh` seams · `lib/merge_lock.sh` · `aitask_merge_task.sh` ·
5 whitelist touchpoints · the whole concurrency test suite. **Provable end-to-end
without touching a single skill file**, which is why it goes first.

Tests (`aidocs/framework/testing_conventions.md:10,18` mandates the enumeration;
`tests/test_gate_lock_single_winner.sh` is the shape to copy).

**Fixture rule for every recovery assertion:** a task branch's mergeability is a
property of the fixture, so "the lock works again" is always proved by a task
whose branch merges **cleanly** into `<output_branch>` — never by re-running the
branch whose merge produced the residue being recovered from. The fixture
therefore keeps three shapes on hand: cleanly-mergeable, conflicting, and
unrelated-history.

| # | Case | Assertion |
|---|---|---|
| 1 | Red proof, mutex disabled | A parks between checkout and merge (FIFO hook); B merges; A resumes → A's merge commit's tree **contains B's file**. Same test with the mutex enabled: B reports `BUSY:tA`, A's commit is clean. |
| 1n | Negative control for 1 | The mutation must reach the *merge-contamination* assertion, not trip an earlier one — assert the named failing case, not "goes red somewhere". |
| 2 | N = 51 concurrent callers | **Lifecycle is explicit**: each caller runs `begin … --wait-secs <budget>` and, on `BUSY`, **retries to completion** up to a bounded attempt cap, then `finish`es so the next can proceed. Assert exactly 51 `MERGE_OK`, 51 merge commits on `<output_branch>`, one per logical caller; **zero** nonzero exits and zero git-level errors; and — so the case is not vacuous — **at least one** `BUSY`/`WAITING` was observed naming a real holder task id. A caller that exhausts its cap is a failure, not a permitted outcome. |
| 3 | Conflict-parked reservation | A stops at `MERGE_CONFLICT`; B does **not** enter and its report names A's task id; after A's `abort`, B proceeds. |
| 4 | Stale-holder recovery | anchor = a `AIT_AGENT_PID` fixture process; killed mid-section → exactly **one** waiter reclaims. Live-anchored holder → **never** displaced (and `unknown` anchor → never displaced). |
| 5 | Guard gates | removing the acquire (via the documented seam) makes case 1 and case 3 fail. |
| 6 | Callers unchanged | `test_stale_lock.sh`, `test_gate_lock_single_winner.sh`, `test_registry_lock_single_winner.sh`, `test_parallel_child_create.sh`, `test_task_lock.sh` all still pass. |
| 7 | Wedge recovery terminates | unresolvable anchor → lock never auto-reclaimed; `status` names it; `force-release --yes` clears it. Plus: `force-release` on a **live** holder is refused (`REFUSED_LIVE_HOLDER`, lock intact); with `MERGE_HEAD` present and no flag it is refused (`RESIDUE_PRESENT`, lock intact); with `--abort-merge` the tree is verified clean **and** the lock released. **Both residue states are driven separately**: for unmerged-index-without-`MERGE_HEAD` (planted by conflicting a merge then removing `.git/MERGE_HEAD`), `--abort-merge` must return `WRONG_REMEDY:no_merge_head` with the lock **kept**, and `--reset-hard --yes` must reach a verified-clean tree and release. On **every** rung the "lock is usable again" assertion is a `begin` from a **different, cleanly mergeable task**, never a re-run of the branch whose merge produced the residue — that one would just reproduce `MERGE_CONFLICT` and assert nothing about the recovery. The ladder must terminate on both rungs, not just the easy one. |
| 8 | Non-owner release refused | (a) task B's `finish`/`abort`/`cleanup` against task A's held lock → `NOT_HOLDER:tA`, A's lock intact and A can still `finish`. (b) **same task id, different caller that cannot prove its anchor** → `NOT_OWNER_SESSION`, lock intact — the hole a task-id-only check would leave. (c) same task id, provably different live session → `NOT_OWNER_SESSION`. (d) planted lock dir with no `task_id` → `status` reports `HOLDER_INCOMPLETE`, `force-release --yes` clears it. (e) `begin` with no resolvable anchor → `NO_SESSION_ANCHOR`, nothing locked. |
| 10 | Cleanup authorization + partial failure | `cleanup` without `--task-complete` → `CLEANUP_REQUIRES_COMPLETION`, **branch and worktree intact**, and a following `begin` on that branch still reaches `MERGE_OK` (the in-flight resume path survives). `cleanup` from a non-owner → refused, worktree intact. `<task_name>` disagreeing with the recorded `task_branch` → `TARGET_MISMATCH`, nothing removed. A **moved** worktree is still found (path derived from the porcelain record, not the argument). An undeletable worktree / unmerged branch → `CLEANED_PARTIAL:<remains>` with the reservation **still held**, never `CLEANED`. |
| 8b | Non-conflict merge failure | driven **separately** from case 3: task **U** owns a branch with a history unrelated to `<output_branch>`, so `git merge` fails *before* `MERGE_HEAD` exists → `MERGE_FAILED`, then `abort` → `RELEASED_NO_MERGE` (**not** `ABORT_FAILED`). The lock-is-usable-again proof must then come from a **different, cleanly mergeable task V** (the ordinary shared-history fixture of cases 1–3) reaching `MERGE_OK` — re-running U's own `begin` would fail identically forever and prove nothing. Plus the planted no-`MERGE_HEAD`-but-unmerged-index state → `ABORT_UNSAFE`, lock **kept**. |
| 8c | Verification window does not strand the lock | a scripted caller mimicking Step 9 — `begin` → run an **injected failing verification command** → take the "release and stop" branch → `finish` **without** cleanup — leaves the lock free, the merge commit intact, and `aitask/<task_name>` plus its worktree still present. Then re-run `begin` on that retained branch: `MERGE_OK` with **no new commit** (idempotent re-reservation), proving the release/resume boundary is recoverable. |
| 9 | Publish is atomic with acquire | with `STALE_LOCK_PUBLISH_FN` returning nonzero, `stale_lock_acquire` unwinds and leaves **no** lock dir behind (fail closed), and the contender's next attempt succeeds. |

### t1560_2 — Step 9 wiring across every rendered surface (AC 6)

Jinja source `.claude/skills/task-workflow/SKILL.md`: replace the inline merge
block with a `status` probe before the approval prompt (to name the holder) and
`begin` / `finish` / `abort` around it, rendering **every row of the §4 verdict
table and the §4a verification-outcome table** — including the held-lock
invariant sentence verbatim, since that is what stops an agent proceeding to
gates after a refused `begin`, and the §4a rows are what stop a long
`error`/`blocked`/`pending` verification stranding the reservation. Replace the unguarded
cleanup (`SKILL.md:836-841`) with the broker's guarded `cleanup` verb and its
`CLEANED_PARTIAL` branch. Add a test that asserts every verdict string the broker
can emit — `begin`, `abort`, `cleanup` and `finish` alike — appears in the
rendered `SKILL-{default,fast,remote}.md`: a verdict with no branch must fail the
build, not ship. That test must also assert the rendered `ABORT_UNSAFE` branch
**echoes the broker-supplied `<remedy_flag>`** and contains no hardcoded
`--abort-merge` / `--reset-hard` literal — a rendered command that names the
wrong remedy for the observed state sends the user to a refusal. Then
`aitask_skill_rerender.sh` **once per profile** (default / fast / remote), the
`.agents/` Codex and `.opencode/` ports, and regenerate
`tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` in the same
commit. Add the assertion that the new question still matches
`workflow_phase.WORKFLOW_PROMPTS`. `ait skill verify` before committing.

Notes for the implementer:
- This repo has no `fast_worktree` profile — only `default` / `fast` / `remote`
  exist under `aitasks/metadata/profiles/`.
- **Verify, do not assume**, that Re-entry Routing's `POSTIMPL` text still holds
  after the change: it asserts `aitask/<task_name>` already exists at re-entry,
  which is exactly what §4a's "no cleanup on an in-flight exit" rule preserves.
  If any rendered branch is found to clean up before archival, that is the bug.

### t1560_3 — docs + the other merge paths

`website/content/docs/concepts/locks.md` (its "what the lock actually excludes"
table is currently accurate *only because* merging is unprotected — it must gain
the merge mutex, its session-anchor lifetime, the **anchor precondition** on
merging, and the `force-release` recovery ladder)
and `website/content/docs/workflows/parallel-development.md:20` (describes the
merge-back with no serialization caveat at all). Audit `aitask-pickrem`,
`aitask-pickweb` and `aitask-web-merge` — the last is the only merge path in the
tree that uses `--no-ff` and pushes the target, and it mutates the same shared
root, so it either takes the same mutex or the doc states why not.

## Non-goals (carried from the task — do not absorb)

- **No fetch added to Step 9** — that is **t1393**. Record in t1560_2's Final
  Implementation Notes that its wiring point is now the broker script.
- **No edit-time file-overlap advice** — t1343 / t1344.
- **No change to push behaviour.** Step 9 never pushes the output branch; that is
  recorded as a finding, not fixed here.
- **Shared-checkout mode needs no mutex.** Under `create_worktree: false` (this
  repo's own `fast.yaml:5`) there is no task branch and Step 9's merge block does
  not run at all — the broker must not be invoked there, or it adds pure latency.
  A consequence worth stating: day-to-day use of this repo will not exercise the
  feature, so the test suite is the only regression net.

### Post-phase (risk mitigations)

- **wedge_recovery_probe** — carried into `t1560_1`'s plan as its final step (it
  is test 7 in the table above, promoted to a named phase). Drives the
  unresolvable-anchor path to a wedged merge lock and asserts `status` names the
  holder with its liveness verdict and `force-release` clears it — proving the
  recovery ladder **terminates** rather than documenting a hazard.

## Risk

### Code-health risk: medium
- `lib/stale_lock.sh` is a hardened primitive with three production callers (gate-ledger appends, child-task numbering, the project/attach registry lock); adding three seams — one of which runs *inside* the `.gc` guard — risks changing behaviour on paths that are currently correct · severity: medium · → mitigation: inline pre-phase characterize_stale_lock_callers
- An unresolvable session anchor makes the merge lock **never** auto-reclaimable by design, so a leaked lock wedges every future merge in the repo until a human intervenes · severity: medium · → mitigation: inline post-phase wedge_recovery_probe
- The broker centralizes checkout + merge + verification + cleanup, so a bug in it breaks every task's Step 9 at once, where today the failure is per-agent and inline · severity: medium · → mitigation: TBD (covered by the t1560_1 test suite; no separate mitigation)
- Requiring a resolvable session anchor to `begin` is a **new hard precondition** on worktree-mode merges: an agent outside tmux with no `AIT_AGENT_PID` can no longer merge at all until one is supplied · severity: medium · → mitigation: TBD (accepted deliberately — the alternative is a reservation whose owner cannot be proven; `NO_SESSION_ANCHOR` names both remedies inline, and t1560_3 documents the precondition in `locks.md`)

### Goal-achievement risk: medium
- AC 1's red proof depends on a two-caller FIFO rendezvous; if the hook point is wrong the "proof" trips an earlier assertion instead of the raced merge and proves nothing · severity: medium · → mitigation: TBD (test 1n pins the boundary by naming the failing case)
- The feature is inert under this repo's own `fast` profile (`create_worktree: false`), so day-to-day use never exercises it and regressions surface only in the suite · severity: low · → mitigation: TBD (stated as a non-goal consequence; docs in t1560_3 say so explicitly)

### Planned mitigations
- timing: pre-phase | name: characterize_stale_lock_callers | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: stale_lock.sh seams change existing caller behaviour | desc: Baseline the five existing lock test files before editing lib/stale_lock.sh and diff the runs after the seams land, in t1560_1.
- timing: post-phase | name: wedge_recovery_probe | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: unresolvable anchor makes the merge lock never auto-reclaimable | desc: Prove the wedged-lock recovery ladder terminates — status names the holder, force-release clears it — in t1560_1.

## Verification (this parent)

```bash
./.aitask-scripts/aitask_ls.sh -v --children 1560 99   # 3 children + plans
ls aiplans/p1560/
```

Each child carries its own verification; the parent is done when the three child
tasks and their plans exist and `t1560_2` / `t1560_3` declare `depends: [1560_1]`.

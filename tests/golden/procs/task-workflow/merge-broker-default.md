# Merge Broker Procedure

Owns Step 9's merge critical section. The merge runs in the **shared repo root**,
so every concurrently-merging task drives one HEAD, one index and one working
tree. `./.aitask-scripts/aitask_merge_task.sh` is the only sanctioned way to
perform it: one process holds the merge mutex across checkout + merge and
**retains** the reservation through conflict resolution, verification and
cleanup, releasing only on an explicit `finish` / `abort`.

Invoked from `SKILL.md` **Step 9**, which keeps the merge-approval banner, the
approval question and the verification block. Control crosses between the two
files four times; the named section headings below are the handoff anchors, and
`## Carried state` is what must remain true at every crossing.

## Carried state

Four values must be valid at **every** hop, in both directions:

| name | meaning |
|---|---|
| `task_id` | the task being merged (`16` or `16_2`) |
| `task_name` | the filename stem — the task branch is `aitask/<task_name>` |
| `$output_branch` | the merge target, **bound and validated** by Step 9 from the plan header; never substituted as a literal |
| `lock` | `none` · `ours-held` · `not-ours` |

**A hop that cannot state the current `lock` value must stop and say so rather
than guess.** Reporting a released lock that is in fact held is the failure this
whole procedure exists to prevent: the next task then merges into a tree someone
else is still using.

## Preconditions

- **Worktree mode only.** Invoke this procedure solely under Step 9's
  `**If a separate branch was created:**` gate. The broker has **no**
  no-task-branch guard of its own: `begin` with `task_branch` equal to
  `output_branch` merges as "Already up to date" and returns `MERGE_OK`
  **with the reservation held**, so invoking it in current-branch mode acquires
  a lock that nothing in the workflow will ever release.
- `$output_branch` is already bound and validated by Step 9. Pass the **quoted
  variable** to every broker call; never paste the branch name.
- The broker requires a resolvable **session anchor**. Without one it refuses
  before acquiring anything (`NO_SESSION_ANCHOR`).

## Invariant

> Every path on which the broker reported the lock **held** ends in exactly one
> `finish` or `abort`. Every path on which it is **not** held calls neither, and
> never proceeds to verification, cleanup or archival.

The disposition tables below are the executable form of that sentence: the
`lock`, `terminal-release` and `terminal-lock` columns say, per verdict, whether
the reservation is ours and what discharges it.

## Output contract

**Exit status is disjoint from the verdict** (the same contract `ait gates run`
uses):

- `0` — a verdict was produced, **including** `BUSY` and `MERGE_CONFLICT`.
- `1` — infrastructure failure only. **Nothing on stdout.**
- `2` — usage error.

Exactly one verdict line on **stdout**; `WAITING:<holder>:<elapsed>` progress
goes to **stderr**, so stdout parses as data. A **nonzero exit is not a verdict**
— stop and diagnose; never fall through to any branch below.

### Reading the disposition tables

Every verdict the broker can emit has exactly one row, qualified by verb. The
columns are closed vocabularies:

| column | values |
|---|---|
| `lock` (at verdict time) | `ours-held` · `not-ours` · `none` |
| `terminal-release` | `finish` · `abort` · `ladder` · `none` |
| `lock-through` | `n/a` · `immediate` · `verification` · `verification+cleanup` |
| `continues-to` | `approval` · `verification` · `archival` · `caller-path` · `stop-in-flight` · `stop` · `recovery` |
| `terminal-lock` | `released` · `held-ladder` · `n/a` |

`terminal-release` is the verb that **terminates** the path — not one to call on
receipt of the verdict. `lock-through` is what says *when*: it names the stages
the reservation must span **before** that release. `ladder` means the reservation
is held and this branch makes **no further broker release call**; it hands the
user the `## Recovery ladder`. `caller-path` means resume whatever path called
the verb.

**Alternation.** A cell may carry `;`-separated alternatives. All alternating
cells in a row have the same arity, and alternative *i* of each column pairs
positionally with alternative *i* of the others.

## Probe — report the queue holder

Read-only; acquires nothing. Run it **before** Step 9's approval question so the
question can name the task it is queued behind.

```bash
./.aitask-scripts/aitask_merge_task.sh status
```

### `status` verdicts

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `FREE` | none | none | n/a | approval | n/a |
| `FREE_GUARD_PRESENT:<dir>.gc` | none | none | n/a | approval | n/a |
| `HELD:<t>\|<pid>\|<live>\|<branch>\|<at>` | not-ours | none | n/a | approval | n/a |
| `HOLDER_INCOMPLETE:<pid>\|<live>` | not-ours | none | n/a | approval | n/a |

#### status / FREE

Nothing is queued. `terminal-release` is `none`; `continues-to` is `approval` —
return to Step 9 and ask the approval question with no queued clause.

#### status / FREE_GUARD_PRESENT

The mutex is free but a `.gc` guard leaked at the named path, which will block
the next acquisition. `terminal-release` is `none`; `continues-to` is `approval`.
Tell the user the guard path and the cure (`rmdir '<dir>.gc'/h.* '<dir>.gc'` —
**never** `rm -rf`) before asking, so a subsequent `LOCK_UNAVAILABLE` is not a
surprise. Note the merge lock is the one lock dir that deliberately does **not**
auto-reclaim a recordless guard: this file runs `git merge --abort` and
`git reset --hard` under that guard, so no age window can dominate a legitimate
hold (t1598).

#### status / HELD

Another task holds the merge mutex. Parse the pipe-separated fields; the first is
the holder's task id. `terminal-release` is `none`; `continues-to` is `approval`
— return to Step 9 and append `Queued behind t<N>.` to the **end** of the
approval question, naming that holder. Do not skip or auto-answer the question.

#### status / HOLDER_INCOMPLETE

A lock exists but records no task id, so no holder can be named.
`terminal-release` is `none`; `continues-to` is `approval` — say plainly that the
mutex is held by an unidentifiable holder and point at the `## Recovery ladder`,
then ask the approval question without a queued clause.

## Entry — acquire the reservation and merge

Entered from Step 9 **after** the approval question was answered "Yes".
In: `lock: none`.

```bash
./.aitask-scripts/aitask_merge_task.sh begin "<task_id>" "$output_branch" "aitask/<task_name>" --wait-secs 120
```

`--wait-secs 120` lets a short queue drain without a prompt; the broker prints
`WAITING:<holder>:<elapsed>` to stderr meanwhile.

### `begin` verdicts

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `MERGE_OK:<sha>` | ours-held | finish | verification+cleanup | verification | released |
| `MERGE_CONFLICT:<paths>` | ours-held | finish;abort | verification+cleanup;immediate | verification;stop-in-flight | released;released |
| `MERGE_FAILED:<msg>` | ours-held | abort | immediate | stop-in-flight | released |
| `RETAINED:<inner>` | ours-held | finish | immediate | stop-in-flight | released |
| `BUSY:<holder>:<waited>` | none | none | n/a | stop-in-flight | n/a |
| `STALE_MERGE_RESIDUE` | none | none | n/a | stop | n/a |
| `DIRTY_TREE:<n>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_MISSING:<b>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_FOREIGN_WORKTREE:<p>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_CHECKOUT_FAILED:<msg>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_HEAD_MISMATCH:<b>:<head>` | none | none | n/a | stop | n/a |
| `UNSAFE_OUTPUT_BRANCH:<b>` | none | none | n/a | stop | n/a |
| `NO_SESSION_ANCHOR` | none | none | n/a | stop | n/a |
| `LOCK_UNAVAILABLE` | none | none | n/a | stop | n/a |

#### begin / MERGE_OK

The merge landed at the reported sha and the reservation is **ours-held**.
`terminal-release` is `finish`, but **not now**: `lock-through` is
`verification+cleanup`, so the reservation spans Step 9's gates run *and*
cleanup. Releasing here would hand the shared tree to another task while
`ait gates run` is reading it, which is precisely the contamination this mutex
prevents. `continues-to` is `verification` — go to
`## Return to Step 9 — Verify implementation`.

#### begin / MERGE_CONFLICT

The merge is parked on conflicts in the reported paths and the reservation is
**ours-held** — that retention is the fix: the tree stays reserved while a human
resolves. Show the paths and ask "Resolve conflicts now" / "Abort the merge".

- **Resolve** → the user resolves and commits, then `terminal-release` `finish`
  with `lock-through` `verification+cleanup`; `continues-to` `verification`.
- **Abort** → `terminal-release` `abort` with `lock-through` `immediate`;
  `continues-to` `stop-in-flight`. Go to `## Exit — cleanup and release` and run
  `abort`, then end the workflow with the task in-flight and its branch retained.

#### begin / MERGE_FAILED

The merge failed **after** the reservation was taken, so it is **ours-held**.
Surface the message. `terminal-release` is `abort`, `lock-through` `immediate` —
go to `## Exit — cleanup and release`, run `abort`, and branch on **its**
verdict. `continues-to` is `stop-in-flight`: no verification, no cleanup, no
archival, whatever `abort` reports.

#### begin / RETAINED

**The reservation is still held**, even though the wrapped inner verdict reads
like a release. The broker could not release after a pre-merge refusal — a leaked
`.gc` guard makes this reachable — and reports `RETAINED:<inner>` precisely so
the caller does not conclude the lock is free.

Attempt **exactly one** `finish` (`terminal-release` `finish`, `lock-through`
`immediate`, `continues-to` `stop-in-flight`, `terminal-lock` `released`), then
**branch on that call's own verdict via the `finish` table** — do not assume the
outcome. `finish` can report four things that are *not* "still held", and
treating them as such would state a falsehood and start the wrong recovery:

- `RELEASED` → released; end in-flight as normal.
- `RETAINED:release_failed` → **this** is the still-held case; it routes to
  `## Recovery ladder` via its own row.
- `NOT_HELD` → the reservation is **gone**, not held. Surface as a defect.
- `NOT_HOLDER` / `NOT_OWNER_SESSION` / `HOLDER_INCOMPLETE` → the lock is **not
  ours**. Surface as a defect; never force another session's reservation.

Never report a released lock as held, or a held lock as released.

#### begin / BUSY

Another task holds the mutex; nothing was acquired, so `terminal-release` is
`none`. Name the holder and the seconds waited, then ask "Wait and retry" /
"Stop here".

- **Wait and retry** → re-run `begin` with `--wait-secs 300`. Bounded: after
  **3** declines, stop.
- **Stop here** → `continues-to` `stop-in-flight`: end the workflow, task and
  branch retained, re-enterable at `POSTIMPL`.

#### begin / STALE_MERGE_RESIDUE

A `MERGE_HEAD` from an earlier, abandoned merge is present. The lock was
released, so `terminal-release` is `none` and `continues-to` is `stop`. Surface
the residue and the `force-release --abort-merge --yes` remedy from
`## Recovery ladder`; do not merge.

#### begin / DIRTY_TREE

The shared tree has the reported number of modified tracked files. The lock was
released: `terminal-release` `none`, `continues-to` `stop`. List the files and
ask the user to commit or stash them. **No automatic retry.**

#### begin / PREFLIGHT_MISSING

`$output_branch` does not exist as a local branch. The lock was released:
`terminal-release` `none`, `continues-to` `stop`. Stop and ask the user — fetch
it, create it, pick a different target, or abort. Never let `git checkout` DWIM a
tracking branch into existence unnoticed. The broker fully qualifies the ref
(`refs/heads/`) for a reason: a bare name resolves tags **above** heads, so a tag
named `dev` would pass a bare check and the checkout would land in detached HEAD,
committing the merge onto no branch at all.

#### begin / PREFLIGHT_FOREIGN_WORKTREE

Another worktree, at the reported path, holds `$output_branch`, so checkout would
refuse. The lock was released: `terminal-release` `none`, `continues-to` `stop`.
Surface the path and ask. The broker rejects **only** when that path differs from
the repo root — the root is itself listed among the worktrees, and the case where
the root already holds the output branch is a safe no-op, not a conflict.

#### begin / PREFLIGHT_CHECKOUT_FAILED

`git checkout` of `$output_branch` failed; the reported message is git's own,
truncated. **The lock was released** — this verdict exists precisely so it is not
confused with `MERGE_FAILED`, which retains. `terminal-release` is `none`:
calling `abort` here would run held-lock recovery against a free lock.
`continues-to` is `stop`.

#### begin / PREFLIGHT_HEAD_MISMATCH

After checkout, HEAD is not on `$output_branch` (the reported value is the actual
head, or `DETACHED`). Merging would commit onto no branch. **The lock was
released**, exactly as for `PREFLIGHT_CHECKOUT_FAILED`: `terminal-release`
`none`, `continues-to` `stop`.

#### begin / UNSAFE_OUTPUT_BRANCH

The reported branch name — the output branch or the task branch — is not
shell-safe or is not a valid ref. Nothing was acquired: `terminal-release`
`none`, `continues-to` `stop`. Report the offending value and do not merge; a
plan header recording such a name is untrustworthy about where work lands.

#### begin / NO_SESSION_ANCHOR

The broker could not resolve a session anchor, so it refused **before**
acquiring: a reservation whose owner cannot be proven could never be released
safely. `terminal-release` `none`, `continues-to` `stop`. Name both remedies —
set `AIT_AGENT_PID` to a live process, or run inside a tmux pane — then re-run.

#### begin / LOCK_UNAVAILABLE

The lock infrastructure itself is unavailable. Nothing was acquired:
`terminal-release` `none`, `continues-to` `stop`. Surface the reason and stop.
(The shipped broker emits this only from `force-release`; the branch exists
because `begin` declares it in its vocabulary.)

## Return to Step 9 — Verify implementation

Out: `lock: ours-held`, and it **stays** `ours-held` for the whole of Step 9's
verification block. Return to `SKILL.md` Step 9 and run
**Verify implementation (build / tests / lint)** now. The reservation spanning
that block is what makes the verdict attributable: nothing else can check out,
merge into, or mutate the tree the build is reading.

When it finishes, come back to `## Re-entry — release decision` with the outcome.

## Re-entry — release decision

In: `lock: ours-held`, plus the outcome of Step 9's verification block.

`abort` is valid on **no** row here — the merge commit already exists, and
`git merge --abort` cannot undo a completed merge. `finish` on an in-flight row
is a **release, not a success claim**; say so plainly, and say that the merge
landed and archival is pending.

**Cleanup is a completion step, never an in-flight one.** `cleanup` deletes
`aitask/<task_name>` and its worktree, so running it on a path that leaves the
task in-flight would destroy the very branch the `POSTIMPL` resume must re-merge.
Every in-flight row below therefore calls `finish` **alone** and retains the
branch and worktree.

### Verification outcomes

| outcome | cleanup | terminal-release | lock-through | continues-to |
|---|---|---|---|---|
| all `pass`/`skip`, or no declared gates and `verify_build` passed | `--task-complete` | finish | verification+cleanup | archival |
| `fail` caused by this task | no | none | verification | re-run |
| `fail` pre-existing / unrelated | `--task-complete` | finish | verification+cleanup | archival |
| `error` / `blocked:` / `pending` | no | finish | verification | stop-in-flight |
| `gates_rc` nonzero | no | finish | verification | stop-in-flight |

- **all `pass`/`skip`** — the normal path. Go to `## Exit — cleanup and release`,
  run `cleanup`, then `finish`, then archive.
- **`fail` caused by this task** — fix and re-run `./ait gates run <task_id>`
  **while holding**; that is what the reservation is for, since nothing else can
  move the tree under the re-run. After each failed re-run ask "Keep the
  reservation and keep fixing" / "Release and stop here". The latter takes the
  in-flight exit: `finish` alone, no cleanup.
- **`fail` pre-existing / unrelated** — record
  `./ait gate fail <task_id> <gate> --reason "…"`, note it in the plan's Final
  Implementation Notes, then `cleanup --task-complete` → `finish` → archive.
- **`error` / `blocked:` / `pending`** — not minutes-scale. Surface, **skip
  cleanup entirely**, `finish` to release, and end with the task in-flight.
- **`gates_rc` nonzero** — infrastructure. Same as above: surface, skip cleanup,
  `finish`, stop. **Never archive.**

Releasing early is recoverable, because `begin` is idempotent: a `POSTIMPL`
re-entry re-runs it against the retained `aitask/<task_name>`, git reports
"Already up to date", and the broker returns `MERGE_OK` with no new commit — the
tree is re-reserved for the retried verification.

## Exit — cleanup and release

Terminal state is `lock: none` on the archival path **and on every ordinary
in-flight exit** (released; task and branch retained).

**Rows whose `continues-to` is `recovery` are exempt.** Their terminal state is
`held-ladder`: the reservation is still held, the agent must say so in plain
words, must **not** report a released lock, and must **not** take ordinary
in-flight routing. They leave via `## Recovery ladder`.

```bash
./.aitask-scripts/aitask_merge_task.sh cleanup "<task_id>" "<task_name>" --task-complete
./.aitask-scripts/aitask_merge_task.sh finish "<task_id>"
./.aitask-scripts/aitask_merge_task.sh abort "<task_id>"
```

`cleanup` **never releases** the mutex — `finish` does. `--task-complete` is
required: without it the broker refuses and changes nothing, which is what stops
an in-flight path from deleting the branch its resume needs.

### `cleanup` verdicts

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `CLEANED` | ours-held | finish | immediate | archival | released |
| `CLEANED_PARTIAL:<remains>` | ours-held | finish | immediate | stop-in-flight | released |
| `CLEANUP_REQUIRES_COMPLETION` | ours-held | finish | immediate | stop-in-flight | released |
| `TARGET_MISMATCH:<recorded>` | ours-held | finish | immediate | stop-in-flight | released |
| `NOT_HELD` | none | none | n/a | stop-in-flight | n/a |
| `NOT_HOLDER:<t>` | not-ours | none | n/a | stop-in-flight | n/a |
| `NOT_OWNER_SESSION:<t>:<pid>` | not-ours | none | n/a | stop-in-flight | n/a |
| `HOLDER_INCOMPLETE` | not-ours | none | n/a | stop-in-flight | n/a |

**A deliberate narrowing of "any refusal verdict → still `finish`".** That rule
holds where the broker reports **our** lock still held
(`CLEANUP_REQUIRES_COMPLETION`, `TARGET_MISMATCH`). Where it reports the lock
absent (`NOT_HELD`) or foreign (`NOT_HOLDER` / `NOT_OWNER_SESSION` /
`HOLDER_INCOMPLETE`), `terminal-release` is `none`: a second call cannot change
the outcome, and releasing another task's reservation is never correct.

#### cleanup / CLEANED

The worktree and `aitask/<task_name>` are gone. `terminal-release` `finish`,
`continues-to` `archival` — run `finish`, then return to Step 9 for archival.

#### cleanup / CLEANED_PARTIAL

Teardown was incomplete and the reservation is **kept**. Surface exactly what
remains (the reported `WORKTREE_KEPT=<reason>` / `BRANCH_KEPT=<reason>` pairs, or
`cleanup_did_not_run` when the delegate never produced a well-formed result) and
offer "Retry cleanup" / "Release and stop in-flight".

- **Retry cleanup** → run `cleanup` again and branch on the **new** verdict.
  Only a fresh `CLEANED` reaches archival.
- **Release and stop in-flight** → `terminal-release` `finish`, `continues-to`
  `stop-in-flight`.

**Never archive over residue.** A surviving worktree or `aitask/<task_name>` is
exactly the state the `POSTIMPL` resume needs in order to finish the job;
archiving the task would close the only route back to it, and would contradict
the teardown contract this delegates to, where **only** `CLEAN` is a success.
Whichever option is taken, the reservation is released, so the ladder terminates
— but a partial cleanup is never reported as success and never completes the
task.

#### cleanup / CLEANUP_REQUIRES_COMPLETION

`--task-complete` was not passed, so nothing was touched. This is a **defect in
the call site** — this procedure always passes it. Surface it as such. The lock
is still ours: `terminal-release` `finish`, `continues-to` `stop-in-flight`. Do
not archive over an unclean teardown.

#### cleanup / TARGET_MISMATCH

The reservation records a different task branch than `aitask/<task_name>`, so the
broker refused rather than tear down the wrong task's work. Surface the recorded
branch as a defect; do **not** retry with another name. The lock is still ours:
`terminal-release` `finish`, `continues-to` `stop-in-flight`.

#### cleanup / NOT_HELD

The reservation is gone — it should not be, on a path that reached cleanup.
Surface it as a defect. `terminal-release` is `none` (a `finish` would report the
same thing and change nothing); `continues-to` `stop-in-flight`.

#### cleanup / NOT_HOLDER

The mutex is held by the reported **other** task. Surface as a defect;
`terminal-release` `none` — never release another task's reservation.
`continues-to` `stop-in-flight`.

#### cleanup / NOT_OWNER_SESSION

The mutex records this task id but a different session, so this process cannot
prove ownership. Surface with the reported holder and pid; `terminal-release`
`none`, `continues-to` `stop-in-flight`. `## Recovery ladder` covers a genuinely
dead session.

#### cleanup / HOLDER_INCOMPLETE

The lock records no task id, so ownership can never be matched. Surface;
`terminal-release` `none`, `continues-to` `stop-in-flight`, and point at
`## Recovery ladder`.

### `finish` verdicts

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `RELEASED` | none | none | n/a | caller-path | n/a |
| `NOT_HELD` | none | none | n/a | caller-path | n/a |
| `NOT_HOLDER:<t>` | not-ours | none | n/a | caller-path | n/a |
| `NOT_OWNER_SESSION:<t>:<pid>` | not-ours | none | n/a | caller-path | n/a |
| `HOLDER_INCOMPLETE` | not-ours | none | n/a | caller-path | n/a |
| `RETAINED:release_failed` | ours-held | ladder | immediate | recovery | held-ladder |

#### finish / RELEASED

The reservation is released. `terminal-release` `none` — it has just been
discharged. `continues-to` `caller-path`: resume whatever brought you here
(archival on the completion path, or the in-flight stop).

#### finish / NOT_HELD

There was no reservation to release. Surface as a defect — this path believed it
held one. `terminal-release` `none`, `continues-to` `caller-path`.

#### finish / NOT_HOLDER

The mutex is held by the reported other task, so nothing was released. Surface as
a defect; `terminal-release` `none` — never force another task's lock from here.
`continues-to` `caller-path`.

#### finish / NOT_OWNER_SESSION

The mutex records this task id but a different session (reported holder and pid),
so release was refused. `terminal-release` `none`, `continues-to` `caller-path`.
Point at `## Recovery ladder` if that session is genuinely gone.

#### finish / HOLDER_INCOMPLETE

The lock records no task id and can never be matched. `terminal-release` `none`,
`continues-to` `caller-path`; point at `## Recovery ladder`.

#### finish / RETAINED

The release was attempted and **failed** — the reservation is still held. Do
**not** call `finish` again: `terminal-release` is `ladder`, `continues-to` is
`recovery`, `terminal-lock` is `held-ladder`. Say plainly that the merge mutex is
still held, and go to `## Recovery ladder`.

### `abort` verdicts

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `ABORTED` | none | none | n/a | stop-in-flight | n/a |
| `RELEASED_NO_MERGE` | none | none | n/a | stop-in-flight | n/a |
| `ABORT_FAILED:<msg>` | ours-held | ladder | immediate | recovery | held-ladder |
| `ABORT_UNSAFE:<state>:<remedy_flag>` | ours-held | ladder | immediate | recovery | held-ladder |
| `NOT_HELD` | none | none | n/a | stop-in-flight | n/a |
| `NOT_HOLDER:<t>` | not-ours | none | n/a | stop-in-flight | n/a |
| `NOT_OWNER_SESSION:<t>:<pid>` | not-ours | none | n/a | stop-in-flight | n/a |
| `HOLDER_INCOMPLETE` | not-ours | none | n/a | stop-in-flight | n/a |
| `RETAINED:<inner>` | ours-held | ladder | immediate | recovery | held-ladder |

#### abort / ABORTED

The merge was aborted, the tree verified clean, and the reservation released.
`terminal-release` `none`, `continues-to` `stop-in-flight`: end the workflow with
the task in-flight and `aitask/<task_name>` retained.

#### abort / RELEASED_NO_MERGE

There was nothing to abort — the merge failed before touching anything — and the
reservation was released. This is the normal outcome after `MERGE_FAILED`.
`terminal-release` `none`, `continues-to` `stop-in-flight`.

#### abort / ABORT_FAILED

`git merge --abort` ran but the tree did not reach a clean state, so **the
reservation was deliberately kept** rather than handing a broken tree to the next
caller. `terminal-release` is `ladder`, `continues-to` `recovery`,
`terminal-lock` `held-ladder`. Surface the message and go to
`## Recovery ladder`.

#### abort / ABORT_UNSAFE

The tree is in a state this session did not create (the reported `<state>`), so
the broker refused to discard it and **kept the reservation**.
`terminal-release` is `ladder`, `continues-to` `recovery`, `terminal-lock`
`held-ladder`.

**Echo the remedy flag the broker named.** The verdict's second field is the
flag to pass to `force-release`; render it from the parsed verdict, never from a
fixed string. The broker owns the state-to-remedy mapping, and a command naming
the wrong remedy for the observed state sends the user to a refusal that touches
nothing. Then go to `## Recovery ladder`.

#### abort / NOT_HELD

There was no reservation to abort. Surface as a defect; `terminal-release`
`none`, `continues-to` `stop-in-flight`.

#### abort / NOT_HOLDER

The mutex is held by the reported other task. `terminal-release` `none` — never
abort into another task's reservation. `continues-to` `stop-in-flight`.

#### abort / NOT_OWNER_SESSION

The mutex records this task id but a different session (reported holder and pid).
`terminal-release` `none`, `continues-to` `stop-in-flight`; point at
`## Recovery ladder` if that session is gone.

#### abort / HOLDER_INCOMPLETE

The lock records no task id and can never be matched. `terminal-release` `none`,
`continues-to` `stop-in-flight`; point at `## Recovery ladder`.

#### abort / RETAINED

The abort succeeded but the release did not — **the reservation is still held**,
despite the wrapped inner verdict reading like a release. `terminal-release` is
`ladder`, `continues-to` `recovery`, `terminal-lock` `held-ladder`. Do not call
`finish` afterwards; go to `## Recovery ladder`.

## Recovery ladder

Reached only from a `recovery` row, where `terminal-lock` is `held-ladder`. State
first, in plain words, that **the merge mutex is still held** and that no other
task can merge until it is cleared. Then:

1. **Describe the holder.**

   ```bash
   ./.aitask-scripts/aitask_merge_task.sh status
   ```

2. **If `FREE_GUARD_PRESENT`** — a `.gc` guard leaked and is blocking recovery.
   Remove it with `rmdir '<dir>.gc'/h.* '<dir>.gc'`. **Never** `rm -rf`: `rmdir`
   is structurally incapable of destroying a lock's contents, which is exactly
   why it is the prescribed cure. Two arguments because the guard now carries a
   holder record (`h.<pid>.<nonce>`), so a bare `rmdir '<dir>.gc'` returns
   ENOTEMPTY. If `status` reported a holder pid, check that process is really
   gone first — a guard whose holder is alive is never stale.

3. **Dry-run the release** to see the holder, the tree residue, the remedy flag
   the broker itself derives, and a copy-safe armed command bound to this exact
   holder:

   ```bash
   ./.aitask-scripts/aitask_merge_task.sh force-release
   ```

4. **Run the armed command the dry run printed, verbatim.** It carries the
   `--expect <token>` that pins the holder, so a holder that changed in between
   is refused rather than silently overridden. Where a verdict named a remedy
   flag (`ABORT_UNSAFE`), that flag is the one to use — take it from the verdict
   or the dry run, never from memory.

`force-release` refuses a provably live holder, and its own verdicts are the
human's to read — they are documented with the lock model rather than rendered
here. The ladder terminates: either the mutex is released, or the tool names the
specific reason it will not act on it.

---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [git, bash_scripts, worktree]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1560
created_at: 2026-08-18 11:39
updated_at: 2026-08-18 12:54
---

## Context

Parent: **t1560** — Step 9's end-of-task merge is the only mutating operation in
the pipeline with **zero serialization**. It runs in the *shared repo root*
(`.claude/skills/task-workflow/SKILL.md:745` says "not from `aiwork/<task_name>/`"),
so every concurrently-merging task drives one HEAD, one index and one working
tree. The existing pre-flight cannot detect the race by design — `SKILL.md:758`
deliberately permits "the current tree is already on the output branch", which is
exactly the state both racing agents are in.

Read the parent plan **`aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md`
first** — it is the design of record and this task implements §1, §1a, §1b, §2,
§2a and §3 of it verbatim. The design was settled with the user before planning;
do not re-litigate the three decisions it records (parameterize `stale_lock.sh`
rather than fork it; hold the mutex through verification and cleanup; decompose
into three children).

This child is deliberately **first and provable end-to-end without touching a
single skill file** — it is the riskiest part of the parent, and every one of the
parent's five behavioural acceptance criteria can be demonstrated here.

## Scope

### 1. Three opt-in seams in `.aitask-scripts/lib/stale_lock.sh`

All default-off; with all three unset the file must behave **exactly** as today,
so `aitask_gate.sh`, `aitask_create.sh` and `lib/registry_lock.sh` are untouched.

| Seam | Default | Effect when set |
|---|---|---|
| `STALE_LOCK_IDENTITY_PID` | `$$` | value written into `<lock_dir>/pid` at publish time |
| `_STALE_LOCK_LIVENESS_FN` | unset | called as `<fn> <lock_dir>` at the top of `_stale_lock_reclaim_under_gc`; **sole** authority on the holder verdict (exit 0 = do not displace, 1 = reclaim), bypassing both the `kill -0` branch and the 120s tokenless-age branch |
| `STALE_LOCK_PUBLISH_FN` | unset | called as `<fn> <lock_dir>` **inside the `.gc` guard**, right after `pid`/`owner` are written and read-back-verified and before the guard is dropped; a nonzero return is a publish failure and takes the existing unwind-and-fail-closed path |

The third seam is required because the guard is released *inside*
`stale_lock_acquire` (`stale_lock.sh:207`) before it returns — a caller cannot
make its own identity files atomic with the acquisition from the outside.

Do **not** relax any invariant documented in that file's header (t1496/t1507).

### 2. `.aitask-scripts/lib/merge_lock.sh` — the adapter

Same shape as `lib/registry_lock.sh`, including its "deliberate boundary deltas"
header convention. It sets `STALE_LOCK_IDENTITY_PID` from
`lib/pid_anchor.sh::get_session_anchor_pid` (the same session identity
`aitask_lock.sh` anchors task locks to) and supplies a liveness fn that reads the
lock's recorded `pid` / `anchor_token` / `anchor_kind` and calls
`lock_holder_liveness`:

- `dead` → reclaim (single-winner, under the existing `.gc` guard);
- `alive` **or** `unknown` → **never** displace.

Lock name: **one global lock per repo**, `ait_lock_dir merge`. Two tasks merging
into *different* output branches still share the same HEAD, index and working
tree, so a per-branch lock would not exclude them.

The publish fn writes, under the guard, verified on read-back: `anchor_token`,
`anchor_kind`, `task_id`, `output_branch`, `task_branch`, `acquired_at`. Only
`state` (`merging` / `conflict` / `verifying`) is written afterwards and is
purely advisory — no decision reads it.

### 3. `.aitask-scripts/aitask_merge_task.sh` — the broker

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
on **stdout**; `WAITING:<holder_task>:<elapsed>` progress goes to **stderr**.

Full verdict vocabulary, the ownership contract, the abort state table, the
`force-release` two-remedy ladder and the `cleanup` contract are specified in
parent plan §1a / §1b / §2 / §2a. Implement them as written. The load-bearing
points:

- `begin` refuses with `NO_SESSION_ANCHOR` when `get_session_anchor_pid` returns
  the UNKNOWN sentinel — the capability is required at acquire time so it exists
  at release time.
- `finish` / `abort` / `cleanup` require **task match AND provable session match**
  (`lock_anchor_is_self`, `lib/pid_anchor.sh:224`). A task-id match is **never**
  sufficient on its own.
- `abort` branches on the **observed** merge state; `git merge` fails before
  creating `MERGE_HEAD` for a whole class of errors, and `git merge --abort` on
  that state exits non-zero. `ABORT_UNSAFE:<state>:<remedy_flag>` carries its own
  remedy flag so callers never hardcode one.
- `force-release` refuses a provably `alive` holder, and has **two distinct
  remedies** (`--abort-merge` for `MERGE_HEAD` present, `--reset-hard` for an
  unmerged index without it). A mismatched flag is refused
  (`WRONG_REMEDY:no_merge_head`), never attempted.
- `cleanup` requires `--task-complete` (`CLEANUP_REQUIRES_COMPLETION` otherwise),
  derives the worktree path from the porcelain record rather than trusting the
  argument, and returns `CLEANED_PARTIAL:<remains>` **keeping the reservation**
  rather than reporting success for a partial cleanup.

The lock is **retained** on `MERGE_OK` / `MERGE_CONFLICT` / `MERGE_FAILED` and
released on every pre-merge refusal. That retention is the behaviour change that
fixes the conflict-parked hazard.

### 4. Test-only seams (honoured **only** when `AITASKS_LOCK_DIR` is set)

- `AIT_MERGE_LOCK_DISABLED=1` — skip the acquire. Makes the red proof reachable
  and "the guard actually gates" executable rather than a hand mutation.
- `AIT_MERGE_BROKER_HOOK=<cmd>` — run inside the critical section between the
  checkout and the merge. Tests rendezvous on FIFOs through it, so interleaving
  is deterministic and **no test sleeps to reproduce a race**.

### 5. Helper whitelist — all five touchpoints

Per `aidocs/framework/aitasks_extension_points.md:163-184`, `aitask_merge_task.sh`
is skill-invoked (t1560_2 wires it into Step 9), so it needs an entry in **each**:
`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`. `lib/merge_lock.sh` is sourced, not invoked —
it needs **none**.

No `ait` dispatcher subcommand: per the same doc, helpers that exist to be shelled
out from skills stay full-path.

## Key files

- `.aitask-scripts/lib/stale_lock.sh` — the three seams (read its header first)
- `.aitask-scripts/lib/pid_anchor.sh` — `get_session_anchor_pid`,
  `lock_holder_liveness`, `lock_anchor_is_self` (all already exist; do not fork)
- `.aitask-scripts/lib/registry_lock.sh` — the adapter shape to copy
- `.aitask-scripts/aitask_gate.sh:119-160` — a caller's acquire/release/trap shape
- `.claude/skills/task-workflow/task-abort.md:57-88` — the guarded-cleanup shape
- `tests/test_gate_lock_single_winner.sh` — the concurrency-test shape to copy
- `tests/lib/proc_fixtures.sh` — process fixtures for anchored-session tests
- `aidocs/framework/shell_conventions.md` — read before writing either script

## Verification

`aidocs/framework/testing_conventions.md:10,18` mandates the enumeration below —
skipping an axis is a planning gap, not a stretch.

**Fixture rule for every recovery assertion:** a task branch's mergeability is a
property of the fixture, so "the lock works again" is always proved by a task
whose branch merges **cleanly** into `<output_branch>` — never by re-running the
branch whose merge produced the residue being recovered from. Keep three shapes
on hand: cleanly-mergeable, conflicting, unrelated-history.

| # | Case | Assertion |
|---|---|---|
| 1 | Red proof, mutex disabled | A parks between checkout and merge (FIFO hook); B merges; A resumes -> A's merge commit's tree **contains B's file**. Same test with the mutex enabled: B reports `BUSY:tA`, A's commit is clean. |
| 1n | Negative control for 1 | The mutation must reach the *merge-contamination* assertion, not trip an earlier one — assert the named failing case, not "goes red somewhere". |
| 2 | N = 51 concurrent callers | Each caller runs `begin ... --wait-secs <budget>` and, on `BUSY`, **retries to completion** up to a bounded attempt cap, then `finish`es. Assert exactly 51 `MERGE_OK`, 51 merge commits, one per logical caller; **zero** nonzero exits and zero git-level errors; and **at least one** `BUSY`/`WAITING` observed naming a real holder (else the case is vacuous). A caller that exhausts its cap is a failure. |
| 3 | Conflict-parked reservation | A stops at `MERGE_CONFLICT`; B does **not** enter and its report names A's task id; after A's `abort`, B proceeds. |
| 4 | Stale-holder recovery | anchor = an `AIT_AGENT_PID` fixture process; killed mid-section -> exactly **one** waiter reclaims. Live-anchored holder -> **never** displaced; `unknown` anchor -> never displaced. |
| 5 | Guard gates | removing the acquire (via the documented seam) makes case 1 and case 3 fail. |
| 6 | Callers unchanged | `test_stale_lock.sh`, `test_gate_lock_single_winner.sh`, `test_registry_lock_single_winner.sh`, `test_parallel_child_create.sh`, `test_task_lock.sh` all still pass. |
| 7 | Wedge recovery terminates | unresolvable anchor -> lock never auto-reclaimed; `status` names it; `force-release --yes` clears it. `force-release` on a **live** holder -> `REFUSED_LIVE_HOLDER`, lock intact. `MERGE_HEAD` present, no flag -> `RESIDUE_PRESENT`, lock intact; with `--abort-merge` the tree is verified clean and the lock released. **Both residue states driven separately**: unmerged-index-without-`MERGE_HEAD` (plant it by conflicting a merge then removing `.git/MERGE_HEAD`) -> `--abort-merge` returns `WRONG_REMEDY:no_merge_head` with the lock **kept**, and `--reset-hard --yes` reaches a verified-clean tree and releases. On **every** rung the "usable again" assertion is a `begin` from a **different, cleanly mergeable task**. |
| 8 | Non-owner release refused | (a) task B's `finish`/`abort`/`cleanup` against A's held lock -> `NOT_HOLDER:tA`, A's lock intact, A can still `finish`. (b) **same task id, different caller that cannot prove its anchor** -> `NOT_OWNER_SESSION`, lock intact. (c) same task id, provably different live session -> `NOT_OWNER_SESSION`. (d) planted lock dir with no `task_id` -> `status` reports `HOLDER_INCOMPLETE`, `force-release --yes` clears it. (e) `begin` with no resolvable anchor -> `NO_SESSION_ANCHOR`, nothing locked. |
| 8b | Non-conflict merge failure | task **U** owns a branch with a history unrelated to `<output_branch>`, so `git merge` fails *before* `MERGE_HEAD` exists -> `MERGE_FAILED`, then `abort` -> `RELEASED_NO_MERGE` (**not** `ABORT_FAILED`). The usable-again proof comes from a **different, cleanly mergeable task V** — re-running U's own `begin` would fail identically forever. Plus the planted no-`MERGE_HEAD`-but-unmerged-index state -> `ABORT_UNSAFE`, lock **kept**. |
| 8c | Verification window does not strand the lock | a scripted caller mimicking Step 9 — `begin` -> run an **injected failing verification command** -> take the "release and stop" branch -> `finish` **without** cleanup — leaves the lock free, the merge commit intact, and `aitask/<task_name>` plus its worktree still present. Then re-run `begin` on that retained branch: `MERGE_OK` with **no new commit** (idempotent re-reservation). |
| 9 | Publish is atomic with acquire | with `STALE_LOCK_PUBLISH_FN` returning nonzero, `stale_lock_acquire` unwinds and leaves **no** lock dir behind (fail closed), and the contender's next attempt succeeds. |
| 10 | Cleanup authorization + partial failure | `cleanup` without `--task-complete` -> `CLEANUP_REQUIRES_COMPLETION`, **branch and worktree intact**, and a following `begin` on that branch still reaches `MERGE_OK`. Non-owner -> refused, worktree intact. `<task_name>` disagreeing with the recorded `task_branch` -> `TARGET_MISMATCH`, nothing removed. A **moved** worktree is still found (path from the porcelain record). Undeletable worktree / unmerged branch -> `CLEANED_PARTIAL:<remains>` with the reservation **still held**, never `CLEANED`. |

Also run: `shellcheck .aitask-scripts/aitask_merge_task.sh .aitask-scripts/lib/merge_lock.sh .aitask-scripts/lib/stale_lock.sh`.

## Notes for sibling tasks

- **t1560_2** consumes the verdict vocabulary from here. Every verdict this
  script can emit must get a branch in the rendered Step 9 — export the list
  plainly (e.g. a comment block or a `--list-verdicts` verb) so t1560_2's
  rendered-verdict test can assert coverage mechanically rather than by hand.
- `ABORT_UNSAFE` carries `<state>:<remedy_flag>`; t1560_2's rendered branch must
  echo that flag rather than hardcoding `--abort-merge` / `--reset-hard`.
- **t1560_3** documents the `NO_SESSION_ANCHOR` precondition and the
  `force-release` ladder in `website/content/docs/concepts/locks.md`.

## Non-goals

- No Step 9 / skill edits — that is **t1560_2**.
- No website docs — that is **t1560_3**.
- No fetch added to Step 9 (**t1393**); no edit-time file-overlap advice
  (**t1343** / **t1344**); no change to push behaviour.

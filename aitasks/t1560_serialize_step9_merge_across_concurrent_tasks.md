---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [task_workflow, git, worktree, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1560_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-17 23:29
updated_at: 2026-08-18 11:39
---

## Problem

When several tasks run concurrently in `aiwork/<task>/` worktrees and each
reaches Step 9, approving "Proceed with merge?" in more than one session at the
same time is **unsafe**. The end-of-task merge is the only mutating operation in
the entire pipeline with **zero serialization**.

**The merge runs in the shared repo root, not in the task's worktree.**
`.claude/skills/task-workflow/SKILL.md:745` instructs "Run from the repo root,
not from `aiwork/<task_name>/`", and the merge itself
(`.claude/skills/task-workflow/SKILL.md:783-788`) is:

```bash
git checkout "$output_branch" --
git symbolic-ref --short HEAD    # MUST print "$output_branch"
git merge "aitask/<task_name>"
```

So every concurrently-merging task drives **one** HEAD, **one** index and **one**
working tree. It is agent-executed inline bash — no script owns the critical
section, so there is nothing to wrap.

### What actually goes wrong

1. **The pre-flight cannot detect the race, by design.**
   `SKILL.md:745-758` checks only that `refs/heads/<output_branch>` exists and
   that no *other* worktree holds it, and `:758` deliberately **permits** the
   case "the current tree is already on the output branch" — because for a single
   agent that makes checkout a safe no-op. That is exactly the state both racing
   agents are in, so the check passes for A and B simultaneously. It is a TOCTOU
   check against the wrong hazard.

2. **The `symbolic-ref` assertion does not cover this.** It proves HEAD is not
   detached; it cannot distinguish "I put us on `main`" from "another session
   put us on `main` and is mid-merge". It passes in the race.

3. **A conflict-parked merge leaves the shared tree reserved by nobody.**
   `SKILL.md:791` is "Handle merge conflicts: Ask user for guidance if needed" —
   no `--abort` path, no reservation. While A waits for a human, the tree holds
   a conflicted index and `MERGE_HEAD`. B's `git checkout` then either fails, or
   B proceeds and **A's partially-resolved conflict work is absorbed into B's
   merge commit**. This is the most damaging outcome: not repo corruption, but
   misattributed content plus lost resolution work.

4. **Interleaved merges fail hard.** Two `git merge` invocations against one
   index race on `.git/index.lock` / `MERGE_HEAD`. Git's own locking prevents
   corruption, so the failure mode is an aborted operation mid-workflow, not a
   broken repository — but Step 9 has no recovery path for it.

5. **Post-merge verification is cross-contaminated.**
   `SKILL.md:800` runs `./ait gates run <task_id>` in that same tree. If B's
   merge landed first, A's verdict measures `main + A + B`. The gate ledger
   append is itself mutex-protected (`aitask_gate.sh:119-138`), so the *record*
   is safe — the **verdict** is not. In a project whose gate re-records
   protected image baselines, a contaminated run can demand a re-record that the
   task never earned.

6. **`git status --porcelain` (`SKILL.md:780`) cannot attribute what it sees.**
   It will show B the other task's in-flight merge residue with no way to tell
   whose it is — the same declared-not-observed limitation already documented in
   `.aitask-scripts/aitask_change_surface.sh:32-42`.

7. **Unhandled cleanup failure.** `SKILL.md:836-841` runs
   `git worktree remove` / `rm -rf` / `git branch -d` with **no error handling**
   (unlike the abort path in `.claude/skills/task-workflow/task-abort.md:57-88`,
   which guards every call). These are name-scoped per task, so two tasks can
   **not** delete each other's worktree or branch — but they do contend on the
   repo-level worktree lock, and `git worktree prune` in unrelated scripts
   (`aitask_init_data.sh:100`, `aitask_setup.sh`, `aitask_crew_cleanup.sh:109`,
   `aitask_brainstorm_delete.sh:105`, `install.sh:383`) can prune a registration
   whose directory is momentarily absent.

### Why nothing existing covers it

`grep -rn flock` over the repo returns **nothing**, and no lock in the tree
guards a merge:

* `aitask_lock.sh` (git-CAS on the `aitask-locks` orphan branch, PID-anchored via
  `lib/pid_anchor.sh`) excludes two sessions from **the same task ID** — not two
  different tasks from the shared repo root.
* `lib/stale_lock.sh` is the tree's single hardened mutex protocol
  (`.gc`-guarded single-winner reclaim, live PIDs never displaced, owner-token
  release, verified removals). Its adapters and callers cover the project
  registry / agent marks / shadow rejections (`lib/registry_lock.sh`), gate
  ledger appends (`aitask_gate.sh:119-138`), child-task numbering
  (`aitask_create.sh:339-341`) and attach/artifact transactions
  (`lib/attachment_lock.sh`). **No caller guards the merge.**
* `lib/task_utils.sh` protects only the `aitask-data` branch: a wedge guard
  (`:108-136`) and a 3-attempt `pull --rebase` push retry (`:342-361`).
* `lib/atomic_write.sh:1-12` states outright that it does not serialize a
  read-modify-write cycle and that callers must hold their own mutex.

The published story matches: `website/content/docs/concepts/locks.md:33` says
locks exist to stop two sessions picking the same task, and
`website/content/docs/workflows/parallel-development.md:20` describes the
merge-back **with no serialization caveat at all**.

### Two adjacent facts this task should keep in view

* **Step 9 never fetches** (`SKILL.md:323`) — already filed as **t1393**. Two
  concurrent local merges therefore also both land on a possibly-stale local
  `main`.
* **Step 9 never pushes the output branch.** In branch mode `./ait git push`
  (`SKILL.md:975`) pushes only `aitask-data`; in legacy mode `./ait git`
  degrades to plain `git` and pushes the code branch only by accident of mode.
  Merged commits accumulate locally until a manual push, at which point the
  divergence surfaces as a non-fast-forward rejection outside the workflow.

## Scope

Serialize the Step 9 merge critical section behind a mutex, and make the
serialization visible to the user instead of failing at a git error.

### 1. A merge broker script

Extract the critical section out of inline bash into one script (working name
`.aitask-scripts/aitask_merge_task.sh`) so that a single process owns the lock
for the whole section and releases it from a trap. Suggested surface:

* `begin <task_id> <output_branch> <task_branch>` — acquire the mutex, run the
  existing pre-flight (`refs/heads/` fully qualified, foreign-worktree check),
  `checkout` + `symbolic-ref` assert + `merge`, and emit structured lines
  (`MERGE_OK`, `MERGE_CONFLICT:<paths>`, `WAITING:<holder_task>:<seconds>`,
  `PREFLIGHT_MISSING`, `UNSAFE_OUTPUT_BRANCH`, …).
* `finish <task_id>` / `abort <task_id>` — release, so a conflict-parked merge
  **keeps the shared tree reserved** until the human is done. This is the
  behaviour change that fixes hazard 3.
* `status` — report the current holder so the waiting agent can tell the user
  *which* task it is queued behind rather than printing a bare timeout.

### 2. Lock lifetime is the hard design problem

A shared-tree reservation must survive **between** agent turns: each Bash tool
call is a separate short-lived process, so a `kill -0`-on-caller-PID holder dies
instantly and the reclaim logic would hand the tree to the next agent while the
first is still resolving a conflict. `aitask_lock.sh` already solved this class
of problem with `lib/pid_anchor.sh`; anchor the merge mutex to the **same
session identity the task lock uses**, and reuse `lib/stale_lock.sh` for the
protocol rather than forking a new one. Plan must state explicitly what happens
when the anchored session dies mid-conflict, and how a human recovers (the
equivalent of `aitask_lock_diag.sh` / `registry_lock_describe`).

### 3. Decide where verification sits, and say why

Holding the mutex across `./ait gates run` removes contamination (hazard 5) but
serializes multi-minute build/test runs across all concurrent tasks; releasing
before it restores contamination. **The plan must pick one and justify it** —
"safer either way" is not an outcome. If the lock is released before
verification, the plan must name what makes the verdict attributable instead;
if it is held, the plan must specify the wait budget and the user-facing
progress reporting that makes a long queue legible rather than looking hung.

### 4. Wire it in, everywhere

* Step 9 in the Jinja source `.claude/skills/task-workflow/SKILL.md` (the merge
  block at `:778-791` and the cleanup at `:836-841`, which must also gain the
  error handling it currently lacks).
* Re-render every variant: `task-workflow-{default,fast,remote}-`, the
  `fast_worktree` variant used by downstream installs, the Codex ports under
  `.agents/skills/`, the opencode ports under `.opencode/skills/`, and the
  golden fixtures `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`.
* `.claude/skills/aitask-pickrem/`, `aitask-pickweb/` and
  `.claude/skills/aitask-web-merge/SKILL.md` must be checked for the same
  pattern (the web-merge skill is the only merge path in the tree that uses
  `--no-ff` and pushes the target).
* The merge-approval wording is pinned by
  `tests/test_workflow_phase_prompt_drift.sh:60,104` and the phase regex in
  `.aitask-scripts/lib/workflow_phase.py:103`. If the prompt gains a "queued
  behind tN" line, both must be updated in the same change, and the
  non-skippable banner at `SKILL.md:760-770` must stay intact — the mutex
  serializes the merge, it does not become a reason to auto-approve it.
* `website/content/docs/workflows/parallel-development.md:20` and
  `website/content/docs/concepts/locks.md` must document the merge mutex; the
  latter's "what the lock actually excludes" table is currently accurate only
  because merging is unprotected.

## Constraints

* `CLAUDE.md:322` requires **explicit approval before introducing a new
  concurrency primitive**. Ask before building one; reusing `stale_lock.sh` +
  `pid_anchor.sh` rather than inventing a protocol is the point of the design
  above.
* `aidocs/framework/testing_conventions.md:10,18` mandates enumerated
  concurrency test cases for any change introducing a concurrency primitive,
  including an N-concurrent-caller case with N raised past 50.

## Non-goals

* Adding a fetch to Step 9 — that is **t1393**, and it must not be silently
  absorbed here. If this task lands first, t1393's wiring point becomes the
  broker script; record that in the Final Implementation Notes.
* Edit-time file-overlap advice between running agents — that is **t1343**, with
  worktree-aware granularity in **t1344**. This task is about the merge, not
  about who is editing what.
* Pushing the output branch. The absence of a push is recorded above as a
  finding, but changing push behaviour is a separate decision with its own blast
  radius.
* Shared-checkout mode (`create_worktree: false`, as in `fast.yaml:5`) needs no
  merge mutex: with no task branch, Step 9's merge block does not run at all.
  The plan should state this so the guard is not applied where it only adds
  latency.

## Acceptance criteria

1. **A reachable red proof exists first.** A test drives two callers into the
   critical section and, **with the mutex disabled**, observes a concrete
   failure — either a non-zero merge exit, or a commit on `<output_branch>`
   containing the other caller's tree. The proof must be shown failing before
   the fix and must not depend on `sleep`-based timing to reproduce. With the
   mutex enabled the same test passes.
2. **N-concurrent test at N > 50** (per `testing_conventions.md:18`): all
   callers either merge or report `WAITING`/busy with the holder's task id;
   **zero** callers exit on a git-level error, and the final
   `<output_branch>` history contains exactly one merge commit per caller.
3. **Conflict-parked reservation is proven.** Caller A stops at a conflict; a
   test asserts caller B does **not** enter the critical section, and that B's
   report names A's task id. After `abort`/`finish` by A, B proceeds.
4. **Stale-holder recovery is proven.** With A's anchored session killed
   mid-critical-section, exactly one waiting caller reclaims, and a test asserts
   a live-anchored holder is **never** displaced.
5. **The guard actually gates.** Removing the mutex acquisition from the broker
   makes at least one enumerated test fail. A documentation-only note about the
   hazard does not satisfy any criterion here.
6. **No prose contradicts the shipped behaviour**: the prompt-drift test passes,
   the golden fixtures match, and every rendered variant/port contains the same
   merge instructions as the Jinja source.

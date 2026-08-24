---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1560_1]
issue_type: feature
status: Implementing
labels: [task_workflow, git, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1560
implemented_with: claudecode/opus5
created_at: 2026-08-18 11:40
updated_at: 2026-08-24 18:05
---

## Context

Parent: **t1560**. Sibling **t1560_1** ships
`.aitask-scripts/aitask_merge_task.sh` (the merge broker), `lib/merge_lock.sh`
and three opt-in seams in `lib/stale_lock.sh`. This task wires the broker into
Step 9 of the shared workflow and propagates it to every rendered surface.

Read **`aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md`** first —
its **§4** (Step 9 control flow, one branch per verdict) and **§4a** (the
verification window) are the specification for this task, and its **§5** records a
finding that makes this cheaper than the parent task assumed. Read
`aiplans/archived/p1560/p1560_1_*.md` for what actually shipped in the broker —
verdict strings must be taken from the implementation, not from the plan's
prose, in case they diverged.

`depends: [1560_1]` — this task cannot be verified before the broker exists.

## Scope

### 1. The Jinja source: `.claude/skills/task-workflow/SKILL.md`

Replace the inline merge block (currently `SKILL.md:778-791` in the Jinja source
— re-locate it, line numbers drift) with:

1. a `aitask_merge_task.sh status` probe **before** the approval prompt, so the
   question can name the task it is queued behind;
2. `begin` / `finish` / `abort` around the merge;
3. the cleanup block (now `SKILL.md:841-851`) routed through the broker's
   `cleanup ... --task-complete` verb, with a branch per cleanup verdict
   including `CLEANED_PARTIAL`. **Amended:** the parent task's "cleanup must
   gain the error handling it currently lacks" premise is stale — **t1548**
   already replaced the unguarded `git worktree remove` / `rm -rf` /
   `git branch -d` sequence with a bare, `--strict`
   `aitask_task_worktree.sh remove`, which is the same helper the broker's
   `cleanup` delegates to. What this task adds is running cleanup **under the
   reservation** and branching its verdicts, not error handling.

**Render every row of parent-plan §4 and §4a**, including this invariant sentence
verbatim in the skill text — it is what stops an agent proceeding to gates after
a refused `begin`:

> Every path on which the broker reported the lock **held** ends in exactly one
> `finish` or `abort`. Every path on which it is **not** held calls neither, and
> never proceeds to verification, cleanup or archival.

Two branches are easy to get wrong and are called out in the plan:

- **`ABORT_UNSAFE:<state>:<remedy_flag>`** — the rendered text must **echo the
  broker-supplied `<remedy_flag>`**, never a hardcoded `--abort-merge` or
  `--reset-hard`. The broker owns the state→remedy mapping; a hardcoded command
  sends the user to a `WRONG_REMEDY` refusal in the state it does not match.
- **In-flight exits must not clean up.** `cleanup` deletes `aitask/<task_name>`
  and its worktree, so any §4a row that leaves the task in-flight
  (`error` / `blocked` / `pending` / `gates_rc` nonzero / "release and stop here")
  calls `finish` **alone** and retains the branch. Deleting it would destroy the
  branch the `POSTIMPL` resume must re-merge.

The **non-skippable merge-approval banner stays intact** — the mutex serializes
the merge, it does not become a reason to auto-approve it.

### 2. What is NOT needed (verify, do not assume)

The parent task expected `tests/test_workflow_phase_prompt_drift.sh:60,104` and
`.aitask-scripts/lib/workflow_phase.py:103` to need updating. They do not, *if*
the "queued behind t<N>" clause is appended to the **end** of the question:
both match on the **prefix** `Proceed with merge of code changes into`.

**Prove it, don't assume it:** add an assertion that the new question form still
matches `workflow_phase.WORKFLOW_PROMPTS`, and do not reword the prefix.
(Verified at plan verification: both guards match the 39-character prefix, and
everything after `into` is outside them. Guard A greps
`.claude/skills/task-workflow/` recursively for `hits >= 1`.)

**Amended — one test this task did not name DOES need updating.**
`tests/test_skill_render_task_workflow.sh` **Test 4c** pins three literals that
move *into* the broker: `git checkout "$output_branch" --`,
`git rev-parse --verify --quiet "refs/heads/$output_branch"` and
`git merge "aitask/<task_name>"`. They must be **re-pinned before they are
deleted** — replacement assertions that the rendered `begin` invocation passes
`"$output_branch"` as a bound quoted variable and that no rendered command line
substitutes the literal `<output_branch>` placeholder — so the injection-safety
property is never unpinned, not even between two edits of one commit.
`UNSAFE_OUTPUT_BRANCH` survives unchanged: it is now a broker verdict.

### 3. New test: rendered-verdict coverage

**Amended at plan verification — the control flow is extracted to a procedure
file, and the coverage unit is a verb-qualified table row.**

The broker control flow lives in a new
`.claude/skills/task-workflow/merge-broker.md`, invoked from Step 9 (the pattern
already used by `remote-drift-check.md` / `merge-target-sync.md` /
`gate-recording.md`); rendering ~26 verdict branches inline would take Step 9
from ~260 to ~410 lines across nine rendered surfaces. The coverage target is
therefore the rendered `merge-broker.md` (canonical golden
`tests/golden/procs/task-workflow/merge-broker-default.md`, plus the
profile-invariance assertion) rather than `SKILL-{default,fast,remote}.md`.

`merge-broker.md` carries **one row per (verb, verdict) pair** — 41 rows over 30
distinct tokens — with closed-vocabulary `lock` / `terminal-release` /
`lock-through` / `continues-to` / `terminal-lock` columns, and one
`#### <verb> / <TOKEN>` operational branch per row. Coverage scope is the five
verbs Step 9 invokes: `begin` / `finish` / `abort` / `cleanup` / **`status`**
(the pre-approval holder probe). `force-release` is excluded — it is a human
recovery ladder run outside the workflow, documented by **t1560_3**.

A row-less verdict, an orphan branch, or a branch contradicting its row must
**fail the build, not ship**, and the test also asserts the `ABORT_UNSAFE` branch
carries no hardcoded remedy literal. Verb-qualification is the point:
`NOT_HELD` appears under three verbs and `RETAINED` under three, so a token-union
check passes with an entire verb's branch missing.

### 4. Rerender and goldens — in the same commit

- `./.aitask-scripts/aitask_skill_rerender.sh` **once per profile**
  (`default` / `fast` / `remote` — one call per profile; a single call does not
  cover them all).
- The Codex ports under `.agents/skills/task-workflow-*-codex-` and the OpenCode
  ports under `.opencode/skills/task-workflow-*`.
- Regenerate `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`.
- Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.

## Key files

- `.claude/skills/task-workflow/SKILL.md` — the Jinja source (the ONLY hand-edited copy)
- `.aitask-scripts/aitask_skill_rerender.sh` — the rerender driver
- `.aitask-scripts/aitask_skill_verify.sh` — run before committing
- `.claude/skills/task-workflow/merge-broker.md` — the new procedure file
- `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
- `tests/golden/procs/task-workflow/merge-broker-default.md` — canonical golden
- `tests/test_merge_broker_rendered_verdicts.sh` — the new coverage test
- `tests/test_skill_render_task_workflow.sh` — Test 4c re-pin; register the new
  procedure in `WRAPPED_FILES_INVARIANT`
- `tests/test_workflow_phase_prompt_drift.sh` — Guard A greps the literal prefix
- `.aitask-scripts/lib/workflow_phase.py:96-108` — `WORKFLOW_PROMPTS`
- `aidocs/framework/skill_authoring_conventions.md` — read before editing any `.md.j2` / skill file

## Commit boundary

`aitasks/` and `aiplans/` are symlinks into the `aitask-data` branch, so this
amendment is committed **on its own**, path-scoped, through `./ait git`, before
any source edit. The implementation, tests, rerender and goldens land in a
separate `feature:` commit that contains no `aitasks/` or `aiplans/` path — an
amended AC mixed into the implementation commit is unreviewable, because the
reviewer cannot tell which came first.

## Verification

- `bash tests/test_workflow_phase_prompt_drift.sh` — passes unchanged
- `bash tests/test_skill_render.sh` and `bash tests/test_skill_verify.sh`
- the new rendered-verdict coverage test, plus a **negative control**: delete one
  verdict's branch from the source and confirm the test fails **naming that
  verdict**, not merely going red somewhere
- `./.aitask-scripts/aitask_skill_verify.sh` exits 0
- `git diff` on the goldens is reviewable and matches the Jinja change

## Notes for the implementer

- This repo has **no `fast_worktree` profile** — only `default` / `fast` /
  `remote` exist under `aitasks/metadata/profiles/`. The parent task's mention of
  one refers to downstream installs.
- **Verify, do not assume**, that Re-entry Routing's `POSTIMPL` text still holds:
  it asserts `aitask/<task_name>` already exists at re-entry, which is exactly
  what the "no cleanup on an in-flight exit" rule preserves. If any rendered
  branch cleans up before archival, that is the bug.
- Under `create_worktree: false` (this repo's own `fast.yaml:5`) there is no task
  branch and the merge block does not run at all — the broker must **not** be
  invoked there, or it adds pure latency for nothing.

## Non-goals

- No changes to the broker script — that is **t1560_1**. If a verdict is missing
  or misshapen, note it and coordinate rather than editing it here.
- No website docs — that is **t1560_3**.
- **No fetch added to Step 9** — that is **t1393**. Record in this task's Final
  Implementation Notes that t1393's wiring point is now the broker script.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-24T15:06:05Z status=pass attempt=1 type=human

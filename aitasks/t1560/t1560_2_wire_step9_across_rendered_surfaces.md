---
priority: high
effort: medium
depends: [t1560_1]
issue_type: feature
status: Ready
labels: [task_workflow, git, bash_scripts]
gates: [risk_evaluated]
anchor: 1560
created_at: 2026-08-18 11:40
updated_at: 2026-08-18 11:40
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
3. the unguarded cleanup block (currently `SKILL.md:836-841`) replaced by the
   broker's guarded `cleanup ... --task-complete` verb and its `CLEANED_PARTIAL`
   branch. This is the "cleanup must gain the error handling it currently lacks"
   requirement from the parent task.

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

### 3. New test: rendered-verdict coverage

Every verdict string the broker can emit — `begin`, `abort`, `cleanup` and
`finish` alike — must appear in the rendered
`tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`. A verdict with
no branch must **fail the build, not ship**. The same test asserts the
`ABORT_UNSAFE` branch carries no hardcoded remedy literal.

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
- `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
- `tests/test_workflow_phase_prompt_drift.sh` — Guard A greps the literal prefix
- `.aitask-scripts/lib/workflow_phase.py:96-108` — `WORKFLOW_PROMPTS`
- `aidocs/framework/skill_authoring_conventions.md` — read before editing any `.md.j2` / skill file

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

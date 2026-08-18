---
Task: t1560_2_wire_step9_across_rendered_surfaces.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Sibling Tasks: aitasks/t1560/t1560_1_*.md, aitasks/t1560/t1560_3_*.md
Archived Sibling Plans: aiplans/archived/p1560/p1560_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1560_2 — Wire Step 9 across every rendered surface

## Context

Sibling **t1560_1** ships `.aitask-scripts/aitask_merge_task.sh` (the merge
broker), `lib/merge_lock.sh` and three opt-in seams in `lib/stale_lock.sh`. This
task replaces Step 9's inline, unserialized merge with calls to that broker, and
propagates the change to every rendered variant, port and golden.

Read the parent plan
`aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md` — its **§4**
(Step 9 control flow, one branch per verdict) and **§4a** (the verification
window) are this task's specification. Then read
`aiplans/archived/p1560/p1560_1_*.md`: **verdict strings must be taken from what
shipped**, not from the plan's prose, in case the two diverged.

`depends: [1560_1]`.

## Implementation

### Step 1 — The Jinja source `.claude/skills/task-workflow/SKILL.md`

This is the **only** hand-edited copy; everything else is rendered from it.

Re-locate the merge block (currently around `:778-791`) and the cleanup block
(currently around `:836-841`) — line numbers drift. Replace with:

1. an `aitask_merge_task.sh status` probe **before** the approval prompt, so the
   question can name the task it is queued behind;
2. `begin` / `finish` / `abort` around the merge;
3. the broker's guarded `cleanup … --task-complete` verb in place of the
   unguarded `git worktree remove` / `rm -rf` / `git branch -d` sequence, plus
   its `CLEANED_PARTIAL` branch. This is the parent task's "cleanup must gain the
   error handling it currently lacks" requirement.

Render **every row** of parent-plan §4 and §4a, and include this invariant
sentence verbatim in the skill text:

> Every path on which the broker reported the lock **held** ends in exactly one
> `finish` or `abort`. Every path on which it is **not** held calls neither, and
> never proceeds to verification, cleanup or archival.

Two branches are easy to get wrong:

- **`ABORT_UNSAFE:<state>:<remedy_flag>`** — the rendered text must **echo the
  broker-supplied `<remedy_flag>`**, never a hardcoded `--abort-merge` or
  `--reset-hard`. The broker owns the state→remedy mapping; a hardcoded command
  sends the user to a `WRONG_REMEDY` refusal in the state it does not match.
- **In-flight exits must not clean up.** `cleanup` deletes `aitask/<task_name>`
  and its worktree, so every §4a row that leaves the task in-flight
  (`error` / `blocked` / `pending` / `gates_rc` nonzero / "release and stop
  here") calls `finish` **alone** and retains the branch. Deleting it would
  destroy the branch the `POSTIMPL` resume must re-merge — and would falsify Re-
  entry Routing's own claim that `aitask/<task_name>` "already exists" at
  re-entry.

The **non-skippable merge-approval banner stays intact**. The mutex serializes
the merge; it is not a reason to auto-approve it.

The "queued behind t\<N\>" clause goes at the **end** of the question — see
Step 2.

### Step 2 — What is NOT needed (verify, do not assume)

The parent task expected `tests/test_workflow_phase_prompt_drift.sh:60,104` and
`.aitask-scripts/lib/workflow_phase.py:103` to need updating. They do **not**,
provided the new clause is appended to the end: both match on the **prefix**
`Proceed with merge of code changes into`.

Prove it rather than assuming it — add an assertion that the new question form
still matches `workflow_phase.WORKFLOW_PROMPTS` — and do not reword the prefix.

### Step 3 — New test: rendered-verdict coverage

Every verdict string the broker can emit (`begin`, `abort`, `cleanup`, `finish`)
must appear in the rendered
`tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`. Source the
list from t1560_1's exported vocabulary (its `--list-verdicts` verb / delimited
comment block), not from a hand transcription — a transcribed list silently rots.

The same test asserts the rendered `ABORT_UNSAFE` branch carries **no** hardcoded
`--abort-merge` / `--reset-hard` literal.

**Negative control:** delete one verdict's branch from the Jinja source and
confirm the test fails **naming that verdict**, not merely going red somewhere.

### Step 4 — Rerender and goldens, in the same commit

- `./.aitask-scripts/aitask_skill_rerender.sh` **once per profile** — `default`,
  `fast`, `remote`. One call does not cover them all.
- The Codex ports under `.agents/skills/task-workflow-*-codex-` and the OpenCode
  ports under `.opencode/skills/task-workflow-*`.
- Regenerate `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`.
- `./.aitask-scripts/aitask_skill_verify.sh` before committing.

Stage explicitly by path — a rerender touches many targets, and only the
task-workflow ones belong in this commit.

## Verification

- `bash tests/test_workflow_phase_prompt_drift.sh` — passes unchanged
- `bash tests/test_skill_render.sh`, `bash tests/test_skill_verify.sh`
- the new rendered-verdict coverage test, **plus its negative control**
- `./.aitask-scripts/aitask_skill_verify.sh` exits 0
- `git diff` on the goldens is reviewable and matches the Jinja change
- read the rendered `SKILL-fast.md` and confirm no in-flight row reaches
  `cleanup` — check the **rendered** output, not the Jinja source

## Notes for the implementer

- This repo has **no `fast_worktree` profile** — only `default` / `fast` /
  `remote` exist under `aitasks/metadata/profiles/`. The parent task's mention of
  one refers to downstream installs.
- **Verify, do not assume**, that Re-entry Routing's `POSTIMPL` text still holds.
- Under `create_worktree: false` (this repo's own `fast.yaml:5`) there is no task
  branch and the merge block does not run at all — the broker must **not** be
  invoked there.
- Read `aidocs/framework/skill_authoring_conventions.md` before editing.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge per the shared workflow's Step 9.

## Non-goals

- No changes to the broker script — **t1560_1**. If a verdict is missing or
  misshapen, note it and coordinate rather than editing it here.
- No website docs — **t1560_3**.
- **No fetch added to Step 9** — that is **t1393**. Record in the Final
  Implementation Notes that t1393's wiring point is now the broker script.

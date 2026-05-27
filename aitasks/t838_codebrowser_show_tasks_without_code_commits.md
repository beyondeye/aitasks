---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [codebrowser]
created_at: 2026-05-27 08:45
updated_at: 2026-05-27 08:45
---

## Problem

`ait codebrowser` history screen silently omits archived tasks that have
no `(tNN)`-tagged source-code commit. Concrete trigger: task **t787**
(a `manual_verification` task) was archived just now but does not appear
in the history list.

This is **not** an isolated bug — it is a missing capability for an
entire class of tasks that legitimately produce no source-code commits:

- `manual_verification` tasks where the verification work is recording
  PASS / FAIL / SKIP on a checklist and spawning follow-up tasks (e.g.
  t787 → spawned t837 for the failed item)
- `brainstorm` sessions whose only output is a set of newly-created
  child / follow-up tasks (no code changes)
- Possibly other task types (chore/refactor variants) that may complete
  without any code commit

Counter-example: `t604` is also `manual_verification` but produced an
incidental `refactor: ... (t604)` commit and so shows up correctly.

## Root cause

`.aitask-scripts/codebrowser/history_data.py`:

- `_build_commit_map()` (line ~72) runs `git log --all --grep=(t ...`
  and parses messages with regex `\(t(\d+(?:_\d+)?)\)` (line 83) —
  this only matches commits using the documented `<type>: ... (tNN)`
  convention.
- `_merge_chunk()` (line ~100) silently drops any archived task whose
  `task_id` is not present in `commit_map`. The archived `.md` file is
  iterated and discarded — no fallback.

For tasks with no source commit, all activity lives on the
`aitask-data` branch as framework `ait:` commits without `(tNN)`
parens (e.g. `ait: Archive completed t787 task and plan files`,
`ait: Record verification state for t787`,
`ait: Seed verification checklist for t787`). These are
**intentionally** framework-style — the documented commit recipe in
`.claude/skills/task-workflow/manual-verification.md:225` is
`ait: Record verification state for t<task_id>`.

So the `(tNN)` requirement should NOT be dropped. Instead, codebrowser
needs a deliberate fallback path for the no-code-commit case.

## Goal

Surface these tasks in `ait codebrowser` history with a clear visual
marker so users can distinguish "verification / planning only" from
"produced code".

## Acceptance criteria

1. Archived tasks with no `(tNN)` code commit (e.g. t787) appear in
   `ait codebrowser` history list.
2. Their commit date / hash is anchored to a sensible fallback —
   preferred order:
   - latest framework commit on `aitask-data` branch that touches the
     task's archived file (typically the
     `ait: Archive completed t<N>...` commit)
   - else file mtime of the archived `.md`
3. Each such row is **visually marked** in the list — e.g. an icon, a
   suffix like `[no-code]` / `[verif-only]`, or a distinct issue_type
   badge color — so the user immediately sees "this task did not
   change source code".
4. Existing tasks with `(tNN)` commits continue to anchor on those
   (no regression in date/hash for the common case).
5. Detail pane behavior for a no-code-commit task:
   - Task body and (if applicable) plan content still load
   - The commits / affected-files panel makes it clear there are no
     source-code commits (e.g. show the framework commits from
     `aitask-data` with a separator, or an explicit empty-state
     message)

## Out of scope

- Dropping or weakening the `(tNN)` commit-message requirement.
- Rewriting manual-verification's commit recipe to use `(tNN)`.
- Migrating existing archived tasks' commits.

## Implementation notes / file pointers

- `.aitask-scripts/codebrowser/history_data.py`
  - `_build_commit_map` (line 72) — extend to also collect
    archive-commits on `aitask-data` branch, keyed by task ID parsed
    from the `ait: Archive completed t<N>...` message (or from the
    affected file path `aitasks/archived/t<N>_*.md`).
  - `_merge_chunk` (line 100) — replace the `continue` with a fallback
    that stamps the row from the archive commit (or mtime) and flags
    `has_code_commits = False` (new field on `CompletedTask`).
- `CompletedTask` dataclass — add a `has_code_commits: bool` (or
  `source_kind: Literal["code","framework_only"]`) field so the UI can
  branch.
- `.aitask-scripts/codebrowser/history_list.py`
  - `_TaskRow.render` (around line 125) — adjust the row composition
    to show the new marker when `has_code_commits is False`.
- `.aitask-scripts/codebrowser/history_detail.py` — surface the
  framework commits / empty-state for the no-code case (verify
  filename / function during implementation).

## Investigation already done

- Verified t787 has zero commits matching `\(t787[)_]` on any branch.
- Verified all t787 commits are `ait:` framework commits on
  `aitask-data` branch.
- Verified t604 (also manual_verification) DOES have a `refactor: ...
  (t604)` commit on `main`, confirming the gating mechanism.
- Confirmed the documented manual-verification commit recipe uses
  `ait: Record verification state for t<id>` (no parens) — by design.
- User flagged that `brainstorm` tasks (no-code output, only new
  tasks spawned) are another instance of the same class — the fix
  must be type-agnostic, not manual-verification-specific.

---
priority: medium
effort: high
depends: []
issue_type: bug
status: Ready
labels: [git, task_workflow, bash_scripts]
anchor: 1560
created_at: 2026-08-24 22:56
updated_at: 2026-08-24 22:56
---

## Problem

`.claude/skills/aitask-web-merge/SKILL.md` carries the **same shared-repo-root
merge hazard** that t1560 fixed for the task workflow's Step 9 — and it is the
only merge path left in the tree that is unprotected. This was found by t1560_3's
audit of every merge path; `aitask-pickrem` and `aitask-pickweb` were audited and
are exempt (neither merges nor switches branches).

Three separate defects, all in the shared repository root:

1. **No mutex.** It merges `origin/<branch>` with `git merge --no-ff --no-commit`
   (`:69`), strips `.aitask-data-updated/`, commits (`:92`) and **pushes** the
   target (`:167`). It consults nothing. The `--no-commit` window is deliberate
   (`:238`) and is exactly the window that must sit inside a reservation. If a
   Step 9 `begin` fires during it, the broker's pre-flight reports
   `STALE_MERGE_RESIDUE` / `DIRTY_TREE` and refuses; conversely, running
   web-merge while a task worktree's merge is half-staged makes its
   `git rm -rf` + `git commit` absorb the other task's staged work.

2. **It never asserts HEAD.** There is not one `git checkout` token in the file —
   it assumes HEAD is on `main`. Step 9 deliberately leaves the shared root
   checked out on `$output_branch`, so a web-merge started after any Step 9 merge
   to a non-`main` output branch will `git pull --ff-only`, merge and `git push`
   **that** branch. The broker guards this with `PREFLIGHT_HEAD_MISMATCH`;
   web-merge has no equivalent.

3. **The unconditional `git push` at `:167`** propagates (2) to the remote.

## Why it was not fixed in t1560_3

The broker cannot be adopted as-is, and t1560_3's non-goals forbid changing it:

- `begin` runs a plain `git merge "$task_branch"`
  (`.aitask-scripts/aitask_merge_task.sh:207`) which **creates** the merge
  commit. web-merge needs the index left uncommitted so it can remove
  `.aitask-data-updated/` first. There is no `--no-commit` mode and no
  acquire-only verb.
- `begin`'s `task_branch` is a local `aitask/<name>` ref (cleanup compares
  against `"aitask/$task_name"`, `:295`); web-merge's source is a **remote**
  `origin/<branch>`.

## Scope

- Extend `aitask_merge_task.sh` with a surface that fits this caller — an
  acquire-only verb, or a `--no-commit` mode on `begin` that accepts a
  remote-ref source. Honour the existing contract: exit status disjoint from
  verdict, one verdict line on stdout, and the held-lock invariant (every path
  reporting the lock held ends in exactly one `finish` / `abort`).
- Wire `.claude/skills/aitask-web-merge/SKILL.md` to it, covering the whole
  critical section: merge, `git rm`, commit, and the pushes.
- Add the missing HEAD assertion before the merge.
- Re-check `tests/test_merge_broker_rendered_verdicts.sh` — any new verdict needs
  a rendered disposition row.

## Notes

- **No port follow-ups are needed.** Both ports
  (`.agents/skills/aitask-web-merge/SKILL.md`,
  `.opencode/skills/aitask-web-merge/SKILL.md`) are thin "Source of Truth"
  pointer wrappers carrying no merge code, so a fix to the Claude Code file
  propagates with no regeneration.
- **Do not change web-merge's frontmatter `description:`** — it is copied into
  the wrapper frontmatter and would trip the parity check in
  `aitask_audit_wrappers.sh`.
- `aitask-web-merge` is a **static** skill (no `SKILL.md.j2`, no rendered
  variants, no goldens), so body edits need no regeneration.
- When this lands, the boundary note in
  `website/content/docs/concepts/locks.md` ("Only the task workflow's
  end-of-task merge participates in this mutex") stops being true and must be
  updated in the same change.

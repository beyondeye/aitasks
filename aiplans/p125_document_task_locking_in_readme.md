---
Task: t125_document_task_locking_in_readme.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Task t125 asks to document the atomic task locking mechanism (`aitask_lock.sh`) in the README.md Development section. The locking system prevents race conditions when two PCs try to pick the same task simultaneously. It uses a separate git orphan branch `aitask-locks` — similar in concept to the already-documented `aitask-ids` atomic counter, but for locking tasks during implementation.

## Plan

Add a new subsection **"Atomic Task Locking"** in README.md immediately after the existing "Atomic Task ID Counter" section (after line 950), following the same documentation style.

### File to modify
- `README.md` (line ~951, after the Atomic Task ID Counter section)

### Content to add

A new `#### Atomic Task Locking` subsection covering:

1. **Purpose** — Prevents race conditions when two PCs pick the same task via `aitask-pick`
2. **Branch** — Uses a separate git orphan branch `aitask-locks` with per-task YAML lock files (`t<id>_lock.yaml`)
3. **Atomicity mechanism** — Same compare-and-swap approach as the ID counter (git plumbing + push rejection + retry with backoff, up to 5 attempts)
4. **Lock/unlock lifecycle** — Locked when a task is picked (Step 4 of aitask-pick), unlocked when archived (Step 9) or aborted
5. **Available commands** — `--init`, `--lock`, `--unlock`, `--check`, `--list`, `--cleanup` (internal, not exposed via `ait` dispatcher)
6. **Integration with `ait setup`** — Initializes the lock branch on the remote

### Style
- Match the existing "Atomic Task ID Counter" section format (bullet-point list, concise)
- Keep it ~10-12 lines total

## Verification

- Read the modified README.md to confirm formatting and accuracy
- Run `bash -n aiscripts/aitask_lock.sh` to confirm the script path reference is valid

## Final Implementation Notes
- **Actual work done:** Added a 12-line "Atomic Task Locking" subsection to README.md, placed immediately after the existing "Atomic Task ID Counter" section. Matched the same documentation style (intro paragraph + bullet list).
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Included the idempotency detail (same email can refresh lock, unlock on non-existent succeeds silently) as it's a notable design choice worth documenting.

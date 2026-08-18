---
Task: t1560_3_document_merge_mutex_and_audit_merge_paths.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Sibling Tasks: aitasks/t1560/t1560_1_*.md, aitasks/t1560/t1560_2_*.md
Archived Sibling Plans: aiplans/archived/p1560/p1560_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1560_3 — Document the merge mutex, audit the other merge paths

## Context

Sibling **t1560_1** ships the merge broker and its session-anchored mutex;
**t1560_2** wires it into Step 9. This task closes the parent's two remaining
surfaces: the published documentation, and the *other* merge paths in the tree.

Read `aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md` (design of
record) and `aiplans/archived/p1560/p1560_1_*.md` (what shipped). Per
`aidocs/framework/documentation_conventions.md`, document the **current source**,
not the plan's intent, and write current-state-only prose — no version history in
the body.

`depends: [1560_1]`. Independent of t1560_2; the two can run alongside each other.

## Implementation

### Step 1 — `website/content/docs/concepts/locks.md`

Its "What the lock actually excludes" table is currently accurate **only because
merging is unprotected**. Add:

- the **merge mutex** as a lock distinct from the task lock: what it excludes
  (any two tasks from the shared repo root, regardless of output branch) and why
  it is global per repo rather than per branch — two tasks merging into different
  branches still drive one HEAD, one index, one working tree;
- its **session-anchor lifetime**: the reservation survives between agent turns
  because it is anchored to the agent session rather than the short-lived script
  process, and it is deliberately held through verification and cleanup;
- the **anchor precondition** — a merge cannot begin without a resolvable session
  anchor, with both remedies named. This is a real user-visible constraint on
  worktree-mode merges, not an implementation detail; do not bury it;
- the **`force-release` recovery ladder**: it refuses a provably live holder, the
  two tree-residue states have two distinct remedies, and the ladder terminates.

Keep the existing "cannot tell is never rounded up to go ahead" framing — the
merge mutex applies the same rule.

### Step 2 — `website/content/docs/workflows/parallel-development.md`

Its merge-back description (around `:20`) carries **no serialization caveat at
all**. It must say that concurrent tasks reaching the merge are serialized, that
a queued agent is told which task it is waiting on, and that a conflict-parked
merge keeps the shared tree reserved until the human is done.

Also state the consequence recorded in the parent plan: under
`create_worktree: false` there is no task branch and the merge block does not
run, so shared-checkout mode is unaffected.

Use generic example project names, never real repository names. Omit
`diffviewer` from any list of TUIs.

### Step 3 — Audit the other merge paths

Check three skills for the same shared-root hazard and record the outcome —
**mutex or documented exemption** — either way:

- **`.claude/skills/aitask-web-merge/SKILL.md`** — the only merge path in the
  tree using `--no-ff --no-commit` (`:69`) that also **pushes the target**
  (`:167`). It mutates the same shared repo root as Step 9, so it either takes
  the same mutex or this task states precisely why not.
- **`.claude/skills/aitask-pickrem/SKILL.md`** and
  **`.claude/skills/aitask-pickweb/SKILL.md`** — check for the same inline
  checkout/merge pattern.

If any gains the mutex, the Claude Code version is the source of truth; suggest
separate aitasks to port it to the Codex (`.agents/skills/`) and OpenCode
(`.opencode/skills/`) trees rather than doing it here.

## Verification

- `cd website && hugo build --gc --minify` succeeds
- every added cross-reference resolves (`relref` builds clean)
- `grep` the two pages for the merge mutex, the anchor precondition and the
  `force-release` ladder — all three present
- the audit outcome for **each** of the three skills is recorded in the Final
  Implementation Notes, including any exemption and its reason
- if `aitask-web-merge` gains the mutex:
  `./.aitask-scripts/aitask_skill_verify.sh` exits 0, and the port follow-up
  tasks exist

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge per the shared workflow's Step 9.

## Non-goals

- No changes to the broker script (**t1560_1**) or to Step 9 (**t1560_2**).
- Do not document `aidocs/` internals in user-facing pages.

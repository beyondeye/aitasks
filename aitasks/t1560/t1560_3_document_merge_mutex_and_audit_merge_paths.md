---
priority: medium
effort: medium
depends: [t1560_1]
issue_type: documentation
status: Implementing
labels: [documentation, git, task_workflow]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1560
created_at: 2026-08-18 11:40
updated_at: 2026-08-24 22:29
---

## Context

Parent: **t1560**. Sibling **t1560_1** ships the merge broker
(`.aitask-scripts/aitask_merge_task.sh`) and its session-anchored mutex;
**t1560_2** wires it into Step 9. This task closes the parent's remaining two
surfaces: the published documentation, and the *other* merge paths in the tree.

Read **`aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md`** (the
design of record) and `aiplans/archived/p1560/p1560_1_*.md` (what actually
shipped) before writing prose — per
`aidocs/framework/documentation_conventions.md`, document the **current source**,
not the plan's intent, and write current-state-only prose with no version history
in the body.

`depends: [1560_1]` — the docs describe behaviour that must exist first. This
task does **not** depend on t1560_2 and can run alongside it.

## Scope

### 1. `website/content/docs/concepts/locks.md`

Its "What the lock actually excludes" table is currently accurate **only because
merging is unprotected**. It must gain:

- the **merge mutex** as a distinct lock from the task lock: what it excludes
  (any two tasks from the shared repo root, regardless of output branch), and
  why it is global per repo rather than per branch (two tasks merging into
  different branches still drive one HEAD, one index, one working tree);
- its **session-anchor lifetime** — the reservation survives between agent turns
  because it is anchored to the agent session, not the short-lived script
  process, and it is deliberately held through verification and cleanup;
- the **anchor precondition**: a merge cannot begin without a resolvable session
  anchor (`NO_SESSION_ANCHOR`), with both remedies named. This is a real new
  user-visible constraint on worktree-mode merges, not an implementation detail
   — do not bury it;
- the **`force-release` recovery ladder**, including that it refuses a provably
  live holder and that the two tree-residue states have two distinct remedies.
  State that the ladder terminates.

Keep the existing "cannot tell is never rounded up to go ahead" framing — the
merge mutex applies the same rule.

### 2. `website/content/docs/workflows/parallel-development.md`

Its merge-back description (around line 20) currently carries **no serialization
caveat at all**. It must say that concurrent tasks reaching the merge are
serialized, that a queued agent is told which task it is waiting on, and that a
conflict-parked merge keeps the shared tree reserved until the human is done.

Also state plainly the consequence recorded in the parent plan: under
`create_worktree: false` there is no task branch and the merge block does not run,
so shared-checkout mode is unaffected.

Use generic example project names, never real repository names.

### 3. Audit the other merge paths

Three skills must be checked for the same shared-root hazard, and the outcome —
**mutex or documented exemption** — recorded either way:

- **`.claude/skills/aitask-web-merge/SKILL.md`** — the only merge path in the
  tree that uses `--no-ff --no-commit` (`:69`) and **pushes the target**
  (`:167`). It mutates the same shared repo root as Step 9, so it either takes
  the same mutex or this task states precisely why not.
- **`.claude/skills/aitask-pickrem/SKILL.md`** and
  **`.claude/skills/aitask-pickweb/SKILL.md`** — check for the same inline
  checkout/merge pattern.

If any of these gains the mutex, the Claude Code version is the source of truth;
suggest separate aitasks to port the change to the Codex (`.agents/skills/`) and
OpenCode (`.opencode/skills/`) trees rather than doing it here.

## Key files

- `website/content/docs/concepts/locks.md`
- `website/content/docs/workflows/parallel-development.md`
- `.claude/skills/aitask-web-merge/SKILL.md`
- `.claude/skills/aitask-pickrem/SKILL.md`, `.claude/skills/aitask-pickweb/SKILL.md`
- `aidocs/framework/documentation_conventions.md` — read before writing prose

## Verification

- `cd website && hugo build --gc --minify` succeeds
- every cross-reference added resolves (`relref` builds clean)
- `grep` the two doc pages for the merge mutex, the anchor precondition and the
  `force-release` ladder — all three present
- the audit outcome for **each** of the three skills is recorded in the Final
  Implementation Notes, including any explicit exemption and its reason
- if `aitask-web-merge` gains the mutex:
  `./.aitask-scripts/aitask_skill_verify.sh` exits 0, and follow-up tasks for the
  Codex / OpenCode ports are created

## Non-goals

- No changes to the broker script (**t1560_1**) or to Step 9 (**t1560_2**).
- No `diffviewer` mention in user-facing website docs (it is transitional).
- Do not document `aidocs/` internals in user-facing pages.

---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [skills, tmp_cleanup]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-13 01:27
updated_at: 2026-11-13 01:30
---

## Problem

Generalize the prevention work from **aitasks_go task t126** into the aitasks framework so every installed project receives consistent guidance for temporary repository copies used during planning and verification.

In aitasks_go, agents exported/cloned repositories into session scratchpads and left them there after verification. The task records approximately 6.2GB and 520k inodes of leftovers on 2026-11-13. These copies were created by ad-hoc agent commands in plans rather than by the framework's normal task-worktree lifecycle. A project-local CLAUDE.md rule will not protect other repositories or other agents.

A read-only spot check during this discussion found that thinking_app and thinking_backend both use the framework's task-worktree helper and completion procedure. The helper already uses targeted teardown, refuses ambiguous/dirty worktrees, and explicitly forbids repository-wide pruning. As of that check, neither repository's worktree list reported stale registrations. This is evidence of a shared prevention gap for ad-hoc verification copies, not proof that all normal task worktrees leak. The same repositories' plans also contain ad-hoc git archive/worktree recipes outside the normal task-worktree path.

## Requested change

1. Add a shared convention to the canonical planning/verification instructions that generate these recipes. Audit the relevant creation paths and propagate the convention through the framework's installed/generated agent skills using its normal source-of-truth and rendering process. Avoid relying on an aitasks_go-only instruction or Claude-only auto-memory.
2. Require verification steps to copy only the paths needed. Prefer path-limited git archive when Git metadata is unnecessary. Where Git metadata is required, document an appropriate short-lived worktree or shared sparse clone, including configuring sparse checkout before materializing the checkout. A shared clone alone does not narrow the working tree.
3. Make each recipe identify its owned temporary paths and cleanup, on successful and failed checks. Record durable evidence before removal. Use type-appropriate cleanup: directories for archives/clones; targeted Git worktree teardown for linked worktrees, including registrations. Register cleanup early enough to cover partial setup failures. Do not recommend repository-wide git worktree prune as per-session cleanup.
4. Reuse a suitable copy of the same revision within a verification sequence when possible, then remove it when that sequence finishes. Preserve the distinction between temporary verification copies and framework-managed implementation worktrees: active/in-flight task worktrees, other sessions' work, and .aitask-data must retain their existing lifecycle and protections.
5. Validate representative final recipes for archive, metadata-bearing copy, and linked worktree on both pass and intentional failure. Confirm owned temporary directories and registrations are gone, unrelated worktrees are untouched, and the copied paths are sufficient for the actual check. Keep validation proportionate; do not deliberately damage the shared repository to demonstrate Git behavior.

## Acceptance criteria

- The shared instructions consistently prescribe narrow copies, durable evidence, and cleanup on both outcomes across the affected installed agent variants.
- A representative verification run follows the documented final recipe and leaves no owned temporary repository copy or worktree registration behind.
- Existing framework task-worktree cleanup, dirty-work preservation, and in-flight resume behavior remain intact.
- Guidance is portable: it does not bake this machine's tmpfs size, user paths, or Claude-specific scratch directory layout into general framework policy.

## Related work and scope

- aitasks_go t126: immediate project-local scratch-copy prevention; coordinate with its final convention rather than duplicating divergent rules.
- t2290: fixes actual leaks in framework tests/helpers and their per-run temporary directories. This task covers agent-generated planning/verification recipes.
- t2291: local, opt-in recovery of existing temporary leftovers. This task covers distributed prevention, not a cleanup sweep.

Do not remove existing leftovers, introduce a background sweeper, or change normal task-worktree retention as part of this task. No hard dependency on t2290/t2291 is required.

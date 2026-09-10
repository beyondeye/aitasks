---
priority: medium
effort: low
depends: [t1166_3, t1166_4]
issue_type: documentation
status: Ready
labels: [task_workflow, git-integration, child_tasks, documentation]
gates: [risk_evaluated]
anchor: 1166
created_at: 2026-07-20 12:07
updated_at: 2026-07-20 12:07
---

## Context

Fifth child of t1166 (shared family worktree). Documents the feature across the profile schema help and the website, and verifies the cross-agent render story. Depends on t1166_3 and t1166_4 (documents the behavior they land).

## Key Files to Modify

- `.claude/skills/task-workflow/profiles.md` — `create_worktree` schema-table row (~line 28) + worktree example (~113-124): note that a parent's `family_worktree: true` overrides `create_worktree: false` for its children (family mode), and that family worktrees always base on `main` (profile `base_branch` does not apply — documented v1 limitation).
- `.aitask-scripts/lib/profile_editor.py` — `create_worktree` help text (~129-137): same one-liner about the family override.
- `website/content/docs/workflows/parallel-development.md` (~line 20) — add a family-worktree section: opt-in at split time, shared `aiwork/t<parent>` on `aifamily/t<parent>`, per-child selective sync with main-side verification, final merge at family completion, hard serialization guard, v1 limitations (single-host, path-level, main-base).
- `website/content/docs/skills/aitask-pick/_index.md` (~30, 46) — mention family-mode child picks reuse the shared worktree.
- `website/content/docs/workflows/crash-recovery.md` — family worktree survey note.
- Check `website/content/docs/workflows/_index.md` — it is a HAND-CURATED page list; only needs a bullet if a NEW page is added (prefer extending existing pages; then no bullet needed).

## Cross-agent verification (not a port)

The task-workflow closure (incl. family-sync.md) auto-renders into the Codex (`.agents/skills/`) and OpenCode (`.opencode/skills/`) trees — no port tasks by default. In this task: verify the rendered closures contain the family additions after `aitask_skill_rerender.sh`, and confirm the `.codex/instructions.md` / `.opencode/instructions.md` frontmatter mirrors were hand-synced by t1166_2. Create separate port tasks ONLY if an agent-specific surface actually diverges (record the finding either way in the plan's Final Implementation Notes).

## Documentation conventions

Read `aidocs/framework/documentation_conventions.md` before writing website prose: current-state-only (no version history), genericize agent names where the passage is agent-generic. Website docs list only: board, monitor, minimonitor, codebrowser, settings, brainstorm (no diffviewer).

## Verification Steps

- `cd website && hugo build --gc --minify` (site builds clean)
- Grep rendered skill trees for `family-sync` / `aifamily` to confirm closure rendering
- Re-read `profiles.md` rendered copies match the authoring source after rerender.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_10** id=2026-09-10T18:36:21Z.2bc8f98c9005d35586c60aa2 from=t1705_10 at=2026-09-10T18:36:21Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting.
> | 
> | 1. The workflow you will document moved after t1166 was written (2026-07-20):
> |    t1536 moved the worktree fork from Step 5 to Step 7, after plan approval
> |    (bbafbd4f5; follow-up 7bae59b51); resource admission (68af4d67a) and the
> |    parallel-admission preflight (2384e4a64) now run before the fork; t1233 added
> |    output_branch (b9c44161b). t1166_3 still places family setup in Step 5 (a
> |    note went there too) — document what it actually ships, and the "always
> |    bases on main" limitation must also address output_branch (profiles.md ~31).
> | 
> | 2. Line refs: profiles.md create_worktree row ~29 is fine; the worktree example
> |    is ~166-185 (~113-124 is now gate prose). skills/aitask-pick/_index.md step 8
> |    (~32) now describes the fork.
> | 
> | 3. SHARED: t1705_10 adds one-line pointers to parallel-development.md and
> |    crash-recovery.md (different sections; likely to land first). t1687
> |    (Concepts gap sweep) may add a worktrees concept page and a relref inside
> |    § Git Worktrees for Isolation — link it rather than re-explain.

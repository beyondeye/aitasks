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

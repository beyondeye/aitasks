---
Task: t888_rerender_stale_task_workflow_remote_prerenders.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Rerender stale task-workflow-remote- prerenders (t888)

## Problem

The committed `task-workflow-remote-` prerenders are stale vs. their source
(`.claude/skills/task-workflow/`). A prior cross-repo task added two paragraphs
to source without rerendering the committed remote closures:

- `planning.md` §6.1 — **Cross-repo dispatch check** paragraph
- `SKILL.md` Step 7 — **Cross-repo child assignment** paragraph

`aitask_skill_verify.sh` enforces headless-prerender freshness only for
`aitask-pickrem` (`TODO(t777_29)` to generalize), so the drift went uncaught.

## Verified drift (pre-implementation)

- `grep "Cross-repo dispatch" .claude/skills/task-workflow/planning.md` → present (source).
- Same grep on committed `task-workflow-remote-/planning.md` → **absent** (drift confirmed).
- Same pattern for "Cross-repo child assignment" in `SKILL.md` (source present, committed remote absent).

## Fix

Run the rerender driver for the `remote` profile and commit the refreshed
closures across all 3 agent trees:

```bash
./.aitask-scripts/aitask_skill_rerender.sh remote
```

The renderer is skip-if-fresh, so only stale closures change. Result observed:

**6 modified files (the expected ones):**
- `.claude/skills/task-workflow-remote-/{planning.md,SKILL.md}`
- `.agents/skills/task-workflow-remote-codex-/{planning.md,SKILL.md}`
- `.opencode/skills/task-workflow-remote-/{planning.md,SKILL.md}`

**6 new closure-dependency files** (the cross-repo paragraphs reference these
procedures; the closure render copies them in, and they were never committed):
- `cross-repo-child-assignment.md` (×3 agent trees)
- `planning-cross-repo.md` (×3 agent trees)
- Verified `diff -q` against source: IDENTICAL.

Diff shape: planning.md +28 lines each, SKILL.md +2 lines each (84 insertions,
6 deletions total). All other 24 (skill,agent) `remote` pairs were already
fresh and unchanged.

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` → `OK (10 template(s) verified across 3 agents)`, exit 0.
2. Cross-repo paragraphs now present in committed remote closures (grep count 1 each).
3. New closure files byte-identical to source via `diff -q`.

## Scope note / follow-up

Suggested-fix #2 (generalize `aitask_skill_verify.sh`'s headless-prerender
freshness check beyond `aitask-pickrem` so this drift class fails loudly —
the existing `TODO(t777_29)`) is larger than this task and is tracked
separately. Surfaced via the upstream-defect follow-up at Step 8b.

## Post-Implementation

See task-workflow Step 9 for cleanup, archival, and merge. No branch/worktree
was created (profile 'fast', current branch).

## Final Implementation Notes

- **Actual work done:** Ran `./.aitask-scripts/aitask_skill_rerender.sh remote`.
  Skip-if-fresh meant only the stale `task-workflow-remote-` closures changed:
  6 modified files (planning.md +28, SKILL.md +2 across claude/codex/opencode)
  plus 6 new closure-dependency files (`cross-repo-child-assignment.md`,
  `planning-cross-repo.md` × 3 trees), byte-identical to source. All other 24
  `remote` (skill,agent) pairs were already fresh. Verifier returned
  `OK (10 template(s) verified across 3 agents)`, exit 0.
- **Deviations from plan:** None to the fix itself. The task's "6 affected
  committed files" undercounted: the restored cross-repo paragraphs reference
  two procedure files (`planning-cross-repo.md`, `cross-repo-child-assignment.md`)
  that were never committed into the remote closure, so the rerender correctly
  added 6 new files in addition to the 6 modified ones.
- **Issues encountered:** Mid-task, the SOURCE file
  `.claude/skills/task-workflow/profiles.md` was modified by a separate
  concurrent editor (added a `risk_evaluation` profile-key row, related to the
  recent t884 risk plumbing) — mtime 12:15, after the 12:12 rerender, and not
  present in the rendered output. Excluded it from this task's commit and
  staged only the 12 t888 closure files (concurrent-writer hygiene: stage
  specific paths, never `git add -A`).
- **Key decisions:** Staged the exact 12 closure paths explicitly rather than
  `git add .claude .agents .opencode` to avoid sweeping in the unrelated
  profiles.md edit.
- **Upstream defects identified:** `.aitask-scripts/aitask_skill_verify.sh:151 — headless-prerender freshness check is hardcoded to aitask-pickrem only (TODO t777_29); no check covers the committed task-workflow-remote- closure, so source-vs-committed-prerender drift like this goes unnoticed. Generalize the freshness check (read a prerender marker from j2 frontmatter + headless flag from profile YAML) so this drift class fails loudly.`


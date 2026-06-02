---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [agents_md]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-02 10:48
updated_at: 2026-06-02 11:37
---

## Origin

Spawned from t903 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_skill_rerender.sh:67-68` — invokes `aitask_skill_render.sh` without `--force`; the renderer's mtime-based skip-if-fresh treats git-committed prerenders that drifted via a source-only commit as fresh (mtimes equalize on `git checkout`/clone), so committed `*-remote-` prerenders silently stay stale and `rerender` reports `RERENDERED:N` with an empty diff. Recovering t903's stale renders required a manual `--force` on the headless entry points. Consider passing `--force` in the rerender driver, or making skip-if-fresh content-hash based rather than mtime based.

## Diagnostic context

During t903 (regenerate stale t884_5 planning renders + goldens), the plan's
step 1 was `./.aitask-scripts/aitask_skill_rerender.sh remote`. It reported
`RERENDERED:30 (skill,agent) pairs for profile 'remote'` but produced an empty
git diff — the 3 stale committed `task-workflow-remote-*/planning.md` renders
(missing the Step 6.0a block from t884_5) were NOT refreshed.

Two contributing causes:
1. `aitask_skill_rerender.sh` deliberately skips the `task-workflow` skill
   because it has no `SKILL.md.j2` authoring template (it is rendered only via
   other skills' closure walks) — so walking the `task-workflow-remote-` dir
   alone never refreshes it.
2. Even via the headless entry-point skills (`aitask-pickrem`,
   `aitask-pickweb`) whose closure walks DO write
   `task-workflow-remote-/planning.md`, the renderer's mtime-based
   skip-if-fresh considered the git-stale committed renders fresh and skipped
   the write.

Workaround used in t903: force-render the two headless entry points across the
three agents:
`./.aitask-scripts/aitask_skill_render.sh aitask-pickrem|aitask-pickweb --profile remote --agent claude|codex|opencode --force`

This means committed headless prerenders can silently drift whenever a source
closure file (`.claude/skills/task-workflow/*.md`) is edited and committed
without a same-commit re-render, and `aitask_skill_rerender.sh` will NOT detect
or repair the drift on a subsequent run. `aitask_skill_verify.sh` does catch
headless prerender freshness — but the auto-repair path is broken.

## Suggested fix

Either (a) have `aitask_skill_rerender.sh` pass `--force` to
`aitask_skill_render.sh` (simplest; re-renders unconditionally, accepting the
extra work), or (b) make the renderer's skip-if-fresh compare a content hash of
the resolved closure inputs rather than mtimes, so git-induced mtime
equalization no longer masks real source drift. Option (b) is more robust and
keeps skip-if-fresh's performance benefit. Verify against the t903 repro:
revert the 3 `task-workflow-remote-*/planning.md` to their pre-t903 (stale)
state, run the rerender driver, and confirm the Step 6.0a block is restored
without a manual `--force`.

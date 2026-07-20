---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, git-integration, child_tasks, skills]
gates: [risk_evaluated]
anchor: 1166
created_at: 2026-07-20 12:07
updated_at: 2026-07-20 12:07
---

## Context

Fourth child of t1166 (shared family worktree). Makes the failure/recovery surfaces family-aware: abort must never destroy the shared worktree, crash recovery must survey it, plan externalization must emit family headers, and — the durable backstop — `aitask_archive.sh` must surface "archived but family branch unmerged" as structured output that the workflow routes to recovery. Depends on t1166_1 (helper) and t1166_2 (field); coordinate with t1166_3 (shares SKILL.md-adjacent goldens — if picked concurrently, sequence after it).

## Key Files to Modify

- `.claude/skills/task-workflow/task-abort.md` (~41-47, verbatim/no Jinja)
- `.claude/skills/task-workflow/crash-recovery.md` (~29-35, verbatim)
- `.aitask-scripts/aitask_plan_externalize.sh` (~304-311)
- `.aitask-scripts/aitask_archive.sh` (new FAMILY_UNMERGED guard)
- `.claude/skills/task-workflow/SKILL.md` Step 9 archive-output parsing (adds one parsed line; small edit — t1166_3 owns the big Step 9 restructure)
- Tests: `tests/test_plan_externalize.sh` (family-header case), archive test (new or extended, e.g. alongside `tests/test_archive_carryover.sh` conventions), goldens for any templated file touched.

## Implementation Plan

**1. task-abort.md** — replace the unconditional worktree cleanup with: run `./.aitask-scripts/aitask_family_worktree.sh status <task_id>`; if `FAMILY_MODE:true` → do NOT remove worktree/branch (siblings depend on it); if `DIRTY:true` → AskUserQuestion: discard the aborted child's uncommitted changes in the shared worktree (`git -C aiwork/t<N> checkout -- . && git clean -fd`) vs leave them; inform that committed work stays on the family branch and resurfaces at the next sync evaluation / final merge. Non-family path unchanged.

**2. crash-recovery.md** — Step 1 survey: for child tasks also run `status`; if `FAMILY_MODE:true` and `EXISTS:true`, set `survey_dir` to `DIR` (family worktree takes precedence; the per-task `refs/heads/aitask/<task_name>` match cannot fire for `aifamily/` branches by construction). Survey stays read-only.

**3. aitask_plan_externalize.sh** — after the existing per-task `[[ -d "aiwork/${task_name}" ]]` check: if basename matches child pattern `t<p>_<n>_*` and `aiwork/t<p>` exists → emit `Worktree: aiwork/t<p>` and `Branch: aifamily/t<p>` (structural check, no frontmatter read).

**4. aitask_archive.sh FAMILY_UNMERGED durable guard** — abnormal archival paths (task-workflow Step 3 Check 1/2/4 backstops, `--ignore-gates`, board-driven archival) bypass Step 9's family logic; cover them at the shared sink: when archiving a task whose family branch `aifamily/t<N>` exists with commits unreachable from main, emit `FAMILY_UNMERGED:<branch>:<ahead>` (archival itself PROCEEDS — merge-independent semantics are pinned). Applies on both child archival (N = parent id) and parent auto-archival.

**5. Workflow routing** — where archive output is parsed (SKILL.md Step 9 "Parse the script output" list), handle `FAMILY_UNMERGED:` → route to family-sync.md's Recovery section: offer "run final merge now" or create an explicit recovery task via `aitask_create.sh --batch` (e.g. name `merge_family_branch_t<N>`, type chore) so the unmerged branch is a visible, pickable task.

## Verification Steps

- `bash tests/test_plan_externalize.sh` (family-header case: child file + `aiwork/t<p>` dir present → both lines; absent → neither)
- Archive test: fixture repo with an `aifamily/t<N>` branch carrying an unmerged commit → archive a child → `FAMILY_UNMERGED:` line present; merged/absent branch → line absent (negative control)
- `shellcheck .aitask-scripts/aitask_plan_externalize.sh .aitask-scripts/aitask_archive.sh`
- `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh` if any templated skill file changed (regenerate goldens + rerender in the same commit).

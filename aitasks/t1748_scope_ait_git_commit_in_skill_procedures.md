---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-09-08 22:15
updated_at: 2026-09-08 22:15
---

## Origin

Spawned from t1728 during Step 8b review.

t1728 converted the three unscoped `./ait git commit` **command** sites in
`.aitask-scripts/` to the path-scoped `ait_commit_paths_staging_untracked` seam
and extended `tests/test_no_unscoped_task_commit.sh` to cover that seam. That
guard scans `.aitask-scripts/**/*.sh` only. The identical defect exists at the
**instruction layer**, where agents follow it literally.

## Upstream defect

Skill procedures instruct the agent to run an index-wide `./ait git commit` on
the shared task-data branch. `./ait git` is `task_git` in a subprocess, so each
of these commits the ENTIRE index — whatever a concurrent session has staged at
that instant lands in a commit whose message names unrelated work.

- `.claude/skills/task-workflow/plan-externalization.md:134 — instructs the agent to run an unscoped "./ait git commit", the exact defect t1728 fixes, at the instruction layer`
- `.claude/skills/task-workflow/plan-approved-stop.md:69,127 — same unscoped ./ait git commit instruction`
- `.claude/skills/task-workflow/planning.md:305 — same, for the child-plans commit`
- `.claude/skills/task-workflow/risk-mitigation-followup.md:398 — same, for the mitigation witness commit`
- `.claude/skills/task-workflow/auto-verification.md:146 — same`
- `.claude/skills/aitask-contribute/SKILL.md:60,274 — same`
- `.claude/skills/aitask-add-model/SKILL.md:141 — same`
- `.claude/skills/aitask-web-merge/SKILL.md:123 — same`
- `.claude/skills/aitask-contribution-review/SKILL.md:294 — same`
- `.claude/skills/aitask-refresh-code-models/SKILL.md:146 — same`
- `.claude/skills/aitask-wrap/SKILL.md.j2:277 — same`
- `.claude/skills/ait-git/SKILL.md:15 — teaches the unscoped form as the canonical example, so it seeds the pattern`

Line numbers are from the **sources**; re-derive before starting. Rendered
per-profile variants under `.claude/skills/*-<profile>-/` carry copies, and the
Codex (`.agents/skills/`) and OpenCode (`.opencode/skills/`) trees carry their
own — the sweep must cover all of them, not just the Claude Code sources.

## Diagnostic context

This was found by grepping the skill trees while looking for other instances of
the seam t1728 was fixing. It is not hypothetical: while executing t1728 itself,
the agent reached `plan-externalization.md`'s "Commit the externalized plan"
block and would have run the unscoped form had it not just spent the session
studying why that is wrong. Every agent that runs `/aitask-pick` on a machine
with a concurrent session is exposed.

`.claude/skills/ait-git/SKILL.md:15` is the highest-leverage entry: it is the
skill whose entire purpose is teaching how to commit task/plan files, and its
worked example is unscoped.

## Suggested fix

Add `-- <path>` pathspecs to every instructed commit (the guard's own failure
hint offers this as a valid cure), or route them through
`./.aitask-scripts/aitask_task_commit.sh`, which already wraps the t1702 seam
with the trap armed — check whether that helper covers each call shape before
duplicating the pathspec form by hand.

Per CLAUDE.md: change the Claude Code sources first, run
`./.aitask-scripts/aitask_skill_verify.sh`, regenerate the affected goldens in
the same commit, and suggest separate aitasks for the Codex CLI and OpenCode
trees.

Consider whether `tests/test_no_unscoped_task_commit.sh` should grow a third
scan over the skill trees, and record the decision either way — a scanner over
markdown fenced blocks has different false-positive characteristics than the
shell scan, and the file's header documents its detection scope on purpose.

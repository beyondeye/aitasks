---
priority: high
effort: medium
depends: [t777_21, t777_22]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 11:59
updated_at: 2026-05-18 08:54
---

## Context

Re-scoped on 2026-05-18 after the t777_6 verify-pass. The original
scope (a manual classification + bespoke render-path rewriting) is
obsoleted by **uniform recursive rendering** in t777_22: the
dep-walker handles cross-skill references uniformly, and every
referenced `.md` is rendered through minijinja regardless of whether
it contains profile keys (identity transform when there are none).

What this task now owns: **edit the specific profile-check sites in
`.claude/skills/task-workflow/*.md` enumerated by t777_21's audit**,
wrapping each in a `{% if profile.<key> %}…{% else %}…{% endif %}`
block. No file renames (`.md` stays `.md`). No render-path rewriting
in templates (the dep-walker does it at render time).

## Depends on

- **t777_21** — provides the audit table listing exact files +
  line numbers + profile keys consumed. This task's edit scope is
  exactly that list, no broader.
- **t777_22** — provides the dep-walker that turns these edits into
  per-profile rendered output. Required for tests + verification.

## Probable file list (validate against t777_21's audit)

Likely needing `{% if profile.<key> %}` wrapping (verify keys at
impl time):

- `task-workflow/SKILL.md` — Steps 3/3b/4/5/6 profile branches
  (consumed: `default_email`, `create_worktree`, `base_branch`).
- `task-workflow/planning.md` — Step 6.0/6.1/Checkpoint branches
  (consumed: `plan_preference`, `plan_preference_child`,
  `plan_verification_required`, `plan_verification_stale_after_hours`,
  `post_plan_action`, `post_plan_action_for_child`).
- `task-workflow/satisfaction-feedback.md` —
  `enableFeedbackQuestions`.
- `task-workflow/manual-verification.md` and
  `task-workflow/manual-verification-followup.md` —
  `manual_verification_followup_mode`.
- `task-workflow/remote-drift-check.md` — `base_branch`.
- Plain `.md` procedures with no profile branches
  (`agent-attribution.md`, `lock-release.md`, `task-abort.md`,
  `issue-update.md`, `pr-close-decline.md`, etc.) stay completely
  unchanged. The dep-walker renders them as identity transforms.

## Implementation Plan

1. **Confirm scope** against the t777_21 audit (must already exist).
2. For each file with profile-check sites, wrap each site in
   `{% if profile.<key> %}<true-branch text>{% else %}<existing
   interactive block>{% endif %}`. True-branch text is straight-line
   "do X" instructions, no LLM decision wording.
3. **No frontmatter changes.** No file renames. No `.md.j2` extension.
4. **Cross-skill references stay literal** (`.claude/skills/...`) in
   source — the dep-walker (t777_22) rewrites per-(profile, agent) at
   render time.
5. Add golden-file regression tests for each modified file under
   `tests/golden/procs/task-workflow/<name>-<profile>-<agent>.md`
   (or whatever convention t777_22 establishes). Render fresh per
   (profile × agent), diff against golden, assert empty diff.

## Verification

1. `./ait skill verify` exits 0 — dep-walker validates the rendered
   `task-workflow-<profile>-/` snapshots for all 4 agents × 3
   profiles.
2. `bash tests/test_skill_render_task_workflow.sh` (or per-file
   variants) passes.
3. Manual smoke: render `aitask-pick --profile fast --agent claude`
   and inspect the produced
   `.claude/skills/task-workflow-fast-/planning.md` — the
   `post_plan_action` block should render as the auto-action
   straight-line text, not as an interactive AskUserQuestion block.

## Notes for sibling tasks

- t777_6 (PILOT) consumes the rendered output produced by this task.
- t777_8..t777_15 (per-skill conversions) gain `depends: [t777_22,
  t777_7]` so they sequence after this. That metadata edit is owned
  by t777_22's plan, not this task.
- Best practice surfaced during t777_6 planning: skills decompose
  into many referenced procedures (CLAUDE.md "Extract new procedures
  to their own file"). The uniform render model is what makes that
  decomposition compatible with profile templating.

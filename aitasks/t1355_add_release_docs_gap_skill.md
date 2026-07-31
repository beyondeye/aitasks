---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_changelog, claudeskills, web_site, docs]
gates: [risk_evaluated]
created_at: 2026-07-31 07:54
updated_at: 2026-07-31 07:54
---

## Goal

Add a new skill (working name: `aitask-docs-gap`) complementary to
`aitask-changelog`: it analyzes all tasks landed since the last release and
determines which shipped changes are missing documentation on the framework
website (`website/content/docs/`), then creates **one single** `documentation`
task capturing all the gaps. That task can later be split into sibling child
tasks at `aitask-pick` time via the normal task-workflow decomposition — the
skill itself never creates children.

Model skills: `aitask-changelog` (release-scope gathering, static skill shape)
and `aitask-explore` (exploration → single-task creation ending).

## Mechanics (from exploration)

1. **Release scope — reuse the existing gather step unchanged.**
   `./.aitask-scripts/aitask_changelog.sh --gather` already emits `BASE_TAG:`
   (last `v*` tag) and one `=== TASK tNN ===` section per landed task with
   `ISSUE_TYPE:` / `TITLE:` / `PLAN_FILE:` (archived plan) / `COMMITS:` /
   `NOTES:`. Include the same Step-0 remote-sync preflight as aitask-changelog
   (fetch + behind-check) so remote-only tasks are not silently missed.
2. **Changed-file surface per task.** `--gather` does not include file lists;
   derive them with `git show --name-only --format=` over each task's commits
   (same pattern as `aitask-gate-docs-updated` Step 2). Ignore task/plan data
   paths (`aitasks/`, `aiplans/`, `.aitask-data/`).
3. **Docs-relevance method — reuse the configured doc-update spec.** Resolve it
   via `./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide
   aitasks/metadata/doc_update_guide.md` (same seam as the `docs_updated`
   gate). The guide holds the change-kind→doc-area map (TUI → `docs/tuis/`,
   skill → `docs/skills/`, `ait` subcommand → `docs/commands/`, workflow →
   `docs/workflows/`, concept → `docs/concepts/`), the writing conventions, and
   pass/skip-style relevance semantics. The skill is **analysis-only**: unlike
   the gate verifier it never edits docs — it classifies each landed task as
   documented / gap / not doc-relevant by checking the mapped website pages.
4. **Filtering.** Skip tasks whose `ISSUE_TYPE` is inherently non-doc-relevant
   per the guide (e.g. `test`, pure internal `chore`/`refactor`), and skip
   tasks whose doc area was already updated in the same release window (the
   task's own commits or another task's commits touched the mapped page).
5. **Ending — one task.** Present the per-gap findings for user confirmation
   (AskUserQuestion; findings summary must be carried inside the question text
   per the t1150 visibility rule), then create a single task via
   `aitask_create.sh --batch --commit` with `issue_type: documentation`, whose
   description contains **one clearly delimited section per doc gap**
   (`## Gap: <feature> (tNN)` — target doc page(s), what shipped, what to
   write, source plan/commits pointers) so that pick-time decomposition can
   split it cleanly into siblings if desired.

## Acceptance criteria

- New static skill under `.claude/skills/` (no profile variants — same shape
  as `aitask-changelog`; not a stub + `.md.j2` pair). Follow
  `aidocs/framework/skill_authoring_conventions.md`; run
  `./.aitask-scripts/aitask_skill_verify.sh` if any guarded surface is touched.
- Reuses `aitask_changelog.sh --gather` for release scope (no parallel
  gathering logic); reuses the resolved `doc_update.guide` spec for the
  change-kind→doc-area map (no hardcoded map in the skill).
- Handles the no-tasks case (`COMMITS_ONLY:`) and the no-gaps case (report
  "docs are complete for this release", create nothing) gracefully.
- Creates exactly one `documentation` task with per-gap sections; never
  creates child tasks itself.
- Website docs page for the new skill added under
  `website/content/docs/skills/` (and any workflow page bullet added by hand
  to the relevant `_index.md` body list if a workflows page is added — known
  hand-curated-list footgun).
- Suggest (as separate follow-up tasks, per CLAUDE.md) porting the skill to
  Codex CLI and OpenCode after the Claude Code version lands.

## Non-goals

- Editing website docs directly (that is the created task's job, or the
  `docs_updated` gate's job going forward).
- Replacing or modifying the `docs_updated` gate / `aitask-gate-docs-updated`
  verifier — this skill is the retroactive batch complement for releases where
  the gate was not active per-task.

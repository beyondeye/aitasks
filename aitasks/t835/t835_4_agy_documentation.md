---
priority: medium
effort: high
depends: [t835_3]
issue_type: documentation
status: Ready
labels: [codeagent]
created_at: 2026-05-28 12:18
updated_at: 2026-05-28 12:18
---

## Context

Inverse counterpart of t812_4. Adds `Antigravity CLI (agy)` to every
user-facing documentation surface: top-level prose, website docs,
internal `aidocs/` reference tables, and skill-closure source files.
Then regenerates affected goldens in the same commit per CLAUDE.md.

Applies CLAUDE.md's existing genericization rule: leave "Claude Code
and all other supported coding agents" prose intact; only insert
explicit `agy` rows where the enumeration is normative.

Primary inverse reference: `aiplans/archived/p812/p812_4_remove_geminicli_documentation.md`
→ `### For t814 (add-agy): inverse instructions`.

## Key Files to Modify

*Top-level prose:*
- `README.md`, `CLAUDE.md` (agent-list prose only — keep
  genericization where used).
- `CHANGELOG.md` — new entry under next pending release.

*Skill closure sources:*
- `.claude/skills/task-workflow/model-self-detection.md`
- `.claude/skills/task-workflow/satisfaction-feedback.md`
- `.claude/skills/task-workflow/plan-externalization.md`
- `.claude/skills/aitask-add-model/SKILL.md` (or `.md.j2`)
- `.claude/skills/aitask-refresh-code-models/SKILL.md`
- `.claude/skills/aitask-audit-wrappers/SKILL.md`

*Website docs — normative (add agy row):*
- `website/content/docs/commands/codeagent.md`
- `website/content/docs/installation/known-issues.md` (NEW
  `## Antigravity CLI` H2)
- `website/content/docs/installation/updating-model-lists.md`
- `website/content/docs/installation/windows-wsl.md`
- `website/content/docs/skills/aitask-add-model.md`
- `website/content/docs/development/skills/aitask-audit-wrappers.md`
  (use IDs from t835_2; do NOT reuse vacant gemini IDs 2/5)
- `website/content/docs/tuis/settings/{_index,how-to,reference}.md`

*Website docs — genericized (leave intact unless agy carries
editorial weight):* `_index.md`, `about/_index.md`,
`docs/overview.md`, `docs/getting-started.md`,
`docs/skills/_index.md`, `docs/installation/_index.md`,
`docs/concepts/agent-attribution.md`,
`docs/concepts/verified-scores.md`,
`docs/skills/aitask-pick/commit-attribution.md`,
`docs/skills/aitask-refresh-code-models.md`,
`docs/tuis/board/how-to.md`.

*aidocs:*
- `aitasks_extension_points.md` — touchpoint table (IDs from t835_2).
- `model_reference_locations.md` — model registry + supported-agents
  tables (agy as `yes (limited)`).
- `issue_type_vocabulary_duplication.md` — add
  `seed/agy_instructions.seed.md` line.
- `stub-skill-pattern.md` — §3g row; bump per-skill stub count
  from 3 to 4.

## Reference Files for Patterns

- Codex's row at each table/list.
- `aidocs/adding_a_new_codeagent.md` § 23 — user-facing docs
  playbook.

## Implementation Plan

1. Edit top-level prose (README.md, CLAUDE.md). Apply
   genericization rule.
2. Add CHANGELOG entry.
3. Edit skill-closure sources to add agy to enumerations / detection
   branches.
4. Edit normative website pages (add agy rows). Add new
   `## Antigravity CLI` H2 to `known-issues.md`.
5. Update aidocs reference tables.
6. Run `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for
   each of default/fast/remote.
7. Regenerate `tests/golden/procs/task-workflow/satisfaction-feedback-*.md`
   and any other affected goldens. Commit goldens with the source
   changes in the same commit.
8. (Optional) Add a blog post under `website/content/blog/`
   announcing agy support — deferable if pressed for time.

## Verification Steps

- `cd website && ./serve.sh` and visually inspect each edited page.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/test_*goldens*.sh` passes (or equivalent
  golden-diff test suite).
- `grep -r "Codex CLI\|Antigravity CLI\|agy" website/content/docs/`
  shows agy consistently alongside codex where normative.

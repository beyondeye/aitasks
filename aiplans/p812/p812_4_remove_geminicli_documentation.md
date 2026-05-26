---
Task: t812_4_remove_geminicli_documentation.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_1_*.md, aitasks/t812/t812_2_*.md, aitasks/t812/t812_3_*.md, aitasks/t812/t812_5_*.md
Archived Sibling Plans: aiplans/archived/p812/p812_1_*.md, p812_2_*.md, p812_3_*.md (after archived)
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified: []
---

# Plan: Remove geminicli from documentation (t812_4)

## Context

Fourth child of t812. Removes geminicli mentions from **current-state
user-facing documentation**. Dated/historical content (CHANGELOG entries
prior to this change, the v0.9.0 "Gemini CLI first-class" blog post) is
preserved per the parent plan; a new CHANGELOG entry records the
removal.

## Files to modify

### Top-level
- `README.md` (line 20) — remove "Gemini CLI" from supported-agent list.
- `CLAUDE.md` (lines 202, 222–223) — remove `.gemini/` from "Working on
  Skills" section.

### `website/content/docs/` (14 files)
- `installation/_index.md`
- `installation/known-issues.md`
- `installation/updating-model-lists.md`
- `installation/windows-wsl.md`
- `commands/codeagent.md`
- `concepts/agent-attribution.md`
- `concepts/verified-scores.md`
- `skills/aitask-pick/commit-attribution.md`
- `skills/aitask-add-model.md`
- `skills/aitask-refresh-code-models.md`
- `development/skills/aitask-audit-wrappers.md`
- `tuis/settings/_index.md`
- `tuis/settings/how-to.md`
- `tuis/settings/reference.md`

Per CLAUDE.md docs-writing rules: remove current-state mentions, do NOT
add "previously…" prose.

### Skill source files / templates

- `.claude/skills/task-workflow*/model-self-detection.md`
- `.claude/skills/task-workflow*/satisfaction-feedback.md`
- `.claude/skills/aitask-add-model/SKILL.md`
- `.claude/skills/aitask-refresh-code-models/SKILL.md`
- Any other `.md` or `.md.j2` files under `.claude/skills/` that
  enumerate supported agents (grep for `geminicli`).

After editing `.md.j2` source files, regenerate goldens via
`./.aitask-scripts/aitask_skill_rerender.sh` (or equivalent) and
commit the regenerated outputs.

## Files to append to

- `CHANGELOG.md` — new entry under the next pending release:
  ```
  - Removed geminicli (Gemini CLI) support. Google is sunsetting
    Gemini CLI in favor of Antigravity CLI (agy); see t813 and t814
    for the agy migration path.
  ```

## Historical content to RETAIN

- `CHANGELOG.md` lines 83, 158, 890, 998 — do NOT rewrite.
- `website/content/blog/v090-gemini-cli-and-opencode-are-first-class-citizens-model-discovery-and-status.md`
  — keep intact.

## Step-by-step

1. For each file in the lists above, grep for `gemini`, `geminicli`,
   `gemini-cli`. Remove mentions describing **current behavior**;
   preserve dated/historical mentions.
2. For `.md.j2` source files: edit source, then regenerate
   goldens.
3. Build the Hugo site to confirm no broken cross-references:
   ```bash
   cd website && hugo build --gc --minify
   ```
4. Add the CHANGELOG entry.
5. Final grep check:
   ```bash
   grep -rn 'geminicli\|gemini-cli' --include='*.md' .
   # Acceptable matches:
   #  - aitasks/archived/, aiplans/archived/
   #  - aitasks/t812*, t813*, t814*
   #  - CHANGELOG.md historical entries (pre-this-change)
   #  - v090 blog post
   #  - aidocs/geminicli_to_agy.md (retained for t814)
   ```

## Verification

1. `cd website && hugo build --gc --minify` — succeeds, no broken
   cross-references.
2. `./.aitask-scripts/aitask_skill_verify.sh` — passes for all
   remaining agents (post regen).
3. Grep check above returns only acceptable matches.

## Step 9 (Post-Implementation)

Standard archival. Final Implementation Notes **must** include the
`### For t814 (add-agy): inverse instructions` subsection.

## Final Implementation Notes (template)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Upstream defects identified:** None (or list)
- **Notes for sibling tasks:** …

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy:** (file list, including `.md.j2`
  sources).
- **Pattern removed:** geminicli mentions in agent-list prose and
  templated agent enumerations.
- **Inverse instruction:** to add agy, add `Antigravity CLI (agy)`
  to each agent-list mention, modeled on codex's position. Re-run
  `aitask_skill_rerender.sh` after `.j2` edits. Add a new
  CHANGELOG entry for the agy addition.
- **Hidden coupling discovered during removal:** cross-references
  between docs files, golden-regen triggers, etc.

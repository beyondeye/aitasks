---
priority: medium
effort: medium
depends: [t812_3]
issue_type: documentation
status: Done
labels: [geminicli, docs]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 12:07
updated_at: 2026-05-28 03:28
completed_at: 2026-05-28 03:28
---

## Context

Fourth child of t812 (remove all geminicli support). This child removes
geminicli mentions from **current-state user-facing documentation** —
README, CLAUDE.md, website pages, and skill files that list supported
agents. Dated/historical content (CHANGELOG entries, v0.9.0 blog post)
is preserved per the parent plan; a new CHANGELOG entry records the
removal.

Does NOT touch code paths (t812_1, t812_2, t812_3) or pending gemini
aitasks (t812_5).

## Key files to modify (current-state prose — remove geminicli mentions)

- `README.md` (line 20) — remove "Gemini CLI" from the supported-agent
  list.
- `CLAUDE.md` (lines 202, 222–223) — remove the `.gemini/`
  agent-directory entry from the "Working on Skills" section.

- `website/content/docs/` (14 files — remove geminicli mentions;
  per CLAUDE.md, no "previously…" prose):
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

- `.claude/skills/task-workflow*/model-self-detection.md`,
  `satisfaction-feedback.md`, `aitask-add-model/SKILL.md`,
  `aitask-refresh-code-models/SKILL.md`, and any other SKILL.md
  files that mention `geminicli` in agent-name enumerations — remove
  the geminicli mentions and regenerate per-profile rendered
  variants via
  `./.aitask-scripts/aitask_skill_rerender.sh` (or equivalent).
  Apply the same removal to `.j2` source files and regenerate
  goldens.

## Files to add / append

- `CHANGELOG.md` — add a new entry under the next pending release:
  "Removed geminicli (Gemini CLI) support. Google is sunsetting
  Gemini CLI in favor of Antigravity CLI (agy); see t813 and t814
  for the migration path."
- Optional: a new short blog post in `website/content/blog/` titled
  "Sunset: Gemini CLI support removed, agy migration in progress",
  pointing to t813 and t814. Judgement call during impl — only add
  if the blog cadence supports it.

## Historical content to RETAIN as-is

- `CHANGELOG.md` existing entries that mention gemini (lines 83,
  158, 890, 998) — do NOT rewrite. They are dated facts.
- `website/content/blog/v090-gemini-cli-and-opencode-are-first-class-citizens-model-discovery-and-status.md`
  — keep intact.

## Implementation plan

1. For each file in the list, grep for `gemini`, `geminicli`,
   `gemini-cli` and remove only the mentions that describe
   **current behavior**. Leave dated/historical mentions intact.
2. For `.j2` source files: edit the source, then regenerate goldens
   via `./.aitask-scripts/aitask_skill_rerender.sh` and commit the
   regenerated outputs.
3. For website MD files: confirm hugo builds cleanly afterwards.
4. Add the CHANGELOG entry.

## Verification

1. `cd website && hugo build --gc --minify` — succeeds with no
   broken cross-references.
2. `grep -rn 'geminicli\|gemini-cli' --include='*.md' .` returns
   ONLY:
   - Archived tasks/plans under `aitasks/archived/` /
     `aiplans/archived/`.
   - Active sibling task files (`t812*`, `t813*`, `t814*`).
   - `CHANGELOG.md` historical entries (lines that pre-date this
     change).
   - The v0.9.0 blog post.
   - `aidocs/geminicli_to_agy.md` (retained for t814).
3. `./.aitask-scripts/aitask_skill_verify.sh` passes for all
   remaining agents after the skill regenerations.

## Final implementation notes — REQUIRED subsection

Include a top-level subsection titled exactly:

```
### For t814 (add-agy): inverse instructions
```

Contents:
- **Files re-touched by agy:** the same file list, plus any
  `.j2` source files modified.
- **Pattern removed:** geminicli mentions in agent enumerations and
  configuration prose.
- **Inverse instruction:** "to add agy: add `agy` (or `Antigravity
  CLI (agy)`) to each agent-list mention, modeled on codex's
  position in the same list. Re-run
  `aitask_skill_rerender.sh` after `.j2` edits."
- **Hidden coupling discovered during removal:** any
  cross-references between docs files, golden-regen triggers, etc.

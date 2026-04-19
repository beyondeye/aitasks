---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: []
created_at: 2026-04-19 17:12
updated_at: 2026-04-19 17:12
---

Child of t594. Sweep the 27 pages across three smaller sections: Concepts (14), Commands (10), Development (3). Depends on t594_2 for canonical wording.

## Context

Parent plan: `aiplans/p594_website_documentation_coherence.md`. These three sections share the same pattern — reference material for the framework internals — and drift in the same way (missing flags, missing fields, stale schemas). Bundled into one child because per-page changes are small.

## Key Files to Modify

**Development (highest priority — authoritative schema pages):**
- `website/content/docs/development/task-format.md` — add missing `verifies` frontmatter field and any other fields added since the last edit.
- `website/content/docs/development/review-guide-format.md` — verify against actual files in `aireviewguides/`.

**Commands:**
- `website/content/docs/commands/task-management.md` — add missing flags for `ait update` and `ait create`.
- `website/content/docs/commands/codeagent.md` — tighten the 4x-repeated "agent string" definition; verify default model claims.
- All other command pages — spot-check flag lists against their scripts.

**Concepts:**
- `website/content/docs/concepts/tasks.md` — align schema sentences with `development/task-format.md`; add explicit "see task-format.md for the full schema" note.
- `website/content/docs/concepts/locks.md` — verify against `.aitask-scripts/aitask_lock.sh`, `aitask_lock_diag.sh`.
- `website/content/docs/concepts/agent-attribution.md` — verify against `.claude/skills/task-workflow/agent-attribution.md`.
- All 14 concept pages — diff against the relevant scripts / SKILL.md references.

## Reference Files for Patterns (Authoritative Sources)

- `.aitask-scripts/aitask_create.sh` — source of `--verifies` and all other create flags.
- `.aitask-scripts/aitask_update.sh:52-82` — source of missing update flags (`--verifies`, `--file-ref`, `--pull-request`, `--contributor*`, `--folded*`, `--implemented-with`, `--boardcol`, `--boardidx`).
- `.aitask-scripts/aitask_codeagent.sh:27`, `aitasks/metadata/codeagent_config.json` — default-model truth.
- `CLAUDE.md` §"Task File Format" — authoritative frontmatter field list (may need updating itself).
- `aireviewguides/` directory — truth for review guide format.

## Implementation Plan

1. **`development/task-format.md`:** add `verifies` field to the frontmatter schema table. Cross-check all 13+ existing fields against `CLAUDE.md` and the create/update scripts. Ensure this page is positioned as THE schema authority.
2. **`commands/task-management.md`:** add the missing `ait update` flags: `--verifies`, `--add-verifies`, `--remove-verifies`, `--file-ref`, `--remove-file-ref`, `--pull-request`, `--contributor`, `--contributor-email`, `--folded-tasks`, `--folded-into`, `--implemented-with`, `--boardcol`, `--boardidx`. Add `--verifies` to `ait create` documentation.
3. **`commands/codeagent.md`:** extract "agent string" definition into a single upfront section; replace 3 subsequent re-introductions with references to it. Verify "pick: claudecode/opus4_7_1m" against current config files.
4. **`concepts/tasks.md` vs `development/task-format.md`:** add explicit cross-link; align overview sentences; state the division of labor (concepts = what/why, development = full schema).
5. **Concept page verification pass:** for each of the 14 concept pages, identify the corresponding source (script, SKILL.md, procedure file), diff claims vs source, fix drift.
6. **"Next:" footers within each section** (concepts, commands, development internal reading order).

## Verification Steps

- `grep -E "^\s*--[a-z]" website/content/docs/commands/task-management.md` lists every flag that `.aitask-scripts/aitask_update.sh` accepts (via `grep -E "^\s*--" .aitask-scripts/aitask_update.sh` for comparison).
- `grep -i "verifies" website/content/docs/development/task-format.md` — hit found.
- `grep -c "agent string" website/content/docs/commands/codeagent.md` — reduced from 4+ to 1-2.
- `cd website && hugo build --gc --minify` succeeds.

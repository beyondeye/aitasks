---
Task: t594_6_concepts_commands_development_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,3,4,5,7}_*.md
Archived Sibling Plans: aiplans/archived/p594/p594_{1,2,3,4,5}_*.md
Depends on: t594_2 (canonical wording — archived)
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-21 08:24
---

# t594_6 — Concepts + Commands + Development coherence sweep

## Context

Parent plan `p594_website_documentation_coherence.md` covers the website doc
sweep. This child covers three reference-oriented sections: **Concepts (14
pages), Commands (10 pages), Development (3 pages)** — 27 pages total.

This plan has been **verified (2026-04-20)** against current source scripts
and website content. Several items from the original plan were already fixed
by siblings t594_2 and t594_5 and have been **removed**. New drift found
during verification was **added**.

Page counts confirmed: 14 / 10 / 3.

## Scope

**In-bounds:**
- Add missing `verifies` frontmatter field to `development/task-format.md`.
- Add missing `ait update` flags and `ait create --verifies` to `commands/task-management.md`.
- Replace stale model examples in `concepts/agent-attribution.md` with current ones.
- Add "Next:" footer links within each of the three sections.

**Out-of-bounds:**
- Reorganizing section structure or page weights.
- Splitting or merging pages.
- Content already handled by siblings t594_2 (canonical wording), t594_4 (skills), t594_5 (workflows).
- The `docsy labels` support is in sibling t594_7 — skip anything labels-related.

## Verified drift

### A. `website/content/docs/development/task-format.md` — missing `verifies` field

Frontmatter table at lines 31–49 lists 17 fields. Missing: `verifies`.

- Source: `.aitask-scripts/aitask_create.sh` (`--verifies` / `--add-verifies` / `--remove-verifies`); `.aitask-scripts/aitask_update.sh:205-207` (`--verifies`, `--add-verifies`, `--remove-verifies`).
- Add one row after `file_references` (line 49):
  ```
  | `verifies` | `[t10_1, t10_2]` | Task IDs this task verifies (used by manual_verification sibling tasks) |
  ```

No other frontmatter fields are missing — `verifies` is the only gap.

### B. `website/content/docs/commands/task-management.md` — missing `ait update` flags

The `ait update` section documents many flags, but **these are missing** (source `.aitask-scripts/aitask_update.sh:196-228`):

- `--file-ref`, `--remove-file-ref` (script lines 211-212)
- `--pull-request` (script line 223)
- `--contributor`, `--contributor-email` (script lines 224-225)
- `--folded-tasks`, `--folded-into` (script lines 226-227)

**Already documented** (no action): `--verifies`, `--add-verifies`, `--remove-verifies`, `--boardcol`, `--boardidx`, `--implemented-with` — these are in the page at lines 152-174. (The original plan overstated the gap; 6 of 13 listed flags are already present.)

### C. `website/content/docs/commands/task-management.md` — missing `ait create --verifies`

`ait create` flag table at lines 49-69 does not mention `--verifies`.

- Source: `.aitask-scripts/aitask_create.sh` accepts `--verifies "<csv>"`.
- Add one row to the `ait create` flag table for `--verifies`.

### D. `website/content/docs/concepts/agent-attribution.md` — stale model examples

Line 12 cites these agent/model examples:
- `claudecode/opus4_7_1m` ✓ (matches `aitasks/metadata/codeagent_config.json`)
- `geminicli/gemini-2.5-pro` ✗ (no such `name` in `aitasks/metadata/models_geminicli.json` — current names are `gemini3_1pro`, `gemini3pro`, `gemini3flash`)
- `codex/gpt-5` ✗ (no such `name` in `aitasks/metadata/models_codex.json` — current names are `gpt5_4`, `gpt5_3codex`, `gpt5_3codex_spark`)

Replace with `name`-field values that actually exist in the JSON configs — e.g., `geminicli/gemini3pro`, `codex/gpt5_4`.

### E. "Next:" footers within the three sections

Add a bottom-of-page cross-link to the next page in the section's intended reading order. Minimal, one-line footers only — not multi-item "See also" blocks.

- **Concepts** — follow the existing `weight:` ordering. 14 pages; each gets a "Next: [title]" pointing to the next-weight page.
- **Commands** — 10 pages; same pattern.
- **Development** — 3 pages; same pattern.

## Already-aligned items (no action needed — removed from scope)

Originally in the plan but **verified clean**:

- **`commands/codeagent.md`** "agent string" repetition — already defined once upfront (lines 23-32); remaining occurrences are references, not re-definitions. Default model claim `claudecode/opus4_7_1m` matches `.aitask-scripts/aitask_codeagent.sh:21` and `codeagent_config.json`.
- **`concepts/tasks.md`** cross-link to `development/task-format.md` — already present at line 18.
- **`development/review-guide-format.md`** — structure matches `aireviewguides/*.md` sample files (frontmatter `name`, `description`, `reviewtype`, `reviewlabels`; `## Review Instructions` heading).
- **`concepts/execution-profiles.md`** — correctly lists 3 shipped profiles (`default`, `fast`, `remote`) which matches `aitasks/metadata/profiles/`. Brevity of the key list is by design (page explicitly defers to `/aitask-pick/execution-profiles` for full schema at line 28).
- **`concepts/locks.md`**, **`concepts/git-branching-model.md`**, **`concepts/task-lifecycle.md`** — aligned with their source scripts.

## Authoritative sources

| Topic | Source |
|---|---|
| `ait create` flags | `.aitask-scripts/aitask_create.sh` |
| `ait update` flags | `.aitask-scripts/aitask_update.sh:196-228` |
| Task frontmatter schema | `CLAUDE.md` §"Task File Format" + create/update scripts |
| Default code-agent model | `.aitask-scripts/aitask_codeagent.sh:21` + `aitasks/metadata/codeagent_config.json` |
| Agent/model examples | `aitasks/metadata/models_*.json` (use `name` field) |

## Implementation plan

1. **`development/task-format.md`** — add `verifies` row to the frontmatter table after `file_references`.
2. **`commands/task-management.md`** — add 7 missing `ait update` rows (`--file-ref`, `--remove-file-ref`, `--pull-request`, `--contributor`, `--contributor-email`, `--folded-tasks`, `--folded-into`) and 1 `ait create` row (`--verifies`), consulting `aitask_update.sh:196-228` and `aitask_create.sh` for exact semantics.
3. **`concepts/agent-attribution.md`** — replace the two stale examples on line 12 with names that exist in `models_geminicli.json` / `models_codex.json`.
4. **"Next:" footers** — add to all 14 concept, 10 command, and 3 development pages. Use `weight:` frontmatter to determine order; link to next page in sequence; omit footer on the final page of each section.
5. **Hugo build check** — `cd website && hugo build --gc --minify`.

## Verification

- `grep -c "verifies" website/content/docs/development/task-format.md` — ≥ 1.
- `for flag in file-ref remove-file-ref pull-request contributor folded-tasks folded-into implemented-with; do grep -q -- "--$flag" website/content/docs/commands/task-management.md && echo "OK: $flag" || echo "MISSING: $flag"; done` — all OK.
- `grep -q -- '--verifies' website/content/docs/commands/task-management.md` — hit (covers both create and update).
- `grep -E "geminicli/|codex/" website/content/docs/concepts/agent-attribution.md` — examples resolve to names present in `models_geminicli.json` / `models_codex.json`.
- `grep -c "Next:" website/content/docs/concepts/*.md | grep -v ":0$" | wc -l` — ≥ 13 (14 minus last).
- `cd website && hugo build --gc --minify` succeeds.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_6`.

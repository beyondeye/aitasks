---
Task: t163_4_classify_skill.md
Parent Task: aitasks/t163_review_modes_consolidate.md
Sibling Tasks: aitasks/t163/t163_5_merge_skill.md
Archived Sibling Plans: aiplans/archived/p163/p163_1_vocabulary_files_and_install.md, aiplans/archived/p163/p163_2_add_reviewguide_metadata.md, aiplans/archived/p163/p163_3_reviewguide_scan_script.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 4 of t163 (Review Guides Consolidation). Creates a Claude Code skill to classify reviewguide files by assigning metadata (`reviewtype`, `reviewlabels`, `environment`), with `similar_to` detection. Also adds the missing `reviewenvironments.txt` vocabulary file and synthetic test files for verification.

## Plan

### 1. Create `reviewenvironments.txt` vocabulary file

**New files:**
- `seed/reviewenvironments.txt` — 17 values (android, bash, c-sharp, cmake, cpp, dart, flutter, go, ios, java, javascript, kotlin, python, rust, shell, swift, typescript), one per line sorted
- `aitasks/metadata/reviewenvironments.txt` — copy from seed

**Update `install.sh`:**
- Add `install_seed_reviewenvironments()` function after `install_seed_reviewlabels()` (after line ~263), same pattern
- Add call after line ~495: `info "Installing review environments..."` + `install_seed_reviewenvironments`

### 2. Update scan script `--missing-meta` mode

In `aiscripts/aitask_reviewguide_scan.sh`, update the `missing-meta` case (line ~288-294) to also flag files in non-general subdirectories that have `environment` as "universal" (i.e., missing). Current check:
```bash
if [[ "$rtype" == "MISSING" || "$rlabels" == "MISSING" ]]; then
```
Change to also detect missing environment for non-general files:
```bash
if [[ "$rtype" == "MISSING" || "$rlabels" == "MISSING" || ( "$_env" == "universal" && "$_path" != general/* ) ]]; then
```

### 3. Create synthetic test files

Copy 2-3 existing reviewguide files into `aireviewguides/` with `test163_` prefix and strip all `reviewtype`, `reviewlabels`, and `environment` metadata from their frontmatter. These will be used to verify the skill works. Delete them after verification.

Candidates:
- `aireviewguides/general/test163_security.md` — copy of `general/security.md` with metadata stripped
- `aireviewguides/python/test163_python.md` — copy of `python/python_best_practices.md` with metadata stripped (also strip `environment`)

### 4. Create skill directory and file

```bash
mkdir -p .claude/skills/aitask-reviewguide-classify/
```

Create `.claude/skills/aitask-reviewguide-classify/SKILL.md` — single new file.

### 5. Skill file structure

**Frontmatter:**
```yaml
---
name: aitask-reviewguide-classify
description: Classify a review guide file by assigning metadata and finding similar existing modes.
---
```

**Sections:**

#### Step 1: Mode Selection
- If argument provided → single-file mode (Step 2)
- If no argument → batch mode (Step 8)

#### Steps 2-7: Single-file mode
- **Step 2: Resolve File** — use fzf to fuzzy-find the argument in `aireviewguides/`:
  ```bash
  find aireviewguides/ -name '*.md' -not -path '*/.reviewguidesignore' | sed 's|aireviewguides/||' | fzf --filter "<argument>" | head -4
  ```
  - If exactly 1 match → use it directly
  - If 2-4 matches → AskUserQuestion to pick one (each match as an option)
  - If 0 matches → inform user, abort
  - Read the resolved file's content, parse frontmatter
- **Step 3: Analyze Content** — read markdown body, identify H2/H3 headings and bullet points, determine what topics the file covers
- **Step 4: Assign Metadata** — read all 3 vocabulary files (`reviewtypes.txt`, `reviewlabels.txt`, `reviewenvironments.txt`):
  - Assign `reviewtype` (1 value from reviewtypes.txt)
  - Assign `reviewlabels` (3-6 values from reviewlabels.txt)
  - Assign `environment` — if file is in a non-general subdirectory, select values from `reviewenvironments.txt` matching the subdirectory scope; if in `general/`, leave as universal (no environment field)
  - Strongly prefer existing vocabulary values; only propose new values if nothing fits
- **Step 5: Compare** — run `./aiscripts/aitask_reviewguide_scan.sh --compare <path>`, parse pipe-delimited output (`path|name|score|shared_labels|type_match|env_overlap`), set `similar_to` if top score >= 5
- **Step 6: Present Results** — show classification summary with all assigned values and similarity info
- **Step 7: Confirm and Apply** — AskUserQuestion (Apply / Modify / Cancel):
  - Update frontmatter with `reviewtype`, `reviewlabels`, optionally `environment` and `similar_to`
  - If new vocab values: append to both `aitasks/metadata/` and `seed/` copies, sort
  - Copy updated file to `seed/reviewguides/<same_relative_path>`
  - Commit (single-file mode) or stage (batch mode)
  - If `similar_to` set: suggest `/aitask-reviewguide-merge`

#### Steps 8-13: Batch mode
- **Step 8: Scan** — run `./aiscripts/aitask_reviewguide_scan.sh --missing-meta`, exit if none found
- **Step 9: Present List** — show files with what's missing (reviewtype, reviewlabels, environment)
- **Step 10: Autocommit consent** — AskUserQuestion (Yes autocommit / No single commit / Cancel)
- **Step 11: Iterate** — run Steps 3-7 for each file
- **Step 12: Final commit** — if not autocommit, single commit: `ait: Classify <N> reviewguide files`
- **Step 13: Summary** — show what was classified, new vocab values, similar_to pairs

#### Notes section
- Argument is a fuzzy search pattern, not necessarily an exact relative path
- Vocab files kept in sync between `aitasks/metadata/` and `seed/` directories
- Scoring formula: `(shared_labels * 2) + (type_match ? 3 : 0) + (env_overlap ? 2 : 0)`
- Threshold for `similar_to`: score >= 5
- Files in `general/` are universal (no environment field); non-general files should have environment
- Label count: 3-6 per file
- Commit format: `ait: Classify reviewguide <filename>`

### 6. Update aitask-review SKILL.md documentation

Update `.claude/skills/aitask-review/SKILL.md` line ~297 Notes section to:
- Mention all three vocabulary files: `reviewtypes.txt`, `reviewlabels.txt`, `reviewenvironments.txt`
- Note that `environment` values should come from `reviewenvironments.txt`
- Add a brief note about the classify skill for maintaining metadata

### Critical Files

| File | Action |
|------|--------|
| `.claude/skills/aitask-reviewguide-classify/SKILL.md` | **new** (main deliverable) |
| `.claude/skills/aitask-review/SKILL.md:295-301` | **edit** (add vocabulary file references + environment vocab note) |
| `seed/reviewenvironments.txt` | **new** |
| `aitasks/metadata/reviewenvironments.txt` | **new** (copy from seed) |
| `install.sh:248-263,495` | **edit** (add reviewenvironments install function + call) |
| `aiscripts/aitask_reviewguide_scan.sh:288-294` | **edit** (add environment check to --missing-meta) |
| `aireviewguides/general/test163_security.md` | **new** (temporary test, delete after) |
| `aireviewguides/python/test163_python.md` | **new** (temporary test, delete after) |

### Key Design Decisions

- **Environment as full vocabulary**: Like reviewtype/reviewlabel, environment gets its own vocabulary file with the same seed→metadata install pattern
- **Scan script update**: minimal change — `--missing-meta` also flags non-general files missing `environment`
- **fzf for file resolution**: fuzzy matching is more user-friendly than requiring exact relative paths
- **Synthetic tests**: temporary files created before skill, used to verify batch + single-file modes, deleted after

## Verification

1. Run `./aiscripts/aitask_reviewguide_scan.sh --missing-meta` — should show the 2 test files
2. Manually run the skill workflow on `test163_security` (single-file mode) — verify it assigns correct metadata
3. Run batch mode — should pick up remaining test file
4. Verify vocabulary files are consistent: `diff seed/reviewenvironments.txt aitasks/metadata/reviewenvironments.txt`
5. Run `shellcheck install.sh` — no new warnings
6. Run `shellcheck aiscripts/aitask_reviewguide_scan.sh` — no new warnings
7. Delete test files after verification
8. Read SKILL.md and verify structure matches aitask-fold conventions

## Post-Review Changes

### Change Request 1 (2026-02-18)
- **Requested by user:** Seed directory should not be synced by the classify skill — seed is only for install.sh distribution
- **Changes made:** Removed all seed file copies from SKILL.md Step 7 and Step 12. Vocabulary files now only updated in `aireviewguides/`. Added note clarifying seed is not modified.
- **Files affected:** `.claude/skills/aitask-reviewguide-classify/SKILL.md`

### Change Request 2 (2026-02-18)
- **Requested by user:** Move vocabulary .txt files into the reviewguides directory for easier management
- **Changes made:** Moved `aitasks/metadata/{reviewtypes,reviewlabels,reviewenvironments}.txt` → `aireviewguides/`. Same for `seed/`. Updated all references in install.sh, classify skill, review skill docs, and t163_5 task spec.
- **Files affected:** `install.sh`, `.claude/skills/aitask-reviewguide-classify/SKILL.md`, `.claude/skills/aitask-review/SKILL.md`, `aitasks/t163/t163_5_merge_skill.md`, seed and metadata vocabulary files

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-reviewguide-classify/SKILL.md` (classify skill with single-file fzf search + batch modes), `reviewenvironments.txt` vocabulary file (17 values, both seed and metadata), updated `install.sh` with install function, updated scan script `--missing-meta` to detect missing environment, updated aitask-review SKILL.md docs, moved all 3 vocabulary files into the `reviewguides/` directory for co-location.
- **Deviations from plan:** (1) Skill does NOT sync to seed directory per user feedback — only writes to `aitasks/metadata/`. (2) Vocabulary files relocated from `aitasks/metadata/*.txt` to `aireviewguides/*.txt` (and same for seed). (3) fzf-based file resolution in Step 2 (added per user request during planning). (4) Added 5 extra environments (ios, swift, dart, flutter, c-sharp) per user request.
- **Issues encountered:** Initial implementation copied all classified files to seed, which is incorrect for custom/test files. Fixed to not touch seed at all.
- **Key decisions:** Vocabulary files co-located with reviewguide files in `reviewguides/` directory for simpler management. Environment vocabulary follows same pattern as reviewtype/reviewlabels but with more comprehensive initial values.
- **Notes for sibling tasks:** Vocabulary file paths are now `aireviewguides/reviewtypes.txt`, `aireviewguides/reviewlabels.txt`, `aireviewguides/reviewenvironments.txt`. The t163_5 task spec has been updated with correct paths. The classify skill does not modify seed — sibling t163_5 should follow the same pattern.

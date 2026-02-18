---
priority: medium
effort: medium
depends: [t163_4]
issue_type: feature
status: Implementing
labels: [aitask_review, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 15:12
updated_at: 2026-02-18 19:05
---

## Context

This is child task 5 of the review modes consolidation (t163). Create a new Claude Code skill for comparing and merging/splitting similar reviewmode files. Has both single-pair and batch modes. Uses the scan script (t163_3) for finding merge candidates.

## Dependencies

- Depends on t163_3 (scan script must exist for `--find-similar` mode)
- Depends on t163_4 (classify skill should exist first, as it populates `similar_to` fields that this skill reads)

## Key Files to Create

- `.claude/skills/aitask-reviewmode-merge/SKILL.md` — **new file**

## Reference Files for Patterns

- `.claude/skills/aitask-fold/SKILL.md` — Best pattern reference for a skill that compares and consolidates content
- `.claude/skills/aitask-reviewmode-classify/SKILL.md` — Sibling skill created in t163_4
- `aiscripts/aitask_reviewmode_scan.sh` — Helper script for `--find-similar` mode
- `aitasks/metadata/reviewmodes/reviewtypes.txt` — Controlled vocabulary
- `aitasks/metadata/reviewmodes/reviewlabels.txt` — Controlled vocabulary

## Implementation Plan

### Skill file: `.claude/skills/aitask-reviewmode-merge/SKILL.md`

**Frontmatter:**
```yaml
---
name: aitask-reviewmode-merge
description: Compare two similar review mode files and merge, split, or keep separate.
---
```

### Single-pair mode (invoked with arguments)

`/aitask-reviewmode-merge <file1> [file2]`

Arguments are paths relative to `aitasks/metadata/reviewmodes/`. If only one file given, reads `similar_to` from its frontmatter for the second file. If no arguments, jump to Batch mode.

#### Step 1: Resolve input files
- Parse arguments
- If one argument: read its frontmatter, get `similar_to` field. If empty, ask user for second file.
- Validate both files exist in `aitasks/metadata/reviewmodes/`
- Read full content of both files (frontmatter + body)

#### Step 2: Detailed comparison
For each file, parse:
- All H2/H3 sections and their bullet points
- Frontmatter metadata (name, description, environment, reviewtype, reviewlabels)

Categorize each bullet point as:
- **Duplicate** — Same check, same or similar wording in both files
- **Unique to A** — Only in file A
- **Unique to B** — Only in file B

Compute overlap percentage: duplicates / (duplicates + unique_A + unique_B)

Present the comparison:
```
## Comparison: <file_A> vs <file_B>

### Duplicate Instructions (N items)
- "<bullet from A>" == "<bullet from B>"

### Unique to <file_A> (N items)
- "<bullet>" (section: <heading>)

### Unique to <file_B> (N items)
- "<bullet>" (section: <heading>)

### Overlap: N% (N duplicate / M total)
```

#### Step 3: Propose action
Based on overlap percentage:
- **>70%** → Recommend "Merge fully" (combine into one, delete other)
- **30-70%** → Recommend "Split" (extract shared content, keep unique parts separate)
- **<30%** → Recommend "Keep separate" (remove exact duplicates, add cross-references)

Present recommendation with rationale.

#### Step 4: User selection
Use `AskUserQuestion`:
- Question: "How should these files be consolidated?"
- Header: "Merge"
- Options:
  - "Merge into <file_A>" (description: "Combine unique content into <file_A>, delete <file_B>")
  - "Merge into <file_B>" (description: "Combine unique content into <file_B>, delete <file_A>")
  - "Keep separate" (description: "Remove duplicates from one file, keep both")
  - "Cancel" (description: "No changes")

Note: "Split" (extracting common parts into a new file) is a complex operation. For the initial implementation, offer merge or keep-separate. Split can be added later if needed.

#### Step 5: Execute chosen action

**If "Merge into <target>":**
1. Build merged content: keep target's structure, integrate unique bullets from the other file into matching sections (or add new sections)
2. Update target's `reviewlabels` to union of both files' labels
3. If environments differ, union the `environment` lists
4. Remove `similar_to` from the target file
5. Delete the other file from both `aitasks/metadata/reviewmodes/` and `seed/reviewmodes/`
6. If new reviewlabels created, add to both vocabulary files (sorted)
7. Copy updated target to `seed/reviewmodes/`
8. Commit: "ait: Merge reviewmode <source_name> into <target_name>"

**If "Keep separate":**
1. Remove exact duplicate bullets from whichever file has fewer unique items
2. Clear `similar_to` from both files
3. Sync to seed directory
4. Commit: "ait: Deduplicate reviewmodes <file_A> and <file_B>"

### Batch mode (invoked without arguments)

`/aitask-reviewmode-merge` (no arguments)

#### Step 1: Find merge candidates
Run: `./aiscripts/aitask_reviewmode_scan.sh --find-similar`

Parse the output to extract pairs and their overlap counts.

#### Step 2: Optional environment filter
Use `AskUserQuestion`:
- Question: "Filter merge candidates by environment?"
- Header: "Filter"
- Options: one for each detected environment from the scan output + "All environments"

#### Step 3: Present candidate pairs
Show pairs with overlap scores, sorted by overlap (highest first).
Use pagination if more than 3 pairs (AskUserQuestion max 4 options, reserve 1 for "Skip all").

#### Step 4: User selects pair
Use `AskUserQuestion` to pick which pair to process (or "Skip all").

#### Step 5: Execute
Run the single-pair workflow (steps 2-5 above) for the selected pair.

#### Step 6: Loop
After completing a pair, use `AskUserQuestion`:
- "Process next pair?" / "Done"

## Verification Steps

1. Read the skill file and verify it follows existing skill conventions
2. Verify the skill references the correct script paths
3. Compare the skill structure to `.claude/skills/aitask-fold/SKILL.md` for consistency

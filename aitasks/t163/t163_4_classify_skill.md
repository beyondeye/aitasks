---
priority: medium
effort: medium
depends: [t163_3]
issue_type: feature
status: Implementing
labels: [aitask_review, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 15:12
updated_at: 2026-02-18 16:06
---

## Context

This is child task 4 of the review modes consolidation (t163). Create a new Claude Code skill that classifies reviewmode files by analyzing their content and assigning metadata (reviewtype, reviewlabels). Has both single-file and batch modes. Uses the scan script (t163_3) for comparison.

## Dependencies

- Depends on t163_3 (scan script must exist for the `--compare` and `--missing-meta` modes)

## Key Files to Create

- `.claude/skills/aitask-reviewmode-classify/SKILL.md` — **new file**

## Reference Files for Patterns

- `.claude/skills/aitask-fold/SKILL.md` — Best pattern reference for a skill with argument parsing, AskUserQuestion usage, and multi-step workflow
- `.claude/skills/aitask-review/SKILL.md` — Shows how reviewmodes are used, for context
- `aitasks/metadata/reviewtypes.txt` — Controlled vocabulary for reviewtype field
- `aitasks/metadata/reviewlabels.txt` — Controlled vocabulary for reviewlabels field
- `aiscripts/aitask_reviewmode_scan.sh` — Helper script for `--missing-meta` (batch mode) and `--compare` (single-file mode)

## Implementation Plan

### Skill file: `.claude/skills/aitask-reviewmode-classify/SKILL.md`

**Frontmatter:**
```yaml
---
name: aitask-reviewmode-classify
description: Classify a review mode file by assigning metadata and finding similar existing modes.
---
```

### Single-file mode (invoked with argument)

`/aitask-reviewmode-classify <relative_path>`

The argument is a path relative to `aitasks/metadata/reviewmodes/` (e.g., `general/code_conventions.md`).

#### Step 1: Validate input
- Parse the argument to get the target file path
- If no argument provided, jump to Batch mode below
- Verify the file exists at `aitasks/metadata/reviewmodes/<path>`
- Read the file's full content (frontmatter + body)
- Parse existing frontmatter fields

#### Step 2: Analyze content
- Read the markdown body (everything after the second `---`)
- Identify H2/H3 section headings and their bullet points
- Determine what the file covers by analyzing headings and content

#### Step 3: Assign metadata
- Read allowed values from `aitasks/metadata/reviewtypes.txt` and `aitasks/metadata/reviewlabels.txt`
- **Assign `reviewtype`:** Must be a value from `reviewtypes.txt`. Choose the best fit based on content analysis. If no existing value fits, propose adding a new value (but prefer existing values strongly).
- **Assign `reviewlabels`:** Select 3-6 values from `reviewlabels.txt` that describe the file's topics. Only propose new labels if no existing label covers the topic.
- **Validate `environment`:** If file is in a language-specific subdirectory (not `general/`), verify it has an `environment` field. Suggest one if missing.

#### Step 4: Compare to existing files
- Run: `./aiscripts/aitask_reviewmode_scan.sh --compare <relative_path>`
- Parse the output to get similarity scores against all other reviewmode files
- Identify the most similar file
- If the top score >= 5, set `similar_to` to that file's relative path

#### Step 5: Present results
Show the user:
```
## Classification Results

**File:** <path>
**Assigned reviewtype:** <type>
**Assigned reviewlabels:** [<labels>]
**Environment:** <env or universal>

### Similarity Analysis
Most similar: <file> (score: <N>, shared labels: <labels>)
```

#### Step 6: Confirm and apply
Use `AskUserQuestion`:
- Question: "Apply the suggested classification?"
- Header: "Classify"
- Options:
  - "Apply as proposed" (description: "Update frontmatter with suggested metadata")
  - "Modify before applying" (description: "Change the suggested values before writing")
  - "Cancel" (description: "Don't modify the file")

If "Modify": Let user adjust values, then apply.

If applying:
1. Update the file's YAML frontmatter with `reviewtype`, `reviewlabels`, and optionally `similar_to`
2. If new reviewtype was added: append to both `aitasks/metadata/reviewtypes.txt` and `seed/reviewtypes.txt`, re-sort
3. If new reviewlabels were added: append to both `aitasks/metadata/reviewlabels.txt` and `seed/reviewlabels.txt`, re-sort
4. Copy the updated file to `seed/reviewmodes/` at the matching relative path
5. Commit all changes

#### Step 7: Suggest next action
If `similar_to` was set:
- Inform: "This file is similar to `<similar_to>`. Consider running `/aitask-reviewmode-merge <file> <similar_file>` to compare and potentially consolidate."

### Batch mode (invoked without arguments)

`/aitask-reviewmode-classify` (no arguments)

#### Step 1: Scan for incomplete files
Run: `./aiscripts/aitask_reviewmode_scan.sh --missing-meta`

If no files are missing metadata, inform user and exit.

#### Step 2: Present list
Show which files are missing metadata (with the specific fields that are missing).

#### Step 3: Ask for autocommit consent
Use `AskUserQuestion`:
- Question: "Auto-commit after each file is classified?"
- Header: "Commit"
- Options:
  - "Yes, autocommit" (description: "Commit changes after each file is processed")
  - "No, single commit at end" (description: "Stage all changes, commit once at the end")
  - "Cancel batch" (description: "Don't process any files")

#### Step 4: Iterate
For each file missing metadata:
- Run the single-file workflow (steps 2-6 above)
- If autocommit: commit immediately after each file
- If not: stage changes, continue to next file

#### Step 5: Final commit (if not autocommit)
If "No, single commit at end" was selected:
- Commit all staged changes with message: "ait: Classify <N> reviewmode files"

#### Step 6: Summary
Show which files were updated and any `similar_to` relationships discovered.

## Verification Steps

1. Read the skill file and verify it follows existing skill conventions (YAML frontmatter, ## Workflow sections, AskUserQuestion patterns)
2. Verify the skill references the correct script paths and vocabulary file paths
3. Compare the skill structure to `.claude/skills/aitask-fold/SKILL.md` for consistency

---
priority: high
effort: medium
depends: [t341_2]
issue_type: feature
status: Implementing
labels: [aitask_contribute, claudeskills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-09 13:06
updated_at: 2026-03-09 17:28
---

Update aitask-contribute SKILL.md with framework-vs-project target selection (Step 0). Add incremental multi-pass codemap generation sub-workflow when code_areas.yaml is missing. Implement hierarchical drill-down for project areas. Add dynamic area updates for unlisted areas.

## Context

This is the third and final child of t341 (generalize aitask-contribute). Tasks t341_1 and t341_2 created the `code_areas.yaml` format, parser, codemap scanning script, and dual-mode `--target` support in `aitask_contribute.sh`. This task updates the skill definition (SKILL.md) to expose the new functionality to users through the AI agent workflow.

## Key Files to Modify

- **Modify** `.claude/skills/aitask-contribute/SKILL.md` — Restructure workflow: add Step 0 (target selection), codemap sub-workflow, hierarchical drill-down, and dynamic area updates

## Reference Files for Patterns

- `.claude/skills/aitask-contribute/SKILL.md` — Current skill (197 lines), the starting point
- `.aitask-scripts/aitask_contribute.sh` — Script with new `--target`, `--parent` flags (from t341_2)
- `.aitask-scripts/aitask_codemap.sh` — Codemap scanning script (from t341_1)
- Archived sibling plans `aiplans/archived/p341/p341_1_*.md` and `p341_2_*.md` — patterns and decisions from previous siblings

## Implementation Plan

### Step 1: Add Step 0 — Target Selection

Insert before current Step 1:

```markdown
### Step 0: Target Selection

Use `AskUserQuestion`:
- Question: "What would you like to contribute to?"
- Header: "Target"
- Options:
  - "aitasks framework" (description: "Contribute improvements to the aitasks framework itself")
  - "This project" (description: "Contribute changes to the project's own codebase")

If "aitasks framework" → proceed with existing Steps 1-7 unchanged (all script calls use `--target framework`).
If "This project" → proceed to Step 0a (Code Areas Check).
```

### Step 2: Add Step 0a — Code Areas Check & Codemap Sub-workflow

When "This project" is selected, check for `code_areas.yaml`:

```markdown
### Step 0a: Code Areas Check (project mode only)

Run prerequisites check with project target:
\`\`\`bash
./.aitask-scripts/aitask_contribute.sh --list-areas --target project
\`\`\`

**If the command fails** (no code_areas.yaml): proceed to **Codemap Generation Sub-workflow**.
**If it succeeds**: proceed to Step 2 (Project Area Selection).
```

The codemap generation sub-workflow is the core new feature:

```markdown
#### Codemap Generation Sub-workflow

This workflow generates code_areas.yaml incrementally. It is designed for multi-pass operation to manage context.

1. Run `./.aitask-scripts/aitask_codemap.sh --scan` to get the directory skeleton (or `--scan --existing aitasks/metadata/code_areas.yaml` if a partial file exists)
2. Parse the skeleton YAML output
3. For each unmapped top-level area (and its children):
   a. Read 2-3 representative files (README, main entry point, config files) in the area's directory
   b. Generate a meaningful 1-sentence description based on AI analysis
   c. If the area has children in the skeleton, repeat for each child
   d. Periodically save: write the updated code_areas.yaml
4. After all areas are mapped, commit:
   \`\`\`bash
   ./ait git add aitasks/metadata/code_areas.yaml
   ./ait git commit -m "ait: Generate code areas map"
   \`\`\`
5. Post-scan checkpoint — AskUserQuestion:
   - "Code areas map generated. How would you like to proceed?"
   - Options: "Continue with contribute workflow" / "Abort (resume later in fresh context)"
   - If Abort → end workflow. File is committed and available next session.
   - If Continue → proceed to Step 2.
```

### Step 3: Restructure Step 2 for hierarchical drill-down (project mode)

When in project mode, replace flat area multi-select with hierarchical drill-down:

```markdown
### Step 2: Area Selection (project mode)

Present top-level areas from `--list-areas --target project` output.

Use AskUserQuestion with multiSelect: true. Options: each area + "Other (unlisted area)".

When a selected area has children, drill down:
\`\`\`bash
./.aitask-scripts/aitask_contribute.sh --list-areas --target project --parent <area-name>
\`\`\`
Present child areas + "Use all of <area>" + "Other (unlisted sub-area)".

If "Other" selected:
- Ask for directory path and description via AskUserQuestion
- Use --area-path for the contribution
- After contribution completes: read code_areas.yaml, append new entry, commit via ./ait git
```

### Step 4: Update Steps 3-7 for project mode

All script invocations in Steps 3-7 must include `--target project` when in project mode. Key changes:
- Step 7 "Create issue": The issue goes to the project's own repo (auto-detected by the script), not `beyondeye/aitasks`
- Step 7 confirm dialog: Change "Submit to beyondeye/aitasks" to "Submit to <project-repo>"
- Notes section: Document the new `--target project` flag and codemap sub-workflow

### Step 5: Update Notes section

Add documentation for:
- The new Step 0 target selection
- The codemap generation sub-workflow and its multi-pass behavior
- The `--target project` and `--parent` flags
- Dynamic area updates (the "Other" option flow)

## Verification Steps

1. Read through the updated SKILL.md end-to-end for consistency
2. Verify all script command examples use correct flags
3. Verify framework flow is unchanged (selecting "aitasks framework" at Step 0)
4. Verify project flow covers: missing code_areas.yaml → codemap generation → area selection → drill-down → contribution
5. Verify "Other" area flow includes code_areas.yaml update and commit

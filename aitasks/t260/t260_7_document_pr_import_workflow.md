---
priority: medium
effort: medium
depends: [t260_6, t260_8]
issue_type: documentation
status: Ready
labels: [documentation]
created_at: 2026-03-01 15:34
updated_at: 2026-03-01 18:11
---

## Context

This is child task 7 of the "Create aitasks from Pull Requests" feature (t260). After all implementation tasks (t260_1 through t260_6) are complete, this task adds comprehensive documentation for the new PR import workflow: bash script reference pages, skill reference pages, and an end-to-end workflow guide.

**Why this task is needed:** The aitasks project has a Hugo/Docsy documentation website (`website/`) with structured reference pages for all commands and skills. New commands (`ait pr-import`, `ait pr-close`) and the new skill (`/aitask-pr-review`) need proper documentation following existing conventions. Additionally, a workflow guide explaining the motivation and end-to-end flow is needed.

**Depends on:** t260_3 (PR import script), t260_4 (PR review skill), t260_5 (PR close script) — documentation must reflect final implementations

## Key Files to Create/Modify

1. **Create `website/content/docs/commands/pr-integration.md`** — Reference page for `ait pr-import` and `ait pr-close` commands
2. **Create `website/content/docs/skills/aitask-pr-review.md`** — Skill reference page
3. **Create `website/content/docs/workflows/pr-workflow.md`** — End-to-end workflow guide
4. **Modify `website/content/docs/commands/_index.md`** — Add PR commands to master command table
5. **Modify `website/content/docs/skills/_index.md`** — Add skill to skill table

## Reference Files for Patterns

### Command Documentation Pattern
- **`website/content/docs/commands/issue-integration.md`** — PRIMARY REFERENCE for command pages. Shows:
  - Hugo frontmatter format: `title`, `linkTitle`, `weight`, `description`
  - Multi-command page structure (multiple `## ait command` sections)
  - Interactive mode section (numbered steps)
  - Batch mode section (code examples + CLI flags)
  - Options table format: `| Option | Description |`
  - Key features list
  - Separator `---` between commands

- **`website/content/docs/commands/_index.md`** — Master command index. Shows:
  - Category headers and two-column command table format
  - Links to full documentation pages

### Skill Documentation Pattern
- **`website/content/docs/skills/aitask-explore.md`** — PRIMARY REFERENCE for skill pages. Shows:
  - Hugo frontmatter format
  - Opening paragraph describing the skill
  - Usage block with example
  - `> **Note:** Must be run from project root` standard note
  - Step-by-step numbered list matching UI flow
  - Key capabilities bulleted list
  - Links to related workflows

- **`website/content/docs/skills/_index.md`** — Master skill index with table format

### Workflow Documentation Pattern
- **`website/content/docs/workflows/`** — Existing workflow guides showing:
  - Motivation/problem description
  - Step-by-step usage flow
  - Examples for different platforms

## Implementation Plan

### 1. Create `website/content/docs/commands/pr-integration.md`

```yaml
---
title: "PR Integration"
linkTitle: "PR Integration"
weight: 42
description: "Import pull requests as tasks and close/decline PRs after implementation"
---
```

**Sections:**

#### `## ait pr-import`
- Brief description: Import pull request data from GitHub/GitLab/Bitbucket and optionally create an aitask
- **Interactive mode:** Numbered steps matching the fzf menu flow
  1. Choose input method (specific PR, browse, range, all)
  2. Preview and select PRs
  3. Configure task metadata (priority, effort, labels)
  4. Create task or write intermediate data
- **Batch mode:**
  ```bash
  ait pr-import --batch --pr 42                    # Import single PR
  ait pr-import --batch --pr 42 --data-only        # Extract data only
  ait pr-import --batch --all --skip-duplicates     # Import all open PRs
  ```
- **Options table:**
  | Option | Description |
  |--------|-------------|
  | `--batch` | Enable non-interactive mode |
  | `--pr NUM` | PR/MR number to import |
  | `--data-only` | Write intermediate data only, don't create task |
  | `--range START-END` | Import range of PR numbers |
  | `--all` | Import all open PRs |
  | ... (all flags from t260_3) |
- **Key features:** Multi-platform support, duplicate detection, contributor email resolution, intermediate data for AI analysis
- **Intermediate data format:** Brief description of `.aitask-pr-data/` files

---

#### `## ait pr-close`
- Brief description: Close or decline a PR linked to a completed aitask, with optional implementation notes
- **Platform behavior:**
  - GitHub: Closes the PR with an optional comment
  - GitLab: Closes the MR (posts note separately if commenting)
  - Bitbucket: Declines the PR (uses "decline" semantics)
- **Usage:**
  ```bash
  ait pr-close <task_num>                 # Close with implementation notes
  ait pr-close --no-comment <task_num>    # Close without comment
  ait pr-close --dry-run <task_num>       # Preview comment
  ```
- **Options table** for all flags
- **Comment format:** Example of what gets posted to the PR

### 2. Create `website/content/docs/skills/aitask-pr-review.md`

```yaml
---
title: "/aitask-pr-review"
linkTitle: "/aitask-pr-review"
weight: 22
description: "Analyze a pull request and create an aitask with implementation plan"
---
```

**Sections:**
- Opening paragraph explaining the skill
- Usage block: `/aitask-pr-review`
- `> **Note:** Must be run from project root`
- **Step-by-step** (numbered list):
  1. PR selection (enter number, browse, use existing data)
  2. PR analysis (AI-powered analysis of purpose, approach, quality)
  3. Interactive Q&A (explore codebase, ask questions)
  4. Related task discovery (check for overlapping pending tasks)
  5. Task creation (with `pull_request:`, `contributor:`, `contributor_email:` metadata)
  6. Decision point (save for later or continue to implementation)
- **Key capabilities** list
- **Profiles** section: How execution profiles affect the workflow
- **Workflows:** Link to `pr-workflow.md`

### 3. Create `website/content/docs/workflows/pr-workflow.md`

```yaml
---
title: "PR Import Workflow"
linkTitle: "PR Import"
weight: 35
description: "End-to-end guide for importing pull requests as aitasks"
---
```

**Sections:**

#### Motivation
- Why import PRs as tasks instead of merging directly
- Use cases: external contributions, code quality gates, approach validation
- Benefits: proper attribution, structured review, consistent implementation

#### Overview Flow
```
External PR → ait pr-import → Intermediate Data → /aitask-pr-review → Task + Plan
    ↓                                                                      ↓
Contributor                                                          Implementation
credited via                                                              ↓
Co-authored-by                                                     Archive + PR Close
```

#### Step-by-Step Guide
1. Import PR data: `ait pr-import --batch --pr 42 --data-only`
2. Review with AI: `/aitask-pr-review`
3. Implement the task: `/aitask-pick <N>`
4. Archive: automatic PR close and contributor attribution

#### New Metadata Fields
- `pull_request:` — URL of the source PR
- `contributor:` — Platform username of the PR author
- `contributor_email:` — Pre-computed noreply email for attribution

#### Contributor Attribution
- How `Co-authored-by` trailers work
- GitHub and GitLab noreply email formats
- Example commit message with attribution

#### Platform-Specific Examples
- GitHub example (PR → close)
- GitLab example (MR → close)
- Bitbucket example (PR → decline)

### 4. Update `website/content/docs/commands/_index.md`

Add a new category in the command table:

```markdown
### PR Integration

| Command | Description |
|---------|-------------|
| [`ait pr-import`](pr-integration/) | Import pull requests as tasks |
| [`ait pr-close`](pr-integration/) | Close/decline PRs after task completion |
```

### 5. Update `website/content/docs/skills/_index.md`

Add to the skill table:

```markdown
| [`/aitask-pr-review`](aitask-pr-review/) | Analyze a pull request and create an aitask with implementation plan |
```

## Verification Steps

1. **Build the website:**
   ```bash
   cd website && hugo build --gc --minify
   ```
   Verify no build errors.

2. **Run local dev server:**
   ```bash
   cd website && ./serve.sh
   ```
   Check each new page renders correctly:
   - `/docs/commands/pr-integration/`
   - `/docs/skills/aitask-pr-review/`
   - `/docs/workflows/pr-workflow/`

3. **Verify navigation:**
   - Check sidebar shows PR Integration under Commands
   - Check sidebar shows /aitask-pr-review under Skills
   - Check all cross-links work (commands ↔ skills ↔ workflows)

4. **Verify content accuracy:**
   - Compare command documentation against actual CLI flags in `aitask_pr_import.sh` and `aitask_pr_close.sh`
   - Compare skill documentation against actual SKILL.md workflow steps
   - Verify examples work with actual commands

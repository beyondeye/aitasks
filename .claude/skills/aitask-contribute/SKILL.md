---
name: aitask-contribute
description: Contribute local aitasks framework changes back to the upstream repository by opening structured GitHub issues.
user-invocable: true
---

## Workflow

### Step 1: Prerequisites Check

Verify `gh` CLI is installed and authenticated:

```bash
command -v gh >/dev/null 2>&1 && gh auth status 2>&1
```

If `gh` is not available or not authenticated, abort: "The `gh` CLI is required for this skill. Install it from https://cli.github.com/ and run `gh auth login`."

Detect contribution mode and list available areas:

```bash
./.aitask-scripts/aitask_contribute.sh --list-areas
```

Parse the output:
- First line: `MODE:<clone|downstream>` — contribution mode
- Subsequent lines: `AREA|<name>|<dirs>|<description>` — one per available area

Inform user: "Detected contribution mode: **clone/fork**" or "Detected contribution mode: **downstream project**".

### Step 2: Area Selection

Use `AskUserQuestion` with `multiSelect: true`:
- Question: "Which areas of the framework did you modify?"
- Header: "Areas"
- Options: Each area from `--list-areas` output. Label = area name, description = area description + directories. If more than 4 areas, paginate (3 per page + "Show more").
- Add "Other (custom path)" option (description: "Specify a custom directory path")

If "Other" selected: Use `AskUserQuestion` to ask "Enter the custom directory path to scan for changes:" with header "Path" (free text via "Other" option). Store as `--area-path` instead of `--area`.

### Step 3: File Discovery

For each selected area, run:

```bash
./.aitask-scripts/aitask_contribute.sh --list-changes --area <area>
```

(Or `--area-path <path>` for custom paths.)

Collect all changed file paths across areas.

**If no changed files found:** Inform user: "No changes detected in the selected areas compared to upstream." Abort.

**If files found:** Present changed files to user via `AskUserQuestion` with `multiSelect: true`:
- Question: "These files have changes compared to upstream. Select the files you want to contribute:"
- Header: "Files"
- Options: Each file path as a selectable option. If more than 4 files, paginate (3 per page + "Show more" option).

Store selected files for subsequent steps.

### Step 4: Upstream Diff + AI Analysis

For the confirmed files, generate the diff via dry-run:

```bash
./.aitask-scripts/aitask_contribute.sh --dry-run --area <area> \
  --files "<file1,file2,...>" \
  --title "placeholder" --motivation "placeholder" \
  --scope enhancement --merge-approach "clean merge"
```

Read the generated issue body from stdout. It contains the full diffs embedded in markdown.

**AI analysis:** Analyze the diffs and present a structured summary:

```
## Changes Summary
- **Mode:** <clone|downstream>
- **Files:** N files across M areas
- **Change groups:** (AI-identified logical groups)
  - Group 1: <description> (files: ...)
  - Group 2: <description> (files: ...)
```

Assess:
- What changed in each file (semantic understanding)
- Whether changes are logically related (one feature) or distinct (multiple contributions)
- Appropriate scope classification per change group
- Merge complexity

### Step 5: Contribution Grouping

**If only one logical group identified:** Skip this step. Proceed with all files as one contribution.

**If multiple distinct groups identified:** Use `AskUserQuestion`:
- Question: "These changes appear to cover multiple distinct improvements. Would you like to split them into separate contributions?"
- Header: "Grouping"
- Options:
  - "Split into N separate contributions" (description: "One GitHub issue per logical change group")
  - "Keep as single contribution" (description: "Submit all changes in one GitHub issue")
  - "Custom grouping" (description: "Manually adjust which files go in which contribution")

If "Custom grouping": Use follow-up `AskUserQuestion` interactions to let user assign files to groups.

Each group becomes a separate issue in Step 7.

### Step 6: Motivation and Scope per Contribution

For each contribution group (loop if multiple):

**Title:** Use `AskUserQuestion`:
- Question: "Proposed title for this contribution. Confirm or modify:"
- Header: "Title"
- Options:
  - AI-proposed title based on diff analysis
  - "Other" for free text modification

**Motivation:** Use `AskUserQuestion`:
- Question: "Why should this change be contributed upstream? What problem does it solve or what value does it add?"
- Header: "Motivation"
- Options: free text only (use "Other")

**Scope:** Use `AskUserQuestion`:
- Question: "What type of change is this?"
- Header: "Scope"
- Options:
  - "Bug fix" (description: "Fixes incorrect behavior") — maps to `bug_fix`
  - "Enhancement" (description: "Improves existing functionality") — maps to `enhancement`
  - "New feature" (description: "Adds entirely new capability") — maps to `new_feature`
  - "Documentation" (description: "Documentation improvements") — maps to `documentation`

**Merge approach:** Use `AskUserQuestion`:
- Question: "Proposed merge approach for upstream maintainers:"
- Header: "Merge"
- Options:
  - AI-proposed approach based on change complexity (description: "Based on diff analysis")
  - "Clean merge" (description: "Standard merge, no conflicts expected")

### Step 7: Review, Confirm, and Create Issue(s)

For each contribution (loop if multiple):

**Generate final preview:**

```bash
./.aitask-scripts/aitask_contribute.sh --dry-run --area <area> \
  --files "<files>" \
  --title "<title>" --motivation "<motivation>" \
  --scope <scope> --merge-approach "<approach>"
```

Present the issue body preview to the user.

**Confirm:** Use `AskUserQuestion`:
- Question: "Create this contribution issue on the upstream repository?"
- Header: "Confirm"
- Options:
  - "Create issue" (description: "Submit to beyondeye/aitasks")
  - "Edit" (description: "Go back and modify title, motivation, or scope")
  - "Abort" (description: "Cancel this contribution")

**Handle selection:**

- **"Create issue":** Run without `--dry-run`:
  ```bash
  ./.aitask-scripts/aitask_contribute.sh --area <area> \
    --files "<files>" \
    --title "<title>" --motivation "<motivation>" \
    --scope <scope> --merge-approach "<approach>" --silent
  ```
  The output is the issue URL. Display to user.

- **"Edit":** Loop back to Step 6 for this contribution.

- **"Abort":** Skip this contribution, continue to next (if any).

**After all contributions processed:** Display summary:

```
## Contribution Summary
- Issue #X: <title> — <url>
- Issue #Y: <title> — <url>

When these issues are imported via /aitask-pr-import or /aitask-issue-import,
your Co-authored-by attribution will be preserved in implementation commits.
```

---

## Notes

- This skill creates GitHub issues on the upstream repository — it does NOT create local aitasks
- No execution profiles are used (unlike aitask-pick, aitask-explore, and aitask-pr-import)
- No remote sync step needed
- No handoff to task-workflow
- The `--list-areas` output format: first line `MODE:<mode>`, then `AREA|<name>|<dirs>|<description>` per area
- The `--list-changes` output format: one file path per line
- The `--dry-run` flag outputs the full issue markdown body to stdout
- Without `--dry-run` and with `--silent`, the script outputs only the issue URL
- Scope values map: "Bug fix" -> `bug_fix`, "Enhancement" -> `enhancement`, "New feature" -> `new_feature`, "Documentation" -> `documentation`. The "Other" option via AskUserQuestion maps to `other`
- Additional script flags available but not used interactively: `--area-path` (for custom paths), `--repo` (override upstream repo), `--diff-preview-lines` (control diff truncation)

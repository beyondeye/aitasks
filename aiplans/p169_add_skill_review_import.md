## Context

Task t169 introduces a new `aitask-reviewguide-import` skill — a complementary skill to `aitask-review` (alongside the existing `classify` and `merge` skills from t163). The skill imports external content (from local files, URLs, or GitHub source directories) and transforms it into reviewguide-compatible format with proper metadata. This enables users to quickly onboard external coding standards, best practices, or style guides into their review workflow.

## Implementation Plan

### 1. Create skill directory and SKILL.md

**File:** `.claude/skills/aitask-reviewguide-import/SKILL.md`

#### Skill Frontmatter
```yaml
---
name: aitask-reviewguide-import
description: Import external content (file, URL, or GitHub directory) as a reviewguide with proper metadata.
---
```

#### Workflow Design

**Step 1: Input Resolution**

Accept input via skill argument: `/aitask-reviewguide-import <source>`

Where `<source>` can be:
- **Local file path** — e.g., `docs/coding-standards.md`, `~/standards/security.md`
- **GitHub URL to a single file** — e.g., `https://github.com/org/repo/blob/main/docs/style.md`
- **GitHub URL to a directory** — e.g., `https://github.com/org/repo/tree/main/docs/guides/`
- **Any other URL** — e.g., `https://example.com/coding-standards`

If no argument provided, use `AskUserQuestion` to ask for the source (file path or URL).

**Detection logic:**
- If starts with `/` or `~` or `./` or exists as a local file → local file
- If contains `github.com` and `/blob/` → GitHub single file
- If contains `github.com` and `/tree/` → GitHub directory
- Otherwise → generic URL

**Fetching:**
- Local file: Read directly
- GitHub single file: Convert blob URL to raw URL (`raw.githubusercontent.com`) and fetch with `WebFetch`, or use `gh api` to get content
- GitHub directory: Use `gh api repos/{owner}/{repo}/contents/{path}?ref={branch}` to list files, filter to `.md` files, then process each one (ask user which to import if multiple)
- Generic URL: Use `WebFetch` to fetch and extract content

**Step 2: Content Analysis**

Read the fetched content and analyze it:
- Identify the document type (coding standards, workflow guide, best practices, style guide, architecture doc, etc.)
- Extract the sections/topics covered
- Identify which parts are relevant for code review (actionable checks) vs. which are not (narrative, workflow steps, project setup, etc.)

Present a brief summary to the user:
```
## Source Analysis

**Source:** <url_or_path>
**Document type:** <identified type>
**Sections found:** <list of H2/H3 headings>
**Review-relevant sections:** <list of sections with actionable review content>
**Non-relevant sections:** <list of sections to skip (workflows, setup, etc.)>
```

**Step 3: Transform Content**

Rephrase the relevant content into reviewguide-compatible format:
- Convert narrative text into actionable bullet points (imperative review checks)
- Group by topic under H3 sections within a single `## Review Instructions` heading
- Remove workflow/process content that isn't about reviewing code
- Preserve technical specifics (patterns to check, antipatterns to flag)
- Use the established tone from existing guides: "Check that...", "Flag...", "Look for...", "Verify that..."

**Step 4: Determine Placement**

Read vocabulary files:
```bash
cat aireviewguides/reviewtypes.txt
cat aireviewguides/reviewlabels.txt
cat aireviewguides/reviewenvironments.txt
```

Based on content analysis:
- **Assign `name`:** Short descriptive name (e.g., "React Best Practices")
- **Assign `description`:** One-line description of what the guide checks
- **Assign `reviewtype`:** Best-fit from `reviewtypes.txt`
- **Assign `reviewlabels`:** 3-6 from `reviewlabels.txt`
- **Assign `environment`:** From `reviewenvironments.txt` if language-specific; omit if general
- **Set `source_url`:** The original URL or file path (for reference only)
- **Determine subdirectory:** `general/` if universal, or language-specific dir (e.g., `python/`, `kotlin/`)
- **Determine filename:** `<topic>_<descriptor>.md` following convention (lowercase, underscores)

**Step 5: Preview and Confirm**

Show the user the complete generated reviewguide file (frontmatter + body) and proposed path.

Use `AskUserQuestion`:
- Question: "Review the imported guide. How would you like to proceed?"
- Header: "Import"
- Options:
  - "Save as proposed" — Write file and proceed to classification check
  - "Edit before saving" — User provides modifications
  - "Cancel" — Abort import

**If "Edit before saving":** Ask what to change, apply modifications, re-preview.

**Step 6: Save and Classify**

1. Write the reviewguide file to `aireviewguides/<subdir>/<filename>.md`
2. Run the scan script to find similar files:
   ```bash
   ./aiscripts/aitask_reviewguide_scan.sh --compare <relative_path>
   ```
3. If similarity score >= 5, set `similar_to` in frontmatter
4. Update vocabulary files if new values were used (same pattern as classify skill)
5. Commit:
   ```bash
   git add aireviewguides/
   git commit -m "ait: Import reviewguide <filename> from <source_type>"
   ```
6. If `similar_to` was set, suggest running `/aitask-reviewguide-merge`

**Step 7: Batch Mode (for GitHub directories)**

When source is a GitHub directory with multiple `.md` files:
1. List all markdown files in the directory
2. Use `AskUserQuestion` (multiSelect) to let user choose which files to import:
   - Options include each markdown file found (up to 3 per page with pagination)
   - First option: **"Import all"** (description: "Import all N markdown files from this directory")
   - If "Import all" selected, process every file
3. For each selected file, run Steps 2-6
4. Show batch summary at the end

### 2. Register the skill in install.sh

No code change needed — `install.sh` already uses a glob pattern (`skills/aitask-*/`) that will automatically pick up the new skill directory.

### 3. Ensure `source_url` is ignored by review skill

Already confirmed: `aitask-review/SKILL.md` only reads the markdown body after frontmatter. The `source_url` field in YAML frontmatter is naturally ignored. No changes needed to the review skill.

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `.claude/skills/aitask-reviewguide-import/SKILL.md` | **Create** | New skill definition |

No other files need modification. The review skill, scan script, and install.sh all work with the new skill without changes.

## Verification

1. **Skill loads correctly:** Run `/aitask-reviewguide-import` — should prompt for source
2. **Local file import:** Test with a local markdown file containing coding standards
3. **URL import:** Test with a GitHub raw markdown URL
4. **Generated format:** Verify the output matches existing reviewguide format (frontmatter + bullet points)
5. **source_url preserved:** Check frontmatter contains original source reference
6. **Classify integration:** Run `./aiscripts/aitask_reviewguide_scan.sh --compare <new_file>` to verify similarity scoring works
7. **Review integration:** Run `/aitask-review` and verify the imported guide appears in the guide selection list

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-reviewguide-import/SKILL.md` with a 7-step workflow: input resolution (local file, GitHub file, GitHub directory, generic URL), content analysis, content transformation to bullet-point review format, metadata assignment, preview/confirm, save/classify with similarity check, and batch mode for GitHub directories.
- **Deviations from plan:** None — the implementation followed the plan exactly. The SKILL.md is self-contained and requires no changes to existing files.
- **Issues encountered:** None.
- **Key decisions:** Used `gh api` as primary GitHub fetch mechanism with `WebFetch` as fallback. Batch mode pagination uses "Import all" as the first option per user feedback.

## Post-Implementation (Step 9)

Archive task and plan per the standard workflow.

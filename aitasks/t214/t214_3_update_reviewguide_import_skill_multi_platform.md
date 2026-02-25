---
priority: high
effort: medium
depends: [t214_2]
issue_type: bug
status: Ready
labels: [claudeskills, aitask_reviewguide, portability]
created_at: 2026-02-25 12:13
updated_at: 2026-02-25 12:13
---

## Context

This is child task 3 of t214 (Multi-platform reviewguide import and setup dedup). The `aitask-reviewguide-import` Claude skill (`.claude/skills/aitask-reviewguide-import/SKILL.md`) currently hardcodes GitHub-specific URL patterns and API calls. With the helper library from t214_1 available, this task updates the skill instructions to support GitHub, GitLab, and Bitbucket.

## Key Files to Modify

- `.claude/skills/aitask-reviewguide-import/SKILL.md` — Primary file, multi-platform URL detection and fetching instructions

## Reference Files for Patterns

- `aiscripts/lib/repo_fetch.sh` (created by t214_1) — The helper library with verified API methods
- `aiscripts/aitask_issue_import.sh:64-388` — Existing multi-platform dispatcher pattern for reference
- `aidocs/gitremoteproviderintegration.md` — Extension guide documenting platform URL patterns

## Implementation Plan

### Changes needed

1. **YAML description (line 3):** Change "GitHub directory" to "repository directory"

2. **Step 1 intro text (lines 10, 13, 17):** Replace "GitHub directory URL" with "repository directory URL", update AskUserQuestion option to mention all three platforms

3. **Step 1b: Detect Source Type (lines 21-28):** Expand URL detection:
   - Repository single file: GitHub (`github.com` + `/blob/`), GitLab (`gitlab.com` + `/-/blob/`), Bitbucket (`bitbucket.org` + `/src/` + file extension)
   - Repository directory: GitHub (`github.com` + `/tree/`), GitLab (`gitlab.com` + `/-/tree/`), Bitbucket (`bitbucket.org` + `/src/` + no extension or trailing `/`)
   - Platform detection by hostname

4. **Step 1c: Fetch Content (lines 30-61):** Platform-specific fetching:
   - URL parsing table per platform (split patterns)
   - Single file: GitHub (`gh api` + base64), GitLab (`glab api` + URL-encoded path), Bitbucket (`curl` raw URL)
   - Directory listing: GitHub (`gh api` + jq), GitLab (`glab api` + jq), Bitbucket (REST API `2.0/repositories/` + jq)
   - Each platform has a fallback (raw URL via WebFetch or curl)

5. **Step 7: Batch Mode (lines 255-294):** Change "GitHub directories" to "repository directories", replace `gh api` with "platform-specific method from Step 1c"

6. **Notes section (lines 296-308):** Per-platform fetching notes, self-hosted instances note

### Important: This is a skill/instruction file, not a shell script
The changes are to markdown text that Claude follows as instructions. The "code" shown is illustrative commands, not executed directly. Reference `repo_fetch.sh` for Bash tool calls where applicable, but keep WebFetch instructions for the skill's non-bash paths.

## Verification Steps

1. Review the updated SKILL.md for correctness of all URL patterns and API commands
2. Manually test: invoke `/aitask-reviewguide-import` with a GitLab URL and verify the skill follows the new instructions correctly
3. Manually test: invoke with a Bitbucket URL
4. Verify existing GitHub URL flow is not broken

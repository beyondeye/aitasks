---
priority: high
effort: low
depends: []
issue_type: feature
status: Ready
labels: [bash_scripts]
created_at: 2026-03-01 15:28
updated_at: 2026-03-01 15:28
---

## Context

This is the foundation child task for the "Create aitasks from Pull Requests" feature (t260). The aitasks framework currently supports an `issue:` metadata field in task YAML frontmatter for linking tasks to GitHub/GitLab/Bitbucket issues. We need to add three new analogous metadata fields to support linking tasks to pull requests and attributing external contributors.

**Why this task is needed:** All other child tasks (board TUI, PR import script, PR review skill, archive workflow, contributor attribution, documentation) depend on these metadata fields existing in the create/update/ls scripts. This must be completed first.

**New metadata fields:**
- `pull_request: <URL>` — link to the source PR/MR (e.g., `https://github.com/owner/repo/pull/42`)
- `contributor: <username>` — platform username/handle of the PR author (e.g., `octocat`)
- `contributor_email: <email>` — pre-computed noreply email for Co-authored-by attribution (e.g., `12345+octocat@users.noreply.github.com`)

## Key Files to Modify

1. **`aiscripts/aitask_create.sh`** (~1467 lines)
   - Add `BATCH_PULL_REQUEST=""`, `BATCH_CONTRIBUTOR=""`, `BATCH_CONTRIBUTOR_EMAIL=""` global variables (around line 30, near `BATCH_ISSUE`)
   - Add `--pull-request`, `--contributor`, `--contributor-email` to argument parsing in `parse_args()` (around line 166, near `--issue`)
   - Pass new fields to `create_task_file()`, `create_child_task_file()`, and `create_draft_file()` — follow exact pattern of how `--issue` is written to YAML frontmatter
   - Write fields in YAML output blocks: after the `issue:` line, add `pull_request:`, `contributor:`, `contributor_email:` (only if non-empty)

2. **`aiscripts/aitask_update.sh`** (~700 lines)
   - Add `BATCH_PULL_REQUEST`, `BATCH_PULL_REQUEST_SET`, `BATCH_CONTRIBUTOR`, `BATCH_CONTRIBUTOR_SET`, `BATCH_CONTRIBUTOR_EMAIL`, `BATCH_CONTRIBUTOR_EMAIL_SET` variables
   - Add `--pull-request`, `--contributor`, `--contributor-email` to argument parsing
   - Add `CURRENT_PULL_REQUEST`, `CURRENT_CONTRIBUTOR`, `CURRENT_CONTRIBUTOR_EMAIL` to `parse_yaml_frontmatter()` function (around line 244, case statement — add cases for `pull_request)`, `contributor)`, `contributor_email)`)
   - Pass new fields through `write_task_file()` function

3. **`aiscripts/aitask_ls.sh`** (~400 lines)
   - Add `pull_request` and `contributor` parsing in the frontmatter loop (around line 188)
   - Display in verbose output format: add `PR: <url>` and `Contributor: <username>` lines (similar to how `Issue: <url>` is displayed)

4. **`aiscripts/lib/task_utils.sh`** (~400 lines)
   - Add `extract_pr_url()` function modeled on `extract_issue_url()` (around line 283). Same pattern: grep for `^pull_request:` in the YAML frontmatter section
   - Add `extract_contributor()` function — same pattern, grep for `^contributor:`
   - Add `extract_contributor_email()` function — same pattern, grep for `^contributor_email:`

## Reference Files for Patterns

- **`aiscripts/aitask_create.sh`** — Search for `BATCH_ISSUE` and `--issue` to find all locations where the `issue` field is handled. Replicate this pattern for all three new fields.
- **`aiscripts/aitask_update.sh`** — Search for `CURRENT_ISSUE` and `issue)` in parse_yaml_frontmatter to see the pattern. Also search for `BATCH_ISSUE_SET` for the update flag pattern.
- **`aiscripts/lib/task_utils.sh`** — Look at `extract_issue_url()` function (around line 283) for the extraction pattern.
- **`aiscripts/aitask_ls.sh`** — Search for `issue_text` to see how the issue field is displayed in verbose output.

## Implementation Steps

1. **task_utils.sh** — Add the three extraction functions first (foundation for other scripts):
   ```bash
   extract_pr_url() { ... }        # grep ^pull_request: pattern
   extract_contributor() { ... }    # grep ^contributor: pattern  
   extract_contributor_email() { ... }  # grep ^contributor_email: pattern
   ```

2. **aitask_create.sh** — Add batch variables, argument parsing, and YAML output:
   - Add global vars near `BATCH_ISSUE`
   - Add cases in `parse_args()` near `--issue)`
   - In `create_task_file()`, `create_child_task_file()`, `create_draft_file()`: write the fields in YAML block after `issue:` (only if non-empty, same conditional pattern as issue)

3. **aitask_update.sh** — Add parsing and update support:
   - Add `CURRENT_*` variables and `BATCH_*` + `BATCH_*_SET` variables
   - Add case statements in `parse_yaml_frontmatter()`
   - Pass through `write_task_file()`

4. **aitask_ls.sh** — Add display support in verbose mode

## Verification Steps

1. Create a task with all three new fields:
   ```bash
   echo "Test PR task" | ./aiscripts/aitask_create.sh --batch --name "test_pr_metadata" \
     --pull-request "https://github.com/owner/repo/pull/42" \
     --contributor "octocat" \
     --contributor-email "12345+octocat@users.noreply.github.com" \
     --desc-file - --commit
   ```

2. Verify the task file contains all three fields in YAML frontmatter

3. Verify `./ait ls -v` shows the PR and contributor info

4. Verify `./ait update --batch <task_num> --pull-request "https://github.com/owner/repo/pull/99"` updates the field

5. Run existing tests to ensure no regressions:
   ```bash
   bash tests/test_draft_finalize.sh
   ```

6. Run shellcheck:
   ```bash
   shellcheck aiscripts/aitask_create.sh aiscripts/aitask_update.sh aiscripts/aitask_ls.sh aiscripts/lib/task_utils.sh
   ```

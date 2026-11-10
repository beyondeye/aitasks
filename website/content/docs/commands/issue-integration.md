---
title: "Issue Integration & Utilities"
linkTitle: "Issues & Utilities"
weight: 40
description: "ait issue-import, ait issue-update, ait release-notify, ait changelog, and ait zip-old commands"
depth: [advanced]
---

## ait issue-import

Import GitHub/GitLab/Bitbucket issues as AI task files. Supports interactive selection with fzf or batch automation. The source platform is auto-detected from the git remote URL (`github.com` → GitHub, `gitlab.com` → GitLab, `bitbucket.org` → Bitbucket). Use `--source` to override.

**Interactive mode** (default — requires fzf and gh/glab CLI):

1. **Import mode selection** — Choose via fzf: "Specific issue number", "Fetch open issues and choose", "Issue number range", "All open issues"
2. **Issue selection** — Depends on mode:
   - *Specific issue*: enter issue number manually
   - *Fetch & choose*: fetches all open issues via `gh issue list` (or `glab issue list` for GitLab), presents in fzf with multi-select (Tab to select multiple) and preview pane showing issue body/labels
   - *Range*: enter start and end issue numbers
   - *All open*: fetches all open issues with confirmation prompt showing count
3. **Duplicate check** — Searches active and archived tasks for matching issue URL. If found, warns and offers Skip/Import anyway
4. **Issue preview** — Shows title and first 30 lines of body (truncated warning if longer). Confirm Import/Skip via fzf
5. **Task name** — Auto-generated from issue title (lowercase, sanitized). Editable with free text entry
6. **Labels** — Two-phase: first review each issue label individually (keep/skip via fzf), then iterative add loop (select from existing labels in `labels.txt`, add new label, or done)
7. **Priority** — fzf selection: high, medium, low
8. **Effort** — fzf selection: low, medium, high
9. **Issue type** — Auto-detected from issue labels: `bug` → bug, `refactor`/`tech-debt`/`cleanup` → refactor, otherwise → feature
10. **Create & commit** — Creates task file via `aitask_create.sh`, then prompts Y/n to commit to git

**Batch mode** (for automation and scripting):

```bash
ait issue-import --batch --issue 42
ait issue-import --batch --range 1-10 --priority high
ait issue-import --batch --all --skip-duplicates
ait issue-import --batch --all --parent 53 --skip-duplicates
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode (required for non-interactive) |
| `--issue, -i NUM` | Import a specific issue number |
| `--range START-END` | Import issues in a number range (e.g., 5-10) |
| `--all` | Import all open issues |
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab`, `bitbucket` (auto-detected from git remote) |
| `--priority, -p LEVEL` | Override priority: high, medium (default), low |
| `--effort, -e LEVEL` | Override effort: low, medium (default), high |
| `--type, -t TYPE` | Override issue type (default: auto-detect from labels) |
| `--status, -s STATUS` | Override status (default: Ready) |
| `--labels, -l LABELS` | Override labels (default: mapped from issue labels) |
| `--deps DEPS` | Set dependencies (comma-separated task numbers) |
| `--parent, -P NUM` | Create as child of parent task |
| `--no-sibling-dep` | Don't add dependency on previous sibling |
| `--commit` | Auto git commit after creation |
| `--silent` | Output only created filename(s) |
| `--skip-duplicates` | Skip already-imported issues silently |
| `--no-comments` | Don't include issue comments in task description |

**Key features:**
- Platform-extensible dispatcher architecture (GitHub, GitLab, and Bitbucket backends implemented; add new platforms by implementing backend functions)
- Auto-detection of source platform from git remote URL (override with `--source`)
- Issue label → aitask label mapping (lowercase, special chars sanitized)
- Auto issue type detection from issue labels (`bug`, `refactor`, `tech-debt`, `cleanup`)
- Duplicate detection across active and archived task directories
- Issue comments included in task description by default (disable with `--no-comments`)
- Issue timestamps (created/updated) embedded in task description

---

## ait issue-update

Post implementation notes and commit references to a GitHub/GitLab/Bitbucket issue linked to a task. Optionally closes the issue. No interactive mode — fully CLI-driven. The source platform is auto-detected from the issue URL in the task's frontmatter. Use `--source` to override.

```bash
ait issue-update 83                           # Post comment on linked issue
ait issue-update --close 53_1                 # Close issue with implementation notes
ait issue-update --commits "abc123,def456" 83 # Override commit detection
ait issue-update --dry-run 53_6               # Preview without posting
ait issue-update --close --no-comment 83      # Close silently
```

| Option | Description |
|--------|-------------|
| `TASK_NUM` | Task number (required): `53`, `53_6`, or `t53_6` |
| `--source, -S PLATFORM` | Source platform: `github`, `gitlab`, `bitbucket` (auto-detected from issue URL) |
| `--commits RANGE` | Override auto-detected commits. Formats: comma-separated (`abc,def`), range (`abc..def`), or single hash |
| `--close` | Close the issue after posting the comment |
| `--comment-only` | Post comment only, don't close (default behavior) |
| `--no-comment` | Close without posting a comment (requires `--close`) |
| `--dry-run` | Show what would be done without doing it |
| `--record-only` | Record the release-ledger entry only, with no platform call (the recovery for exit status 3) |

**How it works:**

1. Reads the `issue` field from the task file's YAML frontmatter to find the issue URL (auto-detects GitHub/GitLab/Bitbucket from the URL)
2. Resolves the archived plan file and extracts the "Final Implementation Notes" section
3. Auto-detects associated commits by searching git log for `(t<task_id>)` in commit messages (only source code commits use this parenthesized pattern)
4. Builds a markdown comment with: task reference header, link to plan file, implementation notes, and commit list
5. Posts the comment and/or closes the issue

**Key features:**
- Commit auto-detection from `(tNN)` pattern in commit messages — distinguishes source code commits from administrative ones
- Commit override with flexible formats: comma-separated hashes, hash range, or single hash
- Plan file resolution across active and archived directories
- Dry-run mode for previewing the comment before posting
- Auto-detection of source platform from issue URL (override with `--source`)
- Platform-extensible dispatcher (same architecture as issue-import)

**Release ledger.** After the comment is posted or the issue is closed, the issue is recorded in the release ledger, so [`ait release-notify`](#ait-release-notify) can later tell it which release ships the fix. GitHub and GitLab issues are recorded; `--dry-run` records nothing. The last stdout line reports the outcome:

| Line | Meaning |
|------|---------|
| `RELEASE_LEDGER:recorded:<path>` | Recorded and committed by this run |
| `RELEASE_LEDGER:duplicate:<path>` | Already recorded for this task and issue |
| `RELEASE_LEDGER:skipped:unsupported_platform` | Not a GitHub or GitLab issue |
| `RELEASE_LEDGER_FAILED:<reason>` | The issue was updated, but the entry was not recorded (exit status 3) |

| Exit status | Meaning |
|-------------|---------|
| `0` | Done |
| `1` | Failed before or during the platform call; nothing was recorded |
| `3` | The issue **was** updated, but its ledger entry was not recorded. Do not re-run the command, which would post the comment again: run the `--record-only` command printed on stderr |

---

## ait release-notify

Comment "Released in vX.Y.Z" on every resolved issue whose fix ships in a release, then move its ledger record to the release's history. In the aitasks repository itself this runs automatically at the end of `./create_new_release.sh` (see [Releases]({{< relref "/docs/workflows/releases" >}})).

```bash
ait release-notify --dry-run              # What would be posted for the latest v* tag
ait release-notify --tag v1.4.0           # Notify the issues fixed in v1.4.0
ait release-notify --list                 # Pending records and the per-release history
```

| Option | Description |
|--------|-------------|
| `--tag T` | The release tag (default: the latest `v*` tag) |
| `--prev-tag P` | The previous release tag (default: the next lower `v*` tag; with none, all history up to `T`) |
| `--dry-run` | Report what would be posted and the state of every gate below; change nothing |
| `--list` | List pending records, then the released records grouped by tag |
| `--no-push` | Do not push the task data at the end |

### The release ledger

Every successful `ait issue-update` adds one record file under `aitasks/metadata/release_issues/pending/`, committed with the task data. A record holds the task id, the issue URL, the platform, the action (`closed`, `commented` or `closed_silent`) and when it was recorded. The ledger is rolling: a record stays pending until a release actually contains its task's commits.

For each pending record, `ait release-notify` looks for the task's commits in `<prev-tag>..<tag>`. A parent task `tP` matches the commit tags `(tP)` and `(tP_<n>)`; a child task `tP_C` matches `(tP_C)` only. Then:

- **Due:** a commit is in the range. The issue gets one comment, with a hidden marker (`<!-- aitask-release:<tag> t<id> -->`), a link to the release page and the task's commits in the release. The record moves to `released/<tag>/`, with the tag, the time, the outcome and the commit ids added, in one commit.
- **Already notified:** the marker is already on the issue. Nothing is posted; the record moves with outcome `already_present`.
- **Shipped earlier:** the commits are all in an older release, so this range is not the one that shipped them. The record stays pending and the exact command to notify it is printed, `ait release-notify --tag <that release>`. Nothing catches these up automatically.
- **Pending:** no commit is in the tag yet. The record waits for a later release.

### The posting gate

A run that may post goes through these checks in order, and posts nothing unless all of them pass:

1. **Fresh task data.** The task-data branch is fetched and must not be behind its remote. A failed fetch, or a count that cannot be established, counts as not fresh.
2. **The publication policy can be read** (see below).
3. **The designated machine.** `hostname` must equal `release_notify_host`.
4. **The local run lock.** Only one run at a time on the machine.
5. **Interrupted moves are completed.** A run that died between posting a comment and committing the move leaves its traces in the ledger. They are completed now, without a new comment. Traces that do not match the record in git are left as they are and reported for a human, and that record is not processed.
6. **The release is published,** under the project's publication policy.

A failed check prints `INCOMPLETE:<check>:<state>` with a `HINT:` line, keeps every record pending, and exits with status 3. `--dry-run` reports the same states as `FRESHNESS:`, `DESIGNATION:` and `PUBLICATION:` lines, without requiring them.

The release must exist as a platform release (GitHub release, GitLab release). A project that only pushes tags never gets release notices, because the comment links to the release page.

### Publication policy

The checks a release must pass are set per project, in `aitasks/metadata/project_config.yaml`. With none of these keys, a release only has to exist, match the tag, and not be a draft (GitHub) or upcoming (GitLab).

| Key | Meaning |
|-----|---------|
| `release_publication_workflow` | GitHub only: a workflow file whose run for the tag and the tagged commit must have concluded `success`. Set on a GitLab project, it blocks posting |
| `release_publication_assets` | Asset names that must be uploaded, non-empty release assets. A string or a list; only `{tag}` and `{version}` (the tag without a leading `v`) may appear |
| `release_publication_checksum_manifests` | Globs of `sha256sum` manifests among the assets. Every file a matching manifest lists must itself be a published asset |

```yaml
release_notify_host: build-box
release_publication_workflow: release.yml
release_publication_assets:
  - myapp-{tag}.tar.gz
  - myapp_{version}_amd64.deb
release_publication_checksum_manifests: "*_SHA256SUMS.txt"
```

The file is read with a real YAML parser, so quoted keys and flow mappings count the same as plain keys. A template with braces inside a flow list must be quoted (`["myapp-{tag}.tar.gz"]`). A value of the wrong type, an unknown placeholder, a duplicated key, or no Python interpreter to read the file is reported as `policy_unreadable` and blocks posting. It never falls back to the generic checks.

### The designated machine

`release_notify_host` names the one machine that posts, compared byte-for-byte with `hostname`. With the key unset, no machine posts, and the hint shows the line that designates the current one. There is no distributed lock and no automatic failover. To move notifications to another machine:

1. Make sure no `ait release-notify` (or release wrapper) run is in progress on the old machine.
2. Set the new hostname with `ait settings`, or edit `aitasks/metadata/project_config.yaml` and commit it with `./.aitask-scripts/aitask_metadata_commit.sh aitasks/metadata/project_config.yaml`.
3. Run `./ait sync` on both machines.

### Duplicate comments

The run lock, the marker check before each post, and the one-commit move of each record prevent duplicate comments for runs on the designated machine, one at a time, and for sequential retries, including a retry after a run died between a post and its record move. This is not an exactly-once guarantee. A duplicate is still possible when:

- runs on two machines overlap, because the designation was bypassed or reassigned mid-run;
- a retry follows so quickly that the platform's comment listing does not show the comment just posted;
- someone edits or deletes a marker comment by hand.

### Output and exit status

Each line starts with a key: `RANGE:`, `FRESHNESS:`, `DESIGNATION:`, `PUBLICATION:`, `RESIDUE:`, `RESUMED:`, `DUE:`, `POSTED:`, `ALREADY_NOTIFIED:`, `PENDING:`, `SHIPPED_EARLIER:`, `FAILED:`, `MALFORMED:`, `INCOMPLETE:`, `HINT:`, `PUSH:` and a final `SUMMARY:`.

| Exit status | Meaning |
|-------------|---------|
| `0` | Complete |
| `1` | Usage error |
| `2` | Refused input: a missing or invalid tag |
| `3` | Incomplete: a gate check failed and nothing was posted |
| `4` | Partial: at least one record `FAILED` or is `MALFORMED`. Re-running is safe: only what is still pending is processed |

---

## ait changelog

Gather changelog data from git commits and archived task plans. Used by the `/aitask-changelog` skill to generate CHANGELOG.md entries. No interactive mode — output-oriented data gatherer.

```bash
ait changelog --gather                        # Gather all task data since last release
ait changelog --gather --from-tag v0.1.1      # Gather from a specific tag
ait changelog --check-version 0.2.0           # Check if changelog has entry for v0.2.0
```

| Option | Description |
|--------|-------------|
| `--gather` | Output structured data for all tasks since last release tag |
| `--check-version VERSION` | Check if CHANGELOG.md has a `## vVERSION` section (exit 0 if found, 1 if not) |
| `--from-tag TAG` | Override the base tag (default: auto-detect latest semver tag) |

**Output format** for `--gather`:

```
BASE_TAG: v0.1.2

=== TASK t89 ===
ISSUE_TYPE: feature
TITLE: detect capable terminal on windows
PLAN_FILE: aiplans/archived/p89_detect_capable_terminal_on_windows.md
NOTES:
- **Actual work done:** ...
COMMITS:
1c7aac4 Add terminal capability detection (t89)
=== END ===
```

Each task section includes: issue type (from task frontmatter), human-readable title (from filename), plan file path, "Final Implementation Notes" extracted from the plan, and associated commits.

**Key features:**
- Semver tag detection (`v*` tags, sorted by version)
- Task ID extraction from parenthesized `(tNN)` and `(tNN_MM)` patterns in commit messages
- Plan file resolution via shared `task_utils.sh` (checks active and archived directories)
- `--check-version` used by `create_new_release.sh` to verify changelog completeness before release
- Falls back to showing raw commits when no task-tagged commits are found

---

## ait zip-old

Archive old completed task and plan files to compressed `tar.zst` archives.

This is **periodic maintenance** — run it from time to time (a natural cadence
is right after a release) to keep `aitasks/archived/` and `aiplans/archived/`
tidy. See the [Repository Maintenance]({{< relref "/docs/workflows/repo-maintenance" >}})
workflow for the full set of upkeep commands.

```bash
ait zip-old                    # Archive and commit
ait zip-old --dry-run          # Preview what would be archived
ait zip-old --no-commit        # Archive without git commit
ait zip-old -v                 # Verbose output
```

| Option | Description |
|--------|-------------|
| `-n, --dry-run` | Preview what would be archived without making changes |
| `--no-commit` | Archive files but don't commit to git |
| `-v, --verbose` | Show detailed progress (files added/removed) |

**How it works:**

1. Scans `aitasks/archived/` and `aiplans/archived/` for parent and child files
2. Keeps the most recent parent file and most recent child (per parent) uncompressed — this preserves task numbering for `ait create`
3. Groups eligible files by 100-task bundles and archives each group to a numbered archive:
   - **Bundle** = `task_id / 100` (integer division)
   - **Directory** = `bundle / 10` (integer division)
   - **Path** = `archived/_b{dir}/old{bundle}.tar.zst`
   - Example: task 150 → `archived/_b0/old1.tar.zst`, task 1050 → `archived/_b1/old10.tar.zst`
4. If a numbered archive already exists, merges new files into it
5. Verifies archive integrity before deleting originals
6. If an existing archive is corrupted, creates a backup before starting fresh
7. Removes empty child directories after archiving
8. Commits changes to git (unless `--no-commit`)

---

**Next:** [PR Import]({{< relref "/docs/commands/pr-import" >}})

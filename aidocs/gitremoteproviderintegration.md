# Git Remote Provider Integration Guide

How to add support for a new git remote provider (e.g., Bitbucket) to the aitasks framework.

## Architecture Overview

The aitasks framework uses a **platform-extensible dispatcher pattern**. Each bash script that interacts with a git hosting platform implements:

1. **Backend functions** — platform-specific implementations (e.g., `github_fetch_issue()`, `gitlab_fetch_issue()`)
2. **Dispatcher functions** — `case` statements that route to the correct backend based on the `SOURCE` variable
3. **Auto-detection** — determines the platform from git remote URL or issue URL

All backends produce **normalized JSON** matching the GitHub field structure, so consumer code works unchanged regardless of platform.

## Extension Checklist

### 1. Platform Detection — `aiscripts/lib/task_utils.sh`

Add URL patterns for the new provider to both detection functions:

- **`detect_platform()`** — detects from git remote URL (used by issue-import and setup)
- **`detect_platform_from_url()`** — detects from issue/web URL (used by issue-update)

Add a new `elif` branch matching the provider's hostname pattern.

### 2. Issue Import — `aiscripts/aitask_issue_import.sh`

Implement **7 backend functions**:

| Function | Purpose | Notes |
|----------|---------|-------|
| `<platform>_check_cli()` | Verify CLI tool installed and authenticated | Check `command -v` and auth status |
| `<platform>_fetch_issue()` | Fetch single issue as normalized JSON | Must normalize to GitHub field structure (see JSON table below) |
| `<platform>_format_comments()` | Format comments as text | Can reuse `github_format_comments()` if JSON is normalized |
| `<platform>_list_issues()` | List all open issues as normalized JSON array | Fields: `number`, `title`, `labels[{name}]`, `url` |
| `<platform>_map_labels()` | Map labels JSON to comma-separated string | Can reuse `github_map_labels()` if labels are normalized |
| `<platform>_detect_type()` | Detect issue type from labels | Can reuse `github_detect_type()` if labels are normalized |
| `<platform>_preview_issue()` | Print issue preview to stdout | Used in interactive mode |

Then wire up:
- Add `<platform>)` case to **7 dispatcher functions**: `source_check_cli`, `source_fetch_issue`, `source_list_issues`, `source_map_labels`, `source_detect_type`, `source_preview_issue`, `source_format_comments`
- Add `<platform>)` to the validation `case` in `parse_args()`

### 3. Issue Update — `aiscripts/aitask_issue_update.sh`

Implement **5 backend functions**:

| Function | Purpose | Notes |
|----------|---------|-------|
| `<platform>_check_cli()` | Verify CLI tool installed and authenticated | Same as import |
| `<platform>_extract_issue_number()` | Extract issue number from URL | Parse the URL format specific to the platform |
| `<platform>_get_issue_status()` | Get current issue state | Must normalize to `OPEN`/`CLOSED` |
| `<platform>_add_comment()` | Post a comment on an issue | |
| `<platform>_close_issue()` | Close an issue with optional comment | Note: some CLIs don't support `--comment` on close (GitLab requires separate note + close) |

Then wire up:
- Add `<platform>)` case to **5 dispatcher functions**: `source_check_cli`, `source_extract_issue_number`, `source_get_issue_status`, `source_add_comment`, `source_close_issue`
- Add `<platform>)` to the validation `case` in `parse_args()`

### 4. Setup — `aiscripts/aitask_setup.sh`

- Add the new provider's hostname to `_detect_git_platform()` (inline detection function)
- Add CLI tool name to the `case "$platform"` block in `install_cli_tools()`
- Add OS-specific installation commands for each supported OS:
  - **Arch Linux**: package name for `pacman`
  - **Debian/Ubuntu**: APT package or `.deb` download from releases
  - **Fedora**: package name for `dnf`
  - **macOS**: Homebrew formula name

### 5. Documentation

- **`README.md`**: Add authentication instructions under "Authentication with Your Git Remote"
- **`docs/commands.md`**: Update `ait issue-import` and `ait issue-update` sections to mention the new platform
- **Help text**: Update `show_help()` in both `aitask_issue_import.sh` and `aitask_issue_update.sh` — update `--source` description

## JSON Normalization Reference

All backends must normalize their API responses to match this GitHub-compatible structure.

### Single Issue (`*_fetch_issue`)

```json
{
  "title": "Issue title",
  "body": "Issue description/body text",
  "labels": [{"name": "bug"}, {"name": "priority-high"}],
  "url": "https://platform.com/owner/repo/issues/123",
  "comments": [
    {
      "author": {"login": "username"},
      "body": "Comment text",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  ],
  "createdAt": "2024-01-10T09:00:00Z",
  "updatedAt": "2024-01-15T10:30:00Z"
}
```

### Issue List (`*_list_issues`)

```json
[
  {
    "number": 123,
    "title": "Issue title",
    "labels": [{"name": "bug"}],
    "url": "https://platform.com/owner/repo/issues/123"
  }
]
```

### Field Mapping Examples

| Normalized field | GitHub (`gh`) | GitLab (`glab`) |
|-----------------|---------------|-----------------|
| `.body` | `.body` | `.description` |
| `.url` | `.url` | `.web_url` |
| `.labels[].name` | `.labels[].name` (objects) | `.labels[]` (strings, wrap in `{name: .}`) |
| `.createdAt` | `.createdAt` | `.created_at` |
| `.updatedAt` | `.updatedAt` | `.updated_at` |
| `.comments[].author.login` | `.comments[].author.login` | `.notes[].author.username` (filter `system != true`) |
| `.number` (list) | `.number` | `.iid` |
| Issue state | `OPEN`/`CLOSED` | `opened`/`closed` (normalize to uppercase) |

## Auto-Detection Flow

**Issue import** (`aitask_issue_import.sh`):
1. If `--source` provided → use it
2. Else → `detect_platform()` from git remote URL
3. If still empty → die with supported platforms list

**Issue update** (`aitask_issue_update.sh`):
1. If `--source` provided → use it
2. Else → `detect_platform_from_url()` from the task's `issue` field URL
3. If still empty → `detect_platform()` from git remote as fallback
4. If still empty → die with error

## Common Pitfalls

- **Close with comment**: Not all CLIs support `--comment` on close commands. Check the CLI docs and implement a two-step approach (post comment, then close) if needed.
- **JSON field names**: Different platforms use different field names for the same data. Always normalize in the `*_fetch_issue` and `*_list_issues` functions.
- **Label formats**: Some platforms return labels as strings, others as objects. Normalize to `[{name: "label_name"}]`.
- **Issue numbers**: Some platforms use `iid` (project-scoped) vs `id` (global). Use the project-scoped number.
- **Pagination**: When listing issues, ensure pagination is handled (some CLIs have `--paginate` flags, others need manual page iteration).
- **System notes**: Some platforms include system-generated notes (e.g., "changed status") in the notes/comments API. Filter these out (e.g., GitLab: `select(.system != true)`).

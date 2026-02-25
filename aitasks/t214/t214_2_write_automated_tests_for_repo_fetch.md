---
priority: high
effort: medium
depends: [t214_1]
issue_type: test
status: Ready
labels: [portability, shell, testing]
created_at: 2026-02-25 12:13
updated_at: 2026-02-25 12:13
---

## Context

This is child task 2 of t214 (Multi-platform reviewguide import and setup dedup). The sibling task t214_1 creates `aiscripts/lib/repo_fetch.sh` with functions for multi-platform URL parsing, file fetching, and directory listing. This task creates automated tests for that library.

## Key Files to Create

- `tests/test_repo_fetch.sh` — Automated test file

## Reference Files for Patterns

- `tests/test_claim_id.sh`, `tests/test_detect_env.sh` — Existing test file patterns with `assert_eq`/`assert_contains` helpers
- `aiscripts/lib/repo_fetch.sh` (created by t214_1) — The library being tested

## Test Repos (stable, public, official)

| Platform | Repo | Branch | Purpose |
|----------|------|--------|---------|
| GitHub | `cli/cli` | `trunk` | Official GitHub CLI — extremely stable |
| GitLab | `gitlab-org/gitlab` | `master` | GitLab's own monorepo |
| Bitbucket | `tutorials/markdowndemo` | `master` | Atlassian's markdown tutorial (single file test) |
| Bitbucket | `atlassian/aws-s3-deploy` | `master` | Atlassian pipe (directory listing test) |

## Implementation Plan

### Test structure

Follow existing test conventions: self-contained script, `assert_eq`/`assert_contains` helpers, PASS/FAIL summary.

### Test cases

**Offline tests (URL parsing/detection — no network needed):**
1. `test_detect_platform_github` — `https://github.com/cli/cli/blob/trunk/README.md` → `github`
2. `test_detect_platform_gitlab` — `https://gitlab.com/gitlab-org/gitlab/-/blob/master/README.md` → `gitlab`
3. `test_detect_platform_bitbucket` — `https://bitbucket.org/tutorials/markdowndemo/src/master/README.md` → `bitbucket`
4. `test_detect_platform_unknown` — `https://example.com/foo` → empty string
5. `test_parse_url_github_file` — parse GitHub blob URL → owner=cli, repo=cli, branch=trunk, path=README.md, type=file
6. `test_parse_url_gitlab_file` — parse GitLab blob URL → owner=gitlab-org, repo=gitlab, branch=master, path=README.md, type=file
7. `test_parse_url_bitbucket_file` — parse Bitbucket src URL with .md → owner=tutorials, repo=markdowndemo, branch=master, path=README.md, type=file
8. `test_parse_url_github_dir` — parse GitHub tree URL → type=directory
9. `test_parse_url_gitlab_dir` — parse GitLab tree URL → type=directory
10. `test_parse_url_bitbucket_dir` — parse Bitbucket src URL without extension → type=directory
11. `test_parse_url_nested_path` — parse URL with nested path like `doc/api/markdown.md` → path correctly extracted

**Network tests (require internet + CLI tools, gated by SKIP_NETWORK=1):**
12. `test_fetch_file_github` — fetch cli/cli README.md, assert contains "GitHub CLI"
13. `test_fetch_file_gitlab` — fetch gitlab-org/gitlab README.md, assert contains "GitLab"
14. `test_fetch_file_bitbucket` — fetch tutorials/markdowndemo README.md, assert contains "Markdown"
15. `test_list_md_github` — list cli/cli/docs, assert count > 0
16. `test_list_md_gitlab` — list gitlab-org/gitlab/doc/api, assert count > 0
17. `test_list_md_bitbucket` — list atlassian/aws-s3-deploy root, assert contains "README.md"

### Guard for network tests
```bash
if [[ "${SKIP_NETWORK:-0}" == "1" ]]; then
    echo "SKIP: $test_name (network tests disabled)"
    return 0
fi
```

## Verification Steps

1. `bash tests/test_repo_fetch.sh` — all tests pass
2. `SKIP_NETWORK=1 bash tests/test_repo_fetch.sh` — offline tests pass, network tests skipped
3. `shellcheck tests/test_repo_fetch.sh`

---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [git-integration, contribution]
anchor: 2235
created_at: 2026-11-08 22:04
updated_at: 2026-11-08 22:04
---

## Context

Bitbucket Cloud's native issue tracker no longer exists. The Atlassian Bitbucket Cloud changelog
(https://developer.atlassian.com/cloud/bitbucket/changelog/) entry of 20 August 2026,
"Removal of native Bitbucket Cloud Issue tracker", states that "the API endpoints that support
Issue Tracker are now fully removed". The Community announcement "Announcing sunset of Bitbucket
Issues and Wikis"
(https://community.atlassian.com/forums/Bitbucket-articles/Announcing-sunset-of-Bitbucket-Issues-and-Wikis/ba-p/3193882)
says Issues and Wikis were removed from the app and the API, and that issues migrate to Jira Cloud.
Bitbucket Server/Data Center never had native issues.

Every `api.bitbucket.org/2.0/repositories/<ws>/<slug>/issues…` call in the framework therefore
targets a removed API.

t2247 (found while fixing the Bitbucket contribution scan) retired the **contribution-check**
part only:
- the Bitbucket backend of `aitask_contribution_check.sh` / `aitask_contribution_review.sh` now
  fails with a clear "issue tracker removed" message;
- the Bitbucket CI template is gone, and `ait setup` no longer installs it, and warns when an
  existing `bitbucket-pipelines.yml` still runs the check;
- the contribution-flow doc page is updated.

This task covers the rest.

## Inventory (verify each before editing; this is a starting list, not a guarantee of completeness)

- `.aitask-scripts/aitask_contribute.sh`: `bitbucket_check_cli`, `bitbucket_upstream_url`,
  `bitbucket_resolve_contributor`, `bitbucket_create_issue`, and the help text
  ("creates GitHub/GitLab/Bitbucket issues").
- `.aitask-scripts/aitask_issue_import.sh`: the `bitbucket_*` issue backend (fetch, list,
  comments, labels, type detection) and `--source bitbucket`.
- `.aitask-scripts/aitask_issue_update.sh`: the `bitbucket_*` backend (status, comment, close) and
  `bitbucket.org/<ws>/<repo>/issues/<n>` URL parsing.
- `lib/task_utils.sh`, `lib/repo_fetch.sh`: check for Bitbucket *issue* helpers; repo / PR /
  remote helpers stay.
- The board's "BB" issue indicator (`board/board_widgets.py`;
  `tests/test_textual_markup_structure.py` asserts `bitbucket.org/.../issues/7` → "BB"). Decide
  what an existing task's `issue:` URL on bitbucket.org should show.
- `ait setup`: does it still install the `bkt` CLI only for issue work? Check what bkt is used for
  (PRs?) before touching it.
- Skills: `.claude/skills/aitask-contribute/SKILL.md`,
  `.claude/skills/aitask-contribution-review/SKILL.md` (Bitbucket mentions). Port to the other
  agent trees per CLAUDE.md.
- Website pages that present Bitbucket issues as supported: `docs/commands/issue-integration.md`,
  `docs/workflows/issue-tracker.md`, `docs/skills/aitask-contribute.md`,
  `docs/workflows/contribute-and-manage/_index.md`, `docs/development/task-format.md`,
  `docs/tuis/board/_index.md` and `how-to.md`, `docs/commands/_index.md`, `docs/overview.md`.
  Current-state prose only (`aidocs/framework/documentation_conventions.md`). Run
  `check_links.py --build`.

## Boundary

- Bitbucket **pull requests** (`aitask_pr_import.sh`, `aitask_pr_close.sh`), remote detection, git
  auth and locking/sync over a Bitbucket remote are unaffected and stay.
- Existing-user behaviour to decide: a task whose frontmatter `issue:` points at a bitbucket.org
  issue URL. `ait issue-update` should fail clearly (not silently) and must not block archival.

## Out of scope

A replacement integration (e.g. Jira Cloud, where Atlassian migrates Bitbucket issues) is a
separate design decision for its own task. Do not build it here.

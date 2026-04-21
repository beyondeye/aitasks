---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [docs, website]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-21 16:35
updated_at: 2026-04-21 16:45
---

## Problem

Five docs pages under `website/content/docs/concepts/` link to the aitasks source on GitHub using the wrong owner: `github.com/dario-elyasy/aitasks/...`. The correct owner is `beyondeye` (confirmed by `website/hugo.toml` `github_repo`, `website/go.mod` module path, `website/content/_index.md` install snippet, and all blog release-post URLs).

## Wrong occurrences (7 links across 5 files)

- `website/content/docs/concepts/plans.md:19` — `task-workflow/planning.md`
- `website/content/docs/concepts/git-branching-model.md:28` — `task-workflow/repo-structure.md`
- `website/content/docs/concepts/agent-memory.md:25` — `.aitask-scripts/aitask_query_files.sh`
- `website/content/docs/concepts/agent-attribution.md:25` — `task-workflow/agent-attribution.md` and `task-workflow/model-self-detection.md` (two links on the same line)
- `website/content/docs/concepts/task-lifecycle.md:30` — `aitask_pick_own.sh`, `aitask_archive.sh`, and `task-workflow/task-abort.md` (three links on the same line)

## Fix

Replace `github.com/dario-elyasy/aitasks` with `github.com/beyondeye/aitasks` across the five files above. No other text changes. No occurrences exist outside `website/`.

## Verification

- `grep -r "dario-elyasy" website/` returns nothing after the fix.
- The linked paths resolve on `https://github.com/beyondeye/aitasks/blob/main/...` (paths themselves are already correct — only the owner segment is wrong).
- Optional spot-check: `hugo build --gc --minify` (from `website/`) still succeeds.

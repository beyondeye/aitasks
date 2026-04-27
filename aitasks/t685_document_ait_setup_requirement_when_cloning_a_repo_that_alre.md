---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_setup, web_site]
issue: https://github.com/beyondeye/aitasks/issues/11
created_at: 2026-04-27 22:29
updated_at: 2026-04-27 22:29
---

Issue created: 2026-04-27 22:15:15

## Document `ait setup` requirement when cloning a repo that already uses aitasks

## Problem

When a user clones a repository that already has aitasks installed in
data-branch mode, the framework appears "empty" until `ait setup` is run.
The website does not currently document this post-clone step, so users hit
the failure mode below before they understand what's missing.

## Symptoms (observed on a fresh clone of an aitasks-enabled repo)

- `aitasks/` directory exists but contains only an empty `metadata/`
  subdirectory — no task files visible.
- `git board` / `./ait board` shows no tasks.
- `./ait git-health` reports:
  `Mode: legacy (no separate .aitask-data worktree) — nothing to check.`
- The remote does have an `aitask-data` branch (visible via
  `git branch -a`), but it is not checked out anywhere locally.

## Fix

Run `./ait setup` (use `./ait` rather than `ait` since the shim may not
be on PATH on a fresh clone). This:
1. Fetches the remote `aitask-data` branch.
2. Creates the `.aitask-data/` git worktree checked out at that branch.
3. Replaces `aitasks/` and `aiplans/` with symlinks into the worktree.
4. Initializes `userconfig.yaml` and other per-user state.

## Request

Add a "Cloning a repo that already uses aitasks" section to the install /
getting-started docs on the website, calling out:
- The post-clone `./ait setup` requirement.
- Use `./ait` not `ait` on a fresh clone.
- The exact symptoms above so users can recognize the situation in search.

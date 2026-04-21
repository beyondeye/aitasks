---
Task: t620_fix_wrong_github_username_in_website_docs.md
Worktree: (none — working on current branch per `fast` profile `create_worktree: false`)
Branch: main
Base branch: main
---

# Plan: Fix wrong GitHub username in website docs (t620)

## Context

Five docs pages under `website/content/docs/concepts/` link to the aitasks source on GitHub using the wrong owner segment: `github.com/dario-elyasy/aitasks/...`. The correct owner is `beyondeye`, confirmed by the already-correct references in:

- `website/hugo.toml` → `github_repo = "https://github.com/beyondeye/aitasks"` and `github_project_repo = "https://github.com/beyondeye/aitasks"`
- `website/go.mod` → `module github.com/beyondeye/aitasks/website`
- `website/content/_index.md` → repo button and install-snippet URL both use `beyondeye/aitasks`
- Every entry under `website/content/blog/` → release links use `github.com/beyondeye/aitasks/releases/tag/…`

The Docsy-rendered "View page source" link also uses `github_repo` from `hugo.toml`, so this bug is isolated to prose links authored inside the concept pages — not the chrome.

Exploration (`Grep "dario-elyasy"` across the entire repo) shows the wrong URL appears only in the five files below, a total of seven link occurrences. No code, config, or other markdown references it.

## Scope — exact occurrences

| File | Line | Wrong links on that line |
|---|---|---|
| `website/content/docs/concepts/plans.md` | 19 | 1 (`task-workflow/planning.md`) |
| `website/content/docs/concepts/git-branching-model.md` | 28 | 1 (`task-workflow/repo-structure.md`) |
| `website/content/docs/concepts/agent-memory.md` | 25 | 1 (`.aitask-scripts/aitask_query_files.sh`) |
| `website/content/docs/concepts/agent-attribution.md` | 25 | 2 (`task-workflow/agent-attribution.md`, `task-workflow/model-self-detection.md`) |
| `website/content/docs/concepts/task-lifecycle.md` | 30 | 3 (`aitask_pick_own.sh`, `aitask_archive.sh`, `task-workflow/task-abort.md`) |

Total: 7 link occurrences across 5 files. The path portion after the owner/repo is correct in every case — **only the owner segment is wrong**.

## Approach

A straight find-and-replace across the five files:

- **Wrong:** `github.com/dario-elyasy/aitasks`
- **Correct:** `github.com/beyondeye/aitasks`

This is a safe substitution because:
- The substring `dario-elyasy` appears nowhere else in the repo (verified).
- The replacement keeps the `github.com/<owner>/aitasks` shape, so every link path after it resolves unchanged on the correct repo.
- No link text (the part in `[...]`) references the wrong owner — only the URL bodies.

Use `Edit` with `replace_all: true` on each file, matching the substring `github.com/dario-elyasy/aitasks` → `github.com/beyondeye/aitasks`. Five edits, one per file.

## Files to modify

- `website/content/docs/concepts/plans.md`
- `website/content/docs/concepts/git-branching-model.md`
- `website/content/docs/concepts/agent-memory.md`
- `website/content/docs/concepts/agent-attribution.md`
- `website/content/docs/concepts/task-lifecycle.md`

## Non-goals (explicitly out of scope)

- No rewording of the surrounding prose.
- No change to anchor text or link structure.
- No sweep of blog posts, `hugo.toml`, `go.mod`, or `_index.md` — those already use the correct owner.
- No broken-link audit beyond the `dario-elyasy → beyondeye` fix.
- No change to the Docsy "view page source" chrome (driven by `hugo.toml`, already correct).

## Implementation steps

1. Apply the substring replacement to each of the 5 files listed above via `Edit` with `replace_all: true`.
2. Verify: re-run `Grep "dario-elyasy"` across the repo — expect zero matches.
3. Verify: re-run `Grep "github.com/beyondeye/aitasks"` on the 5 files — expect the corresponding link counts (1, 1, 1, 2, 3).
4. Show a `git status` / `git diff --stat` to the user in Step 8.

## Verification

- `grep -r "dario-elyasy" .` (excluding `.git`) returns zero matches.
- Each of the 5 edited files now contains `github.com/beyondeye/aitasks` in place of the wrong owner, with the correct per-file count (plans.md: 1, git-branching-model.md: 1, agent-memory.md: 1, agent-attribution.md: 2, task-lifecycle.md: 3).
- Spot-check one fixed URL (e.g., `https://github.com/beyondeye/aitasks/blob/main/.claude/skills/task-workflow/planning.md`) — it should resolve to a real file on the `beyondeye/aitasks` repo on GitHub.
- Optional: `cd website && hugo build --gc --minify` still succeeds (pure-text change, unlikely to break the build, but cheap to confirm).

## Step 9 (Post-Implementation)

Per the task-workflow skill: after user approval in Step 8 and commit, proceed to Step 9 (archival via `aitask_archive.sh 620`) and Step 9b (satisfaction feedback).

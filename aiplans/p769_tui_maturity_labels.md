---
Task: t769_tui_maturity_labels.md
Base branch: main
plan_verified: []
---

## Context

The website's `maturity:` taxonomy values (frontmatter on TUI and skill pages) are out of date relative to the user's current view of project maturity. The user dictated the correct value for every TUI and every skill in t769's description. Several skill pages also have **no** `maturity:` line at all and need one added.

This task is purely YAML-frontmatter edits in `website/content/docs/`. No code, no behavior change, no tests. Hugo's `[taxonomies]` is dynamic, so introducing a new term value `stable` (not currently used anywhere) requires no schema change.

## Maturity matrix (target → current)

### TUIs (`website/content/docs/tuis/`)

| TUI | Target | Files | Current |
|---|---|---|---|
| board (kanban) | `stable` | `board/_index.md`, `board/how-to.md`, `board/reference.md` | `stabilizing` |
| codebrowser | `stable` | `codebrowser/_index.md`, `codebrowser/how-to.md`, `codebrowser/reference.md` | `stabilizing` |
| monitor | `stable` | `monitor/_index.md`, `monitor/how-to.md`, `monitor/reference.md` | `stabilizing` |
| minimonitor | `stable` | `minimonitor/_index.md`, `minimonitor/how-to.md` | (no maturity — ADD) |
| settings | `stable` | `settings/_index.md`, `settings/how-to.md`, `settings/reference.md` | `stabilizing` |
| stats | `stabilizing` | `stats/_index.md` | `experimental` |
| syncer | `stabilizing` | `syncer/_index.md` | `stabilizing` (no change) |

### Skills (`website/content/docs/skills/`)

| Skill | Target | File | Current |
|---|---|---|---|
| pick | `stable` | `aitask-pick/_index.md` | (no maturity — ADD) |
| pickrem | `experimental` | `aitask-pickrem.md` | `stabilizing` |
| pickweb | `experimental` | `aitask-pickweb.md` | `stabilizing` |
| web-merge | `experimental` | `aitask-web-merge.md` | (no maturity — ADD) |
| explore | `stable` | `aitask-explore.md` | `stabilizing` |
| pr-import | `stable` | `aitask-pr-import.md` | (no maturity — ADD) |
| contribute | `stable` | `aitask-contribute.md` | (no maturity — ADD) |
| contribution-review | `stable` | `aitask-contribution-review.md` | (no maturity — ADD) |
| fold | `stable` | `aitask-fold.md` | `stabilizing` |
| revert | `stable` | `aitask-revert.md` | (no maturity — ADD) |
| create | `stable` | `aitask-create.md` | (no maturity — ADD) |
| wrap | `stable` | `aitask-wrap.md` | (no maturity — ADD) |
| stats | `stable` | `aitask-stats.md` | `experimental` |
| explain | `stable` | `aitask-explain.md` | (no maturity — ADD) |
| refresh-code-models | `stabilizing` | `aitask-refresh-code-models.md` | (no maturity — ADD) |
| add-model | `stabilizing` | `aitask-add-model.md` | `experimental` |
| changelog | `stable` | `aitask-changelog.md` | (no maturity — ADD) |
| review | `stable` | `aitask-review.md` | (no maturity — ADD) |
| qa | `stabilizing` | `aitask-qa.md` | (no maturity — ADD) |
| reviewguide-classify | `stabilizing` | `aitask-reviewguide-classify.md` | (no maturity — ADD) |
| reviewguide-import | `stabilizing` | `aitask-reviewguide-import.md` | (no maturity — ADD) |
| reviewguide-merge | `stabilizing` | `aitask-reviewguide-merge.md` | (no maturity — ADD) |

## Implementation

For each file in the matrices above:

- **If a `maturity:` line already exists**, replace its value with the target list value (`maturity: [stable]` / `[stabilizing]` / `[experimental]`).
- **If no `maturity:` line exists**, insert a new line `maturity: [<target>]` inside the YAML frontmatter, immediately above the `depth:` line if present, otherwise immediately before the closing `---`. Match the formatting of neighboring frontmatter pages (e.g., `aitask-pickrem.md`).

No other content in any file is touched. Subpages of `aitask-pick/` (`build-verification.md`, `commit-attribution.md`, `execution-profiles.md`) currently have no `maturity:` and remain that way — only the parent `_index.md` is tagged, mirroring the existing skill pattern of one maturity tag per skill (the same applies to monitor: `_index.md` is the index, but monitor _does_ tag its subpages, so we keep that file's existing convention and update all three).

The `syncer/_index.md` row is in the matrix for traceability only — no edit is needed.

## Verification

1. `grep -rH "^maturity:" website/content/docs/tuis/ website/content/docs/skills/` — every row in the matrix above should match its target.
2. `cd website && hugo build --gc --minify` — build must succeed (no taxonomy errors from the new `stable` term).
3. Spot-check one previously-untagged skill (e.g., `aitask-create.md`) and confirm the new line is inside the frontmatter block.

## Step 9 (Post-Implementation)

Standard archival: commit code (this task only edits markdown under `website/content/docs/`), then plan file via `./ait git`, then archive via `./.aitask-scripts/aitask_archive.sh 769`.

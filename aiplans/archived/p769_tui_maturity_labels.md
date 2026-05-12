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

## Post-Review Changes

### Change Request 1 (2026-05-12 12:05)
- **Requested by user:** Reported that several skill pages (aitask-contribute, aitask-contribution-review, aitask-create, aitask-explain) had broken Maturity-label rendering, plus called out aitask-explore / aitask-fold / aitask-stats as "is stable".
- **Investigation:** Source frontmatter was correct on every page (`maturity:` and `depth:` in proper YAML). The broken rendering was reproduced as `<h2 id="th-advanced">th: [advanced]</h2>` in the output HTML, but only for the two pages whose `index.html` files had stale timestamps from before the edits — a partial-build artifact. After `rm -rf website/public/ && hugo build --gc --minify`, every page renders both the sidebar Maturity cloud and the per-article Maturity badge (verified: 2 occurrences of `taxo-maturity` in every skill/TUI page, zero residual stray `<h2 id="th-…">` headings anywhere).
- **Changes made:** No source-file changes were needed. Re-ran a clean Hugo build to flush stale build output.
- **Files affected:** none beyond the original matrix — but `website/public/` was rebuilt.

## Final Implementation Notes

- **Actual work done:** Frontmatter edits in 37 markdown files under `website/content/docs/{tuis,skills}/`, all matching the matrix in this plan. 20 in-place value changes (existing `maturity:` line) and 18 inserts of `maturity: [<value>]` immediately above the `depth:` line on pages that previously had no maturity tag.
- **Deviations from plan:** None. The Hugo `[taxonomies]` block accepted the new term value `stable` without changes (16 pages tagged stable on first build; clean rebuild later corroborated at the expected count of ~27 across all sections).
- **Issues encountered:** During Step 8 review the user observed broken Maturity-label rendering plus a stray `<h2 id="th-advanced">th: [advanced]</h2>` heading on `aitask-contribute` / `aitask-contribution-review`. Source `.md` files were verified clean; root cause was stale incremental-build output in `website/public/`. Resolved by `rm -rf website/public && hugo build --gc --minify` — every page then rendered both the sidebar Maturity cloud and the per-article Maturity badge (2 occurrences of `taxo-maturity` per page, zero `th: [advanced]` stragglers anywhere under `website/public/docs/`).
- **Key decisions:**
  - Introduce the new term value `stable` rather than reusing `stabilizing` for everything; aligns with the task's wording and is well-supported by Hugo's dynamic taxonomy.
  - Tag only `aitask-pick/_index.md`, not the three subpages (`build-verification.md`, `commit-attribution.md`, `execution-profiles.md`) — keeps the existing one-maturity-tag-per-skill convention.
  - Skip `syncer/_index.md` (already `stabilizing` and target was `stabilizing`).
- **Upstream defects identified:** None.


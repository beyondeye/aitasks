---
Task: t243_latest_releases_section_in_website_main_page_not_updated_whe.md
Branch: (current branch)
Base branch: main
---

## Context

After releasing v0.7.0, the "Latest Releases" section on the website landing page (`website/content/_index.md`) still shows v0.6.0 as the latest. The section is hardcoded markdown — `create_new_release.sh` generates the blog post automatically via `new_release_post.sh --auto`, but nobody updates `_index.md`. This is documented as a manual step in `releases.md` but is routinely forgotten.

## Plan

### 1. Add landing page auto-update to `website/new_release_post.sh`

Add two functions after the existing helper functions (after line 27):

**`format_display_date()`** — Converts `YYYY-MM-DD` to `Mon DD, YYYY` (e.g., "Feb 25, 2026"). Uses platform detection (`uname -s`) for macOS BSD vs GNU `date` compatibility.

**`update_landing_page()`** — Updates the "Latest Releases" section in `_index.md`:
- Takes title, slug, release_date as args
- Formats date via `format_display_date()`
- Checks for duplicates (grep for slug in file)
- Uses `awk` to insert new entry before the first `- **[v` line and keep only 3 total entries
- Uses `mktemp` with template pattern (macOS-compatible, per CLAUDE.md conventions)
- Non-fatal: all error paths use `warn` + `return 0`

Call `update_landing_page "$TITLE" "$SLUG" "$RELEASE_DATE"` in the auto-mode block after the blog post is created (after line 229).

Also update the scaffold mode hint (line 268) to note that `--auto` handles this automatically.

### 2. Fix `website/content/_index.md` (one-time fix for v0.7.0)

Replace the 3 release entries with:
- v0.7.0 (new, top)
- v0.6.0 (kept)
- v0.5.0 (kept)
- v0.4.0 (removed)

### 3. Update `create_new_release.sh` to stage `_index.md`

Add `git add website/content/_index.md 2>/dev/null || true` after the existing `git add website/content/blog/` line (line 70).

### 4. Update `website/content/docs/workflows/releases.md`

Update the "Blog Release Post" section step 3 to reflect that `_index.md` is now auto-updated in `--auto` mode.

### 5. Add test script `tests/test_update_landing.sh`

Test the awk logic in isolation using the existing test pattern (`assert_eq`/`assert_contains` helpers, PASS/FAIL summary). Test cases:

- **Normal case (3 existing entries):** Insert new entry at top, remove oldest → result has 3 entries with new at top
- **Fewer than 3 entries:** Insert new entry, keep all existing → result has 2 or 3 entries
- **Duplicate detection:** If slug already in file, skip update
- **Format preservation:** Surrounding Hugo shortcodes and HTML are unchanged after update

The test creates temp `_index.md` files with sample content, runs the awk command, and validates the output.

## Files to modify

- `website/new_release_post.sh` — Add `format_display_date()`, `update_landing_page()`, call in auto-mode
- `website/content/_index.md` — Add v0.7.0, remove v0.4.0
- `create_new_release.sh` — Stage `_index.md` in git add
- `website/content/docs/workflows/releases.md` — Update docs
- `tests/test_update_landing.sh` — New test for the awk landing page update logic

## Verification

1. Run `bash tests/test_update_landing.sh` — all test cases pass
2. Run `cd website && hugo server` and verify v0.7.0 appears on the landing page
3. Verify `format_display_date` output: `date -d "2026-02-25" "+%b %-d, %Y"` → "Feb 25, 2026"

## Final Implementation Notes
- **Actual work done:** All 5 plan items implemented as designed. Added `format_display_date()` and `update_landing_page()` to `new_release_post.sh`, fixed `_index.md` to show v0.7.0, updated `create_new_release.sh` to stage `_index.md`, updated releases workflow docs, and created test script with 29 test assertions.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None. Shellcheck passed clean, all 29 tests pass.
- **Key decisions:** Used awk for the markdown transformation (portable, no Python dependency). The awk pattern `^- \*\*\[v` is distinctive enough to reliably identify release entries. Non-fatal design ensures release process never blocks on a landing page update failure.

## Step 9 (Post-Implementation)
Archive task, push changes.

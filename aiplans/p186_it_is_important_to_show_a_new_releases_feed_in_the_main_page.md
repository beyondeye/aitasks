---
Task: t186_it_is_important_to_show_a_new_releases_feed_in_the_main_page.md
Worktree: (none, working on current branch)
Branch: main
Base branch: main
---

# Plan: Add Releases Blog to Hugo/Docsy Website (t186)

## Context

The aitasks documentation site (Hugo/Docsy) has no blog or release announcement section. Users have no way to discover what changed between releases without visiting GitHub directly. The task is to add a "Releases" blog section with informal summaries of each release, a navbar entry, landing page integration, and a scaffolding script for future releases.

## Steps

### 1. Enable RSS in Hugo config
- [x] **File:** `website/hugo.toml` — Add RSS to output formats

### 2. Create blog section landing page
- [x] **File (new):** `website/content/blog/_index.md`

### 3. Create blog posts for existing releases (v0.2.0–v0.6.0)
- [x] v0.2.0 blog post
- [x] v0.3.0 blog post
- [x] v0.4.0 blog post
- [x] v0.5.0 blog post
- [x] v0.6.0 blog post

### 4. Add "Latest Releases" section to landing page
- [x] **File:** `website/content/_index.md`

### 5. Create blog post scaffolding script
- [x] **File (new):** `website/new_release_post.sh` with `--auto` mode
- [x] Prefers `CHANGELOG_HUMANIZED.md` over `CHANGELOG.md`

### 6. Update release workflow documentation
- [x] **File:** `website/content/docs/workflows/releases.md`

### 7. Integrate into release automation
- [x] **File:** `create_new_release.sh` — Call `new_release_post.sh --auto` before tagging

### 8. Add humanized changelog generation to aitask-changelog skill
- [x] **File:** `.claude/skills/aitask-changelog/SKILL.md` — Steps 7b/7c
- [x] **File (new):** `CHANGELOG_HUMANIZED.md` — Initial entries for v0.2.0–v0.6.0

### 9. macOS compatibility
- [x] Replace `grep -oP` (PCRE) with portable `grep -o | sed` in `new_release_post.sh`
- [x] Document `grep -P` macOS incompatibility in `CLAUDE.md` and `aidocs/sed_macos_issues.md`

## Verification

1. [x] `hugo build --gc --minify` succeeds (67 pages, no errors)
2. [x] RSS feed generated at `public/blog/index.xml`
3. [x] `./website/new_release_post.sh 0.1.0` scaffolding works correctly
4. [x] `./website/new_release_post.sh --auto 0.6.0` correctly detects existing post and skips
5. [x] shellcheck clean on `new_release_post.sh`
6. [x] No `grep -P` or `grep -oP` usage (macOS-safe)

## Post-Review Changes

### Change Request 1 (2026-02-22)
- **Requested by user:** Integrate `new_release_post.sh` into existing release automation
- **Changes made:** Added `--auto` mode to the script, integrated call into `create_new_release.sh`
- **Files affected:** `website/new_release_post.sh`, `create_new_release.sh`

### Change Request 2 (2026-02-22)
- **Requested by user:** Add CHANGELOG_HUMANIZED.md generation to aitask-changelog skill
- **Changes made:** Added Steps 7b/7c to skill for generating informal blog-style entries; created initial CHANGELOG_HUMANIZED.md; updated script to prefer humanized content
- **Files affected:** `.claude/skills/aitask-changelog/SKILL.md`, `CHANGELOG_HUMANIZED.md`, `website/new_release_post.sh`

### Change Request 3 (2026-02-22)
- **Requested by user:** Review macOS compatibility for sed/grep usage
- **Changes made:** Replaced `grep -oP` (PCRE, not available on macOS) with portable `grep -o | sed`; fixed `pipefail` crash when grep finds no matches; documented grep portability in CLAUDE.md and aidocs reference
- **Files affected:** `website/new_release_post.sh`, `CLAUDE.md`, `aidocs/sed_macos_issues.md`

## Final Implementation Notes
- **Actual work done:** Created a full Docsy blog section with 5 release posts, RSS feed, landing page integration, and an automated blog post generation pipeline. Extended the aitask-changelog skill to produce humanized changelog entries. Integrated blog post creation into the release script.
- **Deviations from plan:** Originally planned just a scaffold script; evolved into full automation with `--auto` mode, `CHANGELOG_HUMANIZED.md`, and `create_new_release.sh` integration per user feedback. Also added macOS grep portability documentation.
- **Issues encountered:** `grep -oP` (PCRE) is not available on macOS; replaced with portable `grep -o | sed`. Also hit `set -eo pipefail` crash when grep finds no matches in the humanized changelog path; fixed with `|| true` and separate code paths for humanized vs standard content.
- **Key decisions:** Blog posts live as flat files in `website/content/blog/` (no subcategories); `CHANGELOG_HUMANIZED.md` uses the same `## vX.Y.Z` section format as `CHANGELOG.md` for easy extraction; the `new_release_post.sh` script is non-fatal in the release flow so blog post failures don't block releases.

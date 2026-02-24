---
Task: t231_readme_improvement.md
Branch: main (current branch)
Base branch: main
---

# Plan: Recover and Improve README.md (t231)

## Context

The README.md was accidentally overwritten and is now empty (just `# fresh project`). The last good version is at commit `8e24a2a`. The task is to recover it and add visual improvements: logo, badges, punchline, and styled section titles.

## Steps

1. Recover README content from git history (`git show 8e24a2a:README.md`)
2. Add centered logo with dark/light theme support using `<picture>` element
3. Add formatted punchline (spec-kit style centered h3)
4. Add badges section: docs, stargazer, last commit, issues
5. Add emoji-prefixed section titles (beads style)
6. Remove old h1 heading and standalone badge line

## Post-Review Changes

### Change Request 1 (2026-02-24)
- **Requested by user:** Add more badges (suggested license, issues, last-commit, claude code), remove macOS known issues (resolved), always show `ait setup` after curl in install instructions
- **Changes made:** Added last-commit + issues badges, removed Known Issues section, updated macOS to "Fully supported" in platform table, added `ait setup` to all install code blocks
- **Files affected:** README.md

### Change Request 2 (2026-02-24)
- **Requested by user:** Add issues badge
- **Changes made:** Added GitHub issues badge
- **Files affected:** README.md

### Change Request 3 (2026-02-24)
- **Requested by user:** Remove license badge
- **Changes made:** Removed license badge from badges section
- **Files affected:** README.md

## Final Implementation Notes
- **Actual work done:** Recovered README from commit 8e24a2a, added centered logo with dark/light theme support, formatted punchline, 4 badges (docs, stars, last-commit, issues), emoji section titles, removed Known Issues section, updated install instructions
- **Deviations from plan:** Added more badges than originally planned (last-commit, issues), removed Known Issues section (macOS issues resolved), updated install instructions to always include `ait setup`
- **Issues encountered:** None
- **Key decisions:** Used `<picture>` element with `prefers-color-scheme` media queries for automatic dark/light logo switching; chose `aitasks_logo_dark_theme_im.png` (dark) and `aitasks_logo_light_theme_pil.png` (light) as the logo pair

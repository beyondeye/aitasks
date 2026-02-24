---
Task: t187_web_site_about_page.md
Branch: main (current branch)
Base branch: main
---

# Plan: Redesign About Page (t187)

## Context

The current About page (`website/content/about/_index.md`) is a plain-text copy of the homepage feature list plus basic links and a license paragraph. It duplicates the homepage and docs Overview without adding unique value. The task is to replace it with a well-structured, visually appealing page that contains distinct content.

## Approach

Replace the About page body with Docsy block shortcodes (same pattern as the homepage) containing **unique content** not found elsewhere on the site. Single-file change — no new layouts, partials, or SCSS needed.

## Page Structure (7 sections)

1. Cover Hero (`blocks/cover`, color="primary", height="min")
2. Project Origin Story (`blocks/section`, color="white")
3. Philosophy Pull-Quote (`blocks/lead`, color="light")
4. Project Stats (`blocks/section`, color="white", type="row" + 3x `blocks/feature`)
5. Author/Team (`blocks/section`, color="dark")
6. License (`blocks/section`, color="light")
7. Links & Resources (`blocks/section`, color="white", type="row" + 3x `blocks/feature`)

## Files to Modify

- `website/content/about/_index.md` — Replace body content (frontmatter stays same)

## Verification

1. Run `cd website && hugo server`
2. Navigate to `/about/` and verify all sections render correctly

## Final Implementation Notes

- **Actual work done:** Completely redesigned the About page from 31 lines of plain markdown to 124 lines using Docsy shortcodes. Added 7 visually distinct sections: cover hero, origin story, philosophy quote, project stats with shields.io badges, author profile with GitHub avatar, license table, and resource link cards.
- **Deviations from plan:** Used `fa-star` instead of `fa-github` for the Open Source stats icon, because Docsy's `blocks/feature` shortcode prepends `fas` (solid) prefix and `fa-github` is a brand icon requiring `fab`. Also used `fa-code-branch` for the bottom GitHub card and `fa-tags` for Release Notes instead of originally planned `fa-newspaper-o` (FA4 syntax).
- **Issues encountered:** (1) Brand icons (`fa-github`) don't render in Docsy's `blocks/feature` because it uses `fas` prefix — switched to solid icons. (2) Relative URLs in `blocks/feature` `url` parameter resolve relative to the About page — fixed by prefixing with `../`.
- **Key decisions:** Used `<br>` tags instead of markdown bullet lists for "By the Numbers" section per user preference. Bolded **aitasks** name throughout for visual distinction.
- **Post-review changes:** 5 fixes applied after initial review — bold aitasks name, shorter subtitle, Beads description corrected, bullets removed, icons fixed. Then fixed broken relative URLs for docs/blog links.

## Post-Implementation (Step 9)

Archive task and plan per standard workflow.

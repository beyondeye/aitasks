---
Task: t763_about_page_redesign.md
Base branch: main
plan_verified: []
---

# Plan for t763 — About page redesign

## Context

The website About page (`website/content/about/_index.md`) carries stale narrative
content and outdated stats from earlier in the project's life. Task t763 asks for a
slimmer page: drop the historical/aspirational prose, refresh the by-the-numbers
panel against the current repo state, and tighten the "Created By" section to just
the author card + links.

## Changes to `website/content/about/_index.md`

### 0. Replace the big cover banner with a slim header (lines 10–12)

Currently:

```html
{{< blocks/cover title="About aitasks" height="min" color="primary" >}}
<p class="lead mt-2">The story behind the framework</p>
{{< /blocks/cover >}}
```

This renders as a full-width primary-colored hero banner with a large title and
the tagline "The story behind the framework". Replace with a slim, normally-sized
heading and drop the tagline entirely:

```html
{{% blocks/section color="white" %}}
<h2 class="text-center mb-0">About aitasks</h2>
{{% /blocks/section %}}
```

This keeps Docsy's section framing (preserves consistent left/right padding with
the rest of the page) but renders just an `<h2>` instead of the hero cover. Use
a literal `<h2>` (not Markdown `## About aitasks`) so we avoid Docsy auto-adding
an anchor link icon to the heading and keep the typography matching a normal
section heading.

### 1. Remove "How aitasks Started" section (lines 14–22)

Delete the entire `{{% blocks/section color="white" %}} ... {{% /blocks/section %}}`
block containing the `## How **aitasks** Started` heading and its two paragraphs.

### 2. Remove "Our approach" lead block (lines 24–26)

Delete the `{{% blocks/lead color="light" %}}` block that reads
"**Our approach:** Tasks are living documents...". The same line already appears
verbatim on the home page (`website/content/_index.md:84-86`), so removing it
from About avoids the duplication.

### 3. Update the "By the Numbers" feature card (lines 49–54)

Refresh stats against the current repo:

| Stat | Current text | New text | Evidence |
|------|--------------|----------|----------|
| Releases | `6 releases since February 2026` | `37 releases since February 2026` | `find website/content/blog -name "v*.md" \| wc -l` → 37 |
| Skills | `17 AI Agent skills built-in (Claude Code, Gemini CLI, Codex CLI, OpenCode)` | `26 AI Agent skills built-in (Claude Code, Gemini CLI, Codex CLI, OpenCode)` | `ls -d .claude/skills/*/ \| wc -l` → 26 |
| Platforms | `5 platforms fully supported` | keep as-is | Home page lists 5 install platforms (macOS brew, Arch AUR, Debian/Ubuntu .deb, Fedora/RHEL .rpm, generic install.sh) |
| CLI scripts | `28+ CLI scripts in the framework` | `80+ CLI scripts in the framework` | `ls .aitask-scripts/aitask_*.sh \| wc -l` → 82; round down to 80+ for stability |

### 4. Trim and re-center the "Created By" section (lines 62–87)

Two changes in this section:

**(a) Remove the trailing prose paragraph:**

> **aitasks** is built and maintained by Dario Elyasy. The framework grew out of
> real production use — every feature was driven by the need to ship code faster
> with AI coding agents.

**(b) Vertically + horizontally center the heading and the author card.**

Currently the `## Created By` heading sits left-aligned at the top of the section
and the author card sits in a `<div class="row justify-content-center"><div class="col-lg-8">`
wrapper below. The card itself is a left-aligned `d-flex` (avatar + name/links
column). Visually, the heading and the card stack but neither is horizontally
centered as a pair.

Apply two corrections inside the `{{% blocks/section color="dark" %}}` block:

1. Wrap the heading in a `text-center` div so it is horizontally centered:
   ```html
   <div class="text-center">

   ## Created By

   </div>
   ```
   (Blank lines around `## Created By` are required so Hugo still parses it as a
   Markdown heading inside the raw HTML wrapper.)

2. Change the card's `d-flex` from a left-anchored row to a centered row by
   adding `justify-content-center`:
   ```html
   <div class="d-flex align-items-center justify-content-center mb-3" style="gap: 1.5rem;">
   ```

The avatar, name (`<h3>`), and social links inside the card stay as-is —
`align-items-center` already vertically aligns avatar with name/links within
the flex row.

Resulting layout: centered "Created By" heading, with the avatar + name/links
group centered as a single flex row directly beneath it.

## Sections explicitly left untouched

- "Open Source" and "Community" feature cards (around "By the Numbers")
- License section
- Bottom row: GitHub / Documentation / Release Notes feature cards

## Verification

1. `cd website && ./serve.sh` (or `hugo server`) and open `/about/` in a browser:
   - The big "About aitasks" cover banner with "The story behind the framework" tagline is gone, replaced by a slim centered "About aitasks" `<h2>`.
   - The "How aitasks Started" section is gone.
   - The "Our approach" lead block is gone.
   - "By the Numbers" shows the updated stats.
   - "Created By" shows only the author card (no explainer paragraph below).
   - The "Created By" heading is horizontally centered above the card.
   - The author card (avatar + name/links) is centered as a single row.
   - The page still renders without Hugo errors (no orphan shortcodes).
2. Skim the rendered Markdown to confirm shortcode balance: every `{{% blocks/section %}}` has a matching `{{% /blocks/section %}}`, and the `{{% blocks/lead %}}` removal does not orphan another tag.
3. Optional: `hugo build --gc --minify` in `website/` to confirm a clean build.

## Files touched

- `website/content/about/_index.md` (single file edit)

## Post-Review Changes

### Change Request 1 (2026-05-11 10:00)
- **Requested by user:** Center the "License" heading horizontally (it was previously left-aligned at the top of the License section, mismatching the now-centered "Created By" heading).
- **Changes made:** Wrapped `## License` in a `<div class="text-center">...</div>` block (same pattern as "Created By"), with blank lines around the Markdown heading so Hugo still parses it as an `<h2>`.
- **Files affected:** `website/content/about/_index.md`

## Final Implementation Notes

- **Actual work done:** Edited `website/content/about/_index.md` end-to-end per the approved plan:
  1. Replaced the `{{< blocks/cover >}}` hero banner ("About aitasks" / "The story behind the framework") with a slim `<h2 class="text-center mb-0">About aitasks</h2>` inside a normal white `blocks/section`.
  2. Deleted the "How aitasks Started" section in its entirety.
  3. Deleted the "Our approach" `blocks/lead` block (line was a duplicate of the home page anyway).
  4. Refreshed the "By the Numbers" stats: `6 → 37 releases`, `17 → 26 AI Agent skills`, `28+ → 80+ CLI scripts`, kept `5 platforms`.
  5. Wrapped `## Created By` in a `<div class="text-center">` and added `justify-content-center` to the author-card flex so the avatar+name/links row is centered.
  6. Removed the trailing "aitasks is built and maintained by Dario Elyasy…" paragraph.
  7. After Step 8 review, wrapped `## License` in `<div class="text-center">` to match the "Created By" treatment.
- **Deviations from plan:** None of substance. The plan's draft for the slim header used `<h2 class="text-center mb-0">…</h2>` inside `{{% blocks/section color="white" %}}` and that's what shipped.
- **Issues encountered:** None. Hugo build (`hugo build --gc --minify`) completed cleanly twice (after the initial edits and after the License-centering change). Pre-existing deprecation warnings (`.Language.LanguageDirection`, `.Site.AllPages`) are unrelated to this task.
- **Key decisions:**
  - Used a literal `<h2>` for the slim "About aitasks" header rather than a Markdown `## About aitasks` to avoid Docsy's auto-generated heading anchor link icon and keep the typography slim.
  - Kept the `5 platforms` stat unchanged — it matches the 5 install rows on the home page (`macOS brew / Arch AUR / Debian .deb / Fedora .rpm / generic install.sh`).
  - Rounded `82` CLI scripts down to `80+` for stability across upcoming releases.
- **Upstream defects identified:** None.

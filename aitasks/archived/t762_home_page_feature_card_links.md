---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [web_site]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-10 17:08
updated_at: 2026-05-10 17:29
completed_at: 2026-05-10 17:29
---

The home page (`website/content/_index.md`) currently has 3 prominent feature cards near the top but none of them are clickable links. Add doc links and one in-page anchor so visitors can drill into each capability.

## Changes

1. **Add an anchor on the tour mosaic section** so the first feature card can link to it in-page. The tour section is the `{{< blocks/section >}}` containing `## 🎛️ Take the tour`. Wrap the heading in an `id="take-the-tour"` anchor (or add a `<span id="take-the-tour"></span>` immediately above the heading).

2. **Wrap each of the 3 feature cards in a link.** Currently they are `{{% blocks/feature %}}` blocks with no `url` parameter. The Docsy `blocks/feature` shortcode accepts a `url` param (already used by the Linux/macOS/Windows feature cards lower on the page — see lines 97-108 of `_index.md`).

   Mappings:

   | Card | Link target |
   |------|-------------|
   | Agentic IDE in your terminal | `#take-the-tour` (in-page anchor) |
   | Long-term memory for agents | `/docs/concepts/agent-memory/` |
   | Tight git coupling, AI-enhanced | `/docs/workflows/#git` (the **Git** subsection of the workflows landing page) |

3. **Add a "See all TUIs →" footer CTA below the tour mosaic.** Centered below the 5-tile mosaic, link target `/docs/tuis/`. Style as a plain text link (matching "All releases →" pattern used in the Latest Releases section), or as a small `btn-outline-primary` button — pick whatever looks best in the live preview.

## Verification

- Build the site (`hugo build --gc --minify` in `website/`) — no new warnings.
- Local preview (`./serve.sh`):
  - Click each of the 3 top feature cards; each navigates to the correct target. The Agentic IDE card scrolls to the tour mosaic on the same page.
  - Click "See all TUIs →" below the mosaic; navigates to `/docs/tuis/`.
  - The 5 mosaic tiles still navigate to their individual TUI doc pages.

## Reference

- Original home-page redesign: `aiplans/archived/p760_more_visually_appealing_home_page.md`
- Docsy feature shortcode `url` param: see lines 97-108 of `website/content/_index.md`

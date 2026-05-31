---
priority: medium
effort: low
depends: [t848_5]
issue_type: documentation
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-27 17:30
updated_at: 2026-05-31 19:02
---

## Context

Sixth (last code) child of t848. Documents the customization layer in the Hugo/Docsy website so users discover `?` from any TUI's documentation and the Settings TUI page from the customization features page. Per CLAUDE.md "Documentation Writing", text describes current state only — no "previously" / "now" / "earlier" framings.

Depends on the earlier children for behavior to document. Should be picked **after** t848_5 lands so the Settings → Shortcuts tab and export/import semantics are stable.

## Key Files to Modify

- `website/content/docs/tuis/_index.md`:
  - Add a top-level section **"Customizing keyboard shortcuts"** with subsections:
    - **In-TUI editor**: press `?` in any TUI for a scope-filtered editor (DataTable layout, Enter to rebind, r/d to reset/clear, s to save).
    - **Where customizations live**: `aitasks/metadata/userconfig.yaml` under the `shortcuts:` key — per-user, gitignored.
    - **Label updates**: `(P)ick`-style button labels reflect the current key; rebind → label updates (mention the few cases where a restart is needed if `refresh_bindings` proved unreliable in t848_4).
    - **Cross-TUI view**: link to `tuis/settings/_index.md`'s Shortcuts tab.
    - **Coherence**: shared actions (`quit`, `tui_switcher`, `refresh`, `shortcuts_editor`) should keep the same key across TUIs; the Settings tab's `Lint` button surfaces drift.

- `website/content/docs/tuis/settings/_index.md`:
  - New section **"Shortcuts tab"** documenting:
    - Tab letter `k` to switch to.
    - Table layout (Scope, Action, Current, Default, Label, Origin).
    - Per-row Edit (Enter) / Reset (r) / Clear override (d).
    - **Export shortcuts** button: produces an aitasks_config bundle containing only the `shortcuts:` portion of `userconfig.yaml`. Compatible with the existing full `aitasks_config_export_*` bundles (Settings → Export).
    - **Import shortcuts** button: accepts the same bundle format; merges into current overrides.
    - **Lint coherence** button: reports cross-TUI mismatches for shared actions.
    - Note: full Settings → Export already includes shortcuts since they live in `userconfig.yaml` — point users at the focused "Export shortcuts" only when they want a bundle that *only* changes keys on import.

- Every per-TUI page (`website/content/docs/tuis/<name>/_index.md` for `board`, `monitor`, `minimonitor`, `codebrowser`, `stats`, `syncer`, `applink`, plus a brief mention in `brainstorm`'s page since `op_help` migrated from `?` to `H`):
  - Append the same callout block (single source of truth lives in `tuis/_index.md`):
    ```
    {{% alert %}}
    **Customizable keys:** every shortcut on this page can be rebound. Press `?` in this TUI for the in-place editor, or visit [Settings → Shortcuts]({{<ref "/docs/tuis/settings#shortcuts-tab">}}).
    {{% /alert %}}
    ```
    (Check the actual Docsy alert/shortcode syntax used elsewhere in the site — if `{{% alert %}}` is not registered, fall back to a blockquote.)
  - For `brainstorm`: also note the operation-help key moved to `H`.

- `aitasks/metadata/labels.txt` / `aitasks/metadata/userconfig.yaml` user-facing examples:
  - Not docs files, but if the website embeds an example `userconfig.yaml`, update it to show a `shortcuts:` stanza.

## Reference Files for Patterns

- Existing `website/content/docs/tuis/settings/_index.md` — current tab-by-tab layout (Agent Defaults, Board, Project Config, etc.) for the new "Shortcuts tab" section's style.
- `website/content/docs/tuis/_index.md` — current TUI overview for inserting the new top-level section.
- `website/content/docs/concepts/` or `website/content/docs/workflows/` — Docsy shortcode conventions in use (alert, ref, etc.).

## Implementation Plan

1. Open `website/content/docs/tuis/_index.md`; add the "Customizing keyboard shortcuts" section near the top (after the TUI inventory, before per-TUI links).
2. Open `website/content/docs/tuis/settings/_index.md`; add the "Shortcuts tab" subsection in the natural ordering with the other tabs.
3. Identify the Docsy shortcode used for alerts (`{{% alert %}}` vs `{{< callout >}}` vs blockquote). Grep `website/content/docs` for examples.
4. For each per-TUI page, append the callout in a consistent location (likely just under the page title or under "Keyboard shortcuts").
5. Build the site locally and visually inspect each touched page; confirm internal links resolve.

## Verification Steps

```bash
cd website && hugo build --gc --minify         # site builds without warnings
./serve.sh                                     # spot-check rendered pages in browser:
                                               #   - /docs/tuis/ (new section visible)
                                               #   - /docs/tuis/settings/ (Shortcuts tab section)
                                               #   - /docs/tuis/board/ /monitor/ /codebrowser/ … (callouts visible)
grep -rn "shortcut" website/content/docs/tuis/ | wc -l   # confirm every TUI page references shortcuts
grep -rn "Press \`?\`" website/content/docs/tuis/        # callout text present on each per-TUI page
```

Manual cross-link verification is captured in the t848_7 manual-verification sibling.

## Notes for sibling tasks

None. This is the last code/doc child before manual verification.

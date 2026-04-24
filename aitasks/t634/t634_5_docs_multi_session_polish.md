---
priority: low
effort: low
depends: [t634_4]
issue_type: documentation
status: Ready
labels: [website, documentation]
created_at: 2026-04-24 10:22
updated_at: 2026-04-24 10:22
---

## Context

t634_2 added a "Multi-session view" subsection to `website/content/docs/tuis/monitor/reference.md` covering the main monitor's `M` binding and behavior. Once t634_4 (minimonitor multi-session awareness) lands, the docs need a refresh to describe the full cross-TUI story end-to-end: both TUIs, their matching `M` bindings, and any handoff behavior between them.

## Key files

- `website/content/docs/tuis/monitor/reference.md` — expand the multi-session section to cover the minimonitor counterpart.
- Any cross-references in `website/content/docs/workflows/` that mention single-session monitor assumptions — update them to describe the current unified multi-session view.
- If a separate minimonitor reference page exists (check `website/content/docs/tuis/minimonitor/`), surface the `M` binding there too.

## Required content

1. A short "Multi-session view" section (monitor page) describing:
   - That by default both monitor and minimonitor aggregate agents across every aitasks tmux session on the box, in a single unified list.
   - The `M` keyboard shortcut that toggles this behavior in-memory (same key in both TUIs).
   - How sessions are auto-discovered (registry set by `ait ide` + pane cwd walk-up).
2. A mention on the minimonitor docs (if it has its own page) pointing to the same story.
3. Any screenshot/example output showing the session tag prefix on each agent row.

## Per CLAUDE.md docs rule

Current-state only. No version history, no "previously this was single-session" callouts, no migration notes.

## Dependency

Blocked on t634_4 so the documented behavior matches what shipped.

## Verification

- `hugo build --gc --minify` (in `website/`) succeeds without broken links.
- Cross-references to `ait monitor` / `ait minimonitor` throughout the docs are consistent with the multi-session default.

## Post-implementation

Standard workflow: Step 8 commit (`documentation: Polish multi-session docs for monitor and minimonitor (t634_5)`), Step 9 archive.

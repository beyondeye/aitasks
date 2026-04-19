---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:10
updated_at: 2026-04-19 17:23
---

Pilot child of t594. Sweep the 15 pages under `website/content/docs/tuis/` for factual drift against the TUI source code and coherence issues, with no structural edits.

## Context

Parent plan: `aiplans/p594_website_documentation_coherence.md`. First child of 6 — establishes the sweep pattern applied by siblings to other sections.

The user's scoping decisions for the whole sweep apply here:
- Conservative dedup — keep repetitions, align wording.
- In-bounds: content rewrites, factual fixes vs source code, new bridging content.
- Out-of-bounds: page splits/merges, heading-hierarchy rewrites.

## Key Files to Modify

- `website/content/docs/tuis/_index.md` — polish section intro, fix switcher claim.
- `website/content/docs/tuis/board/{_index,how-to,reference}.md` — add `p`/`b` keys to reference; remove fabricated `Ctrl+Backslash`; collapse 8 repetitive how-tos into a keybinding table.
- `website/content/docs/tuis/monitor/{_index,how-to,reference}.md` — add `t`/`R`/`b`/`L` keys; fix `capture_lines` default (shown 30, actual 200).
- `website/content/docs/tuis/minimonitor/{_index,how-to}.md` — align with switcher reality (not in KNOWN_TUIS).
- `website/content/docs/tuis/codebrowser/{_index,how-to,reference}.md` — verify keybindings against source.
- `website/content/docs/tuis/settings/{_index,how-to,reference}.md` — add `t` Tmux tab shortcut.

## Reference Files for Patterns (Authoritative Sources)

- `.aitask-scripts/board/aitask_board.py:3220-3262` — Board `BINDINGS` (truth for `p`, `b`; no `Ctrl+Backslash` action exists).
- `.aitask-scripts/monitor/monitor_app.py:432-449` — Monitor bindings (`t`=scroll_preview_tail, `R`=restart_task, `b`=toggle_scrollbar, `L`=open_log).
- `.aitask-scripts/settings/settings_app.py:346-353, 1504-1516` — Settings tab bindings including `t`=tab_tmux.
- `.aitask-scripts/lib/tui_switcher.py:59-65` — `KNOWN_TUIS = [board, monitor, codebrowser, settings, diffviewer]` — Minimonitor is NOT switchable; per `CLAUDE.md` diffviewer is switchable but not documented on the site.
- `aitasks/metadata/project_config.yaml:11` — actual `capture_lines: 200`.

## Implementation Plan

1. Source-vs-doc verification pass:
   - For each TUI, `grep BINDINGS`/action names in its source file.
   - Diff against the corresponding `reference.md` keybinding table.
   - List additions/removals.
2. Apply fixes from parent plan (see §"Required fixes (from verification)" for t594_1).
3. Collapse `tuis/board/how-to.md` (438 lines) into reference table + one narrative per operation. Target ≤ 310 lines without information loss.
4. Add "Next:" footers along each TUI's page chain (`_index → how-to → reference → next TUI's _index`).
5. Polish `tuis/_index.md` section intro — one-sentence description per TUI.

## Verification Steps

- `cd website && hugo build --gc --minify` succeeds without warnings.
- For each TUI, manually launch it (`ait board`, `ait monitor`, etc.) and press every documented keybinding — all must fire.
- `wc -l website/content/docs/tuis/board/how-to.md` ≤ 310.
- Every "Next:" link resolves (click through start to end).

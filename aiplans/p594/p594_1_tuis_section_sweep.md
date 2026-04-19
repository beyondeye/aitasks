---
Task: t594_1_tuis_section_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{2,3,4,5,6}_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 17:34
---

# t594_1 — TUIs section coherence sweep (pilot)

## Context

First child of t594 (of 6). Pilot task — establishes the sweep pattern applied by siblings to other sections. See parent plan `aiplans/p594_website_documentation_coherence.md` for the overall context, user's scoping decisions (conservative dedup, no structural edits, source-vs-docs verification mandatory), and the full drift list that informed these children.

This child sweeps all 15 pages under `website/content/docs/tuis/` — Board, Monitor, Minimonitor, Codebrowser, and Settings each with their `_index`/how-to/reference subpages.

## Scope

**In-bounds:**
- Content rewrites to shorten verbose prose.
- Factual fixes against the TUI Python source code.
- New bridging content (Next/Prev, section intros).

**Out-of-bounds:**
- Page splits/merges.
- Heading-hierarchy rewrites (e.g., reshaping Settings docs to match other TUIs — explicitly deferred).
- Changes to TUI source code.

## Concrete factual drift to fix (with source citations)

1. **Board `Ctrl+Backslash` is real — do NOT remove it.** (Verify-pass correction.)
   - Doc: `website/content/docs/tuis/board/reference.md:51` claims `Ctrl+Backslash` opens the command palette.
   - Source: `.aitask-scripts/board/aitask_board.py:3218` registers `COMMANDS = App.COMMANDS | {KanbanCommandProvider}`. The command palette is Textual's built-in (bound to `Ctrl+Backslash` by the `App` base class, not in the subclass `BINDINGS` list). The doc is correct. Initial planning wrongly flagged this as fabricated — leave the entry in place. Optional: add a brief note to the doc that the palette provides context-aware commands via `KanbanCommandProvider`.

2. **Board: add `p` and `b` to reference keybinding table.**
   - Source: `.aitask-scripts/board/aitask_board.py:3246` (`p` → `pick_task`), `:3248` (`b` → `brainstorm_task`). These are shown conditionally in the footer (via `check_action`) but missing from the reference doc's keybinding tables. Add them to the "Task Operations" section with a "(context-dependent)" note.

3. **Monitor: add `t`, `R`, `b`, `L` to reference keybinding table.**
   - Source: `.aitask-scripts/monitor/monitor_app.py:432-449` — `t`=scroll_preview_tail (442), `R`=restart_task (445), `b`=toggle_scrollbar (441), `L`=open_log (448). All absent from `website/content/docs/tuis/monitor/reference.md`.

4. **Settings: add `t` (Tmux tab) shortcut.**
   - Source: `.aitask-scripts/settings/settings_app.py:346-352` — `"t": "tab_tmux"`. Also see lines 1504-1516 for tab behavior. The Tmux tab itself is mentioned in `tuis/settings/_index.md` but the `t` shortcut is absent from the reference doc.

5. **TUI switcher (`j`) reality check in `tuis/_index.md:27`.**
   - Source: `.aitask-scripts/lib/tui_switcher.py:59-65` — `KNOWN_TUIS = [board, monitor, codebrowser, settings, diffviewer]`. Minimonitor is NOT in `KNOWN_TUIS` (it's auto-spawned from other TUIs). Brainstorm appears only via dynamic crew-brainstorm-* session discovery, not at startup. Per `CLAUDE.md`, diffviewer stays switchable but is not documented on the website.
   - Fix: the doc must say what the switcher actually lists at startup + how Brainstorm appears dynamically. Do not mention Minimonitor as switchable. Keep diffviewer absent from user-facing text (per CLAUDE.md's "transitional" note).

6. **Monitor: `capture_lines` default.**
   - Doc: `website/content/docs/tuis/monitor/reference.md:94-102` claims default `capture_lines: 30`.
   - Source: `aitasks/metadata/project_config.yaml:11` has `capture_lines: 200`. Either update the doc to 200, or label the shown value as "schema default, overridden in shipped config".

## Coherence fixes (non-drift)

7. **`tuis/board/how-to.md` (438 lines) — shorten.**
   - Collapse the 8 repetitive "1. 2. 3." micro-how-tos into a single keybinding reference table plus one short narrative per operation. Do not split the page. Target ≤ 310 lines (30% reduction).

8. **Add "Next:" footers** along each TUI's page chain: `_index → how-to → reference → next TUI's _index`. The traversal order should follow the section's weight ordering (board 10, codebrowser 20, monitor 15 or per actual weights — verify in the `_index.md` frontmatter of each TUI).

9. **Polish `tuis/_index.md` section intro** — one-sentence description per TUI (Board, Monitor, Minimonitor, Codebrowser, Settings — per CLAUDE.md's list of documented TUIs).

## Authoritative sources

| Topic | Source file |
|---|---|
| Board bindings/actions | `.aitask-scripts/board/aitask_board.py` (`BINDINGS` list ~3220-3262) |
| Monitor bindings | `.aitask-scripts/monitor/monitor_app.py:432-449` |
| Settings bindings/tabs | `.aitask-scripts/settings/settings_app.py:346-353, 1504-1516` |
| Codebrowser bindings | `.aitask-scripts/board/aitask_codebrowser.py` (resolve via `glob`; name may differ) |
| Minimonitor source | resolve via `.aitask-scripts/` glob for `minimonitor*.py` |
| TUI switcher scope | `.aitask-scripts/lib/tui_switcher.py:59-65` |
| Config defaults | `aitasks/metadata/project_config.yaml` |
| diffviewer policy | `CLAUDE.md` §"Project-Specific Notes" |

## Implementation plan (step-by-step)

1. **Source audit pass** — for each TUI (Board, Monitor, Minimonitor, Codebrowser, Settings):
   - Locate the source file via `.aitask-scripts/` glob.
   - Grep `BINDINGS`/action definitions.
   - List current doc keybinding table vs source.
   - Produce a per-TUI diff note (additions, removals, drift).

2. **Apply drift fixes 2-6** from the list above (item 1 is a verify-pass correction — leave the doc as-is, optionally enhance with a mention of `KanbanCommandProvider`).

3. **`tuis/board/how-to.md` tightening:**
   - Replace the 8 "1. 2. 3." sections with a single keybinding reference table.
   - Keep one short narrative paragraph per operation where truly needed for context.
   - Verify no information is lost — diff before/after.

4. **Next-footer pass:** add a terminal "Next:" line to each TUI page pointing to the next page in the reading order. Use the same footer shape everywhere so t594_3 and siblings can reuse the pattern.

5. **Intro polish:** rewrite `tuis/_index.md` opener so each TUI has a one-sentence hook.

6. **Hugo build check:** `cd website && hugo build --gc --minify` — no warnings.

## Verification

- `cd website && hugo build --gc --minify` passes with no warnings.
- Launch each TUI and press every documented keybinding — all must fire. Especially verify newly-added `p`/`b`/`t`/`R`/`L` work as described, and `Ctrl+Backslash` opens the command palette.
- `wc -l website/content/docs/tuis/board/how-to.md` ≤ 310.
- Click every "Next:" link from `tuis/_index.md` through `settings/reference.md`; all resolve.
- `Ctrl+Backslash` entry remains in `tuis/board/reference.md` (verify-corrected; the palette is real).

## Step 9 reference

No worktree (`create_worktree: false`). `verify_build` in `project_config.yaml` is null, so Hugo build verification is this task's own responsibility (run before committing). Archive via `./.aitask-scripts/aitask_archive.sh 594_1`.

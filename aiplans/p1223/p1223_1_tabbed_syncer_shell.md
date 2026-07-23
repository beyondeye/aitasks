---
Task: t1223_1_tabbed_syncer_shell.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_2_*.md, aitasks/t1223/t1223_3_*.md, aitasks/t1223/t1223_4_*.md, aitasks/t1223/t1223_5_*.md, aitasks/t1223/t1223_6_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# p1223_1 — Tabbed syncer shell

> The task file `aitasks/t1223/t1223_1_tabbed_syncer_shell.md` carries the full
> context, verified source anchors, and reference-pattern list. This plan is the
> execution view; read the task file first and do not duplicate its detail here.
> Parent design: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.

## Goal

Introduce `TabbedContent` into `.aitask-scripts/syncer/syncer_app.py` so the
existing branches table + detail pane become a *Branches* tab alongside two empty
panes that later siblings fill. **No new features, no behavior change** other
than per-tab action gating.

## Steps

1. Read `aidocs/framework/tui_conventions.md` (required by CLAUDE.md before any
   Textual edit).
2. `compose()` (`syncer_app.py:384-401`): wrap the current `Vertical()` in
   `TabbedContent` → `TabPane("Branches", id="tab_branches")`. **Keep widget ids
   `#branches`, `#detail_scroll`, `#detail` unchanged** so existing `query_one`
   call sites keep resolving.
3. Add `TabPane("Versions", id="tab_versions")` and
   `TabPane("Settings", id="tab_settings")`, each holding only a `Static`
   placeholder. Establishing the ids now means t1223_3/_5 never re-touch
   `compose()`.
4. Add `_active_tab()` returning `TabbedContent.active`, degrading to
   `"tab_branches"` when the query fails (pre-mount / unit-test safety).
5. Extend `check_action` (`:426-430`) with a tab check **before** the existing
   ref check, covering `sync_data`, `pull`, `push`, `refresh`, `toggle_fetch`.
   `q`, `j`, `?` stay available on every tab.
6. Verify `_set_busy` (`:437-441`) and `_update_table` (`:551-571`) still resolve
   `#branches` inside the pane. Leave the refresh timers and the
   coalescing/generation machinery untouched — Branches data must stay current
   while another tab is active.
7. CSS (`:321-336`): add a `TabPane` padding rule; confirm
   `#branches { max-height: 14 }` and the `#detail_scroll` `1fr` height still lay
   out inside a pane.
8. Extend `tests/test_syncer_rows.py` (do not rewrite it).

## Verification

- `bash tests/test_syncer_rows.py` passes, including its pre-existing 381 lines untouched.
- Mounting the app yields `TabbedContent` with panes `tab_branches`, `tab_versions`, `tab_settings`, and `tab_branches` active on start.
- With `tab_branches` active and an `aitask-data` row selected, `check_action("sync_data", ())` is truthy.
- Negative control: with `tab_versions` active, `check_action` returns `None` for `sync_data`, `pull` and `push` even when the selected row would otherwise allow them.
- Ref gating unchanged on `tab_branches`: `sync_data` is `None` on a `main` row; `pull`/`push` are `None` on an `aitask-data` row.
- Single-repo regression: with fewer than 2 discovered sessions the Project column is absent, row keys are literal ref names, and all actions behave as before the refactor.
- `query_one("#branches", DataTable)` and `query_one("#detail", Static)` both resolve after the refactor.
- Manual smoke: `ait syncer` renders tabs; Branches behaves exactly as before; the other tabs swallow `s`/`u`/`p`/`r`/`f`; `j` and `?` work from every tab.

## Out of scope

Any version or settings content (t1223_3 / t1223_5) and any new keybinding.

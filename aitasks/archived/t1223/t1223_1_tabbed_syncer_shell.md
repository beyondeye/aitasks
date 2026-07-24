---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1223
implemented_with: claudecode/opus4_8
created_at: 2026-07-23 18:29
updated_at: 2026-07-24 15:02
completed_at: 2026-07-24 15:02
---

## Context

First child of t1223 (expand `ait syncer` into a cross-repo sync console). This
is a **pure structural refactor with no new features**: it introduces the tab
container that t1223_3 (Version tab) and t1223_5 (Settings tab) will hang their
views on, and nothing else. It is deliberately first because it touches the
load-bearing parts of `syncer_app.py` that daily git-sync depends on — landing it
alone keeps any regression attributable.

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`
(read it — the `## Safety contracts` section is binding for later siblings; none
of the contracts apply to this child except "single-repo behavior is unchanged").

## Current state (verified 2026-07-23)

`.aitask-scripts/syncer/syncer_app.py:384-401` — `compose()` yields exactly:

```python
def compose(self) -> ComposeResult:
    yield Header()
    with Vertical():
        table = DataTable(id="branches", cursor_type="row", zebra_stripes=True)
        if self.multi_repo:
            table.add_column("Project", key="project")
        table.add_column("Branch", key="branch")
        table.add_column("Status", key="status")
        table.add_column("Ahead", key="ahead")
        table.add_column("Behind", key="behind")
        if self.multi_repo:
            table.add_column("Fetched", key="last")
        else:
            table.add_column("Last refresh", key="last")
        yield table
        with VerticalScroll(id="detail_scroll"):
            yield Static("Loading…", id="detail")
    yield Footer()
```

Related anchors:
- `BINDINGS` — `syncer_app.py:338-348` (`r`/`s`/`u`/`p`/`a`/`f`/`q` + switcher `j`
  + shortcuts `?`).
- `check_action` — `syncer_app.py:426-430`, delegates to
  `action_allowed_for_ref` (`:178-184`).
- CSS — `syncer_app.py:321-336` (`#branches { max-height: 14 }`,
  `#detail_scroll` border/height).
- `on_mount` — `:403-417` (seeds rows, starts `set_interval` timers).
- `_shortcuts_scope = "syncer"` — `:317`; registered in
  `.aitask-scripts/lib/shortcut_scopes.py:56`.
- `multi_repo` gate — `:357` (`len(self.sessions) >= 2`).

## Key files to modify

- `.aitask-scripts/syncer/syncer_app.py` — `compose()`, `check_action`, CSS, and
  any `query_one("#branches", DataTable)` call sites that must still resolve once
  the table lives inside a `TabPane`.
- `tests/test_syncer_rows.py` — extend (do not rewrite; it is 381 lines of
  existing pure-helper coverage that must keep passing).

## Reference files for patterns

- `.aitask-scripts/settings/settings_app.py:1578-1590` — the canonical in-repo
  `TabbedContent` / `TabPane` composition, including the comment explaining that
  **`TabPane` title is the single source of truth** (Textual ignores
  `TabbedContent`'s positional titles when `TabPane` children are composed).
- `.aitask-scripts/settings/settings_app.py:1531-1543` — per-tab guarding via
  `self.query_one(TabbedContent).active != "tab_<name>"`; this is the pattern for
  tab-aware `check_action`.
- `.aitask-scripts/settings/settings_app.py:1363` — `TabPane { padding: 1 2; }`
  CSS precedent.
- `.aitask-scripts/brainstorm/nav_mixin.py` — alternative tab-navigation pattern
  if a mixin shape fits better.
- `aidocs/framework/tui_conventions.md` — **read before editing** (required by
  CLAUDE.md for any Textual TUI change).

## Implementation plan

1. **Wrap the existing view in a tab.** In `compose()`, place the current
   `Vertical()` block (table + detail scroll) inside
   `with TabbedContent(): with TabPane("Branches", id="tab_branches"):`. Keep the
   widget ids (`#branches`, `#detail_scroll`, `#detail`) **unchanged** so every
   existing `query_one` call site keeps working.

2. **Add the two placeholder panes** so the shell is complete and testable now,
   each containing only a `Static` placeholder — no data, no bindings:
   - `TabPane("Versions", id="tab_versions")` (filled by t1223_3)
   - `TabPane("Settings", id="tab_settings")` (filled by t1223_5)

   Rationale: landing the tab ids now means t1223_3/_5 add content without
   re-touching `compose()`, and the per-tab gating below is exercised
   immediately rather than being dead code.

3. **Make `check_action` tab-aware.** Current body (`:426-430`) gates only on the
   selected row's ref. Add a tab check *first*, so `s`/`u`/`p`/`r`/`f`/`a` are
   inert when a non-Branches tab is active:

   ```python
   BRANCH_TAB_ACTIONS = (
       "sync_data", "pull", "push", "refresh", "toggle_fetch", "agent_resolve",
   )

   def check_action(self, action, parameters):
       if action in BRANCH_TAB_ACTIONS:
           if self._active_tab() != "tab_branches":
               return False
       if action in ("sync_data", "pull", "push"):
           if not action_allowed_for_ref(action, self._selected_row().ref_name):
               return None
       return True
   ```

   Two amendments to the original sketch, both made during planning:
   - `agent_resolve` (`a`, `show=False`) is a Branches-domain action and is
     gated with the rest.
   - The tab gate returns **`False`**, not `None`. In Textual 8.2.7
     `Screen.active_bindings` drops a binding only on `is False`; `None` yields
     `enabled=False`, i.e. kept-but-dimmed. A Branches-only action is not part
     of another tab's vocabulary, so it should disappear from the footer there —
     which is what "the other tabs swallow those keys" below means. The **ref**
     check keeps `None` (dimmed): same tab, just a non-applicable row.

   Add a small `_active_tab()` helper that returns the `TabbedContent.active` id
   and degrades to `"tab_branches"` if the query fails (so unit tests and any
   pre-mount call cannot crash). `q`, `j` (switcher) and `?` (shortcuts) stay
   available on every tab.

3b. **Refresh bindings on tab activation.** Switching tabs with ←/→ changes no
   focus, so Textual never fires its focus-change bindings refresh and the
   footer keeps advertising the now-inert Branches keys. Add:

   ```python
   def on_tabbed_content_tab_activated(self, event) -> None:
       self.refresh_bindings()
   ```

   Leave the existing `on_data_table_row_highlighted` (`:653-655`) **untouched**
   — it already calls both `_refresh_detail()` and `refresh_bindings()`, and
   row-gating dim states are correct today.

3c. **Keep the branch table focused at boot.** Wrapping the table in
   `TabbedContent` hands boot focus to the tab bar, so ↑/↓ would no longer move
   the branch cursor on open. Call `table.focus()` at the end of `on_mount()`.
   Reaching the tab bar then costs two `Tab` presses (detail pane first); that
   is accepted — `#detail_scroll` is focusable today and that focus is what
   scrolls a long detail pane.

4. **Refresh/worker safety.** `_set_busy` (`:437-441`) and `_update_table`
   (`:551-571`) already wrap their `query_one` in try/except or resolve by id —
   verify each still resolves inside the `TabPane` and leave the refresh timers
   untouched. The refresh loop must keep running regardless of the active tab
   (the Branches data should be current when the user tabs back).

5. **CSS.** Add a `TabPane` padding rule; confirm `#branches { max-height: 14 }`
   and the `#detail_scroll` `1fr` height still lay out correctly inside a pane.

6. **No new keybindings in this child.** Tab switching uses Textual's built-in
   tab navigation. If a dedicated switch key is wanted later, it belongs with
   the tab that needs it, routed through `ShortcutsMixin` (scope `"syncer"`).

## Verification steps

```bash
python3 tests/test_syncer_rows.py  # existing 381 lines must pass untouched
python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/syncer'); import syncer_app"
```

Tests to add in `tests/test_syncer_rows.py` (follow the file's existing style —
pure helpers where possible, `App.run_test()` only where a render assertion is
genuinely needed; see `aidocs/framework/tui_conventions.md` on asserting
`widget.render().plain`):

1. **Tab presence** — mounting the app yields `TabbedContent` with panes
   `tab_branches`, `tab_versions`, `tab_settings`, and `tab_branches` is active
   on start.
2. **Per-tab gating (positive)** — with `tab_branches` active and an
   `aitask-data` row selected, `check_action("sync_data", ())` is truthy.
3. **Per-tab gating (negative control)** — with `tab_versions` active, every
   action in `BRANCH_TAB_ACTIONS` returns `False`, **even when the selected row
   would otherwise allow it**. This is the load-bearing assertion: it must fail
   if the tab check is removed. Exercise both cursor rows — `pull`/`push` are
   ref-denied on the `aitask-data` row and `sync_data` on `main`, so a
   single-row test would let a removed tab check survive on the other.
4. **Ref gating unchanged** — on `tab_branches`, `sync_data` is still `None` for a
   `main` row and `pull`/`push` still `None` for an `aitask-data` row.
5. **Single-repo regression** — with `<2` discovered sessions, `multi_repo` is
   `False`, the Project column is absent, row keys are the literal ref names
   (`single_repo_rows()`), and all three actions behave exactly as before.
6. **Widget ids preserved** — `query_one("#branches", DataTable)` and
   `query_one("#detail", Static)` both resolve after the refactor.
7. **Boot focus** — `app.focused` is the `#branches` table and `down` moves the
   cursor (fails if `table.focus()` is dropped).
8. **Footer drops the Branches keys on tab activation** — drive the switch with
   real ←/→ keypresses, not by assigning `TabbedContent.active`: focusing the
   tab bar is itself a focus change that refreshes bindings for free, so an
   assignment-based helper passes even with the handler deleted.
9. **Footer/detail still follow the row cursor** — regression coverage for the
   existing `on_data_table_row_highlighted`; assert both the re-dim and that
   `#detail` repoints, so trimming either half of that handler fails.

Manual smoke: `ait syncer` in this repo — tabs render; ↑/↓ moves the branch
cursor immediately on open; Branches works exactly as before (`s`/`u`/`p`/`r`/`f`),
with the footer re-dimming `s`/`u`/`p` and the detail pane following the cursor;
one `Tab` reaches the detail pane and a second the tab bar, where ←/→ switch
tabs; the other two tabs show placeholders, the Branches keys are **gone** from
the footer there and pressing them does nothing; `j` and `?` work from every tab.

## Notes for sibling tasks

- `tab_versions` / `tab_settings` ids are established here; t1223_3 and t1223_5
  fill them and must not re-shape `compose()`.
- `_active_tab()` is the seam for any further per-tab gating — extend
  `BRANCH_TAB_ACTIONS` (or add a sibling tuple) rather than adding parallel
  checks.
- Any tab-switch **keybinding** a sibling adds must use the
  `brainstorm_app._select_tab` pattern (`brainstorm_app.py:2704-2722`): assigning
  `TabbedContent.active` while a widget inside the current pane holds focus is
  silently reverted by Textual, so hand focus to the tab bar when the tab
  actually changes.
- Tests that switch tabs must do it with real ←/→ keypresses on a focused tab
  bar (`activate_tab` in `tests/test_syncer_rows.py`). Assigning `active`
  directly makes footer assertions pass vacuously, because focusing the bar is
  itself a focus change that refreshes bindings.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-24T11:43:07Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T12:01:51Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-24T12:02:09Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:dbdd7608760dc77c

> **✅ gate:risk_evaluated** run=2026-07-24T12:02:09Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1223_1/risk_evaluated_2026-07-24T12:02:09Z-risk_evaluated-a1.log`

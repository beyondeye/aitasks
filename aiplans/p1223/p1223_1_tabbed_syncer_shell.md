---
Task: t1223_1_tabbed_syncer_shell.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_2_framework_version_and_upgrade_command_model.md, aitasks/t1223/t1223_3_version_tab_upgrade_action_and_handoff.md, aitasks/t1223/t1223_4_cross_repo_settings_seam.md, aitasks/t1223/t1223_5_settings_tab_and_push_action.md, aitasks/t1223/t1223_6_syncer_scope_documentation.md, aitasks/t1223/t1223_7_manual_verification_expand_syncer_scope_version_and_settings.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-24 13:55
---

# p1223_1 — Tabbed syncer shell (verified 2026-07-24)

> Execution view for `aitasks/t1223/t1223_1_tabbed_syncer_shell.md`. The task
> file carries the full context and source anchors; parent design lives in
> `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.

## Context

`ait syncer` (`.aitask-scripts/syncer/syncer_app.py`) today composes a single
flat view: `Header` → `DataTable(#branches)` → `VerticalScroll(#detail_scroll)`
→ `Footer`. t1223 expands it into a cross-repo sync console with two new
surfaces (framework versions, cross-repo settings). This child introduces
**only the tab container** those siblings will hang their views on — a
structural refactor, no new features — and lands alone so any regression in the
daily git-sync path is attributable.

`tab_versions` / `tab_settings` ids are established here so t1223_3 and t1223_5
add content without re-touching `compose()`.

## Verification findings (this plan revises the pre-existing p1223_1)

Re-read against live source at `4ce8f2fd2` plus headless Textual 8.2.7 probes.
Source anchors in the task file all still resolve (`compose` 384–401,
`check_action` 426–430, CSS 321–336, `BINDINGS` 338–348, `on_mount` 403–417,
`multi_repo` :357; `_set_busy` is at :432–436, not :437–441). Eight findings —
1–6 are corrections to the pre-existing plan, 7 retracts an error in an earlier
draft of *this* plan, 8 records the end-to-end validation:

1. **Boot focus regresses.** Probe confirmed that wrapping the table in
   `TabbedContent` moves boot focus `DataTable → ContentTabs`, so ↑/↓ no longer
   moves the branch cursor on open. **Decision (user-confirmed): focus
   `#branches` in `on_mount`** to preserve today's UX.
2. **`agent_resolve` was missing from the gated action set.** `a`
   (`action_agent_resolve`, `show=False`) is a Branches-domain action and must be
   inert on the other tabs like its siblings.
3. **Setting `TabbedContent.active` silently reverts (t1060).** Probe reproduced
   it exactly: with a widget inside `tab_branches` focused, `tabbed.active =
   "tab_versions"` snaps back to `tab_branches`. Load-bearing for the
   negative-control test — without focusing the tab bar first, the test asserts
   against `tab_branches` and passes for the wrong reason. Production form:
   `brainstorm_app._select_tab` (`brainstorm_app.py:2704-2722`).
4. **CSS is a non-issue.** Probe shows the existing `#branches` /
   `#detail_scroll` rules lay out correctly inside a `TabPane` with no height
   overrides (`detail_scroll` 23→21 rows, the two the tab bar consumes). Only a
   cosmetic `TabPane` padding rule is needed.
5. **The tab check alone does not update the Footer — a tab-activation handler
   is mandatory.** Switching tabs with ←/→ leaves focus on `ContentTabs`, so
   Textual never fires a focus-change bindings refresh and the footer keeps
   advertising `s`/`u`/`p`/`r`/`f` as live while `check_action` has made them
   inert. Probe matrix (footer state after switching to Versions):

   | `check_action` returns | no handler | + `refresh_bindings()` handler |
   |---|---|---|
   | `None` | unchanged (stale) | keys shown **dimmed** (`-disabled`) |
   | `False` | unchanged (stale) | keys **removed** from footer |

   Note this inverts the usual folklore: in Textual 8.2.7 `Screen.active_bindings`
   drops a binding only on `is False`; `None` yields `enabled=False`, i.e.
   kept-but-dimmed. **Decisions (user-confirmed):** add
   `on_tabbed_content_tab_activated` → `self.refresh_bindings()`, and have the
   **tab** check return `False` so Branches-only keys disappear on the other
   tabs (matching the task's "other tabs swallow those keys" smoke). The
   pre-existing **ref/row** check keeps `None` (dim) — same tab, just this row.

   > **AC deviation (explicit):** the task file's snippet writes `return None`
   > for the tab check. This plan returns `False`. Update the task file's
   > `## Implementation plan` snippet in the same commit.

6. **Reaching the tab bar takes two Tabs, and that is correct.** From
   `#branches` the traversal is `#detail_scroll` → `ContentTabs` → `#branches`.
   `#detail_scroll` is focusable **today, pre-refactor** (verified against the
   current tree, with both short and overflowing detail content) and that focus
   is what allows keyboard-scrolling a long detail pane. Setting
   `can_focus=False` on it would be a genuine behavior regression in a
   no-behavior-change refactor, so the two-Tab route is **explicitly accepted**,
   documented in the smoke steps, and pinned by a test.
7. **Row-highlight refresh already exists and works — do not touch it.**
   `syncer_app.py:653-655` already defines
   `on_data_table_row_highlighted` calling **both** `self._refresh_detail()` and
   `self.refresh_bindings()`, and a `run_test` boot of the real `SyncerApp`
   confirms `s`/`u`/`p` re-dim correctly on `main` → `aitask-data`. An earlier
   draft of this plan claimed a pre-existing staleness bug and proposed
   replacing the handler with `refresh_bindings()` alone — that was an artifact
   of probing a synthetic replica that lacked the handler, and would have
   dropped `_refresh_detail()`, making the detail pane stop following the
   selection. **Leave the handler exactly as-is.** Test 11 is regression
   coverage for existing behavior, not a fix.

8. **The whole design was validated against the real class before
   implementation.** A `run_test` harness subclassed the real `SyncerApp` with
   the proposed `compose()` / `_active_tab()` / `check_action()` and measured a
   2×2 matrix (handler present/absent × `focus()` direct/`call_after_refresh`).
   Results: plain `table.focus()` in `on_mount` is sufficient (boot focus =
   `DataTable#branches`; `call_after_refresh` is unnecessary); row-highlight
   dimming works in every cell; and the footer at Versions collapses from
   `? r s u p f q ^p` to `? q ^p` **only** when
   `on_tabbed_content_tab_activated` is present. Probe gotcha worth knowing if
   anyone re-runs it: Textual dispatches `on_mount` for **every** class in the
   MRO, so a subclass must **not** call `super().on_mount()` (doing so
   double-seeds the table and raises `DuplicateKey`). Irrelevant to the real
   implementation, which edits `on_mount` in place.

Also: the task file's verification command says `bash tests/test_syncer_rows.py`;
it is a Python file (`python3 tests/test_syncer_rows.py`) — correct it in the
task file while implementing.

## Steps

1. Read `aidocs/framework/tui_conventions.md` (required by CLAUDE.md before any
   Textual edit) — already read during verification.
2. **`compose()`** (`:384-401`): wrap the current `Vertical()` block in
   `TabbedContent()` → `TabPane("Branches", id="tab_branches")`. Widget ids
   `#branches`, `#detail_scroll`, `#detail` stay **unchanged** so all existing
   `query_one` call sites (`:404`, `:434`, `:552`, `:582`, `:593`, `:615`) keep
   resolving. Add `TabbedContent`/`TabPane` to the `textual.widgets` import
   (`:65`).
3. Add the two placeholder panes, each holding only a `Static`:
   `TabPane("Versions", id="tab_versions")` → `Static(..., id="versions_placeholder")`,
   `TabPane("Settings", id="tab_settings")` → `Static(..., id="settings_placeholder")`.
4. **`on_mount()`** (`:403-417`): after the row-seeding loop and before the
   `set_interval` calls, add `table.focus()` (finding 1 — plain `focus()` is
   sufficient; `call_after_refresh` is not needed, verified). Leave the refresh
   timers and the coalescing/generation machinery untouched — Branches data must
   stay current while another tab is active.
5. Add `_active_tab()` returning `self.query_one(TabbedContent).active`,
   degrading to `"tab_branches"` on any exception (pre-mount / unit-test safety).
6. **`check_action`** (`:426-430`): tab check **before** the existing ref check.

   ```python
   _BRANCH_TAB_ACTIONS = (
       "sync_data", "pull", "push", "refresh", "toggle_fetch", "agent_resolve",
   )

   def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
       if action in self._BRANCH_TAB_ACTIONS:
           if self._active_tab() != "tab_branches":
               return False        # removed from the footer, key inert
       if action in ("sync_data", "pull", "push"):
           if not action_allowed_for_ref(action, self._selected_row().ref_name):
               return None         # unchanged: dimmed on a non-applicable row
       return True
   ```

   `q`, `j` (switcher) and `?` (shortcuts) stay available on every tab. The
   `False` / `None` split is deliberate and asserted separately by tests 4 and 5.
7. **Add the tab-activation bindings refresh** (finding 5) — one new handler,
   alongside the existing `on_data_table_row_highlighted` (`:653-655`), which
   stays **untouched** (finding 7):

   ```python
   def on_tabbed_content_tab_activated(
       self, event: TabbedContent.TabActivated
   ) -> None:
       """←/→ on the tab bar changes no focus, so Textual never refreshes the
       footer on its own; without this the Branches keys stay advertised."""
       self.refresh_bindings()
   ```

8. **CSS** (`:321-336`): add `TabPane { padding: 0 1; }`. No height overrides —
   probe-verified.
9. Verify `_set_busy` (`:432-436`) and `_update_table` (`:551-571`) still resolve
   `#branches` inside the pane (both resolve by id; `_set_busy` and
   `_update_age_cells` additionally try/except).
10. **No new keybindings.** Tab switching is Textual's built-in tab-bar
    navigation. A dedicated switch key belongs with the sibling that needs it,
    routed through `ShortcutsMixin` (scope `"syncer"`), and must use the
    `_select_tab` focus dance from finding 3.

## Tests — extend `tests/test_syncer_rows.py` (do not rewrite its 381 lines)

New async section using `asyncio` + `App.run_test()` (pattern:
`tests/test_shortcuts_mixin_live_remap.py`; the file has **no** `run_test()`
usage today — all 39 tests are pure helpers). Boot needs two module-level mocks:
`mock.patch.object(syncer_app, "discover_syncer_sessions", ...)` to control
`multi_repo`, and `mock.patch.object(syncer_app, "snapshot", ...)` so the
`@work(thread=True)` refresh worker never shells out to git. Construct with
`argparse.Namespace(interval=3600, no_fetch=True)`.

Two shared helpers make tests 4/10/11 honest:

```python
async def activate(app, pilot, tab_id):
    """Focus the tab bar first — setting .active from a focused pane reverts."""
    tabbed = app.query_one(TabbedContent)
    tabbed.query_one(Tabs).focus()
    tabbed.active = tab_id
    await pilot.pause()
    assert tabbed.active == tab_id      # tripwire: the switch must have stuck
    return tabbed

def footer_state(app):
    """key -> 'dim' | 'on' for every FooterKey currently rendered."""
    return {
        k.key: ("dim" if k.has_class("-disabled") else "on")
        for k in app.query_one(Footer).query("FooterKey")
    }
```

1. **Tab presence** — panes are exactly `["tab_branches", "tab_versions",
   "tab_settings"]`, `active == "tab_branches"` on start.
2. **Boot focus** — `app.focused` is the `#branches` `DataTable`; after
   `pilot.press("down")`, `table.cursor_row == 1`. Pins finding 1.
3. **Per-tab gating, positive** — on `tab_branches` with the `aitask-data` row
   selected, `check_action("sync_data", ())` is truthy.
4. **Per-tab gating, negative control** — on `tab_versions`, `check_action`
   returns `False` for all six `_BRANCH_TAB_ACTIONS` **while the selected row is
   one that would otherwise allow them**. Load-bearing: must fail if the tab
   check is removed.
5. **Ref gating unchanged** — on `tab_branches`, `sync_data` returns `None`
   (not `False`) for the `main` row; `pull`/`push` return `None` for the
   `aitask-data` row. Asserts the deliberate `False` vs `None` split.
6. **Single-repo regression** — with one discovered session `multi_repo` is
   `False`, the Project column is absent (5 columns), row keys are the literal
   ref names from `single_repo_rows()`, and all three actions gate as before.
7. **Widget ids preserved** — `query_one("#branches", DataTable)` and
   `query_one("#detail", Static)` both resolve post-refactor.
8. **`_active_tab()` degrade path (pure)** — on an instance whose `query_one`
   raises, `_active_tab()` returns `"tab_branches"`, so a pre-mount
   `check_action` call cannot crash. Covers the fail-open default explicitly.
9. **Placeholder render** — `query_one("#versions_placeholder",
   Static).render().plain` matches the expected text (render-level assertion per
   `tui_conventions.md`).
10. **Footer clears on tab activation** — `footer_state(app)` contains `r`,
    `s`, `u`, `p`, `f` on Branches; after `activate(..., "tab_versions")` none
    of them are present, while `q` remains. Pins finding 5 and fails if the
    `on_tabbed_content_tab_activated` handler is dropped.
11. **Footer re-dims on row change (regression coverage)** — on Branches with
    the `main` row selected, `footer_state(app)["s"] == "dim"` and
    `["u"] == "on"`; after `pilot.press("down")` to the `aitask-data` row,
    `["s"] == "on"` and `["u"] == "dim"`. This behavior **already works** via
    the existing `on_data_table_row_highlighted` (`:653-655`); the test pins it
    so the refactor — or a future edit to that handler — cannot silently break
    it. A companion assertion that `#detail` still updates on row change guards
    the `_refresh_detail()` half of the same handler.
12. **Focus traversal is documented, not accidental** — from `#branches`, one
    `Tab` reaches `#detail_scroll` and a second reaches `ContentTabs`;
    `#detail_scroll.can_focus` stays `True`. Pins finding 6 so a later
    "simplification" that drops detail-pane focus is caught.

## Risk

### Code-health risk: medium

- `_active_tab()` degrades **fail-open** to `"tab_branches"`, so a mis-wired or
  regressed tab check goes silently permissive rather than loud; a future
  `compose()` refactor that breaks the `TabbedContent` query would re-enable
  `s`/`u`/`p` on every tab with no visible symptom · severity: medium · →
  mitigation: covered in-task by test 8 (degrade path) + test 4 (negative
  control) + test 10 (footer)
- Footer correctness depends on two message handlers that nothing structural
  enforces — the new `on_tabbed_content_tab_activated` and the pre-existing
  `on_data_table_row_highlighted`; deleting or trimming either silently restores
  stale-footer behavior, and trimming the latter also stops the detail pane
  following the selection · severity: medium · → mitigation: test 10 fails if
  the new handler is dropped, test 11 (plus its `#detail` assertion) fails if
  the existing one is dropped or trimmed
- Two empty placeholder tabs ship to users between this child and
  t1223_3 / t1223_5 · severity: low · → mitigation: accepted by design (id-first
  so siblings never re-touch `compose()`)

### Goal-achievement risk: low

- None identified. The target shape is fully specified by the task, every source
  anchor was re-verified against live source, and all four behavioral unknowns
  (layout inside `TabPane`, boot focus, footer refresh semantics, focus
  traversal) were settled empirically with headless Textual 8.2.7 probes before
  planning closed.

## Verification

```bash
python3 tests/test_syncer_rows.py     # 39 existing + ~12 new, all pass
python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/syncer'); import syncer_app"
```

Harness falsifiability (per repo convention): after the suite is green, confirm
each guard actually bites — drop the tab check from `check_action` and re-run
(tests 4 and 10 must exit non-zero); drop `table.focus()` from `on_mount` and
re-run (test 2 must exit non-zero); trim `on_data_table_row_highlighted` to just
`refresh_bindings()` and re-run (test 11's `#detail` assertion must exit
non-zero). Restore by undoing the mutation only — never `git checkout --`, and
restore **both** lines of the row-highlight handler.

Manual smoke: `ait syncer` in this repo —
- tabs render; ↑/↓ moves the branch cursor immediately on open;
- `s`/`u`/`p`/`r`/`f` behave exactly as before on Branches; the footer still
  re-dims `s`/`u`/`p` and the detail pane still follows the cursor as it moves
  between `main` and `aitask-data` (both unchanged, not new);
- `Tab` once reaches the detail pane (↑/↓ scrolls it), `Tab` twice reaches the
  tab bar, then ←/→ switches tabs;
- Versions/Settings show placeholders, the Branches keys are **gone** from the
  footer there, and pressing them does nothing;
- `j` and `?` work from every tab.

## Out of scope

Any version or settings content (t1223_3 / t1223_5) and any new keybinding.

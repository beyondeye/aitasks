---
Task: t2212_minimonitor_key_hints_collapse_and_help.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2212 — minimonitor key hints: full / collapsed / full-help (+ merged t1574)

## Context

`ait minimonitor` has no Footer; its bottom-docked `#mini-key-hints` Static (`KEY_HINTS_TEXT`,
10 authored lines) is its only key surface and permanently costs ~10 rows of a ~40×20 companion
pane. The task adds:

1. **Full** band (today's, plus `x` and `H`), 2. **Collapsed** one-liner (`x:keys H:help`) that
   gives ~9 rows back to the agent list, 3. a **full-help modal** (`H`) listing every binding with a
   paragraph of explanation.

User-confirmed decisions (task body): one key `x` toggles both ways; `H` opens help (`?` stays the
shortcut editor); the collapsed/full choice persists per user in `aitasks/metadata/userconfig.yaml`,
fail-soft. Both keys rebindable under the `minimonitor` scope.

Merged **t1574**: `_refresh_short_mode` compares against `_KEY_HINTS_ROWS` (a newline count), but
below ~24 columns the band word-wraps (22 rows at width 18) so short mode never engages and the
pane-list floor breaks. Fix: a width-aware **desired** height.

### Measured facts this plan rests on (headless runs, Textual 8.2.7)

| band text | (15,30) | (18,30) | (22,30) | (40,30) |
|---|---|---|---|---|
| current | 28 | 22 | 18 | 10 |
| **chosen layout A** (x/H on line 1) | **28** | 22 | 19 | **10** |
| A with `?:rebind` instead of `?:keys` | 31 ✗ | 22 | 19 | 10 |
| collapsed `x:keys H:help` | 1 | 1 | 1 | 1 |
| collapsed, overrides as raw names `ctrl+x:keys ctrl+h:help` | 2 ✗ | 2 ✗ | 2 ✗ (and at 24) | 1 |
| same, compact display `^x:keys ^h:help` | 2 ✗ | 1 | 1 | 1 |
| any text with `text-wrap: nowrap; text-overflow: ellipsis` | 1 | 1 | 1 | 1 |

- **The collapsed band holds user-configurable text, so "one row" cannot rest on the default keys
  being short.** Override keys are arbitrary `event.key` names; the second key is what an
  ellipsis would cut. Hence: a compact key formatter + a measured fallback ladder that keeps both
  keys visible, with a structural one-row backstop (Implementation §1, §2).

- `hints.get_content_height(app.size, app.size, width - gutter)` equals the rendered region height
  at every width where the band fits on screen → usable as the desired height.
- Textual's `_modal_binding_chain` stops at a modal, so the app's `H` binding does **not** fire while
  the help modal is open — the modal must close itself on the resolved help key.
- The shortcut editor stores `event.key` names (`question_mark`, `space`, `ctrl+y`); new keys take
  effect on restart, so rendering the band from the instance's composed `self.BINDINGS` at compose
  time is exact. Shared-scope actions (`?`, `j`, `q`) get their override key in that list via
  `register_app_bindings`' shared de-dup — never resolve them through `resolve_key("minimonitor", …)`
  (tui_conventions.md, MultiRowFooter note).
- Several tests call `MiniMonitorApp.compose(app)` on an app built with `__new__` (no `__init__`) and
  read the `#mini-key-hints` Static's text; compose must not need instance state.

## Implementation

### Pre-phase (risk mitigations)

1. [red_proof_t1574_floor] Before touching `minimonitor_app.py`, add the t1574 narrow-width floor
   test (own panel `"full"`, widths 18 and 22, heights picked by measurement) to
   `tests/test_minimonitor_top_chrome_render.py` and run it against the **unmodified** predicate:
   it must FAIL (pane list overlapping the hints or 0 rows). Record the failing sizes and the
   observed regions in the plan's Final Implementation Notes; if no size fails, stop and re-measure
   before writing the fix — the case would not discriminate.

### 1. New module `.aitask-scripts/monitor/minimonitor_keys.py` (table + modal)

- `HintSeg(NamedTuple)`: `actions: tuple[str, ...]`, `label: str`, `suffix: str = ""` (`"/↑↓"`
  after `s`). A line is `(separator, tuple[HintSeg, ...])` — separators stay per line because the
  single spaces were measured choices.
- `FULL_HINT_LINES` — layout A, reproducing today's text except lines 1–2:
  ```
  x:hide H:help q:quit tab:agent          (toggle_key_hints, show_key_help, quit, focus_sibling_pane)
  i:info I:info (followed)                (show_task_info, show_own_task_info)
  s/↑↓:switch  enter:send
  d:detect ≈strip =raw
  j:switcher  m:monitor
  k:kill  n:next  e/E:shadow  o:notes     (e/E = one seg, actions (launch_shadow, launch_shadow_pick))
  c:concerns  p:pick  P:parked/frozen
  f:freeze  Z:all  h:harvest
  L:loop ?:keys M:multi S:sitrep
  space:mark ★ (followed agent)
  ```
  Line 1 hosts x/H so they stay visible when short mode clips the band to its first 2 rows.
  Move the existing row-budget comment block here, updated with the table above.
- `COLLAPSED_HINT_LINE = (" ", (HintSeg(("toggle_key_hints",), "keys"), HintSeg(("show_key_help",), "help")))`.
- `render_collapsed(keymap, content_width: int | None) -> str` — a measured ladder, first rung
  whose `rich.cells.cell_len` fits `content_width` (None ⇒ rung 1):
  1. `<toggle>:keys <help>:help` (defaults: `x:keys H:help`, 13 cells — fits at width 15);
  2. `<toggle> <help>` — keys only, so both ACTIVE shortcuts stay visible (`^y ^u`, `alt+y alt+u`).
  Guarantee stated in the docstring: the band is always one row (CSS backstop below); both keys are
  visible whenever rung 2 fits, i.e. `cell_len(a) + 1 + cell_len(b) ≤ width − 2` — at width 15 any
  two keys of ≤ 6 display cells each (every single key, `^y`, `alt+y`); at 24, ≤ 10 cells each
  (`shift+f12`). Longer chords at narrower widths get an ellipsised tail, still on one row.
- `key_display(key)` — the ONE formatter used by the band, the collapsed line and the modal.
  Split modifiers from the base key with `Binding(key, "").parse_key()`; base = `key_to_character`
  when printable and not whitespace (`question_mark`→`?`), else the key name (`space`, `tab`,
  `enter` kept as names so the default band text and `test_key_hints_surface_every_binding`'s
  `enter:` form are unchanged); `ctrl` becomes a `^` prefix exactly as Textual's
  `App.get_key_display` does (`ctrl+x`→`^x`, `ctrl+shift+f12`→`shift+^f12`); other modifiers stay
  `+`-joined (`alt+x`).
- `binding_keymap(bindings) -> dict[action, key]`; `render_hints(lines, keymap) -> str` (keys of a
  seg joined by `/`, then `suffix`, `:`, label; segs joined by the line's separator).
- `KEY_HELP: tuple[HelpEntry, ...]` — `HelpEntry(actions: tuple[str, ...], title, body)`; one entry
  per binding action plus two non-binding entries (`↑/↓` card navigation, mouse) with a literal key
  field. Bodies condensed from `website/content/docs/tuis/minimonitor/how-to.md` with a top-of-block
  source-trace comment plus per-entry `# Source: how-to.md — "<section>"` (code_conventions.md). The
  `?` entry says it opens the shortcut editor to rebind any key (takes effect on restart); the `x`
  entry notes the choice is remembered in `userconfig.yaml`.
- `KeyHelpModal(GuardedModalScreen)` (from `lib/guarded_dismiss`), self-contained `DEFAULT_CSS`:
  `#mm-help-dialog { width: 100%; max-width: 64; height: 100%; max-height: 100%; border: round $accent; padding: 0 1; }`,
  `VerticalScroll#mm-help-scroll { height: 1fr; }`, one `Static` per entry (`[b]<escaped keys>[/b] <title>`
  then body; keys/text through `rich.markup.escape`), footer `Label` `"Esc/<help key display> close"` (≤ 20 cells
  with the default key so it fits 24 columns; `height: auto`, so a long override wraps rather than
  clipping). `__init__(keymap, close_keys)`; `BINDINGS = [escape → close, q → close]`;
  `on_key`: if `event.key in close_keys` → `event.stop()` + `self.dismiss(None)`; `on_mount` focuses
  the scroll so ↑↓/PgUp/PgDn scroll.

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

- `BINDINGS`: add `Binding("x", "toggle_key_hints", "Collapse key hints", show=False)` and
  `Binding("H", "show_key_help", "Key help", show=False)` with a comment: both free in `ait monitor`
  too and deliberately left unbound there (parity).
- Replace the `KEY_HINTS_TEXT` literal: after the class,
  `KEY_HINTS_TEXT = render_hints(FULL_HINT_LINES, binding_keymap(MiniMonitorApp.BINDINGS))` and
  `KEY_HINTS_COLLAPSED_TEXT` likewise (importable for every current consumer).
  `_KEY_HINTS_ROWS = len(FULL_HINT_LINES)` (authored count = rendered height at 40 cols, still pinned).
- `__init__(…, key_hints_collapsed: bool = False)` → `self._key_hints_collapsed`.
- `_active_keymap()` → `binding_keymap(self.BINDINGS)` (instance list = post-override).
- `_key_hints_text(content_width=None)` → collapsed (`render_collapsed`) or full render of
  `_active_keymap()`, reading `getattr(self, "_key_hints_collapsed", False)` so `__new__`-built test
  apps still compose. `compose()` yields `Static(self._key_hints_text(), id="mini-key-hints",
  classes="collapsed" if collapsed else "")`.
- CSS backstop: `#mini-key-hints.collapsed { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }`
  — the one-row promise is structural, whatever key names an override produces.
- `_sync_key_hints_text()`: compute `content_width = self.size.width - hints.styles.gutter.width`,
  render the current mode's text for it, `update()` only when it differs, and keep the `collapsed`
  class in step with the flag. Called at the top of `_refresh_short_mode`, so every resize (already
  scheduled from `on_resize`) re-picks the collapsed rung before the predicate measures.
- `action_toggle_key_hints()`: flip the flag, `_sync_key_hints_text()`,
  `_schedule_short_mode_refresh()`, then persist via `userconfig_persist.set_minimonitor_key_hints_collapsed`;
  any exception → `self.notify("Key-hint mode not saved: …", severity="warning")` (session toggle stands).
- `action_show_key_help()`: `keymap = self._active_keymap()`; push
  `KeyHelpModal(keymap, close_keys=(keymap["show_key_help"],))`.
- `_key_hints_desired_rows()`: `hints.get_content_height(self.size, self.size, max(1, self.size.width - hints.styles.gutter.width))`;
  on exception fall back to the current text's line count.
- `_refresh_short_mode`: use `_key_hints_desired_rows()` in place of `_KEY_HINTS_ROWS`; rewrite the
  docstring's no-oscillation argument: the desired height is the content height of the current
  mode's text at the current width — independent of `max-height` (the only thing `.short` changes) and
  of the chrome — so the class still never feeds its own input. Collapsed ⇒ desired = 1.
- `main()`: pass `key_hints_collapsed=userconfig_persist.get_minimonitor_key_hints_collapsed()` (read
  only in the production launcher, so directly-constructed test apps never read the real userconfig).
- grep `.aitask-scripts/` for other `KEY_HINTS_TEXT` users and keep them working.

### 3. `.aitask-scripts/lib/userconfig_persist.py`

- `get_minimonitor_key_hints_collapsed() -> bool`: `_load_full().get("minimonitor_key_hints") == "collapsed"`;
  `MalformedUserConfigError` → stderr note + `False`; `OSError` → `False`; any other value → `False`.
- `set_minimonitor_key_hints_collapsed(collapsed: bool)`: round-trip `_load_full` → set
  `"collapsed"`/`"full"` → `_atomic_dump`. Malformed config raises (never overwrite it). Module
  docstring key list gains the new key.

### 4. Tests

- **New `tests/test_minimonitor_key_hints_modes.py`** (scratch cwd + `TASK_DIR`, registry
  `_reset_for_tests()` + `register_shared_bindings()` around each test, `TMUX` unset):
  - parity: every binding action is in `FULL_HINT_LINES` and has exactly one `KEY_HELP` entry; no
    table/help action without a binding; `toggle_key_hints`/`show_key_help` are in both and in the
    collapsed line; every full-band line ≤ 38 cells; line 1 carries both new keys.
  - `key_display` unit table: defaults render byte-identical to today's names (`enter`, `space`,
    `tab`, `?`), `ctrl+y`→`^y`, `alt+y`→`alt+y`, `ctrl+shift+f12`→`shift+^f12` (== Textual's
    `App.get_key_display` for each — asserted against it, not a hand-copied literal).
  - override render **and dispatch**, single keys: overrides `toggle_key_hints: y`,
    `show_key_help: Y` → band shows `y:hide`/`Y:help`, not `x:`/`H:`; pressing `y` collapses (`x`
    does nothing); `Y` opens the modal, the modal shows `Y`, and `Y` closes it.
  - **long modifier overrides, collapsed** — matrix of override pairs `(ctrl+y, ctrl+u)` and
    `(alt+y, alt+u)` × widths 15/18/22/24/40: band region height == 1 AND both active key displays
    appear in the composited band row (read from `_compositor.render_strips`, not from the widget
    text), and the rung is the one this literal table expects (content width = width − 2; rung 1 is
    15 cells for `^y:keys ^u:help`, 21 for `alt+y:keys alt+u:help`):

    | pair \ width | 15 (13) | 18 (16) | 22 (20) | 24 (22) | 40 (38) |
    |---|---|---|---|---|---|
    | `ctrl+y`, `ctrl+u` | 2 | 1 | 1 | 1 | 1 |
    | `alt+y`, `alt+u` | 2 | 2 | 2 | 1 | 1 |

    Same pairs, dispatch: pressing `ctrl+y` toggles both
    ways, `ctrl+u` opens the modal and closes it.
  - **one-row backstop**: overrides `(ctrl+shift+f11, ctrl+shift+f12)` at widths 15–40 → band height
    is still exactly 1. Companion control: with the `.collapsed` CSS rule removed (class not set),
    the same case renders > 1 row at 18 — proves the backstop is what holds it.
  - resize, both transitions, each crossing a real rung boundary from the table above: collapsed
    with `(alt+y, alt+u)` at 40 shows rung 1 → `pilot.resize_terminal(18, 30)` → rung 2 → back to 40
    → rung 1; and `(ctrl+y, ctrl+u)` 40 → 15 → 40 (rung 1 → 2 → 1). Band height stays 1 throughout.
  - full band with `(ctrl+shift+f11, ctrl+shift+f12)` overrides at 22: `_key_hints_desired_rows()`
    equals the rendered height (long overrides cost honest, measured rows in full mode).
  - modal: at (24,20) and (40,20) the dialog fits the screen, the scroll is scrollable, every binding's
    displayed key appears in the content; `escape`, `q`, `H` each close it.
  - persistence: get/set round-trip; other keys (`email`, `shortcuts`) preserved; malformed file → getter
    `False`, setter raises, file bytes unchanged; unknown value → `False`; app toggle with a malformed
    config still collapses and calls `notify` with warning severity.
  - startup: `key_hints_collapsed=True` boots with a 1-row band; `main()` passes the getter's value
    (patch `MiniMonitorApp` with a kwargs-capturing stub, `sys.argv`, `_detect_tmux_session`).
  - parity with full monitor: `x` and `H` unbound in `monitor_app.MonitorApp.BINDINGS`.
- **`tests/test_minimonitor_top_chrome_render.py`**:
  - `_ChromeFixture.setUp` points `TASK_DIR` at a temp dir (keys pressed here must never write the real
    userconfig).
  - collapsed geometry: 1 row at (40,30) and (22,30); pane list grows by `_KEY_HINTS_ROWS - 1`;
    `x` round-trips to `_KEY_HINTS_ROWS`; collapsed holds 1 row through short-mode engage/release;
    expanding while short gives `_SHORT_HINT_ROWS`.
  - t1574 width sweep: at widths 18/22/24/30/40 (tall pane) `_key_hints_desired_rows()` equals the
    rendered band height, and is identical with `.short` on and off (no feedback).
  - t1574 floor: own panel `"full"` at widths 18 and 22, heights chosen by measurement where the old
    predicate fails → pane list ≥ 1 row and above the hints. Companion **mutant control** in the same
    class: patch `_key_hints_desired_rows` to return `_KEY_HINTS_ROWS` and assert the same case DOES
    break, proving the case discriminates.
- Existing consumers (`test_minimonitor_concern_action`, `_own_mark`, `_own_task_info`,
  `_pick_by_number`, `_scratchpad_spawn`, `_shadow_pick`, `test_monitor_agent_marks`,
  `_parked_filter`, `_frozen_filter`): run unchanged; fix any literal that assumed old lines 1–2.

### 5. Docs — `website/content/docs/tuis/minimonitor/how-to.md`

- New section "How to Collapse the Key Hints or Open the Full Key Help" (before "How to Quit"): `x`
  toggles, remembered per user as `minimonitor_key_hints: collapsed|full` in `userconfig.yaml`; `H`
  opens the scrollable help; `?` still rebinds.
- Quick Reference: add `x`, `H`, and the missing `h` (harvest followed agent) and `S` (sitrep window).
- If a userconfig-key reference page exists under `website/content/`, add the key there.
- `cd website && python3 check_links.py --build`.

### Step 9

Post-implementation per the shared workflow (review, commit `feature: … (t2212)`, archival; folded
t1574 is deleted at archival).

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir <scratch dir holding the touched modules>   # or per file:
~/.aitask/venv/bin/python -m pytest -q tests/test_minimonitor_key_hints_modes.py \
  tests/test_minimonitor_top_chrome_render.py tests/test_minimonitor_concern_action.py \
  tests/test_minimonitor_own_mark.py tests/test_minimonitor_own_task_info.py \
  tests/test_minimonitor_pick_by_number.py tests/test_minimonitor_scratchpad_spawn.py \
  tests/test_minimonitor_shadow_pick.py tests/test_monitor_agent_marks.py \
  tests/test_monitor_parked_filter.py tests/test_monitor_frozen_filter.py \
  tests/test_shortcut_scopes.py tests/test_shortcuts_mixin_live_remap.py
cd website && python3 check_links.py --build
```
Then the full python suite (`bash tests/run_all_python_tests.sh`, read the last line only), and a
live check in tmux: `ait minimonitor` beside an agent — `x` collapses/expands, a new minimonitor opens
in the last mode, `H` opens the help at 40 and ~24 columns and closes with Esc/H/q.

## Risk

### Code-health risk: medium
- `_refresh_short_mode` is load-bearing and its no-oscillation argument changes: if `get_content_height` turned out to depend on the `.short` max-height or on scrollbar state, the class could feed its own input · severity: medium (residual — the predicate change is red-proven on real code by inline pre-phase red_proof_t1574_floor; no-feedback covered in-plan by the desired-rows-identical-with-short-on/off test + the existing convergence test) · → mitigation: inline pre-phase red_proof_t1574_floor
- `userconfig_persist` is read-modify-write with no lock; two minimonitors toggling at once, or a toggle racing the shortcut editor's save, can drop the other writer's change (pre-existing pattern shared with `shortcut_persist`, now reachable from one more key) · severity: low · → mitigation: userconfig_write_lock
- The band becomes table-rendered and lines 1–2 change; nine test files read the band text and the (15,30) ≤ 29 budget is tight (layout A measures 28) · severity: low · → mitigation: TBD (in-plan: measured, existing tests rerun)

### Goal-achievement risk: low
- The collapsed band's one-row promise holds user-configurable key names; reproduced: `ctrl+x:keys ctrl+h:help` renders 2 rows at widths 18 and 24 (review finding) · severity: low (residual — compact `^` formatter + measured labels→keys-only ladder keep both active keys visible, the `.collapsed` nowrap/ellipsis rule makes one row structural; covered by the long-modifier-override matrix, the backstop control and dispatch tests) · → mitigation: none (in-plan)
- At width 15 the overflowing band gains a scrollbar and re-wraps, so the measured desired height is an approximation there; the t1574 floor is proven at widths 18/22, not below · severity: low · → mitigation: inline pre-phase red_proof_t1574_floor
- Help-modal descriptions are condensed from the how-to doc by hand and can drift from behaviour · severity: low · → mitigation: none (in-plan: source-trace comments + parity test that every binding has an entry)

### Planned mitigations
- timing: pre-phase | name: red_proof_t1574_floor | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: short-mode predicate change / t1574 floor proof | desc: write the narrow-width floor test first and confirm it fails on the unmodified predicate
- timing: after | name: userconfig_write_lock | type: bug | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: unlocked read-modify-write in userconfig_persist | desc: serialize userconfig_persist load+dump with a file lock so concurrent writers (minimonitor toggles, shortcut editor saves) cannot drop each other's changes

## Final Implementation Notes

- **Actual work done:** all plan steps 1–5 as written. New `.aitask-scripts/monitor/minimonitor_keys.py`
  (hint table, `key_display`, `render_hints` / `render_collapsed`, `KEY_HELP`, `KeyHelpModal`);
  `minimonitor_app.py` binds `x` / `H`, derives `KEY_HINTS_TEXT` / `KEY_HINTS_COLLAPSED_TEXT` from
  the table after the class, measures the band's desired height (`_key_hints_desired_rows`), re-renders
  it per width (`_sync_key_hints_text`, called at the top of `_refresh_short_mode`), carries the
  `.collapsed` one-row CSS backstop, and reads the persisted mode in `main()` only;
  `userconfig_persist.py` gains `get_/set_minimonitor_key_hints_collapsed`; the minimonitor how-to gains
  the new section and the `x` / `H` / `h` / `S` quick-reference rows.
- **Pre-phase `red_proof_t1574_floor` (done before the fix):** `test_pane_list_keeps_a_row_at_narrow_widths`
  FAILED on the unmodified predicate. Measured regions (own panel full, no banners, no session bar):
  (18, 28) → list `(y=7, h=1)` under hints `(y=2, h=26)`; (22, 24) → list `(y=7, h=1)` under hints
  `(y=4, h=20)`; `short` never engaged. A wider sweep found the same break at every height ≤ 28 (w18)
  and ≤ 24 (w22) with no banners. Passes after the fix; the in-suite mutant control
  (`test_the_narrow_cases_need_the_measured_height`) pins that the cases discriminate.
- **Deviations from plan:**
  - `on_mount` also schedules the short-mode refresh (before the TMUX early return), so a collapsed
    band fits its measured width at startup even without a resize event.
  - The help-modal footer is a `Content`, not a markup string — a key rebound to `[` would otherwise be
    parsed as a tag.
  - `HelpEntry`'s paragraph field is `description`, not the planned `body`: `tests/test_concern_body_display_contract.py` audits every `.body` read in the monitor package
    and allows no per-site exemptions; a help paragraph is not a concern body, so the field was
    renamed rather than adding `HelpEntry` to the guard's `NON_CONCERN_TYPES` allowlist.
- **Issues encountered:** the first full-suite run failed 3 `test_concern_body_display_contract` cases
  (the `.body` read above — fixed by the rename) and `test_monitor_shadow_zone::test_restore_focus_refuses_a_hidden_shadow_column`, which passed 3/3 in isolation and does not touch
  minimonitor (parallel-lane flake). Verified with three in-process mutants (no file edits) that
  the new tests catch: (a) `render_collapsed` always returning the labelled rung → 6 failures across
  the rung matrix and resize tests; (b) the `.collapsed` CSS rule removed → the backstop test and its
  control fail; (c) the modal ignoring its close key → close and dispatch tests fail.
- **Key decisions:** keys come from the composed `self.BINDINGS` (never `resolve_key`), so shared-scope
  overrides (`?`, `j`, `q`) show too; `_KEY_HINTS_ROWS` stays the authored line count (40-column height)
  for the existing pins, while the predicate measures.
- **Upstream defects identified:** None.

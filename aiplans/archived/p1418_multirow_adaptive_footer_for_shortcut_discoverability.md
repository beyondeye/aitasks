---
Task: t1418_multirow_adaptive_footer_for_shortcut_discoverability.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1418 — Multi-row adaptive footer for shortcut discoverability

## Context

`ait board` declares 45 bindings on its main screen; 27 are `show=True`, totalling
~385 columns of label text. Textual 8.2.7's `Footer` is a single `height: 1`
horizontal strip, and its overflow is reachable **only by horizontal mouse-wheel
scroll** (`Footer._on_mouse_scroll_down/up`) — a keyboard user has no way to learn
that a key exists. Measured against the real `Footer` with the board's own key set:

| terminal width | keys fully visible (stock `Footer`) |
|---|---|
| 200 | 16 / 27 |
| 160 | 13 / 27 |
| 120 | 9 / 27 |

t1243_7 already hit this wall and hid `m` (Move to Col) with an explicit comment
that the footer "is already full at 200 columns". That constraint is what this
task removes: build a shared, width-adaptive multi-row footer widget and adopt it
on the board.

CSS alone cannot fix it — `Footer.compose()` ends with
`self.styles.grid_size_columns = len(action_to_bindings)`, so a subclass that only
sets `layout: grid` still gets one row. The layout must be re-asserted *after*
`super().compose()` runs, and must survive the recompose that `bindings_changed`
triggers on every `bindings_updated` signal.

**Everything below was measured**, not projected — with a headless `run_test`
harness driving the real `Footer` at nine widths under both CPython 3.14 and
PyPy 3.11 (both venvs carry textual 8.2.7; pin is `textual>=8.2.7,<9`).

## Approach

Subclass `Footer`. In `compose()`, run the parent generator through Textual's own
public composer — `textual.compose.compose(self, super().compose())` — and re-place
the resulting real `FooterKey` / `KeyGroup` / `FooterLabel` widgets into packed
`HorizontalGroup` rows inside a `layout: vertical; height: auto` footer.

Using `textual.compose.compose` rather than `list(super().compose())` is
deliberate: `Footer.compose()` builds grouped bindings with a `with KeyGroup(...)`
context manager, which pushes onto `app._compose_stacks` instead of yielding. A
bare `list()` would silently produce empty `KeyGroup`s and corrupt the caller's
compose stack. The public composer gives it fresh stacks and returns fully-formed
top-level widgets.

Reflowing upstream's own widgets (rather than re-deriving bindings, as
`codebrowser.ContextualFooter` does) keeps every piece of upstream machinery
working for free: `screen.active_bindings` (so `check_action` gating still
hides/disables keys), `FooterKey.on_mouse_down` click-to-fire, key-display
resolution via `app.get_key_display`, the `bindings_updated` recompose
subscription, and the `-command-palette` key.

### Row planning (deterministic, order-preserving)

Two pure functions, unit-testable without mounting anything:

- `footer_item_width(item, *, footer_compact)` — the column cost of one composed
  item, per the measured model below. **Measure every rendered text component in
  cells, not characters** — `cell_len` from `rich.cells` (the spelling already used
  at `tests/test_board_filter_row_layout.py:26`; there is no `rich.cell`). That
  means the key display, the binding description, the group caption **and** the
  overflow-hint text. Terminal columns are cells, so `len()` undercounts every
  wide/CJK glyph by one column each and the row silently overflows.
- `plan_footer_rows(costs, width, max_rows, *, hint_cost, pinned_tail)` →
  `(rows_of_indices, dropped_count)`.

**Measured width model** (textual 8.2.7). The quantity that matters for packing is
`outer_size.width + margin.left + margin.right` — **`outer_size` excludes margins**,
and margins *collapse* between adjacent siblings, so neither can be ignored:

Below, `kd` = `cell_len(key_display)`, `desc` = `cell_len(description)`,
`cap` = `cell_len(caption)` — never `len()`.

| composed item | width | notes |
|---|---|---|
| plain `FooterKey` | `kd + desc + 3` (non-compact) / `+ 2` (compact) | non-compact = key padding `0 1` + desc padding-right 1; compact = padding 0/`0 0 0 1` + `margin-right: 1` |
| `-command-palette` `FooterKey` | `kd + desc + 3` in **both** modes | it is never `data_bind`-ed, so it always carries `-compact`; padding-right 1 + `border-left: vkey` non-compact, padding-right 0 + border + margin 1 compact |
| `FooterLabel` (group caption) | `cap + 1` (non-compact) / `cap + 0` (compact) | `margin: 0 1 0 0`, zeroed under the footer's `-compact` |
| `KeyGroup`, `Group(compact=False)` | `Σ kd + n + 1` | children are `margin: 0 1` and **collapse**: 2 children of width 1 measure 5, not 6 |
| `KeyGroup`, `Group(compact=True)` | `Σ kd + 2` | children `margin: 0`; group gets `padding-left: 1` + `margin-right: 1` |

Verified against wide text: a `保存文件` description measures 12 cells non-compact
(`len()` predicts 8) and a `导航栏` group caption measures 7 (`len()` predicts 4).

Grouped children always carry `description=""`, and `FooterKey.render()` skips
padding entirely on that branch — which is why `Σ kd` is the right inner term.
Both `KeyGroup` widths are independent of the footer's compact flag; only the
group's own `-compact` class matters. Note also that Textual forces `show=False`
on any binding with an empty description, so a *top-level* shown key always has
one; keep the no-description branch as a defensive fallback.

The planner is **greedy first-fit at full width**, preserving declaration order so
muscle memory holds. Row count is emergent, not computed: content that fits stays
on one row, so a wide terminal renders exactly as today and the footer only grows
when it must.

The command-palette key is passed as a **pinned tail** — the last item in the cost
list, never droppable. That is what makes its row *be* the last row by
construction. An earlier design that tried to reserve its width for "the last row"
computed the wrong row (the final row count isn't known until packing finishes)
and let `O Options` collide with it at 200 and 400 columns.

The planner runs at most twice:

1. Pack with the pinned tail's width reserved from every row, so the palette key
   always shares the final content row instead of sitting alone on a row of its own.
2. If (and only if) that forces drops, re-pack **without** the reservation, so
   coverage wins over tidiness at narrow widths (measured: 26 keys visible at 120
   columns instead of 24).

`hint_cost` must be an upper bound in **cells**, not the width of the hint as
finally rendered: the dropped count `N` is only known *after* dropping, and the
resolved key display varies (`?` is 1 cell, `f1` is 2, a wide glyph is 2). Reserve
`cell_len` of the hint formatted with the largest plausible `N` (the total item
count) and the resolved key, so the affordance can never itself overflow the row
it announces.

### Measured behavior (board key set, all four keys un-hidden = 31 footer items)

| width | rows | keys shown | palette | clipped | overlap | overflow hint |
|---|---|---|---|---|---|---|
| 460 | 1 | 31 / 31 | bottom-right | none | none | — |
| 440 | 1 | 31 / 31 | bottom-right | none | none | — |
| 400 | 2 | 31 / 31 | bottom-right | none | none | — |
| 240 | 2 | 31 / 31 | bottom-right | none | none | — |
| 200 | 3 | 31 / 31 | bottom-right | none | none | — |
| 160 | 3 | 31 / 31 | bottom-right | none | none | — |
| 120 | 3 | 26 / 31 | bottom-right | none | none | `+5 more (?)` |
| 100 | 3 | 22 / 31 | bottom-right | none | none | `+9 more (?)` |
| 80 | 3 | 15 / 31 | bottom-right | none | none | `+16 more (?)` |

`footer_max_rows` at 200 columns: `1` → 13 keys + `+18 more (?)`; `2` → 29 keys +
`+2 more (?)`; `3` → all 31.

## Decisions settled with the user

- **Over-cap behavior:** drop the tail and render a muted `+N more (?)` indicator
  as the last item of the last row, before the palette key. Keyboard users learn
  that more exists and where to find it. A scrollable last row was rejected — it
  reintroduces exactly the mouse-only invisibility this task removes.
- **`footer_max_rows` default = `3`.** It is the only value that satisfies the
  "every shown binding at 200 columns" criterion. `1` restores today's single-row
  behavior (now with an honest `+N more` hint instead of silent clipping).
- **AC amendment (400 columns).** The task's AC says the footer "still renders as a
  single row" on a 400-column terminal. Un-hiding four keys adds ~45 columns of
  content, moving the single-row threshold to ~440. The AC is restated as: *renders
  exactly one row whenever the total content fits the available width* (measured:
  ≥440 with the four new keys). The real invariant — the footer grows only when it
  must — is preserved. **Update the AC in the task file as part of this change**;
  do not leave it silently contradicted.
- **`ctrl+p` stays.** It is not a duplicate of `?`: `KanbanCommandProvider`
  (`aitask_board.py:5782`) exposes 9 commands, of which **Add / Edit / Delete /
  Expand Column and Clear Selection have no key binding at all**, plus Textual's
  built-ins. `?` lists and *rebinds* keys, so it can only reach operations that
  already have one. Neither subsumes the other. Reconciling the two surfaces is
  **out of scope** — record it as a follow-up in the Final Implementation Notes.

## Files

### 1. New — `.aitask-scripts/lib/multirow_footer.py`

Dependencies limited to `textual` + stdlib + the two `lib/` config helpers, so it
imports cleanly under both PyPy (the board's fast path) and CPython — the same
discipline `lib/numbered_source_view.py:26-28` documents.

- `DEFAULT_MAX_ROWS = 3`, module-level `_MAX_ROWS_CACHE`, `_resolve_max_rows()`,
  `refresh_max_rows()` — a direct transcription of the `shortcut_label_case`
  precedent at `.aitask-scripts/lib/shortcuts_mixin.py:39-73`: read once via
  `load_yaml_config(_userconfig_path())` (from `config_utils` /
  `userconfig_persist`), cache, expose a refresh hook for tests, and **fail soft**
  — `load_yaml_config` raises on malformed YAML, so a bare `except Exception`
  degrades to the default. A malformed gitignored userconfig must not crash every
  TUI. Clamp to `1..6`; any non-integer or out-of-range value falls back to the
  default.
- `footer_item_width()` and `plan_footer_rows()` as specified above.
- `class MultiRowFooter(Footer)` with:
  - `DEFAULT_CSS` nesting `layout: vertical; height: auto`, a
    `HorizontalGroup.-footer-row { height: 1; width: 1fr; }` rule, and a muted
    `Static.-footer-overflow` rule. Subclass `DEFAULT_CSS` outranks `Footer`'s on
    Textual's MRO tie-break, so `dock: bottom` is inherited while `height: 1` is
    overridden.
  - `__init__(..., max_rows: int | None = None, hint_action: str | None = None)` —
    `max_rows=None` resolves from userconfig.
  - **`hint_action`, not a literal key.** The `+N more (…)` affordance must name
    the key that actually opens the shortcuts editor. Resolve it at compose time
    from the composed set: find the `FooterKey` whose `.action == hint_action` and
    use its `.key_display`. Textual already resolved that display through
    `app.get_key_display(binding)`, so it tracks any user remap for free, needs no
    registry import, and degrades to a bare `+N more` when the action is absent
    (a TUI without the editor). Look it up in the **pre-drop** composed set so the
    hint is correct even if that key were itself dropped.

    Do **not** use `resolve_key("board", "open_shortcuts_editor")`. Verified:
    `shortcuts_mixin.py:196` registers that action under the **`shared`** scope, and
    `register_app_bindings` (`keybinding_registry.py:127`) deliberately does not
    shadow shared actions into the app scope — so with the editor remapped to `f1`,
    `resolve_key("board", …)` returns `None` and `… or "?"` yields a stale `?`,
    breaking the affordance precisely for customized setups.
  - `compose()` — compose → split off `-command-palette` → plan → yield rows.
  - `on_resize()` → `call_after_refresh(self.recompose)`, so the row count tracks
    terminal width as well as `bindings_updated`.

### 2. `.aitask-scripts/board/aitask_board.py`

- Import `MultiRowFooter` alongside the existing bare-name `lib/` imports
  (`sys.path` is already set at line 15).
- `KanbanApp.compose()` (line 6478-6480): yield
  `MultiRowFooter(hint_action="open_shortcuts_editor")` instead of `Footer()`.
  Keep `footer.can_focus = False`.
- Flip four bindings to footer-visible — `ctrl+up` Task Top (6119), `ctrl+down`
  Task Btm (6120), `m` Move to Col (6175), `X` Collapse Col (6180).
- **Rewrite the t1243_7 comment at 6165-6175.** It currently asserts the footer is
  full at 200 columns; leaving it would contradict the code. Replace with a note
  that the multi-row footer removed the constraint, keeping the surviving facts
  (`check_action` still gates `m`; the palette entry still exists).
- Leave `a l f i y z g t` `show=False` — `ViewSelector` (line 1844) already renders
  them in the filter row, so footer entries would duplicate, not reveal. Leave the
  plain navigation keys (arrows / `tab` / `escape`) hidden.

No board CSS change is needed: `KanbanApp.CSS` has no `Footer` rule today, and the
docked-bottom auto-height footer shrinks `#board_container` automatically.

### 3. Docs

- `aidocs/framework/tui_conventions.md` — extend the existing
  "TUI footer must surface every operation on the affected tab/screen" section
  (lines 387-407) with a bullet pointing at `lib/multirow_footer.py` as the way to
  *satisfy* that rule when a screen has more keys than one row holds, so
  "no room in the footer" stops being a reason to hide a binding.
- `website/content/docs/tuis/_index.md` — document `footer_max_rows` under the
  existing "Where customizations live" userconfig section (~line 61), which
  already carries the `userconfig.yaml` sample.
- `website/content/docs/tuis/board/_index.md:35` — the footer bullet becomes
  "wraps to multiple rows on narrow terminals".

Do **not** seed `footer_max_rows` into `aitask_setup.sh`. The code default is the
single source; seeding it is what left `shortcut_label_case` with a seeded value
(`preserve`) that disagrees with its code default (`upper`).

## Tests

### `tests/test_multirow_footer.py` (new)

Pure-function tests (no mounting): row membership and counts across widths,
order preservation, determinism, `pinned_tail` never dropped, room reserved for
the hint, `max_rows=1`, and the `width <= 0` guard.

Render-level tests per `feedback_tui_render_level_verification`, using the
standard harness shape (`sys.path` bootstrap from `__file__`, `asyncio.run`, a
minimal host `App`; a fresh app instance per size, as
`tests/test_brainstorm_node_hub.py:243-265` does):

- Pin the measured table above: row count and per-row key membership at
  440 / 400 / 240 / 200 / 160 / 120 / 100 / 80.
- **No clipping:** every mounted `FooterKey` has `region.right <= width`.
- **No palette collision:** no key on the palette's row overlaps its x-range.
- **Palette is bottom-right:** always on the last row, never alone on it.
- **Ground truth for the cost model — every planner input, not just plain keys.**
  For **each** top-level composed item, assert
  `footer_item_width(item, footer_compact=…) == item.outer_size.width + margin.left + margin.right`.
  Margins are the whole point: `outer_size` excludes them, so a check against
  `outer_size` alone silently passes while the row overflows. Run the assertion over
  a fixture **matrix**, since each cell has a different rule (see the width table):
  `{footer compact, non-compact}` × `{plain FooterKey, Group(compact=False) KeyGroup
  + its FooterLabel, Group(compact=True) KeyGroup + its FooterLabel,
  -command-palette FooterKey}`. Also assert the collapsed-margin term directly —
  a non-compact `KeyGroup` of two 1-cell children measures **5**, not 6 — because
  that is the term a naive `sum(child totals)` gets wrong. This is the tripwire that
  turns a Textual padding/margin change into a loud failure instead of clipping.
- **Wide-character fixture (cells, not characters).** Add a CJK binding description
  *and* a CJK group caption to the matrix. This is a shared widget, and a `len()`
  cost is a *silently* clipping bug rather than a failing one. Assert the predicted
  widths (`保存文件` description = 12 cells non-compact, `导航栏` caption = 7) and,
  at a width narrow enough to force packing, that no `FooterKey.region.right`
  exceeds the terminal width. Measured evidence worth keeping in the docstring:
  with `len()`-based costs and CJK labels at 40 columns two keys render at x-right
  **48 and 60** — entirely off-screen — while `cell_len` costs overflow nothing.
- **Hint appears iff keys were dropped** — guards the spurious-`+N more` bug an
  earlier planner draft produced while room still remained.
- **Resize reflow and settling.** `pilot.resize_terminal(460→160)` changes the row
  count — and the sequence must be shown to *terminate*. The footer's own
  `height: auto` changes its size when the row count changes, which emits a second
  `Resize` on the footer, which recomposes again: a real feedback path that must
  converge rather than flicker. Instrument a compose counter and assert, per
  `feedback_bounded_recovery_envelope_and_best_effort_contract`, that after one
  terminal resize the widget composes **at most twice** and that further idle
  `pilot.pause()` cycles add **zero** composes and zero resize events. Measured
  today: 460→160 = 2 composes / 2 resizes then stable; 160→100 (no row change) = 1
  / 1; 300 = 2 / 2. Pin a boot bound too (currently 4 composes at 460). Include the
  no-row-change case, which must not recompose twice.
- **Overflow hint tracks a remapped key.** Bind the hint action to a non-default
  key in the host app and assert the hint renders that key, not a hardcoded `?`;
  assert it degrades to a bare `+N more` when no binding carries `hint_action`.
  Pair it with a board-level case that sets a `shared` scope override
  (`keybinding_registry._OVERRIDES_CACHE`, reset in `tearDown`) for
  `open_shortcuts_editor` and asserts the board's hint follows it — the case that
  the rejected `resolve_key("board", …)` approach fails.
- **`footer_max_rows`:** temp tree + `TASK_DIR`, `refresh_max_rows()` in `setUp`
  *and* `tearDown`, a cache-staleness test, and malformed YAML → default — mirroring
  `tests/test_shortcut_label_case.py:39-103`.
- **Negative control** (`feedback_negctrl_proves_test_discriminates`): the same
  coverage assertion run against the stock `Footer` must **fail**. Assert
  positively that stock clips at 200 columns, so the control fails loudly if it
  ever stops discriminating.

### `tests/test_board_footer_multirow.py` (new, board fixture)

Uses `tests/lib/board_fixture.py` (`FixtureBoardTestBase`). Asserts the board
mounts a `MultiRowFooter`; that `move_to_column`, `toggle_column_collapsed`,
`move_task_top`, `move_task_bottom` are footer-**visible**; that
`view_all/locked/free/inflight/bytopic/bytrail/git/type` remain `show=False`; and
that `check_action` gating still removes `move_to_column` from the rendered footer
when no card is focused. Key footer assertions by **action**, not by key
(`tests/test_syncer_rows.py:700-712`), so a user rebind cannot break them.

Existing board tests should be unaffected: `show` does not change
`active_bindings` membership, which is what `test_board_move_command.py:690-711`
and `test_board_footer_visibility.py:63-68` assert.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST stderr line
# targeted:
~/.aitask/venv/bin/python -m pytest tests/test_multirow_footer.py \
    tests/test_board_footer_multirow.py tests/test_board_move_command.py \
    tests/test_board_footer_visibility.py -q
# PyPy (the board's actual runtime) — import + mount smoke:
~/.aitask/pypy_venv/bin/python -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); \
    import multirow_footer; print(multirow_footer.MultiRowFooter)"
```

Then a live look, since visibility claims need a real terminal
(`feedback_visibility_claims_need_real_terminal`): run `ait board` in a tmux pane
at ~200 and ~120 columns, capture the pane, and confirm the footer renders 3 rows
with `m` / `X` / `ctrl+up` / `ctrl+down` legible and `ctrl+p` bottom-right.

## Risk

### Code-health risk: medium
- The cost model mirrors constants spread across Textual's private
  `FooterKey.render()`, its CSS padding, **and** margin/collapsing rules that differ
  per item kind and per compact flag; a Textual upgrade could shift any of them and
  silently reintroduce clipping · severity: medium · → mitigation: covered in-scope
  by the ground-truth matrix test, which asserts every planner input's predicted
  width against its real `outer_size + margins` in both compact modes — including a
  wide-character fixture, since cell-vs-character miscounting clips silently — and
  converts a silent drift into a loud failure
- The module imports the private `textual.widgets._footer` names
  (`FooterKey`, `FooterLabel`, `KeyGroup`), as `codebrowser_app.py:51-53` already
  does · severity: low · → mitigation: pin is `textual>=8.2.7,<9`; the public
  `textual.compose.compose` is used for the composition itself
- **Transitional duplication:** two `Footer` subclasses now coexist with different
  strategies — `codebrowser.ContextualFooter` *replicates* `Footer.compose()`,
  `MultiRowFooter` *reflows* it. Intentional and bounded (this task ships the
  widget and adopts it on the board only), but it is added duplication until the
  other five TUIs adopt it · severity: medium · → mitigation: t1423
  (`adopt_multirow_footer_in_remaining_tuis`)
- The footer recomposes on every `bindings_updated`; a compose-time exception would
  break the board's footer entirely · severity: low · → mitigation: render-level
  tests boot the real board and the real widget
- `on_resize` → `recompose` → `height: auto` change → `Resize` is a genuine
  feedback path. Measured to converge in one extra round today, but a future CSS or
  planner change could make it oscillate and flicker on a real terminal ·
  severity: low · → mitigation: covered in-scope by the bounded-recompose /
  idle-stability assertion

### Goal-achievement risk: low
- Approach, row planner, overflow behavior, palette placement and both
  interpreters were validated end-to-end against the real `Footer` before planning
  closed; the one AC conflict (400-column single row) was surfaced and amended with
  the user rather than silently deviated from · severity: low · → mitigation: none
  needed

### Planned mitigations
- timing: after | created: t1423 | name: adopt_multirow_footer_in_remaining_tuis | type: enhancement | priority: medium | effort: medium | addresses: transitional duplication — two Footer subclasses with different strategies | desc: Adopt MultiRowFooter in agentcrew_dashboard, codebrowser (refactoring ContextualFooter onto it), monitor, stats and codebrowser/history_screen, so the replicate-compose and reflow-compose strategies converge on one widget.
- timing: after | created: t1424 | name: reconcile_shortcuts_editor_and_command_palette | type: enhancement | priority: medium | effort: medium | addresses: discovery-surface overlap between `?` and ctrl+p | desc: Reconcile the two discovery surfaces — four board commands (Add/Edit/Delete/Expand Column, Clear Selection) exist only in the ctrl+p palette because they have no key binding, while `?` is the only place keys can be rebound; neither surface currently shows the whole operation set.

## Final Implementation Notes

- **Actual work done:** Implemented exactly the approved design. New shared widget
  `.aitask-scripts/lib/multirow_footer.py` (`MultiRowFooter` + the pure
  `plan_footer_rows` / `footer_item_width` + the `footer_max_rows` userconfig
  resolver with a `refresh_max_rows()` test hook). Board adoption in
  `aitask_board.py`: mounts `MultiRowFooter(hint_action="open_shortcuts_editor")`,
  un-hides `ctrl+up` / `ctrl+down` / `m` / `X`, rewrites the stale t1243_7
  "footer is already full" comment, drops the now-unused `Footer` import. Docs in
  `aidocs/framework/tui_conventions.md` (the "footer must surface every operation"
  section now points at the widget) and the website (`tuis/_index.md`
  `footer_max_rows`, `tuis/board/_index.md` footer bullet). Tests:
  `tests/test_multirow_footer.py` (48) and `tests/test_board_footer_multirow.py`
  (10).

- **Deviations from plan:** None in design. Two plan *statements* were corrected
  while implementing: the module is `rich.cells`, not `rich.cell`, and the
  ground-truth comparison is against `outer_size.width + margin.left + margin.right`
  — `outer_size` excludes margins, so comparing against it alone would have passed
  while rows overflowed by exactly the margin. One extra file was touched that the
  plan did not anticipate: `tests/test_board_fixture_harness.py` (below).

- **Issues encountered:**
  - `HorizontalGroup(*children)` keeps its children *pending* until mount, so the
    first draft of the width-model test captured an empty list at compose time and
    passed vacuously. Rewritten to measure after mount and reduce to plain data
    inside the running app.
  - The row planner went through three drafts. Reserving width for "the last row"
    cannot work (the final row count is unknown until packing finishes) and let
    `O Options` collide with the docked palette key at 200 and 400 columns; a
    balanced split dropped a key at 200 columns, failing the coverage AC. Final
    design: the palette is a *pinned tail* item, so its row **is** the last row by
    construction, with one reserve pass and a coverage fallback.
  - `tests/test_board_fixture_harness.py` regressed: its control boots the board at
    `size=(200, 12)`, and a 2-row footer left a 4-row column viewport, so the
    5-row short-slug cards no longer fit and the control failed for a reason
    unrelated to slug length. Raised to `(200, 14)`, which restores headroom on
    both halves (short cards 5 ≤ 6; tall cards 13 > 6). The test it protects,
    `test_board_scroll_focus_jump`, asserts the opposite direction and was
    unaffected.
  - Live verification initially looked broken: the real board in tmux showed only
    4 footer keys. Root-caused with a stock-`Footer` control to pre-existing
    behavior, not this change — see the upstream defects below.

- **Key decisions:**
  - Compose via Textual's public `textual.compose.compose(self, super().compose())`
    rather than `list(super().compose())`. `Footer.compose()` builds grouped
    bindings with a `with KeyGroup(...)` context manager that pushes onto
    `app._compose_stacks` instead of yielding; a bare `list()` produces empty
    `KeyGroup`s and corrupts the caller's compose stack.
  - `hint_action` takes an **action**, not a key. The key display is resolved from
    the composed binding (Textual already resolved it via `app.get_key_display`),
    so it follows a user remap. `resolve_key("board", "open_shortcuts_editor")`
    would have returned `None` — that action is registered under the `shared`
    scope and `register_app_bindings` deliberately does not shadow shared actions
    into the app scope — leaving a hardcoded `?` that goes stale for exactly the
    users who rebound it.
  - All text measured with `cell_len`, never `len`. Proven necessary: with
    character-based costs and CJK labels at 44 columns, a key renders at x-right
    48, entirely off-screen.
  - Both negative controls were exercised by mutating the source and confirming a
    loud failure (`cell_len → len` fails the three wide-character guards;
    breaking the collapsed-margin term fails the width matrix), then reverted. The
    board control (reverting one `show=True`) fails the two un-hide tests. The
    overflow-width guard originally could not discriminate and was widened to a
    sweep that does.

- **Upstream defects identified:**
  - `.aitask-scripts/lib/shortcuts_mixin.py:117-131` — `_relink_live_bindings` removes the default key with `mapping.get(old_key)` using the *raw* binding key, but Textual stores the live keymap under the normalized key name (`?` → `question_mark`, `#` → `number_sign`). For any punctuation/special key the removal silently no-ops: the override key is added while the default stays live, so the old key keeps firing after a rebind (defeating the method's stated purpose) and the footer keeps displaying the old key. Plain-letter rebinds are unaffected. Verified live: with a `shared` override of `open_shortcuts_editor` to `f2`, `app._bindings.key_to_bindings` contained **both** `question_mark` and `f2`.
  - `.aitask-scripts/board/aitask_board.py:6470-6478` — at startup in a real terminal the search `Input` takes focus, and a focused `Input` consumes printable characters, so Textual drops every single-character binding from `active_bindings`. The board's footer therefore shows only 4 non-printable movement keys (`shift+↑/↓`, `^↑/^↓`) until the user presses Escape. Confirmed pre-existing with a stock-`Footer` control (identical 4-key result), so it is not caused by t1418 — but it does mean the footer is nearly empty on the screen the user first sees, which blunts this task's discoverability goal.

- **Follow-up noted for the user (agreed during planning):** reconciling the `?`
  shortcuts editor and the `ctrl+p` command palette. They are not duplicates —
  four board commands (Add / Edit / Delete / Expand Column, Clear Selection) exist
  only in the palette because they have no key binding, while `?` is the only
  place keys can be rebound — so neither surface shows the whole operation set.
  Captured as the `reconcile_shortcuts_editor_and_command_palette` mitigation.

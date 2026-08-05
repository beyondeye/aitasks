---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [board, tui, textual, shortcuts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1423, 1424]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-04 18:39
updated_at: 2026-08-05 10:52
completed_at: 2026-08-05 10:52
---

`ait board`'s main screen declares far more shortcuts than its single-line
footer can show, and the overflow is silently invisible. Textual ships no
multi-line footer, so build one — a shared, width-adaptive multi-row footer
widget — and adopt it on the board.

## Problem (measured)

Textual 8.2.7's `Footer` is `dock: bottom; layout: horizontal; height: 1`, one
`FooterKey` (height 1) per shown binding. Overflow is reachable only by
horizontal **mouse-wheel** scroll (`Footer._on_mouse_scroll_down/up`) — a
keyboard user has no way to know a key exists.

The board's main screen (`BoardApp.BINDINGS`, `.aitask-scripts/board/aitask_board.py`)
declares 45 bindings on that screen: 27 shown, 18 `show=False`. The 27 shown
labels total ~385 columns of text. Measured with a headless `run_test`
harness against the real `Footer`, using the board's own key/label set:

| terminal width | keys fully visible (stock Footer) |
|---|---|
| 120 cols | 9 / 24 |
| 200 cols | 16 / 24 |

So even on a 200-column terminal a third of the *shown* footer is off-screen.
t1243_7 already hit this wall and hid `m` (Move to Col) with an explicit
comment: "the footer is already full at 200 columns … a shown `m` renders as
a bare key with its label clipped off". That constraint is what this task
removes.

## Why CSS alone cannot fix it

`Footer.compose()` ends with `self.styles.grid_size_columns = len(action_to_bindings)`.
Subclassing with `layout: grid; grid-columns: auto; height: 2` therefore still
produces **one** row — verified in the probe; the forced column count equals the
key count. Any fix must re-assert the layout *after* `super().compose()` runs,
and must survive the recompose that `bindings_changed` triggers on every
`bindings_updated` signal.

## Verified approach

Subclass `Footer`; in `compose()`, take `list(super().compose())` — the real
`FooterKey` widgets — and re-place them into packed `HorizontalGroup` rows
(`height: 1; width: 1fr`) inside a `layout: vertical; height: auto` footer.
This keeps every piece of upstream machinery: `screen.active_bindings` (so
`check_action` gating still hides/disables keys), `FooterKey.on_mouse_down`
click-to-fire, key-display resolution via `app.get_key_display`, the
`bindings_updated` recompose subscription, and the `-command-palette` key.

Measured with the board's key set (prototype in probes, not committed):

| width | rows | keys fully visible |
|---|---|---|
| 400 | 1 | 24 / 24 |
| 200 | 2 | 23 / 23 |
| 160 | 3 | 23 / 23 |
| 120 | 3 | 22 / 22 |
| 100 | 3 | 18 / 18 |
| 80  | 3 | 14 / 14 |

Row count is derived from content vs. available width (`ceil(total_cost / width)`)
under a cap, so a wide terminal renders exactly one row as today and the footer
only grows when it must.

## Scope

1. **New shared widget** under `.aitask-scripts/lib/` (e.g. `multirow_footer.py`),
   importable by every TUI. Not board-local — see "Other TUIs" below.
   - Width-adaptive row count with a configurable maximum.
   - Packed (not equal-width-grid) rows: a grid wastes columns because every
     column is sized to the widest cell across rows.
   - Recompute on resize (`on_resize` → `recompose`) as well as on
     `bindings_updated`.
2. **Board adoption:** `BoardApp.compose()` yields the new footer instead of
   `Footer()`. Keep `footer.can_focus = False`.
3. **Un-hide the keys that were hidden only for lack of room** — with the extra
   rows there is space for all four:
   - `m` → Move to Col (hidden by t1243_7's measured decision; update that
     comment rather than leaving it contradicting the code)
   - `X` → Collapse Col
   - `ctrl+up` → Task Top, `ctrl+down` → Task Btm
   Do **not** un-hide `a l f i y z g t` — the `ViewSelector` widget already
   renders those in the filter row (`[a All | l Locked | f Free | i In-Flight]
   g Git t Type`); footer entries would duplicate, not reveal. Leave the plain
   navigation keys (arrows / `tab` / `escape`) hidden.
4. **Configuration:** a global `footer_max_rows` key in
   `aitasks/metadata/userconfig.yaml`, following the `shortcut_label_case`
   precedent in `.aitask-scripts/lib/shortcuts_mixin.py` exactly — read once via
   `load_yaml_config(_userconfig_path())`, module-level cache plus a
   `refresh_*()` hook for tests, fail-soft to the default on any read/parse
   error (a malformed gitignored userconfig must not crash every TUI). Decide
   and document the default (1 = today's behavior, or 2).

## Open design points the plan must settle

- **Beyond the cap.** At ~80 columns even 3 rows cannot hold every key; the
  probe simply dropped the remainder. The plan must choose an explicit
  behavior — keep the last row horizontally scrollable, drop with a visible
  "+N more (?)" affordance, or another option — and test it. It must not be
  left implicit.
- **Command-palette key overlap.** `FooterKey.-command-palette` is `dock: right`.
  In the multi-row prototype it overlapped row content below ~130 columns
  (e.g. `ctrl+p` at x=88–100 on top of `x` at 72–91). Reserve its width per row
  or dock it to a single row.
- **Row balancing rule.** Greedy cost-based split vs. first-fit; keep it
  deterministic so render-level tests can pin exact row membership.

## Testing

Per `feedback_tui_render_level_verification`, assert on real geometry/render
output, not on internal bookkeeping: mount the widget in `run_test(size=(w, h))`
at several widths and assert row count, per-row key membership, and that every
placed `FooterKey.region.right <= width`. Include a negative control that the
harness fails against the stock `Footer` (which clips) — otherwise the test is
not discriminating. Note the board runs on **PyPy** (`~/.aitask/pypy_venv`) while
the test suite runs on CPython; the widget is pure Textual, but verify it loads
under both.

## Other TUIs (follow-up, not this task)

Shown-label width vs. a 120-column terminal, so the same overflow already
exists elsewhere:

| TUI | shown bindings | ~label width |
|---|---|---|
| `aitask_board.py` | 27 | 385 |
| `agentcrew_dashboard.py` | 27 | 342 |
| `codebrowser_app.py` | 16 | 245 |
| `monitor_app.py` | 20 | 226 |
| `stats_app.py` | 13 | 177 |
| `codebrowser/history_screen.py` | 10 | 166 |

This task ships the shared widget and adopts it on the board only. Adoption in
the other five is a follow-up once the widget has proven itself in place.

## Acceptance criteria

- A reusable multi-row footer widget exists in `.aitask-scripts/lib/`, built by
  reflowing `Footer.compose()`'s own `FooterKey` widgets (not by re-deriving
  bindings), so `check_action` gating, click-to-fire and `bindings_updated`
  recompose all still work on the board.
- On a 200-column terminal the board footer shows **every** shown binding
  (vs. 16/24 today), and it renders exactly **one** row whenever the total
  content fits the available width.

  > **AC amended during implementation (agreed with the user).** This criterion
  > originally read "on a 400-column terminal it still renders as a single row".
  > Un-hiding the four keys below adds ~45 columns of label text, which moves the
  > single-row threshold from ~400 to ~440 columns — measured 1 row at 440/460,
  > 2 rows at 400. The invariant worth pinning is "grows only when it must", not
  > a specific column count, so the criterion is stated that way instead.
- `m`, `X`, `ctrl+up`, `ctrl+down` are footer-visible on the board; the stale
  t1243_7 "footer is already full" comment is updated.
- `a l f i y z g t` stay `show=False` (already surfaced by `ViewSelector`).
- `footer_max_rows` is honored from `userconfig.yaml`, fail-soft, defaulting to
  documented behavior.
- Over-cap overflow behavior is explicitly chosen, documented, and tested.
- Render-level tests pin row count and per-row membership at several widths, and
  the harness is proven to fail against the stock single-row `Footer`.
- `aidocs/framework/tui_conventions.md` is updated: the existing "TUI footer must
  surface every operation on the affected tab/screen" section should reference
  the new widget as the way to satisfy itself when a screen has too many keys.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T06:57:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T07:47:26Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-05T07:52:50Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c9bb2a7332ba880b

> **✅ gate:risk_evaluated** run=2026-08-05T07:52:50Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1418/risk_evaluated_2026-08-05T07:52:50Z-risk_evaluated-a1.log`

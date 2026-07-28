---
Task: t1278_fix_failed_verification_t1273_item3.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1278 — Make the board's freshness banner actually visible

## Context

t1273 item #3 (manual verification of t1268) failed. The check was:

> Press `d` — banner returns to `⟳ checking freshness…` then `⚠ stale: N`, and
> detail-bearing drift markers appear on the owning cards.

The **drift-marker half passes**. The **banner half never renders**. Investigation
found *two independent* reasons it cannot render, and the plan fixes both —
fixing only the first still leaves the item failing on an ordinary terminal.

## Defect 1 — the header row is never drawn

`_refresh_subtitle()` (`aitask_board.py:5885-5926`) is the single writer for
`App.sub_title`. Only the docked `Header` displays `sub_title`, and the board's
`Header` is fully occluded.

`KanbanApp.compose` (`:5803`) yields `Header()` first, then `#filter_area`.
`Header` docks top via Textual's stock `DEFAULT_CSS`; the board's own CSS also
docks the filter row (`:5365`). In Textual 8.2.7 two same-edge docked siblings
are **both placed at `y=0`** — they overlap rather than stack, and the 3-row
filter row paints over the 1-row header.

Measured on the real `KanbanApp` (`run_test(size=(120,20))`):

```
          Header                  #filter_area          #board_container
as-is     Region(0, 0, 120, 1)    Region(0, 0, 120, 3)  Region(0, 4, 120, 15)
```

Composited row 0 as-is is `' Task filter …'`. Confirmed through a **real
terminal** too: `ait board` in a throwaway tmux socket captures row 0 as
`Task filter`, not the title bar.

This is why headless tests missed it. `run_test` reports the `Header` as
`display=True`, `visible=True`, `region=(0,0,120,1)`, and lists it in the
compositor's `visible_widgets` — every property is "correct" while the widget is
entirely painted over. Every existing assertion reads the `app.sub_title`
*reactive* (`test_board_bytrail_view.py:520, 638, 712, 905`), never the frame.

The defect predates t1268 — `sub_title` also carries `Auto-refresh: …`, equally
invisible. t1268 is the origin only because it built the freshness UX there.

## Defect 2 — the freshness marker is the first thing clipped

Found while validating the fix. `HeaderTitle` renders `"{title} — {sub_title}"`
and ellipsis-truncates the **tail**. The freshness marker *is* the tail, so it is
the first thing lost as the terminal narrows. Measured with defect 1 already
fixed, short trail title, drift = STALE:

| width | row 0 | `⚠ stale: 3` visible |
|---|---|---|
| 100 | `aitasks board — By-Trail: "Gate framework landing order" (⚠ stale: 3)` | yes |
| **80** | `aitasks board — By-Trail: "Gate framework landing order" (⚠ s…` | **no** |
| 60 | `aitasks board — By-Trail: "Gate framework…` | **no** |

With a long trail title it fails at 120 columns. **80 columns is an ordinary
terminal**, so shipping only the CSS fix would still fail the checklist item for
most users. Fixing this is therefore in scope, not scope creep — but it is a
second change beyond the one-line fix originally scoped, so it is called out
here explicitly rather than folded in silently.

## Fix 1 — undock the filter row

**`.aitask-scripts/board/aitask_board.py:5365`**

```css
- #filter_area { dock: top; height: auto; margin: 0 0 1 0; }
+ #filter_area { height: auto; }
```

Two changes on one line, and the second is not cosmetic:

- **`dock: top` removed** — the actual fix.
- **`margin: 0 0 1 0` removed** — reclaims the row the header now needs. Docked,
  that bottom margin produced a *second* blank separator row (rows 2 and 3 were
  both blank). Undocked with the margin kept, the board starts at `y=5` and
  loses a row; with it dropped, the board keeps `y=4` height 15 — the same board
  area as today.

| variant | Header | #filter_area | #board_container |
|---|---|---|---|
| as-is | (0,0,120,1) *occluded* | (0,**0**,120,3) | (0,4,120,**15**) |
| undock, margin kept | (0,0,120,1) *visible* | (0,1,120,3) | (0,5,120,**14**) |
| **undock, margin dropped** | (0,0,120,1) *visible* | (0,1,120,3) | (0,4,120,**15**) |

**UX trade-off, recorded deliberately:** the board used to have *two* blank rows
between the filter row and the lanes; it now has one (row 3, which still carries
the search Input's bottom border on the right). This is an accepted trade to buy
the header row for free. It is pinned by an assertion (Verification §1) so a
later theme/border change that collapses the boundary fails a test rather than
silently degrading. If you would rather keep both blank rows and pay one row of
board height, say so and I will restore `margin: 0 0 1 0` — nothing else changes.

The CSS comment above the block (`:5359-5363`) gains a line recording *why*
`#filter_area` must not be re-docked, so the occlusion is not reintroduced.

## Fix 2 — budget the banner so the marker always survives

Add a width-budgeted composer used by the trail-doc branch of
`_refresh_subtitle` (`:5896-5916`).

The budget is **derived at runtime, not hardcoded**:

```python
def _banner_budget(self) -> int:
    """Cells available to sub_title on the header row.

    Read off the live HeaderTitle rather than a constant inset: the inset is
    Textual's (icon + clock reservation) and would drift on upgrade or if the
    clock were ever enabled. 0 => not laid out yet; caller skips elision."""
    try:
        usable = self.query_one(HeaderTitle).content_region.width
    except Exception:
        return 0
    return max(0, usable - cell_len(str(self.title)) - 3)   # " — "
```

Verified exact: `HeaderTitle.content_region.width` equals the maximum unclipped
text width at every width tested (60/80/100/120/160/200).

Measurement uses `rich.cells.cell_len` / `set_cell_size`, not `len()` — the
banner carries `⚠`, `⟳`, `·`, `…`, whose cell width is not their character
count in general.

The composer sheds context from the widest rung down until it fits, so the one
volatile signal is the last thing dropped rather than the first:

1. `By-Trail: "{title}"{suffix}{owner_note}` — unchanged when it fits.
2. same, with `{title}` elided to the remaining room + `…`.
3. `By-Trail:{suffix}{owner_note}` — title dropped entirely.
4. `{suffix}` bare (parens/space stripped) — e.g. `⟳ checking freshness…`.

Measured results with the ladder in place (marker retained at every width):

```
w= 60  aitasks board — By-Trail: (⚠ stale: 3)
w= 80  aitasks board — By-Trail: "Cross-repo gate fram…" (⚠ stale: 3)
w=100  aitasks board — By-Trail: "Cross-repo gate framework landing order …" (⚠ stale: 3)
w= 60  aitasks board — ⟳ checking freshness…            <- rung 4
```

`on_resize` (`:5851`) must also call `_refresh_subtitle()` — the budget changes
with width, and without this a board resized narrower keeps a banner composed
for the old width.

**Stated exclusion:** the `_trail_error` branch (`:5894`,
`By-Trail: {handle} — trail unavailable`) is left unbudgeted. A long handle can
still clip there, but its tail is a static identifier the user just selected, not
a volatile signal — the failure mode this task exists to fix does not apply.
Disposition: no follow-up task; revisit only if a real handle proves long enough
to hide the words `trail unavailable`.

## Verification

Three guards. The headless-only story is exactly what let this ship.

### 1. Render-level regression tests (headless, deterministic)

Helper on `ByTrailTestBase` in `tests/test_board_bytrail_view.py`, beside the
existing `_footer_actions` / `_enter_synthetic_bytrail`:

```python
@staticmethod
def _screen_rows(app) -> list[str]:
    """Composited frame text, row by row.

    Deliberately NOT app.sub_title / widget.region / widget.display: an
    occluded widget reports display=True with a correct region and appears in
    visible_widgets, which is how t1273 item #3 shipped invisible (t1278).
    Only the composited frame proves a row reaches the screen."""
    return [strip.text for strip
            in app.screen._compositor.render_strips(app.screen.size)]
```

**(a) The real `d` flow — not injected state.** Drives the actual key through
the actual action, worker and callback chain, with only the two module-level
subprocess seams replaced. `load_trail_blob` blocks on a `threading.Event` so
the intermediate state is observed deterministically rather than raced for:

```python
gate = threading.Event()
def fake_load(handle):
    gate.wait(timeout=5)
    return (copy.deepcopy(doc), "", ["v1"])
def fake_drift(handle):
    return ("STALE", [("stale_status", "aitasks#1", "d1"),
                      ("stale_status", "aitasks#2", "d2")])

with patch.object(ab, "load_trail_blob", fake_load), \
     patch.object(ab, "run_trail_drift", fake_drift):
    # enter By-Trail with the REAL _start_trail_drift (not the
    # _enter_synthetic_bytrail no-op stub) so the whole chain runs
    ...
    await pilot.press("d")            # real key -> real action
    await pilot.pause()
    try:
        # intermediate state
        self.assertIn("⟳ checking freshness…", self._screen_rows(app)[0])
    finally:
        # Release the worker even when the assertion above fails: an
        # unreleased gate leaves the thread parked until its 5s timeout,
        # so a failing test would also be a slow, noisy one.
        gate.set()
        await app.workers.wait_for_complete()
    # settled state
    self.assertIn("⚠ stale: 2", self._screen_rows(app)[0])
```

The `finally` covers only the gate release and the drain — the settled-state
assertion stays outside it, so a failure there is still reported as itself.

Already executed end-to-end during planning against the real `KanbanApp`:

```
[FIXED]   entry   : aitasks board — By-Trail: "Gate framework landing order" (⚠ stale: 2)
[FIXED]   after d : aitasks board — By-Trail: "Gate framework landing order" (⟳ checking freshness…)
[FIXED]   settled : aitasks board — By-Trail: "Gate framework landing order" (⚠ stale: 2)
[UNFIXED] entry   : (row 0 is the filter row — nothing)
[UNFIXED] after d : (row 0 is the filter row — nothing)
[UNFIXED] settled : (row 0 is the filter row — nothing)
```

A regression in key routing, worker launch, callback delivery or ordering fails
this test; it cannot pass on a prepared subtitle alone.

**(b) Narrow + long title.** Same flow at `size=(80, 30)` and `(60, 30)` with a
75-character trail title.

Assert **presence of each complete expected status substring** — exactly
`"⚠ stale: 3"` and exactly `"⟳ checking freshness…"` — and nothing else. Do
**not** add a generic "row 0 contains no `…`" check: the checking marker
legitimately *ends* in an ellipsis, so such a rule contradicts its own
expectation, and the elided-title rungs render a deliberate `…` inside the
quoted title.

The complete-substring form is already sufficient, because clipping destroys the
substring it is meant to detect — verified on the real app:

| state | row 0 without Fix 2 (w=80) | `assertIn` outcome |
|---|---|---|
| stale | `… "Gate framework landing order" (⚠ s…` | `"⚠ stale: 3"` absent → fails |
| checking | `… "Cross-repo gate framework land…` | `"⟳ checking freshness…"` absent → fails |

With Fix 2 both substrings are present in full at 80 and 60 columns.

**(c) Board-wide half.** With no trail active, assert row 0 carries
`Auto-refresh: off` — pins the defect beyond By-Trail.

**(d) Separator + geometry pin (concern 4).** Assert `#board_container.region`
is `(0, 4, W, H)` — identical to pre-fix — and that the row directly above the
lanes (row 3) is blank on the left, so the filter-to-lane boundary stays legible
if a theme or border changes.

**Negative control (already run):** every assertion above was executed against
unpatched CSS and fails there; against patched CSS it passes. The guards
discriminate.

### 2. Live tmux smoke test (real terminal)

New `tests/test_board_header_row_live.py` — the repo's first test booting a real
TUI in a pane. Modelled on `tests/test_minimonitor_concern_smoke.py:46-141`.

- Throwaway socket `ait_t1278_hdr_<pid>`; `AITASKS_TMUX_SOCKET` exported into the
  child so the board's own gateway calls stay on that socket and never reach the
  user's server or the dedicated `ait` socket.
- `new-session -d -x 120 -y 30` running `./ait board` from `REPO_ROOT`.
- Poll `capture-pane -p` until row 0 settles, then assert it contains
  `aitasks board` and `Auto-refresh`.
- `kill-server` in `tearDownClass`.

**Skip vs fail (concern 3).** `SkipTest` only for *environment unavailability*:
`tmux` not on `PATH`, or `new-session` / `list-panes` returning no pane. Once a
pane exists, a render timeout is a **failure**, not a skip — a startup crash or a
permanently blank board is precisely the regression this test exists to catch.
The failure message includes the full final `capture-pane` output for diagnosis.

Verified during planning: a full boot settles in ~3 s and leaves
`aitasks/metadata/board_config.json` byte-identical (md5 before/after). The test
sends no keys.

Raw `tmux` is correct here: `tests/test_no_raw_tmux.sh` scopes its guard to
`.aitask-scripts/`, and every existing live test in `tests/` calls tmux directly.

### 3. Re-run the adjacent geometry suite

`tests/test_board_filter_row_layout.py` (t1247) asserts `#view_col.region`, the
`.narrow` reflow class, and *relative* positions (`:204`, `:218`). A uniform
y-shift should leave it green, but it is the file most likely disturbed and must
be run, not assumed.

```bash
python3 -m unittest tests.test_board_bytrail_view \
                    tests.test_board_filter_row_layout \
                    tests.test_board_header_row_live -v
```

## Files touched

| File | Change |
|---|---|
| `.aitask-scripts/board/aitask_board.py` | CSS `:5365` undock + drop margin; comment `:5359`; `_banner_budget` + banner ladder in `_refresh_subtitle` `:5885`; `_refresh_subtitle()` call in `on_resize` `:5851` |
| `tests/test_board_bytrail_view.py` | `_screen_rows` helper + render-level tests (a)–(d) |
| `tests/test_board_header_row_live.py` | **new** — live tmux pane capture of row 0 |

## Step 9 (Post-Implementation)

Current-branch profile — no worktree to remove. Merge target `main` per the
header. Then `ait gates run 1278` (`risk_evaluated` is the enforced active gate)
and archival via `aitask_archive.sh 1278`. Re-verification of the user-visible
`d` flow against a real trail is a natural Step 8c manual-verification follow-up.

## Risk

### Code-health risk: low

- The board gains a permanently visible header row it has never drawn, and loses
  one of its two blank separator rows; every board user sees a changed first row
  · severity: low · → mitigation: covered in-plan by the live tmux row-0 capture,
  the geometry/separator pin (§1d) and the t1247 suite re-run.
- Fix 2 adds a composition ladder to `_refresh_subtitle`, which t1210_4
  established as the single subtitle writer — more logic in a load-bearing method
  · severity: low · → mitigation: covered in-plan — the ladder is exercised at
  three widths through the real `d` flow (§1a, §1b), and it is additive (rung 1
  is today's exact string, so wide terminals are byte-identical to today).
- `_screen_rows` reaches into `app.screen._compositor`, a Textual private API, so
  an upgrade could break the guard · severity: low · → mitigation: none warranted
  — it would fail loudly (`AttributeError`) rather than silently pass, which is
  the safe direction for a guard, and Textual exposes no public frame-text export
  (`export_text` does not exist; `export_screenshot` emits per-glyph SVG tspans
  that defeat substring matching — both checked during planning).

### Goal-achievement risk: low

- None identified. Both defects were reproduced in a real terminal, both fixes
  were measured on the real `KanbanApp` (not a replica), and every guard was
  confirmed to fail before the change and pass after.

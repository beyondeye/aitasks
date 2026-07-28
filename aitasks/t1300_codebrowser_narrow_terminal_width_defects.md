---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-07-28 17:46
updated_at: 2026-07-28 17:46
---

## Origin

Spawned from t1251 during Step 8b review. t1251 centralized the codebrowser's
terminal-width *tier* breakpoints into `.aitask-scripts/lib/tui_layout.py`; while
inventorying that file these two pre-existing narrow-terminal defects surfaced.
Neither was in t1251's scope (it was a behavior-preserving refactor), and neither
is fixable by the tier seam.

## Upstream defect

- `.aitask-scripts/codebrowser/codebrowser_app.py:357` — inline CSS
  `#copy_path_dialog { width: 80 }` is a fixed width with no narrow variant, so
  the copy-path dialog overflows any terminal narrower than 80 columns.
  Pre-existing, unrelated to t1251's tier work, and not fixable by the tier seam
  (it is CSS, not a Python branch).
- `.aitask-scripts/codebrowser/codebrowser_app.py:709` — `_apply_detail_width`
  falls back to `sidebar_width = 35` (the WIDE-tier value) when
  `sidebar.styles.width` is unset. On a narrow terminal the real sidebar is 22,
  so the fallback under-computes `available` by 13 cells and can hide the detail
  pane that would otherwise fit. Latent because `on_resize` normally sets the
  width first, but it is a wrong default rather than a safe one.

## Diagnostic context

From t1251's plan (`aiplans/archived/p1251_centralize_tui_narrow_breakpoint.md`
once archived). t1251 inventoried every width literal under `.aitask-scripts/`
and split them into two categories: *terminal tier breakpoints* (centralized) and
*component minimum widths* (deliberately left with their widget, documented in
`aidocs/framework/tui_conventions.md`, section "Terminal-width tiers vs component
minimum widths").

Both defects above fall outside that split — they are neither a tier decision nor
a correctly-scoped component minimum, but simply wrong values:

- The `width: 80` dialog is a hardcoded dimension that happens to equal
  `NARROW_TERMINAL_WIDTH`; at exactly the narrow boundary it consumes 100% of the
  terminal, and below it, it overflows.
- The `sidebar_width = 35` fallback silently assumes the widest tier. t1251 made
  the real per-tier widths explicit as
  `CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER = {WIDE: 35, NORMAL: 28, NARROW: 22}`,
  which now makes the hardcoded 35 visibly inconsistent with the tier it is
  standing in for.

Note the codebrowser had **no** `on_resize` / `_apply_detail_width` test coverage
before t1251; `tests/test_tui_narrow_breakpoint.py` now boots the real
`CodeBrowserApp` under `run_test(size=...)` and is the natural harness to extend.

## Suggested fix

- Give `#copy_path_dialog` a responsive width (`width: 90%; max-width: 80`) or a
  `.narrow` variant, mirroring the narrow-dialog pattern already used in
  `monitor/monitor_shared.py` (`width: 90%; min-width: 30`).
- Derive the `_apply_detail_width` fallback from the current tier —
  `SIDEBAR_WIDTH_BY_TIER[terminal_tier(self.size.width)]` — instead of the
  hardcoded 35, so the fallback matches whatever `on_resize` would have set.

## Verification

- Extend `tests/test_tui_narrow_breakpoint.py` (or add a sibling suite) to boot
  `CodeBrowserApp` at a sub-80-column size and assert the copy-path dialog's
  rendered region fits inside the screen.
- Assert `_apply_detail_width` computes the same `available` whether or not
  `sidebar.styles.width` has been set, at each tier.

---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [docs, web_site]
created_at: 2026-08-05 16:06
updated_at: 2026-08-05 16:06
---

Documentation gaps found by /aitask-docs-gap for the release window v0.30.0..HEAD.
Each section below is self-contained and can become its own child task at
decomposition time.

## Gap: Board multi-select marking (t1243_6)

- **Target doc page(s):** `website/content/docs/tuis/board/reference.md` (keybinding table), `website/content/docs/tuis/board/how-to.md`
- **What shipped:** The board gained a per-card mark. `Space` toggles the mark on the focused **parent** card (`Binding("space", "toggle_mark", "Mark")`); marked cards show an always-on checkbox glyph (`☑` marked / `☐` unmarked) in the card title row, with marked cards styled bold. Child cards refuse with an explanatory notification ("Child tasks move with their parent — mark the parent instead."). Marking is disabled in the derived views (`inflight`, `bytopic`, `bytrail`), gated both in `check_action` and again inside `action_toggle_mark`. Marks are cleared when the base filter changes, survive a filter pass (a marked card can be hidden), and are pruned with a notification when a marked task disappears on refresh.
- **What to write:** Add `Space` → "Mark / unmark the focused task" to the board keybinding reference table (scoped to the kanban views). Add a how-to section covering: what the glyph means, that only parent cards are markable, that marks survive filtering so a marked card may be off-screen, that switching view clears them, and that vanished tasks are dropped from the selection with a notice.
- **Sources:** `aiplans/archived/p1243/p1243_6_multiselect_marking.md`; commits: 29ad1ab78

## Gap: Board bulk move-to-column command (t1243_7)

- **Target doc page(s):** `website/content/docs/tuis/board/reference.md` (keybinding table + command palette), `website/content/docs/tuis/board/how-to.md`
- **What shipped:** `m` (`Binding("m", "move_to_column", "Move to Col", show=False)`) moves the marked task(s) — or, with nothing marked, the focused card — to a column chosen from a picker. The binding is deliberately hidden from the footer (the footer is already full at 200 columns); discovery is the `?` shortcuts editor and two new command-palette entries: **"Move Tasks to Column"** and **"Clear Selection"** (`action_clear_marks`, unmark everything). Because marks survive a filter pass, a marked-but-hidden selection triggers a **review step first** — the board lists what will move, in board order, before offering the destination picker. The destination list excludes collapsed columns and the column the whole selection already sits in; when nothing is left it says so instead of opening an empty picker. Child cards refuse with the same explanatory notification as marking. Disabled in the `inflight` / `bytopic` / `bytrail` views, re-checked inside the action because the palette invokes `action_*` directly.
- **What to write:** Document `m` in the keybinding reference (noting it is not shown in the footer and why discovery is via `?` / the palette), add the two palette entries to whatever palette listing the reference carries, and add a how-to section for the bulk-move flow: mark cards → `m` → review list → pick destination. Cover the parent-only restriction, the review-before-move step for hidden marked cards, and the "nowhere to move to" case.
- **Sources:** `aiplans/archived/p1243/p1243_7_move_to_column_command.md`; commits: 8b0e63a3e

## Gap: Concern-picker unparsed view and narrow-width adaptation missing from the monitor docs (t1293)

- **Target doc page(s):** `website/content/docs/tuis/monitor/how-to.md` (the "How to Pick Shadow Concerns" section), `website/content/docs/tuis/monitor/reference.md` (keybinding table)
- **What shipped:** The concern picker lives in the **shared** `.aitask-scripts/monitor/monitor_shared.py`, so both `ait monitor` and `ait minimonitor` got the change. Inside the picker, `u` (`Binding("u", "inspect_unrecovered", "Unparsed", show=False)`) opens a read-only view of the exact marker lines the parser could not use, alongside the raw block they came from — so an over-bound wrapped marker can be told apart from a genuine mistake by the shadow. When *no* line parsed there is no checklist to hang the warning on, so `u`'s view opens straight away. `q` / `Esc` closes it and returns to the checklist with ticks intact. The picker also adapts to narrow panes: at 30 columns and below it drops its OK/Cancel buttons for a compact key hint (`Enter` confirm, `Esc` cancel); 24 columns is the narrowest supported width.
- **What to write:** Mirror the two paragraphs that landed on `tuis/minimonitor/how-to.md` ("Seeing what was lost" and the narrow-width paragraph) onto the monitor how-to's concern-picking section, adapted to monitor's wording, and extend the monitor reference's `c` row the way minimonitor's was extended (`inside the picker, u shows any lines that could not be parsed`). Note: this is the parallel-surface half of t1293 that was left behind — only the minimonitor pages were updated when the change shipped.
- **Sources:** `aiplans/archived/p1293_concern_block_parse_diagnostics.md`; commits: e2db6e3f6

## Gap: Minimonitor "other" pane section — docs state the opposite (t1382)

- **Target doc page(s):** `website/content/docs/tuis/minimonitor/_index.md`, `website/content/docs/tuis/minimonitor/how-to.md`
- **What shipped:** `_rebuild_pane_list` now partitions the list into agents and **others**, mounting a bold `── other (n) ──` section header (`.mini-section-header`) when non-agent panes exist, each rendered compactly for the ~40-column sidebar. Separately, the pinned top card's header reads `── this window ──` (instead of `── this agent ──`) when the followed pane is not classified as an agent, so the uncategorized state is legible rather than invisible. Companion panes remain hidden, and renamed agent windows stay visible.
- **What to write:** These pages currently assert the **opposite** of the shipped behavior and must be corrected, not merely extended:
  - `_index.md` intro: "no preview panel, no TUI/other pane categories — just the running agents" is now wrong.
  - `_index.md` monitor-vs-minimonitor comparison table: the row "Shows TUIs and other panes | Yes | No" is now wrong.
  - `how-to.md`: "TUIs, shells, and other panes are deliberately filtered out" is now wrong.
  Describe the `── other (n) ──` section (what lands in it, that companion panes still do not), and document the `── this window ──` header variant alongside the existing `── this agent ──` description. Apply the current-state-only convention — state the behavior positively, no "previously".
- **Sources:** `aiplans/archived/p1382_renamed_agent_window_pane_classification.md`; commits: af3111dd9

## Gap: Parallel test-lane knobs are not on the site (t1354_3, t1354_4)

- **Target doc page(s):** `website/content/docs/commands/setup-install.md` (the `ait setup --with-dev` bullet) and/or `website/content/docs/development/_index.md` ("Testing Changes")
- **What shipped:** `ait setup --with-dev` installs an opt-in dev tier (`pytest` + `pytest-xdist`) that gives `tests/run_all_python_tests.sh` a parallel lane (`-n <workers> --dist loadfile`) with a small serial carve-out. Two environment knobs control it: `AIT_TEST_WORKERS=<n>` sets the worker count (default is **load-aware** — 4 when the box has headroom, 2 otherwise; never `auto`), and `AIT_TEST_PARALLEL=0` forces serial execution. Opting out is two separate actions: `AIT_TEST_PARALLEL=0` stops the lane, while `rm ~/.aitask/dev_tier` stops `ait setup` reinstalling the tier. Narrowing a run uses `--test-dir`; a positional test path *widens* the run and disables the lane. The site currently mentions only the one-line existence of `--with-dev`.
- **What to write:** Document the two env knobs, the load-aware default, the two-part opt-out, and the `--test-dir` vs positional-path caveat, on the contributor-facing page. `CLAUDE.md` holds the canonical explanation — condense it for the site rather than duplicating it wholesale, and keep the site copy current-state-only.
- **Sources:** `aiplans/archived/p1354/p1354_3_parallel_test_lane.md`, `aiplans/archived/p1354/p1354_4_retrospective_measure.md`; commits: 4f6c0b319, 07e16b81a

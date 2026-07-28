---
priority: medium
effort: medium
depends: [1268]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
created_at: 2026-07-28 01:18
updated_at: 2026-07-28 09:17
---

## Failed verification item from t1268

> Press `d` — banner returns to `⟳ checking freshness…` then `⚠ stale: N`, and detail-bearing drift markers appear on the owning cards (including an archived member rendered as a ghost card)

### Source

- **Manual-verification task:** `aitasks/t1273_manual_verification_bytrail_refresh_semantics_followup.md` (item #3)
- **Origin feature task:** t1268
- **Origin archived plan:** `aiplans/archived/p1268_bytrail_refresh_semantics_and_key_footer_contract.md`

### Commits that introduced the failing behavior

- ceb07381d bug: Fix By-Trail refresh semantics and key/footer contract (t1268)

### Files touched by those commits

- .aitask-scripts/board/aitask_board.py
- tests/test_board_bytrail_view.py

### Observed failure

The **drift-marker half passes**: after `d`, detail-bearing markers render on the
owning cards, including archived members drawn as ghost cards (observed
`⚠ task_completed: aitasks#1264 compl…` on the `👻 archived — read-only` ghost).

The **banner half never renders**. The freshness banner is written to
`App.sub_title` (`aitask_board.py:5894-5918`), which only the docked `Header`
displays — and the board's `Header` is not drawn at all. Six pane captures taken
at 1s intervals after pressing `d` contain neither `⟳ checking freshness…` nor
`⚠ stale:` anywhere on screen; no `sub_title` text (not even the default
`Auto-refresh: off`) is visible in any view.

### Root cause (reproduced minimally)

`KanbanApp.compose` yields `Header()` first, but the board CSS also docks the
filter row: `#filter_area { dock: top; height: auto; margin: 0 0 1 0; }`
(`aitask_board.py` CSS block). With a second top-docked widget declared in the
app's own CSS, the `Header` ends up with no drawn row — `#filter_area` occupies
row 0.

Minimal repro (same pypy/Textual 8.2.7 the board runs on): a `Header` +
`Static` + `Input` app renders `⭘  TITLE — sub-here` on row 0; adding
`#filter_area { dock: top; ... }` to the app CSS makes the header row vanish and
the filter row take row 0. Removing `dock: top` brings the header back.

Headless (`run_test`) the widget reports `display=True`, `region=(0,0,120,1)` —
so unit tests asserting on `app.sub_title` cannot catch this. Verification must
assert on rendered pane content.

### Scope note

The invisible `Header` predates t1268 (`sub_title` also carries the
`Auto-refresh: …` text), so this is a board-wide layout defect. t1268 is listed
as the origin because it built the freshness UX on that surface. A fix should
either restore the header row or move the freshness banner to a surface the
board actually draws.

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1273 item #3.

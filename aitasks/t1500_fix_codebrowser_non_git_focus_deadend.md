---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-12 23:14
updated_at: 2026-08-13 14:04
---

## Origin

Spawned from t1495 during Step 8b review.

## Upstream defect

- `.aitask-scripts/codebrowser/codebrowser_app.py:1332-1345` — `_focus_recent_or_tree`
  collapses the focus cycle to a self-loop whenever neither `#recent_files` nor
  `#file_tree` is mounted, stranding `#file_search_input` and `#detail_pane`.
- `.aitask-scripts/codebrowser/codebrowser_app.py:720-725` — the `set_files`
  seeding sits inside a `try` that queries `#file_tree` first, so the non-git
  branch renders a search box whose file list is never populated and which can
  therefore match nothing. The same shape recurs at `:1085-1087` in the
  `TrackedFilesRefreshed` handler.
- `tests/test_board_startup_focus_live.py:201-212` — `_launch_board` returns one
  0.25s poll after the *header* row (`Task filter`) appears at `:206-209`, but
  the board's columns mount asynchronously, so under load the capture is taken
  mid-mount and the `CARD_TITLE` assertion fails.

## Diagnostic context

All three surfaced while fixing the codebrowser's startup-focus defect (t1495).

Both codebrowser defects live in the `compose()` branch taken when
`get_project_root()` raises — i.e. `ait codebrowser` launched outside a git
repo. There the sidebar is a bare `Container` holding one non-focusable
`Static`, so `action_toggle_focus` finds neither `#recent_files` nor
`#file_tree` and falls through to `_focus_recent_or_tree(None, None,
code_viewer)`, which re-focuses the code viewer it started from.

Before t1495 the search box was reachable exactly once — at boot, because
Textual's `AUTO_FOCUS` happened to select it — and Tabbing away already
stranded it. t1495 removed that accidental first focus, so it is now
unreachable by keyboard. Nothing functional was lost, because the box is inert
in that branch anyway (`set_files` never runs, so `_all_files` stays empty), but
the pair should be resolved together: either populate the list and make the box
reachable, or hide the widget entirely when there is no project root.

The board flake is unrelated to the codebrowser and was observed while running
the suite for t1495: it passes 3/3 alone and 3/3 running the serial trio in
order, but fails roughly 2 of 4 full-suite runs, where the serial phase follows
a ~200s four-worker parallel phase. It is a fixture timing assumption, not a
product bug.

## Suggested fix

- Focus cycle: give `_focus_recent_or_tree` a `search_input` fallback (or handle
  it in `action_toggle_focus`) so the cycle degrades to `search → code_viewer`
  when no sidebar target exists. Note that
  `tests/test_codebrowser_startup_focus.py::test_tab_is_a_self_loop_without_a_sidebar`
  pins the current self-loop deliberately and must be updated in the same
  commit. Consider instead hiding `FileSearchWidget` in the non-git branch,
  which removes both defects at once.
- Search list: split the `set_files` seeding out of the `#file_tree` `try`, or
  seed it from a source that exists in both branches.
- Board flake: in `_launch_board`, wait for a marker that proves the columns
  mounted (the card title, or `(empty)`) rather than the header row.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T11:04:33Z status=pass attempt=1 type=human

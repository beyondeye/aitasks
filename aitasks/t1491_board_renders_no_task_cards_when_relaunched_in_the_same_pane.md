---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui, board]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-12 09:37
updated_at: 2026-08-12 13:49
---

## Problem

On a **freshly launched** `ait board`, every non-`priority` single-key binding is
swallowed as text by the search box — `q` (Quit) included — until the user
presses `Tab`/`Esc` or clicks. Whatever lands there becomes the search filter, so
`apply_filter` hides every card while the column headers keep their **unfiltered**
counts, and the board appears to render "no task cards".

`KanbanApp` set no startup focus. Textual applies `App.AUTO_FOCUS = "*"` inside
`Screen._compose()` — **before** `on_mount` runs — and the first focusable widget
in the board's DOM is `Input#search_box` (`aitask_board.py:7930`, composed ahead
of `#board_container`). Traced live, focus is set once and never moved:

```
[  0.024] set_focus -> Input#search_box (from_app_focus=False)
    textual/screen.py:1487  in _compose  ->  :1499 in _update_auto_focus
```

Only the `priority=True` bindings (arrows, `tab`, `escape`) still work, which is
why the board otherwise feels functional. A resize never repairs the render —
`on_resize` only reflows the filter row.

This is the same defect family t1486 fixed in logview, where `on_mount` was
changed to focus the RichLog first so single-key bindings fire without a prior
mouse click. The board was missed.

Compounding it: a column emptied **by a filter** and a column that is genuinely
empty both rendered a bare `(empty)`, so nothing on screen distinguished
"filtered to nothing" from "no tasks here".

## Reported as (superseded)

Filed from the t1490 checklist run as: *"relaunching `ait board` in the same
shell/pane after quitting with `q` renders correct header counts but zero task
cards"*. **There is no relaunch bug.** The board never quit — the `q` was typed
into the search box, and so was the `./ait board` that followed it, leaving
`search_filter = "q./ait board"`. The original report is kept here because it is
the symptom a user will hit and search for.

## Reproduction

Isolated `-L` tmux server, a synthetic fixture project, 200x50:

```
tmux -L <sock> new-session -d -s b -x 200 -y 50 -c <fixture>
tmux -L <sock> send-keys -t b "./ait board" Enter   # renders all cards      ✔
tmux -L <sock> send-keys -t b q                      # NOT a quit — types "q" ✘
tmux -L <sock> display-message -p -t b '#{pane_current_command}'   # => python
```

Controls:

- `Escape` then `q` **does** quit (`pane_current_command` => `bash`).
- Relaunching in the same pane after a *real* quit renders every card — the
  relaunch path is sound.
- Identical under PyPy and under `AIT_USE_PYPY=0` (CPython) — not
  interpreter-dependent.
- **A headless test cannot fail on this.** `Screen._update_auto_focus` picks a
  different widget per driver: a real terminal picks `Input#search_box`, while
  `App.run_test` picks `HorizontalScroll#board_container`, where `q` quits
  cleanly. The pin must drive a real pty.

## Acceptance criteria

- [x] Root-cause why a launched board renders correct header counts with no
      visible cards, and why single keys do not reach their bindings.
- [x] Fix so a freshly launched board answers `q` — and every other single-key
      binding — with no prior `Tab` / `Esc` / click, while `Tab` still focuses
      the search box and `Esc` still returns to the board.
- [x] Make a column emptied by a filter distinguishable from a genuinely empty
      one, so this symptom cannot be misread again.
- [x] Add a **live tmux** regression pin that launches the board, presses a bare
      `q`, asserts the pane returns to the shell, then relaunches in the same
      pane and asserts card presence. A headless pin cannot fail on this bug, so
      a live fixture is required; the headless pin covers the positive
      focus-target contract alongside it.

## References

- Found during t1490 (manual verification of t1486).
- Original evidence: `aiplans/archived/p1490_manual_verification_auto.md`,
  "Upstream defects identified".

---
Task: t1012_minimonitor_agent_command_dialog_narrow.md
Base branch: main
plan_verified: []
---

# Plan: Add a narrow mode to AgentCommandScreen for the minimonitor (t1012)

## Context

In the minimonitor companion pane (~40 cols wide), pressing `n` to start the
next sibling task opens the shared **`AgentCommandScreen`** ("Pick Task t<N>")
modal, which overflows the narrow pane: the `Cancel` button is truncated to
`Can`, the command preview is clipped (`claude --model claud…`), and the tmux
`(S)ession` / `(W)indow` `Select` boxes are cut off at the dialog border
(captured live from `aitasks_go:agent-pick-5_4`, pane width 40).

The `n` flow chains two dialogs:
1. `NextSiblingDialog` / `ChooseSiblingModal` (`monitor_shared.py`) — these
   **already** implement a `narrow=True` mode (widen + stack buttons vertically),
   and the minimonitor already passes `narrow=True` to them.
2. `_launch_pick_for_own` (`minimonitor_app.py:896`) then pushes
   **`AgentCommandScreen`** (`lib/agent_command_screen.py:132`) — which has
   **no narrow mode**. Its `DEFAULT_CSS` uses `width: 80%` with many horizontal
   rows; at ~26 usable columns every horizontal row overflows.

This is the only dialog in the `n` chain without a narrow variant. The fix
mirrors the established `narrow` pattern (and the `KillConfirmDialog`
`show_preview` minimonitor-variant precedent): add a `narrow` flag +
`.narrow` CSS that widens the dialog and stacks horizontal rows vertically,
and pass `narrow=True` from the single minimonitor call site.

## Blast radius

`AgentCommandScreen` has 12 call sites (board ×5, codebrowser ×3, monitor full
×2, syncer ×1, minimonitor ×1). Only the minimonitor renders in a ~40-col pane;
all others run in full-width TUI windows. A `narrow: bool = False` default
parameter leaves the 11 wide callers byte-for-byte unchanged — only the
minimonitor opts in.

## Changes

### 1. `.aitask-scripts/lib/agent_command_screen.py` — add `narrow` mode

- **Constructor** (`__init__`, ~line 278): add `narrow: bool = False` parameter
  (place it last to preserve the existing keyword call shape); store
  `self._narrow = narrow`.
- **`compose`** (~line 318): at the top, `if self._narrow: self.add_class("narrow")`
  (mirrors `NextSiblingDialog.compose`).
- **`DEFAULT_CSS`**: append a `.narrow` block that targets
  `AgentCommandScreen.narrow ...` selectors. Concretely:
  - Widen the dialog and trim chrome so content has room:
    `#agent_cmd_dialog { width: 100%; min-width: 30; padding: 0 1; border: round $accent; }`
    (round/thinner border + smaller horizontal padding reclaims the ~6 cols the
    `thick` border + `padding 1 2` consume).
  - Stack the side-by-side button/copy rows vertically and make buttons full
    width: for `.agent-cmd-buttons`, `.agent-cmd-copy-row`, `#agent_row`,
    `#profile_row` → `layout: vertical; height: auto; align: left top;` and
    their `Button { width: 1fr; margin: 0 0 1 0; }` (same recipe
    `NextSiblingDialog.narrow` uses for `#next-sib-buttons`).
  - Reflow the tmux field rows so the `width: 12` label no longer eats half the
    pane: for `.tmux-field-row`, `#tmux_new_session_row`, `#tmux_new_window_row`,
    `#tmux_split_row` → `layout: vertical; height: auto;`, their `Label
    { width: auto; height: 1; }`, and their `Select`/`Input`/`Button
    { width: 1fr; }` (label sits above the control instead of beside it).
  - Give the stacked content vertical room: `#agent_cmd_tabs { max-height: 1fr; }`
    (the default `max-height: 20` can clip the now-taller tmux tab; the
    minimonitor pane is ~64 rows, so there is ample height).

  All values are tuned against the 40-col pane during implementation using the
  runtime test below as the objective check.

### 2. `.aitask-scripts/monitor/minimonitor_app.py:926` — pass `narrow=True`

In `_launch_pick_for_own`, add `narrow=True` to the `AgentCommandScreen(...)`
constructor call (the only narrow call site). No other call site changes.

### 3. `tests/test_agent_command_dialog_narrow.py` — new runtime test

Mirror `tests/test_kill_confirm_dialog.py` (`test_buttons_fit_inside_narrow_dialog`,
line 113): a small host `App` that `push_screen(AgentCommandScreen(narrow=True, ...))`,
driven with `app.run_test(size=(40, 50))`. Assert:
- the dialog (`#agent_cmd_dialog`) carries the `narrow` CSS class;
- every `Button` (and the command `Input`, and any `Select`) has its region
  fully within the dialog's region (`button_left >= dialog_left` and
  `button_right <= dialog_right`) — i.e. nothing is clipped at 40 cols.
- A companion assertion at a wide size (e.g. `size=(120, 40)`, `narrow=False`)
  confirms the dialog does **not** carry the `narrow` class (default unchanged).

Construct the screen with `default_agent_string`/`skill_name`/`default_profile`
set so the profile + agent rows render. Tmux availability is environment
dependent; if the tmux tab is absent in CI the test still validates the
profile/agent/command/Direct-tab rows — keep the button/input queries scoped to
what is present (`app.screen.query("Button")`).

## Verification

- `python3 -m pytest tests/test_agent_command_dialog_narrow.py -v` (new test passes).
- `python3 -m pytest tests/test_agent_command_dialog_default_session.py -v`
  (existing dialog test still passes — no regression to constructor).
- `shellcheck` n/a (Python only). Run the repo's Python suite if quick:
  `bash tests/run_all_python_tests.sh` (or at least the two dialog tests).
- **Manual (the real proof):** in a ~40-col minimonitor pane (e.g. reproduce in
  `aitasks_go`), press `n` → confirm the "Pick Task t<N>" dialog fits: no
  truncated buttons, full command text, Session/Window selectors fully visible,
  Direct/tmux tabs operable, `Run`/`Cancel` reachable.
- **Regression spot-check:** open the same dialog from `ait board` (full-width)
  and confirm it looks identical to before (narrow defaults off).

## Step 9 (Post-Implementation)

Standard cleanup/archival: fast profile works on the current branch (no
worktree/merge). Commit code (`bug: …(t1012)`), update + commit the plan via
`./ait git`, then archive via `./.aitask-scripts/aitask_archive.sh 1012`.

## Notes

- Source of truth is the Claude Code TUI Python code; this is not a skill change,
  so no cross-agent skill port follow-up is needed.
- Follow `aidocs/framework/tui_conventions.md` for Textual modal conventions.

## Risk

### Code-health risk: low
- Purely additive: one defaulted constructor param + a scoped `.narrow` CSS
  block + one opt-in call site. Default `narrow=False` keeps all 11 wide callers
  unchanged. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Textual CSS at a fixed 40-col width can be finicky (a row may still overflow if
  a `min-width`/label width is mis-tuned). Bounded and self-checking: the runtime
  test asserts every control fits within the dialog region, so a mis-tune fails
  the test rather than shipping. · severity: low · → mitigation: TBD

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added a `narrow: bool =
  False` parameter to `AgentCommandScreen.__init__`, set `self._narrow`, and call
  `self.add_class("narrow")` at the top of `compose()`. Appended a `.narrow` CSS
  block to `DEFAULT_CSS` widening `#agent_cmd_dialog` to `width: 100%`
  / `min-width: 30` with `padding: 0 1` and a `round` border, and stacking the
  profile/agent/copy/button rows and all tmux field rows vertically (labels
  `width: auto` above their controls; buttons/selects/inputs `width: 1fr`). Set
  `narrow=True` at the single minimonitor call site
  (`minimonitor_app.py` `_launch_pick_for_own`). Added
  `tests/test_agent_command_dialog_narrow.py` (3 runtime tests via
  `App.run_test`).
- **Deviations from plan:** None to the source changes. One test fix during
  development: the `narrow` CSS class is added to the **screen**
  (`AgentCommandScreen`), not the inner `#agent_cmd_dialog` Container — the CSS
  selector `AgentCommandScreen.narrow #agent_cmd_dialog` matches the screen
  class. The class-presence assertions check `app.screen.classes` accordingly.
- **Issues encountered:** Initial test asserted `narrow` on the dialog Container
  and failed; corrected to assert on the screen. No `pytest` in the env — ran via
  `python3 -m unittest`.
- **Key decisions:** Reused the established narrow pattern from
  `NextSiblingDialog`/`ChooseSiblingModal` (`monitor_shared.py`) and the
  `KillConfirmDialog` minimonitor-variant precedent rather than inventing new
  structure. Kept `narrow` defaulting to `False` so the 11 full-width callers
  (board/codebrowser/monitor/syncer) are byte-for-byte unchanged.
- **Upstream defects identified:** None
- **Verification:** `python3 -m unittest tests.test_agent_command_dialog_narrow`
  → 3/3 pass (controls-fit test ran inside tmux, exercising the tmux Select
  boxes). `python3 -m unittest tests.test_agent_command_dialog_default_session`
  → 7/7 pass (no regression). Live manual proof (press `n` in a fresh ~40-col
  minimonitor) deferred to a manual-verification check — the currently-running
  minimonitor holds an old in-memory copy of the code until restarted.

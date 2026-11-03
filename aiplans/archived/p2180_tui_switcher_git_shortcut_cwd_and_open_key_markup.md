---
Task: t2180_tui_switcher_git_shortcut_cwd_and_open_key_markup.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2180 — TUI switcher: git shortcut reads the cwd project; open key breaks markup

## Context

Two defects in `.aitask-scripts/lib/tui_switcher.py`, found by the aitasks_go
(t19_2) Pilot oracle of the real `TuiSwitcherOverlay`:

1. **`action_shortcut_git` (now :1198-1202)** gates on `_build_tui_list()` with
   **no root**. That reads `project_config.yaml` from `Path.cwd()`, not from the
   selected session's project. Every other path passes
   `self._selected_project_root()` (t814/t1099), including the launch path
   (`_get_launch_command(name, project_root)` :1540). In a cross-session or
   cross-repo selection, `g` can no-op although the selected project configures
   `git_tui`, or switch although it does not.
2. **`_render_hint` (now :824)** puts `display_form(_OVERLAY_OPEN_KEY)` into
   Textual markup unescaped. With `shortcuts: shared: tui_switcher: "["`,
   mounting the overlay raises `MarkupError: closing tag '[/Esc[/]' does not
   match any open tag`, so the switcher cannot be opened at all. I reproduced
   this with Textual 8.2.7's `Content.from_markup`.

**Correction to the task's suggested fix.** `rich.markup.escape("[")` and
`textual.markup.escape("[")` both return `"["` unchanged. They only escape a `[`
that starts a tag-shaped token, so "escape the key" would not fix the crash. The
repo already records the right rule for Textual's parser in
`monitor_shared.markup_literal` (t2006). Textual opens a tag at any `[` not
preceded by a backslash, turns exactly `\[` back into `[`, and leaves every
other backslash alone. So prefixing each `[` with `\` is an exact round trip.

**Open-key collision (review finding, verified).** Fixing the markup alone
leaves a second bug for `"["`. The overlay binds `[`/`]` with `priority=True`
to `prev_group`/`next_group`. `_OVERLAY_RESERVED_KEYS` (:444) omits them, so the
toggle also gets a non-priority `dismiss_overlay` binding on `[`. Textual
8.2.7's `App._check_bindings` runs priority bindings first, from the App down.
`_cycle_group` consumes the key whenever `advance_group_selection` finds ≥2
groups, and raises `SkipAction` (falling through to dismiss) only below that.
So with two groups, `[` changes groups, while the planned hint would still say
`[/Esc close`. Parser-only tests cannot see this, because the bindings are
built at import.

Related: `_OVERLAY_RESERVED_KEYS` is built from the **default** quick-jump keys
(`b.key for b in _QUICK_JUMP_BINDINGS`), while `BINDINGS` registers the
**override-applied** ones. When a quick-jump is rebound, its new key is missed
by the collision check and its old key is wrongly blocked. A raw config string
is also never normalised the way Textual normalises binding keys (`"["` becomes
`left_square_bracket`).

**Audit of the other key-into-markup sites (probed, Textual 8.2.7):**

| site | key | today |
|---|---|---|
| `_render_hint` close hint :824 | `[` | **MarkupError** (switcher won't open) |
| `_TuiListItem.compose` :384 | `[` | parses but renders literal `([)[/]`; the style leaks |
| `_hint_segment` :265-285 | `[` | `([)[/] board`: same leak |
| `_hint_segment` | `)` | regex `\(([^)]*)\)` matches `()` in `()) board`, so the wrong span is highlighted |
| any of them | `]`, `\`, `(` | correct |

## Policy decision: structural keys win; the hint advertises only what closes

This keeps the rule the code already states at :438-441: the toggle "skip[s]
it when it collides with a fixed/quick-jump key (escape always closes
regardless)". `[`/`]` are fixed structural keys that were simply missing from
that set. When the toggle collides with any reserved key:

- the toggle gets **no** close binding, so group navigation and quick-jumps
  keep working;
- the hint advertises **`Esc close`** only.

Giving the toggle precedence instead would silently disable group navigation
for anyone who binds the open key to `[`. One module constant decides both the
binding and the hint, so they cannot drift apart.

## Implementation

All code changes are in `.aitask-scripts/lib/tui_switcher.py`.

1. **`_markup_literal(text)`** (new private helper, near `TUI_KEY_HINT_STYLE`)
   returns `text.replace("[", "\\[")`. The docstring names the rule and points
   to `monitor_shared.markup_literal` (t2006) as the canonical statement. That
   module is not imported: `lib/` must not pull in a 4000-line `monitor/`
   module for one line. The docstring also records the one shape the rule
   cannot express, a backslash directly before a real tag, and why every call
   site here is safe: the key is always followed by `)` or `/Esc`.
2. **Escape the three key sites.**
   - `_render_hint` close hint: `_markup_literal(display_form(_OVERLAY_OPEN_KEY))`.
   - `_TuiListItem.compose` :384: `({_markup_literal(display_form(shortcut))})`.
   - `_hint_segment`: `rendered = _markup_literal(render_label(label, key))`
     before the regex sub. This is safe because labels are framework words with
     no `[`. Change `_KEY_PAREN_RE` to `re.compile(r"\((.+?)\)")`. For any
     non-empty group it matches exactly what the old regex matched, because
     both stop at the first `)`. It differs only on `()`, which `render_label`
     never produces for a non-empty key. So the `)` key highlights `())`.
     Update the docstring.
3. **Collision policy (replaces :438-447 and the class-body call).**
   ```python
   def _normalized_keys(key: str) -> frozenset[str]:
       # Textual's own normalisation ("[" -> "left_square_bracket", comma lists unrolled)
       return frozenset(b.key for b in Binding.make_bindings([Binding(key, "noop")]))

   _QUICK_JUMP_LIVE_BINDINGS = register_app_bindings(_TUI_SWITCHER_SCOPE, _QUICK_JUMP_BINDINGS)
   _OVERLAY_OPEN_KEY = resolve_key("shared", "tui_switcher", "j") or "j"
   _OVERLAY_RESERVED_KEYS = frozenset().union(
       *(_normalized_keys(k) for k in ("escape", "enter", "left", "right", "[", "]")),
       *(_normalized_keys(b.key) for b in _QUICK_JUMP_LIVE_BINDINGS),
   )
   #: The single source of truth for "does the open key also close the overlay";
   #: read by BINDINGS and by _render_hint.
   _OVERLAY_TOGGLE_CLOSES = not (_normalized_keys(_OVERLAY_OPEN_KEY) & _OVERLAY_RESERVED_KEYS)
   ```
   `BINDINGS` adds the toggle `dismiss_overlay` binding only if
   `_OVERLAY_TOGGLE_CLOSES`. It splices `*_QUICK_JUMP_LIVE_BINDINGS` in place
   of the inline `register_app_bindings(...)` call. That is the same call at the
   same import time with the same result, now named once so the reserved set
   reads the live keys. Update the comments at :436-441 and :496-500 to state
   the policy. `_QUICK_JUMP_BINDINGS` (the defaults list) stays unchanged, since
   four tests read it.
4. **`_render_hint`** builds `close` as
   `f"[{S}]{_markup_literal(display_form(_OVERLAY_OPEN_KEY))}/Esc[/] close"`
   when `_OVERLAY_TOGGLE_CLOSES`, else `f"[{S}]Esc[/] close"`.
5. **`action_shortcut_git` :1200** uses
   `_build_tui_list(self._selected_project_root())`, and the docstring says it
   gates on the same root the launch path reads.

## Tests (write first; prove red on the current code; prove each guard with a mutant)

- **`tests/test_tui_switcher_hint_text.py`**: add `HostileKeyMarkupTests`. Each
  assertion parses the produced markup with Textual's real parser
  (`textual.content.Content.from_markup`).
  - `_render_hint` with `_OVERLAY_OPEN_KEY="ctrl+["` and
    `_OVERLAY_TOGGLE_CLOSES=True`, single mode and two-group multi mode. The
    output must parse, and its plain text must end with `Ctrl+[/Esc close`.
    Red today: `MarkupError`.
  - `_render_hint` with `_OVERLAY_TOGGLE_CLOSES=False`: the plain text must end
    with `Enter switch  Esc close` (in the multi-group form, `[/] group  Esc
    close`), and the toggle must not appear.
  - `_hint_segment` with `resolve_key` patched to each of `[ ] ( ) \`. The
    plain text must equal `render_label("board", key)`. Exactly one styled
    span must exist, and its slice must equal `f"({display_form(key)})"`. Red
    today for `[` and `)`.
  - `_TuiListItem("board", "Board", False, False)`, with
    `ts._resolve_tui_shortcut` patched to `[`. Parse `Static.content`; the
    plain text must end with ` ([)`. Red today.
  - The existing pinned tests stay unchanged. They prove default keys render
    byte-identically after the change.
- **New `tests/test_tui_switcher_open_key_collision.py`**: a keypress
  regression with the override applied **before the class is built**. Each case
  runs a fresh child interpreter (`subprocess`, `sys.executable`) with
  `TASK_DIR=<tmp>` holding `metadata/userconfig.yaml` with the case's
  `shortcuts:`. The child imports `tui_switcher`, so `BINDINGS` is built from
  the override exactly as in production. It stubs only the I/O seams:
  `discover_aitasks_sessions` returns two `AitasksSession`s in groups `ga` and
  `gb`; `_render_desync_line`, `_populate_list_for` and
  `_resolve_companion_target` are no-ops. It pushes a real
  `TuiSwitcherOverlay(session="s1")` in a host `App` under `run_test`, drives
  keys with Pilot, and prints a JSON verdict that the parent asserts.
  - **Open key `[`, two groups.** The child asserts `ts._OVERLAY_OPEN_KEY ==
    "["` and `_OVERLAY_TOGGLE_CLOSES is False`, which proves the override
    reached import. The mount must not raise. The hint's plain text must
    contain `[/] group` and end with `Esc close`, with no `[/Esc`. Pressing `[`
    must leave the overlay as the active screen and change `_selected_group`.
    Pressing `escape` must dismiss it.
  - **Open key `[`, one group (single mode).** Pressing `[` must leave the
    overlay open. This is the case a missing reservation would fall through
    and close.
  - **Control: default config.** Pressing `j` must dismiss the overlay, and the
    hint must end with `J/Esc close`. This proves the harness detects a close,
    so "still open" above is not vacuous. With two groups, `[` still cycles.
  - **Live-key reservation.** With `shared.tui_switcher: b` and
    `shared.tui_switcher.shortcut_board: k`, the `b` toggle must close
    (`B/Esc close`): the default `b` is no longer reserved. With
    `shared.tui_switcher: k` and `shortcut_board: k`, the toggle must not
    close, and pressing `k` must reach the board quick-jump (record
    `_shortcut_switch`).
  - **Mutants, applied in a scratch copy and never committed.** Drop `"["`/`"]"`
    from the reserved tuple: the two-group hint check and the single-group
    keypress must go red. Revert to the default-key reserved set: the
    live-key cases must go red.
- **New `tests/test_tui_switcher_git_shortcut_root.py`**: an overlay built with
  `object.__new__`, `_selected_project_root` stubbed to a temp project, and
  `_shortcut_switch` stubbed to record calls. Two temp projects:
  `tmux: {git_tui: lazygit}` versus no config. Each test chdirs into the other
  project and restores the cwd in `finally`.
  - Selected project has git, cwd does not: `g` switches to `"git"`. Red today.
  - Selected project has no git, cwd does: `g` is a no-op. Red today.

## Verification

- The three test files above: red before the fix, green after. Run them with
  `~/.aitask/venv/bin/python` if the system `python3` lacks Textual.
- Neighbouring suites: `tests/test_tui_switcher_companion_spawn.py`,
  `tests/test_tui_switcher_agent_launch.py`,
  `tests/test_tui_switcher_default_session_notify.py`,
  `tests/test_shortcut_scopes.py`, `tests/test_markup_colour_contract.py`, and
  `bash tests/test_tui_switcher_footer_fit.sh`.
- `bash tests/run_all_python_tests.sh --test-dir tests`. Read only the last
  line of output for the verdict.

## Out of scope (record as upstream defects in Final Implementation Notes)

- `_render_session_row` (~:877-895) and `_WindowListItem.compose` (~:399)
  insert tmux session, project, group and window names into markup unescaped.
  These are user-derived names, not keys; it is the same hazard class as
  monitor t1580/t2006.

## Step 9

Current-branch mode: there is no merge. Step 9 runs the build/gate
verification, then archives with `aitask_archive.sh 2180` and pushes with
`./ait git push`.

## Risk

### Code-health risk: low
None identified. The change stays in one module. Moving `register_app_bindings`
from the class body to a module constant is the same call at the same import
time with an identical result, and the existing binding and shortcut-scope
tests cover it. The regex change is equivalent on every `render_label` output
for a non-empty key, and the existing pinned-segment tests guard it.

### Goal-achievement risk: low
None identified. Both defects and the collision are reproduced. Each fix is
checked against Textual's real parser, the real keypress dispatch with
import-time overrides, or the real config reader, by tests that are red before
the fix and have guard-specific mutants.

## Final Implementation Notes

- **Actual work done:** I implemented the plan as approved, in
  `.aitask-scripts/lib/tui_switcher.py`.
  - `_markup_literal` escapes `[` at the three key-into-markup sites: the close
    hint, `_TuiListItem` and `_hint_segment`.
  - `_KEY_PAREN_RE` is now `\((.+?)\)`.
  - `_normalized_keys` (via `Binding.make_bindings`) feeds an
    `_OVERLAY_RESERVED_KEYS` that includes `[`/`]` and the override-applied
    quick-jump keys (`_QUICK_JUMP_LIVE_BINDINGS`).
  - One constant, `_OVERLAY_TOGGLE_CLOSES`, decides both the toggle close
    binding and the `_render_hint` close text.
  - `action_shortcut_git` gates on `_build_tui_list(self._selected_project_root())`.
  - The tests are: `tests/test_tui_switcher_hint_text.py` (new
    `HostileKeyMarkupTests`), `tests/test_tui_switcher_git_shortcut_root.py`
    (new) and `tests/test_tui_switcher_open_key_collision.py` (new, a Pilot
    keypress test in a fresh interpreter per case, with
    `TASK_DIR/metadata/userconfig.yaml`).
- **Deviations from plan:** None, apart from correcting a stale comment
  ("registered at class body") above `_TUI_SWITCHER_SCOPE`.
- **Issues encountered:**
  - The task's suggested fix (`rich`/`textual` `markup.escape(key)`) does not
    work: both return a lone `[` unchanged. I used the Textual-specific rule
    from `monitor_shared.markup_literal` (t2006) instead.
  - The plan's first draft deferred the open-key/group-navigation collision.
    Review rejected that, and the collision was verified in Textual 8.2.7's
    `App._check_bindings`. Priority bindings run first, from the App down.
    `_cycle_group` consumes `[` when there are two or more groups and raises
    `SkipAction` (falling through) below that. A modal limits the
    non-priority pass to its own bindings.
- **Key decisions:**
  - **Policy: structural keys and quick-jumps win.** A colliding toggle gets
    no close binding, and the hint advertises only `Esc close`. This matches
    the rule the code already stated ("skip it when it collides with a
    fixed/quick-jump key").
  - The alternative, toggle precedence, would silently kill group navigation
    for anyone who binds the open key to `[`.
  - The `register_app_bindings` call moved from the class body to the
    module-level `_QUICK_JUMP_LIVE_BINDINGS`. It is the same call at the same
    import time with an identical result, and it is named so the reserved set
    reads the live keys.
- **Verification evidence:**
  - All new tests failed on the pre-fix code (including the child's real mount
    `MarkupError` for open key `[`) and pass after the fix.
  - Mutants, run in a scratch copy that was never committed:
    - (M1) dropping `[`/`]` from the reserved tuple makes 2 tests fail. A
      direct run showed `[` closing the overlay in single mode
      (`open: False`), against `open: True` with the fix.
    - (M2) building the reserved set from `_QUICK_JUMP_BINDINGS` defaults
      makes both live-key tests fail.
    - (M3) a hint that ignores `_OVERLAY_TOGGLE_CLOSES` makes 3 tests fail.
  - Neighbouring suites (companion_spawn, agent_launch,
    default_session_notify, shortcut_scopes, markup_colour_contract,
    ring_dedupe, footer_fit.sh, multi_session.sh, brainstorm_session.sh) are
    green.
  - The full `tests/run_all_python_tests.sh` reported `PYTHON SUITE: PASSED
    (runner=pytest, exit=0)`: 10166 passed and 6 skipped in the parallel lane,
    13 passed in the serial lane.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/tui_switcher.py:949-968` — `_render_session_row`
    interpolates tmux session names, disambiguated project names and the
    project-group label into Textual markup unescaped. A session named `[/]`
    (legal for tmux) would raise `MarkupError` and break the overlay mount.
    This is the same hazard class as monitor t1580/t2006. It is not
    reproduced here, only read from the code.
  - `.aitask-scripts/lib/tui_switcher.py:434` — `_WindowListItem.compose`
    interpolates the tmux window name into markup unescaped (same class). It is
    not reproduced here, only read from the code.

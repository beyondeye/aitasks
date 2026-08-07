---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_monitor, minimonitor, tui, ui]
gates: [risk_evaluated]
created_at: 2026-08-07 10:40
updated_at: 2026-08-07 10:40
---

## Problem

In `ait monitor` and `ait minimonitor`, the agent list draws a separator line
between the agents of different repos (implemented as a **tmux session
divider** — in multi-session mode each session is one repo/project, and the
divider is labelled with `snap.pane.session_name`).

That divider is rendered dark grey, with exactly the same `[dim]` style used by
the per-agent task-title lines directly above and below it. The result is that
the divider reads as just another task title, and the repo grouping is hard to
pick out at a glance.

Give the divider a colour that is clearly distinguishable and — as far as
possible — not already in use for other text in the agent list.

## Current state (as explored)

**The divider is duplicated, not shared.** There is no shared separator helper,
no `Separator`/`Divider` widget, and nothing for it in `monitor_shared.py`.
Each app builds its own inline `Static` in a nested closure of
`_rebuild_pane_list()`:

- `.aitask-scripts/monitor/monitor_app.py:1638-1657` — helper
  `mount_with_session_dividers()`:
  ```python
  container.mount(Static(
      f"  [dim]── {label} ──[/]",
      classes="session-divider",
  ))
  ```
  Note: **there is no `.session-divider` CSS rule anywhere** — the class is a
  pure DOM marker and the dark-grey look comes entirely from the `[dim]`
  markup.

- `.aitask-scripts/monitor/minimonitor_app.py:988-1004` — helper
  `append_group()`:
  ```python
  widgets.append(Static(
      f"[dim]── {label} ──[/]",
      classes="mini-session-divider",
  ))
  ```
  Here there are **two** style sources: the `[dim]` markup **and** the CSS rule
  at `minimonitor_app.py:170-174`:
  ```
  .mini-session-divider { height: 1; padding: 0 1; color: $text-muted; }
  ```

Glyph in both: `──` (U+2500 ×2) either side of the label. The full monitor
prepends two literal spaces; minimonitor does not.

**Why it collides.** The task-title line under each agent card uses the same
`[dim]`:
- `monitor_app.py:1565` — `f"\n     [dim italic]t{task_id}: {info.title}[/]"`
- `minimonitor_app.py:768` — `f"\n  [dim]{title}[/]"`

`[dim]` is additionally used for the gates suffix, the `○` other-pane glyph,
the unmarked `☆` glyph, the legend, and the key hints.

**Colours already taken in the agent list** (from `monitor_shared.py`
`_state_color()` at 104-124 and the `format_*` helpers at 127-193, plus inline
markup in both apps):

| colour | meaning |
|---|---|
| `bold magenta` | PROMPT / awaiting-input state dot + status |
| `bold dodger_blue1` | COMPLETED / DONE |
| `yellow` | IDLE; also compare-mode override glyph; `[AUTO]` tag |
| `green` | Active |
| `bold white` | marked `★` (deliberately white so it is not confused with the yellow IDLE dot — see the `format_mark_glyph` docstring at `monitor_shared.py:170-193`) |
| `red` | control fallback in the session bar |
| `dim` | task titles, gates, `○`, `☆`, legend, hints |

**Cyan is unused** anywhere in either agent list, which makes it the natural
candidate. In the Textual CSS blocks the theme vars `$text-muted`, `$accent`,
`$primary`, `$boost`, `$surface`, `$error`, `$warning` are in use.

**No theme/palette module exists** for the monitor TUIs — every colour is a
hardcoded literal at its call site. The only palette in the repo,
`PALETTE_COLORS` in `.aitask-scripts/lib/board_columns.py:124`, belongs to the
board and is unrelated.

## Scope decisions to make during implementation

1. **Sibling `── … ──` headers.** The same glyph + `[dim]` shape is used for
   several *non-divider* headers, which the recolour should probably NOT take
   over (otherwise the new colour stops being a repo-grouping signal):
   - `minimonitor_app.py:940` — own-panel header (`this agent` / `this window`),
     class `mini-own-header`
   - `minimonitor_app.py:1010-1014` — the `── other (N) ──` section header,
     class `mini-section-header`
   - `.aitask-scripts/lib/tui_switcher.py:312-320` — `_GroupHeader`, `bold dim`
     (a different TUI entirely; out of scope unless deliberately included)

   Decide and record whether the new colour is exclusive to the repo/session
   divider.

2. **Where the colour lives.** The two implementations style the divider
   differently (markup-only vs markup + CSS). Consider whether to factor a
   single shared constant/helper into `monitor_shared.py` alongside the other
   `format_*` helpers, rather than editing two hardcoded literals that can
   drift apart again.

## Acceptance criteria

- [ ] The repo/session divider in `ait monitor` renders in a colour that is
      visually distinct from the `[dim]` task-title lines around it.
- [ ] The repo/session divider in `ait minimonitor` renders in the same new
      colour — which requires changing **both** style sources: the inline
      markup and the `.mini-session-divider { color: $text-muted; }` CSS rule
      (leaving the CSS in place would fight or override the markup).
- [ ] The chosen colour is not one already carrying meaning in the agent list
      (not magenta / dodger_blue1 / yellow / green / white / red / dim).
- [ ] Monitor and minimonitor agree on the divider colour.
- [ ] The scope decision on the sibling `── … ──` headers (own-panel header,
      `other` section header, `tui_switcher._GroupHeader`) is made explicitly
      and recorded in the plan.
- [ ] Render-level test coverage: assert the divider's markup/style, not just
      that a `Static` was mounted.

## Testing notes

Existing divider coverage is **structural only** — neither test asserts the
glyph, the markup, or the colour, so a colour change today would break nothing
and be caught by nothing:

- `tests/test_minimonitor_other_section.py:194-212` —
  `test_session_dividers_are_emitted_inside_the_other_section`; asserts 3
  `Static`s are mounted and that `"sA"` / `"sB"` appear in `render().plain`
  (plain text, so markup is stripped).
- `tests/test_multi_session_minimonitor.sh:170-256` (Tier 1e) — asserts widget
  counts and `isinstance(w, Static) and not isinstance(w, mm.MiniPaneCard)` at
  indices 0 and 2, plus "single mode: no divider widgets present".
- `tests/test_multi_session_monitor.sh` has **no** divider coverage at all —
  the full monitor's `mount_with_session_dividers()` is untested.

Add a render-level assertion for the styled divider in both TUIs (this repo's
convention is to assert against `render()` output rather than a replica), and
consider closing the full-monitor gap while here.

## Related

- `t1441_escape_user_titles_in_tui_markup_renderers` touches the same render
  sites (`monitor_app.py` / `minimonitor_app.py` card text builders) but for a
  different purpose — escaping user-supplied titles in markup. Not overlapping
  in goal; watch for edit collisions if both are in flight.

---
Task: t1449_distinguishable_repo_session_divider_color_in_monitors.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

## Context

In `ait monitor` and `ait minimonitor` the agent list draws a rule between the
agents of different repos. It is implemented as a **tmux session divider** — in
multi-session mode each session is one repo/project, so `── <session_name> ──`
*is* the repo boundary.

That rule is rendered `[dim]` — the exact style the per-agent task-title line
under each card uses (`monitor_app.py:1565` `[dim italic]t{id}: {title}[/]`,
`minimonitor_app.py:768` `[dim]{title}[/]`). The divider therefore reads as one
more task title and the repo grouping is invisible at a glance.

**Outcome:** the divider becomes **bold cyan** in both TUIs — a colour that
carries no other meaning in either agent list — and the styling is single-sourced
in `monitor_shared.py` instead of being hardcoded twice.

**Decisions taken with the user:**
- Colour: `bold cyan`. Every other colour in the list is spoken for — `bold
  magenta` (PROMPT), `bold dodger_blue1` (DONE), `yellow` (IDLE), `green`
  (active), `bold white` (`★` mark), `red` (control fallback), `dim` (titles,
  gates, `○`, `☆`, hints). Cyan appears nowhere under `.aitask-scripts/monitor/`
  (only in `lib/tui_switcher.py`, a different TUI).
- Scope: **only** the repo/session divider. The sibling `── … ──` rows in
  minimonitor — the own-agent panel header (`.mini-own-header`) and the OTHER
  section header (`.mini-section-header`) — stay `dim`, so cyan means "repo
  boundary" and nothing else. `lib/tui_switcher.py:312` `_GroupHeader` is a
  different TUI and is out of scope.

## Implementation

### 1. `\.aitask-scripts/monitor/monitor_shared.py` — new shared seam

Add next to the other row formatters (after `format_mark_glyph`, ~line 191), so
the divider joins `format_state_dot` / `format_shadow_glyph` / `format_mark_glyph`
as a shared, styled row element rather than a literal repeated per app:

```python
# Repo/session divider (t1449): in multi-session mode each tmux session is one
# repo/project, so this rule is the repo boundary in the agent list.
#
# Bold cyan, deliberately NOT `dim`: `dim` is what the task-title line under
# every agent card uses, so a dim divider read as one more task title and the
# repo grouping vanished. Cyan also belongs to no state in the ladder
# (magenta / dodger_blue1 / yellow / green) and is not the ★ mark's white,
# which is what makes it legible as *structure* rather than status.
SESSION_DIVIDER_STYLE = "bold cyan"


def format_session_divider(label: str) -> str:
    """The ``── <session> ──`` repo-boundary rule, styled once for both TUIs.

    Callers own their own leading indent (the full monitor indents by two
    columns; minimonitor pads via CSS) but never the style — that is the point
    of this seam.
    """
    return f"[{SESSION_DIVIDER_STYLE}]── {label} ──[/]"
```

### 2. `\.aitask-scripts/monitor/monitor_app.py` — use it

- Add `format_session_divider` to the `from monitor.monitor_shared import (…)`
  list (line 40-48).
- In `mount_with_session_dividers()` (line 1638-1655) replace the literal,
  keeping the two-space indent the call site owns:

```python
container.mount(Static(
    f"  {format_session_divider(label)}",
    classes="session-divider",
))
```

The `.session-divider` class has no CSS rule anywhere — it stays a pure DOM
marker, and the markup remains the only style source for this app.

### 3. `\.aitask-scripts/monitor/minimonitor_app.py` — use it, and drop the second style source

- Add `format_session_divider` to the `from monitor.monitor_shared import (…)`
  list (line 45-54).
- In `append_group()` (line 1000-1003):

```python
widgets.append(Static(
    format_session_divider(label),
    classes="mini-session-divider",
))
```

- In `MiniMonitorApp.CSS`, **delete the `color: $text-muted;` declaration** from
  `.mini-session-divider` (line 170-174), leaving `height` / `padding`:

```
    /* No `color:` — the divider's style is single-sourced in
       monitor_shared.format_session_divider (t1449). */
    .mini-session-divider {
        height: 1;
        padding: 0 1;
    }
```

Leaving `$text-muted` in place would be a second, now-untrue source of truth for
the same row (the markup span wins over the widget colour, so it would be dead
config that reads as if the divider were still muted).

`.mini-own-header` and `.mini-section-header` are **left untouched** — the scope
decision above.

### 4. Tests — new `tests/test_monitor_session_divider.py`

One module covering the shared seam and both TUIs at render level, with the
scope decision pinned as a negative control. Style is asserted via
`Static.render()` → `textual.content.Content.spans` (verified in this Textual
8.2.7: `Content('── sA ──', spans=[Span(0, 8, style='cyan')])`), not just
`.plain`, because `.plain` strips exactly the thing under test.

- `format_session_divider("sA")` contains `bold cyan` and the `── sA ──` body;
  `SESSION_DIVIDER_STYLE` is not `dim`.
- **minimonitor:** reuse the `_snap` / `_FakeContainer` / `_mk_list_app` harness
  pattern from `tests/test_minimonitor_other_section.py:60-125` with
  `multi_session=True` and two sessions; assert each divider Static's spans carry
  a `cyan` style and none carries `dim`.
- **minimonitor negative control:** in the same rebuild, the `── other (N) ──`
  header Static still carries `dim` and **not** cyan.
- **full monitor:** use the `MonitorApp(...).run_test()` + `_FakeMonitor` harness
  pattern from `tests/test_monitor_focus_switch.py:36-165`, with
  `multi_session = True` and snapshots in two sessions; query the
  `#pane-list .session-divider` Statics and assert the same cyan spans, plus that
  the divider text still begins with the two-space indent.
- **cross-TUI agreement:** assert both apps' dividers resolve to the same style
  string, so the two can't drift apart again.

Also extend `tests/test_minimonitor_other_section.py:194-213`
(`test_session_dividers_are_emitted_inside_the_other_section`) with a one-line
style assertion so the existing structural test and the style contract sit
together.

## Verification

```bash
# targeted
~/.aitask/venv/bin/python tests/test_monitor_session_divider.py
~/.aitask/venv/bin/python tests/test_minimonitor_other_section.py
bash tests/test_multi_session_minimonitor.sh     # existing structural divider tier
bash tests/test_multi_session_monitor.sh

# suite (read only the LAST line for the verdict)
bash tests/run_all_python_tests.sh
```

Live check (this is a colour change — the real terminal is the ground truth):
run `ait monitor` and `ait minimonitor` with multi-session mode on (`M` in the
monitor) while agents are running in two repos, and confirm the `── <repo> ──`
rules stand out from the dim task-title lines and from the state colours.

## Risk

### Code-health risk: low
- Three edited call sites plus one new formatter in an existing shared-formatter
  cluster; the change removes a duplicated literal rather than adding structure.
  The only non-cosmetic edit is deleting `color: $text-muted` from
  `.mini-session-divider`, which is inert once the markup carries the colour ·
  severity: low · → mitigation: none needed
- Cyan's legibility depends on the user's terminal palette, and no automated
  test can judge that · severity: low · → mitigation: none needed — the live
  two-repo check is already part of this plan's Verification section

### Goal-achievement risk: low
- The goal is a visual distinction the user judges by eye; the colour and the
  scope were both settled with the user before planning, and the live check is
  the acceptance step · severity: low · → mitigation: none needed

## Step 9 (Post-Implementation)

Merge target `main` (current-branch profile — no worktree), then archival per
task-workflow Step 9.

## Post-Review Changes

### Change Request 1 (2026-08-07 08:20)

- **Requested by user:** the `── other (N) ──` section header should also get a
  distinguishable colour, different from the repo divider's cyan.
- **Changes made:** this **reverses the plan's recorded scope decision**, which
  had deliberately kept that header `dim` so cyan would be the only structural
  colour. New rationale: the two rows share the `── … ──` glyph shape, so the
  header needs a colour of its own to stop reading as a repo boundary — but a
  *different* one, so cyan still means "repo boundary" and nothing else.
  Added `SECTION_HEADER_STYLE` / `format_section_header()` to `monitor_shared.py`
  beside the divider pair; `minimonitor_app.py` uses it and `.mini-section-header`
  lost both `color:` and `text-style: bold` (the markup carries them now).
  Confirmed with the user: the docked own-panel header (`.mini-own-header`,
  `── this agent ──`) stays `dim` — it is outside the pane list.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `.aitask-scripts/monitor/minimonitor_app.py`,
  `tests/test_monitor_session_divider.py`.

## Final Implementation Notes

- **Actual work done:** as planned for the repo divider —
  `SESSION_DIVIDER_STYLE = "bold cyan"` + `format_session_divider()` in
  `monitor_shared.py`, consumed by both `monitor_app.mount_with_session_dividers()`
  (which keeps its two-space indent) and `minimonitor_app.append_group()`, with
  `color: $text-muted` deleted from `.mini-session-divider`. Plus the
  post-review addition of the parallel `SECTION_HEADER_STYLE = "bold #af87ff"` /
  `format_section_header()` seam for the `── other (N) ──` header. New
  `tests/test_monitor_session_divider.py` (18 tests) and a style assertion added
  to the existing structural test in `tests/test_minimonitor_other_section.py`.

- **Deviations from plan:**
  1. The sibling-header scope decision was reversed at user request — see
     Post-Review Changes above.
  2. **The plan's span-only test strategy was insufficient and had to be
     extended.** The plan specified asserting style via
     `Static.render() → Content.spans`. That catches a `dim` divider but is
     blind to an *unresolvable* colour: a span stores the markup's style string
     verbatim, whether or not the renderer can parse it. `CompositedColourTests`
     was added — it mounts both rules under the real `MiniMonitorApp.CSS` and
     asserts the resolved hex off `screen._compositor.render_strips()`.
  3. The plan predicted `Span(0, 8, style='cyan')`; the real span carries the
     whole style string (`'bold cyan'`), so the assertions test substring
     membership.

- **Issues encountered:** the first pass used `medium_purple1` (the name the
  user picked from a preview swatch). It rendered as default foreground.
  **Textual's markup parser resolves CSS colour names only — it does not know
  Rich's xterm names**, and an unknown name fails *silently* rather than
  raising. All 15 span-level tests passed while the header painted `#e0e0e0`.
  Only the composited probe caught it. Fixed by spelling the colour as the hex
  literal `#af87ff` (exactly the swatch previewed to the user) and by adding the
  composited tier so the failure mode is caught mechanically from now on.

- **Key decisions:**
  - Colour spelled as hex, not a name, with the reason recorded at the constant
    — a future edit that "tidies" it back to a name reintroduces the bug.
  - Both `color:` and `text-style:` removed from `.mini-section-header` for the
    same single-source-of-truth reason as the divider's `color:`; leaving them
    would be dead config that reads as if the row were still muted.
  - The full monitor's `AGENTS (N)` / `OTHER (N)` headers were **not** touched:
    they are bold uppercase labels with no `── … ──` rule, so they are not
    siblings of the recoloured rows and colouring them was not requested.
  - Seven negative controls were run, one mutation each. The decisive one:
    reverting to `medium_purple1` failed exactly the two composited tests while
    every span test stayed green — confirming the new tier is load-bearing.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_shared.py:120 — "bold dodger_blue1" is a Rich xterm colour name Textual cannot parse; the COMPLETED/DONE state colour silently paints the default foreground (#e0e0e0) with no bold, so DONE has never rendered blue. Same string at monitor_shared.py:798, monitor_app.py:1261, monitor_app.py:1454, minimonitor_app.py:706. Pre-existing, unrelated to this task's change; found by the composited probe written for it. Fix is `dodgerblue` or a hex literal, plus a composited assertion per state colour.`

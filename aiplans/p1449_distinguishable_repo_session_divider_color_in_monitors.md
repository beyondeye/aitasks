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

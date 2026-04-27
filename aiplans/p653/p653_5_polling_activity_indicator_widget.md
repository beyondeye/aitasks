---
Task: t653_5_polling_activity_indicator_widget.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_4_*.md
Archived Sibling Plans: aiplans/archived/p653/p653_1_*.md, aiplans/archived/p653/p653_2_*.md, aiplans/archived/p653/p653_3_*.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: t653_5 — Reusable PollingIndicator widget for the brainstorm TUI

## Context

Sibling t653_1 introduced two background `set_interval` polls in `brainstorm_app.py` (the fast 2 s initializer poll at line 3240 and the slow 30 s post-Error watcher at line 3276) plus a persistent `#initializer_apply_banner`. Even with the banner, there is no live signal that the watcher is alive between ticks — the user sees a stale banner and no proof that the TUI is still checking. The same gap applies to the recurring 30 s `_status_refresh_timer` installed by `_load_existing_session()` (line 1805) and to the one-shot `set_timer(2.0, self._refresh_status_tab)` calls scattered through the agent control handlers (lines 1618, 1629, 1640, 2100).

This task adds a small reusable `PollingIndicator(Static)` widget — a single-character circle (`●`) with three states (`off` / `dim` / `flash`) — and wires one indicator per polling operation, mounted next to the operation's associated widget (initializer banner, Status tab content), per the user direction "contextual to the operation it refers to". The dim cycle reassures the user the watcher is installed; the flash confirms a tick just fired.

## Approach

1. New file `.aitask-scripts/brainstorm/polling_indicator.py` containing the `PollingIndicator` widget (~80 LOC). Colocating inside the already-3290-line `brainstorm_app.py` would worsen its size without benefit.
2. Two indicator instances mounted via `compose()` in `BrainstormApp`:
   - **Initializer indicator** — sibling of `#initializer_apply_banner`, on the right edge of the same row.
   - **Status indicator** — small header row inside the `tab_status` TabPane, above `#status_content` (cannot live inside `#status_content` because `_refresh_status_tab` calls `container.remove_children()`).
3. Wiring in `brainstorm_app.py`:
   - Initializer indicator: `start()` at the top of `_start_initializer_wait` (next to the `set_interval(2, ...)`), `flash()` at the top of `_poll_initializer`, `stop()` on the `Completed` branch of `_poll_initializer` (line 3257). The Error/Aborted branch keeps the timer alive (slow 30 s) so the indicator stays in dim cycle and only its tick rate changes — no extra wiring needed.
   - Status indicator: `start()` at the top of `_load_existing_session` (right before line 1805), `flash()` at the top of `_refresh_status_tab` (line 1865). One-shot `set_timer(2.0, self._refresh_status_tab)` calls inherit the flash for free since they invoke the same callback. `stop()` is never needed (timer lives for the app's lifetime).
4. Theme integration via `$accent-darken-3 / -2 / -1 / $accent` color tokens; no hard-coded RGB.

## Verified codebase facts

- `BrainstormApp.compose()` — `brainstorm_app.py:1343`. Currently:
  - `Header` (1344)
  - `Static("", id="initializer_apply_banner", classes="initializer-banner")` (1345)
  - `TabbedContent` opens at 1346
  - `TabPane("Status", id="tab_status")` at 1369 contains a single `VerticalScroll(id="status_content")` (1370)
  - `Footer()` (1371)
- Inline `CSS = """..."""` block — `brainstorm_app.py:904`. `.initializer-banner` rule at lines 909–919 (uses `display: none` / `display: block`).
- `__init__` — `brainstorm_app.py:1299`. Already initializes `_initializer_*` and `_status_refresh_timer` state at lines 1313–1319.
- Polling sites (verified via grep `set_interval|set_timer`):
  - `brainstorm_app.py:1618` — `set_timer(2.0, self._refresh_status_tab)` on resume/pause
  - `brainstorm_app.py:1629` — same on kill
  - `brainstorm_app.py:1640` — same on hard-kill (only on success)
  - `brainstorm_app.py:1805` — `self._status_refresh_timer = self.set_interval(30, self._refresh_status_tab)` in `_load_existing_session`
  - `brainstorm_app.py:2100` — `set_timer(2.0, self._refresh_status_tab)` in `_delayed_refresh_status`
  - `brainstorm_app.py:3240` — `self._initializer_timer = self.set_interval(2, self._poll_initializer)` in `_start_initializer_wait`
  - `brainstorm_app.py:3276` — `self._initializer_timer = self.set_interval(30, self._poll_initializer)` in the Error/Aborted branch of `_poll_initializer`
- `_refresh_status_tab` — `brainstorm_app.py:1865`. First action after the early-return guards is `container.remove_children()` (line 1875) — confirms the indicator must live OUTSIDE `#status_content`.
- `_poll_initializer` Completed branch sets `_initializer_done = True` and calls `self._initializer_timer.stop()` at line 3258. The Error branch only swaps the timer interval (line 3276) — does NOT set `_initializer_done`.
- `Static`, `Horizontal`, `reactive` already imported at lines 28, 17, 36.

## Step-by-step

### S1. Create `polling_indicator.py`

New file `.aitask-scripts/brainstorm/polling_indicator.py`:

```python
"""Reusable polling-activity indicator for the brainstorm TUI.

A single-character circle widget with three states:
  - off:   blank/transparent, does not draw attention
  - dim:   slowly cycles through three brightness levels (~0.8 s/step)
  - flash: briefly bright (~0.2 s) then returns to dim cycle

Use start()/stop() to bracket the lifetime of an underlying poll, and
flash() to acknowledge a poll-fire.
"""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class PollingIndicator(Static):
    """Visual heartbeat for a background poller."""

    GLYPH = "●"
    DIM_INTERVAL = 0.8       # seconds per dim-cycle step
    FLASH_DURATION = 0.2     # seconds the bright flash stays on

    DEFAULT_CSS = """
    PollingIndicator {
        width: 1;
        height: 1;
        padding: 0;
        margin: 0;
        content-align: center middle;
        color: $background;          /* off → invisible but reserves width */
    }
    PollingIndicator.-dim-1 { color: $accent-darken-3; }
    PollingIndicator.-dim-2 { color: $accent-darken-2; }
    PollingIndicator.-dim-3 { color: $accent-darken-1; }
    PollingIndicator.-flash { color: $accent; text-style: bold; }
    """

    state: reactive[str] = reactive("off")

    def __init__(self, **kwargs) -> None:
        super().__init__(self.GLYPH, **kwargs)
        self._cycle_timer = None
        self._flash_timer = None
        self._dim_idx = 0  # 0..2 → -dim-1, -dim-2, -dim-3

    # ---- public API ----------------------------------------------------

    def start(self) -> None:
        """Begin the dim-cycle. No-op if already running."""
        if self._cycle_timer is not None:
            return
        self._dim_idx = 0
        self.state = "dim"
        self._apply_dim_class()
        self._cycle_timer = self.set_interval(self.DIM_INTERVAL, self._dim_tick)

    def stop(self) -> None:
        """Stop dim-cycle and any in-flight flash. Returns to off."""
        if self._cycle_timer is not None:
            self._cycle_timer.stop()
            self._cycle_timer = None
        if self._flash_timer is not None:
            self._flash_timer.stop()
            self._flash_timer = None
        self.state = "off"

    def flash(self) -> None:
        """Briefly switch to bright; then return to dim (or off)."""
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self.state = "flash"
        self._flash_timer = self.set_timer(self.FLASH_DURATION, self._end_flash)

    # ---- internals -----------------------------------------------------

    def watch_state(self, _old: str, new: str) -> None:
        for cls in ("-dim-1", "-dim-2", "-dim-3", "-flash"):
            self.remove_class(cls)
        if new == "dim":
            self._apply_dim_class()
        elif new == "flash":
            self.add_class("-flash")
        # off → no class; CSS default rule renders it transparent.

    def _apply_dim_class(self) -> None:
        for cls in ("-dim-1", "-dim-2", "-dim-3"):
            self.remove_class(cls)
        self.add_class(f"-dim-{self._dim_idx + 1}")

    def _dim_tick(self) -> None:
        self._dim_idx = (self._dim_idx + 1) % 3
        # Don't override an active flash; the flash-end callback restores dim.
        if self._flash_timer is None and self.state == "dim":
            self._apply_dim_class()

    def _end_flash(self) -> None:
        self._flash_timer = None
        if self._cycle_timer is not None:
            self.state = "dim"
            self._apply_dim_class()
        else:
            self.state = "off"
```

### S2. Import + compose changes in `brainstorm_app.py`

Add import (top of file, with the other brainstorm imports near line 49–60):

```python
from brainstorm.polling_indicator import PollingIndicator
```

In `compose()` (`brainstorm_app.py:1343`), replace the current line 1345:

```python
yield Static("", id="initializer_apply_banner", classes="initializer-banner")
```

with a Horizontal row that holds both the banner and its indicator:

```python
with Horizontal(id="initializer_row", classes="initializer-row"):
    yield Static("", id="initializer_apply_banner", classes="initializer-banner")
    yield PollingIndicator(id="initializer_polling_indicator")
```

In the `tab_status` `TabPane` (`brainstorm_app.py:1369–1370`), change:

```python
with TabPane("Status", id="tab_status"):
    yield VerticalScroll(id="status_content")
```

to:

```python
with TabPane("Status", id="tab_status"):
    with Horizontal(id="status_header", classes="status-header"):
        yield Label("Status", classes="status_pane_title")
        yield PollingIndicator(id="status_polling_indicator")
    yield VerticalScroll(id="status_content")
```

### S3. CSS adjustments

Update the inline `CSS` block (`brainstorm_app.py:904`):

1. Replace the current `.initializer-banner` rule (lines 909–919) with:

   ```css
   #initializer_row {
       height: 1;
   }

   .initializer-banner {
       width: 1fr;
       height: 1;
       padding: 0 1;
       background: transparent;
       color: $text;
   }

   .initializer-banner.visible {
       background: $error;
   }
   ```

   This keeps the row at a constant 1 line so the indicator's position is stable; the banner's "visible" toggle now changes only its background, not layout.

2. Add a small block for the new Status header row (anywhere in the CSS block — alongside the other `.status_*` rules near line 944 is a natural fit):

   ```css
   .status-header {
       height: 1;
       padding: 0 1;
   }

   .status_pane_title {
       width: 1fr;
       text-style: bold;
   }
   ```

### S4. Wire the initializer indicator

In `_start_initializer_wait()` (`brainstorm_app.py:3231`), insert just before the existing `self._initializer_timer = self.set_interval(2, ...)` line (3240):

```python
try:
    self.query_one("#initializer_polling_indicator", PollingIndicator).start()
except Exception:
    pass
```

In `_poll_initializer()` (`brainstorm_app.py:3242`), insert as the very first statement after the early-return guard (i.e., immediately after the `if self._initializer_done or self._initializer_agent is None: return` block, around line 3245):

```python
try:
    self.query_one("#initializer_polling_indicator", PollingIndicator).flash()
except Exception:
    pass
```

In the Completed branch of `_poll_initializer()` (around line 3258, right after `self._initializer_timer.stop()`), add:

```python
try:
    self.query_one("#initializer_polling_indicator", PollingIndicator).stop()
except Exception:
    pass
```

The Error/Aborted branch deliberately does NOT call `stop()` — the timer is still alive (slow 30 s) and the indicator should keep dim-cycling.

### S5. Wire the status indicator

In `_load_existing_session()` (`brainstorm_app.py:1794`), insert just before the existing `self._status_refresh_timer = self.set_interval(30, ...)` line (1805):

```python
try:
    self.query_one("#status_polling_indicator", PollingIndicator).start()
except Exception:
    pass
```

(The `try/except` covers the case where `_load_existing_session()` is called multiple times — `start()` is already a no-op if the cycle timer is running.)

In `_refresh_status_tab()` (`brainstorm_app.py:1865`), insert as the very first statement (above the `tabbed = self.query_one(TabbedContent)` line):

```python
try:
    self.query_one("#status_polling_indicator", PollingIndicator).flash()
except Exception:
    pass
```

This single placement covers all five `_refresh_status_tab` call sites: the recurring 30 s `set_interval` AND the four one-shot `set_timer` triggers AND the `on_tabbed_content_tab_activated` direct call.

No `stop()` call — the status timer lives for the app's lifetime.

## Files touched

- **NEW** `.aitask-scripts/brainstorm/polling_indicator.py` — `PollingIndicator(Static)` widget (~80 lines)
- `.aitask-scripts/brainstorm/brainstorm_app.py` — import (1 line), `compose()` changes (initializer row + status header), CSS (`.initializer-banner` rewrite + `#initializer_row` + `.status-header` + `.status_pane_title`), and 5 wiring touch-points (`start`/`flash`/`stop` calls in `_start_initializer_wait`, `_poll_initializer` (×2), `_load_existing_session`, `_refresh_status_tab`). Net: ~30 lines added, ~5 changed.

## Verification

1. **Static audit.** After wiring, every `set_interval`/`set_timer` site in `brainstorm_app.py` should be reachable from a `.flash()` call via its callback:
   ```bash
   grep -nE "set_interval|set_timer" .aitask-scripts/brainstorm/brainstorm_app.py
   ```
   Cross-check each callback name against `.flash()` placements in `_poll_initializer` and `_refresh_status_tab`. The two `set_interval` sites have matching `.start()` calls; the Completed branch has the only `.stop()` for the initializer indicator.

2. **Live initializer (happy path).** Run `ait brainstorm <fresh_id>` on a new session that triggers the initializer agent. Confirm:
   - `●` indicator appears next to the (empty) initializer row immediately on `_start_initializer_wait`.
   - Indicator dim-cycles continuously.
   - At each 2 s tick, indicator flashes bright then returns to dim.
   - On `Completed`, indicator goes dark (off) and the banner stays hidden.

3. **Live initializer (Error → recovery).** Reuse the synthetic Error fixture from t653_1's verification step 3 (`crew-brainstorm-9999/` with `status: Error` and no `_output.md`). Open `ait brainstorm 9999`. Confirm:
   - Indicator stays in dim cycle after the Error transition (timer is now slow 30 s).
   - Every ~30 s, indicator flashes briefly.
   - Banner shows the retry hint.
   - When a valid `_output.md` is dropped in and the slow watcher fires, indicator flashes, banner clears, indicator goes off.

4. **Status tab.** Open any session, switch to the Status tab. Confirm:
   - Indicator visible in the `Status` header row.
   - Dim cycles continuously (alive for the app's lifetime).
   - Flashes immediately on tab activation, then on each 30 s tick.
   - Pressing `p` / `k` / `K` on a process row triggers an additional flash 2 s later (one-shot `set_timer` → `_refresh_status_tab` → `flash()`).

5. **Theme.** Toggle Textual theme (dark/light). Indicator brightness levels remain readable in both. No hard-coded colors.

6. **No-regression.** Banner display behavior must remain visually identical when no initializer error is active (the new constant-height row is empty and transparent, so it should look the same as the old `display: none` collapsed row aside from one extra blank line of vertical space).

7. **Existing test suite.**
   ```bash
   for f in tests/test_*brainstorm*.sh tests/test_*initializer*.sh; do bash "$f"; done
   ```
   Should pass with no regressions.

## Out of scope

- Wiring polling indicators in OTHER ait TUIs (board, monitor, codebrowser, etc.). This task is brainstorm-only. If the widget proves useful, a follow-up task can lift `polling_indicator.py` to a shared location (e.g. `.aitask-scripts/lib/`) and wire those TUIs.
- Heartbeat fixes (Layer A — owned by parent t650), tolerant initializer apply (Layer C — t653_2), agent-crew status changes (Layer D — t653_3).
- Adding new polling sites or changing existing poll cadences. The widget is purely visual.

## Step 9 — Post-Implementation

Standard task-workflow archival. No build verification configured (`verify_build` not set in `project_config.yaml`). After commit:
- Append "Final Implementation Notes" covering: actual files touched, any deviations (especially around CSS or compose tweaks), and a note for sibling t653_4 (manual-verification aggregate) pointing at this plan's Verification §2/§3/§4 as candidate live-TUI checklist items to add.
- Run `aitask_archive.sh 653_5`. Push.

## Notes

- Depends on t653_1 landing first (confirmed — already archived). The slow 30 s watcher introduced by t653_1 is the headline consumer of the initializer indicator.
- t653_4 (manual verification aggregate) can optionally be extended with checklist items for the new visual behavior; the offer is non-blocking for this task and naturally surfaces via the Step 8c follow-up procedure.

## Final Implementation Notes

- **Actual work done:** All 5 step blocks (S1–S5) implemented as planned.
  - S1: New file `.aitask-scripts/brainstorm/polling_indicator.py` (~99 lines) — `PollingIndicator(Static)` widget with reactive `state` ("off" / "dim" / "flash"), `start()` / `stop()` / `flash()` methods, three-level dim cycle via `-dim-1` / `-dim-2` / `-dim-3` classes, and a brief `-flash` highlight class. Off state uses `color: $background` so the cell is invisible but reserves width.
  - S2: Added `from brainstorm.polling_indicator import PollingIndicator` import. `compose()` now yields a `Horizontal(id="initializer_row")` containing the existing banner Static plus a `PollingIndicator(id="initializer_polling_indicator")`. The Status tab pane now opens with a `Horizontal(id="status_header", classes="status-header")` containing a `Label("Status", classes="status_pane_title")` and a `PollingIndicator(id="status_polling_indicator")`, followed by the existing `VerticalScroll(id="status_content")` (kept unchanged so `_refresh_status_tab`'s `container.remove_children()` does not strip the indicator).
  - S3: Replaced the old `display: none` / `display: block` `.initializer-banner` rules with a constant-height `#initializer_row` (`height: 1`), a transparent `.initializer-banner` (`width: 1fr`), and a `.initializer-banner.visible` rule that flips only the background to `$error`. Added `.status-header` and `.status_pane_title` rules for the new Status header row.
  - S4: `start()` call inserted in `_start_initializer_wait` immediately before the existing 2 s `set_interval`. `flash()` call inserted at the very top of `_poll_initializer` (after the early-return guard). `stop()` call inserted in the Completed branch right after `self._initializer_timer.stop()`. The Error/Aborted branch is intentionally unchanged so the indicator keeps dim-cycling on the slower 30 s timer.
  - S5: `start()` call inserted in `_load_existing_session` immediately before the existing `_status_refresh_timer = self.set_interval(30, ...)`. `flash()` call inserted at the very top of `_refresh_status_tab` so it covers the recurring 30 s tick, the four one-shot `set_timer(2.0, ...)` triggers (lines 1618/1629/1640/2100 in the original file), and the `on_tabbed_content_tab_activated` direct call. No `stop()` — the status timer lives for the app's lifetime.

- **Deviations from plan:** None of substance. The plan is implemented as specified.

- **Issues encountered:**
  - `tests/test_brainstorm_cli.sh` was already failing on `main` before this task started (missing `launch_modes_sh.sh` from `setup_test_repo` + missing `codeagent_config.json`). The failure is unrelated to PollingIndicator and was not regressed by this change.
  - All other Python and bash tests in the brainstorm suite pass: `test_brainstorm_crew.py` (34/34), `test_brainstorm_dag.py` (24/24), `test_brainstorm_sections.py` (20/20), `test_brainstorm_wizard_sections.py` (16/16), `test_brainstorm_cli_python.py` (14/14), `test_apply_initializer_output.sh` (8/8), `test_apply_initializer_tolerant.sh` (15/15), `test_brainstorm_init_proposal_file.sh` (3/3).

- **Key decisions:**
  - **New file vs colocated:** Placed `PollingIndicator` in its own module rather than inside `brainstorm_app.py` (already 3290 lines). Easier to lift into `.aitask-scripts/lib/` later if other TUIs adopt it.
  - **Off state via background-coloured glyph, not `display: none`:** Keeps the column width reserved so the indicator's position is stable when it transitions in and out of the dim cycle. The visual is identical to a blank cell for the user.
  - **Single `flash()` call inside `_refresh_status_tab` instead of one per call site:** All five `set_timer(2.0, self._refresh_status_tab)` and `set_interval(30, self._refresh_status_tab)` sites end up calling the same method. Wiring once at the top of the method covers them all without leaking polling-indicator concerns into agent control handlers (resume/pause/kill).
  - **Defensive `try/except` around every `query_one(...)` call:** The wiring fires on session load before the widget tree is fully ready (`_start_initializer_wait` runs from a thread callback, `_load_existing_session` can be re-entered) and during shutdown when widgets may already be detached. Mirrors the same pattern used by t653_1's `_set_apply_banner` / `_clear_apply_banner`.

- **Notes for sibling tasks:**
  - **t653_4 (manual verification aggregate):** Three live-TUI checks in this plan's Verification section (§2 happy path, §3 Error → recovery dim-cycle / 30 s flash, §4 Status tab dim-cycle + one-shot flashes from `p`/`k`/`K`) are not exercisable from automated tests and are good candidates to append to t653_4's checklist. Theme switching (§5) is also human-only.
  - **Future "lift to shared lib":** When another TUI (board, monitor, codebrowser) wants a polling indicator, move `polling_indicator.py` from `.aitask-scripts/brainstorm/` to `.aitask-scripts/lib/`. The widget has no brainstorm-specific dependencies — it only imports from `textual.reactive` and `textual.widgets`. Update the brainstorm import accordingly and add the new TUI's import.

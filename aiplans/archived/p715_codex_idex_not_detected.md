---
Task: t715_codex_idex_not_detected.md
Base branch: main
plan_verified: []
---

# t715 — Codex CLI agent windows reported as not-idle in monitor / minimonitor

## Context

The user observed that `agent-pick-713` (a Codex CLI agent window in the
`aitasks` tmux session) was actually idle — sitting on a `Yes, proceed (y) /
No, ... (esc)` confirmation prompt waiting for user input — but both
`ait minimonitor` and `ait monitor` reported it as OK / not-idle in the
agentlist pane.

Hands-on diagnosis with `tmux capture-pane`:

```
# With -e (preserves escape codes) — what the monitor uses
tmux capture-pane -p -e -t %28 -S -200 > /tmp/cap1.txt; sleep 4; tmux capture-pane -p -e -t %28 -S -200 > /tmp/cap2.txt; diff /tmp/cap1.txt /tmp/cap2.txt
# → captures DIFFER. Sole diff is the spinner bullet color:
#   <  …[38;2;156;164;198m•…
#   >  …[38;2;124;130;159m•…

# Without -e — visible-text-only
tmux capture-pane -p -t %28 -S -200 > /tmp/cap1.txt; sleep 4; tmux capture-pane -p -t %28 -S -200 > /tmp/cap2.txt; diff …
# → captures BYTE-IDENTICAL.
```

**Root cause:** `.aitask-scripts/monitor/tmux_monitor.py:372-376` captures
pane content with `-e` (escape codes preserved) and `_finalize_capture`
(`tmux_monitor.py:345-370`) compares the raw captured string verbatim
against the previously stored value. Codex CLI animates the "Running"
spinner bullet color even when blocked on a user-confirmation prompt —
`\x1b[38;2;156;164;198m•` ↔ `\x1b[38;2;124;130;159m•` etc. The visible glyph
never changes, but the escape codes do, so the byte-equality check declares
the pane content "changed" every refresh tick. `_last_change_time[pane_id]`
resets to "now" forever, `idle_seconds` never grows past `idle_threshold`
(default 5s), `is_idle` stays False — and every Codex agent waiting on an
interactive prompt shows up as active in `monitor_app.py` / `minimonitor_app.py`.

The display path (`_ansi_to_rich_text` in `monitor/monitor_shared.py:38`,
consumed at `monitor_shared.py:417` and `monitor_app.py:1072`) needs the
escape codes for colored rendering, so the capture call must keep `-e`.

## Approach

Per the user's direction: keep the existing raw-byte comparison as one mode,
add an ANSI-stripped comparison as a second mode, **default to stripped**
globally, and expose a per-pane override toggled by a keyboard shortcut on
the focused pane in both `ait monitor` and `ait minimonitor`.

Two compare modes:

| Mode | Comparison form | When to use |
|------|-----------------|-------------|
| `stripped` (default) | ANSI escape codes removed before equality check | Codex CLI / any agent that animates colors while idle |
| `raw` | Current behavior — full captured bytes including escape codes | Diagnostic / legacy fallback if a future agent renders idle UI by toggling escape codes that DO matter |

Per-pane override is in-memory only (not persisted across runs). Global
default comes from a new optional `tmux.monitor.compare_mode_default` key
in `aitasks/metadata/project_config.yaml` (defaults to `stripped` if
absent), so the project default is configurable but does not require a
config edit to fix the reported bug.

The shortcut cycles the focused pane's mode `default → raw → stripped →
default` (where `default` means "follow the global default", clearing any
per-pane override).

## Implementation

### 1. `.aitask-scripts/monitor/tmux_monitor.py`

a. Add `re` to the standard-library imports near the top of the file.

b. Add a module-level regex matching CSI sequences (covers SGR colors plus
   any other CSI animation tokens) and a tiny strip helper:

   ```python
   _ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

   def _strip_ansi(s: str) -> str:
       return _ANSI_CSI_RE.sub("", s)
   ```

c. Add a module-level constant for valid mode names:

   ```python
   COMPARE_MODE_STRIPPED = "stripped"
   COMPARE_MODE_RAW = "raw"
   COMPARE_MODES = (COMPARE_MODE_STRIPPED, COMPARE_MODE_RAW)
   DEFAULT_COMPARE_MODE = COMPARE_MODE_STRIPPED
   ```

d. Extend `TmuxMonitor.__init__` with a new keyword argument
   `compare_mode_default: str = DEFAULT_COMPARE_MODE` and store it on the
   instance. Initialize `self._compare_mode_overrides: dict[str, str] = {}`
   alongside the other per-pane state.

e. Add three new methods on `TmuxMonitor`:

   ```python
   def get_compare_mode(self, pane_id: str) -> str:
       """Effective compare mode for a pane (override if set, else default)."""
       return self._compare_mode_overrides.get(pane_id, self.compare_mode_default)

   def set_compare_mode(self, pane_id: str, mode: str | None) -> str:
       """Set per-pane override; pass None to clear and follow the global default.

       Clears the stored last-content for the pane so the next capture
       re-baselines under the new comparison form (avoids one tick of
       false 'changed' immediately after the toggle).
       """
       if mode is None:
           self._compare_mode_overrides.pop(pane_id, None)
       else:
           if mode not in COMPARE_MODES:
               raise ValueError(f"unknown compare mode: {mode!r}")
           self._compare_mode_overrides[pane_id] = mode
       self._last_content.pop(pane_id, None)
       return self.get_compare_mode(pane_id)

   def cycle_compare_mode(self, pane_id: str) -> tuple[str, bool]:
       """Cycle the pane through default → raw → stripped → default.

       Returns (new_effective_mode, is_following_default).
       """
       current_override = self._compare_mode_overrides.get(pane_id)
       # Order: no override (follow default) → raw → stripped → no override
       if current_override is None:
           new_override: str | None = COMPARE_MODE_RAW
       elif current_override == COMPARE_MODE_RAW:
           new_override = COMPARE_MODE_STRIPPED
       else:
           new_override = None
       effective = self.set_compare_mode(pane_id, new_override)
       return effective, (new_override is None)
   ```

f. Modify `_finalize_capture` to pick the comparison form per-pane while
   keeping the raw `content` on `PaneSnapshot.content`:

   ```python
   def _finalize_capture(
       self, pane: TmuxPaneInfo, content: str
   ) -> PaneSnapshot:
       now = time.monotonic()
       pane_id = pane.pane_id

       mode = self.get_compare_mode(pane_id)
       if mode == COMPARE_MODE_STRIPPED:
           compare_value = _strip_ansi(content)
       else:  # COMPARE_MODE_RAW
           compare_value = content

       prev = self._last_content.get(pane_id)
       if prev is None or compare_value != prev:
           self._last_content[pane_id] = compare_value
           self._last_change_time[pane_id] = now

       last_change = self._last_change_time.get(pane_id, now)
       idle_seconds = now - last_change
       is_idle = (
           idle_seconds > self.idle_threshold
           if pane.category == PaneCategory.AGENT
           else False
       )

       return PaneSnapshot(
           pane=pane,
           content=content,        # raw — _ansi_to_rich_text needs colors
           timestamp=now,
           idle_seconds=idle_seconds,
           is_idle=is_idle,
       )
   ```

g. Extend `_clean_stale` to also drop overrides for vanished panes:

   ```python
   def _clean_stale(self, current_ids: set[str]) -> None:
       stale = [pid for pid in self._last_content if pid not in current_ids]
       for pid in stale:
           del self._last_content[pid]
           self._last_change_time.pop(pid, None)
           self._pane_cache.pop(pid, None)
       for pid in list(self._compare_mode_overrides):
           if pid not in current_ids:
               self._compare_mode_overrides.pop(pid, None)
   ```

h. Extend `load_monitor_config` to read an optional
   `tmux.monitor.compare_mode_default` key and validate it:

   ```python
   if "compare_mode_default" in monitor:
       val = str(monitor["compare_mode_default"])
       if val in COMPARE_MODES:
           defaults["compare_mode_default"] = val
       # silently ignore invalid values; defaults remain
   ```

   And add `"compare_mode_default": DEFAULT_COMPARE_MODE` to the `defaults`
   dict at the top of the function.

### Per-pane idle-mode indicator (pseudo-icon — shown on every agent card)

Each agent card in BOTH `monitor` and `minimonitor` shows the pane's
effective idle-detection mode as a small one-character pseudo-icon, with
color/dim conveying default-vs-override:

| Mode | Glyph | Meaning |
|------|-------|---------|
| stripped | `≈` | Fuzzy / ANSI-stripped equality |
| raw      | `=` | Strict byte-equal |

Color rule:
- Following the global default: dim glyph (e.g. `[dim]≈[/]`).
- Per-pane override: bright glyph (e.g. `[yellow]=[/]`) — the color flags
  that the user has actively diverged from the default.

This lets the user scan the agent list and immediately see which detection
mode each pane is using, without enlarging the compact UI.

The pseudo-icon glyphs are introduced as module-level constants in
`monitor_shared.py` so both TUIs share the same vocabulary:

```python
COMPARE_MODE_ICONS = {
    "stripped": "≈",
    "raw": "=",
}

def format_compare_mode_glyph(mode: str, is_override: bool) -> str:
    glyph = COMPARE_MODE_ICONS.get(mode, "?")
    if is_override:
        return f"[yellow]{glyph}[/]"
    return f"[dim]{glyph}[/]"
```

Both call sites read the per-pane mode from `monitor.get_compare_mode(pane_id)`
and `(pane_id in monitor._compare_mode_overrides)` to decide override.
(Optionally expose a small public helper `monitor.is_compare_mode_overridden(pane_id) -> bool` to avoid touching the underscore attribute.)

### 2. `.aitask-scripts/monitor/monitor_app.py`

a. Add a binding inside the existing `BINDINGS` list (anywhere after the
   primary navigation bindings — `r`/`z`/`t` block):

   ```python
   Binding("d", "cycle_compare_mode", "Detect"),
   ```

b. Add the action handler. The action looks up the focused pane, calls
   `monitor.cycle_compare_mode(pane_id)`, and shows a Textual notification:

   ```python
   def action_cycle_compare_mode(self) -> None:
       pane_id = self._focused_pane_id
       if pane_id is None or self._monitor is None:
           return
       new_mode, is_default = self._monitor.cycle_compare_mode(pane_id)
       suffix = " (default)" if is_default else ""
       self.notify(
           f"Idle detect mode for this pane: {new_mode}{suffix}",
           timeout=3,
       )
   ```

   Wire `monitor.compare_mode_default` from `load_monitor_config()` through
   to the existing `TmuxMonitor(...)` construction (extend the kwargs).

c. In `_format_agent_card_text` (`monitor_app.py:892`), append the
   pseudo-icon next to the dot/status. Concretely, modify the `text =`
   line to insert the glyph between the status and any trailing space:

   ```python
   def _format_agent_card_text(self, snap: PaneSnapshot) -> str:
       if snap.is_idle:
           idle_s = int(snap.idle_seconds)
           dot = "[yellow]●[/]"
           status = f"[yellow]IDLE {idle_s}s[/]"
       else:
           dot = "[green]●[/]"
           status = "[green]Active[/]"

       pane_id = snap.pane.pane_id
       mode = self._monitor.get_compare_mode(pane_id) if self._monitor else "stripped"
       is_override = (
           self._monitor is not None
           and self._monitor.is_compare_mode_overridden(pane_id)
       )
       glyph = format_compare_mode_glyph(mode, is_override)

       text = (
           f" {dot} {glyph} {snap.pane.window_index}:{snap.pane.window_name} "
           f"({snap.pane.pane_index})  {status}"
       )
       # ...task_id line unchanged
       return text
   ```

d. In the pane detail render path (the same area where `Status:` is shown
   around `monitor_app.py:893`/`monitor_shared.py:389`), append one line
   showing the effective mode for the focused pane, e.g.
   `Detect:   ≈ stripped (default)` or `Detect:   = raw (override)` —
   spelled-out for the focused pane in the detail view.

### 3. `.aitask-scripts/monitor/minimonitor_app.py`

a. Add a binding to `BINDINGS`:

   ```python
   Binding("d", "cycle_compare_mode", "Detect", show=False),
   ```

b. Add the action handler symmetric to monitor's (same body as 2.b above —
   factor into a small helper if desired).

c. In the card-rendering path (around `minimonitor_app.py:363-378`),
   insert the pseudo-icon for EVERY card, not just overridden ones:

   ```python
   pane_id = snap.pane.pane_id
   mode = self._monitor.get_compare_mode(pane_id) if self._monitor else "stripped"
   is_override = (
       self._monitor is not None
       and self._monitor.is_compare_mode_overridden(pane_id)
   )
   glyph = format_compare_mode_glyph(mode, is_override)
   line1 = f"{dot} {glyph} {name}  {status}"
   ```

   The glyph is one column wide so the narrow ~40-column layout still fits.

d. Wire `compare_mode_default` from `load_monitor_config()` through to the
   `TmuxMonitor(...)` construction in this file too.

e. Update the `#mini-key-hints` Static (around `minimonitor_app.py:146`)
   to include `d:detect` in the hint text so the shortcut is discoverable
   in the compact UI. Also append a one-line legend so the user can decode
   the glyph at-a-glance, e.g.:

   ```
   d:detect (≈ stripped, = raw; bright = override)
   ```

### 3b. `.aitask-scripts/monitor/monitor_shared.py`

Add the shared icon vocabulary used by both TUIs:

```python
COMPARE_MODE_ICONS = {
    "stripped": "≈",
    "raw": "=",
}

def format_compare_mode_glyph(mode: str, is_override: bool) -> str:
    glyph = COMPARE_MODE_ICONS.get(mode, "?")
    color = "yellow" if is_override else "dim"
    return f"[{color}]{glyph}[/]"
```

Add `is_compare_mode_overridden(pane_id) -> bool` to `TmuxMonitor` so
neither TUI has to read the underscore-prefixed override dict directly:

```python
def is_compare_mode_overridden(self, pane_id: str) -> bool:
    return pane_id in self._compare_mode_overrides
```

### 4. `seed/project_config.yaml`

Document the new optional key under `tmux.monitor` with a comment block
describing the two valid values and their tradeoffs. Do **not** set a
non-default value — let the loader default win.

```yaml
tmux:
  monitor:
    # ...existing keys...
    # Idle-detection comparison mode:
    #   stripped (default) — strip ANSI escape codes before comparing pane
    #     content. Required to detect Codex CLI agents as idle (Codex
    #     animates spinner colors even while waiting on user input).
    #   raw — compare full captured bytes including escape codes. Legacy
    #     behavior; only use if a future agent renders idle UI by toggling
    #     escape codes that semantically matter.
    # Per-pane override is available at runtime via the `d` shortcut in
    # `ait monitor` / `ait minimonitor` (cycles default → raw → stripped).
    compare_mode_default: stripped
  # ...
```

Setting it explicitly in the seed (even at the default value) makes the
key discoverable to users who read the seed config — keeping with the
project's pattern of self-documenting `tmux.git_tui` etc.

### 5. `aitasks/metadata/project_config.yaml`

Same single key, with a brief comment, so this repo's own config matches
the seed and is discoverable. Defaults remain `stripped`.

## Tests

### New file: `tests/test_idle_compare_modes.py`

Python unit test exercising `TmuxMonitor._finalize_capture` directly (no
tmux needed). Four cases:

1. **Default (stripped) mode ignores animated color codes.** Two captures
   with identical visible text but different SGR colors — assert `is_idle`
   becomes True after `idle_threshold` elapses.
2. **Raw mode preserves legacy behavior.** Same two captures with raw mode
   active for the pane — assert `is_idle` stays False (animated colors
   keep resetting the timer).
3. **Visible text change always resets idle (in either mode).** Assert
   that with stripped mode, two captures whose visible text differs reset
   `is_idle` to False.
4. **`cycle_compare_mode` cycles through default → raw → stripped →
   default and clears stored last-content on each transition.** Assert
   the returned `(mode, is_default)` tuple sequence and that the next
   `_finalize_capture` after a cycle does not register a spurious
   "changed" event from a stale stored value of the wrong form.

Sketch:

```python
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))

from monitor.tmux_monitor import (
    TmuxMonitor, TmuxPaneInfo, PaneCategory,
    COMPARE_MODE_RAW, COMPARE_MODE_STRIPPED,
)

def make_pane(pane_id="%test"):
    return TmuxPaneInfo(
        window_index="1", window_name="agent-pick-715", pane_index="0",
        pane_id=pane_id, pane_pid=1, current_command="codex",
        width=80, height=24, category=PaneCategory.AGENT,
        session_name="aitasks",
    )

def test_default_mode_ignores_animated_color():
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    a = "\x1b[38;2;156;164;198m• Running\x1b[0m\nWait...\n"
    b = "\x1b[38;2;124;130;159m• Running\x1b[0m\nWait...\n"
    mon._finalize_capture(pane, a)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, b)
    assert snap.is_idle, "animated color codes must not reset idle timer in stripped mode"

def test_raw_mode_preserves_legacy_behavior():
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon.set_compare_mode(pane.pane_id, COMPARE_MODE_RAW)
    a = "\x1b[38;2;156;164;198m• Running\x1b[0m\nWait...\n"
    b = "\x1b[38;2;124;130;159m• Running\x1b[0m\nWait...\n"
    mon._finalize_capture(pane, a)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, b)
    assert not snap.is_idle, "raw mode must keep counting animated color changes as activity"

def test_visible_text_change_resets_idle():
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, "\x1b[31mLine A\x1b[0m\n")
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, "\x1b[31mLine B\x1b[0m\n")
    assert not snap.is_idle, "visible text change must reset idle timer"

def test_cycle_compare_mode_sequence():
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    # Seed last_content so we can verify it gets cleared on each cycle.
    mon._finalize_capture(pane, "\x1b[31mhello\x1b[0m\n")
    assert pane.pane_id in mon._last_content

    # default → raw
    mode, is_default = mon.cycle_compare_mode(pane.pane_id)
    assert mode == COMPARE_MODE_RAW and not is_default
    assert pane.pane_id not in mon._last_content

    # raw → stripped
    mon._finalize_capture(pane, "\x1b[31mhello\x1b[0m\n")
    mode, is_default = mon.cycle_compare_mode(pane.pane_id)
    assert mode == COMPARE_MODE_STRIPPED and not is_default

    # stripped → default
    mon._finalize_capture(pane, "\x1b[31mhello\x1b[0m\n")
    mode, is_default = mon.cycle_compare_mode(pane.pane_id)
    assert mode == COMPARE_MODE_STRIPPED and is_default  # default IS stripped

if __name__ == "__main__":
    test_default_mode_ignores_animated_color()
    test_raw_mode_preserves_legacy_behavior()
    test_visible_text_change_resets_idle()
    test_cycle_compare_mode_sequence()
    print("PASS")
```

Invocation:

```bash
python3 tests/test_idle_compare_modes.py
```

### Manual verification (post-implementation)

1. Park `agent-pick-713` (or any Codex agent) on a confirmation prompt.
   Open `ait minimonitor` — within ~5s the pane flips to idle (default
   `stripped` mode).
2. Open `ait monitor`, focus the same pane, press `d` — pane should flip
   to `raw` mode and immediately register as not-idle (animated colors
   keep resetting the timer). Notification "Idle detect mode for this
   pane: raw" appears.
3. Press `d` again — `stripped (override)`; idle within ~5s.
4. Press `d` once more — `stripped (default)`; same behavior.
5. Detail header shows the effective mode while a pane is focused.
6. Every agent card (in BOTH `ait monitor` and `ait minimonitor`) shows a
   single-character mode glyph next to the status: `≈` (stripped) or
   `=` (raw), dim when following the global default and yellow when the
   pane has a per-pane override.
7. Regression: a Claude/Gemini agent actively streaming output stays
   marked active in both monitor and minimonitor.

## Files changed

- `.aitask-scripts/monitor/tmux_monitor.py` — `re` import, ANSI regex +
  helper, mode constants, four new `TmuxMonitor` methods
  (`get_compare_mode`, `set_compare_mode`, `cycle_compare_mode`,
  `is_compare_mode_overridden`), modified `_finalize_capture` and
  `_clean_stale`, extended `load_monitor_config`.
- `.aitask-scripts/monitor/monitor_shared.py` — `COMPARE_MODE_ICONS` map
  and `format_compare_mode_glyph()` helper used by both TUIs.
- `.aitask-scripts/monitor/monitor_app.py` — new `d` binding, new action,
  agent-card glyph in `_format_agent_card_text`, detail-row showing
  effective mode for focused pane, plumb `compare_mode_default` from
  `load_monitor_config` to `TmuxMonitor`.
- `.aitask-scripts/monitor/minimonitor_app.py` — new `d` binding, new
  action, agent-card glyph rendered for every pane, plumb
  `compare_mode_default`, update `#mini-key-hints` text with shortcut +
  legend.
- `seed/project_config.yaml` — document new `tmux.monitor.compare_mode_default`
  key with comment.
- `aitasks/metadata/project_config.yaml` — same key with brief comment so
  this repo matches the seed.
- `tests/test_idle_compare_modes.py` — new unit test, four cases.

## Notes for the implementation step

- Do **not** change the `-e` flag in `_capture_args` — display still needs it.
- Do **not** introduce a second tmux call per pane.
- The strip regex must NOT be applied to `PaneSnapshot.content`; that field
  feeds `_ansi_to_rich_text` and must remain colored.
- `set_compare_mode` and `cycle_compare_mode` BOTH clear the stored
  `_last_content` for the pane — this is the load-bearing detail that
  prevents one tick of false "changed" right after a mode transition.
- Per-pane overrides are in-memory only (no persistence across runs); the
  global default IS configurable in `project_config.yaml`.
- No public API breakage: existing `TmuxMonitor(...)` constructions
  without the new kwarg keep working (the parameter has a default).

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Two compare modes
  (`stripped` / `raw`), default `stripped`, per-pane in-memory override
  cycled `default → raw → stripped → default` via `d` shortcut in both
  `ait monitor` and `ait minimonitor`. Mode glyph (`≈` / `=`) appears on
  every agent card, dim when following the global default and yellow when
  the pane has an override. Configurable global default via
  `tmux.monitor.compare_mode_default` in `project_config.yaml`.
- **Deviations from plan:**
  1. Did **not** add a separate `Detect:` row to a per-pane detail view —
     the full `MonitorApp` does not have a stable preview-detail strip
     (the kill-confirm dialog is the only place with a `Status:` line, and
     adding the Detect row only to that ephemeral dialog would have been
     low-value). The glyph on every agent card plus the post-`d`
     notification cover the same need with less surface area.
  2. Marked the `tmux.monitor` block in `seed/project_config.yaml` as a
     commented-out example rather than an active block. The seed previously
     had no `tmux.monitor` block at all (other monitor keys live only in
     the runtime config), so adding only the new key while leaving the
     others undocumented in the seed would have been misleading. The
     comment block is documentation; the runtime loader default
     (`stripped`) applies on fresh installs.
  3. Test file added one extra case beyond the planned four
     (`test_set_compare_mode_clears_last_content`) to pin the
     "clear last_content on mode change" invariant directly. Pure
     addition, no test removed.
- **Issues encountered:**
  - `tests/test_multi_session_minimonitor.sh` constructs `MiniMonitorApp`
    via `__new__()` (bypassing `__init__`) and manually sets a subset of
    instance attributes. Adding the new `_compare_mode_default` ctor
    parameter required the same attribute on the test fixture, plus the
    fixture's `SimpleNamespace(_monitor=...)` mock had to gain
    `get_compare_mode` and `is_compare_mode_overridden` lambdas to satisfy
    the new `_rebuild_pane_list` calls. Updated in-place — same pattern
    the file already uses for other constructor-aligned attributes.
- **Key decisions:**
  - **Strip ANSI for comparison only, keep `-e` in capture.** Display
    path (`_ansi_to_rich_text`) needs the escape codes; running
    `tmux capture-pane` twice (once with `-e`, once without) would double
    the per-tick tmux-call overhead. Stripping in `_finalize_capture`
    achieves the same outcome with no extra tmux calls.
  - **Cycle order `default → raw → stripped → default`.** Putting `raw`
    first after the default lets a user toggle "show me byte-equal idle
    detection" with one keypress (the most common diagnostic), then a
    second press locks in `stripped` as an explicit override (visually
    different from the default — yellow vs dim glyph), and a third press
    returns to the default.
  - **Glyph `≈` for stripped, `=` for raw.** Semantic match: `≈` (fuzzy
    match) for ANSI-stripped equality, `=` (strict equal) for raw
    byte-equal. Both are width-1 in monospace fonts so the narrow
    minimonitor layout is unaffected.
  - **In-memory override only.** Per-pane mode is a runtime/diagnostic
    affordance; persisting overrides across runs would require a tiny
    state file and stale-pane-id cleanup logic for negligible benefit.
    The global default IS configurable in `project_config.yaml` for users
    who want a different baseline.
- **Upstream defects identified:** None.

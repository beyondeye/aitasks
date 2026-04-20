---
Task: t598_more_zoom_levels_in_ait_monitor.md
Base branch: main
plan_verified: []
---

# Plan: Add agent-list-sized XL zoom levels to `ait monitor`

## Context

In `ait monitor`, pressing `z` cycles the preview pane through 4 size presets: S (12-line preview) → M (24) → L (40) → XL (fullscreen). With XL on a typical terminal, the pane-list (agent list) shrinks to only ~3 agents visible.

The user wants to trade some preview space for more agent-list rows. Instead of adding a single new preset, the user wants to restructure the "XL zone" so that multiple XL_N presets are parameterized by **how many agents the pane-list fits** (rather than by preview height). S / M / L remain preview-sized; the single current XL/fullscreen becomes three modes XL_9 / XL_6 / XL_3, computed at apply time from the terminal height.

New cycle: `S → M → L → XL_9 → XL_6 → XL_3 → (back to S)` — cycle order goes from most agents visible (S, many) through preview-sized modes to agent-list-sized modes ending at XL_3 (the old "fullscreen" behavior, now explicit about reserving 3 agents).

## Changes

### 1. `.aitask-scripts/monitor/monitor_app.py` — zoom presets and sizing

**Lines 60-70 — replace the `PREVIEW_SIZES` table.** Introduce an `agents:N` sentinel that is resolved dynamically in `_apply_preview_size()`. Keep `PREVIEW_FULLSCREEN_RESERVE` removed (no longer needed — replaced by the explicit agent-count formula).

```python
# Preview panel size presets: (section_max_height, preview_max_height, label)
#
# Numeric heights are applied as-is. String heights of the form
# "agents:N" mean: size the pane-list to fit N agent cards and give the
# rest of the terminal to the preview section (resolved at apply time).
PREVIEW_AGENT_CARD_LINES = 2        # worst-case lines per PaneCard (status row + task title row)
PREVIEW_LAYOUT_FIXED_LINES = 3       # header + session-bar + footer
PREVIEW_MIN_SECTION_H = 4            # minimum section height so preview is never fully hidden
PREVIEW_MIN_PREVIEW_H = 2            # minimum inner scroll height

PREVIEW_SIZES = [
    (12, 10, "S"),
    (24, 22, "M"),
    (40, 38, "L"),
    ("agents:9", "agents:9", "XL_9"),
    ("agents:6", "agents:6", "XL_6"),
    ("agents:3", "agents:3", "XL_3"),
]
PREVIEW_DEFAULT_SIZE = 1  # Medium
```

Delete the `PREVIEW_FULLSCREEN_RESERVE = 10` constant at line 63 — it is replaced by the per-mode reserve implied by `agents:N`.

**Lines 1221-1245 — generalize `_apply_preview_size()`.** Replace the `if section_h == "fullscreen":` branch with an `agents:N` branch:

```python
def _apply_preview_size(self) -> None:
    """Apply the current preview size index to the preview widgets."""
    section_h, preview_h, label = PREVIEW_SIZES[self._preview_size_idx]

    if isinstance(section_h, str) and section_h.startswith("agents:"):
        n_agents = int(section_h.split(":", 1)[1])
        screen_h = self.size.height or 40
        reserve = PREVIEW_LAYOUT_FIXED_LINES + n_agents * PREVIEW_AGENT_CARD_LINES
        section_h = max(PREVIEW_MIN_SECTION_H, screen_h - reserve)
        preview_h = max(PREVIEW_MIN_PREVIEW_H, section_h - 2)

    try:
        section = self.query_one("#content-section")
        scroll = self.query_one("#preview-scroll", ScrollableContainer)
    except Exception:
        return

    section.styles.max_height = section_h
    scroll.styles.max_height = preview_h
    self.notify(f"Preview size: {label}")
    self._update_content_preview()
```

**Lines 1272-1276 — update `on_resize()`.** The current guard only re-applies on resize for the `"fullscreen"` spec; broaden it to any dynamic (`agents:`) spec:

```python
def on_resize(self, event) -> None:
    """Recompute dynamic sizing specs (agents:N) when the terminal is resized."""
    section_spec, _, _ = PREVIEW_SIZES[self._preview_size_idx]
    if isinstance(section_spec, str) and section_spec.startswith("agents:"):
        self._apply_preview_size()
```

No other call-sites reference `PREVIEW_FULLSCREEN_RESERVE` or the `"fullscreen"` literal (verified by grep).

### 2. `website/content/docs/tuis/monitor/reference.md` — Preview Size Presets table

**Lines 71-81.** Replace the 3-row outdated table with the 6 current presets. Describe XL_N semantics explicitly:

```markdown
### Preview Size Presets

Pressing `z` cycles through six preview size presets:

| Label | Section max height | Preview max height | Notes |
|-------|-------------------|--------------------|-------|
| `S` | 12 | 10 | Largest pane-list, smallest preview |
| `M` (default) | 24 | 22 | Balanced |
| `L` | 40 | 38 | Large preview |
| `XL_9` | auto | auto | Sized so the pane-list fits 9 agents; preview takes the rest |
| `XL_6` | auto | auto | Sized so the pane-list fits 6 agents; preview takes the rest |
| `XL_3` | auto | auto | Sized so the pane-list fits 3 agents; preview takes the rest (largest preview) |

The `XL_N` presets are **terminal-aware**: they compute the section height from the current terminal height so the pane-list always has room for N agent cards (2 lines each). Resizing the terminal while in an `XL_N` preset re-applies the sizing. A notification shows the new size label when you cycle.
```

### 3. `website/content/docs/tuis/monitor/how-to.md` — Cycle the Preview Size

**Lines 128-130.** Rewrite to describe six presets:

```markdown
### How to Cycle the Preview Size

Press **z** to cycle the preview zone through six size presets — **S**, **M**, **L**, **XL_9**, **XL_6**, **XL_3** — for quickly adjusting how much pane output vs. agent-list you see at once. The `S/M/L` presets set a fixed preview height; the `XL_N` presets set the pane-list to fit N agents and give the rest of the screen to the preview. A notification shows the new size label. The default is **M**.
```

## Verification

1. **Static checks.** Run `shellcheck .aitask-scripts/aitask_*.sh` (should still pass — no shell changes). Optional: `python3 -m py_compile .aitask-scripts/monitor/monitor_app.py` to catch syntax errors.

2. **Interactive TUI verification** (the core of this task — cannot be automated):
   - Start a tmux session with several agent windows (or mock with several `agent-*` windows): `tmux new-session -d -s aitasks`, then create 12+ windows with names like `agent-t598-foo`, `agent-t598-bar`, etc.
   - Inside the tmux session, run `ait monitor`.
   - Press `z` six times and confirm the notification cycles through `S → M → L → XL_9 → XL_6 → XL_3 → S`.
   - At `XL_9`: confirm the pane-list shows 9 agent cards (scrollbar may appear if cards are taller than expected; that is fine).
   - At `XL_6`: confirm the pane-list shows 6 agent cards.
   - At `XL_3`: confirm the pane-list shows ~3 agent cards (matches the previous fullscreen XL behavior).
   - Resize the terminal while in `XL_6` and confirm the preview grows/shrinks to maintain 6 agents visible.

3. **Docs preview.** `cd website && ./serve.sh`, then load the monitor reference and how-to pages; confirm the updated tables render correctly.

## Post-Implementation

Follow **Step 9 (Post-Implementation)** of the task-workflow: user review → commit → push → archive.

## Files touched

- `.aitask-scripts/monitor/monitor_app.py` (3 localized edits)
- `website/content/docs/tuis/monitor/reference.md`
- `website/content/docs/tuis/monitor/how-to.md`

No new files, no test additions (no existing zoom tests; behavior is interactive-only).

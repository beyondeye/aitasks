---
Task: t1996_compact_monitor_elapsed_badge.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1996 — Compact the monitor/minimonitor elapsed badge

## Context

Every agent card in `ait monitor` and `ait minimonitor` shows a state badge with
an elapsed counter (`PROMPT 412s`, `DONE 412s`, `IDLE 412s`). It is always in
seconds and unbounded, so large values are unreadable (`IDLE 18734s`) and the
badge grows without limit — in minimonitor (~38 usable columns) it wraps the
card's first line. Goal: cap the number at **4 characters** by switching units
s → m → h (rounded down), so the longest badge is `PROMPT 999s` / `PROMPT 240m`
/ `PROMPT 999h` (11 cells).

Current-branch mode (profile `fast`): no worktree, work on `main`.

## Implementation

### 1. Helper + call sites — `.aitask-scripts/monitor/monitor_shared.py`

`format_pane_status()` (line 2146) is the only place that builds the badge; its
three branches do `f"... {int(snap.idle_seconds)}s"`. Add a pure helper
immediately above it and use it in all three branches:

```python
def format_elapsed_compact(seconds: float) -> str:
    """Elapsed time in at most 4 characters, rounded down (t1996).

    ``0s``…``999s``, then whole minutes up to ``240m``, then whole hours,
    capped at ``999h``. Keeps the PROMPT/DONE/IDLE badge bounded (at most
    ``PROMPT 999s``, 11 cells). Not :func:`format_stale_duration`, which is
    the ``2m05s``-style banner formatter.
    """
    s = int(max(0.0, seconds))
    if s <= 999:
        return f"{s}s"
    m = s // 60
    if m <= 240:
        return f"{m}m"
    return f"{min(s // 3600, 999)}h"
```

```python
    if getattr(snap, "awaiting_input", False):
        return f"[{STATE_STYLE_PROMPT}]PROMPT {format_elapsed_compact(snap.idle_seconds)}[/]"
    if completed:
        return f"[{STATE_STYLE_DONE}]DONE {format_elapsed_compact(snap.idle_seconds)}[/]"
    if snap.is_idle:
        return f"[{STATE_STYLE_IDLE}]IDLE {format_elapsed_compact(snap.idle_seconds)}[/]"
```

Callers that pick it up automatically (no edits): minimonitor
`_agent_card_text` (`minimonitor_app.py:2355`), monitor
`_format_agent_card_text` (`monitor_app.py:1780`), kill-confirm dialog
(`monitor_shared.py:2688`).

**Not touched:** `format_stale_duration()` (line 2020, pinned by
`test_shadow_seam.py` / `test_minimonitor_concern_action.py`); the restart
dialog's `Terminal: idle for Ns` (`monitor_app.py:356`); applink's raw
`idle_seconds` wire field.

### 2. Comment — `.aitask-scripts/monitor/minimonitor_app.py` ~line 2371

Rewrite the name-cap comment's worst-case row: the status is now bounded —
at most `PROMPT 999s` (11 cells) — instead of citing `PROMPT 123s` as if it
were the open-ended worst case.

### 3. Docs

**What the number means — state it exactly.** `idle_seconds` is
`now - last_change` (`monitor_core.py:2853-2854`), where `_last_change_time`
moves only when the pane's *compared content* differs from the previous capture
(the first capture counts as a change). It is independent of the badge's state:
task completion never resets it, so a quiet pane whose task is just archived can
read `DONE 83m` immediately. The docs must therefore describe `<t>` as **time
since the monitor last saw the pane's output change** — never "how long the pane
has been in that state" or "time since it finished".

- `website/content/docs/tuis/monitor/how-to.md` lines 47–49: keep the three
  table rows (`PROMPT <n>s` etc. → `PROMPT <t>` / `DONE <t>` / `IDLE <t>`) and
  add after the table: `<t>` is the time since the monitor last saw the pane's
  output change — not how long the pane has been in that state, so a quiet pane
  whose task has just been archived can already read `DONE 83m`. It is shown in
  at most four characters: seconds up to `999s`, then whole minutes up to
  `240m`, then whole hours (`4h` … capped at `999h`), always rounded down.
- `website/content/docs/tuis/minimonitor/how-to.md` line 48: same `<t>`
  substitution in the "matching label" bullet plus a short clause with the same
  meaning (time since the pane's output last changed) and the same unit switch.
- The helper's docstring says "elapsed time", with no claim about state
  duration, and the `minimonitor_app.py` comment speaks only of width. The
  existing timing behaviour does not change.
- Run `python3 check_links.py --build` in `website/`.

### 4. Tests — new `tests/test_monitor_elapsed_badge.py`

Same import scaffold as `tests/test_monitor_completed_status.py` (sys.path
inserts, `TMUX` scrub not needed — no app constructed). Two classes:

- `FormatElapsedCompactTests` — boundaries: `0`→`0s`, `-5`→`0s`, `999.9`→`999s`,
  `1000`→`16m`, `240*60+59`→`240m`, `241*60`→`4h`, `999*3600+3599`→`999h`,
  `1500*3600`→`999h`; plus a sweep (dense near each threshold + a geometric
  spread up to ~10⁷ s) asserting `len(result) <= 4` and that the result
  matches `^\d+[smh]$`.
- `FormatPaneStatusCompactTests` — one value past each threshold through
  `format_pane_status`: PROMPT at 5000 s → `[STATE_STYLE_PROMPT]PROMPT 83m[/]`,
  DONE at 241*60 → `DONE 4h`, IDLE at 999 s → `IDLE 999s`; colours asserted via
  the `STATE_STYLE_*` constants (never literals), as the existing suite does.
  A negative control: IDLE at 18734 s must not contain `18734`.

Existing tests pinning `412s` (`test_monitor_completed_status.py`,
`test_markup_colour_contract.py`, `test_minimonitor_gate_phase_row.py`) stay
unchanged since 412 < 1000.

### 5. After commit — note to t1351

`./ait note 1351 --from 1996 --text "..."`: the minimonitor status badge is
now bounded at 11 cells (`PROMPT 999s` / `PROMPT 240m` / `PROMPT 999h`), so
t1351's worst-case row width should use 11 cells for the status rather than
`PROMPT 123s` as an open-ended example.

### Step 9 reference

Post-implementation per task-workflow Step 9 (current-branch mode: no merge;
gates run via `./ait gates run 1996`, then archive).

## Verification

```bash
python3 tests/test_monitor_elapsed_badge.py
python3 tests/test_monitor_completed_status.py
python3 tests/test_markup_colour_contract.py
python3 tests/test_minimonitor_gate_phase_row.py
python3 tests/test_shadow_seam.py
python3 tests/test_minimonitor_concern_action.py
(cd website && python3 check_links.py --build)
```

Red proof: write the test file before editing `monitor_shared.py` and run it
once — `FormatPaneStatusCompactTests` must fail on the pre-change code (and the
helper tests fail on the missing import), then pass after step 1.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_monitor, aitask_monitormini, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 08:48
updated_at: 2026-10-15 09:09
---

## Problem

In `ait minimonitor` and `ait monitor`, every agent row shows a state badge with
an elapsed-time counter: `PROMPT 412s`, `DONE 412s`, `IDLE 412s`. The counter is
always in seconds and has no upper bound, so:

- large values are unreadable (`IDLE 18734s`);
- the badge grows without limit, and in minimonitor (~38 usable columns) it pushes
  the first line of the agent card onto a second line.

## Goal

Cap the formatted elapsed time at **4 characters** by switching units as it grows.
All values are rounded down:

| elapsed | shown as | range |
|---|---|---|
| 0 – 999 s | `<n>s` | `0s` … `999s` |
| 1000 s – 240 min (whole minutes ≤ 240) | `<n>m` | `16m` … `240m` |
| more than 240 min | `<n>h` | `4h` … `999h` |
| 999 h or more | `999h` (capped) | |

Rule, with `s = int(max(0, seconds))`: `s <= 999` → `f"{s}s"`; else `m = s // 60`,
and `m <= 240` → `f"{m}m"`; else `h = min(s // 3600, 999)` → `f"{h}h"`.
(1000 s = `16m`; 240 min 59 s = `240m`; 241 min = `4h`.)

The longest badge becomes `PROMPT 999s` / `PROMPT 240m` / `PROMPT 999h`.

## Where

- `.aitask-scripts/monitor/monitor_shared.py` — `format_pane_status()` (~line 2146)
  is the only place that builds the badge. It currently does
  `f"... {int(snap.idle_seconds)}s"` in three branches (PROMPT / DONE / IDLE).
  Add a pure helper next to it (e.g. `format_elapsed_compact(seconds) -> str`)
  and use it in all three branches.
  - Callers that pick this up automatically: the minimonitor agent card
    (`minimonitor_app.py` `_agent_card_text`, ~line 2355), the full monitor card
    (`monitor_app.py` `_format_agent_card_text`, ~line 1780), and the kill-confirm
    dialog (`monitor_shared.py` ~line 2688). Using the same format in all of them
    is intended.
- **Do not change** `format_stale_duration()` (same file, ~line 2020). It is the
  `2m05s`-style formatter used by the shadow-staleness banner and is pinned by
  `tests/test_shadow_seam.py` and `tests/test_minimonitor_concern_action.py`.
- Out of scope: the restart dialog's `Terminal: idle for Ns` line
  (`monitor_app.py` ~line 356, a dialog rather than a list row), and applink's raw
  `idle_seconds` wire field (`applink/pusher.py`, `applink/router.py`). The mobile
  client formats that number itself.
- `minimonitor_app.py` ~line 2371: the comment explaining the name cap gives
  `PROMPT 123s` as the worst-case status. Update it so it says the status is now
  bounded (at most `PROMPT 999s`, 11 cells).

## Docs

The website pages describe the badge as `<n>s`. Update them to describe the
unit switch (s → m → h, max 4 characters):

- `website/content/docs/tuis/monitor/how-to.md` lines ~48–49 (table rows
  `DONE <n>s`, `IDLE <n>s`; check for a `PROMPT <n>s` row nearby)
- `website/content/docs/tuis/minimonitor/how-to.md` line ~48

Run `python3 check_links.py --build` (in `website/`) after editing, as CLAUDE.md
requires.

## Tests

- Unit tests for the helper at every boundary: `0`, negative → `0s`, `999.9` →
  `999s`, `1000` → `16m`, `240*60+59` → `240m`, `241*60` → `4h`,
  `999*3600+3599` → `999h`, `1500*3600` → `999h`. Also assert
  `len(result) <= 4` across a sweep of values.
- A `format_pane_status` test for at least one value past each threshold (for
  example PROMPT at 5000 s → `PROMPT 83m`). Existing tests that pin `412s`
  (`tests/test_monitor_completed_status.py`, `tests/test_markup_colour_contract.py`,
  `tests/test_minimonitor_gate_phase_row.py`) should still pass unchanged, since
  412 < 1000.

## Related (not folded)

t1351 (minimonitor row-width audit) uses `PROMPT 123s` as the status width in its
worst-case row. This task bounds that width, so after it lands send t1351 a note
(`./ait note 1351 --from <this task> ...`) saying the status badge is now at most
11 cells (`PROMPT 999s`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T06:09:05Z status=pass attempt=1 type=human

---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Postponed
labels: [aitask_monitormini, tmux, tui, monitor]
gates: [risk_evaluated]
created_at: 2026-07-02 17:49
updated_at: 2026-07-03 10:19
boardidx: 260
---

Several already-running `ait minimonitor` instances can report an agent pane as `PROMPT` after the checked-in prompt-detection fix says it is `IDLE`. The live diagnosis on 2026-07-02 found stale minimonitors in the `aitasks` tmux session still reporting `agent-pick-1114 PROMPT`, while the current monitor code and the full `ait monitor` reported `agent-pick-1114 IDLE`.

## Live Evidence

- `agent-pick-1114` pane `%313` was an idle Codex pane whose live bottom lines did not contain an approval prompt.
- The captured scrollback did contain stale prompt-pattern text higher up, including `Yes, proceed (y)` from earlier conversation output.
- Running the latest code path directly with `TmuxMonitor(session="aitasks")` classified `agent-pick-1114` as `IDLE`, not `PROMPT`.
- `python3 tests/test_prompt_detection.py` passed all 7 tests, including `test_old_prompt_text_in_scrollback_is_not_awaiting`.
- The main full monitor window `%328` reported `10:agent-pick-1114` as `IDLE`.
- These minimonitor panes were sampled and reported `agent-pick-1114 PROMPT`: `%24` (`git` side pane), `%226` (`agent-pick-635_29`), `%285` (`agent-pick-1112`), `%297` (`agent-pick-1061`), `%308` (`agent-pick-1111_2`), and `%326` (`agent-raw-1`).
- These sampled minimonitor panes did not show the same false prompt: `%314` (`agent-pick-1114`) and `%336` (`agent-raw-2`); `%336` explicitly showed `agent-pick-1114 IDLE`.

## Problem To Solve

The current code appears to handle stale scrollback correctly, but older already-running minimonitor processes can continue using the previous prompt-detection behavior until restarted. That creates contradictory monitor state in one tmux session after a monitor/prompt-detection code update.

Investigate and implement a lightweight way to detect or mitigate stale monitor/minimonitor code drift. Possible directions:

- Surface a version/revision mismatch in monitor and minimonitor TUIs when the running process predates the checked-out monitor code.
- Provide a clear restart hint/action for stale minimonitor instances after monitor code changes.
- Consider whether the TUI switcher or agent companion launch path should reuse/restart stale minimonitors when launching a new companion.
- Keep the already-fixed prompt matching behavior: only the live bottom prompt window should drive `awaiting_input`, not stale scrollback.

## Acceptance Criteria

- A stale running minimonitor using outdated monitor code can be identified or recovered without needing to manually compare captures across panes.
- Current prompt detection still reports panes with stale prompt text outside the live bottom window as not awaiting input.
- Full monitor and minimonitor behavior stays consistent for live prompt, idle, and active states.
- Add focused tests for any new revision/restart/version-drift logic, plus keep `tests/test_prompt_detection.py` passing.

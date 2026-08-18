---
Task: t1562_manual_verification_tighten_claude_proceed_pattern_to_whole_.md
Worktree: current branch
Branch: main
Base branch: main
---

# Plan - t1562: Manual verification of t1557 (auto-executed)

Autonomous auto-verification of the five checklist items. Every item was
exercised against a **live Claude Code 2.1.234 (Haiku 4.5) session** running in
a real pane on a private tmux socket (`tmux -L av1562`), driven to a genuine
Bash tool-permission dialog. No fixture replay: the frames classified below
were captured from that pane with the monitor's own capture arguments
(`capture-pane -p -e -S -200`).

## Harness

Three scratch scripts under the session scratchpad, all reading production
seams rather than reimplementing them:

- `probe_live.py` / `frames.py` — capture a labelled frame from the live pane
  (`agent_key_from_pane` for the agent key, `pane_width/height` and
  `history_size` for geometry), classify it with
  `monitor_core.classify_content` + `prompt_patterns.all_patterns()`, and
  compare two frames with `review_loop.classify_followed_change` using exactly
  the argument shape `minimonitor_app` passes at line 2776.
- `negctrl.py` — **negative control**: replays the *same* captured frames with
  the `claude_proceed` pattern restored to its pre-t1557 substring form
  (`re.compile(r"Do you want to proceed\?")`), everything else untouched.

## Execution Log

### Item 1 — short-height regime, `ait monitor` flags `claude_proceed`

- Approach: live TUI + production classify seam.
- Action: session created at 120x9; the real dialog rendered with the option
  list truncated to the selected row. `ait monitor` was launched in a second
  window of the same server (`AITASKS_TMUX_SOCKET=av1562`); the agent window was
  renamed to the `agent-` prefix so `classify_pane` categorises it as
  `PaneCategory.AGENT` (the framework categorises by *window name*, not by
  `pane_current_command`).
- Output: monitor header `1 awaiting`; pane row `☆ ● ≈ 1:agent-probe (1)
  PROMPT 38s`. Production classify: `awaiting_input=True
  kind='claude_proceed'`, `agent_key='claude'`, `scoped=True`. The question
  rendered at detection-window index **-5**, inside `_PROMPT_DETECTION_TAIL_LINES`
  (6) — the regime the pattern exists for, unchanged by the tightening.
- Verdict: **pass**

### Item 2 — typed amend text fires no auto-recheck round

- Approach: live keystroke drive + review-loop classification.
- Action: same dialog resized to 120x14 (question moves to -7, so the reported
  kind is `claude_help_bar`). `Tab` (option 1 becomes the amend row), then
  `Do you want to proceed?` typed in two chunks, capturing a frame per chunk.
- Output: the typed copy lands **inside** the detection window (index -6) as
  ` ❯ 1. Yes, Do you want to proceed?` — the row prefix is what the whole-line
  anchor rejects. Kind stayed `claude_help_bar` on every frame;
  `classify_followed_change` returned `selection_only` on all three transitions.
- Negative control: with the pre-t1557 substring pattern the same frames flip
  `claude_help_bar` -> `claude_proceed` at the moment the phrase completes, and
  the transition classifies **`work`** — the spurious auto-recheck round the
  task was raised for. The fix, not the fixture, is what prevents it.
- Verdict: **pass**

### Item 3 — cursor moves do not flip the reported kind

- Approach: same live dialog, text still typed into option 1.
- Action: `Down`, `Down`, `Up` (rows 1 -> 2 -> 3 -> 2), a frame per move.
- Output: kind stayed `claude_help_bar` on all four frames; all three
  transitions `selection_only`; the `ait monitor` badge stayed `PROMPT`
  throughout. Under the pre-t1557 pattern every one of these frames reports the
  wrong kind (`claude_proceed`) instead.
- Verdict: **pass**

### Item 4 — `monitor/prompt_patterns.py` end-to-end in tmux

- Covered by items 1-3: the module was driven through the real capture path at
  both geometries and reported the two distinct kinds the docs predict
  (`claude_proceed` at 9 rows, `claude_help_bar` at 14).
- `python3 tests/test_prompt_detection.py` — `PASS: all 22 tests passed`.
- Verdict: **pass**

### Item 5 — `monitor/review_loop.py` end-to-end in tmux

- Covered by items 2-3: `classify_followed_change` was driven over six live
  frames with real `history_size` and pane geometry, across both the typing and
  the cursor-move sequences.
- `python3 tests/test_review_loop.py` — `Ran 145 tests ... OK`.
- Verdict: **pass**

## Notes

- The amend row always renders as `<n>. Yes, <typed text>`, so a typed copy of
  the phrase can never hold its whole line unless it wraps — which is exactly
  the "wrapped amend" limit recorded at the pattern and accepted there.
- `ait monitor` reads the socket named by `AITASKS_TMUX_SOCKET` (default `ait`),
  not the socket it happens to be running inside; without that env var the
  probe monitor scanned the user's real agent sessions instead.

## Cleanup

- `tmux -L av1562 kill-server` (agent + monitor windows).
- `/tmp/av1562_probe.txt` — never created; the dialog was cancelled, not answered.
- `/tmp/av1562_monitor.log`, scratchpad `av1562/` dir and probe scripts removed.

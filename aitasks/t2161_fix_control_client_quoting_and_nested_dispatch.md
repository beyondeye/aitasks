---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor, tmux]
gates: [risk_evaluated]
followup_kind: upstream_defect
created_at: 2026-10-28 17:56
updated_at: 2026-10-28 17:56
---

## Origin

Spawned from aitasks_go t17_2 (the Go port of the tmux control-mode client) during Step 8b review. The Go client fixed both defects; the Python source of truth still has them.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:1425` — `_quote_arg` double-quotes control-mode args, so tmux expands `$VAR` and `~` in them, and a raw LF splits the command line. The result is argument corruption, plus reply misattribution once the extra line gets its own `%error` block.
- `.aitask-scripts/lib/tmux_exec.py:562` — `run_via_control` (and `run_async_via_control`) send every non-pane-creating argv over the control client:
  - Nested commands (`if-shell`, `run-shell -C`, `source-file`) answer in a 2nd reply block. That block is lost, or misattributed to the next pending caller.
  - `;`-separated argv sequences get a literal-`;` parse error (rc 1), so there is no fallback.

## Diagnostic context

Measured on tmux 3.8, on a private server, while porting:
- **Lexer:** only single quotes suppress `$VAR`, `~` and `\` expansion. Control mode reads its input one line at a time, so a raw LF ends the command. Probe: `set-option -g @p "$HOME"` over `-C` stores the expanded home path; argv stores `$HOME`.
- **Nested commands:** `if-shell -F 1 'display-message -p inner'` over `-C` emits `%begin…%end` (empty) for the if-shell, then a **separate** `%begin…inner…%end` block. `run-shell 'echo x'` (no `-C`) prints `x` outside any block. `confirm-before` never runs its command. `RunViaControl` returned `(0,"")` where `Run` returned `(0,"inner\n")`.
- **argv `;` rule:** tmux's argv parser treats any argument ending in `;` as a command separator (`\;` = a literal). Over the control line, a quoted `;` is literal data, so `display-message -p first ; display-message -p second` → `parse error: … too many arguments`.

## Suggested fix

Mirror the Go fix (aitasks_go `goengines/tmux/control.go`):
- Encode each arg as `'…'`, with `'` → `'\''`, LF → `'\n'` and CR → `'\r'`; this is verified live, byte-identical to argv.
- Make control eligibility a fail-closed allowlist of full verb names that answer in exactly one block and never run a nested command/shell. Also exclude pane creators and any argv with an arg ending in `;`. Everything else → subprocess.
- Add live tests comparing control vs subprocess for `$HOME`, `~`, LF, nested output and failure, and a `;` sequence, with a pipelined follow-up request to prove correlation.

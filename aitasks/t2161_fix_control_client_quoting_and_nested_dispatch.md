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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2236** id=2026-11-08T13:39:14Z.e721e6145c800c0b2464f430 from=t2236 from_verified=yes at=2026-11-08T13:39:14Z base=85b688f06300e7fcdab1ada992343b7036e4aeb8 base_branch=main dirty=no host=omg16
>
> | Advisory (from t2236, committed in 95bc60116 on main): the control-client code this task edits changed underneath it. These are tree-relative claims, dated by this note's base SHA.
> | 
> | 1. Line numbers in this task's body are stale. `_quote_arg` is now at `.aitask-scripts/monitor/monitor_core.py:1478`; `run_via_control` / `run_async_via_control` are at `.aitask-scripts/lib/tmux_exec.py:677` / `:701`.
> | 
> | 2. `_quote_arg` no longer feeds a joined str line. `TmuxControlClient.request()` now sends `_control_line(args)` (monitor_core.py:1491), which quotes each argument and then encodes it **on its own** with `tmux_exec.encode_tmux_wire()`: native OS bytes (`os.fsencode`), falling back to UTF-8 + surrogateescape only when the OS codec cannot represent the string (tmux_gateway.md policy 5). The per-argument split is load-bearing: a whole-line encode lets one non-encodable argument re-encode a native OS-path argument beside it. Your new `'…'` quoting therefore must:
> |    - keep adding only ASCII characters (`'`, `\`, the `\n` / `\r` escape letters), so that quoting commutes with the per-argument encoding;
> |    - keep running per argument inside `_control_line`, never on a joined string.
> | 
> | 3. `tests/test_tmux_exec.py` `TestControlLineParity` (line ~708) hard-codes the CURRENT double-quote escaping (`b'"' + w.replace(b"\\", b"\\\\").replace(b'"', b'\\"') + b'"'`). Switching to single-quote encoding means updating that expected-bytes builder. Keep its assertion that the native OS-path bytes appear intact inside the quoted argument, and keep the Latin-1 negative control, which pins the whole-line-encoding bug class.
> | 
> | 4. Every tmux client now passes `-u` (`TMUX_CLIENT_FLAGS`), including the control attach (`["tmux", "-u", <socket>, "-C", "attach", …]`), and tmux output is decoded as UTF-8 + surrogateescape (`decode_tmux_output`). A live control-vs-subprocess comparison test should run its control client through `TmuxControlClient`, so it inherits both. `tests/test_tmux_utf8_client_live.sh` shows the pattern on a private server.

---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2236
followup_kind: upstream_defect
created_at: 2026-11-08 15:24
updated_at: 2026-11-08 15:58
---

## Origin

Spawned from t2236 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:1551` — `TmuxControlClient._attach_argv` attaches with a bare `-t <session>` instead of the mandatory exact-match `=<session>` target (tmux_gateway.md policy 2). When the named session is absent, tmux prefix-matches, so the monitor's persistent control client can attach to another project's session (e.g. `aitasks_mob` while `aitasks` is not running) and serve every per-tick query from the wrong project.

## Diagnostic context

While adding `-u` to `_attach_argv` in t2236 (the control-mode client now builds `["tmux", *TMUX_CLIENT_FLAGS, *socket_args, "-C", "attach", "-t", self.session, "-f", "no-output,ignore-size"]`), the attach target was found to be the bare session name. Both constructors (`TmuxMonitor.start_control_client` near `monitor_core.py:1833` and the supervisor's reconnect near `:1907`) pass `self.session` unformatted. Every other gateway call site uses `session_target()`. `attach-session -t` is session-typed, so `session_target()` (`=<s>`) is the right helper.

## Suggested fix

Use `session_target(self.session)` in `_attach_argv`. Update the argv-pinning tests in `tests/test_tmux_exec.py` (`TestControlAttachArgv`, which expect `"-t", "mysess"`). Add a live regression: with only `aitasks_mob` running, a control client for `aitasks` must fail `start()` rather than attach. Verify against the reconnect path too.

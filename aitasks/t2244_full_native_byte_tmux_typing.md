---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tmux, robustness]
gates: [risk_evaluated]
anchor: 2236
followup_kind: risk_mitigation
created_at: 2026-11-08 15:27
updated_at: 2026-11-08 15:27
---

## Origin

Risk-mitigation ("after") follow-up for t2236, created at Step 8d after implementation landed.

## Risk addressed

single-byte-locale tmux-text round trip — "Under single-byte named locales, non-ASCII tmux-text arguments (names read back from tmux) do not round-trip. This is a deliberate partial delivery of the task's "non-UTF-8 named locale" case, decided by the user. OS paths, the separator and captured text are covered · severity: medium"

## Goal

Type the OS-path inputs to the tmux gateway at their builders (launcher argv[0], `-c <dir>`, pane shell commands, path-valued options/env such as `@aitask_project_root` and `AITASKS_PROJECT_<s>`) as native bytes, and send all other tmux text as UTF-8. Non-ASCII names then round-trip under single-byte named locales too, which removes the policy-5 limitation from t2236.

Context, from t2236's archived plan and `aidocs/framework/tmux_gateway.md` policy 5:
- Today `encode_tmux_wire(s)` is `os.fsencode(s)`, falling back to UTF-8 + surrogateescape only when the OS codec cannot represent `s`. Under Latin-1 a tmux-text name like `wïn` (decoded from tmux's UTF-8) therefore goes out as `b"w\xefn"` and does not match. Its pane-vote discovery issues `list-panes -t =wïn:`, gets "can't find session", and `discover_aitasks_sessions_checked` reports the session as gone with `complete=True`.
- The fix needs the gateway to know each argument's domain: an OS path is native bytes; everything else is tmux text, sent as UTF-8. Mark OS paths at the builders (e.g. pass `os.fsencode(path)` bytes, which `encode_tmux_argv` already passes through). Every other `str` can then be encoded as UTF-8 unconditionally, including in the control client's per-argument `_control_line`.
- The tests to update are pinned for exactly this: the Latin-1 row of `TestTextModelEncoding.test_latin1_codec_documented_limitation` in `tests/test_tmux_exec.py`, and the "Limitation pin" checks in `tests/test_tmux_utf8_client_live.sh` (the L3 lane, which runs only where `locale -a` lists a single-byte locale).

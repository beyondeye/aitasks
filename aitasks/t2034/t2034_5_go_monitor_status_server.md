---
priority: medium
effort: high
depends: [t2034_4]
xdeps: [16_1]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [monitor, tmux, performance]
anchor: 2034
created_at: 2026-10-16 08:02
updated_at: 2026-10-16 08:02
---

Reimplement the shared monitor status server (child 4) in Go as a goengines
binary (proposed name `goengines/cmd/ait-monitord`), speaking the same protocol
(child 3). Keep it behind a switch, with the Python server as the default,
until the cross-check (child 6) passes.

## Scope

- tmux access through the Go tmux package from aitasks_go#16_1. Its location
  follows the ship-path decision in aitasks_go#15.
- Producer port:
  - pane discovery + session→project map;
  - capture (`capture-pane -p -e -S -<n>`);
  - `strip_ansi` (SGR + OSC 8, `monitor/ansi_utils.py`);
  - the prompt registry (`monitor/prompt_patterns.py`), including per-pattern
    `skip_trailing_blank_rows`, the 6-line tail and `scope_patterns`;
  - the agent-key ladder (`lib/agent_keys.py`: pane command, then one level of
    children via `pgrep -P` + `ps -o comm=`);
  - the idle clock and shadow pairing;
  - task completion (`TaskInfoCache`: identity-keyed on `(st_mtime_ns,
    st_size)`, re-resolves under `archived/` on `OSError`).
- Lifecycle and socket rules identical to the Python server.
- Reuse `internal/platform` (flock, cache root); `gopkg.in/yaml.v3` and
  `golang.org/x/sync` are already in `go.mod`.

## Known Go pitfalls

- RE2 has no lookarounds. `prompt_patterns.py` has none today, but
  `review_loop.py:611` does (`(?=\x1b\[|$)`); that stays client-side, so keep it
  that way or rewrite the pattern.
- `\s`, `\w` and `\b` are ASCII-only in Go but Unicode in Python 3 `str`
  patterns, and Python's `splitlines()` splits on more than `\n`. Matching runs
  on the last 6 lines, so line splitting must match exactly.

## Not in this task

Event-driven change detection — tmux control-mode `%output` (disabled today by
`-f no-output,ignore-size`) or `refresh-client -B` format subscriptions
(tmux ≥ 3.2) — so quiet panes need no capture. Worth a follow-up once a single
process owns the event stream.

## Verification

`ait engine test`; protocol conformance against child 3's codec and recorded
fixtures. Child 6 is the gate for switching the default.

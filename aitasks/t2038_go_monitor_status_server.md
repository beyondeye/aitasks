---
priority: medium
effort: high
depends: [2037]
xdeps: [17]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [monitor, tmux, performance]
children_to_implement: [t2038_1, t2038_2, t2038_3]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

Reimplement the shared monitor status server in Go as a goengines binary
(proposed name `goengines/cmd/ait-monitord`). It speaks the same protocol
(t2034_3) as the Python server it replaces, and stays behind a switch — the
Python server is the default — until the classifier cross-check (t2034_6)
passes. Background: aitasks#2034. Split out of t2034 because it is a full port
of the producer.

## Children

1. Binary skeleton: protocol codec + lifecycle.
2. Discovery + capture.
3. Classifier.
4. State (idle clock, shadows, task completion) + end-to-end comparison.

## Dependencies

- The Python server task (the Go one mirrors its lifecycle and behaviour).
- The Go tmux package aitasks_go#17. Its location follows the ship-path decision
  in aitasks_go#15.

## Known Go pitfalls

- RE2 has no lookarounds. `monitor/prompt_patterns.py` has none today, but
  `monitor/review_loop.py:611` does (`(?=\x1b\[|$)`); that stays client-side.
- `\s`, `\w` and `\b` are ASCII-only in Go but Unicode in Python 3 `str`
  patterns, and Python's `splitlines()` splits on more than `\n`.

## Not in this task

Event-driven change detection — tmux control-mode `%output` (disabled today by
`-f no-output,ignore-size`) or `refresh-client -B` format subscriptions
(tmux ≥ 3.2) — so quiet panes need no capture. A follow-up once one process owns
the event stream.

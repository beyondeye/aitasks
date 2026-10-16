---
priority: medium
effort: medium
depends: [2037]
xdeps: [17]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [monitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

The `ait-monitord` binary skeleton (parent: Go monitor status server task).

## Do

- `goengines/cmd/ait-monitord` (name per the parent) with a Go codec for the
  t2034_3 protocol; conformance tests against the recorded fixtures and the
  Python codec's round-trip cases.
- Lifecycle identical to the Python server: socket path per (tmux socket,
  `VERSION`), `ensure` under an exclusive lock (`internal/platform` flock), idle
  exit, stale-socket recovery, shutdown on control-mode `%exit` (through the Go
  tmux package, aitasks_go#17).
- The switch that selects the Go or Python server; the Python one stays the
  default.

## Verification

`ait engine test`; lifecycle tests mirroring the Python server's.

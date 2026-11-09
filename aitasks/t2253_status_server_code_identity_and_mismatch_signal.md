---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [monitor, minimonitor]
gates: [risk_evaluated]
anchor: 2034
followup_kind: carry_over
created_at: 2026-11-09 10:47
updated_at: 2026-11-09 10:47
---

## Context

Carried over from t2246. That task shipped only an **explicit** restart of the
shared monitor status server: `ait monitor --restart-server` /
`--server-status` (verified SIGTERM via `monitor/status_restart.py`) and the
owner-scoped `ait upgrade` hook. The user narrowed the scope because the Go
server (aitasks_go#t47) is planned to replace the Python one. What is still
missing is any **automatic** detection that a running server's code is
older than the checkout. A dev commit that changes producer code still needs
someone to run `ait monitor --restart-server`.

**Pick this up only once aitasks_go#t47's shape is known.** The identity must
be impl-agnostic: Python source digest today, the binary digest for
`ait-monitord`.

## Deferred scope (design analysis from t2246 planning)

1. **Code identity.**
   - The server reports a content-derived identity, `<scheme>:<hex>`, opaque,
     e.g. `py1:<sha256>`. Clients and `ensure` compute the same value from the
     checkout. Never use mtime or stat freshness.
   - A server reporting none must read as mismatched on every consumer.
   - Measured candidate input set: every regular `*.py` under `monitor/` and
     `lib/` (recursive), plus the top level of `.aitask-scripts/`. These are
     the server's import roots. That is 141 files / 4.4 MB, about 3 ms to hash.
     Skip `__pycache__`, dotfiles (editor `.#x.py` locks) and non-regular files.
   - Use relative paths in the digest so that identical trees hash identically.
   - Shell scripts the producer executes are re-read on every run, so they are
     not inputs.
   - Lazy imports exist: `monitor_core` imports `sitrep_harvest` and `yaml`
     inside functions, `gate_ledger` imports `gate_registry_sync`. Guard them
     with an AST import-closure test (function-level imports included), plus
     a runtime `identity_incomplete` warning.
   - Hash **before** the heavy imports, so the ordering race errs toward a
     restart. Known limits: an edit to `status_server.py` itself in the
     sub-millisecond window, and the CPython mtime+size pyc check.
2. **Policy chosen in analysis: (a)+(c).**
   - (a) Key the socket on the code identity: stem
     `monitor-<key>-<version>-<code12>`.
   - (c) The server watches its own inputs and exits `code_changed` once the
     digest has differed and then stayed stable for a quiet period (about 6 s,
     checked every 2 s). Clients reconnect through the existing loss path.
   - (a) alone accumulates one scanner per code vintage. (c) alone, with
     version-only keying, lets two different trees at the same `VERSION`
     share one server, and any "ensure retires a mismatched server" rule then
     ping-pongs between them. (b) (a new client asks the old server to retire)
     was rejected for the same ping-pong reason.
   - Consequence: a project whose installed copy differs from the dev checkout
     at the same `VERSION` gets its own server.
3. **Visible signal.** When a client falls back because of a code mismatch,
   `ait monitor` gets a header badge. The minimonitor needs a one-row banner,
   because its session bar ships hidden; that touches `_TOP_CHROME` and
   `_MAX_CHROME_ROWS`.
4. **Possibly:** a `retire` protocol request and SIGKILL escalation. t2246
   deliberately deferred both until their necessity is demonstrated (SIGTERM
   is the baseline today).

## Files

- `.aitask-scripts/monitor/status_server.py`, `status_client.py`,
  `status_protocol.py`, `status_paths.py`, `status_restart.py`
- `.aitask-scripts/monitor/monitor_app.py`, `minimonitor_app.py`,
  `monitor_shared.py`
- `aidocs/framework/monitor_status_protocol.md` ("Restart" section, Known
  limits)

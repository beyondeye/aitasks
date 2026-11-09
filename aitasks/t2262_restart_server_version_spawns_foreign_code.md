---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor, minimonitor]
gates: [risk_evaluated]
anchor: 2034
followup_kind: upstream_defect
created_at: 2026-11-09 16:22
updated_at: 2026-11-09 16:22
---

## Origin

Spawned from t2256 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/status_server.py:1238` — `ait monitor --restart-server --version V`
  (`_cmd_restart`) retires V's server and then calls `ensure_server(version=V)`, which
  spawns **this checkout's** `SERVER_SCRIPT` (`status_server.py:134`, argv built at
  `:323`) under V's socket key with `--version V`. Clients of version V accept it,
  because the handshake only compares the version string. They are then served by a
  different release's producer code (prompt patterns, idle detection), which defeats
  the "one server per (tmux server, `VERSION`)" rule. That rule exists precisely
  because prompt patterns change between releases
  (`aidocs/framework/monitor_status_protocol.md` "Scope").

## Diagnostic context

While writing the t2256 troubleshooting docs, the `--version V` advice was traced
through `_cmd_restart` → `ensure_server(version=…)` → `_spawn_server`. The spawned
argv is `[sys.executable, SERVER_SCRIPT, "serve", …, "--version", V, …]`, where
`SERVER_SCRIPT = Path(__file__).resolve()`, i.e. the invoking checkout, whatever its
own `VERSION`. t2256's how-to therefore advises running `ait monitor --restart-server`
**from a project on that version** instead of passing `--version`. The options table in
`website/content/docs/tuis/monitor/reference.md` still advertises "Add `--version V` to
restart the server of another framework version" (text from t2246).

An `ensure` started by a reconnecting client never hits this: it always uses its own
`VERSION`. Only the explicit operator verb can mislabel a server.

## Suggested fix

Either refuse `--version V` when V differs from this checkout's `VERSION` after
retiring nothing (point at running the verb from a project on V), or make it
retire-only for a foreign version: stop V's server and let V's own clients respawn
it from their own files. Then update the reference row and the protocol doc's
"Entry points" table, with a test that a foreign `--version` never spawns this
tree's script under V's key.

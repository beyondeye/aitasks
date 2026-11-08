---
Task: t2232_fix_applink_devices_fakeserver_tunnel.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2232 — Fix `test_applink_devices.sh` FakeServer missing `tunnel`

## Context

`tests/test_applink_devices.sh` exits 1 at mount: `DevicesScreen._refresh`
(`.aitask-scripts/applink/applink_app.py:490-492`) reads `server.tunnel` (added by
t1061_3), but the test's hand-built `FakeServer` predates it and has no `tunnel`
attribute → `AttributeError`, so every later check in the file never runs.
The real server initialises `self.tunnel = None` (`.aitask-scripts/applink/server.py:175`)
and only assigns a `tunnel.QuickTunnel` when auto-tunnel is on. Fixture drift,
not a product bug — fix the fixture, and add coverage for the tunnel segment of
the status line so the read is no longer untested.

## Changes — `tests/test_applink_devices.sh` only (embedded Python heredoc)

1. `FakeServer.__init__`: add `self.tunnel = None` with a comment naming it the
   real `AppLinkServer.tunnel` no-tunnel state.
2. Import the real module: `import tunnel as T` (applink dir is already on
   `sys.path`) — exercise the real `QuickTunnel.status_line()` rather than a stub.
3. Status-line helper: `status_text = lambda: str(screen.query_one("#devices_status", Static).render())`
   (Textual 8.2.7; `Static.render()` → Content, `str()`/`.plain` gives text —
   pattern already used in other tests). Import `Static` from `textual.widgets`.
4. New checks, after the existing row checks and before the revoke block:
   - `"no tunnel segment when server.tunnel is None"` → `"Tunnel" not in status_text()`
     and `"state: Connected" in status_text()`.
   - Set `server.tunnel = T.QuickTunnel(8765)`, then `tun.state = T.STATE_UP`,
     `tun.url = "https://abc-def.trycloudflare.com"`; call `screen._refresh()`,
     `await pilot.pause()`; check `"Tunnel: up — abc-def.trycloudflare.com" in status_text()`.
     (QuickTunnel construction is I/O-free — no spawn until `start()`.)
   - Reset `server.tunnel = None` before the revoke block so the existing revoke
     checks run against the original fixture state.
5. Update the header comment to mention the tunnel status-line coverage.

## Verification

- `bash tests/test_applink_devices.sh; echo rc=$?` → all `ok -` lines incl. new
  ones, `ALL PASSED`, rc=0.
- Pre-fix control: already observed rc=1 with the `AttributeError` (task body + reproduced).
- Mutant control for the new tunnel check, in a scratch copy (never touching the
  shared worktree): copy `.aitask-scripts/` + the test into the scratchpad,
  change `_refresh`'s `tunnel_part` to `""` in the copy, run the copied test →
  must fail on the "Tunnel: up" check.
- `shellcheck tests/test_applink_devices.sh`.
- Sibling sweep: run the other `tests/test_applink_*.sh` to confirm nothing else
  regressed (t2189 reported 13/14 pass).

## Step 9

Commit `bug: … (t2232)` naming only `tests/test_applink_devices.sh`; then
post-implementation archival per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. (Test-only change in one file; no production code touched.)

### Goal-achievement risk: low
None identified. (Root cause reproduced; fix mirrors the real server's default.)

---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [applink]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
created_at: 2026-11-08 08:55
updated_at: 2026-11-08 08:59
---

## Origin

Spawned from t2189 during Step 8b review.

## Upstream defect

- `tests/test_applink_devices.sh:41` — `FakeServer` lacks a `tunnel` attribute, so the
  devices-screen mount crashes in `.aitask-scripts/applink/applink_app.py:491`
  (`_refresh` reads `server.tunnel.status_line()` behind `if server.tunnel is not None`,
  which itself raises `AttributeError` when the attribute is absent). The script exits 1.
  The `server.tunnel` read was added by t1061_3 (`0c0111627`); the test's last change was
  t822_7 (`e12e508bc`), so the fixture predates it.

## Diagnostic context

t2189 fixed the same class of fixture drift in `tests/test_applink_pusher.sh` (a hand-built
`FakePane` missing `current_command` / `pane_pid`) and swept the sibling
`tests/test_applink_*.sh` scripts afterwards: 13 of 14 others exit 0, and
`test_applink_devices.sh` exits 1 with:

```
File "<stdin>", line 63, in main
...
File ".aitask-scripts/applink/applink_app.py", line 473, in on_mount
    self._refresh()
File ".aitask-scripts/applink/applink_app.py", line 491, in _refresh
    f" — {server.tunnel.status_line()}" if server.tunnel is not None else ""
AttributeError: 'FakeServer' object has no attribute 'tunnel'
```

(`line 63` is inside the test's embedded Python heredoc, not a line of the .sh file.)
Both the test and `applink_app.py` were unmodified against HEAD when observed, so this is
pre-existing. Because the crash is at mount, every check after it never runs.

## Suggested fix

Give `FakeServer` `self.tunnel = None` (the real server's no-tunnel state, which
`_refresh` already handles), then confirm the script exits 0 and that the
previously-skipped checks pass. Consider whether any devices-screen check should also
cover a non-None tunnel status line.

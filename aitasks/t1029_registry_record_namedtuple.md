---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [tui_switcher, tmux]
assigned_to: dario-e@beyond-eye.com
anchor: 1025
implemented_with: codex/gpt5_5
created_at: 2026-06-18 15:15
updated_at: 2026-06-21 10:56
boardidx: 40
---

## Origin

Risk-mitigation ("after") follow-up for t1025_1, created at Step 8d after the
project-group data layer landed.

## Risk addressed

Code-health (medium): `_parse_registry_records()` in
`.aitask-scripts/lib/agent_launch_utils.py` returns a **positional** tuple
unpacked at 4+ sites feeding load-bearing discovery (TUI switcher / monitor /
stats). After t1025_1 grew it 4→5 (added `project_group`), a missed unpack site
raises `ValueError` at runtime, not at lint — a fragile positional contract.

## Goal

Convert `_parse_registry_records()` to return a `NamedTuple` (named fields:
`name`, `path`, `git_remote`, `last_opened`, `project_group`) so every registry
reader references fields by name instead of positional unpacking. This
structurally removes the missed-unpack-site `ValueError` class of bug.

Scope:
- Define a `NamedTuple` (or equivalent) for the registry record and have
  `_parse_registry_records()` return a list of it.
- Migrate the consumers (`_read_registry_index`, `_cli_list_registry`,
  `_cli_resolve_index`, and any others) to attribute access.
- Keep the byte-parity wire contract unchanged — this is an in-memory shape
  change only; `tests/test_registry_reader_parity.sh` must stay green.
- The bash awk/IFS readers are out of scope (they parse the serialized pipe
  format, not the Python tuple).

## Verification

- `bash tests/test_registry_reader_parity.sh`
- `bash tests/test_projects_cmd.sh`
- `python3 -m unittest tests.test_project_groups tests.test_discover_include_registered`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:risk_evaluated** run=2026-06-21T07:56:17Z status=pass attempt=1 type=machine

> **✅ gate:plan_approved** run=2026-06-21T07:56:44Z status=pass attempt=1 type=human

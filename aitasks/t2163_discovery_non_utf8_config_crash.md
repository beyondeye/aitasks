---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor, tui, robustness]
followup_kind: upstream_defect
created_at: 2026-10-29 11:47
updated_at: 2026-10-29 11:47
---

## Origin

Spawned from aitasks_go#t17_4 (Go port of `session.TmuxDiscoverer`, the port of
`discover_aitasks_sessions`) during Step 8b review. This is a cross-repo follow-up:
`t17_4` names a task in the **aitasks_go** repository, not this one.

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:690-733,735-765` (as of aitasks `44439196`):
  `_resolve_config_project_group` and `_parse_registry_records` catch only `OSError`.
  When `aitasks/metadata/project_config.yaml` or `~/.config/aitasks/projects.yaml`
  is not valid UTF-8, `open(..., encoding="utf-8")` raises `UnicodeDecodeError`
  (a `ValueError`, not an `OSError`). That error escapes out of
  `discover_aitasks_sessions` in every mode: plain, `include_registered=True`, and
  `discover_aitasks_sessions_checked`.

## Diagnostic context

The Go port pins its behaviour to the real Python module through a generated
fixture (aitasks_go `session/testdata/gen_discovery_fixture.py`). Two of its
scenarios, `registry_non_utf8` and `config_non_utf8`, record `raises:
UnicodeDecodeError` from Python in all three modes. The registry is read for
project-group lookup on every call, so a single bad byte in projects.yaml can do
two things:

- break every live discovery (monitor, stats, TUI switcher, syncer, agent_restore);
- make the `_checked` variant raise instead of answering `(sessions, complete)`.

By contrast, `read_default_session_status` reads bytes and reports an `encoding`
shape, so it handles the same input gracefully.

The Go port treats both files as unreadable: the registry reads as empty and the
config as no project group. It lists this as an intentional difference.

## Suggested fix

Catch `UnicodeDecodeError` (or `ValueError`) next to `OSError` in
`_parse_registry_records` (non-strict wrapper) and `_resolve_config_project_group`,
so that each returns `[]` / `None`. Keep `_parse_registry_records_strict` raising
(its callers need "could not look"). Add test rows for a non-UTF-8 registry and a
non-UTF-8 config to `tests/test_discover_include_registered.py` /
`tests/test_project_groups.py`.

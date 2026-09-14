---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-14 14:47
updated_at: 2026-09-14 14:47
---

## Origin

Spawned from t1784 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:1913-1914 — load_tmux_defaults() returns the string "None" for a blank tmux.default_session (the seed ships it blank), disagreeing with _read_default_session() and the bash resolver, which both return "aitasks"; callers include aitask_board.py:12205/12375, agent_command_screen.py, agentcrew_runner.py`

## Diagnostic context

While planning t1784 (restoring a frozen record when no tmux session exists for
its root), the framework's three resolvers of a project's tmux session name were
compared on a `project_config.yaml` whose `tmux:` block has `default_session:`
with no value. That is the shape `seed/project_config.yaml:441` ships. Measured
2026-09-14:

- `load_tmux_defaults(p)["default_session"]` → `'None'`. `yaml.safe_load`
  yields `None`, `"default_session" in tmux` is true, and the value goes
  through `str()`.
- `agent_launch_utils._read_default_session(p)` → `'aitasks'`.
- `tmux_bootstrap.sh::_tmux_bootstrap_resolve_session` (awk) → `aitasks`.

So on an unconfigured project, a caller reading `default_session` from
`load_tmux_defaults()` would target a tmux session literally named `None`,
while `ait ide` creates and attaches to `aitasks`. t1784 sidestepped the
disagreement by leaving name resolution entirely to the bash bootstrap; it did
not fix it.

Not verified: `monitor_app.py:3894` and `minimonitor_app.py:5302` read the same
key with `tmux_config.get("default_session", "aitasks")`, which returns `None`
(not the default) for a present-but-blank key. Check whether they share the
defect.

## Suggested fix

Treat a null or empty `default_session` as absent in `load_tmux_defaults()`
(fall back to `DEFAULT_TMUX_SESSION`), matching the other two resolvers. Add a
test pinning all three resolvers against the blank-value seed shape.

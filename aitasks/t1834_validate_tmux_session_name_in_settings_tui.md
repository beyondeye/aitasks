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
created_at: 2026-09-18 08:03
updated_at: 2026-09-18 08:03
---

## Origin

Spawned from t1828 during Step 8b review.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:277 — TMUX_CONFIG_SCHEMA["default_session"] is an unvalidated free-text string field, so `ait settings` is a third way to write a name tmux cannot address. Reader-side fallback neutralizes it, but the TUI should refuse it at the point of entry as `ait setup` and `ait ide` do.`

## Diagnostic context

t1828 made every reader refuse a configured `tmux.default_session` holding `.`
or `:` (tmux target separators), falling back to `aitasks` and reporting the
`illegal_tmux_name` shape. That closed the *read* side across all four readers.

Three paths can still **write** such a name:
- `ait setup`'s prompt — already rejects it (`_tmux_bootstrap_session_name_ok`, t1825).
- a hand edit of `project_config.yaml` — deliberately out of reach of any guard.
- **`ait settings`** — no validation at all.

`TMUX_CONFIG_SCHEMA` (`settings_app.py:276-285`) declares `default_session` as
`"type": "string"` with `"default": "aitasks"`. Unlike the sibling
`default_split`, which is an `enum` constrained to `horizontal,vertical`, the
string fields get no validation hook on save (the only validators in that module
are `validate_project_group_slug` and `validate_export_bundle`, neither of which
is wired to this field).

Consequence after t1828: a name typed here is accepted and written, then
silently ignored by every reader at load time. The user sees their configured
value in the settings TUI while every TUI actually runs on `aitasks` — and the
board, both monitors and agentcrew fall back with no message at all, because
`load_tmux_defaults` returns a bare dict with no channel for a problem.

## Suggested fix

Validate at the point of entry, reusing the existing rule rather than restating
it — the Python twin `agent_launch_utils._tmux_session_name_ok` (added by t1828)
is the natural import; `_tmux_bootstrap_session_name_ok` is its bash counterpart.
Refuse the save with a message naming the two characters, in the same spirit as
`ait ide --session` (die) and `ait setup` (warn + fall back).

Worth deciding while implementing: whether the schema grows a general
`validator` hook for string fields (there is currently no such seam), or whether
this one field gets a special case. Check whether other `TMUX_CONFIG_SCHEMA` /
`PROJECT_CONFIG_SCHEMA` string fields have the same latent gap before choosing.

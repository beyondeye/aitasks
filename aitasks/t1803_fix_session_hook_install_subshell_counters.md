---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codex]
gates: [risk_evaluated]
anchor: 1797
followup_kind: upstream_defect
created_at: 2026-09-14 16:48
updated_at: 2026-09-14 16:48
---

## Origin

Spawned from t1797 during Step 8b review.

## Upstream defect

- tests/test_session_hook_install.sh:122 — Groups A–D assert inside `( … )` subshells without `assert_counters_init`/`assert_counters_load`, so a failure there cannot reach the footer and the file still exits 0 (the t1207 pattern)

## Diagnostic context

Found while reading this file as the model for t1797's new
`tests/test_codex_config_tui_seed.sh`. CLAUDE.md requires a file whose test
bodies run inside `( … )` subshells to opt into the file-backed counters:
`assert_counters_init` after sourcing `tests/lib/asserts.sh`, and
`assert_counters_load` in the footer before the `[[ "$FAIL" -eq 0 ]]` guard.
The shared helpers mutate in-process `PASS`/`FAIL`/`TOTAL`, and those
increments die at subshell exit.

`test_session_hook_install.sh` runs Groups A, B, C, C2 and D (the Codex TOML
merge round trip) in `( … )` subshells with neither call. Every assertion in
those groups is invisible to the footer, so the file reports only Group 0 and
Group E and exits 0 whatever A–D did. It passed during t1797, which proves
nothing about A–D.

## Suggested fix

Add `assert_counters_init` after sourcing `tests/lib/asserts.sh` and
`assert_counters_load` before the footer guard (or drop the subshells). Prove it
with a deliberately failing assertion inside one group that must turn the file
red. Consider sweeping `tests/*.sh` for other files that have `( … )` group
bodies and no counter opt-in.

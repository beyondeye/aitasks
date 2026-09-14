---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [test_infrastructure, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: upstream_defect
created_at: 2026-09-14 14:07
updated_at: 2026-09-14 14:26
---

## Origin

Spawned from t1794_1 during Step 8b review.

## Upstream defect

- `tests/test_parallel_admission_collect.py:500,830 — replay fixtures hard-code locked_at "2026-08-30 08:00" while the replay path reads the wall clock; the lock crossed MAX_CLAIM_AGE_S (14 d, parallel_admission.py:47) at 2026-09-13 08:00, so 4 tests now fail for everyone (stale_claim instead of CONFLICT / no-plan exclusion / threshold sensitivity)`
- `.aitask-scripts/lib/shortcut_scopes.py:80-81 — the docstring asserts the TUI dirs have no colliding module basenames, but applink/ and chatlink/ both ship paths.py and audit.py (applink imports them flat); harmless today (8/8 hash seeds load cleanly because applink's own dir wins), now pinned in test_board_package_contract.KNOWN_COLLISIONS`

## Diagnostic context

From t1794_1's full-suite run (2026-09-14, `bash tests/run_all_python_tests.sh`):
`4 failed, 7478 passed` — all four in `tests/test_parallel_admission_collect.py`:

- `ReplayInvariantTests::test_the_inflight_task_is_still_compared_when_listed_first`
  — `VERDICT_FOR:11|CLEAR_CAVEATED` instead of `CONFLICT`
- `ExcludeNoPlanPredicateTests::test_only_the_blocking_no_plan_claim_is_selected`
  — `no_plan_claims()` returned `()` instead of `("9",)`
- `ExcludeNoPlanPredicateTests::test_the_flag_removes_the_cause_it_names`
  — no `EXCLUDED:9`; the output shows `CAUSE_RATE_AT:10|stale_claim|1`
- `ThresholdSweepTests::test_the_threshold_override_reaches_the_verdict`
  — the rates at thresholds 5 and 50 are identical (`3|1|2|0|0`)

Root cause, proven by the clock alone: run in-process, all four FAIL on the
wall clock and PASS with `time.time` pinned to the test file's own
`col.parse_ts("2026-08-30 08:05")`. The `_ReplayScaffold` fixture (`:500`) and
`ExcludeNoPlanPredicateTests.LIVE` (`:830`) carry `locked_at: "2026-08-30 08:00"`,
and `MAX_CLAIM_AGE_S = 14 * 24 * 3600` demotes the in-flight holder to an
advisory/stale claim once the wall clock passes 2026-09-13 08:00. By contrast,
`CollectIntegrationTests` already pins `NOW = col.parse_ts("2026-08-30 08:05")`
(`:295`), and its comment at `:292` warns that a hard-coded epoch silently ages
the fixture.

The second defect was found while building t1794_1's basename-uniqueness
guard: `lib/shortcut_scopes._ensure_import_paths` puts every manifest module's
directory on `sys.path` from a set, and its docstring claims the TUI
directories have no colliding basenames. `applink/` and `chatlink/` both ship
`paths.py` and `audit.py`, and `applink` imports them flat
(`applink_app.py:47`, `server.py:33-34`, …); `chatlink` imports `chatlink.audit`
qualified. `register_all_known_bindings()` loaded cleanly under
PYTHONHASHSEED 0–7, so this is latent, not failing.

## Suggested fix

- Anchor `now` for the replay-path tests to the fixture's own lock timestamp,
  as `CollectIntegrationTests` does — pass `now=` through the replay entry
  point, or derive the fixture's `locked_at` from the current time — so the
  fixtures cannot age out again. Add a guard test that fails if a fixture
  timestamp is older than `MAX_CLAIM_AGE_S` relative to the clock the code
  under test reads.
- Correct the `shortcut_scopes.py:80-81` docstring, or rename one side of the
  applink/chatlink collision (e.g. `chatlink/paths.py` → `chatlink_paths.py`),
  then drop the pin from `test_board_package_contract.KNOWN_COLLISIONS` — its
  stale-pin check will require that.

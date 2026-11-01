---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [install, ait_setup, trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2173
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-31 23:37
updated_at: 2026-11-01 09:17
completed_at: 2026-11-01 09:17
---

## Origin

Spawned from t2173_1 during Step 8b review.

## Upstream defect

- `install.sh:1909-1914` — `ait upgrade` never runs setup and calls only the `.gitignore` repairs explicitly wired into it, so the setup-only rules `.aitask-scratchpad/`, `.aitask-shadow/`, `.aitask-gates/` and `.aitask-testmap/` (`setup_scratchpad_gitignore`, `setup_shadow_store_gitignore`, `setup_gate_logs_gitignore`, `setup_testmap_gitignore` in `aitask_setup.sh`) never reach an upgraded-only project — their stores show as untracked there (t2173_1 wired only `.aitask-cache/`).
- `.aitask-scripts/lib/trail_schema.py:645-652` — `load_trail` catches only `ValueError` from `json.loads`, so a deeply nested JSON payload raises `RecursionError` out of `load_trail` (and out of `trail_discovery.load_trail_blob`, which catches only `TrailValidationError`), crashing the discovery worker instead of yielding a fail-closed `load_error` card. The cache's hit path already treats it as a miss.

## Diagnostic context

From t2173_1 (content-keyed trail discovery cache):

- A plan review found that `setup_cache_gitignore` ran only from `ait setup`;
  `ait upgrade` runs `install.sh`, which skips setup, and the release tarball
  carries no root `.gitignore`. A scratch release-style upgrade left
  `.aitask-cache/` unignored (`?? .aitask-cache/`). t2173_1 fixed its own rule
  by adding `upgrade_cache_gitignore` (write-only) to `aitask_setup.sh` and
  calling it from `install.sh` for existing installs, beside
  `setup_data_gitignore_symlink_safe` and before `commit_installed_files`, so
  the pre-upgrade dirty baseline decides whether `.gitignore` is committed.
  The four older setup-only rules have exactly the same gap.
- While hardening the doc cache against corrupt entries, a deeply nested JSON
  payload (`b'[' * 200000 + b']' * 200000`) was confirmed to raise
  `RecursionError` straight out of `trail_schema.load_trail`. The cache's hit
  path catches it (miss), but a real blob of that shape fetched by
  `load_trail_blob` would escape into the `@work(thread=True)` discovery
  worker (Textual `exit_on_error=True` → TUI exit).

## Suggested fix

- Give each setup-only `.gitignore` helper a write-only upgrade variant (the
  `_ait_add_cache_gitignore_rule` / `upgrade_cache_gitignore` shape: 0 added /
  1 present / 2 failure, writes checked, rule read back), call them from
  `install.sh` under the same `EXISTING_INSTALL` + `declare -F` guard, and add
  a K-style case per rule to `tests/test_install_upgrade_dirty_baseline.sh`.
- Convert `RecursionError` from `json.loads` (and from `validate_trail`'s
  recursive walk, if reachable) into a `TrailValidationError` issue in
  `load_trail`, with a test over a deeply nested payload through both
  `load_trail` and `load_trail_blob`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-31T22:00:36Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-01T07:15:17Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-01T07:17:04Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:64b082c769579f33

> **✅ gate:risk_evaluated** run=2026-11-01T07:17:04Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2177/risk_evaluated_2026-11-01T07:17:04Z-risk_evaluated-a1.log`

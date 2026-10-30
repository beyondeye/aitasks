---
priority: medium
effort: medium
depends: [t1859_1]
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-19 15:44
---

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.2 — `testmap_check` gate**, wave **E** (moved from D by Dev 11). This is
the machine gate that checks the map is consistent before `tests_pass` runs.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, component *Gates*, *Workflow Seam → Gates* (the YAML),
*Enumeration and reconciliation* (the `check` contract and severity table),
and Invariant 8. The parent plan
`aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists the cut fixes
in *Deviations*: Dev 3, 4, 5, 11, 13 and 14.

This coarse plan records what the proposal fixes for M8.2. It does not design
internals against providers that do not exist yet; the Reality check does that
when this child is picked.

**Automation-first:** no path requires a person.

## Dependency hold

`Postponed` only because a provider has no child id yet:

- **M4.2** (t1855): `UNMAPPED_SOURCE:` from M4.1 arrives through it.

t1855's coarse pass adds the id to `depends:` and flips this task to `Ready`
once nothing is left unresolved. Landed providers, satisfied and not in
`depends:`: M2.1 `t1853_1`, M2.6 `t1853_6`. In `depends:`: M8.1 `t1859_1`.
Never depend on a whole provider parent.

## Key Files to Modify

- **New** `.aitask-scripts/aitask_gate_testmap_check.sh`:
  - It is called as `<task-id> <attempt> <run-id>` and takes no flags.
  - It always runs `ait-testmap check --strict`; `bootstrap_until` is the
    strict flip, and an absent value means strict right away.
  - It maps engine exits 0→0, 1→1, 2→3 (`registry_absent`, Invariant 8),
    3→3, 64→3, and a missing engine to 3.
  - It passes `SEEDED:` / `ADOPTED:` through as Info lines that never fail.
  - It reports `UNMAPPED_SOURCE:` for the task's change surface
    (`aitask_change_surface.sh` intake, selector line): reported during
    bootstrap, failing past it.
  - On `UNSTAMPED` (always failing under `require_stamp` past bootstrap), it
    fails with `result=` naming the repair handoff to t1853_7. It never writes
    a stamp and never touches config.
  - It appends the terminal block like the other verifiers.
- `.aitask-scripts/gates_reference.yaml`: add the `testmap_check` entry (type
  machine, `max_retries: 0`, `timeout_seconds: 120`, `blocks_dependents:
  false`, verifier `aitask-gate-testmap-check`). **No `unlocks`:** any explicit
  `unlocks` switches the whole declared set to DAG mode
  (`gate_orchestrator._dag_mode`), so the gate precedes `tests_pass` by list
  position. Sync it to the live registry per the header's edit protocol.
- `tests/test_gates_reference_drift.sh`: the new expected gate.
- Allowlist entries for the new verifier, alongside the existing gate
  verifiers: `.claude/settings.local.json`, `seed/claude_settings.local.json`,
  `.codex/rules/default.rules`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`.
- **New** test file for the verifier (fake engine via `AIT_TESTMAP_BIN` or
  the shim's override; confirm in the Reality check).

## Reference Files for Patterns

- `.aitask-scripts/aitask_gate_tests_pass.sh` / `aitask_gate_risk.sh`
  (verifier shape).
- `aitask-gate-template` skill (verifier contract).
- `lib/gate_orchestrator.py` (`predecessors_map`, `compute_unlocked`).
- `goengines/internal/testmap/registry/rules_core.go` (severities).

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M4.2 has not landed.
1. Write the verifier script.
2. Add the registry entry and sync it.
3. Update the drift test.
4. Add the allowlist entries.
5. Write the tests.

## Verification Steps

- Fake-engine replay of each exit gives the right verifier exit and block.
- A missing engine → 3.
- `SEEDED:` / `ADOPTED:` never fail.
- `UNMAPPED_SOURCE:` is reported before `bootstrap_until` and fails after; an
  absent `bootstrap_until` is strict from the start.
- `UNSTAMPED` past bootstrap → fail with the handoff; no stamp, config
  untouched.
- **Mixed-gate case** through the real orchestrator over `[build_verified,
  testmap_fresh, testmap_check, tests_pass, lint]`: each gate stays blocked
  until its predecessor is satisfied (`tests_pass` while `build_verified` is
  unsatisfied, `testmap_check` while `testmap_fresh` is pending). A negative
  control adds an `unlocks:` and shows the ordering collapse.
- The drift test is green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:22:54Z.0a2331841477d86dbbb7b96b from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:54Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:15:35Z.4ff1607b15aa937ee78edc89 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:35Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.

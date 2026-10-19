---
Task: t1859_2_m8_2_testmap_check_gate.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_1_*.md, aitasks/t1859/t1859_3_*.md, aitasks/t1859/t1859_4_*.md, aitasks/t1859/t1859_5_*.md, aitasks/t1859/t1859_6_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1859_2 — M8.2 `testmap_check` gate (coarse)

## Context

Parent t1859 (M8); Module Map row **M8.2**; wave **E** (moved from D by the
parent's Deviation 11). This child is the machine gate that checks the map is
consistent before `tests_pass` runs.

This coarse plan records what the proposal fixes for M8.2. It does not design internals against providers that do not exist yet; the Reality check below
does that when this child is picked.

**Automation-first:** no path may require a human action. An `UNSTAMPED`
failure is handed to the repair coordinator t1853_7. It is never repaired by
an invented stamp or by weakening the check.

**Dependency hold:** `Postponed` until M4.2 (t1855) has a child id in
`depends:`. t1855's coarse pass wires it and flips this task to `Ready`.

## Proposal reading list

- The `#### M8` row (M8.2).
- Component *Gates*.
- *Workflow Seam → Gates* (the YAML, as amended: no `unlocks`).
- *Enumeration and reconciliation* (the `check` contract and severity table).
- *Line-protocol index*; Invariants 1 and 8.
- Parent plan Deviations 3, 4, 5, 11, 13 and 14.
- `aitask-gate-template`; `aidocs/gates/aitask-gate-framework.md`.

## Owned files / provides / consumes

- **Owns:**
  - `.aitask-scripts/aitask_gate_testmap_check.sh` (new);
  - the `testmap_check` entry in `.aitask-scripts/gates_reference.yaml`,
    synced to the live `gates.yaml`;
  - its expected name in `tests/test_gates_reference_drift.sh`;
  - the verifier's allowlist entries in five files:
    `.claude/settings.local.json`, `seed/claude_settings.local.json`,
    `.codex/rules/default.rules`, `seed/codex_rules.default.rules`,
    `seed/opencode_config.seed.json`;
  - the verifier's test file.
- **Provides:** the consistency gate, placed before `tests_pass` by list
  position; the `UNSTAMPED` handoff reason. Consumers: M6.5 (which owns the
  gate order) and t1853_7.
- **Consumes:**
  - landed: M2.1 `check` (t1853_1, `0d04347ab`; contract `c07193265`) and
    M2.6 `SEEDED:` / `ADOPTED:` (t1853_6, `aaeb10b0f`);
  - pending: M8.1 `t1859_1`;
  - held: M4.2, plus M4.1's `UNMAPPED_SOURCE:` through it;
  - `aitask_change_surface.sh`.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

1. Re-read the M8.2 row, *Gates*, and the interface rows for the `stale`
   report and `UNMAPPED_SOURCE:`.
2. Inspect the actual state, naming the task and commit for each:
   - `check`'s exits and lines (incl. `SEEDED:` / `ADOPTED:` and `--json`
     `summary`), and `bootstrap_until` / `require_stamp` handling;
   - how M4.1/M4.2 expose `UNMAPPED_SOURCE:` for a task (`select --explain`,
     the `test --explain` composite, or `stale --task`);
   - the shim's engine override for a fake engine;
   - the orchestrator's DAG-mode code;
   - the allowlist pattern used by the existing verifiers.
3. Tabulate *proposal* / *coarse plan* / *repository*.
4. Decide each difference and record the decision and its reason. **Stop if
   M4.2 has not landed.**
5. Send notes to downstream consumers whose assumptions break (t1857 M6.5,
   t1853_7, `t1859_3`), hedged.
6. Re-confirm ownership. Whichever of `t1859_2` / `t1859_3` lands second
   rebases the shared drift-test edit.

## Implementation steps (coarse)

1. Write the verifier. It is called as `<task-id> <attempt> <run-id>` and
   takes no flags.
   - It always runs `check --strict`, with `bootstrap_until` as the strict
     flip.
   - It maps engine exits 0→0, 1→1, 2→3 (`registry_absent`), 3→3, 64→3, and a
     missing engine to 3.
   - It passes `SEEDED:` / `ADOPTED:` through as Info.
   - It adds `UNMAPPED_SOURCE:` over the task's change surface: reported
     during bootstrap, failing past it.
   - On `UNSTAMPED` it fails with `result=` naming the handoff to t1853_7.
   - It appends the terminal block.
2. Add the registry entry: `type: machine`, verifier
   `aitask-gate-testmap-check`, `max_retries: 0`, `timeout_seconds: 120`,
   `blocks_dependents: false`, **no `unlocks`**. Sync it with the edit
   protocol's `cp` and commit.
3. Update the drift test.
4. Add the allowlist entries.
5. Write the tests.

## Verification / acceptance

- Fake-engine replay: each engine exit gives the right verifier exit and
  ledger block; a missing engine gives 3.
- `SEEDED:` / `ADOPTED:` never fail.
- `UNMAPPED_SOURCE:` is reported before `bootstrap_until` and fails after;
  with `bootstrap_until` absent it is strict from the start.
- `UNSTAMPED` under `require_stamp` past bootstrap → `fail` with the handoff
  reason. No stamp is written and the config is untouched.
- **The mixed-gate case** runs through the real orchestrator
  (`predecessors_map` / `compute_unlocked`, and an `ait gates run` with fake
  verifiers) over `[build_verified, testmap_fresh, testmap_check, tests_pass,
  lint]`:
  - each gate stays blocked until its predecessor is terminal-satisfied:
    `tests_pass` while `build_verified` is unsatisfied, and `testmap_check`
    while `testmap_fresh` is pending;
  - a negative control adds an `unlocks:` to the fixture registry and shows
    the ordering collapse.
- The drift test is green after the sync; the five allowlist files carry the
  verifier.
- No path requires a human action.

## Step 9 reference

The shared post-implementation flow: current branch, no merge.

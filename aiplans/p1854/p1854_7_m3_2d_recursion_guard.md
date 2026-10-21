---
Task: t1854_7_m3_2d_recursion_guard.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_7 — M3.2d Recursion guard

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_7_m3_2d_recursion_guard.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2d — Recursion guard** of t1854. Wave **1**. See the parent's *M3.2
re-decomposition (2026-10-21)* section.

A test, a suite command, or a framework's native discovery (pytest collection
imports `conftest.py`; `go test -list` runs package `init`) can start another
engine run of the **same repository**. Through `./ait test` that would also
reach `aitask_test.sh`, against Invariant 5. Command-text inspection is only an
early diagnostic (t1854_12). This task owns the **runtime** protection (G9)
and is a prerequisite of every production adapter through t1854_6.

It is a named extension of M3.1's `runner.Run` and `runner.Load`.

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/{run,repo}.go` and a new `recursion.go`, with tests.
- `goengines/cmd/ait-testmap/run.go` (the error line).
- `goengines/README.md`.

## Provides / consumes

- **Provides:** G9, to t1854_6 (and so every adapter), t1854_12, t1859_4, M4.5, M5.1 and `testmap_pidns_invocation_boundary`.
- **Consumes:** M3.1 (t1854_1, landed).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

- Inspect `Run` / `Load` and every caller that reaches them (`scan`, `check`, `run`, and the in-process tests that call them).
- Confirm that no engine test runs `Run` / `Load` against the real repository while a marker would be active.
- Tabulate the differences and decide each one.

Also, as in every M3 child:

- tabulate *task body says* / *repository has* for every difference;
- decide each one (adapt, revise this plan, or revise the proposal per the parent's protocol);
- send a note (`/aitask-note`) to each sibling or downstream task whose assumptions a decision breaks;
- re-confirm that every touched file is this task's or a named extension of its owner.

## Implementation steps (coarse)

1. Step 0 (above).
2. Implement each acceptance criterion below, tests first where a refusal is specified.
3. Red proofs: isolated mutants for every fail-closed rule the criteria name, restored byte-identical.
4. README Interfaces rows and the proposal edits the criteria name.
5. `ait engine test` green.

## Verification (= the task's acceptance criteria)
- **Repository identity.** The realpath of the git common dir. Another worktree of the same repository has the same identity.
- **The guard.** Every engine entry that starts runner processes — `Run`, and `Load` (so the `describe` / `list` discovery behind `scan` and `check`; later `test` / `select`) — refuses when that identity is already active: `RUN_ERROR:recursion|<root>`, exit 3, before any runner process starts.
- **The marker.** Active identities travel in `AIT_TESTMAP_ACTIVE`, which the engine exports to every runner process (`describe`, `list`, `run`).
- **The `env -i` backstop.** A per-repository run lock under `.aitask-testmap/` records the holder's pid and start time. A nested entry whose holder is one of its own ancestors is refused. A concurrent, non-ancestor run of the same repository is not affected by this check.
- **Tests:**
  - nested `run` of the same repository through `sh -c`, `bash` and `python` subprocesses → refused;
  - the same under `env -i` → refused by the ancestry backstop;
  - another worktree of the same repository → refused;
  - **originating in discovery:** a project runner whose `list` calls `ait-testmap check` / `run` on the same repository → refused;
  - **originating in execution:** a runner whose `run` does the same → refused;
  - a fixture repository → allowed, from both paths;
  - goengines' own suite under an active marker → green.

  These tests are written so t1854_6 can parameterize them over its boundary backends.
- **Docs.** The README Interfaces row. `ait engine test` is green.
- **Owner coordination (notes sent at implementation time):**
  - **t1856 (M5.1):** `aitask_test.sh` calls the guard first and never strips the marker; its own tests use fixture repositories.
  - **t1855 (M4.5):** the `test` verb runs through the same guard.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).

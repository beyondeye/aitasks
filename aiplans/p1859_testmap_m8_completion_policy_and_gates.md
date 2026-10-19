---
Task: t1859_testmap_m8_completion_policy_and_gates.md
Base branch: main
Output branch: main
---

# Plan: t1859 — Testmap M8: Completion policy and gates (coarse planning pass)

## Context

The test-map feature (`aidocs/testing_engine/n014_explorer_006_proposal.md`) is
cut into ten modules, one parent task each (t1852–t1861). This task is **M8 —
Completion policy and gates**: what completion runs, who decided it, and the
gates that keep the map honest.

The task body sets the protocol. This session does only the **coarse planning
pass**: one child per submodule, and a coarse plan for each child that records
scope, owned files, provided and consumed interfaces, acceptance list, wave, and
the **mandatory Reality-check step**. The session then **stops** at the child
checkpoint, so no code is written. The body prescribes both "Yes, create child
tasks" and "Stop here", so both are treated as decided.

**Sequencing.** The earliest-wave child, M8.1 (wave A), consumes no other
module. Its only inputs are existing framework files. Under the
submodule-granular rule (memory `feedback_testmap_parents_in_strict_wave_order`;
the t1852 note), the pass is therefore admissible now, even though M4 (t1855),
M5 (t1856) and M7 (t1858) are not decomposed yet.

Children whose providers have no child id yet cannot have those dependencies
wired. They use the convention t1853_7 already set:
- status `Postponed`, with a **Dependency hold** paragraph listing the
  unresolved `M<n>.<m>` references;
- never a placeholder dependency on a whole provider parent (that graph is
  cyclic, and parent completion is too coarse);
- each provider parent's coarse pass adds the real child ids and flips the hold
  to `Ready` once nothing is left unresolved.

**Inbox (6 notes, acknowledged, advisory).**

| note | used for |
|---|---|
| t1852 | the `goengines/internal/testmap/<pkg>` layout; the first skill that calls `ait testmap` owes the five-touchpoint checklist (→ M8.3, Dev 10) |
| t1853 | M2.6 moved to wave B, which resolves the task's *Known inconsistency*; the automation-first directive (Dev 9 plus the decisions below) |
| t1853_7 | wire `t1859_2` / `t1859_3` into t1853_7 (post-approval step 3) |
| t1853_1 | the `check` exit / line contract that M8.2 maps (Dev 3, Dev 4) |
| t1854 | the disjoint full-suite p95 (M8.5); `policy.yaml` carries `contract` (M3.4 owns the format); the bash front reads `fallback_command` without the engine (M8.4) |
| t1853_6 | `SEEDED:` / `ADOPTED:` are always printed, are uncounted Info lines, and `--json` puts them in `summary` (M8.2) |

## Repository reality anchors (verified 2026-10-19, main @ 245754abe)

| fact | state now |
|---|---|
| `run_project_command_key()` (`.aitask-scripts/lib/gate_verifier_lib.sh`) | Statuses are `pass\|fail\|skip` only; reasons are `none_configured\|all_passed\|command_failed\|command_malformed\|command_skipped`. Under the opt-in, 2 means skip and every other non-zero exit is a fail. It returns 3 only when `yaml_utils` is missing. There are no `AIT_GATE_*` exports. |
| `run_command_gate()` | Appends one terminal block with `result="$PROJECT_CMD_RESULT"` (fixed human text) and returns `PROJECT_CMD_CODE`. On return 3 it appends nothing. |
| gate ledger (`lib/gate_ledger.py`) | `VALID_STATUSES` includes `error` (terminal). `unlocks` is parsed: absent means linear, `[]` means terminal. |
| orchestrator (`lib/gate_orchestrator.py`) | `map_exit`: 0 pass / 1 fail / 2 skip / everything else error. `fail` and `error` both spend the retry budget. `reconcile_terminal` does nothing when the appended block matches the exit. Procedure gates are excluded from the headless run (`needs agent`). |
| `aitask_run_project_command.sh` | Has `--task-id` (only to place the log); exports nothing. |
| `gates_reference.yaml` | Has `plan_approved`, `risk_evaluated`, `build_verified`, `tests_pass` (`aitask-gate-tests-pass`, `max_retries 1`, `timeout 600`, `blocks_dependents: true`), `lint`, `docs_updated` (`kind: procedure`), `review_approved`, `merge_approved`. The edit protocol is in its header: `cp` to the live registry, the drift test, and the parser when a key is added. |
| task-workflow Step 8 | The procedure-gate dispatch is **generic** over `kind: procedure` (`procedure-gates` → `begin-procedure` → Read-and-follow the skill), so `testmap_fresh` needs no workflow edit. |
| t635_29 (headless procedure-gate dispatch) | `Ready`, not landed. Autonomous lanes defer procedure gates as `needs agent`. |
| engine verbs (`goengines/cmd/ait-testmap/verbs.go`) | `check` is real and prints `SEEDED:` / `ADOPTED:` (M2.6). `stale`, `select`, `test`, `readiness`, `brief`, `score` and `onboard *` are `stub(...)` (exit 64). No `policy` verb exists. |
| `registry/config.go` | Parses `completion` (`mode`, `full_run_every`, …) and `run_gate_admission`. |
| packages | `goengines/internal/testmap/{annot,classify,deps,fixture,registry,runner}` exist; there is no `feedback`, `stale`, `selectr`, `cost` or `brief`. |
| `aitask_test.sh` | Absent (M5.1). `aitask_testmap.sh` (the shim) is present. |
| permissions | No `./ait testmap` / `aitask_testmap.sh` allowlist entry in `.claude/settings.local.json`. |
| landed providers | M2.1 t1853_1 (`0d04347ab`; contract doc `c07193265`), M2.2 t1853_2, M2.3 t1853_3, M2.5 t1853_5 (`6f6d1ed79`), M2.6 t1853_6 (`aaeb10b0f`/`093d98a19`), M3.1 t1854_1 (`3d1a2b628`) |
| pending providers with ids | M3.2 `t1854_2`, M3.4 `t1854_4` (both `Ready`) |
| providers without ids | M4.1–M4.4 (t1855), M5.1–M5.2 (t1856), M7.1–M7.2 (t1858) |
| t1853_7 | `Postponed`; depends on `t1853_1..6` and `t1854_1`; its provider table names "M8.2, M8.3 → t1859" |
| t1863 | `Ready` cross-linking audit. It treats archived providers as satisfied and omits them from `depends:`. |

## Decomposition — six children

Create all six with `--no-sibling-dep`, in this order, so `t1859_<n>` = `M8.<n>`
for n=1..5 and `t1859_6` is the M8.3 seeds step. Archived providers are
recorded in the bodies and never written into `depends:`. Labels
`testing,testmap,gates`, priority `medium`, type `feature`; the profile adds
`--gates risk_evaluated`.

| child | name | scope (Module Map row, after the Deviations) | depends (now) | unresolved (hold) | status | wave | effort |
|---|---|---|---|---|---|---|---|
| t1859_1 | `m8_1_verifier_exit_contract_and_environment` | `run_project_command_key()` rows for opted-in keys: 75 → `error`/3/`command_refused` and 3 → `error`/3/`command_errored`; 64 and every other non-zero stay `fail` (Dev 1). `run_command_gate` appends the `error` block and returns 3. It exports `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID` around the command, plus the **result carrier** `AIT_GATE_RESULT_FILE` (Dev 2). `aitask_run_project_command.sh --task-id` exports `AIT_GATE_TASK_ID` and reports the new verdict (`STATUS:error`, exit 3). The docblock table; `tests/test_gate_verifiers.sh` cases | — | — | Ready | A | medium |
| t1859_2 | `m8_2_testmap_check_gate` | `aitask_gate_testmap_check.sh` maps engine exits 0/1/2/3/64 and a missing engine to 0/1/3/3/3/3 (Dev 3). It always runs `check --strict`; `bootstrap_until` is the switch (Dev 4). It passes `SEEDED:` / `ADOPTED:` through, and `UNMAPPED_SOURCE:` from the task's change surface (selector, M4.1 via M4.2), failing past `bootstrap_until`. Adds the `testmap_check` entry (`max_retries 0`, `timeout 120`, **no `unlocks` key**: it comes before `tests_pass` by list position, Dev 13) to `gates_reference.yaml`. On an `UNSTAMPED` failure, `result=` names the repair handoff (Dev 14), synced to `gates.yaml`, and updates `tests/test_gates_reference_drift.sh`. Adds the verifier's allowlist entries alongside the existing gate verifiers (`.claude/settings.local.json`, `seed/claude_settings.local.json`, `.codex/rules/default.rules`, `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`) | t1859_1 | M4.2 (→ M4.1) | Postponed | **E** (Dev 11) | medium |
| t1859_3 | `m8_3_testmap_fresh_gate` | The skill `aitask-gate-testmap-fresh` without the seeds step: `stale --task`, `git diff` per `STALE` row, retarget `STALE_PATH`, re-stamp `EVIDENCED` (`--confirm-evidenced`), resolve structural rows, never guess `UNKNOWN`. It never confirms `STALE` and never first-stamps `UNSTAMPED` autonomously (Dev 9): the autonomous lane leaves both. `STALE` is counted, with a `pass`. `UNSTAMPED` mirrors `check`'s own severity, read from the engine and never re-derived: `pass` with a count during bootstrap or without `require_stamp`, and otherwise `fail` with a machine-readable handoff to the repair coordinator (Dev 14). The attended lane prompts. `adopted(… by <who>)` context. Attended and non-interactive branches modelled on `aitask-gate-docs-updated`. The `testmap_fresh` registry entry (Dev 5). The five allowlist entries for `ait testmap` (Dev 10). Goldens / `aitask_skill_verify.sh` | — | M4.2, M4.3 | Postponed | E | high |
| t1859_4 | `m8_4_completion_policy_full_selected` | The `completion:` block semantics (`mode`, `deferred`, `on_empty_selection`, `engine_absent`). The `full` / `selected` arms of `aitask_test.sh`'s `POLICY` hook: readiness re-check, `POLICY_DEMOTED:selected->full\|<criterion>`, `fallback_command` under `engine_absent` (the front reads `runners.yaml` without the engine). Writes the `result=` line through M8.1's carrier (Dev 2). Readiness's `POLICY:` line. The data the `--policy selected` re-entry writes. The `policy` package in `internal/testmap/feedback` and the engine verb `policy` (decide, read-only for full/selected; Dev 7). Cases in `tests/test_ait_test_entrypoint.sh` | t1859_1, t1854_2 | M4.4, M5.1 | Postponed | E | high |
| t1859_5 | `m8_5_auto_policy_and_cadence` | `feedback/cadence.go`; the `auto` arm; the three triggers (with the disjoint full-suite p95, M3.4); `costs/policy.yaml` writes through M3.4's helpers (verb `policy`, Dev 7) and `POLICY_WRITE:`; the front's `ait: testmap policy <flip\|full-run> (t<id>)` path-scoped commit; `POLICY_FLIPPED:` / `POLICY_DEMOTED:auto->full` (clears `approved_by`); `POLICY:auto\|…` shapes; `cadence_declared`, the `CADENCE:` line and `approved_by\|met\|engine` in readiness; the window-score trigger (an extension of M4.4's `score`); `next full in` and the `FULL_GATE:` cadence on the brief; the `auto` matrix | t1859_4, t1854_4 | M4.4, M5.2 | Postponed | G | high |
| t1859_6 | `m8_3_testmap_fresh_seeds_step` | The seeds step of `aitask-gate-testmap-fresh`: `onboard review --ids` for each `COMMITTED:` / `TASK:` test file with seeds. Attended: pre-fill / confirm / override / trust-batch. Autonomous: `onboard adopt --agent-verdicts - --by <agent-string> --run <gate-run>`. Stamps ride the `(t<id>)` commit. Goldens | t1859_3 | M7.1, M7.2 | Postponed | G | medium |

**Automation-first decisions** (user directive; recorded in every child body):

- **`selected`'s human `approved_by` (M8.4).** It stays an *optional* attended
  alternative. `auto` (what `detect --write` writes) is the automated route, and
  under `selected` a missing or unmet approval demotes to `full`, which fails
  toward running more. M8.4 reads the field and never requires it. No proposal
  edit.
- **M8.3.** No branch needs a person:
  - unconfirmable `STALE` and `UNSTAMPED` rows are left as they are, keep
    selecting (Invariant 1), and are counted in `result=`;
  - where the project's rule makes `UNSTAMPED` fail (`require_stamp` past
    `bootstrap_until`), the gate fails loudly and hands the rows to the
    automated repair coordinator t1853_7. That task repairs them through a
    legitimate adoption route and reruns the real verifiers (Dev 14). The gate
    never invents a stamp, and nothing weakens the check;
  - the only autonomous stamp the gate itself writes is `--confirm-evidenced`,
    which re-stamps an *existing* claim once a run evidences it; it is never a
    first stamp;
  - a first stamp for an unstamped edge stays a claim that needs an adoption
    route (M6.3 class, M7.2 verdict — the seeds step `t1859_6` — or M7.4
    author), never one the gate invents (Invariants 2–3);
  - the attended prompt and the confirm / trust-batch steps are UX only.

## Deviations from the proposal (cut fixes, edited into the proposal per protocol §1)

1. **Exit 64 under the opt-in.** Four statements give M8.1 exactly two new rows
   (75, 3): the Module Map row, *Gates*, `assumption_gate_exit_contract_reused`
   and the Data Flow line. The Run Surface exit table keeps 64 → fail. Only the
   Workflow-Seam *Gates* paragraph says "(0/1/2/75/64 → 0/1/2/3/3)". Fix that
   sentence to "0/1/2/3/75 → pass/fail/skip/error/error; 64 and any other code
   stay a fail". (The difference from M8.2 is deliberate. A 64 from a
   *project's* `test_command` is a misconfigured command, so it is a visible
   fail. A 64 from the engine inside *our own* verifier is a framework bug, so
   it is an error.)
2. **`result=` has no carrier.** M8.4 owns the `result=` field ("MODE:…\|policy:…")
   on the `tests_pass` block. That block is written by `run_command_gate`
   (M8.1's file) from fixed text, so nothing carries a string from `./ait test
   --gate` to it. Fix: **M8.1** exports a third variable,
   `AIT_GATE_RESULT_FILE=.aitask-gates/<task>/<gate>_<run>.result`, from
   `run_command_gate` only. When the command leaves a one-line file there, its
   sanitized content becomes `result=` (with the status reason kept as a
   prefix); an absent or empty file keeps today's text. **M8.4 / M8.5** write
   it, and the writer is the bash front `aitask_test.sh`, never the engine
   (Invariant 5).
   - **Command lists:** the file is truncated before each command, and the
     value used is the one written by the command that decided the verdict
     (the failing command, else the last one that wrote).
   - **Sanitization:** newlines are what matters, because the ledger shows the
     value as a `> Result:` line: keep the first line, strip CR/LF, cap the
     length.
   - **Rejected alternatives:**
     - a path derived from `AIT_GATE_TASK_ID` + `AIT_GATE_RUN_ID` couples
       `./ait test` to the `.aitask-gates/` layout;
     - scraping a marker line from the log turns ordinary test output into a
       protocol.

   Edit:
   - *The two environment variables* (→ "two variables and a result carrier");
   - the M8.1 row;
   - *Gates*;
   - the interface row.
3. **`testmap_check` exit mapping.** "Maps engine exits 0/1/2/64 and a missing
   engine to 0/1/2/3/3" omits the engine's own 3 (`CONTRACT_MISMATCH` /
   `INPUT_*` / `CHECK_ERROR`). It also maps 2 (`TESTMAP_ABSENT`) to skip, which
   contradicts Invariant 8 ("a *declared* gate errors (exit 3) and never
   skips"). Fix: 0→0, 1→1, 2→3 (`registry_absent`), 3→3, 64→3, missing engine→3.
4. **The verifier takes no flags, and `UNMAPPED_SOURCE` has a provider.** The
   orchestrator runs `<verifier> <task> <attempt> <run>`, so "`--strict` past
   `bootstrap_until`" cannot be a verifier flag. Fix:
   - the verifier always runs `check --strict` and applies the same
     past-`bootstrap_until` rule to `UNMAPPED_SOURCE:`;
   - `bootstrap_until` is the strict flip: `detect --write` sets it to +90
     days and `finish` shortens it. An absent value means strict right away
     (`registry/config.go`), so a hand-written map is strict from the start.
     That case goes into M8.2's acceptance list.

   `UNMAPPED_SOURCE:` is the selector's line (M4.1). M8.2 consumes it over the
   task's change surface, transitively satisfied through M4.2. The interface
   row "the ranked list, `SELECTED:`, `UNMAPPED_SOURCE:`" gains M8.2 as a
   consumer.
5. **`testmap_fresh` registry entry moves to M8.3.** Otherwise the reference
   registry would name a procedure skill before it exists, and `ait gates
   sync-registry` would ship that downstream. Fix: M8.3 adds its own entry.
   M8.2 and M8.3 are both wave E after Dev 11, so a dependency between them
   would break the wave rule. They stay independent: each adds one entry and
   one expected name in the drift test, and whichever lands second rebases.
   (The Reality check says so.)
6. **M8.3 is two children.** The base gate is wave E and the seeds step is
   wave G. A single child would sit half-done for two waves and could not be
   archived. Edit to make: the proposal's M8.3 row gains "(two child tasks:
   base; seeds step)".
7. **No verb owns the policy decision or the `policy.yaml` write.** The `test`
   composite "never applies a completion policy". `readiness` "enables nothing".
   Yet "the engine writes" `costs/policy.yaml` under `ait test --gate`. Fix:
   - **M8.4** adds an engine verb `policy`, as a named extension of M1.2's verb
     table. Its `decide` subcommand prints the `POLICY:` / `POLICY_DEMOTED:`
     lines for `full` / `selected`.
   - **M8.5** extends it with the `auto` arm and the two write points: the
     pre-run flip or demotion, and the post-run full-run reset or selected
     increment. Each prints `POLICY_WRITE:`.
   - `readiness`'s `POLICY:` line calls the same `feedback/policy` code, so the
     two cannot disagree.
   - The exact subcommand shape is fixed in M8.4's Reality check.
   - Also edit the proposal's engine verb list (*Go engine and CLI*, ~line
     1982). The verb calls M3.4's `policy.yaml` helpers; send a note to
     `t1854_4`.
8. **M5.1 consumes M8.1.** The interface table has "the verifier exit contract
   and the two environment variables — M8.1 → M5.1 (mode)", but M5.1's depends
   cell lacks it. Add `M8.1` to M5.1's depends cell. Wave A precedes D, so
   nothing changes. Note to t1856.
9. **Autonomous outcomes of `testmap_fresh` are unstated.** Add to *Skills* and
   *Freshness*: in the autonomous lane the gate never confirms a `STALE` row
   and never writes a first stamp, and it never pends for a person. The outcome
   per row class:
   - **`STALE`** — left, counted in `result=`, gate `pass`. The row keeps
     selecting. It leaves through `--confirm-evidenced`, which **re-stamps an
     existing claim** once an anchored run evidences it.
   - **`UNSTAMPED`** — left and counted. The outcome follows `check`'s own
     severity:
     - during bootstrap, or without `require_stamp`: gate `pass`;
     - under `require_stamp` past `bootstrap_until`: gate `fail` with the
       repair handoff (Dev 14).

     A first stamp comes only from a legitimate adoption route, never from
     `--confirm-evidenced`.
10. **Permission touchpoints for `ait testmap`.** M8.3 (wave E) is the first
    skill to call the shim (M6.5 is F; M9.3 and M7.5 are G). It owns the five
    allowlist entries. Nothing needs re-pinning:
    `tests/test_touchpoint_count_contract.sh` counts touchpoint *files*, and
    it belongs to M5.1. Add this to the M8.3 row.
11. **Wave contradiction: M8.2 (wave D) depends on M4.2 (wave D).** Move M8.2
    to **wave E**.
    - The wave D state text "`testmap_check` can be declared" moves to wave E.
    - Every consumer of M8.2 (M6.5) is wave F, so no other wave changes.
12. **M6.5 consumes M8.3.** Onboarding's `enable` phase writes `testmap_fresh`
    into the profiles' `default_gates`, but M6.5's depends cell names only
    M8.2 and M8.4. Add `M8.3`. M8.3 is wave E and M6.5 is F, so the waves are
    unaffected. Note to t1857.

13. **`unlocks: [tests_pass]` breaks every mixed gate set.** In
    `gate_orchestrator.py`, `_dag_mode()` (l. 91) switches the **whole**
    declared set to DAG mode as soon as any declared gate carries `unlocks`.
    `successors()` (l. 103) then makes every gate without an explicit
    `unlocks` terminal. Take a declared set `[build_verified, testmap_fresh,
    testmap_check, tests_pass, lint]`: `tests_pass` would wait only for
    `testmap_check`, while `build_verified`, `testmap_fresh` and `lint` would
    lose all ordering, so tests could start before the build passes. The
    proposal's "an `unlocks:` target absent … is ignored, so `testmap_check`
    declared alone is linear as before" overlooks this.

    Fix:
    - **`testmap_check` declares no `unlocks`.** Like every shipped gate, it
      stays in linear mode.
    - The chain is expressed by **list position**: the active tuple keeps the
      declared order (`compute_active_gates` resolves `task.gates` /
      `default_gates` in order).
    - **M6.5's `enable` phase owns the order.** It inserts `testmap_fresh,
      testmap_check` immediately before `tests_pass`, or appends all three in
      that order when `tests_pass` is absent, and never reorders existing
      entries. Note to t1857.
    - **Pre-existing DAGs are refused, not merged.** Inserting into a gate set
      that is already in DAG mode enforces nothing: if any gate in the
      resulting declared set (the profile's `default_gates` /
      `rendered_gates`, read against the project's `gates.yaml`) carries an
      explicit `unlocks`, the new gates are terminal and have no predecessors.
      For example, with `build_verified` unlocking `tests_pass` and
      `tests_pass` unlocking `lint`, `tests_pass` keeps only `build_verified`
      as a predecessor. M6.5's `enable` therefore runs a **compatibility
      check before it writes anything**:
      - when `_dag_mode` would be true for the resulting set, it writes
        nothing and refuses with a precise diagnostic, e.g.
        `ENABLE_REFUSED:gate_dag_mode|<profile>|<gates declaring unlocks>`,
        plus a one-line remedy;
      - the check must use the orchestrator's own predicate
        (`gate_orchestrator._dag_mode` / `predecessors_map`), not a copy;
      - this is the smaller fix: it detects and refuses, and leaves the
        scheduler alone. Integrating the map gates into an existing DAG is a
        named follow-up, not v1.

      M6.5's acceptance gains a **pre-existing-DAG fixture**: that exact
      registry and profile → refused, nothing written, diagnostic exact. A
      linear control fixture → written in the required order. Proposal edit
      under *Onboarding → enable* and the M6.5 row; note to t1857.
    - Proposal edits: the `gates:` YAML under *The Workflow Seam → Gates*,
      the concrete-edits row, *Gates* in Components, and the "unlocks
      `tests_pass`" wording in the Module Map / interfaces. The reference
      header's "None below declare it" remains true.
    - **M8.2 acceptance gains a mixed-gate case** through the real orchestrator
      (`predecessors_map` / `compute_unlocked`, plus an `ait gates run` with
      fake verifiers) over `[build_verified, testmap_fresh, testmap_check,
      tests_pass, lint]`:
      - each gate stays blocked until its predecessor is terminal-satisfied:
        `tests_pass` while `build_verified` is unsatisfied, and `testmap_check`
        while `testmap_fresh` is pending;
      - a negative control adds an `unlocks:` to the fixture registry and
        shows the ordering collapse the fix avoids.
14. **`UNSTAMPED` past bootstrap is a dead end without a repair handoff.** In
    M2.1's `check`, `checkUnstamped` (`registry/rules_core.go:87`) is an
    always-failing finding under `require_stamp` past `bootstrap_until`, even
    without `--strict` (`check_test.go:49`). So:
    - an autonomous `testmap_fresh` that leaves such rows is followed by a
      failing `testmap_check`;
    - that failure blocks `tests_pass`;
    - no policy demotion or further test run can supply the missing first
      adoption.

    Fix (assignment, not new machinery):
    - **M8.3** reports these rows as a `fail` whose `result=` and log carry
      the `UNSTAMPED` pairs and the handoff reason.
    - **M8.2** fails with the same reason in `result=`.
    - Neither invents a stamp, extends `bootstrap_until` or flips
      `require_stamp`.
    - **The repair is assigned to t1853_7**, the existing automated repair
      coordinator, which already consumes M8.2/M8.3 "to repair check/freshness
      failures and rerun the real verifier". Post-approval step 3 adds to its
      body and acceptance:
      - this case, by name;
      - the legitimate **first-stamp adoption** routes: `annotate --author`
        for pairs on the change surface (M7.4), verdict adoption from packets
        (M7.2), and class `--auto` over a rule or measurement class (M6.3).
        Each writes the stamp together with its `adopted.yaml` provenance.
        `--confirm-evidenced` is **not** one of them: it only re-stamps an
        existing claim (the `STALE` + evidence case) and is out of scope for a
        missing first stamp;
      - an **integration scenario** under an autonomous profile with
        `require_stamp: true` past `bootstrap_until`: a task leaves an
        unstamped edge → `testmap_fresh` fails with the handoff → the
        coordinator adopts it through a legitimate route → the **real**
        `testmap_check` passes → `tests_pass` runs;
      - negative controls: an edge with no legitimate route stays failing
        and is reported, and no invented stamp, `bootstrap_until` extension
        or `require_stamp` flip occurs.
    - **Rollout prerequisite, stated in the proposal (*Freshness*, *Skills*)
      and in notes to t1857 / t1861:** unattended completion under
      `require_stamp: true` past `bootstrap_until` requires t1853_7. Until it
      lands, an autonomous lane in that configuration fails loudly; it never
      passes silently.

**M8.1 helper contract (record for the Reality check, no proposal edit).**
`aitask_run_project_command.sh` prints `VERDICT:`, and its header promises that
exit 3 prints no `VERDICT:` line. M8.1 must restate that header for the new
`error` verdict, either `VERDICT:error` + `REASON:command_refused|command_errored`
with exit 3, or keep exit 3 verdict-less. Whichever it picks, the
`build-verification.md` capture form ("rc 3 or empty verdict → infrastructure")
must still read it as infrastructure until M9.1 adds the specific branch. This
is the correct interim behaviour.

The *Known inconsistency* in the task body (M8.2 wave D vs M2.6 wave E) is
already resolved: M2.6 is wave B (`3bc0de8ac`, t1853).

## Cross-module seams (recorded in every child body)

**Provides:**

| what | provider | consumers |
|---|---|---|
| exit rows 75/3 → error, `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`, the result carrier | M8.1 | M5.1, M8.4, M8.5, M9.1, M9.2 |
| `testmap_check` (precedes `tests_pass` by list position, Dev 13) | M8.2 | M6.5 (owns the order), t1853_7 |
| the `UNSTAMPED` handoff reason in `result=` / log (Dev 14) | M8.2, M8.3 | t1853_7 (repair coordinator) |
| `testmap_fresh` (base) | M8.3 | M6.5, M9.5, M10.x, t1853_7 |
| the seeds step | M8.3 seeds (t1859_6) | M10.1/M10.3–M10.5 review loops |
| the `completion:` block, `POLICY:` lines, verb `policy` | M8.4, M8.5 | M5.2, M6.1, M6.5, M9.1 |

**Consumes:**
- landed: M2.1, M2.2, M2.3, M2.6, M3.1;
- pending with ids: M3.2 `t1854_2`, M3.4 `t1854_4`;
- held: M4.1–M4.4, M5.1, M5.2, M7.1, M7.2;
- external: t635_29 (headless procedure dispatch; soft — see Risk).

**Named extensions:**

| extension | owner | added by |
|---|---|---|
| `POLICY` hook arms in `aitask_test.sh` | M5.1 | M8.4 (full/selected), M8.5 (auto) |
| cases / `auto` matrix in `tests/test_ait_test_entrypoint.sh` | M5.1 | M8.4, M8.5 |
| `policy` package, `cadence.go` in `internal/testmap/feedback` | M4.4 | M8.4, M8.5 |
| `POLICY:` / `CADENCE:` / `cadence_declared` / `approved_by` lines in `readiness` | M4.4 | M8.4, M8.5 |
| window-score trigger in `score` | M4.4 | M8.5 |
| `next full in` / `FULL_GATE:` cadence on `brief` | M5.2 | M8.5 |
| `costs/policy.yaml` writer logic | M3.4 helpers | M8.5 |
| verb row `policy` | M1.2 verb table | M8.4 |
| seeds step in `aitask-gate-testmap-fresh` | M8.3 | t1859_6 |
| verifier / `ait testmap` allowlist entries (five files) | existing framework touchpoints | M8.2 (verifier), M8.3 (`ait testmap`) |

Invariants 1, 5, 8 and 9 bind:
- a demotion runs full, and a cadence full run is never skipped;
- the engine never commits, and the front commits path-scoped;
- a declared gate errors and never skips;
- `tests_pass` runs `./ait test --gate`.

## Child plan template (`aiplans/p1859/p1859_<n>_<name>.md`)

Header per `planning.md`: `Task:`, `Parent Task:`, `Sibling Tasks:`,
`Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md`,
`Base branch: main`, `Output branch: main`, no `Worktree:`. Then:

1. **Context.** The parent goal, this row, the wave, and verbatim: *"This
   coarse plan records what the proposal fixes for M8.<n>. It does not design
   internals against providers that do not exist yet; the Reality check below
   does that when this child is picked."* Then the automation-first decisions
   and, for held children, the **Dependency hold** paragraph (unresolved
   `M<n>.<m>` refs, with the rule that the provider's coarse pass wires the ids
   and flips the child to `Ready` when nothing is left unresolved).
2. **Proposal reading list.** The `#### M8` row; the component(s):
   - M8.1–M8.3: *Gates*;
   - M8.3 / seeds step: *Freshness*, *Skills*;
   - M8.4: *Completion policy*;
   - M8.5: *Auto completion policy*, *Cost ledger*, *Feedback tools*.

   Also: *The Workflow Seam* (Gates, Completion policy, Verification by
   module); *Run Surface → Output and exit contract, The two environment
   variables*; *Data Flow → A completion run under policy, The policy flip*;
   *The in-gate site* (seeds step); the invariants; the *Open questions* (3 and
   4 for M8.4/M8.1, 13 for M8.5); this parent plan's Deviations; the
   precedents `aitask-gate-docs-updated`, `aitask-gate-template` and
   `aidocs/gates/aitask-gate-framework.md`.
3. **Owned files / provides / consumes**, from the tables above.
4. **Step 0 — Reality check (MANDATORY, before any code; outcome recorded in
   this plan file).** The six sub-steps of the parent body §2, starting from
   the anchors table above. By pick time those anchors are claims, not facts.
   Child-specific items:
   - **M8.1:** `map_exit` / `reconcile_terminal` against an appended `error`
     block; the helper's `VERDICT:` header contract for the new `error`
     verdict, read against the build-verification capture form; the carrier
     (truncation per command, first line only, CR/LF stripped, length cap).
   - **M8.2:** M2.1 `check`'s current exits and lines; how M4.1/M4.2 expose
     `UNMAPPED_SOURCE:` for a task (`select --explain` or `stale --task`);
     `aitask_change_surface.sh` intake. **Stop if M4.2 has not landed.**
   - **M8.3:** the M4.2 `stale` line classes and `--confirm*` / `--retarget`
     as landed; the M4.3 join; t635_29's non-interactive contract and status;
     the docs gate skill's structure; whether `t1859_2` has already edited
     `gates_reference.yaml` and the drift test (rebase onto it). **Stop if
     M4.2/M4.3 have not landed.**
   - **M8.4:** M5.1's `POLICY` hook and its carrier use; M4.4 `readiness`
     lines; the `completion:` parse in `registry/config.go`; the bash reading
     of `runners.yaml` `fallback_command` (M3.1 schema); Open question 3.
     **Stop if M4.4/M5.1 have not landed.**
   - **M8.5:** M3.4's `policy.yaml` helpers and full-suite p95; M4.4 `score`;
     M5.2 `brief`. Also concurrency of the committed counter across sessions
     and worktrees: lock, read-modify-write, and a merge rule that fails
     toward running more. **Stop if M3.4/M4.4/M5.2 have not landed.**
   - **Seeds step:** M7.1 packets and M7.2 intake as landed. **Stop if not
     landed.**
5. **Implementation steps (coarse):** the scope cell expanded into ordered
   steps, naming files and verb rows.
6. **Verification / acceptance:**
   - **M8.1** (`tests/test_gate_verifiers.sh`, file-backed counters if it
     uses subshells):
     - opted-in 75 → `error`/`command_refused`, and 3 → `error`/`command_errored`,
       each with an appended `error` block and return 3;
     - not opted in, 75 and 3 → fail;
     - 64 → fail;
     - 2 → skip unchanged;
     - the command sees `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`, and
       `aitask_run_project_command.sh --task-id` exports the former;
     - the carrier: present, absent and malformed (multi-line, a quote);
     - a negative control proving each new row is the one that fires.
   - **M8.2:**
     - fake-engine replay of each exit → verifier exit and block;
     - a missing engine → 3;
     - `SEEDED:` / `ADOPTED:` never fail;
     - `UNMAPPED_SOURCE:` reported before `bootstrap_until` and failing after;
       with `bootstrap_until` absent, strict from the start;
     - the five allowlist files carry the new verifier;
     - drift test green after the `cp`;
     - the **mixed-gate case** (Dev 13) over `[build_verified, testmap_fresh,
       testmap_check, tests_pass, lint]`, through the real orchestrator:
       - `tests_pass` is blocked while `build_verified` is unsatisfied, and
         `testmap_check` while `testmap_fresh` is pending;
       - each gate unblocks only after its predecessor;
       - a negative control proves an `unlocks:` would collapse the ordering;
     - `UNSTAMPED` under `require_stamp` past `bootstrap_until` → `fail` whose
       `result=` names the handoff (Dev 14); no stamp written, config
       untouched.
   - **M8.3:**
     - the skill goldens via `aitask_skill_verify.sh`;
     - a fixture run of each branch:
       - STALE left and counted with a `pass`;
       - UNSTAMPED `pass`+count in bootstrap, and `fail`+handoff under
         `require_stamp` past bootstrap (Dev 14);
       - EVIDENCED re-stamped;
       - STALE_PATH retargeted;
       - UNKNOWN never guessed;
       - no stamp ever invented;
     - the five `ait testmap` allowlist entries present;
     - the drift test with `testmap_fresh` (procedure, no verifier check).
   - **M8.4** (`tests/test_ait_test_entrypoint.sh`):
     - `full`;
     - `selected` with every criterion met;
     - `selected` demoted per criterion;
     - `engine_absent: error` (3) and `fallback_command` (`MODE:fallback`);
     - `on_empty_selection` skip/full;
     - `deferred: run|fail`;
     - the `result=` shape in the ledger block;
     - readiness `POLICY:`.
   - **M8.5:**
     - the `auto` matrix: `NOT_YET`, first `ADMISSIBLE` (flip, write, commit
       path-scoped), each cadence trigger, the steady selection with the
       counter incremented, a demotion clearing `approved_by`, and a cadence
       full run ignoring `on_empty_selection`;
     - engine tests for the window score attributing a miss to the right task;
     - the cadence check < 50 ms.
   - **Seeds step:**
     - autonomous `--agent-verdicts` adoption riding the commit;
     - attended pre-fill / override / trust-batch (`by: human` / `by: agent`);
     - parked rows left.
   - **Every child:**
     - `ait engine test` green where Go is touched;
     - no path requires a human action — a human-only step met in the proposal
       is reported to its owning parent, never encoded.
7. **Step 9 reference.** The shared post-implementation; current branch, no
   merge.

## Post-approval sequence

0. **Edit the proposal for Deviations 1–14 in one change.** The edits:
   - **Dev 13:** remove `unlocks: [tests_pass]` from the *Workflow Seam →
     Gates* YAML and from every "unlocks `tests_pass`" statement. State the
     DAG-mode reason, that M6.5 writes the order, and that M6.5's `enable`
     refuses a pre-existing DAG (`ENABLE_REFUSED:gate_dag_mode|…`) with its
     fixture added to the M6.5 row / *Onboarding → enable*. Add the DAG-merge
     to *Named follow-ups*.
   - **Dev 14:** *Freshness* / *Skills* gain the `UNSTAMPED` fail+handoff and
     the rollout prerequisite (the automated repair coordinator, t1853_7).
   - **Module Map:** M8.1 scope (carrier), M8.2 scope (exits, no flags, only
     `testmap_check`, verifier allowlist), M8.3 scope (registry entry,
     allowlist, autonomous outcomes, two children; depends unchanged), M8.4
     scope (verb `policy`, carrier), M8.5 scope (writes via `policy`); M5.1
     depends `+ M8.1`; M6.5 depends `+ M8.3`.
   - **Suggested implementation order:** M8.2 moves from D to E, and the
     "`testmap_check` can be declared" state text moves with it.
   - *Go engine and CLI* verb list: `+ policy`.
   - **Cross-module interfaces:** the M8.1 row (+ carrier); the
     `UNMAPPED_SOURCE:` row (+ M8.2); the `completion:` row (+ verb `policy`).
   - *Run Surface → The two environment variables*.
   - *Workflow Seam → Gates* (the exit sentence) and the concrete-edits rows
     for the lib, `gates_reference.yaml` and `aitask_gate_testmap_check.sh`.
   - Components *Gates*, *Completion policy*, *Auto completion policy*,
     *Freshness* and *Skills*.

   Commit:
   `git commit -m "documentation: Fix the M8 cut in the testmap proposal (t1859)" -- aidocs/testing_engine/n014_explorer_006_proposal.md`.
0b. **Sync t1859's body**, using the Edit tool and never touching `## Inbox`:
   - the `## Submodules` table (six rows; scope and depends cells as above);
   - mark the *Known inconsistencies* bullet resolved;
   - the hooks bullets (the named-extensions table);
   - the automation-first decisions.

   Commit with
   `aitask_task_commit.sh -m "ait: Sync t1859 submodule table with the corrected M8 cut" aitasks/t1859_testmap_m8_completion_policy_and_gates.md`.
1. **Externalize the plan:**
   `aitask_plan_externalize.sh 1859 --force --profile aitasks/metadata/profiles/fast.yaml --no-worktree`.
   Commit it with `aitask_task_commit.sh`.
2. **Create the six children**, in order, with `aitask_create.sh --batch
   --commit --parent 1859 --no-sibling-dep …`. `--deps` and `--status` go on
   the create call, so nothing is left uncommitted:
   - `_1`: no deps, Ready.
   - `_2`: `--deps 1859_1 --status Postponed`.
   - `_3`: no deps, `--status Postponed`.
   - `_4`: `--deps 1859_1,1854_2 --status Postponed`.
   - `_5`: `--deps 1859_4,1854_4 --status Postponed`.
   - `_6`: `--deps 1859_3 --status Postponed`.

   Each description carries the Child Task Documentation Requirements sections
   and, when held, the Dependency hold. If a create call cannot take a dep on a
   not-yet-created sibling, fall back to `aitask_update.sh --batch <id> --deps …
   --commit`.
3. **Wire t1853_7**, reading its list first: `aitask_update.sh --batch 1853_7
   --deps "t1853_1,t1853_2,t1853_3,t1853_4,t1853_5,t1853_6,t1854_1,t1859_2,t1859_3"
   --commit`. Keep it `Postponed`. Its provider-table row `M8.2, M8.3` →
   `t1859_2`, `t1859_3`; it does not consume the seeds step `t1859_6`. Using
   the Edit tool, and never touching its `## Inbox`, add the **Dev 14
   assignment** to its body:
   - the `UNSTAMPED`-past-bootstrap case;
   - the legitimate routes;
   - the integration scenario plus its negative controls (as an
     `## Acceptance` bullet);
   - the rollout-prerequisite sentence.

   Commit the body edit with `aitask_task_commit.sh`, naming the path.
4. **Revert the parent:** `aitask_update.sh --batch 1859 --status Ready
   --assigned-to "" --plan-approved-at "" --commit`, then
   `aitask_lock.sh --unlock 1859`.
5. **Write the six child plans** to `aiplans/p1859/` and commit them together,
   naming every file.
6. **Send notes** (`/aitask-note`, citing the step-0 commit; hedged as tree
   claims):

   | to | content |
   |---|---|
   | t1855 (M4) | At your pass, wire: `t1859_2` ← M4.2; `t1859_3` ← M4.2, M4.3; `t1859_4` ← M4.4; `t1859_5` ← M4.4. Flip each to `Ready` when its hold list empties.<br>M8.2 consumes M4.1's `UNMAPPED_SOURCE:` over a task (Dev 4).<br>`internal/testmap/feedback` gains `policy` (M8.4) and `cadence.go` (M8.5); readiness gains `POLICY:` / `CADENCE:` / `cadence_declared` / `approved_by\|met\|engine`; `score` gains the window trigger; verb `policy` (Dev 7). |
   | t1856 (M5) | Dev 8: M5.1 depends on `t1859_1`.<br>The `POLICY` hook and the `AIT_GATE_RESULT_FILE` carrier (Dev 2).<br>Wire `t1859_4` ← M5.1 and `t1859_5` ← M5.2.<br>Observation for your pass (unverified design reading): the exit table's "2 = TESTMAP_ABSENT + no `test_command` → skip" under the opt-in, and `--gate` delegating to `test_command` = `./ait test`, read against Invariant 8 and recursion. |
   | t1854_4 (M3.4) | Dev 7: the new engine verb `policy` (M8.4/M8.5) calls your `costs/policy.yaml` read/write helpers; the writer logic stays M8.5's. |
   | t1857 (M6) | M6.5 depends on `t1859_2`, `t1859_3` (Dev 12), `t1859_4`; M8.2 moved to wave E (Dev 11).<br>**Dev 13:** `enable` owns the gate order. It inserts `testmap_fresh, testmap_check` immediately before `tests_pass` (or appends all three in that order) and never adds `unlocks:`, because any `unlocks` flips the whole set into DAG mode (`gate_orchestrator.py:91`). Before writing, `enable` runs a compatibility check with the orchestrator's own `_dag_mode` / `predecessors_map`: if the resulting set is in DAG mode, it refuses with `ENABLE_REFUSED:gate_dag_mode\|<profile>\|<gates declaring unlocks>` and writes nothing. Acceptance: a pre-existing-DAG fixture (`build_verified`→`tests_pass`→`lint`) is refused, and a linear control is written in order.<br>**Dev 14:** `finish` / config must not put an autonomous profile under `require_stamp: true` past `bootstrap_until` before t1853_7 lands; until then that configuration fails loudly at `testmap_check`.<br>Enable must not declare `testmap_fresh` into a headless profile before t635_29 lands (procedure gates defer as `needs agent`).<br>`--policy selected` is an optional attended alternative; `auto` is the automated route.<br>`bootstrap_until` is the strict flip `testmap_check` reads (Dev 4). |
   | t1858 (M7) | Wire `t1859_6` ← M7.1, M7.2; flip to `Ready` when both are wired. |
   | t1860 (M9) | Ids: M8.1 = `t1859_1` (M9.1, M9.2); M8.3 = `t1859_3` (+ seeds `t1859_6`) for M9.5; M8.5 = `t1859_5` for M9.4.<br>`build-verification.md` reads `STATUS:error` + exit 3 for `command_refused` / `command_errored`.<br>The `AIT_GATE_RESULT_FILE` carrier. |
   | t1861 (M10) | M8.3 = `t1859_3`; its seeds step = `t1859_6` (the review loops of M10.1/M10.3–M10.5 rely on it).<br>Rollout prerequisite (Dev 14): a target that runs autonomous lanes under `require_stamp: true` past `bootstrap_until` needs t1853_7 (the repair coordinator) to have landed. |
   | t1863 | Six M8 children; holds on `t1859_2..6`; new edges `t1853_7 → t1859_2, t1859_3`, M5.1 → `t1859_1` (pending t1856), M6.5 → `t1859_3` (pending t1857). M8.2 → M2.1/M2.6 omitted as archived. |

   Then update memory `feedback_testmap_parents_in_strict_wave_order`: t1859
   decomposed; `t1859_1` is pickable now (wave A); t1855 is still next for a
   coarse pass.
7. **Manual-verification sibling prompt** (automation-first → recommend "No");
   child checkpoint → **Stop here**.

### Post-phase (risk mitigations)

1. **[verify_child_plans_carry_reality_check]** Before committing the child
   plans, run
   `grep -L 'Step 0 — Reality check' aiplans/p1859/p1859_*_*.md` and
   `grep -L 'does not design internals against providers that do not exist yet' aiplans/p1859/p1859_*_*.md`.
   Both must print nothing.
2. **[verify_child_dependency_graph]** After steps 2–3, read back
   `grep -H '^depends:\|^status:' aitasks/t1859/t1859_*_*.md aitasks/t1853/t1853_7_*.md`.
   It must show exactly:

   | task | depends | status |
   |---|---|---|
   | _1 | `[]` | Ready |
   | _2 | `[t1859_1]` | Postponed |
   | _3 | `[]` | Postponed |
   | _4 | `[t1859_1, t1854_2]` | Postponed |
   | _5 | `[t1859_4, t1854_4]` | Postponed |
   | _6 | `[t1859_3]` | Postponed |
   | t1853_7 | `[… t1854_1, t1859_2, t1859_3]` | Postponed |

   Correct any mismatch before reverting the parent. Every held child body must
   contain `Dependency hold` (`grep -L`).
3. **[verify_parent_table_matches_proposal]** Extract the M8 depends cells from
   the proposal and from t1859's `## Submodules` table, counting fields from
   the end. Diff them against the expected strings:
   - proposal: `—` / `M2.1, M2.6, M4.2, M8.1` / `M4.2, M4.3; seeds step:
     M7.1, M7.2` / `M3.2, M4.4, M5.1, M8.1` / `M3.4, M4.4, M5.2, M8.4`;
   - parent table: the same, except that the M8.3 row is `M4.2, M4.3` and
     there is a seeds-step row `M8.3, M7.1, M7.2`.

   Also check that M5.1's cell contains `M8.1`, M6.5's contains `M8.3`, and
   M8.2 is listed in wave E, not D. Grep the proposal for
   `0/1/2/75/64 *→` (expect nothing; this narrow pattern avoids M3.1's runner
   contract at ~line 710, which must stay untouched) and for
   `AIT_GATE_RESULT_FILE` (expect a hit). Also grep the proposal for
   `unlocks: \[tests_pass\]` (expect nothing), and grep t1853_7's body for
   `UNSTAMPED` (expect a hit). Fix any mismatch before reverting the parent.

## Verification (of this pass)

- `aitask_ls.sh -v -s all --children 1859 99` lists six children. `_1` is
  Ready and unblocked. `_2`..`_6` are Postponed: they are hidden without
  `-s all`, and the dependents show as blocked.
- The post-phase greps are clean.
- The parent is `Ready`, unassigned and unlocked, with
  `children_to_implement` covering `_1`..`_6`.
- The proposal carries Deviations 1–14: M5.1's depends cell includes M8.1 and
  M6.5's includes M8.3, no `unlocks: [tests_pass]` remains, and the rollout
  prerequisite is stated.
- t1853_7's body names the `UNSTAMPED` handoff case and its integration
  scenario.
- t1853_7's depends include `t1859_2` and `t1859_3`.

## Plan review

A read-only planning agent reviewed the draft adversarially against the
proposal and the tree. It confirmed Deviations 1–8. These changes came from its
findings:

- **Dev 9 redesigned:** there is no autonomous first stamp; `UNSTAMPED` is left
  and counted, like `STALE`.
- **Dev 10:** no re-pin.
- **New Deviations:** Dev 11 (M8.2 → wave E, so it no longer waits on M4.2 in
  the same wave) and Dev 12 (M6.5 → M8.3).
- **M8.2 additions:** the verifier allowlist entries.
- **M8.1 helper:** the `VERDICT:` header contract.
- **Dev 2 details:** command lists, sanitization, and the rejected
  alternatives.
- **Post-approval mechanics:** deps on the create call, `--commit` on
  updates, the narrow `0/1/2/75/64 *→` grep, and `-s all`.

The user's review of the revised plan raised two blocking concerns. Both were
verified against the code and are addressed:

- **Dev 13** (`gate_orchestrator.py:91-124`, DAG mode): `testmap_check`
  declares no `unlocks`, list order is owned by M6.5, and M8.2 gains a
  mixed-gate acceptance case with a negative control.
- **Dev 14** (`rules_core.go:87`, `check_test.go:49`): the `UNSTAMPED` dead
  end is a loud fail with a handoff. The repair is assigned to t1853_7, with an
  integration scenario and negative controls, and the rollout prerequisite is
  stated.

The user's second review raised two more blocking concerns, both verified and
addressed:

- **Pre-existing explicit DAGs.** Insertion enforces nothing once the set is
  in DAG mode, so M6.5's `enable` now detects this with the orchestrator's own
  predicate and refuses with `ENABLE_REFUSED:gate_dag_mode|…`, backed by a
  pre-existing-DAG fixture and a linear control. Merging into an existing DAG
  is a named follow-up.
- **Dev 9 and Dev 14 contradicted each other.** Dev 9 is rewritten to the
  conditional `UNSTAMPED` outcome. `--confirm-evidenced` is restricted to
  re-stamping an existing claim and removed from the first-stamp adoption
  routes.

## Risk

### Code-health risk: low
- The pass writes task/plan data and one documentation edit. A wrong `depends:` cell or a forgotten `Postponed` hold would mis-block or prematurely unblock a child · severity: low · → mitigation: inline post-phase verify_child_dependency_graph

### Goal-achievement risk: medium
- The twelve cut fixes are hypotheses made before M4/M5/M7 are planned. A child implemented without executing its Reality check would build against the proposal's description rather than the tree · severity: medium · → mitigation: inline post-phase verify_child_plans_carry_reality_check
- t1863 audits children against each parent's `## Submodules` table and the proposal's cells. A stale table, or a proposal edit that misses a cell (M5.1 + M8.1, M6.5 + M8.3, the M8.2 wave) or over-matches (M3.1's `0/1/2/75/64` contract), would let a consumer unblock early or corrupt an unrelated row · severity: medium · → mitigation: inline post-phase verify_parent_table_matches_proposal
- A gate registry change that silently reorders a project's mixed gate set (DAG mode), or an autonomous freshness pass that leaves a `require_stamp` failure with no repair route, would let tests run before the build or dead-end unattended completion · severity: high before the fix · → mitigation: Dev 13 (no `unlocks`, order by list, mixed-gate case with negative control) and Dev 14 (fail+handoff, assigned to t1853_7 with an integration scenario, rollout prerequisite)
- Held children depend on later provider passes (t1855/t1856/t1858) to wire ids and lift the hold. If a pass forgets, a child stays Postponed indefinitely, which is fail-safe but stalls · severity: low · → mitigation: the step-6 notes plus t1863's audit (no extra mitigation)

### Planned mitigations
- timing: post-phase | name: verify_child_plans_carry_reality_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — child plan lacking the mandatory Reality check | desc: grep every child plan for the Step 0 heading and the no-internals sentence before committing them
- timing: post-phase | name: verify_child_dependency_graph | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — wrong depends cell or missing Postponed hold | desc: read back the six child depends/status lines plus t1853_7 and the Dependency-hold text, compare with the table before reverting the parent
- timing: post-phase | name: verify_parent_table_matches_proposal | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — stale submodule table or mis-scoped proposal edit | desc: diff the M8 depends cells (proposal + parent table) against the expected strings, check M5.1/M6.5 cells and the M8.2 wave, and run the narrow exit-mapping and carrier greps

## Step 9 reference

Post-implementation per the shared workflow. In this pass it ends at the child
checkpoint ("Stop here"), so there is no Step 9 for the parent now.

---
priority: medium
effort: high
depends: [t1859_1, t1854_12, t1854_7]
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-21 22:08
---

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.4 — Completion policy `full` / `selected`**, wave **E**. It makes the one
completion gate (`tests_pass` running `./ait test --gate`) mean a committed
policy:
- `full` runs the whole registry;
- `selected` runs the task's selection, after a readiness re-check that demotes
  loudly to full.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, component *Completion policy*, *The registry directory*
(the `completion:` block), *Workflow Seam → Completion policy*, *Data Flow →
A completion run under policy*, *Test entrypoint* (the `POLICY` hook), and
Open question 3. The parent plan
`aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists the cut fixes
in *Deviations*: Dev 2 (the `result=` carrier) and Dev 7 (verb `policy`).

This coarse plan records what the proposal fixes for M8.4. It does not design
internals against providers that do not exist yet; the Reality check does that
when this child is picked.

**Automation-first:** `selected`'s human `approved_by` (written by M6.5's
`--policy selected`) is an optional attended alternative. `auto` (M8.5) is the
automated route. Under `selected`, a missing or unmet approval demotes to
`full`. M8.4 reads the field and never requires it.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M4.4** (`readiness`, the `internal/testmap/feedback` package), in t1855;
- **M5.1** (`aitask_test.sh` and its `POLICY` hook,
  `tests/test_ait_test_entrypoint.sh`), in t1856.

Each provider parent's coarse pass adds the ids and flips this task to `Ready`
once nothing is left unresolved. In `depends:`: M8.1 `t1859_1`, M3.2
`t1854_2`. Landed: M3.1 `t1854_1` (defines `fallback_command:`).

## Key Files to Modify

- `.aitask-scripts/aitask_test.sh` (M5.1's): the `full` / `selected` arms of
  the `POLICY` hook:
  - the readiness re-check, `POLICY_DEMOTED:selected->full|<criterion>`;
  - `on_empty_selection` (skip → exit 2 | full);
  - `deferred: run|fail`;
  - `engine_absent: error|fallback_command`: the front reads `runners.yaml`'s
    full-suite `fallback_command` **without the engine** and prints
    `MODE:fallback`;
  - writes `result="MODE:<full|selected>|<n units>|policy:<mode>"` through
    M8.1's `AIT_GATE_RESULT_FILE`.
- `goengines/internal/testmap/feedback/policy/` (a new package in M4.4's
  `feedback`): the decision logic, shared by `readiness`'s `POLICY:` line and
  the new verb.
- `goengines/cmd/ait-testmap/verbs.go`: verb **`policy`** (`decide`, read-only
  for full/selected) as a named extension of M1.2's verb table. The exact
  subcommand shape is fixed in the Reality check.
- `readiness` (M4.4's): the additive `POLICY:<mode>|<what --gate would run
  now>` line.
- The data schema the `--policy selected` re-entry writes
  (`completion.mode: selected`, `run_gate_admission.approved_by {who, at,
  statement}`); M6.5 writes it.
- `tests/test_ait_test_entrypoint.sh` (M5.1's): the cases.

## Reference Files for Patterns

- `goengines/internal/testmap/registry/config.go` (`Completion`,
  `RunGateAdmission`, `FullRunEvery` already parsed).
- `.aitask-scripts/lib/yaml_utils.sh` (bash YAML reads).

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M4.4 or M5.1 has not landed.
1. Write the `policy` package and the verb.
2. Add the readiness line.
3. Add the front's arms and the fallback.
4. Write the `result=` line.
5. Write the tests.

## Verification Steps

- `full`; `selected` with every criterion met; `selected` demoted per
  criterion.
- `engine_absent: error` (3) and `fallback_command`.
- `on_empty_selection` skip/full; `deferred: run|fail`.
- The `result=` shape in the gate-run block; readiness `POLICY:`.
- `ait engine test` green.
- No path requires a human action.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1859_1** id=2026-10-20T15:55:14Z.92b52b7e838b42cef3ed2e11 from=t1859_1 from_verified=yes at=2026-10-20T15:55:14Z base=e2116c90aa17f9410b5d451c5eb87f70d6b47cf4 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1859_1 (M8.1), landed in e2116c90a on main. Tree claims as of that commit; verify them in your reality check.
> | 
> | The result carrier you write `result=` through, as landed:
> | 
> | - `AIT_GATE_RESULT_FILE` is an ABSOLUTE path, `<repo>/.aitask-gates/<task>/<gate>_<run>.result`, exported by `run_command_gate` only.
> |   - It is unset under the legacy helper `aitask_run_project_command.sh`, which exports `AIT_GATE_TASK_ID` only, and only with `--task-id`.
> |   - So the front must treat "variable unset" as "no carrier".
> | - Write ONE line. The ledger records `result="<PROJECT_CMD_REASON>: <your line>"`, e.g. `all_passed: MODE:full|720 units|policy:full`.
> |   - The proposal's Data Flow example shows the value without the `<reason>: ` prefix. The prefix is the landed shape (Module Map: "behind the status reason").
> | - Sanitizer (`lib/gate_result_carrier.py`):
> |   - decodes UTF-8 with replacement and keeps `str.splitlines()[0]`;
> |   - drops Unicode Cc/Cf/Zl/Zp and every splitlines boundary;
> |   - strips, then caps at 200 characters.
> |   - A sanitizer failure keeps the fixed text.
> | - **Command lists:** the file is truncated before each command. A failing or erroring command's OWN value is used (an empty one means the fixed text, never an earlier command's value). Otherwise the last value written is used.
> | - **Opted-in exits:** 75 → `error`/`command_refused`, 3 → `error`/`command_errored` (verifier exit 3, retried within budget). 64 and any other non-zero stay `fail`.
> | 
> | Contract and docblock: `run_project_command_key()` in `.aitask-scripts/lib/gate_verifier_lib.sh`.

> **✉ note:t2131** id=2026-10-23T05:01:12Z.ccf056d6d03b30d2ee1f569c from=t2131 at=2026-10-23T05:01:12Z base=b460828651acc16079e3a895296343b1c422620d base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2131 (testmap code-modules tier, status Ready, not yet planned). Nothing here is an instruction; your own planning decides.
> | 
> | t2131 plans a `module` completion-policy mode next to `full | selected` (and M8.5's `auto`). It runs the complete test sets of the code modules a task's change affects, plus the task's individually selected tests outside them. This was decided during exploration (user-confirmed, not yet a landed design). Touchpoints in what M8.4 owns:
> | 
> | - `completion.mode` in `aitestmap/config.yaml`: a third value, `module`.
> | - The ledger result line `result="MODE:<full|selected>|<n units>|policy:<mode>"`: a `module` value. Since this contract has not landed yet, it may be cheaper to keep the MODE vocabulary open-ended now than to widen it later.
> | - Demotion: a module-scope run is only allowed when the module evidence bounds it. `gradle-dynamic` builds, opaque files and unresolved references mean full. A loud demotion line in the style of `POLICY_DEMOTED:selected->full|<criterion>` (e.g. `module->full|<reason>`) would fit the existing pattern. This is a suggestion, not a settled design.
> | - `on_empty_selection` and the fallback path stay full-suite by default under the decisions above.
> | - Related but outside this task: M8.5 (t1859_5) `auto`/cadence and M4.4 `readiness`'s `POLICY:` line would need to learn the mode too. A note went to t1855 for the readiness side; t1859_5 was not notified.
> | 
> | The mode's selection mechanics (dependent-module reach, membership) are planned under t2131 and M4.1 (t1855), not here.

> **✉ note:t2131** id=2026-10-23T08:55:57Z.2b60364c0d40db91543de014 from=t2131 at=2026-10-23T08:55:57Z base=6b3161606e2989d1865628155f4e0bc1021cb917 base_branch=main dirty=yes host=omg16
>
> | t2131_8 (`module_completion_mode`, Postponed) now depends on this task (and on t1859_5 and t2131_7). It adds a `module` arm to the `POLICY` hook in `aitask_test.sh` and to the `policy` verb:
> | - `completion.mode: full|selected|module|auto`, plus `completion.widen`;
> | - `MODE:module|…` in `result=`, within the 200-character cap;
> | - `POLICY_DEMOTED:module->full|<criterion>`.
> | 
> | Advisory: if the `completion.mode` enum or the `MODE:` vocabulary is closed in code you write here, keeping it easy to extend would help t2131_8.
> | 
> | Separately, a small staleness I noticed while reading. Tree-relative, as of the commit this note records: this task's body line 48 still says "In `depends:`: M8.1 `t1859_1`, M3.2 `t1854_2`", but the frontmatter has `depends: [t1859_1, t1854_12, t1854_7]` since the M3.2 re-decomposition.
> | 
> | Plans: `aiplans/p2131/p2131_8_module_completion_mode.md`.

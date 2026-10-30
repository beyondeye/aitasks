---
priority: medium
effort: high
depends: [t1859_1, t1854_12, t1854_7]
xdeps: [t65_1]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t65_1
in beyondeye/aitasks_go. This body is the framework half.

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.4 — Completion policy `full` / `selected`**, wave **E**: the bash front.
It makes the one completion gate (`tests_pass` running `./ait test --gate`)
mean a committed policy:
- `full` runs the whole registry;
- `selected` runs the task's selection, after a readiness re-check that demotes
  loudly to full.

The decision logic (the `policy` package under
`goengines/internal/testmap/feedback/policy/`), the engine verb `policy`
(`decide`) and the `readiness` `POLICY:` line are aitasks_go#t65_1. This task adds
the front's arms and calls that verb; it waits on aitasks_go#t65_1 through `xdeps`
(`xdeprepo: aitasks_go`), which unblocks only when aitasks_go#t65_1 is Done. Its
tests use a fake engine that speaks the verb's published line protocol.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, component *Completion policy*, *The registry directory*
(the `completion:` block), *Workflow Seam → Completion policy*, *Data Flow →
A completion run under policy*, *Test entrypoint* (the `POLICY` hook), and
Open question 3. The parent plan
`aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists the cut fixes
in *Deviations*: Dev 2 (the `result=` carrier) and Dev 7 (verb `policy`).

This coarse plan records what the proposal fixes for M8.4's front. It does
not design internals against providers that do not exist yet; the Reality
check does that when this child is picked.

**Automation-first:** `selected`'s human `approved_by` (written by M6.5's
`--policy selected`) is an optional attended alternative. `auto` (M8.5) is the
automated route. Under `selected`, a missing or unmet approval demotes to
`full`. M8.4 reads the field and never requires it; no front path requires a
human action.

## Dependency hold

`Postponed` because its providers have not landed:

- **aitasks_go#t65_1** (the `policy` verb and the decision): `xdeps`.
- **M5.1** (`aitask_test.sh` and its `POLICY` hook,
  `tests/test_ait_test_entrypoint.sh`), in t1856, not yet decomposed. t1856's
  coarse pass adds the M5.1 child id to `depends:`.
- M4.4 (`readiness`) reaches this task through aitasks_go#t65_1, which holds on
  it in aitasks_go (aitasks_go#t61's M4.4 child). If t1855 adds an `xdeps` entry on
  that child here, keep it.

In `depends:`: M8.1 `t1859_1` (landed), plus the landed engine providers
`t1854_12` and `t1854_7` (the stale body line naming M3.2 `t1854_2` is
superseded). Landed: M3.1 `t1854_1` (defines `fallback_command:`). Flip this
task to `Ready` once nothing in its hold is left unresolved.

## Key Files to Modify

- `.aitask-scripts/aitask_test.sh` (M5.1's): the `full` / `selected` arms of
  the `POLICY` hook:
  - the readiness re-check through aitasks_go#t65_1's `policy decide` /
    `readiness`, printing `POLICY_DEMOTED:selected->full|<criterion>` with the
    criterion the engine reports;
  - `on_empty_selection` (skip → exit 2 | full);
  - `deferred: run|fail`;
  - `engine_absent: error|fallback_command`: the front reads `runners.yaml`'s
    full-suite `fallback_command` **without the engine**, runs it as
    `bash -c <command>` (the same shell the suite builtin uses, so the
    engine-present and engine-absent runs share semantics), and prints
    `MODE:fallback`. The suite builtin never reads `fallback_command:`;
  - writes `result="MODE:<full|selected>|<n units>|policy:<mode>"` through
    M8.1's `AIT_GATE_RESULT_FILE`.
- The data schema the `--policy selected` re-entry writes
  (`completion.mode: selected`, `run_gate_admission.approved_by {who, at,
  statement}`); M6.5 writes it, and the engine parses it.
- `tests/test_ait_test_entrypoint.sh` (M5.1's): the cases.

## The result carrier (t1859_1, landed; re-verify)

- `AIT_GATE_RESULT_FILE` is an absolute path,
  `<repo>/.aitask-gates/<task>/<gate>_<run>.result`, exported by
  `run_command_gate` only. It is unset under the legacy helper
  `aitask_run_project_command.sh`, so treat "unset" as "no carrier".
- Write ONE line. The ledger records `result="<PROJECT_CMD_REASON>: <your line>"`,
  e.g. `all_passed: MODE:full|720 units|policy:full`.
- The sanitizer (`lib/gate_result_carrier.py`) keeps the first line, drops
  control and separator characters, strips, and caps at 200 characters.
- Command lists: the file is truncated before each command; a failing or
  erroring command's own value is used, otherwise the last value written.
- Opted-in exits: 75 → `error` / `command_refused`, 3 → `error` /
  `command_errored`; 64 and any other non-zero stay `fail`.

## Open modes (code-modules tier)

- `completion.mode: full|selected|module|auto`. Keep the `MODE:` vocabulary
  and the arm dispatch easy to extend: t2131_8 adds a `module` arm here
  (`POLICY_DEMOTED:module->full|<criterion>`, passing `--widen-modules` to the
  engine `test` composite). `completion.widen` does not exist.
- The full `result=` shape is
  `MODE:<full|selected|module>|<n units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>|widen_full:<reason>]`,
  at most 200 characters.

## Reference Files for Patterns

- `.aitask-scripts/lib/yaml_utils.sh` (bash YAML reads).
- `.aitask-scripts/lib/gate_verifier_lib.sh` (`run_project_command_key()`
  docblock: the carrier and exit contract).

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M5.1 or aitasks_go#t65_1 has not landed. Read aitasks_go#t65_1's published verb shape
   and build the fake engine from it.
1. Add the front's arms and the fallback.
2. Write the `result=` line.
3. Write the entrypoint cases.

## Verification Steps

- `full`; `selected` with every criterion met; `selected` demoted per
  criterion — through the front, with the fake engine.
- `engine_absent: error` (3) and `fallback_command`.
- `on_empty_selection` skip/full; `deferred: run|fail`.
- The `result=` shape in the gate-run block.
- No path requires a human action.

## Carried obligations (framework half)

- Intro / "`full` runs the whole registry; `selected` runs the task's selection, after a readiness re-check that demotes loudly to full" — Intro (the front runs the policy; the decision is aitasks_go#t65_1's)
- Intro **Automation-first** / "`selected`'s human `approved_by` … optional … a missing or unmet approval demotes to `full`. M8.4 reads the field and never requires it" — Intro **Automation-first** paragraph
- `## Dependency hold` / "M5.1 (`aitask_test.sh` and its `POLICY` hook, `tests/test_ait_test_entrypoint.sh`), in t1856" — *Dependency hold*, M5.1 bullet
- `## Dependency hold` / "In `depends:`: M8.1 `t1859_1`, M3.2 `t1854_2`. Landed: M3.1 `t1854_1`" — *Dependency hold*, `depends:` paragraph (the stale M3.2 line is superseded)
- Key Files / "`aitask_test.sh` … the readiness re-check, `POLICY_DEMOTED:selected->full|<criterion>`" — *Key Files*, readiness re-check bullet (prints the criterion aitasks_go#t65_1 reports)
- Key Files / "`on_empty_selection` (skip → exit 2 | full)" — *Key Files*, `on_empty_selection` bullet
- Key Files / "`deferred: run|fail`" — *Key Files*, `deferred` bullet
- Key Files / "`engine_absent: error|fallback_command`: the front reads `runners.yaml`'s full-suite `fallback_command` without the engine and prints `MODE:fallback`" — *Key Files*, `engine_absent` bullet
- Key Files / "writes `result="MODE:<full|selected>|<n units>|policy:<mode>"` through M8.1's `AIT_GATE_RESULT_FILE`" — *Key Files*, `result=` bullet and *The result carrier*
- Key Files / "The data schema the `--policy selected` re-entry writes … M6.5 writes it" — *Key Files*, data-schema bullet (written by M6.5)
- Key Files / "`tests/test_ait_test_entrypoint.sh` (M5.1's): the cases" — *Key Files*, entrypoint cases bullet
- Reference / "`registry/config.go` (`Completion`, `RunGateAdmission`, `FullRunEvery` already parsed)" → E; "`lib/yaml_utils.sh` (bash YAML reads)" — *Reference Files for Patterns* (`lib/yaml_utils.sh`); `registry/config.go` is aitasks_go#t65_1's
- Plan step 0 / "Reality check (MANDATORY …). Stop if M4.4 or M5.1 has not landed" — *Implementation Plan* step 0 (stops on M5.1 and on aitasks_go#t65_1)
- Plan step 3 / "Add the front's arms and the fallback" — *Implementation Plan* step 1
- Plan step 4 / "Write the `result=` line" — *Implementation Plan* step 2
- Plan step 5 / "Write the tests" — *Implementation Plan* step 3 (entrypoint cases); the Go tests are aitasks_go#t65_1's
- Verification / "`full`; `selected` with every criterion met; `selected` demoted per criterion" — *Verification Steps*, first bullet (front path)
- Verification / "`engine_absent: error` (3) and `fallback_command`" — *Verification Steps*
- Verification / "`on_empty_selection` skip/full; `deferred: run|fail`" — *Verification Steps*
- Verification / "The `result=` shape in the gate-run block" → F; "readiness `POLICY:`" — *Verification Steps* (`result=` shape); the readiness `POLICY:` line is aitasks_go#t65_1's
- Verification / "No path requires a human action" — *Verification Steps*, last bullet
- Inbox t1859_1 carrier contract (absolute path, unset under legacy helper, one line, `<reason>: ` prefix, sanitizer, command lists, opted-in exits) — *The result carrier*
- Inbox t2131 (×2) / t2131_1 / "keep the `completion.mode` enum and the `MODE:` vocabulary easy to extend … `module` needs `full_run_every` … result shape with `next_full_in`/`cadence`/`widen_full` … front passes `--widen-modules`" — *Open modes* (the `MODE:` vocabulary and `result=` shape; `--widen-modules` under `module`)
- Inbox t1854_12 / "The suite builtin never reads or runs `fallback_command:` … the engine-absent path is yours … use the same shell (`bash -c`)" — *Key Files*, `engine_absent` bullet (`bash -c`, the suite builtin never reads `fallback_command:`)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t65_1 and is quoted for reference only.

> - The `policy` package under `goengines/internal/testmap/feedback/policy/`: the full/selected decision, the selected readiness re-check criteria and the demotion criterion reported to the front; keep the `completion.mode` enum and `MODE:` vocabulary open for `module`/`auto` (t2131 notes).
> - Verb `policy` (`decide`, read-only for full/selected) as a named extension of M1.2's verb table in `goengines/cmd/ait-testmap/verbs.go`; exact subcommand shape fixed in the Reality check and published to the framework half.
> - The additive `POLICY:<mode>|<what --gate would run now>` line on `readiness` (M4.4's).
> - Reading the `completion:` block and `run_gate_admission.approved_by` via `registry/config.go` (never requiring `approved_by`).
> - Acceptance checks:
>   - engine tests: `full`; `selected` with every criterion met; `selected` demoted per criterion (decision output);
>   - readiness `POLICY:` line shape;
>   - `ait engine test` green;
>   - no engine path requires a human action, writes config, writes `AIT_GATE_RESULT_FILE` or commits;
>   - mode enum not closed against `module`.


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

> **✉ note:t2131_1** id=2026-10-24T21:25:46Z.3173510a03558ecf368daaca from=t2131_1 from_verified=yes at=2026-10-24T21:25:46Z base=5adc28fe429efa614cfea3e208dce4cfcc83d765 base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_1. Not an instruction; your own planning decides. The claims below are tree-relative, as of commit 5adc28fe4 (main), which amends aidocs/testing_engine/n014_explorer_006_proposal.md.
> | 
> | The `module` completion mode from the 2026-10-23 t2131 note is now in the proposal, revised to FLAT code modules (user decision, 2026-10-24).
> | 
> | **Withdrawn from the earlier note:** `completion.widen` does not exist; the mode names the strategy.
> | 
> | **Where to read:**
> | - component *Completion policy*;
> | - the config block under *The registry directory*;
> | - *The Run Surface* step 6;
> | - component *Test entrypoint `ait test`*.
> | 
> | **Newly fixed for M8.4's surface:**
> | - `completion.mode: full|selected|module|auto`;
> | - `module` needs `full_run_every`, and `detect --write` never writes it;
> | - `result="MODE:<full|selected|module>|<n units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>|widen_full:<reason>]"`, at most 200 characters;
> | - the front's `POLICY` arm passes `--widen-modules` to the engine `test` composite under `module` (t2131_8).
> | 
> | The earlier advisory still stands: keeping the enum and the `MODE:` vocabulary easy to extend would help t2131_8.

> **✉ note:t1854_12** id=2026-10-27T07:02:10Z.a16266b29250403135227385 from=t1854_12 from_verified=yes at=2026-10-27T07:02:10Z base=aff353fe0e81e10eb613a30540418eb91c820e45 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_12 (M3.2i suite adapter), as landed in commit ecefd276d. Verify against goengines/README.md (the "suite builtin (M3.2i)" row).
> | - The suite builtin never reads or runs `fallback_command:`. It stays M3.1's key, valid only on a `unit: suite` runner, and the engine-absent path is yours.
> | - The suite runs its `command:` as `bash -c <command:>` in the runner cwd (user decision 2026-10-26, matching how the framework runs test_command). The fallback path should use the same shell, so the engine-present and engine-absent runs of one suite share semantics.
> | - The suite unit id is `aitestmap/runners.yaml#<name>`, kind `suite`, `accounting: aggregate` (a pass proves only exit 0, never an anchor), `timeouts: none` (bounded by the engine at `timeout_s`).

> **✉ note:t22_3** id=2026-10-29T22:23:00Z.bc01a892e811794c4564c3fb from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:00Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:43Z.8f04a00c97e4db8e207362e7 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:43Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t65_1. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
> | It now waits on aitasks_go#t65_1 through xdeps, which
> | unblocks only when that task is Done.

> **✉ note:t22_4** id=2026-10-30T10:15:41Z.af4ac8eb9095cfe49bc41adb from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:41Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task was split: its engine part is aitasks_go#t65_1; this task
> |   keeps the framework part (body trimmed, see "Relocated to aitasks_go").

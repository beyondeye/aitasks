---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, bash_scripts]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t62
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M5 — Run surface**: how an agent or a
person runs tests, in any repository state.

This module delivers `ait test` — a bash front in three modes (interactive,
completion, advisory) over the engine `test` composite, which still answers
correctly when no registry or no engine exists (`TESTMAP_ABSENT` delegation to
the project's `test_command`, `ENGINE_MISSING`); the computed project brief
(`ait test --howto`, a front over the engine verb `brief`); and the
fourteen-line `## Running Tests` section every agent reads at session start.

Only one piece is engine work: M5.2's `goengines/internal/testmap/brief`
package and the verb `brief [--md]`, now aitasks_go#t62. This task stays the M5
parent for the framework children: M5.1, the M5.2 front, and M5.3. It carries
the module's cut and the planning protocol; it does **not** restate the
specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M5 — Run surface`, then the *Components* subsections tagged
`(M5.x)`, then the narrative sections those components name.
*Architecture*, *Design decisions* and the *Invariants every module honours*
apply to every module.

**Acceptance:** the union of the framework components' test lists (*Module
Map — How to read it*): M5.1, the M5.2 front and M5.3. The M5.2 engine tests
belong to aitasks_go#t62.

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M5.1** `ait test` bash front | the modes, task resolution (incl. the new `aitask_lock.sh --list-mine` verb), the intake, `TESTMAP_ABSENT` delegation to `aitask_run_project_command.sh test_command`, `ENGINE_MISSING`, the advisory verdict and log, the exit contract, run-id prefixes, `UNANNOTATED_TEST` / `HINT`, the `POLICY` hook (M8.4 / M8.5 fill it; until then completion runs `--all`), the `ait` dispatcher arm, the five permission touchpoints, the result-carrier write, honouring the recursion guard, forwarding `--widen-modules`. Owns `.aitask-scripts/aitask_test.sh`, the `ait` `test)` arm, `--list-mine` in `aitask_lock.sh`, `tests/test_ait_test_entrypoint.sh` with the fake engine, the `tests/test_touchpoint_count_contract.sh` re-pin | M1.4 (t1852_4, landed), M4.1, M4.5 (aitasks_go#t61, not yet decomposed), M8.1 (t1859_1, landed), the recursion guard (t1854_7, landed) | D |
| **M5.2 front** Brief front | `ait test --howto [--md]` and the `ait testmap brief` pass-through, calling aitasks_go#t62's verb `brief [--md]`; tested against a fake `brief`. The engine verb and `internal/brief` are aitasks_go#t62 | M5.1, aitasks_go#t62 (`xdeps`) | D |
| **M5.3** Agent instructions seed | the fourteen-line `## Running Tests` section; the `tests/test_agent_instructions.sh` case. Owns that section of `seed/aitasks_agent_instructions.seed.md` and the test case | M5.1 | D |

## M5.1 contract notes (from the notes this task received; re-verify at the Reality check)

- **Engine probe** (t1852_4): `source "$SCRIPT_DIR/aitask_testmap.sh" --source-only`,
  then `rc=0; testmap_resolve_engine || rc=$?` (sourcing enables
  `set -euo pipefail`). rc 0 sets `TESTMAP_ENGINE_BIN`; rc 3 or 64 sets
  `TESTMAP_ENGINE_ERROR` to one line (`ENGINE_MISSING:<path>|<repair>`,
  `VERSION_INVALID:<file>`, `ENGINE_PATH_UNSAFE:<var>`, `USAGE:`). The repair
  text is `run 'ait setup' or set AIT_TESTMAP_BIN`. Do not guess from exit
  codes: the engine exits 3 for its own framework errors.
- **Diagnostics** go to stderr only; stdout is the engine's output.
  `AIT_TESTMAP_BIN` is the fake-engine hook (absolute path to an executable,
  no version check; a broken override never falls through).
- **No network fetch.** The `ait` dispatcher runs `check_for_updates` for
  every command not in its skip list; the `test)` arm needs the same skip-list
  entry as `testmap` (test it as `tests/test_testmap_shim.sh` W1/W2/W4 do).
- **Gate path** (t1859_1): `run_command_gate` exports `AIT_GATE_TASK_ID`,
  `AIT_GATE_RUN_ID` and `AIT_GATE_RESULT_FILE` for the command run only; the
  legacy helper exports only `AIT_GATE_TASK_ID`, and only with `--task-id`.
  Exit contract for an opted-in key: 0 pass, 1 fail, 2 skip, 3 →
  `command_errored`, 75 → `command_refused`, 64 and others → fail. The front
  writes one line to `AIT_GATE_RESULT_FILE`; it becomes the gate block's
  `result=`. The engine never writes it. Canonical statement: the
  `run_project_command_key()` docblock in `.aitask-scripts/lib/gate_verifier_lib.sh`.
- **Recursion guard** (t1854_7, t1854_2): enter through the guarded engine
  first and never strip or rewrite `AIT_TESTMAP_ACTIVE`. The front's tests
  drive fixture repositories (a temp git repo), never the real checkout.
- **`--widen-modules`** (t2131_1): the front parses the flag and forwards it
  unchanged to the engine `test` composite, alone or with `--explain`; no
  widening logic in the front. Keep flag parsing table-driven so a named
  extension adds one entry. Delivery is t2131_7's framework half.
- **POSIX sed** (t2095): when re-pinning `tests/test_touchpoint_count_contract.sh`,
  keep POSIX intervals (`\{1,\}`, `\{0,1\}`) or `sed -E`; GNU-only `\+` / `\?`
  break macOS.

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- `ait test` modes, the exit table, the advisory `VERDICT:` / `REASON:` —
  M5.1 → M8.4 (`tests_pass` through `test_command`), M9.1, M9.2, every agent.
- The computed project brief — through the front (`ait test --howto`) over
  aitasks_go#t62's verb; M6.1, M7.3 and M8.5 add lines to the engine side.
- The sentence every agent reads at session start — M5.3.

**Consumes:** the shim `ait testmap` (M1.4); the ranked list and the `test`
composite (M4.1, M4.5, engine output from aitasks_go#t61's children); the
verifier exit contract and the two environment variables (M8.1) for the
completion mode; `aitask_run_project_command.sh` and
`aitask_change_surface.sh` (exist today). The front's tests use the fake
engine, so they do not wait on engine timing.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- The `POLICY` hook in `aitask_test.sh` is left in place by M5.1 and filled by
  **M8.4** (`full` / `selected`, t1859_4) and **M8.5** (`auto`, t1859_5) via
  the engine verb `policy` (aitasks_go#t65_1, aitasks_go#t65_2); until then completion
  runs `--all`. This interim state is deliberate
  (`tradeoff_module_boundaries_cut_across_packages`) — do not pre-empt it.
- `tests/test_ait_test_entrypoint.sh` is M5.1's; M8.4 and M8.5 add their cases
  (incl. the `auto` matrix) to it.
- The workflow-seam data rows that name `ait test` are owned by M5.1
  (*Workflow seam — the data edits*); the procedure edits are **M9.1**'s.
- Invariant 8: every seam degrades to a printed skip where the engine or the
  registry is absent in advisory mode; a declared gate errors (exit 3) and
  never skips.

## Proposal edits (settle at the coarse pass)

- **One `RESULT:` shape.** *The Run Surface* has
  `RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>`,
  the `test` composite (M4.5) has `RESULT:pass|fail|skip|deferred|<run_id>`.
  The front passes the engine's line classes through, so M5.1 and M4.5 agree
  on one shape (with aitasks_go#t61's M4.5 child); t1855 writes it into the
  proposal.
- **Exit 2 vs Invariant 8.** The Run Surface exit table treats
  "2 = TESTMAP_ABSENT + no test_command → skip" as a skip under the opt-in,
  which reads against Invariant 8 (a declared gate errors, never skips). Also,
  `--gate` with no `aitestmap/` delegates to `test_command`, which in an
  onboarded project is `./ait test` itself (possible recursion). Settle both
  in the proposal.
- **M8.1 in M5.1's depends cell** (t1859 Dev 8): the cell names t1859_1.
- **Automation-first:** treat any proposal step that makes a human action a
  precondition as a candidate to automate; record the decision in the plan.

## Wiring (when the children exist)

- t1859_4 ← M5.1: an in-repo `depends:` edge.
- t1859_5: its M5.2 hold is engine-side and already encoded as
  aitasks_go#t65_2 → aitasks_go#t62; t1859_5 waits on aitasks_go#t65_2 through `xdeps`.
  Remove the M5.2 prose hold from its body.
- t2131_7 ← M5.1 (its framework half forwards `--widen-modules`): an in-repo
  `depends:` edge.
- t1853_7 ← M5.1: an in-repo `depends:` edge.
- The M5.2 front child ← aitasks_go#t62: `xdeps` with `xdeprepo: aitasks_go`.
- M5.1 ← M4.1 / M4.5: `xdeps` on aitasks_go#t61's children once they exist (see
  t1855); until then the child body records the prose hold "M4.1 / M4.5
  (aitasks_go#t61, not yet decomposed)".

`--deps` and `--xdeps` replace the whole list, so repeat the existing
entries. Flip a consumer to Ready only once nothing in its hold is left
unresolved; `xdeps` unblock only when the target is Done.

## Reading list in the proposal

- *Module Map* — `#### M5`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (wave D).
- *Components* — *Test entrypoint `ait test` (M5.1)*, *Agent brief (M5.2)*,
  *Agent instructions (M5.3)*.
- *The Run Surface* — whole section (*Forms*, *Resolution, in order*, *Output
  and exit contract*, *The two environment variables*, *`ait test --howto`*,
  *The generic instructions section*).
- *Running Tests*.
- *Data Flow* — *A task in steady state*, *A completion run under policy*.
- *Assumptions* / *Tradeoffs* — *Run surface and workflow (M5, M8, M9)*;
  *Open questions*.
- Framework rules that apply: `aidocs/framework/shell_conventions.md`; the
  permission-touchpoint contract pinned by
  `tests/test_touchpoint_count_contract.sh`.

## Planning and implementation protocol (binding for this task and every child)

This feature spans **ten parent tasks**, one per module of the proposal (see the
module → task map at the end). Since the t22 cutover the engine halves of
several parents live in beyondeye/aitasks_go. The modules are cut by ownership
of files, verbs and line protocols, so children of different parents meet on
the interfaces listed above. Two consequences are binding.

### 1. Coarse planning pass

- Plan this task through the normal workflow (`/aitask-pick` → planning). In
  the Complexity Assessment choose **"Yes, create child tasks"** and decompose
  into **one child task per row** of the table above (M5.1, the M5.2 front,
  M5.3; keep the `M5.<m>` id in the child name); let the workflow write the
  child plan files; at the child-task checkpoint choose **"Stop here"**.
  Start once the provider submodules the wave-earliest child consumes have
  landed (submodule-granular, never whole-parent), and implement in proposal
  wave order.
- Keep the coarse plan coarse. A child's plan records what the proposal fixes
  for that submodule — scope, owned files, provided and consumed interfaces,
  the component test lists that are its acceptance — and its wave. It does
  **not** design internals against providers that do not exist yet; that is
  the reality check's job (§2 below), and the child plan must say so.
- Express cross-module order in task data, not in prose: `depends:` inside
  this repository, `xdeps` (`xdeprepo: aitasks_go`) on aitasks_go tasks. When
  a provider has no child ids yet, the child body records the `M<n>.<m>`
  reference and its owner, and the edge is added with
  `./.aitask-scripts/aitask_update.sh --batch <child-id> --deps ...` (or
  `--xdeps ... --xdeprepo aitasks_go`) as soon as the ids exist.
- Parent-level `depends:` stays empty on purpose: module-level dependencies
  form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2) and would
  block wrongly; the real graph is acyclic only at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations
  from the proposal"** section of the plan. A wrong cut is fixed **in the
  proposal**, not patched in a plan (`assumption_modules_map_to_parent_tasks`).
  Send a note (`/aitask-note`) to every parent whose tables the change touches,
  including the aitasks_go halves (`--project aitasks_go`).

### 2. Reality check at child implementation time — a mandatory step in every child's plan

**Every child task's plan MUST carry an explicit "Reality check" step, executed
before any code is written, and its outcome MUST be recorded in the child's
plan file.** The step:

1. Re-reads the proposal's Module Map row for this submodule, its component
   subsections, and the row of every interface it consumes.
2. Inspects the **actual current state** of every provider it consumes and
   names the task and commit that landed each one. Engine providers are
   inspected in beyondeye/aitasks_go (or through the installed engine and
   `goengines/README.md` exports).
3. Tabulates every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decides, per difference: adapt; revise the coarse plan; or revise the
   proposal. Records the decision and its reason.
5. Sends a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or a decision breaks, hedging what cannot be proven.
6. Re-confirms that every file this child will touch is owned by this
   submodule, or that the edit lands as the owner's named extension.

A child whose plan lacks this step, or whose step is not recorded as executed,
is not implementing this task as specified.

## Acceptance

- `tests/test_ait_test_entrypoint.sh` passes with the fake engine, including
  the `brief` / `--howto` arm against a fake `brief`.
- `tests/test_touchpoint_count_contract.sh` is re-pinned with POSIX sed
  intervals.
- The `tests/test_agent_instructions.sh` case passes.
- The dispatcher makes no network fetch on `ait test`.
- The body points to aitasks_go#t62 (header above).

## Module → task map

| module | framework (aitasks) | engine (aitasks_go) |
|---|---|---|
| M1 — Engine foundation and distribution | t1852 (landed) | — |
| M2 — Registry and map model | t1853 | aitasks_go#t59 |
| M3 — Runners, scheduling and cost | t1854 | aitasks_go#t60 |
| M4 — Selection, freshness and feedback | t1855 (tracker) | aitasks_go#t61 |
| M5 — Run surface | t1856 | aitasks_go#t62 (M5.2 `brief`) |
| M6 — Onboarding | t1857 | aitasks_go#t63 |
| M7 — Agent review and author annotation | t1858 | aitasks_go#t64 |
| M8 — Completion policy and gates | t1859 | aitasks_go#t65 |
| M9 — Workflow integration, skills and documentation | t1860 | — |
| M10 — Rollout to the target repositories | t1861 | — |

All ten aitasks parents share the topic anchor of the M1 task, so the board's
By-Topic view shows the whole feature as one lane.

## Carried obligations (framework half)

- `## Goal` / "`ait test` — a bash front in three modes (interactive, completion, advisory) over the engine `test` composite" — *Goal* and the M5.1 row of *Submodules*
- `## Goal` / "`TESTMAP_ABSENT` delegation to the project's `test_command`, `ENGINE_MISSING`" — M5.1 row of *Submodules*
- `## Goal` / "the computed project brief (`ait test --howto`)" — M5.2 front row of *Submodules* over aitasks_go#t62's verb (*Relocated* below)
- `## Goal` / "the fourteen-line `## Running Tests` section" — M5.3 row of *Submodules*
- `## Goal` / "**Acceptance:** the union of the module's components' test lists" — *Goal* (acceptance line) and *Acceptance*; the M5.2 engine tests are aitasks_go#t62's
- `## Submodules` / M5.1 row (modes, task resolution incl. `aitask_lock.sh --list-mine`, intake, delegation, `ENGINE_MISSING`, advisory verdict / log, exit contract, run-id prefixes, `UNANNOTATED_TEST` / `HINT`, `POLICY` hook, `ait` arm, five touchpoints; owns `aitask_test.sh`, `tests/test_ait_test_entrypoint.sh`, the touchpoint re-pin) — M5.1 row of *Submodules* and *M5.1 contract notes*
- `## Submodules` / M5.2 row "`ait test --howto [--md]`, `ait testmap brief`" — M5.2 front row of *Submodules*
- `## Submodules` / M5.3 row "fourteen-line `## Running Tests` section; the `tests/test_agent_instructions.sh` case" — M5.3 row of *Submodules*
- `## Cross-module seams` › Provides / "`ait test` modes, the exit table, the advisory `VERDICT:` / `REASON:` — M5.1 → M8.4, M9.1, M9.2, every agent" — *Cross-module seams* → Provides
- `## Cross-module seams` › Provides / "sentence every agent reads at session start — M5.3" — *Cross-module seams* → Provides
- `## Cross-module seams` › Consumes / "the shim `ait testmap` (M1.4)" — *Cross-module seams* → Consumes; *M5.1 contract notes* (engine probe)
- `## Cross-module seams` › Consumes / "the ranked list and the `test` composite (M4.1, M4.5)" — *Cross-module seams* → Consumes (engine output from aitasks_go#t61's children; fake engine in tests); *Wiring* (M5.1 ← M4.1 / M4.5)
- `## Cross-module seams` › Consumes / "verifier exit contract and the two environment variables (M8.1)" — *Cross-module seams* → Consumes; *M5.1 contract notes* (gate path)
- `## Cross-module seams` › Consumes / "`aitask_run_project_command.sh` and `aitask_change_surface.sh`" — *Cross-module seams* → Consumes
- `## Cross-module seams` › Hooks / "The `POLICY` hook in `aitask_test.sh` … filled by M8.4 / M8.5; until then completion runs `--all` … do not pre-empt it" — *Cross-module seams* → Hooks (`POLICY` hook)
- `## Cross-module seams` › Hooks / "`tests/test_ait_test_entrypoint.sh` is M5.1's; M8.4 and M8.5 add their cases" — *Cross-module seams* → Hooks
- `## Cross-module seams` › Hooks / "workflow-seam data rows that name `ait test` are owned by M5.1; the procedure edits are M9.1's" — *Cross-module seams* → Hooks
- `## Cross-module seams` › Hooks / "Invariant 8: every seam degrades to a printed skip … a declared gate errors (exit 3) and never skips" — *Cross-module seams* → Hooks (Invariant 8); the engine verb's clean absent-registry exit is aitasks_go#t62's
- `## Reading list` / proposal sections — *Reading list in the proposal*
- `## Reading list` / "`aidocs/framework/shell_conventions.md`; the permission-touchpoint contract" — *Reading list in the proposal*, framework rules bullet
- Protocol §1 / "decompose into one child task per submodule row" — *Planning protocol* §1, first bullet (M5.1, M5.2 front, M5.3 children)
- Protocol §1 / "Keep the coarse plan coarse" — *Planning protocol* §1
- Protocol §1 / "Express cross-module order in task data" — *Planning protocol* §1 and *Wiring* (`depends:` here, `xdeps` to aitasks_go)
- Protocol §1 / "Parent-level `depends:` stays empty" — *Planning protocol* §1
- Protocol §1 / "Deviations … fixed in the proposal … Send a note" — *Planning protocol* §1, deviations bullet; *Proposal edits*
- Protocol §2 / Reality check steps 1–6 — *Planning protocol* §2
- `## Module → task map` — *Module → task map* (both repositories)
- Inbox t1852 / sequencing; goengines layout — *Planning protocol* §1 (submodule-granular sequencing, wave order)
- Inbox t1852_4 / "Probe for the engine … `testmap_resolve_engine`"; "All shim diagnostics go to STDERR"; "`AIT_TESTMAP_BIN` (your fake-engine hook)"; "Your `test)` arm needs the same [check_for_updates skip-list] entry" — *M5.1 contract notes*: engine probe, stderr diagnostics, fake-engine hook, skip-list entry
- Inbox t1853 / "Automation-first … treat any proposal step that makes a human action a precondition as a candidate to automate" — *Proposal edits*, automation-first bullet
- Inbox t1854 / "`RESULT:` has two shapes … M5.1 and M4.5 need one shape" — *Proposal edits*, `RESULT:` bullet
- Inbox t1859 / "Dev 8. M5.1's depends cell now includes M8.1 = t1859_1" — M5.1 row of *Submodules* (depends cell names M8.1 = t1859_1, landed) and *Proposal edits*
- Inbox t1859 / "Dev 2 … The bash front (aitask_test.sh) writes one line there [AIT_GATE_RESULT_FILE]" — *M5.1 contract notes*, gate path bullet (the front writes `AIT_GATE_RESULT_FILE`)
- Inbox t1859 / "The POLICY hook. M8.4 … M8.5 … via the new engine verb `policy`" — *Cross-module seams* → Hooks (`POLICY` hook filled by t1859_4 / t1859_5 via aitasks_go#t65_1 / aitasks_go#t65_2's verb)
- Inbox t1859 / "Wiring … add your child ids to t1859_4 (← M5.1) and t1859_5 (← M5.2)" — *Wiring*: t1859_4 ← M5.1 in-repo; the t1859_5 ← M5.2 hold is engine-side (aitasks_go#t65_2 → aitasks_go#t62)
- Inbox t1859 / observation "exit table treats '2 = TESTMAP_ABSENT + no test_command → skip' … reads against Invariant 8"; "`--gate` with no aitestmap/ delegates to `test_command` … (possible recursion)" — *Proposal edits*, exit 2 vs Invariant 8 bullet
- Inbox t1859_1 / gate-path env vars, legacy helper, exit contract, "M5.1's `depends:` should name `t1859_1`" — *M5.1 contract notes*, gate path bullet; M5.1 depends cell names t1859_1
- Inbox t2095 / "When t1856 re-pins this test, keep POSIX intervals" — *M5.1 contract notes*, POSIX sed bullet; *Acceptance*
- Inbox t1854_2 / "M5.1's `aitask_test.sh` should call or honour that guard **first**, and never strip the marker. Its own tests should drive fixture repositories"; "write M5.1's child edge to t1854_7" — *M5.1 contract notes*, recursion guard bullet (t1854_7 is landed, recorded in M5.1's depends cell)
- Inbox t1854_7 / "enters through the guarded engine first and never strips or rewrites `AIT_TESTMAP_ACTIVE` … tests should use fixture repositories" — *M5.1 contract notes*, recursion guard bullet
- Inbox t2131_1 / "`--widen-modules` … the front parses the flag and forwards it unchanged"; "wire the M5.1 id into t2131_7"; "keeping the front's flag parsing table-driven" — *M5.1 contract notes*, `--widen-modules` bullet; *Wiring* (t2131_7 ← M5.1)
- Inbox aitasks_go#t15 / coordination / freeze / re-home — The freeze is over; the engine half lives in aitasks_go#t62 (header above)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t62 and is quoted for reference only.

> - aitasks_go#t62 owns M5.2's engine half: the `goengines/internal/testmap/brief` package and the engine verb `brief [--md]`.
> - It emits the `TESTMAP:` / `RUNNER:` / `FULL_GATE:` / `GATE:` / `VERBS:` / `AXES:` / `RESOURCE:` / `NEW_TEST:` / `DOCS:` / `NOTES:` lines. `AXES:` comes via `axes.Of(reg)` plus `(*Table).Counts(reg.Units)` over committed `_scanned.yaml`, with no runner run.
> - It leaves additive seams for `ONBOARD_NEXT:` (M6.1), `AGENT_REVIEW:` (M7.3), and `KIND_PROPOSALS:` / `REVIEW_HUMAN:` / policy and cadence fields / `next full in` (M8.5).
> - Its plan carries the Reality-check step.
> - Acceptance:
>   - M5.2's component test list (the engine side) passes in aitasks_go CI.
>   - The `AXES:` line runs < 100 ms warm (per the t1853_4 note), with a bench where the proposal pins a budget.
>   - The brief reads only committed state.
>   - The verb is registered in the verb table with its exit contract, and the version / verb interface is pinned for the shim.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:32Z.6fa95739602f0cc016c18f5f from=t1852 at=2026-09-22T14:31:32Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.

> **✉ note:t1852_4** id=2026-10-05T14:12:24Z.128efd2074b7997a565f900e from=t1852_4 from_verified=yes at=2026-10-05T14:12:24Z base=1041d7d2a9841c15813c7c373a181e6b7757efeb base_branch=main dirty=yes host=omg16
>
> | For M5.1 (`aitask_test.sh`), from the t1852_4 (M1.4) reality check. Treat these as claims, not instructions. The shim is approved but UNCOMMITTED as of this note (main @ 95f0394cb plus the working tree), so verify it against the landed `.aitask-scripts/aitask_testmap.sh` header table ("Interfaces") when you plan M5.1.
> | 
> | 1. Probe for the engine, do not guess from exit codes. The engine itself exits 3 for framework errors (CONTRACT_MISMATCH and similar), so the shim's exit 3 is ambiguous.
> |    - Use `source "$SCRIPT_DIR/aitask_testmap.sh" --source-only`, then `rc=0; testmap_resolve_engine || rc=$?`. Guard the call this way: sourcing enables `set -euo pipefail`.
> |    - rc 0 sets `TESTMAP_ENGINE_BIN`.
> |    - rc 3 or rc 64 sets `TESTMAP_ENGINE_ERROR` to one full line:
> |      - `ENGINE_MISSING:<path>|<repair>`: the "engine absent" case, which gives interactive exit 3, advisory `VERDICT:skip REASON:testmap_absent`, and completion `completion.engine_absent`;
> |      - `VERSION_INVALID:<file>`;
> |      - `ENGINE_PATH_UNSAFE:<var>`;
> |      - `USAGE:` (for a bad AIT_ENGINE, with rc 64).
> |    - The repair text for the release slot is the proposal's exact text: `run 'ait setup' or set AIT_TESTMAP_BIN`.
> | 2. All shim diagnostics go to STDERR: `ENGINE_OVERRIDE:`, `ENGINE_REJECTED:`, `ENGINE_MISSING:`. Stdout is only ever the engine's own output. `AIT_TESTMAP_BIN` (your fake-engine hook) is accepted with NO version check, but it must be an absolute path to an executable file. A broken override never falls through to another tier.
> | 3. The `ait` dispatcher runs `check_for_updates` for every command not in its skip list. On a fresh cache it prints `Update available` to STDOUT, and on a stale or missing cache it starts a background curl to api.github.com. t1852_4 adds `testmap` to that skip list. Your `test)` arm needs the same entry, or `ait test` breaks the "gate run never performs a network fetch" assumption and can corrupt its line-protocol stdout. `tests/test_testmap_shim.sh` cases W1/W2/W4 show how to test it: run with a seeded cache, and with a fake curl on PATH captured by `$( … )`.

> **✉ note:t1853** id=2026-10-11T14:44:10Z.0db4d6d9abaf1a07f51d7f15 from=t1853 at=2026-10-11T14:44:10Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass (proposal commit 3bc0de8ac).
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1).

> **✉ note:t1854** id=2026-10-13T16:21:03Z.88728013db5459b22ac69108 from=t1854 at=2026-10-13T16:21:03Z base=6a3a81efc30577c762d42f815f3e95eac95b4e3f base_branch=main dirty=no host=omg16
>
> | Advisory, from the t1854 (M3) coarse pass (proposal at 6a3a81efc). It is a tree claim; verify it at your pass.
> | 
> | `RESULT:` has two shapes in the proposal:
> | - *The Run Surface → Output and exit contract*: `RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>` (M5.1's line).
> | - *Engine `test` composite (M4.5)*: `RESULT:pass|fail|skip|deferred|<run_id>`.
> | 
> | The front passes the engine's line classes through, so M5.1 and M4.5 need one shape. The same note went to t1855.
> | 
> | M3 also now homes `run`'s wave and per-id result lines in the *Runner contract* / *Scheduler* components. The line-protocol index has a new M3 row.

> **✉ note:t1859** id=2026-10-19T12:47:05Z.278852b976b8c707b0cfc0e7 from=t1859 at=2026-10-19T12:47:05Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. The proposal fix is commit bf32b336c. These are tree claims; verify them at your pass.
> | 
> | - **Dev 8.** M5.1's depends cell now includes M8.1 = t1859_1 (exit rows 75/3 → error, `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`). t1859_1 is Ready, wave A.
> | - **Dev 2.** run_command_gate also exports a result carrier, `AIT_GATE_RESULT_FILE`. The bash front (aitask_test.sh) writes one line there, and it becomes the gate block's `result=` (e.g. `MODE:selected|14|policy:auto|next_full_in:3`). The engine never writes it.
> | - **The POLICY hook.** M8.4 (t1859_4) fills its full/selected arms and M8.5 (t1859_5) its auto arm, via the new engine verb `policy`.
> | - **Wiring.** At your pass, add your child ids to t1859_4 (← M5.1) and t1859_5 (← M5.2) and lift their holds when empty.
> | - **Observation for your coarse pass; a design reading, unverified:**
> |   - the Run Surface exit table treats "2 = TESTMAP_ABSENT + no test_command → skip" as a skip under the opt-in, which reads against Invariant 8 (a declared gate errors, never skips);
> |   - `--gate` with no aitestmap/ delegates to `test_command`, which in an onboarded project is `./ait test` itself (possible recursion).

> **✉ note:t1859_1** id=2026-10-20T15:55:16Z.7a839abdcaf3563b89e0db52 from=t1859_1 from_verified=yes at=2026-10-20T15:55:16Z base=e2116c90aa17f9410b5d451c5eb87f70d6b47cf4 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1859_1 (M8.1), landed in e2116c90a on main. M5's children are not decomposed yet, so this note goes to the parent. Tree claims as of that commit; verify them in your reality check.
> | 
> | What `./ait test` (M5.1) can rely on:
> | 
> | - **Gate path** (`tests_pass` → `run_command_gate`): it exports, for the duration of the command run only:
> |   - `AIT_GATE_TASK_ID=<task>`;
> |   - `AIT_GATE_RUN_ID=<run-id>`;
> |   - `AIT_GATE_RESULT_FILE=<ABSOLUTE path>/.aitask-gates/<task>/<gate>_<run>.result`. One line written there becomes `result="<reason>: <line>"`; M8.4/M8.5 own the writer.
> | - **Legacy helper** (`aitask_run_project_command.sh <key> --task-id <id>`, used by Step 9 and aitask-qa): exports ONLY `AIT_GATE_TASK_ID`.
> |   - It never exports `AIT_GATE_RUN_ID` or `AIT_GATE_RESULT_FILE`.
> |   - Without `--task-id` it exports nothing.
> |   - Inherited values are passed through untouched; nobody clears them (Open question 4 default).
> | - **Exit contract** for an opted-in key (`gate_command_exit_contract: [test_command]`):
> |   - 0 pass, 1 fail, 2 skip;
> |   - 3 → `error`/`command_errored`, 75 → `error`/`command_refused` (verifier exit 3, retried within `max_retries`);
> |   - 64 and any other non-zero → `fail`.
> | - The helper reports an opted-in 75/3 as `VERDICT:error` + `REASON:command_refused|command_errored` with exit 3. A usage or infrastructure exit 3 has no `VERDICT:` line.
> | - Aggregation: an error short-circuits a command list like a fail.
> | 
> | The canonical statement is the `run_project_command_key()` docblock in `.aitask-scripts/lib/gate_verifier_lib.sh`. M5.1's `depends:` should name `t1859_1` (parent plan Dev 8).

> **✉ note:t1853_4** id=2026-10-21T09:40:05Z.9cfacc15969cf855393d1d2c from=t1853_4 from_verified=yes at=2026-10-21T09:40:05Z base=1518db7680e1a4a7d968ae489f0c67218d0f7f34 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_4 (M2.4 Axes and variants) as landed in 1518db768; re-verify in your Reality check. Tree-relative claims only.
> | 
> | For M5.2's `AXES:` brief line (facets and value counts, < 100 ms warm):
> | - Declared axes: `axes.Of(reg)` (goengines/internal/testmap/axes) after `registry.Load` — the axes package registers itself as a registry post-loader for `aitestmap/axes.yaml`; `Declared()` is false when the file is absent.
> | - Per-value variant counts without running any runner: `(*Table).Counts(reg.Units)` over the committed `_scanned.yaml` rows, which now carry `axis:` on variant-bearing rows. Undeclared values are not counted (check reports them as UNKNOWN_VARIANT).
> | - `ait-testmap axes --list` prints the same data from LIVE inputs (it runs the lister, like `check`): `AXIS_DECL:<axis>|<facets>|<values>|<variants>`, `AXIS_VALUE:...`, `AXIS_DECLS:<n>` — a different line family from the brief's `AXES:`.

> **✉ note:t2095** id=2026-10-21T11:44:59Z.dc85c0af2b1e6f38a7e9a59a from=t2095 from_verified=yes at=2026-10-21T11:44:59Z base=b08780dd4742b3e1f7ea605fd9785462de86f417 base_branch=main dirty=yes host=Darios-Mac-mini.local
>
> | tests/test_touchpoint_count_contract.sh:146 — t2095 (commit b08780dd4) changed this sed from `\([0-9]\+\)` to `\([0-9]\{1,\}\)`. BSD sed's BRE has no `\+`, so the old form made the "table lists exactly the live id/file pairs" check red on macOS (it got '').
> | 
> | When t1856 re-pins this test, keep POSIX intervals (`\{1,\}`, `\{0,1\}`) or use `sed -E`. GNU-only `\+` / `\?` would turn it red on macOS again. Advisory only; line number as of b08780dd4.

> **✉ note:t1854_2** id=2026-10-21T19:10:41Z.42cfa6a85fc731895986bba3 from=t1854_2 from_verified=yes at=2026-10-21T19:10:41Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Ids are as of the commit this note records.
> | - Recursion protection is now a runtime guard owned by t1854_7: `RUN_ERROR:recursion|<root>`, keyed on the git common dir. It uses the `AIT_TESTMAP_ACTIVE` marker plus a run-lock ancestry backstop for `env -i`.
> | - M5.1's `aitask_test.sh` should call or honour that guard **first**, and never strip the marker. Its own tests should drive fixture repositories, which the guard allows.
> | - The command-text check in the suite adapter (t1854_12) is only an early diagnostic.
> | - When you decompose, write M5.1's child edge to t1854_7, and to the adapters it runs through M4.5.
> | Details: parent t1854, section "M3.2 re-decomposition (2026-10-21)", and t1854_7's body.

> **✉ note:t1854_7** id=2026-10-23T07:52:07Z.000c41fffddbfb5ae5f2608f from=t1854_7 from_verified=yes at=2026-10-23T07:52:07Z base=ee468201fb47e48ead1fdab3019d6384bfaf8f23 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_7 (M3.2d recursion guard, G9), landed in commit ee468201f. Not checked against your plan; re-verify in your own Step 0.
> | 
> | - Every engine entry that starts runner processes (`runner.Run`, `runner.Load` -> run/scan/check) now refuses a nested entry for the same repository before any runner process starts: `RUN_ERROR:recursion|<root>`, exit 3; when the guard cannot establish the answer, `RUN_ERROR:recursion-unverifiable|<root>|<detail>`, exit 3.
> | - Detectors: the context (in-process), the `AIT_TESTMAP_ACTIVE` marker exported to every runner process, and holder records under `<git-common-dir>/ait-testmap/active/` matched against the caller's process ancestry (the `env -i` backstop).
> | - For M5.1 (`aitask_test.sh`): the task body's coordination item is that it enters through the guarded engine first and never strips or rewrites `AIT_TESTMAP_ACTIVE` (stripping it leaves only the ancestry backstop, which an orphaned descendant can escape until t1854_6's subreaper lands). Its own tests should use fixture repositories (a temp git repo), never the real checkout: a test run from under an active run of this repository is refused.
> | - Repository identity = realpath of `git rev-parse --git-common-dir`, so every worktree of the repo is the same repository. Exported Go helpers: `runner.Identity`, `runner.ActiveEnv`, `runner.FormatActive` / `ParseActive`.
> | - Details: goengines/README.md Interfaces row "recursion guard (M3.2d, G9)" and archived plan p1854_7 (Final Implementation Notes).

> **✉ note:t2131_1** id=2026-10-24T21:26:15Z.33bb4afb3600da1d9ce32654 from=t2131_1 from_verified=yes at=2026-10-24T21:26:15Z base=5adc28fe429efa614cfea3e208dce4cfcc83d765 base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_1. Not an instruction; your own planning decides. The claims below are tree-relative, as of commit 5adc28fe4 (main), which amends aidocs/testing_engine/n014_explorer_006_proposal.md.
> | 
> | t2131 (the test-map code-module tier) adds one public flag to the `ait test` bash front that M5.1 owns. Component *Test entrypoint `ait test`* now lists `--widen-modules` in the front's flag table, as M2.7's named extension:
> | - the front parses the flag and forwards it unchanged to the engine `test` composite, alone or with `--explain`;
> | - the front adds no widening logic, because a `WIDEN_FULL` outcome is already the composite's `--all` path;
> | - under `completion.mode: module`, the `POLICY` arm passes the same flag (t2131_8).
> | 
> | **Delivery and hold:**
> | - t2131_7 (`selector_module_widening`, Postponed) delivers the flag's parsing and forwarding, plus a fake-engine invocation case in `tests/test_ait_test_entrypoint.sh`.
> | - Its Dependency hold now names M5.1. When your coarse pass creates the M5 children, please wire the M5.1 id into t2131_7 with `aitask_update.sh --batch 2131_7 --deps "<existing>,<new>"`. That flag replaces the list, so keep `t2131_6` and the M4.1, M4.4 and M4.5 ids. Flip t2131_7 to Ready once nothing in its hold is left unresolved.
> | 
> | **Advisory:** keeping the front's flag parsing table-driven, so a named extension adds one entry, would keep t2131_7's edit to `aitask_test.sh` small.
> | 
> | Plans: `aiplans/p2131/p2131_7_selector_module_widening.md`.

> **✉ note:t15** id=2026-10-25T08:53:51Z.5470743d20bc0320e72f29b1 from=aitasks_go#t15 at=2026-10-25T08:53:51Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:22:43Z.ee0079a6e930e02c7d7fcc82 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:43Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:32Z.94568975ad63958f080d4ec4 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:32Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t62. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").

> **✉ note:t22_4** id=2026-10-30T10:15:24Z.fac01b9dc20dd8919d00fd7c from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:24Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task was split: its engine part is aitasks_go#t62; this task
> |   keeps the framework part (body trimmed, see "Relocated to aitasks_go").

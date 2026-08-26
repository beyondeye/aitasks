---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1605
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-08-25 17:41
updated_at: 2026-08-26 07:57
completed_at: 2026-08-26 07:57
---

## Origin

Risk-mitigation ("after") follow-up for t1605, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement — the legacy Step-9 prose path disagrees with the gate path.

From t1605's `## Risk`:

> The legacy Step-9 `verify_build` prose path keeps treating an opted-in command's
> exit 2 as a build failure, so a project sees two different answers for the same
> command depending on which path ran it.

t1605 named this in its plan's **Out of scope** section rather than dropping it
silently: it is agent prose across three skills plus their goldens, a different change
in kind from the shell-library fix.

## The divergence

t1605 taught `.aitask-scripts/lib/gate_verifier_lib.sh` an **opt-in, per-key** exit
contract: with a config key listed in `project_config.yaml`'s
`gate_command_exit_contract`, that key's command exiting **2** records a gate `skip`
("I did not run") instead of a `fail`. Any other non-zero exit is still a fail, and
over a command list a fail short-circuits while a skip does not.

That covers only the three **gate verifiers** (`build_verified`, `tests_pass`,
`lint`). The framework also runs `verify_build` a second way: as **agent
instructions** in the Step-9 legacy build-verification block, which says to run each
command sequentially and stop on the first failure. That path never routes through
`run_command_gate` and knows nothing about the contract.

So a project that opts in gets two different verdicts for the same command:

| path | command exits 2 |
|---|---|
| `build_verified` gate verifier | `skip` — satisfied, dependents released |
| legacy Step-9 `verify_build` prose | build failure |

### Where the prose lives

- `.claude/skills/task-workflow/SKILL.md` — Step 9's `verify_build` block (search for
  "If `verify_build` is a list of commands"). This is the SOURCE; the rendered
  per-profile variants and the tracked `-remote-` copies come from it.
- `.claude/skills/aitask-pickrem/SKILL.md` — its own Step-9-equivalent block.
- `aitask-pickweb` — same shape.

Per CLAUDE.md, the Claude Code version is edited first and the other agent trees are
re-rendered (`aitask_skill_rerender.sh` per profile), with goldens regenerated in the
same commit.

## Design points for planning

1. **Fix or document — decide explicitly.** Two defensible outcomes: teach the prose
   the contract, or state the divergence in the docs and accept it. Do not leave it
   implicit. If documenting, say *why* the legacy path is stricter.
2. **Agent prose cannot read a config file for free.** The gate path resolves the
   opt-in in bash. The prose path would need either a shell snippet the agent runs, or
   a small helper the agent calls that returns the effective verdict. Prefer the
   helper: it puts the contract in ONE place rather than restating the rule in three
   skill files that will drift. `run_command_gate`'s constants
   (`GATE_COMMAND_EXIT_CONTRACT_KEY`, `GATE_COMMAND_SKIP_EXIT`, `GATE_COMMAND_KEYS`)
   are already the canonical site.
3. **What "skip" means on the legacy path.** The gate path has a ledger status to
   record. The prose path has only "proceed" / "go back and fix". A skip there most
   likely means "proceed, and say so" — but say what gets recorded, since Step 9 also
   calls the Gate Recording Procedure with `build_verified`.
4. **Scope of the sweep.** Check whether `aitask-qa`'s test/lint execution
   (`test-execution.md`) has the same blind spot — it also runs `test_command` and
   `lint_command` directly.

## Acceptance

- One documented rule covers both paths, and the docs state which behavior applies
  where — no reader can conclude the two agree when they do not.
- If the prose path is taught the contract: an opted-in command exiting 2 does **not**
  send the agent back to fix a build, and an opted-in command exiting **1** still
  does — a reachable rejection probe, observed failing.
- The rule is expressed in one canonical place, not restated independently in
  `task-workflow`, `aitask-pickrem` and `aitask-pickweb`.
- Goldens under `tests/golden/procs/task-workflow/` are regenerated in the same commit
  as any SKILL.md edit, and the diff is reviewed rather than rubber-stamped.
- `./.aitask-scripts/aitask_skill_verify.sh` and
  `bash tests/test_skill_render_task_workflow.sh` pass.

## Reference

- t1605 — the gate-path fix; its plan documents the contract, the aggregation rule,
  and the "Out of scope" statement this task discharges.
- `.aitask-scripts/lib/gate_verifier_lib.sh` — `run_command_gate`'s docblock is the
  canonical statement of the contract.
- `aidocs/gates/aitask-gate-framework.md` — the verifier exit-code section.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T19:44:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-25T20:59:59Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-26T04:57:37Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:7ba2f960a452b7ed

> **✅ gate:risk_evaluated** run=2026-08-26T04:57:37Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1610/risk_evaluated_2026-08-26T04:57:37Z-risk_evaluated-a1.log`

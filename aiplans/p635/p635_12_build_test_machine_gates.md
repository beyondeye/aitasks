---
Task: t635_12_build_test_machine_gates.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_13_risk_evaluation_gate_integration.md, aitasks/t635/t635_14_profile_gate_declaration_unification.md, aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_20_stats_multistage_completion.md, aitasks/t635/t635_21_gate_ledger_merge_safety.md, aitasks/t635/t635_22_polish_board_inflight_empty_gate_state.md, aitasks/t635/t635_23_port_gate_skills_codex_opencode.md
Archived Sibling Plans: aiplans/archived/p635/p635_10_monitor_gate_status_column.md, aiplans/archived/p635/p635_11_orchestrator_verifier_contract.md, aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_5_ledger_driven_reentry.md, aiplans/archived/p635/p635_6_aitask_resume_skill.md, aiplans/archived/p635/p635_7_gate_aware_aitask_pick.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md, aiplans/archived/p635/p635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_12 — Build / Tests / Lint machine-gate verifiers (Phase 4)

## Context

The gate framework's **engine** shipped in t635_11 (`lib/gate_orchestrator.py` +
`aitask_run_gates.sh` + the `aitask-gate-template` contract). It runs a task's
declared machine-gate **verifiers** — but no concrete verifier exists yet: every
`verifier:` in `aitasks/metadata/gates.yaml` is empty (`""` = "no auto-run"). The
engine is therefore validated only against stub scripts.

**t635_12 lands the first real verifiers** (roadmap Phase 4 / decision D4): convert
the three project-command checks — **build**, **tests**, **lint** — into machine
gates whose commands come from `aitasks/metadata/project_config.yaml`
(`verify_build` / `test_command` / `lint_command`), with **no hardcoded project
commands**. It also wires task-workflow's Step 9 verify region to dispatch
`ait gates run` for tasks that declare these gates, keeping today's inline
`verify_build` behavior for tasks that don't. After this, `ait gates run` exercises
real verifiers end-to-end; t635_14 later makes tasks actually *declare* the gates.

**Confirmed scope (user, this session):**
- Ship **all three** verifiers + gates (build + tests + lint). Each **skips (exit
  2 = "evaluated, not applicable")** when its `project_config.yaml` command is
  null/absent — so `lint` ships now even though this repo has `lint_command: null`.
- task-workflow Step 9 wiring is **conditional**: route to `ait gates run` only
  when the task declares machine gates in `gates:`; inline path unchanged
  otherwise (dormant-but-tested now, goes live with t635_14).

**Scope-honesty note (no silent AC deviation):** the task text says ship
verifier *"skills"*. t635_11 **froze the orchestrator-facing contract as
resolvable COMMANDS, not skills** (`aitask-gate-<x>` → `.aitask-scripts/aitask_gate_<x>.sh`,
positional `<task-id> <attempt> <run-id>`, exit 0/1/2/3). These are therefore
shell verifier **scripts**, exactly as t635_11's "Notes for sibling tasks"
prescribe. The plan honors the frozen contract; the AC wording is reconciled in
the Final Implementation Notes.

## Design

### 1. New shared lib: `.aitask-scripts/lib/gate_verifier_lib.sh`

The three verifiers are near-identical (read a config key → run command(s) → log →
append → exit). Rather than three copy-pasted standalone scripts (the
`aitask-gate-template` shows a *standalone* copy-me script — illustrative, not
mandatory), encapsulate the core in one sourced lib and ship thin wrappers. This
follows the repo's "encapsulate workflow bash in a helper" / "derive don't
duplicate" conventions. The wrappers still honor the verifier contract verbatim.

```bash
# gate_verifier_lib.sh — shared core for project-command machine-gate verifiers.
# CONTRACT: the sourcing wrapper MUST set SCRIPT_DIR (dir of .aitask-scripts) before
# sourcing — run_command_gate calls "$SCRIPT_DIR/aitask_gate.sh". Guard so a direct
# source (a future test/helper) fails loudly instead of silently mis-resolving:
: "${SCRIPT_DIR:?gate_verifier_lib.sh requires SCRIPT_DIR (set by the wrapper) before sourcing}"

# run_command_gate <gate> <config_key> <verifier_name> <task-id> <attempt> <run-id>
#   Reads project_config.yaml <config_key> (scalar OR list), runs the command(s)
#   sequentially (stop on first failure), tees output to the sidecar log, appends
#   the terminal gate-run block via aitask_gate.sh, returns the contract code:
#   0=pass 1=fail 2=skip(no command configured) 3=error.
run_command_gate() {
    local gate="$1" config_key="$2" verifier_name="$3"
    local task_id="$4" attempt="$5" run_id="$6"
    local config="aitasks/metadata/project_config.yaml"
    local logdir=".aitask-gates/${task_id}"; mkdir -p "$logdir"
    local log="${logdir}/${gate}_${run_id}.log"

    # commands: list form (read_yaml_list handles inline [a,b] AND block) first;
    # fall back to scalar (read_yaml_field); drop empty / literal "null".
    local -a cmds=() raw=()
    if [[ -f "$config" ]]; then
        mapfile -t raw < <(read_yaml_list "$config" "$config_key" 2>/dev/null || true)
        if [[ ${#raw[@]} -eq 0 ]]; then
            local scalar; scalar="$(read_yaml_field "$config" "$config_key" 2>/dev/null || true)"
            [[ -n "$scalar" ]] && raw=("$scalar")
        fi
        local v; for v in "${raw[@]}"; do [[ -n "$v" && "$v" != "null" ]] && cmds+=("$v"); done
    fi

    local status code result
    if [[ ${#cmds[@]} -eq 0 ]]; then
        status=skip; code=2; result="no ${config_key} configured"
        printf '(no %s configured in %s; gate not applicable)\n' "$config_key" "$config" > "$log"
    else
        status=pass; code=0; result="all ${config_key} command(s) passed"; : > "$log"
        local c
        for c in "${cmds[@]}"; do
            printf '$ %s\n' "$c" >> "$log"
            if ! bash -c "$c" >> "$log" 2>&1; then
                status=fail; code=1; result="command failed: ${c}"; break
            fi
        done
    fi

    "$SCRIPT_DIR/aitask_gate.sh" append "$task_id" "$gate" "$status" \
        run="$run_id" attempt="$attempt" type=machine \
        verifier="$verifier_name" result="$result" log="$log" >/dev/null
    return "$code"
}
```

> **Impl note:** verify `read_yaml_list`/`read_yaml_field` behavior on a plain
> scalar value in `.aitask-scripts/lib/yaml_utils.sh` (lines ~48–141) before
> finalizing the read path — the fallback above is defensive for both shapes.
> Verifiers run from repo root (orchestrator cwd via `ait`), so the relative
> `aitasks/metadata/...` and `.aitask-gates/...` paths resolve correctly.

### 2. Three wrapper scripts (whitelisted helpers)

Each ~8 lines: shebang, `set -euo pipefail`, source `terminal_compat.sh` +
`yaml_utils.sh` + `gate_verifier_lib.sh`, call `run_command_gate` with `"$@"`.

| Script | gate | config key | registry `verifier:` |
|---|---|---|---|
| `.aitask-scripts/aitask_gate_build.sh` | `build_verified` | `verify_build` | `aitask-gate-build` |
| `.aitask-scripts/aitask_gate_tests_pass.sh` | `tests_pass` | `test_command` | `aitask-gate-tests-pass` |
| `.aitask-scripts/aitask_gate_lint.sh` | `lint` | `lint_command` | `aitask-gate-lint` |

(`resolve_verifier` maps `aitask-gate-tests-pass` → `aitask_gate_tests_pass.sh`
via `.replace("-","_")` — confirmed in `gate_orchestrator.py:257-269`.)

### 3. Registry: `aitasks/metadata/gates.yaml`

- `build_verified.verifier`: `""` → `aitask-gate-build` (gate already present;
  keep `max_retries: 1`, `timeout_seconds: 600`).
- Add gate `tests_pass`: `type: machine`, `blocks_dependents: true`,
  `verifier: aitask-gate-tests-pass`, `max_retries: 1`, `timeout_seconds: 600`.
- Add gate `lint`: `type: machine`, `blocks_dependents: false` (style check
  shouldn't gate dependents), `verifier: aitask-gate-lint`, `max_retries: 0`.
- Header comment: drop the "build/tests t635_12 … stay empty here" line now that
  build is populated; document the **skip-when-unconfigured** semantics (exit 2 =
  terminal-satisfied) for command-driven verifiers. Leave `unlocks:` ABSENT
  (linear default) per the absent-vs-`[]` rule.

### 4. task-workflow Step 9 wiring (source `.claude/skills/task-workflow/SKILL.md`, lines 553–565)

**Deterministic, engine-owned seam (revised per review concern 1).** task-workflow
is agent *instructions*, not code, so the branch must not depend on each agent
re-deriving "does this task declare a runnable machine gate?" from a registry
lookup (ambiguous around missing registry entries / human-only gates). Instead the
**orchestrator decides** and the workflow branches on one literal sentinel:

Replace the "Verify build (if configured)" block + its `{%- if record_gates %}`
recording with:

- **Dispatch the engine and capture BOTH its output and exit status** (it is a
  guaranteed no-op for a task that declares no `gates:` — `Engine.run()` returns
  early with no ledger append, confirmed `gate_orchestrator.py:395-396`):
  ```bash
  gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?
  ```
- **Step A — exit status FIRST (revised per review concern 1).** `Engine.run()`
  returns `0` for every *normal* outcome (a gate `fail`/`error` is a recorded
  result, not a process error), so a **nonzero `gates_rc` means infrastructure
  failure** — `ait`/wrapper error, task-resolution failure, Python unavailable,
  bad registry path, CLI-usage error (rc 2). On nonzero: **STOP and diagnose**
  (show `gates_out`); do **NOT** select either branch — in particular do not fall
  through to the inline path (the sentinel test is only meaningful on a clean exit).
- **Step B — only on `gates_rc == 0`, branch on the exact sentinel:**
  - `gates_out` contains the literal line **`No gates declared; nothing to do.`** →
    the task has not opted into gates (the common case today). Run the **existing**
    inline `verify_build` block + `{%- if record_gates %}` manual `build_verified`
    recording, **unchanged**.
  - Otherwise → the engine ran the declared gates and **recorded each run itself**.
    Parse its report lines and act per status (revised per review concern 2 — cover
    `error` and `blocked:`, not just pass/fail/skip/pending):
    - `pass` / `skip` → satisfied; continue.
    - `fail` (`  <gate>: fail …`) → ordinary gate failure: inspect
      `./ait gate log <task_id> <gate>`, diff vs base; if caused by this task, fix
      and re-run `./ait gates run <task_id>`; if pre-existing/unrelated, record
      `./ait gate fail <task_id> <gate> --reason "…"` and log in Final Impl Notes.
    - **`error`** (`  <gate>: error …`) **or a malformed-correction line**
      (`  ⚠ <gate>: malformed …`) → **verifier INFRASTRUCTURE failure** (launch
      failure, timeout, exit 3, status/exit mismatch), NOT an ordinary gate result:
      **diagnose the verifier/config** (its log, the command, timeout) — do not
      "fix the code" as if it were a `fail`, do not record a manual pass, and do
      **not** proceed to archival until the verifier itself runs cleanly.
    - **`blocked: …`** lines (engine reports these when an unlocked gate cannot run /
      none remain runnable — `blocked: upstream … not satisfied`, `blocked: exhausted …`,
      `blocked: no verifier configured`) → surface and diagnose; an `exhausted`/`upstream`
      block means the gate is **unsatisfied**, so do **not** silently treat it as
      satisfied or proceed. (`blocked: pending human signal` → route to the human
      sign-off action, never self-signal.)
    - `pending` (human) → surface, never self-signal.
    - **Do NOT** also run the manual "Record build-verified gate" step — the engine
      already appended it (no double-record).

This removes the agent-side registry interpretation entirely: the "did this task opt
into gates?" decision is the engine's `if not declared` check, surfaced as a single
machine-checkable sentinel **guarded by a clean exit**; declared-gate dispatch
distinguishes ordinary gate results from verifier infrastructure failures.
Backward-compatible (no task declares `gates:` yet); the orchestrator becomes the
single recorder once gates are declared (t635_14).

### 5. `applies_when` — explicitly DEFERRED

Open question 3 (change-scoped gate skip) is **not** pulled in. The exit-2 "no
command configured → skip" path already covers "not applicable" for build/tests/
lint. Change-scoped predicate skipping is only motivated by `docs_updated`
(t635_19); `applies_when` stays a framework-doc proposal. Recorded as a deferral
note in the plan + gates.yaml header.

### 6. Whitelist new helpers (4 framework touchpoints, mirror t635_11 format)

Add `aitask_gate_build.sh`, `aitask_gate_tests_pass.sh`, `aitask_gate_lint.sh`:
- `seed/claude_settings.local.json` — `"Bash(./.aitask-scripts/aitask_gate_<n>.sh:*)"`
- `.codex/rules/default.rules` and `seed/codex_rules.default.rules` —
  `prefix_rule(pattern = ["./.aitask-scripts/aitask_gate_<n>.sh"], decision = "allow", justification = "Aitasks helper script")`
- `seed/opencode_config.seed.json` — `"./.aitask-scripts/aitask_gate_<n>.sh *": "allow"`

(`gate_verifier_lib.sh` is sourced, never invoked → not whitelisted.) The live
`.claude/settings.local.json` is intentionally NOT edited (t635_11 precedent: the
auto-mode self-modification guard blocks it) — note in Final Impl Notes that the
user may add the 3 entries to their live settings.

### 7. Tests (same commit)

- **`tests/test_gate_verifiers.sh`** (new; mirror `tests/test_gate_orchestrator.sh`
  scaffold — `asserts.sh`, `mktemp` fixture with `aitasks/metadata/`, `cd` fixture
  + `TASK_DIR=…`, run real scripts from `$PROJECT_DIR/.aitask-scripts`). Cases per
  verifier (parametrized over build/tests/lint):
  1. command passes (`true`) → exit 0, ledger `pass`, sidecar log exists.
  2. command fails (`false`) → exit 1, ledger `fail`.
  3. command null/absent → exit 2, ledger `skip`, log says "not applicable".
  4. list of commands, middle one fails → exit 1, stops early (assert a later
     command's side effect did NOT happen).
  5. sidecar log captures command stdout/stderr.
  - **Integration**: registry with `build_verified.verifier: aitask-gate-build` +
    `verify_build: "true"` + `gates: [build_verified]` → orchestrator records `pass`.
  - **Retry — assert the DURABLE contract (revised per review concern 3), not the
    blocked-reason string.** Fixture is a plain `mktemp` dir (NOT a git repo), so
    `code_digest()` returns `None` and the stopping-heuristic is inert by design →
    the **retry budget alone** governs deterministically. With `verify_build:
    "false"` + `max_retries: 1`, assert: **exactly two terminal `fail` runs recorded
    for `build_verified`** and the gate is **NOT satisfied** (final derived status =
    `fail`, not `pass`/`skip`). Do not assert the human-readable "exhausted (… )"
    wording (it varies with digest availability and is not part of the contract).
- **Step 9 seam — behavioral assertion (revised per review concern 2).** Two layers,
  because render goldens only prove the markdown renders:
  - **Engine-primitive test** (in `test_gate_verifiers.sh` or `test_gate_cli_wiring.sh`):
    a task with **no** `gates:` → `ait gates run <id>` prints the exact sentinel
    `No gates declared; nothing to do.` AND appends nothing to the task file; a task
    with `gates: [build_verified]` (verifier configured) → `ait gates run <id>`
    records a `build_verified` terminal block. This proves the primitive the Step 9
    branch keys on actually discriminates the two cases. Also assert the
    **exit-status guard**: an infrastructure failure (e.g. nonexistent task-id /
    bad `--registry` path via the wrapper) yields a **nonzero** exit and does NOT
    print the `No gates declared` sentinel — confirming Step A (nonzero ⇒ stop, do
    not fall through to the inline branch). The `error`-status path (stub verifier
    exit 3 → engine reports `error`, rc still 0) is already covered by
    `test_gate_orchestrator.sh`.
  - **Render-content assertion** (extend/author a task-workflow render test): the
    rendered Step 9 of a `record_gates`-enabled profile MUST contain both
    `ait gates run` and the literal sentinel `No gates declared; nothing to do.`,
    so the instructions and the engine sentinel cannot silently drift apart.
- **`tests/lib/test_scaffold.sh`**: only touch if a fake-repo-baseline test sources
  `gate_verifier_lib.sh` (the new tests build their own fixtures → likely no-op;
  verify during impl).

### 8. Goldens + skill-verify (same commit)

Editing `.claude/skills/task-workflow/SKILL.md` (Jinja source) requires
regenerating its rendered per-profile variants and goldens:
- Re-render: `./.aitask-scripts/aitask_skill_render.sh task-workflow --profile <p> --agent claude` for each profile (or the bulk rerender driver — see
  `aidocs/framework/skill_authoring_conventions.md` "Regenerate goldens after any
  …closure edit").
- Regenerate the task-workflow render goldens under `tests/`.
- `./.aitask-scripts/aitask_skill_verify.sh` must pass.
- No new skill is added (verifiers are scripts), so no new skill golden dirs.
- Cross-agent port: closure/script changes auto-render Claude→Codex/OpenCode; no
  agent-specific surface is touched → no separate port task expected.

### 9. Docs

- The `gates.yaml` header comment (updated in §3) is the in-tree current-state doc.
- **Project Configuration table** in `.claude/skills/task-workflow/SKILL.md`
  (lines 754–758) (revised per review concern 4): its "Used in" column currently
  scopes `test_command`/`lint_command` to "aitask-qa Step 4" and `verify_build` to
  "Step 9" only. After this task these keys also drive machine-gate verifiers (and
  thus archival readiness once tasks declare gates). Update the column:
  - `verify_build` → `Step 9; build_verified gate`
  - `test_command` → `aitask-qa Step 4; tests_pass gate`
  - `lint_command` → `aitask-qa Step 4; lint gate`
  (This is a Jinja-source edit → re-render + goldens, same as §8.)
- Website docs deferred to **t635_18** (comprehensive gates config sweep) — no
  gates config reference page exists yet to update, and the roadmap assigns that
  surface to t635_18. (Confirm no existing page mentions verifier scripts during
  impl; if one does, update it per current-state-only rule.)

## Files

**New:** `lib/gate_verifier_lib.sh`, `aitask_gate_build.sh`,
`aitask_gate_tests_pass.sh`, `aitask_gate_lint.sh` (all under `.aitask-scripts/`),
`tests/test_gate_verifiers.sh`.
**Edited:** `aitasks/metadata/gates.yaml`, `.claude/skills/task-workflow/SKILL.md`
(+ rendered variants + goldens), the 4 whitelist files, possibly
`tests/test_gate_cli_wiring.sh` / `tests/lib/test_scaffold.sh`.

## Verification

1. `shellcheck .aitask-scripts/aitask_gate_build.sh .aitask-scripts/aitask_gate_tests_pass.sh .aitask-scripts/aitask_gate_lint.sh .aitask-scripts/lib/gate_verifier_lib.sh`
2. `bash tests/test_gate_verifiers.sh` (+ `tests/test_gate_orchestrator.sh`,
   `tests/test_gate_cli_wiring.sh` still pass).
3. `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens regenerated.
4. **Live smoke:** temp task with `gates: [build_verified]`, set
   `verify_build: "true"` in a scratch `project_config.yaml`, run
   `./ait gates run <id>` → ledger shows `build_verified pass`; flip to `false`
   → repeated runs leave `build_verified` **unsatisfied** (terminal `fail`, budget
   spent — exact blocked-reason text not asserted); unset → `skip`. Also confirm a
   task with **no** `gates:` prints `No gates declared; nothing to do.` and appends
   nothing. `./ait gate log <id> build_verified` prints the sidecar.
5. Step 9 (Post-Implementation) handles cleanup / archival / merge.

## Follow-up task (created post-approval, per user request)

This task keeps the inline `verify_build` path as a **transitional fallback** (the
convergence seam in §4 runs it only for tasks that haven't opted into gates). Once
gate declaration becomes the universal path (t635_14), that fallback — and the
project-side `verify_build` configuration surface — become dead weight and should
be removed. Create a follow-up task (a new **t635 child**, e.g. `t635_24`, sibling
auto-deps disabled → explicit `depends: [t635_14]`) scoped to:

- **Remove the legacy inline `verify_build` procedure** from task-workflow Step 9
  (the non-gate branch added in §4) and the `{%- if record_gates %}` manual
  `build_verified` recording — leaving `ait gates run` as the single verify path.
- **Replace the settings-TUI `verify_build` configuration** with new ad-hoc
  **gate-configuration UIs** in the settings TUI (configure declared gates +
  per-gate verifier/registry settings) instead of the standalone `verify_build`
  field. (Impl must first locate where `verify_build` is configured in the settings
  TUI / `project_config` editor — discover the surface, then redesign it as gate
  config. See `aidocs/framework/tui_conventions.md`.)
- **Update documentation** to the post-removal current state: the Project
  Configuration table (drop/redefine `verify_build`), any verify-build prose, and
  the gates config reference — coordinate with t635_18's website sweep.
- Gated on `t635_14` (cannot remove the fallback until every task declares gates);
  references `t635_12` (this task, which introduced the gate path) and t635_14.

Per the bidirectional-link convention, when this follow-up is created, add a
reverse pointer from `t635_14` (and note it in t635_18's docs-sweep scope) so the
removal is visible from the unification task. **`risk_mitigations_planned` is
unaffected — this is a user-requested convergence follow-up, not a risk mitigation;
it is created explicitly during implementation (Step 7/8), not via the
risk-mitigation procedure.**

## Risk

### Code-health risk: medium
- The task-workflow Step 9 edit modifies `.claude/skills/task-workflow/SKILL.md`,
  a **central shared workflow** consumed (by reference) by every task-based skill;
  a mis-scoped conditional or a Jinja/golden regression could affect the verify
  region for all tasks · severity: medium · → mitigation: the new branch is
  **dormant** (gated on a `gates:` declaration no task carries yet, so the inline
  path runs unchanged in every current case) + golden regeneration + `aitask_skill_verify.sh` + the existing render goldens guard against drift (in-plan).
- Populating `gates.yaml` verifiers ripples to the shared orchestrator + ledger
  TUIs · severity: low · → mitigation: verifiers default to **skip (exit 2)** when
  unconfigured, so no current task's behavior changes; `test_gate_orchestrator.sh`
  + the new integration test assert the engine still derives correctly (in-plan).
- Shared `gate_verifier_lib.sh` is new surface, but additive and unit-tested via
  the three wrappers · severity: low · → mitigation: `test_gate_verifiers.sh` +
  `shellcheck` (in-plan).

### Goal-achievement risk: medium
- The verifiers are exercised here only against **test fixtures + a manual smoke
  test**; the real declared-gate flow goes live with t635_14, so end-to-end
  validation against a real verifier in a real pick is deferred · severity: medium
  · → mitigation: **t1015** (`gate_orchestrator_live_verify`, manual_verification)
  already exists — filed by t635_11 and explicitly coordinated to run **after
  t635_12 lands a concrete verifier**. t635_12 IS that verifier; no new mitigation
  task is needed — add a coordination note to t1015 that the build/tests/lint
  verifiers landed.
- The scalar-vs-list `project_config.yaml` read path rests on `read_yaml_list` /
  `read_yaml_field` behavior on a plain scalar · severity: low · → mitigation:
  defensive list→scalar fallback + a dedicated "single string command" test case
  (in-plan); confirm helper behavior before finalizing.

### Planned mitigations
- The goal-achievement "no live declared-gate exercise until t635_14" risk is
  covered by the **pre-existing t1015** (after t635_12). No new before/after task
  is created; instead, per the bidirectional-link convention, add a coordination
  note to `aitasks/t635/t635_17...`/the t1015 task file recording that t635_12's
  verifiers are ready for it to drive. (`risk_mitigations_planned: false` — no new
  task.)

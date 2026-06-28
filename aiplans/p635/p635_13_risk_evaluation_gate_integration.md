---
Task: t635_13_risk_evaluation_gate_integration.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_14_profile_gate_declaration_unification.md, aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_20_stats_multistage_completion.md, aitasks/t635/t635_21_gate_ledger_merge_safety.md, aitasks/t635/t635_22_polish_board_inflight_empty_gate_state.md, aitasks/t635/t635_23_port_gate_skills_codex_opencode.md, aitasks/t635/t635_24_remove_legacy_verify_build_path.md
Archived Sibling Plans: aiplans/archived/p635/p635_10_monitor_gate_status_column.md, aiplans/archived/p635/p635_11_orchestrator_verifier_contract.md, aiplans/archived/p635/p635_12_build_test_machine_gates.md, aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_5_ledger_driven_reentry.md, aiplans/archived/p635/p635_6_aitask_resume_skill.md, aiplans/archived/p635/p635_7_gate_aware_aitask_pick.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md, aiplans/archived/p635/p635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_13 — Wrap risk evaluation as the `aitask-gate-risk` machine gate

## Context

The risk-evaluation feature (t884) ships **standalone**: at the end of planning it
assesses two risk dimensions, authors a `## Risk` section in the plan, and (post-approval,
Step 7) writes `risk_code_health` / `risk_goal_achievement` to the task frontmatter. It is
deliberately *not* coupled to the gate framework — a forward-compat seam was documented in
`aidocs/gates/risk-evaluation-gate-seam.md` to be realized once the framework landed.

The framework has now landed: the orchestrator + verifier contract shipped in **t635_11**,
and sibling **t635_12** built the first concrete verifiers (build/tests/lint) plus the
Step 9 seam where task-workflow dispatches `ait gates run`. The registry
(`aitasks/metadata/gates.yaml`) already declares `risk_evaluated` with an **empty verifier
reserved for this task** (`# verifier populated by t635_13`).

**This task = the risk-specific conversion**, mirroring t635_12 exactly: build + register
the `aitask-gate-risk` verifier (dormant until a task declares the gate). The verifier
encodes the seam's satisfied-condition: the `## Risk` plan section exists (evidence) **and**
both frontmatter levels are written (verdict).

**Producer vs. checker — the risk feature is two parts, and the gate is only the checker.**
The plan-quality value lives in the **producer**: the planning-time Risk Evaluation Procedure
(`risk-evaluation.md`) that *authors* the `## Risk` section and threads the two levels, run
**before plan approval**. A machine verifier can only *check* artifacts after the fact — it
can never *produce* the assessment. So `aitask-gate-risk` is the **verify-time checker** of
what the producer made; it does **not** and must **not** replace the producer. t635_13 leaves
the producer completely untouched (it edits no skill markdown — the `risk_evaluation` Jinja
toggle keeps running the procedure at planning exactly as today). The consequence for t635_14
is a hard requirement (see §5): when it swaps the `risk_evaluation` toggle for gate
*declaration*, **declaring `risk_evaluated` must continue to drive the planning-time producer
before plan approval**, not only the Step 9 checker — otherwise the gate is kept but the
plan-quality benefit is lost.

**Scope boundary (explicit).** The roadmap and t635_14's definition assign the
profile→gate-declaration unification — retiring the duplicated `risk_evaluation` Jinja
toggle and making profiles *declare* the gate — to **t635_14** (`depends: [t635_12, t635_13]`).
So this task does **not** touch any skill markdown, the Jinja toggle, or the Step 7
self-recording. The Step 9 seam already dispatches `ait gates run` generically (t635_12), so
no task-workflow change is needed — the new verifier is consumed by the existing dispatch
once t635_14 declares the gate.

**Task-definition amendment (no silent AC deviation).** t635_13's own `## Scope` currently
says "Replace the standalone profile-gated dispatch with the gate wrapper … Regenerate
goldens and run `aitask_skill_verify.sh` in the same commit." That wording predates the
t635_12/t635_14 split crystallizing: the dispatch *replacement* (declaration + Jinja-toggle
retirement) is t635_14's job, and since **this child edits no skill markdown there are no
goldens to regenerate**. Rather than quietly archive with that scope unmet, **§0 amends the
task's `## Scope`** to state the correct split explicitly (build+register the verifier here;
dispatch replacement in t635_14) and mark goldens N/A. This mirrors t635_12, which shipped
dormant verifiers and reconciled its AC wording rather than dropping it.

## Design

### 0. Amend t635_13's task `## Scope` (no silent AC deviation)

Edit `aitasks/t635/t635_13_risk_evaluation_gate_integration.md`'s `## Scope` so the deliverable
matches reality, committed via `./ait git`:
- Reframe "Replace the standalone profile-gated dispatch with the gate wrapper" → **build and
  register the `aitask-gate-risk` verifier** (the gate wrapper) so the orchestrator can run it;
  the *dispatch replacement* (profiles declaring the gate, retiring the `risk_evaluation` Jinja
  toggle, transitioning the Step 7 self-record) is **t635_14**.
- Replace "Regenerate goldens and run `aitask_skill_verify.sh` in the same commit" → note that
  this child **edits no skill markdown, so there are no goldens to regenerate**;
  `aitask_skill_verify.sh` is run only to confirm a clean no-op.
- Keep the existing "t635_14 retires the duplicated Jinja toggle" note.

This makes the scope decision visible in the task file itself, not just the plan/Final Notes.

### 1. New verifier — `.aitask-scripts/aitask_gate_risk.sh`

A **state-inspection** verifier (not a project-command gate), so it is *standalone* and does
**not** reuse `run_command_gate` from `lib/gate_verifier_lib.sh` (that lib is project-command
specific — reads a `project_config.yaml` key and runs it). It follows the
`aitask-gate-template` copy-me scaffold and the frozen contract
(`<task-id> <attempt> <run-id>`; exit `0=pass 1=fail 3=error`; append a terminal block whose
status matches the exit code; sidecar log at `.aitask-gates/<task-id>/<gate>_<run-id>.log`).

Reuses existing helpers from `lib/task_utils.sh`: `resolve_task_file` (parent/child + archive
fallback, `die`s if not found), `resolve_plan_file` (returns the path, empty string if none),
and `read_yaml_field` (pulled in via `yaml_utils.sh`).

```bash
#!/usr/bin/env bash
# aitask_gate_risk.sh - verifier for the `risk_evaluated` gate.
#
# A STATE-inspection gate (not a project-command gate): it runs no command. It
# checks that the planning-time risk evaluation produced its two durable artifacts —
#   1. EVIDENCE — a `## Risk` section in the task's PLAN file containing BOTH
#      authored subsections `### Code-health risk` and `### Goal-achievement risk`
#      (a bare/empty `## Risk` heading is NOT sufficient evidence), and
#   2. VERDICT — the `risk_code_health` / `risk_goal_achievement` frontmatter levels
#      (each high|medium|low) on the TASK file.
# The subsection/level patterns mirror the format authored by
# .claude/skills/task-workflow/risk-evaluation.md (kept in lockstep — no drift).
# It does NOT enforce a "no unmitigated high risk" policy: the seam leaves that
# "per whatever policy the framework adopts" and the task Goal defines satisfied as
# section + levels present; blocking high-risk tasks is a deferred future policy.
# See aidocs/gates/risk-evaluation-gate-seam.md.
#
# Verifier contract: <task-id> <attempt> <run-id>; exit 0=pass 1=fail 3=error.
# No exit-2/skip path: a task that DECLARES this gate has opted into risk
# evaluation, so the artifacts MUST exist — their absence is a real fail (opt-OUT
# is "do not declare the gate", wired by t635_14).
# Resolved by the orchestrator from registry `verifier: aitask-gate-risk`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"   # -> terminal_compat, yaml_utils (read_yaml_field),
                                         #    resolve_task_file, resolve_plan_file

GATE="risk_evaluated"
VERIFIER="aitask-gate-risk"
task_id="${1:?task-id required}"
attempt="${2:?attempt required}"
run_id="${3:?run-id required}"

logdir=".aitask-gates/${task_id}"
mkdir -p "$logdir"
log="${logdir}/${GATE}_${run_id}.log"

# Resolve the task file (holds the frontmatter levels). Unresolvable => verifier
# error (3): the orchestrator handed us an id whose file is gone — infra, not fail.
task_file="$(resolve_task_file "$task_id" 2>/dev/null)" || {
    printf 'ERROR: could not resolve task file for %s\n' "$task_id" > "$log"
    exit 3
}

valid_level() { [[ "$1" == high || "$1" == medium || "$1" == low ]]; }

plan_file="$(resolve_plan_file "$task_id" 2>/dev/null || true)"
code_health="$(read_yaml_field "$task_file" risk_code_health 2>/dev/null || true)"
goal_achv="$(read_yaml_field "$task_file" risk_goal_achievement 2>/dev/null || true)"

reasons=()
if [[ -z "$plan_file" || ! -f "$plan_file" ]]; then
    reasons+=("no plan file found for $task_id")
else
    grep -q '^## Risk'                  "$plan_file" || reasons+=("plan has no '## Risk' section: $plan_file")
    grep -q '^### Code-health risk'      "$plan_file" || reasons+=("plan '## Risk' missing '### Code-health risk' subsection")
    grep -q '^### Goal-achievement risk' "$plan_file" || reasons+=("plan '## Risk' missing '### Goal-achievement risk' subsection")
fi
valid_level "$code_health" || reasons+=("risk_code_health not high|medium|low (got: '${code_health:-<empty>}')")
valid_level "$goal_achv"   || reasons+=("risk_goal_achievement not high|medium|low (got: '${goal_achv:-<empty>}')")

{
    printf 'Risk-evaluation gate for %s\n' "$task_id"
    printf 'plan file: %s\n' "${plan_file:-<none>}"
    printf 'risk_code_health: %s\n' "${code_health:-<empty>}"
    printf 'risk_goal_achievement: %s\n' "${goal_achv:-<empty>}"
} > "$log"

if [[ ${#reasons[@]} -eq 0 ]]; then
    status=pass; code=0; result="risk evaluated (## Risk section + both levels present)"
    printf 'RESULT: pass\n' >> "$log"
else
    status=fail; code=1; result="risk evaluation incomplete: ${reasons[0]}"
    { printf 'RESULT: fail\n'; printf '  - %s\n' "${reasons[@]}"; } >> "$log"
fi

"$SCRIPT_DIR/aitask_gate.sh" append "$task_id" "$GATE" "$status" \
    run="$run_id" attempt="$attempt" type=machine \
    verifier="$VERIFIER" result="$result" log="$log" >/dev/null
exit "$code"
```

Evidence check (concern 4): the `## Risk` heading alone is **not** sufficient — the verifier
also requires both authored subsections `### Code-health risk` and `### Goal-achievement risk`,
so an empty or headingless `## Risk` block fails. The `^## Risk` line reuses the exact pattern
of the existing `planning.md` "Risk-section guard" (no drift), and the subsection/level
patterns mirror `risk-evaluation.md` Step 3's authored template (lines 89–97). The level check
rejects empty/garbage values, so the gate verifies the **verdict** (the two levels) on top of
the **evidence** (the two dimension subsections) — not just "some text".

### 2. Registry — populate `risk_evaluated.verifier` in `aitasks/metadata/gates.yaml`

- Line 86: `verifier: ""` → `verifier: aitask-gate-risk`.
- Line 85 comment → describe current behavior (state-inspection: passes when the `## Risk`
  plan section exists and both frontmatter levels are written; no skip path).
- Header comment (lines 26–31): drop "the risk (t635_13) … stay empty until then"; note risk
  is now populated and is a **state-inspection** verifier (distinct from the command-driven
  build/tests/lint that skip via exit 2). Leave `blocks_dependents: false` and `max_retries: 0`
  unchanged — risk is a deterministic pre-code state check (a re-run can't flip without
  re-planning, and it must not block dependents).

### 3. Whitelist the new helper — 4 touchpoints (mirror t635_12 exactly)

Append one line for `aitask_gate_risk.sh` to each, copying the `aitask_gate_build.sh` entry's
format:
- `seed/claude_settings.local.json` — `"Bash(./.aitask-scripts/aitask_gate_risk.sh:*)",`
- `seed/codex_rules.default.rules` — `prefix_rule(pattern = ["./.aitask-scripts/aitask_gate_risk.sh"], decision = "allow", justification = "Aitasks helper script")`
- `.codex/rules/default.rules` — same `prefix_rule` line
- `seed/opencode_config.seed.json` — `"./.aitask-scripts/aitask_gate_risk.sh *": "allow",`

Do **not** edit the live `.claude/settings.local.json` (t635_12 precedent: the auto-mode
self-modification guard blocks it). Note in Final Impl Notes that the user may add the entry
to their live settings.

### 4. Tests — new `tests/test_gate_risk_verifier.sh`

Mirror `tests/test_gate_verifiers.sh` scaffold (`asserts.sh`, `mktemp` fixture with
`aitasks/metadata` + `aiplans`, run the real script with `cd $dir` and `TASK_DIR`/`PLAN_DIR`
set). Helpers: `write_task` (frontmatter with/without the two risk fields), `write_plan`
(plan with/without a `## Risk` section, at the parent `aiplans/p<id>_x.md` or child
`aiplans/p<parent>/p<parent>_<child>_x.md` path), `run_verifier` (sets `RC`).

Cases:
1. **pass** — plan has `## Risk`, task has both levels valid → exit 0, ledger `status=pass`,
   sidecar log exists.
2. **fail: no `## Risk` section** — both levels present, plan lacks the section → exit 1, `fail`.
2b. **fail: `## Risk` present but a dimension subsection missing** — plan has `## Risk` +
   `### Code-health risk` but no `### Goal-achievement risk`; both levels present → exit 1,
   `fail` (pins the strengthened evidence check, concern 4).
3. **fail: missing field** — plan has `## Risk` + both subsections, task missing
   `risk_goal_achievement` → exit 1.
4. **fail: no plan file** — task has both levels, no plan file on disk → exit 1, log "no plan file".
5. **fail: invalid level** — `risk_code_health: bogus` → exit 1 (level-validation bites).
6. **child task path** — `10_2` style id (task in `aitasks/t10/`, plan in `aiplans/p10/`),
   pass case → exit 0 (covers parent+child resolution).
7. **sidecar capture** — pass log names the plan file + both levels; fail log lists the reason.
8. **orchestrator integration + reconciliation hygiene (concern 3)** — registry with
   `risk_evaluated.verifier: aitask-gate-risk` + `gates: [risk_evaluated]`; valid artifacts →
   `ait gates run` reports `risk_evaluated: pass` and records it. Because the verifier
   self-appends a terminal block AND the engine reconciles terminal status from the exit code
   (`reconcile_terminal`, gate_orchestrator.py:309–330: matching status → **no-op**; mismatch
   → a fresh-run `error` "malformed:" correction), assert explicitly:
   - exactly **one** terminal (non-`running`) `risk_evaluated` marker for the run-id,
   - the recorded status equals the exit-code-implied status (`pass`),
   - **no** `status=error` marker and **no** `malformed:` correction line in the ledger.
   Repeat for the missing-section case → exactly one terminal `fail`, no `error`/`malformed`.
   (Mirrors `test_orchestrator_integration`; proves the self-append agrees with the exit code
   so the engine adds neither a duplicate nor a correction.)

### 5. Coordination note → t635_14 (bidirectional link)

Per the bidirectional-link convention, add a "Coordination (from t635_13)" block to
`aitasks/t635/t635_14_profile_gate_declaration_unification.md` recording, as **required
acceptance criteria** for t635_14, what it must handle when it makes profiles *declare*
`risk_evaluated`:
- **Declaration must keep the planning-time PRODUCER alive** (the core requirement). The risk
  feature is a planning-time producer (the `risk-evaluation.md` procedure authoring `## Risk` +
  threading the levels, run **before plan approval**) plus a verify-time checker (this gate).
  When t635_14 retires the `risk_evaluation` Jinja toggle in favor of declaring `risk_evaluated`,
  declaring the gate MUST continue to trigger that planning-time procedure before plan approval
  — the gate must not become a post-planning-only check. Dropping the producer would keep the
  gate but lose the plan-quality benefit (and the verifier would just fail, with no `## Risk`).
- **Drive declaration from the same `risk_evaluation` opt-in** — a task declares the gate iff
  risk evaluation is enabled (producer and checker are toggled together), else the verifier
  fails spuriously (no `## Risk` section / no levels) or the producer runs with nothing
  checking it.
- **No double-recording of `risk_evaluated`** (concern 2). Today task-workflow Step 7
  self-records `risk_evaluated` (guarded by `record_gates`); once a task *declares* the gate,
  the Step 9 orchestrator also records it → two terminal `risk_evaluated` runs for one
  planning approval. t635_14 MUST close this with a **structural fix** (preferred over a
  fragile test-only invariant): gate the Step 7 self-record so it fires **only when the task
  does not declare `risk_evaluated`** (the orchestrator owns recording for declared gates) —
  making the double-record impossible rather than merely detected. **Plus a regression test**
  asserting that for a task declaring `risk_evaluated`, exactly **one** terminal
  `risk_evaluated` run is recorded across a full plan→implement→Step 9 pass (no Step 7 + Step 9
  duplicate). This is the risk analog of t635_24 removing build's inline self-record.

Commit the t635_14 edit with `./ait git`.

### 6. Explicitly out of scope / rejected (scope-honesty)

- **No task-workflow / skill markdown change** → no goldens, no `.md.j2` edits. The Step 9
  seam already dispatches `ait gates run` generically.
- **No Jinja `risk_evaluation` toggle retirement, no profile→declaration wiring, no Step 7
  self-record removal** — all t635_14. The planning-time producer (the `risk-evaluation.md`
  procedure that authors `## Risk` + threads the levels before plan approval) stays exactly as
  today, still gated by the `risk_evaluation` toggle — this child only adds the checker.
- **No "no unmitigated high risk" blocking policy** in the verifier. The seam leaves this
  "per whatever policy the framework adopts"; the task Goal defines satisfied = section +
  levels written. Blocking high-risk tasks would wrongly gate legitimate ones. Deferred as a
  possible future policy (note in the verifier's comment + Final Impl Notes).
- **No `run_command_gate` extension / no `gate_verifier_lib.sh` change** — risk is bespoke;
  folding it into the project-command lib would muddy that lib's single purpose. Standalone is
  cleaner.
- **No `skip` (exit 2) path** — a declared risk gate has opted in, so artifacts must exist;
  opt-out is non-declaration (t635_14).

## Files

- **New:** `.aitask-scripts/aitask_gate_risk.sh`, `tests/test_gate_risk_verifier.sh`.
- **Edited:** `aitasks/t635/t635_13_risk_evaluation_gate_integration.md` (§0 scope amendment);
  `aitasks/metadata/gates.yaml` (populate verifier + comments); the 4 whitelist files;
  `aitasks/t635/t635_14_profile_gate_declaration_unification.md` (coordination note, §5).

## Verification

1. `shellcheck .aitask-scripts/aitask_gate_risk.sh`
2. `bash tests/test_gate_risk_verifier.sh` (all pass)
3. Regression: `bash tests/test_gate_verifiers.sh` and `bash tests/test_gate_orchestrator.sh`
   still pass (registry change is additive — only an empty field is populated).
4. **Live smoke:** temp task declaring `gates: [risk_evaluated]` with a plan containing a
   `## Risk` section and both frontmatter levels → `./ait gates run <id>` → ledger shows
   `risk_evaluated pass`; remove the section → `fail`; `./ait gate log <id> risk_evaluated`
   prints the sidecar.
5. No skill surface touched, so `aitask_skill_verify.sh` / goldens are unaffected (will run it
   to confirm a clean no-op).
6. **Step 9 (Post-Implementation)** handles cleanup / archival / merge.

## Risk

### Code-health risk: low
- The change is purely **additive**: one new standalone verifier, populating one already-
  reserved registry field, a new test file, 4 one-line whitelist appends, and a coordination
  note. No existing code path is modified · severity: low · → mitigation: none needed
  (additive; `test_gate_risk_verifier.sh` + shellcheck + regression of the existing gate tests).
- `gates.yaml` is read by the shared orchestrator, so populating risk's `verifier:` makes
  `ait gates run` dispatch it for any task that declares `risk_evaluated` — but **no task
  declares it yet** (dormant until t635_14), exactly the t635_12 pattern · severity: low ·
  → mitigation: orchestrator-integration test + regression of `test_gate_orchestrator.sh` (in-plan).

### Goal-achievement risk: low
- The verifier is exercised here only against **fixtures + a manual smoke test**; the real
  declared-gate flow goes live with t635_14, so end-to-end validation in a real pick is
  deferred · severity: medium · → mitigation: **t1015** (`gate_orchestrator_live_verify`, the
  pre-existing live-verify MV task) already covers this for all Phase-4 verifiers; the seam
  doc's satisfied-condition is encoded verbatim and the `^## Risk` check reuses the planning
  guard's exact pattern (no drift). No new mitigation task needed.

### Planned mitigations
- The "no live declared-gate exercise until t635_14" risk is covered by the **pre-existing
  t1015** (no new before/after task). Risk-specific coordination is captured in the t635_14
  note (§5). `risk_mitigations_planned: false`.

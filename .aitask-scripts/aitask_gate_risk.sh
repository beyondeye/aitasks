#!/usr/bin/env bash
# aitask_gate_risk.sh - verifier for the `risk_evaluated` gate.
#
# A STATE-inspection gate (not a project-command gate): it runs no command. It
# checks that the planning-time risk evaluation produced its two durable artifacts —
#   1. EVIDENCE - a `## Risk` section in the task's PLAN file containing BOTH
#      authored subsections `### Code-health risk` and `### Goal-achievement risk`
#      (a bare/empty `## Risk` heading is NOT sufficient evidence), and
#   2. VERDICT - the `risk_code_health` / `risk_goal_achievement` frontmatter levels
#      (each high|medium|low) on the TASK file.
# The subsection/level patterns mirror the format authored by
# .claude/skills/task-workflow/risk-evaluation.md (kept in lockstep - no drift).
#
# This verifier is only the CHECKER of what the planning-time risk-evaluation
# PRODUCER made; it does NOT (and must NOT) replace that producer, which authors
# the `## Risk` section before plan approval and is the source of the plan-quality
# benefit. It does NOT enforce a "no unmitigated high risk" policy: the seam leaves
# that "per whatever policy the framework adopts" and the task Goal defines
# satisfied as section + levels present; blocking high-risk tasks is a deferred
# future policy.
# See aidocs/gates/risk-evaluation-gate-seam.md.
#
# Verifier contract: <task-id> <attempt> <run-id>; exit 0=pass 1=fail 3=error.
# No exit-2/skip path: a task that DECLARES this gate has opted into risk
# evaluation, so the artifacts MUST exist - their absence is a real fail (opt-OUT
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
# error (3): the orchestrator handed us an id whose file is gone - infra, not fail.
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

#!/usr/bin/env bash
# aitask_risk_mitigation_landed.sh - Decide whether a task's plan must be
# force-reverified because a "before" risk-mitigation task landed after the
# plan was last verified.
#
# Used by the task-workflow planning.md Step 6.0a. Reads the task's
# `risk_mitigation_tasks` frontmatter list; for each, resolves its archived
# task file and reads `completed_at`; compares against the plan's most-recent
# `plan_verified` timestamp. Emits the IDs that landed AFTER that timestamp so
# the caller can both force verify mode and read exactly those mitigations'
# archived plans during re-verification.
#
# This check is meaningful ONLY when risk evaluation produced
# `risk_mitigation_tasks` (populated by the risk-mitigation follow-up
# procedure). Outside that context it is a pure no-op → FORCE_VERIFY:0.
#
# Usage:
#   aitask_risk_mitigation_landed.sh <task_file> <plan_file>
#
# Output (exit 0):
#   FORCE_VERIFY:<0|1>
#   LANDED:<id>|<completed_at>   # one line per mitigation that landed after the
#                               # last verification (only when FORCE_VERIFY:1)
#
# Timestamps (`completed_at`, `plan_verified`) share the fixed
# `YYYY-MM-DD HH:MM` format, so a lexicographic string comparison is a correct
# chronological comparison.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"

PLAN_VERIFIED="$SCRIPT_DIR/aitask_plan_verified.sh"
QUERY_FILES="$SCRIPT_DIR/aitask_query_files.sh"

usage() {
    cat <<'EOF'
Usage:
  aitask_risk_mitigation_landed.sh <task_file> <plan_file>
EOF
}

main() {
    local task_file="${1:-}"
    local plan_file="${2:-}"
    [[ -z "$task_file" || -z "$plan_file" ]] && { usage >&2; die "requires <task_file> <plan_file>"; }
    [[ -f "$task_file" ]] || die "task file not found: $task_file"

    # No plan file → nothing has been verified yet; `decide` already returns
    # VERIFY in that case, so there is nothing to force. No-op.
    [[ -f "$plan_file" ]] || { echo "FORCE_VERIFY:0"; return 0; }

    # 1. Read risk_mitigation_tasks; absent/empty → pure no-op.
    local ids
    ids=$(read_yaml_list "$task_file" "risk_mitigation_tasks" || true)
    if [[ -z "${ids//[[:space:]]/}" ]]; then
        echo "FORCE_VERIFY:0"
        return 0
    fi

    # 2. Most-recent plan_verified timestamp (lexicographic max).
    local last_ts="" ts
    while IFS='|' read -r _ ts; do
        [[ -z "$ts" ]] && continue
        if [[ -z "$last_ts" || "$ts" > "$last_ts" ]]; then
            last_ts="$ts"
        fi
    done < <("$PLAN_VERIFIED" read "$plan_file")
    # No prior verification → `decide` already returns VERIFY. No-op.
    if [[ -z "$last_ts" ]]; then
        echo "FORCE_VERIFY:0"
        return 0
    fi

    # 3-4. Collect every mitigation whose archived completed_at is later than
    # the last verification.
    local landed=()
    local id resolved arch_path completed
    while IFS= read -r id; do
        id="${id//[[:space:]]/}"
        [[ -z "$id" ]] && continue
        resolved=$("$QUERY_FILES" archived-task "$id" 2>/dev/null || true)
        # Not yet archived (mitigation hasn't landed) → skip.
        [[ "$resolved" == ARCHIVED_TASK:* ]] || continue
        arch_path="${resolved#ARCHIVED_TASK:}"
        [[ -f "$arch_path" ]] || continue
        completed=$(read_yaml_field "$arch_path" "completed_at")
        [[ -z "$completed" ]] && continue
        if [[ "$completed" > "$last_ts" ]]; then
            landed+=("$id|$completed")
        fi
    done <<< "$ids"

    if [[ ${#landed[@]} -eq 0 ]]; then
        echo "FORCE_VERIFY:0"
        return 0
    fi

    echo "FORCE_VERIFY:1"
    printf 'LANDED:%s\n' "${landed[@]}" | sort
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
esac
main "$@"

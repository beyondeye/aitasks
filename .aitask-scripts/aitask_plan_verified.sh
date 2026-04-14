#!/usr/bin/env bash
# aitask_plan_verified.sh - Read, append, and decide on plan verification
# metadata stored in a plan file's YAML header under `plan_verified:`.
#
# The helper owns all counting/staleness/decision logic so the task-workflow
# skill markdown stays trivial (parse KEY:value lines, branch on DECISION).
#
# Usage:
#   aitask_plan_verified.sh read <plan_file>
#   aitask_plan_verified.sh append <plan_file> <agent>
#   aitask_plan_verified.sh decide <plan_file> <required> <stale_after_hours>
#
# Output (exit 0):
#   read:   one `<agent>|<timestamp>` line per entry (empty if none)
#   append: silent on success
#   decide: 8 KEY:value lines in fixed order — TOTAL, FRESH, STALE, LAST,
#           REQUIRED, STALE_AFTER_HOURS, DISPLAY, DECISION

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

usage() {
    cat <<'EOF'
Usage:
  aitask_plan_verified.sh read <plan_file>
  aitask_plan_verified.sh append <plan_file> <agent>
  aitask_plan_verified.sh decide <plan_file> <required> <stale_after_hours>
EOF
}

# --- Date portability helpers ---

compute_cutoff() {
    local hours="$1"
    if date -d "1 hour ago" +%s >/dev/null 2>&1; then
        date -d "${hours} hours ago" +%s
    else
        date -v-"${hours}"H +%s
    fi
}

parse_ts() {
    local ts="$1"
    if date -d "1 hour ago" +%s >/dev/null 2>&1; then
        date -d "$ts" +%s 2>/dev/null || return 1
    else
        date -jf '%Y-%m-%d %H:%M' "$ts" +%s 2>/dev/null || return 1
    fi
}

# --- read <plan_file> ---
# Emit one "<agent>|<timestamp>" line per entry in the plan's plan_verified list.
cmd_read() {
    local plan_file="${1:-}"
    [[ -z "$plan_file" ]] && die "read requires a plan file"
    [[ -f "$plan_file" ]] || die "plan file not found: $plan_file"

    local in_header=0
    local header_count=0
    local in_pv=0
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "---" ]]; then
            header_count=$((header_count + 1))
            if [[ $header_count -eq 1 ]]; then
                in_header=1
                continue
            fi
            if [[ $header_count -eq 2 ]]; then
                break
            fi
        fi
        [[ $in_header -eq 0 ]] && continue

        if [[ "$line" == "plan_verified: []" ]]; then
            in_pv=0
            continue
        fi
        if [[ "$line" == "plan_verified:" ]]; then
            in_pv=1
            continue
        fi

        if [[ $in_pv -eq 1 ]]; then
            if [[ "$line" =~ ^[[:space:]]+-[[:space:]]+(.+)[[:space:]]@[[:space:]]+([0-9]{4}-[0-9]{2}-[0-9]{2}[[:space:]][0-9]{2}:[0-9]{2})[[:space:]]*$ ]]; then
                printf '%s|%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
            elif [[ -z "$line" ]] || [[ ! "$line" =~ ^[[:space:]] ]]; then
                in_pv=0
            fi
        fi
    done < "$plan_file"
}

# --- append <plan_file> <agent> ---
# Insert a new verification entry into the plan's YAML header.
cmd_append() {
    local plan_file="${1:-}"
    local agent="${2:-}"
    [[ -z "$plan_file" ]] && die "append requires a plan file"
    [[ -z "$agent" ]] && die "append requires an agent string"
    [[ -f "$plan_file" ]] || die "plan file not found: $plan_file"

    local ts
    ts=$(date '+%Y-%m-%d %H:%M')
    local new_entry="  - $agent @ $ts"

    local tmp
    tmp=$(mktemp "${TMPDIR:-/tmp}/ait_plan_verified_XXXXXX.md")

    local in_header=0
    local header_count=0
    local state="none"
    local pv_seen=0
    local inserted=0
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "---" ]]; then
            header_count=$((header_count + 1))
            if [[ $header_count -eq 1 ]]; then
                in_header=1
                printf '%s\n' "$line" >> "$tmp"
                continue
            fi
            if [[ $header_count -eq 2 ]]; then
                if [[ $pv_seen -eq 0 ]]; then
                    printf '%s\n' "plan_verified:" >> "$tmp"
                    printf '%s\n' "$new_entry" >> "$tmp"
                    inserted=1
                elif [[ "$state" == "found_pv" || "$state" == "in_pv_list" ]]; then
                    printf '%s\n' "$new_entry" >> "$tmp"
                    inserted=1
                    state="done"
                fi
                in_header=0
                printf '%s\n' "$line" >> "$tmp"
                continue
            fi
        fi

        if [[ $in_header -eq 1 ]]; then
            if [[ "$line" == "plan_verified: []" ]]; then
                pv_seen=1
                printf '%s\n' "plan_verified:" >> "$tmp"
                printf '%s\n' "$new_entry" >> "$tmp"
                inserted=1
                state="done"
                continue
            fi
            if [[ "$line" == "plan_verified:" ]]; then
                pv_seen=1
                state="found_pv"
                printf '%s\n' "$line" >> "$tmp"
                continue
            fi
            if [[ "$state" == "found_pv" || "$state" == "in_pv_list" ]]; then
                if [[ "$line" =~ ^[[:space:]]+- ]]; then
                    state="in_pv_list"
                    printf '%s\n' "$line" >> "$tmp"
                    continue
                elif [[ -z "$line" ]] || [[ ! "$line" =~ ^[[:space:]] ]]; then
                    printf '%s\n' "$new_entry" >> "$tmp"
                    inserted=1
                    state="done"
                    printf '%s\n' "$line" >> "$tmp"
                    continue
                fi
            fi
        fi

        printf '%s\n' "$line" >> "$tmp"
    done < "$plan_file"

    if [[ $inserted -eq 0 ]]; then
        rm -f "$tmp"
        die "failed to insert plan_verified entry into: $plan_file"
    fi

    mv "$tmp" "$plan_file"
}

# --- decide <plan_file> <required> <stale_after_hours> ---
# Emit 8 KEY:value lines describing whether verification can be skipped.
cmd_decide() {
    local plan_file="${1:-}"
    local required="${2:-}"
    local stale_hours="${3:-}"
    [[ -z "$plan_file" ]] && die "decide requires a plan file"
    [[ -z "$required" ]] && die "decide requires a required count"
    [[ -z "$stale_hours" ]] && die "decide requires stale_after_hours"
    [[ "$required" =~ ^[0-9]+$ ]] || die "required must be a positive integer: $required"
    [[ "$stale_hours" =~ ^[0-9]+$ ]] || die "stale_after_hours must be a positive integer: $stale_hours"

    if [[ ! -f "$plan_file" ]]; then
        printf 'TOTAL:0\nFRESH:0\nSTALE:0\nLAST:NONE\nREQUIRED:%s\nSTALE_AFTER_HOURS:%s\nDISPLAY:No plan file found.\nDECISION:VERIFY\n' \
            "$required" "$stale_hours"
        return 0
    fi

    local cutoff_ts
    cutoff_ts=$(compute_cutoff "$stale_hours")

    local fresh=0
    local stale=0
    local total=0
    local last_entry="NONE"
    local last_ts=0
    local agent
    local timestamp
    local entry_ts

    while IFS='|' read -r agent timestamp; do
        [[ -z "$agent" ]] && continue
        total=$((total + 1))
        entry_ts=""
        entry_ts=$(parse_ts "$timestamp" 2>/dev/null || true)
        [[ -z "$entry_ts" ]] && continue
        if [[ $entry_ts -ge $cutoff_ts ]]; then
            fresh=$((fresh + 1))
        else
            stale=$((stale + 1))
        fi
        if [[ $entry_ts -gt $last_ts ]]; then
            last_ts=$entry_ts
            last_entry="$agent @ $timestamp"
        fi
    done < <(cmd_read "$plan_file")

    local display
    local decision
    if [[ $total -eq 0 ]]; then
        decision="VERIFY"
        display="No prior verifications found — entering verify mode."
    elif [[ $fresh -ge $required ]]; then
        decision="SKIP"
        display="Plan has $fresh fresh verification(s) (most recent: $last_entry). Skipping verification."
    else
        decision="ASK_STALE"
        display="Plan has $total verification(s) ($fresh fresh, $stale stale). Required: $required."
    fi

    printf 'TOTAL:%d\nFRESH:%d\nSTALE:%d\nLAST:%s\nREQUIRED:%s\nSTALE_AFTER_HOURS:%s\nDISPLAY:%s\nDECISION:%s\n' \
        "$total" "$fresh" "$stale" "$last_entry" "$required" "$stale_hours" "$display" "$decision"
}

# --- Dispatcher ---

cmd="${1:-}"
shift || true
case "$cmd" in
    read)   cmd_read "$@" ;;
    append) cmd_append "$@" ;;
    decide) cmd_decide "$@" ;;
    ""|help|-h|--help) usage ;;
    *) die "Unknown subcommand: $cmd" ;;
esac

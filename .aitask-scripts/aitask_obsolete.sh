#!/usr/bin/env bash
# aitask_obsolete.sh - `ait obsolete`: the obsolescence layer (t1981_6).
#
# Advisory "obsolete score with reasons" for pending tasks, stored on the
# `aitask-relations` orphan branch (never in task files) and NEVER auto-actioned.
# Design: aidocs/framework/task_relations.md D9 ("Obsolescence API").
#
# Verbs:
#   evidence <id> [--json] [--no-fetch]   live static evidence rows (signal | context)
#   ls [--min-band low|medium|high] [--all] [--no-fetch]
#   show <id> [--json] [--no-fetch]       one stored assessment
#   dismiss <id> [--note <text>]          hide it until its evidence changes
#   review                                walk the list; act only on an explicit choice
#   sweep [--budget N]                    enqueue a fairly rotated batch of assessments
#   unblock <id> [--kill] [--force]       clear an obsolescence unresolved-invocation guard
#
# Everything but `review` runs lib/obsolete_cli.py. `review` reads one choice
# letter per item from stdin: empty or unknown input re-prompts, EOF ends the
# review with no action. Folding validates BOTH ends by parsing
# aitask_fold_validate.sh's VALID:/INVALID: lines (its exit status is 0 for every
# content outcome) and re-validates after the confirmation, before mutating.
#
# Test-only seam: AIT_OBSOLETE_REVIEW_PRE_MUTATE_HOOK=<cmd> runs after a fold is
# confirmed and before the re-validation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PY="$(require_ait_python)"
CLI="$SCRIPT_DIR/lib/obsolete_cli.py"

say() { printf '%s\n' "$*" >&2; }

# ask <prompt> -> the answer on stdout; exit status 1 on EOF.
ask() {
    printf '%s' "$1" >&2
    local answer
    IFS= read -r answer || return 1
    printf '%s' "$answer"
}

FOLD_PRIMARY_FILE=""
FOLD_ITEM_FILE=""
FOLD_WARNINGS=()

# check_fold_pair <primary> <item>: validate both ends; prints FOLD_REFUSED:<x>|<reason>
# and returns 1 on any refusal. Sets FOLD_PRIMARY_FILE / FOLD_ITEM_FILE / FOLD_WARNINGS.
check_fold_pair() {
    local primary="$1" item="$2" out line
    FOLD_PRIMARY_FILE="" FOLD_ITEM_FILE="" FOLD_WARNINGS=()
    if ! out=$("$SCRIPT_DIR/aitask_fold_validate.sh" "$primary" 2>/dev/null </dev/null); then
        echo "FOLD_REFUSED:${primary}|validator_error"
        return 1
    fi
    while IFS= read -r line; do
        case "$line" in
            "VALID:${primary}:"*) FOLD_PRIMARY_FILE="${line#"VALID:${primary}:"}" ;;
            "INVALID:"*)
                line="${line#INVALID:}"
                echo "FOLD_REFUSED:${line%%:*}|${line#*:}"
                return 1 ;;
        esac
    done <<<"$out"
    if [[ -z "$FOLD_PRIMARY_FILE" ]]; then
        echo "FOLD_REFUSED:${primary}|unexpected_validator_output"
        return 1
    fi
    if ! out=$("$SCRIPT_DIR/aitask_fold_validate.sh" --exclude-self "$primary" "$item" 2>/dev/null </dev/null); then
        echo "FOLD_REFUSED:${item}|validator_error"
        return 1
    fi
    while IFS= read -r line; do
        case "$line" in
            "VALID:${item}:"*) FOLD_ITEM_FILE="${line#"VALID:${item}:"}" ;;
            "INVALID:"*)
                line="${line#INVALID:}"
                echo "FOLD_REFUSED:${line%%:*}|${line#*:}"
                return 1 ;;
            "WARNING:"*) FOLD_WARNINGS+=("$line") ;;
        esac
    done <<<"$out"
    if [[ -z "$FOLD_ITEM_FILE" ]]; then
        echo "FOLD_REFUSED:${item}|unexpected_validator_output"
        return 1
    fi
    return 0
}

# fold_item <item> <default primary or ->; returns 2 on EOF.
fold_item() {
    local item="$1" default="$2" primary answer w
    [[ "$default" == "-" ]] && default=""
    default="${default#*#}"
    primary=$(ask "Fold t${item} into which task?${default:+ [${default}]} ") || return 2
    primary="${primary:-$default}"
    primary="${primary#*#}"
    primary="${primary#t}"
    if [[ ! "$primary" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
        echo "FOLD_REFUSED:${primary:-none}|bad_id"
        return 0
    fi
    if [[ "$primary" == "$item" ]]; then
        echo "FOLD_REFUSED:is_self"
        return 0
    fi
    check_fold_pair "$primary" "$item" || return 0
    for w in ${FOLD_WARNINGS[@]+"${FOLD_WARNINGS[@]}"}; do
        echo "$w"
    done
    answer=$(ask "Fold t${item} into t${primary}${FOLD_WARNINGS[0]:+ despite the warnings above}? [y/N] ") || return 2
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        echo "FOLD_CANCELLED:t${item}"
        return 0
    fi
    if [[ -n "${AIT_OBSOLETE_REVIEW_PRE_MUTATE_HOOK:-}" ]]; then
        bash -c "$AIT_OBSOLETE_REVIEW_PRE_MUTATE_HOOK" >&2 </dev/null || true
    fi
    # The foldee (or the destination) may have changed while the prompt was open.
    check_fold_pair "$primary" "$item" || return 0
    if ! "$SCRIPT_DIR/aitask_fold_content.sh" "$FOLD_PRIMARY_FILE" "$FOLD_ITEM_FILE" \
            | "$SCRIPT_DIR/aitask_update.sh" --batch "$primary" --desc-file - >&2; then
        echo "FOLD_FAILED:t${item}|content"
        return 0
    fi
    if ! "$SCRIPT_DIR/aitask_fold_mark.sh" --commit-mode fresh "$primary" "$item" >&2 </dev/null; then
        echo "FOLD_FAILED:t${item}|mark"
        return 0
    fi
    echo "FOLDED:t${item}|t${primary}"
}

# archive_item <item>; returns 2 on EOF.
archive_item() {
    local item="$1" answer out rc=0
    answer=$(ask "Archive t${item} as obsolete (archived_reason: obsolete)? [y/N] ") || return 2
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        echo "ARCHIVE_CANCELLED:t${item}"
        return 0
    fi
    out=$("$SCRIPT_DIR/aitask_archive.sh" --obsolete "$item" 2>&1 </dev/null) || rc=$?
    if [[ "$rc" -eq 2 && "$out" == *"GATE_PENDING:"* ]]; then
        printf '%s\n' "$out" | grep -E '^GATE_' || true
        answer=$(ask "t${item} has pending gates. Archive anyway with --ignore-gates? [y/N] ") || return 2
        if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
            echo "ARCHIVE_CANCELLED:t${item}|gates"
            return 0
        fi
        rc=0
        out=$("$SCRIPT_DIR/aitask_archive.sh" --obsolete --ignore-gates "$item" 2>&1 </dev/null) || rc=$?
    fi
    if [[ "$rc" -ne 0 ]]; then
        printf '%s\n' "$out" >&2
        echo "ARCHIVE_FAILED:t${item}|exit_${rc}"
        return 0
    fi
    echo "ARCHIVED_OBSOLETE:t${item}"
}

dismiss_item() {
    local item="$1" note
    note=$(ask "Dismissal note (optional): ") || return 2
    if [[ -n "$note" ]]; then
        "$PY" "$CLI" dismiss "$item" --note "$note" </dev/null | grep -E '^(DISMISSED|DISMISS_|NO_ASSESSMENT|RETAINED)' || true
    else
        "$PY" "$CLI" dismiss "$item" </dev/null | grep -E '^(DISMISSED|DISMISS_|NO_ASSESSMENT|RETAINED)' || true
    fi
}

task_file_of() {
    local id="$1"
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        ls "${TASK_DIR:-aitasks}/t${BASH_REMATCH[1]}/t${id}_"*.md 2>/dev/null | head -1 || true
    else
        ls "${TASK_DIR:-aitasks}/t${id}_"*.md 2>/dev/null | head -1 || true
    fi
}

cmd_review() {
    local items line item target choice rc file n=0
    items=$("$PY" "$CLI" _review-items "$@")
    if [[ -z "$items" ]]; then
        echo "REVIEW_EMPTY"
        return 0
    fi
    while IFS= read -r line <&3; do
        [[ -n "$line" ]] || continue
        item="${line%%|*}"
        target="${line#*|}"
        n=$((n + 1))
        "$PY" "$CLI" show "$item" --no-fetch >&2 </dev/null || true
        while true; do
            choice=$(ask "t${item}: [o]pen [f]old [a]rchive-obsolete [d]ismiss [s]kip [q]uit > ") || {
                echo "REVIEW_ENDED:eof"
                return 0
            }
            rc=0
            case "$choice" in
                o)
                    file=$(task_file_of "$item")
                    if [[ -n "$file" ]]; then "${PAGER:-less}" "$file" >&2 || true; else say "t${item}: task file not found"; fi
                    continue ;;
                f) fold_item "$item" "$target" || rc=$? ;;
                a) archive_item "$item" || rc=$? ;;
                d) dismiss_item "$item" || rc=$? ;;
                s) echo "SKIPPED:t${item}" ;;
                q) echo "REVIEW_ENDED:quit"; return 0 ;;
                *) say "Choose one of o, f, a, d, s or q."; continue ;;
            esac
            if [[ "$rc" -eq 2 ]]; then
                echo "REVIEW_ENDED:eof"
                return 0
            fi
            break
        done
    done 3<<<"$items"
    echo "REVIEW_DONE:${n}"
}

case "${1:-}" in
    review) shift; cmd_review "$@" ;;
    ""|-h|--help|help)
        sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
        ;;
    *) exec "$PY" "$CLI" "$@" ;;
esac

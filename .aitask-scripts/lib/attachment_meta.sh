#!/usr/bin/env bash
# attachment_meta.sh - shared bash front for the per-blob attachment ledger
# (t1030_3). Extracted from aitask_attach.sh so all three ledger consumers ---
# `ait attach add/rm/gc` (aitask_attach.sh), archive (no-op under D4), and fold
# re-bind (aitask_fold_mark.sh) --- share ONE implementation (no drift).
#
# Wraps lib/attachment_meta.py (the lock-free per-blob refcount primitive) and
# adds the small bash helpers the consumers need: meta-dir resolution, the
# data-root-relative meta relpath (for `task_git add` staging), a task's
# attachment hashes (for gc's blocking-ref scan), and a duration parser (for the
# gc grace knob).
#
# MUTATING subcommands (incref/decref/rebind) are lock-free here --- the CALLER
# must already hold the global attachments/.attach.lock (see attachment_lock.sh).
# Read-only subcommands (refs/orphaned-at/zero-refcount) are safe lock-free
# (attachment_meta.py writes are atomic temp+os.replace).
#
# Source this file; do not execute. Requires task_utils.sh (for
# _ait_detect_data_worktree) + yaml_utils.sh (read_yaml_mappings) to be sourced
# by the caller; sources python_resolve.sh + attachment_utils.sh itself.

[[ -n "${_AIT_ATTACHMENT_META_SH_LOADED:-}" ]] && return 0
_AIT_ATTACHMENT_META_SH_LOADED=1

_AIT_ATTACHMENT_META_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$_AIT_ATTACHMENT_META_DIR_SELF/python_resolve.sh"
# shellcheck source=lib/attachment_utils.sh
source "$_AIT_ATTACHMENT_META_DIR_SELF/attachment_utils.sh"

# attach_meta_dir -> per-blob metadata dir in the data worktree.
attach_meta_dir() {
    _ait_detect_data_worktree
    printf '%s/attachments/meta' "$_AIT_DATA_WORKTREE"
}

# attach_meta <subcommand> [args...] -- run the lock-free per-blob ledger helper.
# Callers MUST already hold the global attach lock for mutating subcommands.
attach_meta() {
    local py; py="$(require_python)"
    "$py" "$_AIT_ATTACHMENT_META_DIR_SELF/attachment_meta.py" \
        --meta-dir "$(attach_meta_dir)" "$@"
}

# attach_meta_relpath <hash> -> data-root-relative meta file path (for staging).
attach_meta_relpath() {
    printf 'attachments/meta/%s.json' "$(attachment_shard_path "$1")"
}

# attach_task_hashes <task_file> -- print each attachment `hash` recorded in a
# task's `attachments:` frontmatter, one per line. Used by gc's blocking-ref
# scan; built on the t1030_1 read_yaml_mappings reader.
attach_task_hashes() {
    local task_file="$1" records ln
    records="$(read_yaml_mappings "$task_file" attachments)" || true
    [[ -z "$records" ]] && return 0
    while IFS= read -r ln; do
        [[ "$ln" == hash=* ]] && printf '%s\n' "${ln#hash=}"
    done <<< "$records"
}

# parse_duration_to_seconds <str> -- convert 30d / 24h / 90m / 120s / bare-int
# to seconds (prints the integer). die on anything else. Used by the gc grace
# knob; integer math avoids non-portable `date` arithmetic.
parse_duration_to_seconds() {
    local s="${1:-}"
    [[ -n "$s" ]] || die "parse_duration_to_seconds: empty duration"
    if [[ "$s" =~ ^([0-9]+)$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"; return 0
    fi
    if [[ "$s" =~ ^([0-9]+)([smhd])$ ]]; then
        local num="${BASH_REMATCH[1]}" unit="${BASH_REMATCH[2]}"
        case "$unit" in
            s) printf '%s' "$num" ;;
            m) printf '%s' "$(( num * 60 ))" ;;
            h) printf '%s' "$(( num * 3600 ))" ;;
            d) printf '%s' "$(( num * 86400 ))" ;;
        esac
        return 0
    fi
    die "parse_duration_to_seconds: invalid duration '$s' (use e.g. 30d, 24h, 90m, 120s, or bare seconds)"
}

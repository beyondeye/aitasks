#!/usr/bin/env bash
# aitask_attach.sh - User-facing dispatcher for task file attachments, routed by
# `ait attach <verb>`. Part of the task-attachments feature (t1030).
#
# Attachments are content-addressed (SHA-256) files recorded in a task's
# `attachments:` frontmatter (schema: aidocs/task_attachments_design.md §3) and
# stored in a pluggable backend (design §4/§5). Full CLI surface: design §6.
#
# SCAFFOLD STATE (t1030_1): only `ls` (and `help`) are functional — they need no
# blob storage. The storage verbs (`add`/`get`/`rm`/`move`/`gc`) are stubs until
# t1030_2 (local backend + cache + index) and t1030_3 (archive integration / gc).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/attachment_utils.sh
source "$SCRIPT_DIR/lib/attachment_utils.sh"

NOT_YET="storage not yet available — implemented in t1030_2 (add/get/rm/move) / t1030_3 (gc)"

show_help() {
    cat <<'EOF'
Usage: ait attach <verb> [args]

Manage content-addressed file attachments on a task (design §6).

  ls   <task>                                  List a task's attachments.
  add  <task> <file> [--backend <n>] [--name <d>]   Attach a file.        (not yet implemented)
  get  <task> <name-or-hash> [--out <path>]    Fetch an attachment.        (not yet implemented)
  rm   <task> <name-or-hash>                   Remove an attachment.       (not yet implemented)
  move <task> <name-or-hash> --to <backend>    Move an attachment backend. (not yet implemented)
  gc                                           Sweep orphaned blobs.       (not yet implemented)
  help                                         Show this help.

<task> accepts a parent id (e.g. 16) or a child id (e.g. 16_2), with or without
the leading `t`.
EOF
}

# _attach_print_row
# Validate and print one accumulated table row. Operates on cmd_list's
# dynamically-scoped locals (private helper; only called from cmd_list).
_attach_print_row() {
    idx=$((idx + 1))
    if ! attachment_validate_hash "$rhash"; then
        die "ait attach ls: attachment #$idx (${rname:-<unnamed>}) has an invalid or missing hash: '${rhash}'"
    fi
    local short="${rhash#sha256:}"
    short="${short:0:12}"
    printf '%-28s  %-14s  %-10s  %s\n' \
        "${rname:-<unnamed>}" "$short" "${rsize:-?}" "${rbackend:-?}"
}

# cmd_list <task-id> — the one functional verb in this scaffold.
cmd_list() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || die "Usage: ait attach ls <task-id>"
    task_id="${task_id#t}"

    local task_file records
    task_file="$(resolve_task_file "$task_id")"
    records="$(read_yaml_mappings "$task_file" attachments)"

    if [[ -z "$records" ]]; then
        echo "No attachments."
        return 0
    fi

    local idx=0 have_row=false ln k v
    local rname="" rhash="" rsize="" rbackend=""
    printf '%-28s  %-14s  %-10s  %s\n' "NAME" "HASH" "SIZE" "BACKEND"
    while IFS= read -r ln; do
        if [[ -z "$ln" ]]; then
            if [[ "$have_row" == true ]]; then
                _attach_print_row
            fi
            rname=""; rhash=""; rsize=""; rbackend=""; have_row=false
            continue
        fi
        have_row=true
        # Split on the FIRST '=' only (per read_yaml_mappings output contract).
        k="${ln%%=*}"
        v="${ln#*=}"
        case "$k" in
            name)    rname="$v" ;;
            hash)    rhash="$v" ;;
            size)    rsize="$v" ;;
            backend) rbackend="$v" ;;
        esac
    done <<< "$records"
    if [[ "$have_row" == true ]]; then
        _attach_print_row
    fi
}

cmd_stub() { die "ait attach $1: $NOT_YET"; }

main() {
    local verb="${1:-}"
    case "$verb" in
        ""|--help|-h|help) show_help ;;
        ls|list)   shift; cmd_list "$@" ;;
        add)       cmd_stub add ;;
        get)       cmd_stub get ;;
        rm|remove) cmd_stub rm ;;
        move)      cmd_stub move ;;
        gc)        cmd_stub gc ;;
        *)         die "Unknown verb: $verb (try 'ait attach help')" ;;
    esac
}

main "$@"

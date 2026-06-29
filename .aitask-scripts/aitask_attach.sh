#!/usr/bin/env bash
# aitask_attach.sh - User-facing dispatcher for task file attachments, routed by
# `ait attach <verb>`. Part of the task-attachments feature (t1030).
#
# Attachments are content-addressed (SHA-256) files recorded in a task's
# `attachments:` frontmatter (schema: aidocs/task_attachments_design.md §3) and
# stored in a pluggable backend (design §4/§5). Full CLI surface: design §6.
#
# STATE: `ls`/`add`/`get`/`rm` (and `help`) are functional. `move`/`gc` are stubs
# until t1030_3 (backend move + archive-driven garbage collection).
#
# STORAGE MODEL (t1030_2): the canonical refcount ledger is PER-BLOB metadata
# files (attachments/meta/<2>/<62>.json via lib/attachment_meta.py) — NOT a single
# global index.json. Blobs live at attachments/blobs/<2>/<62> (local backend). The
# whole add/rm body runs under one global attach-transaction lock (with_attach_lock).
# See aiplans/p1030/p1030_2_local_backend_cache_index.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/attachment_utils.sh
source "$SCRIPT_DIR/lib/attachment_utils.sh"
# shellcheck source=lib/attachment_backend.sh
source "$SCRIPT_DIR/lib/attachment_backend.sh"
# shellcheck source=lib/attachment_cache.sh
source "$SCRIPT_DIR/lib/attachment_cache.sh"
# shellcheck source=lib/attachment_lock.sh
source "$SCRIPT_DIR/lib/attachment_lock.sh"

NOT_YET="not yet available — implemented in t1030_3 (backend move / gc)"

show_help() {
    cat <<'EOF'
Usage: ait attach <verb> [args]

Manage content-addressed file attachments on a task (design §6).

  ls   <task>                                  List a task's attachments.
  add  <task> <file> [--backend <n>] [--name <d>]   Attach a file.
  get  <task> <name-or-hash> [--out <path>]    Fetch an attachment.
  rm   <task> <name-or-hash>                   Remove an attachment.
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

# ── Storage helpers (t1030_2) ────────────────────────────────────────────────

# _attach_meta_dir -> per-blob metadata dir in the data worktree.
_attach_meta_dir() {
    _ait_detect_data_worktree
    printf '%s/attachments/meta' "$_AIT_DATA_WORKTREE"
}

# _attach_meta <subcommand> [args...] -- run the lock-free per-blob ledger helper.
# Callers MUST already hold the global attach lock for mutating subcommands.
_attach_meta() {
    local py; py="$(require_python)"
    "$py" "$SCRIPT_DIR/lib/attachment_meta.py" --meta-dir "$(_attach_meta_dir)" "$@"
}

# _attach_meta_relpath <hash> -> data-root-relative meta file path (staging).
_attach_meta_relpath() {
    printf 'attachments/meta/%s.json' "$(attachment_shard_path "$1")"
}

# _attach_records <task_file> -- print "<hash>\t<name>\t<backend>" per attachment.
_attach_records() {
    local task_file="$1" records ln k v
    records="$(read_yaml_mappings "$task_file" attachments)" || true
    [[ -z "$records" ]] && return 0
    local rhash="" rname="" rbackend="" have=false
    while IFS= read -r ln; do
        if [[ -z "$ln" ]]; then
            [[ "$have" == true ]] && printf '%s\t%s\t%s\n' "$rhash" "$rname" "$rbackend"
            rhash=""; rname=""; rbackend=""; have=false; continue
        fi
        have=true; k="${ln%%=*}"; v="${ln#*=}"
        case "$k" in
            hash) rhash="$v" ;; name) rname="$v" ;; backend) rbackend="$v" ;;
        esac
    done <<< "$records"
    [[ "$have" == true ]] && printf '%s\t%s\t%s\n' "$rhash" "$rname" "$rbackend"
}

# _attach_resolve_ref <task_file> <name-or-hash> -- print the matching hash, or
# exit non-zero. Hash match (full or bare hex) wins over name match.
_attach_resolve_ref() {
    local task_file="$1" ref="$2" pairs h n b
    pairs="$(_attach_records "$task_file")"
    while IFS=$'\t' read -r h n b; do
        [[ -z "$h" ]] && continue
        [[ "$ref" == "$h" || "$ref" == "${h#sha256:}" ]] && { printf '%s\n' "$h"; return 0; }
    done <<< "$pairs"
    while IFS=$'\t' read -r h n b; do
        [[ -z "$h" ]] && continue
        [[ "$ref" == "$n" ]] && { printf '%s\n' "$h"; return 0; }
    done <<< "$pairs"
    return 1
}

# _attach_record_backend <task_file> <hash> -- print the attachment's backend
# (defaults to local).
_attach_record_backend() {
    local task_file="$1" hash="$2" pairs h n b
    pairs="$(_attach_records "$task_file")"
    while IFS=$'\t' read -r h n b; do
        [[ "$h" == "$hash" ]] && { printf '%s\n' "${b:-local}"; return 0; }
    done <<< "$pairs"
    printf 'local\n'
}

# _attach_size_cap_bytes -- size cap in bytes from project_config.yaml
# (attachment_max_size_mb, default 25 MB).
_attach_size_cap_bytes() {
    local cfg="aitasks/metadata/project_config.yaml" mb=""
    if [[ -f "$cfg" ]]; then
        mb="$(read_yaml_field "$cfg" attachment_max_size_mb 2>/dev/null || true)"
        mb="${mb//\"/}"; mb="${mb//\'/}"; mb="$(printf '%s' "$mb" | tr -d '[:space:]')"
    fi
    [[ "$mb" =~ ^[0-9]+$ && "$mb" -gt 0 ]] || mb=25
    printf '%s' "$(( mb * 1024 * 1024 ))"
}

# _attach_commit <message> <relpath>... -- stage explicit data-root-relative
# paths and commit ONLY those paths (partial commit) as one commit on the data
# branch. The trailing `-- "$@"` is load-bearing: a bare `git commit` would also
# commit anything else a concurrent writer left staged in the shared index.
# Non-zero on failure.
_attach_commit() {
    local msg="$1"; shift
    task_git add -- "$@" >/dev/null 2>&1 || return 1
    task_git commit -q -m "$msg" -- "$@" >/dev/null 2>&1 || return 1
}

# ── Verb: add ────────────────────────────────────────────────────────────────

cmd_add() {
    local task_id="" file="" backend="local" name=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --backend) backend="${2:-}"; shift 2 ;;
            --name)    name="${2:-}";    shift 2 ;;
            --)        shift ;;
            -*)        die "ait attach add: unknown option $1" ;;
            *) if [[ -z "$task_id" ]]; then task_id="$1"
               elif [[ -z "$file" ]]; then file="$1"
               else die "ait attach add: too many arguments"; fi; shift ;;
        esac
    done
    [[ -n "$task_id" && -n "$file" ]] || die "Usage: ait attach add <task> <file> [--backend <n>] [--name <d>]"
    task_id="${task_id#t}"
    [[ -f "$file" ]] || die "ait attach add: not a file: $file"
    [[ "$backend" == "local" ]] || die "ait attach add: backend '$backend' not yet supported (local only in t1030_2)"
    local task_file; task_file="$(resolve_task_file "$task_id")"
    [[ -n "$name" ]] || name="$(basename "$file")"
    with_attach_lock _attach_add_txn "$task_id" "$task_file" "$file" "$backend" "$name"
}

# _attach_add_txn -- the full add transaction (runs under the global attach lock).
_attach_add_txn() {
    local task_id="$1" task_file="$2" file="$3" backend="$4" name="$5"
    export ATTACHMENT_BACKEND="$backend"

    # Size cap.
    local size cap
    size="$(wc -c < "$file" | tr -d '[:space:]')"
    cap="$(_attach_size_cap_bytes)"
    if (( size > cap )); then
        die "ait attach add: file is ${size} bytes, over the ${cap}-byte cap (attachment_max_size_mb in aitasks/metadata/project_config.yaml; default 25 MB). Use a remote backend or 'gh release upload' for larger files."
    fi

    local mime hash
    mime="$(file --mime-type -b "$file" 2>/dev/null || echo application/octet-stream)"
    hash="$(attachment_sha256 "$file")"

    # Duplicate rejection — hash AND name, both per task (keeps (hash,task) 1:1).
    local pairs h n b
    pairs="$(_attach_records "$task_file")"
    while IFS=$'\t' read -r h n b; do
        [[ -z "$h" ]] && continue
        [[ "$h" == "$hash" ]] && die "ait attach add: this file ($hash) is already attached to t${task_id} as '${n}'"
        [[ "$n" == "$name" ]] && die "ait attach add: an attachment named '${name}' already exists on t${task_id} — pass --name to disambiguate"
    done <<< "$pairs"

    # Pre-existence (for deterministic rollback).
    local blob_pre=false meta_pre=false
    attachment_backend_head "$hash" && blob_pre=true
    local meta_file; meta_file="$(_attach_meta_dir)/$(attachment_shard_path "$hash").json"
    [[ -f "$meta_file" ]] && meta_pre=true

    # Store blob (idempotent atomic copy) + populate cache.
    attachment_backend_put "$hash" "$file"
    attachment_resolve "$hash" >/dev/null

    local added_at; added_at="$(date '+%Y-%m-%d %H:%M')"
    _attach_meta incref "$hash" "$task_id" "mime=$mime" "size=$size" "backend=$backend"
    require_python >/dev/null
    "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$task_file" attachments \
        "hash=$hash" "name=$name" "mime=$mime" "size=$size" "added_at=$added_at" "backend=$backend"

    # Commit the trio (blob + meta + task) as one commit.
    local blob_rel meta_rel
    blob_rel="$(attachment_local_blob_relpath "$hash")"
    meta_rel="$(_attach_meta_relpath "$hash")"
    if ! _attach_commit "ait: Attach ${name} to t${task_id}" "$blob_rel" "$meta_rel" "$task_file"; then
        _attach_rollback_add "$task_file" "$meta_rel" "$meta_file" "$meta_pre" "$blob_rel" "$hash" "$blob_pre"
        die "ait attach add: commit failed — rolled back to pre-attach state"
    fi
    success "Attached '${name}' (${hash}) to t${task_id}"
}

# _attach_rollback_add -- restore HEAD copies of pre-existing files and remove
# newly-created ones, so a failed commit leaves no drift (runs under the lock).
_attach_rollback_add() {
    local task_file="$1" meta_rel="$2" meta_file="$3" meta_pre="$4" blob_rel="$5" hash="$6" blob_pre="$7"
    # Task .md always pre-exists -> unstage + restore from HEAD.
    task_git reset -q -- "$task_file" >/dev/null 2>&1 || true
    task_git checkout -- "$task_file" >/dev/null 2>&1 || true
    # Meta file: restore if it pre-existed, else unstage + delete.
    task_git reset -q -- "$meta_rel" >/dev/null 2>&1 || true
    if [[ "$meta_pre" == true ]]; then
        task_git checkout -- "$meta_rel" >/dev/null 2>&1 || true
    else
        rm -f "$meta_file"
    fi
    # Blob: only created this op -> unstage + delete (orphan would be GC-reclaimed
    # anyway, but remove eagerly for a clean rollback).
    if [[ "$blob_pre" == false ]]; then
        task_git reset -q -- "$blob_rel" >/dev/null 2>&1 || true
        attachment_backend_delete "$hash"
    fi
}

# ── Verb: get ────────────────────────────────────────────────────────────────

cmd_get() {
    local task_id="" ref="" out=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --out) out="${2:-}"; shift 2 ;;
            --)    shift ;;
            -*)    die "ait attach get: unknown option $1" ;;
            *) if [[ -z "$task_id" ]]; then task_id="$1"
               elif [[ -z "$ref" ]]; then ref="$1"
               else die "ait attach get: too many arguments"; fi; shift ;;
        esac
    done
    [[ -n "$task_id" && -n "$ref" ]] || die "Usage: ait attach get <task> <name-or-hash> [--out <path>]"
    task_id="${task_id#t}"
    local task_file; task_file="$(resolve_task_file "$task_id")"
    local hash; hash="$(_attach_resolve_ref "$task_file" "$ref")" \
        || die "ait attach get: no attachment matching '$ref' on t${task_id}"
    local backend; backend="$(_attach_record_backend "$task_file" "$hash")"
    export ATTACHMENT_BACKEND="${backend:-local}"
    local cache; cache="$(attachment_resolve "$hash")"
    # Verify the resolved bytes hash back to the expected hash (design §8).
    local got; got="$(attachment_sha256 "$cache")"
    [[ "$got" == "$hash" ]] || die "ait attach get: hash mismatch for '$ref' (expected $hash, got $got)"
    if [[ -n "$out" ]]; then
        cp "$cache" "$out"
        success "Wrote $out"
    else
        cat "$cache"
    fi
}

# ── Verb: rm ─────────────────────────────────────────────────────────────────

cmd_remove() {
    local task_id="${1:-}" ref="${2:-}"
    [[ -n "$task_id" && -n "$ref" ]] || die "Usage: ait attach rm <task> <name-or-hash>"
    task_id="${task_id#t}"
    local task_file; task_file="$(resolve_task_file "$task_id")"
    with_attach_lock _attach_rm_txn "$task_id" "$task_file" "$ref"
}

_attach_rm_txn() {
    local task_id="$1" task_file="$2" ref="$3"
    local hash; hash="$(_attach_resolve_ref "$task_file" "$ref")" \
        || die "ait attach rm: no attachment matching '$ref' on t${task_id}"
    _attach_meta decref "$hash" "$task_id"     # blob NOT deleted — gc is t1030_3
    "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" remove "$task_file" attachments \
        --match-key hash --match-val "$hash"
    local meta_rel; meta_rel="$(_attach_meta_relpath "$hash")"
    if ! _attach_commit "ait: Detach attachment from t${task_id}" "$meta_rel" "$task_file"; then
        task_git reset -q -- "$task_file" "$meta_rel" >/dev/null 2>&1 || true
        task_git checkout -- "$task_file" "$meta_rel" >/dev/null 2>&1 || true
        die "ait attach rm: commit failed — rolled back"
    fi
    success "Removed attachment '${ref}' from t${task_id}"
}

cmd_stub() { die "ait attach $1: $NOT_YET"; }

main() {
    local verb="${1:-}"
    case "$verb" in
        ""|--help|-h|help) show_help ;;
        ls|list)   shift; cmd_list "$@" ;;
        add)       shift; cmd_add "$@" ;;
        get)       shift; cmd_get "$@" ;;
        rm|remove) shift; cmd_remove "$@" ;;
        move)      cmd_stub move ;;
        gc)        cmd_stub gc ;;
        *)         die "Unknown verb: $verb (try 'ait attach help')" ;;
    esac
}

main "$@"

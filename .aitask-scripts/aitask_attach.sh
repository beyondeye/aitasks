#!/usr/bin/env bash
# aitask_attach.sh - User-facing dispatcher for task file attachments, routed by
# `ait attach <verb>`. Part of the task-attachments feature (t1030).
#
# Attachments are content-addressed (SHA-256) files recorded in a task's
# `attachments:` frontmatter (schema: aidocs/task_attachments_design.md §3) and
# stored in a pluggable backend (design §4/§5). Full CLI surface: design §6.
#
# STATE: `ls`/`add`/`get`/`rm`/`gc` (and `help`) are functional. `move` is a stub
# (remote backend move — a later remote-backend task). `gc` (t1030_3) reclaims
# fully-orphaned blobs, honoring the grace knob; archival itself never decrefs
# (an archived task is still a real referrer — browsable history).
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
# shellcheck source=lib/attachment_meta.sh
source "$SCRIPT_DIR/lib/attachment_meta.sh"

NOT_YET="not yet available — backend move arrives with a remote-backend task"

show_help() {
    cat <<'EOF'
Usage: ait attach <verb> [args]

Manage content-addressed file attachments on a task (design §6).

  ls   <task>                                  List a task's attachments.
  add  <task> <file> [--backend <n>] [--name <d>]   Attach a file.
  get  <task> <name-or-hash> [--out <path>]    Fetch an attachment.
  rm   <task> <name-or-hash>                   Remove an attachment.
  move <task> <name-or-hash> --to <backend>    Move an attachment backend. (not yet implemented)
  gc                                           Sweep fully-orphaned blobs (opt-in; honors grace).
  help                                         Show this help.

Internal (used by the board on hard-delete; not for routine manual use):
  decref-deleted [--protect-task <id>]... <task-id>...   Release (or rebind to survivors) a deleted task's attachment refs.

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

# Per-blob ledger helpers (attach_meta_dir / attach_meta / attach_meta_relpath /
# attach_task_hashes / parse_duration_to_seconds) live in lib/attachment_meta.sh
# (t1030_3 — shared with aitask_fold_mark.sh). Sourced above.

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
    local meta_file; meta_file="$(attach_meta_dir)/$(attachment_shard_path "$hash").json"
    [[ -f "$meta_file" ]] && meta_pre=true

    # Store blob (idempotent atomic copy) + populate cache.
    attachment_backend_put "$hash" "$file"
    attachment_resolve "$hash" >/dev/null

    local added_at; added_at="$(date '+%Y-%m-%d %H:%M')"
    attach_meta incref "$hash" "$task_id" "mime=$mime" "size=$size" "backend=$backend"
    require_python >/dev/null
    "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$task_file" attachments \
        "hash=$hash" "name=$name" "mime=$mime" "size=$size" "added_at=$added_at" "backend=$backend"

    # Commit the trio (blob + meta + task) as one commit.
    local blob_rel meta_rel
    blob_rel="$(attachment_local_blob_relpath "$hash")"
    meta_rel="$(attach_meta_relpath "$hash")"
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
    # decref stamps orphaned_at if this empties refs (the gc grace clock); blob
    # NOT deleted here — reclamation is `ait attach gc` (also t1030_3).
    attach_meta decref "$hash" "$task_id" "now=$(date +%s)"
    "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" remove "$task_file" attachments \
        --match-key hash --match-val "$hash"
    local meta_rel; meta_rel="$(attach_meta_relpath "$hash")"
    if ! _attach_commit "ait: Detach attachment from t${task_id}" "$meta_rel" "$task_file"; then
        task_git reset -q -- "$task_file" "$meta_rel" >/dev/null 2>&1 || true
        task_git checkout -- "$task_file" "$meta_rel" >/dev/null 2>&1 || true
        die "ait attach rm: commit failed — rolled back"
    fi
    success "Removed attachment '${ref}' from t${task_id}"
}

# ── Verb: decref-deleted (internal — board hard-delete, t1093) ────────────────
# Release attachment refs for one or more tasks being HARD-DELETED. Unlike `rm`
# it does NOT patch task frontmatter (the whole file is being removed). It
# self-commits its decref path-limited (so it is decoupled from the board's own
# delete commit) and rolls back on commit failure, mirroring `_attach_rm_txn`.
#
# Usage: ait attach decref-deleted [--protect-task <id>]... <doomed-id> [<doomed-id>...]
#
# `--protect-task <id>` names a task that SURVIVES the delete but shares
# attachments with a doomed task (the unfold-on-delete case: fold merged a
# folded task's attachments into the primary and rebound their refs to it; the
# board revives the folded task on delete). Any doomed-task hash that a protected
# task still lists in its frontmatter — AND that the doomed task currently
# references in the ledger — is REBOUND to the protected task(s): incref each
# survivor, then decref the doomed id, so the ref moves to the revived owner
# instead of being orphaned onto the deleted primary (t1096, the proper
# rebind-on-unfold that replaced t1093's conservative skip guard). A protected id
# that cannot be resolved is FATAL (it is the intended new owner — fail-closed).
cmd_decref_deleted() {
    local protect_ids=() args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --protect-task) [[ -n "${2:-}" ]] || die "ait attach decref-deleted: --protect-task needs a value"
                            protect_ids+=( "${2#t}" ); shift 2 ;;
            --) shift ;;
            *)  args+=( "$1" ); shift ;;
        esac
    done
    [[ ${#args[@]} -ge 1 ]] \
        || die "Usage: ait attach decref-deleted [--protect-task <id>]... <task-id> [<task-id>...]"
    with_attach_lock _attach_decref_deleted_txn "${#protect_ids[@]}" \
        ${protect_ids[@]+"${protect_ids[@]}"} "${args[@]}"
}

_attach_decref_deleted_txn() {
    local n_protect="$1"; shift
    # Map each folded-origin hash -> the revived (surviving) task id(s) that still
    # list it, so a doomed ref can be REBOUND to the survivor(s) instead of merely
    # released (t1096). A hash listed by >1 revived folded task -> ALL become
    # referrers. Unlike the old guard-set, an unresolvable protected id is FATAL:
    # under rebind semantics it is the intended NEW OWNER, so silently dropping it
    # would decref/orphan a primary-owned blob as if no survivor existed
    # (fail-closed, mirroring the doomed-id treatment below).
    local -A protect_ids_for_hash=()
    local i pid pf h
    for (( i=0; i<n_protect; i++ )); do
        pid="${1#t}"
        pf="$(resolve_task_file "$pid" 2>/dev/null)" \
            || die "ait attach decref-deleted: cannot resolve protected (revived) task t${pid}"
        while IFS= read -r h; do
            [[ -n "$h" ]] || continue
            case " ${protect_ids_for_hash[$h]:-} " in
                *" $pid "*) : ;;                                   # de-dup pid per hash
                *) protect_ids_for_hash["$h"]="${protect_ids_for_hash[$h]:+${protect_ids_for_hash[$h]} }$pid" ;;
            esac
        done < <(attach_task_hashes "$pf")
        shift
    done

    local now; now="$(date +%s)"
    local -A seen_relpath=()
    local stage=() task_id task_file hash rel survivors sid
    for task_id in "$@"; do
        task_id="${task_id#t}"
        # Doomed ids are derived from files the caller is about to delete, so an
        # unresolved id means we could not inspect attachments before deletion ->
        # FATAL (fail-closed: the board aborts the delete rather than leak). t1093
        task_file="$(resolve_task_file "$task_id" 2>/dev/null)" \
            || die "ait attach decref-deleted: cannot resolve doomed task t${task_id}"
        while IFS= read -r hash; do
            [[ -n "$hash" ]] || continue
            survivors="${protect_ids_for_hash[$hash]:-}"
            # REBIND only a ledger ref the doomed task ACTUALLY holds (t1096): a
            # blind incref on a drifted / already-rebound state would resurrect an
            # orphan (incref clears orphaned_at) or grant unearned ownership. Confirm
            # the doomed id is a current referent before moving it to the survivor(s).
            if [[ -n "$survivors" ]] && attach_meta refs "$hash" | grep -qxF "$task_id"; then
                # incref survivors FIRST so refs never transiently empties -> decref
                # cannot stamp a spurious orphaned_at.
                for sid in $survivors; do
                    attach_meta incref "$hash" "$sid"
                done
                attach_meta decref "$hash" "$task_id" "now=$now"
                printf 'REBOUND:%s:%s:%s\n' "$task_id" "$hash" "${survivors// /,}"
            elif [[ -n "$survivors" ]]; then
                # Survivor lists it, but the doomed id no longer references it in the
                # ledger -> nothing to move (already rebound / never owned). No incref,
                # no staging (bytes unchanged).
                printf 'REBIND_NOOP:%s:%s\n' "$task_id" "$hash"
                continue
            else
                # decref PER (task_id, hash): a blob shared by two doomed tasks must
                # lose BOTH refs. `now=` drives the orphaned_at stamp (cf _attach_rm_txn).
                attach_meta decref "$hash" "$task_id" "now=$now"
                printf 'DECREFED:%s:%s\n' "$task_id" "$hash"
            fi
            rel="$(attach_meta_relpath "$hash")"
            if [[ -z "${seen_relpath[$rel]:-}" ]]; then
                seen_relpath["$rel"]=1
                stage+=( "$rel" )            # dedup the STAGING list, not the ops
            fi
        done < <(attach_task_hashes "$task_file")
    done

    if (( ${#stage[@]} > 0 )); then
        task_git add -- "${stage[@]}" >/dev/null 2>&1 \
            || die "ait attach decref-deleted: failed to stage meta files"
        # No-op guard: an idempotent re-run (after a partial failure) rewrites
        # identical bytes -> an empty commit would fail; only commit if changed.
        if ! task_git diff --cached --quiet -- "${stage[@]}" 2>/dev/null; then
            if ! _attach_commit "ait: Release/rebind attachments of deleted task(s): $*" "${stage[@]}"; then
                task_git reset  -q -- "${stage[@]}" >/dev/null 2>&1 || true
                task_git checkout  -- "${stage[@]}" >/dev/null 2>&1 || true
                die "ait attach decref-deleted: commit failed — rolled back"
            fi
        fi
    fi
    printf 'STAGED:%s\n' "${#stage[@]}"
}

# ── Verb: gc ─────────────────────────────────────────────────────────────────

# _attach_gc_grace -- grace duration string from project_config.yaml
# (attachments_gc_grace, default 30d). The window after a blob becomes FULLY
# orphaned (no active OR archived task references it) before gc may reclaim it.
_attach_gc_grace() {
    local cfg="aitasks/metadata/project_config.yaml" v=""
    if [[ -f "$cfg" ]]; then
        v="$(read_yaml_field "$cfg" attachments_gc_grace 2>/dev/null || true)"
        v="${v//\"/}"; v="${v//\'/}"; v="$(printf '%s' "$v" | tr -d '[:space:]')"
    fi
    [[ -n "$v" ]] || v="30d"
    printf '%s' "$v"
}

# _attach_gc_blocking_hashes -- print every attachment hash referenced by a task
# that must KEEP its blobs: all active tasks AND all archived tasks (archived
# references are real — browsable history, D4), EXCLUDING Folded tasks (pending-
# deletion; their refs were rebound to the primary). This is the belt-and-
# suspenders cross-check against ledger drift before any delete.
_attach_gc_blocking_hashes() {
    shopt -s nullglob
    local files=( "$TASK_DIR"/t*.md "$TASK_DIR"/t*/t*.md \
                  "$ARCHIVED_DIR"/t*.md "$ARCHIVED_DIR"/t*/t*.md )
    shopt -u nullglob
    local f st
    for f in "${files[@]}"; do
        [[ -f "$f" ]] || continue
        st="$(read_task_status "$f" 2>/dev/null || true)"
        [[ "$st" == "Folded" ]] && continue
        attach_task_hashes "$f"
    done
}

cmd_gc() {
    [[ $# -eq 0 ]] || die "Usage: ait attach gc"
    with_attach_lock _attach_gc_txn
}

# _attach_gc_txn -- the orphan sweep (runs under the global attach lock).
_attach_gc_txn() {
    local grace_sec now
    grace_sec="$(parse_duration_to_seconds "$(_attach_gc_grace)")"
    now="$(date +%s)"

    # Blocking set: hashes any non-Folded active/archived task still references.
    local blocking; blocking="$(_attach_gc_blocking_hashes)"

    local swept=0 retained=0
    local -a del_paths=()
    local h refs orphaned_at meta_file
    while IFS= read -r h; do
        [[ -n "$h" ]] || continue
        # Re-confirm zero refs under the held lock (zero-refcount is advisory).
        refs="$(attach_meta refs "$h")"
        if [[ -n "$refs" ]]; then retained=$((retained + 1)); continue; fi
        # Belt-and-suspenders: a live/archived task still lists it -> keep.
        if printf '%s\n' "$blocking" | grep -qxF "$h"; then
            retained=$((retained + 1)); continue
        fi
        # Grace window: skip orphans more recent than the grace period. A missing
        # orphaned_at (pre-feature orphan) is treated as eligible (age = inf).
        orphaned_at="$(attach_meta orphaned-at "$h")"
        if [[ -n "$orphaned_at" ]] && (( now - orphaned_at < grace_sec )); then
            retained=$((retained + 1)); continue
        fi
        # Reclaim: delete blob + meta (v1 is local-only; add rejects other
        # backends, so every stored blob is local).
        export ATTACHMENT_BACKEND="local"
        attachment_backend_delete "$h"
        meta_file="$(attach_meta_dir)/$(attachment_shard_path "$h").json"
        rm -f "$meta_file"
        del_paths+=( "$(attachment_local_blob_relpath "$h")" "$(attach_meta_relpath "$h")" )
        swept=$((swept + 1))
    done < <(attach_meta zero-refcount)

    if (( swept > 0 )); then
        if ! _attach_commit "ait: GC ${swept} orphaned attachment(s)" "${del_paths[@]}"; then
            # Restore the just-deleted tracked files so a failed commit leaves no
            # deleted-on-disk-but-uncommitted split-brain.
            task_git reset -q -- "${del_paths[@]}" >/dev/null 2>&1 || true
            task_git checkout -- "${del_paths[@]}" >/dev/null 2>&1 || true
            die "ait attach gc: commit failed — restored ${swept} blob(s); no changes made"
        fi
    fi
    success "gc: swept ${swept} orphaned attachment(s), retained ${retained} referenced/in-grace blob(s)"
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
        gc)        shift; cmd_gc "$@" ;;
        decref-deleted) shift; cmd_decref_deleted "$@" ;;
        *)         die "Unknown verb: $verb (try 'ait attach help')" ;;
    esac
}

main "$@"

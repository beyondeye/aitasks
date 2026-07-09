#!/usr/bin/env bash
# aitask_artifact.sh - User-facing dispatcher for versioned task artifacts,
# routed by `ait artifact <verb>`. Part of the unified artifact model (t1076_2;
# design: aidocs/unified_artifact_design.md §3/§4).
#
# THE MODEL — stable handle / mutable manifest split: an artifact is a stable
# logical handle (`art:<id>`, recorded ONCE in the owning task's `artifacts:`
# frontmatter and never rewritten) whose mutable state (current version,
# version history, backend) lives in a per-artifact manifest
# (artifacts/manifests/<id>.json via lib/artifact_manifest.py, t1076_1).
# Updating or repointing an artifact touches ONLY the manifest — never the
# referencing task file. Attachments (`ait attach`) are the immutable,
# single-version sibling; the two frontmatter fields stay separate (t1076_2
# settled decision, design §10).
#
# STATE: every verb is functional, `move` included (t1076_3: copy every
# version blob to the registered target, verify, then repoint the manifest —
# non-destructive, resumable). Backends: `local` (zero-config, always
# registered) and `dir` (a mounted directory root registered under
# artifacts.backends.dir in aitasks/metadata/project_config.yaml). Backend
# selection goes through lib/artifact_registry.sh (t1076_3); remote adapters
# (s3/gdrive) arrive with t1089/t1090.
#
# LOCKING: every mutating verb runs its whole transaction (blob put, manifest
# mutation, frontmatter patch, path-scoped commit) under the global
# attach-transaction lock (with_attach_lock) shared with `ait attach` — the
# blob store and gc blocking set are shared substrate.

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
# shellcheck source=lib/artifact_utils.sh
source "$SCRIPT_DIR/lib/artifact_utils.sh"
# shellcheck source=lib/artifact_backend.sh
source "$SCRIPT_DIR/lib/artifact_backend.sh"
# shellcheck source=lib/artifact_cache.sh
source "$SCRIPT_DIR/lib/artifact_cache.sh"
# shellcheck source=lib/attachment_lock.sh
source "$SCRIPT_DIR/lib/attachment_lock.sh"
# shellcheck source=lib/attachment_meta.sh
source "$SCRIPT_DIR/lib/attachment_meta.sh"
# shellcheck source=lib/artifact_manifest.sh
source "$SCRIPT_DIR/lib/artifact_manifest.sh"
# shellcheck source=lib/artifact_registry.sh
source "$SCRIPT_DIR/lib/artifact_registry.sh"

KIND_RE='^[a-z][a-z0-9_]{0,31}$'
HANDLE_RE='^art:[a-z0-9][a-z0-9._-]{0,127}$'

show_help() {
    cat <<'EOF'
Usage: ait artifact <verb> [args]

Manage versioned, handle-addressed task artifacts (design: unified artifact
model §3/§4). A task's frontmatter carries only the stable `art:<id>` handle
(+ kind/name); the current version, version history, and backend live in the
artifact manifest and never rewrite the task file.

  create <task> <file> --kind <kind> [--name <label>] [--handle art:<id>] [--backend <n>]
                                               Create an artifact (v1) on a task.
  update <handle> <file>                       Store a new version and repoint `current`.
  move   <handle> --to <backend>               Copy every version to a registered backend,
                                               then repoint the manifest (source blobs stay).
  rm     <task> <handle-or-name>               Remove an artifact reference (and, when
                                               unreferenced, its manifest + orphan blobs).
  ls     [<task>]                              List a task's artifacts, or every manifest.
  get    <handle> [--out <path>] [--version <sha256:hash>]
                                               Fetch the current (or a specific) version.
  versions <handle>                            List versions oldest-first (* = current).
  help                                         Show this help.

<task> accepts a parent id (e.g. 16) or a child id (e.g. 16_2), with or without
the leading `t`. <kind> classifies the render type (html_plan, mockup, report,
...) — lowercase [a-z0-9_], open set. The default handle is derived as
art:t<task>-<kind-without-underscores> (child `_` becomes `.`), e.g.
`ait artifact create 774 plan.html --kind html_plan` -> art:t774-htmlplan.
EOF
}

# ── Shared helpers ───────────────────────────────────────────────────────────

# _artifact_records <task_file> -- print "<handle>\t<kind>\t<name>" per
# `artifacts:` frontmatter entry.
_artifact_records() {
    local task_file="$1" records ln k v
    records="$(read_yaml_mappings "$task_file" artifacts)" || true
    [[ -z "$records" ]] && return 0
    local rhandle="" rkind="" rname="" have=false
    while IFS= read -r ln; do
        if [[ -z "$ln" ]]; then
            [[ "$have" == true ]] && printf '%s\t%s\t%s\n' "$rhandle" "$rkind" "$rname"
            rhandle=""; rkind=""; rname=""; have=false; continue
        fi
        have=true; k="${ln%%=*}"; v="${ln#*=}"
        case "$k" in
            handle) rhandle="$v" ;; kind) rkind="$v" ;; name) rname="$v" ;;
        esac
    done <<< "$records"
    [[ "$have" == true ]] && printf '%s\t%s\t%s\n' "$rhandle" "$rkind" "$rname"
}

# _artifact_resolve_ref <task_file> <ref> -- print the matching handle, or exit
# non-zero. An exact handle match wins. A name match is accepted only when it is
# UNAMBIGUOUS: names are advisory, optional metadata (fold dedupes by handle,
# not name), so a destructive verb must never pick "first parsed wins" — two
# same-name artifacts make the name reference die with a pointer to the handle.
_artifact_resolve_ref() {
    local task_file="$1" ref="$2" recs h k n
    recs="$(_artifact_records "$task_file")"
    while IFS=$'\t' read -r h k n; do
        [[ -z "$h" ]] && continue
        [[ "$ref" == "$h" ]] && { printf '%s\n' "$h"; return 0; }
    done <<< "$recs"
    local matches=()
    while IFS=$'\t' read -r h k n; do
        [[ -z "$h" ]] && continue
        [[ "$ref" == "$n" ]] && matches+=( "$h" )
    done <<< "$recs"
    if (( ${#matches[@]} > 1 )); then
        die "ait artifact: ambiguous name '$ref' (matches ${matches[*]}) — use the handle"
    fi
    if (( ${#matches[@]} == 1 )); then
        printf '%s\n' "${matches[0]}"
        return 0
    fi
    return 1
}

# _artifact_size_cap_bytes -- size cap in bytes from project_config.yaml
# (artifact_max_size_mb, default 25 MB). Own knob, distinct from
# attachment_max_size_mb — HTML plans may warrant a different cap later.
_artifact_size_cap_bytes() {
    local cfg="aitasks/metadata/project_config.yaml" mb=""
    if [[ -f "$cfg" ]]; then
        mb="$(read_yaml_field "$cfg" artifact_max_size_mb 2>/dev/null || true)"
        mb="${mb//\"/}"; mb="${mb//\'/}"; mb="$(printf '%s' "$mb" | tr -d '[:space:]')"
    fi
    [[ "$mb" =~ ^[0-9]+$ && "$mb" -gt 0 ]] || mb=25
    printf '%s' "$(( mb * 1024 * 1024 ))"
}

# _artifact_commit <message> <relpath>... -- stage explicit data-root-relative
# paths and commit ONLY those paths (partial commit) as one commit on the data
# branch. The trailing `-- "$@"` is load-bearing: a bare `git commit` would also
# commit anything else a concurrent writer left staged in the shared index.
_artifact_commit() {
    local msg="$1"; shift
    task_git add -- "$@" >/dev/null 2>&1 || return 1
    task_git commit -q -m "$msg" -- "$@" >/dev/null 2>&1 || return 1
}

# _artifact_manifest_backend <handle> -- print the manifest's backend field.
_artifact_manifest_backend() {
    local handle="$1"
    artifact_manifest get "$handle" \
        | "$(require_python)" -c 'import json,sys; print(json.load(sys.stdin)["backend"])'
}

# _artifact_handle_referenced_elsewhere <handle> <excluded_task_file> -- print
# the first OTHER task file (active or archived) whose `artifacts:` lists
# <handle>; empty if none. Folded tasks are deliberately NOT skipped: a Folded
# task can be revived by board hard-delete (unfold-on-delete), so its handle
# reference must keep the manifest alive. Consequence: a fold-then-archive
# sequence can leave an unreferenced manifest behind — conservative
# (never loses data); orphan reaping is t1135.
_artifact_handle_referenced_elsewhere() {
    local handle="$1" excluded="$2"
    shopt -s nullglob
    local files=( "$TASK_DIR"/t*.md "$TASK_DIR"/t*/t*.md \
                  "$ARCHIVED_DIR"/t*.md "$ARCHIVED_DIR"/t*/t*.md )
    shopt -u nullglob
    local f h k n
    for f in "${files[@]}"; do
        [[ -f "$f" ]] || continue
        [[ "$f" -ef "$excluded" ]] && continue
        while IFS=$'\t' read -r h k n; do
            [[ "$h" == "$handle" ]] && { printf '%s\n' "$f"; return 0; }
        done < <(_artifact_records "$f")
    done
    return 0
}

# ── Verb: create ─────────────────────────────────────────────────────────────

cmd_create() {
    local task_id="" file="" kind="" name="" handle="" backend=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --kind)    kind="${2:-}";    shift 2 ;;
            --name)    name="${2:-}";    shift 2 ;;
            --handle)  handle="${2:-}";  shift 2 ;;
            --backend) backend="${2:-}"; shift 2 ;;
            --)        shift ;;
            -*)        die "ait artifact create: unknown option $1" ;;
            *) if [[ -z "$task_id" ]]; then task_id="$1"
               elif [[ -z "$file" ]]; then file="$1"
               else die "ait artifact create: too many arguments"; fi; shift ;;
        esac
    done
    [[ -n "$task_id" && -n "$file" ]] \
        || die "Usage: ait artifact create <task> <file> --kind <kind> [--name <label>] [--handle art:<id>] [--backend <n>]"
    task_id="${task_id#t}"
    [[ -f "$file" ]] || die "ait artifact create: not a file: $file"
    [[ -n "$kind" ]] || die "ait artifact create: --kind is required (html_plan, mockup, report, ...)"
    [[ "$kind" =~ $KIND_RE ]] \
        || die "ait artifact create: invalid kind '$kind' (lowercase [a-z0-9_], max 32 chars, must start with a letter)"
    if [[ -z "$backend" ]]; then
        # Explicit `|| die`: a failed capture must not silently yield "".
        backend="$(artifact_registry_default_backend)" \
            || die "ait artifact create: could not resolve the default backend (see error above)"
    fi
    if [[ -z "$handle" ]]; then
        # Derived handle: art:t<task>-<kindslug>. Child ids keep their structure
        # readable via `_` -> `.` (both in the handle charset): 16_2 -> t16.2.
        local tid_slug="${task_id//_/.}" kind_slug="${kind//_/}"
        handle="art:t${tid_slug}-${kind_slug}"
    fi
    [[ "$handle" =~ $HANDLE_RE ]] \
        || die "ait artifact create: invalid handle '$handle' (expected art:[a-z0-9][a-z0-9._-]{0,127})"
    local task_file; task_file="$(resolve_task_file "$task_id")"
    with_attach_lock _artifact_create_txn "$task_id" "$task_file" "$file" "$kind" "$name" "$handle" "$backend"
}

# _artifact_create_txn -- the full create transaction (runs under the lock).
_artifact_create_txn() {
    local task_id="$1" task_file="$2" file="$3" kind="$4" name="$5" handle="$6" backend="$7"
    # Registry membership + config validation — dies actionably pre-mutation.
    artifact_registry_activate "$backend"

    # Size cap.
    local size cap
    size="$(wc -c < "$file" | tr -d '[:space:]')"
    cap="$(_artifact_size_cap_bytes)"
    if (( size > cap )); then
        die "ait artifact create: file is ${size} bytes, over the ${cap}-byte cap (artifact_max_size_mb in aitasks/metadata/project_config.yaml; default 25 MB)"
    fi

    local hash; hash="$(artifact_sha256 "$file")"

    # Frontmatter dup guard — one entry per handle per task.
    local h k n
    while IFS=$'\t' read -r h k n; do
        [[ "$h" == "$handle" ]] \
            && die "ait artifact create: t${task_id} already lists artifact ${handle}"
    done < <(_artifact_records "$task_file")

    # Manifest collision guard — handles are minted once, globally.
    [[ -z "$(artifact_manifest get "$handle")" ]] \
        || die "ait artifact create: handle ${handle} already exists — pass --handle to choose another"

    # Pre-existence (for deterministic rollback; blob may be shared content).
    local blob_pre=false
    artifact_backend_head "$hash" && blob_pre=true

    # Store blob (idempotent atomic put + presence verify) and warm the cache
    # from the verified local bytes — the write-back wrapper (design §5).
    artifact_store "$hash" "$file"

    artifact_manifest create "$handle" "$hash" "backend=$backend"
    require_python >/dev/null
    if [[ -n "$name" ]]; then
        "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$task_file" artifacts \
            "handle=$handle" "kind=$kind" "name=$name"
    else
        "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$task_file" artifacts \
            "handle=$handle" "kind=$kind"
    fi

    # Commit the trio (blob + manifest + task) as one path-scoped commit.
    # Only local-backend blobs live on the data branch; other backends hold
    # their blobs outside git, so only manifest + task file are staged.
    local manifest_rel commit_paths=()
    manifest_rel="$(artifact_manifest_relpath "$handle")"
    [[ "$backend" == "local" ]] && commit_paths+=( "$(artifact_local_blob_relpath "$hash")" )
    commit_paths+=( "$manifest_rel" "$task_file" )
    if ! _artifact_commit "ait: Create artifact ${handle} on t${task_id}" \
            "${commit_paths[@]}"; then
        _artifact_rollback_create "$task_file" "$manifest_rel" "$handle" "$backend" "$hash" "$blob_pre"
        die "ait artifact create: commit failed — rolled back to pre-create state"
    fi
    success "Created artifact ${handle} (v1 ${hash}) on t${task_id}"
    printf 'HANDLE:%s\n' "$handle"
}

# _artifact_rollback_create -- restore HEAD copies of pre-existing files and
# remove newly-created ones, so a failed commit leaves no drift (under lock).
# The txn's backend activation is still in effect, so backend_delete routes
# to the same backend the blob was put on.
_artifact_rollback_create() {
    local task_file="$1" manifest_rel="$2" handle="$3" backend="$4" hash="$5" blob_pre="$6"
    # Task .md always pre-exists -> unstage + restore from HEAD.
    task_git reset -q -- "$task_file" >/dev/null 2>&1 || true
    task_git checkout -- "$task_file" >/dev/null 2>&1 || true
    # Manifest: create dies on pre-existing, so it is always new here -> delete.
    task_git reset -q -- "$manifest_rel" >/dev/null 2>&1 || true
    rm -f "$(artifact_manifest_dir)/${handle#art:}.json"
    # Blob: only created this op -> unstage (local only — nothing staged for
    # other backends) + delete from the backend.
    if [[ "$blob_pre" == false ]]; then
        if [[ "$backend" == "local" ]]; then
            task_git reset -q -- "$(artifact_local_blob_relpath "$hash")" >/dev/null 2>&1 || true
        fi
        artifact_backend_delete "$hash"
    fi
}

# ── Verb: update ─────────────────────────────────────────────────────────────

cmd_update() {
    local handle="${1:-}" file="${2:-}"
    [[ -n "$handle" && -n "$file" && $# -eq 2 ]] \
        || die "Usage: ait artifact update <handle> <file>"
    [[ -f "$file" ]] || die "ait artifact update: not a file: $file"
    [[ -n "$(artifact_manifest get "$handle")" ]] \
        || die "ait artifact update: no manifest for ${handle} — create it first (ait artifact create)"
    with_attach_lock _artifact_update_txn "$handle" "$file"
}

# _artifact_update_txn -- store a new version + repoint `current`. Touches the
# blob store and the manifest ONLY — never any task file (the core AC of the
# stable-handle/mutable-manifest split).
_artifact_update_txn() {
    local handle="$1" file="$2"
    local hash current
    hash="$(artifact_sha256 "$file")"
    current="$(artifact_manifest current "$handle")"
    if [[ "$hash" == "$current" ]]; then
        success "Artifact ${handle} is already current (${hash}) — nothing to do"
        return 0
    fi

    local backend; backend="$(_artifact_manifest_backend "$handle")"
    # Fails closed pre-mutation if the manifest names an unregistered backend.
    artifact_registry_activate "$backend"

    local size cap
    size="$(wc -c < "$file" | tr -d '[:space:]')"
    cap="$(_artifact_size_cap_bytes)"
    if (( size > cap )); then
        die "ait artifact update: file is ${size} bytes, over the ${cap}-byte cap (artifact_max_size_mb in aitasks/metadata/project_config.yaml; default 25 MB)"
    fi

    local blob_pre=false
    artifact_backend_head "$hash" && blob_pre=true

    # Write-back: put + presence verify + warm cache from local bytes (§5).
    artifact_store "$hash" "$file"
    artifact_manifest set-current "$handle" "$hash"

    local manifest_rel commit_paths=()
    manifest_rel="$(artifact_manifest_relpath "$handle")"
    commit_paths=( "$manifest_rel" )
    [[ "$backend" == "local" ]] && commit_paths+=( "$(artifact_local_blob_relpath "$hash")" )
    if ! _artifact_commit "ait: Update artifact ${handle}" "${commit_paths[@]}"; then
        # Manifest pre-exists -> restore from HEAD; blob only if newly created.
        task_git reset -q -- "${commit_paths[@]}" >/dev/null 2>&1 || true
        task_git checkout -- "$manifest_rel" >/dev/null 2>&1 || true
        if [[ "$blob_pre" == false && "$backend" == "local" ]]; then
            artifact_backend_delete "$hash"
        fi
        die "ait artifact update: commit failed — rolled back"
    fi
    success "Updated artifact ${handle} — current is now ${hash}"
}

# ── Verb: move ───────────────────────────────────────────────────────────────

cmd_move() {
    local handle="" target=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --to) target="${2:-}"; shift 2 ;;
            --)   shift ;;
            -*)   die "ait artifact move: unknown option $1" ;;
            *) if [[ -z "$handle" ]]; then handle="$1"
               else die "ait artifact move: too many arguments"; fi; shift ;;
        esac
    done
    [[ -n "$handle" && -n "$target" ]] || die "Usage: ait artifact move <handle> --to <backend>"
    [[ -n "$(artifact_manifest get "$handle")" ]] || die "ait artifact move: no manifest for ${handle}"
    with_attach_lock _artifact_move_txn "$handle" "$target"
}

# _artifact_move_txn -- safe backend move: copy EVERY version blob to the
# registered target, verify presence, then repoint the manifest. Properties:
# non-destructive (source blobs stay — recoverable / shared-store safe),
# resumable (a re-run after any failure converges; a same-backend re-run is a
# clean no-op), and no task-file path is ever staged (stable-handle split).
_artifact_move_txn() {
    local handle="$1" target="$2" source
    source="$(_artifact_manifest_backend "$handle")" \
        || die "ait artifact move: cannot read backend for ${handle}"
    if [[ "$target" == "$source" ]]; then
        success "Artifact ${handle} is already on backend '${target}' — nothing to do"
        return 0
    fi
    # Validate the TARGET first: dies pre-mutation if unregistered/misconfigured.
    artifact_registry_activate "$target"

    local versions=() v
    while IFS= read -r v; do [[ -n "$v" ]] && versions+=( "$v" ); done \
        < <(artifact_manifest versions "$handle")
    (( ${#versions[@]} > 0 )) || die "ait artifact move: ${handle} has no versions"

    # Phase 1: resolve EVERY version from the source into the local cache
    # (verified bytes) BEFORE touching the target — one activation each way.
    local srcs=() p
    artifact_registry_activate "$source"
    for v in "${versions[@]}"; do
        p="$(artifact_resolve "$v")" \
            || die "ait artifact move: could not resolve ${v} from backend '${source}' — nothing moved"
        srcs+=( "$p" )
    done

    # Phase 2: copy to the target + verify presence per blob (a failed put
    # does not abort under the lock's suppressed errexit — the head verify is
    # load-bearing; backend CONTENT correctness is owned by dir-put's
    # pre-existing-dest verification / local resolve's canonical check).
    # Track per-version pre-existence so rollback deletes only what WE created.
    local i commit_paths=() new_hashes=()
    artifact_registry_activate "$target"
    for i in "${!versions[@]}"; do
        artifact_backend_head "${versions[$i]}" || new_hashes+=( "${versions[$i]}" )
        artifact_backend_put "${versions[$i]}" "${srcs[$i]}" \
            || die "ait artifact move: put failed for ${versions[$i]} on '${target}'"
        artifact_backend_head "${versions[$i]}" \
            || die "ait artifact move: ${versions[$i]} not present on '${target}' after put"
        [[ "$target" == "local" ]] \
            && commit_paths+=( "$(artifact_local_blob_relpath "${versions[$i]}")" )
    done

    # Phase 3: repoint + commit (manifest always; blobs only for a local target).
    artifact_manifest set-backend "$handle" "$target"
    local manifest_rel; manifest_rel="$(artifact_manifest_relpath "$handle")"
    commit_paths+=( "$manifest_rel" )
    if ! _artifact_commit "ait: Move artifact ${handle} to backend ${target}" "${commit_paths[@]}"; then
        # Restore HEAD state fully: unstage everything, restore the manifest,
        # and delete only the target blobs THIS move created (pre-existing
        # target blobs stay). Target activation is still in effect.
        task_git reset -q -- "${commit_paths[@]}" >/dev/null 2>&1 || true
        task_git checkout -- "$manifest_rel" >/dev/null 2>&1 || true
        local nh
        for nh in ${new_hashes[@]+"${new_hashes[@]}"}; do
            artifact_backend_delete "$nh" || true
        done
        die "ait artifact move: commit failed — manifest and target backend restored to pre-move state, re-run to retry"
    fi
    success "Moved ${handle} to backend '${target}' (${#versions[@]} version(s) copied; source blobs on '${source}' were NOT deleted)"
}

# ── Verb: rm ─────────────────────────────────────────────────────────────────

cmd_remove() {
    local task_id="${1:-}" ref="${2:-}"
    [[ -n "$task_id" && -n "$ref" ]] || die "Usage: ait artifact rm <task> <handle-or-name>"
    task_id="${task_id#t}"
    local task_file; task_file="$(resolve_task_file "$task_id")"
    with_attach_lock _artifact_rm_txn "$task_id" "$task_file" "$ref"
}

_artifact_rm_txn() {
    local task_id="$1" task_file="$2" ref="$3"
    local handle
    handle="$(_artifact_resolve_ref "$task_file" "$ref")" \
        || die "ait artifact rm: no artifact matching '$ref' on t${task_id}"

    # Capture manifest state BEFORE mutation. A missing manifest is the
    # stale-reference case (failed/manual cleanup, data-branch inconsistency):
    # still remove the broken frontmatter entry so the task stays repairable
    # through the same verb — just skip the manifest/blob work.
    local manifest_json versions=()
    manifest_json="$(artifact_manifest get "$handle")"
    if [[ -n "$manifest_json" ]]; then
        while IFS= read -r v; do
            [[ -n "$v" ]] && versions+=( "$v" )
        done < <(artifact_manifest versions "$handle")
    fi
    local backend="local"
    [[ -n "$manifest_json" ]] && backend="$(_artifact_manifest_backend "$handle")"

    require_python >/dev/null
    "$(require_python)" "$SCRIPT_DIR/lib/frontmatter_patch.py" remove "$task_file" artifacts \
        --match-key handle --match-val "$handle"

    if [[ -z "$manifest_json" ]]; then
        warn "manifest for ${handle} is missing — removing the stale frontmatter reference only"
        if ! _artifact_commit "ait: Remove stale artifact reference ${handle} from t${task_id}" "$task_file"; then
            task_git reset -q -- "$task_file" >/dev/null 2>&1 || true
            task_git checkout -- "$task_file" >/dev/null 2>&1 || true
            die "ait artifact rm: commit failed — rolled back"
        fi
        success "Removed stale artifact reference ${handle} from t${task_id}"
        return 0
    fi

    # Another task (active, archived, or Folded — revivable) still lists the
    # handle -> keep the manifest, drop only this task's entry.
    local other
    other="$(_artifact_handle_referenced_elsewhere "$handle" "$task_file")"
    if [[ -n "$other" ]]; then
        if ! _artifact_commit "ait: Remove artifact ${handle} from t${task_id}" "$task_file"; then
            task_git reset -q -- "$task_file" >/dev/null 2>&1 || true
            task_git checkout -- "$task_file" >/dev/null 2>&1 || true
            die "ait artifact rm: commit failed — rolled back"
        fi
        success "Removed artifact ${handle} from t${task_id}; manifest kept (still referenced by ${other})"
        return 0
    fi

    # Last reference -> delete the manifest, then sweep version blobs that
    # nothing else owns. A blob is KEPT if the attachment ledger has a meta
    # file for it (an attachment owns it) or any remaining manifest still
    # references it. Deletions are ordinary data-branch commits — recoverable
    # from git history.
    local manifest_rel manifest_path
    manifest_rel="$(artifact_manifest_relpath "$handle")"
    manifest_path="$(artifact_manifest_dir)/${handle#art:}.json"
    rm -f "$manifest_path"

    local del_paths=( "$task_file" "$manifest_rel" )
    local swept=0
    if [[ "$backend" == "local" ]]; then
        artifact_registry_activate local
        local remaining h
        if ! remaining="$(artifact_manifest referenced-hashes)"; then
            # The fail-closed tree scan died (a malformed manifest somewhere —
            # its path is in the error above). The task file is already patched
            # and this manifest already deleted, both uncommitted — restore
            # BOTH from HEAD so the tree is left untouched and the same rm can
            # be re-run once the named manifest is repaired. (Computing the
            # scan before mutation is not an option: it would include this
            # doomed manifest's own hashes and block the whole sweep.)
            task_git reset -q -- "$task_file" "$manifest_rel" >/dev/null 2>&1 || true
            task_git checkout -- "$task_file" "$manifest_rel" >/dev/null 2>&1 || true
            die "ait artifact rm: could not compute remaining manifest references (see the malformed-manifest error above) — rolled back; repair that manifest and re-run"
        fi
        for h in ${versions[@]+"${versions[@]}"}; do
            [[ -f "$(attach_meta_dir)/$(artifact_shard_path "$h").json" ]] && continue
            printf '%s\n' "$remaining" | grep -qxF "$h" && continue
            artifact_backend_delete "$h"
            del_paths+=( "$(artifact_local_blob_relpath "$h")" )
            swept=$((swept + 1))
        done
    else
        warn "backend '${backend}' is not local — backend blobs were not deleted (cross-backend orphan reaping is t1135)"
    fi

    if ! _artifact_commit "ait: Remove artifact ${handle} from t${task_id}" "${del_paths[@]}"; then
        task_git reset -q -- "${del_paths[@]}" >/dev/null 2>&1 || true
        task_git checkout -- "${del_paths[@]}" >/dev/null 2>&1 || true
        die "ait artifact rm: commit failed — rolled back"
    fi
    success "Removed artifact ${handle} from t${task_id} (manifest deleted, ${swept} orphan blob(s) swept; recoverable from data-branch history)"
}

# ── Verb: ls ─────────────────────────────────────────────────────────────────

cmd_list() {
    local task_id="${1:-}"
    if [[ -z "$task_id" ]]; then
        # Global view: every manifest.
        local handles h cur backend
        handles="$(artifact_manifest list)"
        if [[ -z "$handles" ]]; then
            echo "No artifacts."
            return 0
        fi
        printf '%-40s  %-14s  %s\n' "HANDLE" "CURRENT" "BACKEND"
        while IFS= read -r h; do
            [[ -n "$h" ]] || continue
            cur="$(artifact_manifest current "$h")"
            backend="$(_artifact_manifest_backend "$h")"
            local short="${cur#sha256:}"
            printf '%-40s  %-14s  %s\n' "$h" "${short:0:12}" "$backend"
        done <<< "$handles"
        return 0
    fi

    task_id="${task_id#t}"
    local task_file records
    task_file="$(resolve_task_file "$task_id")"
    records="$(_artifact_records "$task_file")"
    if [[ -z "$records" ]]; then
        echo "No artifacts."
        return 0
    fi
    printf '%-40s  %-12s  %-14s  %-5s  %-8s  %s\n' "HANDLE" "KIND" "CURRENT" "VERS" "BACKEND" "NAME"
    local h k n cur nvers backend
    while IFS=$'\t' read -r h k n; do
        [[ -n "$h" ]] || continue
        if [[ -n "$(artifact_manifest get "$h" 2>/dev/null)" ]]; then
            cur="$(artifact_manifest current "$h")"
            nvers="$(artifact_manifest versions "$h" | grep -c . || true)"
            backend="$(_artifact_manifest_backend "$h")"
            local short="${cur#sha256:}"
            printf '%-40s  %-12s  %-14s  %-5s  %-8s  %s\n' \
                "$h" "${k:-?}" "${short:0:12}" "$nvers" "$backend" "${n:-}"
        else
            warn "artifact ${h} has no manifest — the reference is stale (repair with: ait artifact rm ${task_id} ${h})"
            printf '%-40s  %-12s  %-14s  %-5s  %-8s  %s\n' "$h" "${k:-?}" "?" "?" "?" "${n:-}"
        fi
    done <<< "$records"
}

# ── Verb: get ────────────────────────────────────────────────────────────────

cmd_get() {
    local handle="" out="" version=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --out)     out="${2:-}";     shift 2 ;;
            --version) version="${2:-}"; shift 2 ;;
            --)        shift ;;
            -*)        die "ait artifact get: unknown option $1" ;;
            *) if [[ -z "$handle" ]]; then handle="$1"
               else die "ait artifact get: too many arguments"; fi; shift ;;
        esac
    done
    [[ -n "$handle" ]] || die "Usage: ait artifact get <handle> [--out <path>] [--version <sha256:hash>]"
    [[ -n "$(artifact_manifest get "$handle")" ]] \
        || die "ait artifact get: no manifest for ${handle}"

    local hash
    if [[ -n "$version" ]]; then
        artifact_manifest versions "$handle" | grep -qxF "$version" \
            || die "ait artifact get: ${version} is not a version of ${handle} (see: ait artifact versions ${handle})"
        hash="$version"
    else
        hash="$(artifact_manifest current "$handle")"
    fi

    local backend; backend="$(_artifact_manifest_backend "$handle")"
    artifact_registry_activate "$backend"
    # artifact_resolve verifies the resolved bytes' hash itself (t1076_1) — no
    # caller-side re-hash needed.
    local cache; cache="$(artifact_resolve "$hash")"
    if [[ -n "$out" ]]; then
        cp "$cache" "$out"
        success "Wrote $out"
    else
        cat "$cache"
    fi
}

# ── Verb: versions ───────────────────────────────────────────────────────────

cmd_versions() {
    local handle="${1:-}"
    [[ -n "$handle" && $# -eq 1 ]] || die "Usage: ait artifact versions <handle>"
    [[ -n "$(artifact_manifest get "$handle")" ]] \
        || die "ait artifact versions: no manifest for ${handle}"
    local current v
    current="$(artifact_manifest current "$handle")"
    while IFS= read -r v; do
        [[ -n "$v" ]] || continue
        if [[ "$v" == "$current" ]]; then
            printf '* %s\n' "$v"
        else
            printf '  %s\n' "$v"
        fi
    done < <(artifact_manifest versions "$handle")
}

main() {
    local verb="${1:-}"
    case "$verb" in
        ""|--help|-h|help) show_help ;;
        create)     shift; cmd_create "$@" ;;
        update)     shift; cmd_update "$@" ;;
        move)       shift; cmd_move "$@" ;;
        rm|remove)  shift; cmd_remove "$@" ;;
        ls|list)    shift; cmd_list "$@" ;;
        get)        shift; cmd_get "$@" ;;
        versions)   shift; cmd_versions "$@" ;;
        *)          die "Unknown verb: $verb (try 'ait artifact help')" ;;
    esac
}

main "$@"

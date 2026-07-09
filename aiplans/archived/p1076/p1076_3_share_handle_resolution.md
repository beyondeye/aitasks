---
Task: t1076_3_share_handle_resolution.md
Parent Task: aitasks/t1076_unified_artifact_implementation.md
Sibling Tasks: aitasks/t1076/t1076_4_artifact_producing_gate_archetype.md
Archived Sibling Plans: aiplans/archived/p1076/p1076_1_storage_abstraction_generalization.md, aiplans/archived/p1076/p1076_2_artifact_pointer_version_model.md
Worktree: (current branch, profile fast)
Branch: main
Base branch: main
---

# t1076_3 — Share-handle resolution + cache wrapper

## Context

Third substrate piece of the unified artifact model (parent t1076, design spec
`aidocs/unified_artifact_design.md` §5, §6, §11 row 3). t1076_1 shipped the
storage seam (`artifact_backend` 5-op dispatcher, self-verifying
`artifact_resolve`, per-artifact manifests with a `backend` field whose
registry membership was explicitly deferred to this task). t1076_2 shipped the
`ait artifact` CLI and the stable-handle/mutable-manifest split, exporting
`ARTIFACT_BACKEND` from the manifest before every resolve/put — but backend
selection is env-var-only, only the `local` backend exists, and nothing reads
backend configuration from project config. This task adds the **sharing
dimension**: a git-tracked `artifacts:` registry block in
`aitasks/metadata/project_config.yaml` describing how to reach backends, so an
`art:<id>` handle authored on one machine resolves on any machine with the
project config (handle → manifest → config → backend get → hash verify →
cache → local path).

## Settled decisions

**User-confirmed (this session — binding):**

1. **Ship a `dir` backend in this task** — filesystem-directory backend with a
   configured absolute root (NAS / mounted share / USB). First config-driven
   backend, reference implementation for t1089 (S3) / t1090 (GDrive), and
   makes both task ACs testable with real bytes.
2. **Implement `ait artifact move <handle> --to <backend>`** replacing
   `cmd_stub` (aitask_artifact.sh:355-359): generic safe move — copy every
   version blob to the registered target, verify presence, repoint via
   `artifact_manifest set-backend` (test-pinned since t1076_1,
   tests/test_artifact_manifest_lib.sh §D). Non-destructive: source blobs stay.

**Design decisions (recorded here, with rejected alternatives):**

3. **Backend name IS the adapter name** (`local`, `dir`, later `s3`,
   `gdrive`) — one instance per adapter, keyed under `artifacts.backends:`.
   `local` is always implicitly registered, zero-config. *Rejected:*
   multi-instance name→type indirection (`backends.nas1.type: dir`) — no
   current need (one shared store per project is the realistic shape), and the
   manifest `backend` field + dispatcher `case` already key on adapter names.
4. **`artifact_max_size_mb` stays a flat top-level key.** The new `artifacts:`
   block is a *backend registry*, not a general artifact-settings home. Moving
   the cap would churn `_artifact_size_cap_bytes` (aitask_artifact.sh:134-142),
   its test, and die-message text for zero functional gain. *Rejected:*
   nesting as `artifacts.max_size_mb`.
5. **Python bridge = new dedicated `lib/artifact_registry.py`** (CLI shape
   mirrors `artifact_manifest.py`: `--config <path> <subcommand>`), loading
   the YAML **directly with `yaml.safe_load`** and explicit root-shape
   handling (see Step 1) — `config_utils.load_yaml_config` is the pattern
   reference but returns `{}` for a non-mapping root (config_utils.py:162-164),
   a fail-open the registry must not inherit. *Rejected:* (a) extending
   `resolve_config_path` — its contract is file-paths-only and it fail-opens
   (empty line, exit 0), the opposite of the fail-closed posture a backend
   registry needs; (b) inline heredoc python — the registry has real
   validation logic that needs its own unit-testable home and will grow with
   t1089/t1090; (c) reusing `load_yaml_config` as-is — silently masks a
   list-shaped config file.
6. **Registry vs dispatcher responsibility split:** the registry
   (`artifact_registry.{py,sh}`) validates *registration + configuration* (is
   the name in config, required keys present/sane) and exports adapter params;
   the dispatcher `_artifact_backend_call` (artifact_backend.sh:38-46) remains
   the *adapter* authority. The registry's Python also carries a
   `KNOWN_ADAPTERS` table so registering a not-yet-shipped adapter (`s3`
   today) dies actionably at activation, not deep in dispatch.
7. **`dir.path` must be absolute; the root must already exist** (die "is the
   share mounted?"); only shard subdirs are `mkdir -p`'d. A relative path is
   cwd-ambiguous across checkouts, and silently creating a missing NAS
   mountpoint would write blobs into the empty mountpoint dir (the
   unmounted-share data-loss trap).
8. **`rm` keeps the non-local warn** (aitask_artifact.sh:454-456) —
   dir-backend blobs are NOT swept on last-reference rm. Local-blob deletions
   are recoverable from data-branch history (the success message at :463
   promises this); dir-store deletions are not, and the store may be shared by
   multiple clones mid-fetch. Cross-backend orphan reaping is t1135's charter.
   Reword the warn to point at t1135. *Rejected:* sweeping via
   `artifact_backend_delete` — destructively asymmetric with the
   "recoverable" promise.
9. **`move` to the current backend = friendly no-op success** (mirrors
   update's same-bytes idempotence, :317-320). Load-bearing for crash
   recovery: a move that copied blobs but failed at commit is simply re-run;
   after the repoint lands, a re-run is a clean no-op.
10. **No skills/SKILL.md changes.** Precedent: `artifact_max_size_mb`
    (t1076_2) was never added to task-workflow's Project Configuration table.
    The `artifacts:` block is `ait artifact`-CLI-internal; its user-facing doc
    home is `seed/project_config.yaml`. Avoids the rendered-variant/goldens
    chain entirely.
11. **Config path read cwd-relative** as `aitasks/metadata/project_config.yaml`
    (matches `_artifact_size_cap_bytes`, :135 — `ait` cd's to repo root; test
    fixtures cd into the fixture repo).
12. **Attachments stay local-only** — `ait attach` guards and gc's
    `export ARTIFACT_BACKEND="local"` are untouched. Verified: gc iterates
    attachment meta files only; dir-backend artifact blobs have no meta files
    and live outside the data worktree → invisible to gc; manifest versions
    block the sweep backend-independently via `referenced-hashes`. No gc
    change needed.

## Config schema (normative)

```yaml
# aitasks/metadata/project_config.yaml  (git-tracked, team-shared)
artifacts:
  default_backend: dir            # optional; backend `create` uses when --backend absent (default: local)
  backends:
    dir:
      path: /mnt/share/ait-artifacts   # REQUIRED, absolute; blobs at <path>/<2hex>/<62hex>
```

Secrets NEVER live here — t1089/t1090 put credentials in env vars / gitignored
per-user files; this block carries only non-secret coordinates (pre-agreed in
both task files).

## Blast radius

**New:** `.aitask-scripts/lib/artifact_registry.py`,
`.aitask-scripts/lib/artifact_registry.sh`,
`.aitask-scripts/lib/artifact_backends/dir.sh`,
`tests/test_artifact_dir_backend.sh`, `tests/test_artifact_share_resolution.sh`.

**Edited:** `.aitask-scripts/lib/artifact_backend.sh` (2 extension-point
markers + "known:" string), `.aitask-scripts/lib/artifact_cache.sh` (new
`artifact_store`), `.aitask-scripts/aitask_artifact.sh` (registry wiring at 4
export sites, create default-backend, non-local commit paths, `cmd_move`,
help, header STATE), `.aitask-scripts/lib/artifact_manifest.py` (comment only,
lines 25-28), `ait` (help line: "move pending" → real verb),
`seed/project_config.yaml` (commented `artifacts:` block),
`aidocs/unified_artifact_design.md` (§5, §6, §11 row 3),
`aidocs/task_attachments_design.md` (§5 + universal-cache note, backend
table `dir` row), `tests/test_artifact_cli.sh` (reword the "non-local backend
dies" and move-stub assertions — behavior-compatible).

**Verified NOT touched:** `aitask_attach.sh` (gc + attach add guard, decision
12), `artifact_manifest.{py,sh}` logic, `artifact_utils.sh`, board Python,
fold/decref paths (backend-agnostic — they operate on manifests/frontmatter),
`tests/lib/test_scaffold.sh` (new libs not on `ait`'s source-on-startup
chain), whitelists (CLI-invoked only, attach precedent), `config_utils.py`
(imported read-only), live `aitasks/metadata/project_config.yaml` (no
`artifacts:` block needed for local-only default; teams opt in).

## Implementation steps

### Step 1 — `lib/artifact_registry.py` (new, ~120 lines)

CLI: `artifact_registry.py --config <path> <subcommand>`. Loads the YAML
**directly with `yaml.safe_load`** (see "Config loading" below — do NOT use
`config_utils.load_yaml_config`). Exit non-zero + stderr on any failure —
**fail-closed on malformed config** (`artifacts:` not a dict, `backends:` not
a dict, a backend entry not a dict, YAML parse error, non-mapping root → die
naming the file and the problem).

```python
BACKEND_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")   # same shape as artifact_manifest.py:59

# BACKEND-EXTENSION-POINT (registry): adapter name -> {config_key: (ENV_VAR, validator)}
KNOWN_ADAPTERS = {
    "dir": {"path": ("ARTIFACT_DIR_ROOT", "abs_path")},
    # s3 (t1089), gdrive (t1090) add entries here.
}
```

**Config loading (fail-closed, does NOT use `load_yaml_config`):** the
registry loads the file with `yaml.safe_load` directly and distinguishes all
four states explicitly — `config_utils.load_yaml_config` returns `{}` for a
syntactically-valid file whose root is not a mapping (config_utils.py:162-164),
which would silently treat a list-shaped `project_config.yaml` as "no config"
and fail open to `local`:
- file missing → `{}` (fine: zero-config default, `local` resolves).
- YAML parse error → die naming the file and the parse problem.
- root is `None` (empty file) → `{}`.
- root parses but is **not a mapping** → die "aitasks/metadata/project_config.yaml:
  top-level YAML is not a mapping — fix the file". (Contrast-only note:
  `config_utils` remains the pattern reference for CLI/config helpers, but
  its fail-open root behavior is exactly wrong for a registry — per
  decision 5, the load is direct.)

Subcommands:
- `backend-env <name>` — `local` → print nothing, exit 0. Else: name not
  under `artifacts.backends` → die "backend '<name>' is not registered — add
  artifacts.backends.<name> to aitasks/metadata/project_config.yaml". Name
  not in `KNOWN_ADAPTERS` → die "no adapter for backend '<name>' (known:
  local, dir; s3/gdrive arrive with t1089/t1090)". Missing/empty required
  key → die naming it. `dir.path` not absolute (`os.path.isabs`) → die. On
  success print one `ENV_VAR=value` line per param.
- `default-backend` — print `artifacts.default_backend` if set (must be
  `local` or registered+known, else die), else `local`.
- `list` — registered names, `local` always first.

### Step 2 — `lib/artifact_registry.sh` (new, ~70 lines)

`_AIT_ARTIFACT_REGISTRY_LOADED` guard; dir-detection
`_AIT_ARTIFACT_REGISTRY_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`
+ sources `python_resolve.sh` itself (exact pattern:
artifact_manifest.sh:27-29); `die` from caller-sourced terminal_compat.

```bash
_AIT_ARTIFACT_REGISTRY_CONFIG="aitasks/metadata/project_config.yaml"
# BACKEND-EXTENSION-POINT (params): every adapter param var, so activation
# always clears the previous backend's params (no cross-activation leakage —
# load-bearing for `move`, which activates source then target in one process).
_AIT_ARTIFACT_REGISTRY_PARAM_VARS=( ARTIFACT_DIR_ROOT )

artifact_registry_activate() {
    local name="${1:-}"
    [[ -n "$name" ]] || die "artifact_registry_activate: backend name required"
    local v; for v in "${_AIT_ARTIFACT_REGISTRY_PARAM_VARS[@]}"; do unset "$v"; done
    if [[ "$name" == "local" ]]; then export ARTIFACT_BACKEND="local"; return 0; fi
    local py out; py="$(require_python)"
    out="$("$py" "$_AIT_ARTIFACT_REGISTRY_DIR_SELF/artifact_registry.py" \
            --config "$_AIT_ARTIFACT_REGISTRY_CONFIG" backend-env "$name")" \
        || die "artifact_registry: cannot activate backend '$name' (see error above)"
    local line k val
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        k="${line%%=*}"; val="${line#*=}"
        [[ "$k" =~ ^ARTIFACT_[A-Z0-9_]+$ ]] || die "artifact_registry: unexpected param line '$line'"
        export "$k=$val"
    done <<< "$out"
    export ARTIFACT_BACKEND="$name"
}

artifact_registry_default_backend() {  # capture-safe printer
    local py; py="$(require_python)"
    "$py" "$_AIT_ARTIFACT_REGISTRY_DIR_SELF/artifact_registry.py" \
        --config "$_AIT_ARTIFACT_REGISTRY_CONFIG" default-backend
}
```

The `|| die` on the capture is **mandatory** — every caller runs inside
`with_attach_lock`'s errexit-suppressed call tree (p1076_1 Final Notes; gc
precedent comment at aitask_attach.sh). The `^ARTIFACT_[A-Z0-9_]+$` guard on
exported names is load-bearing: config-driven strings must never choose
arbitrary env var names.

### Step 3 — `lib/artifact_backends/dir.sh` (new, ~70 lines)

Mirror local.sh naming exactly (`artifact_dir_{head,put,get,delete,list}`),
`_AIT_ARTIFACT_BACKEND_DIR_BACKEND_LOADED` guard (note: local.sh's guard is
`_AIT_ARTIFACT_BACKEND_LOCAL_LOADED`; pick `_AIT_ARTIFACT_BACKEND_DIRFS_LOADED`
or similar that cannot collide with `_AIT_ARTIFACT_BACKEND_DIR`, which is
already a *path variable* in artifact_backend.sh:29 — naming hazard).

```bash
_artifact_dir_root() {
    [[ -n "${ARTIFACT_DIR_ROOT:-}" ]] || die "artifact_dir: ARTIFACT_DIR_ROOT not set — activate via artifact_registry_activate dir"
    [[ -d "$ARTIFACT_DIR_ROOT" ]] || die "artifact_dir: backend root not found: $ARTIFACT_DIR_ROOT (is the share mounted?)"
    printf '%s' "$ARTIFACT_DIR_ROOT"
}
_artifact_dir_blob_path() { printf '%s/%s' "$(_artifact_dir_root)" "$(artifact_shard_path "$1")"; }
```

- Layout: `<root>/<2hex>/<62hex>` (same `artifact_shard_path` sharding; no
  `blobs/` intermediate — the root IS the store).
- `put`: idempotent atomic, **with content verification of a pre-existing
  dest** (deliberate deviation from local.sh's bare `[[ -f ]] && return 0`):
  if `$dest` exists, hash it — match → return 0 (true idempotence); mismatch
  → `warn` + atomic overwrite with the (provably correct) source bytes. A
  content-addressed store entry whose bytes don't hash to its own address is
  by definition corruption (atomic `mv` means no half-writes sit at a final
  name), and the source bytes we hold DO hash to the address, so the
  overwrite is a strict repair — mirroring the cache's self-heal philosophy.
  Without this, a previously interrupted/corrupted store state would make
  put+head succeed while a second checkout fetches bad bytes (resolve dies
  loudly there, but the store stays corrupt and the manifest is committed).
  *Rejected:* die on mismatch — local's "never auto-repair the canon" rule
  exists because local blobs are git-tracked (repair = data-branch surgery);
  the dir store has no history and the correct bytes are in hand. Then
  `mkdir -p` the *shard dir only*; `mktemp "$(dirname "$dest")/.put.XXXXXX"`
  + `cp` + `mv -f` (temp in the destination dir so `mv` is same-filesystem
  atomic on the NAS).
- `get`: `-` = stdout (local.sh:52-57 pattern).
- `head`/`delete`/`list`: mirror local.sh:33-35, 60-62, 65-77 (list scans
  `<root>/*/`).

### Step 4 — Wire the dispatcher (`lib/artifact_backend.sh`)

- Source marker (line 34): add `# shellcheck source=lib/artifact_backends/dir.sh`
  + `source "$_AIT_ARTIFACT_BACKEND_DIR/artifact_backends/dir.sh"` above it.
- Dispatch marker (line 43): add `dir)   "artifact_dir_${op}" "$@" ;;` above it.
- Line 44: `(known: local)` → `(known: local, dir)` (only occurrence repo-wide).

### Step 5 — `artifact_store` write-back helper (`lib/artifact_cache.sh`)

The §5 "write-back" half: store verified local bytes to the active backend AND
warm the cache **without a backend get round-trip**.

```bash
# artifact_store <hash> <file> -- write-back: verify <file> hashes to <hash>,
# put it to the active backend, VERIFY the backend reports it, then warm the
# universal cache from the verified LOCAL bytes (no backend round-trip).
# Every step carries an explicit `|| die`: this helper runs inside
# with_attach_lock transactions where errexit is suppressed (p1076_1).
artifact_store() {
    local hash="$1" file="$2" cache
    artifact_validate_hash "$hash" || die "artifact_store: invalid hash: '$hash'"
    [[ -f "$file" ]] || die "artifact_store: not a file: $file"
    [[ "$(artifact_sha256 "$file")" == "$hash" ]] \
        || die "artifact_store: $file does not hash to $hash"
    artifact_backend_put "$hash" "$file" || die "artifact_store: backend put failed for $hash"
    artifact_backend_head "$hash" \
        || die "artifact_store: backend does not report $hash after put — write-back failed"
    if [[ "${ARTIFACT_BACKEND:-local}" == "local" ]]; then
        artifact_resolve "$hash" >/dev/null    # symlink fast path + canonical verify
        return 0
    fi
    cache="$(artifact_cache_path "$hash")"
    mkdir -p "$(dirname "$cache")" || die "artifact_store: cannot create cache dir"
    local tmp; tmp="$(mktemp "$(dirname "$cache")/.store.XXXXXX")" || die "artifact_store: mktemp failed"
    if ! cp "$file" "$tmp" || ! mv -f "$tmp" "$cache"; then
        rm -f "$tmp"; die "artifact_store: could not warm cache for $hash"
    fi
    [[ "$(artifact_sha256 "$cache")" == "$hash" ]] \
        || { rm -f "$cache"; die "artifact_store: cache warm verification failed for $hash"; }
}
```

The post-put `head` verify catches a *lost* put (a failed `cp`/`mv` under
suppressed errexit does not abort the transaction — without the head check,
create/update could commit a manifest whose blob never landed on the NAS).
`head` proves **presence only** — backend *content* correctness is owned one
level down: the dir backend's `put` content-verifies a pre-existing dest
(Step 3), and the local branch's `artifact_resolve` call hash-verifies the
canonical blob. Do not present `head` as content verification.

### Step 6 — Wire `aitask_artifact.sh`

Source block (after line 42 `artifact_cache.sh`):
`source "$SCRIPT_DIR/lib/artifact_registry.sh"` (+ shellcheck directive).

**create** (`cmd_create` :187-221, `_artifact_create_txn` :224-278):
- Line 188: `backend="local"` → `backend=""`.
- Lines 209-210 (hard reject): replace with default resolution after arg parse:
  ```bash
  if [[ -z "$backend" ]]; then
      backend="$(artifact_registry_default_backend)" \
          || die "ait artifact create: could not resolve the default backend (see error above)"
  fi
  ```
- Line 226: `export ARTIFACT_BACKEND="$backend"` →
  `artifact_registry_activate "$backend"` (membership/config validation dies
  actionably here, pre-mutation).
- Lines 254-255: `artifact_backend_put` + `artifact_resolve >/dev/null` →
  `artifact_store "$hash" "$file"`.
- Lines 267-272 (commit trio): blob path conditional, mirroring update :339-342:
  ```bash
  local manifest_rel commit_paths=()
  manifest_rel="$(artifact_manifest_relpath "$handle")"
  [[ "$backend" == "local" ]] && commit_paths+=( "$(artifact_local_blob_relpath "$hash")" )
  commit_paths+=( "$manifest_rel" "$task_file" )
  ```
- `_artifact_rollback_create` (:282-295): add a `backend` parameter; the blob
  arm (`task_git reset` of blob_rel) runs only when local;
  `artifact_backend_delete "$hash"` runs for any backend when `blob_pre` is
  false (activation env still set inside the txn). Compute `blob_rel` only
  when local (it calls `artifact_local_blob_relpath` unconditionally today).

**update** (`_artifact_update_txn` :312-353):
- Line 323: `export ARTIFACT_BACKEND="$backend"` →
  `artifact_registry_activate "$backend"` (manifest-names-unregistered-backend
  fails closed before any mutation).
- Lines 335-336: put+resolve pair → `artifact_store "$hash" "$file"`.
- Rollback :344-349 already branches on local — unchanged.

**rm** (`_artifact_rm_txn`): line 433 `export ARTIFACT_BACKEND="local"` →
`artifact_registry_activate local` (uniformity); line 455 warn reworded:
`warn "backend '${backend}' is not local — backend blobs were not deleted (cross-backend orphan reaping is t1135)"`.

**get** (`cmd_get` :542-543): `export ARTIFACT_BACKEND="$backend"` →
`artifact_registry_activate "$backend"`. No other change — the read side
(`artifact_resolve`) needs zero changes for the new backend.

**help/header/dispatcher:** show_help line 65 drop "(not yet implemented)";
header STATE paragraph (:16-19) rewritten ("`move` is functional (t1076_3);
backends: local (zero-config) + dir (config-registered via
artifacts.backends); s3/gdrive: t1089/t1090"); `ait` help line for artifact:
"move pending" → include move.

### Step 7 — `cmd_move` (replaces `cmd_stub` :355-359 + dispatch :580)

```bash
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
    local srcs=()
    artifact_registry_activate "$source"
    for v in "${versions[@]}"; do
        local p
        p="$(artifact_resolve "$v")" \
            || die "ait artifact move: could not resolve ${v} from backend '${source}' — nothing moved"
        srcs+=( "$p" )
    done

    # Phase 2: copy to the target + verify presence per blob (put failures do
    # not abort under the lock's suppressed errexit — head verify is load-bearing;
    # content correctness is owned by dir-put's pre-existing-dest verification /
    # local resolve). Track per-version pre-existence for rollback.
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
```

Dispatch: `move) shift; cmd_move "$@" ;;`. Properties (comment block):
non-destructive, idempotent/resumable (re-run after any failure converges;
same-backend re-run is a no-op), no task-file path ever staged.

Phase-1 caveat: for a `local` source, `artifact_resolve` returns a symlinked
cache path — `cp` in the target backend's `put` follows symlinks (fine). For a
`dir` source the resolve fills the cache as regular files (fine).

### Step 8 — `tests/test_artifact_cli.sh` (behavior-compatible rewording only)

- §B "non-local backend dies" (`--backend s3`): still dies — `s3` is
  *unregistered* in that fixture (no `artifacts:` block). Rename the assert to
  "unregistered backend dies", update the expected message substring.
- §D move-stub assertions (`move ... --to s3` dies + manifest byte-identical):
  still hold (unregistered target dies pre-mutation). Retitle from "move is a
  stub" to "move to an unregistered backend dies pre-mutation".
- Header comment mentions "the move stub" → update.

### Step 9 — New test `tests/test_artifact_dir_backend.sh` (lib-level)

Fixture: legacy-mode git repo in mktemp (test_attach_local_backend.sh shape),
`XDG_CACHE_HOME=$TMP/xdg`, source terminal_compat, task_utils, python_resolve,
artifact_utils, artifact_backend, artifact_cache, artifact_registry. Write
`aitasks/metadata/project_config.yaml` with an `artifacts:` block pointing
`dir.path` at pre-created `$TMP/store`.

- **A. dir adapter round-trip:** activate dir → put/head/get/list/delete;
  blob lands at `$TMP/store/<2>/<62>`; `get -` stdout; idempotent double-put;
  no `.put.*` temp residue (atomicity smoke); **corrupt pre-existing dest
  self-heal:** pre-seed WRONG bytes at the target shard path → `put` warns and
  repairs (dest now hashes to its address), and a pre-seeded CORRECT dest is
  left untouched (no gratuitous rewrite — compare mtime or inode).
- **B. registry activation:** `activate dir` exports `ARTIFACT_BACKEND=dir` +
  `ARTIFACT_DIR_ROOT`; `activate local` afterwards **unsets**
  `ARTIFACT_DIR_ROOT` (leakage guard); `activate nosuch` dies in a subshell
  ("not registered"); registered-but-unknown adapter (`backends.s3:` fixture)
  dies naming t1089; `dir` with missing `path` dies; relative `path` dies;
  malformed YAML (`artifacts:` as a list) dies (fail-closed); **top-level
  non-mapping config** (whole file replaced by a YAML list/string) → both
  `backend-env dir` and `default-backend` die naming the file (must NOT
  silently fail open to `local`); missing config file → `default-backend`
  prints `local` (the intentional zero-config default, as the positive
  control beside the fail-closed cases);
  `default-backend` → `dir` from config, `local` when block absent, dies when
  set to an unregistered name.
- **C. resolver through dir:** put via dir, clear cache, `artifact_resolve` →
  cache is a **regular file** (`[[ -f && ! -L ]]`), bytes verify; corrupted
  cache copy self-heals from the dir store; missing root (`mv $TMP/store`
  away) → resolve dies with "is the share mounted?".
- **D. `artifact_store` write-back:** store on dir backend → blob in store AND
  cache warmed; delete the store blob → fresh `artifact_resolve` still
  succeeds from cache (proves no get round-trip needed); tampered source
  (file≠hash) dies before any put; **store-repair regression:** pre-seed
  wrong bytes at the shard path, `artifact_store` → the store blob is
  repaired, and a cache-cleared re-resolve returns correct bytes (the
  second-checkout corruption scenario, closed).

### Step 10 — New test `tests/test_artifact_share_resolution.sh` (CLI e2e, both ACs, move)

Separate file (fixture differs structurally from test_artifact_cli.sh: a
committed `artifacts:` config block, an out-of-repo store, a second clone).
Fixture = test_artifact_cli.sh shape + `mkdir -p "$TMP/store"` + config with
`default_backend: dir` and `backends.dir.path: $TMP/store`, committed at init.

- **A. create on dir:** `create 5 plan.html --kind html_plan --backend dir` →
  manifest `"backend": "dir"`, blob in `$TMP/store/<shard>`, **no** blob under
  `attachments/blobs/`, exactly one commit touching manifest+task only
  (`git show --name-only`), cache warmed (regular file).
- **B. default_backend from config:** create without `--backend` → manifest
  backend `dir`.
- **C. get via dir after cache clear:** `rm -rf "$TMP/xdg"` → `get --out` →
  bytes match; cache repopulated as a regular file.
- **D. AC 1 — second checkout:** `git clone -q "$REPO" "$TMP/repo2"`;
  `rm -rf "$TMP/xdg"`; in repo2 → `ait artifact get art:t5-htmlplan --out`
  succeeds (fetch), bytes verify, cache entry exists; a second get with the
  store root temporarily renamed still succeeds (proves the verified-cache
  leg). *The literal task AC.*
- **E. AC 2 — backend swap in config:** `cp -r "$TMP/store" "$TMP/store2"`;
  rewrite config `path:` to `$TMP/store2`; `rm -rf "$TMP/xdg"`; same get
  succeeds; assert **zero task-file and zero manifest diff**
  (`git status --porcelain -- aitasks/ artifacts/` empty + `cmp` of the task
  file against a pre-swap snapshot).
- **F. update on dir backend (write-back):** update with new bytes → manifest
  repointed, one commit **containing only the manifest**; delete the new blob
  from the store → get still returns v2 bytes (cache warmed at write time);
  restore blob; `get --version <v1>` fetches v1 from the store.
- **G. move suite:** local→dir with 2 versions → both shards in `$TMP/store`,
  manifest backend `dir`, source local blobs intact, one commit touching only
  the manifest, task file byte-identical, cache-cleared get serves from dir;
  dir→local → blobs under `attachments/blobs/` **and committed** (blob
  staging), get works with the store renamed away; move to unregistered
  target dies with manifest byte-identical (pre-mutation); same-backend move
  → exit 0, "nothing to do", zero new commits; move of missing handle dies;
  **commit-failure rollback:** force the commit to fail with an
  always-failing pre-commit hook (`printf 'exit 1' > .git/hooks/pre-commit;
  chmod +x` — `add` succeeds, `commit` fails, and the rollback's
  `reset`/`checkout` still work; an `.git/index.lock` would block the
  restore itself and make the test fail for the wrong reason), run a
  dir→local move → die message, manifest restored byte-identical, the newly
  copied local blobs are GONE (`git status --porcelain` empty — no dirty
  working-tree residue), while a target blob that pre-existed the move
  survives (pre-existence tracking is load-bearing); remove the hook and
  re-run the same move → succeeds (resumability positive control).
- **H. rm on dir backend:** last-reference rm deletes manifest + frontmatter
  entry, warns (t1135), **store blob survives**; commit contains task+manifest
  only.
- **I. unregistered-backend get fails closed:** manifest set-backend'd (via
  the lib) to a name absent from config → get dies actionably naming the
  config key.

### Step 11 — Seed + docs

- `seed/project_config.yaml`: insert a commented `artifacts:` block after the
  `attachments_gc_grace` section (~line 187), following its box-comment +
  commented-example pattern: purpose, "local always registered / zero-config",
  `default_backend`, `backends.dir.path` (absolute), **secrets-never-here**
  warning, **the same-path mount assumption** (the git-tracked `path` is one
  absolute path for the whole team — every participating machine must mount
  the share at that path; per-user mount differences need a symlink or a
  future per-user override), design-doc pointer.
- `aidocs/unified_artifact_design.md`: §5 — write-back wrapper implemented
  (`artifact_store`, t1076_3); §6 — "Proposed config home" → settled/
  implemented (the `artifacts:` registry, `lib/artifact_registry.{py,sh}`,
  name-is-adapter decision, `dir` first configured backend,
  `ait artifact move`), plus a note that the dir backend's "any machine with
  the project config" property additionally assumes the share is mounted at
  the same absolute path on every machine (true remotes — t1089/t1090 — carry
  no such assumption); §11 coverage row 3 → **Done (t1076_3)**.
- `aidocs/task_attachments_design.md`: §5 dispatcher paragraph +
  universal-cache section — write-back helper + registry note; backend table —
  add a `dir` (NAS/mounted share) row.
- `lib/artifact_manifest.py` :25-28 comment: "registry membership … is
  t1076_3's" → "membership is enforced at the registry layer
  (lib/artifact_registry.py) at activation time; the manifest keeps shape-only
  validation".
- Task file needs no AC rewording (no deviations). Task/plan commits via
  `./ait git`.

### Step 12 — Regression + lint

- New suites: `bash tests/test_artifact_dir_backend.sh`,
  `bash tests/test_artifact_share_resolution.sh`.
- Regressions: `test_artifact_cli.sh`, `test_artifact_manifest_lib.sh`,
  `test_attach_local_backend.sh`, `test_attach_archive_gc.sh`,
  `test_attach_gc_manifest_blocking.sh`, `test_artifact_fold_transfer.sh`,
  `test_attach_meta.sh`, `test_attach_task_delete_decref.sh`,
  `test_attach_fold_rebind.sh`.
- `bash -n` + `shellcheck` on: `aitask_artifact.sh`, `artifact_backend.sh`,
  `artifact_cache.sh`, `artifact_registry.sh`, `artifact_backends/dir.sh`.
- Commit: `feature: Add share-handle backend registry, dir backend, and move verb (t1076_3)`.

## Conventions

- `#!/usr/bin/env bash`, `set -euo pipefail` (executables), `_AIT_*_LOADED`
  guards, `die`/`warn`/`success` from terminal_compat; mutations under
  `with_attach_lock`; partial path-scoped commits (`_artifact_commit`);
  rollbacks restore HEAD state. New libs not on `./ait`'s source-on-startup
  chain → no test_scaffold registration; no whitelist entries.
- Code commits: `feature: ... (t1076_3)`; task/plan commits: `ait:` via
  `./ait git`.

## Verification (maps to the task's ACs)

1. **"A handle authored on one checkout resolves on a second checkout that
   has only the project config (clear cache, resolve, confirm
   fetch+cache+verify)"** — Step 10 §D: git clone of the fixture (manifests +
   config travel via git; blobs only in the external store), cache wiped,
   `ait artifact get` in the clone → bytes verified by `artifact_resolve`'s
   in-resolver hashing; cache-hit re-get with the store unmounted proves the
   cache leg. *Scope note:* the automated second checkout is same-machine, so
   it cannot catch per-user mount-path differences — the dir backend's
   contract assumes one team-wide absolute mount path (documented, Step 11);
   distinct-environment coverage is the planned real-mount manual
   verification.
2. **"Backend swap in config re-resolves the same handle without any
   task-file change"** — Step 10 §E: `dir.path` swapped to a moved store copy
   → same handle resolves, `git status` over `aitasks/` + `artifacts/` empty;
   plus §G local↔dir moves: manifest-only commits, task file byte-identical.
3. Config plumbing fail-closed (unregistered / unknown-adapter / missing-key /
   malformed YAML each die actionably) — Step 9 §B, Step 10 §I, each with the
   working positive control beside it.
4. No regression — Step 12 suite.

## Hazards (for the implementer)

1. **Errexit suppression inside `with_attach_lock` txns** (p1076_1 Final
   Notes): every load-bearing capture (`artifact_registry_default_backend`,
   `_artifact_manifest_backend` in move, `artifact_resolve` in move phase 1)
   and every backend `put` needs an explicit `|| die` / post-`head` verify.
   Steps 2, 5, 7 bake these in — do not "simplify" them away.
2. **Env leakage between `artifact_registry_activate` calls in `move`:** the
   `_AIT_ARTIFACT_REGISTRY_PARAM_VARS` unset-loop is the guard; Step 9 §B
   pins it.
3. **Unmounted-share trap:** `dir` never `mkdir -p`s the configured root —
   only shard subdirs; `_artifact_dir_root`'s existence check is the
   fail-closed gate (Step 9 §C).
4. **Guard-variable naming:** `_AIT_ARTIFACT_BACKEND_DIR` is already a *path*
   variable in artifact_backend.sh:29 — the dir backend's source guard must
   not collide with it.
5. **Config read is uncached per activation** — one python call per activate.
   Fine at CLI scale; do NOT memoize (would break same-process config swaps —
   AC 2's test shape).
6. **gc interplay:** verified safe with zero changes (decision 12).
7. **`head` is presence, not content:** never claim content verification from
   a head check. Content correctness lives in dir-put's pre-existing-dest
   verification (Step 3), local resolve's canonical check, and
   `artifact_resolve`'s in-resolver hashing on every fetch.
8. **`load_yaml_config` fails open on a non-mapping root** — the registry
   must load YAML directly and die on a non-mapping root (Step 1); reusing
   the helper here would silently turn a broken config into "default local".
9. **Move rollback must delete only NEWLY created target blobs** — track
   pre-existence per version before put (Step 7); deleting a pre-existing
   target blob on rollback would destroy independently-owned data.

## Step 9 reference (post-implementation)

Current-branch profile — no worktree/merge. Archive via
`./.aitask-scripts/aitask_archive.sh 1076_3`, push via `./ait git push`.
t1076_4 remains; parent archival waits for it.

## Risk

### Code-health risk: medium
- Registry activation replaces the 4 backend-selection sites inside
  errexit-suppressed `with_attach_lock` transactions; a silently-failed
  capture or put could commit a manifest whose blob never landed · severity:
  medium · → mitigation: in-plan (`artifact_store` post-put head verify;
  explicit `|| die` on every capture; Step 9 §D + Step 10 §F write-back tests)
- Env-var leakage between source/target activations in `move` could route a
  put at the wrong backend root · severity: medium · → mitigation: in-plan
  (param-var unset loop at activation start; leakage regression test Step 9 §B)
- The `dir` backend on an unmounted share could silently write into the empty
  mountpoint or fail confusingly · severity: medium · → mitigation: in-plan
  (root must pre-exist + absolute-path validation, "is the share mounted?"
  die; Step 9 §C) + t1142 (manual_verification_dir_backend_real_mount, after)
- Dispatcher/CLI edits touch the shared attach substrate (artifact_backend.sh
  is sourced by aitask_attach.sh) · severity: low · → mitigation: in-plan
  (dir.sh functions are inert unless activated; full attach regression suite
  Step 12)

### Goal-achievement risk: low
- The `artifacts:` config schema might not fit t1089/t1090's needs, forcing a
  redesign · severity: low · → mitigation: in-plan (schema verified against
  both task files' pinned expectations; KNOWN_ADAPTERS extension point;
  name-is-adapter decision recorded with its revisit condition)
- The two ACs are simulated with a filesystem store rather than a true remote
  · severity: low · → mitigation: in-plan (the dir backend exercises the
  identical resolution chain — config lookup, backend get, verify, cache;
  real-remote specifics are t1089/t1090's scope by design) +
  t1142 (manual_verification_dir_backend_real_mount, after)

### Planned mitigations
- timing: after | name: manual_verification_dir_backend_real_mount (created: t1142) | type: manual_verification | priority: medium | effort: low | addresses: unmounted-share code-health risk + simulated-AC goal-achievement risk | desc: Verify dir backend + share-handle resolution on a real mounted share (NAS/USB) across two DISTINCT checkouts/environments (ideally two machines, or at minimum two users/paths on one machine) — create/get/move against the mount, confirm the same-absolute-path assumption holds or fails clearly, unmount to confirm the fail-closed "is the share mounted?" path, confirm atomic put across the mount boundary

## Post-Review Changes

### Change Request 1 (2026-07-09 11:20)
- **Requested by user:** `artifact_dir_put` ran `cp "$src" "$tmp"` then
  `mv -f "$tmp" "$dest"` without checking the copy succeeded. In
  errexit-suppressed transaction trees (`with_attach_lock`), a failed/partial
  `cp` would not abort — `mv` would install truncated bytes at the
  content-addressed path and `put` would return success. `artifact_store`'s
  `head` check only proves presence and the pre-existing-dest verification
  only fires when the dest existed BEFORE the put, so create/update could
  commit a manifest that works locally (cache warmed from the source file)
  but serves corrupt store bytes to a fresh checkout.
- **Verification:** confirmed — nothing re-verified freshly-written dir-store
  bytes; the local backend is protected downstream (artifact_store's local
  branch runs artifact_resolve, which hash-verifies the canonical blob), the
  dir path had no equivalent.
- **Changes made:** `artifact_dir_put` is now atomic in the strong sense:
  `mktemp` failure dies; `cp` failure removes the temp and dies; the STAGED
  temp bytes are hash-verified against `$hash` before `mv` (catches
  disk-full / dropped-mount partial copies); `mv` failure removes the temp
  and dies. New regression asserts in test_artifact_dir_backend.sh §A: a put
  whose staged bytes fail verification dies, installs no store entry, and
  leaves no temp residue (47/47 pass; share-resolution 61/61 and CLI 82/82
  unchanged).
- **Files affected:** `.aitask-scripts/lib/artifact_backends/dir.sh`,
  `tests/test_artifact_dir_backend.sh`.

## Final Implementation Notes

- **Actual work done:** Everything in the plan landed as designed. New
  backend registry `lib/artifact_registry.py` (~180 lines: `backend-env` /
  `default-backend` / `list`; `KNOWN_ADAPTERS` extension table; fail-closed
  config loading via direct `yaml.safe_load` with explicit non-mapping-root
  die) + bash front `lib/artifact_registry.sh`
  (`artifact_registry_activate` with the param-var unset loop and the
  `^ARTIFACT_[A-Z0-9_]+$` export-name guard;
  `artifact_registry_default_backend`). New `dir` backend
  (`lib/artifact_backends/dir.sh`): sharded `<root>/<2>/<62>` store at an
  absolute configured path, root-must-exist "is the share mounted?" guard,
  strong-atomic content-verifying put (see CR1). Dispatcher gained the `dir`
  arm at both BACKEND-EXTENSION-POINT markers. `artifact_store <hash> <file>`
  in artifact_cache.sh is the §5 write-back wrapper (verify source → put →
  head verify → warm cache from local bytes, no get round-trip); create and
  update store through it. All four backend-selection sites in
  aitask_artifact.sh route through `artifact_registry_activate`; create
  resolves `artifacts.default_backend`; commit/rollback paths are
  backend-conditional (blob relpaths staged only for local). `cmd_move`
  replaced the stub: copy every version to the registered target (per-version
  pre-existence tracked), head-verify each, `set-backend` repoint,
  manifest-only commit, rollback deletes only newly-created target blobs;
  same-backend move is a friendly no-op. Seed template documents the
  `artifacts:` block (incl. secrets-never-here and the same-absolute-path
  mount assumption); design docs updated (§3 move paragraph, §5 write-back,
  §6 settled config home, §11 row 3 Done; attachments doc registry/write-back
  notes + `dir` backend-table row).
- **Deviations from plan:** None of substance. CR1 (below) strengthened
  `artifact_dir_put` beyond the planned pre-existing-dest verification to
  also verify freshly staged bytes.
- **Issues encountered:** (1) Two test-fixture bugs in the first draft of
  the share-resolution suite: the "local→dir move" artifact was created
  without `--backend local` while the fixture's `default_backend` was `dir`
  (making the move a same-backend no-op), and the rollback tree-cleanliness
  assert needed scoping to data paths (test scratch files are untracked in
  the fixture cwd). (2) An intended "dir→local move commits the blobs"
  assert initially targeted a round-tripped artifact whose local blobs had
  never left the data branch (non-destructive move) — nothing to commit;
  the test now uses a dir-born artifact. (3) The unmounted-root resolve test
  first failed because the resolver correctly served offline from the warm
  cache — the test clears the cache before unmounting (the offline-serve
  behavior is asserted separately).
- **Key decisions:** Backend name IS the adapter name (one instance per
  adapter; multi-instance indirection rejected until actually wanted);
  `artifact_max_size_mb` stays flat (the `artifacts:` block is a backend
  registry, not a settings home); registry loads YAML directly instead of
  `config_utils.load_yaml_config` (that helper fails open on a non-mapping
  root — exactly wrong for a registry); `rm` keeps the non-local warn (dir
  deletions are not git-recoverable; reaping is t1135); dir-store corruption
  is self-healed by put (bytes in hand provably hash to the address) while
  local canonical corruption still dies (git-tracked, repair = data-branch
  surgery).
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1076_4 (gate archetype) can target any
  registered backend by exporting nothing: `ait artifact create`'s
  `default_backend` resolution + `HANDLE:` output and `update`'s same-bytes
  idempotency are unchanged; on a configured project the gate's artifacts
  land on the shared backend automatically. t1089/t1090: add the adapter
  module in `lib/artifact_backends/<name>.sh`, a dispatch arm + source line
  at the two BACKEND-EXTENSION-POINT markers, a `KNOWN_ADAPTERS` entry
  (config keys → env vars + validators) in artifact_registry.py, and the
  param var(s) in `_AIT_ARTIFACT_REGISTRY_PARAM_VARS` (leakage guard);
  everything else (resolve, store, move, CLI) lights up without surgery.
  `artifact_store` is the put-side entry point — remote puts get the same
  presence verify + local-bytes cache warm for free.

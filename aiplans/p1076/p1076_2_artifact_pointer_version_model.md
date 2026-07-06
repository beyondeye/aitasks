---
Task: t1076_2_artifact_pointer_version_model.md
Parent Task: aitasks/t1076_unified_artifact_implementation.md
Sibling Tasks: aitasks/t1076/t1076_3_share_handle_resolution.md, aitasks/t1076/t1076_4_artifact_producing_gate_archetype.md
Archived Sibling Plans: aiplans/archived/p1076/p1076_1_storage_abstraction_generalization.md
Base branch: main
plan_verified: []
---

# t1076_2 — Artifact pointer/version model + `artifacts:` frontmatter

---
Task: t1076_2_artifact_pointer_version_model.md
Parent Task: aitasks/t1076_unified_artifact_implementation.md
Sibling Tasks: aitasks/t1076/t1076_3_share_handle_resolution.md, aitasks/t1076/t1076_4_artifact_producing_gate_archetype.md
Archived Sibling Plans: aiplans/archived/p1076/p1076_1_storage_abstraction_generalization.md
Worktree: (current branch, profile fast)
Branch: main
Base branch: main
---

## Context

Second substrate piece of the unified artifact model (parent t1076, design spec
`aidocs/unified_artifact_design.md` §3, §4, §9, §10). t1076_1 landed the storage
substrate: shared `artifact_backend` seam, universal verifying resolver
(`artifact_resolve`), and the per-artifact manifest primitive
(`lib/artifact_manifest.{py,sh}` — create/get/current/versions/set-current/
set-backend/list/referenced-hashes, all mutations under `with_attach_lock`).
This task builds the **artifact concept** on top: the stable `art:<id>` handle,
artifact-level operations, and the handle-only `artifacts:` frontmatter schema —
the stable-handle / mutable-manifest split. Deliverable is a new user-facing
CLI `ait artifact` (script `.aitask-scripts/aitask_artifact.sh`), modeled
directly on `aitask_attach.sh` (t1030), plus the frontmatter integration points.

## Settled decisions (user-confirmed this session)

1. **§10 reconciliation — keep `attachments:` separate.** `attachments:` stays
   the typed inline-hash view (safe because immutable); `artifacts:` is a new
   independent list. A **brainstorm follow-up task** will be created (during
   implementation, none exists yet — verified by grep) to evaluate pros/cons of
   eventual unification. The design doc §4 "Open reconciliation" paragraph is
   updated to record this as settled.
2. **Lifecycle scope: core ops + `rm` + fold re-bind.**
   - `ait artifact rm` removes the frontmatter entry and, when no other task
     references the handle, deletes the manifest and sweeps now-unreferenced
     artifact-only blobs (guards below).
   - Fold transfers `artifacts:` entries to the primary task (frontmatter-only;
     the manifest is handle-keyed and has no ownership field — nothing to
     rebind there).
   - **Board hard-delete: fail-closed guard NOW, full handling as follow-up**
     (review round 1). The board's hard-delete already invokes
     `ait attach decref-deleted` unconditionally for every doomed task id and
     aborts the delete on non-zero exit BEFORE any mutation
     (`aitask_board.py:6821-6834`, `_decref_doomed_attachments` at 6751 —
     called for all doomed ids, not just attachment-bearing ones). This task
     adds an artifact guard inside `cmd_decref_deleted`: die if a doomed task
     still carries `artifacts:` entries (unless every such handle is also
     listed by a `--protect-task` revived file — the fold-revive case). Full
     manifest cleanup / orphaned-manifest reaping stays a follow-up task.
3. **`move` verb is a stub in this task** (review round 1 — supersedes the
   earlier "manifest-only set-backend" idea, which could commit an
   unresolvable backend pointer on a typo). A user-facing safe move must copy
   every version blob to a *registered* target backend before repointing the
   manifest; with only `local` registered, the verb has no valid target. So
   `ait artifact move` dies with a clear message (exact `cmd_stub` pattern of
   `ait attach move`, aitask_attach.sh:50,592,602): "backend move arrives with
   remote-backend support (t1076_3/t1089/t1090)". The *model-level* backend-
   move operation exists and is tested at the substrate (`artifact_manifest
   set-backend`, t1076_1). **Explicit AC deviation:** the task file's
   "backend-move — manifest only" Key-work line is updated (via `./ait git`)
   to record this scope decision — no silent deviation.

## Blast radius (verified by exploration + review round 1)

- New: `.aitask-scripts/aitask_artifact.sh`, `tests/test_artifact_cli.sh`,
  `tests/test_artifact_fold_transfer.sh`.
- Edited: `lib/yaml_utils.sh` (mapping reader learns handle/kind — **the
  load-bearing fix**: the reader currently whitelists the 7 attachment keys at
  lines 187-196 and emits only those at 211-217; without this every artifact
  read path silently fails), `ait` (dispatcher + help),
  `lib/frontmatter_patch.py` (FIELD_ORDER), `aitask_update.sh` (preserve
  `artifacts:` block), `aitask_fold_mark.sh` (Step 5b transfer),
  `aitask_attach.sh` (decref-deleted artifact guard),
  `board/aitask_merge.py` (comment only), `tests/test_yaml_utils.sh`,
  `aidocs/unified_artifact_design.md`, `aidocs/task_attachments_design.md`,
  `aitasks/t1076/t1076_2_...md` (AC wording for move — via `./ait git`).
- NOT touched: board Python (`_decref_doomed_attachments` already fail-closed;
  block-fields flow through `task_yaml.py serialize_frontmatter` generically —
  attachments precedent), `aitask_create.sh` (entries only added
  post-creation via the CLI — attach precedent, explicit decision), gc
  (`_attach_gc_blocking_hashes` already unions manifest references, t1076_1),
  whitelists (`aitask_artifact.sh` is CLI-invoked only, not skill-invoked —
  per `aidocs/framework/aitasks_extension_points.md` caveat; same as
  `aitask_attach.sh` which has zero whitelist entries).

## Frontmatter schema (design §4 — normative)

```yaml
artifacts:
  - handle: art:t774-htmlplan   # stable logical handle, set once, never rewritten
    kind: html_plan             # html_plan | mockup | report | attachment | ... (open set)
    name: "Login flow mockups"  # optional human label
```

- `handle` required, matches `^art:[a-z0-9][a-z0-9._-]{0,127}$` (pinned by
  t1076_1 in both `artifact_manifest.py` HANDLE_RE and
  `artifact_manifest.sh::artifact_manifest_relpath`).
- `kind` required, shape-validated `^[a-z][a-z0-9_]{0,31}$` (open set — no
  membership enum; consumers branch on it later).
- `name` optional, advisory. **Not unique, not an identifier** — destructive
  ops resolve names but die on ambiguity (Step 4 rm).
- **No `current` / `versions` / `backend` here** — manifest-owned. The entry is
  immutable for the artifact's life; updates touch only the manifest.

## Implementation steps

### Step 1 — `lib/yaml_utils.sh`: teach the mapping reader handle/kind (FIRST — everything reads through it)

`read_yaml_mappings` is the single frontmatter-mapping read seam and currently
knows only the attachment schema:

- `_read_yaml_mappings_set` (lines 182-198): add two cases before `hash`:
  `handle) f_handle="$val"; p_handle=1 ;;` and `kind) f_kind="$val"; p_kind=1 ;;`.
- `_read_yaml_mappings_flush` (lines 204-220): emit `handle` then `kind`
  BEFORE the seven attachment keys (matches FIELD_ORDER; attachment records
  never carry them → their output is byte-identical, proven by the attach
  suite in 9c).
- `read_yaml_mappings` locals (lines 256-257): add `f_handle="" f_kind=""` /
  `p_handle=0 p_kind=0`, and reset them wherever the seven are reset (item
  flush/reset sites).
- Update the OUTPUT CONTRACT comment (lines 228-239): schema order becomes
  `handle, kind, hash, name, mime, size, added_at, backend, url`; note the
  reader serves both `attachments:` (t1030 §3) and `artifacts:` (t1076_2,
  unified design §4). Update `_read_yaml_mappings_set`'s "design §3 schema"
  comment (line 181/195) likewise.
- `tests/test_yaml_utils.sh`: add an `artifacts:`-block fixture — assert
  `read_yaml_mappings <file> artifacts` emits `handle=`/`kind=`/`name=` in
  that order, blank-line-separated records, quoted-name round-trip; and a
  mixed-file assert that reading `attachments` from a task that ALSO has
  `artifacts:` yields only the attachment records (field-scoping regression).

### Step 2 — `frontmatter_patch.py`: extend FIELD_ORDER

Line 28: `FIELD_ORDER = ["hash", "name", ...]` → prepend the artifact keys:

```python
# Emission order for attachment (t1030 §3) and artifact (t1076_2 §4) mapping
# fields. The two entry shapes never mix keys, so one ordered list serves both.
FIELD_ORDER = ["handle", "kind", "hash", "name", "mime", "size", "added_at", "backend", "url"]
```

Attachment entries carry no `handle`/`kind` → their rendering is unchanged
(existing attach tests prove it). Artifact entries render handle → kind → name.
Update the module docstring (line 3) to name both fields.

### Step 3 — `aitask_update.sh`: preserve the `artifacts:` block

Mirror the attachments preservation exactly:
- After line 579 (`preserved_attachments=...`): add
  `local preserved_artifacts` +
  `preserved_artifacts="$(extract_frontmatter_block "$file_path" artifacts)"`.
- After the re-emission at lines 691-694: add the same 3-line
  `if [[ -n "$preserved_artifacts" ]]` block with a `(t1076_2)` comment.
- Update the `extract_frontmatter_block` header comment (line 525, "notably
  `attachments:`") to name both fields.

Without this, any `aitask_update.sh` rewrite would silently drop `artifacts:` —
the highest-blast-radius integration point.

### Step 4 — New CLI `.aitask-scripts/aitask_artifact.sh` (~420 lines)

Modeled on `aitask_attach.sh` (same source block: terminal_compat, yaml_utils,
task_utils, python_resolve, artifact_utils, artifact_backend, artifact_cache,
attachment_lock, attachment_meta, artifact_manifest). `#!/usr/bin/env bash`,
`set -euo pipefail`. Header documents the stable-handle/mutable-manifest split
and the shared attach lock.

**Verbs** (dispatch in `main()` like aitask_attach.sh:594-609):

```
ait artifact create <task> <file> --kind <kind> [--name <label>] [--handle art:<id>] [--backend <n>]
ait artifact update <handle> <file>
ait artifact move   ...                          # stub — dies (settled decision 3)
ait artifact rm <task> <handle-or-name>
ait artifact ls [<task>]
ait artifact get <handle> [--out <path>] [--version <sha256:hash>]
ait artifact versions <handle>
ait artifact help
```

**Shared private helpers:**
- `_artifact_records <task_file>` — print `handle\tkind\tname` per `artifacts:`
  entry (via `read_yaml_mappings <file> artifacts`; same parse-loop shape as
  `_attach_records`, aitask_attach.sh:137-153).
- `_artifact_resolve_ref <task_file> <ref>` — exact handle match wins; else
  name match, **dying on ≥2 name matches** ("ambiguous name '<ref>' — use the
  handle"; review round 1: names are advisory and non-unique; a destructive op
  must never pick "first parsed wins"). Handle is always unambiguous (create's
  dup guard + fold's dedupe-by-handle keep one entry per handle per task).
- `_artifact_size_cap_bytes` — reads `artifact_max_size_mb` from
  `aitasks/metadata/project_config.yaml`, default 25 (own knob, NOT
  `attachment_max_size_mb` — scope-honest; HTML plans may warrant a different
  cap later).
- `_artifact_commit <msg> <relpath>...` — identical partial-commit helper as
  `_attach_commit` (aitask_attach.sh:199-203; the trailing `-- "$@"` is
  load-bearing against concurrent staged files).
- `_artifact_handle_referenced_elsewhere <handle> <excluded_task_file>` — scan
  `$TASK_DIR`/`$ARCHIVED_DIR` globs (same glob set as
  `_attach_gc_blocking_hashes`, aitask_attach.sh:514-527) for any OTHER task
  whose `artifacts:` lists `<handle>`; prints the first referencing file.
  **Folded tasks are NOT skipped** (review round 1 interaction): a Folded task
  can be revived by board delete (`_unfold_deleted_primary_children`), so its
  handle reference must keep the manifest alive. Consequence: a fold-then-
  archive sequence can leave an unreferenced manifest behind — same
  conservative orphaned-manifest state as hard-delete; reaped by the follow-up
  task (Step 8 #2). Never loses data.

**`cmd_create`** — arg parse mirrors `cmd_add` (aitask_attach.sh:207-227).
`--kind` required; validate `^[a-z][a-z0-9_]{0,31}$`. Default handle:
`art:t<tid>-<kindslug>` with `kindslug="${kind//_/}"` and `tid="${task_id//_/.}"`
(design example: kind `html_plan` on t774 → `art:t774-htmlplan`; child `16_2`
→ `art:t16.2-htmlplan` — `.` is in the handle charset, keeps parent/child
readable). `--handle` overrides (validated against the handle regex). Backend
default `local`; die on non-local (same guard shape as attach add line 223 —
remote backends arrive with t1076_3/t1089/t1090). Then
`with_attach_lock _artifact_create_txn`:

1. Size cap (like `_attach_add_txn` lines 234-240, artifact knob).
2. `hash="$(artifact_sha256 "$file")"`.
3. Frontmatter dup guard: die if the task already lists `<handle>`.
4. Manifest collision guard: `artifact_manifest get <handle>` non-empty → die
   "handle already exists — pass --handle to choose another".
5. Record blob pre-existence (`artifact_backend_head`) for rollback.
6. `artifact_backend_put "$hash" "$file"`; `artifact_resolve "$hash" >/dev/null`
   (warm + verify; resolver self-verifies — t1076_1).
7. `artifact_manifest create "$handle" "$hash" "backend=$backend"`.
8. `frontmatter_patch.py append "$task_file" artifacts "handle=$handle"
   "kind=$kind"` + `name=` iff provided.
9. Commit trio: `$(artifact_local_blob_relpath "$hash")`,
   `$(artifact_manifest_relpath "$handle")`, `$task_file` — message
   `ait: Create artifact <handle> on t<task_id>`.
10. Rollback on commit failure (mirror `_attach_rollback_add`,
    aitask_attach.sh:284-302): restore task file from HEAD; unstage+delete the
    manifest (create dies on pre-existing → always newly created here);
    unstage+delete blob iff not pre-existing. Then die.
11. `success ...` and print `HANDLE:<handle>` (machine-parseable — t1076_4's
    gate will consume it).

**`cmd_update`** — `update <handle> <file>`. Reads manifest (`get`); die if
missing. `with_attach_lock _artifact_update_txn`:
1. `hash="$(artifact_sha256 "$file")"`; if equal to
   `artifact_manifest current <handle>` → `success "already current"` no-op
   (idempotent — feeds t1076_4's re-run AC).
2. Backend from the manifest JSON
   (`artifact_manifest get <handle> | "$(require_python)" -c 'import json,sys;
   print(json.load(sys.stdin)["backend"])'`). Export `ARTIFACT_BACKEND`.
   Size cap. Record blob pre-existence.
3. `artifact_backend_put` + `artifact_resolve >/dev/null`.
4. `artifact_manifest set-current "$handle" "$hash"`.
5. Commit: blob relpath (local backend) + manifest relpath — message
   `ait: Update artifact <handle>`. **No task-file path anywhere in this txn**
   (the core AC). Rollback: restore manifest from HEAD (pre-exists), delete
   blob iff new.

**`cmd_move`** — stub: `die "ait artifact move: not yet available — a safe
backend move (copy all version blobs, then repoint) arrives with remote-backend
support (t1076_3/t1089/t1090)"`. See settled decision 3.

**`cmd_remove`** — `rm <task> <handle-or-name>` (mirror `cmd_remove`/
`_attach_rm_txn`, aitask_attach.sh:339-363). Under lock:
1. `_artifact_resolve_ref` → handle (dies on ambiguous name); capture the
   manifest JSON (versions + backend) BEFORE mutation. `artifact_manifest get`
   prints empty + exit 0 for a missing handle (t1076_1 contract) — branch on
   that: **stale-entry cleanup path** (review round 2): when the manifest is
   already missing (failed/manual cleanup, data-branch inconsistency), do NOT
   die — remove the frontmatter entry (step 2), skip steps 3-5 (no manifest to
   keep/delete, no blob sweep) with
   `warn "manifest for <handle> is missing — removing the stale frontmatter
   reference only"`, commit just the task file (message
   `ait: Remove stale artifact reference <handle> from t<task_id>`), and exit
   success. The task stays repairable through the same verb.
2. `frontmatter_patch.py remove "$task_file" artifacts --match-key handle
   --match-val "$handle"`.
3. `other="$(_artifact_handle_referenced_elsewhere "$handle" "$task_file")"`;
   if non-empty → commit just the task file; success "entry removed; manifest
   kept (still referenced by <other>)". Done.
4. Else delete the manifest file (`rm -f "$(artifact_manifest_dir)/<id>.json"`).
5. Blob sweep (local backend only; non-local: skip with a note): for each
   version hash from the captured manifest — keep if a per-blob meta file
   exists (`[[ -f "$(attach_meta_dir)/$(artifact_shard_path "$h").json" ]]` —
   the attachment ledger owns it) OR the hash appears in the remaining
   `artifact_manifest referenced-hashes`; else `artifact_backend_delete` and
   collect its relpath.
6. Commit: task file + manifest relpath + deleted blob relpaths — message
   `ait: Remove artifact <handle> from t<task_id>`. Rollback via
   `task_git reset`/`checkout` of all paths.
7. Success note mentions recovery: all deletions are ordinary data-branch
   commits — recoverable from git history.

**`cmd_list`** — `ls <task>`: table `HANDLE  KIND  CURRENT(12hex)  VERS
BACKEND  NAME` joining each frontmatter entry with `artifact_manifest
current/versions/get`; a handle with no manifest renders `?` columns plus a
`warn` (surface breakage, don't hide the row). Bare `ls`:
`artifact_manifest list` + per-handle current/backend (global view).

**`cmd_get`** — `get <handle> [--out <path>] [--version <hash>]`: manifest
lookup (die if missing); hash = `--version` (validated ∈ `versions` output)
else `current`; export `ARTIFACT_BACKEND` from manifest;
`artifact_resolve "$hash"` (self-verifying); `cat` or `cp` + success. This is
the "handle resolves to current version via manifest" AC path.

**`cmd_versions`** — print versions oldest→newest, `*` marking current.

### Step 5 — `ait` dispatcher + help + task AC wording

- `ait` line 197 area: add
  `artifact) shift; exec "$SCRIPTS_DIR/aitask_artifact.sh" "$@" ;;`
  (alphabetically next to `attach`).
- `show_usage()` heredoc: one line under the attach line (line 48):
  `artifact       Manage versioned artifacts (create/update/rm/ls/get/versions; move pending)`.
- Task file `aitasks/t1076/t1076_2_artifact_pointer_version_model.md`: update
  the "backend-move (manifest only)" Key-work line to record the settled
  scope ("substrate `set-backend` (t1076_1); user-facing `move` stub until a
  remote backend exists"). Commit via `./ait git` (`ait:` prefix).

### Step 6 — Fold transfer (`aitask_fold_mark.sh` Step 5b)

- Detection loop (lines 459-465): extend to also set the flag when
  `read_yaml_mappings "$_ff" artifacts 2>/dev/null | grep -q '^handle='`
  (works after Step 1's reader extension). Rename `_fold_any_attachments` →
  `_fold_any_attach_or_artifacts` (comment: artifacts need no ledger rebind —
  manifests are handle-keyed — only the frontmatter merge).
- `_fold_attach_txn` (447-453): append a call to new
  `_fold_transfer_artifacts "$primary_file" <folded+transitive files>`.
- New `_fold_transfer_artifacts` — simplified mirror of
  `_fold_transfer_attachments` (377-414): seed `seen_handles` from the
  primary's `artifacts:`; for each folded/transitive file's entries, skip if
  handle already present, else `frontmatter_patch.py append "$primary_file"
  artifacts handle=… kind=… [name=…]`. Dedupe by handle only (no name
  uniquing — `get` is handle-addressed; names are advisory).
- `_fold_rebind_refs` needs no change (attachment-meta rebind on an
  artifacts-only fold is a harmless no-op — the meta tree scan finds nothing).
- Folded files keep their entries (same as attachments; they feed the
  revive-on-delete case and rm's conservative referenced-elsewhere scan).

### Step 7 — Hard-delete fail-closed guard (`aitask_attach.sh` decref-deleted)

Review round 1. The board hard-delete already fail-closes on
`ait attach decref-deleted` (invoked for ALL doomed ids before any mutation —
`aitask_board.py:6763-6776, 6821-6834`). Add the artifact guard at that choke
point, inside `_attach_decref_deleted_txn` (aitask_attach.sh:399-483), right
after each doomed `task_file` is resolved (~line 433):

- Read the doomed task's `artifacts:` handles. For each, allow only if some
  `--protect-task` (revived folded survivor) file also lists the handle —
  ownership survives the revive. Otherwise
  `die "ait attach decref-deleted: t<id> still has artifact <handle> — remove
  it first (ait artifact rm <id> <handle>); manifest cleanup on hard-delete
  lands with a follow-up task"`.
- Protected-task files were already resolved fail-closed at lines 410-422 —
  collect their handle sets in the same loop that builds
  `protect_ids_for_hash`.
- Zero board-python changes: the board surfaces the die message verbatim and
  aborts the delete ("task NOT deleted"), exactly as for attachment failures.
- Update the `cmd_decref_deleted` header comment + `show_help` internal line.

### Step 8 — Merge-rule decision comment (`board/aitask_merge.py`)

No merge branch (deliberate): like `attachments`, a concurrent edit of
`artifacts:` falls to the unresolved/PARTIAL manual-conflict path — for
list-of-mappings fields, degrading to manual conflict beats a silent union
guess. Add a short comment next to `_LIST_UNION_FIELDS` (line 125) recording
that `attachments`/`artifacts` intentionally take the conflict path.

### Step 9 — Follow-up task creation (post-approval, during implementation)

Via the Batch Task Creation Procedure command shape
(`aitask_create.sh --batch`):
1. **Brainstorm: attachments↔artifacts unification** — evaluate recasting
   attachments as single-version artifacts under one `artifacts:` schema
   (design §4/§10); pros/cons + migration plan if adopted. Labels
   `task_attachments,html_plans`; anchor 1065; priority low.
2. **Artifact manifest lifecycle on hard-delete + orphan reaping** — replace
   the Step-7 fail-closed guard with real handling: manifest cleanup /
   handle re-bind on board hard-delete (decref-deleted analog), plus an
   orphaned-manifest reaper (manifests no task file references — reachable via
   fold-then-archive, see Step 4 `_artifact_handle_referenced_elsewhere`
   note). Depends: [1076_2]; labels `task_attachments`; priority low.

### Step 10 — Docs

- `aidocs/unified_artifact_design.md`:
  - §4: replace the "Open reconciliation" paragraph (lines 133-137) with the
    settled decision (keep `attachments:` separate; unification tracked by the
    brainstorm follow-up, reference its task id).
  - §3 operations table + §4 schema: mark implemented (t1076_2) and name
    `ait artifact` as the operations surface; note the user-facing `move` verb
    is deferred to remote-backend work (substrate `set-backend` exists).
  - §11 coverage table row 2 → **Done (t1076_2)**.
- `aidocs/task_attachments_design.md` §3: one-line pointer that mutable,
  versioned references use the sibling `artifacts:` field (t1076_2, unified
  design §4).
- No website/seed/skill changes (attach precedent: `ait attach` has no website
  page; `artifacts:` follows `attachments:` in being CLI-managed, not part of
  the documented create/update flag surface).

### Step 11 — Tests

**11a. `tests/test_yaml_utils.sh` additions** (Step 1): artifacts-block
emission (handle/kind/name, order, quoting, multi-record separation); mixed
attachments+artifacts field-scoping regression.

**11b. `tests/test_artifact_cli.sh`** (new; fixture modeled on
`test_artifact_manifest_lib.sh` — legacy-mode git repo, `aitasks/t5_demo.md` +
a child `aitasks/t16/t16_2_child.md`, `XDG_CACHE_HOME` sandbox, asserts via
`tests/lib/asserts.sh`):
- **create**: derived handle (`art:t5-htmlplan` from kind `html_plan`; child
  `16_2` → `art:t16.2-htmlplan`), manifest content (current=versions=[hash],
  backend=local), frontmatter entry present with key order handle→kind→name
  AND `read_yaml_mappings … artifacts` round-trips it (proves Step 1 + Step 2
  agree), blob stored + cache warmed, one commit landed, `HANDLE:` line
  printed.
- **create validation** (each dies): missing `--kind`; bad kind shape
  (`Upper`, `1x`, spaces); duplicate handle (second create; message mentions
  `--handle`); duplicate entry on same task; non-local `--backend`; over-cap
  file (fixture `artifact_max_size_mb: 1`, 2MB file); bad explicit `--handle`
  (`art:../x`, uppercase).
- **update (core ACs)**: byte-capture the task file before → update with new
  content → manifest `current` moved + `versions` grew; **task file
  byte-identical** and `git status --porcelain -- aitasks/` empty; second
  update with same bytes → idempotent no-op (no new commit); update on missing
  handle dies.
- **move**: dies with the stub message; manifest unchanged afterwards
  (construction-spy: byte-compare the manifest file).
- **rm**: entry removed + manifest deleted + artifact-only blob swept;
  **negative control — blob shared with an attachment survives** (attach the
  same bytes to another task first; meta file exists → kept);
  **negative control — hash shared by another manifest survives**; manifest
  KEPT when a second task's `artifacts:` lists the handle (seeded via a direct
  `frontmatter_patch.py append`); manifest KEPT when a **Folded** task lists
  the handle (revive-safety — review round 1); **ambiguous name dies** (two
  artifacts, explicit handles, same `--name`; assert error says "use the
  handle" and NOTHING was removed); rm by unambiguous name works; rm of
  unknown ref dies; **stale-entry cleanup** (review round 2): delete the
  manifest file out-of-band, then `rm` → warns, removes the frontmatter entry,
  commits the task file, exits 0, and no blob is touched (byte-check one
  surviving blob).
- **get/versions/ls**: get returns current bytes; `--version` of an old hash
  returns old bytes; `--version` with hash ∉ versions dies; versions marks
  current; `ls <task>` row joins manifest fields; `ls` global lists handles;
  `ls <task>` with a missing manifest warns but exits 0.
- **decref-deleted guard** (Step 7): doomed task with an artifact → helper
  dies naming task + handle, exit non-zero, no meta/ledger mutation committed;
  doomed task whose every handle is also on a `--protect-task` file →
  proceeds; attachment-only doomed task → unchanged behavior (regression).
- **update.sh preservation**: `aitask_update.sh --batch 5 --priority high` on
  the artifact-bearing task → `artifacts:` block byte-identical afterwards.
- **gc interplay**: blob attached-then-rm'd (orphaned, grace 0) but referenced
  by a manifest survives `ait attach gc` (t1076_1 guard recheck); after
  `ait artifact rm` deletes that manifest, the same gc sweeps it — proves
  "the block lifts when pruning removes the reference".

**11c. `tests/test_artifact_fold_transfer.sh`** (new; fixture modeled on
`test_attach_fold_rebind.sh`):
- Fold a task carrying `artifacts:` into a primary → entry appended (handle/
  kind/name preserved), `updated_at` bumped.
- Dedupe: primary already lists the handle → no duplicate entry.
- Mixed fold (attachments + artifacts on the folded task) → both transferred,
  attachment rebind still works (regression).
- Artifacts-only fold triggers the transfer (detection extension is
  load-bearing); fold with neither → Step 5b body skipped (negative control,
  as today).

**11d. Regression + lint**: run the existing attach suite
(`test_attach_scaffold.sh`, `test_attach_local_backend.sh`,
`test_attach_meta.sh`, `test_attachment_meta_lib.sh`,
`test_attach_archive_gc.sh`, `test_attach_fold_rebind.sh`,
`test_attach_task_delete_decref.sh`, `test_attach_gc_manifest_blocking.sh`,
`test_artifact_manifest_lib.sh`) + `test_yaml_utils.sh`, `test_fold_mark.sh`,
`test_update_multiline_yaml.sh`, `test_board_decref_doomed_attachments.py`;
`shellcheck` on new/edited `aitask_*.sh`; `bash -n` every touched script.

## Conventions

- `#!/usr/bin/env bash`, `set -euo pipefail`, `die`/`warn`/`success` from
  `terminal_compat.sh`; no lib added to `./ait`'s source-on-startup chain → no
  `test_scaffold.sh` registration; no whitelist entries (not skill-invoked).
- All data-branch commits are partial (`-- "$@"`), all mutations under
  `with_attach_lock`, rollbacks restore HEAD state (attach patterns).
- Commit format: `feature: <description> (t1076_2)` for code; `ait:` for
  task/plan file commits via `./ait git`.

## Verification (maps to the task's ACs)

1. **Update-in-place repoints the manifest and leaves the referencing task
   file byte-identical (no frontmatter rewrite on edit)** — 11b update
   byte-capture assertions (move verb deferred; substrate `set-backend`
   already test-pinned in t1076_1 — recorded as an explicit AC scope update,
   Step 5).
2. **`artifacts:` frontmatter parses; handle resolves to current version via
   manifest** — 11a reader emission + 11b create round-trip + get.
3. Lifecycle extensions (rm guards incl. ambiguity + Folded revive-safety,
   fold transfer, hard-delete guard) — 11b/11c, each with negative controls.
4. No regression — 11d suite.

## Final Implementation Notes

- **Actual work done:** Everything in the plan landed as designed. New
  `ait artifact` CLI (`.aitask-scripts/aitask_artifact.sh`, ~590 lines):
  `create` (derived `art:t<id>-<kindslug>` handle with `_`→`.` child ids,
  `--handle`/`--name`/`--backend` overrides, size cap via own
  `artifact_max_size_mb` knob, dup + collision guards, blob+manifest+task
  commit trio with full rollback, machine-parseable `HANDLE:` output),
  `update` (manifest-only repoint — the core stable-handle/mutable-manifest
  AC; idempotent no-op on same bytes), `move` stub (settled decision 3),
  `rm` (name-ambiguity die, referenced-elsewhere manifest keep incl. Folded
  revive-safety, meta-file + remaining-manifest blob-sweep guards,
  stale-entry repair path), `ls`/`get`/`versions`. Reader/writer extensions
  (`yaml_utils.sh` handle/kind first, `frontmatter_patch.py` FIELD_ORDER),
  `aitask_update.sh` artifacts-block preservation, fold Step 5b transfer
  (dedupe by handle), fail-closed decref-deleted artifact guard,
  merge-rule decision comment, design-doc updates (§4 reconciliation
  settled → t1134; §11 row 2 Done), follow-up tasks t1134 + t1135 created.
- **Deviations from plan:** None of substance. The `--handle` suggestion in
  the duplicate-collision error and the `ls` stale-row repair hint are small
  usability additions beyond the plan text.
- **Issues encountered:** The implementing session crashed mid-task
  (RECLAIM_CRASH); work was recovered intact from the working tree, verified
  against the plan step-by-step, and completed in a follow-up session. A
  review round after recovery found the rm scan-failure hazard (see
  Post-Review Changes — Change Request 1): destructive uncommitted mutations
  could be left behind when `referenced-hashes` fail-closed on an unrelated
  malformed manifest; fixed with an in-txn rollback + test F10.
- **Key decisions:** (1) Rollback-on-scan-failure over pre-mutation scanning —
  the union output of `referenced-hashes` loses multiplicity, so a
  pre-mutation scan would include the doomed manifest's own hashes and block
  the entire blob sweep. (2) `attachments:`/`artifacts:` stay separate
  schemas sharing one reader/writer (settled §10 decision; unification
  evaluation → t1134). (3) Folded tasks deliberately count as manifest
  references in `rm` (revive-on-delete safety); the resulting
  fold-then-archive orphan-manifest state is t1135's reaper concern.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1076_3 (share-handle resolution) gets the
  manifest `backend` field already flowing through every CLI path (exported
  as `ARTIFACT_BACKEND` before resolve/put) — registering a remote backend
  should light up `get`/`update` without CLI surgery; the `move` verb stub
  (`cmd_stub`) is the place to implement the copy-then-repoint safe move.
  t1076_4 (gate archetype) should consume `create`'s `HANDLE:<handle>` line
  and can rely on `update`'s same-bytes idempotency for its re-run AC. The
  `_artifact_records`/`_artifact_resolve_ref` helpers are the reference
  pattern for reading `artifacts:` frontmatter from bash.

## Step 9 reference (post-implementation)

Current-branch profile — no worktree/merge. Archive via
`./.aitask-scripts/aitask_archive.sh 1076_2`, push via `./ait git push`.
t1076_3 and t1076_4 remain; parent archival waits for them.

## Post-Review Changes

### Change Request 1 (2026-07-06 20:30)
- **Requested by user:** `ait artifact rm` mutated the task frontmatter and
  deleted the manifest BEFORE running `artifact_manifest referenced-hashes`;
  since that scan fail-closes on any malformed manifest in the tree, the error
  path left uncommitted destructive working-tree changes while claiming
  "nothing committed / re-run to retry" — and the retry could not work (the
  frontmatter entry was already gone, so `_artifact_resolve_ref` fails).
- **Verification:** confirmed against `artifact_manifest.py`'s named
  MALFORMED-MANIFEST POLICY (dies on any invalid manifest during
  `referenced-hashes`) and the `_artifact_rm_txn` mutation order.
- **Changes made:** rollback on scan failure (restore task file + manifest
  from HEAD via `task_git reset`/`checkout`, matching the txn's other rollback
  paths), with an honest die message ("rolled back; repair that manifest and
  re-run"). Computing the scan pre-mutation was rejected: the union output
  would include the doomed manifest's own hashes and block the entire blob
  sweep (multiplicity is lost, so it cannot be subtracted). New test F10:
  malformed sibling manifest → rm dies, frontmatter entry + manifest restored,
  no uncommitted `aitasks/` changes; after repairing the malformed file the
  SAME rm succeeds (negative control).
- **Files affected:** `.aitask-scripts/aitask_artifact.sh`,
  `tests/test_artifact_cli.sh` (82/82 pass).

## Risk

### Code-health risk: medium
- The `read_yaml_mappings` extension touches the shared reader every
  attachment consumer uses (attach ls/records, fold, meta hashes) · severity:
  medium · → mitigation: in-plan (additive keys only, attachment emission
  order untouched; field-scoping regression test 11a; full attach suite 11d)
- A missed `aitask_update.sh` preservation edit would silently drop the
  `artifacts:` block on any task update · severity: medium · → mitigation:
  in-plan (Step 3 mirrors the attachments mechanism; dedicated preservation
  test in 11b)
- `rm`'s blob sweep could delete a blob shared with an attachment or another
  artifact · severity: medium · → mitigation: in-plan (meta-file guard +
  remaining-manifests guard, each with a negative-control test; deletions are
  committed and git-recoverable)
- The decref-deleted guard could regress attachment-only hard-deletes ·
  severity: low · → mitigation: in-plan (guard fires only on `artifacts:`
  entries; attachment-only regression case in 11b +
  `test_attach_task_delete_decref.sh` / board test in 11d)
- Fold Step 5b extension could regress the attachment rebind path · severity:
  low · → mitigation: in-plan (mixed-fold regression test in 11c)

### Goal-achievement risk: low
- Handle-derivation convention (`art:t<id>-<kindslug>`, `_`→`.` in child ids)
  might not match what t1076_4's gate wants to derive · severity: low ·
  → mitigation: in-plan (`--handle` override exists; derivation is a single
  helper, trivially adjustable; `HANDLE:` output gives the gate the
  authoritative value)
- Deferring the `move` verb leaves no user-facing backend-move until t1076_3 ·
  severity: low · → mitigation: in-plan (explicit AC scope update on the task
  file; substrate op exists and is test-pinned; only one backend exists today,
  so the verb has no valid target anyway)

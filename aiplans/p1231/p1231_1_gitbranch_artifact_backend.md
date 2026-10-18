---
Task: t1231_1_gitbranch_artifact_backend.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_2_artifacts_settings_tab.md, aitasks/t1231/t1231_3_artifact_documentation.md, aitasks/t1231/t1231_4_manual_verification_configurable_git_branch_artifact_backend.md
Archived Sibling Plans: (none — first child)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-18 18:40
---

# t1231_1 — `gitbranch` artifact backend (verified 2026-10-18)

## Context

`ait artifact`'s zero-config `local` backend commits blobs onto the
**aitask-data branch** next to every task and plan file (`unified_artifact_design.md`
§7: it "bloats that branch for large HTML"). `dir` needs an out-of-band mount
that every teammate has to replicate. `gitbranch` keeps blobs **in git** but on a
**dedicated orphan branch** (default `aitask-artifacts`), written with
**plumbing only, no worktree**. First and riskiest of t1231's children; no TUI
(t1231_2), no website docs (t1231_3).

`.aitask-data` is a *linked worktree of the same repo*
(`.aitask-data/.git` → `.git/worktrees/-aitask-data`), so refs and objects are
shared. Plain `git` from the repo root is the right handle in branch mode and
in legacy mode alike.

### What changed since the plan was written (verify findings)

The July plan's design holds. These premises are stale and are corrected below:

1. **The backend contract gained a sixth op, `init`** (`artifact_backend.sh:21`,
   `ait artifact init-store <backend>`, `cmd_init_store`). `dir` now requires a
   marker, `.ait-artifact-store`, written by `init-store` (t1283). The `gitbranch`
   module must define `artifact_gitbranch_init`. It becomes the **optional eager**
   init. Lazy init on first write is still the default (parent decision #3).
2. **`delete` must RETURN non-zero, never die** (`dir.sh:229-237`). Delete is
   called from the rollback hooks inside the chained EXIT trap. An exit there
   skips the rollback report and leaks the global attach lock.
3. **`head` must die rather than answer "absent" when the store is unusable**
   (`dir.sh:149-152`). `blob_pre=false` makes the rollback delete the blob.
4. **`rm` no longer touches non-local stores.** Its sweep activates `local`
   explicitly (t1286), and for any other backend it only warns
   (`cmd`: `_artifact_rm_txn`). **`ls` activates no backend at all.** "Guard
   immediately after `artifact_registry_activate` in rm and list" therefore has
   no anchor. See the guard redesign below.
5. **Errexit is OFF inside every `with_attach_lock` callback** (t1675 contract,
   `attachment_lock.sh` header). Every returning call needs an explicit
   `|| die`, and `tests/test_attach_lock_callback_contract.sh` checks callbacks
   statically. A new callback's **first statement must be `txn_begin`**.
6. All of the plan's line numbers in `aitask_artifact.sh` and `artifact_cache.sh`
   are stale (the file is now 916 lines). Steps below cite **functions**.
7. Remote probing: `git ls-remote --heads origin X | grep X` tail-matches refs.
   Use `--exit-code origin refs/heads/<b>`, which returns 0 / 2 / other
   (`aitask_lock.sh:75-82`, lesson recorded at `aitask_setup.sh:1668`). A bare
   `git fetch origin <b>` does not update `refs/remotes/origin/<b>` under a
   single-branch refspec, so always fetch with the explicit
   `+refs/heads/<b>:refs/remotes/origin/<b>`.
8. **Read-path regression in the July guard.** Trails read artifacts through one
   `ait artifact get` subprocess per artifact (`trail_discovery.py`,
   `aitask_trail_gather.sh`). Guarding `get` with a network probe would add a
   fetch to every trail read and **fail offline even on a cache hit**. The guard
   is therefore split (R4 below). The local checks need no network; the
   store-identity checks happen inside the adapter at the moment it actually
   touches the store.

## Config contract (PINNED, unchanged)

```yaml
artifacts:
  default_backend: gitbranch
  backends:
    gitbranch:
      branch: aitask-artifacts
```

Remote is hard-coded `origin`. Branch layout: `blobs/<2hex>/<62hex>` + a
root `.ait-artifact-store` marker:

```
store_id: <32 lowercase hex>
branch: <branch name at init>
created_at: <YYYY-MM-DD HH:MM>
```

A marker is **valid** iff it is a blob at `<tip>:.ait-artifact-store` with a line
`store_id: [0-9a-f]{32}`. Anything else (missing, no id, a tree) is invalid.

## Correctness model (R1–R4, as implemented)

**R1 — remote is the store of record; publish is push-gated.**
- With a remote, the authority is `origin`. Refresh = `ls-remote --exit-code`
  (absence vs error) followed by the explicit-refspec fetch.
- **The read memo is read-only.** `_ARTIFACT_GITBRANCH_FRESH_FOR=<branch>`
  gates *only* whether head/get/list re-fetch. The tip is always re-read from the
  ref, never cached. **Every CAS iteration refreshes unconditionally.** A lease
  rejection means the observed tip was stale by definition, and a memoized
  retry livelocks.
- Publish order: build the commit → `git push --force-with-lease=refs/heads/B:<expected> origin <c>:refs/heads/B`
  (`<expected>` empty = must not exist) → on success, `git update-ref refs/remotes/origin/B <c>`
  (so the same process's post-put `head` sees it without fetching) → mirror
  `refs/heads/B` best-effort, *only* when the local ref is absent or equals the
  observed tip (a diverged local branch is never overwritten). A mirror failure
  never fails the op.
- **Failed push classifier (no stderr parsing).** Re-run `ls-remote`:
  - error → hard failure → die;
  - remote tip ≠ expected → lease lost → retry;
  - remote tip == expected → the push was refused for another reason (hook,
    permissions) → die.
  The budget is 5 attempts with jitter, matching `lock_task`; when it is
  exhausted, die. **Never warn-and-continue.** A locally-only blob would publish
  a manifest that other clones can resolve but cannot `get`.
- No remote: `refs/heads/B` is authoritative, and the CAS is
  `git update-ref refs/heads/B <new> <old|"">`. No push. Stated in the file
  header.
- Network git runs with `GIT_TERMINAL_PROMPT=0`, so an HTTPS credential prompt
  cannot hang while the global attach lock is held.
- **A read whose refresh fails dies.** It never falls back to a stale tracking
  ref, because a stale "absent" becomes `blob_pre=false`, and that rolls back a
  blob another clone owns. Offline writes are t1259.

**R2 — one probe, the single seam.** `_artifact_gitbranch_probe` →
`ABSENT` | `STORE:<id>` | `UNPUBLISHED:<id>` | `RETIRED:<id>:<to>` | `OCCUPIED`.
- Tip source, remote mode: the remote ref when origin has `B` (published).
  Otherwise a local `refs/heads/B`: marked → `UNPUBLISHED:<id>` (a store that
  exists only in this clone, e.g. created before `origin` was added); unmarked →
  `OCCUPIED`. Otherwise `ABSENT`. No-remote mode never yields `UNPUBLISHED`: the
  local ref *is* the store of record.
- `RETIRED:<id>:<to>` = a valid marker **plus** a `.ait-artifact-retired` file
  (`store_id`, `retired_to`, `retired_at`). It is written once, by
  `gitbranch-migrate`, as the cutover fence (see the migration contract). The
  marker itself is never rewritten.
- `ABSENT` → root commit (no `-p`) carrying blob + marker, pushed with
  expected-absent.
- `STORE` → append on the tip; **the existing marker is never rewritten**.
- **`UNPUBLISHED` → a write must publish before it succeeds.** The CAS builds on
  the local tip and pushes with **expected-absent**, *even when the build is a
  NOOP* (the blob or entries are already on the local tip). In that case the
  local tip itself is pushed. Only a successful push ends the write, so an
  unchanged local tip can never yield a write success. Reads (`get`, `list`) may
  serve bytes from the local tip: they are real and hash-verified, and reading
  them claims nothing about publication. `head` reports local presence (used
  only as `blob_pre`, the conservative direction for rollback). **`put`'s
  idempotent short-circuit applies only to a published `STORE`**, so it never
  skips the publish.
- `RETIRED` → reads allowed (the blobs stay on the branch); **every write dies**
  with: `artifact store <id> was migrated from 'X' to '<to>' — pull the data
  branch and set artifacts.backends.gitbranch.branch: <to>`.
- `OCCUPIED` → die, mutating nothing:
  > `artifacts.backends.gitbranch.branch is 'X', but branch 'X' already exists and is not an aitask artifact store (no .ait-artifact-store marker at its tip). Refusing to write artifact commits onto an existing branch — pick an unused branch name.`

  Re-evaluated on every CAS iteration. Two concurrent first writers converge: the
  loser's expected-absent push is rejected, and it retries on the winner's root.

**R3 — project-level identity; the minted id stays provisional until published.**
- Data-branch record: `artifacts/gitbranch_store.json` =
  `{"store_id": "...", "branch": "..."}`.
- **The record is always derived from the branch, after the store write.** Every
  gitbranch *write* path (create, update, move→gitbranch) calls
  `_artifact_gitbranch_record_sync` after `artifact_store`. It reads the
  `store_id` from the post-publish tip. If the record is absent, it writes the
  record and adds it to the same path-scoped commit. A loser of the root race
  therefore records the **winner's** id, never its own candidate.
- Read paths never write the record. A fresh clone of an existing store is
  allowed and adopts at its first write. (July plan: "adopt on any op". Writing
  a data-branch file from a lock-free `get` would leave an uncommitted file
  outside any transaction.)
- `store_id` survives migration.

**R4 — the guard, split by what it needs.**
`_artifact_activate <name>` wraps `artifact_registry_activate`. For `gitbranch` it
also runs `_artifact_assert_gitbranch_store`. It replaces the bare activation at
**every** site that can touch a gitbranch store: create, update, get, both
`move` activations of source/target (all three calls), and `init-store`.
`rm`'s explicit `artifact_registry_activate local` stays as it is. `rm`/`ls`
never touch a non-local store, so guarding them would only block metadata
cleanup.

*Local checks (no network; die before any mutation):*

| Record | Condition | Action |
|---|---|---|
| present | `record.branch` ≠ configured branch | **die** with the migrate message |
| absent | `artifact_manifest backends` lists `gitbranch` | **die**: the record is missing although gitbranch manifests exist; restore `artifacts/gitbranch_store.json` from data-branch history |
| present, branch matches | — | export `ARTIFACT_GITBRANCH_STORE_ID=<record.id>` |
| absent, no gitbranch manifests | — | export `ARTIFACT_GITBRANCH_STORE_ID=""` (first use) |

*Adapter-enforced (at the first store access, same probe):*

| Expected id | Probe | Action |
|---|---|---|
| any | `OCCUPIED` | die (R2) |
| set | `STORE:<same>` | allow |
| set | `STORE:<other>` | die, naming both ids |
| set | `ABSENT` | die: the store is missing from `<branch>` (deleted? `git push` it back from a clone that has it) — **never re-bootstraps** |
| empty | `STORE:<x>` | allow (record adopted at write time) |
| empty | `ABSENT` | reads: absent / empty / "not present"; writes: bootstrap |
| set or empty, id matches if set | `UNPUBLISHED:<x>` | reads: serve the local tip; writes: publish it (R2) |
| set or empty, id matches if set | `RETIRED:<x>:<to>` | reads: allow; writes: die (R2) |
| set | `UNPUBLISHED`/`RETIRED` with another id | die, naming both ids |

A cache hit therefore needs no network, and an offline `get` of a cached
version still works. Its bytes are hash-verified by `artifact_resolve`.

Migrate message (rename case):
> `artifacts.backends.gitbranch.branch is 'Y', but this project's artifact store is <id> on branch 'X'. Blobs on 'X' will not resolve from 'Y'. Set the branch back to 'X', or migrate the store with: ait artifact gitbranch-migrate --from X --to Y`

Do not suggest `ait artifact move` here: a same-backend move is a no-op success,
and manifests carry no branch coordinate.

`ARTIFACT_GITBRANCH_STORE_ID` is added to `_AIT_ARTIFACT_REGISTRY_PARAM_VARS`, so
every activation clears it. (The registry's `^ARTIFACT_` guard is unaffected.
`KNOWN_ADAPTERS` maps only `branch`, so config can never set it.)

## Implementation steps

### Pre-phase (risk mitigations)
1. [baseline_artifact_suites] Before editing anything, run on the current tree
   and record the pass/fail counts: `test_artifact_dir_backend.sh`,
   `test_artifact_cli.sh`, `test_artifact_share_resolution.sh`,
   `test_attach_local_backend.sh`, `test_artifact_manifest_lib.sh`,
   `test_attach_lock_callback_contract.sh`, `test_attach_txn_worktree_isolation.sh`,
   `test_artifact_fold_transfer.sh`, `test_attach_fold_rebind.sh`,
   `test_metadata_writer_inventory.py`. A suite that is red at baseline is
   reported, not "fixed" by this task. Do not stash: run them on the tree as it
   is (the tree has unrelated dirty files from other sessions).

### 1. `lib/artifact_registry.py`
- `validate_value`: add a `ref_name` arm. Rules: matches
  `^[A-Za-z0-9][A-Za-z0-9._/-]*$`; no `..`, `//`, `/.`, `@{`; no leading or
  trailing `/`; no trailing `.` or `.lock` (per `/`-component too); not `HEAD`.
  **Reserved** (exact): `main`, `master`, `aitask-data`, `aitask-locks`,
  `aitask-ids` (same set as `aitask_web_merge.sh::is_skip_branch`). The message
  names `artifacts.backends.gitbranch.branch`.
- Factor the rule into `check_ref_name(value) -> error|None`, so `validate_value`
  and the new verb share it.
- `KNOWN_ADAPTERS["gitbranch"] = {"branch": ("ARTIFACT_GITBRANCH_BRANCH", "ref_name")}`.
  Update the `# BACKEND-EXTENSION-POINT (registry)` comment's validator list.
- New verbs, wired into `main` and its usage line:
  - `adapters` — `local` + `sorted(KNOWN_ADAPTERS)`, independent of config.
  - `validate-ref <name>` — exit 0 silently, or exit 1 with the message on
    stderr.
- The module docstring gets the gitbranch config example.

### 2. `lib/artifact_registry.sh`, `lib/artifact_backend.sh`
- `_AIT_ARTIFACT_REGISTRY_PARAM_VARS=( ARTIFACT_DIR_ROOT ARTIFACT_GITBRANCH_BRANCH ARTIFACT_GITBRANCH_STORE_ID )`.
- `artifact_backend.sh`: `source` line for `artifact_backends/gitbranch.sh`, a
  `gitbranch) "artifact_gitbranch_${op}" "$@" ;;` arm, and `known: local, dir, gitbranch`.
  Header prose updated.

### 3. NEW `lib/artifact_backends/gitbranch.sh` (shape mirrors `dir.sh`)
Double-source guard. A header covering R1–R3, the no-remote authority, and the
errexit-off discipline (every failure path has its own `die`, or `return` in
delete).
- `_artifact_gitbranch_branch` — fail-closed accessor (`die` if unset).
- `_artifact_gitbranch_has_remote` — `git remote get-url origin`.
- `_artifact_gitbranch_refresh <read|cas>` — sets `_AGB_TIP` (sha or empty) and
  `_AGB_EXPECT` (lease value). `read` skips the network when
  `_ARTIFACT_GITBRANCH_FRESH_FOR == branch`; `cas` always goes to the network and
  sets the memo. In remote mode: `ls-remote --exit-code origin refs/heads/B`
  (0 → fetch explicit refspec, tip = tracking ref; 2 → prune a stale tracking
  ref with `update-ref -d`, then use the local-branch fallback; else die).
- `_artifact_gitbranch_classify <tip>` → state line. `_artifact_gitbranch_probe`
  = refresh(read) + classify. `_artifact_gitbranch_check_expected <state> <op-kind>`
  applies the adapter table above.
- `_artifact_gitbranch_build <tip> <mode> <args…>` runs in a **subshell** with
  its own EXIT trap removing a `mktemp -d` dir. `GIT_INDEX_FILE=<dir>/index` is a
  *nonexistent* path: git rejects a 0-byte index file. `read-tree <tip>` (unless
  root), `update-index --add --cacheinfo 100644,<oid>,<path>` /
  `--force-remove <path>`, `write-tree`, `commit-tree [-p <tip>]`. Prints the
  commit sha, or `NOOP` when the tree is unchanged. The user's real index is
  never touched.
- `_artifact_gitbranch_publish <commit>` → 0 published / 1 lease lost / die.
  Uses the R1 classifier, the remote-tracking update and the mirror.
- `_artifact_gitbranch_cas <mode> <args…>` — loop: refresh(cas) → classify →
  check_expected (write kind: RETIRED dies) → build → publish. Retries only on 1.
  **NOOP rule:** NOOP ends the loop without pushing only for a published
  `STORE` (or no-remote mode). For `UNPUBLISHED`, `<commit>` := the local tip,
  pushed with expected-absent.
- Contract ops:
  - `head <hash>` — validate the hash; probe (dies on unusable); ABSENT → 1;
    `git cat-file -e <tip>:blobs/<shard>`.
  - `get <hash> <dest>` — empty dest dies; `git cat-file blob <tip>:<path>` to
    stdout (`-`) or into the dest, checked; not present → die.
  - `put <hash> <file>` — probe is a published `STORE` (or no-remote) and the
    blob is on the tip → 0 (idempotent; no commit). Otherwise
    `git hash-object -w`; verify `git cat-file blob <oid> | artifact_sha256 == hash`
    (the staged bytes, as in `dir.sh`); then CAS add-mode. A fresh tip that
    already holds the blob → NOOP. ABSENT adds the marker with a new
    `od -An -N16 -tx1 /dev/urandom` id.
  - `delete <hash>` — body runs in `( … ) || return 1`, so an inner `die` only
    returns. CAS remove-mode; absent → 0.
  - `list` — probe; ABSENT → empty; `git ls-tree -r --name-only <tip> -- blobs/`
    → `sha256:<2><62>`. A failed `ls-tree` dies, so a failed listing never reads
    as an empty one.
  - `init` — CAS marker-only mode. ABSENT (expected empty) → `INITIALIZED:branch <b>`;
    UNPUBLISHED → NOOP-publish of the local tip → `INITIALIZED:branch <b>`
    (published); published STORE (matching or expected empty) →
    `ALREADY_INITIALIZED:branch <b>`; RETIRED/other → the table's die.
  - `artifact_gitbranch_store_id` — prints the probed id (empty for ABSENT/OCCUPIED).
  - `artifact_gitbranch_migrate_from <src-tip> <store-id>` (internal, used only
    by the verb): CAS union-mode on the active branch. **Every iteration**
    re-checks the target: only ABSENT or the same `<store-id>` is accepted, so a
    different store appearing after the verb's precondition dies instead of being
    merged. ABSENT → a root commit whose tree is
    `<src-tip>`'s `blobs/` + marker, built in a temp index that `--force-remove`s
    any `.ait-artifact-retired`, so the fence never propagates. STORE /
    UNPUBLISHED with the same id → add every missing `blobs/` entry of the source
    tree. NOOP when nothing is missing, except that UNPUBLISHED still publishes
    (NOOP rule). git object ids make the copy byte-exact.
  - `artifact_gitbranch_retire <to>` (internal, used only by the verb): CAS on
    the active branch. A published STORE (or UNPUBLISHED, which publishes) → a
    commit adding `.ait-artifact-retired` (`store_id`, `retired_to: <to>`,
    `retired_at`) on the **fresh** tip. Prints that new tip's **parent** (the
    final pre-fence tip, which holds every blob anyone managed to publish there).
    `RETIRED:<same id>:<to>` → NOOP; prints the retirement commit's parent.
    `RETIRED:…:<other>` → die.

### 4. `lib/artifact_manifest.py` — `backends` verb
Distinct `backend` values across manifests, sorted, one per line. It loads every
member through `load()`, so a malformed manifest dies (named), the same
fail-closed rule as `referenced-hashes`. Wired into `main` and its usage line. No
`artifact_manifest.sh` change: the bash front passes the verb through.

### 5. `aitask_artifact.sh`
- Helpers, all errexit-safe (`|| die` on every capture):
  - `_artifact_gitbranch_record_relpath` → `artifacts/gitbranch_store.json`;
  - `_artifact_gitbranch_record_read` → prints `<id>\t<branch>` or empty (python
    json; malformed → die);
  - `_artifact_assert_gitbranch_store` (local checks + export);
  - `_artifact_activate <name>`;
  - `_artifact_gitbranch_record_sync <commit-paths-array-name>` — after the
    store write. Reads `artifact_gitbranch_store_id` (memo-fresh after publish;
    empty → die). If the record is absent, writes it with `printf` (the id is hex
    and the branch passed the ref validator, so JSON-safe) and appends its path.
    If it is present and different → die (cannot happen after the guard; stays
    fail-closed).
- `_artifact_create_txn`, `_artifact_update_txn`: `artifact_registry_activate
  "$backend"` → `_artifact_activate "$backend"`. When the backend is `gitbranch`,
  `txn_require_clean` + `txn_snap_add` the record path at the transaction
  boundary (before the first mutation), then call `record_sync` after
  `artifact_store` and before `_artifact_commit`. The snapshot makes rollback
  delete a newly written record.
- `_artifact_move_txn`: all three activations → `_artifact_activate`. Target
  `gitbranch` → the same record boundary, plus `record_sync` after phase 2.
- `cmd_get`, `cmd_init_store`: `_artifact_activate`.
- **NEW `gitbranch-migrate --from <old> --to <new>`** (dispatch + help text):
  - Pre-lock: both names pass `artifact_registry.py validate-ref`; old ≠ new;
    `artifact_registry_activate gitbranch` (must be registered).
  - **Cutover contract — a shared fence, not a pause request.** The attach lock
    is checkout-local (`attachment_lock_dir` lives under this clone's
    `.aitask-data`), so it cannot exclude other clones. The fence lives **on the
    store branch itself**, so every writer in every clone meets it through the
    same CAS it already runs. Once `<old>` carries `.ait-artifact-retired`, any
    write to it dies at the CAS (R2 `RETIRED`). That happens inside `put`, before
    the writer's manifest is committed. A writer that published *before* the
    fence landed is inside the fenced tip by construction: the retirement push is
    leased on the freshly fetched tip, so nothing can land between that fetch and
    the fence without failing the lease. The catch-up copy reads exactly that
    pre-fence tip, so there is no window between "last source refresh" and
    "cutover". Writers do not need to pause. A late writer gets a fail-closed die
    telling it to pull and reconfigure, never a lost blob. `<old>` therefore
    receives exactly one commit (the fence). Its blobs stay readable, so a clone
    still configured on `<old>` can keep reading until it syncs.
  - `with_attach_lock _artifact_gitbranch_migrate_txn`, whose first statement is
    `txn_begin "ait artifact gitbranch-migrate"`. Every step is idempotent, so a
    crashed or repeated run converges:
    0. **Local preflight, before any probe or store mutation:**
       `txn_require_clean` + `txn_snap_add` on `artifacts/gitbranch_store.json`.
       Also `txn_set_resume_hint "ait artifact gitbranch-migrate --from <old> --to <new>"`.
       A dirty record is therefore refused while both branches are untouched.
    1. **Store identity.** The record (if present) must name `<old>` **or
       `<new>`** (a completed or partly completed earlier run); anything else →
       die, naming where the store is. `S = record.id`. Without a record, S comes
       from the source probe.
    2. **Source.** `BRANCH=<old>`, `STORE_ID=S`; the probe must be `STORE:S`,
       `UNPUBLISHED:S` or `RETIRED:S:<new>`. `RETIRED:S:<other>` → die.
    3. **Target precondition, before any mutation.** `BRANCH=<new>`,
       `STORE_ID=""`, probe. `ABSENT` (only when the record does not already name
       `<new>`), `STORE:S` or `UNPUBLISHED:S` → continue. `STORE:<other>` → die
       naming both ids; `OCCUPIED` → die (R2 message). Both die-arms leave
       `<new>` byte-unchanged.
    4. **Bulk copy:** `artifact_gitbranch_migrate_from <old-tip> S` onto `<new>`.
    5. **Fence:** `BRANCH=<old>`, `STORE_ID=S`;
       `final_tip=$(artifact_gitbranch_retire <new>) || die`.
    6. **Catch-up:** `BRANCH=<new>`; `artifact_gitbranch_migrate_from "$final_tip" S`
       (NOOP when nobody wrote in between).
    7. **Verify:** every `blobs/` entry of `final_tip` is `head`-present on
       `<new>`; the `<new>` probe is a published `STORE:S`.
    8. **Record** = `{S, <new>}` (already preflighted in step 0). If unchanged,
       there is no data commit; otherwise a path-scoped commit
       `ait: Migrate gitbranch artifact store <S> to <new>`, with
       `|| txn_abort "…"`.
    9. Report `MIGRATED` (something changed) or `ALREADY_MIGRATED` (steps 4–8
       were all NOOPs: no commit on `<old>`, `<new>` or the data branch). Remind
       the user to set `artifacts.backends.gitbranch.branch: <new>` when the
       config still names `<old>`.
  - A retired branch is final. To recover from a failed run, re-run the same
    command; there is no "un-retire".
  - **Progress and failure reporting tell the truth about retained remote
    effects.** Remote commits are deliberately not rolled back: reverting a
    published commit or removing the fence would re-open the race. Each step
    that changed a branch prints a stderr progress line *and* registers it with
    `txn_retain`:
    - "branch '<new>' advanced to <sha> (store <S>; INCOMPLETE until the
      migration record is committed)";
    - "branch '<old>' RETIRED at <sha> — it now refuses artifact writes; this is
      final, do not remove .ait-artifact-retired".
    A NOOP step registers nothing. On any abort after that point (EXIT trap or
    `txn_abort`), the report lists what the snapshot restored locally (the
    record), lists the **retained** effects as such, and ends with
    `Resume with: <hint>`. It never says "nothing was committed".

### 5b. `lib/txn_snapshot.sh` — additive retained-effects reporting
Shared by attach, artifact and fold, so the change is **additive with
byte-identical defaults**:
- New globals `_TXN_RETAINED=()` and `_TXN_RESUME_HINT=""`, reset in
  `txn_begin`.
- `txn_retain <text>` appends; `txn_set_resume_hint <cmd>` sets.
- `txn_rollback_report`: when `_TXN_RETAINED` is empty, the output is exactly
  today's (pinned by the existing suites). When it is non-empty:
  - ok → `warn "<ctx> — local changes rolled back; nothing was committed on the
    data branch"`, then "These effects were RETAINED (not rolled back, by
    design):" + items, then `Resume with: <hint>`;
  - incomplete → the itemized failure list, with "Nothing was committed on the
    data branch, but…" in place of the old sentence, then the retained list and
    the resume hint.
  Still returns 0 (the t1283 lock-leak rule).
- `txn_abort`: today a **complete** local rollback goes straight to `die "$msg"`
  and never calls `txn_rollback_report`. `txn_rollback` has already cleared
  `_TXN_ACTIVE`, so the EXIT trap cannot print it either. New success branch:
  when `_TXN_RETAINED` is non-empty, call `txn_rollback_report 1 "${_TXN_LABEL}: aborted"`
  (which prints the retained list and `Resume with:`) **before** `die "$msg — remote effects retained, see above"`.
  With an empty `_TXN_RETAINED`, the branch is unchanged: a bare `die "$msg"`.
  The incomplete branch already reports; it gains the retained list through
  `txn_rollback_report`.
- The file header and help text mention gitbranch, `init-store gitbranch` and
  the migrate verb.

### 6. Tests — NEW `tests/test_artifact_gitbranch_backend.sh`
Written **first** and run before the adapter exists: confirm it exits 1, which
proves the exit path. Uses the `test_artifact_dir_backend.sh` idiom
(scratch-cwd, `asserts.sh`, legacy-mode repo, `XDG_CACHE_HOME` in the fixture,
`write_config`), plus a bare remote + clones A/B (`test_task_git.sh::setup_repo_with_remote`
shape). If test bodies run in `( … )`, opt into the file-backed counters
(`assert_counters_init` / `assert_counters_load`, per CLAUDE.md t1207).

Contention is injected **without production test hooks**, using a fixture
`pre-push` hook in clone A. On its first run, it performs an interloping write
from clone B and records the commit A was pushing (from the hook's stdin) to a
file. A's lease is then genuinely rejected.

1. Round-trip put → head → get (file and `-`) → list. A double put adds no
   second commit.
2. First-write bootstrap: a parentless root carrying blob + marker; a second put
   extends it (parent = root, marker blob oid unchanged).
3. Two concurrent first writers (hook: B bootstraps first) → one root, both
   blobs, linear history, A's commit parent = B's root.
4. Two-clone concurrent full `ait artifact create` → exactly one marker; both
   records equal the marker's id. **Negative control:** A's record ≠ the id in
   the root commit A tried to push (read from the hook's capture).
5. Publish: A creates + pushes main; B pulls and runs `get` on a cold cache →
   correct bytes. **Negative control:** with the remote made read-only
   (`chmod -R a-w`), `create` fails, HEAD gains no manifest, and the working
   tree has no manifest and no record.
6. User index untouched: stage an unrelated file; put + delete; the
   `git diff --cached --name-only` output is unchanged.
7. CAS on an existing branch: the hook advances the remote branch from B →
   both blobs present **and** A's new tip's parent == the interloper commit (the
   real oracle against a memo leaking into the CAS loop).
8. Reserved (each of the 5) and malformed names die naming the key;
   `validate-ref` agrees with activation over the same table; `adapters` prints
   `local dir gitbranch`.
9. Unregistered / adapterless / missing-`branch` config dies.
10. Cross-activation: activating `local` or `dir` clears `ARTIFACT_GITBRANCH_BRANCH`
    and `ARTIFACT_GITBRANCH_STORE_ID`.
11. Guard matrix through `create`, `update` and `get` (cold cache): record
    renamed-branch (also with the remote unreachable — proves no network is
    needed); record missing with gitbranch manifests; present+ABSENT;
    present+STORE:other; any+OCCUPIED; absent+STORE adopt. Positive: `rm` and
    `ls` still work under a renamed config. A warm-cache `get` with the remote
    unreachable succeeds when the record matches.
12. Unmarked existing branch rejected, not adopted: `create` **and**
    `gitbranch-migrate --to <it>` die naming it, and `git rev-parse` is equal
    before and after. **Negative control:** the same branch with a valid marker
    at its tip is accepted.
13. `gitbranch-migrate` copies every blob and preserves `store_id`. `<old>`
    gains exactly one commit (the fence; its parent is the pre-migration tip,
    and every blob is still readable there). After the config is set to `<new>`,
    the guard is lifted (`get` works). **Two consecutive identical invocations:**
    the second prints `ALREADY_MIGRATED`, and `<old>`, `<new>` and the data
    branch HEAD are all equal before and after it.
14. Migrate target with a different `store_id` dies before any write; the error
    names both ids; the target tip is unchanged.
18. **Local-only store published on write.** A no-remote repo creates artifact
    a1 (the store exists only locally). Then `origin` (a bare repo) is added, and
    a second `create` is run **with a1's exact bytes**: the blob is already on the
    local tip, so the old short-circuit would never push. Assert that origin now
    has `B` with the blob and that clone B (pull main + cold-cache `get`) returns
    both artifacts' bytes. **Negative control:** the same sequence with the bare
    remote read-only → `create` dies, HEAD gains no manifest, origin has no `B`.
    The same applies to `init-store gitbranch` on an UNPUBLISHED store: it
    publishes the unchanged tip.
19. **Migration cutover, two clones.** A and B share the store on X. During A's
    `gitbranch-migrate --from X --to Y`, a fixture `pre-push` hook on A's
    **first** push (the bulk copy to Y) runs B's `create` on X (B is still
    configured on X) → that blob lands between the bulk copy and the fence.
    Assert it is on Y after the migration (caught by the catch-up). **After** the
    migration, B (still on X, data branch not yet pulled) runs `create` → dies
    naming Y; B's HEAD gains no manifest; X's tip is still the fence commit.
    Then B pulls and sets its config to Y → `get` of B's earlier artifact
    succeeds from Y. **Negative control (no production shim):** in a copy of
    the fixture, push a plain commit that removes `.ait-artifact-retired` from X.
    B's late `create` now succeeds and its blob is on X but not on Y. That proves
    the fence, not something incidental, is what stops the stranded blob.
20. **Migrate preflight.** Leave `artifacts/gitbranch_store.json` with an
    uncommitted edit → `gitbranch-migrate` dies naming the path. The local
    `refs/heads/X`, `refs/heads/Y` and the remote refs for X and Y are identical
    before and after (Y still absent); X carries no `.ait-artifact-retired`.
21. **Migrate failure reporting + convergence** (faults injected with fixture
    hooks only):
    (a) *Catch-up push fails after retirement.* Test 19's interleaving makes the
        catch-up non-NOOP, and A's `pre-push` hook rejects its 3rd push. Assert:
        exit ≠ 0; stderr names Y as advanced/INCOMPLETE and X as RETIRED and
        final; it contains `Resume with: ait artifact gitbranch-migrate --from X --to Y`;
        it does **not** contain "nothing was committed" unqualified; the record
        is restored (still names X); the attach lock is released (an immediate
        `ait artifact ls` and the rerun do not report a busy lock).
    (b) *Final record commit fails* (the explicit `txn_abort` path). A fixture
        `pre-commit` hook rejects commits that stage
        `artifacts/gitbranch_store.json`. The same assertions apply, and
        specifically: stderr contains **both** retained items (Y advanced, X
        RETIRED) **and** the exact line
        `Resume with: ait artifact gitbranch-migrate --from X --to Y`. The record
        file is restored to its pre-run bytes.
    In both cases, rerunning without the hook → `MIGRATED`, every blob is on Y,
    and the record names Y. A third run → `ALREADY_MIGRATED` with no commits
    anywhere.
22. **txn report default unchanged.** An ordinary artifact create abort (as in
    test 16) prints the exact pre-existing rollback sentence. An ordinary
    explicit `txn_abort` with nothing retained still prints only the `die`
    message: no `RETAINED` and no `Resume with:` lines. The existing attach and
    fold suites stay green.
15. No-remote repo: local ref authoritative, round-trip works, and no push is
    attempted (a `pre-push` hook that would fail stays silent).
16. Rollback: a create whose commit fails (fault-injected as in
    `test_attach_lock_callback_contract.sh` `run_faulted`) removes the blob it
    added from the branch, leaves no record file, and reports a clean rollback.
17. `init-store gitbranch`: INITIALIZED (a marker-only root) then
    ALREADY_INITIALIZED; a later `create` adopts its id into the record.

Plus `tests/test_artifact_manifest_lib.sh`: a `backends` case (distinct, sorted,
fail-closed on a malformed member).

### Post-implementation (Step 9)
Merge approval, `ait gates run 1231_1`, archival per task-workflow Step 9.

## Verification
- `bash tests/test_artifact_gitbranch_backend.sh` (first red, then green).
- Regressions — compare against the pre-phase baseline:
  `test_artifact_dir_backend.sh`, `test_artifact_cli.sh`,
  `test_artifact_share_resolution.sh`, `test_attach_local_backend.sh`,
  `test_artifact_manifest_lib.sh`, `test_attach_lock_callback_contract.sh`
  (static guard over the new migrate callback), `test_attach_txn_worktree_isolation.sh`,
  `test_artifact_fold_transfer.sh`, `test_attach_fold_rebind.sh` (shared
  `txn_snapshot.sh` defaults);
  `python3 -m pytest tests/test_metadata_writer_inventory.py` (or
  `run_all_python_tests.sh --test-dir`).
- `shellcheck .aitask-scripts/lib/artifact_backends/gitbranch.sh .aitask-scripts/aitask_artifact.sh .aitask-scripts/lib/artifact_backend.sh .aitask-scripts/lib/artifact_registry.sh`;
  `bash -n` on every touched script.

## Out of scope
`ait attach` stays local-only (t1258). Offline writes are t1259. Reaping orphan
gitbranch blobs on `rm` stays with the existing t1135 warning.

## Risk

### Code-health risk: medium
- New ~350-line network/CAS adapter (lease classifier, temp-index isolation,
  subshell-returning delete) running inside errexit-off transactions. A missed
  `|| die` or a mis-classified push failure could report success falsely ·
  severity: medium · → mitigation: none — covered by verification tests 3/4/5/7/16
  and the callback-contract static guard
- Edits to the shared create/update/move/get transaction paths could regress the
  `local` / `dir` defaults. Every new branch is keyed on `backend == gitbranch` ·
  severity: low (residual — addressed by inline pre-phase baseline_artifact_suites) ·
  → mitigation: inline pre-phase baseline_artifact_suites
- Publication and cutover correctness hinge on two new probe states,
  `UNPUBLISHED` (a write must push even on a NOOP) and `RETIRED` (the
  cross-clone migration fence). A write path that bypasses the CAS NOOP rule or
  the RETIRED write-die would reintroduce a local-only publish or a stranded
  blob · severity: medium · → mitigation: none — covered by verification tests
  18/19 (each with a negative control) and by routing every write through
  `_artifact_gitbranch_cas`
- `lib/txn_snapshot.sh` is shared with attach and fold. The retained-effects
  addition must leave the default report byte-identical · severity: low ·
  → mitigation: none — covered by verification test 22 and the attach/fold
  suites (`test_attach_txn_worktree_isolation.sh`,
  `test_attach_lock_callback_contract.sh`, `test_artifact_fold_transfer.sh`)
- Rollback of a txn-added blob can delete a blob that another clone published
  between our `head` and our `put` (the same window as the shared `dir` store;
  recoverable from branch history) · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: medium
- The guard deviates from the task's pinned text, for reasons verified above. It
  is not run on `rm`/`ls`, the record is adopted at write time rather than on
  read, and the id checks happen in the adapter. t1231_2/t1231_3 consume
  `adapters`, `validate-ref`, the die messages and `gitbranch-migrate`; those
  interfaces are kept as pinned · severity: low · → mitigation: none
  (send t1231_3 a note at Step 8e describing the final guard and the
  `init-store gitbranch` behaviour)
- An SSH credential prompt can still block while the global attach lock is
  held. `GIT_TERMINAL_PROMPT=0` covers only HTTPS; this is the same exposure as
  `aitask_lock.sh` · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: pre-phase | name: baseline_artifact_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Code-health — regression on local/dir defaults | desc: Run the artifact/attach regression suites on the untouched tree and record the baseline counts before editing

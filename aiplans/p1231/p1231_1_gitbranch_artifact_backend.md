---
Task: t1231_1_gitbranch_artifact_backend.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_2_artifacts_settings_tab.md, aitasks/t1231/t1231_3_artifact_documentation.md
Archived Sibling Plans: (none — first child)
Base branch: main
plan_verified: []
---

# t1231_1 — `gitbranch` artifact backend

## Context

`ait artifact`'s zero-config `local` backend derives its blob root from
`_ait_detect_data_worktree` and commits blobs with `task_git`, so every artifact
lands on the **aitask-data branch** next to every task and plan file.
`aidocs/unified_artifact_design.md` §7 names the consequence directly: `local`
"bloats that branch for large HTML". The only shipped alternative, `dir`
(`lib/artifact_backends/dir.sh`), requires an out-of-band absolute path that
every teammate must mount identically.

`gitbranch` is the missing option: blobs stay **in git** (they travel with a
clone, need no mount and no credentials) but live on a **dedicated orphan
branch**, written via **git plumbing only — no worktree**, so they never
materialize in any checkout.

This is the first and riskiest of t1231's three children. Read the parent plan
`aiplans/p1231_configurable_git_branch_artifact_backend.md` §"Correctness model"
before starting — rules **R1–R4** each close a specific reviewed defect and are
restated below.

### The discovery that makes this additive

`aitask_artifact.sh` guards blob-staging with `[[ "$backend" == "local" ]]` at
seven sites — **L282** (create commit paths), **L308** (create rollback),
**L361/L366** (update), **L437** (move), **L530** (rm orphan sweep), **L553**
(the non-local warn) — and `artifact_cache.sh` at **L51** (resolve symlink fast
path) and **L96** (store symlink fast path). For a non-`local` backend all of
them already do the right thing: stage manifest + task file only, skip the blob,
and fall through to the generic `head`+`get` / copy-warm path.

**No changes to the transaction, rollback, or commit-path logic are required.**
`gitbranch` slots in exactly where `dir` does. The only CLI-layer additions are
the R4 store guard and the `gitbranch-migrate` verb.

## Config contract (PINNED)

```yaml
artifacts:
  default_backend: gitbranch
  backends:
    gitbranch:
      branch: aitask-artifacts
```

Single key. The remote is hard-coded `origin`, matching `aitask_lock.sh`.
On-branch layout:

```
blobs/<2hex>/<62hex>      # content-addressed blob (same sharding as local/dir)
.ait-artifact-store       # store identity marker at the tree root
```

Marker contents:

```
store_id: <32 lowercase hex>
branch: <branch name at init>
created_at: <YYYY-MM-DD HH:MM>
```

## Correctness model

### R1 — the remote is the store of record; publish is push-gated

When a remote is configured the store tip is `refs/remotes/origin/<branch>`;
local `refs/heads/<branch>` is a mirror, never the authority.

**Fetch memoization is READ-ONLY.** A per-process memo (shape of
`_ait_detect_data_worktree`, `lib/task_utils.sh:26-42`) serves `head` / `get` /
`list`, where one refresh per process is enough. It must **never** serve a CAS
iteration: every pass of the `put` / `delete` loop begins with an unconditional
`git fetch origin <branch>` that also invalidates the memo. A lease rejection
means the observed tip was stale *by definition*, so retrying against a memoized
tip rebuilds the same losing commit and livelocks until the retry budget is
exhausted — a failure that only appears under real contention.

`put` orders **push first, local ref second**:

1. build the new commit;
2. `git push --force-with-lease=refs/heads/<branch>:<observed-tip> origin <commit>:refs/heads/<branch>`;
3. only on success, `git update-ref refs/heads/<branch> <commit> <observed-tip>`.

A failed or lease-rejected push **does not return success** — a lease rejection
re-enters the CAS loop; exhaustion or a hard failure `die`s. Warn-and-continue is
unsound: the next step of the artifact transaction commits a manifest on
`aitask-data`, so a locally-only blob publishes a handle a second clone can
resolve but cannot `get`. It also contradicts `artifact_store`'s own post-`put`
lost-put `head` check (`artifact_cache.sh:87-109`).

Push succeeded but local `update-ref` failed ⇒ the store is still correct; a
later fetch repairs the mirror. Do not fail the operation for that.

**No remote configured:** `refs/heads/<branch>` is authoritative, no push is
attempted. State this in the backend file header.

### R2 — three-state probe; first write bootstraps a root commit

There is no separate init step. `_artifact_gitbranch_probe` classifies the
branch and is **re-evaluated on every CAS iteration** (a branch can appear
mid-loop):

| State | Meaning | Action |
|---|---|---|
| `ABSENT` | ref exists neither on `origin` (when configured) nor locally | may be initialized |
| `STORE:<store_id>` | ref exists, tip carries a valid `.ait-artifact-store` | normal CAS append (subject to R4) |
| `OCCUPIED` | ref exists, tip has **no valid marker** | **fail closed, always** |

- **`ABSENT`** → `mktree` a tree containing the blob **and** the marker,
  `commit-tree` **with no `-p`**, **plain (non-force) push**
  `origin <commit>:refs/heads/<branch>`, then
  `git update-ref refs/heads/<branch> <commit> ""` (empty old-value = must not exist).
- **`STORE:<id>`** → `read-tree <tip>` / `update-index` / `write-tree` /
  `commit-tree -p <tip>` / lease push.
- **`OCCUPIED`** → die without mutating anything.

**Ref absence is not marker absence.** The reserved-name validator blocks only
five names, so any ordinary feature or release branch is a legal config value.
Treating an existing unmarked ref as "not initialized yet" would append artifact
blob commits onto a live branch. Only a nonexistent ref may be initialized:

> `artifacts.backends.gitbranch.branch is 'X', but branch 'X' already exists and
> is not an aitask artifact store (no .ait-artifact-store marker at its tip).
> Refusing to write artifact commits onto an existing branch — pick an unused
> branch name.`

Two concurrent first writers cannot create incompatible roots: the loser's plain
push is rejected as non-fast-forward, it re-enters the loop, observes the
winner's tip and rebuilds on top. Same recipe as `aitask_lock.sh:102-113`, plus
a retry.

### R3 — store identity is project-level, and provisional until the root push wins

The registry model is **one instance per adapter**
(`unified_artifact_design.md` §6), so identity is project-level, not
per-manifest:

- **On the artifact branch:** `.ait-artifact-store`, committed with the root commit.
- **On the data branch:** `artifacts/gitbranch_store.json` —
  `{"store_id": "...", "branch": "..."}`, committed inside the same path-scoped
  transaction as the first artifact's manifest.

`store_id` is generated once and **survives migration** — that is what keeps the
identity stable while the branch coordinate moves.

**The minted id is provisional.** The R4 guard's absent/`ABSENT` arm is not
serialized across clones: two clones each running a first `ait artifact create`
both pass it, and each mints a candidate id into its own root commit. One root
push wins. The loser must therefore:

1. after the CAS loop settles, **re-read `.ait-artifact-store` from the winning
   tip** and use *that* `store_id` for `artifacts/gitbranch_store.json`;
2. when rebuilding on an existing tip, **never overwrite an existing marker** —
   the rebuild adds only the blob.

The marker is thus written exactly once, by whoever creates the root, and every
clone's record derives from the branch rather than from its own local candidate.
Without this the two records diverge permanently and R4 starts failing on the
loser for a store it can actually read.

### R4 — the guard runs on every gitbranch-touching operation

`_artifact_assert_gitbranch_store` in `aitask_artifact.sh`, called immediately
after `artifact_registry_activate` in **create, update, get, rm, list, and both
the source and target legs of move**. Its input is the R2 probe, not marker
presence:

| Record | Probe | Action |
|---|---|---|
| absent | `ABSENT` | first use — allow; lazy init writes both |
| absent | `STORE:<id>` | adopt `<id>` into the record (fresh clone of an existing store) |
| present | `STORE:<matching id>` | allow |
| present | `ABSENT` | **die** |
| present | `STORE:<different id>` | **die** |
| *any* | `OCCUPIED` | **die** (R2) |

Die message names the migration verb, **not** `ait artifact move`:

> `artifacts.backends.gitbranch.branch is 'Y', but this project's artifact store
> is <store_id> on branch 'X'. Blobs on 'X' will not resolve from 'Y'. Restore
> the branch name, or migrate the store with:
> ait artifact gitbranch-migrate --from X --to Y`

**Why not `ait artifact move`:** `_artifact_move_txn` short-circuits a
same-backend move as a no-op success, and manifests record only
`backend: gitbranch` with no branch coordinate — so `--to gitbranch` after a
rename does literally nothing while the source adapter already reads the new
branch. Never offer it as the remedy.

## Implementation steps

### 1. `lib/artifact_registry.py` — validator, adapter entry, two new subcommands

- Add a `ref_name` arm to `validate_value` (L97-106): non-empty string, git
  ref-name shape (`^[A-Za-z0-9][A-Za-z0-9._/-]*$`, no `..`, no trailing `.lock`,
  no leading/trailing `/`), plus a **reserved-name rejection** for `main`,
  `master`, `aitask-data`, `aitask-locks`, `aitask-ids` — the same reserved set
  as `aitask_web_merge.sh:222`. Pointing the blob store at `main` must be
  impossible, not discouraged.
- `KNOWN_ADAPTERS` (L44-47):
  `"gitbranch": {"branch": ("ARTIFACT_GITBRANCH_BRANCH", "ref_name")}`.
- Update the validator list in the `# BACKEND-EXTENSION-POINT (registry)`
  comment (L42-43) — it currently documents only `abs_path` and `nonempty`.
- **New `adapters` subcommand** — prints `local` then `sorted(KNOWN_ADAPTERS)`:
  the *available* adapters, independent of config. `cmd_list` (L149-154) prints
  only *registered* backends, so on a fresh project `gitbranch` is unlistable and
  could never be selected to create its own first configuration. t1231_2's
  selector consumes this; leave `cmd_list` unchanged for "what is configured".
- **New `validate-ref <name>` subcommand** — runs the `ref_name` validator
  standalone, exit 0 on success, exit 1 with the message on stderr otherwise. It
  lets the settings TUI validate a branch name *before* the backend is
  registered, without re-encoding the regex or the reserved list in UI code.
- Wire both into `main` (L157-178).

### 2. `lib/artifact_registry.sh` and `lib/artifact_backend.sh`

- `artifact_registry.sh` L33 — extend `_AIT_ARTIFACT_REGISTRY_PARAM_VARS` with
  `ARTIFACT_GITBRANCH_BRANCH`. Required so `move` (which activates source then
  target in one process) does not leak params across activations.
- `artifact_backend.sh` — the `source` line at the L36
  `# BACKEND-EXTENSION-POINT (source)` marker, the `gitbranch)` arm at the L46
  `# BACKEND-EXTENSION-POINT (dispatch)` marker, **and** the `known:` list in the
  `*)` die at L47 (currently `known: local, dir`).

### 3. `lib/artifact_backends/gitbranch.sh` — the adapter

Mirror `dir.sh`'s shape: double-source guard, fail-closed accessor, blob path
helper, then the five contract ops. Every failure path needs its own `die` —
callers run inside `with_attach_lock`'s errexit-suppressed call tree
(`dir.sh:63-67` explains why).

- `_artifact_gitbranch_branch` — fail-closed accessor for
  `ARTIFACT_GITBRANCH_BRANCH`, mirroring `_artifact_dir_root` (`dir.sh:26-32`).
- `_artifact_gitbranch_has_remote` / `_artifact_gitbranch_fetch` — memoized
  (read paths) and forced (CAS paths) variants.
- `_artifact_gitbranch_tip` — per R1.
- `_artifact_gitbranch_probe` — the R2 classifier. **This is the single seam**
  the CAS loop, the R4 guard and `gitbranch-migrate` all branch on, so the
  unmarked-branch rule cannot be enforced in one place and forgotten in another.
- `artifact_gitbranch_head <hash>` — `git cat-file -e <tip>:blobs/<2>/<62>`.
- `artifact_gitbranch_get <hash> <dest>` — `git cat-file blob <tip>:<path>`;
  `-` streams to stdout, else redirect to the dest file.
- `artifact_gitbranch_put <hash> <file>` — idempotent (`head` → return 0);
  `git hash-object -w`; then the R1/R2 CAS loop with **every index operation
  under `GIT_INDEX_FILE=$(mktemp)`**; verify with `head` before returning.
- `artifact_gitbranch_delete <hash>` — same loop, `update-index --force-remove`.
- `artifact_gitbranch_list` — `git ls-tree -r --name-only <tip> blobs/` mapped to
  `sha256:<2><62>`.
- `artifact_gitbranch_store_id` — prints the marker's `store_id` (empty when the
  probe is not `STORE:`); consumed by the CLI guard and by migrate.

**`GIT_INDEX_FILE` isolation is mandatory** — this repo has concurrent writers
and touching the real index would corrupt another session's staged work. Always
`trap`-clean the temp index.

### 4. `lib/artifact_manifest.py` — `backends` subcommand

Print the distinct `backend` values across all manifests, one per line. Needed by
the R4 guard (to know whether any gitbranch artifact exists) and by migrate. Keep
the existing fail-closed malformed-manifest behavior.

### 5. `aitask_artifact.sh` — guard + migration verb

- `_artifact_assert_gitbranch_store` per R4, wired to all six call sites. It
  reads `artifacts/gitbranch_store.json` from the data worktree
  (`_ait_detect_data_worktree`), calls the adapter's probe, and applies the table.
  The adopt arm writes the record; the first-use arm leaves it to the write path.
- **`gitbranch-migrate --from <old> --to <new>`**, added to `main`'s dispatch
  (L672-685) and the help text. Target precondition, checked **before any
  mutation**, using the same probe:

  | Probe on `<new>` | Action |
  |---|---|
  | `ABSENT` | allow — creates the root carrying `<old>`'s `store_id` |
  | `STORE:<same id>` | allow — resume of an interrupted migration |
  | `STORE:<different id>` | **die** — would merge two independent stores |
  | `OCCUPIED` | **die** — the target is an ordinary branch |

  Both die-arms leave `<new>`'s tip byte-unchanged. Body: activate against
  `<old>`, enumerate every hash whose manifest records `backend: gitbranch`,
  `get` from `<old>` and `put` to `<new>` (idempotent, hash-verified, resumable —
  the same non-destructive shape as `_artifact_move_txn`), write the marker on
  `<new>` carrying the **same** `store_id`, update
  `artifacts/gitbranch_store.json`, commit. `<old>` is left untouched so a failed
  migration is recoverable by reverting the config. Run the whole body under
  `with_attach_lock`.

### 6. Tests — write them so they can fail first

Create `tests/test_artifact_gitbranch_backend.sh` and **run it before the adapter
exists, confirming it exits 1**. A passing test pins nothing until the suite's
exit path is proven to work.

## Reference files for patterns

- `lib/artifact_backends/dir.sh` — **the template.** Fail-closed accessor
  (L26-32), hash-verify-staged-bytes-before-install (L52-78), and the
  every-path-needs-its-own-`die` discipline (L63-67).
- `aitask_lock.sh:89-113` (`init_lock_branch`) — the canonical worktree-free
  orphan-branch recipe: `mktree` → `commit-tree` → plain
  `push <sha>:refs/heads/<branch>`. `lock_task()` L116+ for the
  fetch-probe-retry loop and the `die_code` tri-state on remote probing.
- `aitask_claim_id.sh:138-195` — second orphan-branch precedent, incl. the
  remote-first / local-fallback split at L193-195.
- `lib/artifact_registry.sh:38-64` — param clearing, the
  `^ARTIFACT_[A-Z0-9_]+$` env-name guard, the explicit `|| die` on the capture.
- `lib/task_utils.sh:26-42` — the memoization shape to copy for the read-only
  fetch memo (and to deliberately **not** copy in the CAS loop).
- `aidocs/framework/shell_conventions.md` — mandatory before editing any script.
- `aidocs/framework/sed_macos_issues.md` — if any in-place text editing is needed.

## Verification

`tests/test_artifact_gitbranch_backend.sh`, modeled on
`tests/test_artifact_dir_backend.sh` (same `write_config()` fixture idiom at
L28-31, legacy-mode repo so `task_git` is plain `git`), plus a **bare-remote +
two-clone** fixture cribbed from `tests/test_task_git.sh:26-40`:

1. round-trip put → head → get (file and `-`) → list; idempotent double-put adds
   no second commit
2. **first-write bootstrap** creates a parentless root commit carrying blob +
   marker; a second put extends it
3. **two concurrent first writers** (both from no branch) end with both blobs on
   one linear history — negative control for R2
4. **two-clone concurrent full `ait artifact create`** — exactly one
   `.ait-artifact-store` marker on the branch, and **both clones'
   `artifacts/gitbranch_store.json` converge on that one `store_id`** (R3).
   Negative control: the loser's record does **not** hold the id it minted
5. **two-clone publish test** — clone A creates an artifact; clone B (fetch only)
   resolves the handle **and gets its bytes**. Negative control: with the remote
   made unwritable, `ait artifact create` **fails** and publishes no manifest on
   `aitask-data`
6. **the user's index is untouched** across put/delete — stage an unrelated file
   first, assert `git diff --cached --name-only` is unchanged
7. **CAS on an existing branch** — advance the ref behind the adapter's back
   mid-loop, then assert both that the retry lands both blobs **and** that the
   retry's commit has the interloper's commit as its parent. A memo leaked into
   the CAS loop passes the "both blobs" half by accident, so **the parentage
   assertion is the real oracle**
8. reserved-branch and malformed ref names die naming the key; `validate-ref`
   agrees with activation (single-sourced rule)
9. unregistered / adapterless / missing-`branch` config dies (mirrors the dir tests)
10. cross-activation leakage — activating `local` or `dir` clears
    `ARTIFACT_GITBRANCH_BRANCH`
11. **guard matrix (R4)** — all six record×probe states, exercised through `get`
    and `rm` as well as `create`
12. **unmarked existing branch is rejected, not adopted** — point the config at
    an ordinary feature branch created in the fixture; assert **both**
    `ait artifact create` **and** `gitbranch-migrate --to <it>` die naming the
    branch, and `git rev-parse <branch>` is identical before and after. Negative
    control: the same branch **with** a valid marker at its tip **is** accepted,
    so the test discriminates marker validity rather than branch existence
13. **`gitbranch-migrate`** moves every blob, preserves `store_id`, leaves the old
    branch intact, is idempotent on re-run, and lifts the guard
14. **migrate target precondition (negative)** — a target carrying a *different*
    `store_id` dies before the first `put`; the error names both ids; the target
    tip is byte-unchanged
15. no-remote repo — local ref authoritative, no push attempted, round-trip works

Regression suites that must stay green (the "default config unchanged →
byte-identical behavior" AC):

```bash
bash tests/test_artifact_dir_backend.sh
bash tests/test_artifact_cli.sh
bash tests/test_artifact_share_resolution.sh
bash tests/test_attach_local_backend.sh
bash tests/test_artifact_manifest_lib.sh
```

Plus `shellcheck .aitask-scripts/lib/artifact_backends/gitbranch.sh` and `bash -n`
on every touched script.

## Out of scope

`ait attach` stays local-only (`aitask_attach.sh:225` rejects non-local backends;
`cmd_gc` L599 hard-codes `local`). Tracked by **t1258**. Offline writes are
tracked by **t1259**.

## Post-implementation

Per `task-workflow` Step 9 — merge approval, `ait gates run 1231_1`, archival.

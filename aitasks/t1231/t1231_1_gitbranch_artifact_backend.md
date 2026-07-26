---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-26 22:57
updated_at: 2026-07-26 22:57
---

Implement the **`gitbranch` artifact backend**: an adapter that stores artifact
blobs on a dedicated, configurable orphan branch (default `aitask-artifacts`)
using **git plumbing only — no worktree**, so blobs never materialize in any
checkout.

**Full design + rationale: `aiplans/archived/p1231_configurable_git_branch_artifact_backend.md`
(parent plan, §"Correctness model" R1–R4). Read it first — the four rules there
are load-bearing and each was added to close a specific reviewed defect.**

## Context

`ait artifact`'s zero-config `local` backend puts blobs in the `.aitask-data`
worktree and commits them via `task_git`, so every artifact lands on the
**aitask-data branch** alongside every task and plan file.
`aidocs/unified_artifact_design.md` §7 already names the consequence: `local`
"bloats that branch for large HTML". The only shipped alternative, `dir`, needs
an out-of-band mount replicated by every teammate. `gitbranch` is the option
that keeps blobs **in git** (travels with a clone, no mount, no credentials)
while keeping them **off the task-data branch**.

This is the first and riskiest of t1231's three children. No TUI, no website
docs — those are t1231_2 and t1231_3.

**Key enabling discovery:** `aitask_artifact.sh` guards blob-staging with
`[[ "$backend" == "local" ]]` at seven sites (L282, L308, L361, L366, L437,
L530, L553), and `artifact_cache.sh` at L51/L96. For a non-`local` backend they
already do the right thing — stage manifest + task file only, skip the blob.
**So no changes to the transaction / rollback / commit-path logic are needed.**
`gitbranch` slots in exactly where `dir` does. The only CLI-layer additions are
the store guard and the migration verb below.

## Config contract (PINNED)

```yaml
artifacts:
  default_backend: gitbranch
  backends:
    gitbranch:
      branch: aitask-artifacts
```

Single key. The remote is hard-coded `origin`, matching `aitask_lock.sh`.
On-branch layout: `blobs/<2hex>/<62hex>` plus a `.ait-artifact-store` marker at
the tree root.

## Correctness model — the four rules (each needs a named test)

### R1 — remote is the store of record; publish is push-gated

When a remote is configured the store tip is `refs/remotes/origin/<branch>`;
local `refs/heads/<branch>` is a mirror, never the authority.

**Fetch memoization is READ-ONLY.** A per-process memo (shape of
`_ait_detect_data_worktree`) serves `head`/`get`/`list`. It must **never** serve
a CAS iteration: every pass of the `put`/`delete` loop begins with an
unconditional `git fetch origin <branch>` that also invalidates the memo. A
lease rejection means the observed tip was stale by definition, so retrying
against a memoized tip rebuilds the same losing commit and livelocks until the
budget is exhausted.

`put` orders **push first, local ref second**:
1. build the new commit;
2. `git push --force-with-lease=refs/heads/<branch>:<observed-tip> origin <commit>:refs/heads/<branch>`;
3. only on success, `git update-ref refs/heads/<branch> <commit> <observed-tip>`.

A failed or lease-rejected push **does not return success** — lease rejection
re-enters the CAS loop; exhaustion or hard failure `die`s. Warn-and-continue is
unsound: the next step of the artifact transaction commits a manifest on
`aitask-data`, so a locally-only blob publishes a handle a second clone can
resolve but cannot `get`. (It also contradicts `artifact_store`'s own post-`put`
lost-put `head` check, `artifact_cache.sh:87-109`.)

Push succeeded + local `update-ref` failed ⇒ store still correct; a later fetch
repairs the mirror.

**No remote configured:** `refs/heads/<branch>` is authoritative, no push is
attempted. State this in the backend header.

### R2 — three-state probe; first write bootstraps a root commit

No separate init step. `_artifact_gitbranch_probe` classifies the branch and is
**re-evaluated on every CAS iteration** (a branch can appear mid-loop):

| State | Meaning | Action |
|---|---|---|
| `ABSENT` | ref exists neither on `origin` (when configured) nor locally | may be initialized |
| `STORE:<store_id>` | ref exists, tip carries a valid `.ait-artifact-store` | normal CAS append (subject to R4) |
| `OCCUPIED` | ref exists, tip has **no valid marker** | **fail closed, always** |

- `ABSENT` → `mktree` a tree with the blob **and** the marker, `commit-tree`
  **with no `-p`**, **plain (non-force) push** `origin <commit>:refs/heads/<branch>`,
  `git update-ref refs/heads/<branch> <commit> ""` (empty old-value = must not exist).
- `STORE:<id>` → `read-tree <tip>` / `commit-tree -p <tip>` / lease push.
- `OCCUPIED` → die without mutating anything.

**Ref absence != marker absence.** The reserved-name validator blocks only five
names, so any ordinary feature/release branch is a legal config value. Treating
an existing unmarked ref as "not initialized yet" would append artifact blob
commits onto a live branch. Only a nonexistent ref may be initialized:

> `artifacts.backends.gitbranch.branch is 'X', but branch 'X' already exists and
> is not an aitask artifact store (no .ait-artifact-store marker at its tip).
> Refusing to write artifact commits onto an existing branch — pick an unused
> branch name.`

Two concurrent first writers cannot create incompatible roots: the loser's plain
push is rejected as non-fast-forward, it re-enters the loop, observes the
winner's tip and rebuilds on top. Same recipe as `aitask_lock.sh:102-113`
(`mktree` → `commit-tree` → plain `push <sha>:refs/heads/<branch>`), plus retry.

### R3 — store identity (project-level, not per-manifest)

The registry model is **one instance per adapter**
(`unified_artifact_design.md` §6), so identity is project-level:

- **On the artifact branch:** `.ait-artifact-store`, committed with the root
  commit — `store_id: <32 hex>`, `branch: <name at init>`, `created_at:`.
- **On the data branch:** `artifacts/gitbranch_store.json` —
  `{"store_id": "...", "branch": "..."}`, committed inside the same path-scoped
  transaction as the first artifact's manifest.

`store_id` is generated once and **survives migration** — that is what makes the
identity stable while the branch coordinate moves.

**The minted id is PROVISIONAL until the root push wins.** The guard's
absent/ABSENT arm is not serialized across clones: two clones each running a
first `ait artifact create` both pass it and each mints a candidate id into its
own root commit. One root push wins. The loser must:
1. after the CAS loop settles, **re-read `.ait-artifact-store` from the winning
   tip** and use *that* `store_id` for `artifacts/gitbranch_store.json`;
2. when rebuilding on an existing tip, **never overwrite an existing marker** —
   the rebuild adds only the blob.

Otherwise the two clones' records diverge permanently and R4 starts failing on
the loser for a store it can actually read.

### R4 — the guard runs on EVERY gitbranch-touching operation

`_artifact_assert_gitbranch_store` in `aitask_artifact.sh`, called immediately
after `artifact_registry_activate` in **create, update, get, rm, list, and both
the source and target legs of move** — not just the write paths. Input is the R2
probe, not marker presence:

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
branch. Do not offer it as the remedy.

## Key files to modify

- **NEW** `.aitask-scripts/lib/artifact_backends/gitbranch.sh` — the adapter.
  Mirror `dir.sh`'s shape (fail-closed accessor → blob path → head/put/get/delete/list).
  Ops:
  - `_artifact_gitbranch_probe` — the R2 classifier; the **single seam** the CAS
    loop, the R4 guard and `gitbranch-migrate` all branch on, so the
    unmarked-branch rule cannot be enforced in one place and forgotten elsewhere.
  - `head <hash>` — `git cat-file -e <tip>:blobs/<2>/<62>`
  - `get <hash> <dest>` — `git cat-file blob <tip>:<path>`; `-` streams to stdout
  - `put <hash> <file>` — idempotent (`head` → return 0); `git hash-object -w`;
    then the R1/R2 CAS loop with **every index op under `GIT_INDEX_FILE=$(mktemp)`**;
    verify with `head` before returning
  - `delete <hash>` — same loop with `update-index --force-remove`
  - `list` — `git ls-tree -r --name-only <tip> blobs/` → `sha256:<2><62>`
- `.aitask-scripts/lib/artifact_backend.sh` — the `source` marker (L36), the
  `case` arm (L46), **and** the `known:` list in the `*)` die at L47.
- `.aitask-scripts/lib/artifact_registry.py`:
  - L44 `KNOWN_ADAPTERS["gitbranch"] = {"branch": ("ARTIFACT_GITBRANCH_BRANCH", "ref_name")}`
  - a `ref_name` arm in `validate_value` (L97): git ref-name shape, plus a
    reserved-name rejection for `main`, `master`, `aitask-data`, `aitask-locks`,
    `aitask-ids` (same set as `aitask_web_merge.sh:222`). Pointing the blob store
    at `main` must be **impossible**, not discouraged.
  - update the validator list in the `# BACKEND-EXTENSION-POINT (registry)` comment.
  - **NEW `adapters` subcommand** — prints `local` + `sorted(KNOWN_ADAPTERS)`:
    the *available* adapters independent of config. `cmd_list` (L149-154) prints
    only *registered* backends, so on a fresh project `gitbranch` is unlistable
    and could never be selected to create its own first configuration. t1231_2's
    selector needs this; leave `list` as-is for "what is configured".
  - **NEW `validate-ref <name>` subcommand** — exit 0/1 + message, so the
    settings TUI (t1231_2) validates a branch name *before* the backend is
    registered, without re-encoding the regex or reserved list in UI code.
- `.aitask-scripts/lib/artifact_registry.sh` L33 —
  `_AIT_ARTIFACT_REGISTRY_PARAM_VARS+=( ARTIFACT_GITBRANCH_BRANCH )`. Required so
  `move` (which activates source then target in one process) does not leak params.
- `.aitask-scripts/aitask_artifact.sh`:
  - `_artifact_assert_gitbranch_store` per R4, wired into create/update/get/rm/list/move.
  - **NEW `gitbranch-migrate --from <old> --to <new>` verb**, added to `main`'s
    dispatch (L672-685) and the help text. Target precondition, checked **before
    any mutation**, using the same probe: `ABSENT` → allow (creates the root
    carrying `<old>`'s `store_id`); `STORE:<same id>` → allow (resume);
    `STORE:<different id>` → die (merging two independent stores); `OCCUPIED` →
    die. Both die-arms leave `<new>`'s tip byte-unchanged. Body: activate against
    `<old>`, enumerate every hash whose manifest records `backend: gitbranch`,
    `get` from `<old>` and `put` to `<new>` (idempotent, hash-verified,
    resumable — same non-destructive shape as `_artifact_move_txn`), write the
    marker on `<new>` carrying the **same** `store_id`, update
    `artifacts/gitbranch_store.json`, commit. `<old>` untouched.
- `.aitask-scripts/lib/artifact_manifest.py` — **NEW `backends` subcommand**
  (distinct `backend` values across manifests); needed by the guard and migrate.

## Reference files for patterns

- `.aitask-scripts/lib/artifact_backends/dir.sh` — **the template.** Fail-closed
  root accessor (L26-32), hash-verify-staged-bytes-before-install (L52-78), and
  the "every failure path needs its own `die` because callers run under
  suppressed errexit" discipline (comment L63-67).
- `.aitask-scripts/aitask_lock.sh:89-113` (`init_lock_branch`) — the canonical
  worktree-free orphan-branch recipe: `mktree` → `commit-tree` → plain
  `push <sha>:refs/heads/<branch>`. Also `lock_task()` L116+ for the
  fetch-probe-retry loop shape and the `die_code` tri-state on remote probing.
- `.aitask-scripts/aitask_claim_id.sh:138-195` — second orphan-branch precedent,
  including the remote-first / local-fallback split (L193-195).
- `.aitask-scripts/lib/artifact_registry.sh:38-64` (`artifact_registry_activate`)
  — param clearing, the `^ARTIFACT_[A-Z0-9_]+$` env-name guard, the explicit
  `|| die` on the Python capture.
- `.aitask-scripts/lib/task_utils.sh:26-42` — the memoization shape to copy for
  the read-only fetch memo (and to deliberately NOT copy in the CAS loop).
- `aidocs/framework/shell_conventions.md` — mandatory before editing any script.

## Implementation plan

1. `artifact_registry.py`: `ref_name` validator + reserved list, `KNOWN_ADAPTERS`
   entry, `adapters` and `validate-ref` subcommands. Unit-test the validator
   first — it is the cheapest independent piece.
2. `artifact_registry.sh`: param var. `artifact_backend.sh`: source + case +
   `known:` list.
3. `gitbranch.sh`: probe → head/get/list (read side, memoized fetch) →
   put/delete (CAS loop, forced fetch, `GIT_INDEX_FILE` isolation).
4. `artifact_manifest.py backends`; `_artifact_assert_gitbranch_store` in
   `aitask_artifact.sh` wired to all six call sites.
5. `gitbranch-migrate` verb.
6. Tests (below). Run the new test file BEFORE the adapter exists and confirm it
   exits 1 — a passing test pins nothing until the suite's exit path works.

## Verification steps

New `tests/test_artifact_gitbranch_backend.sh`, modeled on
`tests/test_artifact_dir_backend.sh` (same `write_config()` fixture idiom at
L28-31, legacy-mode repo so `task_git` is plain `git`), plus a **bare-remote +
two-clone** fixture cribbed from `tests/test_task_git.sh:26-40`:

- round-trip put → head → get (file and `-`) → list; idempotent double-put adds
  no second commit
- **first-write bootstrap** creates a parentless root commit carrying blob +
  marker; a second put extends it
- **two concurrent first writers** (both from no branch) end with both blobs on
  one linear history — negative control for R2
- **two-clone concurrent full `ait artifact create`**: exactly one
  `.ait-artifact-store` marker on the branch, and **both clones'
  `artifacts/gitbranch_store.json` converge on that one `store_id`** (R3).
  Negative control: the loser's record does NOT hold the id it originally minted
- **two-clone publish test:** clone A creates an artifact; clone B (fetch only)
  resolves the handle **and gets its bytes** — the guarantee R1 exists for.
  Negative control: with the remote unwritable, `ait artifact create` **fails**
  and publishes no manifest on `aitask-data`
- **user's index untouched** across put/delete: stage an unrelated file first,
  assert `git diff --cached --name-only` is unchanged
- **CAS on an existing branch:** advance the ref behind the adapter's back
  mid-loop, then assert both that the retry lands both blobs **and** that the
  retry's commit has the interloper's commit as its parent — proving the forced
  refresh observed the new tip. A leaked memo passes the "both blobs" half by
  accident, so **the parentage assertion is the real oracle**
- reserved-branch and malformed ref names die naming the key; `validate-ref`
  agrees with activation (single-sourced rule)
- unregistered / adapterless / missing-`branch` config dies (mirror the dir tests)
- cross-activation leakage: activating `local` or `dir` clears `ARTIFACT_GITBRANCH_BRANCH`
- **guard matrix (R4)** — all six record×probe states, exercised through `get`
  and `rm` as well as `create`
- **unmarked existing branch is rejected, not adopted** — point the config at an
  ordinary feature branch created in the fixture; assert **both**
  `ait artifact create` **and** `gitbranch-migrate --to <it>` die naming the
  branch, and `git rev-parse <branch>` is identical before and after. Negative
  control: the same branch **with** a valid marker at its tip IS accepted, so the
  test discriminates marker validity rather than branch existence
- **`gitbranch-migrate`** moves every blob, preserves `store_id`, leaves the old
  branch intact, is idempotent on re-run, and lifts the guard
- **migrate target precondition (negative)** — a target carrying a *different*
  `store_id` dies before the first `put`; error names both ids; target tip
  byte-unchanged
- no-remote repo: local ref authoritative, no push attempted, round-trip works

Also: existing suites must stay green (the "default config unchanged →
byte-identical behavior" AC) —
`bash tests/test_artifact_dir_backend.sh`, `bash tests/test_artifact_cli.sh`,
`bash tests/test_artifact_share_resolution.sh`,
`bash tests/test_attach_local_backend.sh`.
Plus `shellcheck .aitask-scripts/lib/artifact_backends/gitbranch.sh` and
`bash -n` on every touched script.

## Out of scope

`ait attach` stays local-only (`aitask_attach.sh:225` rejects non-local backends;
`cmd_gc` L599 hard-codes local). Extending attachments is tracked separately.

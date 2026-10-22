---
Task: t2099_artifact_fetch_exclusion.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2099 — Routine-fetch exclusion for the gitbranch artifact store

## Context

t1890 decided (D1(a), `aidocs/artifact_storage_lifecycle.md` §3) that routine
fetches must never download the `gitbranch` store branch. Today they do:
- `ait sync` runs `git fetch origin` in the `.aitask-data` worktree
  (`aitask_sync.sh:1945`, `:2283`). That worktree is linked, so it shares
  `.git/config`.
- web-merge runs `git fetch --all --prune` (`aitask_web_merge.sh:240`).

Both follow the default `+refs/heads/*` mapping and pull the whole store history.
The t1890 probe showed that a negative refspec `^refs/heads/<store>` on each
remote fixes this. The gitbranch backend's explicit-refspec fetch
(`lib/artifact_backends/gitbranch.sh:126-136`) keeps working.

Decisions taken during planning (user):
- **Every named remote** gets shared mode, not only `origin`.
- **Rename.** A branch retired by `gitbranch-migrate` stays excluded, because it
  remains on the remote as the readable predecessor. The new branch is excluded
  too. A *stale-config correction* (the config changed with no migration)
  releases the old entry. A cleanup is provided for t2104 to call after
  `--delete-retired`.
- Review findings addressed:
  - (1) Retirement must be visible to **other clones and fresh clones** without
    downloading store history, so it moves into the shared store record.
  - (2) Dedicated mode must be **reversible**, or refuse with recovery
    instructions.
  - (3) **Pre-fetch only**: `ait sync` guards both broad fetches (the initial
    fetch and the push-retry fetch) and keeps fingerprint reconciliation. A test
    proves that the first sync after a *published* migration record fetches no
    new store objects. The window before publication is documented, and
    publication-order changes stay out of this task.
  - (4) The guard **fails closed**: when protection is unknown, the broad fetch
    does not run, and the sync defers and retries later.
  - (5) A **post-convergence reconciliation**, with no network, runs after every
    convergence route, so releases and dedicated-mode reversals that arrive from
    another clone settle within the same sync.
  - (6) Dedicated-mode transitions use a **write-ahead state key**. The backup is
    taken once and never overwritten, so an interrupted Enter or Leave resumes
    on the next run.
  - (7) Every apply runs under **one repository-wide lock** in the git common
    dir. Its state is read only after the lock is acquired, and nested acquires
    are ruled out.

## Design

### Shared retirement record (finding 1)

`artifacts/gitbranch_store.json` is on the data branch, so every clone has it
after `ait setup` / `ait sync`. It gains an optional `retired` list:

```json
{"store_id": "<32hex>", "branch": "B", "retired": ["A"]}
```

- **Written by `gitbranch-migrate` step 8**
  (`aitask_artifact.sh` `_artifact_gitbranch_migrate_txn`):
  - the new record is `branch: <to>`, `retired: sorted(old retired ∪ {<from>} − {<to>})`;
  - the rewrite condition is extended to "`from` not yet in `retired`". Re-running
    `gitbranch-migrate --from A --to B` therefore **backfills** a migration made
    before this change; it is idempotent otherwise.
  - The JSON is written through Python `json.dumps`. It is no longer a printf
    template, now that it holds a list.
- **Validated fail-closed by the reader.** `_artifact_gitbranch_record_read`'s
  inline Python also checks `retired`: when present it must be a list of strings,
  each passing `artifact_registry.check_ref_name` (imported via `sys.path` to
  `lib/`). A malformed list dies like a malformed record does. The output stays
  `<id>\t<branch>`, so existing `${rec#*$'\t'}` callers are unaffected.
- **A new reader** `_artifact_gitbranch_record_retired` prints one retired
  branch per line.
- **`_artifact_gitbranch_record_sync`** (first-write record) is unchanged: it
  writes only when no record exists.
- **Release for t2104**: `ait artifact fetch-exclusion drop-retired <b>`. Under
  `with_attach_lock` and the txn helpers (`txn_require_clean` and a snapshot of
  the record), it:
  - removes `<b>` from `retired`, commits with `_artifact_commit`, then runs apply;
  - refuses when `<b>` is the record branch or the configured branch;
  - is a no-op (still running apply) when `<b>` is not listed.

  Other clones release `<b>` on their next apply (see the sync hook below).

### Desired set and ownership (per remote, git config)

**Desired D** = {configured `artifacts.backends.gitbranch.branch`} ∪ {record
`branch`} ∪ {record `retired`}. The record-branch term keeps the real store
excluded when the config was changed without migrating. D derives entirely from
shared data, so every clone computes the same D.

Ownership is recorded in custom keys inside the remote section
(`git remote rename`/`remove` carry or drop them; git ignores unknown keys):
- `remote.<r>.aitaskExclude`: multi-valued, the branch names whose
  `^refs/heads/<b>` **we added**.
- The dedicated-mode keys are listed below.

Shared-mode rules:
- Add `^refs/heads/<b>` for each `b ∈ D` only when the value is **absent** from
  `remote.<r>.fetch`, and record ownership only then. An identical entry the
  user added is never claimed and never removed.
- **Release**: owned names not in D. Remove the exact value together with its
  ownership value. This covers both stale-config correction and a `drop-retired`
  made in another clone.
- Never touch any other `fetch` value. Use `git config --add` and an
  exact-value unset only.
- Exact-value removal:
  1. count the exact matches;
  2. `--unset-all` with an anchored, escaped regex
     (`^\^refs/heads/<b with . escaped>$`; branch charset `[A-Za-z0-9._/-]` is
     guaranteed by `check_ref_name`);
  3. re-add `count-1` copies, so a user duplicate survives.

  `--fixed-value` needs git 2.30, so it is not used.

### Dedicated mode, reversible (finding 2)

This applies only to the remote named by `artifacts.backends.gitbranch.remote`
when `remote_dedicated: true` and that name is a registered `git remote`. It is
never applied to `origin`: that declaration warns and falls back to shared mode.

Each `git config` write is atomic on its own (lockfile + rename), but a
transition takes several writes. A **write-ahead state key**
`remote.<r>.aitaskDedicatedState` (`saved` | `active` | `restoring`) makes every
partial transition resumable. **The backup is written exactly once and is never
re-taken while live settings may already be modified.**

- Backup keys:
  - `remote.<r>.aitaskSavedFetch`: multi-valued, in the original order.
  - `remote.<r>.aitaskSavedSkipFetchAll`: `unset` / `true` / `false`. It
    doubles as the **sentinel**, under the invariant **"sentinel present ⇔ the
    backup is complete and authoritative"**:
    - when saving, it is written **last**, after every `aitaskSavedFetch` value;
    - when clearing, it is deleted **first**, right after the live restore has
      fully succeeded and before any `aitaskSavedFetch` value is deleted.

    A partial backup is therefore never mistaken for a complete one in either
    direction.
- **Enter** (the declared remote, state absent):
  1. Any leftover backup keys can only come from an interrupted save. Live
     settings are never touched before `state=saved`, so they are still
     original. Delete the leftovers and save again from live.
  2. Write `aitaskSavedFetch` values, then the sentinel, then `state=saved`.
  3. `state=saved` means **live may be partially replaced, and the backup is
     authoritative**. Idempotently set `skipFetchAll true` and replace `fetch`
     with exactly `{^refs/heads/<b> : b ∈ D}`.
  4. Write `state=active`.

  A re-run in `saved` resumes at step 3 and never re-saves.
- **Stay** (`active`): when D changed, rewrite the negative-only set. A no-op
  otherwise.
- **Leave**: `remote_dedicated` turned false, the declared remote changed, or
  the keys were removed. The trigger is any remote with a state key that is not
  the current declared one.
  - From `active`: run the **drift check** first. Restore only when the live
    `fetch` set is negative-only, every value is `^refs/heads/<b>` for an owned
    or D name, and `skipFetchAll` is `true`. Otherwise refuse, as described
    below.
  - From `saved`: an Enter was interrupted, live is partial by definition, and
    the backup is authoritative. Skip the drift check.
  - Then, in this order:
    1. write `state=restoring`;
    2. restore the live `fetch` values from the backup, in order, and
       `skipFetchAll` to its saved state;
    3. **delete the sentinel**, which marks the restore complete;
    4. delete the `aitaskSavedFetch` values;
    5. delete the state key.

    Finally continue with shared mode, which re-adds the negatives.
  - A re-run in `restoring`:
    - with the sentinel present → the backup is still complete, so redo
      steps 2–5 from it (idempotent: an unset-all followed by re-adding the
      saved values);
    - with the sentinel absent → the live restore had already completed, so
      only steps 4–5 run. **Live `fetch` is never touched.**
- **Refusals (fail closed, change nothing on that remote, exit 1 after the
  other remotes are handled):**
  - Drift: `FETCH_EXCLUSION:DEDICATED_DRIFT:<r>`. The warning carries the exact
    recovery commands: `git config --unset-all remote.<r>.fetch`, one
    `git config --add …` per saved value, the `skipFetchAll` restore, and the
    `aitask*` key cleanup.
  - Inconsistent state, i.e. an unknown state value, or `saved`/`active`
    without the sentinel: `FETCH_EXCLUSION:DEDICATED_STATE_INVALID:<r>`, with
    the same style of recovery instructions.
- **Reassignment** (remote X → Y): X leaves (restore), and Y enters.
- **gitbranch unregistered** (`NOT_CONFIGURED`): nothing changes anywhere. The
  store still exists, and the docs say so.

### Serialization (one lock over every read-modify-write)

- **Lock:** `"$(git rev-parse --git-common-dir)/ait-fetch-exclusion.lock"`. It is
  taken through `registry_lock_acquire` / `registry_lock_release`
  (`lib/registry_lock.sh`, the stale_lock protocol), with a 10s timeout.
  - The git common dir is shared by the main checkout, the `.aitask-data` linked
    worktree and task worktrees, so every entry point contends on one lock.
- **Scope:** the whole `afx_apply` (shared mode, Enter, Stay and Leave for every
  remote) runs inside it, and so does the reconciliation's fingerprint
  compare → apply → recompute → store.
  - Transition state, ownership keys and the stored fingerprint are read **only
    after** the lock is acquired. A path chosen before acquiring is never acted
    on.
  - A busy lock makes apply exit 1 (`FETCH_EXCLUSION:BUSY`). The sync guard
    treats that as protection unknown and defers, so it fails closed.
- **No nested acquire** (`registry_lock` tracks one active lock per process):
  - Every apply runs in a process that holds no other registry lock. The
    in-process callers, `cmd_gitbranch_migrate` and `drop-retired`, call apply
    only **after** `with_attach_lock` has returned. `cmd_init_store` takes no
    attach lock.
  - Setup, init_data, settings and sync invoke `aitask_artifact.sh` as a child
    process, and the afx lock never waits on a lock its caller holds.
  - The lib asserts this: when this process already holds a registry lock, apply
    dies with a programming-error message instead of attempting the acquire.
- **Fingerprint fast path:** the sync guard compares the fingerprint
  (`afx_fingerprint`, which lives in the lib so both sides compute it the same
  way) **without** the lock. A match means those exact inputs were already
  applied, so skipping is safe. A mismatch calls
  `fetch-exclusion apply --if-changed --also-ref <ref>`, which re-checks the
  fingerprint and stores it inside the lock.

### Old git

Parse `git --version` into integer major.minor, without `sort -V`. Below 2.29:
- one `warn` per invocation, plus `FETCH_EXCLUSION:UNSUPPORTED_GIT:<ver>`;
- nothing is changed, and the exit status is 0.

### Output contract (stdout, one token per line)

- **Early-exit tokens**: `FETCH_EXCLUSION:NOT_CONFIGURED`,
  `FETCH_EXCLUSION:UNSUPPORTED_GIT:<ver>`, `FETCH_EXCLUSION:NO_REMOTES`.
- **Per-remote tokens**: `EXCLUDED:<r>:<b>`, `RELEASED:<r>:<b>`,
  `DEDICATED:<r>`, `RESTORED:<r>`, `FETCH_EXCLUSION:DEDICATED_DRIFT:<r>`,
  `FETCH_EXCLUSION:DEDICATED_STATE_INVALID:<r>`, `FETCH_EXCLUSION:BUSY`.
- **Final token**: `FETCH_EXCLUSION:CHANGED` or `FETCH_EXCLUSION:UNCHANGED`.
- **Exit status**: 1 on drift, on an invalid dedicated state, on a busy lock, or
  on a failed git config write; 0 otherwise.

## Implementation steps

1. **`.aitask-scripts/lib/artifact_fetch_exclusion.sh`** (new sourced lib, with
   a load guard, `die`/`warn` from terminal_compat). It holds the git-config
   mechanics only and takes every input as an argument:
   - `afx_git_supports_negative_refspec`;
   - `afx_apply <declared-remote|""> <dedicated 0|1> <branch>...`, where the
     branches are D;
   - internal helpers `_afx_has_value`, `_afx_unset_exact`, `_afx_enter_dedicated`,
     `_afx_leave_dedicated`, and `_afx_shared <r> <D...>`.
2. **`lib/artifact_registry.py`**: a read-only verb `gitbranch-fetch-config`.
   - It prints nothing when gitbranch is not registered. Otherwise it prints
     `branch<TAB>remote<TAB>0|1`.
   - The branch goes through `check_ref_name`. `remote` defaults to `origin` and
     must be a non-empty string. `remote_dedicated` defaults to false and must be
     a bool.
   - The keys are read, not added to `KNOWN_ADAPTERS`; t2100 owns their
     registration and validation.
   - Update the docstring and the usage text.
3. **`aitask_artifact.sh`**:
   - The record changes above: the reader validation, `_artifact_gitbranch_record_retired`,
     and migrate step 8 maintaining `retired`, with the extended condition.
   - A new verb `fetch-exclusion apply | drop-retired <b>`.
     `_artifact_fetch_exclusion_apply`:
     1. reads the registry verb, printing `NOT_CONFIGURED` when its output is
        empty;
     2. builds D from the config branch, the record branch and the record
        retired list;
     3. sources the lib and runs `afx_apply`.
   - Best-effort call sites (a failure becomes `warn … re-run: ait artifact
     fetch-exclusion apply`, and the verb result is kept): `cmd_init_store` for
     gitbranch, and `cmd_gitbranch_migrate` after the transaction (both
     `MIGRATED` and `ALREADY_MIGRATED`).
   - Add `show_help` entries and `main` dispatch.
4. **`aitask_setup.sh`**: a new step `setup_artifact_fetch_exclusion`.
   - It runs `(cd "$project_dir" && "$SCRIPT_DIR/aitask_artifact.sh" fetch-exclusion apply)`.
     `NOT_CONFIGURED` is silent, other outputs are summarised with `info`, and
     any failure becomes `warn` and never aborts setup.
   - It goes in `main()` immediately after `setup_python_venv`, because the
     registry needs PyYAML.
5. **`aitask_init_data.sh`**: on the `INITIALIZED` path, after
   `ait_ensure_data_symlinks`, run
   `"$SCRIPT_DIR/aitask_artifact.sh" fetch-exclusion apply >&2 || warn … >&2`.
   stdout stays reserved for init_data's tokens.
6. **`aitask_sync.sh`: a pre-fetch guard** (user decision: "pre-fetch only").
   The broad fetch commands stay as they are, and no refspec filtering is added.
   The guard only applies config before each broad fetch runs.
   - **Call sites.** A new `_sync_fetch_exclusion_guard` runs immediately before
     **both** broad fetches: in `do_fetch` before `fetch origin` (`:1945`), and in
     `do_push`'s rejected-push path before the retry refetch (`:2283`). Every
     convergence route therefore runs after a guard: the early guarded merge
     (`:2431`), Step 7's pull, and the retry's guarded merge (`:2313`) or
     `do_pull_rebase` (`:2329`).
   - **Narrow fetch.** `<db>` is the data worktree's `symbolic-ref --short HEAD`;
     in legacy mode that is the code branch. Run
     `_git_with_timeout "${AIT_RECONCILE_GIT_OPTS[@]}" fetch origin "+refs/heads/<db>:refs/remotes/origin/<db>"`.
     - rc 124 → the same `NO_NETWORK` handling as the fetch it precedes. The
       run stops, and an offline run waits out only one timeout.
     - any other failure → `git ls-remote --exit-code origin refs/heads/<db>`
       decides. Exit 2 (definitively absent) means there is no remote data
       branch and therefore no remote record, an expected no-op that uses the
       local inputs. Anything else leaves **protection unknown** (see the
       failure policy below).
   - **Fingerprint** (`git hash-object --stdin`) over:
     - the working-tree contents of `aitasks/metadata/project_config.yaml` and
       `artifacts/gitbranch_store.json` in the data worktree;
     - the blob ids of the same two paths at `refs/remotes/origin/<db>`;
     - `git remote` and `git config --get-regexp '^remote\.'`, so a hand-deleted
       exclusion is repaired;
     - `git --version`.
   - **Reconciliation.** When the fingerprint differs from
     `aitask.fetchExclusionFingerprint` (the lock-free fast path), run
     `aitask_artifact.sh fetch-exclusion apply --if-changed --also-ref refs/remotes/origin/<db> >/dev/null`.
     - Under the lock, it re-checks the fingerprint, applies, recomputes and
       stores it.
     - An unchanged fingerprint skips the CLI and Python.
     - Guard diagnostics go to stderr.
   - **Failure policy: fail closed before the broad fetch.**
     - **Protection known.** The run proceeds when the fingerprint is unchanged,
       or apply exits 0 with `CHANGED` / `UNCHANGED` / `NOT_CONFIGURED` /
       `NO_REMOTES` / `UNSUPPORTED_GIT`. Old git can never be protected and has
       already been warned about, so it must not block forever.
     - **Protection unknown.** The causes are:
       - a narrow-fetch failure that is neither a timeout nor a definitive
         absence;
       - apply exiting non-zero (a config-write failure such as `config.lock`,
         `DEDICATED_DRIFT`, or a record or config read error).

       In these cases **no broad fetch runs** and no fingerprint is stored.
       - In `do_fetch`, `batch_out "DEFERRED:fetch_exclusion:<reason>"`, then
         `iwarn` with the recovery step (`ait artifact fetch-exclusion apply`,
         plus the drift commands it printed), then `exit 0`, like the other
         deferrals.
       - In `do_push`'s retry path, emit the same token, then
         `_gm_note_unpublished; return 2`. That is the existing "deferred, not
         failed" route.
       - The next sync retries automatically.

       This trades sync availability for the agreed download protection.
       Existing consumers already treat `DEFERRED:*` as a deferral; the code
       consumers of the token are checked during implementation.
   - **Post-convergence reconciliation** (no network). The fetch-time union keeps
     a retired name that the incoming record dropped, and a dedicated declaration
     that the incoming config disabled. Both are the safe direction, and both are
     settled within the same sync:
     - `_sync_reconcile_after_converge` runs the same fingerprint check and the
       same apply (`--also-ref` against the already-fetched local ref, so no new
       fetch and the same fingerprint inputs);
     - it is called immediately after **every** successful convergence: after
       main's early guarded merge and Step 7 pull (one call before Step 8), and
       in `do_push` after the retry's guarded merge or `do_pull_rebase` succeeds,
       before the retry push. It therefore runs whatever the push outcome is;
     - its failure is `iwarn` only, because the fetch already happened and
       nothing remains to protect. No fingerprint is stored, so the next sync's
       guard retries, fail-closed.
   - **`--also-ref <ref>`.** `fetch-exclusion apply` also reads the config and
     the record from `<ref>:aitasks/metadata/project_config.yaml` and
     `<ref>:artifacts/gitbranch_store.json`, through a temporary file and the same
     registry and record readers, which are refactored to take a path. D becomes
     the **union** of the local and ref inputs. The dedicated-mode declaration is
     read from local config only.
   - **Remaining window** (documented, not closed; the user kept publication
     order out of scope): `gitbranch-migrate` pushes the new branch (step 4)
     before its record reaches the remote, which happens only at the migrating
     clone's next sync. A store's first creation has the same window. During it,
     other clones' syncs download the new branch once. After the record is
     published, every other clone's first sync fetches no store objects.
   - web-merge needs no change.
7. **Settings TUI** (`.aitask-scripts/settings/settings_app.py`):
   - Add `ARTIFACT_CLI = _SETTINGS_DIR.parent / "aitask_artifact.sh"` and a seam
     `_run_fetch_exclusion()`, the same shape as `_run_artifact_registry`,
     timeout 30.
   - In `save_artifacts_settings`, after a successful save and when the saved
     data has a gitbranch branch, call the seam:
     - non-zero (including drift) → a warning notify with escaped stderr;
     - `CHANGED` → an info notify.
   - The existing rename warning is kept.
8. **Docs**
   - `website/content/docs/commands/artifact.md`, "The gitbranch backend", rewrite
     "What gets downloaded":
     - `ait setup`, the Artifacts tab, `init-store gitbranch` and
       `gitbranch-migrate` add `^refs/heads/<store>` to every named remote, so
       `ait sync`, `git fetch` and `fetch --all --prune` skip it. A plain
       `git clone` still downloads it once.
     - Retired predecessors stay excluded, read from the store record.
     - `ait sync` fetches the data branch first and applies the exclusion
       before its broad fetch. Document the remaining window before a
       migration or creation record is published.
     - Old clones: drop the stale ref with `git update-ref -d
       refs/remotes/<remote>/<store>`.
     - Re-run `ait artifact fetch-exclusion apply` after adding a remote.
       Migrations made before this change are backfilled by re-running
       `gitbranch-migrate --from <old> --to <new>`.
     - Dedicated-mode reversal and the drift recovery.
     - Git ≥ 2.29 is required.
     - Add the `fetch-exclusion` verb to the verb list.
   - `website/content/docs/concepts/git-branching-model.md`: the
     `aitask-artifacts` row says routine fetches skip it.
   - `aidocs/artifact_storage_lifecycle.md`: the §3 `ait sync` cell becomes the
     current behaviour. §8 "Old clones resynchronize" mentions the record's
     `retired` list.
   - Run `cd website && python3 check_links.py --build`.

## Verification

**New `tests/test_artifact_fetch_exclusion.sh`.**
- It is self-contained, uses `asserts.sh` and `sync_isolate_git_config`, and
  opts into the file-backed counters for subshell bodies.
- Remotes are always reached through `file://` URLs. A fixture built by a
  plain-path clone has its origin `set-url` to `file://`.

Scenarios:
1. **Shared-mode mechanics.** Positive mappings are byte-identical before and
   after. A re-run prints `UNCHANGED` and leaves `.git/config` byte-identical. A
   pre-existing user negative entry is never claimed and survives a release.
2. **Fresh `--single-branch` clone + setup + sync** (branch mode, sync fixture,
   and the setup step via `aitask_setup.sh --source-only`). Advance the store,
   then run `aitask_sync.sh --batch`. There is no `refs/remotes/origin/<store>`,
   the store tip object is absent, and `count-objects -v` is unchanged.
3. **Full clone.** After apply and a store advance, `git fetch origin` and
   `fetch --all --prune` bring no ref and no objects. `ait artifact get` of a
   version created by a second clone still works.
4. **Old clone holding the store ref.** After apply, fetch and sync do not
   advance it, and the new tip object is absent.
5. **Mixed named remote `upstream`** (`main` + store). After `fetch --all --prune`,
   `upstream/main` has advanced and there is no store ref and no store objects.
6. **Cross-clone migration (finding 1).**
   - Clone X creates an artifact on A, runs `gitbranch-migrate --from A --to B`
     (the record gains `retired: [A]`), sets the config to B, and **syncs**, which
     publishes the record.
   - **Y's first sync after that** (Y's config still says A): no
     `refs/remotes/origin/B`, B's tip commit object is absent, and A and B are
     excluded afterwards. After both branches advance, a second sync and
     `fetch --all --prune` bring no ref or objects of either.
   - A fresh `--single-branch` clone Z with the setup step excludes A and B.
     Its sync downloads neither.
   - Backfill: a record without `retired`, plus a re-run of migrate, adds A.
   - A malformed `retired` value (not a list, or a bad ref) makes the record
     reader die.
6b. **Sync guard coverage.**
   - **Push retry**: Y has a local commit. The existing `pre_push` sync test seam
     makes X publish a migration record after Y's first fetch, so Y's push is
     rejected. The retry guard applies the record, and the retry fetch brings no
     B objects.
   - **Guarded merge**: Y is diverged with a protected dirty file (the existing
     guarded-merge fixture shape), and the incoming commits carry the migration
     record. No B objects arrive.
   - **Fail-closed fault injection** (X's migration record is already published
     in every case):
     - A stale `.git/config.lock` in Y makes the sync print
       `DEFERRED:fetch_exclusion:…` and exit 0. **During that attempt** no
       `refs/remotes/origin/B` appears and B's tip object is absent. After the
       lock is removed, the next sync applies and still fetches no B objects.
     - A transient narrow-fetch failure: new seams `pre_exclusion_fetch` /
       `post_exclusion_guard` (the existing `_sync_test_seam` pattern) point
       origin at a bogus URL and then restore it. The result is a deferral with
       no B objects, rather than a broad fetch with stale protection.
     - The same lock injection on the push-retry path: `do_push` defers
       (`return 2`), the retry fetch never runs, and no B objects arrive.
     - `DEDICATED_DRIFT` leads to a deferral that names the recovery commands.
     - A narrow-fetch timeout produces `NO_NETWORK` after a single timeout.
     - A remote with no data branch (`ls-remote` exit 2) proceeds on the local
       inputs.
   - **Within-sync reconciliation** (finding: post-merge). Each case completes
     within the one sync that brings the change from X:
     - X runs `drop-retired A` and syncs. Y then releases A on each of the three
       convergence routes: a normal pull, a guarded merge, and the push retry
       via the `pre_push` seam.
     - X turns `remote_dedicated` to false and syncs. Y's dedicated remote is
       restored on a normal pull and on the push retry.
   - **Fingerprint**:
     - unchanged inputs mean `aitask_artifact.sh` is not invoked (a stub in the
       fixture's script copy records invocations);
     - a hand-deleted exclusion is restored on the next sync.
7. **Stale-config correction and release.**
   - Config X with no record → apply → config B → apply: X is `RELEASED` and B is
     excluded.
   - Config changed with no migration while the record says A: A stays excluded.
   - `drop-retired A` in X removes A from the record and commits. X releases A
     immediately; Y releases A within the sync that brings the change
     (scenario 6b).
   - `drop-retired B` (the current store) refuses.
8. **Dedicated mode (finding 2).**
   - Declared on `ait-store`: `skipFetchAll` is set only there, its fetch set is
     negative-only, the saved keys hold the original values, and origin stays in
     shared mode.
   - Without the flag: no `skipFetchAll` anywhere.
   - Declared on origin: a warning, and shared mode.
   - **Dedicated→shared** (the flag set to false): the original fetch values are
     restored byte for byte and in order, `skipFetchAll` is back to its saved
     state (unset, and a separate case where it was `true`), the `aitask*` keys
     are cleared, and the negatives are re-added in shared mode.
   - **Reassignment** `ait-store` → `ait-store2`: the first is restored and the
     second is dedicated.
   - **Drift**: the user edited `fetch` while the remote was dedicated, then the
     flag is turned off. The result is `DEDICATED_DRIFT`, exit 1, that remote is
     untouched, the warning names the recovery commands, and other remotes are
     still processed.
   - **Interrupted transitions** (fault injection through a PATH `git` shim that
     fails one specific `git config` write and delegates everything else; no
     test hooks in production code). Each case starts from a remote with two
     positive mappings and `skipFetchAll` unset, and a second variant with
     `skipFetchAll false`. Each case fails the apply, retries it without the
     shim, then leaves dedicated mode. The assertions are that the original
     fetch values (byte-identical, same order) and the original `skipFetchAll`
     state survive, and that no `aitask*` keys remain:
     - (a) the write of `state=active` fails, after the mapping was replaced:
       the reviewer's sequence;
     - (b) the write of `state=saved` fails, after the backup was written;
     - (c) a mid-replacement `fetch` write fails;
     - (d) during leave, the sentinel deletion (step 3) fails after the live
       restore: the retry redoes the restore from the complete backup;
     - (e) during leave, deleting the `aitaskSavedFetch` values (step 4) fails
       after the sentinel was deleted: the retry runs cleanup only, and the
       restored positive mappings are untouched;
     - (f) during leave, the state-key deletion (step 5) fails: the retry runs
       cleanup only.
     - An invalid state value gives `DEDICATED_STATE_INVALID`, exit 1, and that
       remote is untouched.
   - **Concurrent applies (deterministic).**
     - Apply A runs with a PATH `git` shim. After performing the
       `aitaskDedicatedState saved` write, the shim blocks on a FIFO.
     - While A is paused, apply B (no shim) starts in the background. Assert:
       - B is still running and the lock dir exists;
       - the backup keys and the live `fetch` values are exactly what A left;
       - B wrote nothing.
     - Release the FIFO. A completes (`active`), then B acquires the lock, sees
       `active` and makes no change.
     - Leave dedicated mode: the original positive mappings (byte-identical, in
       order) and the original `skipFetchAll` state are restored. Run this once
       with the original unset and once with it `false`.
     - Mirror case: A pauses mid-Leave, after `state=restoring` has been written
       and before the sentinel deletion. B, a concurrent Enter re-declaration,
       waits, and the final state is consistent.
     - Busy timeout: while A holds the lock past the timeout, B exits 1 with
       `BUSY`. The sync guard then defers, and no broad fetch runs.
   - **No nested acquire:** calling apply while this process holds a registry
     lock dies with the programming-error message.
9. **Old git.** A PATH shim `git` reports 2.28.0 for `--version` and delegates
   everything else. Result: exactly one warning, `UNSUPPORTED_GIT`, the config
   unchanged, exit 0.
10. **Not configured.** Apply prints `NOT_CONFIGURED` and changes nothing.
11. **Call sites.**
    - `init-store gitbranch` adds the exclusion.
    - `aitask_init_data.sh` adds it, and its stdout still carries only
      `INITIALIZED`.

**`tests/test_settings_artifacts_tab.py`**: saving with a gitbranch branch calls
`_run_fetch_exclusion`. A canned non-zero result produces a warning notify, and
the save still succeeds. A save without gitbranch makes no call.

**Regression:**
- `bash tests/test_artifact_fetch_exclusion.sh`,
  `tests/test_artifact_gitbranch_backend.sh` (migrate and record),
  `tests/test_artifact_cli.sh`, `tests/test_init_data.sh`, and the sync suites
  (`tests/test_sync_*.sh`).
- `bash tests/run_all_python_tests.sh --test-dir` for settings.
- `shellcheck` on the touched scripts.
- `check_links.py --build`.

## Post-implementation

Step 9 of the task workflow covers the commit, the archival and the merge. Two
notes go out:
- to t2104: the record's `retired` list and `ait artifact fetch-exclusion
  drop-retired <b>` are its release hook after `--delete-retired`;
- to t2100: `gitbranch-fetch-config` reads `remote`/`remote_dedicated`, so its
  validation belongs there. The record gains `retired`, so its `remote` field
  must carry `retired` forward.

## Risk

### Code-health risk: medium
- Mutates `.git/config` on every named remote. Ownership keys, exact-value
  edits and verbatim save/restore for dedicated mode bound it; scenarios 1 and 8
  prove that positive mappings and user entries survive. · severity: low · → mitigation: none (covered by plan tests)
- Touches five call sites (setup, init_data, settings, sync, CLI) and the
  shared store record format. Every call site is best-effort; the record change
  is additive, and the reader validates it fail-closed. · severity: medium · → mitigation: none (covered by plan tests)

### Goal-achievement risk: low
- **Remaining window**: between another clone's migration copy (or first store
  creation) and the publication of its record, other clones' syncs download the
  new branch once. The user accepted this; publication order is out of scope,
  and the window is documented. · severity: low · → mitigation: none (accepted; an announce-before-copy follow-up task can be offered at Step 8c)
- The guard adds one narrow, data-branch-only fetch round trip per sync. Python
  runs only when the fingerprint changes. · severity: low · → mitigation: none
- Fail-closed deferral can block syncs (a persistent `config.lock` or dedicated
  drift) until the user acts. The trade was chosen deliberately, and the
  deferral message names the exact recovery. · severity: low · → mitigation: none (accepted trade)
- `fetch --prune` with a negative refspec may delete the backend's bookkeeping
  `refs/remotes/origin/<store>`. That ref is never authority (R1); scenarios 3
  and 4 measure it. · severity: low · → mitigation: none (covered by plan tests)

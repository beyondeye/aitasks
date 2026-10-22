---
priority: medium
effort: high
depends: [2099]
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-21 14:51
updated_at: 2026-10-21 14:51
---

## Context

Decided in t1890 (`aidocs/artifact_storage_lifecycle.md`, D1(b), §3, §8): the
`gitbranch` store may live in a **separate artifact repository**, which is the
recommended home for large recordings, so a clone of the code/data repository
never contains store history. **Today** every `ls-remote` / fetch / push in
`lib/artifact_backends/gitbranch.sh` targets `origin` (fetch `:126-136`, CAS push
`:264-296`, the `:352-434` loop). The store identity record
`artifacts/gitbranch_store.json` (`aitask_artifact.sh:235-294`) has no `remote`.
The registry (`lib/artifact_registry.py:89-133, 204-223`) validates only
`branch`.

Depends on t2099 (routine-fetch exclusion), which owns the shared/dedicated
exclusion mechanics. This task adds the remote and declares dedicated mode.

## Scope

1. New `artifacts.backends.gitbranch.remote` (a remote name or a URL; default
   `origin`) and `artifacts.backends.gitbranch.remote_dedicated` (bool, default
   false), validated in `artifact_registry.py`. No credentials ever go in
   `project_config.yaml`; the git credential helper / SSH config handles them.
2. Every `ls-remote`, fetch and push in `gitbranch.sh` uses the configured
   remote.
   - **A URL value registers no git remote.** It fetches with an explicit refspec
     into a private namespace `refs/ait-store/<store_id>/tip`, which lies outside
     `refs/remotes/`, so `fetch --all` and `git remote prune` never see it
     (verified by the t1890 probe).
   - **A named-remote value** gets t2099's exclusion: shared mode by default,
     dedicated mode only with `remote_dedicated: true`.
3. The store record gains `remote` (as configured), and every activation checks
   it like the branch check. A changed remote refuses and names the migration
   command.
4. Extend `gitbranch-migrate` to move a store between remotes (`origin` → the
   separate repo), reusing the copy + verify + fence machinery. The old store is
   retired, not deleted.
5. **Decide and document where fetched objects live**: the main repository's
   object store (today's behaviour) vs. an isolated bare repo, e.g.
   `.git/ait-artifacts.git`, reached via `GIT_DIR`. The isolated repo keeps
   store objects out of the main repo and makes local eviction possible. Record
   the decision with rationale in `aidocs/artifact_storage_lifecycle.md` §8.
6. Settings Artifacts tab: `remote` and `remote_dedicated` fields, validated
   through the registry before saving (same pattern as `branch`, t1231_2).

## Acceptance criteria

- With a separate remote configured, a fresh clone of the code repository plus
  `ait setup` plus `ait sync` downloads **no store blob bytes**.
- `ait artifact get` / `create` / `update` work against the separate remote.
- Offline reads of cached versions need no network.
- A missing or unreachable remote fails closed, like `origin` today (rule R1).

## Verification

- Migration `origin` → separate remote: every version stays retrievable, and the
  old branch is fenced.
- **Combined t2099 + this task**: after configuring a separate *named* store
  remote, `git fetch --all --prune` and `ait sync` create no store refs and
  fetch no objects (`git count-objects -v` unchanged), while `ait artifact get`
  works.
- **Mixed-remote check** (from t2099) repeated with the remote configured
  through this task's keys.
- URL mode: no `remote.*` entry is created, and the private ref survives
  `git remote prune`.
- Offline: cached read succeeds; uncached read fails with a clear message.

## Docs

- `website/content/docs/commands/artifact.md`: new keys, migration between
  remotes, "What gets downloaded".
- A recommended setup for large recordings (separate repo, dedicated mode).
- Settings reference rows for the new fields.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2099** id=2026-10-22T09:52:23Z.60eae19ca87f632886e4ef2e from=t2099 from_verified=yes at=2026-10-22T09:52:23Z base=db9829d512d526d3b23a48829a4e517321a54d87 base_branch=main dirty=yes host=omg16
>
> | t2099 landed (db9829d51): routine-fetch exclusion for the gitbranch store. Context for t2100 (claims as of that commit; verify before relying):
> | 
> | - artifact_registry.py has a read-only verb `gitbranch-fetch-config` that already READS artifacts.backends.gitbranch.remote (default origin, non-empty string) and remote_dedicated (default false, must be bool). Only types are checked; URL-vs-name validation and KNOWN_ADAPTERS registration were left to t2100 — put the real validation there (or in a shared helper both use).
> | - Exclusion mechanics live in .aitask-scripts/lib/artifact_fetch_exclusion.sh (afx_apply_core). Shared mode applies to every named remote. Dedicated mode applies only to a declared remote that is a registered `git remote` and is not origin; a URL value gets no dedicated mode. Dedicated state is reversible via remote.<r>.aitaskDedicatedState / aitaskSavedFetch / aitaskSavedSkipFetchAll / aitaskDedicatedSet (write-ahead, drift-checked). If t2100 changes how the store remote is chosen, keep the declared remote flowing through _artifact_afx_read_inputs (local config only).
> | - The store record gained an optional "retired" list. When t2100 adds "remote" to artifacts/gitbranch_store.json, extend _artifact_gitbranch_record_parse/_record_write and carry "retired" forward in every record write (migrate step 8 included).
> | - `ait sync` guards its broad fetches with a data-branch-first narrow fetch of origin; a store in a separate repo never reaches that path, but a named store remote does via shared/dedicated exclusion.

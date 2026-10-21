---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [task_attachments]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
created_at: 2026-10-21 14:51
updated_at: 2026-10-21 16:49
---

## Context

Decided in t1890 (`aidocs/artifact_storage_lifecycle.md`, D1(a) and §3): routine
fetches must never download the `gitbranch` artifact store. **Today**
`ait sync` runs `git fetch origin` with no refspec (`aitask_sync.sh:278-284`,
`:1945`) and web-merge runs `git fetch --all --prune` (`aitask_web_merge.sh:240`).
Under the default `+refs/heads/*:refs/remotes/origin/*` mapping, both download
the store branch's full history on every machine. `ait setup` and
`aitask_init_data.sh` fetch only `aitask-data` by name (`aitask_setup.sh:1691`,
`aitask_init_data.sh:205`). gitbranch reads use an explicit refspec
(`lib/artifact_backends/gitbranch.sh:126-136`).

The t1890 probe (git 2.56.0, recorded verbatim in the design doc §3) confirmed
the following:
- A negative refspec `^refs/heads/<store>` on a remote makes `git fetch <remote>`
  and `git fetch --all --prune` skip the store, while the gitbranch
  explicit-refspec fetch still works.
- An exclusion on `origin` alone does **not** protect a second named remote that
  also carries the store.
- **Shared mode** (keep the positive mapping, add only the negative) still
  updates that remote's code branches.
- **Dedicated mode** (`skipFetchAll true` plus replacing the mapping) must only
  be applied to a store-only remote, or it freezes code branches.

## Scope

1. A helper (e.g. `lib/artifact_fetch_exclusion.sh` or a verb on
   `aitask_artifact.sh`) that, given the configured store branch and remote:
   - **Shared mode** (the default for every named remote, `origin` included):
     adds `^refs/heads/<store>` to `remote.<name>.fetch` if it is absent and
     **never touches existing positive mappings**. Idempotent.
   - **Dedicated mode**, only when `artifacts.backends.gitbranch.remote_dedicated:
     true` (the key itself lands in the separate-remote task; read it if
     present): sets `remote.<name>.skipFetchAll true` and replaces the remote's
     mapping with the negative refspec.
   - Never applies dedicated mode to a remote that is not declared dedicated.
   - On git older than 2.29 (no negative refspecs): warns once and changes
     nothing.
   - When the store branch is renamed, removes the stale negative entry it
     previously added, and only that entry (track ownership, e.g. by exact value
     match against the previous store record).
2. Call sites: `ait setup` / `aitask_init_data.sh` (when `gitbranch` is
   configured), the settings Artifacts tab save, `gitbranch-migrate`, and
   `init-store gitbranch`.
3. `ait sync` and web-merge need no change once the config is in place. Verify
   that, and do not add ad-hoc refspec filtering in them.

## Acceptance criteria

- After setup on a clone, `git fetch origin`, `ait sync` and
  `git fetch --all --prune` create or advance no
  `refs/remotes/<remote>/<store>` and fetch no store objects
  (`git count-objects -v` unchanged).
- `ait artifact get` of an uncached version still works.
- Existing positive mappings are preserved byte for byte in shared mode.
- Re-running setup is a no-op.

## Verification (tests in `tests/`, scratch repos over `file://` — a plain-path
## clone hard-links objects and hides the difference)

- A fresh `--single-branch` clone plus setup plus sync leaves
  `refs/remotes/origin/<store>` absent.
- An **old clone** that already has the store ref: after enabling the exclusion,
  further syncs do not advance it (document how to drop the stale ref).
- **Mixed code-and-artifact remote**: a shared named remote carries `main` and
  the store. Push a new commit to its `main`, then run `fetch --all --prune`.
  `<remote>/main` advanced, and no store ref or objects were fetched.
- **Dedicated mode**: `skipFetchAll` is set only when declared.
- Branch rename: the stale negative entry is removed and the new one added.

## Docs

- `website/content/docs/commands/artifact.md` "The gitbranch backend" →
  "What gets downloaded": change the `ait sync` sentence to the new behaviour.
- `website/content/docs/concepts/git-branching-model.md`: the `aitask-artifacts`
  row.
- Run `cd website && python3 check_links.py --build`.

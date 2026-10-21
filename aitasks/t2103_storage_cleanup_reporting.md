---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-21 14:52
updated_at: 2026-10-21 14:52
---

## Context

From t1890 (`aidocs/artifact_storage_lifecycle.md` §6), three cleanup and
reporting gaps that no other task covers:

- `ait attach gc` has **no dry run**: `cmd_gc` refuses any argument
  (`aitask_attach.sh:642`).
- The shared blob cache `${XDG_CACHE_HOME:-~/.cache}/ait/artifacts/<hash>`
  (`lib/artifact_utils.sh:85-89`, `lib/artifact_cache.sh`) is **never evicted**:
  no size cap, no TTL.
- Nothing answers "how much is stored where, and what does a fresh clone
  download?"

## Scope

1. `ait attach gc --dry-run`: the same candidate and protection computation as
   gc (`:626-739`), printing what would be reclaimed and the reason each
   protected blob is kept. No writes, no commit. Keep the exit-status contract
   consistent with gc.
2. `ait artifact cache prune [--older-than DUR] [--max-size SIZE] [--dry-run]`:
   - evicts cache entries by access/modification time;
   - **never removes or follows a local-backend symlink's target**: for `local`,
     a cache entry is a symlink into the data worktree (`artifact_cache.sh:50-63`);
     only the link may be removed;
   - entries are re-fetchable, so no lock is needed beyond a safe atomic remove;
   - also mentions the abandoned legacy `~/.cache/ait/attachments/`
     (`artifact_utils.sh:82-84`).
3. `ait artifact usage`: bytes and counts per backend and per artifact kind;
   current vs. historical vs. expired versions; and what a fresh clone downloads
   (data-branch blob bytes in history, whether the store branch is on `origin`
   and whether it is excluded from routine fetches).
   - Read-only.
   - Prefer reusing manifest/registry helpers over a new scanner.

## Verification (tests)

- gc `--dry-run` reports the same set a real gc then reclaims; the tree is
  unchanged after the dry run.
- Cache prune: old entries go and fresh ones stay; a local symlink entry is
  removed as a link only (its target blob still exists); `--dry-run` deletes
  nothing.
- `usage` on a fixture with local + gitbranch artifacts, shared and historical
  versions reports the expected numbers.

## Docs

- `website/content/docs/commands/attach.md` (gc `--dry-run`) and
  `commands/artifact.md` (`cache prune`, `usage`).
- Run `check_links.py`.

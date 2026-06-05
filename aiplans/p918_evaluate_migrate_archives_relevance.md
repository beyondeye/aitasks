---
Task: t918_evaluate_migrate_archives_relevance.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# Plan: Evaluate / migrate `ait migrate-archives` relevance (t918)

## Investigation summary

- **Format-switch date:** The `tar.gz` → `tar.zst` archive migration landed
  2026-03-29 in the t470 series
  (`3b73b3f28 refactor: Migrate aitask_zip_old.sh and aitask_create.sh ...`).
  `ait migrate-archives` was added the same day (`0df79eedf`, t470_6). The
  legacy `tar.gz` format therefore only exists in repos that adopted aitasks
  **before 2026-03-29** — roughly two months before this task.
- **No current write path produces `tar.gz`.** The only archive-creating script,
  `aitask_zip_old.sh`, always writes `.tar.zst` (via `zstd`). Every other
  `tar.gz` reference is a **read-side backward-compat fallback**
  (`archive_utils.sh`, `archive_scan.sh`, `task_utils.sh`, `archive_iter.py`,
  `aitask_revert_analyze.sh`, `aitask_stats_legacy.sh`, `aitask_create.sh`) or a
  third-party CLI download in `aitask_setup.sh` (bkt, lazygit — unrelated to the
  archive format).
- **Legacy fallback does not *require* migration.** Read paths transparently
  handle `old.tar.gz` and numbered `oldM.tar.gz` everywhere; a pre-switch repo
  keeps working without ever running `migrate-archives`. The command is a
  convenience/perf + bundle-consolidation upgrade, not a correctness requirement.
- **Current surface:** listed in `ait help` under "Tools:"; has a test
  (`tests/test_migrate_archives.sh`); mentioned in the v0.14.0 blog post
  (historical, left as-is); **absent** from the command-reference docs
  (`website/content/docs/commands/_index.md`) — t914 deliberately deferred it
  pending this evaluation.

## Decision: **Hide from `ait help`** (user-selected)

Keep the script, its test, and the dispatcher route (so `ait migrate-archives`
still works for the upgraders who need it), but **drop the listing line from
`ait help`**. Rationale:

- **Not Remove:** the format switch is only ~2 months old; early-adopter repos
  can still hold `tar.gz` archives. Removal would strand them.
- **Not document in the everyday command index:** it is a one-time, upgrade-only
  maintenance tool. Fresh installs can never produce `tar.gz`, so promoting it
  alongside routine commands would mislead the majority of users.
- **Hide** keeps the capability available (direct invocation + `--help` still
  work) while removing it from the routine command surface.

## Implementation steps

1. **`ait` — remove the help listing.** Delete line 62 from the `usage()`
   "Tools:" block:
   ```
     migrate-archives Convert tar.gz archives to tar.zst / rebucket legacy archives
   ```
   The remaining Tools block (codeagent, skillrun, explain-runs, explain-cleanup,
   zip-old) stays intact.

2. **`ait` — add a maintainer note at the dispatcher route (line ~204)** so a
   future editor does not "helpfully" re-add the help line, unaware of this
   decision:
   ```bash
   # migrate-archives: intentionally omitted from `ait help` (t918) — one-time,
   # upgrade-only maintenance command for pre-2026-03-29 tar.gz repos. Still
   # invocable directly; `ait migrate-archives --help` documents it.
   migrate-archives) shift; exec "$SCRIPTS_DIR/aitask_migrate_archives.sh" "$@" ;;
   ```

3. **Keep unchanged:** `aitask_migrate_archives.sh`, `tests/test_migrate_archives.sh`,
   the dispatcher route itself, and all read-side `tar.gz` fallbacks. No
   command-reference doc entry is added (consistent with "hide").

## Verification

- `bash -n ait` parses cleanly.
- `./ait migrate-archives --help` still prints usage (route intact).
- `./ait --help` (or `./ait help`) no longer lists `migrate-archives`; the Tools
  section is otherwise unchanged.
- `shellcheck` on `ait` shows no new findings (comment-only + line-removal).
- `bash tests/test_migrate_archives.sh` still passes (behavior untouched).

## Risk

### Code-health risk: low
- None identified. The change removes one help-text line and adds an explanatory
  comment in `ait`; no executable behavior changes (the dispatcher route, script,
  and tests are untouched). Blast radius is a single file.

### Goal-achievement risk: low
- None identified. The decision (Hide) was confirmed by the user, and the edit
  directly realizes it; verification confirms the command stays invocable while
  leaving `ait help`.

## Post-implementation

Single-task chore → Step 9 archival (status → Done, move task + this plan to
archived, commit, push). No build verification configured beyond the checks above.

## Final Implementation Notes

- **Actual work done:** Resolved t918 with the user-selected decision **Hide**.
  Two edits to `ait`: (1) removed the `migrate-archives` listing line from the
  `usage()` "Tools:" block; (2) added a 3-line maintainer comment above the
  dispatcher route documenting the intentional omission (prevents a future editor
  from re-adding the help line unaware of this decision). Script
  (`aitask_migrate_archives.sh`), test (`tests/test_migrate_archives.sh`), the
  dispatcher route, and all read-side `tar.gz` fallbacks left untouched.
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Hide (not Remove) because the tar.gz→tar.zst switch is only
  ~2 months old (2026-03-29, t470 series) and pre-switch repos can still hold
  `tar.gz`; not added to the command index because it is a one-time, upgrade-only
  tool that fresh installs never need. No command-reference doc entry added
  (consistent with "hide").
- **Verification:** `bash -n ait` OK; `migrate-archives` absent from `ait --help`;
  `ait migrate-archives --help` still prints usage (route intact);
  `bash tests/test_migrate_archives.sh` → 28/28 pass; `shellcheck ait` shows only
  pre-existing SC1091 info findings (unrelated).
- **Upstream defects identified:** None.

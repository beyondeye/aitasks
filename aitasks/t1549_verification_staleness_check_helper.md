---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [verification, task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-08-17 18:01
updated_at: 2026-08-17 18:01
---

Implement the deterministic staleness check for `issue_type: manual_verification`
tasks, per the design in `aidocs/framework/manual_verification_staleness.md`
(read it first — it is the source of truth for this task).

Slice 1 of 3 (+ a manual-verification sibling). This slice owns the whole
deterministic seam plus the new frontmatter field.

## Scope

1. **New helper `.aitask-scripts/aitask_verification_stale.sh`**, verb `check
   <task_file>`. Always exits 0. Structured stdout:

   ```
   BASELINE:<sha>|<YYYY-MM-DD HH:MM>
   FILES:<n>
   CHANGED:<path>|<n_commits>|<task_ids>        0+ lines
   DELETED:<path>|<culprit_task>|<subject>      0+ lines
   UNKNOWN:<path>|<reason>                      0+ lines, advisory only
   DISPLAY:<one-line human summary>
   DECISION:<FRESH|ASK_STALE|SKIP>
   ```

   Ordered evaluation — the order is normative:

   ```
   1. not a git repo                              -> SKIP
   2. file_references: empty/absent               -> SKIP   (precondition)
   3. verification_baseline: absent               -> SKIP   (precondition)
   4. baseline not an ancestor of HEAD            -> SKIP   (history rewritten)
   5. classify each curated path
   6. any CHANGED / DELETED                       -> ASK_STALE
   7. otherwise                                   -> FRESH
   ```

   `SKIP` is fail-open and silent — "cannot tell" must never render as "stale"
   (mirror `code_digest` in `lib/gate_ledger.py`, where unverifiable is its own
   answer). Steps 2/3 are the common case for every existing task; that is
   intended, not a bug.

   **Existence is probed, not inferred.** `git log -- <path>` reports history but
   says nothing about current existence, so a history-only implementation handles
   modification and silently misses deletion. Classify each curated path with two
   probes against the committed trees (never the dirty worktree):

   ```bash
   git cat-file -e "<baseline>:<path>"   # present at baseline?
   git cat-file -e "HEAD:<path>"         # present now?
   ```

   | at baseline | at HEAD | result |
   |---|---|---|
   | yes | yes | history query -> `CHANGED:` or nothing |
   | yes | no  | `DELETED:` — culprit via `git log --diff-filter=D -M --name-status <baseline>..HEAD -- <path>` |
   | no  | —   | `UNKNOWN:<path>` — reported, does NOT drive the verdict |

   History query: `git log --format='%h|%ad|%s' <baseline>..HEAD -- <path>`.
   `CHANGED:` task ids come from commit subjects via the existing parenthesised
   `(tNN)` / `(tNN_M)` tag convention.

   Read the curated list with `get_file_references()` from `lib/task_utils.sh`.
   **Ignore any `path:N-M` range suffix** — v1 compares whole files.

2. **`verification_baseline:` frontmatter field** — `<sha> @ <YYYY-MM-DD HH:MM>`.
   Add **additive** write support to `aitask_update.sh` per
   `aidocs/framework/aitasks_extension_points.md`.

   **Do NOT touch how any existing shared field is emitted.** Specifically: do not
   add presence tracking to `file_references`, do not add `--file-refs-none` /
   `--file-refs-clear`, and do not modify `union_file_references()` or
   `aitask_fold_mark.sh`. Those belong to deferred work (see the doc's "Deferred"
   section) and were deliberately excluded to keep this change off the shared
   writer's existing behaviour.

3. **Carry-over inheritance** — a carry-over task must inherit
   `verification_baseline:` rather than reset it (`create_carryover_task` in
   `aitask_archive.sh` currently gives the new task a fresh `created_at`, which is
   exactly why the field exists).

## Tests

Bash with `tests/lib/asserts.sh`, fixed deterministic timestamps in the style of
`tests/test_risk_mitigation_landed.sh`, over a sandbox git repo with real commits.

**Positive paths — the core contract, and the easiest to omit:**
- a curated file **modified** since the baseline => `ASK_STALE` with a `CHANGED:`
  line naming the culprit task
- a curated file **deleted** since the baseline => `ASK_STALE` with a `DELETED:`
  line. Assert specifically that detection comes from the
  `git cat-file -e HEAD:<path>` probe and is not inferred from history — a
  history-only implementation passes the modified case and silently fails this one
- **mixed**: one changed, one deleted, one untouched => exactly two evidence
  lines, `FILES:3`, `ASK_STALE`

**Negative control:** curated files untouched => `FRESH`. Name the failing id if
it reports otherwise — a detector that cannot say FRESH is the failure mode the
whole design exists to avoid.

**Precondition skips** (one each, asserting no `CHANGED:` / `DELETED:` line):
populated list but no baseline; baseline but no list; neither; baseline not an
ancestor of HEAD.

**Baseline advance:** after a simulated "Proceed unchanged" the baseline is at
HEAD and a re-run reports `FRESH` — the prompt does not re-fire.

**Round-trip:** `verification_baseline:` survives an unrelated
`aitask_update.sh --batch <id> --status Done`.

**Guard against scope creep:** assert that a task with **no** `file_references:`
still has none after an unrelated update (no accidental empty-list
materialisation).

## Acceptance

- `bash tests/test_verification_stale.sh` passes (new file).
- `shellcheck .aitask-scripts/aitask_verification_stale.sh` clean.
- The helper is added to the invocation allowlists:
  `.claude/settings.local.json`, `seed/claude_settings.local.json`,
  `seed/opencode_config.seed.json` — an unwhitelisted helper stalls on a
  permission prompt.
- `git diff --stat` shows no change to `union_file_references`,
  `aitask_fold_mark.sh`, or `file_references` emission in `aitask_update.sh`.

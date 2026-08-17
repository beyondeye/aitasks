---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [verification, task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-08-17 19:00
updated_at: 2026-08-17 19:00
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
   UNKNOWN:<path>|<reason>                      0+ lines, raises ASK_STALE
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
   6. any CHANGED / DELETED / UNKNOWN             -> ASK_STALE
   7. otherwise                                   -> FRESH
   ```

   **`UNKNOWN` drives the verdict — it is NOT advisory.** A curated path that
   cannot be checked means the check covers less scope than it claims, so
   reporting `FRESH` would be a false all-clear. An `UNKNOWN:` line raises
   `ASK_STALE` exactly like a change does. The `DISPLAY:` line must distinguish
   the causes, because the remedies differ: a changed file suggests amending the
   checklist, an uncheckable path suggests fixing `file_references:`.

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
   | no  | —   | `UNKNOWN:<path>|absent_at_baseline` — raises `ASK_STALE` |

   History query: `git log --format='%h|%ad|%s' <baseline>..HEAD -- <path>`.
   `CHANGED:` task ids come from commit subjects via the existing parenthesised
   `(tNN)` / `(tNN_M)` tag convention.

   Read the curated list with `get_file_references()` from `lib/task_utils.sh`.
   **Ignore any `path:N-M` range suffix** — v1 compares whole files.

2. **`verification_baseline:` frontmatter field** — `<sha> @ <YYYY-MM-DD HH:MM>`.
   Add **additive** write support to `aitask_update.sh` per
   `aidocs/framework/aitasks_extension_points.md`.

   **Setter interface — this is a cross-task contract, not an implementation
   detail.** t1550 (seeding) and t1551 (advance-on-review) both call it, so ship
   exactly this and do not leave the shape to whichever slice lands first:

   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_id> \
       --verification-baseline "<sha> @ <YYYY-MM-DD HH:MM>"
   ```

   A single scalar in exactly the stored form; an empty string clears the field.
   Reads go through `read_yaml_field` like any other scalar — there is no
   presence-vs-emptiness distinction to preserve, which is what keeps the change
   additive.

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

**Invalid scope must not read as fresh — the anti-false-assurance case:**
- a **hand-edited** `file_references:` entry naming a path that does not exist at
  the baseline (a typo, or a path added after the baseline) => `UNKNOWN:` line
  **and `DECISION:ASK_STALE`**. Assert explicitly that the verdict is **not**
  `FRESH` and not `SKIP`: a bad scope entry must never let the task reach the
  normal verification loop without a prompt, because a `FRESH` verdict over a
  partly-uncheckable list is indistinguishable to the user from a real all-clear.
- **mixed valid + invalid**: two curated paths, one genuinely untouched and one
  bogus => `ASK_STALE` with exactly one `UNKNOWN:` line, and the `DISPLAY:` text
  names the uncheckable path distinctly from a changed one (the remedies differ:
  fix `file_references:` vs amend the checklist).

**Negative control:** curated files untouched **and all valid** => `FRESH`. Name
the failing id if it reports otherwise — a detector that cannot say FRESH is the
failure mode the whole design exists to avoid. Note this control only holds when
every path is checkable, which is what makes the two invalid-scope cases above its
necessary complement.

**Precondition skips** (one each, asserting no `CHANGED:` / `DELETED:` line):
populated list but no baseline; baseline but no list; neither; baseline not an
ancestor of HEAD.

**Baseline advance:** after a simulated "Proceed unchanged" the baseline is at
HEAD and a re-run reports `FRESH` — the prompt does not re-fire.

**Setter round-trip (parse / set / preserve):**
- `--verification-baseline "<sha> @ <ts>"` writes the field, and reading it back
  yields the byte-identical value
- the field **survives** an unrelated `aitask_update.sh --batch <id> --status Done`
- `--verification-baseline ""` clears it
- a task that never had the field does not gain an empty one from an unrelated
  update

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

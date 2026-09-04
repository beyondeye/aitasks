---
Task: t1647_3_trail_merge_preflight_helper.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_1_*.md … t1647_6_*.md
Worktree: (none — profile 'fast', current branch)
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1647_3 — Merge preflight helper (`aitask_trail_merge.sh` + `lib/trail_merge.py`)

## Context

Everything deterministic about a merge — reference resolution, candidate
ranking, depth policy, overlap partitioning, retirement-state detection —
moves out of the model into a script, the same rationale as
`aitask_trail_depth.sh` (t1505_4): the skill forwards arguments and copies
resolved lines; it never re-derives them. The helper is strictly READ-ONLY.

Depends on t1647_1 (`lib/trail_discovery.py`) and t1647_2 (`merged_from`).

## Files

- `.aitask-scripts/aitask_trail_merge.sh` — thin wrapper: `#!/usr/bin/env
  bash`, `set -euo pipefail`, source `lib/aitask_path.sh` +
  `lib/python_resolve.sh`, `exec "$PYTHON" "$SCRIPT_DIR/lib/trail_merge.py"
  "$@"`. Model: `aitask_trail_gather.sh` (but no art:-rewrite preamble —
  resolution happens in Python here). Header comment documents both verbs +
  the full line protocol.
- `.aitask-scripts/lib/trail_merge.py` — imports `trail_discovery`,
  `trail_schema`, `fuzzy_filter`. Owns the protocol.

## Protocol (stdout lines, split on FIRST colon; exit 0 resolved,
1 validation outcome, 2 usage)

### `candidates -- <ref>`

Resolution is two-tier — the base of a destructive merge is a USER
SELECTION, never an inference:

1. Exact handle match (with or without `art:` prefix normalization), or
   UNIQUE exact advisory-name match, over `discover_trails()` output →
   resolved. Mirror `_artifact_resolve_ref` (`aitask_artifact.sh:115`)
   semantics: duplicate exact names die → `ERROR:ambiguous:<ref>:<h1>,<h2>`.
2. Otherwise fuzzy (`fuzzy_filter.rank(query, infos, key=title+handle)`):
   emit `BASE_CANDIDATE:<handle>|<owner_id>|<title>` per hit, best first,
   and NO `BASE:` line. Zero hits → `ERROR:unresolved:<ref>`.

On a resolved base: `BASE:<handle>` then
`CANDIDATE:<handle>|<owner_id>|<n_shared>|<title>` for every OTHER
discovered trail, descending `n_shared` (shared entry refs via
`compute_trail_overlaps`), zero-overlap trails last; `NO_CANDIDATES` when
the base is the only trail. Advisory only (RFC §13-A6 — never auto-dedup).

### `preflight -- <base_ref> <folded_ref> [--lite|--deep]`

1. Resolve both refs with the SAME two-tier rule (approximate →
   `BASE_CANDIDATE` lines for that ref, no plan). Same resolved handle →
   `ERROR:same_trail`.
2. Load both docs via `load_trail_blob` — failure →
   `ERROR:invalid_trail:<handle>`.
3. **Half-merged detection FIRST (record-aware):** iterate **every**
   folded-source record in the base doc's `merged_from` — the record whose
   `handle` differs from the **resolved base handle** — and apply the
   outcomes below to each. **This runs regardless of which folded ref the
   caller passed**, and keying it on the caller's argument instead is a
   correctness bug (corrected by t1647_2; see the `merged_from` schema
   description, which states the retirement obligation):

   > `merged_from` is written **wholesale** — a later merge replaces the
   > value rather than extending it. So a pending A+B retirement that is
   > invisible to an A+C request does not merely go unnoticed: authoring A+C
   > **erases B's recovery record**, orphaning a live trail whose content is
   > already absorbed into A. The check must therefore be driven by what the
   > base document records, not by what the caller asked for.

   Per folded-source record:
   - source resolves AND its current version == the record's `version` →
     `RESUME:retirement_pending|<that_handle>|<remaining_owner_csv>`
     (owners still referencing the handle) and STOP — no plan lines, and
     **not** a plan for the pair the caller named. The consumer completes the
     remaining `rm`s; it never re-authors.
   - source resolves but its version moved →
     `ERROR:merge_conflict:<that_handle>` and stop.
   - source no longer resolves → that retirement completed; continue to the
     next record, then to step 4.

   **Excluding the base's own record is required, not incidental.** A merge
   writes two records — the base's pre-merge snapshot and the folded
   source's — and the base is live but has *moved past* its recorded
   pre-merge version. A rule that did not exclude it would fire
   `ERROR:merge_conflict` on every well-formed merged document. The
   exactly-two-records-with-distinct-handles contract (t1647_2, pinned by
   `tests/test_implementation_trail_design.py::MergedProvenanceContract`)
   is what makes "the record whose handle differs from the base's"
   unambiguous.
4. Emit the plan:
   - `BASE:<handle>|<owner_id>|<depth>|<current_version>`
   - `FOLDED:<handle>|<owner_id>|<depth>|<current_version>`
     (depth from `rendering_hints.depth`, `unmarked` when absent; version
     from the artifact manifest current)
   - `RESULT_DEPTH:<lite|deep>` — **deep-wins (PINNED): deep if EITHER
     source is deep, else lite; `--lite`/`--deep` overrides; conflicting
     double flag → usage error (model the depth-flag conflict handling in
     `aitask_trail_depth.sh`).**
   - `DOWNGRADE:<n_obs>|<n_rel>|<n_excl>|<n_evid>` when the resolved depth
     drops material actually present in a source (counts from the docs; an
     `unmarked` deep-shaped source counts by shape).
   - `OVERLAP:<ref>` / `BASE_ONLY:<ref>` / `FOLDED_ONLY:<ref>` per entry
     `task` ref (the entry key is `task`, NOT `task_ref`).
   - `FOLDED_REF:<owner_task_id>|<active|archived|folded>` per task whose
     frontmatter references the folded handle (reuse the discovery scan's
     record stream — the SAME frontmatter definition the board uses).
     Retirement = removing ALL of them: `ait artifact rm` drops one task's
     reference and keeps the manifest while any other active/archived/
     Folded task still references it
     (`_artifact_handle_referenced_elsewhere`); fold transfer
     (`aitask_fold_mark.sh` 5b) creates shared references in the wild.
     **Verify whether `ait artifact rm` (`resolve_task_file`) can target
     archived / Folded task files.** Any reference it cannot target →
     `ERROR:unretirable_reference:<owner_id>` (fail closed with
     manual-cleanup guidance).

## Whitelist

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_trail_merge.sh
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_trail_merge.sh  # → no MISSING lines
```

## Tests — `tests/test_trail_merge_preflight.sh`

Self-contained bash test over a synthetic project fixture (temp dir with
`aitasks/`, manifests, and stored trail blobs; build via the artifact CLI or
direct manifest fixtures — whichever the artifact substrate's own tests do).
If test bodies run in `( … )` subshells, opt into file-backed counters
(`assert_counters_init` / `assert_counters_load`, CLAUDE.md t1207).

Fixtures MUST include a **divergent pair** — partial entry overlap,
different wave structures, one deep with observations/relations/exclusions
the other lacks — not only the identical-membership shape. Cases:

- exact handle + unique-name auto-resolve; approximate →
  `BASE_CANDIDATE` list and NO `BASE:`; duplicate names →
  `ERROR:ambiguous`; unknown → `ERROR:unresolved`.
- candidate ordering by `n_shared`; `NO_CANDIDATES` single-trail case.
- `ERROR:same_trail`.
- OVERLAP / BASE_ONLY / FOLDED_ONLY partitioning on the divergent pair.
- RESULT_DEPTH: lite+lite→lite, lite+deep→deep, override each way;
  DOWNGRADE counts on `--lite` over the deep source.
- FOLDED_REF enumeration: single owner; shared-reference (two tasks, one
  active + one archived).
- Retirement states: base-records-folded-at-current-version →
  `RESUME:retirement_pending` with NO plan lines (single-owner AND
  shared-reference-with-one-reference-already-removed, which must name only
  the REMAINING owner); folded moved → `ERROR:merge_conflict`; fully
  retired → `ERROR:unresolved`.
- `ERROR:invalid_trail` on a corrupted blob.

Pure-Python pieces (depth policy, partitioning, resume detection) may also
get direct unit tests in `tests/test_trail_merge.py`.

## Verification

- `shellcheck .aitask-scripts/aitask_trail_merge.sh` clean.
- `bash tests/test_trail_merge_preflight.sh` green;
  `bash tests/run_all_python_tests.sh --test-dir tests` green.
- Live read-only smoke:
  `./.aitask-scripts/aitask_trail_merge.sh preflight -- art:trail-mobile-shadow-driving art:trail-mobile-shadow-driving-deep`
  → `RESULT_DEPTH:deep`, 6 `OVERLAP:` lines, no `*_ONLY`, one
  `FOLDED_REF:1118|active`.
- **Record-aware half-merge regression (t1647_2 finding 2a) — partial A+B,
  then a requested A+C.** Set up a base A whose `merged_from` names a
  still-resolving B at exactly its recorded version, then invoke
  `preflight -- A C`. Assert it emits `RESUME:retirement_pending|<B>|…`
  and **no plan lines at all** — never a `BASE:`/`FOLDED:` plan for the A+C
  pair the caller named. Keying the check on the caller's folded ref passes
  every other test in this file and fails only this one.
- **Its negative control (required — without it the test cannot distinguish
  "blocked correctly" from "blocked always"):** with B no longer resolving,
  the same `preflight -- A C` call emits a normal A+C plan. Add the
  version-moved sibling too: with B resolving at a *different* version,
  expect `ERROR:merge_conflict:<B>`.
- **The base's own record must not trip the check:** a preflight against a
  well-formed merged document — whose `merged_from` includes the base's own
  pre-merge version, which no longer matches the base's current version —
  emits a normal plan, not `ERROR:merge_conflict`.

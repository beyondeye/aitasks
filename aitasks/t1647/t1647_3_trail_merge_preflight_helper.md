---
priority: medium
effort: medium
depends: [t1647_2]
issue_type: feature
status: Ready
labels: [trails, bash_scripts, python]
gates: [risk_evaluated]
anchor: 1647
created_at: 2026-09-01 18:50
updated_at: 2026-09-01 18:50
---

## Context

Third child of t1647 (trail-to-trail merge). The `/aitask-merge-trails` skill
(t1647_4) must not interpret merge state itself — resolution, candidate
ranking, depth policy, overlap partitioning, and retirement-state detection
are all deterministic and belong in a script ("script decides, model copies",
the t1505_4 `aitask_trail_depth.sh` rationale). This child builds that script.

New files:
- `.aitask-scripts/aitask_trail_merge.sh` — whitelisted `.sh` entry point
  (skills may only call wrapper scripts). Shebang `#!/usr/bin/env bash`,
  `set -euo pipefail`, source `lib/aitask_path.sh` + `lib/python_resolve.sh`,
  exec the framework interpreter on the lib module (model:
  `.aitask-scripts/aitask_trail_gather.sh`).
- `.aitask-scripts/lib/trail_merge.py` — imports `trail_discovery` (t1647_1)
  and `trail_schema`. Read-only: only `artifact get`/manifest reads via the
  discovery lib; NEVER writes.

## Line protocol (split on the FIRST colon; exit 0 resolved, 1 validation
outcome, 2 usage)

### `candidates -- <ref>`

Two-tier base resolution — **the base of a destructive merge is a user
selection, not an inference**:
- Exact handle match, or UNIQUE exact advisory-name match (mirror
  `_artifact_resolve_ref` semantics, `aitask_artifact.sh:115`) →
  `BASE:<handle>` followed by folded-candidate lines
  `CANDIDATE:<handle>|<owner_id>|<n_shared>|<title>` (descending shared
  entry refs via `compute_trail_overlaps`; all other discovered trails
  listed, zero-overlap ones last), or `NO_CANDIDATES` when the base is the
  only trail.
- ANY approximate match (fuzzy) → NO `BASE:` line; emit
  `BASE_CANDIDATE:<handle>|<owner_id>|<title>` per hit
  (`lib/fuzzy_filter.py rank()` over titles+handles, best first). Consumer
  must ask the user, then re-invoke with the chosen handle.
- Duplicate exact advisory name → `ERROR:ambiguous:<ref>:<h1>,<h2>`.
- Nothing matches → `ERROR:unresolved:<ref>`.
Candidates are ADVISORY only (RFC §13-A6: overlapping trails are legitimate;
never auto-dedup).

### `preflight -- <base_ref> <folded_ref> [--lite|--deep]`

- Resolve both refs with the SAME two-tier rule; approximate → BASE_CANDIDATE
  treatment (per ref); same handle both sides → `ERROR:same_trail`.
- Load both docs fail-closed → `ERROR:invalid_trail:<handle>` on schema
  failure.
- Emit:
  - `BASE:<handle>|<owner_id>|<depth>|<current_version>`
  - `FOLDED:<handle>|<owner_id>|<depth>|<current_version>`
    (`current_version` from the artifact manifest; depth from
    rendering_hints, `unmarked` when absent)
  - `RESULT_DEPTH:<lite|deep>` — **deep-wins policy (PINNED user decision):
    deep if EITHER source is deep, else lite; --lite/--deep override.**
  - `DOWNGRADE:<n_observations>|<n_relations>|<n_exclusions>|<n_evidence>`
    when the resolved depth drops material present in a source (real counts
    from the docs) — the skill turns this into a confirmation.
  - `OVERLAP:<task_ref>` / `BASE_ONLY:<task_ref>` / `FOLDED_ONLY:<task_ref>`
    per entry `task` ref (note: the entry key is `task`, not `task_ref`).
  - `FOLDED_REF:<owner_task_id>|<active|archived|folded>` — one line per
    task referencing the folded handle. CRITICAL: `ait artifact rm` removes
    ONE task's reference and keeps the manifest while any other active,
    archived, or Folded task still references the handle
    (`_artifact_handle_referenced_elsewhere` in the rm txn), and discovery
    scans active + archived frontmatter — so retirement = removing ALL
    references. Fold transfer (`aitask_fold_mark.sh` 5b) creates this
    shared-reference state in the wild. Verify in this child whether
    `ait artifact rm` can target archived/Folded task files; any reference
    it cannot target → `ERROR:unretirable_reference:<owner_id>` (fail
    closed with manual-cleanup guidance — never silently leave the trail
    discoverable).

### Half-merged detection (reference-aware resumable retirement)

Before emitting plan lines, check whether the base's CURRENT doc carries a
`merged_from` entry (t1647_2) naming the folded handle:
- Entry present AND folded still resolves AND folded's current version ==
  entry's recorded `version` → previous merge wrote the base but retirement
  is incomplete: emit `RESUME:retirement_pending|<folded_handle>|<remaining_owner_csv>`
  INSTEAD of plan lines. Consumer must NOT re-author — completing the
  remaining rms is the only action.
- Entry present but folded MOVED since the record →
  `ERROR:merge_conflict:<folded_handle>` (completing the old retirement
  would destroy unseen content; human decision).
- Fully retired → the folded ref no longer resolves → ordinary
  `ERROR:unresolved` (NO false resume).

## Whitelist

`./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_trail_merge.sh`
(writes all 5 touchpoints; verify with `audit-helper-whitelist`).

## Tests

`tests/test_trail_merge_preflight.sh` (bash, self-contained asserts; note the
subshell counter rule in CLAUDE.md if bodies run in `( … )`) over synthetic
fixture trails in a temp project dir. MUST include a **divergent pair** —
partial entry overlap, different wave structures, one deep with
observations/relations/exclusions the other lacks — not just the
identical-membership shape. Pin: OVERLAP/BASE_ONLY/FOLDED_ONLY partitioning;
RESULT_DEPTH deep-wins + override + DOWNGRADE counts; BASE_CANDIDATE list
with no BASE: on approximate input; exact-unique auto-resolve;
ERROR:ambiguous on duplicate names; ERROR:same_trail; FOLDED_REF enumeration
across active + archived owners; retirement states: single-owner
rm-failure-shape → RESUME with no plan lines; shared-reference fixture (two
referencing tasks, one reference already removed) → RESUME naming only the
REMAINING owner; fully-retired → ERROR:unresolved; folded-moved →
ERROR:merge_conflict. Python unit coverage for the pure pieces in
`tests/test_trail_merge.py` if warranted.

## Verification

- `shellcheck .aitask-scripts/aitask_trail_merge.sh` clean.
- `bash tests/test_trail_merge_preflight.sh` green.
- Live smoke (read-only): `./.aitask-scripts/aitask_trail_merge.sh preflight
  -- art:trail-mobile-shadow-driving art:trail-mobile-shadow-driving-deep`
  → RESULT_DEPTH:deep, 6 OVERLAP lines, no *_ONLY lines, single FOLDED_REF
  (t1118).

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.

---
priority: low
effort: medium
depends: [2261]
issue_type: enhancement
status: Ready
labels: [release_scripts, issue_integration]
gates: [risk_evaluated]
anchor: 2261
created_at: 2026-11-09 23:13
updated_at: 2026-11-09 23:13
---

## Context

This scope was deferred from t2261 (release-time issue notifications) by an
explicit user decision during t2261 planning. See
`aiplans/p2261_release_issue_notifications.md` ("Accepted scope boundaries").

t2261_2's consumer `ait release-notify --tag T` posts a "Released in T"
comment for every pending ledger record whose task commits fall in
`<previous tag>..T`. Commits sometimes shipped in an **older** release
instead, for example when `release-notify` was not run for that release, or
when the record was written after it. The consumer then reports
`SHIPPED_EARLIER:<task>|<url>|<E>`, where E is the earliest `v*` tag
containing the newest mapped commit. It **keeps the record pending**, posts
nothing, and prints the exact safe retry command: `ait release-notify --tag
<E>` (or `./wait_release_and_notify.sh <E>` in the framework's own release
flow). The user then has to run that per older release.

## Goal

Notify those records automatically, without weakening any posting gate.

## Open design questions (decide in planning)

- Which release a late record belongs to: E (the first tag containing the
  newest mapped commit), or the first tag containing *any* mapped commit
  when its commits span several releases.
- Chained catch-up across several skipped releases: process the older tags
  oldest-first in a single run, or one tag per run.
- Every older tag must pass the full posting gate:
  - attested data freshness;
  - the designated machine (`release_notify_host`);
  - `release_publication_check E` against the project's
    `project_config.yaml` policy (workflow run success, required assets,
    checksum manifests).
- How the catch-up announces itself: the same marker
  `<!-- aitask-release:E tN -->`, so a later manual retry stays a no-op.
- Output and exit-code additions, keeping the existing `INCOMPLETE:`
  semantics (exit 3: nothing posted when a precondition fails).

## Constraints

- Every posting path keeps the t2261_2 gate. Catch-up must never post for a
  tag whose publication cannot be verified.
- Duplicate prevention keeps the documented t2261 scope: serialised runs on
  the designated machine and sequential retries, not an exactly-once
  guarantee.
- No distributed locking and no failover (also user decisions in t2261).

## Prerequisite

t2261 (both children) must have landed. The ledger layout, the consumer
outputs and the gate this task builds on are defined there.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2261_2** id=2026-11-10T16:32:27Z.a3afac53cdbe2d0412e4628d from=t2261_2 from_verified=yes at=2026-11-10T16:32:27Z base=9b54f33d862389402747cae9cc7c5ce492661cef base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2261_2 (release-notify consumer, committed as 37ddf2fe6), not an instruction.
> | 
> | What a catch-up for SHIPPED_EARLIER records will build on (tree-relative to 37ddf2fe6):
> | - The consumer is `.aitask-scripts/aitask_release_notify.sh`. Every posting run goes through ONE gate, in this order: `ril_data_freshness` (explicit-refspec fetch, attested count) → `release_publication_policy_load` (INCOMPLETE:policy_unreadable) → `release_notify_designation` → the local run lock `ait_ledger_lock_acquire release_notify run` (held in the main shell) → residue sweep (`ril_list_residue` + `ril_resume_move`) → re-classify → `release_publication_check <tag>`. A catch-up for an older tag E would need E's publication checked by the same `release_publication_check E`.
> | - Moving a record is `ril_move_released <pending> <tag> <outcome> <commits_csv>` (lib/release_issue_ledger.sh): a subshell that takes its own ledger lock, never inherits the caller's lock globals, commits released+pending in one path-scoped commit and judges success from git state.
> | - SHIPPED_EARLIER today: E = the earliest `v*` tag (version order) containing the newest mapped commit; the record stays pending and the exact `ait release-notify --tag <E>` is printed. That command already posts once, fully gated (tests/test_release_notify.sh case (c)).
> | - Fail-closed rules a catch-up must keep: git output is read with `$( )` so git's own rc counts (`git_lines` helper), never `mapfile < <(git …)` or `| head` under pipefail; a failed containing-tag lookup is `FAILED:<task>|<url>|tag_lookup_failed` (exit 4), never a guessed release; the marker search is a bash substring test.
> | - Duplicate prevention is scoped to serialised runs on the designated machine and sequential retries — documented in website/content/docs/commands/issue-integration.md ("Duplicate comments"); a catch-up should not claim more.

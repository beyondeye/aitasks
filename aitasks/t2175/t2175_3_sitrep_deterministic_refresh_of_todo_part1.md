---
priority: medium
effort: medium
depends: [t2175_2]
issue_type: feature
status: Ready
labels: [sitrep]
anchor: 2175
created_at: 2026-10-31 19:58
updated_at: 2026-11-01 17:40
---


# Deterministic refresh of Part 1

Child of t2175. Depends on the format/writer and harvest children.

## Scope
- A script that re-checks every open item against the real state and updates Part 1 only, through the locked writer: task ids resolved in `aitasks/` and `aitasks/archived/` (Ready/Implementing/Done/Folded), git ahead/behind for push items, trail tasks resolved and next wave computed (trail freshness from its generation time and owner, no guessing).
- Stamp `checked_at`; anything unverifiable becomes `unknown`, never `done`.
- Item flips open to done only on positive evidence. Done items keep a one-line outcome; their context entry is unchanged (it is a map, not a summary).
- Runs on a cheap trigger (monitor maintenance tick and on demand); safe to run concurrently with the agent.
- Cross-repo ids stay unverified unless the project registry resolves them.

## Tests
Landing of a follow-up, archival, fold, push, unreachable repo (-> unknown), concurrent refresh vs agent write.

## Writing results (handed over by t2175_1)
- Read items with `./.aitask-scripts/aitask_sitrep_todo.sh list --machine`
  (`ITEM:c<N>|<rev>|kind|state|group|checked_at|ref|derived|outcome|title`) and
  write results with `set-state --batch`, one line per item:
  `<id>|<observed rev>|<state>|<checked_at>|<outcome>`.
- A `STALE:c<N>|<rev>` result means someone changed the item since it was read
  (e.g. the user dismissed it) — leave it, re-read it next tick, never retry
  blind. `KEPT:c<N>|dismissed` means the batch tried to touch a dismissed item;
  refresh never writes dismissed items and never sets `dismissed`.
- Format contract: `tests/fixtures/sitrep/` (golden store).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2175_2** id=2026-11-03T09:12:24Z.508a1647fe2dbdb3db209a42 from=t2175_2 from_verified=yes at=2026-11-03T09:12:24Z base=10957dd7286d560c7eb206bf7c25ee1043d40f41 base_branch=main dirty=yes host=omg16
>
> | The sitrep harvest landed in 10957dd72. Item shapes refresh will meet:
> | - task items (follow-ups, Created: tasks, a stopped run's own task) are derived=script with checked_at = the harvest time and state=open when the task file was found, state=unknown when it was not (or a cross-repo ref the registry could not resolve; their titles say "(cross-repo, unverified)"). Refs are normalized by the writer (t154, xproj#2171).
> | - triage items (kind=question, no ref) are not refresh targets: the sitrep agent resolves them.
> | - trail items are kind=watch with a `trail: art:trail-<id>` source and no ref.

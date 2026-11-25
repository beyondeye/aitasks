---
priority: high
effort: medium
depends: [t2335_1]
issue_type: feature
status: Implementing
labels: [sitrep, trails]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-25 12:11
---

## Context

Child of the sitrep work-directions task; depends on the store child (direction records, `direction-freshness --batch`). Trails already have a digest-based verdict with named drift reasons (`lib/trail_gather.py` `drift`); directions get the same treatment, computed by the deterministic refresh (`lib/sitrep_refresh.py`), never by the agent.

## Scope

The store contract this child builds on is the "Directions" section of `aidocs/framework/sitrep.md`, landed by t2335_1 (the record, the membership stamp, drift reasons, baseline evidence, "Saving a proposal"). Where this text and that section differ, the section is right.

- A new refresh target kind `direction`, run in the existing refresh pass after item targets (so it reads the states the pass just wrote), within the pass budget.
- **Digest inputs** (normalized, order-independent): the pending member item ids (state `open` or `unknown`) with state and ref; each member task's status (and existence / archived); the linked trail handles with their artifact version and current drift verdict; the `next` pointer's validity.
- **The digest read builds a baseline snapshot, not only a hash.** It renders the inputs in the store's snapshot grammar (one input per line with a stable key, `sitrep_todo.parse_baseline`), for a direction's current members or for a *proposed* member set, and retains it with the writer's `retain-baseline`; the digest is the snapshot's name. The summary is written from that snapshot and saved with its digest: one read, never a second baseline at write time. Refresh recomputes the snapshot on every pass and compares it with the retained one line by line, which is what makes a specific reason possible.
- **The recheck.** One verb recomputes the snapshots of a proposal and reports every digest that differs. Child 4 runs it before its first write, so a task that closed during the confirmation is caught in code and the proposal is revised instead of saved.
- **Verdict**: `current` when the digest matches; `stale` with reasons otherwise; `unknown` when any input could not be read (a trail export failure, an unreadable task directory) — never rounded to `current`, and a partial read keeps the reasons it did establish. A baseline that `sitrep_todo.load_baseline` does not report `ok` is `unknown` with `baseline_unreadable`. A snapshot above the store's size limit is `unknown` with `baseline_too_large` (for `crashed-agents`, whose members cannot be reassigned, that is the lasting outcome).
- **Drift reasons** (one fixed, documented vocabulary, ordered): `member_added`, `member_closed`, `member_removed`, `task_completed`, `task_archived`, `task_deleted`, `trail_stale` (carrying the trail's own first reason), `trail_new_version`, `trail_unreadable`, `next_invalid`, `never_summarized`, plus `inputs_changed` for a digest mismatch with no classified line difference (a task going from Ready to Implementing is one). The store keeps ONE reason per cause code: build them with `sitrep_todo.aggregate_drift`, which puts the number of causes in the count and samples at most three keys, so twenty closed members are one `member_closed:20:…` reason.
- Also report store-wide: open items in no direction (count), as a refresh line, so the TUI and the skill need no second scan.
- Wire lines in the wrapper header (`REFRESH_ITEM` kind `direction` or a dedicated `REFRESH_DIRECTION:` line; decide in the plan and keep `RefreshReport.verdict` / `.partial` coherent: a refresh with an `unknown` direction is partial).
- **The batch write.** Each `direction-freshness --batch` line carries the direction's rev and its membership stamp (`sitrep_todo.direction_stamp` on the snapshot the verdict was computed from). `STALE:` means the rev or the membership moved: recompute. `NOT_FOUND:` (a direction with no block) and `KEPT:<slug>|no_baseline` / `KEPT:<slug>|baseline_<status>` are reported, never retried blind.
- An unchanged verdict writes nothing (the recovery-item idempotence rule), so `checked_at` semantics must be stated: evidence last changed vs last scanned.
- The monitor maintenance tick and the TUI's `r` get this for free through the shared refresh; verify both paths.

## Tests

`tests/test_sitrep_refresh.py` / `.sh`: one case per drift reason, the `unknown` negative control (an unreadable trail never reads `current`), idempotence (second run writes nothing, rev unchanged), agent fields untouched, budget exhaustion leaves directions `not reached` rather than `current`, the no-direction count. Also: a task that closes during the confirmation is reported by the recheck and nothing is saved; one that closes after the save reads `stale` on the next refresh, never `current`; an unusable baseline and an oversized snapshot read `unknown`; more than three causes of one code aggregate into one reason; a member change between the snapshot and the batch answers `STALE:`.

## Docs

`aidocs/framework/sitrep.md` (Directions section: digest inputs and reason vocabulary).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2335_1** id=2026-11-25T09:40:34Z.af35f885567405acecd7b1ae from=t2335_1 from_verified=yes at=2026-11-25T09:40:34Z base=95d0169d8b7b7b559161028acd85264c4061ad8d base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit 95d0169d8): t2335_1 landed the store side of direction freshness. Your task text was updated to match; this is where to look and what is easy to miss.
> | - Contract: aidocs/framework/sitrep.md, "Directions" (drift reasons, baseline evidence, saving a proposal).
> | - Snapshot grammar: sitrep_todo.parse_baseline. It must end with a newline, list only pending members (state open or unknown), kinds in the order member, task, trail, next, keys sorted (item ids by number). Retain with `aitask_sitrep_todo.sh retain-baseline`; limit sitrep_todo.MAX_BASELINE_BYTES (256 KiB), refused whole above it.
> | - Trust a baseline only when sitrep_todo.load_baseline returns "ok" (other statuses: missing, not_regular, unreadable, hash_mismatch, bad_grammar, wrong_direction).
> | - Build reasons with sitrep_todo.aggregate_drift((code, key) pairs): one reason per code, count = number of causes, at most three sample keys; a key that does not fit is left out and still counted. The batch verb accepts only that form.
> | - Batch line: <slug>|<rev>|<stamp>|<freshness>|<checked_at>|<drift>. Take the stamp (sitrep_todo.direction_stamp) from a snapshot loaded AFTER the pass's item batch is written: item refresh bumps member revs, which moves the stamp.
> | - Answers to handle: STALE:<slug>|<rev>|<stamp>, NOT_FOUND:<slug> (no block), KEPT:<slug>|no_baseline, KEPT:<slug>|baseline_<status>. On a store not yet upgraded every block has rev 0 and no line can match until some write upgrades it.
> | - A write that changes membership already resets a block's freshness to unknown.

> **👁 note:read** id=2026-11-25T10:11:34Z.52d1a85c9f93122a1a238936 by=t2335_2 at=2026-11-25T10:11:34Z mode=explicit ids=2026-11-25T09:40:34Z.af35f885567405acecd7b1ae

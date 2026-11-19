---
priority: high
effort: medium
depends: [t2335_1]
issue_type: feature
status: Ready
labels: [sitrep, trails]
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-19 05:12
---

## Context

Child of the sitrep work-directions task; depends on the store child (direction records, `direction-freshness --batch`). Trails already have a digest-based verdict with named drift reasons (`lib/trail_gather.py` `drift`); directions get the same treatment, computed by the deterministic refresh (`lib/sitrep_refresh.py`), never by the agent.

## Scope

- A new refresh target kind `direction`, run in the existing refresh pass after item targets (so it reads the states the pass just wrote), within the pass budget.
- **Digest inputs** (normalized, order-independent): the member item ids with state and ref; each member task's status (and existence / archived); the linked trail handles with their artifact version and current drift verdict; the `next` pointer's validity. The digest is recorded when the agent writes the summary (child 4 calls a `digest` read at write time) and recomputed on every refresh.
- **Verdict**: `current` when the digest matches; `stale` with reasons otherwise; `unknown` when any input could not be read (a trail export failure, an unreadable task directory) — never rounded to `current`, and a partial read keeps the reasons it did establish.
- **Drift reasons** (one fixed, documented vocabulary; one reason per cause, deduplicated and ordered): `member_added`, `member_closed`, `member_removed`, `task_completed`, `task_archived`, `task_deleted`, `trail_stale` (carrying the trail's own first reason), `trail_new_version`, `trail_unreadable`, `next_invalid`, `never_summarized`.
- Also report store-wide: open items in no direction (count), as a refresh line, so the TUI and the skill need no second scan.
- Wire lines in the wrapper header (`REFRESH_ITEM` kind `direction` or a dedicated `REFRESH_DIRECTION:` line; decide in the plan and keep `RefreshReport.verdict` / `.partial` coherent: a refresh with an `unknown` direction is partial).
- An unchanged verdict writes nothing (the recovery-item idempotence rule), so `checked_at` semantics must be stated: evidence last changed vs last scanned.
- The monitor maintenance tick and the TUI's `r` get this for free through the shared refresh; verify both paths.

## Tests

`tests/test_sitrep_refresh.py` / `.sh`: one case per drift reason, the `unknown` negative control (an unreadable trail never reads `current`), idempotence (second run writes nothing, rev unchanged), agent fields untouched, budget exhaustion leaves directions `not reached` rather than `current`, the no-direction count.

## Docs

`aidocs/framework/sitrep.md` (Directions section: digest inputs and reason vocabulary).

---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [frozen, ait_ide]
anchor: 2039
followup_kind: upstream_defect
created_at: 2026-10-19 15:41
updated_at: 2026-10-19 15:41
---

## Origin

Spawned from t2041 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_sessions.py:2380` (`show` verb) with `.aitask-scripts/lib/agent_frozen_ops.py:289` (`parse_show`, the parser `store_show` uses) — `show`'s `key:value` line protocol does not round-trip stored values. Each value is stripped and cut at its first `str.splitlines` break (`\n`, `\r`, `\x0b`, `\x85`, ` `, …), and a later `key:value` line inside another field overrides that key. Restore, reopen and drop all act on that mangled view. For example, a `root` with surrounding whitespace resolves to a different project, and a field holding `\nstate:live` changes the state those actions read.

## Diagnostic context

t2041 replaced the reopen listing's per-record `show` calls with one batch read: `list --full` prints one `RECORD:<json>` per record, read by `frozen_ops.store_records`. Two review rounds then showed that the batch values, which are verbatim, disagreed with what restore applies. Restore reads through `store_show`, so for example a whitespace-only, `\n`-prefixed or later-field-overridden `codeagent_session_id` / `task_id` was listed `ok` but refused by restore with `no_session` / `no_task_id`.

t2041 resolved the disagreement by making the listing read records the way restore does. `agent_reopen._as_shown` renders each batch record as `show` prints it, parses it with `frozen_ops.parse_show`, and puts the four path fields back verbatim. That keeps the offer and the actions in agreement, but the underlying protocol still mangles values for every `store_show` caller: `agent_restore` and `agent_freeze`'s many `store_show` reads, and `reopen_one`.

## Suggested fix

Make the per-record read lossless, so that what an action reads is the stored value:
- Either switch `store_show` to the JSON form (`show --json` or `list --full`-style `RECORD:<json>`), or have `show` escape values.
- Then decide whether whitespace-only identifiers should be rejected at write time (`upsert` / `fill-task`).
- After that, `agent_reopen._as_shown` can drop the render-and-parse step.
- Keep the seam rule: the read must still go through `frozen_ops.store(...)`.
- Parity tests to keep green: `tests/test_agent_reopen.py::TestSingleStoreRead::test_the_offer_lists_the_eligibility_restore_applies` and `test_listing_reads_like_show_except_paths`.

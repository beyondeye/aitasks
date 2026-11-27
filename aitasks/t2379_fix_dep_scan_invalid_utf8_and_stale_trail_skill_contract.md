---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-27 08:48
updated_at: 2026-11-27 08:50
---

## Origin

Spawned from t2335_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/dep_resolution.py:604-610` (was 562-568 before t2335_3 landed) — `_read_facts` (and the `open()` in `scan`) catch `OSError` only; a task file with invalid UTF-8 raises `UnicodeDecodeError` out of `facts()` / `scan`, so the blocking scan dies with a traceback and no `SCAN_OK`
- `tests/test_trail_skill_contract.sh:134` — expects the phrases 'explicit owner choice is REQUIRED' and 'Always pass --owner <id>' that the aitask-trail skill no longer contains: 6 failures across the default/fast/remote variants, with the skill files unmodified

## Diagnostic context

t2335_3 added a precedence-strict `LocalDepResolver.lookup()` beside the existing `facts()` / `classify()` / `scan` and deliberately left those unchanged (they are the parity core of `ait ls`, the board and the minimonitor). While writing the unreadable-file tests for `lookup()`, which catches `(OSError, UnicodeDecodeError)`, the older readers were seen to catch `OSError` only. A file that is not valid UTF-8 is therefore reported as unreadable by `lookup()` and raises out of the older paths. Line numbers above are against commit 7516a41b4; re-check them before editing.

The skill-contract failures were seen in the baseline run taken before any t2335_3 edit and again afterwards, with the aitask-trail skill files unmodified by that task, so they are pre-existing: the test pins wording the skill no longer has. Decide whether the skill lost a required rule (restore it) or the test is stale (update the pinned phrases).

## Suggested fix

Catch `UnicodeDecodeError` next to `OSError` in `_read_facts` and in the `scan` read, with the same "unreadable" outcome each path already gives an `OSError`, and add a test with an invalid-UTF-8 task file through `facts()`, `classify()` and the blocking scan. For the contract test, compare the pinned phrases with the current `aitask-trail` templates and fix whichever side is wrong.

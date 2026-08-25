---
priority: medium
effort: low
depends: [t1599_1]
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness, task_metadata, concurrency]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-25 17:32
updated_at: 2026-08-25 18:40
---

## Defect

`aitasks/metadata/emails.txt` has exactly **two** writers, and only one of them
holds the contributor-list mutex:

- `.aitask-scripts/aitask_pick_own.sh` — `store_email()` serializes its
  read-modify-write on `ait_lock_dir emails` via `registry_lock_acquire`
  (added by t1599_1).
- `.aitask-scripts/aitask_create.sh:1128-1135` — `add_email_to_file()` still
  does an **unlocked** `echo "$email" >> "$EMAILS_FILE"` followed by
  `sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"`.

A mutex only excludes writers that honour it. Because `create` ignores the
lock entirely, `store_email` holding it buys **no** mutual exclusion against a
concurrent `ait create`: `sort -o` snapshots the file and renames its output
over the target, so whichever finishes second erases the address the other just
appended. The serialization introduced by t1599_1 is therefore incomplete
across the file's actual writers.

`aitask_lock.sh:625`, `.aitask-scripts/board/aitask_board.py:197` and
`lib/profile_editor.py` were swept and are **readers only** — no other writer
exists, so closing this one call site completes the protocol.

This defect predates t1599_1 (both writers were unlocked before it); t1599_1
closed one half and its own scoped-commit requirement is met.

## Fix

Make `add_email_to_file()` use the same protocol as `store_email()`:

- acquire on the **same** lock path — `ait_lock_dir emails` — or the two locks
  are disjoint and nothing is serialized;
- **re-check membership under the lock** (the existing `grep -qFx` pre-check is
  only a fast path; a holder we waited on may have added the address);
- release on every exit path, including failures, under `set -euo pipefail`.

`aitask_create.sh` already sources `lib/stale_lock.sh` and calls
`stale_lock_acquire` / `ait_lock_dir` directly for its child-creation lock
(`:334-355`), so the protocol is already in the file.

**Verify the interop rather than assuming it.** `registry_lock.sh` is an adapter
over `stale_lock.sh` (seconds-budget vs attempts-budget; `registry_lock_release
<dir>` vs `stale_lock_release <dir> <token>`). Two callers using *different*
adapters on the *same* lock dir must be confirmed to actually exclude each
other — if they do not, converge both call sites on one adapter.

Decide the busy behaviour deliberately and state it: `store_email` degrades to
"email not recorded" with a warning because a busy contributor list must never
fail a claim. Task creation may or may not warrant the same call.

## Verification

- A regression test that drives both writers against one lock dir
  (`AITASKS_LOCK_DIR`) and asserts neither address is lost.
- A mutex-boundary test for the new call site, in the shape of Test 8 in
  `tests/test_pick_own_scoped_commit.sh`: with the lock held by a live holder,
  assert the file is **not** written unlocked, and that the chosen busy
  behaviour (fail vs warn-and-continue) is what actually happens.
- A negative control: the test must fail against the current unlocked
  `add_email_to_file`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T15:40:59Z status=pass attempt=1 type=human

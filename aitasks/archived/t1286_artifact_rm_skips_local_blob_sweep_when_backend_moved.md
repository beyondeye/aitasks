---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [artifacts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1142
implemented_with: claudecode/opus5_5
created_at: 2026-07-28 11:50
updated_at: 2026-10-12 16:18
completed_at: 2026-10-12 16:18
boardidx: 59392
---

`ait artifact rm` reports `0 orphan blob(s) swept` and leaves git-tracked local
blobs behind when the manifest's **current** backend is not `local` — even when
those blobs originated on `local` and are still committed on the data branch.

## Observed

During the t1142 manual-verification run:

1. `ait artifact create 1142 mv1.txt --backend local` + `ait artifact update`
   → two versions, both blobs committed under
   `.aitask-data/attachments/blobs/97/...` and `.../e7/...`.
2. `ait artifact move art:t1142-movetest --to dir` (source blobs on `local` are
   deliberately NOT deleted — documented behavior).
3. `ait artifact rm 1142 art:t1142-movetest`:
   ```
   Warning: backend 'dir' is not local — backend blobs were not deleted
            (cross-backend orphan reaping is t1135)
   Removed artifact art:t1142-movetest from t1142
            (manifest deleted, 0 orphan blob(s) swept; ...)
   ```
4. Both local blobs are still present and still tracked. They were removed by
   hand before archiving t1142.

## Why it matters

The `dir`-side blobs being left is the known, documented gap (t1135 —
cross-backend orphan reaping). This is a **different** leak: the blobs on
`local` are exactly the ones `rm` already knows how to sweep, and they are
git-tracked, so every leaked blob is permanent weight on the data branch. The
decision to skip the sweep appears to key off the manifest's current backend
rather than off where each blob actually lives.

`move` leaving source blobs behind is intentional, so this combination
(`create --backend local` → `move --to <remote>` → `rm`) is a normal lifecycle,
not an exotic one.

## Where to look

- `.aitask-scripts/aitask_artifact.sh` — `cmd_remove` / `_artifact_rm_txn`
  (around line 461): the branch that emits the "backend is not local" warning
  and short-circuits the orphan sweep.

## Acceptance

- `rm` sweeps local blobs that are unreferenced after removal, regardless of
  the manifest's current backend.
- The "cross-backend orphan reaping is t1135" warning still fires for blobs on
  the non-local backend (that gap stays open and correctly reported).
- The reported swept count matches what was actually removed.
- Covered by a test in `tests/test_artifact_cli.sh` walking the
  create-local → move-to-dir → rm lifecycle.

## Related

- t1135 — cross-backend orphan reaping (the adjacent, still-open gap).

## Source

Found incidentally during the t1142 verification run; recorded under "Upstream
defects identified" in `aiplans/archived/p1142_manual_verification_auto.md`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T09:34:57Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-12T13:13:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-12T13:18:14Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:253e1b24f4648e9c

> **✅ gate:risk_evaluated** run=2026-10-12T13:18:14Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1286/risk_evaluated_2026-10-12T13:18:14Z-risk_evaluated-a1.log`

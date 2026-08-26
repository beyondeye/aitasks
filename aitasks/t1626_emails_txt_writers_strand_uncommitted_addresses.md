---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness, task_metadata, concurrency]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-26 14:40
updated_at: 2026-08-26 17:21
---

## Origin

Spawned from t1614 during Step 8b review. t1614 fixed `store_email()`'s masked
append; these are two *separate*, pre-existing defects in the same file pair
that t1614 did not touch and could not fix in scope.

Both were reproduced live against a throwaway fixture, and defect 1 was
additionally reproduced against the **pre-t1614** `store_email` body — so
neither is a t1614 regression.

## Upstream defect

- `.aitask-scripts/aitask_pick_own.sh:536-565 — store_email() runs (Step 2) before acquire_lock() (Step 3), and a refused lock exits at line 565 before commit_and_push() at line 601, so a claim refused with LOCK_FAILED / LOCK_LIVE_HOLDER / LOCK_UNVERIFIABLE_HOLDER leaves its appended address uncommitted. A retry with the SAME address then hits the membership fast-path at line 253 and returns before EMAIL_STORED is set, so no later claim ever commits it — emails.txt stays dirty indefinitely. Existing Test 4 in tests/test_pick_own_scoped_commit.sh cannot expose it because it retries with a DIFFERENT address, which legitimately sets the flag and sweeps the stranded line along incidentally. The comment at lines 562-564 ("Nothing was claimed … there is no state to roll back here") is inaccurate for the same reason: emails.txt may already have been mutated by then.`
- `.aitask-scripts/aitask_create.sh:1134-1177 — add_email_to_file() appends to emails.txt, but aitask_create.sh never commits that file (no task_git add names EMAILS_FILE), and since t1599_1 scoped every claim commit to its own paths nothing sweeps it either. A later store_email() hits the same membership fast-path, so `ait create --assigned-to <new address>` appears to leave the address uncommitted and emails.txt dirty indefinitely — the same stranding shape on the other writer.`

## Diagnostic context

Both defects share one root shape: **an append with no guaranteed commit, plus a
membership fast-path that makes the append unrepeatable.** Once the address is on
disk, `grep -qxF -- "$email" "$EMAILS_FILE" && return 0` short-circuits every
later call before the "this claim owns the list" flag can be set, so the one
code path that would have committed it never runs again.

Reproduction for defect 1 (real scripts, paired bare remote + clone):

1. `aitask_lock.sh --lock 1 --email bob@test.com`
2. `aitask_pick_own.sh 1 --email mallory@test.com` → `LOCK_FAILED`, but
   `emails.txt` now carries mallory and is ` M` dirty.
3. Unlock, then `aitask_pick_own.sh 1 --email mallory@test.com` → `OWNED:1`,
   **0** `ait: Record contributor email` commits, `HEAD:emails.txt` still only
   `seed@test.com`, file still ` M`.
4. A third claim with the same address — still dirty, still zero commits.

Identical output when steps 2-4 run against the pre-t1614 `store_email` body,
which is what establishes it as pre-existing.

t1614's own fix is orthogonal: it changed only the inside of the
`{ … } || rc=$?` group and the post-release warning. It touched neither the
`store_email` → `acquire_lock` ordering nor the membership fast-path.

## Suggested fix

Likely directions, to be decided during planning:

- **Defect 1:** commit the contributor list before the lock gate can refuse, or
  move `store_email` after a successful `acquire_lock` so a refused claim never
  writes at all. The latter is probably cleaner — it also makes the lines 562-564
  comment true — but changes when a genuinely new address gets recorded.
- **Defect 2:** give `aitask_create.sh` a path-scoped commit of `EMAILS_FILE`,
  mirroring `_commit_scoped "ait: Record contributor email"` in
  `aitask_pick_own.sh:449-452`.
- Whatever shape is chosen, make the membership fast-path not permanently
  swallow an uncommitted address — that is the property that turns a one-off
  write failure into a permanent one.

## Verification

- A test for the **same-address** retry after a refused claim — the gap Test 4
  cannot cover. Assert that after `LOCK_FAILED` + retry with the same address,
  `emails.txt` is clean and the address is present at `HEAD`.
- A test that `ait create --assigned-to <new address>` leaves `emails.txt` clean.
- Negative controls for both, in the executable-injection style already used by
  `install_prefix_store_email` / `install_prefix_add_email_to_file`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-26T14:21:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-26T15:08:19Z status=pass attempt=1 type=human

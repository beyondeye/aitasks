---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [1608]
issue_type: bug
status: Done
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
created_at: 2026-08-25 19:02
updated_at: 2026-08-26 14:43
completed_at: 2026-08-26 14:43
---

## Origin

Spawned from t1608 during Step 8b review. t1608 fixed this exact defect on the
`ait create` side; this task applies the same correction to the other writer.

## Upstream defect

- `.aitask-scripts/aitask_pick_own.sh:270-277` — `store_email()` masks a failed
  append, and additionally reports a write that never happened.

```bash
    local rc=0
    {
        # Re-check under the lock: a holder we waited on may have added it.
        if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE"
            sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
            EMAIL_STORED=true
        fi
    } || rc=$?
```

Bash **suppresses errexit inside a group whose status is tested by `|| rc=$?`**,
so a failed `printf … >> "$EMAILS_FILE"` does not abort the block. Execution
continues to `sort -u … -o …`, which succeeds, and the group's status is the
last command's — `0`. Two consequences:

1. `rc` stays `0`, so the `warn "store_email: failed to record …"` on the line
   after the release never fires. The claim reports success for an address that
   was never written.
2. `EMAIL_STORED=true` is set on that same path. That flag is what tells
   `aitask_pick_own.sh` the contributor list is this claim's to persist, so the
   claim goes on to commit an **unchanged** `emails.txt` under
   `ait: Record contributor email` — a commit with no content change,
   attributed to a write that failed.

This predates t1608 (it arrived with the mutex in t1599_1) and did not block
t1608's create-side fix.

## Suggested fix

Apply the same correction t1608 made to `add_email_to_file()` in
`.aitask-scripts/aitask_create.sh` — chain the two operations so the append's
failure becomes the group's status, and move the flag behind the chain so it
cannot be set for a write that did not happen:

```bash
            printf '%s\n' "$email" >> "$EMAILS_FILE" &&
                sort -u "$EMAILS_FILE" -o "$EMAILS_FILE" &&
                EMAIL_STORED=true
```

## Verification

Mirror **Test 6** of `tests/test_create_email_lock.sh` (added by t1608), which
is the shape that discriminates this branch:

- Force the **append alone** to fail while `sort` still succeeds. A PATH shim
  cannot do it — `printf` is a bash builtin — and permissions cannot either: a
  mode that blocks the append blocks `sort -o` on the same file too, so both
  fail and the branch is never isolated. Shadow the builtin with a function
  guarded on `${FUNCNAME[1]} == store_email`, injected into the fixture's copy
  of the script ahead of its final `main "$@"` line (the
  `install_prefix_commit_and_push` technique in
  `tests/test_pick_own_scoped_commit.sh`).
- Assert: the `store_email: failed to record` warning **is** emitted;
  `emails.txt` is byte-unchanged and the address is absent; **no**
  `ait: Record contributor email` commit was made; and the claim itself still
  succeeds (`OWNED:<id>`) — the best-effort contract.
- Negative control: with the pre-fix body, the warning is absent and the
  contributor-email commit **is** made. Assert that positively, so an injection
  that silently failed cannot pass.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-26T08:21:42Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-26T11:14:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-26T11:43:09Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a65a3b6a343419fb

> **✅ gate:risk_evaluated** run=2026-08-26T11:43:09Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1614/risk_evaluated_2026-08-26T11:43:09Z-risk_evaluated-a1.log`

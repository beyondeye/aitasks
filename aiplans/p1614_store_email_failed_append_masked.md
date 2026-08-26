---
Task: t1614_store_email_failed_append_masked.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1614 — store_email() masks a failed append

## Context

`aitasks/metadata/emails.txt` has exactly two writers. t1608 fixed a
status-masking defect in one of them (`add_email_to_file()` in
`.aitask-scripts/aitask_create.sh`); this task applies the same correction to
the other, `store_email()` in `.aitask-scripts/aitask_pick_own.sh:270-277`.

Bash suppresses errexit inside a group whose status is tested by `|| rc=$?`, so
in:

```bash
    local rc=0
    {
        if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE"
            sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
            EMAIL_STORED=true
        fi
    } || rc=$?
```

a failed `printf … >>` does not abort the block. Execution continues to
`sort -u`, which succeeds, `EMAIL_STORED=true` is set, and the group's status is
the last command's — `0`. So `rc` stays `0` and the
`warn "store_email: failed to record …"` on the line after the release never
fires: **the claim silently reports success for an address that was never
written.**

### Ground truth (verified by spike, not assumed)

I reproduced each path in a throwaway fixture (real `aitask_pick_own.sh`, the
failure injected the way the sibling suite already does it) and observed:

**(1) Pre-fix, append fails** (`printf` shadowed inside `store_email`):

| observable | clean `emails.txt` | already-dirty `emails.txt` |
|---|---|---|
| `store_email: failed to record` warning | **absent** (the defect) | **absent** (the defect) |
| the address is written | no | no |
| `sort -u` still runs and rewrites the file | yes (content identical, so invisible) | **yes — file is re-sorted** |
| `ait: Record contributor email` commit | **not made** | **made** |

**(2) The task's literal fix, append succeeds / `sort` fails** (`sort` PATH
shim, the `test_create_email_lock.sh` Test 5 technique). With
`printf && sort && EMAIL_STORED=true`, the flag stays **false** on this path:
the address is appended to disk, no contributor-email commit is attempted, and
`emails.txt` is left dirty. A **later claim by the same address never rescues
it** — `store_email`'s membership fast-path (`grep -qxF … && return 0`) finds it
already present in the working-tree file and returns before the flag is ever
set. Spiked over two consecutive claims: `HEAD:emails.txt` still held only
`seed@test.com`, and `emails.txt` was still ` M` dirty. The address is stranded
permanently, and the working tree never comes clean.

That is a **regression against the pre-fix code**, which on this path set the
flag and did commit the address. `sort -u FILE -o FILE` can fail on a full or
read-only filesystem, so the path is reachable — the sibling suite already
tests it (`test_create_email_lock.sh` Test 5).

### Two corrections this plan makes to the task's stated Verification

1. The task predicts the false `EMAIL_STORED=true` makes the claim "commit an
   **unchanged** `emails.txt`". It does not, on a clean list: `_commit_scoped()`
   (`aitask_pick_own.sh:420-437`) runs `git status --porcelain -- <paths>` and
   returns 2 without committing when the path is clean. So "no
   `ait: Record contributor email` commit was made" is **vacuous as a fix-side
   assertion** — it holds pre-fix too, and a negative control built on it could
   not fail. The lie *is* observable, but only when the list is already dirty
   from a concurrent session (the interleaving Test 7 of
   `tests/test_pick_own_scoped_commit.sh` already establishes as real). The
   tests below move that assertion to the state where it discriminates.
2. The task prescribes the chain order `printf && sort && EMAIL_STORED=true`.
   Taken literally that introduces the stranding regression in (2) above, so
   Step 1 orders the chain `printf && EMAIL_STORED=true && sort` instead and
   states the semantics explicitly.

## Step 1 — Fix `store_email()`

`.aitask-scripts/aitask_pick_own.sh`, inside the `{ … } || rc=$?` group
(currently lines 272-278).

**Chosen semantics: `EMAIL_STORED` tracks the *append*, not the sort.** The
append is the write; `sort -u` is normalization of a file whose content is
already correct either way. The flag's documented contract (line 240) is "did this
call actually add a new address" — if the append landed, it did, and the claim
owes that file a commit whether or not the sort that followed succeeded.

```bash
    local rc=0
    {
        # Re-check under the lock: a holder we waited on may have added it.
        if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            # CHAINED ON PURPOSE (t1614, mirroring t1608's add_email_to_file).
            # errexit is suppressed inside a group tested by `|| rc=$?`, so as
            # three statements a failed append followed by a succeeding sort
            # leaves the group's status at 0 — reporting success for an address
            # that was never written.
            #
            # ORDER MATTERS. EMAIL_STORED sits between the append and the sort,
            # not after both: it is what tells commit_and_push the contributor
            # list is this claim's to commit, and the APPEND is the write it
            # answers for. Behind the sort as well, a normalization failure
            # would leave this address appended, uncommitted and dirty forever
            # — the next call's membership fast-path finds it already present
            # and returns before the flag is ever set again (t1614).
            printf '%s\n' "$email" >> "$EMAILS_FILE" &&
                EMAIL_STORED=true &&
                sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
        fi
    } || rc=$?
```

`EMAIL_STORED=true` is an assignment, so it always exits 0 — the group's status
still reflects the append, then the sort. Failed append → short-circuits at
`printf`, flag false, `rc=1`. Append ok / sort fails → flag true, `rc=1`.

Then make the warning below the lock release say which of the two happened —
the flag already encodes it, and "failed to record" is untrue for an address
that was in fact appended and is about to be committed:

```bash
    registry_lock_release "$lockdir"
    if [[ $rc -ne 0 ]]; then
        if [[ "$EMAIL_STORED" == true ]]; then
            # The append landed and will be committed; only the normalization
            # was lost. Report the OBSERVED failure and the one thing that is
            # certain (the address was added) — do NOT claim the file is now
            # unsorted: a failed `sort -u` does not establish that, since an
            # appended address may already be in lexical order.
            warn "store_email: recorded ${email}, but normalizing the contributor list failed (rc=$rc)"
        else
            warn "store_email: failed to record ${email} (rc=$rc)"
        fi
    fi
```

This does not break parity with `add_email_to_file`: `aitask_create.sh` never
commits `emails.txt` at all (verified — no `task_git add` names `EMAILS_FILE`),
so that function has no flag and no commit responsibility, and one message is
right for it.

Also update the function's header comment (line 240) so "Sets
`EMAIL_STORED=true` only when this call actually adds a new address" names the
append as the predicate.

## Step 2 — Tests

All new tests go in `tests/test_pick_own_scoped_commit.sh`, which already owns
the `EMAIL_STORED` → contributor-email-commit relationship (Tests 4-8) and
supplies the fixture (`setup_paired_repos`), the helpers (`assert_non_empty`,
`head_files`, `claim_commits_touching`) and the script-rewrite injection
technique (`install_prefix_commit_and_push`). This mirrors t1608, which put its
Test 6 inside the existing `tests/test_create_email_lock.sh` rather than forking
a file.

### New fixture helpers

- `install_failing_append <tmpdir>` — shadow the `printf` **builtin** with a
  function guarded on `${FUNCNAME[1]} == store_email`, injected ahead of the
  fixture copy's final `main "$@"` line. A PATH shim cannot reach a builtin, and
  permissions cannot discriminate — a mode that blocks the append blocks
  `sort -o` on the same file, so both would fail and the branch would never be
  isolated. The `FUNCNAME[1]` guard keeps every other `printf` in the script
  (including the one inside `warn`) intact.
- `install_failing_sort <dir>` — PATH shim for `sort` that exits 1 only when the
  argv carries both `-o` and a path ending in `emails.txt`, else `exec`s the
  real binary resolved before the PATH prepend. Lifted from
  `test_create_email_lock.sh` Test 5.
- `install_prefix_store_email <tmpdir>` — append the **pre-fix** `store_email`
  body (three unchained statements, single warning) ahead of `main "$@"`, so the
  negative control is executable on every run instead of expiring once the fix
  lands.

### Test sequence

The file currently ends at Test 9 (negative control) + Test 10 (syntax). The
four new tests are inserted before the syntax check, which is **renumbered
10 → 14**. Final order: 1-9 unchanged, then:

- **Test 10 — fixed; append fails, clean list.** `install_failing_append`, claim
  t1 with `--email alice@test.com`. Assert: the `store_email: failed to record`
  warning **is** emitted (the discriminating assertion — pre-fix it is absent);
  `emails.txt` byte-unchanged and `alice@test.com` absent; no
  `ait: Record contributor email` commit; the claim still succeeds (`OWNED:1`)
  and its own claim commit landed — the best-effort contract.
- **Test 11 — fixed; append fails, dirty list.** Same, but append
  `bob@test.com` to `emails.txt` uncommitted first. Assert: `emails.txt`
  byte-unchanged **including order** (still append-order `seed`,`bob` — not
  re-sorted, proving `sort -u` was skipped); still no
  `ait: Record contributor email` commit, i.e. `EMAIL_STORED` stayed false.
  Test 10 alone cannot pin this: a fix that emits the warning but still sets the
  flag would pass it.
- **Test 12 — fixed; append succeeds, `sort` fails (the partial-success path).**
  `install_failing_sort`, claim t1 with `--email alice@test.com`. Assert:
  `alice@test.com` **is** on disk; the
  `normalizing the contributor list failed` warning is emitted and the
  `failed to record` wording is **not** (the two messages are disjoint
  substrings, so each assertion discriminates); an `ait: Record contributor email`
  commit **is** made and contains `alice@test.com`; `emails.txt` is **clean** in
  `git status` afterwards. Then remove the shim, claim t2 with the same address,
  and assert the tree stays clean and `HEAD:emails.txt` still carries her — the
  stranding scenario, pinned as fixed.
- **Test 13 — NEGATIVE CONTROL, pre-fix body** (`install_prefix_store_email`),
  three sub-cases, each asserting the defect **positively** so a silently-failed
  injection cannot pass:
  - *13a, append fails, clean list*: `OWNED:1` reached (the control ran to
    completion) and the `store_email: failed to record` warning is **absent**.
  - *13b, append fails, dirty list*: `emails.txt` **was** rewritten (re-sorted
    to `bob`,`seed`) and an `ait: Record contributor email` commit **is** made
    that does **not** contain `alice@test.com` — a commit attributed to a write
    that failed.
  - *13c, append succeeds, `sort` fails*: **no** warning of either wording is
    emitted — the pre-fix code was silent on this path too.
- **Test 14 — syntax** (the existing Test 10, renumbered; body unchanged).

## Verification

```bash
bash tests/test_pick_own_scoped_commit.sh     # expect ALL TESTS PASSED
bash tests/test_create_email_lock.sh          # the sibling writer, unregressed
shellcheck .aitask-scripts/aitask_pick_own.sh
bash -n .aitask-scripts/aitask_pick_own.sh
```

Then the discriminating check by hand: in a scratch copy, revert Step 1 to each
of the two wrong shapes and confirm the right tests fail —
`printf; sort; EMAIL_STORED=true` (unchained) must fail Tests 10/11, and
`printf && sort && EMAIL_STORED=true` must fail Test 12. A test that passes
against every candidate body pins nothing.

Step 9 (Post-Implementation) handles merge, gate run and archival as usual.

## Note for Step 8b (upstream defect, out of scope here)

`aitask_create.sh` appends to `emails.txt` via `add_email_to_file()` but never
commits it — no `task_git add` in that script names `EMAILS_FILE`. Since
t1599_1 scoped every claim commit to its own paths, nothing sweeps it up either,
and a later `store_email()` hits the same membership fast-path and returns
early. So `ait create --assigned-to <new address>` appears to leave
`emails.txt` dirty and the address uncommitted indefinitely — the same stranding
shape, on the other writer. Carried into the Final Implementation Notes below
for follow-up; not fixed here.

## Risk

### Code-health risk: low
- The `&&` chain makes a failed append skip `sort -u`, so a pre-existing
  unsorted `emails.txt` is no longer opportunistically re-sorted on that path.
  That is the intended "leave the file untouched on failure" behavior, not a
  regression. · severity: low · → mitigation: inline — Test 11 pins the file as
  byte-unchanged, order included
- Splitting the warning into two messages adds a branch to a best-effort path.
  Both wordings are asserted, so neither can rot silently, and neither asserts a
  file state it has not observed — the sort-failure message reports the failed
  normalization and the completed append only, never that the file is unsorted
  (a failed `sort -u` does not establish that). · severity: low ·
  → mitigation: inline — Tests 10 and 12 pin one wording each, 13c pins the
  pre-fix silence
- Change is confined to one function in one script and changes no caller
  contract; the all-succeed path is behaviorally identical. · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low
- The task's Verification asserts "no `ait: Record contributor email` commit was
  made" as the fix-side discriminator and "the commit **is** made" as the
  negative control. Verified by spike: on a clean list that commit is suppressed
  pre-fix too by `_commit_scoped`'s empty-status guard, so taken literally the
  control could not fail. · severity: medium · → mitigation: inline — Tests 11
  and 13b relocate that assertion to the dirty-list state where it discriminates
- The task's prescribed chain order strands an appended address permanently when
  `sort` fails, which the append-failure tests cannot see. · severity: medium ·
  → mitigation: inline — Step 1 reorders the chain and Test 12 pins the
  partial-success path over two consecutive claims
- `EMAIL_STORED`'s placement is not pinned by the warning assertion alone: a fix
  that emits the warning but leaves the flag a separate statement would pass
  Test 10. · severity: medium · → mitigation: inline — Tests 11 and 13b pin the
  flag in both directions

## Final Implementation Notes

- **Actual work done:** `store_email()` in `.aitask-scripts/aitask_pick_own.sh`
  now chains `printf >> && EMAIL_STORED=true && sort -u`, so a failed append
  becomes the `{ … } || rc=$?` group's status and the flag cannot be set for a
  write that did not happen. The post-release warning splits into two accurate
  messages (`failed to record` vs `recorded <email>, but normalizing the
  contributor list failed`). `tests/test_pick_own_scoped_commit.sh` gained three
  fixture helpers (`install_prefix_store_email`, `install_failing_append`,
  `install_failing_sort`) and Tests 10-13; the syntax check renumbered 10 → 14.
  Final: 69 passed / 0 failed, and the sibling `test_create_email_lock.sh` 35/0.

- **Deviations from plan:** none. The plan itself deviated deliberately from the
  task's stated Verification in two places, both documented in its Context
  section and both driven by spiked ground truth: (1) "no contributor-email
  commit" is vacuous as a fix-side discriminator on a clean list, because
  `_commit_scoped()`'s empty-status guard suppresses that commit pre-fix too, so
  the assertion moved to the dirty-list state (Tests 11 / 13b); (2) the task's
  prescribed chain order `printf && sort && EMAIL_STORED=true` strands an
  appended address permanently when `sort` fails, so the flag sits between the
  append and the sort instead.

- **Issues encountered:** none blocking. The discriminating check was run as
  planned — reverting to each wrong shape in a scratch copy fails exactly the
  intended tests: unchained → Tests 10/11/12; `printf && sort && flag` → Test 12
  only, including `12b: emails.txt is still clean — never stranded dirty`
  reporting ` M aitasks/metadata/emails.txt`. The scratch revert was restored
  from a scratchpad copy and checksum-verified, never via `git checkout`, which
  would have destroyed the uncommitted fix.

- **Key decisions:** `EMAIL_STORED` answers for the **append**, not the sort.
  The append is the write; `sort -u` is normalization. Placing the flag behind
  the sort as well would leave a successfully-appended address uncommitted and
  dirty forever, because the next call's membership fast-path finds it already
  present and returns before the flag can be set again. The sort-failure warning
  deliberately reports only what was observed (normalization failed) and what is
  certain (the address was added) — it does not claim the file is now unsorted,
  which a failed `sort -u` does not establish.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_pick_own.sh:536-565 — store_email() runs (Step 2) before acquire_lock() (Step 3), and a refused lock exits at line 565 before commit_and_push() at line 601, so a claim refused with LOCK_FAILED / LOCK_LIVE_HOLDER / LOCK_UNVERIFIABLE_HOLDER leaves its appended address uncommitted. A retry with the SAME address then hits the membership fast-path at line 253 and returns before EMAIL_STORED is set, so no later claim ever commits it — emails.txt stays dirty indefinitely. Reproduced: refused claim → OWNED on retry → 0 contributor-email commits, emails.txt still ` M`, and still dirty after a third claim. PRE-EXISTING, not a t1614 regression — reproduced identically against the t1608-era store_email body. Existing Test 4 cannot expose it because it retries with a DIFFERENT address, which legitimately sets the flag and sweeps the stranded line along incidentally. The comment at lines 562-564 ("Nothing was claimed … there is no state to roll back here") is inaccurate for the same reason: emails.txt may already have been mutated.`
  - `.aitask-scripts/aitask_create.sh:1134-1177 — add_email_to_file() appends to emails.txt, but aitask_create.sh never commits that file (no task_git add names EMAILS_FILE), and since t1599_1 scoped every claim commit to its own paths nothing sweeps it either. A later store_email() hits the same membership fast-path, so `ait create --assigned-to <new address>` appears to leave the address uncommitted and emails.txt dirty indefinitely — the same stranding shape on the other writer.`

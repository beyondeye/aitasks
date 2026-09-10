---
Task: t1747_2_automerge_rebase_skip_probe.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Sibling Tasks: aitasks/t1747/t1747_3_sync_authorization_probes.md, aitasks/t1747/t1747_4_setup_dirty_baseline_probe.md, aitasks/t1747/t1747_5_published_history_amend_probes.md, aitasks/t1747/t1747_6_lock_and_reservation_probes.md, aitasks/t1747/t1747_7_manual_verification_sweep_failopen_git_probes.md
Archived Sibling Plans: aiplans/archived/p1747/p1747_1_failopen_probe_audit_doc.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-10 12:35
---

# t1747_2 — `ait_automerge_advance` must not discard a commit on an unverified assumption

## Context

Audit rows **A1 + A2** of the t1747 fail-open git-probe sweep (rule, fix shape and
dispositions: `aidocs/framework/failopen_git_probes.md`). The highest-severity site
in the sweep — the fail-open outcome is a **discarded commit**, on the framework's
hottest path: both `pull --rebase` drivers reach it (`ait sync::do_pull_rebase` and
every pick/push via `lib/task_utils.sh::_task_pull_rebase_cleanup`).

`lib/task_automerge.sh::ait_automerge_advance` reads the unresolved-file probe as
`… 2>/dev/null || true`, so a failed probe yields `""`, reads as "nothing unresolved
— this is an empty patch", and runs **`git rebase --skip`**, which permanently drops
the commit being replayed.

> **Citations below are anchored on `file::function`, with line numbers as a
> secondary hint as of `9cb61927c`.** `main` advanced *during this planning pass*
> (t1725_3, t1760 landed): the sync consumer moved `:1002 → :1555` mid-session.
> `lib/task_automerge.sh` itself was untouched by those commits.

### What this verification pass established

Measured in live branch-mode fixtures on this box (git **2.55.0**):

1. **The plan's third call-site citation was wrong** (confirmed — note from t1747_1).
   `lib/task_utils.sh:1216` is inside the `_ait_load_automerge` lazy-loader comment
   block, not a consumer. The real site is `_task_pull_rebase_cleanup` — loop call
   `:1346`, the rc-1/rc-2 comment `:1352-1354`, the verified abort `:1359`. The
   *argument* holds; only the pointer was stale.

2. **The `--skip` fallback's stated premise no longer holds.** Its comment claims it
   exists for "when the auto-merge result matches the current HEAD exactly, git sees
   'nothing to commit'". On git 2.55 that case makes `rebase --continue` **succeed**
   (rc 0) and git drops the empty commit itself — verified in a minimal repo. So on
   modern git the fallback is reached **only** when `--continue` fails for some other
   reason, i.e. on a commit with real content.

3. **A1, reproduced end to end:** with `rebase --continue` injected to fail,
   `ait sync --batch` printed `AUTOMERGED`, **exited 0**, left no wedge — and the
   local commit was **gone**, its merged content with it. The probe had *succeeded*;
   `""` was the truthful answer to "anything unresolved?" and still authorised the
   destructive path.

4. **A2's loop-entry route is live, and worse than the plan recorded.** Failing the
   unresolved-file probe from the *second* call onward (the first is
   `do_pull_rebase`'s own, so the run still enters the loop): the merge driver was
   **never invoked**, `--continue` and `--skip` were both attempted, the local commit
   was **gone**, and the run reported `AUTOMERGED` at **rc 0**. The earlier draft of
   this plan called this consumer "covered downstream, no live fixture" — that was
   wrong on both counts, and it is now Test 14.

**User decision (this session):** fix the probe *and* verify the emptiness claim.
`"nothing unresolved"` is not `"empty patch"` — the task body names that exact
conflation, so closing it is the same defect, not scope creep.

## Scope: two files

`.aitask-scripts/lib/task_automerge.sh` and `tests/test_sync_branch_mode_automerge.sh`.
**`aitask_sync.sh` is not edited** — its probes are rows A3/A4/A5/A10, owned by
**t1747_3**, which will be editing that file. Adding this task's convention markers
there would collide with that task and pre-empt its dispositions. Its consumer is
covered by the identity scan in Test 13 instead.

## Implementation

### 1. `lib/task_automerge.sh::ait_automerge_advance` (~:197-208)

```bash
ait_automerge_advance() {
    if GIT_EDITOR=true _ait_data_git rebase --continue &>/dev/null; then
        return 0
    fi
    # A failed probe must never authorise `rebase --skip` -- skipping DISCARDS
    # the replayed commit. Rule + dispositions:
    # aidocs/framework/failopen_git_probes.md
    local unresolved="" u_rc=0
    unresolved="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || u_rc=$?
    (( u_rc == 0 )) || return 1
    [[ -z "$unresolved" ]] || return 1

    # ... and "nothing unresolved" is NOT "empty patch": `--continue` fails for
    # other reasons too. Only skip a patch VERIFIED empty. `--quiet` exits
    # 0 = no difference, 1 = a real patch, >=2 = could not tell -- and
    # "could not tell" is not "empty".
    local e_rc=0
    _ait_data_git diff --cached --quiet HEAD >/dev/null 2>&1 || e_rc=$?
    (( e_rc == 0 )) || return 1

    _ait_data_git rebase --skip &>/dev/null && return 0
    return 1
}
```

`local unresolved="" u_rc=0` on its **own line** before the capture — under
`set -euo pipefail`, `local x="$(…)" || rc=$?` captures `local`'s status, not the
command's. The comments **point at** the doc rather than restating the rule
(t1747_1's convention).

### 2. A2 — `_ait_automerge_conflicted_now` (~:211) becomes tri-state

The canonical doc is unconditional: *"a helper change is only complete when its
**whole** call-site set has been enumerated and each consumer given an **explicit**
disposition for 'unverified'."* Finding 4 shows the loop-entry consumer is not merely
theoretical.

```bash
# Internal: the files git currently reports as unresolved.
#   0 — the list was read; empty output means "none unresolved"
#   2 — the probe could not be read; the empty output means NOTHING
# Rule + dispositions: aidocs/framework/failopen_git_probes.md
_ait_automerge_conflicted_now() {
    local out="" rc=0
    out="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || rc=$?
    (( rc == 0 )) || return 2
    printf '%s' "$out"
}
```

Both consumers are in this file and **must absorb the status** — under
`set -euo pipefail` a bare `conflicted="$(…)"` returning non-zero aborts the shell
mid-rebase, which is worse than fail-closed:

- **loop entry (~:236)** — `conflicted="$(…)" || c_rc=$?`; on `c_rc != 0` return **2**
  *before* `ait_automerge_files` and `ait_automerge_advance` are reached. Move the two
  `AIT_AUTOMERGE_*` initialisations **above** the probe so the globals are
  well-defined on that early return.
- **post-advance (~:273)** — same shape, same `return 2`. Behaviour unchanged; the
  reason is now recorded rather than inferred.

Extend the rc-2 doc-comment: *"the advance failed for a NON-conflict reason … **or
the unresolved-file probe could not be read**"*.

Each of the three call sites carries a one-line `# unverified: <disposition>` comment
— the convention Test 13 enforces (below).

### 3. Call-site table

| helper | consumer (`file::function`) | disposition on "unverified" |
|---|---|---|
| `ait_automerge_advance` | `task_automerge.sh::ait_automerge_rebase_loop` (~:263) | rc 1 ⇒ re-probe ⇒ rc 2 ⇒ caller aborts |
| `ait_automerge_advance` | `aitask_sync.sh::do_pull_rebase` (:1555) | `warn` + `rebase --abort` + `return 1` |
| `_ait_automerge_conflicted_now` | `…::ait_automerge_rebase_loop` — loop entry (~:236) | `return 2` ⇒ caller aborts, **before** any resolver or advance |
| `_ait_automerge_conflicted_now` | `…::ait_automerge_rebase_loop` — post-advance (~:273) | `return 2` ⇒ caller aborts |
| *(the loop's own consumers)* | `aitask_sync.sh::do_pull_rebase:1487`, `task_utils.sh::_task_pull_rebase_cleanup:1346` | rc 1 **and** rc 2 both abort — verified in-tree |

## Verification

Every fixture below was **built and run during this planning pass**; quoted outcomes
are measured, not predicted. Extend `tests/test_sync_branch_mode_automerge.sh`
(**48/48 green at `9cb61927c`**), reusing `setup_branch_mode_repos`, `strip_ansi`,
`assert_no_rebase_wedge`, and the argv-keyed shim shape of
`install_failing_advance_shim`.

### Fixtures and shims

- **P — legitimate empty patch.** local edits *only* `updated_at` (older); pc2 edits
  `priority` + a newer `updated_at`. Adjacent lines ⇒ real conflict; the driver
  resolves to pc2's file **exactly** ⇒ staged tree == HEAD. *Measured:* unshimmed,
  `--continue` succeeds and git drops the empty commit — so **P alone never reaches
  `--skip` on git 2.55**, which is why the task pre-authorises injection.
- **R — real patch.** the base fixture's adjacent-field conflict; merged result
  differs from HEAD. *Measured:* `diff --cached --quiet HEAD` ⇒ **DIFFERS**.
- Shims (all pass `--skip` and `--abort` through, or the abort this suite asserts
  could not run):
  - `install_continue_only_shim` — fails `rebase --continue` only. This is the state
    **old git (<2.26) produces natively** for an empty patch — no minimum git version
    is documented anywhere in the tree — so the case stays production-reachable.
  - `install_advance_probe_shim` — same, plus: once a `rebase --continue` has been
    *seen*, `diff --name-only --diff-filter=U` also fails. The scoping is
    load-bearing: `do_pull_rebase`'s own probe and the loop-entry probe must still
    succeed or the run never reaches `ait_automerge_advance`. Models an index.lock /
    unreadable git-dir appearing mid-rebase — exactly what makes `--continue` fail.
  - `install_first_probe_only_shim` — the **first** `diff --diff-filter=U` passes
    (that is `do_pull_rebase`'s own); every later one fails, so **loop entry** is the
    first unreadable probe. Also appends every git argv to a log and wraps the fixture's
    `board/aitask_merge.py` in a marker-writing shim, so "the resolver never ran" and
    "no advance was attempted" are directly observable rather than inferred.

### Tests — each half gets its own fixture *and* its own mutant

| # | fixture + shim | fixed code must | mutant control (fixture's copy only) |
|---|---|---|---|
| 10 | P + continue-only | `AUTOMERGED`, rc 0, no wedge, `--skip` **taken**. *Precondition:* an unshimmed control run of P succeeds and drops the commit — proving the patch is genuinely empty. | — (this **is** precondition (a) for Test 11) |
| 11 | P + probe shim | `ERROR:rebase_continue_failed`, rc≠0, no wedge, **`local: older ts only` still in `git log`**. *Precondition (b):* invoke the shim directly and assert `diff --diff-filter=U` exits non-zero. | restore `\|\| true` at **A1 only** ⇒ probe reads `""` ⇒ emptiness says EQUAL ⇒ `--skip` ⇒ `AUTOMERGED`, commit gone |
| 12 | R + continue-only | `ERROR:rebase_continue_failed`, rc≠0, no wedge, **`local: labels` still in `git log`**. *Precondition:* assert local's and pc2's files genuinely differ. | delete the **emptiness check only** (keep A1's rc capture) ⇒ `--skip` ⇒ `AUTOMERGED`, **commit gone** — the measured pre-fix behaviour |
| 13 | source scan | call-site identities match the table (below) | — |
| 14 | base fixture + first-probe-only shim | **rc 2 at loop entry:** `ERROR:rebase_continue_failed`, rc≠0, no wedge, `local: labels` still in `git log`, **resolver marker ABSENT**, and the git log contains **no `rebase --continue` and no `rebase --skip`** (only `--abort`). | restore `\|\| true` at **A2 only** ⇒ *measured today:* resolver never runs, `--continue` **and** `--skip` are both attempted, `AUTOMERGED` at **rc 0**, commit **gone** |

Tests 10 and 12 are a **matched pair**: same shim, same code path, opposite outcomes,
differing only in whether the patch is empty — that is what makes the emptiness check
demonstrably the discriminator rather than an assertion about the fixture.

**Test 14 is the A2 regression** the review asked for. Its assertions are chosen so a
typo in the status capture or in the initialisation order cannot pass: a shell that
dies mid-command-substitution prints no `ERROR:` token and leaves a wedge; a capture
that fails to return 2 lets the resolver marker appear and `--continue`/`--skip` into
the verb log; an early return before the globals are initialised is caught by the
same token assertion, since `set -u` would abort the caller.

**Test 13 — identities, not counts.** A small awk emits one
`file::function::helper` row per **call** site (definition lines and comment lines
excluded; function spans tracked via `^name() {` / `^}`), the rows are sorted **without
dedup**, and the resulting multiset is compared to the explicit expected set:

```
aitask_sync.sh::do_pull_rebase::ait_automerge_advance
lib/task_automerge.sh::ait_automerge_rebase_loop::ait_automerge_advance
lib/task_automerge.sh::ait_automerge_rebase_loop::_ait_automerge_conflicted_now
lib/task_automerge.sh::ait_automerge_rebase_loop::_ait_automerge_conflicted_now
```

Three guards make it non-vacuous and close the same-function hole the review named:

1. **Anti-empty:** assert the row count is exactly 4 **and** both helper *definitions*
   are found. A rename that empties the scan must fail, not pass silently.
2. **Multiplicity:** the two loop-internal probes are two rows, so removing one and
   adding another elsewhere in the same function changes the set only if the function
   differs — which guard 3 covers.
3. **Per-site disposition tag:** inside `lib/task_automerge.sh`, every call site must
   carry a `# unverified: …` comment within the 4 lines above it. A new consumer
   dropped into an already-listed function is bare, has no tag, and fails — with a
   message naming this table and `aidocs/framework/failopen_git_probes.md`.

**What it does not buy:** it does not check that a tag's *text* matches the actual
behaviour, and outside `lib/task_automerge.sh` (i.e. `aitask_sync.sh`, owned by
t1747_3) only the identity set applies, not the tag. Both are stated in the test
header rather than implied.

Both mutant installers follow `tests/test_fold_mark.sh::install_prefix_amend_probe`:
patch **`$TMP/local/.aitask-scripts/…`** (never the real repo), `sys.exit(1)` on a
stale anchor, re-grep to prove the substitution landed, and assert
`ait_automerge_advance` and its `rebase --skip` call survived — otherwise the control
observes "no guard" rather than "fail-open guard". Assert via `assert_defect_present`
(copy from `test_fold_mark.sh:1555`; it is **not** in `tests/lib/asserts.sh`).

Test bodies stay at top level (this file mutates `PASS`/`FAIL` in-process), so no
`assert_counters_init` opt-in is needed.

```bash
bash tests/test_sync_branch_mode_automerge.sh   # 48 green today; Tests 10-14 added
bash tests/test_sync.sh
shellcheck .aitask-scripts/lib/task_automerge.sh   # baseline: FULLY clean (not
                                                   # "clean apart from SC1091")
```

**Red proof, without a red commit:** write Tests 10-14 first, run them against the
unmodified `lib/task_automerge.sh` and confirm 11, 12 and 14 fail; then apply the fix
and confirm all five pass. Fix and tests land in **one commit**. The mutant controls
are the permanent form of that proof. Re-check `git status` immediately before
committing and use a path-scoped `aitask_task_commit.sh` — `main` already moved once
mid-session.

## Not in this task

`aidocs/framework/failopen_git_probes.md` rows A1/A2 cite `:203` / `:212`, which this
fix moves. The doc is a point-in-time audit anchored to `ec9641e79`; editing two rows
without moving that SHA would make it internally inconsistent, and the doc is
t1747_7's to reconcile. Send a **`./ait note` to t1747_7** instead (it already owns
the "spot-check five cited file:line references" checklist item), carrying: the moved
lines; findings 2 and 3 as a **new class** the grep-and-read audit could not see — a
*successful* probe answering a different question than the branch it gates; and
finding 4's measured evidence, which confirms the A2 row's "fail-open into A1" wording
concretely (silent `AUTOMERGED` at rc 0 with the commit discarded and the resolver
never invoked).

## Risk

### Code-health risk: low
- `_ait_automerge_conflicted_now` gains a non-zero return under `set -euo pipefail`;
  a consumer that does not absorb the status would abort the shell mid-rebase — worse
  than fail-closed. Both consumers are in-file and updated in the same change.
  · severity: low · → mitigation: inline — **Test 14** drives that exact path
  end-to-end (rc 2 at loop entry, no resolver, no advance, caller abort, no wedge),
  and Test 13's tag guard turns any new bare consumer red.
- Blast radius is one function plus one internal helper in one file; `rebase --skip`
  has exactly **one** call site tree-wide. Shellcheck baseline is fully clean and must
  stay so. · severity: low · → mitigation: none needed.

### Goal-achievement risk: low
- The emptiness check's **permit** direction is only demonstrable through an injected
  `--continue` failure, because on git 2.55 the legitimate empty-patch case never
  reaches `--skip` at all. Test 10 therefore proves the fallback still works *in the
  state old git produces*, not on the git running the suite. · severity: low ·
  → mitigation: none needed — that state is production-reachable on git <2.26, which
  the framework does not exclude, and the alternative is no permit coverage at all.
- `main` moved twice during this planning pass, so a cited line may drift again before
  the commit. · severity: low · → mitigation: none needed — every citation is anchored
  on `file::function` under a named SHA, and Test 13 enforces the identities rather
  than the line numbers.

**No `### Planned mitigations` block:** both dimensions are fully mitigated inside
this plan; a separate mitigation task would duplicate work landing with the fix.

## Post-Review Changes

### Change Request 1 (2026-09-10 15:04)
- **Requested by user:** Test 13 selects files with `grep -rlE … --include='*.sh'`; the
  review stated BSD grep on macOS "does not implement GNU --include" and asked for a
  portable `find` selection, preserving the scanner input and assertions.
- **Verification of the premise:** **false as stated.** The FreeBSD 15.1 `grep(1)`
  (2022-12-18) and the macOS `grep(1)` (Mac OS X 12, 2021-03-22) both document
  `--include`. **But** both pages also state *"Patterns are matched to the full path
  specified, not only to the filename component"*, whereas GNU grep matches
  `--include` against the basename only — so the two are not interchangeable, the
  BSD globbing detail is unspecified, and no CI job runs this suite on macOS
  (every workflow is `ubuntu-latest`) to catch a divergence. The remedy is therefore
  justified on that ground, not on the stated one.
- **Changes made:** `automerge_callsites` now selects files with
  `find "$root" -type f -name '*.sh' -exec grep -lE … {} +` (POSIX `-name` matches the
  basename on every platform), with a three-line comment naming why. The awk
  classifier, the expected table and every assertion are unchanged.
- **Files affected:** `tests/test_sync_branch_mode_automerge.sh`
- **Verified:** same-instant parity on the real tree — old vs new selection
  identical and non-empty (`aitask_sync.sh`, `lib/task_automerge.sh`); suite
  **108/108**, Test 13 and its scanner self-test green through the new selection;
  shellcheck warning classes unchanged.

## Final Implementation Notes
- **Actual work done:**
  - `lib/task_automerge.sh` (+62/−15): **A1** — `ait_automerge_advance` captures the
    unresolved-file probe's status; unreadable ⇒ `return 1`. **A1′** — `--skip` now also
    requires `diff --cached --quiet HEAD` rc 0 (staged tree == HEAD, i.e. a VERIFIED empty
    patch); rc 1 (real patch) and rc ≥ 2 (could not tell) refuse. **A2** —
    `_ait_automerge_conflicted_now` is tri-state (0 read / 2 unreadable); both consumers in
    `ait_automerge_rebase_loop` absorb it with `|| c_rc=$?` and return 2, the loop-entry one
    **before** any merge or advance, with the result globals initialised first. The rc-2
    contract comment now covers the unreadable probe. Each of the three in-file call sites
    carries an `# unverified:` disposition tag directly above it. Shellcheck fully clean.
  - `tests/test_sync_branch_mode_automerge.sh` (+516): Tests 10-14, 48 → **108** assertions.
    10 permit (verified-empty patch still skipped; unshimmed precondition proves emptiness);
    11 A1 + A1-only mutant; 12 A1′ + emptiness-only mutant; 13 function-anchored call-site
    identity multiset + anti-empty + per-site tag guard + scanner self-test; 14 A2 (rc 2 at
    loop entry: no resolver, no `--continue`, no `--skip`, caller abort, no wedge) + resolver
    marker control + A2-only mutant + full pre-fix control.
- **Deviations from plan:**
  - **Test 14's mutant cell conflated two halves.** The plan said an A2-only regression shows
    "`--continue` and `--skip` attempted, commit gone"; that outcome was measured on the build
    with **all** halves regressed. With A1 fixed, an A2-only regression still refuses `--skip`.
    Split into (a) an A2-only control asserting A2's own defect — an unread loop-entry probe
    **reaches the advance** (`rebase --continue` in the verb log) — and (b) a full pre-fix
    control (A1 + A1′ + A2 regressed) reproducing the measured loss: `AUTOMERGED`, rc 0,
    resolver never run, commit gone.
  - The three planned shims became one `install_advance_shim <bindir> <mode>`
    (`continue` / `continue+probe` / `late-probe`) sharing one git-argv log.
  - Post-review Change Request 1: Test 13 selects files with `find -name` (see above).
- **Issues encountered:**
  - `main` advanced three times mid-session and concurrent sessions dirtied unrelated paths.
    Each time I re-checked that nothing touched `lib/task_automerge.sh`, `aitask_sync.sh`,
    `lib/task_utils.sh`, `board/aitask_merge.py` or the test file, re-took the baseline
    (48/48 at `9cb61927c`), and committed by explicit pathspec only.
  - **Red proof:** against the unfixed source Tests 11, 12 and 14 failed with exactly the
    measured pre-fix outcome (`AUTOMERGED`, rc 0, `--skip` taken, commit gone); Test 10 was
    green before and after.
  - `run_all_python_tests.sh <path>` ran past 600 s (a positional path disables the lane and is
    forwarded to every phase); stopped it and ran the one module with pytest directly (51/51).
  - Regression suites green: `test_sync.sh` 42/42, `test_task_push.sh` 346/346 (the
    workflow-pull consumer), `test_sync_rebase_gate.sh` 30/30, `test_sync_protect_paths.sh`
    31/31, `test_sync_action_runner.py` 51/51.
- **Key decisions:**
  - **Scope widened by user decision** from the probe alone to verifying emptiness: on git ≥ 2.26
    `--continue` drops a truly empty commit itself, so every reachable `--skip` discarded a real
    commit even with a *readable* probe (reproduced end to end before the fix).
  - `aitask_sync.sh` deliberately untouched — its probes are rows A3/A4/A5/A10 (t1747_3); its
    consumer is pinned by identity only in Test 13.
  - A2 made an explicit tri-state rather than relying on a downstream catch, per the canonical
    doc's whole-call-site-set rule; Test 14 showed the loop-entry route was live.
  - Test 13 compares identities, not counts; a tag counts only in the comment block directly
    above its call, so a second call cannot borrow the first one's tag.
  - `--skip`'s permit direction is covered through an injected `--continue` failure — the state
    git < 2.26 produces natively — since on current git the legitimate case never reaches it.
- **Upstream defects identified:**
  - `tests/test_aitask_merge_boardgroup.sh:197-203 — Test 3's "every driver invocation passes --base-file" guard greps aitask_sync.sh for "$_MERGE_PYTHON" "$_MERGE_SCRIPT", which t1727 (66da94134) moved to lib/task_automerge.sh as "$_AIT_AUTOMERGE_PYTHON" "$_AIT_AUTOMERGE_SCRIPT"; it finds 0 invocations and fails 1/18 at HEAD dc755d85c independent of this task (replayed in a clean worktree). The moved invocation does pass base_args, so only the guard's target is stale.`
- **Notes for sibling tasks:**
  - **t1747_3:** `aitask_sync.sh::do_pull_rebase`'s own probe (A3) runs directly before
    `ait_automerge_rebase_loop`. The loop's entry probe now returns 2 when unreadable, so an A3
    refusal and an A2 refusal both land in sync's `case 2)` ⇒ `ERROR:rebase_continue_failed`.
    Test 13 pins `aitask_sync.sh::do_pull_rebase::ait_automerge_advance` by identity — if you
    move that call, update the table in the same commit.
  - Reusable test seams in the automerge suite: an argv-logging git shim that fails a verb only
    after a marker verb was seen, a merge-driver wrapper that proves "the resolver never ran",
    and exactly-once mutant installers (`_automerge_replace`, `_require`) that compose.
  - Grep-shape counts lie: `grep 'x[^|]*--include'` stopped at a `|` inside a quoted regex and
    reported zero files. The local `grep` on this box is ugrep 7.8.4, not GNU grep.
  - GNU grep matches `--include` against the basename, BSD/macOS against the full path; prefer
    `find -name` in portable test scanners.
  - `aidocs/framework/failopen_git_probes.md` rows A1/A2 still cite `:203` / `:212`; the probes now sit at `lib/task_automerge.sh:208` (A1) and `:234` (A2), as of this task's commit. Carried to t1747_7 by note rather than edited here (the doc is a point-in-time audit anchored to `ec9641e79`).

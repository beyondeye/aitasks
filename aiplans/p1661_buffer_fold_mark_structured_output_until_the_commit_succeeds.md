---
Task: t1661_buffer_fold_mark_structured_output_until_the_commit_succeeds.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1661 — Buffer fold-mark structured output until the commit succeeds

## Context

`.aitask-scripts/aitask_fold_mark.sh` performs the fold transaction in Steps
3–5b (primary `folded_tasks` update, per-task `status: Folded` / `folded_into`,
child removal from the original parent's `children_to_implement`, transitive
re-pointing, attachment/artifact transfer) and only then commits in Step 6.

Its four progress records — `PRIMARY_UPDATED:<id>` (:345), `FOLDED:<id>` (:353),
`CHILD_REMOVED:<p>:<c>` (:360), `TRANSITIVE:<id>` (:369) — are printed **as each
mutation happens**, i.e. before Step 6 runs. When Step 6 fails or refuses,
`_fold_rollback` (:590) undoes every mutation, but the records are already on
stdout. A stream consumer therefore observes progress for a transaction that no
longer exists.

t1599_2 made this routine rather than rare: `--commit-mode amend` now refuses
outright on a foreign task file in HEAD, unknown metadata, or an
already-published HEAD.

**Not a live defect today.** The exit code is authoritative, refusals go to
stderr, and every in-tree consumer keys off the terminal records only:
`aitask_create.sh:1912` discards stdout entirely (`>/dev/null`), and the
`aitask-fold` skill / `task-workflow` `planning.md` ad-hoc fold both parse for
`COMMITTED:<hash>`, which is emitted on success only. This is a robustness /
honesty fix.

**Chosen design: buffering** (the task's stated preference over a terminal
`ROLLED_BACK:` marker — a marker requires every consumer to opt in, and the ones
that don't are exactly the ones that get it wrong).

## Change 1 — `.aitask-scripts/aitask_fold_mark.sh`

### 1a. Record buffer helpers

Insert a delimited helper block after the lib sourcing (~line 35, before
`usage()`), i.e. **outside** the range that `install_prefix_commit_block` in
`tests/test_fold_mark.sh` excises:

```bash
# --- Structured-record buffer (t1661) ----------------------------------------
# Steps 3-5b describe mutations that Step 6 can still roll back, so their
# records are held here and flushed only when Step 6 reaches a terminal
# success. Every rollback path dies without flushing, so stdout never
# describes a transaction that no longer exists.
_fold_records=()
_fold_emit() { _fold_records+=( "$1" ); }
_fold_flush_records() {
    local r
    for r in ${_fold_records[@]+"${_fold_records[@]}"}; do printf '%s\n' "$r"; done
    _fold_records=()
}
# --- end structured-record buffer --------------------------------------------
```

The `${arr[@]+"${arr[@]}"}` guard matches the file's existing idiom for empty
arrays under `set -u`.

### 1b. Convert the four emission sites

`echo "X"` → `_fold_emit "X"` at :345 (`PRIMARY_UPDATED`), :353 (`FOLDED`),
:360 (`CHILD_REMOVED`), :369 (`TRANSITIVE`). No other stdout writer exists
between Step 3 and Step 6 (Step 5b's only `printf`s are `_fold_unique_name`'s
return values, captured by the caller).

### 1c. Flush at every terminal success in Step 6

Insert `_fold_flush_records` immediately **before** each terminal record, so
emission order is unchanged and the terminal record stays last:

| Step 6 arm | line | action |
|---|---|---|
| `fresh`, `crc=0` | :740 | flush, then `COMMITTED:<hash>` |
| `fresh`, `crc=2` (verified nothing to commit) | :744 | flush, then `NO_COMMIT` |
| `amend` success | :764 | flush, then `AMENDED` |
| `none` | :771 | flush, then `NO_COMMIT` |

The three failure exits (`fresh` `*)`, amend-guard refusal, amend-commit
failure) call `_fold_rollback` + `die` and **do not** flush.

`crc=2` and `none` are terminal *successes*: nothing is rolled back and the
mutations stand on disk (in `none` mode the caller commits them itself), so the
records describe real state.

### 1d. One-line consistency fix in the same block

The `*) die "invalid --commit-mode: $commit_mode"` arm (:774) is the only exit
in Step 6 that mutates and then dies **without** rolling back. Add
`_fold_rollback` before its `die`, matching the other three failure exits.
Keep the `die` line verbatim — `install_prefix_commit_block`
(`tests/test_fold_mark.sh:623`) uses that exact string as its excision-end
anchor.

### 1e. Header comment

Update the `Structured stdout` block (:14–19) to state the contract: the four
per-mutation records are buffered and flushed only on a terminal success
(`COMMITTED:` / `AMENDED` / `NO_COMMIT`); a rollback path emits no records at
all, so stdout only ever describes state that survived Step 6.

## Change 2 — `tests/test_fold_mark.sh`

Add to the file's header comment a `t1661` bullet describing the buffering
contract. Two shared helpers first:

- **`_run_fold_split <args...>`** — runs the script capturing **stdout and
  stderr separately** into `$FOLD_OUT` / `$FOLD_ERR` and setting `FOLD_RC`. The
  existing refusal tests use `2>&1`, which cannot tell a leaked record from a
  refusal message; every silence assertion below needs the split.
- **`_install_failing_pre_commit_hook`** — writes an executable
  `.git/hooks/pre-commit` that `exit 1`s. Neither commit site passes
  `--no-verify` (`task_utils.sh:243`, `aitask_fold_mark.sh:762`), the scaffold
  sets no `core.hooksPath`, and `task_git` is plain `git` in `$PWD` here — so
  this makes the commit itself fail *after* staging, which is the only way to
  reach the two post-staging failure exits. The hook releases the index, so
  `_fold_rollback` still works.

New/changed tests, registered in the runner list at the bottom. Tests 1a–1c
cover **all three** Step 6 failure exits; tests 2–5 cover **all four** flush
points.

1a. **`test_refused_amend_emits_no_records`** — `_setup_amend_fixture`, then the
   foreign-task-in-HEAD shape from `test_amend_refuses_foreign_task_in_head`
   (:410) — the guard-refusal exit, which happens *before* staging. Assert:
   `FOLD_RC` is 1; `FOLD_OUT` is empty and contains none of `PRIMARY_UPDATED:` /
   `FOLDED:` / `TRANSITIVE:`; `FOLD_ERR` carries the refusal text; then
   `assert_no_fold_residue` plus the restored-frontmatter checks (folded task
   back to `Ready`, no `folded_into`, primary has no `folded_tasks`) — the
   rollback half must stay pinned, not just the silence.

1b. **`test_fresh_commit_failure_emits_no_records`** — plain fresh fixture +
   `_install_failing_pre_commit_hook`, then `--commit-mode fresh 10 20`. This is
   `task_git_commit_scoped`'s `return 1` → the `*)` arm (:747). Assert exit 1,
   empty `FOLD_OUT`, `FOLD_ERR` says `fold commit failed`, HEAD unchanged, and
   the frontmatter restored.

1c. **`test_amend_commit_failure_emits_no_records`** — `_setup_amend_fixture`
   clean-HEAD shape (so the guard *permits* the amend) +
   `_install_failing_pre_commit_hook`, then `--commit-mode amend 10 20`. This is
   the amend-commit failure exit (:766), distinct from 1a's pre-staging refusal.
   Same assertions, `FOLD_ERR` says `fold amend-commit failed`.

2. **`test_fresh_flush_order_preserved`** — a fold that produces every record
   type (primary `10`, folded `20` and child `30_1`, plus a transitive via the
   `test_transitive` fixture shape at :201). Assert the **exact stdout line
   sequence**, not just membership: `PRIMARY_UPDATED:10`, the `FOLDED:` /
   `CHILD_REMOVED:30:1` / `TRANSITIVE:` records in their current order, and
   `COMMITTED:` last. This is what proves buffering neither drops nor reorders.

3. **`test_amend_flush_order_preserved`** — same assertion on a permitted amend
   (`_setup_amend_fixture` clean-HEAD shape), terminal record `AMENDED` last.

4. **`test_fresh_verified_noop_flushes_records`** — the `crc=2` flush point,
   which nothing else reaches. `task_git_commit_scoped` returns 2 when
   `git status --porcelain -- <paths>` is empty with rc 0 (`task_utils.sh:235`).
   Trigger it deterministically with `git update-index --assume-unchanged` on the
   fold's task files before the run: the mutations land on disk, git reports the
   paths clean, and the script takes the `2)` arm. Assert the **full ordered
   record set** followed by `NO_COMMIT`, and that the files really are mutated on
   disk (`t20` is `Folded`) — the records must be honest, not merely present.
   The assertion is self-proving: `NO_COMMIT` from a `fresh` invocation can only
   come from `crc=2` (`crc=0` prints `COMMITTED:`), so a fixture that failed to
   reach the branch fails the test rather than passing vacuously. If
   `--assume-unchanged` turns out not to suppress the status entry, fall back to
   `--skip-worktree`; the assertion catches either way.

   Production shape: this is the idempotent re-fold (mutations already landed,
   so the rewrite is byte-identical). That real path is clock-dependent —
   `aitask_update.sh` stamps `updated_at` to the current minute
   (`aitask_update.sh:644`, `:890`), so a re-run only produces an identical file
   within the same minute. The index bit is the deterministic stand-in for a
   genuinely reachable branch, not a synthetic one.

5. **Extend `test_none_mode_no_commit`** (:177) — assert the per-mutation
   records ARE emitted in `none` mode (it currently only checks `NO_COMMIT`),
   pinning that `none` is a flush point.

6. **`test_negative_control_unbuffered_records`** — mirrors the existing
   negative-control discipline (:603). A `python3` patch replaces the delimited
   helper block (1a) with the pre-fix unbuffered form:
   ```
   _fold_emit() { printf '%s\n' "$1"; }
   _fold_flush_records() { :; }
   ```
   Prove the injection landed (`grep -q '_fold_emit() { printf'` and the buffer
   array is gone; fail loudly otherwise, as `install_prefix_commit_block` does).
   Then re-run **two** of the failure fixtures against it — the amend-guard
   refusal (1a) and one post-staging commit failure (1b) — and use
   `assert_defect_present` to require that stdout **does** carry
   `PRIMARY_UPDATED:` in both. Without this, tests 1a–1c would pass against a
   build that simply never emits anything.

7. **Update `install_prefix_commit_block`'s injected `pre` string** (:624–653)
   to call `_fold_flush_records` before each of its terminal records. That
   helper rebuilds t1599_2's pre-fix Step 6 only; the build must stay t1661-fixed
   in every other respect. (Its three existing controls discard stdout, so this
   is correctness-of-the-fixture, not a behavior change for them.)

## Change 3 — `.claude/skills/task-workflow/task-fold-marking.md`

The reference doc (not rendered per-profile; no golden). In `## Structured
Output` (:22): state that the four per-mutation records are buffered and
flushed only when the commit step reaches a terminal success, and that a
refusal/rollback emits none of them. Two accuracy fixes in the same block while
there:

- `CHILD_REMOVED:<parent>_<child>` → `CHILD_REMOVED:<parent>:<child>` (the
  script emits a colon, :360).
- The commit-mode bullets still say `fresh`/`amend` "stage `aitasks/`"; since
  t1599_2 both are path-scoped to the fold's own file set and `amend` can refuse
  outright. Correct the wording and note the refusal.

No other consumer needs a change: `website/content/docs/workflows/create-tasks-from-code.md:97`
describes the script's effect, not its records, and the `aitask-fold` /
`task-workflow` skill surfaces only parse `COMMITTED:`.

## Verification

```bash
bash tests/test_fold_mark.sh                    # primary suite (incl. new tests + controls)
bash tests/test_fold_file_refs_union.sh         # asserts PRIMARY_UPDATED/TRANSITIVE on success
bash tests/test_gate_frontmatter_roundtrip.sh   # asserts PRIMARY_UPDATED:10 on success
shellcheck .aitask-scripts/aitask_fold_mark.sh
./.aitask-scripts/aitask_skill_verify.sh        # doc/stub surface unchanged but cheap to confirm
```

Manual sanity: in a scratch fixture, run `--commit-mode amend` against a HEAD
carrying a foreign task file and confirm `stdout` is empty while the frontmatter
is restored; then run `--commit-mode fresh` and confirm the full ordered record
set still appears.

Post-implementation (Step 9) handles cleanup, archival, and merge.

## Risk

### Code-health risk: low
- Buffering changes the *timing* of four `echo`s in a single 776-line script;
  the flush points are the four terminal records already present. Blast radius
  is one script plus its test file. · severity: low · → mitigation: TBD
- The negative control's `python3` excision anchors couple the test to the
  script's text. The helper block is placed outside that range and the
  `die "invalid --commit-mode: …"` anchor line is kept verbatim, but a future
  edit to Step 6 could still break the injection. · severity: low
  · → mitigation: TBD
- 1d (`_fold_rollback` on the invalid-mode arm) is an adjacent one-line fix, not
  strictly required by the task; it makes the "records only describe surviving
  state" contract true on every Step 6 exit. Called out explicitly rather than
  folded in silently. · severity: low · → mitigation: TBD
- A later edit could drop one flush point or move one onto a failure path while
  the rest of the suite still passes. Mitigated in-plan: tests 2/3/4/5 cover all
  four flush points (`crc=0`, `crc=2`, `amend`, `none`) and tests 1a/1b/1c cover
  all three failure exits, with the negative control proving both classes
  discriminate. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The consumer sweep the task asked for is complete and found no stream
  consumer: `aitask_create.sh:1912` discards stdout; the skill surfaces parse
  `COMMITTED:` only. So the contract change lands with no caller migration.
  · severity: low · → mitigation: TBD
- Whether `--commit-mode none` and the `crc=2` no-op count as flush points is a
  judgment call the task does not spell out. Both are treated as terminal
  successes because nothing is rolled back and the mutations persist; tests 4
  and 5 pin each decision independently. · severity: low · → mitigation: TBD

## Post-Review Changes

### Change Request 1 (2026-09-01 13:15)

- **Requested by user:** The Step 8 review flagged, as blocking, that the new
  script header and `task-fold-marking.md` claim "a run that emits no records
  made no lasting change" — but buffering only covers the Step 6 rollback paths.
  An abort *between* Steps 3 and 6 (e.g. a folded ID with no task file, whose
  `aitask_update.sh` exits non-zero under `set -e`) leaves earlier mutations on
  disk with no rollback, and now prints nothing. Either narrow the documented
  guarantee or make those failures transactional.

- **Verified:** CONFIRMED, and reproduced directly:
  `aitask_fold_mark.sh --commit-mode fresh 10 9999` against a fixture with no
  t9999 exited 1 with **empty stdout** while `aitasks/t10_primary.md` carried
  `folded_tasks: [9999]`. Buffering had moved the dishonesty rather than
  removing it.

- **Changes made:** Made the claim true instead of weakening it. Transactional
  rollback was rejected — `rollback_paths` is not assembled until after Step 5b,
  so an abort in Step 4 has no path set to restore, and building one early would
  reopen t1599_2's scoped-commit / amend-guard design.
  - `aitask_fold_mark.sh`: added `_fold_exit_flush` on an `EXIT` trap. It
    flushes the buffer on **any** exit that did not roll back; `_fold_rollback`
    now sets `_fold_rolled_back=true` to suppress it. On terminal success the
    buffer is already empty, so the trap is a no-op there.
  - Rewrote the header contract as three outcomes (terminal success / Step 6
    rollback / pre-Step-6 abort) and restated the guarantee as **per record**:
    a record on stdout means that mutation survives on disk; whether the *run*
    succeeded is the exit status's job.
  - `task-fold-marking.md`: same three-outcome wording.
  - `tests/test_fold_mark.sh`: added
    `test_abort_mid_mutation_flushes_what_landed`, asserting both halves
    together (stdout reports `PRIMARY_UPDATED:10` **and** the primary really
    carries `folded_tasks: [9999]`), plus a dedicated negative control
    `test_negative_control_abort_without_exit_flush`. The existing
    `install_unbuffered_record_emission` control cannot discriminate this test —
    a pre-fix build prints at mutation time and would pass it — so the new
    control removes the `EXIT` trap specifically and requires the defect
    (mutation lands, stdout silent) to be observable.

- **Verification after the change:** `test_fold_mark.sh` 153/153; all 15
  fold_mark-touching suites green; shellcheck clean; `aitask_skill_verify.sh` OK.

### Change Request 2 (2026-09-01 13:35)

- **Requested by user:** The second Step 8 review rejected Change Request 1's
  `EXIT`-trap flush as blocking: emitting `PRIMARY_UPDATED:10` on a run that
  exits 1 and never reaches a terminal commit outcome **broadens the output
  protocol** beyond the task's stated contract ("flush them only once Step 6
  reaches a terminal success, so stdout describes committed state exclusively").
  Remove the trap and its abort-specific test/control; narrow the documentation
  to the Step 6 rollback/refusal guarantee instead.

- **Verified:** CONFIRMED, and the two reviews converge rather than conflict —
  Change Request 1 offered "narrow the documented guarantee" as its first
  option, and this review selects it. The task specification is explicit, and
  goal fidelity wins over the broader invariant I had preferred.

- **Changes made:**
  - `aitask_fold_mark.sh`: removed `_fold_exit_flush`, the `trap ... EXIT`, and
    the `_fold_rolled_back` flag (including its assignment in `_fold_rollback`).
    Buffering is back to exactly the four Step 6 terminal-success flush points.
  - Header rewritten to the narrowed scope, with an explicit **"WHAT THIS DOES
    NOT BUY"** paragraph: silence is not proof that nothing changed, an abort
    before Step 6 leaves mutations on disk uncommitted, and the **exit status is
    authoritative**. Same wording in `task-fold-marking.md`. The narrowing is
    stated rather than left implicit, so no consumer reads the smaller
    guarantee as the larger one.
  - `tests/test_fold_mark.sh`: deleted `install_no_exit_flush` and
    `test_negative_control_abort_without_exit_flush`. **Converted** (rather than
    deleted) the abort test into `test_abort_mid_mutation_emits_no_records`,
    which now pins the contract as specified — stdout empty on a pre-Step-6
    abort — *and* pins the documented residual (the Step 3 mutation is still on
    disk, dirty and uncommitted). Keeping it guards the narrowed contract on a
    reachable path; say the word and it goes entirely.

- **Known residual (deliberately not fixed here):** a pre-Step-6 abort leaves
  the task files dirty and uncommitted, and stdout does not report it. That is
  the *transactionality* gap, not the output contract: `rollback_paths` is not
  assembled until after Step 5b, so fixing it means hoisting the rollback set
  above Step 3, which would disturb t1599_2's scoped-commit and amend-guard
  design. It predates this task (the pre-fix build left the same files dirty)
  and is now documented in both the script header and `task-fold-marking.md`.

- **Verification after the change:** `test_fold_mark.sh` 155/155; all 15
  fold_mark-touching suites green; shellcheck clean; `aitask_skill_verify.sh` OK.

## Final Implementation Notes

- **Actual work done:** Buffered `aitask_fold_mark.sh`'s four per-mutation
  records (`PRIMARY_UPDATED` / `FOLDED` / `CHILD_REMOVED` / `TRANSITIVE`) behind
  `_fold_emit`, flushing via `_fold_flush_records` at exactly the four Step 6
  terminal successes (`crc=0`, `crc=2`, `amend`, `none`). Documented the
  contract — and what it does **not** buy — in the script header and in
  `task-fold-marking.md`. Added 7 tests and 2 negative controls to
  `tests/test_fold_mark.sh`.

- **Deviations from plan:** Net zero — the delivered change matches the approved
  plan. An `EXIT`-trap flush was added in Change Request 1 and removed again in
  Change Request 2; what survives that round trip is one extra test
  (`test_abort_mid_mutation_emits_no_records`, pinning the narrowed contract and
  its residual) and a sharper header. Plan item 1d (`_fold_rollback` on the
  invalid-`--commit-mode` arm) landed as planned; the plan flagged it as
  adjacent scope.

- **Issues encountered:**
  - Reaching `task_git_commit_scoped`'s `crc=2` arm deterministically. The
    production shape (an idempotent re-fold) is clock-dependent, since
    `aitask_update.sh` stamps `updated_at` to the current minute, so a re-run is
    only byte-identical within one minute. Used `git update-index
    --assume-unchanged` on the fold's paths instead: git reports them clean
    however the fold rewrites them. The assertion is self-proving — `NO_COMMIT`
    from a `fresh` invocation can only come from that arm.
  - Reaching the two post-staging commit failures. Neither commit site passes
    `--no-verify`, the scaffold sets no `core.hooksPath`, and `task_git` is plain
    `git` in `$PWD` in these fixtures, so a failing `.git/hooks/pre-commit` fails
    the commit itself while still releasing the index — which keeps
    `_fold_rollback` working and the restoration half assertable.
  - `install_prefix_commit_block` (t1599_2's control) excises Step 6 by text,
    anchored on `# _fold_task_id_of_path` and the literal
    `die "invalid --commit-mode: $commit_mode"`. The buffer helpers were placed
    **above** Step 6 so the excision cannot take them, the anchor line was kept
    verbatim, and the injected pre-fix block gained `_fold_flush_records` calls
    so it stays t1661-correct while rebuilding t1599_2's defect.

- **Key decisions:**
  - Buffering over a terminal `ROLLED_BACK:` marker — the task's stated
    preference; a marker needs every consumer to opt in.
  - `crc=2` and `--commit-mode none` are flush points: nothing is rolled back
    and the mutations stand, so the records are honest. Each is pinned by its
    own test.
  - The guarantee is scoped to Step 6, per the task specification: a record means
    the mutation *survived Step 6* — which includes the two `NO_COMMIT` successes
    (`--commit-mode none`, and the verified no-op), so it does not imply durable
    git history. A pre-Step-6 abort stays silent. Both costs — `NO_COMMIT` being
    a success, and silence not proving no change — are written into the contract
    rather than left implicit, with the exit status named as authoritative.

- **Upstream defects identified:** None. (The pre-Step-6 abort residual noted
  under Change Request 2 is in this same script, is pre-existing, and is now
  documented behavior rather than a hidden defect — see the follow-up offer at
  Step 8b.)

### Change Request 3 (2026-09-01 13:50)

- **Requested by user:** The header and `task-fold-marking.md` called the
  guarantee "stdout describes committed state only", but the implementation
  deliberately flushes ahead of `NO_COMMIT` in both `--commit-mode none` (the
  caller commits later) and the `fresh` `crc=2` verified no-op. That name
  contradicts the mode semantics and could mislead a consumer into reading an
  uncommitted handoff as durable git history. Rename the guarantee to
  terminal-success / surviving-on-disk, explicitly retain `NO_COMMIT` as a valid
  successful flush outcome, and keep the pre-Step-6-abort disclaimer separate.

- **Verified:** CONFIRMED — the two `NO_COMMIT` flushes are deliberate and are
  pinned by `test_none_mode_no_commit` and
  `test_fresh_verified_noop_flushes_records`. The defect was the name, not the
  behavior.

- **Changes made (documentation only — no behavior change):** retitled the
  script-header contract to `RECORDS MEAN "STEP 6 REACHED A TERMINAL SUCCESS"`
  and gave it a three-row table of the terminal records, spelling out that
  `NO_COMMIT` is a success (either `--commit-mode none` or the verified no-op)
  and that a record therefore means "survived Step 6", **not** "committed".
  Mirrored the same table and wording into `task-fold-marking.md`, kept the
  separate "what this does not buy" abort disclaimer in both, and aligned the
  `tests/test_fold_mark.sh` header comment.

- **Verification after the change:** `test_fold_mark.sh` 155/155; all 15
  fold_mark-touching suites green; shellcheck clean; `aitask_skill_verify.sh` OK.

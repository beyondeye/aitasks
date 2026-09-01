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

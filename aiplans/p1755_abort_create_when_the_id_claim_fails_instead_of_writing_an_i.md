---
Task: t1755_abort_create_when_the_id_claim_fails_instead_of_writing_an_i.md
Branch: main
Base branch: main
Output branch: main
---

# t1755 — Abort create when the id claim fails instead of writing an id-less task file

## Context

`ait create` can produce a task file carrying **no id at all** — `aitasks/t_<name>.md` —
**commit it**, and exit **0**. Reproduced end-to-end in a scratch fixture during
planning (not inferred):

| forced failure | today's observable |
|---|---|
| `TMPDIR` → non-existent dir | `Created: aitasks/t_tdf.md`, rc **0**, commit `ait: Add task t: tdf`, counter unmoved |
| `aitask_claim_id.sh` stubbed to `exit 3` | `Created: aitasks/t_stubfail.md`, rc **0**, commit created |

Two independent defects produce it.

**(1) `claim_parent_id_once()` allocates its stderr capture with an unchecked
`mktemp`** (`.aitask-scripts/aitask_create.sh:1046`). When `TMPDIR` is missing,
full, read-only or not a directory, `claim_stderr` stays empty, `2>"$claim_stderr"`
is an ambiguous redirect, and the claim cannot run. The user sees shell noise —
`line 1047: : No such file or directory`, `cat: '': No such file or directory` —
and then `Atomic ID counter failed: unknown error`, which names the wrong cause.

**(2) The failure status never reaches the caller.** Measured root cause:
**bash drops `errexit` inside every command-substitution subshell.**

```
$ set -e; echo "L0: $SHELLOPTS"; echo "L1: $(echo "$SHELLOPTS")"
L0: braceexpand:errexit:hashall:interactive-comments
L1: braceexpand:hashall:interactive-comments        # <- no errexit
```

So inside `claimed_id=$(claim_unique_parent_id …)`, the inner
`claimed_id=$(claim_parent_id_once …)` failing does **not** abort: the `die` exits
only its own subshell, the retry loop falls through to
`active_parent_task_exists ""` (false, since no `t_*.md` exists), and the function
`echo`s an **empty** id and `return 0`. The outer shell then writes, commits and
reports success. This is why the error prints exactly once rather than five times.

t1721 already had to add downstream handling for "task files whose filename carries
no task id" — evidence this shape leaks into the framework instead of being caught
at the source.

**Intended outcome:** a failed id claim **aborts** the create — nothing written,
nothing committed, non-zero exit — so callers can tell it apart from success.

### Decision taken during planning (resolves an ambiguity in the task text)

The task's Goal says the `mktemp` failure "must degrade **or** abort deliberately"
and cites `_ait_cs_sink` (which degrades), while its Verification row 1 demands a
**non-zero exit**. **The user chose: abort deliberately**, keeping row 1 exactly as
written.

**Consequence that must be recorded:** the task body's sentence *"Fixing (1) alone
would close this reproduction while leaving the class open"* is **false under this
choice** — with only (1) fixed, the new `die` is still invisible to the caller, so
the id-less file still appears. It is (2) that closes the reproduction. Row 1's
**exit/artifact** assertions therefore do **not** discriminate the (1) half at all;
only its **stderr-message** assertions do. The mutant table below is built on that,
and the divergence goes into the plan's Final Implementation Notes.

The `_ait_cs_sink` precedent (`lib/task_utils.sh:547-559`) degraded for a reason
that does **not** transfer here: there the `mktemp` sits *after* the file was
written and the id claimed, so aborting would have burned an id. Here it sits
*before* every side effect, so aborting burns nothing.

## Key files to modify

- `.aitask-scripts/aitask_create.sh` — the only production file. Five regions:
  `claim_parent_id_once()` (~1042), `claim_unique_parent_id()` (~1073), the
  `finalize_draft` call site (~928), and in `run_batch_mode` the new hoisted claim
  (~2233, before the label registration at ~2243) plus the deletion of the old
  in-branch claim (~2321).
- `tests/test_create_id_claim_abort.sh` — **new**.

Reference patterns to follow (do not re-invent):
- `tests/test_create_silent_stdout.sh` — `setup_project()` builds a real
  bare-remote + clone + `setup_fake_aitask_repo` fixture and drives the real
  `--batch --commit` path; `install_sequence_claim_stub()` is the documented seam
  for replacing `aitask_claim_id.sh`. Copy both.
- `tests/lib/test_scaffold.sh:setup_fake_aitask_repo` and `tests/lib/asserts.sh`.
- `.aitask-scripts/lib/task_utils.sh:547-559` — the sibling `mktemp` fix from
  t1725_2, for the comment style and the "why this one differs" note.

## Implementation

### 1. `claim_parent_id_once()` — check the `mktemp` (defect 1)

Replace the unchecked allocation:

```bash
    local claimed_id
    # mktemp CAN fail (TMPDIR missing, full, read-only, or not a directory).
    # Unchecked, $claim_stderr stayed EMPTY, `2>"$claim_stderr"` became an
    # ambiguous redirect, and the claim could not run at all -- surfacing as
    # shell noise plus a misleading "Atomic ID counter failed: unknown error".
    #
    # lib/task_utils.sh's _ait_cs_sink degrades to /dev/null instead; that is
    # correct THERE because its mktemp runs after the file is written and the id
    # claimed, so aborting would burn an id. Here nothing has been written yet,
    # so a deliberate abort costs nothing and fails closed on a shared,
    # cross-machine counter (t1755).
    local claim_errf
    claim_errf="$(mktemp "${TMPDIR:-/tmp}/ait_claim_id_err.XXXXXX" 2>/dev/null)" \
        || die "Cannot allocate a temp file for the ID-claim diagnostic (is TMPDIR=${TMPDIR:-/tmp} writable?); refusing to claim a task ID."
```

Then rename `claim_stderr` → `claim_errf` at its three remaining uses (the
redirect, the `cat`, and the two `rm -f`s). `claim_errf` is guaranteed non-empty
past the `die`, so no `/dev/null` guard is needed and the `rm`s stay unguarded.

The message text is part of the guard and is asserted by the test.

### 2. `claim_unique_parent_id()` — propagate, and validate (defect 2, half A)

The retry loop exists for the **id-collision** case only. A hard claim failure must
propagate immediately, and a non-numeric id must never escape:

```bash
claim_unique_parent_id() {
    local allow_interactive_fallback="${1:-false}"
    local attempt claimed_id once_rc

    for ((attempt = 1; attempt <= MAX_PARENT_ID_CLAIM_RETRIES; attempt++)); do
        # errexit does NOT survive a command substitution (bash clears it in the
        # subshell), and a die() inside claim_parent_id_once exits only THAT
        # subshell -- so the exit status is the one signal that survives. Absorb
        # it explicitly; declare `once_rc` first, because `local x=$(…)` would
        # mask the status in local's own return value (t1755).
        once_rc=0
        claimed_id=$(claim_parent_id_once "$allow_interactive_fallback") || once_rc=$?
        if (( once_rc != 0 )); then
            # Not retryable: the counter is unavailable or the user declined the
            # local-scan fallback. Retrying would only reprint the same error.
            return "$once_rc"
        fi
        if [[ ! "$claimed_id" =~ ^[0-9]+$ ]]; then
            warn "Atomic ID counter returned a non-numeric task ID ('$claimed_id')."
            return 1
        fi
        if active_parent_task_exists "$claimed_id"; then
            warn "Claimed task ID t$claimed_id already exists as an active parent task; retrying ($attempt/$MAX_PARENT_ID_CLAIM_RETRIES)." >&2
            continue
        fi
        echo "$claimed_id"
        return 0
    done

    die "Failed to claim a unique active parent task ID after $MAX_PARENT_ID_CLAIM_RETRIES attempts."
}
```

The numeric check is the **single** choke point that makes an id-less filename
structurally impossible; the call sites below therefore check only the status and
do not restate it. Use real `if … fi` blocks — a trailing `(( rc != 0 )) && …` is a
complete `&&` list whose false case returns 1 and trips `set -e`.

### 3. Both call sites — turn the status into a real abort (defect 2, half B)

Both are reached with **no lock held and nothing written**, so a plain `die` is
clean, and both call chains (`main → run_batch_mode`, `main → … → finalize_draft`)
are direct — verified not to be inside a `$( )`, so the `die` terminates the
process.

`finalize_draft()`, parent branch (~926-928) — the draft is still on disk here,
and `rm -f "$draft_path"` comes later, so aborting preserves it:

```bash
        # Parent task: claim from atomic counter
        local claimed_id claim_rc=0
        claimed_id=$(claim_unique_parent_id true) || claim_rc=$?
        if (( claim_rc != 0 )); then
            die "Task ID claim failed (see the error above). Draft left at $draft_path; nothing was created."
        fi
```

`run_batch_mode()` — **hoist the claim out of the parent branch** to sit directly
after `assert_task_data_writable` (~2233) and **before** the shared label
registration (~2243). Insert:

```bash
        # Claim the parent id BEFORE the label registration below. add_label_to_file
        # writes labels.txt to disk immediately (lib/task_utils.sh:1785), so a claim
        # failure after it would abort with the shared vocabulary already appended --
        # a task-less label the user never asked for. Rolling back is NOT the
        # alternative: restoring the file wholesale would clobber a concurrent
        # session's append, which is the t1662 hazard. Claiming first makes the
        # "nothing is written" guarantee literally true -- resolve_anchor,
        # sanitize_name and normalize_labels_csv are all read-only, the last
        # explicitly so (t1755).
        #
        # The trade this does NOT buy: a label-write failure now burns an id, where
        # before it burned nothing. That is the cheaper direction -- a burned id is
        # self-healing (`aitask_claim_id.sh --resync`), while a vocabulary entry for
        # a task that does not exist is user-visible garbage -- and a local disk
        # write fails far more rarely than a git-backed counter claim.
        local claimed_id="" claim_rc=0
        if [[ -z "$BATCH_PARENT" ]]; then
            claimed_id=$(claim_unique_parent_id false) || claim_rc=$?
            if (( claim_rc != 0 )); then
                die "Task ID claim failed (see the error above); no task was created."
            fi
        fi
```

Then in the parent branch (~2321-2322) **delete** the now-duplicate
`local claimed_id` / `claimed_id=$(claim_unique_parent_id false)` pair; the rest of
that branch already consumes `$claimed_id` unchanged. The child branch is untouched
(`claimed_id` stays empty and unused), and the "ONE gate shared by both commit
sites" registration keeps its single call site.

### 4. New test — `tests/test_create_id_claim_abort.sh`

Fixture: copy `setup_project()` and `install_sequence_claim_stub()` from
`tests/test_create_silent_stdout.sh` (real repo, real `--batch --commit`, real
`aitask_claim_id.sh --init`). Plain in-process counters — no `( … )` subshell test
bodies, so the file-backed `assert_counters_*` opt-in is not needed.

Every forced-failure row snapshots `git rev-parse HEAD` **and** `git status
--porcelain` before the create and re-reads both after — the no-commit guarantee is
per **call site**, and `finalize_draft` (line 909) and `run_batch_mode` (line 2303)
are two distinct `task_git_commit_scoped` sites. A row that checks only the
artifact would let a regression at the other site commit silently.

| row | drive | assert |
|---|---|---|
| **1 — forced failure: mktemp** | `TMPDIR="$PWD/nope" aitask_create.sh --batch --commit --name tdf --labels a_fresh_label` | rc **≠ 0**; no `aitasks/t_*.md`; `HEAD` unchanged; `git status --porcelain` unchanged; **`aitasks/metadata/labels.txt` byte-identical and free of `a_fresh_label`**; `--peek` identical before/after; stderr **contains** `Cannot allocate a temp file for the ID-claim diagnostic`; stderr **does not contain** `cat: ''` nor `aitask_create.sh: line` |
| **2 — negative control** | same create, usable `TMPDIR` | rc **0**; `aitasks/t1_tdf.md` exists; no `t_*.md`; `--peek` advanced; `labels.txt` **does** now contain `a_fresh_label` (proves the label path is live, so row 1's absence is the abort and not a dead flag) |
| **3 — forced failure: not mktemp** | stub `aitask_claim_id.sh` → `exit 3` (`--peek` still echoes), usable `TMPDIR`, `--labels a_fresh_label` | rc **≠ 0**; no `t_*.md`; `HEAD` unchanged; `git status --porcelain` unchanged; `labels.txt` unpolluted; stderr contains `Atomic ID counter failed` |
| **4 — draft path** | `--batch` (draft), then finalize it with the `exit 3` stub | rc **≠ 0**; no `t_*.md`; **`HEAD` unchanged**; **`git status --porcelain` unchanged**; the draft file **still exists** |

Row 2 is the negative control on two axes: it proves the forced failures are the
*injection* and not a broken fixture, and its positive `labels.txt` assertion proves
row 1's negative one is discriminating rather than vacuous. Row 3 is the row that
stays red if only the `mktemp` is fixed — it is what pins defect (2) rather than (1).

Also re-run `tests/test_create_silent_stdout.sh` — its **Test 1b** drives the
id-collision retry through `install_sequence_claim_stub "1" "2"` and must stay
green, proving the retry loop was preserved and not collapsed by the new
early `return`.

### Post-phase (risk mitigations)

- **`verify_label_vocab_clean_on_abort`** — the claim hoist in §3 is the *fix*; this
  phase is its verification. Confirm by direct measurement that a forced-failure
  create carrying `--labels a_fresh_label` leaves `aitasks/metadata/labels.txt`
  byte-identical (rows 1 and 3), and that the same create with a usable counter
  *does* register the label (row 2). Both assertions must be present — the negative
  one alone can pass simply because the label path never ran.

- **`measure_per_half_mutants`** — after the tests are green, actually apply each
  half-revert and record which rows go red (measured, not reasoned), then put the
  table in the test file's header in the house style of
  `tests/test_task_commit_scoped.sh`. Expected, to be confirmed:

  | mutation | rows expected red |
  |---|---|
  | revert only the `mktemp` check (§1) | 1 (**stderr-message assertions only**) |
  | revert only the status propagation (§2+§3) | 1 (rc/artifact), 3, 4 |
  | revert both | 1, 3, 4 |

  If the measured table differs, the **table** is corrected — never the claim.

  **Restore protocol — mandatory, and `git restore` is forbidden here.** This
  experiment mutates production code *after* the suite is green, in a worktree that
  holds the uncommitted fix itself; `git restore` / `git checkout --` would discard
  the whole task's work, not just the mutant. Instead:

  1. Before the first mutation, copy the intended file aside and record its digest:
     `cp .aitask-scripts/aitask_create.sh "$SCRATCH/aitask_create.sh.intended"` and
     `sha256sum` it.
  2. Mutate, run the tests, record the red rows.
  3. Restore by copying the saved file back — never by a git operation.
  4. After the **last** mutation, re-run `sha256sum` and assert it equals the digest
     from step 1. A mismatch means the restore did not land: stop and fix it before
     anything else.
  5. Then re-run the full Verification block below and require it green **before**
     staging anything. Nothing is committed while any mutant is in the tree — a test
     that is red until the fix lands must never reach a commit.

## Verification

```bash
shellcheck .aitask-scripts/aitask_create.sh          # must stay clean
bash tests/test_create_id_claim_abort.sh             # new: rows 1-4
bash tests/test_create_silent_stdout.sh              # collision retry preserved
bash tests/test_create_email_lock.sh                 # neighbouring create path
bash tests/test_claim_id.sh                          # counter itself untouched
bash tests/test_parallel_child_create.sh             # child branch: claim hoist is a no-op there
```

Sequencing: the new test must never reach a commit while red — write §1-§3 and the
test in the same working tree, land them in one commit. The whole block above must
be re-run and green **after** the `measure_per_half_mutants` restore, and the
`aitask_create.sh` digest re-checked, before anything is staged.

## Post-Implementation

Follow **Step 9 (Post-Implementation)** of the task workflow: commit with
`bug: …(t1755)`, record the `risk_evaluated` gate, and archive the task and plan.
Task/plan files are committed with `./ait git`.

## Risk

### Code-health risk: medium
- The success path is byte-identical apart from the `mktemp` template string; every
  addition is on a failure path. · severity: low · → mitigation: inline post-phase measure_per_half_mutants
- `claim_unique_parent_id` now also returns non-zero on retry-exhaustion (which
  previously produced an id-less file), and the new early `return` sits inside the
  retry loop — a mis-placed guard would collapse the collision retry. · severity: medium · → mitigation: `tests/test_create_silent_stdout.sh` Test 1b, listed in Verification
- Blast radius is one script, five small regions; no shared library is touched. · severity: low · → mitigation: none needed
- The `measure_per_half_mutants` phase deliberately mutates production code after
  the suite is green; a botched restore would leave a mutant staged for commit. · severity: high · → mitigation: inline post-phase measure_per_half_mutants (digest-checked restore protocol, `git restore` forbidden)
- Hoisting the claim moves it ahead of the label write, so a label-write failure now
  burns an id where it previously burned nothing. Deliberate: a burned id is
  self-healing via `--resync`, a task-less vocabulary entry is not. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The task text's "fixing (1) alone would close this reproduction" is false under
  the chosen abort route, so row 1's exit/artifact assertions do not discriminate
  the (1) half — only its message assertions do. A mutant table built on the task's
  wording instead of on measurement would claim coverage it does not have. · severity: medium · → mitigation: inline post-phase measure_per_half_mutants
- The task's Goal says "nothing is written", but `add_labels_csv_to_file` ran
  before the claim in `run_batch_mode`, so an aborted `--labels` create appended to
  the shared vocabulary — a reachable failed-create path that violated the stated
  outcome, and unasserted by any row the task named. **Closed by the claim hoist in
  §3**, not deferred. · severity: high · → mitigation: inline post-phase verify_label_vocab_clean_on_abort
- Root cause was reproduced twice in a real fixture and the errexit semantics
  measured directly, so the approach rests on evidence rather than inference. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: post-phase | name: measure_per_half_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (a reasoned mutant table would overclaim, since the task's "fixing (1) alone closes it" is false here) + code-health (the new early return sits inside the collision-retry loop; and the experiment itself mutates production code after green) | desc: apply each half-revert, record which rows actually go red, put the measured table in the test file header, then restore by digest-checked file copy (never git restore) and re-run the full Verification block before staging
- timing: post-phase | name: verify_label_vocab_clean_on_abort | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (an aborted --labels create appended to the shared vocabulary, violating the "nothing is written" outcome) | desc: assert labels.txt is byte-identical after both forced-failure rows AND that the negative control does register the label, so the negative assertion cannot pass vacuously

**Reassessment after inlining and after the review round:** the review turned the
label-vocabulary item from a deferred probe into a **fix** (the §3 claim hoist), and
added a restore gate to the mutant phase plus commit-history assertions to every
forced-failure row. Re-assessed against that augmented plan: **code-health rises to
medium** -- the hoist reorders a load-bearing create path and the plan now
carries a phase that deliberately mutates production code, both bounded and both
with named controls, which is "a real but bounded concern" rather than "no material
concern";
**goal-achievement stays low** — the residual "nothing is written" gap that had been
the one medium-severity goal risk is now closed in the implementation rather than
carried as a follow-up.

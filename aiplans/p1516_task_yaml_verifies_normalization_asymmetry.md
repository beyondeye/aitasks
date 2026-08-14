---
Task: t1516_task_yaml_verifies_normalization_asymmetry.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1516 — Task-id normalization: read/write symmetry + drift guard

## Context

`.aitask-scripts/lib/task_yaml.py` normalizes task-id lists on **read** for
`depends` / `children_to_implement` / `folded_tasks`, while
`.aitask-scripts/aitask_update.sh` normalizes on **write** for `depends` /
`children_to_implement` / `verifies` / `risk_mitigation_tasks` / `xdeps`. The
two field sets were maintained independently and drifted, so a read-modify-write
silently rewrites `verifies: ['635_11']` to `verifies: [t635_11]`. The t1468_6
`followup_kind` backfill hit this on 19 files and had to widen its own delta
check (`_norm_scalar`) to tolerate it.

Both normalizers are semantically identical — add a `t` prefix to child-form ids
matching `^\d+_\d+$`, leave bare parent ids and already-prefixed ids alone
(`task_yaml.py:100-113`, `task_utils.sh:948-961`). **The bug is not the
normalizer; it is that the field set is duplicated with no guard.** So the fix
single-sources the set and adds a guard, rather than adding one more entry to a
list that will drift again.

The audit found the drift runs in both directions, plus two further defects in
the same family:

| field | read (`task_yaml.parse_frontmatter`) | write (`aitask_update.sh`) | write (`aitask_create.sh`) |
|---|---|---|---|
| `depends` | ✅ `:151` | ✅ `:1959` | ❌ |
| `children_to_implement` | ✅ `:151` | ✅ `:2040` | n/a |
| `folded_tasks` | ✅ `:151` | ❌ | n/a |
| `verifies` | ❌ | ✅ `:1010` | ❌ |
| `risk_mitigation_tasks` | ❌ | ✅ `:1910` | n/a |
| `xdeps` | ❌ | ✅ `:1970` | ❌ |

Two extra defects, confirmed by reading the source:

- **`process_verifies_operations` compares mismatched forms**
  (`aitask_update.sh:977-1004`). `verifies_array` holds `t`-prefixed entries
  (normalized at `:544`) but each `--add-verifies` / `--remove-verifies`
  argument is compared **`t`-stripped** (`norm="${vid#t}"`). For child-form ids
  the comparison never matches, so `--remove-verifies 635_11` silently removes
  nothing and `--add-verifies 635_11` appends a duplicate. Parent ids are
  unaffected, and no test in `tests/test_verifies_field.sh` uses a child-form
  id — the bug sits in a test blind spot.
- **`aitask_create.sh` never normalizes at all.** It calls `normalize_task_ids`
  nowhere, so `--deps` / `--verifies` / `--xdeps` are written verbatim. It is
  the *producer* of the non-canonical shape the backfill later rewrote.

**Intended outcome:** one canonical on-disk form for every task-id list field,
produced consistently by every writer and read consistently by every reader,
with an executable guard that fails when read and write disagree.

**Corpus churn is near-zero.** All 76 active `verifies:` values are already
`t`-prefixed or bare parent ids; exactly one file has a bare child-form
`folded_tasks: [635_25]`.

## Changes

### Pre-phase (risk mitigations)

1. `[characterize_verifies_ops]` Before touching
   `process_verifies_operations`, add the child-form cases from step 8 to
   `tests/test_verifies_field.sh` and **run them against unmodified code**.
   Confirm both fail, and record the observed failing output verbatim in the
   plan's Final Implementation Notes: `--remove-verifies 635_11` must be
   observed leaving `verifies: [t635_11]` intact, and `--add-verifies 635_11`
   must be observed producing a duplicated entry. If either case *passes*
   against unmodified code, the source-read diagnosis is wrong — stop and
   re-derive before changing anything.

### 1. `.aitask-scripts/lib/task_yaml.py` — canonical constant, used by the reader

Add a module-level constant next to the existing helpers and drive
`parse_frontmatter` from it. **This constant is the single source of truth** for
the whole framework; the bash side is verified against it behaviorally (step 7)
rather than repeating the list.

```python
# The frontmatter fields holding a LIST of task-id references. Canonical for
# the whole framework: every reader normalizes these, and every writer must
# emit the same canonical form. tests/test_task_id_normalization_parity.sh
# drives itself from this tuple and probes the bash writers behaviorally, so
# adding a field here without teaching the writers fails the suite.
# `anchor` is deliberately absent: it is a scalar, and it is a ROOT task id
# (always parent-form), so the child-form prefix rule never applies to it.
TASK_ID_LIST_FIELDS = (
    'depends',
    'children_to_implement',
    'folded_tasks',
    'verifies',
    'risk_mitigation_tasks',
    'xdeps',
)
```

Then at `:150-153`:

```python
    for key in TASK_ID_LIST_FIELDS:
        if key in metadata:
            metadata[key] = _normalize_task_ids(metadata[key])
```

The `anchor` scalar normalization at `:155-158` is unchanged.

### 2. `.aitask-scripts/aitask_update.sh` — normalize `folded_tasks` on write

Mirror the `depends` pattern at both sites: the parse arm (`:585-587`) and the
pre-write pass (`:2113-2117`), each gaining a `normalize_task_ids` call. Both
`folded_tasks` readers already strip the prefix (`aitask_archive.sh:304`,
`aitask_fold_mark.sh:129`), so this is safe.

### 3. `.aitask-scripts/aitask_update.sh` — fix the verifies add/remove comparison

In `process_verifies_operations` (`:977-1004`), canonicalize **both** sides of
each comparison instead of only the argument:

```bash
            if [[ "${existing#t}" == "$norm" ]]; then
```

in the add-dedup loop (`:983`) and the remove loop (`:998`). Stripping is the
right comparison key here because `verifies_array` can hold either shape: it
comes from the normalized `CURRENT_VERIFIES` (`:544`) *or*, when `--verifies`
was passed, from the raw un-normalized flag value (`:968`). The trailing
`normalize_task_ids` (`:1010`) still decides the emitted form. Also correct the
stale comment at `:1006` — `normalize_task_ids` *adds* the prefix, it does not
strip it.

### 4. `.aitask-scripts/aitask_create.sh` — normalize at the producer

Apply `normalize_task_ids` to `BATCH_DEPS`, `BATCH_VERIFIES` and `BATCH_XDEPS`
once, after argument parsing and before the emit dispatch (around `:2112`, where
`BATCH_DEPS` is already being rewritten for the auto-sibling edge). This stops
new files being born non-canonical — the origin of the 19 rewritten files.

### 5. Retire the two compensating workarounds' stale rationale

- `.aitask-scripts/board/aitask_board.py:3117-3122` — the comment "xdeps values
  are NOT normalized by task_yaml, so coerce/strip the leading 't' here" becomes
  false. Rewrite it to say the values are normalized on read and the
  `lstrip('t')` is retained because the board renders cross-repo refs in bare
  `proj#id` form. Leave the `lstrip('t')` calls themselves in place — they are
  still required for the display form.
- `.aitask-scripts/lib/followup_backfill_classify.py:172-187` — `_norm_scalar`
  **stays** (it also absorbs quote-only and `'16'`-vs-`16` type differences that
  the prefix rule does not touch, and it is applied to every key, not just id
  lists). Update its docstring: the `verifies: ['635_11']` → `[t635_11]` example
  is no longer reachable; replace it with a quoted-vs-int example and note that
  the prefix asymmetry was closed by t1516.

### 6. Tests — repair the one assertion the fix invalidates

`tests/test_followup_backfill_classify.py`:

- `test_id_canonicalisation_is_tolerated_but_reported` (`:266-274`) currently
  pins `verifies: ['635_11']` → `[t635_11]` as `OK_NORMALIZED`. After the fix
  both sides parse identically, the `bmeta[key] == ameta[key]` short-circuit at
  `followup_backfill_classify.py:240` fires, and the verdict is `OK` — the
  assertion fails. **Retarget the fixture, do not delete the guard:** point it
  at a difference that still survives normalization (`depends: ['42']` →
  `depends: [42]`, str-vs-int), so the `OK_NORMALIZED` branch keeps direct
  coverage.
- **Add** `test_verifies_prefix_is_no_longer_a_delta`: the same before/after
  pair the old test used (`['635_11']` → `[t635_11]`) must now report plain
  `OK` with no `verifies` detail. This is the regression guard for this task.
- `test_id_normalisation_does_not_mask_a_real_id_change` (`:335-342`) still
  passes unchanged — verify, do not edit.

### 7. Tests — the parity drift guard (new)

`tests/test_task_id_normalization_parity.sh`, following the fixture style of
`tests/test_verifies_field.sh` (self-contained, `assert_eq`/`assert_contains`,
own PASS/FAIL summary; add `assert_counters_init` / `assert_counters_load` if
any body runs in a `( … )` subshell).

It reads the canonical set from Python and probes the real writers:

```bash
fields=$("$py" -c "import task_yaml; print(' '.join(task_yaml.TASK_ID_LIST_FIELDS))")
```

For each field in that list:

1. **Read side** — write a fixture task carrying `<field>: [900_1]`, parse it
   with `task_yaml.parse_frontmatter`, assert the value is `['t900_1']`.
2. **Write side** — run `aitask_update.sh --batch <n> --priority high --silent`
   (a change that does *not* touch the field, i.e. exactly the read-modify-write
   that caused the bug) and assert the on-disk line reads `[t900_1]`.

Plus a create-side case asserting `aitask_create.sh --batch --deps 900_1
--verifies 900_2` emits `[t900_1]` / `[t900_2]`.

Implementation notes to confirm while writing it: `xdeps` requires a paired
`xdeprepo` (`validate_xdeps_pair`), and `depends` / `children_to_implement` may
be validated against existing files — the fixture must satisfy whatever each
field's validator requires, or the probe will fail for the wrong reason.

**Known limit, to be stated in the test header:** the guard catches a field
present in `TASK_ID_LIST_FIELDS` whose writers do not normalize, and a writer
that stops normalizing. It cannot catch a brand-new frontmatter field added to
neither side — nothing can, short of a schema.

### 8. Tests — child-form coverage for the verifies operations

`tests/test_verifies_field.sh` currently uses only parent-form ids. Add:

- `--add-verifies 635_11` against `verifies: [t635_11]` → stays `[t635_11]`
  (no duplicate).
- `--remove-verifies 635_11` against `verifies: [t635_11]` → becomes `[]`.
- The `t`-prefixed argument spelling for both, asserting identical results.

### Post-phase (risk mitigations)

1. `[negctrl_parity_guard]` Prove the new parity guard can fail, one mutation
   at a time, restoring between each:
   - Remove `'verifies'` from `TASK_ID_LIST_FIELDS` → re-run
     `tests/test_task_id_normalization_parity.sh` and confirm it **fails**,
     naming the failing assertion id in the Final Implementation Notes.
   - Restore, then delete the `normalize_task_ids` call from the
     `folded_tasks` pre-write pass in `aitask_update.sh` → re-run and confirm
     it **fails** on the write-side probe, again naming the assertion.
   - Restore both. Finish with `git diff` over the two files to prove no
     mutation was left behind, and re-run the guard to confirm it passes.
   A negative control that *passes* means the guard is not wired to the thing
   it claims to check — fix the test, not the mutation.
2. `[pin_reader_behavior_changes]` Pin the two intended behavior changes so
   they are deliberate rather than silent:
   - A board test asserting `VerifiesField` built from a parsed task whose
     file says `verifies: [635_11]` renders `t635_11` (render-level assertion
     on `render()`, not on the metadata).
   - An `aitask_merge.py` test asserting that two metadata dicts differing
     only in `verifies` spelling — as produced by `parse_frontmatter` on
     `['635_11']` and `[t635_11]` — merge **without** an unresolved entry.
     Build both sides through `parse_frontmatter` so the test exercises the
     real read path rather than restating the constant.

## Verification

1. `bash tests/test_task_id_normalization_parity.sh` — new guard passes.
2. `bash tests/test_verifies_field.sh` — including the new child-form cases.
3. `bash tests/run_all_python_tests.sh` — read-side normalization touches
   `aitask_board.py`, `aitask_merge.py`, `trail_gather.py` and
   `followup_backfill_classify.py`; read **only the last line** for the verdict
   (`PYTHON SUITE: PASSED|FAILED`), and do not pipe without `pipefail`.
4. `bash tests/test_aitask_merge.py`-adjacent bash suites that touch these
   fields: `tests/test_archive_verification_gate.sh`,
   `tests/test_archive_carryover.sh`, `tests/test_yaml_utils.sh`,
   `tests/test_update_multiline_yaml.sh`.
5. `shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_create.sh`
6. **Corpus no-op check** — confirm the claim that the fix is churn-free for
   `verifies`: parse every active task with the new `parse_frontmatter` and
   diff the serialized `verifies` against the on-disk line. Expect zero
   differences; expect exactly one `folded_tasks` file (`[635_25]`) to become
   canonical on its next `ait update`.

## Risk

### Code-health risk: medium

- Read-side normalization changes what **every** Python consumer sees for
  `verifies` / `risk_mitigation_tasks` / `xdeps`. Each reader was individually
  audited and is prefix-tolerant (`aitask_board.py:4318` re-prefixes;
  `trail_gather.py:254` strips; `followup_backfill_classify.py:186` strips), but
  the surface is wide — 4 modules plus the board detail screen. · severity:
  medium (unchanged — the inline phases pin the two known behavior changes but
  do not narrow the audited surface; the full-suite run in Verification step 3
  is what covers the rest) · → mitigation: inline post-phase
  pin_reader_behavior_changes
- Two behavior changes are intended but user-visible: the board's Verifies label
  renders `t635_11` instead of `635_11`, and `aitask_merge.py` stops reporting a
  spurious unresolved conflict when two checkouts hold different spellings
  (`verifies` falls to the terminal `else` at `:373-375` today). Both are
  improvements, neither is currently pinned by a test. · severity: low
  (residual — both are now asserted by the inline post-phase) · → mitigation:
  inline post-phase pin_reader_behavior_changes
- The parity guard is new infrastructure. If it cannot actually fail, it is
  worse than no guard — it would license future drift. · severity: low
  (residual — the inline post-phase forces one mutation per side and requires a
  named failing assertion for each) · → mitigation: inline post-phase
  negctrl_parity_guard
- Changes touch three scripts plus two test files; `aitask_update.sh` and
  `aitask_create.sh` are load-bearing for every task mutation in the framework.
  · severity: medium · → mitigation: none (covered by the Verification suite
  runs, not by a dedicated mitigation)
- **New (introduced by the inline phases):** `negctrl_parity_guard` temporarily
  mutates `task_yaml.py` and `aitask_update.sh` to prove the guard fails. An
  interrupted run could leave a mutation in the working tree and ship a
  half-disabled normalizer. · severity: medium · → mitigation: none — the phase
  step itself requires one mutation at a time, a restore between each, and a
  closing `git diff` + green re-run as its exit condition

### Goal-achievement risk: low

- The core fix is a one-line loop change over a constant, and the corpus survey
  says it produces zero rewrites for `verifies`. The scope additions (steps 2-4,
  8) are each a one-to-two-line edit against a confirmed, source-read defect.
  · severity: low · → mitigation: none
- The `process_verifies_operations` defect was confirmed by reading the source
  but has not been reproduced by running it (plan mode is read-only), so the
  precise failing shape should be pinned by a failing test before the fix.
  · severity: low (residual — the inline pre-phase makes reproduction a
  precondition and stops the task if the diagnosis does not hold) ·
  → mitigation: inline pre-phase characterize_verifies_ops

### Planned mitigations

- timing: pre-phase | name: characterize_verifies_ops | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the process_verifies_operations defect was source-read but never reproduced | desc: add the child-form add/remove cases first and confirm they fail against unmodified code before fixing
- timing: post-phase | name: negctrl_parity_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the new parity guard may be unable to fail | desc: mutate one field and one writer in turn, requiring a named failing assertion each time, then restore and prove the tree is clean
- timing: post-phase | name: pin_reader_behavior_changes | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the board render change and the aitask_merge conflict change are unpinned | desc: assert both intended behavior changes through the real parse_frontmatter read path

## Step 9 (Post-Implementation)

Standard: verify build/tests, merge to `main` (current-branch mode — base and
output branch are both `main`), then `./.aitask-scripts/aitask_archive.sh 1516`.
The task declares `gates: [risk_evaluated]` and its materialized active set is
`risk_evaluated`, so the Step-9 gate orchestrator records it; archival is
blocked until it passes.

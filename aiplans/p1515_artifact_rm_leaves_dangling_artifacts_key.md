---
Task: t1515_artifact_rm_leaves_dangling_artifacts_key.md
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# t1515 — `rm` must drop an emptied frontmatter list key

## Context

`ait artifact rm` removing a task's **only** artifact leaves a dangling, valueless
`artifacts:` key in the task frontmatter:

```yaml
updated_at: 2026-08-13 16:04
artifacts:
---
```

`task_yaml.parse_frontmatter` then yields `artifacts: None` — not `[]` and not
absent. The board survives it only because `_iter_trail_frontmatter_records`
reads `meta.get("artifacts") or []`; any consumer iterating the key without that
guard hits `TypeError: 'NoneType' is not iterable`. It also makes a task *look*
like it still owns artifacts. Observed on `aitasks/t1505/t1505_1_bytrail_summary_pane.md`
during t1505_1 and cleaned up by hand there.

Goal: a create → rm round trip leaves the task file exactly as it was (modulo
`updated_at`), with the key **absent** — absence being the field's empty state.

**Duplicate found:** `aitasks/t1285_artifact_rm_leaves_empty_artifacts_key.md`
(Ready, low/low, found during the t1142 verification run) reports the identical
bug with matching acceptance criteria — last-artifact rm drops the key,
non-last rm leaves siblings untouched, covered by a test in
`tests/test_artifact_cli.sh` asserting the round trip to the pre-create state.
It is folded into t1515 (step 0 below); every one of its criteria is delivered here.

## Root cause (verified)

Not in `aitask_artifact.sh`. The task's `rm` path (`_artifact_rm_txn`,
`.aitask-scripts/aitask_artifact.sh:490`) delegates the frontmatter edit to the
shared line-based helper `.aitask-scripts/lib/frontmatter_patch.py`, whose
`cmd_remove` (lines 230–250) deletes only the matched **item** lines:

```python
    start, end = target
    del lines[start:end + 1]
    fm_end -= (end + 1 - start)
    bump_updated_at(lines, fm_start, fm_end, stamp)
```

The `<field>:` header line is never reconsidered, so emptying the block leaves it
bare. `cmd_append` is already the exact inverse — it *creates* the header when the
field is absent (line 207–211) — so fixing the header removal restores a true
round trip.

The same helper backs `ait attach rm` (`aitask_attach.sh:356`, field
`attachments`), which has the identical residue. Fixing the shared seam repairs
both call sites rather than patching one caller.

## Changes

### Pre-phase (risk mitigations)

1. `[neighbour_key_control]` In `tests/test_attach_meta.sh`'s frontmatter_patch
   section, **before** editing `frontmatter_patch.py`, add a fixture whose
   `attachments:` block is followed by a blank line and a further top-level key
   (e.g. `priority: high` after the block, with a blank line between). Append one
   item, remove it, then assert: the following top-level key is still present
   (`grep -c '^priority: high'` == 1), the frontmatter still terminates (`sed -n
   '2,/^---$/p'` finds the closing fence), and `read_yaml_field` on that key
   still returns its value. Run the file and confirm the case **passes against
   unfixed code** — it is a tripwire on how far the emptied-block sweep reaches,
   not a characterization of the bug.

### 0. Fold t1285 into t1515 (runs at the start of Step 7, post-approval)

The Ad-Hoc Fold Procedure mutates files, so it runs after plan approval, before
implementation:

```bash
./.aitask-scripts/aitask_fold_validate.sh --exclude-self 1515 1285      # expect VALID:1285:<path>
./.aitask-scripts/aitask_fold_content.sh aitasks/t1515_artifact_rm_leaves_dangling_artifacts_key.md \
    aitasks/t1285_artifact_rm_leaves_empty_artifacts_key.md \
  | ./.aitask-scripts/aitask_update.sh --batch 1515 --desc-file -
./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh 1515 1285     # expect COMMITTED:<hash>
```

t1285 becomes `Folded` with `folded_into: 1515`; its file is deleted by
`aitask_archive.sh` at Step 9. If validation returns `INVALID:1285:<reason>`,
report it and continue without folding — the fix does not depend on it.

### 1. `.aitask-scripts/lib/frontmatter_patch.py` — drop the emptied field

In `cmd_remove`, after the item deletion and **before** `bump_updated_at`, re-derive
the block and delete the header when no items remain:

```python
    start, end = target
    del lines[start:end + 1]
    fm_end -= (end + 1 - start)
    # Removing the last item removes the field. A bare `artifacts:` header
    # parses as None (not []), so the task reads as still owning artifacts and
    # any consumer iterating without an `or []` guard raises TypeError; absence
    # is the field's empty state, and it is what `cmd_append` re-creates, so a
    # create -> remove round trip is byte-identical again (t1515).
    block_end = block_extent(lines, header, fm_end)
    if not parse_items(lines, header, block_end):
        del lines[header:block_end]
        fm_end -= block_end - header
    bump_updated_at(lines, fm_start, fm_end, stamp)
```

Notes on correctness:
- `header` is still valid: the deleted item lines are all *after* it.
- `block_extent` stops at the next top-level key (`^\S`), so the deletion cannot
  reach an unrelated frontmatter key. Whatever is left inside the block (a comment
  or blank line) belonged to the removed field and goes with it.
- `fm_end` is decremented before `bump_updated_at`, which scans `range(fm_start+1,
  fm_end)` and inserts at `fm_end` when there is no `updated_at` — an unadjusted
  `fm_end` would insert past the closing `---`.
- The inline-flow case (`artifacts: []`) is unchanged: it has no items, so
  `cmd_remove` still dies with "no item" before reaching this code.
- Rollback compatibility: `_artifact_rm_txn` rolls back with
  `task_git checkout -- "$task_file"` (HEAD restore), which is unaffected.

Also extend the module docstring's `remove` usage line to state that removing the
last item removes the field header too.

### 2. `tests/test_attach_meta.sh` — unit regression (byte-for-byte round trip)

Extend the existing `── frontmatter_patch.py: append / remove round-trip ──`
section (after the current multi-item removal block, ~line 128). `mk_task` there
already writes `updated_at: 2020-01-01 00:00`, so pinning `--now` to that same
stamp makes the round trip **exactly** byte-for-byte:

- *Positive:* fresh task → `fm append … --now "2020-01-01 00:00"` → `fm remove …
  --now "2020-01-01 00:00"` → `assert_eq` the whole file against the pristine
  fixture; plus `assert_not_contains "attachments:"` on the result.
- *Negative control:* on the existing multi-item file, assert the header line
  **survives** while siblings remain (`grep -c '^attachments:'` == 1) — this is
  what fails if the new branch fires too eagerly.

(The neighbour-key guard lands in the same section — see the Pre-phase block.)

### 3. `tests/test_artifact_cli.sh` — CLI-level regression (the reported bug)

- Fixture: add one clean task in the setup block (~line 38), next to the existing
  `mk_task` calls: `mk_task t11_roundtrip > aitasks/t11_roundtrip.md`. It owns no
  artifacts, so no existing assertion is affected (section H's byte-identical
  `artifacts:` block check runs on `t5_demo`, which keeps `art:t5-htmlplan`
  throughout).
- New subsection `F11`, after `F10`:
  - snapshot the task file minus its `updated_at` line;
  - `"$ART" create 11 rt.txt --kind report --handle art:t11-rt` → assert the
    `artifacts:` block appeared (proves the round trip starts from a real write,
    not a no-op);
  - `"$ART" rm 11 art:t11-rt` → assert:
    - `grep -c '^artifacts:'` is `0`;
    - the file minus `updated_at` equals the snapshot (byte-for-byte round trip);
    - **consumer-level ground truth:** `task_yaml.parse_frontmatter` reports the
      key as *absent* — `'artifacts' in meta` is false, pinning that the observed
      `artifacts: None` can no longer occur (this is the state the board reads,
      independent of the textual greps above);
    - `git status --porcelain -- aitasks/` is empty (rm still commits the cleanup).

### 4. Repair the two live residue files

Two active task files already carry the state the fix prevents (verified: both
lines are inside the frontmatter, both keys are bare):

- `aitasks/t635_gates_framework.md:9`
- `aitasks/t1159_shadow_review_loop_automation.md:15`

Delete those two `artifacts:` lines. **Do not bump `updated_at`** on either file:
the strip is a byte-level repair, not a task-content edit — a bare key and an
absent key are already indistinguishable to every reader (`read_yaml_mappings`
emits nothing for both; the board reads `meta.get("artifacts") or []`) — and
bumping the stamp would misreport both tasks as freshly touched in the board's
staleness view. Commit path-scoped with the task-data wrapper, separately from
the code commit:

```bash
./ait git commit -o -- aitasks/t635_gates_framework.md \
    aitasks/t1159_shadow_review_loop_automation.md \
    -m "ait: Strip dangling empty artifacts: keys from t635 and t1159"
```

Afterwards `grep -rn '^artifacts:$' aitasks/` must report only the two prose
occurrences (`t1515…md:51` inside its own fenced example, `t1231/t1231_1…md:48`
in the body) — no frontmatter hits.

### Post-phase (risk mitigations)

1. `[attach_suite_sweep]` After the helper change, run **the canonical suite list
   in `## Verification` below — every entry, no subset** — and report each file's
   own `Results: N/M passed` line. That list is the single source of truth for
   which suites this change obliges; it is not restated here. Any failure that
   names `attachments:` is a caller depending on the bare key surviving
   `ait attach rm` — diagnose it before proceeding, and do not adjust the
   assertion to match the new behaviour without saying so.
2. `[acceptance_crosscheck]` Re-read t1515's "Suggested fix" and the folded
   t1285's three acceptance criteria, and state for each which delivered test
   satisfies it: (a) last-artifact rm drops the key, (b) non-last rm leaves
   remaining entries untouched, (c) a `tests/test_artifact_cli.sh` test asserting
   the frontmatter round-trips to its pre-create state. Name any criterion not
   covered rather than declaring the task done.

## Verification

**Canonical suite list** — the one referenced by `attach_suite_sweep`. Run every
entry and report each file's own `Results: N/M passed` line:

```bash
bash tests/test_attach_meta.sh                # unit: round trip, sibling control, neighbour-key guard
bash tests/test_artifact_cli.sh               # e2e: F11 plus the whole rm suite
bash tests/test_attach_local_backend.sh       # `ait attach rm` — the second caller of the changed helper
bash tests/test_attach_scaffold.sh            # reader contract: absent vs [] vs bare key
bash tests/test_attach_fold_rebind.sh
bash tests/test_attach_task_delete_decref.sh
bash tests/test_artifact_fold_transfer.sh
bash tests/test_artifact_share_resolution.sh
bash tests/run_all_python_tests.sh --test-dir tests   # test_atomic_write.py drives cmd_remove directly
```

Read the python runner's **last line** only (`PYTHON SUITE: PASSED|FAILED
(runner=…, exit=N)`); an earlier `Results:` line belongs to one script-style
module, not the suite. No `.aitask-scripts/*.sh` file is modified by this task, so
the project shellcheck target does not apply; instead run `shellcheck
tests/test_attach_meta.sh tests/test_artifact_cli.sh` and compare against its
pre-change output — only newly-introduced findings matter (these files are not
guaranteed clean today).

**Negative control for the fix itself.** Revert only the new `if` block in
`cmd_remove` and re-run the two edited test files. Exactly these **five** new
assertions must fail — every one of them reads the same branch, so a smaller
failure set means a test is not actually testing the fix:

| file | assertion |
|---|---|
| `test_attach_meta.sh` | append → remove restores the file byte-for-byte |
| `test_attach_meta.sh` | no bare `attachments:` key survives the round trip |
| `test_artifact_cli.sh` F11 | no bare `artifacts:` key survives the round trip |
| `test_artifact_cli.sh` F11 | create → rm restores the task file (modulo `updated_at`) |
| `test_artifact_cli.sh` F11 | parsed frontmatter has no `artifacts` key |

And these must still **pass** with the block reverted — they are the controls, and
a failure among them means the new tests are over-broad: the multi-item sibling
control, the `neighbour_key_control` guard, F11's `git status` assertion, and
every pre-existing assertion in both files. Restore the block and confirm both
files pass in full before landing.

Plus, after change 4: `grep -rn '^artifacts:$' aitasks/` returns no frontmatter
hit, and `git status --porcelain -- aitasks/` is clean once both commits land.

Step 9 (Post-Implementation) handles cleanup, merge to `main`, and archival.

## Risk

### Code-health risk: low

- The emptied-block sweep deletes every remaining line of the block (a trailing
  comment or blank line inside the field's extent), so a file with decorated
  frontmatter loses those lines along with the field · severity: low · → mitigation: inline pre-phase neighbour_key_control
- The fix lands in a shared helper, so `ait attach rm` changes behaviour too —
  a caller or test could depend on the bare `attachments:` key surviving · severity: low · → mitigation: inline post-phase attach_suite_sweep

### Goal-achievement risk: low

- The task text suggests fixing "in `aitask_artifact.sh`'s `rm` path"; the actual
  defect is one level down in `frontmatter_patch.py`, so the delivered change is
  broader than the literal suggestion, and it must still satisfy both this task's
  and the folded t1285's acceptance criteria · severity: low · → mitigation: inline post-phase acceptance_crosscheck

### Planned mitigations
- timing: pre-phase | name: neighbour_key_control | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — emptied-block sweep extent | desc: guard test pinning that a top-level key following the emptied block survives the sweep
- timing: post-phase | name: attach_suite_sweep | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared helper also changes `ait attach rm` | desc: run the attach/artifact/fold suites as a group and diagnose any failure naming `attachments:`
- timing: post-phase | name: acceptance_crosscheck | type: chore | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — fix lands below where the task points | desc: map t1515's suggested fix and t1285's three acceptance criteria onto the delivered tests

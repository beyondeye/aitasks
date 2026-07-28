---
Task: t1302_board_error_handling_and_frontmatter_ordering_defects.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1302 — Board error handling & frontmatter ordering defects

## Context

Two pre-existing defects were surfaced during t1243_1 while building the
board-movement characterization harness (`tests/test_board_movement.py`).
Neither caused the symptom t1243_1 addressed, so both were carried out as this
standalone bug task. They are unrelated to each other beyond provenance.

**Defect 1 — `refresh_git_status` degrades on fewer failures than its twin.**
`.aitask-scripts/board/aitask_board.py:1044` catches
`(subprocess.TimeoutExpired, FileNotFoundError)`, while `refresh_lock_map`
directly below it (`:1067`) catches `(subprocess.TimeoutExpired,
FileNotFoundError, OSError)`. A `PermissionError` (or any other `OSError`) from
`subprocess.run` therefore propagates out of a board refresh instead of
degrading to "no git status". Every board refresh and every task-move keypress
goes through this call, so the un-caught path crashes the TUI.

**Defect 2 — `serialize_frontmatter` does not honour its documented ordering.**
`.aitask-scripts/lib/task_yaml.py:143-164` documents "board keys (`boardcol`,
`boardidx`) always last", but it inserts `original_key_order` first and then
*re-assigns* the board keys. Re-assigning a key already present in a dict does
not move it, so a task file with `boardcol` mid-frontmatter keeps it there.
Reproduction from the task:

```python
raw = "---\npriority: high\nboardcol: now\nstatus: Ready\nboardidx: 10\n---\nbody\n"
serialize_frontmatter(*parse_frontmatter(raw))
# -> priority, boardcol, status, boardidx   (board keys NOT last)
```

Round-trip is byte-stable, so this is a contract discrepancy rather than data
loss — but **t1243_8 splits `BOARD_KEYS` into `BOARD_LAYOUT_KEYS` /
`BOARD_KEYS` and adds `boardgroup` to the serializer's ordering rule**
(`aitasks/t1243/t1243_8_boardgroup_field_and_model.md:57-67`), so it would
inherit the wrong guarantee. Fix the implementation, not the docstring.

Intended outcome: a board refresh degrades gracefully on any environment
failure, and the serializer's ordering contract is true as written — **without
rewriting any currently-valid task file**.

## Changes

### 1. `.aitask-scripts/board/aitask_board.py:1044`

Widen the handler to exactly match its twin at `:1067`:

```python
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
```

Textually identical to `refresh_lock_map`'s tuple, so the two degrade-on-failure
paths are greppably the same (their silent divergence is what produced this
bug). `FileNotFoundError` is an `OSError` subclass and so is redundant — it is
kept for symmetry with the neighbour rather than trimmed, and
`refresh_lock_map` is **not** touched.

Deliberately **not** doing the alternative the task offers (factoring the shared
"run a helper subprocess, degrade on failure" pattern out of both call sites):
`aitask_board.py` has 30+ `subprocess.run` sites with differing degrade
semantics, so a shared helper is a module-wide refactor well outside this bug's
scope.

### 2. `.aitask-scripts/lib/task_yaml.py:152-164`

Two things must both hold: board keys end up last, **and** every file that is
already valid keeps its exact bytes. A naive `for key in BOARD_KEYS` tail loop
delivers the first and breaks the second — it imposes the canonical
`boardcol, boardidx` order, and **36 live task files end `boardidx, boardcol`**
(see corpus survey below), so all 36 would be rewritten on their next save.

So: skip board keys in the original-order loop, then re-append them last
**preserving whatever relative order they already had**, with any newly
introduced board key appended after them in canonical `BOARD_KEYS` order.

```python
    ordered = {}
    # Original keys first. Board keys are skipped here so the tail loop can
    # genuinely move them last: re-assigning an already-present dict key does
    # NOT reposition it, which is what silently broke the contract below.
    for key in original_key_order:
        if key in metadata and key not in BOARD_KEYS:
            ordered[key] = metadata[key]
    # Any new non-board keys
    for key in metadata:
        if key not in ordered and key not in BOARD_KEYS:
            ordered[key] = metadata[key]
    # Board keys always last, in the relative order the file already used —
    # imposing BOARD_KEYS order instead would rewrite every task file that
    # happens to carry boardidx before boardcol. Board keys not present in the
    # original order are newly introduced and append in canonical order.
    seen_board = [k for k in original_key_order if k in BOARD_KEYS and k in metadata]
    for key in seen_board + [k for k in BOARD_KEYS
                             if k in metadata and k not in seen_board]:
        ordered[key] = metadata[key]
```

The docstring's claim is now true; extend it with the order-preservation clause.

**Corpus survey (re-run, order-sensitive).** Across the 168 task files under
`aitasks/` that carry board keys:

| Trailing shape | Files | Effect of this change |
|---|---|---|
| `boardidx` only | 97 | byte-identical |
| `boardcol, boardidx` | 35 | byte-identical |
| `boardidx, boardcol` | 36 | byte-identical (order preserved) |
| board key mid-frontmatter | 0 | — |

The algorithm above was prototyped against all five shapes (the four in the
table plus the task's repro) and confirmed: repro fixed, all live shapes
byte-stable, a newly-added board key appended last. Byte-stability for the
well-formed shape — which `tests/test_board_movement.py`'s fixture relies on
(`_fixture_text`, lines 92-104) — is preserved exactly.

The three callers are unaffected: `Task.save()` (`aitask_board.py:247`),
`aitask_merge.py:460` (passes `merged_keys` as `original_key_order`; board keys
still land last), and `tests/test_update_multiline_yaml.sh:209` (no board keys
in its input).

### 3. New tests

**`tests/test_task_yaml_key_order.py`** — unit tests on `lib/task_yaml.py`:
1. The task's exact reproduction: `boardcol` mid-frontmatter serializes last.
2. **Reverse-order round-trip:** a file ending `boardidx, boardcol` round-trips
   **byte-identically** (this is the regression the canonical-order loop would
   have caused, and it covers 36 live files).
3. Forward-order round-trip: a file ending `boardcol, boardidx` is byte-stable.
4. A new non-board key added to `metadata` is emitted before the board keys; a
   newly added *board* key is appended after the pre-existing ones.

**`tests/test_board_refresh_degrade.py`** — loads the real `aitask_board` module
against a temp `TASK_DIR` using the established
`importlib.util.spec_from_file_location` pattern from
`tests/test_board_archived_relation_lookup.py:40-55`, and constructs a real
`TaskManager`. For each of `PermissionError`, a base
`OSError(errno.EMFILE, "too many open files")`, `FileNotFoundError` and
`subprocess.TimeoutExpired` — the full promised boundary — it:

- **seeds** `manager.modified_files = {"aitasks/t9999_stale.md"}` and
  `manager.lock_map = {"9999": {...}}` with sentinel entries,
- patches `subprocess.run` to raise,
- asserts the call returns without raising **and that the sentinel is gone**.

Seeding is the point: a fresh `TaskManager` starts with both collections empty,
so asserting "still empty" would only prove the exception was swallowed, not
that the failure degrades stale state to "no git status" / "no locks".
`refresh_lock_map` (the already-correct twin) is covered by the same
parametrized cases, pinning the pair together so a future edit cannot
re-diverge silently.

Both files follow the repo's `unittest` + `if __name__ == "__main__":
unittest.main()` convention and are picked up by `tests/run_all_python_tests.sh`.

## Verification

**The framework interpreter has no pytest**, so `run_all_python_tests.sh` falls
back to `unittest discover`, where `-k "A or B"` is a literal substring that
matches nothing — a targeted run written that way reports `Ran 0 tests` and
exits **0**. Never use it. Invoke the two modules directly (verified: this form
reports a real `Ran N tests` count) and **check that N is non-zero**:

```bash
PY=$( { source .aitask-scripts/lib/python_resolve.sh; require_ait_python; } )

env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$PY" tests/test_task_yaml_key_order.py -v
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$PY" tests/test_board_refresh_degrade.py -v
```

**Negative control — prove each test discriminates.** Revert each fix in place
(edit the source back; do **not** `git checkout`, which would wipe the other
uncommitted edits), re-run the corresponding module, confirm it now **fails**
with a non-zero count, then restore. Specifically confirm that reverting to the
naive `for key in BOARD_KEYS` tail loop fails the reverse-order round-trip test.

**Regression + full suite:**

```bash
env -u PYTHONPATH "$PY" tests/test_board_movement.py -v   # depends on byte-stability
bash tests/test_update_multiline_yaml.sh

set -o pipefail
bash tests/run_all_python_tests.sh 2>&1 | tail -20        # read the LAST line only:
                                                          # PYTHON SUITE: PASSED|FAILED
```

Then Step 9 (Post-Implementation): merge, `ait gates run 1302`, archival.

## Risk

### Code-health risk: low
- The serializer's tail loop must both honour the "board keys last" contract and
  avoid imposing a canonical order on the 36 live files that end
  `boardidx, boardcol`. The order-preserving formulation satisfies both and was
  prototyped against every shape present in the corpus, but the two requirements
  pull in opposite directions, so a future simplification of this loop could
  silently reintroduce mass rewrites · severity: low · → mitigation: pinned by
  the reverse-order round-trip test (case 2) rather than a follow-up task

### Goal-achievement risk: low
- None identified. Both defects have exact line anchors and a runnable
  reproduction; each fix is a direct, locally-verifiable consequence.

## Out of scope (report at Step 8b)

`revert_task` (`aitask_board.py:4529`), `_do_lock` (`:4712`) and `_do_unlock`
(`:4779`) catch the same too-narrow `(subprocess.TimeoutExpired,
FileNotFoundError)` tuple. They are user-triggered dialog actions rather than
refresh-path calls, and the task scopes this fix to `refresh_git_status` — so
they are left alone here and surfaced as upstream defects instead.

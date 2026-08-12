---
Task: t1488_fix_boardcol_test_scaffold_missing_record_protocol.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1488 — Fix the `test_boardcol_update.sh` scaffold's missing `record_protocol`

## Context

`tests/test_boardcol_update.sh` is **red on `main`** and has been for some time.
Its `setup_project()` copies a hand-maintained subset of Python modules into an
isolated scaffold:

```bash
for m in board_columns board_ordering config_utils task_yaml; do
    cp "$PROJECT_DIR/.aitask-scripts/lib/$m.py" .aitask-scripts/lib/
done
```

`.aitask-scripts/lib/board_columns.py:73` does `from record_protocol import (…)`,
and `record_protocol.py` is not in that list, so importing `board_columns` inside
the scaffold raises `ModuleNotFoundError: No module named 'record_protocol'`.

**Reproduced and pinned in this session:**

- `bash tests/test_boardcol_update.sh` prints only its first test header and
  exits 1 — no `FAIL:` line, no summary, no error text.
- `board_columns.py`'s local-module imports are exactly
  `{atomic_write, board_ordering, config_utils, record_protocol, task_yaml}`.
  `atomic_write.py` is already copied unconditionally by
  `setup_fake_aitask_repo` (`tests/lib/test_scaffold.sh`), so `record_protocol`
  is the **sole** missing one — confirmed with a meta-path block that fails the
  import chain at exactly that module.
- The failure is masked twice: `aitask_update.sh … >/dev/null 2>&1` discards the
  diagnostic, and `set -e` aborts the file at that first call.

Note that `normalize_board_column` (`.aitask-scripts/lib/task_utils.sh:928`)
itself runs the probe with `2>/dev/null`, so the `ModuleNotFoundError` never
reaches the caller anyway — what *is* recoverable is its own named message,
`Error: board column 'c1': could not read the configured column list.`

**Intended outcome:** the suite runs green, the copy list stops being a
hand-maintained drift source, and the next such breakage reports itself with a
named `FAIL:` line **carrying the diagnostic** instead of vanishing.

## Approach

1. **Derive the module closure** instead of extending the hand-maintained list
   (the list has now drifted once; any future import added to `board_columns.py`
   breaks the scaffold the same silent way).
2. **Make the probe's health an explicit assertion**, so a broken scaffold fails
   by name rather than by `set -e` abort.
3. **Stop discarding stderr** on the `--boardcol` invocations *and make sure the
   captured text reaches the failure message* — an exit code alone reproduces the
   original defect one level up.
4. **Unit-test the closure helper's own branches**, which the `board_columns`
   chain does not reach — with assertions that can actually fail.

### 1. `tests/lib/test_scaffold.sh` — the closure helper

Two functions, split so the logic is drivable against a synthetic lib tree
without any test-only override:

```bash
# Copy Python modules from <src_lib> into <dst_lib> along with every <src_lib>
# sibling they transitively import. Roots are the entry points a test actually
# drives; the transitive deps are derived, so a new import in a copied module
# can no longer break a scaffold silently (t1488).
#
#   copy_py_closure_from "$PROJECT_DIR/.aitask-scripts/lib" "$d/lib" board_columns
#
# Import extraction is a line scan of `import X` / `from X import …` (top-level
# AND function-local, deliberately — over-copying a lazily-imported module is
# harmless, missing one is not). Docstring prose matches the same shape, so
# every candidate is filtered by "does <src_lib>/<name>.py exist" — that
# existence check is also what drops stdlib and third-party names (os, json,
# yaml, …).
#
# BLIND SPOT: imports built dynamically (importlib, __import__) are invisible to
# a line scan. The derived closure is not exhaustive; a caller relying on a
# dynamic import must pass that module as an explicit root.
#
# Handles diamonds (a module reached twice is copied once) and terminates on an
# import cycle. bash-3.2-safe: no `declare -A`, no `mapfile` (same constraint
# asserts.sh documents).
#
# OUTPUTS (documented contract, readable by the caller after return):
#   AIT_PY_CLOSURE_MODULES  space-delimited closure, appended at the seen-marking
#   AIT_PY_CLOSURE_COPIED   count of `cp` invocations, bumped after each copy
# The two are bumped at deliberately DIFFERENT points, so they agree only when
# the dedup guard holds — a regressed guard shows up as COPIED exceeding the
# module count. tests/test_scaffold_py_closure.sh asserts exactly that.
copy_py_closure_from() { ... }

# Scaffold-flavored wrapper: source lib is the real repo's, destination is the
# scaffold's. One line over copy_py_closure_from.
copy_lib_py_closure() {   # <repo_dir> <module>...
    local repo_dir="$1"; shift
    copy_py_closure_from "$PROJECT_DIR/.aitask-scripts/lib" \
                         "$repo_dir/.aitask-scripts/lib" "$@"
}
```

Implementation shape — recursion, not an array queue (keeps it `set -u`-safe on
bash 3.2, where expanding an empty array is an error):

- `copy_py_closure_from <src_lib> <dst_lib> <module>…`: `mkdir -p "$dst_lib"`,
  reset `AIT_PY_CLOSURE_MODULES=""`, `AIT_PY_CLOSURE_COPIED=0` and the private
  `_AIT_PY_CLOSURE_CALLS=0`, then call the recursive worker once per root.
- `_copy_py_closure_visit <src_lib> <dst_lib> <module>`:
  - **Convergence fail-safe:** bump the monotonic `_AIT_PY_CLOSURE_CALLS`; above
    512 visits, print `the dedup guard is not converging` on stderr and
    `return 1`. A monotonic *call* counter needs no decrement on the return
    paths, and it turns a regressed dedup guard into a named, bounded failure
    instead of a hang — exactly the failure mode this task exists to remove.
  - Return 0 if `$mod` is already in `AIT_PY_CLOSURE_MODULES`; append it
    **before** recursing, so an import cycle terminates.
  - **Fail loudly** (message on stderr + `return 1`) if `$src_lib/$mod.py` does
    not exist — a typo'd root must not degrade into a silent no-op.
  - `cp`, bump `AIT_PY_CLOSURE_COPIED`, then recurse over each derived local dep.
- `_py_local_imports <file> <src_lib>` prints one dep per line via `awk`:
  `from X import …` (`$2`, cut at the first non-identifier char) and
  `import X[, Y][ as Z]` (split the tail on `,`, trim, cut), `sort -u`, then keep
  only names for which `$src_lib/<name>.py` exists.

`awk`/`sort`/`cp` only — no GNU-only flags, per
`aidocs/framework/sed_macos_issues.md`.

### 2. `tests/lib/asserts.sh` — an exit-code assert that prints the output

The existing `assert_exit_zero_rc` reports only the number. That is precisely
what makes a tooling breakage unreadable: the cause is in the output the caller
already captured. Add the sibling (same family as the four existing exit-code
helpers, so it belongs in the shared file rather than inline):

```bash
# Like assert_exit_zero_rc, but prints the command's captured output on failure.
# Use whenever the captured text is the diagnostic (scaffold breakage, tooling
# errors) — an exit code alone reproduces the silent-failure defect one level up
# (t1488).
assert_exit_zero_rc_out() {
    local desc="$1" rc="$2" out="$3"
    if [[ "$rc" -eq 0 ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected zero exit, got $rc; output: $out)"
    fi
}
```

No `_nonzero` sibling: the one non-zero case in this file already asserts on the
captured output via `assert_contains`.

### 3. `tests/test_boardcol_update.sh` — use the closure, surface the diagnostic

- Replace the `for m in …` loop with:

  ```bash
  # board_columns is the only Python entry point the scaffolded scripts drive
  # (aitask_board_column.sh execs it); its transitive lib/ deps are derived.
  copy_lib_py_closure "$PWD" board_columns
  ```

  This yields `{board_columns, atomic_write, board_ordering, config_utils,
  record_protocol, task_yaml}` — a strict superset of today's list.

- **Add a first test, `test_scaffold_column_probe_works`**, running the exact
  seam `normalize_board_column` probes, with stderr captured rather than
  discarded:

  ```bash
  out="$(./.aitask-scripts/aitask_board_column.sh list-columns \
           --root . --task-dir aitasks --include-unordered 2>&1)" || rc=$?
  assert_exit_zero_rc_out "scaffold column probe exits zero" "$rc" "$out"
  assert_contains "probe lists the configured columns" "COLUMN:c1|" "$out"
  ```

  A missing module then surfaces as `ModuleNotFoundError: No module named '…'`
  inside a named `FAIL:` line. This is the guard that converts the whole
  silent-death class into a visible assertion — and, unlike a re-scan of
  `board_columns.py`'s imports, it is **independent ground truth**: it runs the
  real entry point rather than re-deriving the same list the fix derives.

- **Change the three success-path invocations** from
  `./…/aitask_update.sh --batch 1 --boardcol X >/dev/null 2>&1` to capture *and
  report*:

  ```bash
  local out rc=0
  out="$(./.aitask-scripts/aitask_update.sh --batch 1 --boardcol c1 2>&1)" || rc=$?
  assert_exit_zero_rc_out "configured id accepted" "$rc" "$out"
  assert_contains "configured id written" "boardcol: c1" "$(cat aitasks/t1_alpha.md)"
  ```

  `… || rc=$?` disables `errexit` for that command, so a non-zero exit becomes a
  reported `FAIL:` **naming the command's own error text** instead of a
  file-level abort. The `--boardcol ""` clearing case already captures `rc`; swap
  its `>/dev/null 2>&1` for a captured `out` fed to `assert_exit_zero_rc_out`.

- Leave the existing local `assert_nonzero` alone; unrelated to this fix.

### 4. `tests/test_scaffold_py_closure.sh` — new focused test for the helper

`copy_py_closure_from` is shared and its dedup / cycle / error branches are
**unreachable** from the `board_columns` chain (a plain tree — and `sort -u`
collapses the three `atomic_write` import lines before recursion, so even the
repeated-import path never exercises the seen-check). Drive it directly against
synthetic `src_lib` / `dst_lib` directories built in a `mktemp -d`.

**Destination inspection alone cannot fail on a dedup regression** — two `cp`s of
the same file are byte-identical to one. Every dedup claim therefore asserts on
`AIT_PY_CLOSURE_COPIED` (bumped per `cp`) against the module count derived from
`AIT_PY_CLOSURE_MODULES` (bumped at seen-marking); the two disagree exactly when
the guard regresses.

| case | asserts |
|---|---|
| chain `a→b→c` | `MODULES` = `{a,b,c}`, `COPIED` = 3, all three present, exit 0 |
| diamond `a→{b,c}`, `b→d`, `c→d` | `MODULES` = `{a,b,c,d}` **and `COPIED` = 4** — a regressed seen-check yields 5 · exit 0 |
| cycle `a→b`, `b→a` | terminates, exit 0, `COPIED` = 2 |
| two roots sharing a dep, one call | `COPIED` = module count (dedup spans roots) |
| two separate calls | `MODULES`/`COPIED` reset per call, not accumulated |
| docstring prose (`from the same old text, …`) | no error, `the.py` not fabricated |
| stdlib / third-party names (`os`, `yaml`) | not copied |
| `import x, y` and `import x as z` | both `x` and `y` copied |
| indented (function-local) import | copied |
| missing root module | non-zero exit, message names the module |
| missing *dep* whose `.py` does not exist | silently skipped (that is the stdlib filter) |

The convergence fail-safe makes the cycle case deterministic on any bash: if the
seen-check is regressed away entirely, the run ends non-zero with the
`not converging` message instead of hanging.

### Out of scope (noted, not done)

The helper is deliberately reusable, but the ~8 other test files that hand-copy
`.py` modules are **not** migrated here. Checked statically: `launch_modes.py`
has no local imports, and `gate_ledger.py`'s only local import
(`gate_registry_sync`) is function-local to the `sync-registry` subcommand,
which those tests never invoke — so none of them is currently red for this
reason.

## Files to modify

- `tests/lib/test_scaffold.sh` — add `copy_py_closure_from`,
  `copy_lib_py_closure`, `_copy_py_closure_visit`, `_py_local_imports`.
- `tests/lib/asserts.sh` — add `assert_exit_zero_rc_out`.
- `tests/test_boardcol_update.sh` — use the closure; add the probe test; capture
  and report stderr on the update invocations; update the file header comment.
- `tests/test_scaffold_py_closure.sh` — **new**, unit-tests the helper.

## Verification

1. `bash tests/test_boardcol_update.sh` runs to completion and prints
   `Results: N/N passed, 0 failed`, exit 0.
2. `bash tests/test_scaffold_py_closure.sh` — `0 failed`, exit 0.
3. **Negative control A (scaffold closure):** temporarily make `_py_local_imports`
   drop `record_protocol` (a one-line filter). Expect
   `bash tests/test_boardcol_update.sh` to reach its summary with
   `FAIL: scaffold column probe exits zero (expected zero exit, got 1; output:
   …ModuleNotFoundError: No module named 'record_protocol'…)` and exit 1. A
   *passing* run under this mutation means the guard is wrong. Revert.
4. **Negative control B (dedup guard removed):** delete the
   `AIT_PY_CLOSURE_MODULES` early-return outright. Expect
   `tests/test_scaffold_py_closure.sh` to fail the **cycle** case by name via the
   convergence fail-safe (`not converging`) rather than hang. Revert.
5. **Negative control C (dedup guard degraded to cycles-only)** — the case the
   destination-only assertion could not catch: make the early-return suppress
   only a module currently *on the recursion stack*, leaving diamonds
   unsuppressed. Expect the **cycle** case to still pass and the **diamond** case
   to fail by name with `COPIED` = 5 against a 4-module closure. Revert.
6. `shellcheck tests/test_boardcol_update.sh tests/test_scaffold_py_closure.sh
   tests/lib/test_scaffold.sh tests/lib/asserts.sh` clean.
7. Regression sweep over the shared libraries' other consumers:
   `bash tests/test_anchor_update.sh` (same scaffold + asserts),
   `bash tests/test_gate_guarded_archival.sh` (a `setup_fake_aitask_repo` user
   that copies `.py` modules), and one heavy `asserts.sh` consumer.

## Risk

### Code-health risk: low

- `copy_py_closure_from` and `assert_exit_zero_rc_out` land in **shared** test
  libraries, so a defect could in principle reach other scaffolded tests ·
  severity: low · → mitigation: both are purely additive — no existing helper or
  scaffold behaviour changes — and the new focused test covers the helper's own
  branches with assertions proven able to fail (negative controls B and C).
- The helper now exposes two globals (`AIT_PY_CLOSURE_MODULES` /
  `AIT_PY_CLOSURE_COPIED`) as observable contract · severity: low · → mitigation:
  documented in the header comment as outputs, reset per call, and the "two
  separate calls" test case pins the reset.
- A line scan cannot see dynamically built imports (`importlib`, `__import__`),
  so the derived closure is not exhaustive · severity: low · → mitigation:
  inline post-phase `document_closure_blind_spot`

### Goal-achievement risk: low

- None identified. The defect is reproduced, the missing module is pinned to
  exactly one name, and the task file's acceptance criteria map 1:1 onto the
  verification steps above.

### Planned mitigations
- timing: post-phase | name: document_closure_blind_spot | type: documentation | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: dynamic imports are invisible to the line scan | desc: state the importlib/__import__ blind spot in the helper's header comment so a future caller does not assume the derived closure is exhaustive

### Post-phase (risk mitigations)

**`document_closure_blind_spot`** — after the helper is written, confirm its
header comment carries the explicit `BLIND SPOT:` paragraph shown in §1,
including the instruction to pass a dynamically-imported module as an explicit
root.

## Step 9 (Post-Implementation)

Standard: merge to the branch named in the plan header, archive `t1488` and this
plan.

## Final Implementation Notes

- **Actual work done:** All four planned changes landed as designed, with no
  deviation in shape.
  - `tests/lib/test_scaffold.sh` (+130, **purely additive** — 0 deletions):
    `copy_py_closure_from <src_lib> <dst_lib> <module>…` plus the scaffold
    wrapper `copy_lib_py_closure <repo_dir> <module>…`, backed by
    `_copy_py_closure_visit` (recursive, marks-before-recursing) and
    `_py_local_imports` (an `awk` line scan filtered by "does
    `<src_lib>/<name>.py` exist"). Outputs `AIT_PY_CLOSURE_MODULES` /
    `AIT_PY_CLOSURE_COPIED`; private `_AIT_PY_CLOSURE_VISITS` against the
    `_AIT_PY_CLOSURE_MAX_VISITS=512` convergence ceiling.
  - `tests/lib/asserts.sh` (+16): `assert_exit_zero_rc_out`.
  - `tests/test_boardcol_update.sh`: closure call replaces the copy list; new
    first test `test_scaffold_column_probe_works`; all four `aitask_update.sh`
    / probe invocations capture and report output instead of `>/dev/null 2>&1`;
    header comment records why.
  - `tests/test_scaffold_py_closure.sh` (new): 13 cases / 38 assertions.
- **Deviations from plan:** None in substance. Two additions the plan implied
  but did not enumerate: a `test_convergence_failsafe_fires` case (drives the
  512-visit ceiling down to 2 and asserts the `not converging` message, so
  negative control B's expected outcome is grounded rather than assumed), and a
  `test_real_board_columns_closure` case asserting the production graph really
  does pull in `record_protocol.py` / `atomic_write.py` / `task_yaml.py`.
- **Issues encountered:**
  - The plan-mode session exited unexpectedly mid-exploration and had to be
    re-entered; no work was lost.
  - The HEAD-comparison control could not run in a `git worktree` — task data
    lives on the separate `aitask-data` branch, so a detached worktree has no
    `aitasks/metadata/`. Worked around by copying the three modified files
    aside, `git checkout HEAD --` on them, running the control, and restoring.
  - `assert_exit_zero_rc` alone was insufficient (raised in review): it prints
    only the number, so the captured diagnostic still vanished. Hence
    `assert_exit_zero_rc_out`.
  - Destination inspection cannot prove "copied once" (raised in review): two
    `cp`s of one file are byte-identical to one. Hence the
    `AIT_PY_CLOSURE_COPIED` vs `AIT_PY_CLOSURE_MODULES` cross-check, bumped at
    deliberately different points.
- **Key decisions:**
  - Derived closure over an extended list — the list had already drifted once,
    and every future import would break the scaffold the same silent way.
  - Recursion, not an array queue: bash 3.2 + `set -u` errors on expanding an
    empty array.
  - Existence-filtered naive scan over a Python `ast` walk: no interpreter
    dependency at scaffold time, and the filter is what makes docstring prose
    and stdlib names harmless. Documented blind spot: dynamic imports.
  - A monotonic *visit* counter rather than a depth counter — no decrement on
    any return path, and it converts runaway recursion into a bounded named
    failure instead of a hang.
  - `assert_exit_zero_rc_out` went into shared `asserts.sh` rather than inline:
    it is a generic exit-code helper in the same family as the four already
    there, not a domain-specific one.
- **Verification performed:**
  - `bash tests/test_boardcol_update.sh` — 13/13, exit 0 (previously: first test
    header then a silent exit 1).
  - `bash tests/test_scaffold_py_closure.sh` — 38/38, exit 0.
  - Negative control A (drop `record_protocol` from the scan): run reaches its
    summary with `FAIL: scaffold column probe exits zero (expected zero exit,
    got 1; output: … ModuleNotFoundError: No module named 'record_protocol')`,
    exit 1. The unit test independently fails `record_protocol.py in the
    closure`. Reverted.
  - Negative control B (dedup guard removed): cycle case terminates via the
    fail-safe at 512 visits — no hang — with 10 named failures. Reverted.
  - Negative control C (dedup degraded to cycles-only — the case destination
    inspection could not catch): cycle case **passes**, diamond fails
    `diamond copies d exactly once (expected '4', got '5')`. Reverted; `git
    diff --stat` re-confirmed 130 insertions / 0 deletions.
  - `shellcheck -x -e SC1091` on all four files: clean. SC1091 is the
    source-following info present on every untouched test file too.
  - Full sweep of all 69 `tests/lib/test_scaffold.sh` consumers: 68 pass.
- **Upstream defects identified:**
  - `tests/test_brainstorm_cli.sh:? — "archive outputs NO_PLAN warning" fails on
    main; brainstorm archive prints only "Finalizing brainstorm session for task
    999..." without the expected NO_PLAN warning`. Proven pre-existing: with the
    three modified files reverted to their HEAD versions the failure reproduces
    byte-identically (29 pass / 1 fail / 30 total, same assertion).
- **Not done, deliberately:** the other test files that hand-copy `.py` modules
  were not migrated to the new helper. Checked statically — `launch_modes.py`
  has no local imports, and `gate_ledger.py`'s only local import
  (`gate_registry_sync`) is function-local to the `sync-registry` subcommand
  those tests never invoke — so none of them is currently red for this reason.

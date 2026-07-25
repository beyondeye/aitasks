---
Task: t1229_guard_no_zero_collection_test_files.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
---

# t1229 — Guard: no zero-collection test files

## Context

t1211 fixed the Python aggregate suite (`bash tests/run_all_python_tests.sh`)
so a real regression is distinguishable from standing noise. During that work
it found **six** `tests/test_*.py` files that were script-style or
import-guarded and therefore contributed **zero** collected tests — silently
dropping 102 checks out of the aggregate gate. Nothing currently prevents a
seventh such file from being added and silently ignored.

This task adds a **discovery guard**: a committed test that asserts every
`tests/test_*.py` contributes at least one collected test to `unittest`
discovery, and that no module fails to import. It closes the specific
goal-achievement risk recorded in t1211's plan (AC-2's negative control was a
manual, non-committed step) and the broader defect-2 class.

## Key findings from exploration (empirically verified, do not re-derive)

Run under the harness interpreter (`require_ait_python` → `~/.aitask/venv/bin/python`,
Python 3.14) with `PYTHONPATH` = board + lib:

- **Attribution must be by FILE, not by class-definition site.** A single
  top-level `discover` flattened and keyed by `type(test).__module__` reports
  the module where each `TestCase` *class is defined* — so a wrapper/re-export
  file (`from other_test import SomeCase`) would be misreported as
  zero-collection even though it contributes runnable tests, and an allowlist
  entry would then waive a real file. The guard therefore **discovers each
  expected file independently**: `discover(start_dir=tests, pattern="<exact
  filename>")` loads only that file's module and `loadTestsFromModule` counts
  every `TestCase` reachable *from that file* (defined or imported).
  Empirically: a wrapper file that only subclasses an imported base is counted
  as **3** (not zero); a base + wrapper both report ≥1.
- Test ids from per-file discovery are `test_<stem>.Class.method`; the guard
  needs only the **count** and the failed-flag per file, not the ids.
- **Baseline is clean:** 142 `tests/test_*.py` files, **all** with ≥1 collected
  test, **0** `_FailedTest` entries. So **no exclusion list is needed** on day
  one. The whole per-file sweep runs in **~0.5 s** in one subprocess (modules
  are `sys.modules`-cached across the 142 `discover` calls).
- A file that **fails to import** appears in *its own* per-file discovery as a
  `unittest.loader._FailedTest` instance (`type(t).__name__ == "_FailedTest"`),
  yielding count 0 for that file — the guard flags it via a per-file
  `failed` flag so a broken file is reported distinctly from a legitimately
  empty one (rather than registering as a passing "test").
- A **zero-collection** file (script-style with `if __name__ == "__main__":`
  guard and no `TestCase`) yields count 0 with no `_FailedTest` — it silently
  vanishes from the aggregate suite. This is the exact failure the guard catches.
- `run_all_python_tests.sh` prefers **pytest** when installed and falls back to
  **unittest discovery**. This guard validates the **unittest-discovery
  branch**: it always runs its own `unittest discover` subprocess regardless of
  whether pytest is installed, so its verdict is deterministic. (Documented in
  the guard's module docstring per AC-4.)

## Approach

Add one new file, `tests/test_no_zero_collection.py`, a normal
`unittest.TestCase` guard that inspects discovery **externally via a
subprocess** (never importing its siblings in-process — that would be circular
and re-trigger import-time side effects).

### Structure of `tests/test_no_zero_collection.py`

1. **Module docstring** — states the invariant, that it validates the
   `unittest discover` fallback branch of `run_all_python_tests.sh` (not the
   pytest branch), and why discovery must be external (t1229 / t1211 defect-2).

2. **`_PROBE_SRC`** — a self-contained Python source string run as
   `[sys.executable, "-c", _PROBE_SRC, <tests_dir>, <result_path>]`. It:
   - globs `<tests_dir>/test_*.py`,
   - for **each** file, `discover(start_dir=tests_dir, pattern="<basename>")`
     (per-file attribution), walks that file's suite, counts non-`_FailedTest`
     leaves into `counts[stem]` and sets a per-file `failed` flag when a
     `_FailedTest` leaf appears (appending `stem` to a `failed` list),
   - writes `json.dumps({"counts": counts, "failed": failed})` to the
     **result file** at `<result_path>` (argv[2]) — **not** to stdout.

   Using `sys.executable` guarantees the **same interpreter** as the harness
   (the guard is itself run under `$PY`). The subprocess isolates all
   import-time side effects. **The result goes to a dedicated file channel** so
   any import-time banner/debug output on the subprocess's stdout or stderr
   cannot corrupt the protocol (verified: a stray `print()` during import
   leaves the JSON result intact).

3. **`_run_probe(tests_dir) -> (counts: dict[str,int], failed: list[str])`** —
   creates a `tempfile.NamedTemporaryFile` result path; builds the subprocess
   env: copy `os.environ`, prepend `.aitask-scripts/board` and
   `.aitask-scripts/lib` (computed from `REPO_ROOT =
   Path(__file__).resolve().parent.parent`) to `PYTHONPATH`, set
   `PYTHONDONTWRITEBYTECODE=1` — mirroring `run_all_python_tests.sh:17-19` so a
   direct `python tests/test_no_zero_collection.py` run also works, not only
   the harness. `subprocess.run([sys.executable, "-c", _PROBE_SRC, tests_dir,
   result_path], capture_output=True, text=True)`; on non-zero exit, fail with
   the captured stderr; otherwise read+parse JSON from the **result file**
   (stdout/stderr are ignored for the protocol, surfaced only in failure
   messages). Clean up the temp file.

4. **`ZERO_COLLECTION_ALLOWLIST: frozenset[str] = frozenset()`** — explicit,
   commented, **empty**. A comment states: if a file legitimately collects zero
   tests, add its stem here with a one-line justification — never a silent skip.

5. **`NoZeroCollectionTests(unittest.TestCase)`** — the real guard. The probe
   returns a `counts` map keyed by **every** `test_*.py` stem (a zero-collection
   file is present with value `0`, not absent), plus a `failed` list. Cache the
   real-tree probe result in `setUpClass` (one ~0.5 s subprocess for the whole
   case) since both tests read it:
   - `test_every_test_file_contributes_a_collected_test` (AC-1): compute
     `zero = {stem for stem, n in counts.items() if n == 0} -
     ZERO_COLLECTION_ALLOWLIST`; `assertFalse(zero, …)` with a message naming
     the offending files and pointing at the allowlist.
   - `test_no_module_fails_to_import` (AC-2): assert `failed == []`, message
     naming the failing stems and the likely import-error cause.

6. **`GuardFalsifiabilityTests(unittest.TestCase)`** (AC-5, negative control,
   committed & automated — not a manual step): in a `tempfile.TemporaryDirectory`,
   write a synthetic `tests/` dir with **five** files that pin every behavior
   the guard depends on (each fixture makes a specific regression fail loudly,
   so the two hardening guarantees are permanent, not just planning evidence):
   - `test_good.py` — one `TestCase`, one passing method (baseline positive).
   - `test_zerocollect.py` — script-style, `def main(): return 0` + `__main__`
     guard, **no** `TestCase` (the zero-collection defect).
   - `test_broken.py` — `import a_module_that_does_not_exist_zzz` at top (the
     import-failure defect).
   - `test_base_fixture.py` + `test_wrapper_reexport.py` — the base defines a
     `TestCase` with a test; the wrapper does **only** `from test_base_fixture
     import Base` (no own method, no subclass). **Pins per-file attribution:**
     under the rejected class-origin (`type(t).__module__`) attribution the
     wrapper would count 0 and this fixture would falsely flag it. (Verified:
     the pure re-export wrapper counts as 1.)
   - `test_noisy.py` — prints a banner to **stdout at import time** and has a
     normal `TestCase`. **Pins the result-file protocol:** if `_run_probe`
     regressed to parsing bare stdout JSON, the banner would corrupt the parse
     and this fixture would error/fail. (Verified: banner on stdout, result
     file intact.)

   Run the same `_run_probe` against that dir and assert the oracle behaves
   exactly: `counts["test_zerocollect"] == 0`; `test_broken` in `failed`;
   `counts["test_good"] >= 1`; `counts["test_wrapper_reexport"] >= 1`;
   `counts["test_noisy"] >= 1` (and `_run_probe` returned normally, i.e. the
   stdout banner did not break parsing); `failed == ["test_broken"]` (only the
   broken file). This proves the AC-1/AC-2 assertions are not vacuous **and**
   locks in the wrapper-attribution and noisy-stdout hardening. (Same
   `_run_probe` code path as the real test, so it also exercises the env/result-
   file plumbing.)

7. **`if __name__ == "__main__": unittest.main()`** — direct-run support,
   matching the repo idiom (e.g. `test_monitor_refresh_no_sync_tmux.py:241`).

### Why a subprocess TestCase satisfies the "no in-process import" constraint

The guard `TestCase` itself never imports sibling test modules; it shells out.
The subprocess does the `discover` (which imports siblings), but in an isolated
process whose side effects cannot pollute the running harness. The guard file
is itself discovered (it has `TestCase`s → ≥1 collected test, so it is not a
zero-collection file), and importing it during the inner probe only defines
classes — it never runs the subprocess-spawning methods, so there is **no
recursion**.

## Files to modify

- **`tests/test_no_zero_collection.py`** — new file (the entire deliverable).

No production code changes; no docs changes required beyond the self-documenting
module docstring (AC-4 is satisfied in-file).

## Verification

Preamble (harness-identical environment — a pass under bare `python3` proves
nothing, per t1211/t935):

```bash
source .aitask-scripts/lib/python_resolve.sh
PY="$(require_ait_python)"
export PYTHONPATH="$PWD/.aitask-scripts/board:$PWD/.aitask-scripts/lib"
export PYTHONDONTWRITEBYTECODE=1
```

1. **Guard passes on current tree (AC-3):**
   `"$PY" -m unittest tests.test_no_zero_collection -v` → all cases OK,
   including `GuardFalsifiabilityTests` (the negative control).
2. **Direct run works (env self-sufficiency):**
   `"$PY" tests/test_no_zero_collection.py` → OK.
3. **Aggregate suite still green & includes the guard:**
   `bash tests/run_all_python_tests.sh` → exit 0; the run collects the new
   `NoZeroCollectionTests` / `GuardFalsifiabilityTests` cases.
4. **AC-1 negative control (manual, revert after):** temporarily neuter a real
   file into zero collection — e.g. rename the `TestCase` class in a small file
   or comment its body — and confirm
   `"$PY" -m unittest tests.test_no_zero_collection` **fails**, naming that
   file. Revert.
5. **AC-2 negative control (manual, revert after):** temporarily add
   `import nonexistent_zzz` at the top of a real test file and confirm the
   guard fails via `test_no_module_fails_to_import`, naming that stem. Revert.
   (Steps 4-5 are also covered *automatically & committed* by
   `GuardFalsifiabilityTests`, which is the AC-5 deliverable; the manual runs
   are a belt-and-braces cross-check against the live tree.)

## Risk

### Code-health risk: low

- Single new self-contained test file, no production code touched; blast radius
  is one file. The only subtlety is subprocess env parity with
  `run_all_python_tests.sh`, which is copied verbatim from that script ·
  severity: low · → mitigation: none (accepted)
- The real-tree probe runs a per-file `unittest discover` sweep (~0.5 s, 142
  files, one subprocess) once per `setUpClass`, adding a small fixed cost to the
  aggregate suite · severity: low · → mitigation: none (accepted — bounded, one
  subprocess, cached across the case's two tests)

### Goal-achievement risk: low

- Per-file discovery counts every `TestCase` reachable from a file, so a
  wrapper file that imports a shared base is credited (correctly) rather than
  looking empty — the class-origin misattribution failure mode of a single
  flattened discovery is avoided by design. Residual: a file is double-counted
  across the base and every importer, but the guard only asserts ≥1 per file, so
  double-counting is harmless · severity: low · → mitigation: none (accepted;
  `GuardFalsifiabilityTests` pins the oracle against both a zero-collection and
  a broken-import fixture)
- The guard validates the unittest-discovery branch, not pytest collection; if
  the project later standardizes on pytest-only the guard would still be
  correct for what it claims but would not mirror the harness's active branch ·
  severity: low · → mitigation: none (accepted — documented in the module
  docstring per AC-4; branch divergence is out of scope for t1229)

### Planned mitigations
None — the risks are all `low` and self-contained; this task is itself the
mitigation for t1211's recorded risk.

Step 9 (Post-Implementation) handles merge approval, the `risk_evaluated` gate
orchestration, and archival.

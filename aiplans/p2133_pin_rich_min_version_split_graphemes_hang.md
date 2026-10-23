---
Task: t2133_pin_rich_min_version_split_graphemes_hang.md
Base branch: main
Output branch: main
---

# t2133 — Pin rich >= 14.3.3 (split_graphemes hang on leading zero-width char)

## Context

rich 14.3.2's `rich.cells.split_graphemes` loops forever when a zero-width char
(U+200E LRM, U+FE0F, raw ESC...) precedes any visible char. Every Textual surface
that truncates such text freezes at 100% CPU (observed: minimonitor `p` pick
dialog on an RTL task body). `aitask_setup.sh` pins only `textual>=8.2.7,<9`,
whose floor is `rich>=14.2.0`, so old venvs keep 14.3.2 forever.

Measured on this machine during planning:
- `~/.aitask/venv` = rich 14.3.2 / textual 8.2.7; `~/.aitask/pypy_venv` = rich 15.0.0.
- `split_graphemes("‎")`, `set_cell_size("‎____ are you going?", N)`,
  `Content(...).truncate(4)` → hang (timeout rc=124) on 14.3.2; return on 15.0.0.
- Headless `App.run_test(size=(40,30))` with `VerticalScroll(Markdown(table))` where
  a cell is `"‎" + "_"*25 + " are you going?"` next to long unbreakable cells →
  hangs on 14.3.2, renders in 0.23 s on 15.0.0. (A 4-underscore cell does NOT hang —
  the cell must need truncation.)
- Raw-ESC line (`t940` case) via `set_cell_size` also hangs on 14.3.2 and is fine on
  15.0.0 — the t940 hang is the same upstream bug.

Upgrade semantics (decided with the user): `ait setup` repairs automatically
(`pip install 'rich>=14.3.3'` with 14.3.2 installed upgrades without `--upgrade`;
`verify_venv_specs` then confirms / retries). `ait upgrade` (install.sh) never
touches venvs by design → add a **read-only hint** naming the failing dependency
and telling the user to run `ait setup`. `ait upgrade` alone does not repair.

## Implementation

1. **`.aitask-scripts/aitask_setup.sh` — pin.** Append `'rich>=14.3.3'` to
   `AIT_PIP_SPECS_COMMON` (both venvs install COMMON). Extend the comment block
   above it: rich is a version *floor* on textual's transitive dep (14.3.2's
   split_graphemes hang, t2133); it gets no `*_IMPORTS` entry because importing
   textual already imports rich — `verify_venv_specs` is what enforces it.
   `textual` pin unchanged. `AIT_PYPY_RUNTIME_IMPORTS` in `lib/python_resolve.sh`
   unchanged (import-name list, rich covered via textual).

2. **`verify_venv_specs` — report whether the inspection ran.** Today it does
   `out="$(…)" || out=""`, so a failed interpreter (confirmed: `/bin/false` →
   empty `bad_specs`) or an unimportable `packaging` reads as "all in range".
   Add a second global, `specs_check_ok` (`true`/`false`): set `false` when the
   inspection command exits non-zero, `true` otherwise. `bad_specs` semantics and
   the `return 0` contract are unchanged, so the existing setup call sites are
   untouched (they already pair it with `verify_venv_imports`, which catches a
   broken interpreter; whether setup should also gate on `specs_check_ok` is
   recorded as an upstream note, not changed here).

3. **`.aitask-scripts/aitask_setup.sh` — new `report_venv_dep_drift()`** (placed
   next to `report_home_legacy`, same shape: read-only, always `return 0`):
   - If `$VENV_DIR/bin/python` is executable: `verify_venv_specs` with
     COMMON + CPYTHON_EXTRA; if `PYPY_VENV_DIR/bin/python` is executable:
     `verify_venv_specs` with COMMON. Absent venv → silent.
   - `specs_check_ok=false` → nonfatal `warn "Could not check Python dependency
     versions in <dir> (interpreter or version check failed)."` + the same
     `ait setup` hint line. An unsuccessful inspection is never reported as clean.
   - `bad_specs` non-empty → `warn "Python venv <dir> has dependencies outside the
     required range: <bad_specs joined by '; '>"` then
     `info "    'ait upgrade' does not update Python dependencies — run 'ait setup' to repair them."`
   - Nothing installed, nothing removed.

4. **`install.sh` — call site.** Right after the `report_home_legacy` block, add
   (with the same `declare -F` guard, since `--version` can pair this installer with
   an older `aitask_setup.sh`):
   ```bash
   # Upgrade never repairs Python deps (setup owns pip); surface venv spec drift
   # read-only so an upgraded-only machine learns it needs `ait setup` (t2133).
   if declare -F report_venv_dep_drift >/dev/null; then
       report_venv_dep_drift
   fi
   ```

5. **`.aitask-scripts/codebrowser/code_viewer.py` — record the t940 decision.**
   Keep `_sanitize_control_chars` (it renders literal control bytes as visible
   glyphs, which is display behaviour independent of the hang, and stays
   defense-in-depth for a venv not yet re-setup). Amend the comment above
   `_CONTROL_CHAR_TRANSLATION` to say the hang root cause is rich < 14.3.3
   (fixed by the setup pin, t2133) and the translation is retained for visible
   rendering. No behaviour change.

6. **Tests.**
   - **New `tests/test_rich_zero_width_hang.py`** (unittest, runs in the Python
     suite). Each case runs a child `subprocess.run([sys.executable, "-I", "-c", SCRIPT],
     timeout=…)` so a regression is killed and **fails** instead of hanging the
     suite (no sleeps); the failure message names the installed rich version and
     says to run `ait setup`.
     - `split_graphemes("‎")` and `split_graphemes("️")` return (timeout 20 s).
     - `set_cell_size("‎____ are you going?", 4)` returns (same subprocess).
     - Headless Textual: `App.run_test(size=(40, 30))` composing
       `VerticalScroll(Markdown(body))` (the `TaskDetailDialog` body structure)
       where `body` is the 5-column table with a long-unbreakable-word row and a
       row whose two cells are `"‎" + "_"*25 + " are you going?"`; child
       prints `done`; assert rc 0 and `done` in stdout (timeout 60 s).
     `sys.executable` is the suite interpreter (the resolved framework venv), so
     the test checks the venv the TUIs actually run on.
   - **`tests/test_setup_verify_venv_imports.sh`** (extend, existing stub pattern):
     - `AIT_PIP_SPECS_COMMON` contains `rich>=14.3.3`.
     - Real-packaging check of the shipped spec string: using the resolved
       framework python with `pip._vendor.packaging`, the rich spec from the array
       rejects `14.3.2` and accepts `14.3.3` and `15.0.0`.
     - `verify_venv_specs` sets `specs_check_ok=true` for a clean stub and for a
       drift stub, and `specs_check_ok=false` (with empty `bad_specs`) for a stub
       whose `-` branch exits 1 and for `/bin/false` as the interpreter.
     - `report_venv_dep_drift` with `VENV_DIR` / `PYPY_VENV_DIR` pointed at scratch
       dirs whose `bin/python` is a `make_py_stub`: drift stub (`rich 14.3.2 (need >=14.3.3)`)
       → output contains `rich 14.3.2` and `ait setup`; failed-check stub → output
       contains `Could not check` and `ait setup`; clean stub → empty output;
       no venv dirs → empty output; function returns 0 under `set -e` in every case.

## Verification

- Red proof (before remediating this machine): run
  `~/.aitask/venv/bin/python -m unittest tests.test_rich_zero_width_hang -v` →
  fails by timeout (not hang) on rich 14.3.2. Run the same file with the PyPy venv
  interpreter (rich 15.0.0) → passes.
- **Floor evidence at exactly rich 14.3.3:** scratch venv (scratchpad) with
  `textual==8.2.7 rich==14.3.3`; run `tests/test_rich_zero_width_hang.py` with its
  interpreter → all cases pass. Confirm `rich.__version__`/metadata is exactly
  14.3.3 in that run. (If 14.3.3 fails, raise the floor to the lowest version that
  passes and re-run.)
- **Setup upgrades an existing 14.3.2 venv (end-to-end, scratch HOME):** create
  `$S/.aitask/venv` with `textual==8.2.7 rich==14.3.2`, then
  `HOME=$S AITASKS_HOME= bash -c 'source .aitask-scripts/aitask_setup.sh --source-only; setup_python_venv'`;
  assert the scratch venv now reports rich ≥ 14.3.3. Never touches the real `~/.aitask`.
- Hint: `source aitask_setup.sh --source-only; report_venv_dep_drift` against the
  real home before remediation → prints the rich 14.3.2 warning + `ait setup`.
  Also `VENV_DIR=<dir with bin/python -> /bin/false>` → prints the
  `Could not check` diagnostic, exit 0.
- Operator remediation on this machine (documented in the task):
  `~/.aitask/venv/bin/python -m pip install 'rich>=14.3.3'`; re-run the hint (silent)
  and the new Python test (passes).
- `bash tests/test_setup_verify_venv_imports.sh`, `bash tests/test_setup_pip_install_guards.sh`,
  `python -m unittest tests.test_code_viewer_control_chars`,
  `shellcheck .aitask-scripts/aitask_setup.sh install.sh`,
  `bash tests/run_all_python_tests.sh` (check last-line verdict / PIPESTATUS).

## Step 9 (Post-Implementation)

Current-branch workflow: commit code (`bug: … (t2133)`) and plan separately after
review, then archive via `aitask_archive.sh 2133`.

## Risk

### Code-health risk: low
- None identified. Change is a one-entry spec addition, an additive status global
  on `verify_venv_specs` (existing callers and `bad_specs` unchanged), one read-only
  reporting function mirroring `report_home_legacy`, a guarded install.sh call, a
  comment edit and tests.

### Goal-achievement risk: low
- None identified. Behaviour is reproduced red/green on 14.3.2 / 15.0.0 and the
  advertised 14.3.3 floor gets its own behavioural run; the remaining exposure (a venv nobody re-runs `ait setup` on) is an
  accepted design limit the user chose, surfaced by the new upgrade hint.

## Final Implementation Notes
- **Actual work done:** `rich>=14.3.3` added to `AIT_PIP_SPECS_COMMON` (both venvs). `verify_venv_specs` now also sets `specs_check_ok` (false when the inspection command itself fails), so a failed check is no longer indistinguishable from a clean one. New read-only `report_venv_dep_drift()` (next to `report_home_legacy`) checks the CPython venv (COMMON+CPYTHON_EXTRA) and PyPy venv (COMMON), naming bad specs or reporting "Could not check …", always followed by "'ait upgrade' does not update Python dependencies — run 'ait setup' to repair them."; installs nothing. `install.sh` calls it under a `declare -F` guard after `report_home_legacy`. `code_viewer.py` comment records the t940 decision. Tests: new `tests/test_rich_zero_width_hang.py` (subprocess + timeout: cells-level calls and 40-col Markdown table with U+200E cells); `tests/test_setup_verify_venv_imports.sh` +15 assertions (pin present, real-packaging spec verdict 14.3.2=False/14.3.3=True/15.0.0=True, specs_check_ok for clean/drift/failed-stub//bin/false, drift hint for drift/failed/PyPy/clean/absent).
- **Deviations from plan:** `rich` WAS added to `AIT_PYPY_RUNTIME_IMPORTS` (lib/python_resolve.sh) — the plan said no import entry, but `tests/test_setup_pip_install_guards.sh` section B enforces a spec↔import pairing for COMMON. Harmless at runtime (textual imports rich); `tests/test_python_resolve_pypy.sh` fake-package list updated to match. Markdown test timeout 30 s (plan said 60 s) — green runs in <1 s.
- **Issues encountered:** A cell needs truncation to reach `split_graphemes` — a 4-underscore LRM cell does NOT hang on 14.3.2; the test uses 25 underscores beside long unbreakable cells. The real `~/.aitask/venv` held rich 14.3.2 and was remediated with `pip install 'rich>=14.3.3'` (now 15.0.0); running TUIs keep the old rich until restarted.
- **Key decisions:** `ait upgrade` stays read-only for venvs (user decision): it only hints; `ait setup` repairs. t940 sanitizer kept (visible control-byte rendering + defense-in-depth for venvs not yet re-set-up), though raw ESC no longer hangs on rich ≥14.3.3.
- **Evidence:** red — both new tests fail by timeout on rich 14.3.2 (`~/.aitask/venv` before remediation); green on 15.0.0 (PyPy venv) and on exactly 14.3.3 (scratch venv, textual 8.2.7). End-to-end: scratch HOME venv with rich 14.3.2 → `setup_python_venv` → rich 15.0.0, drift hint silent afterwards; real `~/.aitask` untouched. Full Python suite PASSED (runner=pytest, exit=0); setup/resolver bash tests 53/53, 14/14, 26/26, test_setup_python_install exit 0.
- **Upstream defects identified:** .aitask-scripts/aitask_setup.sh:setup_python_venv / setup_pypy_venv — the "need repair" checks gate only on `missing_imports`/`bad_specs` and ignore the new `specs_check_ok`, so if the version inspection itself fails while imports succeed (e.g. no importable packaging) setup treats spec ranges as satisfied

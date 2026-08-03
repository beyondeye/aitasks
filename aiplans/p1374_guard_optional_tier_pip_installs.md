---
Task: t1374_guard_optional_tier_pip_installs.md
Worktree: (none — current-branch mode)
Branch: (none — current-branch mode)
Base branch: main
Output branch: main
---

# t1374 — Guard every `pip install` in `aitask_setup.sh` under `set -e`

## Context

`.aitask-scripts/aitask_setup.sh` runs under `set -euo pipefail` (line 2). Its
dependency installers are each written as **run `pip install` → validate imports
and version specs → warn / degrade / `return 0`**. Two of them state the contract
outright: *"Never fails the overall setup"* (`setup_chat_deps`, line 712-714) and
a documented warn-and-remove degrade for PyPy (`setup_pypy_venv`, line 677-681).

That contract is false whenever pip itself exits non-zero — an offline machine,
an unreachable index, a wheel that will not build. `set -e` aborts the whole
script at the bare `pip install` line, so the validate / warn / `return 0` path
below it is never reached. `t1354_3` fixed this for its own new
`setup_dev_deps()` and confirmed it empirically (stub `pip` exiting 1, driven
through the real function body: unguarded → `exit 1`, continuation never
printed; guarded → warns, returns 0, setup continues). The pre-existing call
sites were left untouched as out of scope — this task closes them.

**Audit finding that widens the scope (user-confirmed).** `setup_python_venv()`
has the same shape at lines 852 / 860 / 875, and it runs **unconditionally on
every `ait setup`** (line 3684) — *before* either optional tier. So the same
defect class sits on the path every user takes, not only on opt-in tiers.

> **Correction, measured during implementation.** The scope widening was
> originally justified with "line 852 is `pip install --quiet --upgrade pip`,
> which always contacts the index, so an offline `ait setup` on a healthy machine
> already dies there". **That is wrong** — measured against real pip (25.x,
> CPython 3.14) with an unreachable index:
>
> | command | rc |
> |---|---|
> | `pip install --quiet --upgrade pip` | **0** (requirement already satisfied) |
> | `pip install --quiet <already-satisfied specs>` | **0** (short-circuits, no index round-trip) |
> | `pip install --quiet <not-installed spec>` | **1** |
>
> So an offline `ait setup` on a fully-healthy machine does **not** abort today,
> at any of the eight sites. The real trigger is narrower and is the same for the
> core venv and the tiers: **offline (or a broken index / proxy / TLS path) AND a
> dependency that is not already satisfied** — e.g. right after a version bump in
> `AIT_PIP_SPECS_*`, or a first-time `--with-chat` / `--with-dev` opt-in. The fix
> and the eight-site scope are unchanged and still correct; only this premise
> was overstated.

**Intended outcome:** when pip genuinely fails, `ait setup` degrades — the
optional tiers warn (or, for PyPy, remove themselves so the board falls back),
and the core venv dies with its *informative* message — instead of aborting
mid-run at a bare `pip install` line with only pip's own error.

## Approach

Introduce one shared guard helper and route all eight fallible `pip install`
calls through it. Each function keeps its **own** existing degrade policy: the
helper only stops `set -e` from firing, it never decides what failure means.

The pre-existing post-install validators (`verify_venv_imports` /
`verify_venv_specs`) are the real arbiters of whether a venv is usable, and they
already exist at every site. Letting them run is what makes the offline-but-
healthy case succeed instead of warning falsely.

### 1. New helper in `.aitask-scripts/aitask_setup.sh`

Add next to the other venv helpers (near `verify_venv_specs`, ~line 75-105):

```bash
# pip_install_guarded <label> <pip-binary> <pip-arg>...
# Run a `pip install` that must never abort `ait setup`.
#
# ALWAYS returns 0 — deliberately. The script runs under `set -euo pipefail`, so
# a bare `pip install` that fails (offline machine, unreachable index, a wheel
# that will not build) aborts the WHOLE run at that line, never reaching the
# validate / warn / degrade path its caller wrote below it. Keeping the call
# inside an `if !` condition is what makes that contract true rather than merely
# stated; returning non-zero here would just move the abort to the call site.
#
# The helper does NOT decide what a failure means — each caller keeps its own
# policy, decided by the verify_venv_* check that follows: an optional tier warns
# (or removes itself), the core CPython venv still dies. This matters because a
# failed pip does not imply a broken venv: on an offline machine whose deps are
# already installed and in range, verification passes and setup continues.
pip_install_guarded() {
    local label="$1" pip_bin="$2"
    shift 2
    if ! "$pip_bin" install "$@"; then
        warn "$label: pip install failed (network or index unavailable?). Continuing — the dependency check below decides whether this is fatal."
    fi
    return 0
}
```

### 2. Convert the eight call sites

Mechanical, one line each; **no surrounding control flow changes.**

| Function | Lines | Label |
|---|---|---|
| `setup_pypy_venv` | 663, 664, 673 | `PyPy venv pip self-upgrade` / `PyPy venv deps` / `PyPy venv dep repair` |
| `setup_chat_deps` | 722, 730 | `Chat deps` / `Chat deps repair` |
| `setup_python_venv` | 852, 860, 875 | `CPython venv pip self-upgrade` / `CPython venv deps` / `CPython venv dep repair` |

e.g. line 664 becomes:

```bash
pip_install_guarded "PyPy venv deps" "$PYPY_VENV_DIR/bin/pip" \
    --quiet "${AIT_PIP_SPECS_COMMON[@]}"
```

Resulting per-function behaviour (all existing blocks untouched):

- **`setup_pypy_venv`** — pip fails, deps still good → PyPy kept, setup continues.
  Deps genuinely bad → existing 677-681 block warns and removes the venv so the
  board falls back to CPython. This is exactly the "documented warn-and-remove
  path" the task says is currently unreachable. See §2b for how that removal is
  made robust.

### 2b. The PyPy removal must actually disable selection

`resolve_pypy_python` (`.aitask-scripts/lib/python_resolve.sh:70-95`) selects
`$PYPY_VENV_DIR/bin/python` on exactly two conditions: it is executable, and it
answers `sys.implementation.name == 'pypy'`. **It never checks that the deps
import.** So removal is not merely cleanup — it is the *only* mechanism that
produces the CPython fallback. A broken-but-present PyPy venv keeps being
selected, and the board fails at `import textual`.

Therefore line 679's `rm -rf` must **not** be softened to `|| warn` + `return 0`:
that would report a fallback that did not happen. Escalate instead:

```bash
if ! rm -rf "$PYPY_VENV_DIR" 2>/dev/null; then
    # Full removal failed (permissions / busy). Selection keys only on the
    # interpreter, so dropping that is enough to disable the fast path.
    rm -f "$PYPY_VENV_DIR/bin/python" "$PYPY_VENV_DIR/bin/python3" 2>/dev/null || true
    if [[ -x "$PYPY_VENV_DIR/bin/python" ]]; then
        die "PyPy venv at $PYPY_VENV_DIR has unusable dependencies and could not be removed (check permissions). It would still be selected ahead of the CPython venv and fail at import. Remove it manually and re-run 'ait setup'."
    fi
    warn "PyPy venv at $PYPY_VENV_DIR could not be fully removed, but its interpreter was — the board will use the CPython venv. Delete the leftover directory at your convenience."
fi
return 0
```

The `die` is deliberate and is the one place this task chooses fail-hard over
degrade: continuing would leave the user with a silently broken board, which is
worse than a setup that stops and says exactly what to delete. Today this case
also aborts (bare `rm -rf` under `set -e`) — but with no message at all.
- **`setup_chat_deps`** — pip fails, deps good → `success "Chat SDK deps ready"`
  (no false alarm). Deps bad → existing 734-737 warn + `return 0`.
- **`setup_python_venv`** — pip fails, deps good → setup proceeds normally. Deps
  bad → retry, then the existing `die "CPython venv still bad (…). Check
  pip/network and re-run 'ait setup'."` **Still fails hard, but now with that
  message instead of a bare pip traceback.**

### 3. Deliberate divergence from `setup_dev_deps` — record it

`setup_dev_deps` (757-807) already guards its own pip calls, but with
`if ! …; then warn; return 0; fi` — an **early return** that also skips the
opt-in marker write, which t1354_3 chose on purpose ("a failed attempt cannot
masquerade as opt-in"). It is left as-is. Add a one-line comment there pointing
at `pip_install_guarded` and saying *why* this function does not use it, so the
two shapes are not later "harmonized" in the wrong direction.

The task's suggested fix reads `if ! cmd; then warn "…"; return 0; fi` verbatim
for all sites. **Deviation, stated explicitly:** early-return is wrong for the
other three functions — it would skip the verification that is the only thing
able to tell "network down" from "venv broken", warning a user that their chat
tier is broken when it is fine, and (for PyPy) skipping the remove-and-fall-back
that is the whole point of the degrade path.

## Verification

One definitive sequence, in order. Steps A-C are the committed test; D-E are
run-once manual gates.

### A. Test harness — `tests/test_setup_pip_install_guards.sh`

Follows `tests/test_setup_verify_venv_imports.sh` (same `assert_*` helpers,
`--source-only` hook at line 3751, `make_py_stub` python stub extended to answer
the version probes `setup_python_venv` makes). No network, deterministic.

Two harness properties are load-bearing:

**A1 — every case runs in a child `bash`.** A broken guard *terminates the shell
it runs in*, so a test that sources the script into its own process cannot
observe the failure it is asserting about — it dies first. All cases therefore go
through one driver:

```bash
# tests/.../driver.sh <setup-script-path> <case-name>
set -euo pipefail
export HOME="$AIT_TEST_SCRATCH_HOME"       # so VENV_DIR/PYPY_VENV_DIR land in scratch
export PATH="$AIT_TEST_STUB_BIN:$PATH"
source "$1" --source-only                  # target is a PARAMETER, not hardcoded
case "$2" in ... esac
echo "__REACHED_END__"                     # continuation marker
```

`run_case <script> <case>` captures **stdout, stderr and exit status separately**
and the caller asserts on all three. Streams matter and are pinned here because
the script splits them: `warn` / `info` / `success` write to **stdout**; only
`die` writes to **stderr**.

**A2 — the script under test is a parameter.** The same driver runs the real
script and the mutated one (§C), so the negative control provably exercises the
identical code path rather than a look-alike.

| # | Case | Assertion (rc · stdout · stderr) |
|---|---|---|
| 1 | `pip_install_guarded`, failing pip, called **bare** under `set -e` | rc 0 · `__REACHED_END__` present + warning on stdout |
| 2 | `setup_chat_deps`, pip fails, deps **good** | rc 0 · `Chat SDK deps ready`, no "could not be installed" |
| 3 | `setup_chat_deps`, pip fails, deps **bad** | rc 0 · warns "could not be installed" |
| 4 | `setup_pypy_venv`, pip fails, deps **good** | rc 0 · `$PYPY_VENV_DIR` still exists |
| 5 | `setup_pypy_venv`, pip fails, deps **bad** | rc 0 · `$PYPY_VENV_DIR` removed |
| 5b | as 5, but `$PYPY_VENV_DIR`'s parent is read-only → `rm -rf` fails, `bin/` writable | rc 0 · `bin/python` gone (selection disabled) · warns "could not be fully removed" |
| 5c | as 5, but `$PYPY_VENV_DIR/bin` read-only → interpreter survives | rc **non-zero** · stderr carries "could not be removed … Remove it manually" |
| 6 | `setup_python_venv`, pip fails, deps **good** | rc 0 · `__REACHED_END__` — offline-but-healthy no longer aborts |
| 7 | `setup_python_venv`, pip fails, deps **bad** | rc non-zero · stderr carries `CPython venv still bad …`, not a bare pip error |

Cases 5b/5c `chmod` a scratch dir; both restore in a `trap` and are **skipped
when `$EUID` is 0** (root ignores the write bit, so the fixture would not
reproduce the condition and the case would pass vacuously).

### B. Structural tripwire

No `^\s*"\$(VENV_DIR|PYPY_VENV_DIR)/bin/pip" install` line remains in
`aitask_setup.sh` — catches a future ninth site added bare, which the behavioural
cases would not drive. Supplementary to A, not a substitute.

### C. Negative control — proves A and B discriminate

The guard collapses to a **single mutable line** (`if ! "$pip_bin" install "$@";
then` inside `pip_install_guarded`), so the control mutates the *real source*:

1. Build the mutated copy in scratch **with its sibling `lib/` reachable** —
   `aitask_setup.sh` derives `SCRIPT_DIR` from `BASH_SOURCE[0]` and sources
   `$SCRIPT_DIR/lib/python_resolve.sh` (which in turn sources
   `terminal_compat.sh` from its own dirname). A bare copy in `/tmp` fails at the
   `source` line, and the control would then "fail" for a reason unrelated to the
   guard:
   ```bash
   mkdir -p "$SCRATCH/mut"
   ln -s "$PROJECT_DIR/.aitask-scripts/lib" "$SCRATCH/mut/lib"
   sed 's|if ! "$pip_bin" install "$@"; then|"$pip_bin" install "$@"; if false; then|' \
       "$SETUP" > "$SCRATCH/mut/aitask_setup.sh"
   ```
   pip now runs bare under `set -e`; the `warn`/`fi` block stays syntactically
   valid but unreachable — the exact pre-fix defect.
2. **Assert the substitution matched** (compare against the original, or count
   the replacement) — a silently no-op `sed` is the classic vacuous control.
3. `bash -n "$SCRATCH/mut/aitask_setup.sh"` — a mutation that merely fails to
   parse would make the control pass for the wrong reason.
4. **Sanity-source it once** (`source … --source-only`, expect rc 0) before using
   it, proving the copy is loadable and that later failures come from the guard.
5. Re-run cases 1-6 against the mutated copy via the *same* `run_case` driver and
   assert they **fail** — non-zero rc and `__REACHED_END__` absent. Case 7's
   discriminator is its stderr message, not its status (it exits non-zero either
   way), so it is asserted on content. Case 5c is not part of the control (it is
   not a guard regression). A **passing** negative control means the test is not
   testing what it claims.
6. Re-run B against the mutated copy and assert it **trips**.

### D. Mandated install-flow run (once, manual)

`aidocs/framework/aitasks_extension_points.md:132-141` requires any setup-flow
change be exercised through a real install, because `install.sh` deletes `seed/`
at the end:

```bash
bash install.sh --local-tarball <tarball-of-working-tree> --dir /tmp/.../scratch1374
```

then run `ait setup` in that dir; expect exit 0 and normal output. (These
functions read no seed file — `AIT_PIP_SPECS_*` in `aitask_setup.sh` is the sole
source — so seed deletion is a non-issue *for them*; the run demonstrates rather
than assumes that.)

### D2. Real-pip confirmation (added during implementation)

The stub proves the control flow; this proves the *premise*. With the **real**
pip, the real venv and an unreachable index (`PIP_INDEX_URL=http://127.0.0.1:9/simple`),
drive the real `setup_chat_deps` with a spec that is not already satisfied —
the actual offline trigger identified in the Context correction:

```bash
PIP_INDEX_URL=http://127.0.0.1:9/simple PIP_RETRIES=0 PIP_TIMEOUT=2 \
bash -c 'set -euo pipefail; source "$1" --source-only
         AIT_PIP_SPECS_CHAT=("nonexistent-ait-probe-pkg==1.0")
         AIT_IMPORTS_CHAT=(nonexistent_ait_probe_pkg)
         setup_chat_deps; echo __REACHED_END__' _ <script>
```

Guarded source → warns, `__REACHED_END__`, rc 0. The same command against a
mechanically un-guarded copy → rc 1, no warning, no marker. (Installs nothing:
the probe package does not exist, so the live venv is unchanged — verified.)

### E. Lint

```bash
shellcheck .aitask-scripts/aitask_setup.sh
bash tests/test_setup_verify_venv_imports.sh   # neighbouring sourcing test unaffected
```

## Files

- `.aitask-scripts/aitask_setup.sh` — new helper; 8 call sites; the escalating
  PyPy removal (§2b); 1 explanatory comment in `setup_dev_deps`.
- `.aitask-scripts/lib/python_resolve.sh` — `resolve_pypy_python()` now requires
  dependency visibility, not just PyPy identity (see Post-Review Changes §1).
- `tests/test_setup_pip_install_guards.sh` — new.
- `tests/test_python_resolve_pypy.sh` — stubs made sentinel-aware; Test 10 added.

## Post-Review Changes

### Change Request 1 (2026-08-03 12:5x) — removal alone did not produce the fallback

- **Requested by user:** blocking review finding, verified CONFIRMED.

  §2b claimed that removing `$PYPY_VENV_DIR` forces the board onto CPython.
  `resolve_pypy_python`'s candidate list continues past the venv to
  `pypy$AIT_PYPY_PREFERRED` and `pypy3` **on PATH** — which is very often the
  exact system interpreter `find_pypy()` built the venv from. Once the venv is
  removed for unusable dependencies, resolution simply moved on to that
  dep-bare system PyPy and the board still died at `import textual`. The new
  PyPy cases asserted only directory removal, never the resolution outcome, so
  they would have passed while the promised fallback did not happen.

- **Verified independently, and it is broader than the degrade path.** `pypy3`
  is a candidate unconditionally, so **any** machine with a system PyPy on PATH
  got `ait board` launched on a dep-bare interpreter — even one that never ran
  `ait setup --with-pypy`. That pre-existing defect is fixed by the same change.

- **Changes made:**

  1. `resolve_pypy_python()` now requires **both** PyPy identity **and**
     dependency visibility. `textual` is the sentinel (every TUI is a Textual
     app); `importlib.util.find_spec()` locates it without importing it and
     folds into the single probe subprocess the loop already spawns. Fail-closed:
     any error rejects the candidate. `find_pypy()` in `aitask_setup.sh` keeps an
     identity-only probe on purpose — it looks for a bare interpreter to *create*
     the venv from — and a comment records the asymmetry.
     Measured cost: probe 17ms → 36ms, once per launch and memoized in
     `_AIT_RESOLVED_PYPY`. The board settles in ~3s against a 45s budget
     (`tests/test_board_header_row_live.py`), so +19ms is ~0.6% of a boot.
     Real resolution on a healthy box is unchanged (still the PyPy venv).
  2. The §2b comment and the user-facing warning were corrected — removal is
     *half* the fallback, not all of it.
  3. **New case 5d** in the guards test drives `setup_pypy_venv` to its degrade
     **with a dep-bare PyPy planted on PATH**, then asserts the end state:
     `resolve_pypy_python` returns empty and `require_ait_python_fast` returns
     the CPython venv. A **positive control** (same stub, deps visible → still
     selected) proves 5d measures the dependency rather than stub usability.
  4. `tests/test_python_resolve_pypy.sh`: stubs gained a `has_deps` flag and run
     the probe under `-S` so dependency visibility is set by the test and never
     by the host's `python3` (on a dev box that is often the framework venv,
     which *does* have textual — a dep-bare stub would have passed silently).
     Their fake `sys.implementation` now copies the real namespace, because the
     import machinery reads `cache_tag` and constructs the type. Test 10 added.

- **Two test defects found and fixed while doing this** (both would have made a
  green run meaningless):
  - `make_mutant` was called inside `$( )`, so its anti-vacuity / parse /
    sourceability self-checks ran in a **subshell**: their PASS/FAIL updates were
    discarded and a failure message would have been spliced into the returned
    path. Proven by probe: with a deliberately non-matching `sed`, the suite
    still reported 40/40 green. It now returns via a global; the same probe now
    correctly reports `mutation 'helper' changed nothing`, and the real count rose
    40 → 46 as the lost self-checks started being counted.
  - `run_case` inherited the developer's `PATH`, so the host's real
    `/home/ddt/.local/bin/pypy3.11` — probed *before* `pypy3` — became the
    resolved candidate instead of the planted stub. Cases now run with
    `PATH=$home/stubbin:/usr/bin:/bin`.

- **Files affected:** `.aitask-scripts/lib/python_resolve.sh`,
  `.aitask-scripts/aitask_setup.sh` (comment + message),
  `tests/test_setup_pip_install_guards.sh`, `tests/test_python_resolve_pypy.sh`,
  this plan.

### Change Request 2 (2026-08-03 13:1x) — locating one module is not proving the runtime

- **Requested by user:** blocking review finding, verified CONFIRMED on both counts.

  CR1's probe accepted a candidate when `find_spec('textual')` was non-null.
  That proves only that a package *directory* is discoverable, and only for one
  module. Two ways it still hands the board a doomed interpreter:

  1. **One module is not the runtime.** `aitask_board.py:6` imports `yaml`
     directly as well as Textual. A PyPy with textual but without
     pyyaml / linkify-it-py / tomli passed the probe and crashed on launch.
  2. **Discoverable is not importable.** Measured: with a `textual/__init__.py`
     containing `raise ImportError`, `find_spec` still reports present while the
     import fails — the shape of a broken install, or of a missing *transitive*
     dependency of Textual itself.

- **Changes made:**

  1. The probe now **imports** the whole required set. The identity check runs
     first so a non-PyPy candidate costs nothing; only a genuine PyPy pays the
     imports. Measured on this box: 16ms identity / 32ms find_spec / **186ms
     full import**, once per launch and memoized in `_AIT_RESOLVED_PYPY`. It is
     the same import work the board performs ~171ms of immediately afterwards,
     against a ~3s boot and a 45s budget.
  2. **Single source of truth for the set.** `AIT_PYPY_RUNTIME_IMPORTS=(textual
     yaml linkify_it tomli)` now lives in `lib/python_resolve.sh` — the resolver
     needs it and setup sources that file, never the reverse — and
     `aitask_setup.sh` *derives* `AIT_IMPORTS_COMMON` from it rather than
     keeping a second copy.
  3. **Found while running it for real: the probe leaked stdout.** Under PyPy,
     `import yaml` prints Cython diagnostic lines. `resolve_pypy_python` echoes
     the interpreter path on stdout, so the first live run returned
     `"(_common_types_metatype, 9088, 128, 128)\n…/bin/python"` — every board
     launch would have exec'd garbage. The probe now discards **both** streams.
     This could not surface with the CR1 probe, which imported only
     `importlib.util`.

- **Tests:** `test_python_resolve_pypy.sh` stubs take a deps *profile*
  (`full` / `none` / `partial` / `broken`) backed by real fake packages, so the
  probe's behaviour is exercised by a real interpreter:
  - **Test 11** — textual present, `yaml` absent → rejected.
  - **Test 12** — all four discoverable, textual's `__init__` raises → rejected.
  - Positive control — the same stub with the full working set → selected.
  - The `full` and `broken` fixtures deliberately make `yaml` **print on
    import**, reproducing the PyPy behaviour above, so the healthy-interpreter
    assertions double as the guard for the stdout redirection.
  - Guards test section B gained a **drift guard**: `AIT_PIP_SPECS_COMMON` and
    `AIT_PYPY_RUNTIME_IMPORTS` must stay the same length (derivation cannot
    catch a spec added without its import name), plus an assertion that
    `AIT_IMPORTS_COMMON` really is derived and not a second copy.

- **Negative controls, each flipping only what it should:**
  - Probe reverted to `find_spec('textual')` → Tests 11 and 12 fail, Test 10 and
    the control pass.
  - Probe's `>/dev/null` removed → 4 tests fail, showing the corrupted path.
  - A spec added to `AIT_PIP_SPECS_COMMON` without its import → drift guard fails
    (`expected '5', got '4'`).

- **Files affected:** `.aitask-scripts/lib/python_resolve.sh`,
  `.aitask-scripts/aitask_setup.sh` (derived list),
  `tests/test_python_resolve_pypy.sh`, `tests/test_setup_pip_install_guards.sh`,
  this plan.

## Risk

### Code-health risk: medium
- The change lands in `setup_python_venv`, the **core install path every `ait
  setup` runs**, and converts a hard abort into continue-then-verify. The
  existing `verify_venv_imports` / `verify_venv_specs` → `die` block is untouched
  and remains the arbiter, but any gap in that validator would now let a broken
  venv proceed where it previously aborted · severity: medium · → mitigation: TBD
- `pip_install_guarded` ALWAYS returning 0 is a subtle, easily-"simplified"
  contract: returning pip's real status would silently relocate the abort back to
  every call site. Mitigated in-plan by the rationale comment and the structural
  tripwire, but it stays a latent maintenance hazard · severity: low ·
  → mitigation: TBD
- §2b introduces a `die` inside an otherwise-optional tier — a deliberate
  exception to "never block the core setup", taken because
  `resolve_pypy_python` selects on interpreter identity alone and would keep
  choosing a dependency-broken venv. Net risk is *reduced* versus today (that
  case already aborts, silently, via `set -e`), but it is a second exit path in
  a function whose contract reads "never fails" · severity: low ·
  → mitigation: TBD

### Goal-achievement risk: low
- The behavioural test proves the guards against a **stub** pip that exits 1, not
  against a genuinely offline machine. Stub-exit-1 and a real network partition
  are not the same ground truth (pip may fail differently, and the
  already-satisfied short-circuit at line 860 is exactly the behaviour the
  offline-but-healthy case depends on) · severity: low ·
  → mitigation: offline_setup_manual_verification
- Driving `setup_python_venv` end-to-end in a test (cases 6-7) needs a scratch
  `HOME` plus stubs satisfying `find_modern_python` and `install_python_wrappers`.
  Feasible, but if it proves fiddly those two cases could shrink; the helper-level
  negative control (§C) and the structural tripwire (§B) still cover the site ·
  severity: low · → mitigation: TBD
- Cases 5b/5c depend on `chmod` write bits actually denying removal, so they are
  skipped under root and could be skipped in some CI images — a skip that hides a
  regression in the §2b escalation. The skip must be *reported*, not silent ·
  severity: low · → mitigation: TBD

### Planned mitigations
- timing: after | name: offline_setup_manual_verification | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement — the guards are proven against a stub `pip` exiting 1, not a real network partition | desc: On a network-disconnected machine, verify `ait setup` completes with warnings and exit 0 when the venv and all installed tiers are already healthy, and still dies with the `CPython venv still bad (…). Check pip/network` message when a core dep is deliberately removed

## Final Implementation Notes

- **Actual work done:** `pip_install_guarded()` added and all 8 fallible
  `pip install` sites in `aitask_setup.sh` routed through it
  (`setup_pypy_venv` 3, `setup_chat_deps` 2, `setup_python_venv` 3); the PyPy
  degrade path made escalating (full removal → interpreter-only removal → `die`
  with instructions); `setup_dev_deps` left on its early-return shape with a
  comment recording why. Beyond the original scope, `resolve_pypy_python()` was
  hardened to require the whole importable runtime set (CR1 + CR2), with the set
  single-sourced in `lib/python_resolve.sh` and `AIT_IMPORTS_COMMON` derived from
  it. Two new/extended test files with negative controls throughout.

- **Deviations from plan:**
  - The task's suggested `if ! cmd; then warn; return 0; fi` was **not** applied
    verbatim. Early-return would skip the `verify_venv_*` check that is the only
    thing able to distinguish "network down" from "venv broken" — it would warn
    that a healthy chat tier is broken, and skip PyPy's remove-and-fall-back.
    The helper warns and lets each caller's existing verification decide.
  - Scope widened to `setup_python_venv` (user-approved) and then, via review,
    to `lib/python_resolve.sh`.

- **Issues encountered:**
  - The scope-widening premise was **wrong** and is corrected in Context above:
    real pip exits 0 offline for `--upgrade pip` and for already-satisfied specs,
    so a healthy offline machine never aborted. The real trigger is offline (or a
    broken index/proxy/TLS path) **and** an unsatisfied dependency.
  - Three defects in my own tests, each of which would have made a green run
    meaningless: `make_mutant` running inside `$( )` (self-checks lost to a
    subshell — a deliberately non-matching `sed` still reported 40/40 green);
    `run_case` inheriting the developer's `PATH` (the host's real `pypy3.11`,
    probed before `pypy3`, displaced the planted stub); and stubs whose
    dependency visibility came from the host's `python3` rather than the test
    (fixed with `-S` plus fake package trees).
  - A stub-fidelity trap: a minimal fake `sys.implementation` breaks the import
    machinery (`cache_tag`, then "takes no arguments"). The stubs now copy the
    real namespace and override only `.name`.
  - **The probe leaked stdout.** `import yaml` under PyPy prints Cython
    diagnostics, and `resolve_pypy_python` returns the interpreter path on
    stdout, so the first live run returned noise prepended to the path — every
    board launch would have exec'd it. Both streams are now discarded.

- **Key decisions:**
  - The guard helper **always returns 0** by design; returning pip's status would
    relocate the abort to every call site. Documented in-code so it is not
    "simplified" away.
  - The PyPy degrade may `die` — a deliberate exception to "an optional tier
    never blocks setup" — because leaving a selectable, dependency-broken PyPy is
    worse than stopping with instructions.
  - The fast-path probe imports rather than locates, accepting ~154ms once per
    `ait board` launch (memoized) to avoid handing the board an interpreter that
    cannot run it.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:650,684 — install_pypy()/_install_pypy_linux() abort all of `ait setup` via `die` when the PyPy INTERPRETER cannot be installed (e.g. `uv python install` offline). Same defect class as this task fixed for pip: an opt-in tier taking down the core install. `ait setup --with-pypy` on an offline machine dies instead of warning and continuing without the fast path. Out of scope here (this task covers `pip install` sites only); the macOS branch `_install_pypy_macos` (~line 590-612) needs the same audit.`

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. Merge target `main` per the
header above. Gate `risk_evaluated` is in the task's active set and is recorded by
the Step-9 orchestrator. Then `./.aitask-scripts/aitask_archive.sh 1374`.

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
every `ait setup`** (line 3684) — *before* either optional tier. Line 852 is
`pip install --quiet --upgrade pip`, which always contacts the index, so on an
offline machine with a completely healthy venv `ait setup` already dies there and
never reaches `setup_pypy_venv` / `setup_chat_deps` at all. Fixing only the two
tiers would relocate the reported symptom rather than remove it.

**Intended outcome:** an offline / flaky-network `ait setup` degrades — warning
where the tier is optional, dying with the *informative* message where the core
venv is genuinely broken — instead of aborting partway through on a machine whose
dependencies are already fine.

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

### E. Lint

```bash
shellcheck .aitask-scripts/aitask_setup.sh
bash tests/test_setup_verify_venv_imports.sh   # neighbouring sourcing test unaffected
```

## Files

- `.aitask-scripts/aitask_setup.sh` — new helper; 8 call sites; the escalating
  PyPy removal (§2b); 1 explanatory comment in `setup_dev_deps`.
- `tests/test_setup_pip_install_guards.sh` — new.

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

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. Merge target `main` per the
header above. Gate `risk_evaluated` is in the task's active set and is recorded by
the Step-9 orchestrator. Then `./.aitask-scripts/aitask_archive.sh 1374`.

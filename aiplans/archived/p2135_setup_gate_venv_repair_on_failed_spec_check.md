---
Task: t2135_setup_gate_venv_repair_on_failed_spec_check.md
Base branch: main
Output branch: main
---

# t2135 — setup: treat a failed version check as "needs repair"

## Context

t2133 added the global `specs_check_ok` to `verify_venv_specs`
(`.aitask-scripts/aitask_setup.sh:109`): it is `false` when the version
inspection itself fails (e.g. neither `packaging` nor `pip._vendor.packaging`
importable), in which case `bad_specs` is empty. Only the read-only
`report_venv_dep_drift` was taught to read it. The four setup call sites still
decide repair/failure on `missing_imports` + `bad_specs` alone, so "imports fine,
inspection failed" reads as "all in range" and setup reports success without
enforcing any version floor (e.g. `rich>=14.3.3`).

Sites (each has a "need repair → retry" condition and a final "still bad"
condition — 8 conditions, 8 messages):

| function | line | final outcome |
|---|---|---|
| `setup_pypy_venv` | 729 / 736 | warn + remove PyPy venv (CPython fallback) |
| `setup_chat_deps` | 803 / 810 | warn, return 0 |
| `setup_dev_deps` | 864 / 873 | warn, return 0, no opt-in marker |
| `setup_python_venv` | 966 / 972 | `die` |

Every message today renders `version: ${bad_specs[*]:-none}` — which prints
`version: none` for a failed check, i.e. the message would claim the versions
are fine.

## Implementation

### 1. `.aitask-scripts/aitask_setup.sh` — two helpers after `verify_venv_specs`

```bash
# venv_deps_bad — true when the last verify_venv_imports + verify_venv_specs
# pair found a problem: a module that will not import, a spec out of range, or
# a version inspection that itself failed. The last leaves bad_specs empty, so
# testing bad_specs alone reads a failed check as "all in range" (t2135).
venv_deps_bad() {
    [[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 || "$specs_check_ok" != true ]]
}

# venv_deps_detail — the "missing: …; version: …" text for the warn/die that
# follows venv_deps_bad. A failed inspection is named as such, never rendered
# as "version: none".
venv_deps_detail() {
    if [[ "$specs_check_ok" == true ]]; then
        printf 'missing: %s; version: %s' "${missing_imports[*]:-none}" "${bad_specs[*]:-none}"
    else
        printf 'missing: %s; version check failed' "${missing_imports[*]:-none}"
    fi
}
```

Also amend the `verify_venv_specs` header comment's last sentence to say
`venv_deps_bad` and `report_venv_dep_drift` both distinguish the two.

### 2. Convert the 8 conditions + messages (same pattern at every site)

- `if [[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 ]]; then`
  → `if venv_deps_bad; then`
- `(missing: ${missing_imports[*]:-none}; version: ${bad_specs[*]:-none})`
  → `($(venv_deps_detail))` — wording around it unchanged.
- CPython final line: `[[ … ]] && \ die "…"` → `venv_deps_bad && \ die "CPython venv still bad ($(venv_deps_detail)). …"`
  (same `&&` errexit shape as today: a false predicate in a non-final `&&`
  position does not trip `set -e`).

`report_venv_dep_drift` is untouched (it already branches on `specs_check_ok`).
Afterwards grep must find no `bad_specs[@]} -gt 0` outside `venv_deps_bad` and
`report_venv_dep_drift`.

### 3. `tests/test_setup_pip_install_guards.sh` — behavioural cases

- Fixture: `make_home <home> <deps_ok> [specs_ok=1]` and
  `_make_py_stub <path> <impl> <deps_ok> [runtime_ok] [specs_ok=1]`.
  `fresh_home <name> <deps_ok> [specs_ok]` passes it through; existing callers
  unchanged. The stub's `-)` branch discards stdin, appends one line to
  `<stub-path>.inspections` (a per-stub call log), then:
  - `specs_ok=1` → today's behaviour (deps_ok decides the canned output);
  - `specs_ok=0` → `exit 1` every time (the inspection failing the way an
    unimportable `packaging` does);
  - `specs_ok=once` → `exit 1` on the first inspection, clean `exit 0`
    afterwards (a failure the repair fixes).
- Add `make_pip_ok <home>`: overwrite `$home/.aitask/venv/bin/pip` with an
  `exit 0` stub (the dev tier short-circuits on a failing pip before verifying,
  so it needs a succeeding one to reach the verify block).
- Driver: add `dev) setup_dev_deps ;;`.
- New section after case 7 — "8: imports pass, version check fails":
  - 8a cpython: rc ≠ 0; ERR contains `CPython venv still bad (missing: none; version check failed)`; OUT contains `need repair (missing: none; version check failed)`.
  - 8b pypy: rc 0; PyPy venv dir removed; OUT contains `version check failed`.
  - 8c chat: rc 0; OUT contains `Chat deps could not be installed (missing: none; version check failed)`; not `Chat SDK deps ready`.
  - 8d dev control (deps ok, specs ok, pip ok): `Dev/test deps ready`, marker `$h/.aitask/dev_tier` exists — proves the dev fixture itself works.
  - 8e dev: rc 0; OUT contains `Dev deps could not be installed (missing: none; version check failed)`; marker absent.
- New section "9: version check fails once, repair recovers" (`specs_ok=once`),
  the recovery direction: 8a–8e only prove the rejection, and they would still
  pass if a site skipped its post-repair re-check, leaving a stale
  `specs_check_ok=false` that rejects a venv the repair made healthy. Each case
  asserts that the repair was attempted, the ready outcome was reached, and the
  inspection ran exactly twice (`<venv>/bin/python.inspections` has 2 lines:
  initial check + post-repair re-check):
  - 9a cpython: rc 0, `__REACHED_END__`; OUT contains `CPython venv deps need repair (missing: none; version check failed). Retrying...`; ERR lacks `still bad`.
  - 9b pypy: rc 0; PyPy venv dir kept; OUT contains `PyPy venv deps need repair (missing: none; version check failed)`; lacks `could not be installed`.
  - 9c chat: rc 0; OUT contains `Chat deps need repair (missing: none; version check failed)` and `Chat SDK deps ready`.
  - 9d dev (pip ok): OUT contains `Dev deps need repair (missing: none; version check failed)` and `Dev/test deps ready`; marker exists.
- Negative control C3 (the predicate): `make_mutant specscheck 's/ || "\$specs_check_ok" != true ]]/ ]]/'`
  (the string occurs only in `venv_deps_bad`; `make_mutant` already asserts the
  sed changed something, parses, and sources). Re-run 8a–8c, 8e against it and
  assert the pre-fix behaviour returns: cpython rc 0 + `__REACHED_END__`; pypy
  dir kept; chat `Chat SDK deps ready`; dev marker written. This proves the
  section-8 cases detect exactly the `specs_check_ok` clause.
- Negative control C4 (the re-check): `make_mutant norecheck 's|^        verify_venv_specs   |        : |'`
  turns the four post-repair `verify_venv_specs` calls (the only 8-space-indented
  ones with the 3-space alignment; `report_venv_dep_drift`'s call has one space)
  into no-ops. Assert the mutant differs from the source in exactly 4 lines, then
  re-run 9a–9d against it and assert each flips to rejection: cpython rc ≠ 0 with
  `still bad`; pypy dir removed; chat `could not be installed`; dev marker absent;
  and each `.inspections` log has 1 line. One mutant covers all four sites
  because each case exercises only its own site.

### 4. `tests/test_setup_verify_venv_imports.sh` — unit asserts for the helpers

After the "failed inspection" block: with imports all present —
`STUB_SPECFAIL` → `venv_deps_bad` true and `venv_deps_detail` contains
`version check failed`; `STUB_OK` → `venv_deps_bad` false; `STUB_VER` →
detail contains `version: textual 7.0.0 (need >=8.2.7,<9)`.

## Verification

```bash
bash tests/test_setup_pip_install_guards.sh
bash tests/test_setup_verify_venv_imports.sh
bash tests/test_aitasks_home.sh          # stubs setup_dev_deps; must stay green
shellcheck .aitask-scripts/aitask_setup.sh
grep -n 'bad_specs\[@\]} -gt 0' .aitask-scripts/aitask_setup.sh   # only the 2 expected sites
```

Then Step 9 (Post-Implementation): commit, archive per the task workflow.

## Risk

### Code-health risk: low
- The core CPython path becomes fail-closed: an inspection that fails for any reason (no importable packaging, but also e.g. corrupted dist-info making `version()` raise, or a future malformed spec string) now aborts `ait setup` where it previously passed silently, and the message cannot say why (the inspection's stderr is discarded) · severity: low — this is the requested direction; a venv whose pip cannot import its own vendored packaging is genuinely broken, and a malformed shipped spec should fail loudly · → mitigation: none (accepted)
- Test fixture signatures grow optional trailing parameters and a stateful `once` mode (a per-stub inspection log) · severity: low — defaults keep every existing caller's behaviour; each case uses a fresh home so the log cannot leak between cases; section 8 + C3 pin the rejection direction and section 9 + C4 pin the recovery direction · → mitigation: none

### Goal-achievement risk: low
None identified. All four sites named by the task (both conditions each) and their messages are converted through one predicate, each site gets a behavioural case, and the mutation control proves the cases fail without the fix.

## Post-Review Changes

### Change Request 1 (2026-10-25, during plan review — before the 06:30 plan approval)
- **Requested by user:** the always-pass / always-fail fixtures cannot see a site that skips its post-repair re-check (a stale `specs_check_ok=false` would then reject a venv the repair made healthy); add a stateful fail-once-then-succeed case asserting the repair is attempted and the ready outcome reached.
- **Changes made:** added the `specs_ok=once` stub mode with a per-venv inspection log, section 9 (recovery cases for all four sites, each asserting exactly two inspections), and negative control C4 (no-op every post-repair `verify_venv_specs`; asserted to change exactly 4 lines).
- **Files affected:** `tests/test_setup_pip_install_guards.sh` (plan only at the time; implemented in Step 7).

## Final Implementation Notes
- **Actual work done:** Added `venv_deps_bad` / `venv_deps_detail` after `verify_venv_specs` in `.aitask-scripts/aitask_setup.sh` and converted all 8 repair/failure conditions and their 8 messages in `setup_pypy_venv`, `setup_chat_deps`, `setup_dev_deps`, `setup_python_venv`; a failed inspection now triggers the repair, then the site's failure outcome, and is named "version check failed". `tests/test_setup_pip_install_guards.sh`: `specs_ok` fixture parameter (1 / 0 / once), `dev` driver case, `make_pip_ok`, `inspections` helpers, sections 8 (8a–8e, incl. the 8d dev-fixture control) and 9 (9a–9d), negative controls C3 and C4 — 108/108 pass. `tests/test_setup_verify_venv_imports.sh`: 4 direct helper asserts — 30/30 pass. `tests/test_aitasks_home.sh` 460/460 and `tests/test_python_resolve_pypy.sh` 14/14 unchanged-green.
- **Deviations from plan:** the inspection log is `<venv-dir>.inspections` (a sibling of the venv directory, derived as `${path%/bin/python}.inspections`) rather than `<stub-path>.inspections`, so the count survives setup removing the PyPy venv under C4. The log append is best-effort (`2>/dev/null || :`) because cases 5b/5c make that directory read-only and never read the count.
- **Issues encountered:** none in the code. The working tree also carried another session's uncommitted edits (`verified_update_lib.sh`, `metadata_update_fixture.sh`, `test_usage_update.sh`, `test_verified_update.sh`); the commit names only this task's three files.
- **Key decisions:** one shared predicate instead of 8 inline edits, so each mutant is a single targeted sed (C3: the predicate clause; C4: the four re-checks) and the sites cannot drift. Red proof: the new test run against the pre-fix script (`bcdeff693`, scratch worktree) fails every section-8 and section-9 case (23 failures) while the 8d control passes. Shellcheck findings on `aitask_setup.sh` are identical to HEAD (31 = 31); the one new SC2016 note in the guards test is the C3 sed script's intentional literal `\$`, the same class as the existing C1/C2 mutant scripts.
- **Upstream defects identified:** None

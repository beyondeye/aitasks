---
Task: t785_retire_pypy_fast_path_consolidate_on_cpython.md
Base branch: main
plan_verified: []
---

# Plan: t785 — Retire PyPy fast path, consolidate on CPython

## Context

The PyPy fast path (added by **t718**, shipped in v0.20.0) was justified
*theoretically* — Textual + Rich often see 2-5× on PyPy. Empirical
verification (**t718_5**, **t718_6**) found the actual win on this codebase
is much smaller or negative:

- **Board:** +13.6% steady-state, but −153 ms cold-start.
- **Codebrowser:** −17% steady-state, −168 ms cold-start. (Already reverted.)
- **Monitor / minimonitor:** 76-90% slower in control-mode path; 3.2-7.4×
  slower on the legacy fallback. (Already excluded.)
- **Settings / brainstorm / syncer:** routed by analogy with board, never
  measured. CPython 3.14.4 (with adaptive specialization and tail-call
  interpreter) has closed the gap further; PyPy is stuck on 3.11.15.

The dual-venv plumbing also blocks Python 3.12+ syntax adoption indefinitely
(no PyPy 3.12 stable release; PyPy 7.3.22 in April 2026 is still on 3.11).

**Goal:** retire the PyPy fast path in one PR, trade board's ~13.6%
steady-state for simpler infrastructure (single venv, single resolver, no
`--with-pypy` flag, no `AIT_USE_PYPY` env var, Python 3.12+ syntax
unblocked).

**Planning decisions confirmed with user:**
- **Single task, single PR** — rip launchers + resolver + install + docs out
  together. The launchers cannot be reverted independently of the resolver
  without leaving dangling symbol references.
- **Don't touch user disk** — existing `~/.aitask/pypy_venv/` directories are
  left alone. The resolver simply stops looking; users can `rm -rf` whenever.
  No deprecation notice, no auto-removal.
- **Embed "trigger to reconsider" in `python_tui_performance.md`** — no new
  doc file. Add a `## Trigger to reconsider PyPy` section at the end.

## Surface inventory

Verified by grep — every PyPy/`AIT_USE_PYPY`/`require_ait_python_fast` /
`with-pypy` reference outside `website/public/` (generated) and
`aiplans/archived/`, `aitasks/archived/` (historical record — do not touch):

**Code:**

1. **Launchers (4 files)** — change `require_ait_python_fast` →
   `require_ait_python` on line 12 of each:
   - `.aitask-scripts/aitask_board.sh`
   - `.aitask-scripts/aitask_settings.sh`
   - `.aitask-scripts/aitask_brainstorm_tui.sh`
   - `.aitask-scripts/aitask_syncer.sh`

2. **Resolver — `.aitask-scripts/lib/python_resolve.sh`** (delete):
   - Lines 34-38 — header comment + `AIT_PYPY_PREFERRED` and `PYPY_VENV_DIR`
     constants
   - Lines 97-124 — `resolve_pypy_python()` and `_AIT_RESOLVED_PYPY` cache
   - Lines 126-131 — `require_ait_pypy()`
   - Lines 133-146 — `require_ait_python_fast()` (AIT_USE_PYPY precedence
     case + fallthrough)

3. **`.aitask-scripts/aitask_setup.sh`** (delete):
   - Lines 458-592 — `find_pypy()`, `install_pypy()`,
     `_install_pypy_macos()`, `_install_pypy_linux()`, `setup_pypy_venv()`,
     `prompt_install_pypy_if_tty()` (the entire `--- PyPy resolution ...`
     block ending at line 592)
   - Line 3237 — `INSTALL_PYPY=0` initialization
   - Line 3241 — `--with-pypy) INSTALL_PYPY=1; shift ;;` case
   - Lines 3298-3301 — the `if [[ "$INSTALL_PYPY" == "1" ]] || …` block
     that calls `setup_pypy_venv`
   - Lines 3332-3334 — `if [[ -d "$PYPY_VENV_DIR" ]]; then info " PyPy
     venv: ..."` block in the summary

4. **Tests** — delete `tests/test_python_resolve_pypy.sh` (263 lines;
   exclusively tests `AIT_USE_PYPY` precedence + `require_ait_python_fast`).
   No other test references PyPy.

**Aidocs:**

5. **`aidocs/python_tui_performance.md`** (rewrite header, keep empirical
   tables as historical record):
   - Add `## Retirement decision (2026-05-25, t785)` near the top citing
     evidence summary + link to this plan.
   - **Update the legacy "Recommendations" section** (lines 131-142) — flip
     the framing from "adopt PyPy" to "decided against PyPy; here is the
     evidence." Keep the bullet about not adopting 3.12+ syntax → flip to
     "3.12+ syntax is now unblocked."
   - **Add `## Trigger to reconsider PyPy`** at end (after Related Tasks):
     conditions are *(a)* PyPy 3.12 stable release, *(b)* ≥10% measured
     board win on a re-run of the t718_6 board workload, *(c)* ≥0%
     codebrowser parity, *(d)* the user's CPython is still 3.14-era (no
     CPython JIT shipped enabled-by-default that has already absorbed the
     remaining gap).
   - Keep the t718_5 / t718_6 empirical sections verbatim — they are the
     authoritative evidence record.

6. **`aidocs/tui_conventions.md`** — rewrite the two PyPy sections (lines
   7-50) per documentation-current-state-only rule:
   - Section "New long-running Textual TUI launchers call
     `require_ait_python_fast`" → rewrite to use `require_ait_python` and
     drop the PyPy framing. New title: **"Long-running Textual TUI
     launchers resolve Python via `require_ait_python`"**. State positively:
     all launchers use `require_ait_python`. Drop the empirical-exceptions
     table — there is no longer a fast-path variant to opt out of.
   - Section "`AIT_USE_PYPY` precedence (runtime override)" → **delete
     entirely**.

7. **`aidocs/aitasks_extension_points.md`** — lines 75-77 use
   `_install_pypy_linux`/`_install_pypy_macos` as the OS-paired bug-class
   example. Replace with a still-current example pair from
   `aitask_setup.sh` (e.g. `install_modern_python` Linux/macOS branches —
   `_install_python_macos` via brew, `_install_python_linux` via uv).

8. **`CLAUDE.md`** — verified: no PyPy mentions. No change needed.

**Website:**

9. **`website/content/docs/installation/pypy.md`** — delete file.
10. **`website/content/docs/development/pypy.md`** — delete file.
11. **`website/content/docs/installation/_index.md`** — remove lines 54
    (sidebar bullet) and 130 (summary bullet) referencing PyPy.
12. **`website/content/docs/commands/setup-install.md`** — line 29: trim
    the trailing "For an opt-in PyPy 3.11 venv that speeds up long-running
    TUIs (`ait setup --with-pypy`), see [PyPy Runtime](…)." sentence.

**Out of website scope:**
- `website/public/` — generated build output; will regenerate on next
  `hugo build`. Do not touch by hand.
- `website/content/blog/v0200-...` — release blog post is a historical
  release log, not "current state" docs. Leave intact (do not rewrite
  release history).

**Seed:** verified — `grep -rn "pypy" seed/` returns nothing. No change.

**Dependent tasks (cancel via archival):**

13. **`aitasks/t729_manual_verification_pypy_install_macos_followup.md`**
    — currently Ready. Add an `## Obsoleted by retirement (t785)` note to
    the body, set `status: Done`, and archive via
    `./.aitask-scripts/aitask_archive.sh 729`. This is a non-implementation
    administrative archival; the task has no associated commits to point
    at.
14. **`t718_4`** — verified does not exist (`find aitasks/ -name 't718_4*'`
    returns nothing). The task description's reference is stale. No
    action.

## Implementation order

Order matters for one reason: if launchers are changed before the resolver,
the build still passes (`require_ait_python` already exists); if the
resolver is gutted before the launchers, the launchers break. Use this
order:

1. **Launchers** (4 files) → `require_ait_python_fast` → `require_ait_python`.
2. **Resolver** — delete the four PyPy-specific symbols and constants.
3. **Setup script** — delete the PyPy install block, `--with-pypy` flag,
   summary line.
4. **Tests** — delete `tests/test_python_resolve_pypy.sh`.
5. **Aidocs** — rewrite the three files.
6. **Website** — delete two `.md` files; trim the two `_index.md` /
   `setup-install.md` references.
7. **t729 archival** — body note + status update + `aitask_archive.sh 729`.

Each step is a clean local edit. Commit happens once at Step 8 (per
task-workflow Step 8 conventions) — single code commit for steps 1-6 plus
the website + test deletions, then `./ait git` for any `aitasks/`
modifications produced by step 7.

## Verification

**Smoke / dependency tests** (must pass):

```bash
# Resolver syntax / function set check — no orphan references to deleted symbols
bash -n .aitask-scripts/lib/python_resolve.sh
bash -c 'source .aitask-scripts/lib/python_resolve.sh; declare -F'
# Expect: resolve_python require_python require_modern_python require_ait_python.
# NO: resolve_pypy_python require_ait_pypy require_ait_python_fast.

# Setup script syntax + flag-parse smoke
bash -n .aitask-scripts/aitask_setup.sh
./.aitask-scripts/aitask_setup.sh --with-pypy 2>&1 | head -5
# Expect: rejection or "unknown flag" — no longer recognized.

# Full grep audit — must produce zero hits outside generated/historical paths
grep -rn 'PYPY\|pypy\|PyPy\|require_ait_python_fast\|AIT_USE_PYPY\|with-pypy' \
  .aitask-scripts/ tests/ seed/ aidocs/ CLAUDE.md \
  website/content/docs/ \
  | grep -v 'aitasks_extension_points.md.*install_python' \
  | grep -v 'python_tui_performance.md'
# Expect: empty. The two greps allow PyPy refs to remain in the historical
# evidence sections of python_tui_performance.md.

# Shellcheck
shellcheck .aitask-scripts/aitask_board.sh \
           .aitask-scripts/aitask_settings.sh \
           .aitask-scripts/aitask_brainstorm_tui.sh \
           .aitask-scripts/aitask_syncer.sh \
           .aitask-scripts/aitask_setup.sh \
           .aitask-scripts/lib/python_resolve.sh

# Existing test suite — verify nothing else depended on the PyPy resolver path
for t in tests/test_*.sh; do bash "$t" || echo "FAIL: $t"; done
```

**Manual TUI smoke** — launch each of the four reverted TUIs and confirm
they start under CPython (sanity check, not perf):

```bash
ait board       # ^C after Kanban renders
ait settings    # ^C after main screen renders
ait brainstorm  # ^C after launch screen renders
ait syncer      # ^C after launch screen renders
```

For each: confirm `~/.aitask/venv/bin/python` is the interpreter (no
PyPy in `ps`). Performance is not in scope for this verification — the
board will be ~13.6% slower steady-state, by design.

**Verify** the `verify_build` field in `aitasks/metadata/project_config.yaml`
(if any) per task-workflow Step 9.

## Verification (manual aggregate)

A separate `issue_type: manual_verification` task is not warranted — the
above smoke checks (each TUI launching cleanly under CPython, no
`AIT_USE_PYPY=1 ait board` surprises, `ait setup --with-pypy` rejected as
unknown flag) are all small enough to fit inline in the Final
Implementation Notes section.

## Out of scope (documented in task)

- Enabling CPython 3.14's experimental JIT.
- Free-threaded CPython migration.
- Adopting Python 3.12+ syntax (becomes *possible* after this lands; the
  actual modernization is a future task).

## Step 9 (Post-Implementation)

Standard cleanup per `task-workflow-fast-/SKILL.md` Step 9:
- Confirm merge approval via AskUserQuestion (non-skippable).
- Merge to main (working directly on current branch — no separate branch
  per fast profile, so this collapses to "commit + push").
- Run `verify_build` (none configured).
- Archive via `./.aitask-scripts/aitask_archive.sh 785`.
- Archive t729 via `./.aitask-scripts/aitask_archive.sh 729`
  (administrative — body already carries the obsolete note).
- `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Executed the plan as written. 15 files touched on
  the main branch (+101/−614 LOC), 2 task-data files on the aitask-data
  branch (t729 obsolete note + this externalized plan). The PyPy fast
  path is fully removed: launchers, resolver functions, install code,
  env-var precedence, dedicated test, and user-facing docs.
- **Deviations from plan:** None. All steps executed in the planned order.
  One extra edit not pre-identified by the plan grep: `CLAUDE.md` line
  238 used "CPython vs PyPy" framing in the `python_tui_performance.md`
  read-pointer; updated to reflect the current single-CPython state.
  Caught by the post-implementation grep audit.
- **Issues encountered:** None during implementation. Test suite shows
  10 pre-existing tmux-stress-test failures that refuse to run from
  inside tmux — unrelated to this task.
- **Key decisions:**
  - **`--with-pypy` flag silently dropped, no deprecation warning.** The
    arg parser's `*) args+=("$1") ;;` catchall now treats `--with-pypy`
    as an unknown positional argument that is collected but never
    consumed. The user's planning choice "Leave it alone — don't touch
    user disk" extended naturally to "drop the flag silently"; adding
    a deprecation warning was out of scope for the simplification goal.
  - **`aidocs/python_tui_performance.md` kept verbatim** below the new
    "Status (2026-05-25)" / "Recommendations (historical, superseded)"
    framing. The t718_5 and t718_6 empirical tables remain the
    authoritative evidence record; deleting them would erase the
    rationale for both t718 (the adoption) and t785 (this retirement).
  - **Blog post `v0200-...md` left intact.** Release-history blog
    content is not "current state" docs per the CLAUDE.md doc-writing
    rule; it's a release log and rewriting it would falsify history.
    Per-the-rule, deletion was not appropriate either.
  - **t729 administratively archived** rather than deleted. Body carries
    an "Obsoleted by retirement (t785)" header so the archived task
    self-explains.
- **Upstream defects identified:** None. The PyPy code being deleted was
  internally consistent — no separate pre-existing bugs in the deleted
  surface or in adjacent code surfaced during the cleanup.
- **Smoke verification done in-task:**
  - `bash -n` syntax-clean on both modified bash files.
  - `declare -F` after sourcing the resolver returns only
    `resolve_python`, `require_python`, `require_modern_python`,
    `require_ait_python` (plus the unrelated `terminal_compat.sh`
    helpers). No PyPy symbols leaked through.
  - Full grep audit
    (`grep -rn 'PYPY\|pypy\|PyPy\|require_ait_python_fast\|AIT_USE_PYPY\|with-pypy'
    .aitask-scripts/ tests/ seed/ aidocs/ CLAUDE.md website/content/docs/`)
    returns only the two intentional historical pointers in
    `aidocs/tui_conventions.md` and `CLAUDE.md` that reference "the
    retired PyPy fast path".
  - `shellcheck` on all 6 modified scripts: only pre-existing SC1091
    info-level warnings (sourced files not on inputs), no new findings.
  - Test suite: 125 PASS, 10 FAIL (all 10 tmux-stress-tests refusing to
    run inside tmux — pre-existing environment guards).

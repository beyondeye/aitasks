---
Task: t831_add_back_support_for_pypy_for_ait_board.md
Base branch: main
plan_verified: []
---

# Plan: t831 — Add back PyPy support, scoped to `ait board` only

## Context

t785 (commit `84d34173`, 2026-05-25) retired the PyPy fast path on the
strength of benchmark numbers showing the board only gained ~13.6%
steady-state. After living with the post-t785 state, the user reports the
real-world slowdown of `ait board` is much larger than the benchmark
estimate. `ait board` is one of the primary interaction surfaces of the
framework, so the trade-off is no longer favorable.

t831 reintroduces the PyPy fast path *for `ait board` only*. The dual-venv
plumbing, install helpers, env-var contract, resolver functions, and tests
all return; only the launcher wiring is narrowed — `aitask_settings.sh`,
`aitask_brainstorm_tui.sh`, and `aitask_syncer.sh` stay on the canonical
`require_ait_python` (their PyPy routing was always speculative — never
empirically measured per the t785 plan notes).

## Approach

Reverse t785 mechanically (`git revert 84d34173`), resolve the single
known conflict in `CLAUDE.md`, then forward-edit three launchers + the
two main docs to express *board-only* intent instead of the pre-t785
*board + settings + brainstorm + syncer* policy. Un-archive t729 (the
macOS PyPy install manual-verification follow-up) so it surfaces again
in the board.

## Implementation

### Step 1 — Mechanical revert of t785

```bash
git revert --no-commit 84d34173
```

This restores **15 files**:
- 4 launchers (`aitask_board.sh`, `aitask_settings.sh`,
  `aitask_brainstorm_tui.sh`, `aitask_syncer.sh`) — all flipped back to
  `require_ait_python_fast`
- `aitask_setup.sh` — 146 lines of PyPy install code restored
  (`find_pypy`, `install_pypy`, `_install_pypy_{linux,macos}`,
  `setup_pypy_venv`, `prompt_install_pypy_if_tty`, the `--with-pypy`
  flag, the post-install summary line)
- `python_resolve.sh` — 56 lines restored (`AIT_PYPY_PREFERRED`,
  `PYPY_VENV_DIR`, `resolve_pypy_python`, `_AIT_RESOLVED_PYPY` cache,
  `require_ait_pypy`, `require_ait_python_fast` with `AIT_USE_PYPY`
  precedence)
- `tests/test_python_resolve_pypy.sh` — 263-line test file restored
- `aidocs/python_tui_performance.md` — Status banner removed, returns
  to pre-t785 framing
- `aidocs/tui_conventions.md` — `require_ait_python_fast` + `AIT_USE_PYPY`
  sections restored
- `aidocs/aitasks_extension_points.md` — OS-paired bug example reverts
  to `_install_pypy_linux`/`_install_pypy_macos`
- `website/content/docs/installation/pypy.md` + `development/pypy.md`
  — both deleted files re-created
- `website/content/docs/installation/_index.md` + `commands/setup-install.md`
  — sidebar / cross-ref entries re-added
- `CLAUDE.md` — **CONFLICT** at lines 237-252 (see Step 2)

### Step 2 — Resolve the CLAUDE.md conflict

t825 inserted a new `monitor_idle_and_prompt_detection.md` pointer after
the `python_tui_performance.md` pointer, so the revert sees competing
edits in the same region. Keep both pointers, with new wording for
python_tui_performance that reflects *board-only* state:

Replace the conflict block (lines 237-252 in the conflicted file) with:

```markdown
> **Read `aidocs/python_tui_performance.md`** when re-evaluating a TUI's
> Python runtime (CPython vs PyPy) choice. The framework currently routes
> only `ait board` through the PyPy fast path; the document records the
> empirical evidence for that scoping decision and the criteria for
> reconsidering other TUIs.
>
> **Read `aidocs/monitor_idle_and_prompt_detection.md`** when `ait monitor`
> / `ait minimonitor` fails to flag an agent that is visibly waiting on
> user input, when adding a new code-agent CLI, or when changing how idle
> vs. "awaiting user input" is detected. The patterns live in
> `.aitask-scripts/monitor/prompt_patterns.py` and are edited in-place when
> a new agent's prompt wording shows up.
```

### Step 3 — Restrict the fast path to `ait board`

t785's revert restores `require_ait_python_fast` on **four** launchers,
but t831 wants only `ait board`. Forward-edit the other three back to
`require_ait_python` (single line each):

- `.aitask-scripts/aitask_settings.sh:12`
- `.aitask-scripts/aitask_brainstorm_tui.sh:12`
- `.aitask-scripts/aitask_syncer.sh:12`

`aitask_board.sh:12` stays on `require_ait_python_fast` (no edit needed
post-revert).

### Step 4 — Update docs to express board-only scope

#### `aidocs/python_tui_performance.md`

The revert restores the pre-t785 text which routes board + settings +
brainstorm + syncer to the fast path. Update the **PyPy Distribution
Integration Sketch** section (the "TUI launchers" row in the comparison
table around line 138 of the post-revert file) to read:

> `aitask_board.sh` uses `require_ait_python_fast` (PyPy if available,
> else CPython). `aitask_settings.sh`, `aitask_brainstorm_tui.sh`, and
> `aitask_syncer.sh` were originally routed by analogy with board but
> were never empirically measured; per t785 / t831 they stay on
> `require_ait_python`. `aitask_codebrowser.sh`, `aitask_monitor.sh`,
> `aitask_minimonitor.sh`, `aitask_stats_tui.sh` stay on CPython
> (empirically verified loss or `plotext` install gap).

Also add a short note at the top (above the legacy investigation
content) recording the t831 re-scoping:

```markdown
## Status (2026-05-25, t831): PyPy fast path restored — board only

t785 retired the PyPy fast path on the strength of benchmarks that
under-estimated the board slowdown. With CPython 3.14.4 in production
use, board users reported the real-world slowdown was much larger than
the predicted ~13.6%. **t831 reintroduces the PyPy fast path scoped to
`ait board` only.** Settings, brainstorm, and syncer — never empirically
measured — stay on CPython. The "Trigger to reconsider PyPy" criteria
in t785 (PyPy 3.12 stable, codebrowser parity, etc.) remain valid for
expanding the scope back to more TUIs in the future.
```

#### `aidocs/tui_conventions.md`

The revert restores the pre-t785 "long-running Textual TUI launchers
call `require_ait_python_fast`" guidance. Tighten the section to
record that `ait board` is currently the only fast-path consumer:

- Change the section title to **"Long-running Textual TUI launchers may
  call `require_ait_python_fast` (current scope: `ait board` only)"**.
- Update the body to state that *new* fast-path adoptions require an
  empirical perf test against the t718_6 protocol; routing by analogy
  is what motivated t785's retirement and is no longer acceptable.
- Keep the `AIT_USE_PYPY` runtime-override section verbatim — it
  remains the documented escape hatch for users who want to A/B test
  other TUIs.

#### `aidocs/aitasks_extension_points.md`

No further edit needed beyond Step 1's revert — the OS-paired
`_install_pypy_linux` / `_install_pypy_macos` example is correct again.

#### Website docs

`website/content/docs/installation/pypy.md` and `development/pypy.md`
are restored by the revert. Add a single sentence at the top of
`installation/pypy.md` clarifying that PyPy currently accelerates
`ait board` only:

> **Scope:** the installed PyPy interpreter currently accelerates
> `ait board`. Other Textual TUIs (`ait settings`, `ait brainstorm`,
> `ait syncer`) run on the default CPython venv; users who want to
> A/B test a TUI on PyPy can prefix `AIT_USE_PYPY=1 ait <command>`.

### Step 5 — Un-archive t729

`aitasks/archived/t729_manual_verification_pypy_install_macos_followup.md`
was administratively archived as "obsoleted by retirement (t785)". With
the install path restored, the macOS verification is needed again. Use
`./ait git`:

```bash
./ait git mv aitasks/archived/t729_manual_verification_pypy_install_macos_followup.md \
             aitasks/t729_manual_verification_pypy_install_macos_followup.md
```

Then edit the moved file:
- Set `status: Ready` (was `Done`)
- Remove `completed_at: 2026-05-25 10:23`
- Set `updated_at:` to the current timestamp
- Delete the entire `## Obsoleted by retirement (t785, 2026-05-25)` section
- Leave the verification checklist unchanged

This restoration is committed on the `aitask-data` branch via `./ait git`,
separately from the code changes.

### Step 6 — Stage and commit

Per task-workflow Step 8 conventions, two commits — code first (regular
`git`), then any task/plan-data file (`./ait git`):

```bash
# Code commit (the 15 reverted files + the 3 launcher tweaks + the doc
# adjustments)
git add .aitask-scripts/ aidocs/ CLAUDE.md tests/test_python_resolve_pypy.sh \
        website/content/docs/
git commit -m "bug: Restore PyPy fast path for ait board only (t831)"

# Plan + t729 un-archive
./ait git add aiplans/p831_*.md \
              aitasks/t729_manual_verification_pypy_install_macos_followup.md \
              aitasks/archived/   # for the removal side of the mv
./ait git commit -m "ait: Add plan for t831 + un-archive t729"
```

## Verification

Smoke checks before committing:

```bash
# 1. Resolver: restored symbols present, no syntax errors
bash -n .aitask-scripts/lib/python_resolve.sh
bash -c 'source .aitask-scripts/lib/python_resolve.sh; declare -F' \
  | grep -E 'resolve_pypy_python|require_ait_pypy|require_ait_python_fast'
# Expect: all three present.

# 2. Setup script: --with-pypy flag accepted
bash -n .aitask-scripts/aitask_setup.sh
./.aitask-scripts/aitask_setup.sh --help 2>&1 | grep -- '--with-pypy'
# Expect: flag documented.

# 3. Launchers: only board on fast path
for f in board settings brainstorm_tui syncer; do
  grep -H 'require_ait_python' .aitask-scripts/aitask_$f.sh
done
# Expect: aitask_board.sh → require_ait_python_fast
#         aitask_settings.sh / brainstorm_tui.sh / syncer.sh → require_ait_python

# 4. Resolver test passes (the restored file)
bash tests/test_python_resolve_pypy.sh

# 5. shellcheck all touched bash scripts
shellcheck .aitask-scripts/aitask_board.sh \
           .aitask-scripts/aitask_settings.sh \
           .aitask-scripts/aitask_brainstorm_tui.sh \
           .aitask-scripts/aitask_syncer.sh \
           .aitask-scripts/aitask_setup.sh \
           .aitask-scripts/lib/python_resolve.sh
```

Manual smoke (only if PyPy is already installed in `~/.aitask/pypy_venv/`):

```bash
ait board     # confirm runs under PyPy (^C after Kanban renders)
ps -ef | grep pypy     # in another shell while board is up
ait settings  # confirm runs under CPython (^C after main renders)
```

If PyPy is not yet installed locally, run `ait setup --with-pypy` first;
the restored install path should populate `~/.aitask/pypy_venv/` via
`uv python install pypy@3.11` (Linux) or `brew install pypy3.11` (macOS).

## Step 9 (Post-Implementation)

Standard cleanup per `task-workflow-fast-/SKILL.md` Step 9:
- Merge approval (non-skippable AskUserQuestion).
- Merge to main (fast profile works on current branch, so this collapses
  to push).
- `verify_build` — none configured for this repo, will skip.
- Archive t831 via `./.aitask-scripts/aitask_archive.sh 831`.
- `./ait git push`.
- The un-archived t729 will re-appear in the board's manual-verification
  column and be pickable in a subsequent session.

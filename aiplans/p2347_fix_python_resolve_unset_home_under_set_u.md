---
Task: t2347_fix_python_resolve_unset_home_under_set_u.md
Base branch: main
Output branch: main
---

# t2347 — python_resolve.sh (and aitask_path.sh) survive an unset HOME under `set -u`

## Context

`lib/python_resolve.sh:38` expands `$HOME` at source time
(`PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"`), and
`resolve_python()` expands `$HOME` for its venv and wrapper candidates
(lines 62–63). Any `set -euo pipefail` script that sources it at startup aborts
with `HOME: unbound variable` when HOME is unset (cron / systemd / `env -i`),
even when `$AIT_PYTHON` names a working interpreter. t2339 worked around this
only inside the three shell bridges.

**Wider blast radius found during planning:** a sweep of
`env -i PATH=/usr/bin:/bin AIT_PYTHON=/usr/bin/python3 bash <script> --help`
over `.aitask-scripts/aitask_*.sh` shows a second library-level crash of the same
class: `lib/aitask_path.sh:16` (`case ":$PATH:" in *":$HOME/.aitask/bin:"*`),
sourced by ~46 scripts, usually *before* python_resolve.sh. Fixing only
python_resolve.sh would leave most of those scripts crashing one line earlier,
so the task's stated outcome ("`$AIT_PYTHON` and `python3` still resolve") would
not be reached for them. The same 2-line guard is folded in here.

A scratch-copy probe with both fixes applied removed every library-level crash.
Plan review then added two same-class sites to the scope, both verified:
`ait:134-135`, the update check that runs before dispatch (`ait ls --help`
still died there), and `aitask_setup.sh`, which needs an explicit guard so that
an *empty* HOME cannot reach the installer with a root-level or empty
destination (steps 1b/1c). Concern 3, verification strength, is addressed in
Step 4 and Verification.

What remains are scripts' **own** top-level HOME uses
(`aitask_questions_mcp.sh:34`, `aitask_projects.sh:47`,
`aitask_project_resolve.sh:77`, `aitask_plan_externalize.sh:142`,
`aitask_agent_sessions.sh:132`, `aitask_agent_marks.sh:55`). Those depend on
HOME by design (per-user registries, setup) and are **out of scope**. They are
reported in Final Implementation Notes, not fixed.

## Design decision: `${HOME:+…}`, not `${HOME:-}`

The task suggests `${HOME:-}`, but that would turn the PyPy default into
`/.aitask/pypy_venv` and the PATH entry into `/.aitask/bin`. Both are paths at the
filesystem root that the framework never owns. Use `${HOME:+$HOME/…}` instead: an
unset **or empty** HOME yields an empty value, and every empty candidate is
already skipped (`[[ -n "$cand" ... ]]` in `resolve_python`, `[[ -z "$cand" ]] &&
continue` in `resolve_pypy_python`). An explicit `PYPY_VENV_DIR` is still honoured.

## Steps

1. **`.aitask-scripts/lib/python_resolve.sh`**
   - Line 38 → `PYPY_VENV_DIR="${PYPY_VENV_DIR:-${HOME:+$HOME/.aitask/pypy_venv}}"`.
     Add a comment: empty when HOME is unset/empty, so no root-level default
     exists. `aitask_setup.sh` is unaffected because it expands `$HOME` itself at
     its line 8, before it sources this file.
   - `resolve_python()` candidates → `"${HOME:+$HOME/.aitask/venv/bin/python}"`
     and `"${HOME:+$HOME/.aitask/bin/python3}"` (the existing `-n "$cand"` check
     skips them).
   - `resolve_pypy_python()`: change the candidate to
     `"${PYPY_VENV_DIR:+$PYPY_VENV_DIR/bin/python}"`. Otherwise an empty
     PYPY_VENV_DIR yields `/bin/python`, an absolute root path that would be
     probed.
   - Header "Resolution order": note that the HOME-based entries 2–3 are skipped
     when HOME is unset or empty.

1b. **`.aitask-scripts/aitask_setup.sh` — refuse a missing installer
   destination (review concern 1, blocking).** Setup aborts on an *unset* HOME
   only by accident, at line 8 (`VENV_DIR="$HOME/.aitask/venv"`). With `HOME=`
   it continues, today with root-level paths (`/.aitask/venv`,
   `/.aitask/pypy_venv`). After step 1 it would also derive `PYPY_VENV_DIR=""`,
   which makes `/bin/pip`, the `/bin/python` probe and
   `rm -f "$PYPY_VENV_DIR/bin/python"` → `rm -f /bin/python` in the fallback
   cleanup. Insert before line 8 (after `set -euo pipefail` and before any path
   derivation or the python_resolve source):
   ```bash
   if [[ -z "${HOME:-}" ]]; then
       echo "Error: ait setup needs HOME (it installs into \$HOME/.aitask); HOME is unset or empty." >&2
       exit 1
   fi
   ```
   This uses a plain `echo`/`exit` because `die` is not defined yet (it comes
   from terminal_compat.sh, sourced through python_resolve.sh). No test sources
   setup with an empty HOME (checked: the only `HOME=` setter,
   `test_setup_questions_server.sh:148`, uses a scratch HOME). Setup is now the
   only consumer of `PYPY_VENV_DIR` besides `resolve_pypy_python`, so this one
   guard covers every installer path derived from it.

1c. **`ait` — skip the optional update check without HOME (review concern 2,
   blocking).** `check_for_updates()` (`ait:134-135`) builds
   `cache_file="$HOME/.aitask/update_check"` under `set -u`. It runs before
   dispatch for every subcommand outside the skip list (e.g. `ait ls`). Make
   `[[ -n "${HOME:-}" ]] || return 0` the first line of the function: there is
   no per-user cache to rate-limit against, and the check is optional by design.
   `ait:135` is the only `$HOME` in `ait`. Its `aitask_path.sh` source at line 11
   is covered by step 2.

2. **`.aitask-scripts/lib/aitask_path.sh`** — wrap the `case` block in
   `if [[ -n "${HOME:-}" ]]; then … fi`, with a comment: with no HOME there is no
   per-user bin dir to prepend, and prepending `/.aitask/bin` would put a
   root-level dir on PATH. The `_AIT_PATH_LOADED` guard is unchanged.

3. **Bridge comments (no code change)** — `lib/launch_modes_sh.sh`,
   `lib/followup_kinds_sh.sh`, `lib/plan_paths_sh.sh`. Their comment says
   python_resolve.sh "expands $HOME at top level, which aborts a `set -u`
   caller". After step 1 that claim is false. Reword it: the `-n "${HOME:-}"`
   guard is kept because every candidate python_resolve.sh adds beyond
   AIT_PYTHON lives under HOME (its PATH fallback duplicates the bridge's own),
   and python_resolve.sh itself tolerates an unset HOME since t2347. Keep the
   bridge code unchanged: t2339's tests cover it, and changing it would widen this
   task. Apply the same rewording to the matching comment in
   `tests/test_shell_bridge_python_resolve.sh` (lines ~189–191).

4. **New test `tests/test_python_resolve_unset_home.sh`**. It is self-contained,
   uses `tests/lib/asserts.sh`, `scratch_cwd.sh` and `run_tmpdir.sh`, and makes no
   assertions inside `( … )` subshells: each case's output is captured with
   `$(env -i …)` and asserted in the parent. Cases (each child is
   `env -i PATH=<stub-bin>:/usr/bin:/bin … bash -c 'set -euo pipefail; source <lib>; …'`):
   - **source under set -u, no HOME**: rc 0, stderr has no "unbound variable".
   - **AIT_PYTHON wins, no HOME**: `resolve_python` prints `$AIT_PYTHON`.
   - **PATH python3 fallback, no HOME**: with a stub `python3` first on PATH,
     `resolve_python` prints the stub's path.
   - **empty HOME (`HOME=`)**: same two results. `PYPY_VENV_DIR` is empty.
   - **PyPy, no HOME**: `PYPY_VENV_DIR` is empty, and `resolve_pypy_python`
     returns rc 0 with empty output (no pypy stub on PATH).
     `require_ait_python_fast` with `AIT_PYTHON` set prints `AIT_PYTHON`.
   - **HOME set is unchanged**: `PYPY_VENV_DIR` defaults to
     `$HOME/.aitask/pypy_venv`. An explicit `PYPY_VENV_DIR=/x` is kept. The
     scratch-HOME venv candidate still wins over the PATH python3 when it is
     executable.
   - **aitask_path.sh, no HOME**: sourcing under set -u gives rc 0 and leaves
     PATH unchanged, with no `/.aitask/bin` on it. **With a scratch HOME**:
     `$HOME/.aitask/bin` is prepended exactly once, even when sourced twice
     (unset `_AIT_PATH_LOADED` between the two sources to exercise the
     `case` dedupe).
   - **Setup refuses a missing destination**: setup is **never executed** here,
     only sourced with `--source-only` in a fresh child. Plain sourcing runs
     `main`; only `aitask_setup.sh:7211`'s `--source-only` returns before it.
     So even a regressed guard cannot reach the installer. Each child is
     `env -i PATH=/usr/bin:/bin [HOME=…] bash -c 'source "$1" --source-only; printf "PYPY=%s\n" "$PYPY_VENV_DIR"' _ <setup>`:
     - `HOME=` (empty) → rc 1, "needs HOME" message, no `PYPY=` line;
     - HOME unset → rc 1, "needs HOME" message, no "unbound variable";
     - scratch HOME → rc 0, `PYPY=<scratch>/.aitask/pypy_venv`.
   - **Public launcher, no HOME** (`env -i PATH=/usr/bin:/bin
     AIT_PYTHON=<real py> bash <repo>/ait …`): `ait ls --help` and
     `ait crew init --help` each give **rc 0** plus a help marker in stdout (the
     exact marker string is read from each script's usage text at
     implementation, e.g. its `Usage:` line). Stderr has no "unbound variable".
   - **Direct entry points, no HOME**: two scripts are run with `--help`. One
     sources python_resolve.sh directly (e.g. `aitask_add_model.sh` /
     `aitask_change_surface.sh`), and one goes through aitask_path.sh first (e.g.
     `aitask_board_column.sh`). Each is chosen only after confirming its `--help`
     is a pure usage print with no git, network or Python dependency beyond the
     interpreter. Assert **rc 0 + its help marker**, never rc parity (review
     concern 3).
   - Every no-HOME child runs with cwd = an empty scratch dir. The `--help`
     paths must not need a repo, and nothing may touch the real tree's git state.

## Verification

- `bash tests/test_python_resolve_unset_home.sh` → all pass.
- **Pre-fix control, one guard at a time.** The test takes its tree from a
  `PYTHON_RESOLVE_TEST_ROOT` override (default: the repo). It must hold `ait`
  plus `.aitask-scripts`. For each guard, build a scratchpad fixture: a copy of
  the **fixed** tree with **exactly one** changed file reverted to
  `git show HEAD:<file>`. Then assert that guard's specific old failure:
  | reverted file | probe | expected old outcome |
  |---|---|---|
  | `lib/python_resolve.sh` | source under set -u, HOME **unset** | rc≠0, `python_resolve.sh: line 38: HOME: unbound variable` |
  | `lib/python_resolve.sh` | same, `HOME=` | rc 0, `PYPY_VENV_DIR=/.aitask/pypy_venv` (root-level default) |
  | `lib/aitask_path.sh` | source under set -u, HOME **unset** | rc≠0, `aitask_path.sh: line 16: HOME: unbound variable` |
  | `lib/aitask_path.sh` | same, `HOME=` | rc 0, PATH gains `/.aitask/bin` |
  | `ait` (libs fixed) | `ait ls --help`, HOME **unset** | rc≠0, `ait: line 135: HOME: unbound variable`. With the same fixture, `ait crew init --help` gives rc 0 (it is on the skip list), which isolates the update check. No `HOME=` probe here: the old check would run and could reach the network |
  | `aitask_setup.sh` (libs fixed) | `source … --source-only`, `HOME=` | rc 0, no "needs HOME", `PYPY=` **empty**: the hazard the guard prevents |
  | `aitask_setup.sh` (libs fixed) | same, HOME **unset** | rc≠0, `aitask_setup.sh: line 8: HOME: unbound variable` |
  The control runs **only these targeted probes** per fixture, each against its
  own recorded old outcome. It does not run the full test there: the reverted
  libs are shared startup dependencies, so other cases would fail for the same
  reason, and that proves nothing new. The **full new test must pass on the
  fully fixed tree**, and that pass is the gate. The control runs
  once at verification, through a scratchpad driver script, and is not part of
  the committed test. Its exact commands and per-row outcomes go verbatim into
  Final Implementation Notes so the evidence is durable.
- Regression: `bash tests/test_python_resolve.sh`,
  `bash tests/test_python_resolve_pypy.sh`,
  `bash tests/test_shell_bridge_python_resolve.sh`,
  `bash tests/test_aitasks_home.sh`, `bash tests/test_stats_tui_dispatch.sh`,
  `bash tests/test_setup_python_install.sh`.
- Broad sweep, **isolated** (review concern 3): copy `.aitask-scripts` + `ait`
  into a scratchpad dir that is not inside any git repo. Run
  `env -i PATH=/usr/bin:/bin AIT_PYTHON=… bash <script> --help </dev/null`
  under `timeout 10` with cwd in that copy, and exclude scripts that ignore
  `--help` and act (`aitask_lock_diag.sh` runs `git fetch origin`; any others
  the run reveals are added to the exclusion list). The sweep reports only;
  it is never an assertion, since the tested allowlist above is the gate. Expect
  no `lib/python_resolve.sh`, `lib/aitask_path.sh` or `ait:` HOME lines, and
  only the script-own lines listed in Context, with setup now reporting its
  explicit "needs HOME" error instead.
  (The planning-time sweep did run once in the real tree, where
  `aitask_lock_diag.sh` would have attempted a lock-branch fetch. The
  `origin/aitask-locks` reflog shows only push updates, so nothing was
  fetched.)
- `shellcheck .aitask-scripts/lib/python_resolve.sh .aitask-scripts/lib/aitask_path.sh tests/test_python_resolve_unset_home.sh`.

## Step 9 (Post-Implementation)

Current-branch workflow: commit the code (`bug: … (t2347)`), then archive
through the standard Step 9 archival. Nothing is merged.

## Risk

### Code-health risk: low
None identified. (Re-assessed after the review additions. The setup guard and
the update-check skip change behaviour only when HOME is unset or empty, where
both previously crashed or derived root-level paths. Neither touches the
HOME-set path, which the existing setup and resolve tests cover.)

### Goal-achievement risk: low
None identified.

## Post-Review Changes

### Change Request 1 (2026-11-22 18:40)
- **Requested by user:** (1) the direct resolver-caller case used
  `aitask_add_model.sh --help`, which runs `require_jq` before dispatch, so a
  jq-less restricted PATH fails it for an unrelated reason; use
  `aitask_change_surface.sh --help`. (2) the fixture took `resolve_python`'s
  answer as the interpreter, but that can be a wrapper (AIT_PYTHON, or setup's
  `~/.aitask/bin/python3` = `exec "$HOME/.aitask/venv/bin/python"`) that needs
  HOME inside the no-HOME children; reduce it to `sys.executable` in the parent.
- **Changes made:** both, verified. `aitask_add_model.sh:542` does call
  `require_jq` first; `aitask_change_surface.sh --help` prints its usage with
  `AIT_PYTHON=/bin/false` under `env -i PATH=/usr/bin:/bin` (no interpreter or
  external tool needed). `REAL_PY` is now `"$(resolve_python)" -c 'import sys;
  print(sys.executable)'`, the same technique as `tests/test_python_resolve_pypy.sh:20`.
  Result: 49/49 normally and 49/49 with
  `AIT_PYTHON=$HOME/.aitask/bin/python3` (the reproduction).
- **Files affected:** `tests/test_python_resolve_unset_home.sh`

## Final Implementation Notes
- **Actual work done:** As planned, plus the two review-added sites.
  `lib/python_resolve.sh`: the `PYPY_VENV_DIR` default and both HOME-based
  `resolve_python` candidates use `${HOME:+…}`, and the `resolve_pypy_python`
  venv candidate is `${PYPY_VENV_DIR:+…}`, so the venv candidate is empty, never
  `/bin/python`. `lib/aitask_path.sh` prepends nothing without HOME.
  `ait`'s `check_for_updates` returns early without HOME. `aitask_setup.sh`
  refuses an unset or empty HOME before deriving any install path. The
  three-bridge comments and `tests/test_shell_bridge_python_resolve.sh` comment
  are reworded. New test `tests/test_python_resolve_unset_home.sh`: 49 assertions.
- **Deviations from plan:** (1) The direct entry points are
  `aitask_change_surface.sh` (python_resolve.sh directly) and
  `aitask_brainstorm_context.sh` (aitask_path.sh first). `aitask_add_model.sh`
  was replaced after review because it runs `require_jq` before `--help`.
  `aitask_board_column.sh` was rejected because its `--help` is argparse via
  modules importing `yaml`. (2) The isolated sweep found one library-level site
  the plan did not list: `lib/aitasks_home.sh:19`, hit by `aitask_engine.sh`
  and `aitask_testmap.sh`. It was left unchanged on purpose. It owns
  `$AITASKS_HOME`, the engine install/prune/migrate root, so an empty or
  root-level default would send engine writes to `/engine/…`. It also already
  honours an explicit `AITASKS_HOME`. The correct fix is a clear refusal, like
  setup's (see Upstream defects).
- **Issues encountered:** `--help` is not a safe probe for every script:
  `aitask_lock_diag.sh` ignores it and runs `git fetch origin <lock branch>`.
  The planning-time sweep ran once in the real tree. The `origin/aitask-locks`
  reflog shows only push updates, so nothing was fetched. Later sweeps ran in a
  scratch copy outside any git repo, with lock_diag excluded.
- **Key decisions:** use `${HOME:+…}` over the suggested `${HOME:-}`, which
  would have produced root-level `/.aitask/…` defaults. Setup refuses with a
  plain `echo`/`exit` (`die` is not defined yet at that point). The setup test
  only sources setup with `--source-only`, so a regressed guard cannot reach
  `main`.
- **Pre-fix control (verbatim evidence).** The driver,
  `scratchpad/prefix_control.sh`, builds one fixture per guard: the fixed tree
  with exactly one file reverted via `git show HEAD:<file>`. It runs targeted
  probes from an empty cwd under `env -i PATH=/usr/bin:/bin`. Output:
  ```
  OK   old python_resolve, HOME unset                                 rc=1 :: <fx>/pr/.aitask-scripts/lib/python_resolve.sh: line 38: HOME: unbound variable
  OK   old python_resolve, HOME= -> root-level default                rc=0 :: PYPY=/.aitask/pypy_venv
  OK   old aitask_path, HOME unset                                    rc=1 :: <fx>/ap/.aitask-scripts/lib/aitask_path.sh: line 16: HOME: unbound variable
  OK   old aitask_path, HOME= -> PATH gains /.aitask/bin              rc=0 :: PATH=/.aitask/bin:/usr/bin:/bin
  OK   old ait (libs fixed), ait ls --help, HOME unset                rc=1 :: <fx>/ait/ait: line 135: HOME: unbound variable
  OK   old ait (libs fixed), ait crew init --help (skip list)         rc=0 :: Usage: ait crew init --id <crew_id> [options] ...
  OK   old setup (libs fixed), --source-only, HOME= -> EMPTY pypy     rc=0 :: PYPY=[]
  OK   old setup (libs fixed), --source-only, HOME unset              rc=1 :: <fx>/st/.aitask-scripts/aitask_setup.sh: line 8: HOME: unbound variable
  UNEXPECTED=0
  ```
  Probe shape (python_resolve row 1):
  `env -i PATH=/usr/bin:/bin bash -c 'set -euo pipefail; source "$1/python_resolve.sh"' _ <fixture>/.aitask-scripts/lib`.
  The setup rows use `bash -c 'source "$1" --source-only; printf "PYPY=[%s]\n" "$PYPY_VENV_DIR"' _ <fixture>/.aitask-scripts/aitask_setup.sh`.
  The ait rows use `env -i PATH=/usr/bin:/bin AIT_PYTHON=<venv py> bash <fixture>/ait ls --help`.
- **Verification run:** new test 49/49 (also 49/49 with
  `AIT_PYTHON=$HOME/.aitask/bin/python3`). Regression tests pass:
  test_python_resolve, test_python_resolve_pypy,
  test_shell_bridge_python_resolve, test_aitasks_home,
  test_stats_tui_dispatch, test_setup_python_install,
  test_setup_pip_install_guards (147/147) and test_setup_verify_venv_imports
  (30/30). Shellcheck at warning level shows no new findings against HEAD in the
  four changed scripts, and the new test is clean. The isolated sweep leaves only
  script-own HOME lines (`aitask_agent_marks.sh:55`,
  `aitask_agent_sessions.sh:132`, `aitask_plan_externalize.sh:142`,
  `aitask_project_resolve.sh:77`, `aitask_projects.sh:47`,
  `aitask_questions_mcp.sh:34`), plus `lib/aitasks_home.sh:19` ×2 and setup's
  explicit "needs HOME" refusal.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/aitasks_home.sh:19 — AITASKS_HOME default expands $HOME at source time, so aitask_engine.sh / aitask_testmap.sh abort with a raw "HOME: unbound variable" when HOME is unset (an empty HOME instead yields a root-level /.aitasks); it should refuse clearly, as aitask_setup.sh now does, rather than default to empty`

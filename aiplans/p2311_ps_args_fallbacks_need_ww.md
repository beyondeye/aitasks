---
Task: t2311_ps_args_fallbacks_need_ww.md
Base branch: main
Output branch: main
---

# t2311 — `ps` argv/name readers need `-ww`

## Context

t2306 found that procps `ps` honours an inherited `COLUMNS` and cuts `-o args=`
output at that width even when stdout is a pipe. Under pytest, `readline` is
imported and GNU readline exports `COLUMNS=80` into the C-level environment,
so every child `ps` inherits it. Measured here (procps-ng 4.0.7, argv of 220
chars, `COLUMNS=80`): `ps -o args=` → 80 chars, marker past col 80 lost;
`ps -ww -o args=` → 220 chars, marker present.

t2306 fixed only the test fixture. Two production readers make the same call
on their non-procfs (macOS) fallback, and the audit found more readers whose
matched text can sit past column 80. Both procps and BSD ps accept `-ww`
(unlimited width), so the flag is safe on both platforms. Whether BSD ps
honours `COLUMNS` on a pipe is **not measured** (no macOS host) — the fix is
correct either way, and it is stated as hardening for macOS, a measured fix
for Linux.

Audit result. The first grep anchored on a literal `"ps"` and so missed
`lib/agent_keys.py`, which calls `ps` through a variable
(`ps = shutil.which("ps")`). The audit was re-run **by field token**
(`comm=`/`ucomm=`/`args=`/`command=`/`cmd=` in `.py`/`.sh`/`.go` under
`.aitask-scripts/`, `tests/`, `goengines/`, `website/screenshots/`, whatever
names the `ps` binary). The readers below are everything it found. Excluded on
purpose: numeric/short fields (`ppid=`, `lstart=`, `tpgid=`, `stat=`, `pgid=…`).
`tests/test_goengines_export_integrity.sh:448` is excluded because its `ps`
output only decorates a debug log and the assertions match git's own `$*`.
`tests/test_monitor_status_restart.py:207/217` is excluded because it drives a
fake `run_ps` (the real callers in `status_restart.py` already pass `-ww`).
Lines that only mention a field in a docstring or comment are not readers.

## Implementation steps

1. **Regression test first (red proof).** New `tests/test_ps_args_full_width.py`
   (unittest, runs under the Python runner; importing via
   `sys.path.insert(0, REPO/.aitask-scripts)` as `test_aitask_questions.py` /
   `test_monitor_companion_filter.py` do). Shared fixture: spawn
   `sys.executable -c "import time; time.sleep(60)" <'x'*150 + marker>`,
   kill + wait in `tearDown`/`addCleanup`. Force the non-procfs fallback by
   patching the module-global `open` (`patch("<module>.open",
   side_effect=OSError, create=True)` — the module global shadows the builtin
   for that module only), and pin `COLUMNS=80` with
   `patch.dict(os.environ, {"COLUMNS": "80"})` (subprocess children inherit
   `os.environ`).
   - `test_owner_argv_fallback_full_width`: `owner._argv(pid)[-1]` ends with
     the marker (`aitask_questions.owner`).
   - `test_companion_fallback_sees_keyword_past_col_80`: marker =
     `"minimonitor"`; `monitor_core._is_companion_process(pid)` is `True`.
   - A positive control in the same file: with the same env, the raw
     `ps -o args=` (no `-ww`) output is ≤ 80 chars and lacks the marker —
     proves the fixture actually exercises truncation (skip, not fail, if the
     platform's ps does not truncate, so the test is not vacuous on Linux and
     not wrong on BSD).
   - Skip the whole class if `ps` is not on PATH.
   Run it **before** step 2 and confirm both production assertions fail.

   **`agent_keys` long-path test** (extend `tests/test_agent_keys.py`, new class
   `FullWidthCommTest`). On Linux the kernel caps `comm` at 15 chars, and
   procps does not truncate it further (measured: `-o comm=` gave 6 chars with
   or without `-ww`), so a real-`ps` long-path test cannot run here. Instead,
   put stub `ps` and `pgrep` scripts in a temp dir and set
   `PATH=<stubdir>` via `patch.dict(os.environ, …)` so that `shutil.which`
   resolves them:
   - stub `ps` prints `/opt/` + `'p'*120` + `/claude` (one line per pid in its
     `-p` list), cut to `${COLUMNS:-80}` columns **unless** `-ww` is in its
     argv. This emulates a width-limited `ps`. It pins the contract (the
     helpers request full width, and a long path survives their parsing). It
     does not show that BSD ps truncates, which stays **unverified** and is
     described that way in the test docstring.
   - stub `pgrep` prints `4243`.
   - `test_own_command_keeps_long_path`: `ak._own_command(4242)` ends with
     `/claude` and `ak.agent_key_from_command(...)` of it is `"claude"`.
   - `test_child_commands_keep_long_path`: `ak._child_commands(4242)` is a
     one-element list ending with `/claude`.
   - `test_stub_truncates_without_ww` (positive control): running the stub
     with `-o comm= -p 1` and no `-ww` yields ≤ 80 chars, without `/claude`.
     This shows the fixture really truncates, so the two tests above are not
     vacuous.
   - Clear `ak._PANE_KEY_CACHE` / `_PANE_MISS_CACHE` in `setUp`, as the
     existing classes do.
   Run before step 2 and confirm the two helper tests fail.

2. **Production fixes** — add `-ww`:
   - `.aitask-scripts/aitask_questions/owner.py:38` →
     `["ps", "-ww", "-o", "args=", "-p", str(int(pid))]`; extend the comment:
     `-ww` because an inherited `COLUMNS` truncates the line (t2311).
   - `.aitask-scripts/monitor/monitor_core.py:502` →
     `["ps", "-ww", "-p", str(pid), "-o", "args="]`, same one-line comment.
   - `.aitask-scripts/lib/pid_anchor.sh:240` (`get_pid_exe`, `comm=`): on
     macOS `comm` is the full executable path and `aitask_session_hook.sh:209`
     matches it against `*/packages/app-server-daemon/*`, so it can sit past
     col 80 → `ps -ww -o comm= -p "$pid"`. Update the function's header comment.
     (Linux reads `/proc/<pid>/exe` first; not exercisable here.)
   - `.aitask-scripts/lib/agent_keys.py:120` (`_own_command`) and `:163`
     (`_child_commands`) → `[ps, "-ww", "-o", "comm=", "-p", …]`. On a
     platform where `comm` is the full executable path, truncation before the
     trailing `claude`/`codex` would leave native or wrapper-launched agents
     unresolved, because `agent_key_from_command` matches the last path
     component exactly. Add one line to each docstring: `-ww` because an
     inherited `COLUMNS` can cut the path (t2311; BSD behaviour unmeasured).

3. **Test-side readers** — add `-ww` (no behaviour change otherwise):
   - `tests/test_sync_action_runner.py:699` — cleanup matches the temp root
     path in `command=`; Linux-live under pytest → a truncated line skips the
     kill and leaks the process.
   - `tests/test_monitor_harvest_close_live.sh:255` — no procfs path at all;
     sentinel match on `args=`.
   - `tests/test_monitor_status_server_live.py:72`,
     `tests/test_kill_agent_run_guarded.sh:88`,
     `tests/test_kill_agent_pane_smart.sh:104` — non-procfs fallbacks.
   - `tests/test_minimonitor_concern_smoke.py:235` — report-only label, full
     name is more useful (task cited `:195`; the line has moved).

4. **Step 9 (Post-Implementation)** — commit code (`bug: … (t2311)`), then
   archival per the workflow.

## Verification

- `python3 tests/test_ps_args_full_width.py` and `python3 tests/test_agent_keys.py`
  — the new tests are red before step 2 and green after. The positive
  controls are green both times.
- `bash tests/run_all_python_tests.sh --test-dir` scoped to: the new file,
  `tests/test_aitask_questions.py`, `tests/test_monitor_companion_filter.py`,
  `tests/test_sync_action_runner.py` (or run each directly); read the final
  `PYTHON SUITE:` line.
- `bash tests/test_kill_agent_run_guarded.sh`,
  `bash tests/test_kill_agent_pane_smart.sh`,
  `bash tests/test_monitor_harvest_close_live.sh` (skip-or-pass if tmux absent).
- `shellcheck .aitask-scripts/lib/pid_anchor.sh`; source it and run
  `get_pid_exe $$` → prints the bash path.
- Re-run the field-token audit grep (not anchored on a literal `"ps"`). It
  should find no `args=`/`command=`/`comm=` reader without `-ww` outside the
  documented exclusions.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

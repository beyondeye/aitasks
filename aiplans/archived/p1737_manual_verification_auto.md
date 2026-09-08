---
Task: t1737_verify_macos_fixes_on_linux.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
---

# t1737 — Linux verification of t1729's macOS-only fixes (autonomous auto-execution)

## Context

t1729 fixed the macOS-only residue of the Python suite and recorded a
**per-change invariance argument** claiming none of it altered Linux behaviour.
No CI runs the Python suite, so that claim was an argument, not a measurement.
This task is the outstanding proof: run it on Linux and try to *falsify* each
row, not merely re-run the suite green.

Checklist seeded from the task body's own `### Checklist` bullets — t1737 has no
plan file, and its bullets sit under an H3 that
`aitask_verification_parse.sh`'s `## verification|checklist` section regex does
not scan, so neither "seed from plan" nor "convert" applied as written.

## Environment (userland identity is part of the evidence)

| | |
|---|---|
| Distro | Omarchy (`ID_LIKE=arch`) |
| Kernel | `Linux 7.1.11-arch1-1 x86_64 GNU/Linux` |
| `mktemp` | GNU coreutils 9.11 |
| `find` | GNU findutils 4.11.0-modified (`/usr/bin/find`) |
| `sed` | GNU sed 4.10 |
| CPython | 3.14.7 (`~/.aitask/venv`) |
| PyPy | 7.3.21 / Python 3.11.15 |
| Dev tier | pytest 8.4.2 + xdist 3.8.0 installed → **parallel lane active** |
| Box | 24 cpus, 1-min load 3.16 at start |

**Caveat worth recording:** in the agent's *interactive* shell, `find` is a
Claude Code shell function shimming to `bfs 4.1.1`. Scripts launched with
`#!/usr/bin/env bash` resolve `/usr/bin/find` (GNU findutils 4.11.0), which is
what the suite actually uses. All direct probes below used `command find` to
bypass the shim.

**This run covers the lane t1729 never saw.** t1729 was verified on the serial
unittest lane only, because pytest was not installed on that box. Here xdist is
present, so `run_all_python_tests.sh` took the parallel lane
(`-n <auto> --dist loadfile`) plus the serial carve-out — the exact gap item 1
was written to close.

## Execution Log

### Item 1 — full suite verdict
- Item text: run `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -20`, expect `PYTHON SUITE: PASSED`, note the lane.
- Approach: CLI invocation, exit status read via `${PIPESTATUS[0]}` (piping alone discards it).
- Action run: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -30`
- Output (trimmed):
  ```
  1 failed, 7035 passed, 2 skipped in 293.43s (0:04:53)
  FAILED tests/test_desync_state.py::DesyncStateTests::
         test_changelog_warns_for_data_desync_and_ignores_bad_helper_output
  … stale_lock.sh: No such file or directory
  [serial carve-out] 11 passed in 39.33s
  PYTHON SUITE: FAILED (runner=pytest, exit=1)   PIPESTATUS_RC=1
  ```
- Verdict: **fail** → follow-up **t1745**.
- Attribution: **not t1729.** `42ee07791` (t1725_1) added `source stale_lock.sh`
  to `task_utils.sh:31` and updated the shared scaffold
  (`tests/lib/test_scaffold.sh:59`) but not `test_desync_state.py`'s private copy
  list at line 60. Platform-agnostic; fails on macOS identically.

### Item 2 — the six touched modules, individually
- Approach: CLI invocation, `~/.aitask/venv/bin/python -m unittest <module>`.
- Output: `test_agent_keys` 18 OK · `test_tmux_exec` 46 OK ·
  `test_settings_project_config_value_types` 22 OK · `test_prompt_scoping_live`
  4 OK · `test_codebrowser_startup_focus_live` 2 OK ·
  `test_board_startup_focus_live` 1 OK.
- Verdict: **pass**.

### Item 3 — the weakest claim, `/tmp`
- Approach: file inspection + forced-fallback execution + negative control.
- Action run:
  - `stat /tmp` → `directory perms=1777 uid=0 sticky`, tmpfs 32G, 13% used.
  - Python: `os.path.isdir('/tmp')` True, `os.access(W_OK|X_OK)` True,
    `mkdtemp(dir='/tmp')` OK, `gettempdir()` `/tmp`, `TMPDIR` unset.
  - Fallback forced by patching `os.path.isdir` to report `/tmp` absent, with
    `TMPDIR=~/.cache/ait_fallback_probe`, then running the real
    `TestGatewayIntegration`. **Mutation asserted to land** before running
    (`assert not d.startswith("/tmp")`).
- Output (trimmed):
  ```
  fallback base dir: /home/ddt/.cache/ait_fallback_probe/probe_66jqrzq2
  emulated socket path len = 71
  Ran 2 tests … OK
  ```
- **Negative control** (this is what makes the evidence non-vacuous): the same
  forced fallback onto a deliberately deep base pushed `sun_path` to 163 bytes
  and the test **failed**, reproducing the macOS error verbatim on Linux:
  ```
  AssertionError: 1 != 0 : error connecting to …/tmux-1000/ait_t952_1_test
                            (File name too long)
  ```
  So `TestGatewayIntegration` really is exercising an AF_UNIX socket and really
  is length-sensitive — it is not passing for free.
- Verdict: **pass**.
- Nuance recorded, not a defect: the fallback works because the *platform
  default* happens to be short here. It carries no length guarantee of its own;
  t1729 only ever claimed `/tmp` is short and present, and that claim holds.

### Item 4 — the fixture ladder
- Approach: file inspection + instrumented execution (spy on rung 2) + negative control.
- Output (fresh process):
  ```
  returned path is a copy of /usr/bin/sleep : True
  returned path is a symlink                : False
  rung-2 (_compiled_sleeper_path) CALL COUNT: 1
  rung-2 actually produced a compiled binary: /tmp/ait-fake-agent-build-…/sleeper
  ```
- Verdict: **fail** → follow-up **t1744**. This one *is* t1729's own new file.
- Finding: `fake_agent_binary.py:134` iterates
  `(_sleep_binary(), _compiled_sleeper_path())` — an **eagerly built tuple**, so
  rung 2 runs a full `cc` compile on every platform even when rung 1 succeeds.
  The *returned* binary is still rung 1's (byte-identical copy of
  `/usr/bin/sleep`, regular file, no symlink rung), so correctness is unaffected;
  the ladder's lazy-ordering assumption is what is falsified. Memoised in
  `_compiled_sleeper`, so the cost is once per process, not once per call.
- Negative control: forcing rung 1's copy unrunnable does fall through to rung 2
  and return the compiled sleeper — the fallback itself is sound.

### Item 5 — the interpreter predicate
- Approach: instrumented execution — wrapped `_is_interpreter` in both live
  modules and recorded every `pane_current_command` string it was handed.
- Output:
  ```
  codebrowser: 'python' -> True ; 'bash' -> False
  board:       'python' -> True ; 'bash' -> False
  post-quit names starting python/pypy: none
  ```
- Verdict: **pass**. Linux reports lowercase `python`, so the *old* exact
  lowercase tuple would have matched here too — which is precisely why the
  defect was macOS-only (framework CPython reports capital-P `Python`). The
  widened prefix predicate is a strict superset on this platform, and
  `_wait_for_shell` genuinely blocks until `bash`.

### Item 6 — `mktemp_suffixed`
- Approach: CLI invocation + direct behavioural probe of GNU `mktemp`.
- Output: `tests/test_sed_compat.sh` → `42 passed, 0 failed` (rc=0).
  The OLD form, twice:
  ```
  run 1: rc=0 out=/tmp/mktemp_probe_VMrrHd/probe_Lgi7pl.log
  run 2: rc=0 out=/tmp/mktemp_probe_VMrrHd/probe_9NFzdl.log
  literal-XXXXXX files left: 0
  ```
- Verdict: **pass**. GNU `mktemp` substitutes `XXXXXX` even with a trailing
  `.log` suffix and succeeds repeatedly with distinct names. t1729's premise —
  "this is exactly why the bug was invisible on Linux" — is **confirmed by
  measurement**, so the sweep needs no re-examination.

### Item 7 — `find -printf`
- Approach: CLI invocation.
- Output: `tests/test_skill_render_task_workflow.sh` →
  `Tests: 294, Passed: 294, Failed: 0` (rc=0) — the expected count exactly.
- Verdict: **pass**. GNU findutils 4.11.0; the `sed` prefix-strip replacement
  produces identical output.

### Item 8 — the other touched bash tests
- Output: `test_merge_issues.sh` 33/33 · `test_stats_data.sh` 6/6 ·
  `test_brainstorm_init_proposal_file.sh` 3/3 ·
  `test_contribution_review.sh` 64/64. All rc=0.
- Verdict: **pass**.

### Item 9 — leftover sweep
- Action run: `command find /tmp -maxdepth 3 -name '*XXXXXX*'` → 0 hits;
  `TMPDIR` unset so the platform default `/tmp` is the whole surface;
  no stray `ait-fake-agent-build-*`; `git status --porcelain` empty.
- Verdict: **pass**.

## Outcome

**t1729's Linux-invariance argument is confirmed by measurement, with one
qualification.** All six modules it touched pass individually and inside the
suite, on the parallel lane t1729 never exercised. Its two behavioural premises
were probed directly rather than assumed: GNU `mktemp` really does substitute
the old suffixed form (so Linux really never saw that bug), and Linux really
does report lowercase `python` (so the old predicate really did match here).

The two failures are recorded honestly and neither undermines that:

- **t1745** (from item 1) is **not t1729's** — it is t1725_1's fixture copy-list
  omission, platform-agnostic, and would fail on macOS too.
- **t1744** (from item 4) **is t1729's**, and is the one thing this task
  genuinely falsified: an eager tuple turns the fixture ladder into an
  unconditional two-rung evaluation. Cost only, not correctness.

## Cleanup

- `~/.cache/ait_fallback_probe/` — removed.
- `~/.cache/ait_longpath_segment_00/…` (negative-control tree) — removed.
- `/tmp/ait-fake-agent-build-*` — removed by the module's own `atexit` hook;
  verified absent.
- Probe scripts under the session scratchpad (`fallback_probe.py`, `negctl.py`,
  `ladder.py`, `ladder2.py`, `interp.py`, `pf.sh`) — session-scoped, outside the
  repo; no repo file was mutated other than the checklist itself.

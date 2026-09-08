---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [testing, python]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-08 11:31
updated_at: 2026-09-08 17:19
completed_at: 2026-09-08 17:19
---

## Origin

Risk-mitigation ("after") follow-up for t1729, created at Step 8d after implementation landed.

## Risk addressed

From t1729's plan `## Risk` section, goal-achievement risk (level: low):

> Every fix is verified on macOS only, and **no CI runs the Python suite** (the
> four GitHub workflows cover contribution checks, Hugo and release packaging) —
> so the task body's "not visible on Linux CI" is an assumption, and a Linux-side
> regression would not be caught anywhere. The task cannot close this itself (no
> Linux box or container runtime is reachable), so it is handled by **narrowing
> the completion claim** — with the spawned task as the named outstanding proof.

t1729 states its completion claim as macOS-only *precisely because* this task is
the outstanding proof. Until it runs, "t1729 did not change Linux behaviour" is
an argument, not a measurement.

## Goal

On a Linux box, run the touched modules and the full Python suite, and
**falsify the per-change invariance argument** t1729 recorded — do not merely
re-run the suite green and call it done. Each row below is a claim to attack.

### Checklist

- Run the full suite and capture the verdict banner without piping away the exit
  status: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -20`.
  Expected `PYTHON SUITE: PASSED`. Note whether the parallel (pytest+xdist) lane
  or the serial unittest lane ran — t1729 was verified on the **serial** lane
  only, because pytest was not installed.
- Run each touched module individually: `tests.test_agent_keys`,
  `tests.test_prompt_scoping_live`, `tests.test_tmux_exec`,
  `tests.test_codebrowser_startup_focus_live`,
  `tests.test_board_startup_focus_live`,
  `tests.test_settings_project_config_value_types`.
- **The weakest claim — `/tmp`.** `tests/test_tmux_exec.py::_short_socket_tmpdir`
  anchors the tmux socket dir at `/tmp` when `os.path.isdir("/tmp")`, else falls
  back to the platform default. Verify on Linux that `/tmp` is present and
  writable in the environment the suite runs in (a hardened container, a
  read-only `/tmp`, or a `TMPDIR`-only sandbox is the case that breaks it), and
  that the fallback branch still produces a working socket when `/tmp` is absent.
- **The fixture ladder.** `tests/lib/fake_agent_binary.py` should take **rung 1**
  on Linux (copy the system `sleep`), never the compiled or symlink rungs.
  Confirm it: `/bin/sleep` on Linux carries no restricted flag and the copy runs.
  If Linux silently falls to rung 2, the ladder's ordering assumption is wrong.
- **The interpreter predicate.** `_is_interpreter` uses
  `command.lower().startswith(("python", "pypy"))`, claimed to be a strict
  superset of the old exact tuple. On Linux, capture what
  `pane_current_command` actually reports for the codebrowser and board panes
  and confirm it still matches, and that no post-quit shell name starts with
  `python`/`pypy`.
- **`mktemp_suffixed`.** Run `bash tests/test_sed_compat.sh` (42 assertions).
  Then confirm GNU `mktemp` behaviour directly: the OLD form
  `mktemp "$TMPDIR/probe_XXXXXX.log"` should SUBSTITUTE on Linux and succeed
  twice — which is exactly why the bug was invisible there. If it does not,
  the whole "Linux never saw it" premise in t1729 is wrong and the sweep needs
  re-examining.
- **`find -printf`.** `bash tests/test_skill_render_task_workflow.sh` (expect
  294/294). GNU find supports `-printf`, so the `sed` prefix-strip replacement
  must produce identical output there.
- Run the other touched bash tests: `test_merge_issues.sh`, `test_stats_data.sh`,
  `test_brainstorm_init_proposal_file.sh`, `test_contribution_review.sh`.
- Finally: `ls "$TMPDIR"/*XXXXXX* /tmp/*XXXXXX*` must return nothing.

## Reporting

Record the Linux distro, kernel, `mktemp --version`, `find --version`, and the
Python/PyPy versions alongside the results — t1729's argument is about GNU vs
BSD userland, so the userland identity is part of the evidence. If everything
passes, say so explicitly in t1729's terms: "t1729's Linux-invariance argument
is confirmed by measurement." If anything fails, file it against t1729's
changes rather than fixing it here blind.

## Verification Checklist

- [fail] Run the full suite without piping away the exit status (`set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -20`); expect `PYTHON SUITE: PASSED`, and note whether the parallel (pytest+xdist) or serial unittest lane ran — t1729 was verified on the serial lane only. — FAIL 2026-09-08 17:16 follow-up t1745
- [x] Run each touched module individually: `tests.test_agent_keys`, `tests.test_prompt_scoping_live`, `tests.test_tmux_exec`, `tests.test_codebrowser_startup_focus_live`, `tests.test_board_startup_focus_live`, `tests.test_settings_project_config_value_types`. — PASS 2026-09-08 17:16 auto: all six modules green individually under venv CPython 3.14.7 (unittest): test_agent_keys 18, test_tmux_exec 46, test_settings_project_config_value_types 22, test_prompt_scoping_live 4, test_codebrowser_startup_focus_live 2, test_board_startup_focus_live 1.
- [x] The weakest claim — `/tmp`: verify `/tmp` is present and writable in the suite's environment, and that `_short_socket_tmpdir`'s fallback branch still produces a working socket when `/tmp` is absent. — PASS 2026-09-08 17:16 auto: /tmp present, mode 1777, tmpfs 32G, writable (os.access W_OK|X_OK True, mkdtemp ok) -> primary rung taken. Fallback forced by patching os.path.isdir('/tmp')->False with TMPDIR=~/.cache/...: mutation verified to land, TestGatewayIntegration passed, socket path 71B. Negative control at 163B reproduced the macOS error verbatim ('File name too long'), proving the test is length-sensitive and not vacuous.
- [fail] The fixture ladder: confirm `tests/lib/fake_agent_binary.py` takes rung 1 on Linux (copies the system `sleep`, which carries no restricted flag), never the compiled or symlink rungs. — FAIL 2026-09-08 17:16 follow-up t1744
- [x] The interpreter predicate: capture what `pane_current_command` reports for the codebrowser and board panes on Linux, confirm `_is_interpreter`'s `startswith(("python","pypy"))` still matches, and that no post-quit shell name starts with python/pypy. — PASS 2026-09-08 17:16 auto: instrumented _is_interpreter in both live modules. Linux reports lowercase 'python' for the codebrowser AND board panes (_is_interpreter=True); post-quit name is 'bash' (False). No observed name starts with python/pypy post-quit. The old exact lowercase tuple would also have matched 'python' here - confirming the defect was macOS-only.
- [x] `mktemp_suffixed`: run `bash tests/test_sed_compat.sh` (42 assertions), then confirm GNU `mktemp "$TMPDIR/probe_XXXXXX.log"` SUBSTITUTES and succeeds twice — the reason the bug was invisible on Linux. — PASS 2026-09-08 17:16 auto: tests/test_sed_compat.sh 42/42 passed. GNU mktemp 9.11 SUBSTITUTES the old form 'probe_XXXXXX.log' and succeeded twice with distinct names (probe_Lgi7pl.log, probe_9NFzdl.log), zero literal-XXXXXX files. t1729's 'invisible on Linux' premise confirmed by measurement.
- [x] `find -printf`: run `bash tests/test_skill_render_task_workflow.sh` (expect 294/294); GNU find supports `-printf`, so the `sed` prefix-strip replacement must produce identical output. — PASS 2026-09-08 17:16 auto: tests/test_skill_render_task_workflow.sh -> Tests: 294, Passed: 294, Failed: 0 (rc=0). GNU findutils 4.11.0 on this box; the sed prefix-strip replacement produces identical output.
- [x] Run the other touched bash tests: `test_merge_issues.sh`, `test_stats_data.sh`, `test_brainstorm_init_proposal_file.sh`, `test_contribution_review.sh`. — PASS 2026-09-08 17:16 auto: test_merge_issues.sh 33/33, test_stats_data.sh 6/6, test_brainstorm_init_proposal_file.sh 3/3, test_contribution_review.sh 64/64. All rc=0.
- [x] Finally: `ls "$TMPDIR"/*XXXXXX* /tmp/*XXXXXX*` must return nothing. — PASS 2026-09-08 17:16 auto: find /tmp -maxdepth 3 -name '*XXXXXX*' returned 0 hits; TMPDIR unset so platform default is /tmp; no stray ait-fake-agent-build-* dirs; repo tree clean.

---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [testing, python]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-08 11:31
updated_at: 2026-09-08 16:49
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

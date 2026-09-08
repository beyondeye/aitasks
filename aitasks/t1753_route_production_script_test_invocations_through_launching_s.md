---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [bash_scripts, testing, macos, test_infrastructure]
gates: [risk_evaluated]
anchor: 1681
created_at: 2026-09-08 22:29
updated_at: 2026-09-08 22:29
---

## Origin

Deferred from t1746, which fixed the "test drivers run under PATH bash, not the
launching shell" defect for the three test files whose *subject* is shell
semantics. This task covers the larger, separate class t1746 deliberately left
alone.

## Problem

~90 call sites across ~10 test files invoke **production framework scripts** as a
bare `bash "$SCRIPT"`, which resolves through `PATH`:

- `tests/test_codeagent.sh`, `tests/test_codeagent_work_report.sh`, `tests/test_codeagent_trail.sh` — `bash "$CODEAGENT" …`
- `tests/test_revert_analyze.sh` — `bash "$SCRIPT" …`
- `tests/test_t167_integration.sh`, `tests/test_t644_branch_mode_upgrade.sh`, `tests/test_crew_runner_config_delivery.sh` — `bash "$PROJECT_DIR/install.sh" …`
- `tests/test_explain_binary.sh`, `tests/test_session_hook.sh`, `tests/test_update_multiline_yaml.sh`, `tests/test_python_runner_exit_status.sh`, and others

Consequently `/bin/bash tests/<file>.sh` runs the harness under macOS system bash
3.2 while every production script under test runs under whatever `bash` PATH
resolves to (Homebrew 5.x on a typical dev box). A deliberate 3.2 audit of the
framework's own shell scripts therefore does not actually exercise them on 3.2.

## Why t1746 excluded this

It is a genuinely different pattern, and the exclusion was reasoned, not
accidental: those scripts carry `#!/usr/bin/env bash` and resolve through `PATH`
in production, so `PATH` bash is the *faithful production shell* there. Routing
them through the launching interpreter changes what the test represents. That
trade needs a deliberate decision rather than a mechanical sweep, which is why it
was split out.

## Decisions this task must make

1. **Is a 3.2 run meant to audit production scripts at all?** If yes, the routing
   should change; if no, the current behaviour is correct and this task closes as
   "won't fix" with the rationale recorded in
   `aidocs/framework/sed_macos_issues.md`.
2. **Where does the knob live?** t1746 defined
   `SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-${BASH:-bash}}"` inline in three files.
   Across ~10 more files a shared helper in `tests/lib/` becomes attractive — but
   per the repo's own convention a new shared API needs its own contract test.
   Decide between inline duplication and a `tests/lib/` helper + contract test.
3. **What about `TEST_BASH`?** `tests/test_python_resolve.sh:23`,
   `tests/test_python_resolve_pypy.sh:25` and
   `tests/test_setup_pip_install_guards.sh:39` already pin
   `TEST_BASH="$(command -v bash)"`, but for a *different* reason — they munge
   `PATH` for stubs and need a bash path captured beforehand. Decide whether
   these converge on the new knob or stay as they are (t1746 left them alone).

## Reference

`aidocs/framework/sed_macos_issues.md` § "Running a Test Under bash 3.2" records
the convention, the banner requirement, and the current production-script
carve-out that this task revisits.

## Verification

- Whatever is decided, the carve-out paragraph in
  `aidocs/framework/sed_macos_issues.md` must end up consistent with the code.
- If routing changes: each converted file prints its `Shell under test:` banner,
  passes under both `/bin/bash` and PATH bash, and any newly-surfaced 3.2 failure
  is filed as its own task rather than papered over by reverting the routing.
- Note t1752 first: `tests/test_yaml_utils.sh` cannot run under 3.2 until the
  cubic flow-list scan is fixed, so it is out of scope for any 3.2 sweep here.

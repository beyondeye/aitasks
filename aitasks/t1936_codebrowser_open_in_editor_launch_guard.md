---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codebrowser, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1911
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-09 15:38
updated_at: 2026-10-09 16:00
---

## Origin

Spawned from t1929 during Step 8b review.

## Upstream defect

- .aitask-scripts/codebrowser/codebrowser_app.py:1079 — action_open_in_editor runs subprocess.call([editor, path]) inside `with self.suspend():` with no OSError guard (a missing $EDITOR binary raises, which ends the codebrowser and leaves the terminal suspended); an $EDITOR with arguments (e.g. "code -w") is also treated as one executable name; and as an exclusive default-group worker it cancels in-flight explain-annotation loading

## Diagnostic context

t1929 moved codebrowser's explain / create / history-QA run-in-terminal launches onto one shared worker, `CodeBrowserApp.run_launch_command` (`@work(exclusive=True, group="launch")`). That worker catches `OSError` INSIDE `with self.suspend():`, because Textual 8.2.7's `App.suspend` resumes the driver after its yield with no `finally`. It also contains `SuspendNotSupported` and uses its own worker group so it does not cancel `_load_explain_data` / `_refresh_explain_data`, which are exclusive in the default group. `action_open_in_editor` is the one remaining suspend-launch in the file and has none of these guards:
- it is `@work(exclusive=True)` in the default group, so opening the editor cancels in-flight annotation loading for the current file;
- `subprocess.call([editor, str(filepath)])` raises `FileNotFoundError` for an unset/mistyped `$EDITOR`; the exception escapes the `with` block (terminal stays suspended) and then the worker (exit_on_error ends the codebrowser);
- `$EDITOR` values carrying arguments (`code -w`, `emacsclient -t`) are passed as a single argv[0] and fail the same way.

## Suggested fix

Give the worker its own group, split `$EDITOR` with `shlex.split`, and catch `OSError` inside the suspend block / `SuspendNotSupported` around it, notifying after resume. Reuse the real-`App.suspend` fake-driver ordering test pattern from `tests/test_codebrowser_dialog_run_dispatch.py::LaunchWorkerLiveTests`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T13:00:24Z status=pass attempt=1 type=human

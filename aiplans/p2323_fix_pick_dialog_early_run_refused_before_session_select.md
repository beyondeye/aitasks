---
Task: t2323_fix_pick_dialog_early_run_refused_before_session_select.md
Base branch: main
Output branch: main
---

## Goal and findings

Accept Run pressed immediately after the pick dialog opens and return the
correct TmuxLaunchConfig once its session and window widgets are initialized.
The shared AgentCommandScreen builds these widgets dynamically in on_mount;
_build_tmux_config currently treats the initial Select.NULL as a user error.
Using _selected_session alone would not protect the window selection, and
could hide a deliberately cleared session after initialization.

Work directly on the current main branch under the fast profile. Existing
unrelated checkout changes are outside this task. Scope is local and low
complexity; no child tasks or cross-repository work are needed.

## Implementation

1. [ ] In .aitask-scripts/lib/agent_command_screen.py, track initial tmux-tab
   readiness and a pending Run request on each dialog instance. Mark readiness
   after the initial refresh, following the existing deferred visibility/window
   callbacks. Have run_tmux queue requests while initialization is incomplete;
   the readiness callback clears the pending flag before dispatching exactly
   one run_tmux. Do not replace normal validation with cached session values.
   Preserve terminal-tab launches and the existing opening-key debounce.
2. [ ] Add tests/test_agent_command_dialog_early_run.py using the real Textual
   headless App/screen lifecycle with mocked tmux discovery and captured dialog
   results, following the existing dialog and opening-debounce test patterns.
   Trigger Run at the first mount/refresh boundary without waiting for the
   selector to settle. Exercise actual r-key dispatch as well as an explicitly
   queued early request so event timing cannot make the regression vacuous.
   Assert the intended session and window in the returned config and no
   erroneous notification. Cover repeated early requests (one result), the
   configured create-new-session path, an explicit existing split window,
   cancellation before deferred launch, and normal post-initialization session
   changes/clears. Keep all tests isolated from real tmux launches and restore
   per-project selection memory.
3. [ ] Run the new regression against the old implementation to confirm it
   detects the failure, then against the fix. Run adjacent session-default,
   empty-prompt, narrow-dialog and opening-debounce tests with the framework
   Python interpreter. Inspect the scoped diff and resolve any failures.
4. [ ] Complete task-workflow Steps 8 and 9: present the verified change for
   review, record required gates, consolidate final implementation notes,
   commit only this task's code paths with a bug: message ending (t2323),
   handle follow-up decisions, and archive/push the task and plan when eligible.

## Verification

- The early request produces one TmuxLaunchConfig for the configured session
  and correct new/existing window, without "Please select a session".
- Early Run while creating a session reads its default name and creates a new
  window; existing-window defaults retain their split target.
- Cancellation cannot dispatch a pending launch after the screen closes.
- After initialization, changing or clearing the session retains normal
  selection/validation behavior. Terminal launches and opening-key debounce
  remain covered by the adjacent suites.
- Use the resolved framework Python with pytest on the new file and
  tests/test_agent_command_dialog_default_session.py,
  tests/test_agent_command_dialog_empty_prompt.py,
  tests/test_agent_command_dialog_narrow.py and
  tests/test_agent_command_open_debounce.py.

## Risk

### Code-health risk: low
None identified. The change is limited to the initial Run lifecycle of one
shared dialog; normal selection validation stays authoritative and the tests
exercise cancellation and repeated requests.

### Goal-achievement risk: low
None identified. Waiting for both selectors addresses the initialization
window without guessing a session or window. Deterministic lifecycle tests
plus actual key dispatch cover the reported trigger.

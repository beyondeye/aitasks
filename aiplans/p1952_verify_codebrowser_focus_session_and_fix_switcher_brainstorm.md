---
Task: t1952_verify_codebrowser_focus_session_and_fix_switcher_brainstorm.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1952 — Owned session for the board's codebrowser focus; fix the switcher brainstorm test

## Context

t1951 moved the board's brainstorm focus and the TUI switcher onto the
socket-verified, ownership-checked session helpers in
`.aitask-scripts/lib/agent_launch_utils.py`. One raw consumer remains:
`_current_tmux_session()` in `.aitask-scripts/board/aitask_board.py:1174`. It runs
a raw ambient `tmux display-message -p '#S'`, which is not socket-verified, and
its result feeds `TaskDetailScreen`'s `FileReferencesField._launch_codebrowser`
→ `launch_or_focus_codebrowser(session, entry)`. That call goes through the
gateway. It sets `AITASK_CODEBROWSER_FOCUS`, then selects or creates
(`./ait codebrowser --focus …`) a `codebrowser` window in that session. So an
unverified name can point it at another server's or another project's session.
Every project's session has a `codebrowser` window, so ownership matters.

Separately, `tests/test_tui_switcher_brainstorm_session.sh` assigns
`ov._session = "s2"`. `_session` has been a read-only property derived from
`_selected_key` since t1099, so the test crashes with `AttributeError`.

**Decision:** the codebrowser focus uses `owned_lookup_session(Path.cwd())`.
This returns the caller's own session when it is socket-verified and owned by
this project. Otherwise it returns the configured `default_session`, again only
when that session is owned. This matches the pick, resume and brainstorm focus
from t1946/t1951. When the result is None, warn the user rather than guess.

## Changes

1. `.aitask-scripts/board/aitask_board.py`
   - Delete `_current_tmux_session()` (the raw `subprocess.run(["tmux", …])`).
   - Add a board helper in its place:
     ```python
     def _owned_tmux_session() -> str | None:
         """This project's tmux session for the codebrowser focus, or None.

         Socket-verified and ownership-checked (t1952): every project's session
         has a `codebrowser` window, so an ambient `#S` could focus or spawn
         one in another project's session."""
         return owned_lookup_session(Path.cwd())
     ```
   - Import `owned_lookup_session` from `agent_launch_utils`, in the existing
     import line.
   - In `make_task_detail_screen`, bind
     `tmux_session_provider=lambda: _owned_tmux_session()`. It is resolved at
     call time, so test stubs still apply.
   - `subprocess` remains imported, because other callers use it.
2. `.aitask-scripts/board/board_detail_screen.py`, `_launch_codebrowser`: when
   there is no session, show the warning "No tmux session of this project to
   focus the codebrowser in". The old text, "Codebrowser focus requires tmux",
   is wrong now: None also means "in tmux, but not in an owned session".
3. `tests/test_no_raw_tmux.sh`: remove the
   `.aitask-scripts/board/aitask_board.py` allowlist entry. Its only raw call is
   gone. Confirm first with a grep that no other raw-tmux hit remains in the file.
4. `tests/test_board_detail_screen.py`:
   - `PROVIDERS["tmux_session_provider"] = "_owned_tmux_session"`.
   - Update the `"requires tmux"` assertion to match the new warning text.
   - New test: patch `ab.owned_lookup_session` and assert that
     `ab._owned_tmux_session()` returns its value and calls it with
     `Path.cwd()`.
   - **End-to-end codebrowser regression (review concern, addressed inline).**
     The tests above cover pieces in isolation: the helper test mocks the
     resolver, and the launch test injects an arbitrary session and mocks
     `launch_or_focus_codebrowser`. Nothing ties the ownership decision to
     what the codebrowser launch actually does. Add a
     `CodebrowserOwnedSessionTests` class. It runs the **real** resolver
     (`owned_lookup_session` → `current_tmux_session` → `_sessions_owned_by` →
     `_collect_live_roots`) and the **real** `launch_or_focus_codebrowser`.
     Only the gateway answers are controlled:
     - Fixture: a temp dir holding `proj_a/` and `proj_b/`, each with
       `aitasks/metadata/project_config.yaml`, so the registration stamp
       resolves through `_registered_root`. The test chdirs into `proj_a` and
       restores the cwd in cleanup. Patch the env with `TMUX=/sock/ait,1,0` and
       `TMUX_PANE=%3`. Patch `alu.load_tmux_defaults` →
       `{"default_session": "configured"}`.
     - Patch `alu._TMUX.run` with a recorder that answers as follows:
       - `display-message` → `(0, "/sock/ait\tprojB\n")`: a verified caller
         sitting in project B's session.
       - `list-sessions` → `projB\t<proj_b>` plus `configured\t<root>`, where
         `<root>` is set per test.
       - `list-windows` → `(0, "codebrowser\n")`.
       - any other command → `(0, "")`.
     - The provider comes from the real factory:
       `ab.make_task_detail_screen(task)._tmux_session_provider`. It is passed
       to a `FileReferencesField`, `app` is patched as in the existing launch
       test, and `_launch_codebrowser("a.py")` is called.
     - **Foreign caller + foreign fallback** (`configured` stamped `proj_b`):
       the user gets the "No tmux session of this project" warning, and the
       recorder holds no `set-environment`, `select-window` or `new-window`.
     - **Owned fallback** (`configured` stamped `proj_a`): `set-environment`
       targets `=configured` with `AITASK_CODEBROWSER_FOCUS a.py`,
       `select-window` targets `=configured:codebrowser`, and no mutating
       command names `projB`.
5. `tests/test_tui_switcher_brainstorm_session.sh`: remove the
   `ov._session = "s2"` assignment. Set `_all_sessions` first, then
   `ov._selected_key = ov._all_sessions[1].key` (the overlay's source of
   truth). Assert that `ov._session == "s2"` before `_populate_list_for("s2")`
   (print a line and check it in bash).
6. `aidocs/framework/tui_conventions.md:654`: rename the injected helper
   `_current_tmux_session` → `_owned_tmux_session`.

## Verification

- `bash tests/test_tui_switcher_brainstorm_session.sh` should pass. It crashed
  before this change.
- `bash tests/test_no_raw_tmux.sh` should pass with the board entry removed.
- `python -m pytest tests/test_board_detail_screen.py` (or the runner with
  `--test-dir`) should pass, including the new helper test, the end-to-end
  codebrowser regression and the mutant-checked factory binding.
- Negative control for the regression: temporarily bind the provider back to
  an ambient-`#S`-style answer (`lambda: "projB"`) in an isolated scratch copy,
  and confirm the foreign-case test goes red. Never use stash or restore for
  this.
- `bash tests/run_all_python_tests.sh` covers board-related regressions. Read
  the last line.
- `shellcheck` on the edited `.sh` tests.

Step 9 (Post-Implementation) covers archival.

## Risk

### Code-health risk: low
- Off-tmux behaviour change: a board run outside tmux used to get a "requires tmux" warning. If the project's `default_session` exists and is owned, the board now focuses or creates the codebrowser window there instead. This is consistent with the pick and brainstorm focus, and the window is visible on attach. · severity: low · → mitigation: None (accepted, matches t1951 semantics)

### Goal-achievement risk: low
None identified.

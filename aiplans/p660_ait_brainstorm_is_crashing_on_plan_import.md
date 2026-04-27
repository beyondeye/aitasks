---
Task: t660_ait_brainstorm_is_crashing_on_plan_import.md
Base branch: main
plan_verified: []
---

# t660 — Brainstorm TUI silently quits on plan import

## Context

`ait brainstorm 635` opens the InitSessionModal (no session yet). The user picks "Import Proposal…", then selects `aidocs/gates/aitask-gate-framework.md` in the file picker. The TUI shows an "initializing" toast for ~0.1s, then **quits silently** — no Python traceback. The user suspects the recent "tolerant YAML load" change in `brainstorm_session.py` (commit 17438565, t653_2).

After tracing the code path I'm fairly sure the YAML-parsing change is **not** the cause: parsing only fires from `apply_initializer_output`, which runs after the initializer agent finishes. The crash happens far earlier than that. The actual exit path is one of two `self.exit()` calls in `_run_init_with_proposal` at `.aitask-scripts/brainstorm/brainstorm_app.py:3221-3257` — and **either path notifies briefly and then unconditionally exits the app**, which matches the user's report.

The two exit conditions are:
1. The `ait brainstorm init …` subprocess exits non-zero (line 3232-3238).
2. The subprocess succeeds but stderr contains `RUNNER_START_FAILED:` (line 3246-3255). This fires when `start_runner` (`agentcrew_runner_control.py:70-114`) sees the runner child process exit within `RUNNER_LAUNCH_VERIFY_SECONDS = 1.5`.

In both cases the user only sees a `notify(...)` toast for a fraction of a second before `self.call_from_thread(self.exit)` tears the app down. There is no persistent error UI, so the actual error message is unreadable in practice — that's the real bug, regardless of which sub-cause is firing.

## Phase 1 — Diagnostic (must run before Phase 2)

We need ground truth on **which** of the two exit paths is firing, and what the stderr says. The user runs the subprocess directly so we see the captured output. This also simulates exactly what the TUI shells out to.

```bash
./ait brainstorm init 635 --proposal-file aidocs/gates/aitask-gate-framework.md
echo "EXIT=$?"
# If a crew was created, inspect the runner launch log:
test -f .aitask-crews/crew-brainstorm-635/_runner_launch.log \
  && cat .aitask-crews/crew-brainstorm-635/_runner_launch.log
# Cleanup before retesting:
./ait brainstorm delete 635
```

The combined stdout/stderr decides Phase 2 path:
- **Path A — non-zero exit, error from `aitask_brainstorm_init.sh`**: a missing dep, codeagent_config issue, crew_init failure, etc. Fix is the underlying cause.
- **Path B — exit 0 with `RUNNER_START_FAILED:brainstorm-635` on stderr**: runner crashed within 1.5s. `_runner_launch.log` will hold the runner's traceback. Fix is whatever the runner is choking on (likely an `ait crew runner` import or claude/codex agent-string resolution, **not** YAML parsing).
- **Path C — exit 0, no `RUNNER_START_FAILED`**: my hypothesis is wrong; the exit comes from somewhere else (likely an unhandled exception in `_start_initializer_wait` or `_load_existing_session`). I'd then re-trace with `TEXTUAL_LOG=/tmp/textual.log ait brainstorm 635`.

## Phase 2 — UX fix (always do this, regardless of Phase 1 outcome)

The current pattern in `_run_init_with_proposal` is wrong for any failure: a fading toast plus immediate `self.exit()` makes the failure unreadable. Replace both exit paths with **a persistent error overlay that does not close the app**, so the user can copy the message and choose how to proceed.

### Files to change

**`.aitask-scripts/brainstorm/brainstorm_app.py`**

1. Add a new `InitFailureModal` (a `ModalScreen`) near `InitSessionModal` (~line 204). Layout:
   - Title: "Brainstorm init failed"
   - A `TextArea(read_only=True)` (or `Static` in a `VerticalScroll`) showing the captured stderr/stdout — large enough to scroll, content is selectable.
   - Footer buttons: `Retry` (re-opens InitSessionModal), `Open log` (only if a `_runner_launch.log` exists — copies the path to the title; we can't really `xdg-open` from a TUI), `Quit`.
   - `BINDINGS = [Binding("escape", "quit", show=False)]`.

2. Refactor `_run_init_with_proposal` (line 3221-3257):
   - On `result.returncode != 0`: build `error_text = f"Subprocess exit {result.returncode}\n\nSTDERR:\n{result.stderr}\n\nSTDOUT:\n{result.stdout}"` and `self.call_from_thread(self._show_init_failure, error_text)`. Do **not** call `self.exit()`.
   - On `RUNNER_START_FAILED:` in stderr: build `error_text` identically, plus append the contents of `<crew_worktree>/_runner_launch.log` if it exists (use `crew_worktree(self.task_num)` to find the path). Call `self._show_init_failure(error_text)`. Do **not** call `self.exit()`.

3. Add `_show_init_failure(self, error_text: str) -> None` on `BrainstormApp` that pushes the `InitFailureModal` with a callback `_on_init_failure_result(self, result)`. On `Retry`, push `InitSessionModal` again (mirroring the `on_mount` no-session branch). On `Quit`, call `self.exit()`. On `Open log`/Escape, leave the user in a quiet state — they can re-press `q` to quit Textual.

4. Make sure the failure path also tears down whatever partial state was created. Specifically, if a crew worktree was just created but the runner failed, we don't want to leave the user with a half-bad state. Two options — pick the simpler one:
   - **Preferred:** leave the partial crew on disk and tell the user to `ait brainstorm delete 635` from the failure modal text. Implementation cost is one extra string in the modal.
   - Alternative: in the Path B branch only, run `ait brainstorm delete <N> --yes` from a worker thread before showing the modal. More moving parts; skip unless the user asks for it.

### Why a modal and not a banner

The existing `initializer_apply_banner` pattern (a 1-row banner) is appropriate for **post-apply** errors where the user is already inside a working session. For init failure the user doesn't have a session yet — there's nothing to overlay a banner on top of, and a 1-row banner truncates the kind of multi-line stderr we get from a runner crash. A modal lets us show a scrollable text area with the full output.

## Phase 3 — Tolerant YAML hardening (only if Phase 1 reveals the apply path is involved)

I'm leaving this section as a **deferred** branch. If the user pastes the diagnostic output and it turns out the actual failure is on the `apply_initializer_output` path (because the agent did finish, output `initializer_bootstrap_output.md` with em-dashes / colons / `#` in `NODE_YAML`, and `_tolerant_yaml_load` re-raised), we then expand the regex coverage in `_PROBLEM_CHARS_RE` (`brainstorm_session.py:287`) and/or move from "quote only flagged values" to "quote everything that doesn't already look like a flow collection or a number/bool". I'd write that as a child task with its own plan; don't pre-commit to it before we have evidence.

## Verification

For Phase 2:
1. Re-run `ait brainstorm 635`, pick "Import Proposal…", pick the gates file. Expect: TUI stays alive, an `InitFailureModal` opens with the exact stderr that would have been swallowed.
2. Force a synthetic failure to confirm the path independently of t635 state — e.g. corrupt `aitasks/metadata/codeagent_config.json` to omit `brainstorm-initializer`, then retry. Expect: same modal, with the missing-key error visible.
3. Existing tests still pass: `bash tests/test_brainstorm_init_proposal_file.sh`, `bash tests/test_apply_initializer_output.sh`, `bash tests/test_apply_initializer_tolerant.sh`.
4. Add one new test (optional, scope dependent): a Python test asserting that `_run_init_with_proposal` calls `_show_init_failure` (not `exit`) when stderr contains `RUNNER_START_FAILED:`. Mock subprocess.

## Files touched (Phase 2)
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `InitFailureModal`, rewrite both failure branches in `_run_init_with_proposal`, add `_show_init_failure` + `_on_init_failure_result`.

## Step 9 reminder
After implementation: `git diff` review with the user, code commit (issue_type=bug, message `bug: Show persistent error modal on brainstorm init/runner failure (t660)`), plan commit, archive via `./.aitask-scripts/aitask_archive.sh 660`.

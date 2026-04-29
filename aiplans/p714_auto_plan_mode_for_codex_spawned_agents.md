---
Task: t714_auto_plan_mode_for_codex_spawned_agents.md
Worktree: .
Branch: main
Base branch: main
---

# Plan: Auto Plan Mode For Codex Spawned Agents

## Summary
- Codex CLI does not treat `/plan ...` as a startup directive when it is passed as the initial prompt argument.
- Use a PTY-based helper for Codex interactive skill operations so the wrapper starts Codex normally, then sends `/plan <skill prompt>` as a real terminal input line.
- Apply the helper to `pick`, `explain`, `qa`, and `explore`; keep `raw` and `batch-review` as direct passthrough.

## Implementation
- Add `.aitask-scripts/aitask_codex_plan_invoke.py`.
- Update `.aitask-scripts/aitask_codeagent.sh` Codex command construction for interactive skill operations to call the helper.
- Extend `tests/test_codeagent.sh` with Codex dry-run assertions for helper use and passthrough preservation.
- Update codeagent/known-issues docs to describe the new wrapper behavior.

## Verification
- `python3 -m py_compile .aitask-scripts/aitask_codex_plan_invoke.py`
- `bash -n .aitask-scripts/aitask_codeagent.sh`
- `bash tests/test_codeagent.sh`

## Final Implementation Notes
- **Actual work done:** Added `.aitask-scripts/aitask_codex_plan_invoke.py`, a PTY helper that launches Codex, sends `/plan <skill prompt>` as an interactive input line, and then hands the interactive session back to the user. Updated `aitask_codeagent.sh` so Codex `pick`, `explain`, `qa`, and `explore` use that helper, while `raw` and `batch-review` remain direct passthrough. Updated focused tests and docs.
- **Deviations from plan:** The helper now keeps `/plan` and the skill prompt on the same line based on manual smoke-test feedback. Instead of delaying Codex startup for tmux companion splits, it propagates terminal resize events into the spawned Codex PTY and syncs the child size immediately before prompt injection. A dummy PTY command was used to verify prompt injection without relying on a live Codex run.
- **Issues encountered:** Passing `/plan ...` as the initial Codex prompt was confirmed not to switch modes; PTY injection is required. `pexpect.interact()` is used without text log hooks because logging to `sys.stdout` can trigger byte/string mismatches on current Python/pexpect combinations.
- **Key decisions:** Kept the behavior centralized in `aitask_codeagent.sh` so board, monitor, codebrowser, and switcher launch paths inherit it through existing dry-run/invoke resolution. The helper reports a clear error when `pexpect` is unavailable or no interactive TTY is present.
- **Upstream defects identified:** None

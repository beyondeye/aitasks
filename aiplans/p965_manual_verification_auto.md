---
Task: t965_manual_verification_revisit_brainstorm_status_distrust_follo.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Auto-Verification: t965 — Brainstorm Error/Aborted handling (verifies t672)

Autonomous auto-verification of the 5-item checklist. Every item is fully
determined by the implemented code paths in
`.aitask-scripts/brainstorm/brainstorm_app.py` and
`.aitask-scripts/brainstorm/brainstorm_session.py`, so each was verified by
source inspection rather than a live TUI run (no runtime/timing ambiguity to
resolve). All five reached a **pass** verdict.

## Execution Log

### Item 1
- Item text: Launch a brainstorm session whose initializer agent fails (status Error/Aborted); confirm the polling indicator (#initializer_polling_indicator) stops and is no longer flashing.
- Approach: source inspection (`_poll_initializer` Error/Aborted branch).
- Action run: `grep` / Read of `brainstorm_app.py:8543-8567` and the poll guard at `:8509`.
- Output (trimmed): Error/Aborted branch sets `self._initializer_done = True` (8550) — the function's first line `if self._initializer_done ...: return` (8509) makes any in-flight tick a no-op, so the `.flash()` at 8512 never fires again. It stops the 2 s timer (8551-8552) and calls `self.query_one("#initializer_polling_indicator", PollingIndicator).stop()` in try/except (8553-8558), matching the Completed branch.
- Verdict: pass

### Item 2
- Item text: Confirm the error toast no longer contains "Watching for output" and still shows the "press ctrl+r or run `ait brainstorm apply-initializer <N>`" retry hint.
- Approach: source inspection + negative grep.
- Action run: Read of the `self.notify(...)` at `brainstorm_app.py:8559-8564`; `grep -n "Watching for output" brainstorm_app.py`.
- Output (trimmed): Toast = `"Initializer agent {status}. Press ctrl+r or run \`ait brainstorm apply-initializer {self.task_num}\` to retry."` — retry hint present, the now-false "Watching for output;" clause removed. Negative grep returned NO MATCH anywhere in the file.
- Verdict: pass

### Item 3
- Item text: Confirm ctrl+r still forces an apply retry (action_retry_initializer_apply) after the agent has failed.
- Approach: source inspection (binding → action → apply chain).
- Action run: `grep -n "ctrl+r\|retry_initializer_apply"` + Read of `brainstorm_app.py:3513, 4810-4812`.
- Output (trimmed): `Binding("ctrl+r", "retry_initializer_apply", ...)` (3513) → `action_retry_initializer_apply` (4810) → `self._try_apply_initializer_if_needed(force=True)` (4812). Untouched by t672. It calls the apply path directly (not via `_poll_initializer`), so the `_initializer_done` terminal guard does not block it — ctrl+r still forces a retry after Error/Aborted.
- Verdict: pass

### Item 4
- Item text: Confirm that when the agent wrote a complete delimited output (all four NODE_YAML/PROPOSAL delimiters) before failing, the one-shot apply on the Error/Aborted branch still imports the proposal into n000_init.
- Approach: source inspection (Error branch → apply gate → import).
- Action run: Read of `brainstorm_app.py:8566` (`_try_apply_initializer_if_needed()`), `:4762-4792`; `grep` of `brainstorm_session.py` for `n000_needs_apply` / `apply_initializer_output`.
- Output (trimmed): The Error branch's final line (8566) is the one-shot `self._try_apply_initializer_if_needed()` (force=False). That gates on `n000_needs_apply` (`brainstorm_session.py:408`, the four-delimiter check NODE_YAML_START/END + PROPOSAL_START/END) and, when satisfied, calls `apply_initializer_output` (`:469`) which rewrites `br_nodes/n000_init.yaml` and `br_proposals/n000_init.md`. A complete-before-failure output therefore still imports into n000_init.
- Verdict: pass

### Item 5
- Item text: Confirm no background timer keeps re-polling after Error/Aborted (no 30s slow-watcher) — e.g. the session does not silently re-apply output minutes later.
- Approach: negative grep + source inspection.
- Action run: `grep -n "set_interval(30, self._poll_initializer)" brainstorm_app.py`; review of the Error branch and the remaining 30 s timer.
- Output (trimmed): Negative grep returned NO MATCH — the slow-watcher reinstall is gone. The Error branch stops `_initializer_timer` and sets `_initializer_done = True` with no `set_interval` re-arm. The only surviving 30 s timer (`:4754` `_status_refresh_timer = self.set_interval(30, self._refresh_status_tab)`) refreshes the status tab and never re-polls or re-applies the initializer, so no silent late re-apply occurs.
- Verdict: pass

## Cleanup

None — verification was pure read-only source inspection (grep / Read). No
scratch files, tmux sessions, or fabricated test data were created; no
user-owned files other than the t965 checklist itself were mutated.

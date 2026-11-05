---
Task: t2211_4_sitrep_tui_guarded_request_delivery.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_4 — Guarded request delivery into the sitrep agent

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. The task file is
the binding spec: three phases, the result vocabulary and test cases (a)-(i), from two
plan-review rounds.

## Steps

1. **Gate + rebase check.** t2211_3 and t2037_2 landed. Re-read `monitor_core.py`
   (`kill_agent_run_guarded`, `RunIdentity`, `RUN_IDENTITY_FORMAT`, `capture_raw_tail`,
   `query_pane_mode`, `find_sitrep_roles`), `helper_panes.py`, `review_loop.py`
   (`shadow_state`, constants), and `minimonitor_app.py` (`_fire_shadow_recheck`,
   `_submit_shadow_prompt`). `git diff HEAD -- <files>` must be empty.
2. **Measurement spike (before the design is final).**
   - In an isolated tmux server with a real Claude Code session (and codex/opencode if
     installed), confirm that `set-buffer` + `paste-buffer -d` of a short single line lands
     as typed composer text, i.e. `shadow_state` reads BUSY with the text visible, and that
     Enter submits it.
   - Record the result per agent in this plan.
   - If any agent turns the paste into a `[Pasted text …]` placeholder or otherwise not
     typed text: **stop and report to the user**. Never inline the text into the `if-shell`
     command.
3. **Pure layer** in a new `monitor/agent_request_delivery.py`:
   - `AGENT_REQUESTS` building + validation (one line, no control chars);
   - `readiness_verdict(tail1, tail2, agent, mode)` → `ready | not_ready:<reason>`, using
     `review_loop.shadow_state` only;
   - `build_dispatch_condition(identity)` = `run_identity_condition(...)` +
     `#{==:#{pane_in_mode},0}`;
   - `dispatch_ack_state(rc, out, pane_id, server_pid, nonce)`;
   - the result vocabulary constants.

   Keep `AGENT_REQUESTS` importable from `sitrep_tui_app.py`. Either define it there and
   import it here, or the reverse; pick one and say which.
4. **`TmuxMonitor.dispatch_text_guarded(identity, text, nonce)` and
   `dispatch_key_guarded(identity, key, nonce)`** in `monitor_core.py`:
   - set-buffer argv-only;
   - the `if-shell -F` branches with controlled tokens only;
   - the ack read-back, then unset the ack, and `delete-buffer` on skip/unknown;
   - on skip, a reason read (`#{pane_in_mode}` + identity).

   Gateway only (`tmux_run`). Add `@aitask_dispatch_ack` to the `tmux_gateway.md`
   inventory.
5. **Orchestrator** `async deliver_request(monitor, root, text, *, pause=None)`:
   1. resolve the roles;
   2. read the identity (frozen → refused);
   3. readiness (two tails, mode);
   4. dispatch text (skipped → `skipped` / in_mode reason; unknown → `unknown`);
   5. re-capture: the text is in the composer and there is no dialog;
   6. the mode gate as the last await, then dispatch Enter;
   7. verify by re-capture, with a bounded retry where each retry passes the mode gate.

   It returns the result string. The pause seam lets the live tests interleave copy-mode or
   respawn.
6. **TUI wiring.**
   - Request keys on details/selection: `t`, `?q` (an input dialog), `w` (theme from the
     item context), `T` (trail refresh on trail-watch items), `p` (pick advice, global).
   - `check_action` requires a matching kind/state and a resolved agent. The action
     re-checks.
   - The result is shown via a markup-safe toast + the result panel.
7. **Tests.**
   - `tests/test_sitrep_request_delivery.py`: pure table + orchestrator over a FakeMon.
   - `tests/test_sitrep_request_delivery_live.sh`: isolated tmux; a scripted fake Claude
     pane renders composer/dialog/draft fixtures (from the `review_loop` test captures) and
     logs the bytes received. Cases (a)-(i) from the task.
   - Mutants: identity, readiness, ack-less-as-sent, inline text, mode gate.

## Verification

- The tests above; `bash tests/test_kill_agent_run_guarded.sh` (unchanged); `bash
  tests/test_no_raw_tmux.sh`; `bash tests/run_all_python_tests.sh` (last line).
- Manual with a real sitrep agent:
  - `t` on an item submits `>t c<N>`;
  - with a permission dialog open, or a half-typed draft, the TUI refuses and the dialog /
    draft is untouched;
  - entering copy-mode during delivery leaves the request typed and unsubmitted.

## Step 9

Commit with `feature: … (t2211_4)` and archive.

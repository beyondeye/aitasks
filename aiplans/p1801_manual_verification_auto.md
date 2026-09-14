---
Task: t1801_manual_verification_restore_frozen_record_when_no_session_ex.md
Base branch: main
Output branch: main
---

# t1801 — Manual verification of t1784 (auto-execution record)

Strategy: autonomous (profile `fast`, "Yes, autonomous"). Every item was
executed inline from a shell that is OUTSIDE tmux, with the dedicated `-L ait`
server stopped at the start (verified: `no server running on
/private/tmp/tmux-501/ait`). This file is the retroactive record of what was
actually run. Full logs of items 1–2 live in this session's scratchpad
(`item1_acceptance.log`, `item2_restore_flows.log`) and are not committed.

## Execution Log

### Item 1
- Item text: Acceptance suite (unverified in t1784) — `bash tests/test_frozen_agents_acceptance.sh` outside tmux with `-L ait` stopped.
- Approach: CLI invocation.
- Action run: `bash tests/test_frozen_agents_acceptance.sh` (background, output logged).
- Output (trimmed):
  ```
  === Case 6c — tmux restarted; only an UNRELATED session exists ===
  === Case 6d — NO tmux server at all (a restore from a plain shell) ===
  === Case 7 — a coordinator killed while aborting is settled by reconcile ===
  … Case 8, 9, 10a, 10b …
  === The real $HOME is still untouched ===
  ACCEPTANCE_ELAPSED:81
  Passed: 154 / 154
  ALL TESTS PASSED
  EXIT=0
  ```
  The assert helpers print only on failure, so the two real-`$HOME` checks
  (`the real $HOME/.local/bin/ait was not rewritten`, `the real per-user
  project registry never names the scratch project`, `:1289-1298`) are inside
  the 154 count. The level-3 full-`ait setup` check was skipped (opt-in,
  `AIT_ACCEPTANCE_FULL_SETUP=1`), as the suite's own NOTE says.
- Verdict: pass

### Item 2
- Item text: Restore-flows suite — `bash tests/test_restore_flows_live.sh`, same preconditions; case 7 must restore into a new window without bootstrapping.
- Approach: CLI invocation.
- Action run: `bash tests/test_restore_flows_live.sh` (run after item 1 finished, since both need the `-L ait` socket).
- Output (trimmed):
  ```
  === Case 7 — a gone pane restores into a NEW window, one record still ===
  … Case 8–13 …
  Passed: 78 / 78
  ALL TESTS PASSED
  EXIT=0
  ```
  Case 7 asserts the recorded window is back inside the fixture's
  pre-existing `$SESSION`, i.e. the restore landed in the existing session and
  did not bootstrap a new one.
- Verdict: pass

### Item 3
- Item text: Manual end-to-end — `ait ide`, launch + freeze an agent, `tmux -L ait kill-server`, `restore --all` from a plain shell; expect the agent back beside `monitor` and `ait ide` attaching to it.
- Approach: TUI/tmux interaction with a REAL Claude Code agent and the REAL
  per-user store (`~/.config/aitasks/agent_sessions.json`).
- Action run:
  1. `bash .aitask-scripts/lib/tmux_bootstrap.sh /Users/daelyasy/Work/aitasks`
     — the same bootstrap `ait ide` sources, minus the interactive `attach`
     (no TTY here). Result: session `aitasks` with window `monitor`,
     `AITASKS_PROJECT_aitasks=/Users/daelyasy/Work/aitasks`.
  2. `launch_in_tmux(".aitask-scripts/aitask_codeagent.sh --agent-string
     claudecode/opus5 invoke raw", session=aitasks, window=agent-t1801-e2e)`
     — the board's launch helper. Real `claude` came up in pane `%1`; the
     session hook bound record `e2d505c1` (state `live`) within 0.4 s.
  3. Sent one prompt (`Reply with exactly the word OK…` → `⏺ OK`) so the
     transcript had content to resume.
  4. `.aitask-scripts/aitask_frozen.sh freeze %1` → `FROZEN:e2d505c1`;
     `@aitask_standin_ready` stamped within 0.2 s; record `frozen`, captures
     under `~/.config/aitasks/frozen/e2d505c1/`.
  5. `tmux -L ait kill-server` → `no server running`.
  6. From this plain shell: `.aitask-scripts/aitask_frozen.sh restore --all`.
- Output (trimmed):
  ```
  RESTORED:e2d505c1|hook
  RESTORE_ALL:1/1
  rc=0 elapsed=1s
  state:live  ack:hook  restore_attempts:1  session:aitasks  window:agent-t1801-e2e  pane_id:%1
  aitasks:monitor %0 Python /Users/daelyasy/Work/aitasks
  aitasks:agent-t1801-e2e %1 2.1.270 /Users/daelyasy/Work/aitasks
  AITASKS_PROJECT_aitasks=/Users/daelyasy/Work/aitasks
  captures dir: No such file or directory        (deleted on the verified ack)
  ide resolves session: aitasks ; has-session aitasks: yes
  ```
  The restored pane shows the resumed transcript (the `OK` exchange). `ait
  ide` was not literally executed (it `exec`s `tmux attach`, which needs a
  TTY); the session it resolves to and would attach to exists and is
  registered. A stale `live` record `feba3449` (t1784's own session, pane `%2`
  of a server that no longer existed) was present before this item and was
  purged by the restore path's reconcile; `restore --all` itself lists only
  `--state frozen`, so it never targeted that record.
- Verdict: pass
- Wording nit for the checklist: `./ait frozen` is not a dispatcher verb
  (`ait: unknown command 'frozen'`; `aitask_frozen.sh`'s header says a
  user-facing verb is a t1705_9/10 decision). The real command is
  `./.aitask-scripts/aitask_frozen.sh restore --all`.

### Item 4
- Item text: Manual collision check — freeze in project B, close B's session, set B's `tmux.default_session` to A's live session name, restore; expect the `session_name_taken` failure and A unchanged.
- Approach: tmux interaction with a scratch project B and the REAL store.
- Action run:
  1. Project B = a scratch install of THIS tree via `install.sh --dir <B>
     --local-tarball` under a redirected `HOME` (the acceptance suite's own
     recipe), in the session scratchpad. `tmux.default_session: bcol1801`.
  2. B's session created by hand (`tmux -L ait new-session -d -s bcol1801 -c
     <B>`), deliberately NOT via the bootstrap, so the real registry was not
     written by setup.
  3. A `claude` shim on B's PATH execs `tests/lib/fake_agent.sh` with
     `AITASKS_FAKE_AGENT_HOOK=<B>/.aitask-scripts/aitask_session_hook.sh`
     (B's real hook → the real store). Launched through B's
     `aitask_codeagent.sh … invoke raw` with `launch_in_tmux`; record
     `34685729` bound to pane `%3` (`root:<B>`, `session:bcol1801`).
  4. `<B>/.aitask-scripts/aitask_frozen.sh freeze %3` → `FROZEN:34685729`,
     stand-in ready.
  5. `tmux -L ait kill-session -t =bcol1801`; then `sed` B's config to
     `default_session: aitasks` (A's live session, holding the real agent
     from item 3 plus `monitor`). Snapshot of A: windows
     `1:monitor:%0 2:agent-t1801-e2e:%1`, `AITASKS_PROJECT_aitasks=<A>`,
     cksum of `~/.config/aitasks/projects.yaml`.
  6. `<B>/.aitask-scripts/aitask_frozen.sh restore 34685729`.
- Output (trimmed):
  ```
  RESTORE_FAILED:34685729|respawn:no_session_for_root:<B>|bootstrap:session_name_taken:aitasks
  rc=1
  state:frozen  restore_attempts:1  pane_id:(empty)
  last_error:f5498b01:respawn:no_session_for_root:<B>|bootstrap:session_name_taken:aitasks
  capture kept: yes
  A_WINDOWS_UNCHANGED   A_ENV_UNCHANGED   REAL_REGISTRY_UNCHANGED   REGISTRY_DOES_NOT_NAME_B
  ```
  B's `tmux.default_session` was reverted to `bcol1801` afterwards (then the
  whole scratch tree was removed, see Cleanup).
- Verdict: pass

## Finding outside the checklist → follow-up t1802

After item 3's successful restore, record `e2d505c1` had `agent_string:` and
`agent_kind:` EMPTY (they were `claudecode/opus5` / `claudecode` at launch).
Mechanism, verified in source: `build_resume_argv` respawns the wrapper's
`--dry-run` argv directly, so `aitask_codeagent.sh`'s `export
AITASK_AGENT_STRING` (`:646`) never runs for the replacement; the hook upserts
`--agent-string ""` (`aitask_session_hook.sh:138`) and
`agent_sessions.py:729-731` overwrites on any non-None value. A second
freeze/restore of the same record would fall back to the project's default
agent, which for a codex agent means the wrong resume shape. Neither live
suite asserts `agent_string` after a restore. Filed as **t1802**
(`followup_kind: upstream_defect`, anchored to t1705) with three fix options
and the missing assertion named.

## Cleanup

Removed:
- B's frozen record: `<B>/.aitask-scripts/aitask_frozen.sh drop 34685729` →
  `DROPPED:34685729`; `~/.config/aitasks/frozen/34685729/` gone.
- The scratch project B tree, its tarball, redirected `HOME`, install log and
  hook log (all under the session scratchpad).
- Verified: `~/.config/aitasks/projects.yaml` never named B.

Deliberately LEFT RUNNING (the item's expected end state, and killing it is
the destructive choice):
- tmux `-L ait` session `aitasks` with `monitor` (`%0`) and the restored real
  Claude agent in window `agent-t1801-e2e` (`%1`, record `e2d505c1`, `live`,
  4% context used). `ait ide` attaches to it. To return to the pre-run state
  (no server), `/exit` the agent or `tmux -L ait kill-server`, then
  `./.aitask-scripts/aitask_frozen.sh reconcile` settles the record.

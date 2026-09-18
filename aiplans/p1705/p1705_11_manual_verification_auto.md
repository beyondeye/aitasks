---
Task: t1705_11_manual_verification_frozen_codeagents_session_store_and_view.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_1_*.md … aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1705_11 — Manual verification: auto-execution record

Autonomous auto-verification pass run on 2026-09-18 from a plain terminal
(`$TMUX` unset) with the dedicated `-L ait` tmux server **down** — the one
environment in which the tmux-stress suites (items 1, 11, 14) can run at all.
Machine: macOS Darwin 24.6.0, tmux 3.6a, claude 2.1.276, codex-cli 0.153.4,
system `python3` 3.9.6, framework venv Python 3.13.13.

Outcome: 6 pass, 0 fail, 10 defer. Every deferral is either a hand check with a
real agent (5–10, 12, 13) or blocked on t1705_10, which is still `Ready`
(4, 16).

## Execution Log

### Item 1
- Item text: [t1705_1] The spike findings block exists in the parent plan and matches what a real `claude --resume` / `codex resume` do on this machine today
- Approach: file inspection + CLI (real-agent spike suite)
- Action run: `sed -n 685,800p aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`; `claude --help | grep resume`; `codex resume --help`; `AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh`
- Output (trimmed): `## Spike findings (t1705_1) — PINNED` present at line 685. Spike: `Total: 48 Passed: 48 RESULT: PASS` in 61s; FINDINGS block reproduces every pinned line — `claude SessionStart fires on --resume: yes (source=resume, same id: yes)`, `codex hooks: unsupported (... fires under codex exec, NOT in the interactive TUI)`, `codex resume: present`, `pane-died on respawn-pane -k: does not fire`.
- Verdict: pass

### Item 2
- Item text: [t1705_2] store created 0600 on first upsert; `ait`-launched agents appear as `live` records with root, window, task id
- Approach: CLI against a fresh store + inspection of the real store
- Action run: `AITASKS_AGENT_SESSIONS_FILE=$SCRATCH/fresh_sessions.json aitask_agent_sessions.sh upsert --root /tmp/x --window agent-pick-42 --pane %9 --pane-pid 1 --agent-string claudecode/opus5`; `stat -f %Lp`; `aitask_agent_sessions.sh list` on the real store
- Output (trimmed): `UPSERTED:e491006f|created`, mode `600`. Real store: `SESSION:4752bba1|live|/Users/daelyasy/Work/aitasks|agent-pick-1828|%22|1828|…` and `…|agent-pick-1837|%27|1837|…`, both with `codeagent_session_id` + `transcript_path` bound. Observation (not a failure of this item): both real records carry an empty `agent_string`; both are also still `live` although the ait server is down at the time of this run (liveness purge is the monitor's job).
- Verdict: pass

### Item 3
- Item text: [t1705_3] `ait setup` in a fresh scratch project installs the Claude hook; a real agent binds a session id + stamps `@aitask_agent_session`; a pre-existing user hook survives; a second setup adds nothing
- Approach: CLI (existing test suites driving the real setup functions + a real tmux pane) + real-store evidence
- Action run: `bash tests/test_session_hook_install.sh` (twice — see item 4 note); `bash tests/test_session_hook_live.sh`
- Output (trimmed): hook-install Groups 0/A/B/C/C2 all pass (fresh project gets hook; existing settings.json preserved; idempotent across repeated setup; hardcoded absolute path not duplicated). hook-live: `16 passed, 0 failed` on a real isolated tmux pane and real store. Real ait-launched claude agents (t1828, t1837) in the store carry their session ids. The pane stamp on a *currently running* ait agent could not be inspected (server down).
- Verdict: pass

### Item 4
- Item text: [t1705_3] Same check for Codex, or the docs and hook header say hooks are unsupported and restore is re-pick only
- Approach: file inspection + spike Case 6 + code reading
- Action run: `sed -n 1,60p .aitask-scripts/aitask_session_hook.sh`; spike Case 6 (above); `sed -n 455,490p .aitask-scripts/lib/agent_restore.py`; `grep -rn -i codex website/content/docs | grep -iE "frozen|freeze|session.id|SessionStart|rollout|re-pick"`
- Output (trimmed): hook header carries the `CODEX LIMITATION` block (interactive TUI never fires SessionStart; id captured at freeze time since t1804; re-pick otherwise). `agent_restore._restore` returns `RESTORE_FAILED:<id>|no_session` and points to `--repick`. Website grep: **no page** mentions codex freeze/restore or session hooks — that content is t1705_10's "Session hooks" setup section, still unimplemented.
- Verdict: defer — docs half blocked on t1705_10

### Items 5, 6, 7, 8, 9, 10, 12, 13
- Item text: real-agent freeze / Freeze-All / restore / re-pick / viewer rendering / list-and-switcher / minimonitor and monitor rows
- Approach: not automatable — each needs a real agent on the user's `-L ait` server or a visual judgement
- Action run: none against the items themselves. Supporting automated evidence gathered this run: `tests/test_frozen_agents_acceptance.sh` 160/160 (freeze/restore/drop cycle against the real viewer, hook-acked and liveness-fallback restore, session-mismatch and agent-exit aborts, gone-pane restore, both drop verbs); `tests/test_cleanup_rule_parity.sh` 59/59 (bash/monitor/coordinator sibling-count rule); `tests/test_codeagent_resume_session.sh` 39/39; hints band = 10 rows pinned by `tests/test_minimonitor_top_chrome_render.py`.
- Verdict: defer — what remains is exactly what the t1705_8 note names: a real `claude` honouring `--resume` and recalling its prior context (item 7), plus the hand UX checks. Also worth exercising by hand: t1773 (freeze, close the window, Restore → permanent `respawn-pane refused`).

### Item 11
- Item text: [t1705_6] From a terminal NOT inside tmux with `-L ait` down: `bash tests/test_cleanup_rule_parity.sh` passes
- Approach: CLI
- Action run: `bash tests/test_cleanup_rule_parity.sh` (precondition verified: `TMUX` unset; `tmux -L ait list-sessions` → `no server running`)
- Output (trimmed): `Passed: 59 / 59  ALL TESTS PASSED`, 7s
- Verdict: pass

### Item 14
- Item text: [t1705_8] `bash tests/test_frozen_agents_acceptance.sh` passes outside the ait server in under three minutes
- Approach: CLI
- Action run: `bash tests/test_frozen_agents_acceptance.sh`
- Output (trimmed): `Passed: 160 / 160  ALL TESTS PASSED`, 84s; final probe `The real $HOME is still untouched`
- Verdict: pass

### Item 15
- Item text: [t1705_9] Frozen Agent TUI pages, minimonitor/monitor updates, tuis/commands indexes build with zero `check_links.py --build` findings and describe the keys the TUIs actually bind
- Approach: CLI + file comparison
- Action run: `cd website && python3 check_links.py --build`; `grep 'Binding(' .aitask-scripts/frozenagent/frozenagent_app.py` vs the key table in `website/content/docs/tuis/frozenagent/reference.md`; grep of `tuis/_index.md`, `commands/_index.md`, minimonitor and monitor pages
- Output (trimmed): `Pages 253`, `broken : 0`, `SWEEP: PASSED`, exit 0. Documented keys r, m, /, n, Escape, shift+↑/↓, y, g/G, R, p, k, Enter, q match the app's BINDINGS exactly (j and ? are the shared switcher/shortcut-editor keys). Both indexes list `ait frozenagent`; minimonitor `_index.md`/`how-to.md` and monitor `reference.md`/`how-to.md` mention frozen rows.
- Verdict: pass

### Item 16
- Item text: [t1705_10] workflow page, framework-session concept page, setup "Session hooks" section
- Approach: file inspection
- Action run: `ls website/content/docs/workflows website/content/docs/concepts | grep -iE "freez|froz|session"`; `grep -rln "Session hooks" website/content/docs`
- Output (trimmed): nothing found — t1705_10 is `Ready`, not implemented
- Verdict: defer — blocked on t1705_10

## Incidental finding (not a checklist item)

`tests/test_session_hook_install.sh` Group D fails on this machine when run
plainly: `ModuleNotFoundError: No module named 'tomllib'` ×5 (`34 passed,
5 failed`). The test's Group D assertions call bare `python3`, which resolves to
the system 3.9.6; `tomllib` is 3.11+. Re-run with the framework venv first on
`PATH` (`PATH=~/.aitask/venv/bin:$PATH`) → `39 passed, 0 failed`. The product
merge is unaffected: `merge_codex_settings` in `aitask_setup.sh` prefers
`$VENV_DIR/bin/python`. Follow-up task filed for the test's interpreter choice.

## Cleanup

- `$SCRATCH/fresh_sessions.json` (fresh-store upsert probe) — removed
- Suite logs under the session scratchpad (`acceptance.log`, `parity.log`,
  `spike.log`, `hook_install*.log`, `hook_live.log`, `resume_session.log`,
  `check_links.log`) — session-local, no cleanup owed
- Each suite tears down its own isolated tmux server and scratch dirs; the
  spike's end-of-run P1 re-assertion and the acceptance suite's `$HOME`
  probe both reported the real environment untouched

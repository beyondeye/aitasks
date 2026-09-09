---
priority: medium
effort: medium
depends: [t1705_10]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1705_1, 1705_2, 1705_3, 1705_4, 1705_5, 1705_6, 1705_7, 1705_8, 1705_9, 1705_10]
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-04 16:20
updated_at: 2026-09-04 16:20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1705_1] The spike findings block exists in aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md and matches what a real `claude --resume <id>` and `codex resume <id>` do on this machine today
- [ ] [t1705_2] `~/.config/aitasks/agent_sessions.json` is created 0600 on first upsert; `ait`-launched agents appear as `live` records with the right project root, window and task id (`aitask_agent_sessions.sh list`)
- [ ] [t1705_3] After `ait setup` in a fresh scratch project, launching a real Claude Code agent in tmux binds a session id to its record and stamps `@aitask_agent_session` on the pane; a pre-existing user hook in `.claude/settings.json` survives; a second `ait setup` adds nothing
- [ ] [t1705_3] Same check for Codex (or, if t1705_1 found Codex hooks unsupported, the docs and the hook header say so and Codex restore is offered as re-pick only)
- [ ] [t1705_4] Freezing a real finished agent from a shell (`aitask_frozen.sh freeze <pane>`) leaves the window and the companion minimonitor in place, the viewer in the agent's pane, and the full scrollback readable; the agent process is gone
- [ ] [t1705_4] Freeze-All on a session with 3+ agents freezes every one and reports each; a window holding one frozen and one live agent survives killing the live one
- [ ] [t1705_5] Restore (`R`) of a real Claude agent brings the same conversation back in the same pane (ask it what it did earlier); the capture directory is deleted and the frozen row disappears
- [ ] [t1705_5] Re-pick (`p`) of a frozen task-bound agent launches `/aitask-pick <id>` in the same pane; a restore whose agent exits immediately shows the failure and the viewer is back with the transcript intact
- [ ] [t1705_6] `ait frozenagent --record <id>` renders colours faithfully; `r` toggles plain text; `/` finds text and `n` cycles; shift+down selects lines and `y` puts them on the system clipboard from inside tmux; `m` renders the selection as markdown
- [ ] [t1705_6] Bare `ait frozenagent` lists frozen agents across two projects; `enter` opens one; `k` removes a record after confirmation; the switcher (`j` then `f`) reaches the list
- [ ] [t1705_6] **From a terminal NOT inside tmux, with the dedicated `-L ait` server down:** `bash tests/test_cleanup_rule_parity.sh` passes. This is the ONE check no agent can run for itself — the script arms real `pane-died` hooks reaching tmux with raw, un-flagged calls, so it refuses while that server is alive, and that server is what hosts the working agents. t1705_6 reordered `kill_agent_pane_smart`'s frozen branch to kill-then-drop and added a third producer of the "does this window still hold a real agent?" rule (`agent_freeze._other_real_agents`), so this table is what proves the bash, monitor and coordinator implementations still agree. The monitor<->coordinator half already runs on every `tests/test_frozenagent_standin_stamp.sh` (Test 7); what this adds is the bash half.
- [ ] [t1705_7] Minimonitor shows a frozen agent as `<mark><F> name  frozen` with no state dot; the `Nf` term stays visible with `F` filtering on; `z` freezes the followed agent after a confirm; `Z` freezes all; `R`/`p`/`k` act on a frozen row; `space` still cycles the mark on it; the hints band is still ten rows
- [ ] [t1705_7] `ait monitor` mirrors the same row, `N frozen` term, `F` filter, preview placeholder and keys; auto-switch never lands on a frozen card
- [ ] [t1705_8] `bash tests/test_frozen_agents_acceptance.sh` passes from a shell outside the `ait` tmux server in under three minutes
- [ ] [t1705_9] The Frozen Agent TUI pages, the minimonitor/monitor updates and the tuis/commands indexes build with zero `check_links.py --build` findings and describe the keys the TUIs actually bind
- [ ] [t1705_10] The freeze-and-restore workflow page reads as a usable daily loop; the framework-session concept page's state diagram matches the store's states; the setup page's "Session hooks" section matches what `ait setup` really writes

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_8** id=2026-09-09T18:30:02Z.c78f5b92fdf9a4beba6d88b7 from=t1705_8 at=2026-09-09T18:30:02Z base=80d5ea53221cf89bcf0fbf4bd14e1ae23f9297b0 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1705_8 landed the composed acceptance suite. Three things change what is left
> | for you to verify by hand. Advisory only -- verify against the tree.
> | 
> | 1. **`tests/test_cleanup_rule_parity.sh` HAS NOW BEEN RUN: 59/59, green.**
> |    t1705_7's note recorded it as unrun because that session was inside the `ait`
> |    server. This session ran outside it and executed the suite. If your checklist
> |    carries "run the parity suite" as an open item, it can be closed on evidence
> |    rather than re-run -- though re-running it costs seconds and is harmless.
> | 
> | 2. **The freeze/restore/drop cycle is now covered end to end against a REAL
> |    viewer**, not a stand-in: `tests/test_frozen_agents_acceptance.sh` boots the
> |    actual `ait frozenagent --record` in the pane (AITASKS_FROZEN_STANDIN_CMD is
> |    deliberately unset), drives a real detached `run-shell -b` coordinator from
> |    the viewer's own `R` key, and covers hook-acked restore, liveness-fallback
> |    restore, session-mismatch abort, agent-exit abort, the gone-pane restore, two
> |    dead-coordinator recoveries, ambiguous relocation and both drop verbs.
> |    128 assertions, 72s.
> | 
> |    What it CANNOT model, and what your manual pass is therefore for: a **real**
> |    `claude` / `codex` binary honouring `--resume <sid>` and actually coming back
> |    to its prior context. The fixture agent only prints the id it was handed and
> |    calls the hook. Everything about whether the resumed agent still knows what
> |    it was doing is unproven and is yours.
> | 
> | 3. **A user-visible dead end worth exercising by hand: t1773.** Freeze an agent,
> |    close its window (or restart tmux), then Restore ->
> |    `RESTORE_FAILED:<id>|respawn:respawn-pane refused for %N`, permanently, for
> |    that record. Cause: `agent_restore._restore` branches on the RECORDED
> |    `pane_id` rather than checking whether the pane still exists
> |    (`agent_restore.py:334,391`). It contradicts `agent_freeze.drop_record()`'s
> |    own docstring, which says a retained record "stays restorable into a fresh
> |    window" -- `drop` preflights the live pane inventory for exactly this reason
> |    and `restore` does not.
> | 
> |    Nothing is lost when it happens (record stays `frozen`, capture intact), so
> |    it is a dead end rather than data loss. Acceptance case 6b pins only that
> |    fail-safe half so it needs no rewrite when t1773 lands; case 6a proves the
> |    gone-pane branch itself works when it is actually reached.

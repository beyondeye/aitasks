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
- [ ] [t1705_7] Minimonitor shows a frozen agent as `<mark><F> name  frozen` with no state dot; the `Nf` term stays visible with `F` filtering on; `z` freezes the followed agent after a confirm; `Z` freezes all; `R`/`p`/`k` act on a frozen row; `space` still cycles the mark on it; the hints band is still ten rows
- [ ] [t1705_7] `ait monitor` mirrors the same row, `N frozen` term, `F` filter, preview placeholder and keys; auto-switch never lands on a frozen card
- [ ] [t1705_8] `bash tests/test_frozen_agents_acceptance.sh` passes from a shell outside the `ait` tmux server in under three minutes
- [ ] [t1705_9] The Frozen Agent TUI pages, the minimonitor/monitor updates and the tuis/commands indexes build with zero `check_links.py --build` findings and describe the keys the TUIs actually bind
- [ ] [t1705_10] The freeze-and-restore workflow page reads as a usable daily loop; the framework-session concept page's state diagram matches the store's states; the setup page's "Session hooks" section matches what `ait setup` really writes

---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [frozen, session_persistence, ait_dispatcher]
created_at: 2026-09-21 22:42
updated_at: 2026-09-21 22:42
---

## Problem

The frozen-agent engine works, but it isn't part of the normal aitasks workflow. The documented flow for shutting down is: press `Z` in monitor to freeze everything, shut down, then bring agents back later (`freeze-and-restore-agents.md`, "Before shutting down"). After a reboot, though, nothing reminds the user that frozen agents exist:

- The stand-in viewer panes lived in tmux, so they die when the tmux server does.
- `ait ide` (`.aitask-scripts/aitask_ide.sh`) has no frozen-agent logic at all.
- `reconcile` deliberately leaves a frozen record whose pane is gone untouched (`agent_freeze.py` `_reconcile_frozen` → `KEEP:<id>|pane_gone`). It only respawns a viewer whose pane still exists but is dead.

Observed on 2026-09-21: 6 frozen records (2 aitasks, 4 thinking_app) survived a PC shutdown. `ait ide` opened a fresh session with no sign of them. The user reasonably expected their frozen agents to come back, at least as frozen viewers.

## Wanted

When `ait ide` starts (or attaches to) a project session, check the session store for this project's `frozen` records whose pane is gone. If there are any:

1. List them to the user: window name, task id, frozen_at, whether restore and/or re-pick is possible (session id / task id present). Also flag records that can be neither restored nor re-picked.
2. Ask what to do, with at least these choices:
   - **Recreate viewers**: bring each back as a frozen stand-in (`ait frozenagent <id>`) in a new window under its recorded name. The agent stays frozen and is only visible again. This is the default the user expected.
   - **Restore all** (`aitask_frozen.sh restore --all`) / **Re-pick all** (`--repick`).
   - **Skip**: do nothing (maybe with a hint to use `ait frozenagent` list mode).
3. Recreated viewer windows must go back into the gone-pane state machine properly: the record's pane/pane_pid is updated through the store (a `standin-respawned`-style verb with a new pane), so monitor/minimonitor show them as `F` again, and restore/drop work from the new pane.

## Notes

- Scope it to the project `ait ide` is opened for (records whose `root` is this project). Records of other projects are listed by `ait frozenagent` already.
- Non-interactive / scripted `ait ide` must not block on the prompt.
- Consider whether the minimonitor companion should also come back with a recreated viewer window (see the sibling task about restore not spawning minimonitor).
- Update `website/content/docs/workflows/freeze-and-restore-agents.md` ("Before shutting down") and the `ait ide` docs.

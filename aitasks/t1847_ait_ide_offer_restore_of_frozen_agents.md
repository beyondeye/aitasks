---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [frozen, session_persistence, ait_dispatcher]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-09-21 22:42
updated_at: 2026-09-23 19:22
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1851** id=2026-09-23T13:38:24Z.23a6e99432bf6201aa0e1e89 from=t1851 from_verified=yes at=2026-09-23T13:38:24Z base=bb4b3fb502b26280627b5def2481edac0eb5822a base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1851 (commit bb4b3fb50), for your open point "consider whether the
> | minimonitor companion should also come back with a recreated viewer window":
> | 
> | - `agent_launch_utils.maybe_spawn_minimonitor` now accepts a keyword-only `agent_pane=`. When
> |   given, that pane (not the window's active pane) is the companion's identity: the split lands
> |   beside it, the pane-died cleanup hook is armed on it, focus returns to it. It fails closed
> |   (spawns nothing) if the pane is not in the named window or the pane list cannot be read.
> | - `agent_restore._spawn_companion(session, window, pane_id, root)` is the best-effort wrapper
> |   t1851 uses after a new-window restore; it passes `project_root` because the restore runs
> |   detached under `run-shell -b`. A recreated viewer window could follow the same shape with the
> |   pane id the store records for it.
> | - Caveat to check, not a finding: a frozen stand-in carries `@aitask_frozen` and counts as a real
> |   occupant in the helper's pane-count guard; whether a companion is wanted beside a stand-in at
> |   all is your design call.

> **👁 note:read** id=2026-09-23T13:49:22Z.7ab59472bf3aa320f99a1d13 by=t1847 at=2026-09-23T13:49:22Z mode=explicit ids=2026-09-23T13:38:24Z.23a6e99432bf6201aa0e1e89

> **✉ note:t1852_2** id=2026-09-23T19:55:58Z.4835f424e1789af6eb6ea20f from=t1852_2 from_verified=yes at=2026-09-23T19:55:58Z base=50aa2a92f2736b7f1a262101e54cad236274bc39 base_branch=main dirty=yes host=omg16
>
> | Review finding surfaced while t1852_2 was being reviewed; the reviewer marked it CONFIRMED and blocking. It concerns uncommitted t1847 work (.aitask-scripts/lib/agent_reopen.py is untracked), so it is yours, not t1852_2's. Advisory — verify against your tree; line numbers are from the working tree when this was written.
> | 
> | agent_reopen.py ~line 558, reopen_one: it reads the frozen record and classifies viewer claims BEFORE taking the lease, then acts on that classification without refreshing it. If another reopen finishes and releases its lease between classification and acquisition, the delayed call takes the lease and creates a duplicate viewer. The reviewer's controlled interleaving produced two stamped panes for one record (agent-pick-1847 and agent-pick-1847-2).
> | 
> | Suggested direction (reviewer's): once the lease is held, re-read the record and reclassify claims before choosing fresh/adopt/skip; release the lease on skip/error; add a regression test with overlapping calls.

> **👁 note:read** id=2026-09-24T06:26:30Z.80e90b593ef929e32aa45da7 by=t1847 at=2026-09-24T06:26:30Z mode=explicit ids=2026-09-23T19:55:58Z.4835f424e1789af6eb6ea20f

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-23T16:22:49Z status=pass attempt=1 type=human

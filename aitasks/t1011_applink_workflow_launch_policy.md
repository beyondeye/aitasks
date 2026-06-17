---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_bridge]
created_at: 2026-06-16 16:56
updated_at: 2026-06-16 16:56
boardidx: 70
---

## Origin

Risk-mitigation ("after") follow-up for t822_11 (applink modal-dialog handshakes), created at Step 8d after the handshake plumbing landed.

## Risk addressed

Goal-achievement "confirmed-execution deferred": the `restart_task` and `pick_next_sibling` modal handshakes are fully served (suggest/choose + idle-gated confirm), but their final kill-old-pane + relaunch-agent **execution** is intentionally deferred — partial surface by design · severity: medium.

The desktop launch orchestration (`AgentCommandScreen` + `launch_in_tmux` + `maybe_spawn_minimonitor`, `monitor_app.py:1646-1726`) lives in Textual screens with no mobile/server-side equivalent. Per `aidocs/applink/monitor_port_design.md` §Command-verb mapping, a server-side default-launch policy "needs its own design".

## Goal

Design and implement the applink workflow launch policy so the confirmed/chosen legs of the modal handshakes actually execute, then remove the deferred signal:

- Define a server-side (or mobile-driven) launch policy that can kill the old pane and relaunch the pick agent for a chosen sibling / restart target without the desktop's interactive `AgentCommandScreen` (resolve agent string + profile, build a `TmuxLaunchConfig`, `launch_in_tmux`, optional minimonitor).
- Wire it into the two deferred branches in `.aitask-scripts/applink/router.py`: `_restart_task`'s `execute()` and `_pick_next_sibling`'s choose-phase (currently both return `err NOT_IMPLEMENTED detail:{reason:"deferred"}`). These two call sites are the single integration point.
- Re-evaluate the `NOT_IMPLEMENTED` error path: on success the verbs should return a real `res`; keep `NOT_IMPLEMENTED` only where execution genuinely cannot be performed.
- Coordinate the wire contract with the mobile client (`../aitasks_mobile`, cross-repo): the handshake response shapes are already pinned by t822_11.

## Reference Files

- `.aitask-scripts/applink/router.py` — `_restart_task` / `_pick_next_sibling` (deferred legs)
- `.aitask-scripts/monitor/monitor_app.py` — desktop `_launch_pick_for_sibling` / `action_restart_task` launch orchestration to port/adapt
- `aidocs/applink/monitor_port_design.md` — §Command verb → applink protocol mapping (deferral rationale)
- `aiplans/archived/p822/p822_11_applink_modal_handshakes.md` — the handshake design + Final Implementation Notes

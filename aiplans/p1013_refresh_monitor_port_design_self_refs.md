---
Task: t1013_refresh_monitor_port_design_self_refs.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Full post-extraction refresh of monitor_port_design.md

## Scope decision (expanded from original task framing)

t1013 was authored as a low/low fix of **two** stale self-references (the
§Command verb intro parenthetical at L61 and the §Command verb table call-site
column at L67–78). During planning the user chose the **Full post-extraction
refresh** scope: bring the whole `aidocs/applink/monitor_port_design.md` doc to
current reality — flip the "(future)/deferred" framing for the now-landed
`monitor_core` extraction, rewrite the §Headless-core "Source" table, and make
the doc's own verify (`grep -n 'tmux_monitor.py:\|monitor_shared.py:'` → empty)
achievable. The task AC is updated to match (see "AC update" below). This is no
longer low effort.

## Ground truth (verified against source this session)

- `tmux_monitor.py` and `tmux_control.py` are now **re-export shims**; the
  monitor command surface, control client, dataclasses, idle-tracking state,
  `_TEXTUAL_TO_TMUX`/`translate_key`, and `TaskInfoCache`/`TaskInfo` all moved to
  `.aitask-scripts/monitor/monitor_core.py` (t822_6; key map t822_7;
  `TmuxControlClient`/`TmuxControlBackend` relocation t822_6, completing t952_3).
- Modal dialogs stayed **UI-bound**: `TaskDetailDialog`, `KillConfirmDialog`,
  `NextSiblingDialog`, `ChooseSiblingModal` in `monitor_shared.py`;
  `SessionRenameDialog`, `RestartConfirmDialog` in `monitor_app.py`.
- Widgets `PaneCard`/`PreviewPanel` in `monitor_app.py`; `MiniPaneCard` in
  `minimonitor_app.py`.
- Launch orchestration moved out of `monitor_app.py`: `AgentCommandScreen` in
  `agent_command_screen.py`; `launch_in_tmux`/`maybe_spawn_minimonitor` in
  `lib/agent_launch_utils.py` (still invoked from `monitor_app.py`).
- tmux-exec substrate `TmuxClient.run_via_control` in `lib/tmux_exec.py`.
- permissions.md verb gating table was synced in t822_12 and now carries
  `forward_key`/`pick_next_sibling`/`restart_task`/`task_detail`. Its citation
  style is **symbol-only, no line numbers**: `` `monitor_core.py` (`capture_all`) ``.

## Citation convention (mirror t822_12 / permissions.md)

Replace every fragile `path:line` citation with drift-proof **symbol-form**:
`` `file.py` (`Symbol`) `` (or just `` `file.py` `` when the symbol already
appears in column 1 of a table). This is what makes `grep ... → empty` hold:
the verify pattern matches `filename:` (filename + colon), so symbol-form
citations (no colon) pass while remaining accurate.

## Edits (section by section in monitor_port_design.md)

1. **Overview (L9, L11):** Add a short status note that the `monitor_core`
   extraction and the permissions-table sync have landed (remaining applink
   follow-ups still deferred). L11 "which symbols move to a future
   `monitor_core.py`" → "which symbols were extracted to `monitor_core.py`".

2. **§Headless-core extraction header (L23):** "Functions moving to … (future)"
   → "Functions extracted to `.aitask-scripts/monitor/monitor_core.py`
   (t822_6, landed)".

3. **Source table (L25–37):** rename middle column "Source" → "Location"; set
   every row's location to `monitor_core.py` (rows for `TmuxControlClient`/
   `TmuxControlBackend` and `TaskInfoCache` included — they relocated from
   `tmux_control.py`/`monitor_shared.py`).

4. **§tmux gateway delegation (L41, L43–44):** drop `tmux_exec.py:230` (symbol
   already named); reframe L43 "are thin wrappers … and move to `monitor_core`
   as-is" → "now live in `monitor_core`"; reframe L44 relocation as landed in
   t822_6 (with `tmux_control.py` now a re-export shim).

5. **§What stays in monitor_app.py table (L47–56):** convert all `monitor_app.py:`
   /`monitor_shared.py:` line citations to symbol-form. Fix L51 modal-screen
   pointer to reference §Modal-dialog handshakes; fix L53 `_TEXTUAL_TO_TMUX`
   "monitor_app.py:100" → "now in `monitor_core.py`"; fix L55 launch
   orchestration to its real homes (`agent_command_screen.py`,
   `lib/agent_launch_utils.py`).

6. **§Command verb intro (L61) [original defect 1]:** reword the parenthetical —
   permissions.md no longer "predates" the new verbs; it is the in-sync
   profile-band view (synced in t822_12). Change "Audited … against
   `tmux_monitor.py` methods and every `action_*` handler in
   `monitor_app.py:1262-1823`" → symbol-form (`monitor_core.py` methods;
   `action_*` handlers in `monitor_app.py`).

7. **§Command verb table (L67–78) [original defect 2]:** rewrite the "Existing
   call site" column to symbol-form mirroring permissions.md
   (`monitor_core.py` (`capture_all`), …; `forward_key` →
   `monitor_app.py` (`_forward_key_to_tmux`; map `_TEXTUAL_TO_TMUX` in
   `monitor_core.py`); `cycle_compare_mode` handler →
   `action_cycle_compare_mode`; `pick_next_sibling`/`restart_task` →
   `action_pick_next_sibling`/`action_restart_task`;
   `task_detail` → `monitor_core.py` (`TaskInfoCache._resolve`)). This also
   corrects two wrong handler line numbers (`:1489`, `:1728`).

8. **Notes after verb table (L83–88):** update `_TEXTUAL_TO_TMUX`/`translate_key`
   to `monitor_core.py` (t822_7); `kill_agent_pane_smart` smart-kill path →
   `action_kill_pane`; pick/restart launch path → symbol-form
   (`action_*` + `agent_command_screen.py`/`lib/agent_launch_utils.py`);
   idle gate → `action_restart_task`.

9. **§Snapshot → row encoding (L96):** `PaneSnapshot.content`/`_capture_args`
   `tmux_monitor.py:…` → `monitor_core.py`.

10. **§Refresh cadence wiring (L106–107):** convert `monitor_app.py:` line
    citations to symbol-form (`_refresh_data` timer; preview fast timer).

11. **§Scroll anchor (L117):** `monitor_app.py:450-458` / `_locate_anchor`
    `monitor_app.py:629-642` → `monitor_app.py` (`_record_preview_scroll` /
    `_locate_anchor`).

12. **§Deltification (L121):** `_last_content`/`_last_change_time`
    `tmux_monitor.py:459-465` → `monitor_core.py`.

13. **§Modal-dialog handshakes table (L133–141):** Location column →
    `monitor_shared.py` / `monitor_app.py` (symbol already in col 1); inline
    `monitor_app.py:1602-1667`/`:1585-1600` → symbol-form
    (`action_pick_next_sibling`; desktop callback style in `monitor_app.py`).

14. **§Task-detail RPC (L145–147):** `TaskInfoCache`/`_resolve`/`TaskInfo` →
    `monitor_core.py`; force-refresh `monitor_app.py:1517` → `action_show_task_info`.

15. **§Permission profile cross-check (L154–160):** reframe "discrepancies … to
    be resolved by the sync follow-up — not silently fixed here" to past tense
    (resolved by t822_12's sync); fix L160 `kill_agent_pane_smart`
    `tmux_monitor.py:643` → `monitor_core.py`.

16. **§Deferred follow-up tasks (L162–173):** mark the **Refactor: extract
    `monitor_core.py`** bullet (L166) and the **update permissions.md verb
    gating table** bullet (L172) as LANDED (t822_6/t822_7; t822_12). Leave the
    remaining applink follow-ups (WS listener, snapshot push, delta engine,
    append fast-path, modal handshakes, applink-mode flag) as deferred — their
    landed-status was **not** verified this session and is out of scope.

## Out of scope (deliberately not touched)

- Landed-status of the applink listener / delta-engine / append / handshake
  follow-ups (not verified; the doc body's `applink/content.py`/`pusher.py`
  references carry no `path:line` citations and don't affect the grep verify).
- Any code under `.aitask-scripts/monitor/`.
- `permissions.md` and the YAML profiles (their sync was t822_12).

## Verification

```bash
grep -n 'tmux_monitor.py:\|monitor_shared.py:' aidocs/applink/monitor_port_design.md   # → empty
grep -nE '[a-z_]+\.py:[0-9]' aidocs/applink/monitor_port_design.md                      # → empty (no path:line left)
```
Spot-check that each rewritten symbol exists at its claimed file (already
verified during planning). Confirm tables still render (column counts intact).

## AC update (no silent deviation)

Update t1013's body: replace the narrow two-bullet defect list with the agreed
full-refresh scope and the broadened verify (no `path:line` citations remain;
`monitor_core` extraction framing reflects landed reality). Commit the task-file
update via `./ait git`.

## Risk

Two dimensions assessed separately.

- **Code-health risk: low.** No code changes — documentation only. The edits are
  mechanical citation substitutions and framing rewrites, each verified against
  the current source this session. The main hazard is introducing a wrong symbol
  reference; mitigated by the per-symbol verification already done and the
  `grep` verifications above. Switching to symbol-form citations *reduces* future
  drift (the root cause of this task).
- **Goal-achievement risk: low.** The goal is concrete and verifiable
  (grep→empty + framing reflects landed extraction). The only judgment call —
  how far to flip "deferred" framing — is bounded explicitly to the two
  verified-landed follow-ups, with the rest left deferred.

No before/after mitigation tasks required.

## Step 9 (Post-Implementation)

Profile 'fast', current branch — no worktree/merge. After review approval:
commit the doc edit (`documentation: …(t1013)`), commit the task-file AC update
via `./ait git`, then archive via `aitask_archive.sh 1013` and push.

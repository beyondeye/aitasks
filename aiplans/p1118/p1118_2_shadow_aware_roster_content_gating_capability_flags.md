---
Task: t1118_2_shadow_aware_roster_content_gating_capability_flags.md
Parent Task: aitasks/t1118_mobile_shadow_agent_driving_over_applink.md
Sibling Tasks: aitasks/t1118/t1118_1_*.md, aitasks/t1118/t1118_3_*.md, aitasks/t1118/t1118_4_*.md, aitasks/t1118/t1118_5_*.md
Archived Sibling Plans: aiplans/archived/p1118/p1118_*_*.md
Worktree: aiwork/t1118_2_shadow_aware_roster_content_gating_capability_flags
Branch: aitask/t1118_2_shadow_aware_roster_content_gating_capability_flags
Base branch: main
---

# Plan: Shadow-aware roster + content gating + capability flags (t1118_2)

Implements parent-plan D1 + D2b + the D3 `shadow_target` field. Contract:
`aidocs/applink/shadow_driving.md` (authored by t1118_1).

## Steps

1. **`monitor/monitor_core.py`:**
   - `TmuxPaneInfo` (~:234): add `shadow_target: str = ""`.
   - `PaneCategory`: add `SHADOW` member.
   - `TmuxMonitor.__init__`: add `include_shadow_panes: bool = False`.
   - `_parse_list_panes` (~:1017): replace the unconditional drop
     (`if is_shadow_target(parts[8]): continue`, ~:1032) with:
     ```python
     if is_shadow_target(parts[8]):
         if not self.include_shadow_panes:
             continue
         # applink-only: surface the shadow with its binding
         shadow_target = parts[8]
         category = PaneCategory.SHADOW  # skip classify_pane
     ```
     keep the companion-process filter applying only to AGENT panes as today.
2. **Construction sites:** `applink/applink_app.py` + `applink/headless.py` —
   pass `include_shadow_panes=True` where the applink `TmuxMonitor` is built
   (desktop TUIs untouched, default False).
3. **`applink/pusher.py` `_send_pane_status`** (~:388): additively emit
   `"shadow_target": snap.pane.shadow_target` only when non-empty.
4. **`applink/router.py` — D2b content gating:** in the `subscribe` branch
   (~:332), when the session's profile does not grant shadow content, exclude
   panes whose roster record (`self._monitor.get_pane(pane_id)`) has non-empty
   `shadow_target` from the effective content set — i.e. filter both the
   `content_panes` list (when the split is active) and, when `content_all`
   would apply, force the split by materializing `content_panes = accepted
   minus shadows`. Decide "grants" via ONE helper in `applink/profiles.py`:
   ```python
   def grants_shadow_content(gate, profile: str) -> bool:
       """True iff this profile may stream shadow-pane content.
       Defined as: the profile is allowed the shadow_concerns verb
       (monitor_control and above)."""
       return gate.is_allowed(profile, "shadow_concerns")
   ```
   (One decision point — the pusher's t1118_4 field split reuses it.)
   `request_keyframe`/`history` need no change: they already reject
   non-content panes via `streams_content` / `not_subscribed`.
5. **Capability flags:** two response sites gain additive fields:
   - `_do_pair` (~:258): extend the existing pair `res` payload with
     `"allowed_verbs": sorted(gate.allowed_verbs(profile))` and
     `"caps": {"shadow_content": grants_shadow_content(gate, profile)}`.
     If the gate object has no `allowed_verbs()` accessor yet, add one to
     `profiles.py` returning the resolved verb set for a profile name.
   - the `resume` handler (router.py:221-227, currently
     `self._res(msg_id, verb, {"profile": session.profile})`): add the same
     two fields.
6. **Downstream audit (record findings in this plan):**
   `_discover_pane_ids` (subscribe-all now includes shadows — intended);
   `kill_agent_pane_smart` real-agent count (marker-driven — verify unchanged);
   snapshot capture path treats SHADOW panes as ordinary panes.

## Verification

- `tests/test_applink_router.sh` additions: subscribe-all includes shadow ids;
  read_only `content_panes` excludes shadows while monitor_control includes;
  `request_keyframe` on a shadow rejected for read_only, accepted for
  monitor_control; pair response carries `allowed_verbs`/`caps` per profile.
- `tests/test_applink_pusher.sh`: `shadow_target` present on shadow panes,
  absent otherwise.
- **Negative control** (new or in a monitor test): `_parse_list_panes` with
  flag False drops a stamped shadow line exactly as today.
- Existing suites: `bash tests/test_applink_router.sh`,
  `bash tests/test_applink_pusher.sh`, monitor tests, `test_no_raw_tmux.sh`.

## Post-implementation

Step 9 (task-workflow): archive via `aitask_archive.sh 1118_2`, push.

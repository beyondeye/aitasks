---
Task: t1118_1_shadow_driving_protocol_design_doc.md
Parent Task: aitasks/t1118_mobile_shadow_agent_driving_over_applink.md
Sibling Tasks: aitasks/t1118/t1118_2_*.md, aitasks/t1118/t1118_3_*.md, aitasks/t1118/t1118_4_*.md, aitasks/t1118/t1118_5_*.md
Archived Sibling Plans: aiplans/archived/p1118/p1118_*_*.md
Worktree: aiwork/t1118_1_shadow_driving_protocol_design_doc
Branch: aitask/t1118_1_shadow_driving_protocol_design_doc
Base branch: main
---

# Plan: Shadow-driving protocol design doc (t1118_1)

Docs-only child. The parent plan
(`aiplans/p1118_mobile_shadow_agent_driving_over_applink.md`, at archival
`aiplans/archived/`) sections **D1–D5** are the authoritative content source —
transcribe their decisions, do not re-decide.

## Exact wire schemas to document (normative — both repos build against these)

```json
// spawn_shadow (req, full band) — pane_id is the FOLLOWED agent pane
{"verb":"spawn_shadow", "payload":{"pane_id":"%12"}}
// res
{"payload":{"ok":true, "shadow_pane":"%15"}}
// err when a shadow already exists for that agent
{"payload":{"code":"BAD_PAYLOAD","message":"shadow already running",
            "detail":{"reason":"shadow_exists","shadow_pane":"%15"}}}

// shadow_concerns (req, monitor_control band) — pane_id is the SHADOW pane
{"verb":"shadow_concerns", "payload":{"pane_id":"%15"}}
// res — analyzed_at is epoch seconds or null (shadow has not analyzed yet)
{"payload":{"concerns":[{"priority":"high","region":"Step 7 ownership guard",
                          "body":"..."}],
            "followed_pane":"%12", "analyzed_at":1783158000, "stale":false}}
// err when the pane is not a shadow pane
{"payload":{"code":"BAD_PAYLOAD","message":"not a shadow pane",
            "detail":{"reason":"not_shadow_pane"}}}

// send_keys gains an optional flag (default false = today's behavior)
{"verb":"send_keys",
 "payload":{"pane_id":"%12","keys":"...","literal":true,"paste":true}}

// pair / resume responses gain (additive):
{"payload":{"bearer":"...", "profile":"monitor_control", "expires_at":"...",
            "allowed_verbs":["snapshot","subscribe","...","shadow_concerns"],
            "caps":{"shadow_content":true}}}

// pane_status additions — on SHADOW panes:
{"shadow_target":"%12"}
// on FOLLOWED panes with a bound shadow (has_concerns only for
// monitor_control+ connections):
{"shadow_pane":"%15","shadow_stale":false,"shadow_analyzed_at":1783158000,
 "shadow_has_concerns":true}
```

Priorities are `high|medium|low` (unknown degrades to `low`, item never
dropped — mirror `aidocs/framework/shadow_concern_format.md`).

## Steps

1. **Author `aidocs/applink/shadow_driving.md`** with sections:
   - *Overview & advisory-only invariant* — the shadow never inputs into the
     followed pane; forwarding is user-initiated client-side `send_keys`.
   - *Roster exposure (D1)* — `TmuxMonitor(include_shadow_panes)` opt-in;
     desktop drop stays default; `PaneCategory.SHADOW`;
     `TmuxPaneInfo.shadow_target`.
   - *Visibility model* — metadata for all profiles; shadow CONTENT streaming
     gated `monitor_control` (subscribe `content_panes` filter, D2b).
   - *Verbs* — `spawn_shadow` `{pane_id}` (FOLLOWED pane, `full`,
     `shadow_exists` error detail) and `shadow_concerns` `{pane_id}` (SHADOW
     pane, `monitor_control`, `not_shadow_pane` error detail, response
     `{concerns:[{priority,region,body}], followed_pane, analyzed_at?, stale}`).
   - *Capability flags* — `pair`/`resume` additive `allowed_verbs` +
     `caps:{shadow_content}`; clients gate UI off these, never profile names.
   - *`pane_status` extensions (D3)* — binding/staleness fields for all
     profiles; `shadow_has_concerns` content-derived, suppressed below
     `monitor_control`.
   - *Non-stamping invariant (D2-inv)* — passive inspection never writes
     `@aitask_shadow_analyzed_at`; raw gateway `capture-pane -J` only, never
     `aitask_shadow_capture.sh`.
   - *Cost contract (D3-cost)* — change-gated, 200-line depth cap, shared
     per-pane verdict cache.
   - *`send_keys paste` mode (D4)* — `load-buffer` + `paste-buffer -p -d`;
     stage-only forwarding.
   - *Staleness semantics* — t1104 model (stamp vs followed-pane last change +
     epsilon).
2. **`aidocs/applink/monitor_port_design.md`** — add rows to the canonical verb
   table for `spawn_shadow` / `shadow_concerns`; note `send_keys` payload gains
   `paste?:bool`. Mark "implementation pending (t1118_3/t1118_4)".
3. **`aidocs/applink/permissions.md`** — gating-table rows
   (`spawn_shadow`→full, `shadow_concerns`→monitor_control), marked pending;
   the yaml profile edits land with the implementing children.
4. **`aidocs/applink/protocol.md`** — one cross-reference line to the new doc.

## Verification

- Cross-links resolve; verb/permission tables and shadow_driving.md agree with
  the parent plan's D-sections verbatim where they overlap.
- No code changes; no profile yaml changes in this child.

## Post-implementation

Step 9 (task-workflow): archive via `aitask_archive.sh 1118_1`, push.

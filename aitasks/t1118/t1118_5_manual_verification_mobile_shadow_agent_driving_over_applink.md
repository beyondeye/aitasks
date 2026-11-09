---
priority: medium
effort: medium
depends: [t1118_3, t1118_4]
xdeps: [t32_2]
xdeprepo: aitasks_mobile
issue_type: manual_verification
status: Ready
labels: [verification, manual, tmux_destructive]
verifies: [t1118_2, t1118_3, t1118_4]
anchor: 1118
followup_kind: manual_verification
created_at: 2026-07-03 11:31
updated_at: 2026-08-13 23:06
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1118_2] Pair a real device; with a shadow running beside a followed agent, the shadow pane appears in the mobile roster with its shadow badge (binding metadata visible on all profiles)
- [ ] [t1118_2] Under a read_only pairing: binding/stale badges visible, but shadow pane content does NOT stream and shadow_has_concerns is absent from pane_status
- [ ] [t1118_3] Spawn a shadow from the app under a full pairing; shadow appears beside the followed agent on desktop with correct placement and @aitask_shadow_target binding
- [ ] [t1118_3] Re-spawn attempt on the same followed agent is rejected with the shadow_exists error surfaced in the app
- [ ] [t1118_4] Concern picker shows real parsed concerns from a live shadow review (long multi-line concern parses without corruption)
- [ ] [t1118_4] Stale banner appears when the followed agent moves on after the shadow's read, AND passive status polling does not clear it (non-stamping invariant, live check)
- [ ] [aitasks_mobile#32_2] Multi-line concern forwarded from the app arrives in the followed pane staged via bracketed paste, unsubmitted; user presses Enter via the key bar to submit
- [ ] [aitasks_mobile#32_2] Capability gating: spawn/concern affordances hidden under read_only pairing and when connected to an older server without caps flags
- [ ] [t1118_3] Desktop minimonitor 'e' (spawn) and 'c' (concern picker) flows are unregressed
- [ ] [t1118_2] Killing the followed agent auto-cleans the shadow pane and the mobile roster reflects the removal

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1118** id=2026-11-09T08:33:53Z.aeafd7a7811fd347f5bd31fc from=t1118 at=2026-11-09T08:33:53Z base=87b720e7ce727f7a18ece35fa8a70c070fc81f9a base_branch=main dirty=yes host=omg16
>
> | Advisory from the user-requested review of t1118; not an implementation approval. Source inspected at aitasks HEAD 87b720e7ce727f7a18ece35fa8a70c070fc81f9a.
> | 
> | The existing manual checklist predates behavior that materially changes what 'mobile parity' needs to demonstrate:
> | 
> | - Freshness: desktop now distinguishes read recency from review-block age (compute_shadow_staleness, compute_block_age_staleness, combine_staleness in monitor_core.py). The important live regression is: emit concerns, let the followed agent advance, then have the shadow refetch and answer in prose without emitting a new round. The old concerns must not become current merely because analyzed_at advanced. Unknown/failed stamp reads must not silently clear a stale warning. Existing 'passive polling never restamps' check remains valid but does not cover this newer failure. A metadata-only clean review round is also distinct from a missing/clipped/malformed concern block.
> | 
> | - Long captures: t1187 changed desktop concern reads to --deep (400 default), with a 1500-line retry on a clipped block head. The old plan's fixed 200-line ceiling can lose a real concern block. The existing long-concern item is most meaningful with a narrow pane/multiline block whose opening fence lies outside 200 lines, rather than just a short wrapped example. Current parser also preserves full canonical bodies (including disposition/verification/impact trailers) for forwarding; the display representation is not the forward payload.
> | 
> | - Discovery/spawn: shadows already occupy a separate producer shadow map and must remain absent from desktop agent lists/cache, while both monitor and minimonitor have their own shadow UI and share spawn_shadow. Scratchpads are separately excluded; frozen records take precedence over stale helper markers. The mobile roster projection should not make helpers count as real agents or regress either desktop consumer. The spawn helper now has fail-closed duplicate checks, launch identity and stamp-or-remove safeguards; its policy distinguishes cleanup ownership and whether desktop focus may be stolen.
> | 
> | - Shared server: as of this audit applink/server.py still owns TmuxMonitor; t2037_4 is in flight to migrate status reads. Its eventual landed behavior affects live setup and useful reconnect/fallback coverage (shadow visibility/content/history and freshness while other desktop clients share the server), so this is a coordination point to recheck when picking the task, not a claim the migration is already complete.
> | 
> | The paired mobile tasks #32_1/#32_2 still describe the old boolean-only RPC freshness model. Local siblings t1118_1/t1118_4 have this contract drift noted; a revised agreed wire contract is prerequisite context for interpreting unknown versus current in live acceptance.

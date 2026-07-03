---
priority: medium
effort: medium
depends: [t1118_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1118_2, 1118_3, 1118_4]
anchor: 1118
created_at: 2026-07-03 11:31
updated_at: 2026-07-03 11:31
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

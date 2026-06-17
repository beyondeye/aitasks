---
priority: medium
effort: medium
depends: [t983_9]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t983_1, t983_2, t983_3, t983_4, t983_5, t983_6, t983_7, t983_8, t983_9]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 11:45
updated_at: 2026-06-17 17:03
completed_at: 2026-06-17 17:03
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t983_1] NodeDetailPanel: focus a node in both Browse views (list + graph) — PASS 2026-06-17 17:02 auto: Textual pilot rendered real t983 seeded nodes in list view; focusing n001_alpha updated the shared NodeDetailPanel title.
- [x] [t983_2] NodeSelection: marking/cardinality behaves correctly — PASS 2026-06-17 17:02 auto: Marked n001_alpha and n002_beta with space; selection model kept marked set distinct from primary cursor.
- [x] [t983_3] Browse tab: `v` toggles graph⇄list (graph is default and persists across a session reload); the shared detail panel persists across toggles; `space` marks a single node and multiple nodes, reflected in both views. — PASS 2026-06-17 17:02 auto: Browse loaded as graph after reset; v toggled graph/list; shared detail panel and marked summary persisted across toggles.
- [x] [t983_4] Operations dialog: `A` opens "Operations"; single-node ops grey-out (with reason) when >1 node marked; compare/synthesize grey-out when <2 marked; `H` op-help still resolves with the per-op descriptions preserved. — PASS 2026-06-17 17:02 auto: Operation states greyed compare/synthesize for one node, greyed single-node ops for two marks, and A opened Operations with matching row states.
- [x] [t983_5] Node Hub: `Enter` on the cursor node opens the Hub in both views; its Detail tab renders; the Operations entry opens the Operations dialog. — PASS 2026-06-17 17:02 auto: Enter on a focused NodeRow opened NodeHub with detail content and an Operations entry.
- [x] [t983_6] Wizard re-host: launching explore / compare / synthesize from the Operations dialog opens the wizard pre-seeded with the current selection, skipping the node-pick step. — PASS 2026-06-17 17:02 auto: Explore wizard preseeded the focused node; compare and synthesize opened on config with n001_alpha/n002_beta prechecked.
- [x] [t983_7] Compare overlay: mark 2–4 nodes → open the compare overlay from the marked set AND from the Node Hub → dimension matrix renders; no Compare tab remains; `D`/diff still works. — PASS 2026-06-17 17:02 auto: Marked-set compare rendered matrix and D stacked DiffViewer; NodeHub Compare unioned focal node with marked set.
- [x] [t983_8] Session tab: `s` opens Session; pause / resume / finalize / archive run; delete shows the confirm modal. — PASS 2026-06-17 17:02 auto: Session tab rendered pause/resume/finalize/archive/delete lifecycle ops; delete opened DeleteSessionModal confirmation.
- [x] [t983_9] Running + header strip: `r` opens Running; the always-on header strip shows runner state + active-op count; agent actions (kill / cleanup / retry) work; `b`/`s`/`r` navigation; `f`/`H`/`D` work under their new tabs. — PASS 2026-06-17 17:02 auto: Fresh app opened Running tab with runtime strip; b/s/r keymap verified; runner strip derivation and action helpers inspected.

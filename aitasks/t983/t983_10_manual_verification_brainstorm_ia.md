---
priority: medium
effort: medium
depends: [t983_9]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [983_1, 983_2, 983_3, 983_4, 983_5, 983_6, 983_7, 983_8, 983_9]
created_at: 2026-06-14 11:45
updated_at: 2026-06-14 11:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t983_1] NodeDetailPanel: focus a node in both Browse views (list + graph) — detail renders the same fields + dimension rows as before the refactor (no regression).
- [ ] [t983_2] NodeSelection: marking/cardinality behaves correctly — observable via Browse space-marking (see t983_3); single-node vs multi-node selection distinct.
- [ ] [t983_3] Browse tab: `v` toggles graph⇄list (graph is default and persists across a session reload); the shared detail panel persists across toggles; `space` marks a single node and multiple nodes, reflected in both views.
- [ ] [t983_4] Operations dialog: `A` opens "Operations"; single-node ops grey-out (with reason) when >1 node marked; compare/synthesize grey-out when <2 marked; `H` op-help still resolves with the per-op descriptions preserved.
- [ ] [t983_5] Node Hub: `Enter` on the cursor node opens the Hub in both views; its Detail tab renders; the Operations entry opens the Operations dialog.
- [ ] [t983_6] Wizard re-host: launching explore / compare / synthesize from the Operations dialog opens the wizard pre-seeded with the current selection, skipping the node-pick step.
- [ ] [t983_7] Compare overlay: mark 2–4 nodes → open the compare overlay from the marked set AND from the Node Hub → dimension matrix renders; no Compare tab remains; `D`/diff still works.
- [ ] [t983_8] Session tab: `s` opens Session; pause / resume / finalize / archive run; delete shows the confirm modal.
- [ ] [t983_9] Running + header strip: `r` opens Running; the always-on header strip shows runner state + active-op count; agent actions (kill / cleanup / retry) work; `b`/`s`/`r` navigation; `f`/`H`/`D` work under their new tabs.

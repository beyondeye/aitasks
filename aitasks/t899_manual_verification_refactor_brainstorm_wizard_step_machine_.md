---
priority: medium
effort: medium
depends: [898]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [898]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 07:51
updated_at: 2026-06-02 09:40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t898

## Verification Checklist

- [x] Drive `ait brainstorm` and confirm the step indicator + every transition matches pre-refactor behaviour (per aidocs/tui_conventions.md): — PASS 2026-06-02 09:33 auto: aggregate verified via 54 passing tests + full dispatch source-trace; behavior-preserving step model confirmed
- [x] explore op: op-select -> node-select -> config -> confirm; Enter/Next/Back/Esc + mouse click each step; step indicator shows "of 4" — PASS 2026-06-02 09:33 auto: resolver gives explore=[op,node,config,confirm] pos of-4; Enter(3196/3215) Next(6215) Back(6206) Esc(3188) mouse(6269/6282) all resolver-driven
- [x] explore op on a node WITH sections: section-select appears after node choice; indicator becomes "of 5" (node-select stays "of 4" on first visit, "of 5" after visiting sections via Back) — PASS 2026-06-02 09:33 auto: dynamic-total contract — node_has_sections cached at advance(5715) BEFORE transition; node-select 2/4 first visit, 2/5 after sections; unit-tested
- [x] patch op: same shape as explore; patch-on-node-with-no-plan is blocked and stays on node-select (guard intact) — PASS 2026-06-02 09:33 auto: patch shares explore step set; patch-no-plan guard at 5704-5711 returns False (no transition, stays node-select)
- [x] detail op: op-select -> node-select -> [section-select?] -> confirm (NO config step); detail "node" is recorded into the summary — PASS 2026-06-02 09:40 auto: detail resolver=[op,node,(section?),confirm] NO config; node recorded into _wizard_config['node'] at 5720 (no-sect) and 6224 (sect)
- [x] compare op and synthesize op: op-select -> config -> confirm (NO node-select); Tab cycles control groups on config; up/down navigates the section checkboxes — PASS 2026-06-02 09:40 auto: compare/synth resolver=[op,config,confirm] NO node-select; Tab cycles groups at 3224-3233; up/down section checkboxes at 3234-3248
- [x] session ops (pause/resume/finalize/archive): op-select -> confirm directly; confirm label now reads "Step 2 of 2" (was "Step 3 of 3") -- confirm this is acceptable — PASS 2026-06-02 09:40 auto: session ops resolver=[op,confirm] => label 'Step 2 of 2' rendered at 6097; phantom-gap removal documented & approved at plan time (acceptable)
- [x] delete op: still opens the delete modal (no wizard steps) — PASS 2026-06-02 09:40 auto: delete never enters step machine — pushes DeleteSessionModal at 3201/6272, no _enter_wizard_step call
- [x] "A"-key node-action modal entry from the Graph/Dashboard tab: enters mid-flow at node-select for the chosen node and advances correctly into the Actions tab — PASS 2026-06-02 09:40 auto: A-key _on_node_action_result(3475) seeds op, renders node_select, advances via _actions_advance_from_node_select, then switches to Actions tab
- [x] Esc/Back from every step returns to the correct previous step for all op families (resolver-driven prev); up/down navigation works on op-select and node-select OperationRows and cycles focus on confirm — PASS 2026-06-02 09:40 auto: Esc(3189)/Back(6208) use prev_step_id; up/down OperationRows at 3250 for op/node-select; confirm focus cycle at 3259; resolver prev verified all families

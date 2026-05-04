---
priority: medium
effort: medium
depends: [t745_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [745_1, 745_2, 745_3, 745_4]
created_at: 2026-05-04 22:24
updated_at: 2026-05-04 22:24
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t745_1] Launch ./.aitask-scripts/aitask_brainstorm.sh 635 — verify the five tabs at top read "(D)ashboard | (G)raph | (C)ompare | (A)ctions | (S)tatus".
- [ ] [t745_1] Verify footer no longer advertises tab letters d g c a s; q (Quit) remains visible.
- [ ] [t745_1] Press each of d, g, c, a, s — tabs still switch correctly (binding behavior unchanged, only show=False).
- [ ] [t745_2] On Compare tab footer, verify "r Regenerate" appears.
- [ ] [t745_2] Initial Compare tab hint Label reads "Press 'r' to (re)select nodes, 'D' to open full diff".
- [ ] [t745_2] Press r — CompareNodeSelectModal opens. Pick n000 + n001 — comparison renders.
- [ ] [t745_2] Press r again — modal reopens; pick a different pair — comparison replaces.
- [ ] [t745_2] Switch to Dashboard tab — "r Regenerate" no longer in footer.
- [ ] [t745_3] On Compare tab, equal-valued dimensions show value once in green, "← same" in dim green in the second cell.
- [ ] [t745_3] Differing-valued dimensions show colored word-level diff inside both cells (matching words dim, differing words highlighted with replace background).
- [ ] [t745_3] Similarity-score row at bottom of the table still renders.
- [ ] [t745_3] Standalone diffviewer launch (./.aitask-scripts/aitask_diffviewer.sh) still works after the helper rename.
- [ ] [t745_4] On Compare tab footer, verify "D Diff" appears.
- [ ] [t745_4] With no nodes picked, press D — warning notification appears, no screen pushed.
- [ ] [t745_4] After picking n000 + n001, press D — DiffViewerScreen pushes inside brainstorm. Color-coded diff visible.
- [ ] [t745_4] Inside diffviewer, m / u / v / n / p navigation keys all behave as expected.
- [ ] [t745_4] Press Escape — return to Compare tab with the dimension matrix still rendered.
- [ ] [t745_4] Switch to Dashboard tab — "D Diff" no longer in footer.

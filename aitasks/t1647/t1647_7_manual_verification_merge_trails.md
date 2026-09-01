---
priority: medium
effort: medium
depends: [t1647_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1647_1, 1647_2, 1647_3, 1647_4, 1647_5, 1647_6]
anchor: 1647
followup_kind: manual_verification
created_at: 2026-09-01 18:55
updated_at: 2026-09-01 18:55
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1647_1] `ait board` boots and By-Trail (`z`) renders the live trails exactly as before the lib promotion (visual parity spot check)
- [ ] [t1647_2] `./.aitask-scripts/aitask_trail_depth.sh validate aidocs/implementation_trail_examples/merged_trail.json --expect-depth deep` prints VALID; existing live trails still load in By-Trail
- [ ] [t1647_3] Live read-only smoke: `./.aitask-scripts/aitask_trail_merge.sh preflight -- art:trail-mobile-shadow-driving art:trail-mobile-shadow-driving-deep` emits RESULT_DEPTH:deep, 6 OVERLAP lines, no *_ONLY lines, one FOLDED_REF:1118|active
- [ ] [t1647_4] `/aitask-merge-trails trail-mobile` (approximate name) reaches the pick-the-base question (BASE_CANDIDATE flow) without performing any write; "no merge" is offered at the candidate step
- [ ] [t1647_5] Board flow: `ait board` → `z` → `s` (select trail) → `F` → picker excludes the active trail → confirm screen names survivor/retired/shared count → AgentCommandScreen shows `/aitask-merge-trails <base> <folded>`; Esc backs out cleanly at every stage; `F` hidden outside By-Trail, with no active trail, and with fewer than two trails
- [ ] [t1647_6] `cd website && hugo build --gc --minify` clean; new skill page + workflows "Merging Two Trails" section render with working links; Modal Dialogs table lists the four trail modals
- [ ] Divergent-pair merge (discriminating case): create two synthetic trails on a scratch task with partial entry overlap, different wave structures, and deep-only material on one side; run the full merge; verify shared entries deduped once, all base-only AND folded-only entries present and sensibly placed, wave ordinals/positions strictly increasing, deep-wins result retains the deep side's observations/relations/exclusions/evidence, narrative reconciled (not concatenated); retire the scratch trails afterwards
- [ ] Live t1118 merge (user scenario 1): merge art:trail-mobile-shadow-driving (lite) into art:trail-mobile-shadow-driving-deep's pair per deep-wins; folded lite trail retired (reference removed, manifest gone), By-Trail shows the merged trail, `ait artifact versions` shows the new version, merged_from records both sources
- [ ] Stale-base guard live check: launch a merge and, while the FINAL confirmation dialog is open, bump one source trail from a second terminal; confirm, and verify the post-confirmation guard catches the move and offers Reload/Overwrite/Abort
- [ ] Half-merged recovery: simulate an rm failure after a successful base update (e.g. temporarily break the folded owner's frontmatter), rerun the skill with the same pair, verify it offers ONLY completing the retirement (never re-authoring)
- [ ] Shared-reference retirement: give the folded trail a second referencing task (fold-transfer shape), run the merge, verify the confirmation enumerates BOTH owners, both references are removed, the manifest is gone, and the trail no longer appears in By-Trail discovery

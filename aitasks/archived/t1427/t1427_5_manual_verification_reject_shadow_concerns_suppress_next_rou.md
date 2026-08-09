---
priority: medium
effort: medium
depends: [t1427_4]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1427_1, t1427_2, t1427_3, t1427_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
created_at: 2026-08-05 17:22
updated_at: 2026-08-09 12:23
completed_at: 2026-08-09 12:23
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1427_1] bash tests/test_shadow_rejected.sh passes; shellcheck on aitask_shadow_rejected.sh clean — PASS 2026-08-09 12:00 auto: tests/test_shadow_rejected.sh 130/130; shellcheck clean apart from the repo-baseline SC1091 source notices (sibling aitask_shadow_context.sh has the same 3)
- [x] [t1427_1] audit-helper-whitelist aitask_shadow_rejected.sh reports no MISSING touchpoints — PASS 2026-08-09 12:00 auto: audit-helper-whitelist reports no MISSING; positive control on an unwhitelisted name emits 5 MISSING lines, so the empty result is a real clean
- [x] [t1427_1] Manual smoke: add/list/list --machine/remove/prune round-trip on a scratch task id; .aitask-shadow/ stays git-ignored (git status clean) throughout — PASS 2026-08-09 12:00 auto: add/list/list --machine/remove/prune round-trip on scratch id 9999 in the live repo; pipe-laden body round-trips, id r1 removed then re-add issued r3 (no reuse), prefix-less remove accepted, prune then PRUNED:absent; git status byte-identical to baseline throughout and git check-ignore confirms .gitignore:22
- [x] [t1427_1] Archive a scratch task that has a rejection store and confirm .aitask-shadow/<id>/ is pruned — PASS 2026-08-09 12:00 auto: tests/test_archive_shadow_prune.sh 26/26, plus a hands-on archive in a throwaway repo -- real aitask_archive.sh on scratch t42 with a seeded store returned COMMITTED, .aitask-shadow/42/ gone, decoy .aitask-shadow/77/ intact
- [x] [t1427_2] In minimonitor: press c on a shadow concern block, mark a concern with r (red mark + dimmed row), confirm; .aitask-shadow/<task_id>/rejected.md gains the canonical marker line — PASS 2026-08-09 12:09 auto: live end-to-end (real tmux shadow pane -> aitask_shadow_capture.sh -> parse_concerns -> real ConcernPickerModal keystrokes -> real subprocess -> real aitask_shadow_rejected.sh). r sets _state=rejected, renders [red]X[/] and the dimming .rejected class; confirming wrote .aitask-shadow/9001/rejected.md holding the canonical marker line verbatim with 'producer: picker', the non-rejected concern absent, and the '1 concern(s) rejected - suppressed next round' toast
- [x] [t1427_2] Re-open the picker, press R: rejected-store view lists the persisted entry; un-reject it and confirm; entry removed from the store file — PASS 2026-08-09 12:09 auto: same live harness - re-opened picker pre-fetched entry r1 with the stored marker line, R opened RejectedStoreModal listing exactly that entry, space+Enter returned to the intact picker, the store still held the entry at that point (staged, not written), and confirming the picker removed it leaving a header-only store plus the '1 concern(s) un-rejected' toast
- [x] [t1427_2] Same reject/un-reject flow in full monitor (non-narrow layout) — PASS 2026-08-09 12:09 auto: same live harness against the real MonitorApp - picker opened non-narrow (narrow=False), r rejected, confirm wrote .aitask-shadow/9002/rejected.md with the canonical marker line, R listed it, un-reject + confirm removed it. Monitor's global r (refresh) / R (restart) never fired under the modal
- [x] [t1427_2] a and A no longer do anything in the picker and are absent from both help lines; help stays readable at 24-col width — PASS 2026-08-09 12:04 auto: behavioral probe on the real ConcernPickerModal -- a and A leave every row's _state untouched while r/space do change it (positive control), no toggle_all/copy_all left in the tree, neither help string names a/A; render-level sweep at 40/30/24 cols shows the full key line unclipped (24 cols wraps to 3 rows, all readable); test_concern_picker_modal.py 47/47
- [x] [t1427_2] With a pane whose window has no task id (e.g. agent-explore-*), rejecting shows the visible "Rejections not persisted — no task id" notice and writes nothing — PASS 2026-08-09 12:09 auto: same live harness with window name agent-explore-scratch - task id resolves to None, picker got store_unavailable=True, R warned 'No task id for this pane - rejection store unavailable' instead of opening a list, and confirming a rejection produced the warning-severity 'Rejections not persisted - no task id for this pane' with the store root byte-identical (nothing written)
- [x] [t1427_3] Live two-round suppression: reject a concern, trigger a fresh shadow review round, confirm the block omits it and the prose reports "Suppressed N previously-rejected concern(s)." — PASS 2026-08-09 12:16 auto: two real shadow rounds by fresh agents following plan-challenge.md against the same scratch plan, differing ONLY in store contents. Round 1 (empty store) reported 'NO_REJECTIONS ... nothing was suppressed' and raised 6 concerns incl. '[medium | Step 4: cleanup thread]'. That marker line was then rejected via the helper. Round 2 read the printed body, reported verbatim 'Suppressed 1 previously-rejected concern(s).' and its block omits the cleanup-thread concern while the other 5 return. Round 1's explicit no-suppression statement is the negative control
- [x] [t1427_3] Un-reject the same concern, trigger another round, confirm it returns — PASS 2026-08-09 12:19 auto: after 'remove 9500 r1' drained the store, a third fresh shadow round reported 'list 9500 -> NO_REJECTIONS, so no concerns were suppressed' and the cleanup-thread concern RETURNED as '[medium | Step 4 sweep thread]'. It came back reworded (round 1 framed it via test-collection imports, round 3 via daemon=True and gunicorn preload/autoreload forking) - same substance, different words, which is the reworded-match property round 2 had to satisfy semantically to suppress it
- [x] [t1427_3] Run a shadow round for a task with no resolvable task id and confirm the output states suppression was skipped — PASS 2026-08-09 12:12 auto: real shadow round via a fresh agent following plan-challenge.md with NO task id in launch args and window agent-explore-scratch. It reported verbatim: 'No task id was passed to me and the followed window name (agent-explore-scratch) does not match the resolvable pattern, so I could not consult the rejection store - suppression was skipped; all concerns below are fresh.' and emitted all 5 concerns (fail-open), never treating the failure as 'nothing was rejected'
- [x] [t1427_4] hugo build --gc --minify clean; the four updated pages read coherently and no picker a/A shortcut references remain — PASS 2026-08-09 12:04 auto: hugo build --gc --minify rc=0 (233 pages; only pre-existing Docsy deprecation warnings). Sweep 28->25 hits, exactly the 3 picker lines gone, sole monitor hit is the auto-switch a (intentional residual). All 7 inbound anchors resolve against real ids in the built HTML incl. the new reject-a-concern slug. reference.md changed only the c row - no new global r/R. Documented glyphs/toasts/report line match source verbatim

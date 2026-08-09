---
priority: medium
effort: medium
depends: [t1427_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1427_1, t1427_2, t1427_3, t1427_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
created_at: 2026-08-05 17:22
updated_at: 2026-08-09 12:01
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
- [ ] [t1427_2] In minimonitor: press c on a shadow concern block, mark a concern with r (red mark + dimmed row), confirm; .aitask-shadow/<task_id>/rejected.md gains the canonical marker line
- [ ] [t1427_2] Re-open the picker, press R: rejected-store view lists the persisted entry; un-reject it and confirm; entry removed from the store file
- [ ] [t1427_2] Same reject/un-reject flow in full monitor (non-narrow layout)
- [ ] [t1427_2] a and A no longer do anything in the picker and are absent from both help lines; help stays readable at 24-col width
- [ ] [t1427_2] With a pane whose window has no task id (e.g. agent-explore-*), rejecting shows the visible "Rejections not persisted — no task id" notice and writes nothing
- [ ] [t1427_3] Live two-round suppression: reject a concern, trigger a fresh shadow review round, confirm the block omits it and the prose reports "Suppressed N previously-rejected concern(s)."
- [ ] [t1427_3] Un-reject the same concern, trigger another round, confirm it returns
- [ ] [t1427_3] Run a shadow round for a task with no resolvable task id and confirm the output states suppression was skipped
- [ ] [t1427_4] hugo build --gc --minify clean; the four updated pages read coherently and no picker a/A shortcut references remain

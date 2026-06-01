---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t826_1, t826_2, t826_3]
created_at: 2026-05-31 12:26
updated_at: 2026-05-31 12:26
boardidx: 120
---

Carry-over of deferred manual-verification items from t826_4. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t826_1] From /home/ddt/Work/aitasks_mobile: `ait projects add` — DEFER 2026-05-31 11:12 auto-blocked: ait projects add from aitasks_mobile fails (sibling runs ait 0.19.2, predates projects verb); entry already exists. Upgrade sibling then re-run.
- [ ] [t826_1] From aitasks_mobile: `ait create --batch --project aitasks --name cross_repo_test --type chore --priority low --effort low --commit` — DEFER 2026-05-31 11:40 CARRY OVER (user choice). Real attempt failed anyway: ait create --batch --project ... --commit -> 'Error: Batch mode requires --desc or --desc-file'; sibling also on old ait 0.19.2. Earlier 't864 created' was fabricated glitch output.
- [ ] [t826_2] Select inactive project (`ait monitor` → `j` switcher → highlight `aitasks_mobile` → Enter) — tmux session spawns + switcher teleports. RE-VERIFY: in archived t826_4 this was marked pass on glitch-fabricated output but was NOT reproduced (detached-driver test spawned no session; the select→spawn→teleport flow appears to need an ATTACHED client). Run from a real attached tmux session. NOTE: switcher *listing* of the inactive project (item 14) and `ait monitor` no-leak (item 16) WERE verified.
- [ ] [t826_3] `cd website && hugo build --gc --minify` — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [ ] [t826_3] `cd website && ./serve.sh` — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [ ] [t826_3] Multi-project page contains all 7 required sections (Why / project: block / ait projects / aitask_create --project / cross-repo notation / TUI switcher behavior / Recipe) — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [ ] [t826_3] Multi-project page explicitly states `ait monitor` is unchanged (live sessions only) — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [ ] [t826_3] Cross-repo notation documented with no-`t` form as preferred default (`aitasks#835_3`), `aitasks#t835_3` also accepted — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [ ] [t826_3] Cross-link from `aidocs/cross_repo_references.md` to the website page works — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet

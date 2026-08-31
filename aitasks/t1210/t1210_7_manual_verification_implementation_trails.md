---
priority: medium
effort: medium
depends: [t1210_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1210_2, t1210_3, t1210_4, t1210_5, t1210_6]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: manual_verification
created_at: 2026-07-22 16:17
updated_at: 2026-08-31 19:22
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1210_3] Create a trail interactively via /aitask-trail on a real task: scope question offered, proposal rendered with full narrative (waves, rationale, observations), single confirmed write; `ait artifact ls <owner>` shows the art:trail-* handle — PASS 2026-08-31 19:22 verified manually by the user (checked prior to this run); auto-verification had deferred it as interactive-only
- [x] [t1210_3] Refresh flow: archive one member task, run /aitask-trail --refresh <handle>; drift reasons named, diff-style summary shown, new version appears in `ait artifact versions <handle>` — PASS 2026-08-31 19:22 verified manually by the user (checked prior to this run); auto-verification had deferred it as interactive-only
- [x] [t1210_2] Drift check is read-only: run the drift verb twice; trail artifact bytes unchanged; boardidx-only board move does NOT flip the trail to stale — PASS 2026-08-31 18:30 auto: drift run twice on art:trail-shadow-review-loop -> identical CURRENT/DIGEST:fe9b43e63208bff5; blob+manifest store sha256 unchanged (1c3c25b6...); boardidx 1094->999999 kept CURRENT with identical digest; negative control (status Ready->Postponed) correctly flipped to STALE/status_changed; task file restored byte-identical, git clean
- [x] [t1210_4] By-Trail view: enter the view, select each of several trails, verify wave columns, classification/confidence badges, completion strike-through, and the stale banner after a member status change — PASS 2026-08-31 18:41 auto: live board in tmux. 'z' entered By-Trail; picker listed all 4 trails with owner/kind/freshness/overlap. Opened 'Shadow review-loop automation' (11 waves) and 'Gate framework landing order' (5 waves) - each rendered its own W<n> columns with titles+counts. Badges show all five glyphs with confidence (hard_prerequisite/preferred_predecessor/core/coordination_only/optional x high/medium). Strike-through pinned at SGR level: landed entries (#1294,#1289,#1427,#1159_1) carry SGR 9, live entries (t1159,t1564,t1506) do not. Stale banner: after flipping member t1503 Ready->Postponed and pressing d, header showed '(warn stale: 1)'; file restored, git clean
- [x] [t1210_4] Error states: temporarily rename the artifact blob/manifest; By-Trail view shows the fail-closed error card and offers versions fallback; restore afterwards — PASS 2026-08-31 18:47 auto: both halves. Blob renamed away -> picker degraded that row to 'owner t1118 · ? · unreadable · ?' (others still current); opening it gave header 'trail unavailable' and the fail-closed card naming the exact missing hash + local backend, PLUS the versions fallback ('Recorded versions (ait artifact versions ...)' with * on current) and 'Press s to select another trail'. Manifest renamed away -> same fail-closed card with 'no manifest for art:...'; no versions list there, correctly, since the manifest IS the version list. Both restored: blob sha256 matches original, no stray .bak files, all 4 handles resolve
- [x] [t1210_4] Launch seams: create/refresh actions from a task card, a By-Topic lane header, and the By-Trail view all open AgentCommandScreen with the expected /aitask-trail arguments — PASS 2026-08-31 18:45 auto: all three seams opened AgentCommandScreen (title 'Implementation Trail') with the expected args, no launch. Task card (t1405 focused) -> '/aitask-trail 1405'. By-Topic lane header (lane t635, focused card was t1393) -> '/aitask-trail 635' i.e. the topic ROOT not the card, as documented. By-Trail view with the gates trail open -> '/aitask-trail --refresh art:trail-gates-framework-landing'. Args are shell-escaped in the command line
- [x] [t1210_5] Move commands: `m` moves a focused entry to a chosen column; `M` moves a whole wave preserving wave order; ghost (archived/cross-repo) cards are excluded with a visible reason — PASS 2026-08-31 19:03 auto: live board, gates trail. 'm' on focused t1417 opened the column picker (correctly OMITTING its current column bug_fixes) and moved ONLY t1417 to tests - other four unchanged. 'M' on W1 (17 entries: 5 live parents + 12 ghosts) opened the review list holding exactly the 5 in wave order and moved them to bug_fixes with boardidx 1024/2048/3072/4096/5120 = wave order 1417,1438,1437,1473,1534 preserved. Ghost exclusion visible: toast 'Skipping 12 ghost: aitasks#635_27, aitasks#1264, ...'; child exclusion on an all-child wave: 'Nothing movable in this wave - 3 child: aitasks#635_31, ...'. M is also binding-gated off on a focused ghost. All 5 files restored from snapshot (only boardcol/boardidx had changed)
- [x] [t1210_5] Passive report bridge: after `M` into a column, run the board Work Report flow on that column; report contains exactly those tasks in board order — PASS 2026-08-31 19:03 auto: after the M into bug_fixes, the shared report seam aitask_work_report_gather.sh --columns bug_fixes emitted COLUMN:bug_fixes|bug fixes plus exactly 5 TASK: rows - 1417,1438,1437,1473,1534 - in board order (boardidx 1024..5120), no extras and none missing. Passive bridge confirmed: the report reads the column only, never the trail artifact. After restore the same command returns NO_TASKS
- [x] [t1210_6] Docs render: open the Implementation Trails workflow page in a browser and confirm the five classification glyphs (◆ ▲ ● ⇄ ○) all render as distinct characters rather than tofu boxes, and that the classification table is readable at a normal window width — PASS 2026-08-31 18:37 auto: real Chromium 151 render of /docs/workflows/implementation-trails/ via hugo server; magnified crop of the Glyph column shows all five (diamond, filled triangle, filled circle, two-arrow, hollow circle) as distinct correct characters, no tofu boxes; table unclipped and no horizontal overflow at 1024/1280/1440 (tbl 557/627/712px inside 697/783/890px column)
- [x] [t1210_6] Docs navigation: from the board Feature Reference page, the By-Trail 'Moving a wave into a column' cross-link scrolls to that section; the workflow page's links to Work Report and Topic anchoring both resolve — PASS 2026-08-31 18:37 auto: CDP-driven navigation. Board reference #moving-a-wave-into-a-column scrolled to scrollY=11211 with the H5 88px from viewport top (inViewport true); negative control without the fragment gave scrollY=0, target 11299px below fold. Workflow-page links resolve to real pages: work-report -> 'Reporting Work to Managers', topic-anchoring -> 'Topic anchoring' (both HTTP 200, correct h1)

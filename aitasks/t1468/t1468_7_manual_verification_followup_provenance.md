---
priority: medium
effort: medium
depends: [t1468_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1468_3, t1468_4, t1468_5]
assigned_to: dario-e@beyond-eye.com
anchor: 1468
followup_kind: manual_verification
created_at: 2026-08-10 16:35
updated_at: 2026-08-14 00:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1468_3] Launch `ait board` in a real terminal. A follow-up task is identifiable at first sight by BOTH colour and shape, without reading the task name. — PASS 2026-08-13 23:57 auto: live ait board in tmux (200x50, real terminal, real repo). SGR-walked capture proves BOTH axes: ▲=#ffff00 risk_mitigation, ◇=#00ffff manual_verification, ◈=#ff00ff review_finding, ▼=#ff0000 upstream_defect -- distinct shape AND distinct colour, in a leading gutter before the task number.
- [x] [t1468_3] Scan a kanban column containing a mix of follow-up and non-follow-up cards — the follow-ups stand out as a group, not one at a time. — PASS 2026-08-13 23:57 auto: live 'Unsorted / Inbox' column is genuinely mixed -- gutter reads blank(t1405)/▲(t1411)/blank(t1412)/blank(t1413)/◇(t1415) at a fixed column offset, so scanning the gutter surfaces the follow-ups as a group rather than one at a time.
- [x] [t1468_3] Two different kinds (e.g. risk_mitigation vs upstream_defect) are distinguishable from each other, not merely distinguishable from "no kind". — PASS 2026-08-13 23:57 auto: two kinds side by side and mutually distinguishable -- ▲ #ffff00 (t1411) vs ◇ #00ffff (t1415) in the SAME column; ◈ #ff00ff (t804) vs ▼ #ff0000 (t879) in Now. Differ in shape and colour, not merely from 'no kind'.
- [x] [t1468_3] Narrow the terminal to ~60 columns. The glyph still renders as a single cell, does not wrap, and does not push the task number or title off-screen. — PASS 2026-08-13 23:57 auto: live board resized to 60x40. '☐ ▲ t1411 shadow learner pane id' -- glyph is one cell, still #ffff00, no wrap; task number and title intact, continuation lines align under the title. ◇ still #00ffff at 60 cols.
- [x] [t1468_3] The glyph does not collide with or shift the ☑/☐ mark on markable kanban cards, and still appears on TopicColumn and child cards, which have no mark. — PASS 2026-08-13 23:57 auto: ☐ sits at an identical column offset with and without a glyph (☐ t1405 vs ☐ ▲ t1411) -- the glyph takes its own gutter, never shifts the mark. Mark-less surfaces still show it: By-Topic TopicColumn cards (▲ t1157, ▲ t1288, ▼ t1356) and the In-Flight CHILD card ◇ t1468_7 (dashed border, no mark).
- [x] [t1468_3] By-Topic view: follow-ups show the glyph and cluster with their topic root. — PASS 2026-08-13 23:57 auto: live By-Topic -- ▲ #ffff00 x4 and ▼ #ff0000 painted on topic cards; follow-ups cluster under their topic root (t1288/t1347/t1356 under the t1111 root; ▲ t1157 is itself a root).
- [x] [t1468_3] In-Flight view: an in-flight follow-up shows the glyph. — PASS 2026-08-13 23:57 auto: live In-Flight -- ▼ t1515 (#ff0000), ↻ t887 (#00ffff) and ◇ t1468_7 (#00ffff) all glyphed; t1505_2 (no kind) correctly bare.
- [x] [t1468_3] By-Trail view: a trail card for a marked task shows the glyph; a trail GHOST card shows no glyph and renders without visual breakage. — PASS 2026-08-14 00:02 auto: real TrailTaskCard/TrailGhostCard, composited. Marked card '▼ t42 marked' glyph coloured (#f4005f under the probe theme -- Textual resolves named colours per theme, so no static hex is pinnable; distinct from the #e0e0e0 default text). Landed card '▲ ✔ t43' -- glyph correctly PRECEDES the ✔. Unmarked 't44 plain' bare (neg control). GHOST 'otherproj#7' shows NO glyph, renders its 👻 cross-repo line + classification badge cleanly, raises nothing. Classification glyphs (◆●○) stay on .trail-badges, never sharing the title row. NOTE: the LIVE By-Trail surface currently reads '✗ unreadable' for both artifacts (schema 1.0.0 vs 1.1.0) until t1508's refresh.
- [x] [t1468_3] Collapse a group containing follow-ups: the GroupHeader roll-up reports them, and the count is correct. — PASS 2026-08-14 00:01 auto: real KanbanApp on a fixture tree; collapsed GroupHeader label = '▸ grp with (4) · ▲2 ◈1' -- reports the follow-ups with correct per-kind counts (2 risk_mitigation + 1 review_finding of 4 members, 1 plain), coloured ▲ yellow / ◈ magenta, in canonical FOLLOWUP_KINDS order.
- [x] [t1468_3] Collapse a group containing NO follow-ups: no roll-up text is shown (negative control). — PASS 2026-08-14 00:01 auto: NEGATIVE CONTROL -- a collapsed group whose 2 members carry no kind renders '▸ grp plain (2)' with NO roll-up segment and no coloured glyph runs.
- [x] [t1468_3] A task with a hand-edited MALFORMED followup_kind (a list, an int, an empty or whitespace-only string) renders NO glyph at all and does not crash the board. — PASS 2026-08-14 00:01 auto: all five malformed forms (list ['risk_mitigation'], int 42, bool True, empty '', whitespace '   ') render NO glyph -- card-windowed composited read gives glyphs=[] colours={} for each -- and the board booted and rendered every card without raising.
- [x] [t1468_3] A task with an UNKNOWN non-empty followup_kind (e.g. a typo like `risk_mitgation`) renders the `·` fallback, UNCOLOURED — it must stay visible, since a value that silently vanishes reads as "not a follow-up". (Decided in t1468_3; this is deliberately different from the malformed case above.) — PASS 2026-08-14 00:01 auto: 'risk_mitgation' typo renders '☐ · t9240' -- the · IS present (not vanished). Uncoloured proven against in-app ground truth, not a hex guess: · = #e0e0e0, byte-identical to the ordinary card title text on the same card (#e0e0e0), while a valid kind's ▼ on a sibling card is #ff0000. Deliberately distinct from the malformed case, which renders nothing.
- [x] [t1468_3] Collapse a group containing an unknown kind: the roll-up tallies it last, under `·`. — PASS 2026-08-14 00:01 auto: collapsed group with a typo kind + a valid one renders '▸ grp unknown (2) · ◇1 ·1' -- the unknown is tallied LAST under ·, and only ◇ carries a colour span (cyan); the · tally is uncoloured.
- [x] [t1468_4] `ait ls -v` shows the kind on a marked task and shows nothing extra on an unmarked one. — PASS 2026-08-13 23:49 auto: ait ls -v shows 'Follow-up: verification_failure' on t1499 and no Follow-up segment on t1509; Type: always present
- [x] [t1468_4] `ait ls --followup-kind risk_mitigation` returns a plausible, non-zero set; spot-check two of the returned tasks are genuinely risk mitigations. — PASS 2026-08-13 23:49 auto: --followup-kind risk_mitigation -> 60 tasks; spot-checked t1508/t1088/t1195 all carry 'Risk-mitigation ("after") follow-up for tNNN' prose
- [x] [t1468_4] `ait ls --type bug` filters correctly and composes with `-l` and `--followup-kind`. — PASS 2026-08-13 23:49 auto: --type bug -> 63 lines, 0 non-bug; composes with --followup-kind (39 bug+upstream_defect, 0 feature+upstream_defect) and -l (24->12->8); no-kind+kinds partition = 111+159 = 270 = all
- [x] [t1468_4] Filters behave in `--tree`, `--children N` and `--all-levels` modes, not only the default listing. — PASS 2026-08-13 23:49 auto: --followup-kind/--no-followup-kind correct in --children 1157, --tree (indented form kept) and --all-levels; all-levels partition 212+177 = 389 = all
- [x] [t1468_4] An unknown long flag still fails with the help text (the arg-parse case was not accidentally loosened). — PASS 2026-08-13 23:49 auto: --nope -> rc=1 'Unknown argument' + full help; bad values die distinctly (invalid-value vs cannot-resolve); mutual exclusion enforced
- [x] [t1468_4] Run `/aitask-pick` far enough to see the Step 2c selection options: the kind is visible in the option descriptions and helps distinguish new work from follow-ups. — PASS 2026-08-13 23:50 auto: ran pick Steps 2a/2b live; first 2c page = t1499 (verification_failure), t1508 (risk_mitigation), t1509 (none) -- kind visible per option without opening a file; SKILL.md 2b/2c mandate it
- [x] [t1468_5] Minimonitor sibling chooser shows the kind for ready siblings. — PASS 2026-08-13 23:54 auto: real TaskInfoCache.find_ready_siblings(1159) over the real repo returns the 4-tuple with the kind; real ChooseSiblingModal composited screen paints '◇' #00ffff (manual_verification, t1159_5) and '◈' #ff00ff (review_finding, t1159_7) while unmarked siblings t1159_4/t1159_6 show a bare gutter and no glyph. Holds in the narrow ~40col minimonitor variant too (single cell, no wrap, t<id>+title still readable).
- [x] [t1468_5] Work report output is not corrupted by the added TASK: field — column/task rows read correctly and the board `w` flow round-trips a reviewed selection with membership and order intact. — PASS 2026-08-13 23:52 auto: 286/286 TASK rows have NF=10 (kind at pos 9, path last, all paths resolve); 0 mismatches vs frontmatter; 8 COLUMN rows fine; w-flow round-trip EXACT for membership AND order, with ERROR:task_order_changed on a scrambled request and ERROR:unknown_task on a foreign id
- [skip] [t1468_5] After the trail schema bump, `art:trail-gates-framework-landing` and `art:trail-shadow-review-loop` report a clean invalid-trail error (not a confusing STALE), and refresh successfully to 1.1.0. — SKIP 2026-08-13 23:51 Covered verbatim by t1508 (Ready, high, dedicated to this refresh; t1470 depends on it) -- duplicating it here would leave t1508 pointless. Verified the half that does not need a refresh: BOTH live trails reject cleanly as 'INVALID:$.schema_version|const|expected 1.1.0, got 1.0.0' + 'ERROR:invalid_trail:1' -- a named const-rule rejection, never a false STALE.
- [skip] [t1468_5] A refreshed trail visibly contains followup_kind in its stored entry snapshots — inspect the artifact, do not rely on validation passing. — SKIP 2026-08-13 23:51 Covered verbatim by t1508 checklist items 4-5 (PRODUCER present case + absent case), which are stricter than this item. Deferring the end-to-end producer inspection to that task.

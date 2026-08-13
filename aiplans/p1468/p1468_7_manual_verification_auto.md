---
Task: t1468_7_manual_verification_followup_provenance.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_8_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_7 — Manual verification of follow-up provenance (autonomous auto-execution)

Retroactive record of the autonomous auto-verification run over t1468_7's
23-item checklist, covering the surfaces landed by t1468_3 (board card glyph),
t1468_4 (`ait ls` / pick) and t1468_5 (work report, sibling chooser, trail).

**Outcome: 21 pass, 2 skip, 0 fail, 0 deferred.**

## Corpus state at verification time

The t1468_6 backfill had landed: 191 active tasks carry a `followup_kind`
(64 `risk_mitigation`, 63 `manual_verification`, 47 `upstream_defect`,
8 `carry_over`, 5 `verification_failure`, 4 `review_finding`; `qa_test_gap`
and `docs_gap` have creation seams but no tasks yet). That made the live
surfaces non-vacuous — a mixed kanban column exists naturally.

## Method

Three tiers, chosen per item:

1. **Live real terminal** (items 1-7) — the real `ait board` booted under a
   dedicated tmux socket (`-L t1468v`, `TMUX` unset so an ambient session
   cannot leak in) against the real repo. Colour was measured by walking the
   SGR state machine over `capture-pane -e`, so every glyph is attributed to
   the foreground actually in effect at that cell. Reading the plain capture
   alone would have proven shape but not colour, and the acceptance criterion
   is both.
2. **Fixture + real widgets** (items 8-13) — items needing frontmatter the real
   repo must never contain (a malformed / unknown `followup_kind`) or a group
   topology it does not have. Run on a synthetic tree via
   `tests/lib/board_fixture.py`, but against the **real** board module, real
   `Task` objects and real `GroupHeader` / `TaskCard` / `TrailTaskCard` /
   `TrailGhostCard` widgets, read off the compositor.
3. **CLI / real class drive** (items 14-21) — `aitask_ls.sh` and
   `aitask_work_report_gather.sh` invoked directly; the sibling chooser driven
   through the real `TaskInfoCache` over the real repo into the real
   `ChooseSiblingModal`.

## Execution Log

### Items 1-3 — glyph identifiable by colour AND shape; mixed column; two kinds
- Approach: live board, 200x50, SGR-walked capture.
- Measured: `▲`=#ffff00 (risk_mitigation), `◇`=#00ffff (manual_verification),
  `◈`=#ff00ff (review_finding), `▼`=#ff0000 (upstream_defect).
- The `Unsorted / Inbox` column is genuinely mixed; its gutter reads
  blank(t1405) / ▲(t1411) / blank(t1412) / blank(t1413) / ◇(t1415) at a fixed
  column offset, so scanning the gutter surfaces the follow-ups as a group.
- Two kinds are mutually distinguishable, not merely distinguishable from "no
  kind": ▲ vs ◇ in the same column; ◈ vs ▼ in `Now`.
- Verdict: **pass** (×3).

### Item 4 — narrow width
- Resized the live window to 60x40. `☐ ▲ t1411 shadow learner pane id` — the
  glyph stays one cell and still paints #ffff00; the task number and title are
  not pushed off; continuation lines align under the title.
- Verdict: **pass**.

### Item 5 — no collision with the ☑/☐ mark; mark-less surfaces
- `☐` sits at an identical offset with and without a glyph (`☐ t1405` vs
  `☐ ▲ t1411`) — the glyph occupies its own gutter and never shifts the mark.
- Mark-less surfaces confirmed live: By-Topic `TopicColumn` cards (▲ t1157,
  ▲ t1288, ▼ t1356) and an In-Flight **child** card (◇ t1468_7, dashed border).
- Verdict: **pass**.

### Items 6-7 — By-Topic, In-Flight
- By-Topic: ▲ #ffff00 ×4 and ▼ #ff0000 painted; follow-ups cluster under their
  topic root.
- In-Flight: ▼ t1515 (#ff0000), ↻ t887 (#00ffff), ◇ t1468_7 (#00ffff); the
  kind-less t1505_2 correctly bare.
- Verdict: **pass** (×2).

### Item 8 — By-Trail card + ghost card
- The live surface could **not** serve this: both stored artifacts are at
  schema 1.0.0 against a 1.1.0 `const`, so By-Trail reads `✗ unreadable` for
  each until t1508's refresh.
- Drove the real widgets instead. Marked card `▼ t42 marked` — glyph coloured
  (#f4005f under the probe app's theme; Textual resolves named colours through
  the active theme, so no static hex is pinnable — what matters is that it
  differs from the #e0e0e0 default text). Landed card `▲ ✔ t43` — the follow-up
  glyph correctly **precedes** the landed ✔. Unmarked `t44 plain` bare.
  Ghost `otherproj#7` shows no glyph, renders its 👻 cross-repo line and
  classification badge cleanly, and raises nothing.
- The classification glyphs (◆ ● ○) stay on `.trail-badges`, never sharing the
  title row with the follow-up glyph — the `▲` ambiguity t1468_3 accepted is
  confirmed harmless.
- Verdict: **pass**.

### Items 9, 10, 13 — collapsed-group roll-up
- Real `KanbanApp` on a fixture tree, real `Task` members, headers collapsed.
- Item 9: `▸ grp with (4) · ▲2 ◈1` — correct per-kind counts (2 + 1 of 4
  members, 1 plain), coloured ▲ yellow / ◈ magenta, canonical order.
- Item 10 (negative control): a group of 2 kind-less members renders
  `▸ grp plain (2)` — no roll-up segment, no coloured runs.
- Item 13: `▸ grp unknown (2) · ◇1 ·1` — the unknown kind is tallied **last**
  under `·` and is uncoloured; only ◇ carries a colour span.
- Verdict: **pass** (×3).

### Item 11 — malformed values
- Five forms seeded: list `['risk_mitigation']`, int `42`, bool `True`, empty
  `""`, whitespace `"   "`.
- Card-windowed composited read returns `glyphs=[] colours={}` for every one,
  and the board booted and rendered all cards without raising.
- Verdict: **pass**.

### Item 12 — unknown non-empty value
- `followup_kind: risk_mitgation` (typo) renders `☐ · t9240` — the `·` is
  present, not vanished.
- "Uncoloured" was pinned against **in-app ground truth** rather than a hex
  guess: on the same card the `·` is #e0e0e0 and the ordinary title text is
  #e0e0e0 — identical — while a valid kind's `▼` on a sibling card is #ff0000.
  The first attempt read colours strip-wide and mis-attributed a neighbouring
  column's glyph; the read was narrowed to the card's x-window before this was
  concluded.
- Verdict: **pass**.

### Items 14-18 — `ait ls`
- Display: `t1499` shows `Follow-up: verification_failure`, `t1509` shows no
  `Follow-up:` segment; `Type:` always present.
- `--followup-kind risk_mitigation` → 60 tasks; three spot-checks (t1508,
  t1088, t1195) all carry `Risk-mitigation ("after") follow-up for tNNN`.
- `--type bug` → 63 lines, 0 non-bug. Composes with `--followup-kind`
  (39 bug+upstream_defect; 0 feature+upstream_defect as a negative control) and
  with `-l` (24 → 12 → 8).
- Partitions exactly: parents 111 no-kind + 159 kinds = 270 = all; all-levels
  212 + 177 = 389 = all.
- Filters behave in `--children`, `--tree` (indent preserved) and
  `--all-levels`.
- `--nope` → rc=1, `Unknown argument` + full help. Bad values die distinctly
  ("Invalid follow-up kind: bogus" vs "cannot resolve the follow-up kind
  vocabulary"), and `--followup-kind` with `--no-followup-kind` is refused.
- Verdict: **pass** (×5).

### Item 19 — `/aitask-pick` Step 2c
- Ran pick Steps 2a/2b live. The first Step 2c page is t1499
  (`verification_failure`), t1508 (`risk_mitigation`), t1509 (none) — the kind
  is visible per option without opening a file, and the rendered skill mandates
  it at both 2b and 2c.
- Verdict: **pass**.

### Item 20 — sibling chooser
- Real `TaskInfoCache.find_ready_siblings("1159")` over the real repo returns
  the widened 4-tuple carrying the kind.
- Real `ChooseSiblingModal`, composited: `◇` #00ffff on t1159_5
  (manual_verification) and `◈` #ff00ff on t1159_7 (review_finding); the two
  kind-less siblings show a bare gutter. Holds in the narrow ~40-col
  minimonitor variant — single cell, no wrap, `t<id>` and title still readable.
- Verdict: **pass**.

### Item 21 — work report
- All 286 `TASK:` rows have exactly 10 fields; the kind is at position 9 and
  the path stays last and always resolves to a real file.
- Cross-checked every row's field 9 against its file's frontmatter: **0
  mismatches**. Values are only real kinds or `unknown` — no `invalid` leaked.
- The `w`-flow round-trip is exact for membership **and** order, and is
  integrity-checked rather than silently re-sorted: a scrambled request returns
  `ERROR:task_order_changed`, a foreign id returns `ERROR:unknown_task`.
- Verdict: **pass**.

### Items 22-23 — live trail refresh + producer inspection (SKIPPED)
- Both are covered **verbatim, and more thoroughly**, by **t1508**
  (`refresh_and_verify_live_trails`) — Ready, high priority, whose 7-item
  checklist includes the present-case and absent-case producer inspections that
  are items 22-23 here. t1470 depends on t1508. Running the refresh here would
  have duplicated that task and left it pointless.
- The half of item 22 that needs no refresh **was** verified: both live
  artifacts reject cleanly as
  `INVALID:$.schema_version|const|expected '1.1.0', got '1.0.0'` followed by
  `ERROR:invalid_trail:1` — a named `const`-rule rejection, never a false
  `STALE`. That is exactly what p1468_5's `trail_v1_clean_rejection_fixture`
  pre-phase mitigation was written to guarantee.
- Verdict: **skip**, with the reason recorded on each item.

## Cleanup

- tmux session and its dedicated server (`-L t1468v`) killed.
- Both fixture trees removed by their registered cleanups; cwd restored.
- Scratchpad probes left under the session scratchpad; nothing written outside
  it except this plan and the task file's checklist annotations.
- **The real repo was never seeded with a malformed or unknown
  `followup_kind`** — every such value lived only in a temporary fixture tree.

## Findings

No defects. Two observations worth carrying forward:

- **`docs_gap` and `qa_test_gap` have zero tasks**, so their glyphs (`▤` #808080
  and `◐` magenta) are the only two of the eight never exercised against real
  data here. Both are covered by the fixture-level per-kind render guard in
  `tests/test_board_followup_glyph.py`.
- **The live By-Trail surface is degraded until t1508 runs.** It fails
  gracefully (`✗ unreadable` in the trail picker, no crash), which is the
  correct behaviour for an invalid document, but anyone opening By-Trail before
  the refresh will see it.

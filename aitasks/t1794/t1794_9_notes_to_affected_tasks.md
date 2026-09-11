---
priority: medium
effort: low
depends: [1794_1]
issue_type: chore
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 9 of t1794. Every pending task that cites the board mono-file, its line
numbers, `KanbanApp` / `TaskManager` / `TaskDetailScreen` internals, or the
By-Trail screen is affected by the split: their line anchors go stale and, for
a few, their approach changes (t1647_5 adds a command inside the By-Trail
view whose code now lives in `board_trail_screen.py` / `board_trail_view.py`;
t1613 is the duplicate-module-identity hazard the parent's C1/C2 guards
address). This child sends each of them a durable `ait note`. It depends on
child 1 only (the guards and file map are settled once child 1 lands) and
runs independently of the extraction chain.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— "Target file map", C1–C3, child 9 section; `CLAUDE.md` "Sending Notes to
Other Tasks"; the `/aitask-note` skill.

## Key files to modify

- No source files. Notes are appended to the target task files by
  `./ait note` (committed on the task-data branch by the helper).
- This child's plan records every `NOTE_APPENDED:<id>|<path>` line.

## Reference files for patterns

- `.claude/skills/aitask-note/SKILL.md` — composition, hedging, `--with-live`.
- Memory-derived rules already in the parent plan: a note carries context
  about work that exists, never work itself; re-check that a target still
  exists (tasks archive mid-session) before sending; `LIVE_NONE:` after
  `NOTE_APPENDED:` is success.

## Implementation plan

1. **Re-derive the target list** at implementation time (the list moves):
   ```bash
   grep -lE 'aitask_board|ait board|By-Trail|bytrail|TrailDetailScreen|TrailSelectScreen|KanbanApp|TaskManager|TaskDetailScreen' aitasks/*.md aitasks/t*/*.md | grep -v t1794
   ```
   (93 files at planning time). Split into (a) trail-subsystem tasks
   (t1647, t1647_4, t1647_5, t1647_6, t1647_7, t1470, t1543, t1526, t1372,
   t1439, t1514, t1645, t1569, t1569_7, t1634, t1261, t1296 at planning
   time), (b) board-architecture tasks (t1243 + t1243_11/12/13/14, t1632,
   t1367, t1450, t1613, t1403, t1402, t1401, t1399, t1400, t1404, t1431,
   t1445, t1442, t1441, t1424, t1421, t1373, t1348, t1338, t1334, t1363,
   t1330, t1329, t1290, t1296, t1256, t1250, t1249, t1257, t1261, t1291,
   t1454, t1455, t1521, t1570, t1572, t1639, t1714, t1725_5, t1725_7, t1710,
   t1447, t1448, t1364, t1663_2, t635_37, t1162, t1162_6, t1301, t1315,
   t1295, t1239, t1422, t1440, t889, t583_9), (c) incidental mentions
   (manual-verification checklists that merely launch `ait board`: t1249,
   t1376, t1462, t1471, t1742, t427, t259_6, t1625, t386_9, t1387, t1386,
   t1459, t729, t571_7, t919, t417_11, t1342) — group (c) gets **no** note
   unless it cites a line number. Also the owners of the six active plans
   citing `aitask_board.py:NN`: p745 → t745, p1186 → t1186, p1162 → t1162,
   p1516 → t1516, p1569 → t1569, p1647 → t1647.
2. **Shared note body** (quoted heredoc, `--file -`): the board is being
   split under t1794 — point at `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
   sections "Target file map" and C1–C3 rather than inlining the map; say
   that `aitask_board.py:NN` anchors in the task body are stale and must be
   re-derived against the module named in the file map; state the three
   rules a future editor must keep (flat imports, no import-time `TASKS_DIR`
   in siblings, no `board/*.py` imports `aitask_board`); hedge that the
   file map describes the approved design and that child status at send
   time is `<list>`.
3. **Specific notes** in addition to the shared body: **t1647 / t1647_5**
   (the By-Trail command belongs in `board_trail_screen.py` — App half — or
   `board_trail_view.py` — widgets/modals — and must satisfy the `TrailHost`
   protocol so it also works in `ait trails`, or be gated off there via the
   capability query); **t1613** (child 1's guards are the source-level
   enforcement of the hazard it describes; its remaining scope should be
   checked against them); **t1632** (`board_columns` seam — the board now
   imports it from `aitask_board.py` only; C5 keeps that import there);
   **t1243** family (`TaskManager` lives in `board_task_manager.py` with
   constructor-injected paths); **t1296** (`R` in By-Trail is a
   `TRAIL_BINDINGS` row shared with `ait trails`).
4. Before each send: `./.aitask-scripts/aitask_query_files.sh resolve <id>`
   — skip archived/missing targets and record the skip.
5. Send with `./ait note <id> --from 1794 --with-live --file - <<'EOF' … EOF`;
   parse `NOTE_APPENDED:` (authoritative) and the `LIVE_*` line; never resend
   on `LIVE_NONE:`; surface `READ_ERROR:rollback-failed` if it ever appears.

## Verification steps

- Every target in groups (a) and (b) plus the six plan owners has a
  `NOTE_APPENDED:` line recorded in this child's plan, or a recorded skip
  reason (archived / missing).
- `./.aitask-scripts/aitask_query_files.sh inbox 1647_5` shows the note
  unread.
- `./ait git log --oneline -5` shows the note commits on the task-data branch.

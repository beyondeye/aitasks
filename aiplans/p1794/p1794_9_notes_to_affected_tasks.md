---
Task: t1794_9_notes_to_affected_tasks.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_8_*.md, t1794_10_*.md, t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_9 — Notes to every pending task the board split affects

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
("Target file map", C1–C3). Depends on `t1794_1` only.

## Procedure

1. Re-derive targets:
   `grep -lE 'aitask_board|ait board|By-Trail|bytrail|TrailDetailScreen|TrailSelectScreen|KanbanApp|TaskManager|TaskDetailScreen' aitasks/*.md aitasks/t*/*.md | grep -v t1794`
   — group (a) trail-subsystem, (b) board-architecture (both get notes),
   (c) incidental `ait board` launches (no note unless a line number is
   cited). Plus plan owners t745, t1186, t1162, t1516, t1569, t1647.
2. Shared body (quoted heredoc): pointer to the parent plan's "Target file
   map" and C1–C3; "`aitask_board.py:NN` anchors in your body are stale —
   re-derive against the module in the file map"; the three editor rules
   (flat imports, no import-time `TASKS_DIR` in siblings, no `board/*.py`
   imports `aitask_board`); hedge with the child status list at send time.
3. Specific additions: t1647 / t1647_5 (By-Trail command → App half in
   `board_trail_screen.py` satisfying `TrailHost`, or gated off in `ait
   trails` via the capability query); t1613 (child 1's guards enforce it);
   t1632 (`board_columns` import stays in `aitask_board.py`); t1243 family
   (`TaskManager` in `board_task_manager.py`, injected paths); t1296 (`R` is a
   shared `TRAIL_BINDINGS` row).
4. `aitask_query_files.sh resolve <id>` before each send; skip + record
   archived/missing.
5. `./ait note <id> --from 1794 --with-live --file - <<'EOF' … EOF`; record
   every `NOTE_APPENDED:` line below; `LIVE_NONE:` is success.

## Sent notes

(filled at implementation)

## Verification

- Every group (a)/(b) target and plan owner has a `NOTE_APPENDED:` line or a
  recorded skip; `aitask_query_files.sh inbox 1647_5` shows it unread;
  `./ait git log --oneline -5` shows the note commits.

## Post-implementation

Task-workflow Step 9 (no code; commit this plan; archive `t1794_9`).

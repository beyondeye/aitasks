---
Task: t1016_5_manual_verification_anchor_task_topic_grouping.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Strategy: autonomous
Created: 2026-06-21
---

# Manual Verification Auto-Execution Log - t1016_5

## Execution Log

### Item 1
- Item text: In `ait board`, press the by-topic key (`y`) -> tasks cluster into per-topic lanes; a topic root + its children + a loose `--followup-of` task all appear in one lane.
- Approach: Headless board pilot plus live grouping inspection.
- Action run: `python3 tests/test_board_topic_view.py`; live `group_tasks_by_topic` inspection for t1016.
- Output trimmed: Board pilot tests ran 6 tests OK. Live grouping showed lane `t1016 anchor task topic grouping` containing `t1016_anchor_task_topic_grouping.md`, `t1016_5_manual_verification_anchor_task_topic_grouping.md`, `t1034_document_anchor_topic_grouping.md`, and `t1035_board_bytopic_sort_modes.md`.
- Verdict: pass

### Item 2
- Item text: Tasks with no anchor and no follow-ups/children appear under a single "Ungrouped" lane (NOT one lane each); legitimate topic roots are not hidden.
- Approach: Pure grouping unit tests.
- Action run: `python3 tests/test_board_topic_group.py`.
- Output trimmed: 13 tests OK, including singleton collapse into `Ungrouped` and mixed clusters retaining legitimate topic lanes.
- Verdict: pass

### Item 3
- Item text: Open a task's detail screen, edit the anchor field, save -> the file gains an `anchor:` line and the card re-groups under the new topic after refresh.
- Approach: Headless board pilot in an isolated `/tmp` copy of the repository.
- Action run: Created scratch tasks `t9000_anchor_root.md` and `t9001_edit_target.md` under `/tmp/auto_verify_1016_5_PmddtU`, opened `t9001` detail, edited `AnchorField` to `9000`, then re-opened By-Topic view.
- Output trimmed: `PASS: detail AnchorField edit persisted anchor: 9000 and by-topic regrouped target with root in temp workspace`.
- Verdict: pass

### Item 4
- Item text: A legacy parent+children tree (files have no `anchor:`) still clusters together in by-topic via the child->parent fallback (no migration).
- Approach: Pure grouping unit tests.
- Action run: `python3 tests/test_board_topic_group.py`.
- Output trimmed: 13 tests OK, including `test_legacy_anchorless_child_groups_with_parent` and `test_topic_key_child_without_loaded_parent_uses_parent_id`.
- Verdict: pass

### Item 5
- Item text: Archive a topic root, then re-open by-topic -> the topic lane still renders (stable id key) and groups the remaining members.
- Approach: Pure grouping unit tests for absent/archived root behavior.
- Action run: `python3 tests/test_board_topic_group.py`.
- Output trimmed: 13 tests OK, including `test_archived_or_absent_root_is_a_stable_lane_key`.
- Verdict: pass

### Item 6
- Item text: Create a follow-up via `aitask_create.sh --followup-of <src>` (or trigger a real spawn site, e.g. qa/verification-followup/carryover) -> the new task's `anchor` equals src's root and it lands in src's topic lane on the board.
- Approach: Shell tests for create/follow-up and spawn-site anchoring, plus live topic grouping inspection.
- Action run: `bash tests/test_anchor_create.sh`; `bash tests/test_verification_followup_anchor.sh`; `bash tests/test_archive_carryover_anchor.sh`; live `group_tasks_by_topic` inspection for `t1034`/`t1035`.
- Output trimmed: `test_anchor_create.sh` passed 20/20; verification-followup anchor tests passed 10/10; archive carryover anchor tests passed 4/4; live t1016 lane included loose follow-ups `t1034` and `t1035`.
- Verdict: pass

### Item 7
- Item text: Spot-check a regenerated agent-instruction mirror (AGENTS.md / .codex / .opencode) and the website task-format page -> the `anchor` field is present.
- Approach: Generated-mirror test and grep inspection.
- Action run: `bash tests/test_agent_instructions.sh`; `rg -n "anchor:" AGENTS.md .codex/instructions.md .opencode/instructions.md`; `rg -n "\`anchor\`" website/content/docs/development/task-format.md`.
- Output trimmed: Agent instruction tests passed 94/94; `anchor:` appears in all three mirrors; the website task-format table contains the `anchor` row.
- Verdict: pass

## Cleanup

- Scratch verification workspace remains at `/tmp/auto_verify_1016_5_PmddtU` and contains only copied task data used for the detail-edit check.
- No tracked source files were edited by the verification run.

---
priority: medium
effort: medium
depends: [t1663_1]
issue_type: feature
status: Ready
labels: [task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:19
updated_at: 2026-09-01 15:19
---

Add the `premise_baseline:` frontmatter field end-to-end: writer flag, merge rule, extension-point sweep, contract test, and documentation surfaces.

## Context

Second child of t1663. Design in `aidocs/framework/task_premise_staleness.md`. The field is `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>` — same grammar as `verification_baseline:`, but a distinct field (the MV field stays issue-type-scoped). Update-path only, like `plan_approved_at` (no interactive create prompt; child 3 adds the creation-time seeding separately).

## Key files

- `.aitask-scripts/aitask_update.sh` — `--premise-baseline` batch flag (empty string clears), positional threading through `write_task_file` (model: `--verification-baseline` at :205/:391/:619/:812-817/:2120-2126/:2253), value validated not accepted.
- `.aitask-scripts/board/aitask_merge.py` — add `premise_baseline` to `_BASE_AWARE_FIELDS` with `deletion_aware=True`. This is the **third** user of `_normalize_opaque_scalar` (:150-166), whose comment says the third user promotes the helper — do that promotion, don't add a fourth copy. The rationale block at :189-207 (why presence-based merge resurrects a dismissed baseline; why updated_at-based merge lets unrelated edits win) applies verbatim.
- `aidocs/framework/aitasks_extension_points.md` — walk the 5-layer checklist ("Adding a new frontmatter field"); the `plan_approved_at` worked example is the closest shape (update-only, contract test pinning sites).
- Docs surfaces: `website/content/docs/development/task-format.md` field table, `seed/aitasks_agent_instructions.seed.md` + generated mirrors, CLAUDE.md task-format block, `.claude/skills/task-workflow/task-creation-batch.md` note that `active`-style framework fields are not caller-authored (premise_baseline IS caller-visible via update).

## Reference files for patterns

- `tests/test_plan_approved_marker_contract.sh` — the contract-test shape: pin each write/clear site by hit count AND pin where the clear must NOT appear.
- `board/aitask_board.py` `Task`/`serialize_frontmatter` path — confirm the field round-trips through the board's writer without being dropped (BOARD_KEYS/BOARD_LAYOUT_KEYS seam, `tests/test_board_persistence_seam.py`).

## Verification (this child owns the concurrent-merge cases; pinned outcomes)

- `aitask_update.sh --batch <id> --premise-baseline "<sha> @ <ts>"` writes; `--premise-baseline ""` clears; malformed value rejected.
- Merge tests in the `aitask_merge.py` suite: (a) baseline cleared on one side + present on the other → stays cleared (deletion-aware, no resurrection); (b) an unrelated `--status` edit with newer `updated_at` does not win a baseline it never touched; (c) divergent advances on both sides → surfaced as PARTIAL/conflict, never a silently guessed winner.
- Contract test: every write/clear site pinned; board round-trip preserves the field.

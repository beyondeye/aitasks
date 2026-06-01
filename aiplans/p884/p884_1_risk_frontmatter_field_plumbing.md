---
Task: t884_1_risk_frontmatter_field_plumbing.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_1_risk_frontmatter_field_plumbing
Branch: aitask/t884_1_risk_frontmatter_field_plumbing
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 09:42
---

# Plan: t884_1 — Frontmatter plumbing for `risk` + `risk_mitigation_tasks`

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.

## Goal

Add two additive task frontmatter fields. **Zero behavior change when absent.**
- `risk` — scalar `high|medium|low`, mirrors `priority`. Display-only; **no** sort score; **no** border color; **omitted by default**.
- `risk_mitigation_tasks` — YAML **list** of task IDs; omitted by default; **dropped on fold**.

## Steps

1. **`aitask_create.sh`** — mirror every `priority` site for `risk` (batch `--risk` flag ~144, validation `high|medium|low` ~1766, `select_risk()` fzf ~802, interactive flow + summary, serialization in `create_draft_file`/`create_task_file`/`create_child_task_file`). **But:** default = omit (no `risk:` line when unset), not `medium`. Do NOT expose `risk_mitigation_tasks` as a create-time prompt — only ensure the serializer emits it if a value is present (or skip entirely at create).
2. **`aitask_update.sh`** — `BATCH_RISK`/`CURRENT_RISK`, `--risk` flag ~227, parse ~380, validation ~1461, `interactive_update_risk()` ~987, field handler, `write_task_file` ~487. Add `--risk-mitigation-tasks` (list) for later read-modify-write by t884_4.
3. **`aitask_ls.sh`** — parse `risk` for display only (~225-230 pattern); do NOT add to `p_score`.
4. **`aitask_board.py`** — snapshot dict (~2388), ReadOnlyField for Done/Folded (~2424), `CycleField("Risk", ["low","medium","high"], meta.get("risk"), "risk", ...)` (~2429). No `_risk_border_color`. **CycleField caveat (verified 2026-06-01):** `CycleField.__init__` falls back to `current_index = 0` ("low") when the passed value isn't in `options` (line ~974), so an *unset* risk renders as "low" in the editor. Omit-by-default still holds at the data layer — the snapshot stores `None` (`meta.get("risk")` with no default), `_current_values`/`_original_values` start equal, and `save_changes` only writes fields the user *actively* cycled (Changed message). So a task opened-but-not-touched is not written a `risk:` line. Accept this display-only quirk for the foundation task (same inherent limitation `priority`/`effort` avoid only by always having a value); do not invent an "unset" sentinel option.
5. **`aitask_fold_mark.sh`** — explicitly drop `risk_mitigation_tasks` on fold (do not union/transfer). `risk` scalar needs no fold change.

## Verification

- Create with/without `--risk`; update; `ait board` renders; fold drops `risk_mitigation_tasks`, keeps primary `risk`.
- `shellcheck` the four scripts; run existing create/update test suites.

## Notes for sibling tasks

t884_3 writes `risk`; t884_4 read-modify-writes `risk_mitigation_tasks`; t884_5 reads it. All depend on these flags/serialization existing.

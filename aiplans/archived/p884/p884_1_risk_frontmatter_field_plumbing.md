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
- `risk` — scalar `high|medium|low`. **A planning output, not a creation-time input:** it is assigned later by the risk-evaluation step (t884_3) via `aitask_update.sh`, never chosen at `ait create`. Mirrors `priority`'s *update/display* plumbing only. Display-only; **no** sort score; **no** border color; **omitted by default**.
- `risk_mitigation_tasks` — YAML **list** of task IDs; written post-create (by t884_4); omitted by default; **dropped on fold**.

## Steps

1. **`aitask_create.sh`** — **No change.** Neither `risk` nor `risk_mitigation_tasks` is chosen up-front: both are written *after* creation (risk by the t884_3 evaluation step, the mitigation list by t884_4), and both are always absent at create time, so there is nothing to serialize. Do **not** add a `--risk` flag, `select_risk()`, interactive prompt, validation, or create-time serialization. (This is the key deviation from the "mirror `priority` everywhere" template — `priority` is a creation input; `risk` is a planning output.)
2. **`aitask_update.sh`** — this is where `risk` enters. `BATCH_RISK`/`CURRENT_RISK`, `--risk` flag ~227, parse ~380, validation `high|medium|low` ~1461, `interactive_update_risk()` ~987, field handler, `write_task_file` serialization ~487 (conditional-emit like `verifies`/`xdeprepo` so unset = no `risk:` line). Add `--risk-mitigation-tasks` (list) for later read-modify-write by t884_4.
3. **`aitask_ls.sh`** — parse `risk` for display only (~225-230 pattern); do NOT add to `p_score`.
4. **`aitask_board.py`** — snapshot dict (~2388), ReadOnlyField for Done/Folded (~2424), `CycleField("Risk", ["low","medium","high"], meta.get("risk"), "risk", ...)` (~2429). No `_risk_border_color`. **CycleField caveat (verified 2026-06-01):** `CycleField.__init__` falls back to `current_index = 0` ("low") when the passed value isn't in `options` (line ~974), so an *unset* risk renders as "low" in the editor. Omit-by-default still holds at the data layer — the snapshot stores `None` (`meta.get("risk")` with no default), `_current_values`/`_original_values` start equal, and `save_changes` only writes fields the user *actively* cycled (Changed message). So a task opened-but-not-touched is not written a `risk:` line. Accept this display-only quirk for the foundation task (same inherent limitation `priority`/`effort` avoid only by always having a value); do not invent an "unset" sentinel option.
5. **`aitask_fold_mark.sh`** — explicitly drop `risk_mitigation_tasks` on fold (do not union/transfer). `risk` scalar needs no fold change.
6. **Automated tests (new, land in this task).** Follow the self-contained bash pattern (`set -e`, `assert_eq`/`assert_contains`, PASS/FAIL summary). Use the `setup_fake_aitask_repo` scaffold from `tests/lib/test_scaffold.sh` (model on `tests/test_fold_mark.sh` for scaffolded fixtures; `tests/test_update_cross_repo.sh`/`test_verified_update_flags.sh` for `aitask_update.sh` argument-level coverage). **Two new files:**
   - **`tests/test_update_risk.sh`** — (a) `--risk high` writes `risk: high`; (b) invalid `--risk bogus` exits non-zero with the validation message; (c) updating an unrelated field (e.g. `--priority low`) on a task with no risk leaves **no** `risk:` line (conditional-emit / omit-by-default holds); (d) `--risk-mitigation-tasks "12,13"` writes the YAML list, and a later unrelated update preserves it (read-modify-write); (e) **guard:** a task created via `aitask_create.sh` has no `risk:` line and no `risk_mitigation_tasks:` line (confirms create stayed untouched).
   - **`tests/test_fold_risk_mitigation_drop.sh`** — primary with `risk: medium` + a folded task carrying `risk_mitigation_tasks: [99]` → after `aitask_fold_mark.sh`, primary keeps `risk: medium` and has **no** `risk_mitigation_tasks:` line.
   - **Board (`aitask_board.py`)** rendering stays under the t884_8 manual-verification sibling (TUI) — no automated board test added here. State this explicitly so the gap is intentional, not an oversight.

## Verification

- A freshly created task has **no** `risk:` line (confirm `aitask_create.sh` was not touched / emits no risk).
- `aitask_update.sh --batch <id> --risk medium` sets the field; interactive update offers Risk; `--risk-mitigation-tasks` writes the list.
- `ait board` renders the risk value (read-only for Done/Folded, CycleField otherwise); tasks with no risk render without error. *(Covered by the t884_8 manual-verification sibling.)*
- Fold a task carrying `risk_mitigation_tasks` into a primary → primary keeps its own `risk`, the list is NOT carried over.
- **Run the new tests:** `bash tests/test_update_risk.sh && bash tests/test_fold_risk_mitigation_drop.sh` (both PASS).
- `shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_fold_mark.sh tests/test_update_risk.sh tests/test_fold_risk_mitigation_drop.sh` (create.sh unchanged); run existing update/fold test suites.

## Notes for sibling tasks

t884_3 writes `risk`; t884_4 read-modify-writes `risk_mitigation_tasks`; t884_5 reads it. All depend on these flags/serialization existing.

## Final Implementation Notes

- **Actual work done:** Implemented exactly the revised 6-step plan.
  - `aitask_update.sh`: added `BATCH_RISK`/`BATCH_RISK_SET`, `BATCH_RISK_MITIGATION_TASKS`/`_SET`, and `CURRENT_RISK`/`CURRENT_RISK_MITIGATION_TASKS`. New flags `--risk` (scalar, validated only when non-empty so `--risk ""` clears) and `--risk-mitigation-tasks` (list, replace-all, `normalize_task_ids`). `write_task_file` gained two positional params (`${25}` risk, `${26}` risk_mitigation_tasks) emitted conditionally — `risk:` right after `priority:`; `risk_mitigation_tasks:` right after the `verifies:` block. Wired through all three `write_task_file` call sites (batch, interactive, child-completion) plus the child-completion save/restore block. Interactive mode: `interactive_update_risk()` + a "risk" row in `interactive_select_field` (7th param) + handler + summary line.
  - `aitask_ls.sh`: `risk_text` parsed (display-only, **no** `r_score`; deliberately excluded from `p_score`), rendered as `, Risk: <v>` between Priority and Effort, only when set.
  - `aitask_board.py`: `risk` added to `_original_values` with **no** default (`task.metadata.get("risk")` → None when unset); ReadOnlyField shown only when `meta.get("risk")` truthy; editable `CycleField("Risk", ...)`. Save round-trips via the generic `serialize_frontmatter`, which also preserves `risk_mitigation_tasks` untouched (no board edit path for it).
  - `aitask_fold_mark.sh`: documented that `risk_mitigation_tasks` is intentionally NOT unioned into the primary (contrast with `verifies`), and added `--risk-mitigation-tasks ""` to the Step-4 folded-task update so the folded instance's list is cleared.
- **Deviations from plan:** None of substance. The only nuance beyond the written plan: chose to also **clear** the folded task's own `risk_mitigation_tasks` (not just skip the union) so "drop on fold" is observable and testable — this is what `test_fold_risk_mitigation_drop.sh` asserts. `--risk`/`--risk-mitigation-tasks` use the `_SET` guard pattern (like `verifies`/`issue`) so `""` explicitly clears.
- **Issues encountered:** None. Verified `serialize_frontmatter` (board) emits arbitrary keys and round-trips lists via `_FlowListDumper`, so no board-serializer change was needed and `risk_mitigation_tasks` is never dropped by a board edit.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - t884_3 (writes `risk`): call `aitask_update.sh --batch <id> --risk <level>`. Omit the flag (or pass `""`) to leave/clear it. Validation accepts only `high|medium|low`.
  - t884_4 (populates `risk_mitigation_tasks`): the flag is **replace-all**, not append. Read-modify-write = read the current list (e.g. `read_yaml_field`/`parse_yaml_list`), append, then pass the full CSV back via `--risk-mitigation-tasks "a,b,c"`.
  - t884_5 (reads `risk_mitigation_tasks`): it serializes as a YAML flow list (`[12, 13]`); parse with `parse_yaml_list`.
  - Board: an **unset** risk renders as "low" in the CycleField editor (index-0 fallback) but is NOT persisted unless the user actively cycles it — accepted display-only quirk; no "unset" sentinel was added.
  - `aitask_create.sh` was deliberately left untouched; `test_update_risk.sh` has a guard asserting created tasks carry neither field.

---
Task: t1159_3_spinoff_triage_arm.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_1_round_metadata_concern_block.md, aitasks/t1159/t1159_2_auto_recheck_loop.md, aitasks/t1159/t1159_4_docs_and_integration.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# Plan — t1159_3: Picker spin-off triage arm

Parent design: `aiplans/p1159_shadow_review_loop_automation.md`. Depends on t1159_1 (modal `block_meta` keyword ordering only); parallel with t1159_2.

## Pinned decisions

- Picker creates tasks directly, as **drafts** (no `--commit`): offline-safe in a TUI worker, reversible, anti-bloat. Drafts land in `aitasks/new/` with **no ids** until finalization — report **draft paths**.
- Provenance: `--followup-of <task_id>` (the **reviewed** task from the picker context) + `--followup-kind review_finding` (`lib/followup_kinds.py` vocabulary, validated pre-write).
- Collision-safe naming via per-batch cross-process nonce (`uuid.uuid4().hex[:8]`) + 1-based index.
- Post-creation store write: `aitask_shadow_rejected.sh add <task_id> --producer spinoff` (suppresses the now-tracked concern next round; t1427 store used exactly as designed, task-scoped, no layout change).

## Steps

1. **`monitor_shared.py` — row state**:
   - `_CONCERN_MARKS` (~1911): add `"spinoff": "[bold cyan]»[/]"` (U+00BB, single-width; verify against the `_NARROW_PREFIX_COLS` budget contract stated on the dict).
   - `_ConcernRow` (1923-2099): fourth mutually-exclusive state `"spinoff"`; `t` in `on_key` with `prevent_default`/`stop` like space/`r`; property `spun_off`; quad-state docstring.
2. **`ConcernPickResult`** (1868-1883): add `spun_off: list[Concern]` **with no default** — contract-completeness: amend every constructor (`ConcernPickerModal._result()` at 2607-2612, ordering all four lists by `original_index`) and **every** test literal in `tests/test_concern_picker_modal.py` + `tests/test_minimonitor_concern_action.py` in the same commit.
3. **Modal text**: `_CONCERN_HELP_FULL`/`_CONCERN_HELP_COMPACT` gain `t:spin off as task`; `_context_line()` wording "forward, reject, or spin off"; docstring "Per-row actions" paragraph.
4. **`apply_concern_pick_result`** (`ShadowRejectionsMixin`, 665-705): after forward/reject handling —
   ```python
   if result.spun_off:
       if not task_id:
           self.notify("Spin-off skipped — no task id for this pane", severity="warning")
       else:
           self.run_worker(self._spawn_concern_tasks(result.spun_off, task_id),
                           exclusive=False, exit_on_error=False, group="shadow-spinoff")
   ```
5. **`_spawn_concern_tasks`** + subprocess seam `_run_create_cmd` (extract beside `_run_rejected_cmd`, ~620-645, same timeout discipline, stdin-fed — tests spy it without executing bash):
   - Per-batch nonce `nonce = uuid.uuid4().hex[:8]`; per concern `i` (1-based): name `shadow_<region>_<nonce>_<i>` with **suffix-preserving truncation** (truncate the region segment, never nonce/index, under the name-length cap; region may be empty → `concern`).
   - Argv: `aitask_create.sh --batch --silent --name <name> --desc-file - --priority <c.priority> --labels shadow-concern --followup-of <task_id> --followup-kind review_finding`.
   - Stdin description: `Spun off from a shadow review concern on t<task_id>.\n\n<concern_marker_line(c)>\n` — canonical `.body` (FORWARD role).
   - `--silent` prints exactly one line (the created path); collect paths; notify `"N concern(s) parked as drafts in aitasks/new/ — finalize with 'ait create'"`; failures → error notify with count.
   - On each success: `aitask_shadow_rejected.sh add <task_id> --producer spinoff` with the marker line on stdin (exit-code vocabulary per `rejection_outcome_message`, 738-760).
   - **Confirm at implementation** that `--followup-of`/`--followup-kind` flow through the draft (no `--commit`) path (frontmatter written at draft-creation sites, validation pre-write at aitask_create.sh:2037-2042); if `--followup-of` resolution fails on the draft path, record the anchor in the description prose and surface it in the Final Implementation Notes.
6. **AST guard**: register the spin-off description builder as a FORWARD surface in `tests/test_concern_body_display_contract.py` (t1294).

## Verification

- Modal (`tests/test_concern_picker_modal.py`): `t` toggles spinoff; mutual exclusivity across all four states; `spun_off` in original input order; all-empty result distinct from `None`; help text names `t`.
- Flow (`tests/test_minimonitor_concern_action.py`): `_run_create_cmd` spy called once per concern with `--batch --silent --desc-file -` + `--followup-of`/`--followup-kind` in argv and the canonical marker line on stdin; draft-path reporting (not ids); no-task-id → warning, no subprocess; store `add --producer spinoff` follows success only.
- Collision: two same-region concerns in one confirmation → distinct names/paths; two distinct confirmations **frozen to the identical epoch second** (patched clock/uuid seam) → distinct paths, first batch's drafts intact.
- AST guard passes; `bash tests/run_all_python_tests.sh` — final stderr verdict line only.
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for cleanup, archival, and merge.

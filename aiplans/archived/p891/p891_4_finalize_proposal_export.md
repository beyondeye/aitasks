---
Task: t891_4_finalize_proposal_export.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_5_manual_verification_brainstorm_proposal_only.md
Archived Sibling Plans: aiplans/archived/p891/p891_1_decision_docs_v2_architecture.md, aiplans/archived/p891/p891_2_ops_agents_removal.md, aiplans/archived/p891/p891_3_schema_data_tui_cleanup.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-11 12:52
---

# Plan — t891_4: finalize replacement (proposal export, no migration)

## Context

Final removal child of t891 (make `ait brainstorm` proposal-only). With the plan
layer gone (t891_2/t891_3 landed), `finalize_session()` is the last place in
`.aitask-scripts/brainstorm/` still referencing the retired plan machinery: it
reads the HEAD node's `plan_file`, raises `ValueError` if absent, and copies
`br_plans/<head>.md` → `aiplans/p<N>_<head>.md`. The `br_plans/` store and the
`plan_file` node field no longer exist (t891_3), so this path is dead and must be
replaced. `ait brainstorm` is unshipped → no migration, no tolerate-legacy.

## Verification of 2026-06-01 anchors against as-landed code (verify path)

- `finalize_session` moved to **L336–366** (was ~L295). The three plan refs are
  now at **L351 (`plan_file = node_data.get(...)`), L352–353 (`raise ValueError`),
  L355–362 (`src = wt / plan_file`, `is_file` check, `shutil.copy2`)**.
- `grep -rn "plan_file\|br_plans" .aitask-scripts/brainstorm/` → **only**
  `finalize_session` (L351–355). t891_3 cleaned everything else (schema fields,
  `read_plan`/`PLANS_DIR`, TUI tabs/bindings/badges). Confirms scope.
- **t756 has landed.** Nodes now store proposals at `br_proposals/<node_id>.md`
  via `create_node` (`brainstorm_dag.py:59,65`); `read_proposal(session_path,
  node_id)` reads them (`brainstorm_dag.py:498`). The module fast-track
  (`_create_linked_module_task`, `brainstorm_session.py:1154`) already creates a
  linked aitask per module seeded from the proposal sections.

## Decision: strategy (a) — proposal export, **plus a module-sync guard**

The v2 architecture doc authored by t891_1 **ratifies (a)**:
`aidocs/brainstorming/brainstorm_engine_architecture_v2.md:135` — *"Session
completed (finalize): The final **proposal** is exported to `aiplans/`."* Not
chosen: pure strategy (b) (finalize as a no-op file-export-wise) — it would
strand the proposal for any session that did **not** go through the per-module
fast-track (simple single-proposal sessions get no handoff at all). (a) keeps a
session-level handoff artifact and preserves the existing caller contract
(CLI/TUI both consume the returned dest path). It does not duplicate fast-track:
fast-track creates per-module *tasks*; finalize exports the session HEAD's
*proposal* as a reference doc.

The "Must preserve" list in the task (crew-runner shutdown, session↔task metadata
link) is a pre-modules guess — as-landed `finalize_session` does **only**
`save_session({"status": "completed"})`. That single transition is preserved.

**Module-sync guard (user-requested).** task + plan creation from a module node
*is* supported (t756 fast-track `_create_linked_module_task`,
`brainstorm_session.py:1154`, runs `aitask_create.sh --parent`; the child aitask
owns its plan). Exporting the umbrella HEAD proposal while submodules are
mid-implementation and unsynced would write a stale handoff. So `finalize_session`
must **block** export when ≥1 non-umbrella module is in/past implementation but
not yet synced (decision: "Block until synced"). After every implemented module
is synced (umbrella proposal reconciled via sync nodes), and for design-only or
simple single-proposal sessions, export proceeds normally.

## Changes

### 1. `.aitask-scripts/brainstorm/brainstorm_session.py` — `finalize_session` (L336–366)
- Docstring → "Export HEAD node's **proposal** to `aiplans/`. Mark session
  completed. Returns dest path. Raises ValueError if no HEAD set, or if a
  module is in implementation but not yet synced."
- Import line (L342): `from .brainstorm_dag import get_head, read_proposal`
  (drop `read_node` — node_data is no longer read).
- Remove: `node_data = read_node(...)` (L350), `plan_file = ...` (L351), the
  `if not plan_file: raise ValueError(... has no plan_file)` guard (L352–353),
  `src = wt / plan_file` + `if not src.is_file(): raise FileNotFoundError`
  (L355–357), and the `shutil.copy2(src, dest)` (L362).
- Keep the `head`/`get_head` guard (raise if no HEAD). Replace the body with the
  **module-sync guard** then the proposal export:
  ```python
  # Block export while a fast-tracked module is mid-implementation and unsynced —
  # its real plan lives in the linked aitask; the umbrella proposal would be stale.
  from .brainstorm_status import (
      module_status_rows, STATUS_IN_IMPLEMENTATION, STATUS_IMPLEMENTED,
  )
  unsynced = [
      r for r in module_status_rows(wt)
      if not r["is_umbrella"]
      and r["status"] in (STATUS_IN_IMPLEMENTATION, STATUS_IMPLEMENTED)
      and not r["last_synced"]
  ]
  if unsynced:
      names = ", ".join(r["module"] for r in unsynced)
      raise ValueError(
          f"Cannot finalize: module(s) {names} are in implementation but not "
          f"synced. Run module_sync before finalizing."
      )

  proposal = read_proposal(wt, head)
  dest_dir = Path(plan_dest_dir)
  dest_dir.mkdir(parents=True, exist_ok=True)
  dest = dest_dir / f"p{task_num}_{head}.md"
  dest.write_text(proposal, encoding="utf-8")
  save_session(task_num, {"status": "completed"})
  return str(dest)
  ```
- The `brainstorm_status` import is **function-local** (not module-level):
  `brainstorm_status.py:38` already does `from brainstorm.brainstorm_session
  import _module_deferred_map`, so a top-level import here would be circular. A
  call-time local import is safe (both modules fully loaded by then) and matches
  the existing `from .brainstorm_dag import …` local-import style in this
  function. `merged` modules are terminal (absorbed) and never match the
  in/post-implementation statuses, so they correctly don't block.
- `shutil` import stays (still used by `delete_session` L382). Keep dest filename
  `p<N>_<head>.md` and the `plan_dest_dir="aiplans"` default — preserves the
  caller contract.

### 2. User-facing wording "plan" → "proposal" (no behavior change)
- `brainstorm_cli.py`: `cmd_finalize` docstring (L115), `finalize` subparser
  `help=` (L191). The stdout token `PLAN:{dest}` (L120): grep the **whole repo**
  for a consumer first; none found in `.aitask-scripts/`. If still unconsumed,
  rename to `PROPOSAL:{dest}` for cleanliness; if any consumer exists, leave the
  token and only fix prose. (TUI calls `finalize_session` directly, not the CLI.)
- `brainstorm_app.py`: `_SESSION_OPS` finalize description (L228), the
  `finalize` help-dict comment + title/summary (L438–445), the `labels`
  finalize string (L6978), and the notify `f"Plan finalized to {dest}"` →
  `"Proposal finalized to {dest}"` (L7424).

### 3. Tests (both pre-marked for t891_4)
- `tests/test_brainstorm_dag.py::TestFinalizeSession::test_finalize_copies_plan`
  (L500–527) → rename to `test_finalize_exports_proposal`. Drop the `br_plans/`
  + `plan_file` setup; create the node with a known proposal body, `set_head`,
  `finalize_session(..., plan_dest_dir=...)`, assert the dest file contains the
  **proposal** body and session status is `completed`.
- **New guard test** in the same `TestFinalizeSession` class —
  `test_finalize_blocked_by_unsynced_module`: build a session with a non-umbrella
  module whose status computes to `in_implementation` and no `last_synced`
  (simplest path: write `module_tasks: {<mod>: <id>}` into `br_graph_state.yaml`
  and add a 2nd node in that subgraph so `compute_module_status` returns past
  `unstarted`; stub the linked-task lookup as Implementing — or follow the setup
  already used by `test_brainstorm_module_status*.py`). Assert `finalize_session`
  raises `ValueError` mentioning the module, and that after stamping
  `last_synced_at[<mod>]` (`_write_last_synced`) the export succeeds. Mirror the
  fixture style in `tests/test_brainstorm_module_status_contract.py` /
  `tests/test_brainstorm_module_status.py` to keep the linked-task state setup
  consistent.
- `tests/test_brainstorm_cli_python.py::TestArchiveCommand::test_archive_sets_crew_status`
  (L155–194) → remove the `br_plans`/`plan_file` setup (L166–174); the node
  already gets a proposal ("Test proposal") from `create_node`. Keep the
  finalize→archive flow and the crew-status assertion. If the token is renamed,
  no assertion here depends on it.

## Verification
- `grep -rn "plan_file\|br_plans" .aitask-scripts/brainstorm/` → no output.
- `python3 tests/test_brainstorm_dag.py` and `python3 tests/test_brainstorm_cli_python.py`
  pass (incl. the new guard test). No circular-import error on
  `brainstorm_status` ← `brainstorm_session`.
- Manual (Step 9 / follow-up): (1) simple session → finalize writes
  `aiplans/p<N>_<head>.md` with proposal content, session `completed`, no raise.
  (2) decompose into a module, fast-track it, leave it unsynced → finalize raises
  the "run module_sync" error. (3) run module_sync → finalize then succeeds.
- Step 9 (Post-Implementation): commit on current branch, then archive via
  `./.aitask-scripts/aitask_archive.sh 891_4`.

## Risk

### Code-health risk: low
- Blast radius is one function plus prose strings and tests, all inside
  `.aitask-scripts/brainstorm/`. Reuses existing accessors (`read_proposal`,
  `module_status_rows`); the only subtlety is the function-local import to dodge
  the known `brainstorm_status` ↔ `brainstorm_session` cycle, verified during
  planning. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Export strategy (a) is fixed by the ratified v2 doc (L135); the module-sync
  guard strictness was explicitly chosen by the user ("Block until synced").
  Anchors and module-state helpers re-verified against as-landed code. ·
  severity: low · → mitigation: TBD

## Final Implementation Notes

- **Actual work done:** Rewrote `finalize_session` (`brainstorm_session.py`) to
  export the HEAD node's **proposal** (`read_proposal` → `aiplans/p<N>_<head>.md`,
  `dest.write_text`) instead of copying a `plan_file`/`br_plans` plan. Added the
  user-requested **module-sync guard**: it computes `module_status_rows(wt)` and
  raises `ValueError("… run module_sync before finalizing.")` when any
  non-umbrella module is `in_implementation`/`implemented` with no `last_synced`
  stamp. The `completed` status transition is preserved; the `shutil` import
  stays (used by `delete_session`). Updated user-facing "plan"→"proposal" wording
  in `brainstorm_cli.py` (finalize docstring + subparser help) and
  `brainstorm_app.py` (`_SESSION_OPS` label, OP help-dict comment/title/summary/
  use-case, session-op config label, and the notify string). Tests:
  `test_finalize_copies_plan`→`test_finalize_exports_proposal`, new
  `test_finalize_blocked_by_unsynced_module`, and stripped the `br_plans`/
  `plan_file` setup from the CLI archive test.
- **Deviations from plan:** None functionally. The plan flagged that the
  `PLAN:<dest>` CLI stdout token *might* be renamed to `PROPOSAL:`; it is **kept**
  because `aitask_brainstorm_archive.sh:82-85` consumes `^PLAN:` — renaming would
  widen blast radius beyond this child's scope. Only prose was changed.
- **Issues encountered:** The `brainstorm_status` ↔ `brainstorm_session` import
  cycle (`brainstorm_status.py:38` imports from `brainstorm_session`) — resolved
  with a **function-local** import inside `finalize_session` (matches the existing
  `from .brainstorm_dag import …` local-import style). Verified importable both
  ways.
- **Key decisions:** Strategy (a) proposal export (ratified by
  `brainstorm_engine_architecture_v2.md:135`), not pure (b) no-op — (b) would
  strand the handoff for non-decomposed sessions. Guard strictness = "Block until
  synced" (user-selected): allows export for design-only/simple sessions and for
  decomposed sessions once every implemented module is synced.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** (1) `t891` is now **grep-clean** of
  `plan_file`/`br_plans` across `.aitask-scripts/brainstorm/` — finalize was the
  last consumer. (2) **Naming lag, not a defect:** `aitask_brainstorm_archive.sh`
  still uses the `PLAN:<path>` stdout token and "Plan file copied to aiplans/"
  usage comments (lines 10, 42, 82-85). These are an internal protocol contract
  with `brainstorm_cli.py`'s `print(f"PLAN:{dest}")`, deliberately left intact;
  if a future task wants full "proposal" naming consistency it must change the
  CLI token and the archive parser together. (3) The module-sync guard reuses
  `brainstorm_status.module_status_rows`; the `in_implementation`/`implemented`
  + unsynced predicate is the canonical "premature export" signal. t891_5
  (manual verification) should exercise the live finalize block/unblock flow.

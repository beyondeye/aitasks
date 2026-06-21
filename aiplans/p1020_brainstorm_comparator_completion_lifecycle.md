---
Task: t1020_brainstorm_comparator_completion_lifecycle.md
Worktree: (current branch — profile 'fast')
Branch: (current)
Base branch: main
---

# Plan: Brainstorm comparator completion lifecycle (t1020)

## Context

In the `ait brainstorm` TUI a **Compare** operation never leaves `Waiting`, even
after the comparator agent finishes and writes its full output. The Status
screen then shows the contradictory "100% progress + Waiting" state, and the
comparison output has no path back into the TUI.

Root cause (confirmed in source): explorer and synthesizer operations each have a
three-part completion lifecycle — a **tracking call** after registration, a
**poll loop** that detects the agent's `Completed` status file, and an **apply**
step that calls `update_operation(..., status="Completed")`. The comparator
branch has **none** of these, so `compare_<seq>` stays `Waiting` forever. The
comparator is also unique in that it **creates no node** (analysis-only output),
so the existing `o`-on-a-node path to `OperationDetailScreen` can never surface
its output.

Goal: give the comparator the same lifecycle as explorer/synthesizer (adapted
for "no node created"), and give a node-less operation group a way to open its
`OperationDetailScreen` so the comparison `_output.md` is readable in-TUI.

## Approach

Mirror the **explorer/synthesizer** machinery exactly, minus node creation. The
apply step for a comparator only flips the owning group's status to `Completed`
(no `create_node`, no `nodes_created`). Output reachability is solved generically
by letting a focused **GroupRow** open `OperationDetailScreen` for its group
(which already renders per-agent `_output.md` tabs and is keyed by group name,
not node).

### Scope decision — AC #4 (`_crew_status.yaml` roll-up): SPLIT OUT

The stale `_crew_status.yaml` (`Running`/`80` while the sole agent is
`Completed`/`100`) is a **crew-runner aggregate** concern — written by the crew
runner and `brainstorm_cli.py::cmd_archive` (`_crew_status.yaml`), a different
subsystem from the brainstorm operation lifecycle. It affects all operation
types, not just comparators, and the task itself frames the runner "stopping" as
a red herring for this bug. **Decision: fix only the operation-level
`Waiting→Completed` transition here; spawn a separate follow-up task for the
crew-runner roll-up** (offered via the Step 8b upstream-defect follow-up — it is
a separate, pre-existing defect in a different module). t1020's acceptance
criteria will be updated to record this split (no silent AC deviation).

## Files to modify

### 1. `.aitask-scripts/brainstorm/brainstorm_session.py` — engine (testable, no App)

Add, mirroring `apply_explorer_output` / `_explorer_needs_apply` (~lines 727,
971) but **without node creation**:

- **`_find_compare_group_for_agent(task_num, agent_name) -> str | None`** — read
  `br_groups.yaml`; return the group name whose `operation == "compare"` and
  whose `agents` list contains `agent_name` (robust to naming; no fragile
  `comparator_NNN → compare_NNN` derivation).
- **`_comparator_needs_apply(task_num, agent_name) -> bool`** — return `True`
  iff the owning compare group exists **and** its `status != "Completed"`. This
  is the durable, restart-safe idempotency signal (once flipped, never
  re-applies), analogous to the explorer's "node already exists" guard.
- **`apply_comparator_output(task_num, agent_name) -> str`** — resolve the group
  via the finder (raise a clear error if not found), then
  `update_operation(task_num, group, status="Completed")` **only**. Returns the
  group name. No `_apply_node_output`, no `nodes_created`, and **no
  `agents_append`** — `record_operation` already recorded the comparator in the
  group's `agents` list at registration, so the comparator's sole apply
  responsibility is the status flip (concern #4 — kept minimal rather than the
  redundant-but-deduped symmetry copy).

Reuse existing `update_operation` (~line 319), `_read_groups_file`, and the
shared `_AGENT_FAILED_STATUSES` / `_agent_apply_scan_should_track` (~line 680).

### 2. `.aitask-scripts/brainstorm/brainstorm_app.py` — TUI lifecycle (mirror explorer)

- **Instance state** (next to `_explorer_*` / `_synthesizer_*`, ~line 5672):
  `self._comparator_agents: set[str] = set()`, `self._applying_comparator: set`,
  `self._comparator_apply_errors: dict`, `self._comparator_poll_timer = None`.
- **`_register_comparator_agent` / `_ensure_comparator_poll_timer` /
  `_stop_comparator_poll_timer` / `_poll_comparators` /
  `_try_apply_comparator_if_needed` / `_scan_existing_comparators`** — direct
  mirrors of the explorer methods (~6836–6962, 6857). `_poll_comparators` reads
  `comparator_<seq>_status.yaml`, gates on `status == "Completed"`, drops on
  `_AGENT_FAILED_STATUSES`, calls `_comparator_needs_apply`, then
  `_try_apply_comparator_if_needed`. On success: clear banner, discard agent,
  `self.notify("Comparator <agent> complete → <group>. Press 'o' on the group to view output.")`,
  and `self._refresh_runtime()` (no DAG reload — nothing changed in the graph).
  The apply-failure banner references the in-TUI **`i`** retry key (not a CLI
  command — `ait brainstorm` has no `apply-*` subcommand).
  - **Force bypass (concern #3 — explicit):** `_try_apply_comparator_if_needed`
    MUST open with the explorer's exact guard shape
    `if agent in self._applying_comparator: return` then
    `if not force and not _comparator_needs_apply(self.task_num, agent): return`
    — so `force=True` (the `i` retry path) **bypasses** `_comparator_needs_apply`
    and re-runs `apply_comparator_output` even when the group is already
    `Completed` (a re-flip to `Completed` is an idempotent no-op). Without the
    `not force and` clause, `i` on a compare group would silently do nothing
    after the first apply.
- **Tracking call**: in the dispatch block's `elif op == "compare":` branch
  (~8622, right after `register_comparator(...)` returns `agent`), add
  `self.call_from_thread(self._register_comparator_agent, agent)` — exactly the
  missing line that explorer/synthesizer branches have.
- **On-mount scan wiring**: add `self._scan_existing_comparators()` beside the
  explorer/synthesizer scans (~6764–6765) so an in-flight/just-completed
  comparator is picked up after a TUI restart.
- **`_retry_group_apply`** (~7765, the `i` key): add
  `elif op == "compare": applier = self._try_apply_comparator_if_needed`.
- **`o`-on-GroupRow handler** (output reachability, AC #3) — factored + gated
  (concern #2): add a small testable helper
  **`_open_group_operation(self, row: "GroupRow") -> None`** (modeled on the
  existing `_open_compare_matrix`). It **gates on `row.has_completed_agent`**: if
  the group has no completed agent it `self.notify("No completed output to open
  yet.", severity="warning")` and returns without pushing; otherwise
  `self.push_screen(OperationDetailScreen(row.group_name, self.session_path))`.
  In `BrainstormApp.on_key` (~5897, alongside the GroupRow `n`/`i`/Enter
  branches) add `if event.key == "o": if isinstance(focused, GroupRow): self._open_group_operation(focused); event.prevent_default(); event.stop(); return`.
  `o` is currently a **NodeRow**-scoped binding (line 2530), so it only reaches
  `app.on_key` when a GroupRow is focused — no conflict. The gate makes the
  **action and the rendered hint consistent** (both keyed on `has_completed_agent`),
  so a Waiting group never opens a placeholder-only modal. Works for **any**
  node-less op, not just compare.
- **`GroupRow.render` hints** (~3172): extend the `i: retry-apply` hint to
  `op in ("explore", "synthesize", "compare")`, and add an `o: open output` hint
  when `self.has_completed_agent` (matching the action gate above).

### 3. `tests/test_brainstorm_apply_comparator.py` — regression test (new)

Mirror `tests/test_brainstorm_apply_explorer.py` fixture style (tmpdir session,
`sys.path.insert` for `.aitask-scripts`) **plus** the `_bare_app` app-level
harness from `tests/test_brainstorm_compare_overlay.py` (lines 146–157:
`BrainstormApp.__new__`, stubbed `push_screen`/`notify`, captured
`pushed`/`notices`).

**Engine tests (no App):**

- **Status transition (AC #1)**: `record_operation(task, "compare_001",
  "compare", ["comparator_001"], head)` → assert group status is `"Waiting"`.
  Write `comparator_001_output.md` (analysis text) and
  `comparator_001_status.yaml` with `status: Completed`. Call
  `apply_comparator_output(task, "comparator_001")` → assert it returns
  `"compare_001"` and the group `status` is now `"Completed"`.
- **Idempotency**: `_comparator_needs_apply` is `True` before apply, `False`
  after (restart-safe; no double-apply).
- **Group resolution**: `_find_compare_group_for_agent` finds the group by agent
  membership; returns `None` for an unknown agent → `apply_comparator_output`
  raises a clear error.

**App-level tests (bare-app — concern #1, the AC #3 TUI path):** since
`_open_group_operation` is a factored method, the bare-app harness can exercise
it directly without Textual focus/key routing. Build a lightweight stub row with
`group_name` + `has_completed_agent` attributes (a `types.SimpleNamespace` or a
tiny stub — no real GroupRow mount needed):

- **Completed group + `o` pushes the modal**: `row.has_completed_agent = True` →
  `app._open_group_operation(row)` → assert `len(app.pushed) == 1`,
  `isinstance(app.pushed[0], OperationDetailScreen)`, and its `group_name`
  matches (proves the routing/push reaches `OperationDetailScreen`, not just the
  engine).
- **Waiting group + `o` is gated**: `row.has_completed_agent = False` →
  `app._open_group_operation(row)` → assert `app.pushed == []` and a warning
  notice was recorded (proves the gate in concern #2).

(`OperationDetailScreen` is already importable from `brainstorm.brainstorm_app`,
as `CompareMatrixModal` is in the existing overlay test.)

## Verification

- **Automated:** `bash`-free Python unit test —
  `python3 tests/test_brainstorm_apply_comparator.py` (or the project's unittest
  invocation) must pass. Run the sibling lifecycle tests
  (`test_brainstorm_apply_explorer.py`, `test_brainstorm_apply_synthesizer.py`,
  `test_brainstorm_compare_overlay.py`) to confirm no regression.
- **Lint:** `shellcheck` not applicable (Python only); ensure no syntax errors
  via `python3 -m py_compile` on both edited modules.
- **Headless app-level:** the bare-app tests above confirm the AC #3 push path
  (`o` → `OperationDetailScreen`) and its gate without a live session.
- **Live / manual (TUI):** the genuinely runtime-only behavior — the 5s poll
  timer flipping a *real* comparator's group `Waiting→Completed` and the
  "100% + Waiting" state disappearing in the rendered Status screen — is
  confirmed in a live `ait brainstorm` session via the **manual-verification
  follow-up** (Step 8c).

## Risk

### Code-health risk: low
- Change is additive and mirrors the proven explorer/synthesizer lifecycle; no
  existing path is removed or restructured. Blast radius is two brainstorm
  modules + one new test. · severity: low · → mitigation: covered by regression
  test + sibling-test re-run.
- Adds a third parallel copy of poll machinery (explorer/synth/comparator); the
  codebase already accepts this role-parallel duplication. · severity: low ·
  → mitigation: TBD (none warranted).

### Goal-achievement risk: medium
- AC #3 assumes `OperationDetailScreen` renders a node-less comparator's
  `_output.md` in a per-agent tab. It is group-keyed and reads agent
  input/output/log files, so this should hold — but it must be confirmed live.
  · severity: medium · → mitigation: manual-verification follow-up (Step 8c).
- Live poll-timer behavior (5s tick flipping status) is not exercised by the
  headless unit test. · severity: medium · → mitigation: manual-verification
  follow-up covers the runtime path.

## Post-Implementation — required checklist (concern #5)

These are **required** steps, not optional offers — completing the split-out
decision is itself part of satisfying AC #4:

1. Step 8 review → commit code + plan.
2. **REQUIRED — create the `_crew_status.yaml` roll-up follow-up task** (bug,
   brainstorming label) describing the stale `Running`/`80`-while-`Completed`/`100`
   crew-aggregate symptom, the writer sites (crew runner +
   `brainstorm_cli.py::cmd_archive`), and that it is split out of t1020. This
   runs through the Step 8b upstream-defect follow-up, but is **mandatory here**
   — do not finish without the new task existing. Record the new task ID.
3. **REQUIRED — update t1020's AC #4** (via `./ait git`) to state the explicit
   decision: the roll-up is split to `t<new_id>`; replace the "consider whether…"
   wording so the known `Running/80` debt is documented and cross-linked, not
   left implicit.
4. Step 8c — offer the live-TUI **manual-verification** task (poll flips
   `Waiting→Completed`; "100% + Waiting" gone; `o` on a completed compare
   GroupRow opens `OperationDetailScreen` with the comparator output tab).
5. Step 9 — archive on the current branch, commit, push.

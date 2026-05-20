---
Task: t741_brainstorm_apply_detailer_output.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# t741 — Implement `apply_detailer_output()` in the brainstorm engine

## Context

The brainstorm engine launches role agents (initializer, explorer, synthesizer,
patcher, detailer, comparator) inside a crew worktree. When an agent finishes,
an **apply** function parses its `<agent>_output.md` and integrates the result
into the design-space DAG, and a **TUI auto-apply hook** polls for completion
and calls that apply function.

Sibling tasks t739 (explorer), t740 (synthesizer) and t743 (patcher) are
already implemented — `apply_explorer_output`, `apply_synthesizer_output`,
`apply_patcher_output` plus their `_poll_*` / `_try_apply_*_if_needed` TUI
hooks all exist. **The detailer is the only role left with no apply flow.**
The detailer writes an implementation-plan markdown document to `_output.md`,
but nothing parses it, nothing writes it to `br_plans/`, and the target node's
`plan_file` field is never set — so `finalize_session()` (which copies HEAD's
`plan_file` to `aiplans/`) cannot complete for a detailed node.

The detailer is structurally different from explorer/synthesizer/patcher: those
**create a new node**; the detailer **enriches an existing node** — it produces
a plan document only. So `apply_detailer_output` does NOT go through the shared
`_apply_node_output` core, does NOT create a node, and does NOT touch
`current_head` / `next_node_id`. Its closest sibling is the patcher (also keyed
on a pre-existing node id), so the TUI hook mirrors the patcher hook.

Intended outcome: a detailer agent completes → its plan is written to
`br_plans/<node>_plan.md` and the target node's YAML gets `plan_file` set,
automatically via a TUI poll hook, with a manual-retry path on failure.

## Current state (verified)

- `brainstorm_session.py` — has `apply_initializer_output`, `apply_explorer_output`,
  `apply_synthesizer_output`, `apply_patcher_output`, the shared `_apply_node_output`
  core, helpers `_extract_block` (line 344), `_output_has_all_delimiters`,
  `_agent_to_group_name` (`detailer`→`detail` map already present), `update_operation`.
- `brainstorm_dag.py` — `update_node()` is a generic merge (`data.update(updates)`),
  so it **already** supports setting `plan_file`. `PLANS_DIR = "br_plans"`,
  `read_plan()` reads `br_plans/<node>_plan.md`. **No change needed** here.
- `templates/detailer.md` — emits a full section-marked plan to `_output.md`
  with **no delimiter pair** (unlike patcher's `--- PATCHED_PLAN_START ---`).
- `brainstorm_crew.py` — `register_detailer()` builds `_input.md` via
  `_assemble_input_detailer()`, which writes a `## Target Node` block with
  `- Metadata: <session>/br_nodes/<node_id>.yaml` — the same shape the patcher
  scan regex (`_PATCHER_INPUT_META_RE`) already matches.
- `brainstorm_app.py` — `_run_design_op()` `detail` branch calls
  `register_detailer(... cfg["node"] ...)` but, unlike the `patch` branch, does
  **not** track the agent for auto-apply. Patcher state: `_patcher_sources`,
  `_applying_patcher`, `_patcher_apply_errors`, `_patcher_poll_timer`, plus
  `_register_patcher_source` / `_ensure_patcher_poll_timer` / `_stop_patcher_poll_timer`
  / `_scan_existing_patchers` / `_poll_patchers` / `_try_apply_patcher_if_needed`
  / `action_retry_patcher_apply` (binding `ctrl+shift+r`, `show=False`).
- CLI: `aitask_brainstorm_apply_{initializer,explorer,synthesizer,patcher}.sh`
  exist; `ait` dispatches `apply-*` subcommands. No `apply-detailer`.
- `ctrl+shift+d` is a free keybinding (`d`/`D` taken; `ctrl+shift+{r,x,y}` used).

## Approach

Mirror the **patcher** flow (closest sibling — keyed on an existing node id)
but simplified: no new node, no graph-state mutation, single delimited block.

### Step 1 — `templates/detailer.md`: add a single plan delimiter pair

The apply function needs a reliable extraction boundary. Add
`--- DETAILED_PLAN_START ---` / `--- DETAILED_PLAN_END ---` around the whole
plan document (section markers stay inside — they are required for the
template's own "Section-Targeted Re-Detailing"). The name parallels the
patcher's `PATCHED_PLAN_START/END`; each brainstorm role defines its own
role-appropriate delimiters.

- In the `## Output` section, change "Write a single Markdown file to
  `_output.md` with these required sections…" to instruct wrapping the entire
  plan between the delimiters:
  ```
  Write your plan to `_output.md`, wrapping the entire plan document
  between these delimiters:

  --- DETAILED_PLAN_START ---
  <the full plan Markdown, with all section markers below>
  --- DETAILED_PLAN_END ---
  ```
- In `## Phase 3: Write Output`, update the final bullet ("Write the final plan
  Markdown to `_output.md`") to "Write the final plan Markdown to `_output.md`,
  wrapped between `--- DETAILED_PLAN_START ---` and `--- DETAILED_PLAN_END ---`."

### Step 2 — `brainstorm_session.py`: `apply_detailer_output()` + `_detailer_needs_apply()`

Add after the synthesizer block (end of file). No new imports — `_extract_block`,
`_output_has_all_delimiters`, `_agent_to_group_name`, `update_operation`,
`update_node`, `NODES_DIR`, `PLANS_DIR`, `read_yaml`, `datetime` are all in scope.

```python
_DETAILER_DELIMITERS = ("DETAILED_PLAN_START", "DETAILED_PLAN_END")


def _detailer_needs_apply(
    task_num: int | str, agent_name: str, target_node_id: str,
) -> bool:
    """Return True iff <agent_name>_output.md contains both DETAILED_PLAN
    delimiters AND its plan body differs from the plan on disk for the target
    node.

    Guards against the registration-time placeholder _output.md (no
    delimiters) and against re-applying an output the poller already
    ingested. Content comparison (rather than a bare "plan_file set"
    check) keeps re-detailing correct: a later detailer on the same node
    produces different content and is still applied.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not _output_has_all_delimiters(text, _DETAILER_DELIMITERS):
        return False
    try:
        plan_text = _extract_block(text, "DETAILED_PLAN_START", "DETAILED_PLAN_END")
    except ValueError:
        return True  # delimiters present but malformed — let apply log it
    plan_path = wt / PLANS_DIR / f"{target_node_id}_plan.md"
    if not plan_path.is_file():
        return True
    try:
        existing = plan_path.read_text(encoding="utf-8")
    except Exception:
        return True
    return existing.strip("\n") != plan_text


def apply_detailer_output(
    task_num: int | str, agent_name: str, target_node_id: str,
) -> str:
    """Parse <agent_name>_output.md and attach the detailer's plan to an
    existing node.

    The detailer ENRICHES a node — it does not create one. The single
    delimited DETAILED_PLAN block is written to br_plans/<target_node_id>_plan.md
    and the node's plan_file field is set via update_node(). current_head
    and next_node_id are left untouched.

    Returns the relative plan path written (e.g. "br_plans/n001_x_plan.md").

    Raises:
        FileNotFoundError: output file missing OR target node missing.
        ValueError: DETAILED_PLAN delimiters missing or the plan body is empty.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    err_log = wt / f"{agent_name}_apply_error.log"
    if not out_path.is_file():
        raise FileNotFoundError(f"No detailer output at {out_path}")
    try:
        node_path = wt / NODES_DIR / f"{target_node_id}.yaml"
        if not node_path.is_file():
            raise FileNotFoundError(
                f"detailer target node not found: {target_node_id}"
            )
        text = out_path.read_text(encoding="utf-8")
        plan_text = _extract_block(text, "DETAILED_PLAN_START", "DETAILED_PLAN_END")
        if not plan_text.strip():
            raise ValueError("detailer PLAN block is empty")

        plan_rel = f"{PLANS_DIR}/{target_node_id}_plan.md"
        (wt / PLANS_DIR).mkdir(parents=True, exist_ok=True)
        (wt / plan_rel).write_text(plan_text, encoding="utf-8")
        update_node(wt, target_node_id, {"plan_file": plan_rel})

        # detailer enriches an existing node — record the agent + flip the
        # detail group Completed, but emit no nodes_created (no new node).
        update_operation(
            task_num,
            _agent_to_group_name(agent_name),
            agents_append=agent_name,
            status="Completed",
        )
        return plan_rel
    except Exception as exc:
        try:
            err_log.write_text(
                f"apply_detailer_output failed at "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"agent_name: {agent_name}\n"
                f"target_node_id: {target_node_id}\n\n"
                f"Error: {type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        raise
```

Notes:
- No `parse_sections` / `validate_sections` — those validate **proposal**
  sections, not plan sections. The patcher's `_write_patcher_plan_file` writes
  its plan block verbatim with no section validation; the detailer matches that.
  Validation is "has content" (`plan_text.strip()`), per the task spec.
- `_agent_to_group_name("detailer_001")` → `"detail_001"` (map already present);
  `update_operation` no-ops gracefully if the group is absent.

### Step 3 — `brainstorm_app.py`: TUI auto-apply hook (mirror the patcher)

1. **State** (in `__init__`, after the synthesizer block ~line 2677):
   ```python
   self._detailer_targets: dict[str, str] = {}   # agent_name -> target_node_id
   self._applying_detailer: set[str] = set()
   self._detailer_apply_errors: dict[str, str] = {}
   self._detailer_poll_timer = None
   ```

2. **Binding** (in `BINDINGS`, after `ctrl+shift+y`):
   ```python
   Binding("ctrl+shift+d", "retry_detailer_apply",
           "Retry detailer apply", show=False),
   ```
   `show=False` matches the existing recovery bindings (`ctrl+shift+{r,x,y}`) —
   these are app-level recovery actions, not tab-scoped operations.

3. **Methods** — add a detailer block mirroring the patcher block
   (`_register_patcher_source` … `action_retry_patcher_apply`):
   - `_register_detailer_target(agent_name, target_node_id)` — store + ensure timer.
   - `_ensure_detailer_poll_timer()` / `_stop_detailer_poll_timer()` —
     `set_interval(5, self._poll_detailers)`.
   - `_scan_existing_detailers()` — scan `detailer_*_status.yaml`, skip non-`Completed`,
     skip already-applied via `_detailer_needs_apply`, recover `target_node_id`
     by matching the `## Target Node` Metadata line in `<agent>_input.md` with
     `_PATCHER_INPUT_META_RE` (same `-\s*Metadata:\s*\S+/br_nodes/(...)\.yaml`
     shape; reuse the existing compiled regex).
   - `_poll_detailers()` — timer tick; for each tracked detailer that is
     `Completed`, call `_try_apply_detailer_if_needed`; drop already-applied
     entries; stop timer when empty.
   - `_try_apply_detailer_if_needed(agent_name, target_node_id, force=False)` —
     single-shot apply; on success `notify` + `_clear_apply_banner` +
     `_load_existing_session`; on failure `_set_apply_banner(...)` with:
     `f"Detailer {agent_name} apply failed: {exc} — run \`ait brainstorm `
     `apply-detailer {self.task_num} {agent_name} {target_node_id}\` to retry"`.
     Uses `_set_apply_banner` (the shared initializer/explorer/synthesizer
     banner) — the detailer has no IMPACT verdict, so it does not use the
     patcher's `_set_impact_banner`.
   - `action_retry_detailer_apply()` — force-retry the most-recent (by
     `_status.yaml` mtime) tracked detailer.

4. **Register at launch** — in `_run_design_op()` `elif op == "detail":` branch,
   after `agents_list.append(agent)`, add:
   ```python
   self.call_from_thread(
       self._register_detailer_target, agent, cfg["node"],
   )
   ```

5. **Recover on session load** — in `_load_existing_session()`, after
   `self._scan_existing_synthesizers()`, add `self._scan_existing_detailers()`.

### Step 4 — CLI fallback `aitask_brainstorm_apply_detailer.sh` + `ait` dispatch

The failure banner tells the user to run `ait brainstorm apply-detailer …`, and
all three sibling roles ship a CLI fallback — so add it for consistency and to
make the banner actionable. (This is one file beyond the task's literal "Files
to touch" list; it is the standard sibling pattern and is surfaced here for the
plan-review checkpoint.)

- New `.aitask-scripts/aitask_brainstorm_apply_detailer.sh` — copy
  `aitask_brainstorm_apply_patcher.sh` verbatim, then: 3 args
  (`<task_num> <agent_name> <target_node_id>`); call `apply_detailer_output`;
  print `APPLIED:<plan_rel>` on success, `APPLY_FAILED:<error>` to stderr on
  failure (exit 1). Keep `require_ait_python` (short-lived CLI).
- `ait` dispatcher: add `apply-detailer)` case after `apply-patcher)` (line 248),
  a help line in the `--help` block, and `apply-detailer` to the unknown-subcommand
  `Available:` list (line 270).

### Step 5 — Tests

- New `tests/test_brainstorm_apply_detailer.py` (mirror
  `test_brainstorm_apply_patcher.py`): build a temp crew worktree with a target
  node + graph state; cases — happy path (plan written to
  `br_plans/<node>_plan.md`, node `plan_file` set, `current_head`/`next_node_id`
  unchanged); missing delimiters → `ValueError`; empty PLAN block → `ValueError`;
  missing output file → `FileNotFoundError`; missing target node →
  `FileNotFoundError` + `_apply_error.log` written; `_detailer_needs_apply`
  True/False (placeholder, applied, re-detail with changed content).
- New `tests/test_brainstorm_apply_detailer_cli.sh` (mirror
  `test_brainstorm_apply_patcher_cli.sh`): synthetic crew under a high task
  number, invoke the wrapper, assert `APPLIED:` output and on-disk state.

### `brainstorm_dag.py` — no change

`update_node()` already merges arbitrary fields, so `{"plan_file": ...}` works
today. Confirmed; nothing to add.

### Step 6 — Create the alignment follow-up task

The brainstorm detailer (`templates/detailer.md`) and the task-workflow
`planning.md` procedure both author implementation plans, and both feed
`aiplans/` (planning.md directly; the detailer via
`finalize_session()` → `aiplans/p<task>_<node>.md`). Their shared
"implementation-plan content contract" (specific file paths, exact per-file
changes, code snippets, dependency-ordered steps, prerequisites, testing,
verification checklist) is currently duplicated and will drift.

t741's delimiter change is purely structural (it wraps agent *output*; an
`<!-- include -->` would expand work2do *instructions*) — so t741 introduces
no new drift. The de-duplication is a separate cross-cutting refactor.

Deliverable: during implementation, create a standalone follow-up task via
`./.aitask-scripts/aitask_create.sh --batch` (see `task-creation-batch.md`):

- **Name:** `align_detailer_planning_plan_contract`
- **issue_type:** `refactor`, **priority:** `medium`, **labels:** `brainstorm`
- **Description:** Single-source the implementation-plan content contract
  shared by `templates/detailer.md` and `.claude/skills/task-workflow/planning.md`.
  Extract the contract into one canonical fragment (`templates/_plan_contract.md`),
  have `detailer.md` pull it via `<!-- include: _plan_contract.md -->`
  (resolved by `resolve_template_includes()` in `lib/agentcrew_utils.sh`), and
  embed the same content into `planning.md` at skill-render time. Regenerate
  task-workflow skill goldens, and port to the Codex/Gemini/OpenCode skill
  trees. Reference: t741 plan, `aidocs/planning_conventions.md` (its own
  "promote into planning.md" note is the same class of refactor).

## Files to modify

| File | Change |
|------|--------|
| `.aitask-scripts/brainstorm/templates/detailer.md` | Add `--- PLAN_START ---` / `--- PLAN_END ---` delimiters around the plan output |
| `.aitask-scripts/brainstorm/brainstorm_session.py` | Add `_DETAILER_DELIMITERS`, `_detailer_needs_apply()`, `apply_detailer_output()` |
| `.aitask-scripts/brainstorm/brainstorm_app.py` | Detailer auto-apply state, binding, hook methods; register in `_run_design_op` + `_load_existing_session` |
| `.aitask-scripts/aitask_brainstorm_apply_detailer.sh` | New CLI fallback (mirror apply-patcher) |
| `ait` | Dispatch `apply-detailer` subcommand + help text |
| `tests/test_brainstorm_apply_detailer.py` | New — engine apply tests |
| `tests/test_brainstorm_apply_detailer_cli.sh` | New — CLI round-trip test |
| _(new task)_ | Step 6 — follow-up task for detailer/planning.md contract alignment |

## Verification

```bash
# Engine + CLI tests
bash tests/test_brainstorm_apply_detailer.py        # or: python3 tests/...
bash tests/test_brainstorm_apply_detailer_cli.sh
# Regression — sibling apply flows must still pass
python3 tests/test_brainstorm_apply_patcher.py
python3 tests/test_brainstorm_apply_explorer.py
bash tests/test_brainstorm_apply_patcher_cli.sh
# Lint the new shell wrapper
shellcheck .aitask-scripts/aitask_brainstorm_apply_detailer.sh
# Brainstorm app still imports cleanly
python3 -c "import sys; sys.path.insert(0,'.aitask-scripts'); import brainstorm.brainstorm_app"
```

Manual TUI smoke test (optional, in a brainstorm session): run a `detail`
operation on a node; when the detailer agent completes, confirm the poll hook
writes `br_plans/<node>_plan.md`, sets `plan_file` on the node YAML, and
toasts "Detailer … applied". Force a failure (corrupt `_output.md`) to confirm
the banner appears and `ctrl+shift+d` / `ait brainstorm apply-detailer` retries.

## Post-implementation

- Per CLAUDE.md "Working on Skills / Custom Commands": this task touches engine
  code, not skills — no skill port needed for t741's own changes.
- The Step 6 follow-up task is created during implementation (not at archival),
  so it is visible in `aitask_ls.sh` regardless of t741's outcome.
- Per CLAUDE.md, after implementation run `/aitask-qa 741` for test-gap analysis.
- Step 9 (Post-Implementation): no separate branch (profile 'fast' works on the
  current branch); commit code + plan separately, then `./.aitask-scripts/aitask_archive.sh 741`.

## Final Implementation Notes

- **Actual work done:** Implemented all 6 planned steps exactly as designed.
  - `templates/detailer.md` — wrapped the plan output in
    `--- DETAILED_PLAN_START ---` / `--- DETAILED_PLAN_END ---` (Output section
    + Phase 3 bullet).
  - `brainstorm_session.py` — added `_DETAILER_DELIMITERS`,
    `_detailer_needs_apply()` (content-comparison guard), and
    `apply_detailer_output()` (writes `br_plans/<node>_plan.md`, sets
    `plan_file` via `update_node`, flips the detail group Completed; no node
    creation, no graph-state mutation).
  - `brainstorm_app.py` — detailer auto-apply state, `ctrl+shift+d` retry
    binding, 7 hook methods mirroring the patcher block, registration in
    `_run_design_op` and `_scan_existing_detailers()` in
    `_load_existing_session`.
  - New `aitask_brainstorm_apply_detailer.sh` CLI fallback + `ait` dispatch.
  - New `tests/test_brainstorm_apply_detailer.py` (16 tests) and
    `tests/test_brainstorm_apply_detailer_cli.sh` (8 checks).
- **Deviations from plan:** None. `brainstorm_dag.py` confirmed unchanged
  (`update_node()` already merges arbitrary fields).
- **Issues encountered:** None. All new tests pass; sibling apply regressions
  (patcher/explorer/synthesizer engine + CLI, brainstorm CLI, session) all
  still pass; `brainstorm_app` imports and compiles cleanly.
- **Key decisions:** (1) `_detailer_needs_apply` uses a plan-body content
  comparison rather than a bare "plan_file set" check, so re-detailing the
  same node (a later detailer with different content) is still applied.
  (2) The detailer reuses the patcher's `_PATCHER_INPUT_META_RE` to recover
  the target node from `<agent>_input.md` — the `## Target Node` Metadata line
  has the same `/br_nodes/<id>.yaml` shape. (3) Delimiter named
  `DETAILED_PLAN` (parallel to the patcher's `PATCHED_PLAN`) per user choice
  during planning — no churn to the shipped patcher.
- **Upstream defects identified:** None.

---
Task: t740_brainstorm_apply_synthesizer_output.md
Base branch: main
plan_verified: []
---

# t740 — Implement `apply_synthesizer_output()` for the brainstorm engine

## Context

The brainstorm engine has a complete end-to-end apply flow for the
**initializer**, **patcher**, and (since t739) **explorer** agents.
Synthesizer agents currently register and run to completion but produce
output that nothing parses — the user has to manually create the hybrid
node. This task closes that gap.

t739 (`apply-explorer`) introduced a shared, role-neutral helper
`_apply_node_output()` in `.aitask-scripts/brainstorm/brainstorm_session.py`
(line 832). Synthesizer output uses the **same** four-delimiter format
(`NODE_YAML_START/END` + `PROPOSAL_START/END`) — no `NEW_DIMENSIONS` block
— so this task reduces to:

1. Adding a thin entry point `apply_synthesizer_output()` that delegates
   to `_apply_node_output(..., expected_role="synthesizer")`.
2. Adding a thin `_synthesizer_needs_apply` alias for the TUI poller.
3. Wiring the brainstorm TUI to auto-call the apply hook when a
   synthesizer agent reaches `Completed` (mirror the explorer pattern).
4. Adding a CLI fallback `ait brainstorm apply-synthesizer <task> <agent>`
   for manual recovery + `ait` dispatcher wiring.
5. Tests covering happy path (including multi-parent hybrid),
   delimiter/error cases, and the `_synthesizer_needs_apply` matrix.

## Reference: explorer pattern (the template for this task)

Reuse rather than rewrite — `_apply_node_output` is already role-neutral
and t739's commit notes explicitly call out that "t740 can call
`_apply_node_output(task_num, agent_name, expected_role="synthesizer")`
directly".

- Engine: `brainstorm_session.py:832` (`_apply_node_output`),
  `:995` (`apply_explorer_output`), `:796` (`_explorer_needs_apply`),
  `:559` (`_agent_to_group_name` — already maps `synthesizer_NNN` →
  `hybridize_NNN`)
- TUI:
  - `brainstorm_app.py:2533` (binding `ctrl+shift+x` retry explorer)
  - `:2577-2580` (explorer state init in `__init__`)
  - `:3308` (`_scan_existing_explorers` called from
    `_load_existing_session`)
  - `:3553-3688` (explorer track / scan / poll / apply / retry block)
  - `:5249-5260` (in `_run_design_op` explorer branch — registers each
    fresh agent via `call_from_thread(self._register_explorer_agent, ...)`)
  - `:5271-5278` (`_run_design_op` synthesizer branch — currently
    registers the agent but does NOT track it)
- CLI: `aitask_brainstorm_apply_explorer.sh`; dispatcher `ait:246`
- Tests: `tests/test_brainstorm_apply_explorer.py`

## Implementation plan

### 1. `brainstorm_session.py` — engine entry points

Append (after `apply_explorer_output`, current file end):

```python
def _synthesizer_needs_apply(
    task_num: int | str, agent_name: str,
) -> bool:
    """Synthesizer alias for ``_explorer_needs_apply`` — the underlying
    check is role-neutral (delimiter presence + node_id collision).

    The alias exists so callers in ``brainstorm_app.py`` can read
    naturally (``_synthesizer_needs_apply(...)``) and to mirror the
    explorer / patcher symmetry.
    """
    return _explorer_needs_apply(task_num, agent_name)


def apply_synthesizer_output(
    task_num: int | str, agent_name: str,
) -> str:
    """Parse ``<agent_name>_output.md`` and integrate it as a new hybrid
    node.

    The synthesizer emits two delimited blocks
    (``NODE_YAML`` + ``PROPOSAL``) with no optional ``NEW_DIMENSIONS``
    block. The new node is parented on every source node listed in
    NODE_YAML's ``parents:`` field (synthesizers merge multiple nodes —
    `templates/synthesizer.md:131`). Head is advanced to the new node
    and the next-node-id counter is incremented.

    Returns:
        The new node_id (parsed from NODE_YAML).

    Raises:
        FileNotFoundError: output file missing.
        ValueError: any delimiter missing, NODE_YAML or proposal invalid,
            or the new node_id already exists.
    """
    new_id, _added = _apply_node_output(
        task_num, agent_name, expected_role="synthesizer",
    )
    return new_id
```

No other changes in this file — `_apply_node_output` already handles all
the synthesizer logic correctly:

- `_agent_to_group_name` maps `synthesizer_001` → `hybridize_001`
  (the no-parallel-suffix branch already verified at
  `brainstorm_session.py:559`).
- `NEW_DIMENSIONS` parsing is optional and a no-op when the tag is
  absent (synthesizer template doesn't emit it).
- Multi-parent handling: `create_node` already accepts
  `parents=node_data["parents"]` as a list — synthesizer's `parents`
  list just contains multiple entries.

### 2. `brainstorm_app.py` — TUI auto-apply hook

Mirror the explorer pattern exactly, swapping `explorer` → `synthesizer`
and using `ctrl+shift+y` for the retry binding.

**State init in `__init__`** (after the explorer state block at
`:2577-2580`):

```python
# Synthesizer auto-apply state. Tracked agent names produce a single
# hybrid node each via apply_synthesizer_output; the poll timer fires
# until every tracked agent has either applied or been dropped.
self._synthesizer_agents: set[str] = set()
self._applying_synthesizer: set[str] = set()
self._synthesizer_apply_errors: dict[str, str] = {}
self._synthesizer_poll_timer = None
```

**Binding** (after the `ctrl+shift+x` explorer binding at `:2533`):

```python
Binding("ctrl+shift+y", "retry_synthesizer_apply",
        "Retry synthesizer apply", show=False),
```

**`_load_existing_session` hook** (add after
`self._scan_existing_explorers()` at `:3308`):

```python
self._scan_existing_synthesizers()
```

**Tracking + polling methods** (add immediately after
`action_retry_explorer_apply` at `:3688` — keep the explorer block
intact and append a parallel synthesizer block):

```python
def _register_synthesizer_agent(self, agent_name: str) -> None:
    """Main-thread: track a freshly-registered synthesizer and ensure
    the poll timer is running."""
    self._synthesizer_agents.add(agent_name)
    self._ensure_synthesizer_poll_timer()

def _ensure_synthesizer_poll_timer(self) -> None:
    if self._synthesizer_poll_timer is not None:
        return
    if not self._synthesizer_agents:
        return
    self._synthesizer_poll_timer = self.set_interval(
        5, self._poll_synthesizers,
    )

def _stop_synthesizer_poll_timer(self) -> None:
    if self._synthesizer_poll_timer is not None:
        try:
            self._synthesizer_poll_timer.stop()
        except Exception:
            pass
        self._synthesizer_poll_timer = None

def _scan_existing_synthesizers(self) -> None:
    """Scan the worktree for completed synthesizer agents whose output
    hasn't been applied yet. Idempotent — safe to call from
    ``_load_existing_session``.
    """
    wt = self.session_path
    if not wt or not Path(wt).is_dir():
        return
    try:
        from brainstorm.brainstorm_session import _synthesizer_needs_apply
    except Exception:
        return
    for status_path in sorted(Path(wt).glob("synthesizer_*_status.yaml")):
        agent = status_path.stem[:-len("_status")]
        if agent in self._synthesizer_agents:
            continue
        try:
            data = read_yaml(str(status_path))
        except Exception:
            continue
        if (data or {}).get("status") != "Completed":
            continue
        if not _synthesizer_needs_apply(self.task_num, agent):
            continue
        self._synthesizer_agents.add(agent)
    self._ensure_synthesizer_poll_timer()

def _poll_synthesizers(self) -> None:
    """Timer tick: for each tracked synthesizer, apply its output if
    it's Completed. Drops entries whose output has already been applied
    (idempotent across restarts). Stops the timer when empty.
    """
    if not self._synthesizer_agents:
        self._stop_synthesizer_poll_timer()
        return
    try:
        from brainstorm.brainstorm_session import _synthesizer_needs_apply
    except Exception:
        return
    for agent in list(self._synthesizer_agents):
        if agent in self._applying_synthesizer:
            continue
        status_path = self.session_path / f"{agent}_status.yaml"
        if not status_path.is_file():
            continue
        try:
            data = read_yaml(str(status_path))
        except Exception:
            continue
        status = (data or {}).get("status", "")
        if status != "Completed":
            continue
        if not _synthesizer_needs_apply(self.task_num, agent):
            # Already applied (e.g., by CLI fallback). Drop and move on.
            self._synthesizer_agents.discard(agent)
            continue
        self._try_apply_synthesizer_if_needed(agent)
    if not self._synthesizer_agents:
        self._stop_synthesizer_poll_timer()

def _try_apply_synthesizer_if_needed(
    self, agent_name: str, force: bool = False,
) -> None:
    """Single-shot apply attempt for one synthesizer agent. Failures
    surface via the initializer apply banner; success refreshes the DAG.
    """
    if agent_name in self._applying_synthesizer:
        return
    from brainstorm.brainstorm_session import (
        _synthesizer_needs_apply,
        apply_synthesizer_output,
    )
    if not force and not _synthesizer_needs_apply(
        self.task_num, agent_name,
    ):
        return
    self._applying_synthesizer.add(agent_name)
    try:
        try:
            new_id = apply_synthesizer_output(self.task_num, agent_name)
        except Exception as exc:
            self._synthesizer_apply_errors[agent_name] = str(exc)
            self._set_apply_banner(
                f"Synthesizer {agent_name} apply failed: {exc} — "
                f"run `ait brainstorm apply-synthesizer "
                f"{self.task_num} {agent_name}` to retry"
            )
            return
        self._synthesizer_apply_errors.pop(agent_name, None)
        self._synthesizer_agents.discard(agent_name)
        self._clear_apply_banner()
        self.notify(f"Synthesizer {agent_name} applied → {new_id}.")
        self._load_existing_session()
    finally:
        self._applying_synthesizer.discard(agent_name)

def action_retry_synthesizer_apply(self) -> None:
    """ctrl+shift+y: force-retry the most recently failed synthesizer.

    If multiple synthesizers are tracked, picks the one with the most
    recent ``_status.yaml`` mtime.
    """
    if not self._synthesizer_agents:
        return
    candidates = list(self._synthesizer_agents)
    if len(candidates) == 1:
        agent = candidates[0]
    else:
        def _mtime(name: str) -> float:
            p = self.session_path / f"{name}_status.yaml"
            try:
                return p.stat().st_mtime
            except Exception:
                return 0.0
        agent = max(candidates, key=_mtime)
    self._try_apply_synthesizer_if_needed(agent, force=True)
```

**`_run_design_op` hook** (at `:5271-5278`, the existing hybridize
branch). Track the registered agent right after registration via
`call_from_thread`:

```python
elif op == "hybridize":
    agent = register_synthesizer(
        self.session_path, crew_id, cfg["nodes"],
        cfg["merge_rules"], group_name,
        launch_mode=launch_mode,
    )
    agents_list.append(agent)
    self.call_from_thread(
        self._register_synthesizer_agent, agent,
    )
    msg = f"Registered synthesizer: {agent}"
```

**Banner reuse:** reuse `_set_apply_banner` / `_clear_apply_banner`
(same generic widget already used by initializer and explorer).
Synthesizer has no IMPACT_FLAG so the patcher's dedicated impact banner
is not needed.

### 3. CLI fallback wrapper

New file: `.aitask-scripts/aitask_brainstorm_apply_synthesizer.sh`.
Copy `aitask_brainstorm_apply_explorer.sh` verbatim and adapt:

- Usage line: `ait brainstorm apply-synthesizer <task_num> <agent_name>`.
- Heredoc imports `apply_synthesizer_output` instead of
  `apply_explorer_output`.
- File-level docstring references the hybrid node + multi-parent
  semantics.

Wire into the `ait` dispatcher (`ait:246-268`):

- Add case: `apply-synthesizer)  exec "$SCRIPTS_DIR/aitask_brainstorm_apply_synthesizer.sh" "$@" ;;`
  immediately after the `apply-explorer` line.
- Add help line under `Available subcommands:`:
  `apply-synthesizer  Re-run apply on a synthesizer agent (recovers stuck hybrids)`
- Update the `Available:` error message at `ait:268`:
  `Available: init, status, list, archive, apply-initializer, apply-explorer, apply-synthesizer, apply-patcher, delete`.

### 4. Tests

New file: `tests/test_brainstorm_apply_synthesizer.py`. Adapt
`tests/test_brainstorm_apply_explorer.py` with the following changes:

- Drop the three `NEW_DIMENSIONS` tests
  (`test_new_dimensions_merged_into_graph_state`,
  `test_new_dimensions_none_is_noop`,
  `test_new_dimensions_absent_is_noop`) — synthesizer template doesn't
  emit that block. Keep "absent is no-op" behavior implicitly via the
  happy-path test (which omits the tag).
- Default `agent_name` becomes `"synthesizer_001"` (no parallel suffix).
- Default `_node_yaml` `node_id` becomes `"n001_hybrid"` and
  `created_by_group` becomes `"hybridize_001"`.
- Default `parents` list contains **two** source nodes
  (e.g. `["n000_init", "n001_explored"]`) to exercise multi-parent
  handling.
- `_seed_session` writes both source nodes so `create_node`'s parent
  validation passes.
- Replace the `test_missing_created_by_group_derived_from_agent_name`
  assertion to expect `"hybridize_001"` from `"synthesizer_001"`.
- Add a `test_multi_parent_node_links_all_parents` case asserting the
  new node's YAML on disk carries the full `parents:` list.
- `_synthesizer_needs_apply` test class covers: missing output, partial
  delimiters, full output + non-existing node, full output + existing
  node (mirrors explorer matrix).
- Error-log assertions reference `apply_synthesizer_output` instead of
  `apply_explorer_output` (the helper's catch-all uses
  `expected_role`, so logs say `apply_synthesizer_output failed at …`).
- Patch target stays `brainstorm.brainstorm_session.crew_worktree`.

### 5. Template verification

Read `.aitask-scripts/brainstorm/templates/synthesizer.md`:

- `--- NODE_YAML_START ---` / `--- NODE_YAML_END ---` ✓ (line 137-139).
- `--- PROPOSAL_START ---` / `--- PROPOSAL_END ---` ✓ (line 140-142).
- No `--- NEW_DIMENSIONS ---` tag — confirmed, and the parser is a
  no-op when absent.

No template changes expected.

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` — add
  `apply_synthesizer_output()` and `_synthesizer_needs_apply()` aliases
  at end of file.
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add synthesizer
  tracking / polling / apply methods, register binding
  `ctrl+shift+y`, call `_scan_existing_synthesizers()` from
  `_load_existing_session()`, track each registered agent in the
  `hybridize` branch of `_run_design_op`.
- `.aitask-scripts/aitask_brainstorm_apply_synthesizer.sh` — NEW
  (copy/adapt explorer wrapper).
- `ait` — add `apply-synthesizer` dispatch case + help text + error
  message.
- `tests/test_brainstorm_apply_synthesizer.py` — NEW.

## Verification

```bash
# Unit tests (new + regression on shared helper)
python -m unittest \
    tests.test_brainstorm_apply_synthesizer \
    tests.test_brainstorm_apply_explorer \
    tests.test_brainstorm_apply_patcher \
    tests.test_brainstorm_session -v

# Lint the new shell wrapper
shellcheck .aitask-scripts/aitask_brainstorm_apply_synthesizer.sh

# CLI smoke test
ait brainstorm apply-synthesizer        # exit 2 with usage line
ait brainstorm | grep apply-synthesizer  # listed in help

# Manual end-to-end (requires existing brainstorm session) — flag as
# manual_verification follow-up sibling at Step 8c:
#   1. ait brainstorm <task>            # open TUI
#   2. Trigger a hybridize operation with 2+ source nodes.
#   3. Wait for the synthesizer to reach Completed.
#   4. Confirm: TUI auto-applies, DAG refreshes with the new hybrid
#      node, parents list contains every source node, no error banner.
#   5. Inspect br_graph_state.yaml: head moved to the new node,
#      next_node_id incremented.
#   6. Force a failure (corrupt the _output.md), press ctrl+shift+y,
#      confirm banner appears with the apply-synthesizer CLI hint,
#      then run the hint command and confirm it surfaces the same
#      error and writes <agent>_apply_error.log.
```

End-to-end TUI verification is manual — candidate for an
`issue_type: manual_verification` follow-up sibling at Step 8c.

## Step 9 — Post-Implementation

Standard merge / archive flow per `task-workflow/SKILL.md` Step 9.
Build verification is the unit-test suite for the affected modules:

```bash
python -m unittest \
    tests.test_brainstorm_apply_synthesizer \
    tests.test_brainstorm_apply_explorer \
    tests.test_brainstorm_apply_patcher \
    tests.test_brainstorm_session -v

shellcheck .aitask-scripts/aitask_brainstorm_apply_synthesizer.sh
```

## Sibling-task handoff (t741 apply-detailer, t743 apply-patcher)

- t741 (detailer) — different output format (plan markdown only, no
  YAML). Cannot reuse `_apply_node_output`; will need its own helper.
  No coupling to this task.
- t743 (patcher) — already implemented and archived, predates the
  shared helper. Out of scope for the core work; a follow-up task is
  created in **Step 6 below** to track the reconciliation refactor.

## Follow-up task: patcher reconciliation

After the code/plan commits land (Step 8 "Commit changes"), but before
archival (Step 9), create a follow-up task that tracks collapsing the
patcher apply path into `_apply_node_output`. The patcher predates
t739's helper and uses a different output format (three blocks —
`PATCHED_PLAN`, `IMPACT`, `METADATA` per
`brainstorm_session.py:497-501`) versus the explorer/synthesizer
two-block format (`NODE_YAML` + `PROPOSAL`), so the reconciliation is
non-trivial: it requires either extending `_apply_node_output` with a
strategy/dispatch parameter, or extracting a more abstract helper that
both apply flows compose. The follow-up task scopes that work out of
t740.

**Create at end of Step 8 (after both commits succeed, before Step 8b
or Step 9 begins)** via the **Batch Task Creation Procedure** (see
`task-creation-batch.md`):

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name brainstorm_reconcile_patcher_into_apply_node_output \
  --priority low \
  --effort medium \
  --issue-type refactor \
  --labels brainstorm,refactor \
  --depends 740 \
  --desc-file - <<'EOF'
Reconcile the patcher apply path into the shared `_apply_node_output()`
helper introduced by t739 (`apply-explorer`).

## Background

`brainstorm_session.py:_apply_node_output()` is the shared engine core
for explorer (t739) and synthesizer (t740) apply flows. Both use the
two-block `NODE_YAML + PROPOSAL` output format and produce a single new
node parented as the agent specifies. The **patcher** apply path
(`apply_patcher_output`, `brainstorm_session.py:636`) predates the
shared helper. It uses a different three-block output format
(`PATCHED_PLAN_START/END`, `IMPACT_START/END`, `METADATA_START/END` —
see `_PATCHER_DELIMITERS` at `:497-501`) and the corresponding
`_patcher_needs_apply` at `:581`. The two flows currently duplicate:
node-id validation, `create_node` invocation, head/next-id advancement,
`update_operation` call, error-log writing, and the
`_NODE_NON_DIMENSION_FIELDS` dimension extraction.

## What to do

1. **Extract a parser-strategy abstraction.** Either
   - extend `_apply_node_output` with a callable that parses the
     output text into a `(node_data_dict, proposal_text, extras_dict)`
     tuple — explorer/synthesizer pass the two-block parser,
     patcher passes a three-block parser that also extracts the
     `IMPACT` block; or
   - introduce a thin layer above `_apply_node_output` that both flows
     compose.
2. **Migrate `apply_patcher_output`** to use the unified path. Preserve
   the patcher-specific behavior:
   - Source node lookup (`source_node_id` argument).
   - `IMPACT` payload returned alongside `new_node_id` (the TUI uses it
     to populate the impact banner).
   - `_patcher_apply_error.log` filename / message format.
3. **Confirm all patcher tests still pass** unchanged
   (`tests/test_brainstorm_apply_patcher.py`,
   `tests/test_brainstorm_apply_patcher_cli.sh`,
   `tests/test_brainstorm_apply_created_by_group.sh`).
4. **Confirm TUI patcher polling/apply/retry still works**
   (`brainstorm_app.py:_try_apply_patcher_if_needed`, retry binding
   `ctrl+shift+r`).

## Files likely to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` (rework
  `_apply_node_output` / `apply_patcher_output`).
- Possibly `brainstorm_app.py` if the patcher apply return signature
  changes (impact payload).
- No new tests required if the abstraction is invisible to callers;
  add targeted parser-strategy tests if the abstraction is exposed
  publicly.

## Constraints

- **No public-API breakage.** `apply_patcher_output`,
  `apply_explorer_output`, `apply_synthesizer_output` keep the same
  signatures and return types.
- **Out of scope:** t741 (detailer — different output entirely;
  separate helper). Don't try to fold detailer into the same
  abstraction.
EOF
```

If the follow-up task creation fails (script returns non-zero or
doesn't print `CREATED:<num>`), surface the error to the user but do
NOT abort the workflow — the task can be created manually with
`/aitask-create` later. The reconciliation is a clean-up refactor, not
a blocker for t740 archival.

## Final Implementation Notes

- **Actual work done:** Added `apply_synthesizer_output()` and
  `_synthesizer_needs_apply()` (both thin delegates onto t739's
  `_apply_node_output()` / `_explorer_needs_apply()`) at the end of
  `brainstorm_session.py`. Mirrored the explorer TUI flow in
  `brainstorm_app.py`: state init, `ctrl+shift+y` retry binding,
  `_scan_existing_synthesizers()` call from `_load_existing_session`,
  five tracking/polling/apply methods, and a `call_from_thread`
  registration hook in the `hybridize` branch of `_run_design_op`.
  Created CLI fallback `aitask_brainstorm_apply_synthesizer.sh`
  (adapted from explorer wrapper) and wired `apply-synthesizer` into
  the `ait` dispatcher (case, help text, error message). Added 14
  tests in `tests/test_brainstorm_apply_synthesizer.py` covering
  happy path, multi-parent linking, reference_files preservation,
  created_at autofill, created_by_group derivation
  (`synthesizer_001` → `hybridize_001`), error cases (missing output,
  missing delimiter, existing-node refusal, invalid YAML, invalid
  node data), and the `_synthesizer_needs_apply` matrix.
- **Deviations from plan:** None to the public-API surface. Two minor
  realignments while writing the tests:
  - Default `node_id` ended up as `n002_hybrid` (not `n001_hybrid`)
    because the seeded session contains `n000_init` + `n001_explored`
    as parents, so the new hybrid naturally takes `n002_*`.
  - Initial `next_node_id` set to `2` (not `1`) to match the seeded
    starting state.
- **Issues encountered:** None. Helper reuse from t739 was clean —
  `_apply_node_output` handled multi-parent synthesizer output
  end-to-end with no engine-side modification needed. The
  `NEW_DIMENSIONS` parser is genuinely optional and no-op when absent
  (synthesizer template doesn't emit it), confirmed by the
  test_creates_node_and_advances_head case.
- **Key decisions:**
  - Added `_synthesizer_needs_apply` as a thin alias for
    `_explorer_needs_apply` rather than renaming the explorer
    function to a role-neutral name. Rationale: keep `git blame`
    history intact on the existing function and let TUI callers read
    naturally; the patcher reconciliation follow-up will revisit
    naming if it merges paths.
  - Used `ctrl+shift+y` for retry (next available after explorer's
    `ctrl+shift+x` and patcher's `ctrl+shift+r`). `show=False` to
    avoid footer crowding — discoverable only via the banner hint.
  - Reused the generic `_set_apply_banner` / `_clear_apply_banner`
    widget (already shared by initializer and explorer); synthesizer
    has no impact-flag payload so the patcher's dedicated banner is
    unnecessary.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** t741 (detailer) cannot reuse
  `_apply_node_output` — different output format (plan markdown only,
  no YAML). The follow-up reconciliation task created here is
  patcher-only (t743 was already implemented before the helper).



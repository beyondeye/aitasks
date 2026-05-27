---
Task: t837_fix_failed_verification_t787_item3.md
Base branch: main
plan_verified: []
---

# t837 — Fix `ctrl+shift+x` retry path so the apply banner shows after explorer success

## Context

Manual-verification item #3 of t787 failed:

> Corrupt one explorer's `_output.md` (e.g. truncate the NODE_YAML block), press
> `ctrl+shift+x`, verify the apply banner shows the `apply-explorer` CLI hint.

Root cause (located in `.aitask-scripts/brainstorm/brainstorm_app.py`):

- The auto-apply loop discards an explorer from `self._explorer_agents`
  immediately after a successful apply (`brainstorm_app.py:4153`):
  ```python
  self._explorer_apply_errors.pop(agent_name, None)
  self._explorer_agents.discard(agent_name)
  self._clear_apply_banner()
  ```
- `action_retry_explorer_apply` (`brainstorm_app.py:4160-4179`) only retries
  agents currently in `self._explorer_agents`, and returns silently when the
  set is empty.
- `_scan_existing_explorers` (`brainstorm_app.py:4053-4084`) re-populates
  `_explorer_agents` on session load, but uses
  `_agent_apply_scan_should_track`, which only tracks Completed agents whose
  output still `_explorer_needs_apply`. Once the node exists in `br_nodes/`,
  `_explorer_needs_apply` returns False (`brainstorm_session.py:830`), so the
  agent is never re-tracked on subsequent opens either.

Verification sequence the user performed (per p739 §Verification step 6 and
the t787 PASS markers for items #1–#2):

1. Auto-apply ran on both explorers → nodes created, `_explorer_agents`
   drained.
2. User corrupted one `_output.md`.
3. User pressed `ctrl+shift+x` → `action_retry_explorer_apply` sees empty
   `_explorer_agents` → returns silently → no banner.

Items #4 (CLI hint command surfaces the same error) and #5 (`ait brainstorm
--help` lists `apply-explorer`) passed, confirming the engine-side and
dispatcher paths are correct. The defect is isolated to the TUI retry
action's candidate-discovery logic.

## Implementation plan

### 1. Rewrite `action_retry_explorer_apply` to scan the worktree

File: `.aitask-scripts/brainstorm/brainstorm_app.py` (currently lines
4160–4179).

Replace the body so that, when invoked, it walks
`self.session_path / "explorer_*_status.yaml"`, picks the most-recently-statused
agent whose `status` is `Completed`, and force-applies it via
`self._try_apply_explorer_if_needed(agent, force=True)`.

```python
def action_retry_explorer_apply(self) -> None:
    """ctrl+shift+x: force-retry an explorer apply.

    After a successful auto-apply the agent is discarded from
    ``self._explorer_agents`` (and ``_scan_existing_explorers`` will not
    re-track it because its node already exists), so we cannot rely on
    that set as the candidate source. Walk the worktree instead and pick
    the most-recently-statused Completed explorer. This is the retry
    path manual verification exercises by corrupting an already-applied
    explorer's ``_output.md``.
    """
    wt = self.session_path
    if not wt or not Path(wt).is_dir():
        return
    try:
        from brainstorm.brainstorm_session import _AGENT_FAILED_STATUSES
    except Exception:
        return
    candidates: list[tuple[str, float]] = []
    for status_path in Path(wt).glob("explorer_*_status.yaml"):
        agent = status_path.stem[: -len("_status")]
        try:
            data = read_yaml(str(status_path))
        except Exception:
            continue
        status = (data or {}).get("status", "")
        if status != "Completed" or status in _AGENT_FAILED_STATUSES:
            continue
        try:
            mtime = status_path.stat().st_mtime
        except Exception:
            mtime = 0.0
        candidates.append((agent, mtime))
    if not candidates:
        self.notify("No completed explorer agents to retry.")
        return
    agent = max(candidates, key=lambda p: p[1])[0]
    self._try_apply_explorer_if_needed(agent, force=True)
```

Notes on the change:

- `force=True` already bypasses the `_explorer_needs_apply` short-circuit at
  line 4138, so `_try_apply_explorer_if_needed` will call
  `apply_explorer_output()`. With a corrupted `_output.md` the engine raises,
  and the existing exception path (lines 4144–4150) sets
  `_set_apply_banner(...)` with the `apply-explorer` CLI hint exactly as the
  verification expects.
- On unexpected success (e.g. user uncorrupted the file before pressing the
  key), the existing success branch fires `_clear_apply_banner()` and
  refreshes the DAG — unchanged behavior.
- `_AGENT_FAILED_STATUSES` is `("Error", "Aborted")`, so the `status !=
  "Completed"` check already excludes them; the redundant clause stays as
  defensive documentation but can be dropped in review if preferred.
- `read_yaml` and `Path` are already imported at the top of the module
  (lines 9 and 87).
- The notification path ("No completed explorer agents to retry.") is new —
  previously the action was a silent no-op when `_explorer_agents` was
  empty. Keeping the no-op behavior is also acceptable; we'll add the
  notification because it makes the failure mode discoverable when the user
  has no Completed explorers in the session.

### 2. No engine changes required

`apply_explorer_output()`, `_explorer_needs_apply()`, the CLI fallback
(`.aitask-scripts/aitask_brainstorm_apply_explorer.sh`), the `ait`
dispatcher, and `tests/test_brainstorm_apply_explorer.py` are correct as-is.
Items #4 and #5 of the t787 checklist confirm this.

### 3. Tests

The retry action is a TUI binding that touches `self.session_path`,
`self.notify`, and Textual's reactive state — none of these are easily
exercised by the existing engine-level pytest suite. The repo has no
unit tests targeting `action_retry_*_apply` for the other agent roles
(patcher/synthesizer/detailer) either, so adding one only for explorer
would set a non-uniform precedent.

Therefore: **rely on manual re-verification** of t787 item #3 once the fix
lands, with an automated regression guard added later only if the parallel
fix for patcher/synthesizer/detailer (see Upstream defects below) lands as
a shared helper that admits a clean unit-test seam.

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_app.py` — replace
  `action_retry_explorer_apply` body (≈20 lines edited around
  lines 4160–4179).

## Verification

```bash
# Lint / sanity
python -c "import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_app.py').read())"

# Existing apply-explorer unit suite must still pass
python -m unittest tests.test_brainstorm_apply_explorer -v

# Targeted manual re-verification of t787 item #3 (must pass now):
#   1. ait brainstorm <task>             # open TUI
#   2. Trigger an explore op with 2 parallel explorers; let auto-apply run.
#   3. Confirm both explorers applied (DAG refreshed, no banner).
#   4. Truncate one explorer's _output.md inside its NODE_YAML block
#      (e.g. delete lines between NODE_YAML_START and NODE_YAML_END).
#   5. Press ctrl+shift+x.
#   6. Expect: the apply banner shows
#      "Explorer <agent> apply failed: ... — run `ait brainstorm
#      apply-explorer <task> <agent>` to retry".
#   7. Press ctrl+shift+x again with no corrupted file in scope
#      (after restarting / cleaning up) — expect "No completed explorer
#      agents to retry." notification (new behavior; previously silent).
```

Manual-verification follow-up sibling for this fix: surface at Step 8c so
the new banner + notification paths can be re-checked by the user in a
fresh TUI session.

## Upstream defects identified

The same candidate-discovery bug exists, symmetrically, in three sister
retry actions in `.aitask-scripts/brainstorm/brainstorm_app.py`:

- `brainstorm_app.py:4001 — action_retry_patcher_apply silently no-ops when
  self._patcher_sources is empty after a successful auto-apply, so the
  ctrl+shift+r banner path cannot be exercised on a previously-applied
  patcher.`
- `brainstorm_app.py:4315 — action_retry_synthesizer_apply has the same
  empty-tracking-set early return for ctrl+shift+y.`
- `brainstorm_app.py:4490 — action_retry_detailer_apply has the same
  empty-tracking-set early return.`

These are out of scope for t837 (which targets the t787 item #3 failure
only) but are real defects worth a follow-up bug task — likely a single
refactor that extracts the worktree-scan candidate-discovery into a shared
helper and reuses it across all four retry actions.

## Step 9 — Post-Implementation

Standard merge / archive flow per `task-workflow/SKILL.md` Step 9. No
shell wrappers or skill templates touched, so `ait skill verify` and
`shellcheck` are not required. Build verification is the existing
`tests.test_brainstorm_apply_explorer` suite plus an `ast.parse` sanity
check on the edited module.

## Final Implementation Notes

- **Actual work done:** Replaced the body of
  `action_retry_explorer_apply` in
  `.aitask-scripts/brainstorm/brainstorm_app.py` so it scans the
  worktree (`explorer_*_status.yaml`) for Completed explorer agents
  instead of consuming `self._explorer_agents`. The most-recently-statused
  Completed agent is force-applied via
  `self._try_apply_explorer_if_needed(agent, force=True)`. When no
  Completed explorer is found, the action now emits
  `self.notify("No completed explorer agents to retry.")` instead of
  silently no-op'ing.
- **Deviations from plan:** Dropped the redundant
  `status in _AGENT_FAILED_STATUSES` clause from the plan draft —
  `status != "Completed"` already excludes Error/Aborted/in-flight, and
  the import of `_AGENT_FAILED_STATUSES` it required was unused.
- **Issues encountered:** None. All 16 existing
  `tests.test_brainstorm_apply_explorer` tests pass after the edit
  (no engine logic touched).
- **Key decisions:**
  - Scanning the worktree on every ctrl+shift+x press is cheap
    (≤ a handful of `_status.yaml` files per session) and keeps the
    auto-apply poll loop unchanged — the alternative (keeping applied
    agents in `_explorer_agents`) would risk re-triggering apply for
    successfully-applied explorers on every poll tick.
  - Added a user-facing `notify(...)` for the no-candidates path; the
    previous silent no-op was undiscoverable when verifying the
    feature manually.
- **Upstream defects identified:**
  - `.aitask-scripts/brainstorm/brainstorm_app.py:4001 —
    action_retry_patcher_apply silently no-ops once
    self._patcher_sources is drained by successful auto-apply, so
    ctrl+shift+r cannot exercise the patcher banner path on a
    previously-applied patcher.`
  - `.aitask-scripts/brainstorm/brainstorm_app.py:4315 —
    action_retry_synthesizer_apply has the same drained-set early
    return for ctrl+shift+y.`
  - `.aitask-scripts/brainstorm/brainstorm_app.py:4490 —
    action_retry_detailer_apply has the same drained-set early
    return.`

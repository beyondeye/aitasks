---
Task: t670_n000_needs_apply_premature_true_on_tui_load.md
Base branch: main
plan_verified: []
---

# Plan: t670 — Tighten `n000_needs_apply` to require all four delimiters

## Context

`ait brainstorm init <N> --proposal-file <plan>` shows the banner

> Initializer apply failed: missing delimiter: NODE_YAML_START/NODE_YAML_END
> — run `ait brainstorm apply-initializer <N>` to retry

immediately on TUI mount, before the initializer agent has produced anything
usable.

**Root cause** (verified in code):
- `aitask_crew_addwork.sh:201-203` writes a placeholder `_output.md` at agent
  registration time:
  ```
  # Output from agent: <name>

  This file is populated by the agent during/after execution.
  ```
- `brainstorm_session.py:n000_needs_apply()` (lines 267–283) returns `True`
  as soon as `n000_init.yaml` and `initializer_bootstrap_output.md` both
  exist AND the n000 description starts with
  `"Imported proposal (awaiting reformat):"`. With the placeholder above
  in place, this is true the moment the agent is registered.
- `brainstorm_app.py:_load_existing_session()` (line 1937) and the
  initializer-only mount path (line 3477) both call
  `_try_apply_initializer_if_needed()`, which calls
  `apply_initializer_output()` → `_extract_block()` raises
  `ValueError("missing delimiter: …")` → banner shown.

The 2 s polling timer (`_poll_initializer`, lines 3484–3534) gates on agent
`status == "Completed"` independently, so the eventual success path is
unaffected. `ctrl+r` retry uses `force=True` and bypasses
`n000_needs_apply` entirely. The fix is purely about suppressing the
spurious early apply attempt on TUI mount.

## Why all four delimiters (not just `NODE_YAML_START`)

The task description suggests checking only `NODE_YAML_START`. That is
necessary but not sufficient: the agent may have emitted the start
delimiter but not yet `NODE_YAML_END`, `PROPOSAL_START`, or
`PROPOSAL_END`. `apply_initializer_output()` calls `_extract_block` twice
(lines 337–338) — both pairs must be present, or the same banner re-fires.

A natural alternative is to gate on the agent's `_status.yaml` showing
`status == "Completed"`. That would break the deliberate post-`Error`/
`Aborted` re-apply path at `brainstorm_app.py:3520-3534`, which is
intended to apply late-arriving output even when the agent's status
ended in `Error`/`Aborted`. The four-delimiter content check captures
the same readiness signal without coupling to status.

Sole caller of `n000_needs_apply` is `_try_apply_initializer_if_needed`
(`brainstorm_app.py:1952`); the manual `apply-initializer <N>` shell
entrypoint goes straight to `apply_initializer_output()` and is
unaffected.

## Files to modify

1. `.aitask-scripts/brainstorm/brainstorm_session.py` — tighten
   `n000_needs_apply` (lines 267–283).
2. `tests/test_brainstorm_session.py` — **new file**; unit tests for
   `n000_needs_apply`. Closest pattern reference:
   `tests/test_brainstorm_init_failure_modal.py` (`unittest` +
   `tempfile` + `unittest.mock.patch`).

## Implementation

### 1. Tighten `n000_needs_apply`

Replace the function body so it requires all four delimiter tokens to be
present in `initializer_bootstrap_output.md`. Until they are, the agent
has not produced a complete structured payload and the function returns
`False`.

```python
_INITIALIZER_DELIMITERS = (
    "NODE_YAML_START",
    "NODE_YAML_END",
    "PROPOSAL_START",
    "PROPOSAL_END",
)


def n000_needs_apply(task_num: int | str) -> bool:
    """Return True iff n000_init is still a placeholder AND the
    initializer output file contains all four delimiter blocks
    expected by ``apply_initializer_output``.

    The delimiter check guards against the placeholder ``_output.md``
    that ``aitask_crew_addwork.sh`` writes at agent-registration time
    (before the agent runs), and against mid-stream agent writes
    where only some delimiters have been emitted so far.
    """
    wt = crew_worktree(task_num)
    node_path = wt / NODES_DIR / "n000_init.yaml"
    out_path = wt / "initializer_bootstrap_output.md"
    if not node_path.is_file() or not out_path.is_file():
        return False
    try:
        data = read_yaml(str(node_path))
    except Exception:
        return False
    desc = (data or {}).get("description", "")
    if not desc.startswith("Imported proposal (awaiting reformat):"):
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    return all(token in text for token in _INITIALIZER_DELIMITERS)
```

The delimiter-tuple constant lives at module scope (next to the existing
`_PROBLEM_VALUE_RE` private helpers) so the agent template (in
`templates/initializer.md`) and `apply_initializer_output()` aren't the
only places the four token names appear.

### 2. New test file: `tests/test_brainstorm_session.py`

Pattern follows `tests/test_brainstorm_init_failure_modal.py`. Each test
uses `tempfile.TemporaryDirectory` and patches
`brainstorm.brainstorm_session.crew_worktree` to point at the temp dir.
Helper builds a minimal `br_nodes/n000_init.yaml` and an output file
with chosen content.

Cases:

1. **`test_returns_false_when_output_only_has_placeholder`** —
   placeholder text from `aitask_crew_addwork.sh:201-203`; expect `False`.
2. **`test_returns_false_when_only_node_yaml_start_present`** —
   output contains `--- NODE_YAML_START ---` but NOT `NODE_YAML_END`,
   `PROPOSAL_START`, or `PROPOSAL_END`; expect `False`. (This is the
   case that motivated tightening beyond the task description's
   suggestion.)
3. **`test_returns_false_when_only_node_block_complete`** —
   contains `NODE_YAML_START` + `NODE_YAML_END` but no proposal block;
   expect `False`.
4. **`test_returns_true_when_all_four_delimiters_present`** —
   contains all four tokens; expect `True`. Body content does not need
   to validate (this function only screens, it doesn't parse).
5. **`test_returns_false_when_output_file_missing`** — only
   `n000_init.yaml`; expect `False`.
6. **`test_returns_false_when_node_file_missing`** — only output file
   with all four delimiters; expect `False`.
7. **`test_returns_false_when_description_does_not_match`** —
   `description: "Some other description"` even with all four
   delimiters; expect `False`.

## Verification

1. **Unit tests** — `python tests/test_brainstorm_session.py`. (The
   existing sibling `test_brainstorm_init_failure_modal.py` is run the
   same way via `unittest.main()`.) Expect all seven cases to PASS.
2. **No other tests should regress.** This change only relaxes
   `n000_needs_apply` — it returns `False` in cases where it previously
   returned `True`. Callers gated on `force=True` (`ctrl+r` retry) or
   on agent status (`_poll_initializer`) are unaffected.
3. **Manual end-to-end** (per the task description):
   - `ait brainstorm delete <N>` (if a stale session exists)
   - `ait brainstorm init <N> --proposal-file <plan>`
   - Open the TUI immediately; confirm the apply-failed banner does
     **not** appear.
   - Wait for the initializer agent (interactive mode after t663) to
     finish; confirm `_poll_initializer` picks up `Completed`, calls
     `apply_initializer_output()`, and the proposal is imported cleanly.

## Risk / unaffected paths

- `_poll_initializer` (`brainstorm_app.py:3502-3519`) does NOT call
  `n000_needs_apply`; it gates on `status == "Completed"` and calls
  `apply_initializer_output()` directly — unaffected.
- `action_retry_initializer_apply` / `ctrl+r` (line 1989) uses
  `force=True`, which short-circuits the `n000_needs_apply` check —
  unaffected.
- The post-`Error`/`Aborted` re-apply (lines 3520–3534) calls
  `_try_apply_initializer_if_needed()` without `force`. With the new
  guard it now correctly waits until the agent's eventual output
  contains all four delimiters before attempting to apply. This is the
  desired behavior.
- `aitask_brainstorm_apply_initializer.sh` invokes
  `apply_initializer_output()` directly (no `n000_needs_apply` call).

## Follow-up task to create

After committing t670 (during Step 8c, before Step 9 archive), create a
new aitask via `aitask_create.sh --batch` capturing the deeper
heartbeat/status redesign idea raised in planning:

- **Title:** *Separate heartbeat freshness from agent terminal status*
- **issue_type:** `refactor`
- **Priority/Effort:** medium / high
- **Labels:** `ait_brainstorm`, `agentcrew`
- **Description gist:** Currently the agent-crew runner can flip a
  still-running agent's `_status.yaml` to `Error` purely because its
  heartbeat hasn't arrived in time. This corrupts the meaning of
  `status` (cause of t653_1 having to soften the Error/Aborted branch
  with a slow-watcher fallback). Redesign: keep `status` reflecting the
  agent's own self-reported lifecycle (`Running`/`Completed`/`Error`/
  `Aborted`) and surface heartbeat freshness as a separate field
  (e.g., `last_heartbeat_at`, `heartbeat_stale: bool`). Consumers that
  currently mistrust `status` (the brainstorm TUI's `_poll_initializer`
  Error/Aborted branch, the slow watcher loop) can become simpler once
  status is trustworthy. Must include migration plan for existing
  `_status.yaml` files and audit of every consumer that reads
  `status`.
- **References to include in body:** archived plan
  `aiplans/archived/p653/p653_1_brainstorm_tui_self_heal_apply.md`
  (for the original t653_1 motivation) and t670 itself (planning
  conversation that surfaced the redesign).

This belongs as its own task — not as a child of t670 — because it
touches the agent-crew runner, the status enum semantics, and every
consumer of `_status.yaml` (brainstorm TUI is just one). Out of scope
for t670, which is a narrow placeholder-on-mount symptom fix that
remains correct independent of the redesign.

## Step 9 reminder

After Step 8 review/commit, Step 9 archives the task and pushes via
`./ait git push`. No worktree was created (profile `fast`:
`create_worktree: false`), so worktree cleanup steps are skipped.

## Final Implementation Notes

- **Actual work done:** Replaced `n000_needs_apply` body in
  `.aitask-scripts/brainstorm/brainstorm_session.py` with the
  four-delimiter check exactly as planned. Added a module-level
  `_INITIALIZER_DELIMITERS` tuple alongside `_PROBLEM_VALUE_RE`. Added
  new test file `tests/test_brainstorm_session.py` with 7 unit tests
  using `tempfile.TemporaryDirectory` + `unittest.mock.patch` against
  `brainstorm.brainstorm_session.crew_worktree`.
- **Deviations from plan:** None on the source change. Test file
  matches the plan's seven cases exactly; the `_seed` helper accepts
  `desc=None` / `output=None` to skip seeding the respective file
  (used by the missing-file cases).
- **Issues encountered:** None. All 7 new tests passed on first run.
  `tests/test_brainstorm_init_failure_modal.py` (10 tests) still
  passes, confirming no regression in the sibling test surface.
- **Key decisions:** Chose the four-delimiter check over a
  status-Completed gate after tracing the code path back to t653_1
  (`aiplans/archived/p653/p653_1_brainstorm_tui_self_heal_apply.md`),
  which deliberately distrusts `_status.yaml` because the agent-crew
  runner can flip a still-running agent to `Error` on missed
  heartbeats. A status-based gate would regress that self-heal path.
  Spun off **t671** (`refactor`, medium/high, labels:
  `ait_brainstorm,agentcrew`) capturing the deeper redesign: separate
  heartbeat freshness from agent terminal status.
- **Build verification:** Not applicable —
  `aitasks/metadata/project_config.yaml` has `test_command: null` /
  `lint_command: null` and no `verify_build` field. Manual
  verification (the live brainstorm-init smoke test in the task
  description) is not run as part of this commit; t671's QA scope
  may pick that up.

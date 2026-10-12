---
Task: t1950_targeted_session_ownership_for_focus_existing_agent_window.md
Base branch: main
Output branch: main
---

# t1950 — Targeted session ownership for `focus_existing_agent_window`

## Context

`focus_existing_agent_window(task_id, project_root)`
(`.aitask-scripts/lib/agent_launch_utils.py:517`) is called on every board `p` /
`g` press and every trails `p` press. Today it calls
`_sessions_owned_by(project_root)` (`:502`), which runs the whole-server
`discover_aitasks_sessions()`. That issues a `list-panes` call, and when no pane
resolves a `show-environment` call, for **every** unregistered session on the
gateway server, including other projects' sessions. Only two sessions ever need
attributing: the caller's verified session and the configured `default_session`.

The goal is to attribute only those candidates, with the **same** canonical
per-session rule `_collect_live_roots` uses (stamp → pane vote → legacy
registry), shared rather than forked.

## Approach

Get the session names and registration stamps from one `list-sessions` call,
which already carries the stamp through `_SESSION_LIST_FORMAT`. Keep only the
candidate names, then run the per-session rule on just those. A candidate that
is not in the `list-sessions` answer does not exist, so it is not owned and
costs no further query. The filter matches exact session names, so tmux
target resolution never comes into it.

### 1. `agent_launch_utils.py` — extract the per-session resolver

Add next to `_unregistered_root` (`:1468`):

```python
def _attribute_session(session, registered, run, read_registry) -> Path | None:
    """One session's project root by the canonical rule (t1922): the
    registration stamp from its ``list-sessions`` line, else the pane vote,
    else the legacy registry. ``None`` = unattributed (positive evidence only)."""
    project_root = _registered_root(registered)
    if project_root is None:
        project_root = _unregistered_root(
            session, run(_list_panes_argv(session)), read_registry)
    return project_root
```

### 2. `_collect_live_roots` — call it, plus an optional `only` filter

```python
def _collect_live_roots(run, read_registry, only=None) -> list[tuple[str, Path]]:
    ...
    for session, registered in entries:
        if only is not None and session not in only:
            continue
        project_root = _attribute_session(session, registered, run, read_registry)
        if project_root is None:
            continue
        live_roots.append((session, project_root))
```

Add a docstring sentence: `only` limits the walk to the named sessions, and an
excluded session issues no per-session query. The default `only=None` keeps
every existing caller byte-identical: `discover_aitasks_sessions`,
`discover_aitasks_sessions_checked`, and the seam tests. The async sibling
`discover_aitasks_sessions_async` keeps its inline copy, because it cannot call
a sync runner. It already applies the same three rules, and the
`test_discover_async_parity` / `_everywhere` parity tests pin that.

### 3. `_sessions_owned_by(project_root, candidates)` — targeted

```python
def _sessions_owned_by(project_root: Path, candidates) -> set[str]:
    names = {c for c in candidates if c}
    if not names:
        return set()
    want = _root_key(Path(project_root))
    return {session for session, root in _collect_live_roots(
                _TMUX.run, _read_registry_entry, only=names)
            if _root_key(root) == want}
```

Update the docstring to say only the named candidates are attributed (at most
two), so another project's sessions are never listed. Keep the existing
paragraph on why name ≠ ownership.

### 4. `focus_existing_agent_window` — compute the candidates first

```python
candidates = (current_tmux_session(),
              load_tmux_defaults(project_root)["default_session"])
owned = _sessions_owned_by(project_root, candidates)
session = next((c for c in candidates if c and c in owned), None)
```

The contract is unchanged: same priority (caller first), same positive-evidence
rule, same return value. Update the docstring to mention that only the
candidates are attributed.

### 5. Tests

- **`tests/test_pick_command_screen.py`, `FocusExistingAgentWindowTests.setUp`**:
  ownership used to be stubbed through `discover_aitasks_sessions`, which is no
  longer on this path. Re-point that one stub at `alu._collect_live_roots` with
  a fake that honours `only`:
  `lambda run, reg, only=None: [(s.session, s.project_root) for s in self.discovered if only is None or s.session in only]`.
  Update the class docstring line. **No assertion changes.**
  `LiveTwoServerTests` stays untouched: it runs the real code on private
  servers.
- **`tests/test_board_inflight_view.py:248`** patches `_sessions_owned_by` with
  `return_value=`, so the new signature is transparent. No change.
- **New: `tests/test_session_root_resolution.py`, class
  `TargetedOwnershipTests(_Base)`** reuses the `_Server` fake, so it needs no
  tmux. The server has:
  `mine` (unregistered, panes in `repo_a`), `other` (unregistered, panes in
  `repo_b`), `stray` (unregistered, no panes, so it would cost a
  `show-environment`), and `stamped` (stamp = `repo_b`).
  `alu._TMUX = server`, and `current_tmux_session` / `load_tmux_defaults` /
  `find_window_by_name` are patched.
  1. `test_lookup_lists_no_unrelated_session`: caller `mine`, default
     `missing`, and a window in `mine`.
     `focus_existing_agent_window("42", repo_a)` is True. `server.cmds("list-panes")`
     targets only `mine`, and `show-environment` is never issued for `other` or
     `stray`.
  2. `test_missing_candidate_is_not_owned_and_costs_nothing`: caller `None`,
     default `missing`. Returns False, `find_window_by_name` is never called,
     and the only tmux call is the one `list-sessions`.
  3. `test_stamped_candidate_of_another_project_is_not_owned`: caller `stamped`
     (stamp = `repo_b`), default `missing`. Returns False and issues no
     `list-panes` at all, because the stamp is authoritative.
  4. Parity control, `test_unfiltered_walk_still_attributes_every_session`:
     `_collect_live_roots(server.run, reg)` with no `only` still returns `mine`,
     `other` and `stamped`, so the filter is the only difference.

## Verification

```bash
python3 tests/test_pick_command_screen.py          # incl. LiveTwoServerTests
python3 tests/test_session_root_resolution.py      # new tests + t1922 rules
python3 tests/test_discover_checked.py
python3 tests/test_discover_async_parity.py
python3 tests/test_board_inflight_view.py
```

Negative control on the new test: temporarily revert `_sessions_owned_by` to the
whole-server walk in a scratch copy (not the shared tree) and confirm
`test_lookup_lists_no_unrelated_session` fails. Alternatively, assert directly
that the old path would list `other`, which the parity test already shows.

## Step 9

Post-implementation: commit the code (`performance: … (t1950)`), then archive
via Step 9 of the task workflow.

## Risk

### Code-health risk: low
None identified. The change is contained in one module and the default (`only=None`)
discovery path is unchanged and pinned by the existing t1922 / parity suites.

### Goal-achievement risk: low
None identified. The task's three verification bullets map directly onto the
unchanged contract tests, the new no-`list-panes` test, and the untouched discovery suites.

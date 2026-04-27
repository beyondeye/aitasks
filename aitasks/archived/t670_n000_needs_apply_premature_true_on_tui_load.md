---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 12:17
updated_at: 2026-04-27 13:20
completed_at: 2026-04-27 13:20
---

The brainstorm TUI shows the banner "Initializer apply failed: missing
delimiter: NODE_YAML_START/NODE_YAML_END — run `ait brainstorm
apply-initializer <N>` to retry" **immediately** after
`ait brainstorm init <N> --proposal-file <plan>` opens the TUI, before
the initializer agent has had any chance to write its output.

## Root cause

`brainstorm_session.py:n000_needs_apply()` (line 267) returns `True` as
soon as:
- `n000_init.yaml` exists, AND
- `initializer_bootstrap_output.md` exists, AND
- the n000 description starts with "Imported proposal (awaiting reformat):"

`aitask_crew_addwork.sh` creates `<agent>_output.md` immediately when
the agent is registered, populated with a placeholder template (no
`NODE_YAML_START` block). So `n000_needs_apply()` returns `True` from
the moment registration completes, even though the agent has produced
nothing usable yet.

`brainstorm_app.py:_try_apply_initializer_if_needed()` (line 1939) is
called from `_load_existing_session()` on TUI mount. With
`n000_needs_apply()` returning True prematurely, it calls
`apply_initializer_output()` → `_extract_block()` raises
`ValueError("missing delimiter: NODE_YAML_START/NODE_YAML_END")` →
banner is shown. The 2 s polling timer (`_poll_initializer`) still
correctly waits for agent `Completed` status before the real apply,
so success cases work — but the user always sees a spurious failure
banner first.

## Fix

Tighten `n000_needs_apply` in
`.aitask-scripts/brainstorm/brainstorm_session.py` to also require that
`initializer_bootstrap_output.md` actually contains the
`NODE_YAML_START` delimiter token. Until that token appears the agent
has not produced anything to apply, so the function should return
`False` and the TUI should suppress the apply attempt.

```python
def n000_needs_apply(task_num: int | str) -> bool:
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
    return "NODE_YAML_START" in text
```

The 2 s polling (`brainstorm_app.py:_poll_initializer`) already gates
its apply on agent `status == "Completed"`, so the success path is
unaffected. The user-initiated `ctrl+r` retry uses `force=True` and
bypasses `n000_needs_apply` entirely, so a manual retry still works
even on a partially-written output file.

## Verification

1. Add a unit test in `tests/test_brainstorm_session.py` (create
   if it does not exist, otherwise extend the existing one):
   - Set up a temporary crew worktree with seeded n000_init.yaml
     (placeholder description) and an output.md containing only the
     placeholder template.
   - Assert `n000_needs_apply()` returns `False`.
   - Append a NODE_YAML_START block to output.md, re-run, assert
     `True`.
2. Manual end-to-end check:
   - `ait brainstorm delete <N>` (if a stale session exists)
   - `ait brainstorm init <N> --proposal-file <plan>`
   - Open the TUI immediately. Confirm no apply-failed banner
     appears.
   - Wait for the agent (which now correctly launches in interactive
     mode after t663) to finish. Confirm the polling picks it up and
     applies cleanly.

## Related

Follow-up to t663 (which fixed the upstream bug where the initializer
agent was registered as `headless` and hung). t663 prevented permanent
failure; this task removes the misleading immediate banner.

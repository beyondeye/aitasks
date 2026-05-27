---
Task: t841_fix_brainstorm_retry_apply_drained_set.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan: Fix brainstorm retry-apply actions silently no-op'ing after drained tracking sets

## Context

t837 fixed `action_retry_explorer_apply`: after a successful auto-apply,
`self._explorer_agents.discard(agent_name)` empties the tracking set, the next
`_scan_existing_explorers` doesn't re-add it (because the node already exists),
and `ctrl+shift+x` then silently returned. t837's fix replaced the in-memory
lookup with a worktree scan of `explorer_*_status.yaml` files filtered by
`status == "Completed"`, picking the most recently mtime'd one.

The same drained-set bug exists in three sibling retry actions:
- `action_retry_patcher_apply` (ctrl+shift+r) — `brainstorm_app.py:4001`
- `action_retry_synthesizer_apply` (ctrl+shift+y) — `brainstorm_app.py:4328`
- `action_retry_detailer_apply` (ctrl+shift+d) — `brainstorm_app.py:4503`

Each early-returns when its tracking container
(`self._patcher_sources` / `self._synthesizer_agents` / `self._detailer_targets`)
is empty, which happens after every successful auto-apply. Re-tracking in
`_scan_existing_<role>s` is gated on `_<role>_needs_apply()` returning True,
which it does not once the resulting node exists. So pressing the retry binding
after auto-apply is a no-op on a previously-applied agent — the exact failure
mode t787 item #3 (and now t837) addresses for explorer.

Patcher and detailer additionally need to recover an extra metadata id
(`source_node_id` / `target_node_id`) for the apply call. Both helpers already
parse this from `<agent>_input.md` via `_PATCHER_INPUT_META_RE`
(see `_scan_existing_patchers` line 3892 and `_scan_existing_detailers`
line 4411).

## Approach

Add a small private helper that performs the worktree scan once, then rewrite
all four retry actions to use it. The helper returns the agent name (or
`None`); the four call sites differ only in (a) the role prefix and (b) what
they pass to `_try_apply_<role>_if_needed`.

### Helper

Add a method on `BrainstormApp` near the existing `action_retry_*` cluster:

```python
def _pick_completed_agent_for_retry(self, role: str) -> str | None:
    """Walk the session worktree and return the agent name with the most
    recent ``_status.yaml`` mtime whose status is ``Completed``, for the
    given role prefix (``patcher``, ``synthesizer``, ``detailer``,
    ``explorer``). Returns ``None`` if the worktree is missing or no
    Completed agent is found. Used by ``action_retry_*_apply`` so the
    retry path keeps working after auto-apply has drained the in-memory
    tracking set.
    """
    wt = self.session_path
    if not wt or not Path(wt).is_dir():
        return None
    candidates: list[tuple[str, float]] = []
    for status_path in Path(wt).glob(f"{role}_*_status.yaml"):
        agent = status_path.stem[: -len("_status")]
        try:
            data = read_yaml(str(status_path))
        except Exception:
            continue
        if (data or {}).get("status", "") != "Completed":
            continue
        try:
            mtime = status_path.stat().st_mtime
        except Exception:
            mtime = 0.0
        candidates.append((agent, mtime))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p[1])[0]
```

### Rewrites

**`action_retry_patcher_apply`** (line 4001) — replace the body with:

```python
def action_retry_patcher_apply(self) -> None:
    """ctrl+shift+r: force-retry a patcher apply.

    Walks the worktree (rather than the in-memory tracking set) so the
    retry works after auto-apply has already drained
    ``self._patcher_sources``. Recovers ``source_node_id`` from
    ``self._patcher_sources`` if present, else from the agent's
    ``_input.md`` via ``_PATCHER_INPUT_META_RE``.
    """
    agent = self._pick_completed_agent_for_retry("patcher")
    if agent is None:
        self.notify("No completed patcher agents to retry.")
        return
    source = self._patcher_sources.get(agent)
    if source is None:
        source = self._recover_node_id_from_input(agent)
    if source is None:
        self.notify(f"Cannot retry {agent}: source_node_id not recoverable.")
        return
    self._try_apply_patcher_if_needed(agent, source, force=True)
```

**`action_retry_synthesizer_apply`** (line 4328) — replace the body with:

```python
def action_retry_synthesizer_apply(self) -> None:
    """ctrl+shift+y: force-retry a synthesizer apply.

    Walks the worktree (rather than ``self._synthesizer_agents``) so the
    retry works after auto-apply has drained the tracking set.
    """
    agent = self._pick_completed_agent_for_retry("synthesizer")
    if agent is None:
        self.notify("No completed synthesizer agents to retry.")
        return
    self._try_apply_synthesizer_if_needed(agent, force=True)
```

**`action_retry_detailer_apply`** (line 4503) — replace the body with:

```python
def action_retry_detailer_apply(self) -> None:
    """ctrl+shift+d: force-retry a detailer apply.

    Walks the worktree (rather than ``self._detailer_targets``) so the
    retry works after auto-apply has drained the tracking dict. Recovers
    ``target_node_id`` from ``self._detailer_targets`` if present, else
    from the agent's ``_input.md`` via ``_PATCHER_INPUT_META_RE``.
    """
    agent = self._pick_completed_agent_for_retry("detailer")
    if agent is None:
        self.notify("No completed detailer agents to retry.")
        return
    target = self._detailer_targets.get(agent)
    if target is None:
        target = self._recover_node_id_from_input(agent)
    if target is None:
        self.notify(f"Cannot retry {agent}: target_node_id not recoverable.")
        return
    self._try_apply_detailer_if_needed(agent, target, force=True)
```

**`action_retry_explorer_apply`** (line 4160) — refactor onto the same helper,
since its inline scan is structurally identical (less the role prefix). The
new body becomes:

```python
def action_retry_explorer_apply(self) -> None:
    """ctrl+shift+x: force-retry an explorer apply.

    Walks the worktree so the manual retry path keeps working after
    auto-apply has already drained ``self._explorer_agents`` — see t787
    item #3 and t837.
    """
    agent = self._pick_completed_agent_for_retry("explorer")
    if agent is None:
        self.notify("No completed explorer agents to retry.")
        return
    self._try_apply_explorer_if_needed(agent, force=True)
```

### `_input.md` node-id recovery helper

Add a small helper used by both patcher and detailer rewrites — both already
do this work inside their `_scan_existing_*` methods using the shared
`_PATCHER_INPUT_META_RE`:

```python
def _recover_node_id_from_input(self, agent: str) -> str | None:
    """Re-parse ``<agent>_input.md`` for the metadata node-id captured by
    ``_PATCHER_INPUT_META_RE``. Used by the patcher and detailer retry
    actions to recover ``source_node_id`` / ``target_node_id`` when the
    in-memory tracking entry has been drained by auto-apply.
    """
    wt = self.session_path
    if not wt or not Path(wt).is_dir():
        return None
    input_path = Path(wt) / f"{agent}_input.md"
    if not input_path.is_file():
        return None
    try:
        text = input_path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = self._PATCHER_INPUT_META_RE.search(text)
    return m.group(1) if m else None
```

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_app.py` — add
  `_pick_completed_agent_for_retry` and `_recover_node_id_from_input`;
  rewrite the four `action_retry_<role>_apply` methods.

No other files. No new imports — `Path` and `read_yaml` are already in scope.

## Verification

Manual TUI re-run, mirroring t787 item #3 and the t837 verification:

1. Open a brainstorm session; trigger a patcher / synthesizer / detailer
   agent through to successful auto-apply, so the resulting node exists.
2. Corrupt that agent's `<agent>_output.md` in the session worktree (so a
   fresh apply would fail and surface the banner).
3. Press the role's retry binding (`ctrl+shift+r` patcher, `ctrl+shift+y`
   synthesizer, `ctrl+shift+d` detailer).
4. Expect the apply banner with the corresponding
   `ait brainstorm apply-<role> <task> <agent>[ <node>]` CLI hint —
   previously this was a silent no-op.
5. Repeat (1)–(4) for the explorer role (`ctrl+shift+x`) to confirm the
   refactor didn't regress t837's fix.

Negative case: with no agents of a given role in the worktree, the retry
binding now shows `No completed <role> agents to retry.` rather than a
silent no-op.

See Step 9 (Post-Implementation) of the task-workflow skill for cleanup,
archival, and merge steps.

## Final Implementation Notes

- **Actual work done:** Added `_pick_completed_agent_for_retry(role)` and
  `_recover_node_id_from_input(agent)` helpers on `BrainstormApp`, then
  rewrote the four `action_retry_<role>_apply` methods (explorer, patcher,
  synthesizer, detailer) to scan the worktree via the new helper instead
  of reading the in-memory tracking container. Patcher/detailer fall back
  to `_input.md` re-parsing (via `_PATCHER_INPUT_META_RE`) when the
  drained tracking dict no longer has the node-id. All four call sites now
  surface a `notify("No completed <role> agents to retry.")` instead of a
  silent no-op when the worktree has no Completed agent of that role.
- **Deviations from plan:** None. The plan was executed as written.
- **Issues encountered:** None.
- **Key decisions:** Refactored `action_retry_explorer_apply` (already
  correct per t837) onto the new shared helper rather than leaving it as
  the lone inline implementation — matched the task description's
  "share one implementation" suggestion and avoids drift between the four
  retry actions.
- **Upstream defects identified:** None.

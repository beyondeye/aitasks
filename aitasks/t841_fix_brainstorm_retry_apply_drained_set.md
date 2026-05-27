---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [verification, bug]
created_at: 2026-05-27 11:06
updated_at: 2026-05-27 11:06
---

## Origin

Spawned from t837 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_app.py:4001 — action_retry_patcher_apply silently no-ops once self._patcher_sources is drained by successful auto-apply, so ctrl+shift+r cannot exercise the patcher banner path on a previously-applied patcher.`
- `.aitask-scripts/brainstorm/brainstorm_app.py:4315 — action_retry_synthesizer_apply has the same drained-set early return for ctrl+shift+y.`
- `.aitask-scripts/brainstorm/brainstorm_app.py:4490 — action_retry_detailer_apply has the same drained-set early return.`

## Diagnostic context

t837 fixed the explorer-side variant of this bug: `action_retry_explorer_apply` returned silently when `self._explorer_agents` was empty, which happens after every successful auto-apply (`brainstorm_app.py:4153`: `self._explorer_agents.discard(agent_name)`). The fix rewrote the action to scan the worktree (`explorer_*_status.yaml`) for Completed agents and force-apply the most recent one.

The patcher (`self._patcher_sources`), synthesizer (`self._synthesizer_agents`), and detailer (`self._detailer_targets`) retry actions all follow the same pattern: their tracking sets are populated by the poll loop and drained on successful apply, then never re-populated by `_scan_existing_*` because `_*_needs_apply` returns False once the resulting node exists. Pressing `ctrl+shift+r`/`y`/<detailer-binding> after auto-apply is therefore a no-op, identical to the t787 item #3 failure.

## Suggested fix

Apply the same worktree-scan pattern used in t837 to the three sister actions. A single helper that takes (agent_prefix, candidates_callback) and returns the most-recently-statused Completed agent name (or None) would let all four retry actions share one implementation. The patcher variant additionally needs to recover `source_node_id` from the agent's `_input.md` (existing `_PATCHER_INPUT_META_RE` does this in `_scan_existing_patchers`).

Verification: manual TUI re-run mirroring t787 item #3 — corrupt a previously-applied `<agent>_output.md`, press the retry binding, expect the apply banner with the corresponding `ait brainstorm apply-<role> ...` CLI hint.

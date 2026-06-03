---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
created_at: 2026-06-03 15:52
updated_at: 2026-06-03 15:52
---

## Context

Foundational child of t929. Today `module_decompose` in the `ait brainstorm` TUI runs **one-shot** and auto-applies its `MODULE_NODE` output to the graph with no review gate — the only recourse is error+retry, and changing module boundaries means cascade-delete + full redo. This child inserts a **preview/steer/accept gate** between decomposer completion and graph application. It is the foundation for the sibling enhancements: t929_2 (prompt-driven inference) needs this gate so the user can review agent-*proposed* names before they commit.

Reference behavior (verified against current code): the explore/patch ops auto-apply too, but at least expose a manual retry binding (`ctrl+shift+x` / `ctrl+shift+r`) after apply; module ops have no manual retry and no preview at all.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `apply_module_decomposer_output()` (~line 1413) — factor out a **parse-only** helper.
  - `_module_decomposer_needs_apply()` gate (~line 1176) — reused to decide when a result is ready for review.
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `_config_module_decompose()` (~line 6698) — add the review-mode config checkbox.
  - `_try_apply_module_agent_if_needed()` (~line 4892, 5-s poll timer) — gate auto-apply behind review state.
  - New modal screen `ModulePreviewScreen` for Accept / Re-run(steer) / Cancel.
- `.aitask-scripts/brainstorm/brainstorm_crew.py`
  - `_assemble_input_module_decomposer()` (~line 510) — reused to pass steer `instructions` on Re-run.
- Tests: `tests/test_brainstorm_apply_module_ops.py` (mirror), and integration `tests/test_brainstorm_module_ops_integration.py`.

## Reference Files for Patterns

- `brainstorm_app.py` `action_retry_*_apply` (~3188; ctrl+shift+x/r bindings) — manual re-apply pattern for explore/patch.
- `brainstorm_app.py` status-tab output-tail preview (~5625-5681) — how agent `_output.md` content is surfaced post-completion.
- Existing `ModalScreen` subclasses in `brainstorm_app.py` — follow the established modal pattern (bindings, dismiss, result return).

## Implementation Plan

1. **Parse-only helper.** Extract `parse_module_decomposer_output(output_text)` from `apply_module_decomposer_output()` returning a list of structured proposed blocks `{module_name, node_yaml, proposal_excerpt, node_id?}` WITHOUT mutating the graph. `apply_module_decomposer_output()` then consumes the parsed blocks (no behavior change when review is off).
2. **Config toggle.** Add checkbox `chk_review_before_apply` to `_config_module_decompose()`, default **on**. Thread its value into the op config the poller can read.
3. **Preview modal.** Implement `ModulePreviewScreen(ModalScreen)` listing each proposed module (name, node id, proposal excerpt) with three actions: **Accept** (dismiss → apply), **Re-run** (collect a steer text, dismiss → re-dispatch), **Cancel** (dismiss → discard, graph untouched).
4. **Gate the poller.** In `_try_apply_module_agent_if_needed()`: when the agent is Completed, `_module_decomposer_needs_apply()` is true, AND review mode is on AND the result is not yet accepted → set a `pending_review` state and push `ModulePreviewScreen` instead of applying. On Accept → call the existing apply path. On Re-run → re-dispatch via the decomposer registration, appending the steer text to the Decomposition Plan `instructions` (`_assemble_input_module_decomposer()`). On Cancel → clear state, discard output. When review mode is **off**, behavior is unchanged (auto-apply).
5. **State hygiene.** Ensure the `pending_review` flag is cleared on accept/cancel/error so the poller does not re-prompt every 5 s; reuse `_module_apply_errors` for the error path.

## Verification Steps

- Unit (`tests/test_brainstorm_apply_module_ops.py`): parse-only returns correct blocks without graph mutation; accept path applies identically to today; review-off preserves auto-apply; re-run re-dispatches with appended instructions.
- Integration (`tests/test_brainstorm_module_ops_integration.py`): end-to-end decompose with review-on stops at preview; accept commits nodes; cancel leaves graph intact.
- Manual: `ait brainstorm <task>`, press `A` on a node → Module Decompose with review on → confirm preview appears, Accept/Re-run/Cancel behave; toggle review off → confirms auto-apply.
- `shellcheck` N/A (Python); run the brainstorm test suite.

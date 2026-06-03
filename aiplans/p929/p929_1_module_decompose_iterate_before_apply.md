---
Task: t929_1_module_decompose_iterate_before_apply.md
Parent Task: aitasks/t929_brainstorm_decompose_prompt_iterate_carveout_and_docs.md
Sibling Tasks: aitasks/t929/t929_2_module_decompose_prompt_driven_inference.md, aitasks/t929/t929_3_brainstorm_tui_code_verified_docs.md
Archived Sibling Plans: aiplans/archived/p929/p929_*_*.md
Worktree: aiwork/t929_1_module_decompose_iterate_before_apply
Branch: aitask/t929_1_module_decompose_iterate_before_apply
Base branch: main
---

# t929_1 — Iterate-before-apply: preview/steer/accept gate

## Goal

Insert a **review gate** between `module_decompose` agent completion and graph
application, replacing today's silent auto-apply. Foundation for t929_2
(agent-proposed names must be reviewable before they commit).

## Current state (verified)

- The 5-s poll timer `_try_apply_module_agent_if_needed()`
  (`brainstorm_app.py` ~4892) auto-applies the decomposer output once the agent
  is Completed and `_module_decomposer_needs_apply()`
  (`brainstorm_session.py` ~1176) passes. On success it notifies + reloads; on
  error it stores `_module_apply_errors[agent]`, sets a banner, retries next
  tick. **No preview, no accept gate.**
- `apply_module_decomposer_output()` (`brainstorm_session.py` ~1413) parses
  `MODULE_NODE` blocks and creates subgraph-root nodes parented on the source.
- explore/patch ops expose a manual retry binding (`ctrl+shift+x` /
  `ctrl+shift+r`, `action_retry_*_apply` ~3188) after auto-apply; module ops
  have neither preview nor manual retry.

## Implementation steps

1. **Parse-only helper** — `brainstorm_session.py`. Extract
   `parse_module_decomposer_output(output_text) -> list[dict]` from
   `apply_module_decomposer_output()`. Each block:
   `{module_name, node_yaml, proposal_excerpt, node_id?}`. No graph mutation.
   `apply_module_decomposer_output()` now consumes the parsed blocks (no
   behavior change when review is off). Keep the existing
   `_MODULE_NODE_BLOCK_RE` parsing.
2. **Config toggle** — `_config_module_decompose()` (`brainstorm_app.py` ~6698).
   Add `Checkbox("Review before apply", classes="chk_review_before_apply")`,
   default **on**. Thread its value into the op config the poller reads.
3. **Preview modal** — new `ModulePreviewScreen(ModalScreen)` in
   `brainstorm_app.py` (follow existing `ModalScreen` subclasses for bindings /
   `dismiss(result)` shape). Lists proposed modules (name, node id, proposal
   excerpt) with actions **Accept** / **Re-run (steer)** / **Cancel**.
4. **Gate the poller** — `_try_apply_module_agent_if_needed()`. When Completed +
   `_module_decomposer_needs_apply()` + review on + not yet accepted: set a
   `pending_review` flag and push `ModulePreviewScreen` instead of applying.
   - **Accept** → existing `apply_module_decomposer_output()` path.
   - **Re-run** → re-dispatch the decomposer, appending the steer text to the
     Decomposition Plan `instructions` via `_assemble_input_module_decomposer()`
     (`brainstorm_crew.py` ~510).
   - **Cancel** → clear state, discard output, graph untouched.
   - Review **off** → unchanged auto-apply.
5. **State hygiene** — clear `pending_review` on accept/cancel/error so the
   poller does not re-prompt every tick; reuse `_module_apply_errors` for errors.

## Verification

- Unit (`tests/test_brainstorm_apply_module_ops.py`): parse-only returns correct
  blocks w/o mutation; accept applies identically to today; review-off preserves
  auto-apply; re-run re-dispatches with appended instructions.
- Integration (`tests/test_brainstorm_module_ops_integration.py`): review-on
  stops at preview; accept commits nodes; cancel leaves graph intact.
- Manual: `ait brainstorm <task>` → `A` on a node → Module Decompose with review
  on → preview appears; Accept/Re-run/Cancel behave; toggle off → auto-applies.

See parent task **Step 9 (Post-Implementation)** for cleanup, archival, merge.

## Notes for sibling tasks

- `parse_module_decomposer_output()` and `ModulePreviewScreen` are the surfaces
  t929_2 builds on (agent-proposed names render in the preview).

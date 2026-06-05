---
Task: t929_1_module_decompose_iterate_before_apply.md
Parent Task: aitasks/t929_brainstorm_decompose_prompt_iterate_carveout_and_docs.md
Sibling Tasks: aitasks/t929/t929_2_module_decompose_prompt_driven_inference.md, aitasks/t929/t929_3_brainstorm_tui_code_verified_docs.md
Archived Sibling Plans: aiplans/archived/p929/p929_*_*.md
Worktree: aiwork/t929_1_module_decompose_iterate_before_apply
Branch: aitask/t929_1_module_decompose_iterate_before_apply
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-05 10:13
---

# t929_1 — Iterate-before-apply: preview/steer/accept gate

## Goal

Insert a **review gate** between `module_decompose` agent completion and graph
application, replacing today's silent auto-apply. Foundation for t929_2
(agent-proposed names must be reviewable before they commit).

## Current state (verified 2026-06-05)

- The 5-s poll timer `_try_apply_module_agent_if_needed()`
  (`brainstorm_app.py:4892`) auto-applies the decomposer output once the agent
  is Completed and `_module_decomposer_needs_apply()`
  (`brainstorm_session.py:1176`) passes. Poll timer is installed by
  `_ensure_module_poll_timer()` (`brainstorm_app.py:4806`) via
  `set_interval(5, self._poll_module_agents)`. On success it notifies + reloads;
  on error it stores `_module_apply_errors[agent]`, sets a banner, retries next
  tick. **No preview, no accept gate.** Dispatch in
  `_try_apply_module_agent_if_needed()` routes `module_decomposer_*` →
  `apply_module_decomposer_output()`.
- `apply_module_decomposer_output()` (`brainstorm_session.py:1413`) parses
  `MODULE_NODE` blocks (regex `_MODULE_NODE_BLOCK_RE`, `brainstorm_session.py:1170`;
  block extract via `_extract_block()` :386, YAML via `_tolerant_yaml_load()` :441)
  and **mutates the graph** — `create_node()` per module, `set_head(..., module=)`,
  `update_operation()`, and optional `_create_linked_module_task()` when
  `link_to_task` is set.
- explore/patch ops expose a manual retry binding (`ctrl+shift+x` /
  `ctrl+shift+r`, methods `action_retry_explorer_apply()` :4978 /
  `action_retry_patcher_apply()` :4636; bindings declared :3189-3196) after
  auto-apply; module ops have neither preview nor manual retry.
- Config is collected in `_config_module_decompose()` (`brainstorm_app.py:6698`)
  into a plain `dict` `self._wizard_config` with keys `modules`, `from_sections`,
  `link_to_task`, `instructions`; consumed at `register_module_decomposer()`
  dispatch (`brainstorm_app.py:7418`).
- `_assemble_input_module_decomposer()` (`brainstorm_crew.py:510`) appends the
  free-text `instructions` as a `## Decomposition Plan` section (:550-551). The
  agent template `templates/module_decomposer.md` reads `_input.md` and treats
  the Decomposition Plan as "optional decomposition instructions." There is
  **today no notion of a revision/steer** — re-running would just resend the same
  `instructions`.
- `register_module_decomposer()` (`brainstorm_crew.py:849`) creates a new agent
  (new sequence number) each call, so re-running is a fresh dispatch; assigned
  module node IDs are minted per call (:864-868).

## Implementation steps

1. **Parse-only helper** — `brainstorm_session.py`. Extract
   `parse_module_decomposer_output(output_text) -> list[dict]` from
   `apply_module_decomposer_output()`. Each block:
   `{module_name, node_yaml, proposal_excerpt, node_id?}`. No graph mutation.
   `apply_module_decomposer_output()` now consumes the parsed blocks (no
   behavior change when review is off). Keep the existing
   `_MODULE_NODE_BLOCK_RE` parsing and reuse `_extract_block()` /
   `_tolerant_yaml_load()`.
2. **Config toggle** — `_config_module_decompose()` (`brainstorm_app.py:6698`).
   Add `Checkbox("Review before apply", classes="chk_review_before_apply")`,
   default **on**. Thread its value into the `self._wizard_config` dict (new key
   `review_before_apply`) the poller reads.
3. **Preview modal** — new `ModulePreviewScreen(ModalScreen)` in
   `brainstorm_app.py` (follow existing `ModalScreen` subclasses — e.g.
   `NodeActionSelectModal`, `CompareNodeSelectModal` — for `Binding("escape",
   "action_cancel", ...)` / `self.dismiss(result)` shape). Lists proposed
   modules (name, node id, proposal excerpt) with actions **Accept** /
   **Re-run (steer)** / **Cancel**. The Re-run action collects free-text steer
   input and returns it with the dismiss result.
4. **Gate the poller** — `_try_apply_module_agent_if_needed()`. When Completed +
   `_module_decomposer_needs_apply()` + review on + not yet accepted: set a
   `pending_review` flag and push `ModulePreviewScreen` instead of applying.
   - **Accept** → existing `apply_module_decomposer_output()` path.
   - **Re-run** → re-dispatch the decomposer via `register_module_decomposer()`
     with the steer text (see step 6 for the composition rule).
   - **Cancel** → clear state, discard output, graph untouched.
   - Review **off** → unchanged auto-apply.
5. **State hygiene** — clear `pending_review` on accept/cancel/error so the
   poller does not re-prompt every tick; reuse `_module_apply_errors` for errors.

6. **Re-run steering composition (explicit, unambiguous rule).** Re-run must NOT
   silently replace or blindly concatenate the operator's text. The original
   Decomposition Plan from the first run is preserved; the steering is added as a
   **separate, clearly-labelled, authoritative override** so both the agent and a
   later reader can see exactly how the two compose.

   - **Do not overload `instructions`.** Add a new explicit parameter
     `steer: str = ""` (a revision note) to both
     `_assemble_input_module_decomposer()` (`brainstorm_crew.py:510`) and
     `register_module_decomposer()` (`brainstorm_crew.py:849`). `instructions`
     keeps carrying the original Decomposition Plan unchanged.
   - **Assembled input layout when `steer` is non-empty** — after the existing
     `## Decomposition Plan` section, emit a new section:

     ```markdown
     ## Steering (revision N — OVERRIDES the Decomposition Plan above)

     A previous decomposition was already produced from the inputs above
     (including the Decomposition Plan). The operator reviewed that attempt and
     is requesting the revisions below.

     Composition rule: the Decomposition Plan above still applies, EXCEPT where
     these steering instructions contradict it. On any conflict, the steering
     instructions WIN. Treat this as a correction of the previous attempt, not a
     fresh unrelated request. Where multiple revisions are listed, a later
     revision overrides an earlier one.

     ### Revision N
     <operator steer text>
     ```

     Revisions accumulate in order across repeated re-runs (Revision 1, 2, …),
     and the rule "later revisions override earlier ones" makes the precedence
     between successive steers explicit too. The original `instructions` text is
     never mutated.
   - **Carry the revision state** on the op config / pending-review state so each
     Re-run appends the next revision and re-dispatches with the full ordered
     list. (Module node IDs are re-minted per `register_module_decomposer()` call
     — expected for a fresh attempt.)
   - **Template update** — `templates/module_decomposer.md`: under `## Input`,
     replace "Optional decomposition instructions." with a note that the input
     may also contain a `## Steering` section, and add a `## Rules` entry stating
     the composition rule verbatim: *the Decomposition Plan applies except where
     Steering contradicts it; on conflict, Steering wins; later revisions
     override earlier ones.* This keeps the override contract authoritative on
     the agent side, not just in the assembled prose.

## Verification

- Unit (`tests/test_brainstorm_apply_module_ops.py`): parse-only returns correct
  blocks w/o mutation; accept applies identically to today; review-off preserves
  auto-apply.
- Unit (assembly): `_assemble_input_module_decomposer(..., steer="")` is
  byte-identical to today (no Steering section, no behavior change when not
  steering); with `steer` set, the output **retains** the original
  `## Decomposition Plan` AND adds a `## Steering` section containing the
  override/precedence wording and the revision body; two accumulated revisions
  render as ordered `### Revision 1` / `### Revision 2`.
- Integration (`tests/test_brainstorm_module_ops_integration.py`): review-on
  stops at preview; accept commits nodes; cancel leaves graph intact; re-run
  re-dispatches a new decomposer agent whose `_input.md` carries the steering
  override section.
- Manual: `ait brainstorm <task>` → `A` on a node → Module Decompose with review
  on → preview appears; Accept/Re-run/Cancel behave; a Re-run with steer text
  produces a revised decomposition that honors the override; toggle off →
  auto-applies.

See parent task **Step 9 (Post-Implementation)** for cleanup, archival, merge.

## Notes for sibling tasks

- `parse_module_decomposer_output()` and `ModulePreviewScreen` are the surfaces
  t929_2 builds on (agent-proposed names render in the preview).
- The `steer`/revision composition rule (original plan preserved; steering
  overrides on conflict; later revisions win) is the established contract for any
  future re-run/iterate surface on module ops.

## Risk

### Code-health risk: medium
- Gating the load-bearing 5-s poll timer and introducing a `pending_review` state machine risks a re-prompt-every-tick loop if the flag is not cleared on accept/cancel/error · severity: medium · → mitigation: in-plan (step 5 State hygiene) + review-off auto-apply regression test
- Refactoring `apply_module_decomposer_output()` into a parse-only helper + consumer could shift behavior on the existing auto-apply path · severity: low · → mitigation: review-off parity test (existing suite)
- New `steer` parameter widens the `_assemble_input_module_decomposer()` / `register_module_decomposer()` signatures · severity: low · → mitigation: default `steer=""` keeps all existing call sites and assembled output byte-identical (asserted by the assembly test)

### Goal-achievement risk: low
- None identified — approach shape matches parent intent; every cited API/pattern (ModalScreen, config-dict threading, `instructions` carrier) verified present; the steering composition rule is now explicit on both the assembled-input and agent-template sides.

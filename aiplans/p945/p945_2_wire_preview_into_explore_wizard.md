---
Task: t945_2_wire_preview_into_explore_wizard.md
Parent Task: aitasks/t945_show_proposal_viewer_side_by_side_to_explore_and_decompose.md
Sibling Tasks: aitasks/t945/t945_1_reusable_proposal_preview_pane.md, aitasks/t945/t945_3_wire_preview_into_decompose_and_add_source_node_choice.md
Archived Sibling Plans: aiplans/archived/p945/p945_*_*.md
Worktree: aiwork/t945_2_wire_preview_into_explore_wizard
Branch: aitask/t945_2_wire_preview_into_explore_wizard
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-08 11:48
---

# t945_2 — Wire the preview pane into the explore wizard

## Context

Second child of t945. The explore wizard's config step collects a free-text
**Exploration Mandate** but shows no view of the proposal the user is writing
against. Use the reusable proposal-preview component built in t945_1
(`ProposalPreviewPane` + `_mount_config_with_preview`) to show the selected base
node's proposal side-by-side (input left / proposal+minimap right) with the
mandate input.

Depends on t945_1 (now landed — read its archived plan
`aiplans/archived/p945/p945_1_reusable_proposal_preview_pane.md`, esp. the
"Notes for sibling tasks" section, for the API contract).

## Plan verification (2026-06-08, verify path)

Re-checked all cited references against the current code after t945_1 landed
(+235 lines). Approach and API unchanged; only line numbers drifted:
- `_config_explore_no_node` → **`brainstorm_app.py:7048-7055`** (was 6813). Mounts
  `Base Node:` label, `Exploration Mandate` label, `TextArea("")`,
  `CycleField("Parallel explorers", ["1","2","3","4"], initial="2")`, and the
  `Next ▶` button (`classes="btn_actions_next"`) directly into `container`.
- `_mount_config_with_preview(container, left_builder, proposal_text)` →
  **`brainstorm_app.py:6954`** — mounts a `Horizontal.config_preview_split`
  (left `VerticalScroll.config_preview_left` + `ProposalPreviewPane`), defers
  `left_builder(left)` + `pane.populate(proposal_text)` via `call_after_refresh`.
  **No config step calls it yet** — this task is its first caller.
- `_actions_collect_config` explore branch → **`brainstorm_app.py:7383-7392`**
  (was 7148-7157): reads `container.query_one(TextArea)` (mandate) and
  `container.query_one(CycleField)` (parallel) against `#actions_content`
  recursively.
- `read_proposal` is **already imported** in `brainstorm_app.py` (line 64, from
  `brainstorm.brainstorm_dag`) and used throughout — no new import needed.
  Definition at `brainstorm_dag.py:514`.

## Existing pieces to reuse
- `_mount_config_with_preview` + `ProposalPreviewPane` (from t945_1,
  `brainstorm_app.py:6954` / `:908`).
- `read_proposal` (already imported; `brainstorm_dag.py:514`).
- Current explore config: `_config_explore_no_node` (`brainstorm_app.py:7048`).

## Implementation steps

1. **Refactor `_config_explore_no_node` (`brainstorm_app.py:7048`):** move the
   existing mounts — the `Exploration Mandate` label + `TextArea`, the
   `CycleField("Parallel explorers", …)`, and the `Next ▶` button — into a
   `left_builder(left)` closure that mounts them into the left pane (verbatim,
   so `_actions_collect_config`'s recursive `query_one(TextArea)` /
   `query_one(CycleField)` against `#actions_content` keep resolving).
2. Keep the `Base Node:` label in the left-pane header for context (mount it
   first inside `left_builder`).
3. Resolve the base node and its proposal, then call the helper:
   ```python
   node_id = self._wizard_config.get("_selected_node", "?")
   try:
       proposal = read_proposal(self.session_path, node_id)
   except Exception:
       proposal = "*No proposal found.*"

   def left_builder(left):
       left.mount(Label(f"[bold]Base Node:[/] {node_id}"))
       left.mount(Label("[bold]Exploration Mandate[/]"))
       left.mount(TextArea(""))
       left.mount(CycleField("Parallel explorers", ["1", "2", "3", "4"], initial="2"))
       left.mount(Button("Next ▶", variant="primary", classes="btn_actions_next"))

   self._mount_config_with_preview(container, left_builder, proposal)
   ```
   (Mirror the `read_proposal` try/except guard already used at
   `brainstorm_app.py:6300`/`6375`/`7350` so a missing proposal degrades to a
   placeholder rather than raising.)

## Collector invariance (must verify, do not regress)
`_actions_collect_config` explore branch (`brainstorm_app.py:7383-7392`) reads
`container.query_one(TextArea)` (mandate) and `container.query_one(CycleField)`
(parallel) against `#actions_content`. These are single-match queries — they
raise if a second `TextArea`/`CycleField` appears. t945_1 guarantees
`ProposalPreviewPane` adds neither (only `Markdown` + minimap `VerticalScroll`),
so the queries stay unambiguous. Confirm by running an explore through to the
confirm step.

## Verification
- Launch `ait brainstorm`; run explore → select a node → config step. Confirm:
  the selected node's proposal renders on the right with a working minimap (Tab
  focus, Enter/↑↓ section jump); the ratio-cycle key (`ctrl+b`) cycles the split
  width; submitting the mandate (`Next ▶`) proceeds to confirm exactly as
  before.
- Confirm `_actions_collect_config` collects mandate + parallel without
  `query_one` ambiguity errors (drive an explore through to the confirm step).
- Run any touched brainstorm tests under `tests/` (e.g.
  `tests/test_brainstorm_proposal_preview.py`).

## Risk

### Code-health risk: low
- None identified. The change is a localized refactor of a single method
  (`_config_explore_no_node`, ~8 lines) that reuses the purpose-built,
  already-landed-and-tested `_mount_config_with_preview` helper. Blast radius is
  one method; the pattern is exactly what the helper was designed for; the one
  contract to preserve (no second `TextArea`/`CycleField` in the collected
  container) is guaranteed by t945_1 and re-checked in this plan's Collector
  invariance section.

### Goal-achievement risk: low
- None identified. The goal (proposal side-by-side with the mandate input) maps
  directly onto t945_1's documented sibling-task API, which was verified
  standalone. Requirement coverage is complete; the only behavior needing a
  human eye (minimap nav / ratio cycle / focus inside a live TUI) is covered by
  this task's Verification steps and the parent's manual-verification flow.

_No separate before/after mitigation tasks: both dimensions are low with no
identified risk, and the one invariant is verified inline. No spike or
characterization-test task is warranted._

## Reference to parent workflow
On completion follow task-workflow Step 8 (review) → Step 9 (archival).

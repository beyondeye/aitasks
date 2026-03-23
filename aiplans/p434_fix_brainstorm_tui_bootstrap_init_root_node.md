---
Task: t434_fix_brainstorm_tui_bootstrap_init_root_node.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix brainstorm TUI bootstrap — create root node on init (t434)

## Context

The brainstorm TUI initialization creates empty session files but no initial root node. This leaves users deadlocked — all 5 design operations (explore, compare, hybridize, detail, patch) require selecting existing nodes, but there are none. The architecture doc assumes `n000_init` exists as the root node, but no code creates it. Additionally, the task description (`initial_spec`) stored in `br_session.yaml` is never displayed in the TUI.

## Implementation

### 1. Create root node during session initialization

**File:** `.aitask-scripts/brainstorm/brainstorm_session.py` — `init_session()` (line 32)

After writing `br_graph_state.yaml` and `br_groups.yaml` (line 83), add:

- Import `create_node`, `set_head`, `next_node_id` from `.brainstorm_dag`
- Extract a one-line description from `initial_spec` (first non-frontmatter, non-empty line, truncated to ~80 chars)
- Call `create_node()` with:
  - `node_id`: `"n000_init"`
  - `parents`: `[]`
  - `description`: extracted one-liner
  - `dimensions`: `{}` (empty — user adds dimensions during exploration)
  - `proposal_content`: the full `initial_spec` text
  - `group_name`: `"bootstrap"`
- Call `set_head(wt, "n000_init")` to set it as HEAD
- Call `next_node_id(wt)` to increment counter to 1
- Set session status to `"active"` in the session data

### 2. Display task brief in TUI dashboard with modal for full text

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

**2a. Add a TaskBriefModal** (new ModalScreen class, near existing modals ~line 220):
- Takes `initial_spec: str` in constructor
- Renders a Textual `Markdown` widget inside a scrollable container, displaying the full `initial_spec` content
- Has a "Close" button and Escape binding to dismiss

**2b. Add brief summary to dashboard** — in `_update_session_status()` (line 722):
- Read `initial_spec` from `self.session_data`
- If non-empty, extract first ~2 non-empty lines as a truncated preview
- Append to the info_lines: `"Brief: <truncated>  [press b for full text]"`

**2c. Add `b` key binding** for opening the full brief:
- Add `b` key handler in `on_key()` (line 640)
- When pressed, push `TaskBriefModal(self.session_data.get("initial_spec", ""))`

### 3. Handle edge case — explore with zero nodes

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py` — `_config_explore()` (line 1007)

After `nodes = list_nodes(self.session_path)`, add:
- If `not nodes`: mount a label "No nodes available. Initialize the session first." and return

## Verification

1. Run `ait brainstorm init <task_num>` on a test task
2. Verify `br_nodes/n000_init.yaml` exists, `br_graph_state.yaml` has HEAD + next_node_id=1, session status=active
3. Launch TUI — Dashboard shows Nodes: 1, HEAD: n000_init, brief preview
4. Press `b` — full Markdown brief modal opens
5. Actions → Explore — n000_init appears as base node
6. Run: `shellcheck .aitask-scripts/aitask_brainstorm_init.sh`

## Post-Review Changes

### Change Request 1 (2026-03-23 10:30)
- **Requested by user:** TaskBriefModal should be a dialog, not a modal screen. Also, clicking explore in the Actions wizard doesn't advance to the next step.
- **Changes made:**
  1. Removed `TaskBriefModal` (ModalScreen) entirely. Instead, pressing `b` shows the full brief inline in the dashboard's detail pane via `_show_brief_in_detail()`.
  2. Added `OperationRow.Activated` message (Textual Message subclass) + `on_click` posts it. App handles `on_operation_row_activated()` to advance wizard on mouse click — same logic as Enter key handler. Works for both step 1 (operation selection) and step 2 (node selection).
  3. Imported `Message` from `textual.message`.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`

## Final Implementation Notes

- **Actual work done:** All three original fixes plus two post-review fixes. Root node creation works. Brief shows inline (not modal). Wizard responds to both keyboard Enter and mouse clicks.
- **Deviations from plan:** Brief display changed from ModalScreen to inline detail pane update. Wizard click handling added (not in original plan, was a pre-existing UX gap exposed by root node fix).
- **Issues encountered:** Wizard click issue was pre-existing — the wizard only responded to Enter key. With root node now being created, users could reach the wizard for the first time after init and discovered the click gap.
- **Key decisions:** Brief preview in dashboard joins first 2 non-empty/non-frontmatter lines with `" | "` separator, truncated at 100 chars. Root node description uses first non-frontmatter line of `initial_spec`, truncated at 80 chars with `…`. User suggested refactoring task detail viewing into a shared library for board + brainstorm TUI — deferred to a follow-up task.

## Step 9 Reference

After implementation, proceed to Step 9 (Post-Implementation) for commit, archival, and push.

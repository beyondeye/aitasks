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

## Step 9 Reference

After implementation, proceed to Step 9 (Post-Implementation) for commit, archival, and push.
